"""Prueba de contrato: el catalogo de codigos coincide con lo que emite el backend.

Recorre el arbol sintactico de `app/` buscando construcciones de `Aviso` e
`Incidencia` con el codigo escrito como literal. Es mas preciso que una busqueda
de texto: distingue la posicion del argumento y no confunde otras cadenas.
"""

import ast
from pathlib import Path

from app.core.entities.incidencias import CODIGOS_INCIDENCIA

RAIZ = Path(__file__).resolve().parents[1] / "app"
# Posicion del codigo en cada constructor: Aviso(codigo, ...) e
# Incidencia(fila, columna, codigo, ...).
POSICION_DEL_CODIGO = {"Aviso": 0, "Incidencia": 2}


def _nombre_llamado(nodo: ast.Call) -> str | None:
    if isinstance(nodo.func, ast.Name):
        return nodo.func.id
    return getattr(nodo.func, "attr", None)


def _codigo_literal(nodo: ast.Call, posicion: int) -> str | None:
    if len(nodo.args) > posicion:
        argumento = nodo.args[posicion]
        if isinstance(argumento, ast.Constant) and isinstance(argumento.value, str):
            return argumento.value
    for clave in nodo.keywords:
        if clave.arg == "codigo" and isinstance(clave.value, ast.Constant):
            valor = clave.value.value
            if isinstance(valor, str):
                return valor
    return None


def codigos_emitidos() -> set[str]:
    codigos: set[str] = set()
    for ruta in RAIZ.rglob("*.py"):
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            posicion = POSICION_DEL_CODIGO.get(_nombre_llamado(nodo) or "")
            if posicion is None:
                continue
            codigo = _codigo_literal(nodo, posicion)
            if codigo is not None:
                codigos.add(codigo)
    return codigos


def test_el_catalogo_coincide_con_los_codigos_que_emite_la_ingesta() -> None:
    emitidos = codigos_emitidos()

    sin_registrar = emitidos - CODIGOS_INCIDENCIA
    sobrantes = CODIGOS_INCIDENCIA - emitidos
    assert not sin_registrar, (
        f"Codigos emitidos que faltan del catalogo de incidencias: {sorted(sin_registrar)}. "
        "Agregalos ahi y tambien a frontend/src/i18n/es.json y en.json."
    )
    assert not sobrantes, (
        f"Codigos registrados que ya nadie emite: {sorted(sobrantes)}. "
        "Quitalos del catalogo y de las traducciones del frontend."
    )


def test_el_catalogo_no_esta_vacio_ni_tiene_codigos_raros() -> None:
    assert len(CODIGOS_INCIDENCIA) >= 20
    assert all(codigo.islower() and " " not in codigo for codigo in CODIGOS_INCIDENCIA)
