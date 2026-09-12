"""Genera una sabana de prueba con datos totalmente inventados.

Python no puede escribir .xlsb, asi que el archivo se crea en .xlsx y, si el
destino termina en .xlsb, se convierte con Excel (Windows). Sirve para probar
la ingesta sin tocar sabanas reales, como exige /AGENTS.md.

Uso, desde backend/:

    uv run python scripts/generar_sabana_sintetica.py "..\data\sabanas\SINTETICA - 26.09.2026.xlsb"
    uv run python scripts/generar_sabana_sintetica.py salida.xlsx --filas 46000

Incluye a proposito casos borde: DNI de 7 digitos (cero perdido), RUC valido,
telefonos invalidos, un pagare repetido y una columna fuera del catalogo.
"""

import argparse
import random
import string
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openpyxl  # noqa: E402

from tests.test_sabana_cabeceras import CABECERAS_10_09  # noqa: E402
from tests.test_sabana_normalizador import _fila_sintetica  # noqa: E402

XL_EXCEL_12 = 50  # formato .xlsb en la API de Excel
PESOS_RUC = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
REGIONES = ("CUSCO SUR", "CUSCO NORTE", "PUNO SUR", "TACNA", "AREQUIPA NORTE")


def _ruc(azar: random.Random, prefijo: str = "20") -> int:
    base = prefijo + "".join(azar.choice(string.digits) for _ in range(8))
    resto = 11 - sum(int(d) * p for d, p in zip(base, PESOS_RUC, strict=True)) % 11
    return int(base + str(0 if resto == 10 else 1 if resto == 11 else resto))


def _nombre(azar: random.Random) -> str:
    letras = lambda n: "".join(azar.choice(string.ascii_uppercase) for _ in range(n))  # noqa: E731
    return f"{letras(7)}/{letras(6)},{letras(5)} {letras(4)}"


def generar_xlsx(destino: Path, filas: int, semilla: int) -> None:
    azar = random.Random(semilla)
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "VENCIDA"
    hoja.append([*CABECERAS_10_09, "Columna Nueva Del Origen"])
    for i in range(1, filas + 1):
        # La 7.a fila de datos (fila 8 de la hoja) repite el pagare de la anterior.
        pagare = f"{6 if i == 7 else i:018d}"
        documento = (
            _ruc(azar)
            if i % 500 == 0
            else azar.choice(
                [azar.randint(1_000_000, 9_999_999), azar.randint(10_000_000, 99_999_999)]
            )
        )
        telefono = (
            azar.randint(100_000_000, 899_999_999)  # invalido: no empieza en 9
            if i % 300 == 0
            else azar.randint(900_000_000, 999_999_999)
        )
        fila = _fila_sintetica(
            **{
                "Región": azar.choice(REGIONES),
                "Titular": _nombre(azar),
                "Analista": _nombre(azar),
                "Analista Actual": _nombre(azar),
                "DniRuc": float(documento),
                "Teléfono": float(telefono),
                "Pagare": pagare,
                "PAGARE": pagare,
                "Saldo Capital Pendiente": round(azar.uniform(50, 250_000), 2),
                "Monto Cuota": round(azar.uniform(20, 9_000), 2),
                "Dias Atraso Hoy": float(azar.randint(-8, 71)),
                "DÍAS SICMAC-C": float(azar.randint(-8, 71)),
            }
        )
        hoja.append([*fila, f"valor libre {i % 13}"])
    libro.save(destino)


def convertir_a_xlsb(origen: Path, destino: Path) -> None:
    """Convierte con Excel: es la unica via practica de producir .xlsb."""
    guion = f"""
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
try {{
  $libro = $excel.Workbooks.Open('{origen}')
  $libro.SaveAs('{destino}', {XL_EXCEL_12})
  $libro.Close($false)
}} finally {{
  $excel.Quit()
}}
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", guion],
        check=True,
        capture_output=True,
    )


def main() -> None:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("destino", type=Path, help="archivo .xlsx o .xlsb a generar")
    analizador.add_argument("--filas", type=int, default=5000)
    analizador.add_argument("--semilla", type=int, default=26)
    opciones = analizador.parse_args()

    destino: Path = opciones.destino.resolve()
    if destino.suffix.lower() == ".xlsb":
        with tempfile.TemporaryDirectory() as temporal:
            intermedio = Path(temporal) / "sabana.xlsx"
            generar_xlsx(intermedio, opciones.filas, opciones.semilla)
            convertir_a_xlsb(intermedio, destino)
    else:
        generar_xlsx(destino, opciones.filas, opciones.semilla)
    print(f"{destino} generado con {opciones.filas} filas de datos inventados")


if __name__ == "__main__":
    main()
