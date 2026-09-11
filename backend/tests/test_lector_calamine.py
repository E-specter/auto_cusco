"""Pruebas del adaptador LectorCalamine con libros .xlsx sinteticos generados en memoria.

No hay sabanas reales en los tests: el formato .xlsb no se puede generar desde
Python, pero python-calamine usa la misma interfaz para .xlsb y .xlsx, y el
lector se valido localmente contra las sabanas reales.
"""

import io
from datetime import date, datetime

import openpyxl
import pytest

from app.adapters.input.lector_calamine import LectorCalamine
from app.core.entities.sabana import ArchivoIlegible, HojaNoEncontrada, HojaVacia, TipoDocumento
from app.core.services.ingesta_sabana.cabeceras import mapear_cabeceras
from app.core.services.ingesta_sabana.normalizador import normalizar_fila
from tests.test_sabana_cabeceras import CABECERAS_10_09
from tests.test_sabana_normalizador import _fila_sintetica


def _libro(hojas: dict[str, list[list]]) -> bytes:
    libro = openpyxl.Workbook()
    libro.remove(libro.active)
    for nombre, filas in hojas.items():
        hoja = libro.create_sheet(nombre)
        for fila in filas:
            hoja.append(fila)
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def test_lee_cabecera_y_filas_con_numeros_de_fila_de_excel() -> None:
    contenido = _libro(
        {
            "Td": [["resumen"]],
            "VENCIDA": [
                [],
                ["Pagare", "Monto", "Fecha"],
                ["001", 10.5, date(2026, 9, 10)],
                [],
                ["002", 3, None],
            ],
        }
    )

    hoja = LectorCalamine().leer_hoja(contenido)

    assert hoja.nombre == "VENCIDA"
    assert hoja.fila_cabecera == 2
    assert hoja.cabeceras == ["Pagare", "Monto", "Fecha"]
    assert [f.numero_fila for f in hoja.filas] == [3, 5]
    pagare, monto, fecha = hoja.filas[0].celdas
    assert (pagare, monto) == ("001", 10.5)
    assert fecha in (date(2026, 9, 10), datetime(2026, 9, 10))
    assert hoja.filas[1].celdas == ["002", 3]  # celdas vacias finales recortadas


def test_hoja_configurable() -> None:
    contenido = _libro({"OTRA": [["Pagare"], ["001"]]})

    assert LectorCalamine().leer_hoja(contenido, hoja="OTRA").filas[0].celdas == ["001"]


def test_hoja_inexistente_informa_las_disponibles() -> None:
    contenido = _libro({"Td": [["x"]], "PREVENTIVA": [["Pagare"]]})

    with pytest.raises(HojaNoEncontrada) as error:
        LectorCalamine().leer_hoja(contenido)

    assert error.value.disponibles == ["Td", "PREVENTIVA"]


def test_hoja_vacia() -> None:
    with pytest.raises(HojaVacia):
        LectorCalamine().leer_hoja(_libro({"VENCIDA": []}))


@pytest.mark.parametrize("contenido", [b"", b"no es excel", b"Pagare,Monto\n001,10\n"])
def test_archivo_ilegible(contenido) -> None:
    with pytest.raises(ArchivoIlegible):
        LectorCalamine().leer_hoja(contenido)


def test_extremo_a_extremo_lector_mapeo_y_normalizador() -> None:
    fila = _fila_sintetica(**{"Vencimiento Cuota": date(2026, 9, 13)})
    contenido = _libro({"VENCIDA": [CABECERAS_10_09, fila]})

    hoja = LectorCalamine().leer_hoja(contenido)
    mapeo = mapear_cabeceras(hoja.cabeceras)
    normalizada = normalizar_fila(hoja.filas[0].celdas, mapeo, hoja.filas[0].numero_fila)

    assert not mapeo.bloqueante and mapeo.incidencias == []
    assert normalizada.numero_fila == 2
    assert normalizada.clave == "000000000000000001"
    assert normalizada.valores["documento_tipo"] is TipoDocumento.DNI
    assert normalizada.valores["documento_numero"] == "01234567"
    assert normalizada.valores["fecha_vencimiento_cuota"] == date(2026, 9, 13)
    assert normalizada.valores["vencimiento_operativo_fecha"] == date(2026, 9, 17)
