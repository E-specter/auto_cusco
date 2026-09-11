"""Pruebas del caso de uso de health-check (app/core/services/health_service.py).

No requieren una base de datos real: se sustituye el puerto por un doble de
prueba, demostrando la ventaja de testabilidad del enfoque puertos/adaptadores.
"""

from app.core.services.health_service import HealthService


class _FakeHealthPort:
    def __init__(self, available: bool) -> None:
        self._available = available

    def is_available(self) -> bool:
        return self._available


def test_health_service_ok_when_database_available() -> None:
    service = HealthService(database_health_port=_FakeHealthPort(True))

    status = service.check()

    assert status.api is True
    assert status.database is True
    assert status.ok is True


def test_health_service_not_ok_when_database_unavailable() -> None:
    service = HealthService(database_health_port=_FakeHealthPort(False))

    status = service.check()

    assert status.database is False
    assert status.ok is False
