"""Puerto de persistencia de las selecciones de cartera guardadas."""

from typing import Protocol

from app.core.entities.selecciones import DatosSeleccion, SeleccionGuardada


class RepositorioSeleccionesPort(Protocol):
    def listar(self) -> list[SeleccionGuardada]:
        """Todas, ordenadas por nombre."""
        ...

    def obtener(self, seleccion_id: int) -> SeleccionGuardada | None: ...

    def crear(self, datos: DatosSeleccion) -> SeleccionGuardada:
        """Lanza NombreDeSeleccionRepetido si el nombre ya existe, sin distinguir mayusculas."""
        ...

    def actualizar(self, seleccion_id: int, datos: DatosSeleccion) -> SeleccionGuardada | None:
        """None si no existe; NombreDeSeleccionRepetido si el nombre choca con otra."""
        ...

    def eliminar(self, seleccion_id: int) -> bool:
        """False si no existia."""
        ...
