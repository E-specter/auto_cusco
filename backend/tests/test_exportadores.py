"""Pruebas de los exportadores de tablas a archivo (RF-13).

Lo que se verifica es lo que se rompe en produccion: los ceros a la izquierda
del pagare, los importes con sus decimales, las fechas, las celdas vacias y las
codificaciones que piden algunas plataformas.
"""

import io
import json
from datetime import date
from decimal import Decimal

import openpyxl
import pytest

from app.adapters.output import exportadores
from app.adapters.output.exportadores import comunes, exportador_xlsx
from app.core.entities.exportacion import (
    ExportacionInvalida,
    FormatoArchivo,
    FormatoNoSoportado,
    OpcionesArchivo,
    Tabla,
)

TABLA = Tabla(
    nombre="SMS preventiva",
    cabeceras=("pagare", "numero", "deuda", "vence", "titular"),
    filas=(
        {
            "pagare": "000000000000000001",
            "numero": "51987654321",
            "deuda": Decimal("1500.50"),
            "vence": date(2026, 9, 18),
            "titular": "APELLIDO, NOMBRE",
        },
        {
            "pagare": "000000000000000002",
            "numero": "51",  # producto sin telefono: queda el prefijo
            "deuda": None,
            "vence": None,
            "titular": "SEÑOR AÑAÑOS",
        },
    ),
)


def _texto(formato: str, opciones: OpcionesArchivo | None = None) -> str:
    archivo = exportadores.exportar(TABLA, formato, opciones or OpcionesArchivo())
    return archivo.contenido.decode((opciones or OpcionesArchivo()).codificacion)


# --- CSV ---------------------------------------------------------------


def test_csv_escribe_cabeceras_y_filas() -> None:
    lineas = _texto("csv").split("\r\n")

    assert lineas[0] == "pagare,numero,deuda,vence,titular"
    assert lineas[1] == '000000000000000001,51987654321,1500.50,2026-09-18,"APELLIDO, NOMBRE"'
    assert lineas[2] == "000000000000000002,51,,,SEÑOR AÑAÑOS"  # los vacios quedan vacios


def test_csv_respeta_el_delimitador_y_puede_ir_sin_cabeceras() -> None:
    texto = _texto("csv", OpcionesArchivo(delimitador=";", con_cabeceras=False))

    assert texto.startswith("000000000000000001;51987654321;1500.50")
    assert "pagare;numero" not in texto


def test_csv_para_excel_lleva_marca_de_orden_de_bytes() -> None:
    archivo = exportadores.exportar(TABLA, "csv", OpcionesArchivo(codificacion="utf-8-sig"))

    assert archivo.contenido.startswith(b"\xef\xbb\xbf")
    assert archivo.tipo_mime == "text/csv; charset=utf-8-sig"


def test_csv_avisa_si_un_caracter_no_cabe_en_la_codificacion_pedida() -> None:
    tabla = Tabla(nombre="x", cabeceras=("titular",), filas=({"titular": "KOJIMA 小島"},))

    with pytest.raises(ExportacionInvalida, match="latin-1"):
        exportadores.exportar(tabla, "csv", OpcionesArchivo(codificacion="latin-1"))


@pytest.mark.parametrize("delimitador", ["", ";;"])
def test_csv_rechaza_un_delimitador_que_no_sea_un_caracter(delimitador) -> None:
    with pytest.raises(ExportacionInvalida, match="delimitador"):
        exportadores.exportar(TABLA, "csv", OpcionesArchivo(delimitador=delimitador))


# --- JSON --------------------------------------------------------------


def test_json_es_una_lista_de_objetos_con_los_vacios_en_null() -> None:
    filas = json.loads(_texto("json"))

    assert list(filas[0]) == list(TABLA.cabeceras)  # orden de las cabeceras
    assert filas[0] == {
        "pagare": "000000000000000001",
        "numero": "51987654321",
        "deuda": 1500.5,
        "vence": "2026-09-18",
        "titular": "APELLIDO, NOMBRE",
    }
    assert filas[1]["deuda"] is None
    assert filas[1]["vence"] is None


def test_json_admite_sangria_y_deja_las_tildes_legibles() -> None:
    texto = _texto("json", OpcionesArchivo(sangria=2))

    assert "\n  {\n" in texto
    assert "SEÑOR AÑAÑOS" in texto


# --- XLSX --------------------------------------------------------------


def _libro(opciones: OpcionesArchivo | None = None):
    archivo = exportadores.exportar(TABLA, "xlsx", opciones or OpcionesArchivo())
    return openpyxl.load_workbook(io.BytesIO(archivo.contenido))


def test_xlsx_conserva_el_texto_como_texto_y_los_numeros_como_numeros() -> None:
    hoja = _libro().active
    filas = list(hoja.iter_rows(values_only=True))

    assert filas[0] == TABLA.cabeceras
    assert filas[1][0] == "000000000000000001"  # los ceros a la izquierda sobreviven
    assert filas[1][2] == 1500.5
    assert filas[1][3].date() == date(2026, 9, 18)  # fecha nativa de Excel
    assert filas[2][2] is None


def test_xlsx_usa_el_nombre_de_hoja_pedido() -> None:
    assert _libro(OpcionesArchivo(hoja="Campaña")).active.title == "Campaña"


@pytest.mark.parametrize(
    ("pedido", "esperado"),
    [
        ("Carga SMS", "Carga SMS"),
        ("2026/09/18: envio", "2026 09 18  envio"),
        ("", "Carga"),
        ("N" * 40, "N" * 31),  # Excel no admite mas de 31 caracteres
    ],
)
def test_nombre_de_hoja_se_ajusta_a_lo_que_excel_acepta(pedido, esperado) -> None:
    assert exportador_xlsx.nombre_de_hoja(pedido) == esperado


def test_xlsx_avisa_de_un_caracter_que_excel_no_admite() -> None:
    tabla = Tabla(nombre="x", cabeceras=("titular",), filas=({"titular": "NOMBRE\x00RARO"},))

    with pytest.raises(ExportacionInvalida, match="Excel"):
        exportadores.exportar(tabla, "xlsx")


# --- Registro y nombres ------------------------------------------------


def test_cada_formato_tiene_su_extension_y_su_tipo_de_contenido() -> None:
    for formato in FormatoArchivo:
        archivo = exportadores.exportar(TABLA, formato)
        assert archivo.nombre.endswith(f".{formato.value}")
        assert archivo.formato is formato
        assert archivo.tamano > 0


def test_un_formato_desconocido_dice_cuales_hay() -> None:
    with pytest.raises(FormatoNoSoportado, match="xlsx"):
        exportadores.exportar(TABLA, "pdf")


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("SMS preventiva", "SMS_preventiva.csv"),
        ("Campaña 18/09", "Campana_18_09.csv"),  # sin tildes ni separadores de ruta
        ("../../etc/passwd", "etc_passwd.csv"),
        ("   ", "carga.csv"),
        ("N" * 120, f"{'N' * 80}.csv"),
    ],
)
def test_nombre_de_archivo_es_seguro(nombre, esperado) -> None:
    assert comunes.nombre_de_archivo(nombre, FormatoArchivo.CSV) == esperado


def test_una_tabla_sin_filas_produce_un_archivo_con_solo_cabeceras() -> None:
    vacia = Tabla(nombre="vacia", cabeceras=("pagare",), filas=())

    assert _csv_de(vacia) == "pagare\r\n"
    assert json.loads(exportadores.exportar(vacia, "json").contenido) == []


def _csv_de(tabla: Tabla) -> str:
    return exportadores.exportar(tabla, "csv").contenido.decode("utf-8")
