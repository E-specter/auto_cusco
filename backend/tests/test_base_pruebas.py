"""La integracion nunca corre contra la base de trabajo (docs/testing.md, seccion 4)."""

import os
import subprocess
import sys
from pathlib import Path

from app.core.config import Settings, exigir_base_de_pruebas

BACKEND = Path(__file__).resolve().parents[1]


def test_una_base_con_sufijo_test_es_de_pruebas() -> None:
    assert exigir_base_de_pruebas(Settings(db_name="auto_cusco_test")) is None


def test_la_base_de_trabajo_no_es_de_pruebas() -> None:
    motivo = exigir_base_de_pruebas(Settings(db_name="auto_cusco"))

    assert motivo is not None
    assert "'auto_cusco'" in motivo


def test_contener_test_sin_ser_el_sufijo_no_basta() -> None:
    assert exigir_base_de_pruebas(Settings(db_name="auto_cusco_test_copia")) is not None


def _recolectar_con_base(db_name: str) -> subprocess.CompletedProcess[str]:
    entorno = {**os.environ, "AUTO_CUSCO_DB_TESTS": "1", "DB_NAME": db_name}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/test_base_pruebas.py",
        ],
        cwd=BACKEND,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_pytest_se_detiene_con_integracion_contra_la_base_de_trabajo() -> None:
    resultado = _recolectar_con_base("auto_cusco")

    assert resultado.returncode == 4
    assert "no termina en '_test'" in resultado.stdout + resultado.stderr


def test_pytest_sigue_con_integracion_contra_la_base_de_pruebas() -> None:
    resultado = _recolectar_con_base("auto_cusco_test")

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
