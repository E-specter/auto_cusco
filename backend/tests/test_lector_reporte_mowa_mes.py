"""Pruebas del lector del reporte de enviados de MES (RF-MM-20), con archivos en memoria."""

import csv
import io
import json
import re
import zipfile

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


@pytest.mark.parametrize("posicion", range(len(COLUMNAS_REPORTE)))
def test_cada_columna_se_encuentra_con_mayusculas_tildes_y_espacios_dobles(posicion) -> None:
    cabeceras = list(COLUMNAS_REPORTE)
    columna = cabeceras[posicion].upper().replace("ENVIO", "ENVÍO")
    cabeceras[posicion] = "  " + columna.replace(" ", "   ") + "  "

    (fila,) = LectorReporteMowaMes().leer(_xlsx(cabeceras, FILA))

    assert fila == LectorReporteMowaMes().leer(_xlsx(COLUMNAS_REPORTE, FILA))[0]


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
    with pytest.raises(ReporteInvalido, match="no coincide con el contenido"):
        LectorReporteMowaMes().leer(b"esto no es un xlsx")


# --- Sobre el lector general (T-MM-C10, L-B7): lo de siempre, con los textos de siempre ---------


def _libro(*hojas: tuple[str, list[list]]) -> bytes:
    libro = openpyxl.Workbook()
    libro.remove(libro.active)
    for nombre, filas in hojas:
        hoja = libro.create_sheet(nombre)
        for fila in filas:
            hoja.append(fila)
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def _reescrito(contenido: bytes, cambiar) -> bytes:
    origen = zipfile.ZipFile(io.BytesIO(contenido))
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w") as destino:
        for nombre in origen.namelist():
            destino.writestr(nombre, cambiar(nombre, origen.read(nombre)))
    return salida.getvalue()


def _sin_hojas(nombre: str, datos: bytes) -> bytes:
    if nombre != "xl/workbook.xml":
        return datos
    return re.sub(rb"<sheets>.*</sheets>", b"<sheets></sheets>", datos, flags=re.S)


def test_toma_la_primera_hoja_aunque_haya_otra_llamada_vencida() -> None:
    contenido = _libro(
        ("Hoja1", [list(COLUMNAS_REPORTE), FILA]), ("VENCIDA", [["otra", "cosa"], [1, 2]])
    )

    (fila,) = LectorReporteMowaMes().leer(contenido, "reporte.xlsx")

    assert fila.mes_id == 70001


def test_la_primera_hoja_vacia_no_se_salta_a_otra() -> None:
    contenido = _libro(("Vacia", []), ("Hoja1", [list(COLUMNAS_REPORTE), FILA]))

    with pytest.raises(ReporteInvalido, match="no tiene cabecera ni filas"):
        LectorReporteMowaMes().leer(contenido, "reporte.xlsx")


def test_un_archivo_vacio_dice_que_no_coincide_con_su_extension() -> None:
    with pytest.raises(ReporteInvalido, match="no coincide con el contenido"):
        LectorReporteMowaMes().leer(b"", "reporte.xlsx")


def test_una_hoja_que_no_se_puede_leer_conserva_su_texto() -> None:
    contenido = _reescrito(
        _xlsx(COLUMNAS_REPORTE, FILA),
        lambda nombre, datos: b"<roto" if nombre == "xl/worksheets/sheet1.xml" else datos,
    )

    with pytest.raises(ReporteInvalido, match="^No se pudo leer la primera hoja del archivo$"):
        LectorReporteMowaMes().leer(contenido, "reporte.xlsx")


def test_un_libro_sin_hojas_conserva_su_texto() -> None:
    contenido = _reescrito(
        _xlsx(COLUMNAS_REPORTE, FILA),
        _sin_hojas,
    )

    with pytest.raises(ReporteInvalido, match="^El archivo no tiene hojas$"):
        LectorReporteMowaMes().leer(contenido, "reporte.xlsx")


def test_el_nombre_es_opcional_y_da_lo_mismo_que_reporte_xlsx() -> None:
    contenido = _xlsx(COLUMNAS_REPORTE, FILA)

    assert LectorReporteMowaMes().leer(contenido) == LectorReporteMowaMes().leer(
        contenido, "reporte.xlsx"
    )


def test_un_xlsx_con_otra_extension_se_rechaza() -> None:
    # El nombre se mira desde L-B7: antes de el, la extension no se comprobaba.
    with pytest.raises(ReporteInvalido, match="no coincide con el contenido"):
        LectorReporteMowaMes().leer(_xlsx(COLUMNAS_REPORTE, FILA), "reporte.csv")


# --- Los formatos de la sabana (T-MM-C10, L-B8, E2-A) ----------------------------------------

FILAS = [
    FILA,
    [
        70002,
        "900000102",
        "Canción, señor; ok",  # lleva la tilde, la ñ, una coma y un punto y coma
        "15/09/26",
        "20123456789",
        "Enviado",
        "Nro. LARGO",
        "usuario_sintetico",
    ],
]


def _csv(separador: str, codificacion: str) -> bytes:
    salida = io.StringIO(newline="")
    escritor = csv.writer(salida, delimiter=separador, lineterminator=chr(10))
    escritor.writerow(COLUMNAS_REPORTE)
    escritor.writerows(FILAS)
    return salida.getvalue().encode(codificacion)


def test_el_reporte_de_ejemplo_trae_los_ceros_del_dni_y_una_tilde() -> None:
    esperadas = LectorReporteMowaMes().leer(_xlsx(COLUMNAS_REPORTE, *FILAS), "reporte.xlsx")

    assert [f.dni for f in esperadas] == ["01234567", "20123456789"]
    assert esperadas[1].mensaje == "Canción, señor; ok"


@pytest.mark.parametrize(
    ("separador", "codificacion", "nombre"),
    [
        (";", "utf-8", "reporte.csv"),
        (",", "utf-8", "reporte.csv"),
        (";", "utf-8-sig", "reporte.csv"),
        (",", "utf-8-sig", "reporte.csv"),
        (";", "latin-1", "reporte.csv"),
        (",", "latin-1", "reporte.csv"),
        (chr(9), "utf-8", "reporte.tsv"),
        (";", "utf-8", "reporte.txt"),
    ],
)
def test_el_mismo_reporte_en_csv_da_las_mismas_filas_que_en_xlsx(
    separador, codificacion, nombre
) -> None:
    esperadas = LectorReporteMowaMes().leer(_xlsx(COLUMNAS_REPORTE, *FILAS), "reporte.xlsx")

    leidas = LectorReporteMowaMes().leer(_csv(separador, codificacion), nombre)

    assert leidas == esperadas


def test_el_mismo_reporte_en_json_da_las_mismas_filas_que_en_xlsx() -> None:
    esperadas = LectorReporteMowaMes().leer(_xlsx(COLUMNAS_REPORTE, *FILAS), "reporte.xlsx")
    objetos = [dict(zip(COLUMNAS_REPORTE, fila, strict=True)) for fila in FILAS]

    leidas = LectorReporteMowaMes().leer(json.dumps(objetos).encode("utf-8"), "reporte.json")

    assert leidas == esperadas


def test_un_dni_de_csv_conserva_sus_ceros() -> None:
    (fila, _) = LectorReporteMowaMes().leer(_csv(";", "utf-8"), "reporte.csv")

    assert fila.dni == "01234567"


def test_un_csv_sin_una_columna_dice_cual_falta() -> None:
    texto = chr(10).join([";".join(COLUMNAS_REPORTE[:-1]), ";".join(map(str, FILA[:-1]))])

    with pytest.raises(ReporteInvalido, match="Faltan columnas del reporte de enviados: usuario"):
        LectorReporteMowaMes().leer(texto.encode("utf-8"), "reporte.csv")


def test_un_csv_con_un_id_que_no_es_numero_dice_la_fila() -> None:
    texto = chr(10).join([";".join(COLUMNAS_REPORTE), ";".join(["abc", *map(str, FILA[1:])])])

    with pytest.raises(ReporteInvalido, match="fila 2"):
        LectorReporteMowaMes().leer(texto.encode("utf-8"), "reporte.csv")


def test_un_csv_vacio_no_tiene_cabecera_ni_filas() -> None:
    with pytest.raises(ReporteInvalido, match="no tiene cabecera ni filas"):
        LectorReporteMowaMes().leer(b"", "reporte.csv")
