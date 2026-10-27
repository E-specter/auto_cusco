"""Configuracion comun de pytest.

Con AUTO_CUSCO_DB_TESTS=1 las pruebas `postgres` escriben en la base configurada,
incluidas filas unicas que se usan al trabajar en la app. Por eso la sesion se
detiene antes de recolectar si esa base no es la de pruebas (sufijo `_test`).
"""

import os

import pytest

from app.api.cartera import obtener_catalogo_cartera
from app.core.config import Settings, exigir_base_de_pruebas
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.main import app


def pytest_configure(config: pytest.Config) -> None:
    if os.environ.get("AUTO_CUSCO_DB_TESTS") != "1":
        return
    motivo = exigir_base_de_pruebas(Settings())
    if motivo:
        pytest.exit(motivo, returncode=4)


@pytest.fixture(autouse=True)
def catalogo_base_sin_base_de_datos():
    """Sin base de pruebas, el catalogo de la cartera de la API es solo la base: leer los campos
    adicionales abriria una conexion. Una prueba que quiera otro lo sobrescribe en su turno."""
    if os.environ.get("AUTO_CUSCO_DB_TESTS") == "1":
        yield
        return
    app.dependency_overrides.setdefault(obtener_catalogo_cartera, lambda: CatalogoCartera())
    yield
    app.dependency_overrides.pop(obtener_catalogo_cartera, None)
