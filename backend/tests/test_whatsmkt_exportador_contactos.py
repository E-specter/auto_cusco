"""El archivo de contactos de WhatsMKT en `.xlsx`, leido de vuelta (T-WM-B2; RF-WM-16, RF-73).

Se escribe con el exportador de verdad y se abre con openpyxl: lo que cuenta es lo que Excel
veria, no lo que el codigo cree haber escrito. Datos sinteticos.
"""

import io

import pytest
from openpyxl import load_workbook

from app.adapters.output.plataformas.whatsmkt.exportador_contactos import HOJA, exportar_contactos
from app.core.entities.exportacion import Tabla
from app.core.entities.mapeo import CampoSalida, DefinicionCarga
from app.core.services.plataformas.whatsmkt.archivo_contactos import ArchivoContactos
from tests.test_whatsmkt_contactos import armar, definicion, producto


def _leer(archivo: ArchivoContactos):
    resultado = exportar_contactos(archivo)
    return load_workbook(io.BytesIO(resultado.contenido)), resultado


def _archivo(productos, **kwargs) -> ArchivoContactos:
    [archivo] = armar(productos, **kwargs).archivos
    return archivo


def test_el_archivo_tiene_una_sola_hoja_con_los_encabezados_y_las_filas() -> None:
    archivo = _archivo([producto(1), producto(2)])

    libro, resultado = _leer(archivo)

    assert libro.sheetnames == [HOJA] == ["Hoja1"]
    hoja = libro[HOJA]
    assert [c.value for c in hoja[1]] == ["número", "[$MARCRO1$]", "[$MARCRO2$]"]
    assert hoja.max_row == 1 + archivo.cantidad
    assert resultado.nombre.endswith(".xlsx")


@pytest.mark.parametrize("celda_texto", [True, False])
def test_numero_va_en_celda_de_texto_con_formato_arroba_aunque_la_definicion_no_lo_pida(
    celda_texto: bool,
) -> None:
    # Una definicion guardada por la API podria venir con celda_texto=False (RF-73).
    archivo = _archivo([producto(1)], definicion_=definicion(celda_texto=celda_texto))

    libro, _ = _leer(archivo)

    for fila in libro[HOJA].iter_rows(min_row=2):
        celda = fila[0]
        assert celda.number_format == "@"
        assert celda.data_type == "s"
        assert isinstance(celda.value, str) and celda.value.startswith("51")
        assert len(celda.value) == 11


def test_los_supervisores_van_primero_y_las_macros_son_texto() -> None:
    archivo = _archivo([producto(1, titular="Ana Perez"), producto(2)])

    hoja = _leer(archivo)[0][HOJA]
    filas = [[c.value for c in fila] for fila in hoja.iter_rows(min_row=2)]

    assert [fila[0] for fila in filas] == [
        "51900000902",
        "51900000901",
        "51900000001",
        "51900000002",
    ]
    assert filas[0][1:] == filas[2][1:]  # los supervisores copian las macros de la primera fila
    for fila in hoja.iter_rows(min_row=2):
        assert all(c.data_type == "s" for c in fila[1:])  # macros: texto, no numero ni fecha


def test_un_valor_que_parece_numero_o_fecha_se_escribe_como_texto() -> None:
    archivo = _archivo([producto(1, titular="000123"), producto(2, titular="15/10/2026")])

    hoja = _leer(archivo)[0][HOJA]

    assert [hoja.cell(row=r, column=2).value for r in (4, 5)] == ["000123", "15/10/2026"]
    assert all(hoja.cell(row=r, column=2).data_type == "s" for r in (4, 5))


def test_un_texto_que_parece_formula_queda_como_texto_literal() -> None:
    # RF-53: el contenido no cambia (sin apostrofo) y no se evalua.
    archivo = _archivo([producto(1, titular="=1+1")], supervisores=())

    celda = _leer(archivo)[0][HOJA]["B2"]

    assert celda.value == "=1+1"
    assert celda.data_type == "s"


def test_una_macro_con_celda_de_texto_en_la_definicion_tambien_lleva_el_formato() -> None:
    con_texto = DefinicionCarga(
        nombre="x",
        campos=(
            CampoSalida(nombre="número", plantilla="51[@telefono]"),
            CampoSalida(nombre="[$MARCRO1$]", plantilla="[@pagare]", celda_texto=True),
            CampoSalida(nombre="[$MARCRO2$]", plantilla="[@titular]"),
        ),
    )

    hoja = _leer(_archivo([producto(1)], definicion_=con_texto, supervisores=()))[0][HOJA]

    assert hoja["A2"].number_format == "@"
    assert hoja["B2"].number_format == "@"
    assert hoja["C2"].number_format != "@"


def test_el_nombre_del_archivo_sale_de_la_tabla() -> None:
    archivo = ArchivoContactos(
        segmento=None,
        tabla=Tabla(
            nombre="CUZCO Vencida", cabeceras=("número",), filas=({"número": "51900000001"},)
        ),
        productos=1,
        supervisores=0,
        columnas_texto=frozenset({"número"}),
    )

    assert exportar_contactos(archivo).nombre == "CUZCO_Vencida.xlsx"
