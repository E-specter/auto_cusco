"""Configuracion comun de pytest.

Con AUTO_CUSCO_DB_TESTS=1 las pruebas `postgres` escriben en la base configurada,
incluidas filas unicas que se usan al trabajar en la app. Por eso la sesion se
detiene antes de recolectar si esa base no es la de pruebas (sufijo `_test`).
"""

import os

import pytest

from app.core.config import Settings, exigir_base_de_pruebas


def pytest_configure(config: pytest.Config) -> None:
    if os.environ.get("AUTO_CUSCO_DB_TESTS") != "1":
        return
    motivo = exigir_base_de_pruebas(Settings())
    if motivo:
        pytest.exit(motivo, returncode=4)
