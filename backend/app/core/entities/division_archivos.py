"""Division de una carga en archivos: lo que entrega y lo que rechaza (T-MM-C10, L-B9).

Es comun a cualquier plataforma que limite los registros o el tamano de un archivo de carga; los
numeros de cada plataforma los pone su modulo.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar


class ArchivoDemasiadoGrande(Exception):
    """Una sola fila ya supera el tamano maximo: no hay division posible."""


class FilaDividible(Protocol):
    """Una fila de carga: solo importa si es de supervision (va al inicio, en el primer archivo)."""

    @property
    def supervision(self) -> bool: ...


F = TypeVar("F", bound=FilaDividible)


@dataclass(frozen=True)
class TramoPrevisto:
    """Un archivo estimado por filas, sin escribirlo."""

    numero: int
    filas: int
    supervision: int


@dataclass(frozen=True)
class Tramo(Generic[F]):  # noqa: UP046 - el proyecto apunta a py311, sin sintaxis PEP 695
    """Un archivo ya escrito: sus filas, en el orden de la carga, y su contenido."""

    filas: Sequence[F]
    contenido: bytes

    @property
    def supervision(self) -> int:
        return sum(1 for fila in self.filas if fila.supervision)
