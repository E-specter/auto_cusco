"""Tipos de valor y comprobacion de la cadena de funciones al compilar (RF-46).

Al compilar se resuelve cada funcion por nombre en el registro y se sigue el tipo
a lo largo de la cadena: `formato_fecha` sobre un texto se rechaza al guardar, no
al generar la fila. Lo que sale de aqui (`NodoResuelto`) es lo que el evaluador
aplica por fila sin volver a buscar ni comprobar nada.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.core.entities.cartera import TipoDato
from app.core.entities.texto_enriquecido import (
    ArgumentoVariable,
    CodigoTexto,
    LlamadaFuncion,
    NodoVariable,
    Problema,
    TipoValor,
)

from .funciones import REGISTRO
from .funciones.base import (
    MISMO_TIPO,
    Funcion,
    Parametro,
    ValorInvalido,
    es_vacio,
    normalizar_argumento,
    texto_a_decimal,
)

__all__ = [
    "ArgumentoResuelto",
    "NodoResuelto",
    "PasoResuelto",
    "coaccionar",
    "es_vacio",
    "resolver_variable",
    "tipo_de_valor",
    "variables_desde_campos",
]


def variables_desde_campos(campos: Mapping[str, TipoDato]) -> dict[str, TipoValor]:
    """Las variables de un catalogo de campos (`CatalogoCartera.tipos()`), con su tipo.

    `TipoDato.BOOLEANO` pasa a `booleano` (D2): incluye los `*_aplica`.
    """
    return {nombre: TipoValor(tipo.value) for nombre, tipo in campos.items()}


def tipo_de_valor(valor: Any) -> TipoValor:
    """El tipo de un valor en tiempo de ejecucion; el vacio es `nulo`."""
    if es_vacio(valor):
        return TipoValor.NULO
    if isinstance(valor, bool):
        return TipoValor.BOOLEANO
    if isinstance(valor, (int, float, Decimal)):
        return TipoValor.NUMERO
    if isinstance(valor, (date, datetime)):
        return TipoValor.FECHA
    return TipoValor.TEXTO


def coaccionar(valor: Any, tipo: TipoValor) -> Any:
    """Deja el valor de un producto en el tipo que declara su variable, o `ValorInvalido`.

    Un `datetime` es fecha; un entero, un `float` o un texto numerico son numero
    (`Decimal`); cualquier cosa puede ser texto, con `str()` como hoy.
    """
    if tipo is TipoValor.TEXTO:
        return valor if isinstance(valor, str) else str(valor)
    if tipo is TipoValor.NUMERO:
        return _a_numero(valor)
    if tipo is TipoValor.FECHA:
        return _a_fecha(valor)
    return valor


def _a_numero(valor: Any) -> Decimal:
    if isinstance(valor, Decimal) and valor.is_finite():
        return valor
    if isinstance(valor, int) and not isinstance(valor, bool):
        return Decimal(valor)
    if isinstance(valor, float) and Decimal(repr(valor)).is_finite():
        return Decimal(repr(valor))
    if isinstance(valor, str):
        return texto_a_decimal(valor)
    raise ValorInvalido(CodigoTexto.NO_ES_NUMERO, f"{valor!r} no es un numero")


def _a_fecha(valor: Any) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        try:
            return date.fromisoformat(valor.strip())
        except ValueError:
            pass
    raise ValorInvalido(CodigoTexto.NO_ES_FECHA, f"{valor!r} no es una fecha")


# --- comprobacion al compilar ---


@dataclass(frozen=True)
class ArgumentoResuelto:
    """Un argumento ya comprobado: un literal listo para aplicar, o una variable por leer."""

    parametro: Parametro
    literal: Any = None
    variable: str | None = None
    tipo_variable: TipoValor | None = None


@dataclass(frozen=True)
class PasoResuelto:
    funcion: Funcion
    argumentos: tuple[ArgumentoResuelto, ...]
    entrada: TipoValor
    salida: TipoValor


@dataclass(frozen=True)
class NodoResuelto:
    nombre: str
    tipo_variable: TipoValor
    pasos: tuple[PasoResuelto, ...]
    obligatoria: bool

    @property
    def tipo_final(self) -> TipoValor:
        return self.pasos[-1].salida if self.pasos else self.tipo_variable


def resolver_variable(
    nodo: NodoVariable,
    indice: int,
    variables: Mapping[str, TipoValor],
    registro: Mapping[str, Funcion] = REGISTRO,
) -> tuple[NodoResuelto | None, list[Problema]]:
    """Comprueba la variable y su cadena. Sin problemas, devuelve el nodo resuelto."""
    problemas: list[Problema] = []
    tipo = variables.get(nodo.nombre)
    if tipo is None:
        problemas.append(
            Problema(
                CodigoTexto.VARIABLE_DESCONOCIDA,
                f"La variable {nodo.nombre!r} no existe",
                nodo=indice,
                nombre=nodo.nombre,
            )
        )
        return None, problemas
    actual = tipo
    pasos: list[PasoResuelto] = []
    for posicion, llamada in enumerate(nodo.funciones):
        funcion = registro.get(llamada.nombre)
        if funcion is None:
            problemas.append(
                Problema(
                    CodigoTexto.FUNCION_DESCONOCIDA,
                    f"La funcion {llamada.nombre!r} no existe",
                    nodo=indice,
                    funcion=posicion,
                    nombre=llamada.nombre,
                )
            )
            break
        argumentos = _resolver_argumentos(
            funcion, llamada, actual, variables, indice, posicion, problemas
        )
        if actual not in funcion.recibe:
            recibe = ", ".join(t.value for t in funcion.recibe)
            problemas.append(
                Problema(
                    CodigoTexto.TIPO_INCOMPATIBLE,
                    f"{funcion.nombre} recibe {recibe} y aqui llega {actual.value}",
                    nodo=indice,
                    funcion=posicion,
                    nombre=funcion.nombre,
                )
            )
            break
        salida = actual if funcion.devuelve == MISMO_TIPO else TipoValor(funcion.devuelve)
        pasos.append(PasoResuelto(funcion, argumentos, actual, salida))
        actual = salida
    if problemas:
        return None, problemas
    return NodoResuelto(nodo.nombre, tipo, tuple(pasos), nodo.obligatoria), problemas


def _resolver_argumentos(
    funcion: Funcion,
    llamada: LlamadaFuncion,
    entrada: TipoValor,
    variables: Mapping[str, TipoValor],
    nodo: int,
    posicion: int,
    problemas: list[Problema],
) -> tuple[ArgumentoResuelto, ...]:
    def problema(codigo: CodigoTexto, detalle: str, parametro: str | None) -> None:
        problemas.append(
            Problema(
                codigo,
                f"{funcion.nombre}: {detalle}",
                nodo=nodo,
                funcion=posicion,
                parametro=parametro,
                nombre=funcion.nombre,
            )
        )

    if len(llamada.args) > len(funcion.parametros):
        problema(
            CodigoTexto.PARAMETRO_INVALIDO,
            f"admite hasta {len(funcion.parametros)} argumentos y recibio {len(llamada.args)}",
            None,
        )
    resueltos: list[ArgumentoResuelto] = []
    for indice, parametro in enumerate(funcion.parametros):
        esperado = parametro.tipo or entrada
        if indice >= len(llamada.args):
            if parametro.obligatorio:
                problema(
                    CodigoTexto.PARAMETRO_INVALIDO, f"falta {parametro.nombre}", parametro.nombre
                )
            else:
                literal = normalizar_argumento(parametro, parametro.por_defecto)
                resueltos.append(ArgumentoResuelto(parametro, literal=literal))
            continue
        argumento = llamada.args[indice]
        if isinstance(argumento, ArgumentoVariable):
            if not parametro.acepta_variable:
                problema(
                    CodigoTexto.PARAMETRO_INVALIDO,
                    f"{parametro.nombre} no admite una variable",
                    parametro.nombre,
                )
                continue
            tipo_variable = variables.get(argumento.nombre)
            if tipo_variable is None:
                problema(
                    CodigoTexto.VARIABLE_DESCONOCIDA,
                    f"la variable {argumento.nombre!r} de {parametro.nombre} no existe",
                    parametro.nombre,
                )
            elif tipo_variable is not esperado:
                problema(
                    CodigoTexto.PARAMETRO_INVALIDO,
                    f"{parametro.nombre} pide {esperado.value} y {argumento.nombre!r} es "
                    f"{tipo_variable.value}",
                    parametro.nombre,
                )
            else:
                resueltos.append(
                    ArgumentoResuelto(
                        parametro, variable=argumento.nombre, tipo_variable=tipo_variable
                    )
                )
            continue
        tipo_literal = _tipo_del_literal(argumento)
        if tipo_literal is not esperado:
            problema(
                CodigoTexto.PARAMETRO_INVALIDO,
                f"{parametro.nombre} pide {esperado.value}",
                parametro.nombre,
            )
            continue
        try:
            resueltos.append(
                ArgumentoResuelto(parametro, literal=normalizar_argumento(parametro, argumento))
            )
        except ValueError as error:
            problema(
                CodigoTexto.PARAMETRO_INVALIDO, f"{parametro.nombre} {error}", parametro.nombre
            )
    return tuple(resueltos)


def _tipo_del_literal(argumento: Any) -> TipoValor | None:
    if isinstance(argumento, bool):
        return None
    if isinstance(argumento, (int, Decimal)):
        return TipoValor.NUMERO
    if isinstance(argumento, str):
        return TipoValor.TEXTO
    return None
