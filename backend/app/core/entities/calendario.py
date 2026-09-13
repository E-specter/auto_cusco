"""Calendario laboral: dias gestionables y feriados (RF-MM-08).

Transversal: lo usa MOWA MES y lo usaran las demas plataformas. Los feriados
nacionales se calculan por regla para cualquier ano (supuesto S-MM-4); lo que se
persiste son solo las excepciones: dias no laborables decretados que se agregan
y feriados de ley que se retiran por un cambio de ley.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

ZONA_HORARIA = "America/Lima"
LARGO_MAXIMO_DESCRIPCION = 200


class TipoExcepcion(StrEnum):
    AGREGADO = "agregado"  # dia no laborable decretado
    RETIRADO = "retirado"  # feriado de ley que no aplica


class OrigenDia(StrEnum):
    LEY = "ley"
    AGREGADO = "agregado"


@dataclass(frozen=True)
class Feriado:
    """Un feriado nacional calculado por la regla de ley."""

    fecha: date
    descripcion: str


@dataclass(frozen=True)
class ExcepcionCalendario:
    fecha: date
    tipo: TipoExcepcion
    descripcion: str
    creado_en: datetime | None = None


@dataclass(frozen=True)
class DiaNoLaborable:
    """Un dia del calendario de un ano, con su origen.

    Un feriado de ley retirado se devuelve igual, marcado, para que la
    configuracion muestre que se retiro y se pueda restituir.
    """

    fecha: date
    descripcion: str
    origen: OrigenDia
    retirado: bool = False


class ExcepcionInvalida(Exception):
    """La excepcion no tiene sentido sobre la regla de feriados."""


class ExcepcionRepetida(Exception):
    def __init__(self, fecha: date) -> None:
        super().__init__(f"Ya existe una excepcion para el {fecha.isoformat()}")
        self.fecha = fecha


class ExcepcionNoEncontrada(Exception):
    def __init__(self, fecha: date) -> None:
        super().__init__(f"No existe una excepcion para el {fecha.isoformat()}")
        self.fecha = fecha
