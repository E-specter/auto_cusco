"""La celda de texto en XLSX (T-HI-B3, RF-73).

`OpcionesArchivo.columnas_texto` (las cabeceras) escribe esas columnas con el formato de celda
«Texto» (`@`) y como texto explicito; un valor que no es texto pasa por `str` y `None` queda como
celda vacia. Sin la opcion, el archivo sale EXACTAMENTE como antes; CSV y JSON ignoran la opcion.

En la definicion, `CampoSalida.celda_texto` (falso por defecto) se serializa SOLO si es verdadero,
para que el JSON canonico de lo ya guardado no cambie, y las columnas marcadas llegan al exportador.
Datos sinteticos (telefonos 900000xxx).
"""

import io
from datetime import date
from decimal import Decimal

import openpyxl
import pytest

from app.adapters.output import exportadores
from app.adapters.output.exportadores import exportador_xlsx
from app.core.entities.exportacion import FormatoArchivo, OpcionesArchivo, Tabla
from app.core.entities.mapeo import CampoSalida, DefinicionCarga
from app.core.entities.segmentacion import TABLA_RANGOS_POR_DEFECTO
from app.core.services.mapeo_campos.serializacion import (
    DefinicionIlegible,
    definicion_a_dict,
    definicion_desde_dict,
)
from tests.exportacion_seguridad_datos import huella_xlsx

CABECERAS = ("telefono", "pagare", "monto", "vence", "nota", "formula", "vacio")
FILA = {
    "telefono": 51900000001,  # un numero de 11 digitos: lo que Excel pasaria a notacion cientifica
    "pagare": "000000000000000001",
    "monto": Decimal("1500.50"),
    "vence": date(2026, 9, 10),
    "nota": "texto normal",
    "formula": "=1+1",
    "vacio": None,
}
TABLA = Tabla(
    nombre="sintetica", cabeceras=CABECERAS, filas=(FILA, {**FILA, "telefono": 51900000002})
)

# SHA-256 del .xlsx de TABLA con las opciones por defecto, calculado con el exportador de HEAD
# 98be952 (antes de RF-73), sin las marcas de tiempo (`huella_xlsx`). Si cambia, el archivo de
# siempre cambio.
HUELLA_ANTES = "b02875c37d06d6b8323e3c6a042f4b731ec190a666cfc9166dc531a0f3f72c37"


def _xlsx(opciones: OpcionesArchivo | None = None, tabla: Tabla = TABLA) -> bytes:
    return exportador_xlsx.exportar(tabla, opciones or OpcionesArchivo()).contenido


def _celdas(contenido: bytes):
    hoja = openpyxl.load_workbook(io.BytesIO(contenido)).active
    return {
        cabecera: [hoja.cell(fila, c + 1) for fila in (1, 2, 3)]
        for c, cabecera in enumerate(CABECERAS)
    }


# --- Sin la opcion, el archivo es el de siempre ----------------------------------------


def test_sin_la_opcion_el_xlsx_tiene_los_mismos_bytes_que_antes() -> None:
    assert huella_xlsx(_xlsx()) == HUELLA_ANTES


def test_una_lista_vacia_o_con_cabeceras_que_no_existen_no_cambia_nada() -> None:
    base = huella_xlsx(_xlsx())

    assert huella_xlsx(_xlsx(OpcionesArchivo(columnas_texto=frozenset()))) == base
    assert huella_xlsx(_xlsx(OpcionesArchivo(columnas_texto=frozenset({"no_existe"})))) == base


def test_la_opcion_esta_vacia_por_defecto() -> None:
    assert OpcionesArchivo().columnas_texto == frozenset()


# --- Con la opcion ----------------------------------------


def test_una_columna_de_texto_se_lee_de_vuelta_como_texto_con_formato_arroba() -> None:
    contenido = _xlsx(OpcionesArchivo(columnas_texto=frozenset({"telefono"})))

    celdas = _celdas(contenido)["telefono"]

    for celda, esperado in zip(celdas[1:], ("51900000001", "51900000002"), strict=True):
        assert celda.number_format == "@"
        assert celda.data_type == "s"
        assert celda.value == esperado  # los 11 digitos intactos, como texto
        assert isinstance(celda.value, str)


def test_un_valor_que_no_es_texto_pasa_por_str_y_none_queda_vacio() -> None:
    columnas = frozenset({"monto", "vence", "vacio", "formula", "pagare"})

    celdas = _celdas(_xlsx(OpcionesArchivo(columnas_texto=columnas)))

    assert celdas["monto"][1].value == "1500.50" and celdas["monto"][1].number_format == "@"
    assert celdas["vence"][1].value == "2026-09-10" and celdas["vence"][1].number_format == "@"
    assert celdas["pagare"][1].value == "000000000000000001"
    assert celdas["vacio"][1].value is None  # no es el texto «None»
    assert celdas["formula"][1].value == "=1+1" and celdas["formula"][1].data_type == "s"


def test_el_formato_de_texto_no_cambia_el_contenido_de_un_texto_que_parece_formula() -> None:
    """Compatible con RF-53: sigue siendo texto literal, sin apostrofo ni `quotePrefix`."""
    celda = _celdas(_xlsx(OpcionesArchivo(columnas_texto=frozenset({"formula"}))))["formula"][1]

    assert (celda.value, celda.data_type, celda.number_format) == ("=1+1", "s", "@")
    assert not celda.quotePrefix


def test_las_demas_columnas_quedan_exactamente_como_sin_la_opcion() -> None:
    sin = _celdas(_xlsx())
    con = _celdas(_xlsx(OpcionesArchivo(columnas_texto=frozenset({"telefono"}))))

    for cabecera in CABECERAS:
        if cabecera == "telefono":
            continue
        for antes, despues in zip(sin[cabecera], con[cabecera], strict=True):
            assert (antes.value, antes.data_type, antes.number_format) == (
                despues.value,
                despues.data_type,
                despues.number_format,
            ), cabecera


def test_la_cabecera_de_la_columna_no_lleva_el_formato_de_texto() -> None:
    celda = _celdas(_xlsx(OpcionesArchivo(columnas_texto=frozenset({"telefono"}))))["telefono"][0]

    assert celda.value == "telefono" and celda.number_format == "General"


def test_sin_cabeceras_las_filas_de_datos_llevan_igual_el_formato() -> None:
    contenido = _xlsx(OpcionesArchivo(con_cabeceras=False, columnas_texto=frozenset({"telefono"})))

    hoja = openpyxl.load_workbook(io.BytesIO(contenido)).active

    assert hoja.cell(1, 1).value == "51900000001" and hoja.cell(1, 1).number_format == "@"


def test_el_nombre_de_una_cabecera_repetida_marca_todas_sus_columnas() -> None:
    tabla = Tabla("rep", ("a", "a"), ({"a": 51900000001},))

    contenido = _xlsx(OpcionesArchivo(columnas_texto=frozenset({"a"})), tabla)

    hoja = openpyxl.load_workbook(io.BytesIO(contenido)).active
    assert hoja.cell(2, 1).number_format == "@" and hoja.cell(2, 2).number_format == "@"


def test_el_xlsx_con_la_opcion_se_abre_y_tiene_la_misma_forma() -> None:
    contenido = _xlsx(OpcionesArchivo(columnas_texto=frozenset({"telefono", "pagare"})))

    hoja = openpyxl.load_workbook(io.BytesIO(contenido)).active

    assert (hoja.max_row, hoja.max_column) == (3, len(CABECERAS))


# --- CSV y JSON la ignoran ----------------------------------------


@pytest.mark.parametrize("formato", [FormatoArchivo.CSV, FormatoArchivo.JSON])
def test_csv_y_json_no_cambian_con_la_opcion(formato) -> None:
    sin = exportadores.exportar(TABLA, formato, OpcionesArchivo())
    con = exportadores.exportar(
        TABLA, formato, OpcionesArchivo(columnas_texto=frozenset({"telefono", "monto"}))
    )

    assert con.contenido == sin.contenido


# --- La definicion ----------------------------------------

VACIA = {"nodos": []}


def _definicion(**extra_columna) -> dict:
    return {
        "proteger_formulas": True,
        "columnas": [
            {"nombre": "numero", "orden": 0, "expresion": VACIA, **extra_columna},
            {"nombre": "mensaje", "orden": 1, "expresion": VACIA},
        ],
        "segmentacion": None,
    }


def _leer(dato):
    return definicion_desde_dict(dato, TABLA_RANGOS_POR_DEFECTO, "dias_atraso")


def test_una_version_guardada_sin_la_clave_da_el_mismo_dict_de_ida_y_vuelta() -> None:
    guardado = definicion_a_dict(_leer(_definicion()), con_nombre=False)

    ida_y_vuelta = definicion_a_dict(_leer(guardado), con_nombre=False)

    assert ida_y_vuelta == guardado
    assert all("celda_texto" not in columna for columna in guardado["columnas"])  # no se agrega
    assert all(not c.celda_texto for c in _leer(guardado).definicion.campos)


def test_con_celda_texto_verdadero_la_ida_y_vuelta_la_conserva() -> None:
    leida = _leer(_definicion(celda_texto=True))

    guardado = definicion_a_dict(leida, con_nombre=False)

    assert [c.celda_texto for c in leida.definicion.campos] == [True, False]
    assert guardado["columnas"][0]["celda_texto"] is True
    assert "celda_texto" not in guardado["columnas"][1]  # solo la que lo tiene
    assert definicion_a_dict(_leer(guardado), con_nombre=False) == guardado


def test_celda_texto_falso_o_nulo_se_lee_pero_no_se_guarda() -> None:
    for valor in (False, None):
        leida = _leer(_definicion(celda_texto=valor))

        assert not leida.definicion.campos[0].celda_texto
        assert "celda_texto" not in definicion_a_dict(leida, con_nombre=False)["columnas"][0]


@pytest.mark.parametrize("valor", ["si", 1, 0, [True], {"a": 1}])
def test_celda_texto_que_no_es_booleano_es_un_problema_de_la_columna(valor) -> None:
    with pytest.raises(DefinicionIlegible) as error:
        _leer(_definicion(celda_texto=valor))

    [problema] = error.value.problemas
    assert (problema.columna, problema.campo) == (0, "celda_texto")


def test_las_columnas_marcadas_son_las_cabeceras_que_llegan_al_exportador() -> None:
    definicion = DefinicionCarga(
        nombre="d",
        campos=(
            CampoSalida("numero", "51[@telefono]", celda_texto=True),
            CampoSalida("pagare", "[@pagare]"),
            CampoSalida("otro", "x", celda_texto=True),
        ),
    )

    assert definicion.columnas_texto == frozenset({"numero", "otro"})
    assert DefinicionCarga("d", (CampoSalida("a", "x"),)).columnas_texto == frozenset()


def test_una_definicion_guardada_marcada_escribe_su_columna_como_texto_en_el_archivo() -> None:
    leida = _leer(_definicion(celda_texto=True))
    columnas = leida.definicion.columnas_texto
    tabla = Tabla("t", ("numero", "mensaje"), ({"numero": 51900000001, "mensaje": 5},))

    contenido = _xlsx(OpcionesArchivo(columnas_texto=columnas), tabla)

    hoja = openpyxl.load_workbook(io.BytesIO(contenido)).active
    assert (hoja.cell(2, 1).value, hoja.cell(2, 1).number_format) == ("51900000001", "@")
    assert hoja.cell(2, 2).number_format == "General" and hoja.cell(2, 2).value == 5
