"""Funciones de texto (seccion 6): recortes, mayusculas, limpieza y relleno.

Ninguna alarga el texto de forma imprevista: mayusculas, minusculas y sin_tildes
trabajan caracter por caracter y dejan igual el que cambiaria de largo (la `ß`,
la `İ`, una silaba hangul), para que el largo maximo de la expresion se pueda
calcular (cota.py).
"""

import unicodedata

from app.core.entities.texto_enriquecido import TipoValor

from ..gsm7 import a_gsm7
from .base import Funcion, Parametro

T = TipoValor.TEXTO
_LARGO_MAXIMO_TEXTO = 200


def _primeros(valor: str, n: int) -> str:
    return valor[:n]


def _ultimos(valor: str, n: int) -> str:
    return valor[-n:]


def _cota_recorte(entrada: int | None, args: tuple) -> int | None:
    n = args[0]
    return n if entrada is None else min(n, entrada)


def _conservar_largo(entrada: int | None, args: tuple) -> int | None:
    return entrada


def _mayusculas(valor: str) -> str:
    if valor.isascii():
        return valor.upper()
    return "".join(m if len(m := c.upper()) == 1 else c for c in valor)


def _minusculas(valor: str) -> str:
    if valor.isascii():
        return valor.lower()
    return "".join(m if len(m := c.lower()) == 1 else c for c in valor)


def _capitalizar(valor: str) -> str:
    return _mayusculas(valor[:1]) + _minusculas(valor[1:])


def _recortar(valor: str) -> str:
    return " ".join(valor.split())


def _sin_marcas(caracter: str) -> str:
    base = "".join(
        c for c in unicodedata.normalize("NFD", caracter) if not unicodedata.combining(c)
    )
    if len(base) <= 1:
        return base
    return caracter  # se descompone en varios caracteres que no son marcas: no se toca


def _sin_tildes(valor: str) -> str:
    if valor.isascii():
        return valor
    return "".join(c if c.isascii() else _sin_marcas(c) for c in valor)


def _reemplazar(valor: str, buscar: str, reemplazo: str) -> str:
    return valor.replace(buscar, reemplazo)


def _cota_gsm7(entrada: int | None, args: tuple) -> int | None:
    """El triple de la entrada: es un tope verdadero (RF-47), en caracteres y en unidades GSM-7.

    El peor caso de `a_gsm7` es `…` o `€`: 1 caracter pasa a 3 (y mide 3); los demas extendidos
    pasan a 1 o se borran. El supuesto de «1 por caracter en las variables» que usa MOWA MES no
    vive en esta funcion sino en como ese conector mide el texto (`compilar(..., medida=...)`, con
    la variable cruda y la normalizacion aplicada al texto ya evaluado).
    """
    return None if entrada is None else 3 * entrada


def _cota_reemplazar(entrada: int | None, args: tuple) -> int | None:
    if entrada is None:
        return None
    buscar, reemplazo = args
    apariciones = entrada // len(buscar)
    return entrada + apariciones * max(0, len(reemplazo) - len(buscar))


def _rellenar_izquierda(valor: str, largo: int, relleno: str) -> str:
    return valor.rjust(largo, relleno)


def _cota_relleno(entrada: int | None, args: tuple) -> int | None:
    return None if entrada is None else max(entrada, args[0])


_N = Parametro("n", TipoValor.NUMERO, entero=True, minimo=1, maximo=10_000)

FUNCIONES = (
    Funcion("primeros", "texto", (T,), T, _primeros, (_N,), cota=_cota_recorte),
    Funcion("ultimos", "texto", (T,), T, _ultimos, (_N,), cota=_cota_recorte),
    Funcion("mayusculas", "texto", (T,), T, _mayusculas, cota=_conservar_largo),
    Funcion("minusculas", "texto", (T,), T, _minusculas, cota=_conservar_largo),
    Funcion("capitalizar", "texto", (T,), T, _capitalizar, cota=_conservar_largo),
    Funcion("recortar", "texto", (T,), T, _recortar, cota=_conservar_largo),
    Funcion("sin_tildes", "texto", (T,), T, _sin_tildes, cota=_conservar_largo),
    Funcion("a_gsm7", "texto", (T,), T, a_gsm7, cota=_cota_gsm7),
    Funcion(
        "reemplazar",
        "texto",
        (T,),
        T,
        _reemplazar,
        (
            Parametro("buscar", T, largo_minimo=1, largo_maximo=_LARGO_MAXIMO_TEXTO),
            Parametro("reemplazo", T, largo_maximo=_LARGO_MAXIMO_TEXTO),
        ),
        cota=_cota_reemplazar,
    ),
    Funcion(
        "rellenar_izquierda",
        "texto",
        (T,),
        T,
        _rellenar_izquierda,
        (
            Parametro("largo", TipoValor.NUMERO, entero=True, minimo=1, maximo=1000),
            Parametro("relleno", T, largo_minimo=1, largo_maximo=1),
        ),
        cota=_cota_relleno,
    ),
)
