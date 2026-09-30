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

Variables de contexto constantes (B7): `compilar` acepta un mapa de variables cuyo valor se
conoce al compilar y es el mismo en toda la carga (el WhatsApp de una campana). Un nodo cuya
variable es constante, y cuyos argumentos variables tambien lo son, se evalua UNA vez al compilar
y queda como texto fijo; sus problemas se informan al compilar (`problemas_plegados`) y salen
igual en cada fila. Plegar no cambia nada observable: el texto, el valor tipado, los problemas y
la cota de cada fila son los mismos que sin constantes.
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
class _Plegado:
    """El resultado de un nodo evaluado al compilar; ocupa el lugar del nodo."""

    texto: str
    valor: Any
    problemas: tuple[Problema, ...]
    tipo_final: TipoValor


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
    constantes: Mapping[str, Any] | None = None,
) -> "Compilada":
    """Comprueba la expresion contra las variables disponibles y la deja lista para evaluar.

    `constantes` son variables del catalogo con un valor fijo para toda la carga: los nodos que
    solo dependen de ellas se evaluan una vez, aqui. Un valor `None` es una constante vacia.
    """
    for nombre in constantes or ():
        if nombre not in variables:
            raise ValueError(f"La constante {nombre!r} no es una variable del catalogo")
    partes, problemas = _resolver(expresion, variables, limites, registro)
    if problemas:
        raise ExpresionInvalida(problemas)
    return Compilada(expresion, tuple(partes), constantes or {})


def compilar_texto(
    texto: str,
    variables: Mapping[str, TipoValor],
    limites: LimitesExpresion = LIMITES,
    constantes: Mapping[str, Any] | None = None,
) -> "Compilada":
    """Puente de las plantillas `[@campo]` (RF-12): texto -> expresion -> compilada."""
    return compilar(sintaxis.leer(texto, limites), variables, limites, constantes=constantes)


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

    def __init__(
        self,
        expresion: Expresion,
        partes: tuple[str | NodoResuelto, ...],
        constantes: Mapping[str, Any] | None = None,
    ) -> None:
        self.expresion = expresion
        self._es_variable_unica = len(partes) == 1 and isinstance(partes[0], NodoResuelto)
        # La cota es la de la expresion sin plegar: lo que ve el usuario no depende de la carga.
        self._cota = cota_de_expresion(partes)
        plegadas, problemas = _plegar(partes, constantes or {}, self._es_variable_unica)
        # Cada parte conserva el indice del nodo de la expresion: los problemas de fila lo informan.
        self._indices = tuple(indice for indice, _ in plegadas)
        self._partes = tuple(parte for _, parte in plegadas)
        self._nodos_plegados = sum(isinstance(p, NodoResuelto) for p in partes) - sum(
            isinstance(p, NodoResuelto) for p in self._partes
        )
        self._problemas_plegados = problemas
        usadas = _variables_usadas(tuple(p for p in self._partes if isinstance(p, NodoResuelto)))
        # Los nodos que no se pliegan pueden leer una constante (un argumento): se la damos.
        self._constantes_en_uso = {
            n: constantes[n] for n in usadas if constantes and n in constantes
        }
        self._variables = tuple(n for n in usadas if n not in self._constantes_en_uso)

    @property
    def nodos_plegados(self) -> int:
        """Cuantos nodos se evaluaron al compilar."""
        return self._nodos_plegados

    @property
    def problemas_plegados(self) -> tuple[Problema, ...]:
        """Problemas de los nodos plegados, con su ubicacion; cada fila los vuelve a informar."""
        return self._problemas_plegados

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
        if self._constantes_en_uso:
            producto = {**producto, **self._constantes_en_uso}  # la constante manda
        trozos: list[str] = []
        problemas: list[Problema] = []
        valor: Any = None
        for indice, parte in zip(self._indices, self._partes, strict=True):
            if isinstance(parte, str):
                trozos.append(parte)
            elif isinstance(parte, _Plegado):
                trozos.append(parte.texto)
                valor = parte.valor
                problemas.extend(parte.problemas)
            else:
                texto, valor = _evaluar_variable(parte, indice, producto, problemas)
                trozos.append(texto)
        return Resultado(
            "".join(trozos),
            valor if self._es_variable_unica else None,
            tuple(problemas),
        )


def _es_constante(nodo: NodoResuelto, constantes: Mapping[str, Any]) -> bool:
    """La variable del nodo y las de sus argumentos son constantes."""
    return nodo.nombre in constantes and all(
        argumento.variable is None or argumento.variable in constantes
        for paso in nodo.pasos
        for argumento in paso.argumentos
    )


def _plegar(
    partes: tuple[str | NodoResuelto, ...],
    constantes: Mapping[str, Any],
    es_variable_unica: bool,
) -> tuple[tuple[tuple[int, str | _Plegado | NodoResuelto], ...], tuple[Problema, ...]]:
    """Evalua los nodos constantes una vez. Devuelve (indice de nodo, parte) en orden."""
    if not constantes:
        return tuple(enumerate(partes)), ()
    resultado: list[tuple[int, str | _Plegado | NodoResuelto]] = []
    problemas: list[Problema] = []
    for indice, parte in enumerate(partes):
        if not (isinstance(parte, NodoResuelto) and _es_constante(parte, constantes)):
            resultado.append((indice, parte))
            continue
        del_nodo: list[Problema] = []
        texto, valor = _evaluar_variable(parte, indice, constantes, del_nodo)
        problemas.extend(del_nodo)
        plegado = _Plegado(texto, valor, tuple(del_nodo), parte.tipo_final)
        # Sin problemas y sin valor tipado que conservar, es un texto fijo mas.
        resultado.append((indice, texto if not del_nodo and not es_variable_unica else plegado))
    return _unir_textos(resultado), tuple(problemas)


def _unir_textos(
    partes: list[tuple[int, str | _Plegado | NodoResuelto]],
) -> tuple[tuple[int, str | _Plegado | NodoResuelto], ...]:
    """Junta los textos fijos contiguos: una fila recorre menos trozos."""
    unidas: list[tuple[int, str | _Plegado | NodoResuelto]] = []
    for indice, parte in partes:
        if isinstance(parte, str) and unidas and isinstance(unidas[-1][1], str):
            unidas[-1] = (unidas[-1][0], unidas[-1][1] + parte)
        else:
            unidas.append((indice, parte))
    return tuple(unidas)


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
