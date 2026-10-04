"""Construccion del mensaje sobre el motor de texto enriquecido (RF-MM-14, RF-MM-16, RF-MM-19).

Una version del speech tiene dos formatos (`FormatoSpeech`):

- **v1** (estructura fija, incluido el Speech original): cada segmento se convierte en una
  expresion del motor y se compila una vez:

      titular | primeros(8)  +  parte 1  +  fecha_vencimiento_cuota | formato_fecha  +  parte 2

  y cada `[whatsapp]` de una parte pasa a ser la variable `whatsapp_contacto | enlace_whatsapp`.
  La expresion se arma directamente con nodos, sin pasar por la sintaxis de texto del motor: las
  partes pueden tener corchetes sueltos, `[whatsapp` sin cerrar o hasta un `[@`, y todo eso es
  texto fijo que nunca se interpreta (`problemas_de` ademas rechaza `[@` al guardar).
- **v2** (M2): una expresion del motor por segmento, guardada tal cual. `convertir_a_v2` arma la
  expresion que da exactamente el mismo mensaje que una v1.

El largo maximo de un segmento es la cota de su expresion (`Compilada.cota`). Una expresion v2
puede no tener cota (una variable cuyo largo depende del dato): se informa como "sin maximo
calculable" con su motivo, y el control por fila de los 160 caracteres sigue siendo sobre el mensaje
real.

Que variables usa un segmento se decide sobre sus nodos (`texto_enriquecido.uso`), nunca buscando un
nombre en el texto: una v1 siempre usa titular y fecha; una v2, solo si su expresion los usa.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date
from typing import Any

from app.core.entities.mowa_mes import (
    LARGO_ADVERTENCIA,
    LARGO_MAXIMO,
    LARGO_MAXIMO_NOMBRE_SPEECH,
    LARGO_TITULAR,
    PREFIJO_WHATSAPP,
    RANGOS_SEGMENTO,
    VARIABLE_WHATSAPP,
    CodigoMowaMes,
    DatosSpeech,
    ExpresionSegmento,
    FaltaWhatsapp,
    FormatoSpeech,
    LargoSegmento,
    MensajeNoGenerable,
    PartesSegmento,
    ProblemaSpeech,
    Segmento,
)
from app.core.entities.texto_enriquecido import (
    LIMITES,
    Expresion,
    ExpresionInvalida,
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
from app.core.services.texto_enriquecido.uso import variables_usadas

CAMPO_MENSAJE = "mensaje"
_REFERENCIA = "[@"
_TITULAR_EJEMPLO = "X" * LARGO_TITULAR
_VENCIMIENTO_EJEMPLO = "dd/mm/yyyy"
_FECHA_DE_EJEMPLO = date(2026, 10, 5)  # el ejemplo de una v2 se evalua con fecha de verdad

# Variables que la fila aporta al motor (RF-43): el conector las declara, el motor no lo conoce.
VARIABLE_TITULAR = "titular"
VARIABLE_VENCIMIENTO = "fecha_vencimiento_cuota"
VARIABLE_CONTACTO = "whatsapp_contacto"
VARIABLE_DIAS = "dias_atraso_ajustados"  # solo una v2 puede usarla: la fila la aporta ya ajustada
VARIABLES_DEL_MENSAJE = {
    VARIABLE_TITULAR: TipoValor.TEXTO,
    VARIABLE_VENCIMIENTO: TipoValor.FECHA,
    VARIABLE_CONTACTO: TipoValor.TEXTO,
}
VARIABLES_V2 = {**VARIABLES_DEL_MENSAJE, VARIABLE_DIAS: TipoValor.NUMERO}
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
    return replace(datos, nombre=datos.nombre.strip())


def _problemas_de_nombre(datos: DatosSpeech) -> list[ProblemaSpeech]:
    if 1 <= len(datos.nombre.strip()) <= LARGO_MAXIMO_NOMBRE_SPEECH:
        return []
    return [
        ProblemaSpeech(
            None,
            "nombre",
            f"El nombre debe tener entre 1 y {LARGO_MAXIMO_NOMBRE_SPEECH} caracteres",
        )
    ]


def _problemas_de_segmentos(presentes: Sequence[Segmento]) -> list[ProblemaSpeech]:
    faltan = [r.segmento.value for r in RANGOS_SEGMENTO if r.segmento not in presentes]
    repetidos = sorted({s.value for s in presentes if presentes.count(s) > 1})
    if not (faltan or repetidos):
        return []
    detalle = "Cada segmento debe aparecer una vez"
    if faltan:
        detalle += f"; faltan: {', '.join(faltan)}"
    if repetidos:
        detalle += f"; repetidos: {', '.join(repetidos)}"
    return [ProblemaSpeech(None, "segmentos", detalle)]


def problemas_de(datos: DatosSpeech) -> tuple[ProblemaSpeech, ...]:
    if datos.formato is FormatoSpeech.V2:
        return _problemas_de_v2(datos)
    problemas = _problemas_de_nombre(datos)
    if datos.expresiones:
        problemas.append(
            ProblemaSpeech(None, "formato", "Una version v1 lleva partes, no expresiones")
        )
    problemas += _problemas_de_segmentos([partes.segmento for partes in datos.partes])
    for partes in datos.partes:
        for campo, texto in (("parte_1", partes.parte_1), ("parte_2", partes.parte_2)):
            if _REFERENCIA in texto:
                problemas.append(
                    ProblemaSpeech(partes.segmento, campo, "El texto no puede contener '[@'")
                )
    return tuple(problemas)


def _problemas_de_v2(datos: DatosSpeech) -> tuple[ProblemaSpeech, ...]:
    """Una v2: nombre, cada segmento una vez y cada expresion valida contra las variables del
    mensaje (RF-46). Un segmento sin contenido no se guarda: seria un SMS vacio."""
    problemas = _problemas_de_nombre(datos)
    if datos.partes:
        problemas.append(
            ProblemaSpeech(None, "formato", "Una version v2 lleva expresiones, no partes")
        )
    problemas += _problemas_de_segmentos([e.segmento for e in datos.expresiones])
    for item in datos.expresiones:
        if not item.expresion.nodos:
            problemas.append(
                ProblemaSpeech(item.segmento, "expresion", "El segmento necesita contenido")
            )
            continue
        problemas += [
            ProblemaSpeech(item.segmento, "expresion", p.detalle, p)
            for p in evaluador.validar(item.expresion, VARIABLES_V2)
        ]
    return tuple(problemas)


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


def convertir_a_v2(partes: Sequence[PartesSegmento]) -> tuple[ExpresionSegmento, ...]:
    """Las expresiones de una v2 que dan el mismo mensaje que esta v1 (C-5).

    Es `expresion_de` de cada segmento, con el titular y la fecha marcados como obligatorios: una
    v2 convertida los necesita igual que la v1. (Que un producto sin ellos se excluya lo decide la
    campana sobre las variables que la expresion usa, no la marca.)
    """
    convertidas: list[ExpresionSegmento] = []
    for segmento in partes:
        nodos = tuple(
            replace(n, obligatoria=True)
            if isinstance(n, NodoVariable) and n.nombre in (VARIABLE_TITULAR, VARIABLE_VENCIMIENTO)
            else n
            for n in expresion_de(segmento).nodos
        )
        convertidas.append(ExpresionSegmento(segmento.segmento, Expresion(nodos)))
    return tuple(convertidas)


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


def _compilar(
    expresion: Expresion,
    variables: Mapping[str, TipoValor],
    limites: LimitesExpresion,
    whatsapp: str | None,
) -> Compilada:
    constantes = {VARIABLE_CONTACTO: whatsapp} if whatsapp else None
    return evaluador.compilar(expresion, variables, limites, constantes=constantes)


def compilar_segmento(partes: PartesSegmento, whatsapp: str | None = None) -> Compilada:
    """Compila un segmento v1. Con `whatsapp`, el contacto es una constante de la campana: el
    enlace se arma y se valida una sola vez, aqui, y no en cada fila (B7). Sin numero no se pasa
    constante alguna: un segmento que no usa `[whatsapp]` compila igual que siempre."""
    expresion = expresion_de(partes)
    return _compilar(expresion, VARIABLES_DEL_MENSAJE, _limites_de(expresion), whatsapp)


def compilar_expresion(expresion: Expresion, whatsapp: str | None = None) -> Compilada:
    """Compila el segmento de una v2, con los limites de tamano de siempre (RF-48)."""
    return _compilar(expresion, VARIABLES_V2, LIMITES, whatsapp)


class _Segmento:
    """Lo que el constructor sabe de un segmento: su expresion y que variables usa."""

    def __init__(
        self,
        expresion: Expresion,
        variables: Mapping[str, TipoValor],
        limites: LimitesExpresion,
        usa_titular: bool,
        usa_vencimiento: bool,
        usa_whatsapp: bool,
    ) -> None:
        self.expresion = expresion
        self.variables = variables
        self.limites = limites
        self.usa_titular = usa_titular
        self.usa_vencimiento = usa_vencimiento
        self.usa_whatsapp = usa_whatsapp


def _segmentos_de(datos: Sequence[PartesSegmento] | DatosSpeech) -> dict[Segmento, _Segmento]:
    if isinstance(datos, DatosSpeech) and datos.formato is FormatoSpeech.V2:
        resultado: dict[Segmento, _Segmento] = {}
        for item in datos.expresiones:
            usadas = variables_usadas(item.expresion)
            resultado[item.segmento] = _Segmento(
                item.expresion,
                VARIABLES_V2,
                LIMITES,
                VARIABLE_TITULAR in usadas,
                VARIABLE_VENCIMIENTO in usadas,
                VARIABLE_CONTACTO in usadas,
            )
        return resultado
    partes = datos.partes if isinstance(datos, DatosSpeech) else datos
    resultado = {}
    for p in partes:
        expresion = expresion_de(p)
        resultado[p.segmento] = _Segmento(
            expresion,
            VARIABLES_DEL_MENSAJE,
            _limites_de(expresion),
            True,  # una v1 siempre necesita el titular y la fecha (RF-MM-13)
            True,
            usa_whatsapp(p),
        )
    return resultado


class ConstructorMensajes:
    """Compila una vez la expresion de cada segmento y arma mensajes para muchos productos.

    Recibe las partes de una v1 o los datos de una version (v1 o v2).

    Sin numero de WhatsApp, los segmentos que lo usan quedan sin compilar:
    pedirles un mensaje lanza FaltaWhatsapp. Asi una campana cuyos productos no
    caen en esos segmentos se puede generar igual.

    El numero es una constante de la campana (B7): el enlace se evalua al compilar. Si da un
    problema (un numero fuera de RF-02, hoy inalcanzable), queda en ESE segmento y se lanza
    `MensajeNoGenerable` al pedirle un mensaje; el constructor y los demas segmentos no se ven
    afectados. Lo mismo vale para una expresion v2 que no compile contra el catalogo de hoy.
    """

    def __init__(
        self, partes: Sequence[PartesSegmento] | DatosSpeech, whatsapp: str | None
    ) -> None:
        self._segmentos = _segmentos_de(partes)
        self._compiladas: dict[Segmento, Compilada] = {}
        self._sin_whatsapp: set[Segmento] = set()
        self._no_generables: dict[Segmento, tuple[Problema, ...]] = {}
        for segmento, datos in self._segmentos.items():
            if datos.usa_whatsapp and not whatsapp:
                self._sin_whatsapp.add(segmento)
                continue
            try:
                compilada = _compilar(datos.expresion, datos.variables, datos.limites, whatsapp)
            except ExpresionInvalida as error:
                self._no_generables[segmento] = error.problemas
                continue
            self._compiladas[segmento] = compilada
            if compilada.problemas_plegados:
                self._no_generables[segmento] = compilada.problemas_plegados

    def usa_titular(self, segmento: Segmento) -> bool:
        """Si el producto sin titular se excluye en este segmento (siempre en una v1)."""
        return self._segmentos[segmento].usa_titular

    def usa_vencimiento(self, segmento: Segmento) -> bool:
        """Si el producto sin fecha de vencimiento se excluye en este segmento."""
        return self._segmentos[segmento].usa_vencimiento

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

    def mensaje_de(
        self,
        segmento: Segmento,
        titular: str | None,
        vencimiento: date | None,
        dias_ajustados: int | None = None,
    ) -> str:
        # El contacto es una constante ya plegada: la fila solo aporta titular, vencimiento y,
        # para una v2 que la use, los dias ajustados a la fecha de envio.
        return self.mensaje(
            segmento,
            {
                VARIABLE_TITULAR: titular,
                VARIABLE_VENCIMIENTO: vencimiento,
                VARIABLE_DIAS: dias_ajustados,
            },
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


def previsualizar_v2(
    expresiones: Sequence[ExpresionSegmento], whatsapp: str | None
) -> tuple[LargoSegmento, ...]:
    """Largo maximo, nivel y ejemplo de cada segmento de una v2 (C-6).

    El largo es la cota de la expresion; sin cota (el largo de una variable depende del dato) es
    `None` con su motivo, y el nivel queda sin codigo: lo que decide si un producto sale es el
    largo del mensaje real, fila por fila. Un segmento cuya expresion no compila no aparece: sus
    problemas los informa `problemas_de`. El ejemplo se evalua con un titular de 8, una fecha de
    ejemplo, los dias del inicio del rango y el WhatsApp dado; `None` si usa el WhatsApp y no hay.
    """
    por_segmento = {e.segmento: e for e in expresiones}
    resultado: list[LargoSegmento] = []
    for rango in RANGOS_SEGMENTO:
        item = por_segmento.get(rango.segmento)
        if item is None or not item.expresion.nodos:
            continue
        try:
            compilada = compilar_expresion(item.expresion)
        except ExpresionInvalida:
            continue
        con_whatsapp = VARIABLE_CONTACTO in variables_usadas(item.expresion)
        ejemplo = None
        if not con_whatsapp or whatsapp:
            dias = rango.desde if rango.desde is not None else rango.hasta
            muestra = compilada.evaluar(
                {
                    VARIABLE_TITULAR: _TITULAR_EJEMPLO,
                    VARIABLE_VENCIMIENTO: _FECHA_DE_EJEMPLO,
                    VARIABLE_CONTACTO: whatsapp,
                    VARIABLE_DIAS: dias,
                }
            )
            ejemplo = None if muestra.problemas else muestra.texto
        largo = compilada.cota
        resultado.append(
            LargoSegmento(
                rango=rango,
                usa_whatsapp=con_whatsapp,
                largo_maximo=largo,
                codigo=None if largo is None else codigo_por_largo(largo),
                ejemplo=ejemplo,
                motivo_sin_cota=compilada.motivo_sin_cota,
            )
        )
    return tuple(resultado)


def whatsapp_valido(numero: str) -> bool:
    """El numero de contacto sigue la misma regla de telefono (RF-02)."""
    return numero_valido(numero)
