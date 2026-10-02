"""Metadatos y contrato de una funcion del catalogo (RF-44).

Cada funcion declara su nombre estable, su familia, los tipos que recibe y el
que devuelve, sus parametros (con tipo y rango) y, si se puede, como cambia el
largo maximo. El comprobador de tipos, el evaluador, el catalogo de la API y la
interfaz leen esos metadatos: agregar una funcion no toca el nucleo.
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.core.entities.texto_enriquecido import CodigoTexto, TipoValor

# `devuelve` de las funciones que responden con el mismo tipo que reciben (`si_vacio`).
MISMO_TIPO = "entrada"


class _SinValor:
    def __repr__(self) -> str:
        return "SIN_VALOR"


SIN_VALOR = _SinValor()


class ValorInvalido(Exception):
    """El valor de esta fila no admite la funcion: se informa como problema de la fila."""

    def __init__(self, codigo: CodigoTexto, detalle: str, parametro: str | None = None) -> None:
        super().__init__(detalle)
        self.codigo = codigo
        self.detalle = detalle
        self.parametro = parametro


@dataclass(frozen=True)
class Parametro:
    """Un parametro de una funcion, con su tipo y sus limites.

    `tipo` es el que debe tener el argumento; None significa "el mismo que recibe
    la funcion" (el valor alternativo de `si_vacio`). Con `acepta_variable` el
    argumento puede ser otra variable en lugar de un literal. `convertir` prepara
    el literal una sola vez al compilar (por ejemplo, un patron de fecha) y lanza
    `ValueError` con el motivo si no sirve.
    """

    nombre: str
    tipo: TipoValor | None
    acepta_variable: bool = False
    por_defecto: Any = SIN_VALOR
    entero: bool = False
    minimo: int | None = None
    maximo: int | None = None
    largo_minimo: int | None = None
    largo_maximo: int | None = None
    convertir: Callable[[Any], Any] | None = None
    # Valores que la interfaz ofrece en un menu. No se imponen al compilar: `opciones_cerradas`
    # dice si la interfaz debe ofrecer solo estas o tambien un valor propio (un patron de fecha).
    opciones: tuple[str, ...] = ()
    opciones_cerradas: bool = False

    @property
    def obligatorio(self) -> bool:
        return self.por_defecto is SIN_VALOR


@dataclass(frozen=True)
class Funcion:
    """Una funcion del catalogo.

    `aplicar(valor, *args)` recibe el valor ya del tipo de `recibe` y los
    argumentos ya normalizados, con los valores por defecto completados. `cota`
    devuelve el largo maximo del resultado dado el del valor de entrada (None si
    no se conoce) y los argumentos literales (None en lugar de un argumento que
    es una variable); si falta, el resultado no tiene cota.
    """

    nombre: str
    familia: str
    recibe: tuple[TipoValor, ...]
    devuelve: TipoValor | str
    aplicar: Callable[..., Any]
    parametros: tuple[Parametro, ...] = ()
    acepta_nulo: bool = False
    cota: Callable[[int | None, tuple[Any, ...]], int | None] | None = None

    @property
    def clave_nombre(self) -> str:
        return f"textoEnriquecido.funcion.{self.nombre}.nombre"

    @property
    def clave_descripcion(self) -> str:
        return f"textoEnriquecido.funcion.{self.nombre}.descripcion"


def normalizar_argumento(parametro: Parametro, valor: Any) -> Any:
    """Comprueba un argumento contra su parametro y lo deja listo para aplicar.

    Sirve para el literal (al compilar) y para el valor de una variable (al
    evaluar). Lanza `ValueError` con el motivo si no cumple.
    """
    if parametro.tipo is TipoValor.NUMERO:
        if isinstance(valor, bool) or not isinstance(valor, (int, Decimal)):
            raise ValueError("se esperaba un numero")
        numero = Decimal(valor)
        if not numero.is_finite():
            raise ValueError("se esperaba un numero finito")
        if parametro.entero:
            if numero != numero.to_integral_value():
                raise ValueError("debe ser un numero entero")
            numero = int(numero)
        if parametro.minimo is not None and numero < parametro.minimo:
            raise ValueError(f"debe ser {parametro.minimo} o mas")
        if parametro.maximo is not None and numero > parametro.maximo:
            raise ValueError(f"debe ser {parametro.maximo} o menos")
        valor = numero
    elif parametro.tipo is TipoValor.TEXTO:
        if not isinstance(valor, str):
            raise ValueError("se esperaba un texto")
        if parametro.largo_minimo is not None and len(valor) < parametro.largo_minimo:
            raise ValueError(_mensaje_largo(parametro))
        if parametro.largo_maximo is not None and len(valor) > parametro.largo_maximo:
            raise ValueError(_mensaje_largo(parametro))
    if parametro.convertir is not None:
        valor = parametro.convertir(valor)
    return valor


def _mensaje_largo(parametro: Parametro) -> str:
    minimo, maximo = parametro.largo_minimo, parametro.largo_maximo
    if minimo is not None and minimo == maximo:
        return f"debe tener exactamente {minimo} caracter(es)"
    if minimo and maximo is not None:
        return f"debe tener entre {minimo} y {maximo} caracteres"
    if minimo:
        return f"debe tener al menos {minimo} caracter(es)"
    return f"debe tener como maximo {maximo} caracteres"


def es_vacio(valor: Any) -> bool:
    """Vacio es None o un texto en blanco: la misma regla con la que MOWA MES excluye un titular."""
    return valor is None or (isinstance(valor, str) and not valor.strip())


_LARGO_MAXIMO_NUMERO = 40


def texto_a_decimal(valor: str) -> Decimal:
    """Un numero escrito con `[+-]digitos[.digitos]`, sin notacion cientifica ni separadores."""
    texto = valor.strip()
    if len(texto) <= _LARGO_MAXIMO_NUMERO:
        digitos = texto[1:] if texto[:1] in ("+", "-") else texto
        entero, punto, decimales = digitos.partition(".")
        if _son_digitos(entero) and (not punto or _son_digitos(decimales)):
            return Decimal(texto)
    raise ValorInvalido(CodigoTexto.NO_ES_NUMERO, f"{valor!r} no es un numero")


def _son_digitos(texto: str) -> bool:
    return bool(texto) and texto.isascii() and texto.isdigit()
