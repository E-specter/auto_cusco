"""Ayudas de las pruebas espejo de i18n: cada codigo del backend tiene su texto en el frontend.

Varios modulos fijan el mismo contrato (un enum de codigos, una clave `<prefijo>.<codigo>` por
codigo en `frontend/src/i18n/{es,en}.json`). Esto lee los diccionarios de verdad, no una copia, y
da el recorrido una sola vez; cada prueba dice su enum y su prefijo.
"""

import json
from collections.abc import Iterable, Mapping
from enum import Enum
from pathlib import Path

I18N = Path(__file__).resolve().parents[3] / "frontend" / "src" / "i18n"
IDIOMAS = ("es", "en")


def diccionario(idioma: str) -> dict[str, str]:
    """El diccionario plano del frontend en ese idioma (`es.json` o `en.json`)."""
    ruta = I18N / f"{idioma}.json"
    assert ruta.exists(), f"No se encontro el diccionario del frontend {ruta}"
    return json.loads(ruta.read_text(encoding="utf-8"))


def claves_de(prefijo: str, idioma: str) -> dict[str, str]:
    """Las entradas del diccionario cuya clave empieza con `<prefijo>.`."""
    return {k: v for k, v in diccionario(idioma).items() if k.startswith(f"{prefijo}.")}


def problemas_de_cobertura(
    codigos: Iterable[Enum], prefijo: str, diccionario_plano: Mapping[str, str]
) -> tuple[list[str], list[str]]:
    """(claves que faltan, claves vacias) de `<prefijo>.<codigo>` para cada codigo."""
    claves = [f"{prefijo}.{codigo.value}" for codigo in codigos]
    faltan = [c for c in claves if c not in diccionario_plano]
    vacias = [c for c in claves if c in diccionario_plano and not diccionario_plano[c]]
    return faltan, vacias


def assert_cubre(enum: type[Enum], prefijo: str, *, ayuda: str = "") -> None:
    """Cada miembro del enum tiene su clave `<prefijo>.<valor>`, con texto, en es.json y en.json."""
    for idioma in IDIOMAS:
        faltan, vacias = problemas_de_cobertura(enum, prefijo, diccionario(idioma))
        assert not faltan, f"Faltan traducciones en {idioma}.json: {faltan}. {ayuda}".rstrip()
        assert not vacias, f"Traducciones vacias en {idioma}.json: {vacias}"
