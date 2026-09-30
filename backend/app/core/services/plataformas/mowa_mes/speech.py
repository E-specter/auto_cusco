"""Construccion del mensaje sobre el motor de texto enriquecido (RF-MM-14, RF-MM-16, RF-MM-19).

Cada segmento se convierte en una expresion del motor y se compila una vez:

    titular | primeros(8)  +  parte 1  +  fecha_vencimiento_cuota | formato_fecha  +  parte 2

y cada `[whatsapp]` de una parte pasa a ser la variable `whatsapp_contacto | enlace_whatsapp`.
La expresion se arma directamente con nodos, sin pasar por la sintaxis de texto del motor: las
partes pueden tener corchetes sueltos, `[whatsapp` sin cerrar o hasta un `[@`, y todo eso es texto
fijo que nunca se interpreta (`problemas_de` ademas rechaza `[@` al guardar).

El largo maximo de un segmento es la cota de su expresion (`Compilada.cota`).

`plantilla_mensaje` y `contexto_fila`, el camino de antes sobre el motor de mapeo (RF-12), quedan
en el codigo hasta cerrar M2 solo como referencia de la prueba de oro
(`tests/test_mowa_mes_speech_oro.py`): ya nada de produccion las llama.
"""

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from app.core.entities.mowa_mes import (
    FORMATO_VENCIMIENTO,
    LARGO_ADVERTENCIA,
    LARGO_MAXIMO,
    LARGO_MAXIMO_NOMBRE_SPEECH,
    LARGO_TITULAR,
    PREFIJO_WHATSAPP,
    RANGOS_SEGMENTO,
    VARIABLE_WHATSAPP,
    CodigoMowaMes,
    DatosSpeech,
    FaltaWhatsapp,
    LargoSegmento,
    MensajeNoGenerable,
    PartesSegmento,
    ProblemaSpeech,
    Segmento,
)
from app.core.entities.texto_enriquecido import (
    LIMITES,
    Expresion,
    LimitesExpresion,
    LlamadaFuncion,
    Nodo,
    NodoTexto,
    NodoVariable,
    Problema,
    TipoValor,
)
from app.core.services.gestiones_digitales.supervision import numero_valido
from app.core.services.texto_enriquecido import evaluador
from app.core.services.texto_enriquecido.evaluador import Compilada

CAMPO_MENSAJE = "mensaje"
CAMPOS_CONTEXTO = ("titular_8", "vencimiento", "whatsapp")
_REFERENCIA = "[@"
_TITULAR_EJEMPLO = "X" * LARGO_TITULAR
_VENCIMIENTO_EJEMPLO = "dd/mm/yyyy"

# Variables que la fila aporta al motor (RF-43): el conector las declara, el motor no lo conoce.
VARIABLE_TITULAR = "titular"
VARIABLE_VENCIMIENTO = "fecha_vencimiento_cuota"
VARIABLE_CONTACTO = "whatsapp_contacto"
VARIABLES_DEL_MENSAJE = {
    VARIABLE_TITULAR: TipoValor.TEXTO,
    VARIABLE_VENCIMIENTO: TipoValor.FECHA,
    VARIABLE_CONTACTO: TipoValor.TEXTO,
}
_PATRON_VENCIMIENTO = "dd/mm/aaaa"  # el FORMATO_VENCIMIENTO de siempre, con marcas legibles


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


def _texto_y_enlaces(texto: str) -> list[Nodo]:
    """El texto de una parte, con cada `[whatsapp]` convertido en la variable del enlace."""
    nodos: list[Nodo] = []
    for posicion, trozo in enumerate(texto.split(VARIABLE_WHATSAPP)):
        if posicion:
            nodos.append(NodoVariable(VARIABLE_CONTACTO, (LlamadaFuncion("enlace_whatsapp"),)))
        if trozo:
            nodos.append(NodoTexto(trozo))
    return nodos


def expresion_de(partes: PartesSegmento) -> Expresion:
    """La expresion de un segmento: titular 8, parte 1, fecha y parte 2 (RF-MM-14).

    Se arma con nodos, nunca por la sintaxis de texto: lo que el usuario escribio en las partes
    es texto fijo aunque tenga `[`, `]` o `[@`. Los espacios de los extremos se conservan.
    """
    return Expresion(
        (
            NodoVariable(VARIABLE_TITULAR, (LlamadaFuncion("primeros", (LARGO_TITULAR,)),)),
            *_texto_y_enlaces(partes.parte_1),
            NodoVariable(
                VARIABLE_VENCIMIENTO, (LlamadaFuncion("formato_fecha", (_PATRON_VENCIMIENTO,)),)
            ),
            *_texto_y_enlaces(partes.parte_2),
        )
    )


def _limites_de(expresion: Expresion) -> LimitesExpresion:
    """Los limites de tamano protegen de expresiones ajenas; esta la arma el propio conector.

    Un speech no tiene tope de largo al editarlo (el largo se mide y se advierte, RF-MM-19), asi
    que el motor no debe rechazar lo que antes se aceptaba: los topes se ajustan a la expresion.
    """
    literal = max((len(n.valor) for n in expresion.nodos if isinstance(n, NodoTexto)), default=0)
    return LimitesExpresion(
        nodos=max(LIMITES.nodos, len(expresion.nodos)),
        largo_literal=max(LIMITES.largo_literal, literal),
    )


def compilar_segmento(partes: PartesSegmento, whatsapp: str | None = None) -> Compilada:
    """Compila un segmento. Con `whatsapp`, el contacto es una constante de la campana: el enlace
    se arma y se valida una sola vez, aqui, y no en cada fila (B7). Sin numero no se pasa
    constante alguna: un segmento que no usa `[whatsapp]` compila igual que siempre."""
    expresion = expresion_de(partes)
    constantes = {VARIABLE_CONTACTO: whatsapp} if whatsapp else None
    return evaluador.compilar(
        expresion, VARIABLES_DEL_MENSAJE, _limites_de(expresion), constantes=constantes
    )


class ConstructorMensajes:
    """Compila una vez la expresion de cada segmento y arma mensajes para muchos productos.

    Sin numero de WhatsApp, los segmentos que lo usan quedan sin compilar:
    pedirles un mensaje lanza FaltaWhatsapp. Asi una campana cuyos productos no
    caen en esos segmentos se puede generar igual.

    El numero es una constante de la campana (B7): el enlace se evalua al compilar. Si da un
    problema (un numero fuera de RF-02, hoy inalcanzable), queda en ESE segmento y se lanza
    `MensajeNoGenerable` al pedirle un mensaje; el constructor y los demas segmentos no se ven
    afectados.
    """

    def __init__(self, partes: Sequence[PartesSegmento], whatsapp: str | None) -> None:
        self._compiladas: dict[Segmento, Compilada] = {}
        self._sin_whatsapp: set[Segmento] = set()
        self._no_generables: dict[Segmento, tuple[Problema, ...]] = {}
        for segmento in partes:
            if usa_whatsapp(segmento) and not whatsapp:
                self._sin_whatsapp.add(segmento.segmento)
                continue
            compilada = compilar_segmento(segmento, whatsapp)
            self._compiladas[segmento.segmento] = compilada
            if compilada.problemas_plegados:
                self._no_generables[segmento.segmento] = compilada.problemas_plegados

    def requiere_whatsapp_faltante(self, segmento: Segmento) -> bool:
        return segmento in self._sin_whatsapp

    def mensaje(self, segmento: Segmento, contexto: Mapping[str, Any]) -> str:
        """El mensaje de un contexto con `titular`, `fecha_vencimiento_cuota` y el contacto.

        Si el motor informa un problema (un WhatsApp fuera de RF-02, una fecha que no es fecha),
        lanza `MensajeNoGenerable`: un SMS sin enlace o con un hueco no puede salir en silencio. Con
        los datos que validan la configuracion y la campana, no ocurre.
        """
        if segmento in self._sin_whatsapp:
            raise FaltaWhatsapp((segmento,))
        if segmento in self._no_generables:
            raise MensajeNoGenerable(segmento, self._no_generables[segmento])
        resultado = self._compiladas[segmento].evaluar(contexto)
        if resultado.problemas:
            raise MensajeNoGenerable(segmento, resultado.problemas)
        return resultado.texto

    def mensaje_de(self, segmento: Segmento, titular: str | None, vencimiento: date | None) -> str:
        # El contacto es una constante ya plegada: la fila solo aporta titular y vencimiento.
        return self.mensaje(
            segmento, {VARIABLE_TITULAR: titular, VARIABLE_VENCIMIENTO: vencimiento}
        )


def previsualizar(
    partes: Sequence[PartesSegmento], whatsapp: str | None
) -> tuple[LargoSegmento, ...]:
    """Largo maximo de cada segmento: la cota de su expresion.

    Titular de 8, fecha de 10 y el enlace de WhatsApp (largo del prefijo mas 9). El largo se
    calcula sobre el texto aunque las partes tengan problemas, para que quien edita vea el largo
    mientras corrige. El enlace mide lo mismo con cualquier numero valido, asi que el largo no
    depende de que haya uno. El `ejemplo` sigue armandose con marcadores (`XXXXXXXX`,
    `dd/mm/yyyy`), no con valores evaluados.
    """
    por_segmento = {p.segmento: p for p in partes}
    resultado: list[LargoSegmento] = []
    for rango in RANGOS_SEGMENTO:
        segmento = por_segmento.get(rango.segmento)
        if segmento is None:
            continue
        largo = compilar_segmento(segmento).cota
        if largo is None:  # no ocurre: el titular, la fecha y el enlace siempre tienen cota
            raise ValueError(f"El segmento {rango.segmento.value} no tiene largo maximo")
        con_whatsapp = usa_whatsapp(segmento)
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
