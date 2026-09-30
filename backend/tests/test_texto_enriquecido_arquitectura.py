"""El motor es nucleo: no importa de `adapters/`, de la API ni de infraestructura (D1)."""

import ast
from pathlib import Path

import app.core.entities.texto_enriquecido as entidades
import app.core.services.texto_enriquecido as paquete

PROHIBIDOS = ("app.adapters", "app.api", "fastapi", "sqlalchemy", "starlette", "pydantic")


def _archivos() -> list[Path]:
    carpeta = Path(paquete.__file__).parent
    return [*carpeta.rglob("*.py"), Path(entidades.__file__)]


def _importaciones(ruta: Path) -> list[str]:
    modulos: list[str] = []
    for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            modulos += [alias.name for alias in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            modulos.append(nodo.module)
    return modulos


def test_el_motor_no_importa_infraestructura() -> None:
    archivos = _archivos()
    assert len(archivos) >= 10  # se encontro el paquete, no una carpeta vacia

    for ruta in archivos:
        for modulo in _importaciones(ruta):
            assert not modulo.startswith(PROHIBIDOS), f"{ruta.name} importa {modulo}"


def test_el_motor_no_usa_eval_ni_equivalentes() -> None:
    peligrosos = {"eval", "exec", "compile", "__import__", "getattr", "setattr", "globals"}

    for ruta in _archivos():
        for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
                assert nodo.func.id not in peligrosos, f"{ruta.name} llama a {nodo.func.id}"
