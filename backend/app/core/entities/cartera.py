"""Entidades de seleccion, filtrado, segmentacion y metricas de cartera.

Cubre RF-04 a RF-06, RF-08 y RF-25 a RF-28. La cartera de una fecha es el
contenido de su version vigente (docs/versionado-sabanas.md).
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any


class TipoDato(StrEnum):
    """Tipo logico de un campo de cartera; decide que operadores admite."""

    TEXTO = "texto"
    NUMERO = "numero"
    FECHA = "fecha"
    BOOLEANO = "booleano"


class Operador(StrEnum):
    IGUAL = "igual"
    DISTINTO = "distinto"
    MAYOR = "mayor"
    MAYOR_IGUAL = "mayor_igual"
    MENOR = "menor"
    MENOR_IGUAL = "menor_igual"
    CONTIENE = "contiene"
    EMPIEZA_CON = "empieza_con"
    EN = "en"
    ENTRE = "entre"
    VACIO = "vacio"
    NO_VACIO = "no_vacio"


_COMUNES = (Operador.IGUAL, Operador.DISTINTO, Operador.EN, Operador.VACIO, Operador.NO_VACIO)
_ORDENABLES = (
    Operador.MAYOR,
    Operador.MAYOR_IGUAL,
    Operador.MENOR,
    Operador.MENOR_IGUAL,
    Operador.ENTRE,
)

OPERADORES_POR_TIPO: dict[TipoDato, frozenset[Operador]] = {
    TipoDato.TEXTO: frozenset((*_COMUNES, Operador.CONTIENE, Operador.EMPIEZA_CON)),
    TipoDato.NUMERO: frozenset((*_COMUNES, *_ORDENABLES)),
    TipoDato.FECHA: frozenset((*_COMUNES, *_ORDENABLES)),
    TipoDato.BOOLEANO: frozenset((Operador.IGUAL, Operador.VACIO, Operador.NO_VACIO)),
}

# Cuantos valores necesita cada operador. None = uno o mas.
VALORES_POR_OPERADOR: dict[Operador, int | None] = {
    Operador.IGUAL: 1,
    Operador.DISTINTO: 1,
    Operador.MAYOR: 1,
    Operador.MAYOR_IGUAL: 1,
    Operador.MENOR: 1,
    Operador.MENOR_IGUAL: 1,
    Operador.CONTIENE: 1,
    Operador.EMPIEZA_CON: 1,
    Operador.EN: None,
    Operador.ENTRE: 2,
    Operador.VACIO: 0,
    Operador.NO_VACIO: 0,
}


class Funcion(StrEnum):
    """Funciones simples de RF-27: nada mas complejo, para no saturar el tiempo real."""

    SUMA = "suma"
    CONTEO = "conteo"
    PROMEDIO = "promedio"
    MINIMO = "minimo"
    MAXIMO = "maximo"


@dataclass(frozen=True)
class Filtro:
    campo: str
    operador: Operador
    valores: tuple[Any, ...] = ()


@dataclass(frozen=True)
class Orden:
    campo: str
    descendente: bool = False


@dataclass(frozen=True)
class Indicador:
    """Indicador adicional definido por el usuario (RF-27)."""

    nombre: str
    funcion: Funcion
    campo: str | None = None  # CONTEO puede no llevar campo


@dataclass(frozen=True)
class PaginaCartera:
    """Resultado de una seleccion, con el aviso de insuficiencia de RF-08."""

    total: int
    filas: tuple[dict[str, Any], ...]
    limite: int
    desplazamiento: int = 0

    @property
    def suficiente(self) -> bool:
        """False cuando se pidieron mas productos de los que hay disponibles."""
        return self.total >= self.limite + self.desplazamiento


@dataclass(frozen=True)
class MetricasCartera:
    """Indicadores minimos de RF-26 mas los adicionales de RF-27."""

    cuentas: int
    capital_total: Decimal
    cuota_minima: Decimal | None
    cuota_maxima: Decimal | None
    cuentas_por_segmento: dict[str, int]
    adicionales: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Grupo:
    valor: Any
    cuentas: int
    capital: Decimal


@dataclass(frozen=True)
class Segmentacion:
    """Analisis por atributo (RF-06): cuentas y capital por cada valor del campo."""

    campo: str
    grupos: tuple[Grupo, ...]


class ConsultaInvalida(Exception):
    """La consulta pide un campo, operador o valor que no existe o no aplica."""


class SinVersionVigente(Exception):
    def __init__(self, fecha_corte: Any) -> None:
        super().__init__(f"La fecha {fecha_corte} no tiene una version vigente de sabana")
        self.fecha_corte = fecha_corte
