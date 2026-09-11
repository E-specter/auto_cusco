"""Puerto para verificar la disponibilidad de la base de datos."""

from typing import Protocol


class DatabaseHealthPort(Protocol):
    """Cualquier adaptador de persistencia que quiera participar del
    health-check debe implementar este puerto."""

    def is_available(self) -> bool:
        """Retorna True si la base de datos responde correctamente."""
        ...
