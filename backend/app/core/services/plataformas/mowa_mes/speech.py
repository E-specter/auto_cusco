"""Construccion del mensaje sobre el motor de texto enriquecido (RF-MM-14, RF-MM-16, RF-MM-19).

Una version del speech es una expresion del motor por segmento, guardada tal cual (M2). Desde
M-B4 (RF-MM-17) no hay otro formato: las versiones de dos partes (v1, incluido el Speech original)
se convirtieron en su lugar con la migracion `d7a3e5b9c241`, y su texto quedo guardado en
`texto_v1`, sin leerse.

El largo maximo de un segmento es la cota de su expresion (`Compilada.cota`). Una expresion puede
no tener cota (una variable cuyo largo depende del dato): se informa como "sin maximo calculable"
con su motivo, y el control por fila de los 160 caracteres sigue siendo sobre el mensaje real.

Que variables usa un segmento se decide sobre sus nodos (`texto_enriquecido.uso`), nunca buscando un
nombre en el texto: un segmento necesita el titular o la fecha solo si su expresion los usa.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

from app.core.entities.mowa_mes import (
    LARGO_ADVERTENCIA,
    LARGO_MAXIMO,
    LARGO_MAXIMO_NOMBRE_SPEECH,
    LARGO_TITULAR,
    RANGOS_SEGMENTO,
    CodigoMowaMes,
    DatosSpeech,
    ExpresionSegmento,
    FaltaWhatsapp,
    LargoSegmento,
    MensajeNoGenerable,
    ProblemaSpeech,
    Segmento,
)
from app.core.entities.telefono import numero_valido
from app.core.entities.texto_enriquecido import (
    LIMITES,
    ArgumentoVariable,
    CodigoTexto,
    Expresion,
    ExpresionInvalida,
    LimitesExpresion,
    NodoTexto,
    NodoVariable,
    Problema,
    TipoValor,
)
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.core.services.texto_enriquecido import evaluador
from app.core.services.texto_enriquecido.evaluador import Compilada
from app.core.services.texto_enriquecido.gsm7 import (
    a_gsm7,
    grafemas_borrados,
    largo_gsm7_normalizado,
)
from app.core.services.texto_enriquecido.uso import variables_usadas

CAMPO_MENSAJE = "mensaje"
_TITULAR_EJEMPLO = "X" * LARGO_TITULAR
_FECHA_DE_EJEMPLO = date(2026, 10, 5)  # el ejemplo de una v2 se evalua con fecha de verdad

# Variables que la fila aporta al motor (RF-43): el conector las declara, el motor no lo conoce.
VARIABLE_TITULAR = "titular"
VARIABLE_VENCIMIENTO = "fecha_vencimiento_cuota"
VARIABLE_CONTACTO = "whatsapp_contacto"
VARIABLE_DIAS = "dias_atraso_ajustados"  # la fila la aporta ya ajustada a la fecha de envio
VARIABLES_DEL_MENSAJE = {
    VARIABLE_TITULAR: TipoValor.TEXTO,
    VARIABLE_VENCIMIENTO: TipoValor.FECHA,
    VARIABLE_CONTACTO: TipoValor.TEXTO,
}
VARIABLES_V2 = {**VARIABLES_DEL_MENSAJE, VARIABLE_DIAS: TipoValor.NUMERO}

# Un valor sintetico por tipo de campo adicional (D-CA-0): el ejemplo de la previsualizacion y el
# del contexto del editor. Nunca un dato real.
EJEMPLO_ADICIONAL: dict[TipoValor, Any] = {
    TipoValor.TEXTO: "ZONA SINTETICA",
    TipoValor.NUMERO: Decimal("1250.50"),
    TipoValor.FECHA: date(2026, 10, 5),
}


def adicionales_de(catalogo: CatalogoCartera | None) -> dict[str, TipoValor]:
    """Los campos adicionales del catalogo (RF-64), con su tipo y archivados incluidos: una v2 que
    ya los usa tiene que seguir resolviendo. Lee `campos()` una sola vez. Sin catalogo, ninguno."""
    if catalogo is None:
        return {}
    return {
        nombre: TipoValor(campo.tipo.value)
        for nombre, campo in catalogo.campos().items()
        if campo.adicional
    }


def _leidas_por(nodo: NodoVariable) -> list[str]:
    """Las variables que lee un nodo: la base y las que son argumento de sus funciones."""
    return [
        nodo.nombre,
        *(
            a.nombre
            for llamada in nodo.funciones
            for a in llamada.args
            if isinstance(a, ArgumentoVariable)
        ),
    ]


def adicionales_usados_en(
    expresion: Expresion, adicionales: Mapping[str, TipoValor]
) -> tuple[str, ...]:
    """Los adicionales que lee la expresion, sin repetir y en el orden de sus nodos."""
    leidas = (
        n for nodo in expresion.nodos if isinstance(nodo, NodoVariable) for n in _leidas_por(nodo)
    )
    return tuple(n for n in dict.fromkeys(leidas) if n in adicionales)


def codigo_por_largo(largo: int) -> CodigoMowaMes | None:
    if largo > LARGO_MAXIMO:
        return CodigoMowaMes.MENSAJE_EXCEDE_160
    if largo > LARGO_ADVERTENCIA:
        return CodigoMowaMes.MENSAJE_EXCEDE_150
    return None


def limpiar(datos: DatosSpeech) -> DatosSpeech:
    """Recorta solo el nombre: los espacios de las partes son parte del mensaje."""
    return replace(datos, nombre=datos.nombre.strip())


def problemas_del_nombre(nombre: str) -> tuple[ProblemaSpeech, ...]:
    """Los problemas de un nombre solo (renombrar no toca el contenido, RF-MM-28)."""
    return tuple(_problemas_de_nombre(DatosSpeech(nombre=nombre)))


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


def problemas_de(
    datos: DatosSpeech, *, adicionales: Mapping[str, TipoValor] | None = None
) -> tuple[ProblemaSpeech, ...]:
    return _problemas_de_v2(datos, adicionales or {})


def _sin_tope(
    nodo: NodoVariable,
    posicion: int,
    variables: Mapping[str, TipoValor],
    adicionales: Mapping[str, TipoValor],
) -> Problema | None:
    """D-CA-1: un nodo que lee un adicional de texto o de numero, como base o como argumento, tiene
    que tener cota por si solo. Se usa la cota del motor, no se busca la palabra `primeros`: vale
    cualquier cadena que la acote. Una fecha no entra (con `formato_fecha` ya la tiene)."""
    leidos = [
        n for n in _leidas_por(nodo) if adicionales.get(n) in (TipoValor.TEXTO, TipoValor.NUMERO)
    ]
    if not leidos:
        return None
    try:
        sola = evaluador.compilar(Expresion((nodo,)), variables)
    except ExpresionInvalida:
        return None  # otro problema del nodo: ya lo informa la validacion normal
    if sola.cota is not None:
        return None
    detalle = sola.motivo_sin_cota.detalle if sola.motivo_sin_cota else ""
    return Problema(CodigoTexto.SIN_COTA_VARIABLE, detalle, nodo=posicion, nombre=leidos[0])


def _problemas_de_v2(
    datos: DatosSpeech, adicionales: Mapping[str, TipoValor]
) -> tuple[ProblemaSpeech, ...]:
    """Una v2: nombre, cada segmento una vez y cada expresion valida contra las variables del
    mensaje y los campos adicionales (RF-46, D-CA-0). Un segmento sin contenido no se guarda: seria
    un SMS vacio. Un adicional de texto o de numero exige tope (D-CA-1)."""
    variables = {**VARIABLES_V2, **adicionales}
    problemas = _problemas_de_nombre(datos)
    problemas += _problemas_de_segmentos([e.segmento for e in datos.expresiones])
    for item in datos.expresiones:
        if not item.expresion.nodos:
            problemas.append(
                ProblemaSpeech(item.segmento, "expresion", "El segmento necesita contenido")
            )
            continue
        sin_tope = (
            _sin_tope(nodo, i, variables, adicionales)
            for i, nodo in enumerate(item.expresion.nodos)
            if isinstance(nodo, NodoVariable)
        )
        problemas += [
            ProblemaSpeech(item.segmento, "expresion", p.detalle, p)
            for p in (*evaluador.validar(item.expresion, variables), *filter(None, sin_tope))
        ]
    return tuple(problemas)


def _compilar(
    expresion: Expresion,
    variables: Mapping[str, TipoValor],
    limites: LimitesExpresion,
    whatsapp: str | None,
) -> Compilada:
    constantes = {VARIABLE_CONTACTO: whatsapp} if whatsapp else None
    # La cota queda en unidades GSM-7 (RF-MM-27): el texto fijo se mide ya normalizado (`…` y `€`
    # miden 3); las variables cuentan 1 por caracter (supuesto documentado, docs/
    # motor-texto-enriquecido.md §24: el control exacto sigue siendo el de cada fila).
    # NO se cuelga `a_gsm7` de las variables: su cota es el triple y romperia el 156 de «9 a 30».
    return evaluador.compilar(
        expresion, variables, limites, constantes=constantes, medida=largo_gsm7_normalizado
    )


def compilar_expresion(
    expresion: Expresion,
    whatsapp: str | None = None,
    *,
    adicionales: Mapping[str, TipoValor] | None = None,
) -> Compilada:
    """Compila el segmento de una v2, con los limites de tamano de siempre (RF-48) y, si los hay,
    los campos adicionales del catalogo (D-CA-0)."""
    return _compilar(expresion, {**VARIABLES_V2, **(adicionales or {})}, LIMITES, whatsapp)


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
        adicionales_usados: tuple[str, ...] = (),
    ) -> None:
        self.expresion = expresion
        self.variables = variables
        self.limites = limites
        self.usa_titular = usa_titular
        self.usa_vencimiento = usa_vencimiento
        self.usa_whatsapp = usa_whatsapp
        self.adicionales_usados = adicionales_usados


def _segmentos_de(
    datos: DatosSpeech, adicionales: Mapping[str, TipoValor]
) -> dict[Segmento, _Segmento]:
    resultado: dict[Segmento, _Segmento] = {}
    variables = {**VARIABLES_V2, **adicionales}
    for item in datos.expresiones:
        usadas = variables_usadas(item.expresion)
        resultado[item.segmento] = _Segmento(
            item.expresion,
            variables,
            LIMITES,
            VARIABLE_TITULAR in usadas,
            VARIABLE_VENCIMIENTO in usadas,
            VARIABLE_CONTACTO in usadas,
            adicionales_usados_en(item.expresion, adicionales),
        )
    return resultado


class ConstructorMensajes:
    """Compila una vez la expresion de cada segmento y arma mensajes para muchos productos.

    Recibe los datos de una version.

    Sin numero de WhatsApp, los segmentos que lo usan quedan sin compilar:
    pedirles un mensaje lanza FaltaWhatsapp. Asi una campana cuyos productos no
    caen en esos segmentos se puede generar igual.

    El numero es una constante de la campana (B7): el enlace se evalua al compilar. Si da un
    problema (un numero fuera de RF-02, hoy inalcanzable), queda en ESE segmento y se lanza
    `MensajeNoGenerable` al pedirle un mensaje; el constructor y los demas segmentos no se ven
    afectados. Lo mismo vale para una expresion v2 que no compile contra el catalogo de hoy.
    """

    def __init__(
        self,
        datos: DatosSpeech,
        whatsapp: str | None,
        *,
        adicionales: Mapping[str, TipoValor] | None = None,
    ) -> None:
        self._segmentos = _segmentos_de(datos, adicionales or {})
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
        """Si el producto sin titular se excluye en este segmento (si su expresion lo usa)."""
        return self._segmentos[segmento].usa_titular

    def usa_vencimiento(self, segmento: Segmento) -> bool:
        """Si el producto sin fecha de vencimiento se excluye en este segmento."""
        return self._segmentos[segmento].usa_vencimiento

    def adicionales_usados(self, segmento: Segmento) -> tuple[str, ...]:
        """Los campos adicionales que lee la expresion del segmento, en el orden de sus nodos
        (D-CA-2)."""
        return self._segmentos[segmento].adicionales_usados

    def adicionales_usados_en_todos(self) -> tuple[str, ...]:
        """Los adicionales que lee el speech entero, sin repetir y en el orden de sus segmentos y
        de sus nodos: ya estan calculados al compilar, no se vuelve a mirar nada."""
        return tuple(
            dict.fromkeys(n for s in self._segmentos.values() for n in s.adicionales_usados)
        )

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
        # Ultimo paso fijo (RF-MM-27): el SMS nunca pasa a UCS-2. Se aplica al texto YA evaluado,
        # despues de `primeros(8)` y antes de medir los 150 y los 160; el archivo, la fila
        # guardada, la supervision y la conciliacion ven todos este mismo texto.
        return a_gsm7(resultado.texto)

    def mensaje_de(
        self,
        segmento: Segmento,
        titular: str | None,
        vencimiento: date | None,
        dias_ajustados: int | None = None,
        *,
        adicionales: Mapping[str, Any] | None = None,
    ) -> str:
        # El contacto es una constante ya plegada: la fila solo aporta titular, vencimiento y,
        # para un segmento que la use, los dias ajustados a la fecha de envio y los valores de sus
        # campos adicionales (D-CA-0).
        return self.mensaje(
            segmento,
            {
                VARIABLE_TITULAR: titular,
                VARIABLE_VENCIMIENTO: vencimiento,
                VARIABLE_DIAS: dias_ajustados,
                **(adicionales or {}),
            },
        )


def _borrados_de(trozos: Sequence[str]) -> tuple[str, ...]:
    """Los grafemas que se borran, sin repetir y en orden, de trozos que en el mensaje NO van
    pegados: un trozo termina en la mitad de una bandera y el siguiente la completa, y eso no
    forma una bandera que nadie escribio."""
    return tuple(dict.fromkeys(g for trozo in trozos for g in grafemas_borrados(trozo)))


def previsualizar_v2(
    expresiones: Sequence[ExpresionSegmento],
    whatsapp: str | None,
    *,
    adicionales: Mapping[str, TipoValor] | None = None,
) -> tuple[LargoSegmento, ...]:
    """Largo maximo, nivel y ejemplo de cada segmento de una v2 (C-6).

    El largo es la cota de la expresion; sin cota (el largo de una variable depende del dato) es
    `None` con su motivo, y el nivel queda sin codigo: lo que decide si un producto sale es el
    largo del mensaje real, fila por fila. Un segmento cuya expresion no compila no aparece: sus
    problemas los informa `problemas_de`. El ejemplo se evalua con un titular de 8, una fecha de
    ejemplo, los dias del inicio del rango y el WhatsApp dado; `None` si usa el WhatsApp y no hay.
    """
    adicionales = adicionales or {}
    por_segmento = {e.segmento: e for e in expresiones}
    resultado: list[LargoSegmento] = []
    for rango in RANGOS_SEGMENTO:
        item = por_segmento.get(rango.segmento)
        if item is None or not item.expresion.nodos:
            continue
        try:
            compilada = compilar_expresion(item.expresion, adicionales=adicionales)
        except ExpresionInvalida:
            continue
        con_whatsapp = VARIABLE_CONTACTO in variables_usadas(item.expresion)
        ejemplo = None
        crudo = None  # el texto evaluado ANTES de normalizar: de ahi salen los borrados
        if not con_whatsapp or whatsapp:
            dias = rango.desde if rango.desde is not None else rango.hasta
            muestra = compilada.evaluar(
                {
                    VARIABLE_TITULAR: _TITULAR_EJEMPLO,
                    VARIABLE_VENCIMIENTO: _FECHA_DE_EJEMPLO,
                    VARIABLE_CONTACTO: whatsapp,
                    VARIABLE_DIAS: dias,
                    **{n: EJEMPLO_ADICIONAL[t] for n, t in adicionales.items()},
                }
            )
            if not muestra.problemas:
                crudo = muestra.texto
                ejemplo = a_gsm7(crudo)  # lo que se enviaria (RF-MM-27)
        if crudo is None:  # sin ejemplo (falta el WhatsApp): cada texto fijo del segmento, aparte
            trozos = [n.valor for n in item.expresion.nodos if isinstance(n, NodoTexto)]
        else:
            trozos = [crudo]
        largo = compilada.cota
        resultado.append(
            LargoSegmento(
                rango=rango,
                usa_whatsapp=con_whatsapp,
                largo_maximo=largo,
                codigo=None if largo is None else codigo_por_largo(largo),
                ejemplo=ejemplo,
                motivo_sin_cota=compilada.motivo_sin_cota,
                caracteres_quitados=_borrados_de(trozos),
            )
        )
    return tuple(resultado)


def whatsapp_valido(numero: str) -> bool:
    """El numero de contacto sigue la misma regla de telefono (RF-02)."""
    return numero_valido(numero)
