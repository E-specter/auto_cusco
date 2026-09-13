"""Construccion del mensaje sobre el motor de mapeo (RF-MM-14, RF-MM-16, RF-MM-19).

El motor de mapeo (RF-12) no se modifica: el conector le pasa un contexto de
fila derivado con campos propios y una plantilla por segmento:

    [@titular_8] + parte 1 + [@vencimiento] + parte 2

`[whatsapp]` se reemplaza por el enlace antes de compilar. Como las partes no
pueden contener `[@` (se valida al guardar), el texto del usuario nunca se
interpreta como referencia a un campo.
"""

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from app.core.entities.mapeo import CampoSalida, DefinicionCarga
from app.core.entities.mowa_mes import (
    FORMATO_VENCIMIENTO,
    LARGO_ADVERTENCIA,
    LARGO_MAXIMO,
    LARGO_MAXIMO_NOMBRE_SPEECH,
    LARGO_NUMERO_WHATSAPP,
    LARGO_TITULAR,
    LARGO_VENCIMIENTO,
    PREFIJO_WHATSAPP,
    RANGOS_SEGMENTO,
    VARIABLE_WHATSAPP,
    CodigoMowaMes,
    DatosSpeech,
    FaltaWhatsapp,
    LargoSegmento,
    PartesSegmento,
    ProblemaSpeech,
    Segmento,
)
from app.core.services.gestiones_digitales.supervision import numero_valido
from app.core.services.mapeo_campos.generador import GeneradorCargas

CAMPO_MENSAJE = "mensaje"
CAMPOS_CONTEXTO = ("titular_8", "vencimiento", "whatsapp")
_REFERENCIA = "[@"
_TITULAR_EJEMPLO = "X" * LARGO_TITULAR
_VENCIMIENTO_EJEMPLO = "dd/mm/yyyy"


def enlace_whatsapp(numero: str) -> str:
    return f"{PREFIJO_WHATSAPP}{numero}"


def usa_whatsapp(partes: PartesSegmento) -> bool:
    return VARIABLE_WHATSAPP in partes.parte_1 or VARIABLE_WHATSAPP in partes.parte_2


def codigo_por_largo(largo: int) -> CodigoMowaMes | None:
    if largo > LARGO_MAXIMO:
        return CodigoMowaMes.MENSAJE_EXCEDE_160
    if largo > LARGO_ADVERTENCIA:
        return CodigoMowaMes.MENSAJE_EXCEDE_150
    return None


def limpiar(datos: DatosSpeech) -> DatosSpeech:
    """Recorta solo el nombre: los espacios de las partes son parte del mensaje."""
    return DatosSpeech(nombre=datos.nombre.strip(), partes=datos.partes)


def problemas_de(datos: DatosSpeech) -> tuple[ProblemaSpeech, ...]:
    problemas: list[ProblemaSpeech] = []
    if not 1 <= len(datos.nombre.strip()) <= LARGO_MAXIMO_NOMBRE_SPEECH:
        problemas.append(
            ProblemaSpeech(
                None,
                "nombre",
                f"El nombre debe tener entre 1 y {LARGO_MAXIMO_NOMBRE_SPEECH} caracteres",
            )
        )
    presentes = [partes.segmento for partes in datos.partes]
    faltan = [r.segmento.value for r in RANGOS_SEGMENTO if r.segmento not in presentes]
    repetidos = sorted({s.value for s in presentes if presentes.count(s) > 1})
    if faltan or repetidos:
        detalle = "Cada segmento debe aparecer una vez"
        if faltan:
            detalle += f"; faltan: {', '.join(faltan)}"
        if repetidos:
            detalle += f"; repetidos: {', '.join(repetidos)}"
        problemas.append(ProblemaSpeech(None, "segmentos", detalle))
    for partes in datos.partes:
        for campo, texto in (("parte_1", partes.parte_1), ("parte_2", partes.parte_2)):
            if _REFERENCIA in texto:
                problemas.append(
                    ProblemaSpeech(partes.segmento, campo, "El texto no puede contener '[@'")
                )
    return tuple(problemas)


def contexto_fila(
    titular: str | None, vencimiento: date | None, whatsapp: str | None
) -> dict[str, Any]:
    """Campos derivados del producto que usa la plantilla del mensaje."""
    return {
        "titular_8": titular[:LARGO_TITULAR] if titular else None,
        "vencimiento": vencimiento.strftime(FORMATO_VENCIMIENTO) if vencimiento else None,
        "whatsapp": enlace_whatsapp(whatsapp) if whatsapp else None,
    }


def plantilla_mensaje(partes: PartesSegmento, whatsapp: str | None) -> str:
    """Plantilla del motor de mapeo de un segmento. FaltaWhatsapp si le falta el numero."""
    if usa_whatsapp(partes) and not whatsapp:
        raise FaltaWhatsapp((partes.segmento,))
    enlace = enlace_whatsapp(whatsapp) if whatsapp else ""
    parte_1 = partes.parte_1.replace(VARIABLE_WHATSAPP, enlace)
    parte_2 = partes.parte_2.replace(VARIABLE_WHATSAPP, enlace)
    return f"[@titular_8]{parte_1}[@vencimiento]{parte_2}"


class ConstructorMensajes:
    """Compila una vez la plantilla de cada segmento y arma mensajes para muchos productos.

    Sin numero de WhatsApp, los segmentos que lo usan quedan sin compilar:
    pedirles un mensaje lanza FaltaWhatsapp. Asi una campana cuyos productos no
    caen en esos segmentos se puede generar igual.
    """

    def __init__(self, partes: Sequence[PartesSegmento], whatsapp: str | None) -> None:
        self._whatsapp = whatsapp
        self._generadores: dict[Segmento, GeneradorCargas] = {}
        self._sin_whatsapp: set[Segmento] = set()
        for segmento in partes:
            if usa_whatsapp(segmento) and not whatsapp:
                self._sin_whatsapp.add(segmento.segmento)
                continue
            definicion = DefinicionCarga(
                nombre=f"mowa_mes {segmento.segmento.value}",
                campos=(CampoSalida(CAMPO_MENSAJE, plantilla_mensaje(segmento, whatsapp)),),
            )
            self._generadores[segmento.segmento] = GeneradorCargas(definicion, CAMPOS_CONTEXTO)

    def requiere_whatsapp_faltante(self, segmento: Segmento) -> bool:
        return segmento in self._sin_whatsapp

    def mensaje(self, segmento: Segmento, contexto: Mapping[str, Any]) -> str:
        if segmento in self._sin_whatsapp:
            raise FaltaWhatsapp((segmento,))
        fila, _ = self._generadores[segmento].generar_fila(contexto, 1)
        return fila[CAMPO_MENSAJE]

    def mensaje_de(self, segmento: Segmento, titular: str | None, vencimiento: date | None) -> str:
        return self.mensaje(segmento, contexto_fila(titular, vencimiento, self._whatsapp))


def previsualizar(
    partes: Sequence[PartesSegmento], whatsapp: str | None
) -> tuple[LargoSegmento, ...]:
    """Largo maximo de cada segmento: titular de 8, fecha de 10 y el enlace de WhatsApp.

    El largo se calcula sobre el texto aunque las partes tengan problemas, para
    que quien edita vea el largo mientras corrige. El enlace mide lo mismo con
    cualquier numero valido, asi que el largo no depende de que haya uno.
    """
    por_segmento = {p.segmento: p for p in partes}
    largo_enlace = len(PREFIJO_WHATSAPP) + LARGO_NUMERO_WHATSAPP
    resultado: list[LargoSegmento] = []
    for rango in RANGOS_SEGMENTO:
        segmento = por_segmento.get(rango.segmento)
        if segmento is None:
            continue
        texto = segmento.parte_1 + segmento.parte_2
        cantidad_variables = texto.count(VARIABLE_WHATSAPP)
        largo = (
            LARGO_TITULAR
            + LARGO_VENCIMIENTO
            + len(texto)
            - cantidad_variables * (len(VARIABLE_WHATSAPP) - largo_enlace)
        )
        con_whatsapp = cantidad_variables > 0
        ejemplo = None
        if not con_whatsapp or whatsapp:
            enlace = enlace_whatsapp(whatsapp) if whatsapp else ""
            ejemplo = (
                _TITULAR_EJEMPLO
                + segmento.parte_1.replace(VARIABLE_WHATSAPP, enlace)
                + _VENCIMIENTO_EJEMPLO
                + segmento.parte_2.replace(VARIABLE_WHATSAPP, enlace)
            )
        resultado.append(
            LargoSegmento(
                rango=rango,
                usa_whatsapp=con_whatsapp,
                largo_maximo=largo,
                codigo=codigo_por_largo(largo),
                ejemplo=ejemplo,
            )
        )
    return tuple(resultado)


def whatsapp_valido(numero: str) -> bool:
    """El numero de contacto sigue la misma regla de telefono (RF-02)."""
    return numero_valido(numero)
