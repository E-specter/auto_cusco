"""Puerto de persistencia de las excepciones del calendario laboral."""

from datetime import date
from typing import Protocol

from app.core.entities.calendario import ExcepcionCalendario


class RepositorioCalendarioPort(Protocol):
    def listar_excepciones(
        self, desde: date | None = None, hasta: date | None = None
    ) -> list[ExcepcionCalendario]:
        """Ordenadas por fecha; los limites son inclusivos."""
        ...

    def agregar_excepcion(self, excepcion: ExcepcionCalendario) -> ExcepcionCalendario:
        """Lanza ExcepcionRepetida si ya hay una excepcion para esa fecha."""
        ...

    def eliminar_excepcion(self, fecha: date) -> bool:
        """False si no existia."""
        ...
