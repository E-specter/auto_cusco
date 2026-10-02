"""Funciones de numero (seccion 6). Los montos son `Decimal`, nunca `float`.

Un resultado que no cabe en la precision de `Decimal` lo informa el evaluador
como `resultado_fuera_de_rango` (captura `ArithmeticError`).
"""

from decimal import ROUND_HALF_UP, Decimal

from app.core.entities.mapeo import FormatoFinanciero
from app.core.entities.texto_enriquecido import CodigoTexto, TipoValor
from app.core.services.mapeo_campos.formatos import formatear_importe

from .base import Funcion, Parametro, ValorInvalido, texto_a_decimal

N, T = TipoValor.NUMERO, TipoValor.TEXTO


def _sumar(valor: Decimal, x: Decimal) -> Decimal:
    return valor + x


def _restar(valor: Decimal, x: Decimal) -> Decimal:
    return valor - x


def _multiplicar(valor: Decimal, x: Decimal) -> Decimal:
    return valor * x


def _dividir(valor: Decimal, x: Decimal) -> Decimal:
    if x == 0:
        raise ValorInvalido(CodigoTexto.DIVISION_POR_CERO, "No se puede dividir por cero", "valor")
    return valor / x


def redondear_mitad_arriba(valor: Decimal, decimales: int) -> Decimal:
    """A la mitad hacia arriba (lejos del cero), como los montos de MOWA MES."""
    return valor.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)


def _formato_numero(valor: Decimal, decimales: int, miles: str, decimal: str) -> str:
    formato = FormatoFinanciero(
        separador_miles=miles, separador_decimal=decimal, decimales=decimales
    )
    return formatear_importe(redondear_mitad_arriba(valor, decimales), formato)


def _a_numero(valor: str) -> Decimal:
    return texto_a_decimal(valor)


def _a_texto(valor: Decimal | object) -> str:
    if isinstance(valor, Decimal):
        return format(valor, "f")
    return str(valor)  # fecha: AAAA-MM-DD


def _redondear(valor: Decimal, decimales: int) -> Decimal:
    return redondear_mitad_arriba(valor, decimales)


_X = Parametro("valor", N, acepta_variable=True)
_DECIMALES = Parametro("decimales", N, entero=True, minimo=0, maximo=6)


FUNCIONES = (
    Funcion("sumar", "numero", (N,), N, _sumar, (_X,)),
    Funcion("restar", "numero", (N,), N, _restar, (_X,)),
    Funcion("multiplicar", "numero", (N,), N, _multiplicar, (_X,)),
    Funcion("dividir", "numero", (N,), N, _dividir, (_X,)),
    Funcion("redondear", "numero", (N,), N, _redondear, (_DECIMALES,)),
    Funcion(
        "formato_numero",
        "numero",
        (N,),
        T,
        _formato_numero,
        (
            Parametro("decimales", N, entero=True, minimo=0, maximo=6, por_defecto=2),
            Parametro(
                "miles",
                T,
                largo_maximo=1,
                por_defecto=",",
                opciones=(",", ".", " ", ""),
                opciones_cerradas=True,
            ),
            Parametro(
                "decimal",
                T,
                largo_minimo=1,
                largo_maximo=1,
                por_defecto=".",
                opciones=(".", ","),
                opciones_cerradas=True,
            ),
        ),
    ),
    Funcion("a_numero", "conversion", (T,), N, _a_numero),
    Funcion("a_texto", "conversion", (N, TipoValor.FECHA), T, _a_texto),
)
