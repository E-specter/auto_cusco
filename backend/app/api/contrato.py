"""Contrato OpenAPI de la API, versionado en `contratos/openapi.json`.

El frontend escribe sus tipos contra ese archivo en vez de contra lo que cree
que responde el backend. Para que sirva, tiene que coincidir siempre con la API
real: `tests/test_contrato_openapi.py` falla si alguien cambia un endpoint y no
lo regenera. Ver docs/contrato-api.md.
"""

import json
from pathlib import Path
from typing import Any

# backend/app/api/contrato.py -> raiz del repositorio
RUTA_CONTRATO = Path(__file__).resolve().parents[3] / "contratos" / "openapi.json"
COMANDO_REGENERAR = "uv run python scripts/exportar_openapi.py (desde backend/)"


def generar() -> dict[str, Any]:
    """Esquema OpenAPI de la aplicacion, tal como lo serializa JSON."""
    from app.main import app

    app.openapi_schema = None  # sin cache: siempre refleja los routers actuales
    return json.loads(json.dumps(app.openapi()))


def serializar(esquema: dict[str, Any]) -> str:
    """Texto estable: mismo esquema, mismos bytes, diffs legibles en git."""
    return json.dumps(esquema, ensure_ascii=False, indent=2) + "\n"


def leer(ruta: Path = RUTA_CONTRATO) -> dict[str, Any] | None:
    """El contrato versionado, o None si todavia no existe.

    Se compara ya interpretado, no como texto, para que el fin de linea que
    ponga git en Windows no cuente como diferencia.
    """
    if not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))


def escribir(ruta: Path = RUTA_CONTRATO) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(serializar(generar()), encoding="utf-8", newline="\n")
    return ruta
