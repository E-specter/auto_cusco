"""Pruebas del lector del reporte de enviados de MES (RF-MM-20), con archivos en memoria."""

import io

import openpyxl
import pytest

from app.adapters.input.lector_reporte_mowa_mes import LectorReporteMowaMes
from app.core.entities.mowa_mes_reporte import COLUMNAS_REPORTE, FilaReporte, ReporteInvalido

FILA = [
    70001,
    "900000101",
    "ZZPRUEBA te informa",
    "14/09/26",
    "01234567",
    "enviado",
    "Nro. LARGO",
    "usuario_sintetico",
]


def _xlsx(cabeceras=COLUMNAS_REPORTE, *filas, hoja="Hoja1") -> bytes:
    libro = openpyxl.Workbook()
    libro.active.title = hoja
    libro.active.append(list(cabeceras))
    for fila in filas:
        libro.active.append(list(fila))
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def test_lee_las_filas_del_reporte() -> None:
    (fila,) = LectorReporteMowaMes().leer(_xlsx(COLUMNAS_REPORTE, FILA))

    assert fila == FilaReporte(
        fila=2,
        mes_id=70001,
        celular="900000101",
        mensaje="ZZPRUEBA te informa",
        fecha_envio="14/09/26",
        dni="01234567",
        estado="enviado",
        salida="Nro. LARGO",
        usuario="usuario_sintetico",
    )


def test_cabeceras_con_mayusculas_tildes_espacios_y_otro_orden() -> None:
    cabeceras = [
        " USUARIO",
        "Id",
        "Celular",
        "Mensaje",
        "Fecha de Envío",
        "DNI",
        "Estado",
        "Salida ",
    ]
    valores = [FILA[7], *FILA[:7]]

    (fila,) = LectorReporteMowaMes().leer(_xlsx(cabeceras, valores))

    assert (fila.mes_id, fila.fecha_envio, fila.usuario) == (70001, "14/09/26", "usuario_sintetico")


def test_celular_y_dni_guardados_como_numero_vuelven_a_texto() -> None:
    valores = [70001.0, 900000101, "ZZPRUEBA", "14/09/26", 1234567, "enviado", "Nro. LARGO", "u"]

    (fila,) = LectorReporteMowaMes().leer(_xlsx(COLUMNAS_REPORTE, valores))

    assert (fila.mes_id, fila.celular, fila.dni) == (70001, "900000101", "01234567")


def test_las_filas_vacias_se_saltan_y_se_respeta_el_numero_de_fila() -> None:
    vacia = [None] * 8

    filas = LectorReporteMowaMes().leer(_xlsx(COLUMNAS_REPORTE, FILA, vacia, FILA))

    assert [f.fila for f in filas] == [2, 4]


def test_falta_una_columna() -> None:
    with pytest.raises(ReporteInvalido, match="usuario"):
        LectorReporteMowaMes().leer(_xlsx(COLUMNAS_REPORTE[:-1], FILA[:-1]))


def test_sin_filas() -> None:
    with pytest.raises(ReporteInvalido, match="no tiene filas"):
        LectorReporteMowaMes().leer(_xlsx(COLUMNAS_REPORTE))


def test_un_id_que_no_es_numero() -> None:
    with pytest.raises(ReporteInvalido, match="fila 2"):
        LectorReporteMowaMes().leer(_xlsx(COLUMNAS_REPORTE, ["abc", *FILA[1:]]))


def test_un_archivo_que_no_es_hoja_de_calculo() -> None:
    with pytest.raises(ReporteInvalido, match="legible"):
        LectorReporteMowaMes().leer(b"esto no es un xlsx")
