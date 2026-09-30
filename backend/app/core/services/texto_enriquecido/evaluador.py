"""Compilar una expresion una vez y evaluarla por fila (RF-42, RF-45, RF-46, RF-48).

`compilar` comprueba limites, variables, funciones, parametros y tipos, y deja la
expresion lista: por fila solo se aplican funciones ya resueltas, sin buscar por
nombre, sin comprobar tipos y sin expresiones regulares. Una expresion invalida
lanza `ExpresionInvalida` con todos sus problemas y su ubicacion, antes de
procesar ninguna fila.

Al evaluar, un problema de una fila no detiene nada: el nodo afectado queda
vacio, el problema se informa con su ubicacion y el resto del texto se conserva.
Una variable vacia hace que su cadena de funciones no se aplique y su nodo quede
vacio, como en RF-12 (salvo las funciones `acepta_nulo`, como `si_vacio`).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.core.entities.texto_enriquecido import (
    LIMITES,
    CodigoTexto,
    Expresion,
    ExpresionInvalida,
    LimitesExpresion,
    NodoTexto,
    Problema,
    TipoValor,
)

from . import sintaxis
from .cota import cota_de_expresion
from .funciones import REGISTRO
from .funciones.base import Funcion, ValorInvalido, normalizar_argumento
from .tipos import NodoResuelto, PasoResuelto, coaccionar, es_vacio, resolver_variable


@dataclass(frozen=True, slots=True)
class Resultado:
    """Lo que produce una expresion para una fila.

    `texto` es el resultado completo. `valor` es el valor tipado final cuando la
    expresion es un solo nodo variable, aunque lleve funciones (una fecha sumada
    sigue siendo fecha; D11): sin pasarlo por texto, para conservar el tipo en
    la columna. En cualquier otra expresion es None. Un valor vacio o un problema
    en ese nodo dejan `valor` en None.
    """

    texto: str
    valor: Any = None
    problemas: tuple[Problema, ...] = ()


def validar(
    expresion: Expresion,
    variables: Mapping[str, TipoValor],
    limites: LimitesExpresion = LIMITES,
    registro: Mapping[str, Funcion] = REGISTRO,
) -> tuple[Problema, ...]:
    """Todos los problemas de la expresion, sin lanzar nada. Vacio si es valida."""
    return _resolver(expresion, variables, limites, registro)[1]


def compilar(
    expresion: Expresion,
    variables: Mapping[str, TipoValor],
    limites: LimitesExpresion = LIMITES,
    registro: Mapping[str, Funcion] = REGISTRO,
) -> "Compilada":
    """Comprueba la expresion contra las variables disponibles y la deja lista para evaluar."""
    partes, problemas = _resolver(expresion, variables, limites, registro)
    if problemas:
        raise ExpresionInvalida(problemas)
    return Compilada(expresion, tuple(partes))


def compilar_texto(
    texto: str,
    variables: Mapping[str, TipoValor],
    limites: LimitesExpresion = LIMITES,
) -> "Compilada":
    """Puente de las plantillas `[@campo]` (RF-12): texto -> expresion -> compilada."""
    return compilar(sintaxis.leer(texto, limites), variables, limites)


def _limites_excedidos(expresion: Expresion, limites: LimitesExpresion) -> list[Problema]:
    problemas: list[Problema] = []
    if len(expresion.nodos) > limites.nodos:
        problemas.append(
            Problema(CodigoTexto.LIMITE_EXCEDIDO, f"La expresion pasa de {limites.nodos} nodos")
        )
        return problemas
    for indice, nodo in enumerate(expresion.nodos):
        if isinstance(nodo, NodoTexto):
            if len(nodo.valor) > limites.largo_literal:
                problemas.append(
                    Problema(
                        CodigoTexto.LIMITE_EXCEDIDO,
                        f"El texto fijo pasa de {limites.largo_literal} caracteres",
                        nodo=indice,
                    )
                )
            continue
        if len(nodo.funciones) > limites.funciones_por_nodo:
            problemas.append(
                Problema(
                    CodigoTexto.LIMITE_EXCEDIDO,
                    f"Una variable admite hasta {limites.funciones_por_nodo} funciones",
                    nodo=indice,
                )
            )
            continue
        for posicion, llamada in enumerate(nodo.funciones):
            if len(llamada.args) > limites.argumentos_por_funcion:
                problemas.append(
                    Problema(
                        CodigoTexto.LIMITE_EXCEDIDO,
                        f"Una funcion admite hasta {limites.argumentos_por_funcion} argumentos",
                        nodo=indice,
                        funcion=posicion,
                    )
                )
            for argumento in llamada.args:
                if isinstance(argumento, str) and len(argumento) > limites.largo_literal:
                    problemas.append(
                        Problema(
                            CodigoTexto.LIMITE_EXCEDIDO,
                            f"Un argumento de texto pasa de {limites.largo_literal} caracteres",
                            nodo=indice,
                            funcion=posicion,
                        )
                    )
    return problemas


def _resolver(
    expresion: Expresion,
    variables: Mapping[str, TipoValor],
    limites: LimitesExpresion,
    registro: Mapping[str, Funcion],
) -> tuple[list[str | NodoResuelto], tuple[Problema, ...]]:
    problemas = _limites_excedidos(expresion, limites)
    if problemas:
        return [], tuple(problemas)
    partes: list[str | NodoResuelto] = []
    for indice, nodo in enumerate(expresion.nodos):
        if isinstance(nodo, NodoTexto):
            partes.append(nodo.valor)
            continue
        resuelto, problemas_del_nodo = resolver_variable(nodo, indice, variables, registro)
        problemas.extend(problemas_del_nodo)
        if resuelto is not None:
            partes.append(resuelto)
    return partes, tuple(problemas)


class Compilada:
    """Una expresion comprobada y lista para evaluar muchas filas."""

    def __init__(self, expresion: Expresion, partes: tuple[str | NodoResuelto, ...]) -> None:
        self.expresion = expresion
        self._partes = partes
        self._es_variable_unica = len(partes) == 1 and isinstance(partes[0], NodoResuelto)
        self._variables = _variables_usadas(partes)
        self._cota = cota_de_expresion(partes)

    @property
    def variables(self) -> tuple[str, ...]:
        """Variables que la expresion lee del producto (incluidas las de los argumentos)."""
        return self._variables

    @property
    def es_variable_unica(self) -> bool:
        """Un solo nodo variable: su valor tipado final viaja en `Resultado.valor` (D11)."""
        return self._es_variable_unica

    @property
    def es_valor_fijo(self) -> bool:
        return not self._variables

    @property
    def tipo(self) -> TipoValor:
        """El tipo del resultado: el del valor final de un nodo variable unico; si no, texto."""
        if self._es_variable_unica:
            return self._partes[0].tipo_final  # type: ignore[union-attr]
        return TipoValor.TEXTO

    @property
    def cota(self) -> int | None:
        """Largo maximo del texto, o None si alguna parte no se puede acotar."""
        return self._cota

    def evaluar(self, producto: Mapping[str, Any]) -> Resultado:
        trozos: list[str] = []
        problemas: list[Problema] = []
        valor: Any = None
        for indice, parte in enumerate(self._partes):
            if isinstance(parte, str):
                trozos.append(parte)
                continue
            texto, valor = _evaluar_variable(parte, indice, producto, problemas)
            trozos.append(texto)
        return Resultado(
            "".join(trozos),
            valor if self._es_variable_unica else None,
            tuple(problemas),
        )


def _variables_usadas(partes: tuple[str | NodoResuelto, ...]) -> tuple[str, ...]:
    usadas: dict[str, None] = {}
    for parte in partes:
        if isinstance(parte, str):
            continue
        usadas[parte.nombre] = None
        for paso in parte.pasos:
            for argumento in paso.argumentos:
                if argumento.variable is not None:
                    usadas[argumento.variable] = None
    return tuple(usadas)


def _evaluar_variable(
    nodo: NodoResuelto,
    indice: int,
    producto: Mapping[str, Any],
    problemas: list[Problema],
) -> tuple[str, Any]:
    valor = producto.get(nodo.nombre)
    if nodo.obligatoria and es_vacio(valor):
        problemas.append(
            Problema(
                CodigoTexto.VARIABLE_OBLIGATORIA_VACIA,
                f"La variable {nodo.nombre!r} es obligatoria y esta vacia",
                nodo=indice,
                nombre=nodo.nombre,
            )
        )
    if not nodo.pasos:
        # Sin funciones: el mismo `str(valor)` que plantillas.aplicar (D1, RF-54).
        return ("" if valor is None else str(valor)), valor
    posicion = -1
    try:
        valor = None if es_vacio(valor) else coaccionar(valor, nodo.tipo_variable)
        for paso in nodo.pasos:
            posicion += 1
            if valor is None and not paso.funcion.acepta_nulo:
                continue
            valor = paso.funcion.aplicar(valor, *_argumentos(paso, producto))
    except ValorInvalido as error:
        problemas.append(
            Problema(
                error.codigo,
                error.detalle,
                nodo=indice,
                funcion=posicion if posicion >= 0 else None,
                parametro=error.parametro,
                nombre=nodo.nombre if posicion < 0 else nodo.pasos[posicion].funcion.nombre,
            )
        )
        return "", None
    except ArithmeticError:  # OverflowError, decimal.InvalidOperation, fecha fuera de calendario
        problemas.append(
            Problema(
                CodigoTexto.RESULTADO_FUERA_DE_RANGO,
                "El resultado no cabe en el rango admitido",
                nodo=indice,
                funcion=posicion,
                nombre=nodo.pasos[posicion].funcion.nombre,
            )
        )
        return "", None
    return _a_texto(valor), valor


def _argumentos(paso: PasoResuelto, producto: Mapping[str, Any]) -> list[Any]:
    valores: list[Any] = []
    for argumento in paso.argumentos:
        if argumento.variable is None:
            valores.append(argumento.literal)
            continue
        crudo = producto.get(argumento.variable)
        parametro = argumento.parametro
        if es_vacio(crudo):
            if paso.funcion.acepta_nulo:
                valores.append(None)
                continue
            raise ValorInvalido(
                CodigoTexto.ARGUMENTO_VACIO,
                f"La variable {argumento.variable!r} de {parametro.nombre} esta vacia",
                parametro.nombre,
            )
        valor = coaccionar(crudo, argumento.tipo_variable)  # type: ignore[arg-type]
        try:
            valores.append(normalizar_argumento(parametro, valor))
        except ValueError as error:
            raise ValorInvalido(
                CodigoTexto.PARAMETRO_INVALIDO,
                f"{parametro.nombre} {error}",
                parametro.nombre,
            ) from error
    return valores


def _a_texto(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, Decimal):
        return format(valor, "f")
    return str(valor)
