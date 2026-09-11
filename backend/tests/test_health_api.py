"""Prueba de integracion liviana del endpoint /health, sin base de datos real:
se sustituye la dependencia del servicio de health-check por un doble de prueba.
"""

from fastapi.testclient import TestClient

from app.api.health import get_health_service
from app.core.services.health_service import HealthStatus
from app.main import app


class _FakeHealthService:
    def check(self) -> HealthStatus:
        return HealthStatus(api=True, database=True)


def test_health_endpoint_returns_ok_when_dependencies_are_healthy() -> None:
    app.dependency_overrides[get_health_service] = lambda: _FakeHealthService()
    try:
        client = TestClient(app)
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"api": True, "database": True, "ok": True}
