"""Un .xlsb guardado desde una carpeta de ruta larga se lee (T-SAB-1): regresion de calamine 0.8.2.

El `.xlsb` del 26.10 daba 400 («no tiene hojas»). La causa NO es la Tabla de Excel que trae: es el
registro 2071 de `xl/workbook.bin` (BrtAbsPath15), donde Excel graba la carpeta desde la que se
guardo el libro. Esa del 26.10 medía 70 caracteres y python-calamine 0.8.2 daba 0 hojas; desde la
0.9.0 se lee. Cambiando solo ese registro de un libro sano, con la 0.8.2, entre 10 y 200 caracteres
solo fallan 70 (0 hojas) y 76 (panico de Rust): un largo del registro de 2 bytes NO basta.

Dos fixtures SINTETICOS (filas inventadas, telefonos 900000xxx, carpeta inventada), generados con
`scripts/generar_fixture_xlsb_con_tabla.py`: `sabana_ruta_larga.xlsb` (ruta de 70 caracteres: falla
con 0.8.2) y `sabana_ruta_corta.xlsb`, de control (30 caracteres: pasa con las dos).
"""

import zipfile
from pathlib import Path

import pytest

from app.adapters.input.lector_calamine import LectorCalamine
from app.adapters.input.lector_tabla import LectorTabla
from app.core.entities.lectura_tabla import FormatoTabla
from app.core.services.ingesta_sabana.cabeceras import mapear_cabeceras
from app.core.services.ingesta_sabana.normalizador import normalizar_fila
from scripts.generar_fixture_xlsb_con_tabla import ruta_grabada

DATOS = Path(__file__).parent / "datos"
LARGA = DATOS / "sabana_ruta_larga.xlsb"
CORTA = DATOS / "sabana_ruta_corta.xlsb"
AMBOS = pytest.mark.parametrize("fixture", [LARGA, CORTA], ids=["ruta_larga", "ruta_corta"])


def test_el_fixture_largo_graba_una_ruta_de_70_caracteres() -> None:
    carga, bytes_del_largo = ruta_grabada(LARGA)

    assert ((carga - 4) // 2, bytes_del_largo) == (70, 2)  # lo que dejaba a la 0.8.2 sin hojas


def test_el_fixture_de_control_graba_una_ruta_de_30_caracteres() -> None:
    carga, bytes_del_largo = ruta_grabada(CORTA)

    assert ((carga - 4) // 2, bytes_del_largo) == (30, 1)


@AMBOS
def test_el_fixture_tambien_trae_la_tabla_de_excel_pero_esa_no_es_la_causa(fixture) -> None:
    with zipfile.ZipFile(fixture) as zip_:
        assert [n for n in zip_.namelist() if n.startswith("xl/tables/")] == [
            "xl/tables/table1.bin"
        ]


@AMBOS
def test_calamine_lista_la_hoja(fixture) -> None:
    tabla = LectorCalamine().leer_tabla(fixture.read_bytes(), formato=FormatoTabla.XLSB)

    assert tabla.hojas == ("VENCIDA",)


@AMBOS
def test_el_lector_lee_el_xlsb_con_sus_filas(fixture) -> None:
    tabla = LectorTabla().leer(fixture.read_bytes(), "sabana.xlsb")

    assert (tabla.formato, tabla.hojas, tabla.hoja) == (FormatoTabla.XLSB, ("VENCIDA",), "VENCIDA")
    assert tabla.cabeceras == [
        "Pagare",
        "Titular",
        "Teléfono",
        "Región",
        "Saldo Capital Pendiente",
    ]
    assert [(f.numero_fila, f.celdas[0]) for f in tabla.filas] == [
        (2, "000000000000000001"),
        (3, "000000000000000002"),
        (4, "000000000000000003"),
    ]
    assert tabla.filas[0].celdas == [
        "000000000000000001",
        "APELLIDO/NOMBRE FICTICIO",
        900000001.0,
        "REGION PRUEBA",
        1500.5,
    ]


@AMBOS
def test_las_filas_se_normalizan_como_las_de_cualquier_sabana(fixture) -> None:
    tabla = LectorTabla().leer(fixture.read_bytes(), "sabana.xlsb")
    mapeo = mapear_cabeceras(tabla.cabeceras)

    fila = normalizar_fila(tabla.filas[0].celdas, mapeo, tabla.filas[0].numero_fila)

    assert fila.clave == "000000000000000001"
    assert fila.valores["telefono"] == "900000001"
    assert str(fila.valores["saldo_capital_pendiente"]) == "1500.50"
    assert not [i for i in fila.incidencias if i.severidad.value == "error"]
