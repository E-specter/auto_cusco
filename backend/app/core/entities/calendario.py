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
# Cuantos dias gestionables se ofrecen como maximo al programar un envio (RF-71, RF-32). La unica
# fuente del numero: `Settings` lo valida y el servicio lo usa.
MAXIMO_PROXIMOS_POR_DEFECTO = 31


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


class ProximosFueraDeRango(Exception):
    """El N de los proximos dias gestionables no esta entre 1 y el tope (RF-71)."""

    def __init__(self, pedido: int, minimo: int, maximo: int) -> None:
        super().__init__(f"Se pidieron {pedido} dias; N va de {minimo} a {maximo}")
        self.pedido = pedido
        self.minimo = minimo
        self.maximo = maximo


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
