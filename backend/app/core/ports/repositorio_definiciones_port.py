"""Puerto de persistencia de las definiciones de columnas guardadas y sus versiones."""

from collections.abc import Mapping
from typing import Any, Protocol

from app.core.entities.definiciones_columnas import (
    DefinicionGuardada,
    ResumenDefinicion,
    VersionDefinicion,
)


class RepositorioDefinicionesPort(Protocol):
    def listar(self) -> list[ResumenDefinicion]:
        """Todas, ordenadas por nombre."""
        ...

    def obtener(self, definicion_id: int) -> DefinicionGuardada | None:
        """La definicion con todas sus versiones, o None si no existe."""
        ...

    def crear(self, nombre: str, contenido: Mapping[str, Any]) -> DefinicionGuardada:
        """Crea la definicion con su version 1. Lanza NombreDeDefinicionRepetido si el nombre ya
        existe, sin distinguir mayusculas."""
        ...

    def agregar_version(
        self, definicion_id: int, contenido: Mapping[str, Any]
    ) -> VersionDefinicion | None:
        """Crea la version siguiente y la deja vigente. None si la definicion no existe."""
        ...

    def marcar_version_usada(self, definicion_id: int, numero: int) -> bool:
        """Marca `usada_en` la primera vez y no la cambia despues. False si no existe."""
        ...
