"""Caso de uso: verificar el estado de salud del sistema (API + base de datos).

Sirve como vertical slice minima de referencia para la Fase 0: muestra el
patron puerto/adaptador que seguiran los casos de uso reales (ingesta,
seleccion, generacion de cargas, reportes) a partir de la Fase 1.
"""

from dataclasses import dataclass

from app.core.ports.health_port import DatabaseHealthPort


@dataclass
class HealthStatus:
    api: bool
    database: bool

    @property
    def ok(self) -> bool:
        return self.api and self.database


class HealthService:
    """Orquesta el health-check sin conocer detalles de infraestructura."""

    def __init__(self, database_health_port: DatabaseHealthPort) -> None:
        self._database_health_port = database_health_port

    def check(self) -> HealthStatus:
        return HealthStatus(api=True, database=self._database_health_port.is_available())
