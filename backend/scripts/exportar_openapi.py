r"""Exporta el contrato OpenAPI de la API a contratos/openapi.json.

Uso, desde backend/:

    uv run python scripts/exportar_openapi.py              # regenera el archivo
    uv run python scripts/exportar_openapi.py --comprobar  # falla si esta desactualizado

El archivo se versiona: el frontend comprueba sus tipos contra el (ver
docs/contrato-api.md). La prueba tests/test_contrato_openapi.py hace la misma
comprobacion en cada corrida de pytest, asi que no hace falta recordar correr
--comprobar a mano.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api import contrato  # noqa: E402


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument(
        "--comprobar",
        action="store_true",
        help="no escribe; termina con error si el contrato versionado no coincide con la API",
    )
    opciones = analizador.parse_args()

    if opciones.comprobar:
        if contrato.leer() != contrato.generar():
            print(f"El contrato esta desactualizado. Regeneralo con: {contrato.COMANDO_REGENERAR}")
            return 1
        print(f"{contrato.RUTA_CONTRATO} coincide con la API")
        return 0

    print(f"{contrato.escribir()} actualizado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
