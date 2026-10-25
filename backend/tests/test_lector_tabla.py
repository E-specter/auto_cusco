"""Los lectores de archivos tabulares (T-MAP-B2, RF-57): formato, Excel/ODS, CSV y JSON.

Todos los archivos se generan en la prueba y son sinteticos: encabezados y valores inventados.
"""

import csv
import io
import json
import random
import zipfile
from datetime import date

import openpyxl
import pytest

from app.adapters.input import lector_csv
from app.adapters.input.lector_calamine import LectorCalamine
from app.adapters.input.lector_csv import leer_csv
from app.adapters.input.lector_json import leer_json
from app.adapters.input.lector_tabla import LectorTabla
from app.core.entities.lectura_tabla import (
    AdvertenciaLectura,
    CodigoAdvertenciaLectura,
    FormatoTabla,
    OpcionesLectura,
)
from app.core.entities.sabana import (
    ArchivoIlegible,
    ArchivoVacio,
    CodificacionInvalida,
    CodificacionNoCoincide,
    ExtensionNoCoincide,
    FilaCruda,
    HojaNoEncontrada,
    HojaVacia,
    SeparadorInvalido,
)
from app.core.services.lectura_tabla import detectar_formato, formato_de_hoja_de_calculo

F = FormatoTabla
LECTOR = LectorTabla()
SEMILLA = 20261025


def leer(contenido: bytes, nombre: str = "", **opciones):
    return LECTOR.leer(contenido, nombre, OpcionesLectura(**opciones))


# --- Archivos de prueba ---------------------------------------------------------------------------


def libro(hojas: dict[str, list[list]]) -> bytes:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for nombre, filas in hojas.items():
        hoja = wb.create_sheet(nombre)
        for fila in filas:
            hoja.append(fila)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


_NS = (
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"'
)


def ods(hojas: dict[str, list[list[str]]]) -> bytes:
    """Un .ods minimo con celdas de texto."""
    cuerpo = ""
    celda = '<table:table-cell office:value-type="string"><text:p>{}</text:p></table:table-cell>'
    for nombre, filas in hojas.items():
        cuerpo += f'<table:table table:name="{nombre}">'
        for fila in filas:
            celdas = "".join(celda.format(c) for c in fila)
            cuerpo += f"<table:table-row>{celdas}</table:table-row>"
        cuerpo += "</table:table>"
    contenido = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<office:document-content {_NS} office:version="1.2">'
        f"<office:body><office:spreadsheet>{cuerpo}</office:spreadsheet></office:body>"
        "</office:document-content>"
    )
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
        z.writestr("content.xml", contenido)
        z.writestr(
            "META-INF/manifest.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<manifest:manifest "
            'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
            'manifest:version="1.2"><manifest:file-entry manifest:full-path="/" '
            'manifest:media-type="application/vnd.oasis.opendocument.spreadsheet"/>'
            '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
            "</manifest:manifest>",
        )
    return salida.getvalue()


def zip_con(*nombres: str) -> bytes:
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w") as z:
        for nombre in nombres:
            z.writestr(nombre, "x")
    return salida.getvalue()


OLE = bytes.fromhex("d0cf11e0a1b11ae1") + b"\x00" * 64


# --- Formato: por extension y por contenido -------------------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("datos.csv", F.CSV),
        ("DATOS.CSV", F.CSV),
        ("datos.tsv", F.CSV),
        ("datos.txt", F.CSV),
        ("datos.json", F.JSON),
        ("Datos Finales.JSON", F.JSON),
    ],
)
def test_el_formato_de_un_texto_sale_de_la_extension(nombre, esperado) -> None:
    contenido = b'[{"a": 1}]' if esperado is F.JSON else b"a,b\n1,2\n"

    assert detectar_formato(contenido, nombre) is esperado


def test_el_formato_de_una_hoja_de_calculo_sale_de_su_contenido() -> None:
    assert detectar_formato(libro({"H": [["a"]]}), "x.xlsx") is F.XLSX
    assert detectar_formato(ods({"H": [["a"]]}), "x.ods") is F.ODS
    assert detectar_formato(zip_con("xl/workbook.bin"), "x.xlsb") is F.XLSB
    assert detectar_formato(OLE, "x.xls") is F.XLS


@pytest.mark.parametrize("nombre", ["", "sin_extension", "raro.dat", "archivo.", None])
def test_sin_extension_conocida_el_formato_sale_del_contenido(nombre) -> None:
    assert detectar_formato(libro({"H": [["a"]]}), nombre) is F.XLSX
    assert detectar_formato(ods({"H": [["a"]]}), nombre) is F.ODS
    assert detectar_formato(zip_con("xl/workbook.bin"), nombre) is F.XLSB
    assert detectar_formato(OLE, nombre) is F.XLS
    assert detectar_formato(b'[{"a": 1}]', nombre) is F.JSON
    assert detectar_formato(b'{"a": 1}', nombre) is F.JSON
    assert detectar_formato(b"a,b\n1,2\n", nombre) is F.CSV


def test_un_json_con_bom_y_espacios_al_principio_se_reconoce() -> None:
    assert detectar_formato(b"\xef\xbb\xbf  \n\t[1]", "") is F.JSON


@pytest.mark.parametrize(
    ("nombre", "contenido"),
    [
        ("datos.xlsx", b"a,b\n1,2\n"),
        ("datos.ods", b'[{"a": 1}]'),
        ("datos.xlsb", b""),
        ("datos.csv", None),  # una hoja de calculo
        ("datos.json", None),
        ("datos.json", b"a,b\n1,2\n"),
    ],
)
def test_una_extension_que_no_coincide_con_el_contenido_es_ilegible_con_el_motivo(
    nombre, contenido
) -> None:
    contenido = libro({"H": [["a"]]}) if contenido is None else contenido

    with pytest.raises(ExtensionNoCoincide) as error:
        detectar_formato(contenido, nombre)

    assert "no coincide con el contenido" in str(error.value)
    assert nombre.rsplit(".", 1)[1] in str(error.value)


def test_un_archivo_vacio_sin_extension_es_ilegible_y_con_extension_csv_no_tiene_datos() -> None:
    with pytest.raises(ArchivoVacio, match="vacío"):
        detectar_formato(b"  \n ", "")
    with pytest.raises(HojaVacia):
        leer(b"", "datos.csv")


def test_una_extension_csv_manda_aunque_el_texto_parezca_json() -> None:
    assert leer(b"[a],[b]\n1,2\n", "datos.csv").cabeceras == ["[a]", "[b]"]


def test_el_formato_de_hoja_de_calculo_es_none_para_un_texto() -> None:
    assert formato_de_hoja_de_calculo(b"a,b") is None
    assert formato_de_hoja_de_calculo(b"") is None


def test_un_zip_corrupto_o_ajeno_se_toma_por_xlsx_y_lo_decide_quien_lo_lee() -> None:
    assert formato_de_hoja_de_calculo(b"PK\x03\x04basura") is F.XLSX
    with pytest.raises(ArchivoIlegible):
        leer(b"PK\x03\x04basura", "x.xlsx")
    with pytest.raises(ArchivoIlegible):
        leer(zip_con("word/document.xml"), "x.xlsx")


def test_un_documento_ole_que_no_es_excel_es_ilegible() -> None:
    with pytest.raises(ArchivoIlegible):
        leer(OLE, "x.xls")


# --- Excel y ODS ----------------------------------------------------------------------------------


def test_una_hoja_de_calculo_lista_sus_hojas_y_lee_vencida_por_defecto() -> None:
    contenido = libro(
        {"Resumen": [["x"]], "VENCIDA": [["Pagare", "Monto"], ["001", 10.5]], "Otra": [["y"]]}
    )

    tabla = leer(contenido, "sabana.xlsx")

    assert tabla.formato is F.XLSX
    assert tabla.hojas == ("Resumen", "VENCIDA", "Otra")
    assert tabla.hoja == "VENCIDA"
    assert (tabla.separador, tabla.codificacion, tabla.advertencias) == (None, None, ())
    assert tabla.cabeceras == ["Pagare", "Monto"]
    assert tabla.filas == [FilaCruda(2, ["001", 10.5])]


def test_sin_vencida_se_lee_la_primera_hoja() -> None:
    contenido = libro({"Julio": [["a", "b"], [1, 2]], "Agosto": [["c"], [3]]})

    tabla = leer(contenido, "datos.xlsx")

    assert (tabla.hoja, tabla.hojas) == ("Julio", ("Julio", "Agosto"))
    assert tabla.cabeceras == ["a", "b"]


def test_la_hoja_elegida_gana_a_la_de_por_defecto() -> None:
    contenido = libro({"VENCIDA": [["a"]], "Otra": [["b"], ["x"]]})

    tabla = leer(contenido, "datos.xlsx", hoja="Otra")

    assert (tabla.hoja, tabla.cabeceras, tabla.filas) == ("Otra", ["b"], [FilaCruda(2, ["x"])])


def test_una_hoja_pedida_que_no_existe_es_hoja_no_encontrada_con_las_disponibles() -> None:
    contenido = libro({"Julio": [["a"]], "Agosto": [["b"]]})

    with pytest.raises(HojaNoEncontrada) as error:
        leer(contenido, "datos.xlsx", hoja="Septiembre")

    assert error.value.disponibles == ["Julio", "Agosto"]


def test_una_hoja_sin_cabecera_ni_datos_es_hoja_vacia() -> None:
    with pytest.raises(HojaVacia):
        leer(libro({"VENCIDA": []}), "datos.xlsx")


def test_los_numeros_de_fila_de_excel_son_los_de_la_hoja() -> None:
    contenido = libro({"H": [[], ["a", "b"], ["1", 2], [], [None, 5, None]]})

    tabla = leer(contenido, "datos.xlsx")

    assert tabla.fila_cabecera == 2
    assert [f.numero_fila for f in tabla.filas] == [3, 5]
    assert tabla.filas[1].celdas == ["", 5]


def test_un_ods_se_lista_y_se_lee_como_una_hoja_de_calculo() -> None:
    contenido = ods({"Resumen": [["x"]], "Datos": [["Pagare", "Zona"], ["001", "Norte"]]})

    tabla = leer(contenido, "sabana.ods")

    assert tabla.formato is F.ODS
    assert (tabla.hojas, tabla.hoja) == (("Resumen", "Datos"), "Resumen")
    assert leer(contenido, "sabana.ods", hoja="Datos").filas == [FilaCruda(2, ["001", "Norte"])]


def test_la_extension_equivocada_entre_hojas_de_calculo_se_corrige_por_el_contenido() -> None:
    assert leer(ods({"H": [["a"], ["1"]]}), "datos.xlsx").formato is F.ODS


# --- Paridad de leer_hoja con lo de antes ---------------------------------------------------------


def _hoja_de_antes(contenido: bytes, hoja: str):
    """`LectorCalamine.leer_hoja` como era antes de B2: una hoja fija, sin listar nada."""
    from python_calamine import CalamineWorkbook

    wb = CalamineWorkbook.from_filelike(io.BytesIO(contenido))
    filas = wb.get_sheet_by_name(hoja).to_python(skip_empty_area=False)

    def recortar(celdas):
        fin = len(celdas)
        while fin and (celdas[fin - 1] is None or str(celdas[fin - 1]).strip() == ""):
            fin -= 1
        return celdas[:fin]

    i = next(i for i, f in enumerate(filas) if recortar(list(f)))
    datos = [
        FilaCruda(k + 1, recortar(list(filas[k])))
        for k in range(i + 1, len(filas))
        if recortar(list(filas[k]))
    ]
    return hoja, i + 1, recortar(list(filas[i])), datos


@pytest.mark.parametrize(
    "contenido",
    [
        libro(
            {
                "VENCIDA": [
                    ["Pagare", "Monto", "Fecha"],
                    ["001", 10.5, date(2026, 9, 10)],
                    [],
                    ["002", 3],
                ]
            }
        ),
        libro(
            {
                "Td": [["r"]],
                "VENCIDA": [[], [], ["a", None, "c"], [None, None, None], ["1", "", "3"]],
            }
        ),
        ods({"VENCIDA": [["Pagare", "Zona"], ["001", "Norte"], ["", ""], ["002", "Sur"]]}),
    ],
)
def test_leer_hoja_da_lo_mismo_que_antes(contenido) -> None:
    hoja = LectorCalamine().leer_hoja(contenido)

    assert (hoja.nombre, hoja.fila_cabecera, hoja.cabeceras, hoja.filas) == _hoja_de_antes(
        contenido, "VENCIDA"
    )


def test_leer_hoja_y_leer_tabla_dicen_lo_mismo() -> None:
    contenido = libro({"A": [["x"]], "VENCIDA": [["Pagare", "Monto"], ["001", 10.5]]})

    hoja = LectorCalamine().leer_hoja(contenido)
    tabla = LectorCalamine().leer_tabla(contenido, OpcionesLectura(hoja="VENCIDA"))

    assert (hoja.nombre, hoja.fila_cabecera, hoja.cabeceras, hoja.filas) == (
        tabla.hoja,
        tabla.fila_cabecera,
        tabla.cabeceras,
        tabla.filas,
    )


def test_leer_hoja_sigue_pidiendo_una_hoja_de_calculo_y_la_hoja_que_se_nombra() -> None:
    with pytest.raises(ArchivoIlegible):
        LectorCalamine().leer_hoja(b"Pagare,Monto\n001,10\n")
    with pytest.raises(HojaNoEncontrada):  # sin VENCIDA: no cae a la primera hoja
        LectorCalamine().leer_hoja(libro({"Otra": [["a"]]}))


# --- CSV: codificacion y separador ----------------------------------------------------------------

FILAS_CON_TILDES = [
    ["Región", "Año", "Observación"],
    ["Ñuñoa", "2026", "ácido"],
    ["Perú", "7", "ok"],
]


def csv_de(
    filas, separador: str = ",", codificacion: str = "utf-8", terminador: str = "\n"
) -> bytes:
    salida = io.StringIO(newline="")
    csv.writer(salida, delimiter=separador, lineterminator=terminador).writerows(filas)
    return salida.getvalue().encode(codificacion)


@pytest.mark.parametrize("separador", [",", ";", "\t"])
@pytest.mark.parametrize(
    ("escrita_en", "informada"),
    [
        ("utf-8", "utf-8"),
        ("utf-8-sig", "utf-8-sig"),
        ("cp1252", "windows-1252"),
        ("latin-1", "windows-1252"),  # las tildes y la ñ son las mismas en las dos
    ],
)
def test_un_csv_se_lee_con_cualquier_separador_y_codificacion(
    separador, escrita_en, informada
) -> None:
    contenido = csv_de(FILAS_CON_TILDES, separador, escrita_en)

    tabla = leer(contenido, "datos.csv")

    assert tabla.formato is F.CSV
    assert (tabla.separador, tabla.codificacion) == (separador, informada)
    assert tabla.cabeceras == FILAS_CON_TILDES[0]
    assert [f.celdas for f in tabla.filas] == FILAS_CON_TILDES[1:]
    assert tabla.hojas == () and tabla.hoja is None and tabla.advertencias == ()


def test_el_bom_de_utf_8_se_quita_del_primer_encabezado() -> None:
    tabla = leer(b"\xef\xbb\xbfPagare,Zona\n001,Norte\n", "datos.csv")

    assert tabla.codificacion == "utf-8-sig"
    assert tabla.cabeceras == ["Pagare", "Zona"]


def test_el_bom_tambien_se_quita_si_la_codificacion_elegida_es_utf_8() -> None:
    tabla = leer(b"\xef\xbb\xbfPagare,Zona\n", "datos.csv", codificacion="utf-8")

    assert (tabla.codificacion, tabla.cabeceras) == ("utf-8", ["Pagare", "Zona"])


def test_si_no_es_utf_8_se_lee_como_windows_1252() -> None:
    tabla = leer("Región;Año\nÑuñoa;1\n".encode("cp1252"), "datos.csv")

    assert (tabla.codificacion, tabla.cabeceras) == ("windows-1252", ["Región", "Año"])


def test_un_archivo_que_windows_1252_no_decodifica_cae_en_latin_1() -> None:
    # 0x81 no esta definido en Windows-1252 (en Latin-1 es un control).
    contenido = b"Regi\xf3n;A\xf1o\nx\x81y;1\n"

    tabla = leer(contenido, "datos.csv")

    assert tabla.codificacion == "latin-1"
    assert tabla.cabeceras == ["Región", "Año"]
    assert tabla.filas[0].celdas == ["x\x81y", "1"]


@pytest.mark.parametrize("indefinido", [0x81, 0x8D, 0x8F, 0x90, 0x9D])
def test_cada_byte_que_windows_1252_no_define_manda_a_latin_1(indefinido) -> None:
    tabla = leer(b"a;b\n" + bytes([indefinido]) + b";\xf1\n", "datos.csv")

    assert tabla.codificacion == "latin-1"


def test_el_orden_de_las_codificaciones_es_el_de_la_lista_de_la_pantalla() -> None:
    assert lector_csv.CODIFICACIONES == ("utf-8-sig", "utf-8", "windows-1252", "latin-1")


def test_las_comillas_y_el_euro_de_windows_se_leen_como_tales() -> None:
    # Estos caracteres caen en 0x80-0x9F: en Latin-1 serian controles invisibles.
    filas = [["Nota", "Monto"], ["\u201chola\u201d \u2013 \u2014 \u2026", "10\u20ac"]]

    tabla = leer(csv_de(filas, ";", "cp1252"), "datos.csv")

    assert tabla.codificacion == "windows-1252"
    assert tabla.filas[0].celdas == filas[1]


def test_un_texto_solo_ascii_se_informa_como_utf_8() -> None:
    assert leer(b"a,b\n1,2\n", "datos.csv").codificacion == "utf-8"


def test_la_codificacion_elegida_gana_a_la_detectada() -> None:
    contenido = "Región,Año\n".encode()  # UTF-8

    tabla = leer(contenido, "datos.csv", codificacion="latin-1")

    assert tabla.codificacion == "latin-1"
    assert tabla.cabeceras == ["RegiÃ³n", "AÃ±o"]  # lo que da leerlo como Latin-1


def test_una_codificacion_elegida_que_no_sirve_es_ilegible_con_el_motivo() -> None:
    with pytest.raises(CodificacionNoCoincide, match="no se puede leer como utf-8"):
        leer("Región\n".encode("latin-1"), "datos.csv", codificacion="utf-8")
    with pytest.raises(CodificacionInvalida, match="no existe"):
        leer(b"a\n", "datos.csv", codificacion="klingon")


def test_el_separador_elegido_gana_al_detectado() -> None:
    contenido = b"a;b\n1;2\n"

    tabla = leer(contenido, "datos.csv", separador=",")

    assert (tabla.separador, tabla.cabeceras, tabla.filas[0].celdas) == (",", ["a;b"], ["1;2"])
    assert leer(contenido, "datos.csv").separador == ";"


@pytest.mark.parametrize("separador", ["", "ab", '"', "\n"])
def test_un_separador_elegido_invalido_es_ilegible(separador) -> None:
    opciones = OpcionesLectura(separador=separador)
    if separador == "":  # vacio = no elegido: se detecta
        assert leer_csv(b"a,b\n", opciones).separador == ","
        return
    with pytest.raises(SeparadorInvalido, match="un solo carácter"):
        leer_csv(b"a,b\n", opciones)


def test_si_el_sniffer_no_decide_va_punto_y_coma_si_esta_en_la_primera_linea(monkeypatch) -> None:
    def no_decide(self, muestra, delimiters=None):
        raise csv.Error("no decide")

    monkeypatch.setattr(csv.Sniffer, "sniff", no_decide)

    assert leer(b"a;b\n1,2\n", "datos.csv").separador == ";"
    assert leer(b"a,b\n1;2\n", "datos.csv").separador == ","
    assert leer(b"\n\nsolo\n", "datos.csv").separador == ","


def test_el_sniffer_es_el_ultimo_recurso_y_solo_ve_los_tres_separadores(monkeypatch) -> None:
    vistos: list[dict] = []
    sniff = csv.Sniffer.sniff

    def espia(self, muestra, delimiters=None):
        vistos.append({"largo": len(muestra), "delimiters": delimiters})
        return sniff(self, muestra, delimiters=delimiters)

    monkeypatch.setattr(csv.Sniffer, "sniff", espia)

    leer(b"a,b\n1,2\n" * 3, "datos.csv")  # un separador consistente: el sniffer no interviene
    assert vistos == []
    leer(b"a,b\n1,2,3\n" + b"1,2\n" * 40_000, "datos.csv")  # ninguno es consistente

    assert vistos == [{"largo": lector_csv.MUESTRA_PARA_SEPARADOR, "delimiters": ",;\t"}]
    assert lector_csv.MUESTRA_PARA_SEPARADOR == 64 * 1024


def test_otro_separador_no_se_detecta_y_se_toma_la_coma() -> None:
    tabla = leer(b"a|b\n1|2\n", "datos.csv")

    assert (tabla.separador, tabla.cabeceras) == (",", ["a|b"])
    assert leer(b"a|b\n1|2\n", "datos.csv", separador="|").cabeceras == ["a", "b"]


# --- CSV: el separador no lo decide el desempate del Sniffer -------------------------------------

EXCEL_EN_ESPANOL = "agencia;saldo\nNorte;1500,25\nSur;980,10\n"


def test_un_csv_del_excel_en_espanol_usa_punto_y_coma_con_coma_decimal() -> None:
    tabla = leer(EXCEL_EN_ESPANOL.encode("cp1252"), "datos.csv")

    assert (tabla.separador, tabla.codificacion) == (";", "utf-8")  # solo ASCII
    assert tabla.cabeceras == ["agencia", "saldo"]
    assert [f.celdas for f in tabla.filas] == [["Norte", "1500,25"], ["Sur", "980,10"]]


def test_el_caso_en_que_el_sniffer_se_equivoca_con_la_coma_decimal() -> None:
    # La coma tambien aparece una vez por linea (encabezado y montos): el Sniffer elige `,`.
    contenido = "agencia;saldo,total\nNorte;1500,25\nSur;980,10\n"
    assert csv.Sniffer().sniff(contenido, delimiters=",;\t").delimiter == ","  # el problema

    tabla = leer(contenido.encode(), "datos.csv")

    assert tabla.separador == ";"
    assert tabla.cabeceras == ["agencia", "saldo,total"]
    assert [f.celdas for f in tabla.filas] == [["Norte", "1500,25"], ["Sur", "980,10"]]


def test_el_excel_en_espanol_con_cp1252_y_comillas_tipograficas() -> None:
    contenido = (
        "Región;Observación;Monto\n"
        "Norte;\u201cal día\u201d \u2013 ok;1500,25\u20ac\n"
        "Sur;\u201cen mora\u201d;980,10\u20ac\n"
    ).encode("cp1252")

    tabla = leer(contenido, "datos.csv")

    assert (tabla.separador, tabla.codificacion) == (";", "windows-1252")
    assert tabla.cabeceras == ["Región", "Observación", "Monto"]
    assert [f.celdas for f in tabla.filas] == [
        ["Norte", "\u201cal día\u201d \u2013 ok", "1500,25\u20ac"],
        ["Sur", "\u201cen mora\u201d", "980,10\u20ac"],
    ]


def test_los_montos_con_coma_entre_comillas_no_parten_un_csv_de_comas() -> None:
    contenido = b'agencia,saldo\nNorte,"1500,25"\nSur,"980,10"\n'

    tabla = leer(contenido, "datos.csv")

    assert tabla.separador == ","
    assert [f.celdas for f in tabla.filas] == [["Norte", "1500,25"], ["Sur", "980,10"]]


def test_un_csv_con_tabulaciones_y_coma_decimal_usa_tabulacion() -> None:
    tabla = leer(b"agencia\tsaldo\nNorte\t1500,25\nSur\t980,10\n", "datos.csv")

    assert tabla.separador == "\t"


def test_un_csv_de_una_sola_columna_se_lee_con_la_coma_por_defecto() -> None:
    tabla = leer(b"agencia\nNorte\nSur\n", "datos.csv")

    assert (tabla.separador, tabla.cabeceras) == (",", ["agencia"])
    assert [f.celdas for f in tabla.filas] == [["Norte"], ["Sur"]]


def test_si_mas_de_un_separador_es_consistente_gana_punto_y_coma_luego_tab_y_luego_coma() -> None:
    assert leer(b"a;b,c\n1;2,3\n", "d.csv").separador == ";"
    assert leer(b"a\tb,c\n1\t2,3\n", "d.csv").separador == "\t"
    assert leer(b"a;b\tc\n1;2\t3\n", "d.csv").separador == ";"
    assert lector_csv.CANDIDATOS_DE_SEPARADOR == (";", "\t", ",")


def test_un_separador_consistente_necesita_mas_de_un_campo_en_todos_los_registros() -> None:
    # `;` da 2 campos en la cabecera y 3 en una fila: no es consistente; `,` si (2 y 2).
    assert leer(b"a;b\n1;2;3\n", "d.csv").separador == ";"  # lo decide el Sniffer o la regla de hoy
    assert leer(b"a,b;c\n1,2;3\n", "d.csv").separador == ";"
    assert leer(b"a,b;c\n1,2\n", "d.csv").separador == ","


def test_los_registros_vacios_no_cuentan_para_la_consistencia() -> None:
    assert leer(b"\n\na;b\n\n1;2\n\n", "d.csv").separador == ";"


def test_solo_cuentan_los_primeros_50_registros() -> None:
    parejo = "a;b\n" + "1;2\n" * 49  # 50 registros iguales
    desparejo = parejo + "1;2;3;4;5\n" * 100

    assert leer(desparejo.encode(), "d.csv").separador == ";"
    assert leer((parejo + "1;2;3\n").encode(), "d.csv").separador == ";"  # el 51 no cuenta


def test_el_registro_partido_al_final_de_la_muestra_no_cuenta() -> None:
    ancho = "x" * 1500
    contenido = (f"{ancho};{ancho}\n" * 100).encode()  # la muestra de 64 KB corta un registro

    assert len(contenido) > lector_csv.MUESTRA_PARA_SEPARADOR
    assert leer(contenido, "d.csv").separador == ";"


def test_una_celda_gigante_en_la_muestra_no_rompe_la_deteccion() -> None:
    contenido = b"a;b\n" + b"x" * 200_000 + b";1\n"

    with pytest.raises(ArchivoIlegible):  # la lectura entera si falla (limite de csv)
        leer(contenido, "d.csv")
    assert lector_csv._detectar_separador("a;b\n" + "x" * 200_000 + ";1\n") == ";"


# --- CSV: filas y celdas --------------------------------------------------------------------------


def test_las_comillas_protegen_el_separador_y_los_saltos_de_linea_dentro_de_una_celda() -> None:
    contenido = b'Nombre;Nota\n"Uno; el primero";"linea 1\nlinea 2"\ndos;"con ""comillas"""\n'

    tabla = leer(contenido, "datos.csv")

    assert [f.celdas for f in tabla.filas] == [
        ["Uno; el primero", "linea 1\nlinea 2"],
        ["dos", 'con "comillas"'],
    ]
    # La celda con dos lineas es UNA fila, como en Excel: la siguiente es la 3.
    assert [f.numero_fila for f in tabla.filas] == [2, 3]


def test_las_filas_vacias_al_principio_no_son_la_cabecera() -> None:
    tabla = leer(b"\n\n,,\n  ,\na,b\n1,2\n", "datos.csv")

    assert tabla.fila_cabecera == 5
    assert tabla.cabeceras == ["a", "b"]
    assert tabla.filas == [FilaCruda(6, ["1", "2"])]


def test_las_filas_vacias_del_medio_se_saltan_pero_cuentan_en_la_numeracion() -> None:
    tabla = leer(b"a,b\n1,2\n\n,\n3,4\n", "datos.csv")

    assert [(f.numero_fila, f.celdas) for f in tabla.filas] == [(2, ["1", "2"]), (5, ["3", "4"])]


def test_las_celdas_vacias_del_final_se_recortan_y_las_del_medio_quedan() -> None:
    tabla = leer(b"a,b,c,d\n1,,3,\n,,,\n,2,,\n", "datos.csv")

    assert tabla.filas == [FilaCruda(2, ["1", "", "3"]), FilaCruda(4, ["", "2"])]


def test_las_celdas_son_siempre_texto_y_no_se_convierte_nada() -> None:
    tabla = leer(b"pagare,monto,fecha,si\n0001,10.50,2026-09-10,true\n", "datos.csv")

    assert tabla.filas[0].celdas == ["0001", "10.50", "2026-09-10", "true"]
    assert {type(c) for c in tabla.filas[0].celdas} == {str}


def test_los_espacios_de_una_celda_se_conservan() -> None:
    assert leer(b"a,b\n  x  ,y\n", "datos.csv").filas[0].celdas == ["  x  ", "y"]


@pytest.mark.parametrize("terminador", ["\n", "\r\n", "\r"])
def test_cualquier_fin_de_linea_da_lo_mismo(terminador) -> None:
    contenido = csv_de([["a", "b"], ["1", "2"], ["3", "4"]], terminador=terminador)

    tabla = leer(contenido, "datos.csv", separador=",")

    assert [f.celdas for f in tabla.filas] == [["1", "2"], ["3", "4"]]


def test_sin_salto_final_y_solo_con_cabecera() -> None:
    assert leer(b"a,b\n1,2", "datos.csv").filas == [FilaCruda(2, ["1", "2"])]
    assert leer(b"a,b\n", "datos.csv").filas == []


@pytest.mark.parametrize("contenido", [b"", b"\n\n", b" \n,,\n ,, \n", b"\xef\xbb\xbf"])
def test_un_csv_sin_cabecera_ni_datos_es_hoja_vacia(contenido) -> None:
    with pytest.raises(HojaVacia):
        leer(contenido, "datos.csv")


def test_una_celda_mas_grande_que_el_limite_de_csv_es_ilegible() -> None:
    contenido = b"a,b\n" + b"x" * 200_000 + b",1\n"

    with pytest.raises(ArchivoIlegible, match="CSV no se pudo leer"):
        leer(contenido, "datos.csv")


def test_el_lector_devuelve_listas_nuevas_en_cada_lectura() -> None:
    contenido = b"a,b\n1,2\n"

    primera, segunda = leer(contenido, "x.csv"), leer(contenido, "x.csv")

    assert primera == segunda and primera.cabeceras is not segunda.cabeceras


# --- JSON -----------------------------------------------------------------------------------------


def json_de(valor) -> bytes:
    return json.dumps(valor, ensure_ascii=False).encode("utf-8")


def test_un_json_es_una_lista_de_objetos_con_la_union_de_las_claves() -> None:
    contenido = json_de([{"a": 1, "b": "x"}, {"b": "y", "c": 2.5}, {"a": 3, "d": True}])

    tabla = leer(contenido, "datos.json")

    assert tabla.formato is F.JSON
    assert tabla.cabeceras == ["a", "b", "c", "d"]  # en el orden de la primera aparicion
    assert tabla.fila_cabecera == 1
    assert [(f.numero_fila, f.celdas) for f in tabla.filas] == [
        (2, [1, "x"]),
        (3, ["", "y", 2.5]),
        (4, [3, "", "", True]),
    ]
    assert (tabla.hojas, tabla.hoja, tabla.separador, tabla.codificacion) == ((), None, None, None)


def test_los_numeros_y_los_booleanos_conservan_su_tipo() -> None:
    tabla = leer(json_de([{"i": 7, "f": 1.5, "b": False, "t": "007", "n": None}]), "d.json")

    celdas = tabla.filas[0].celdas
    assert celdas[:4] == [7, 1.5, False, "007"]
    assert [type(c) for c in celdas[:4]] == [int, float, bool, str]
    assert tabla.cabeceras == ["i", "f", "b", "t", "n"]
    assert len(celdas) == 4  # el null final es una celda vacia y se recorta


def test_un_null_es_una_celda_vacia_como_en_una_hoja_de_calculo() -> None:
    tabla = leer(json_de([{"a": None, "b": 1}]), "d.json")

    assert tabla.filas[0].celdas == ["", 1]


def test_un_objeto_vacio_no_es_una_fila_pero_cuenta_en_la_numeracion() -> None:
    tabla = leer(json_de([{"a": 1}, {}, {"a": 2}]), "d.json")

    assert [(f.numero_fila, f.celdas) for f in tabla.filas] == [(2, [1]), (4, [2])]


def test_un_valor_objeto_o_lista_va_como_texto_json_y_avisa_en_su_fila() -> None:
    contenido = json_de([{"a": 1, "b": {"x": "ñ"}}, {"a": 2, "c": [1, 2]}, {"a": 3}])

    tabla = leer(contenido, "datos.json")

    assert tabla.filas[0].celdas == [1, '{"x": "ñ"}']
    assert tabla.filas[1].celdas == [2, "", "[1, 2]"]
    assert tabla.advertencias == (
        AdvertenciaLectura(2, "b", CodigoAdvertenciaLectura.VALOR_NO_ESCALAR),
        AdvertenciaLectura(3, "c", CodigoAdvertenciaLectura.VALOR_NO_ESCALAR),
    )
    assert CodigoAdvertenciaLectura.VALOR_NO_ESCALAR.value == "valor_no_escalar"


def test_una_lista_o_un_objeto_vacios_valen_como_valor_no_escalar() -> None:
    tabla = leer(json_de([{"a": [], "b": {}}]), "d.json")

    assert tabla.filas[0].celdas == ["[]", "{}"]
    assert [a.columna for a in tabla.advertencias] == ["a", "b"]


def test_un_json_que_es_un_objeto_y_no_una_lista_es_ilegible() -> None:
    with pytest.raises(ArchivoIlegible, match="lista de objetos"):
        leer(json_de({"a": 1}), "datos.json")


@pytest.mark.parametrize("valor", [{"a": 1}, "texto", 7, True, None])
def test_el_lector_de_json_pide_una_lista_de_objetos(valor) -> None:
    with pytest.raises(ArchivoIlegible, match="lista de objetos"):
        leer_json(json_de(valor))


@pytest.mark.parametrize("valor", ["texto", 7, True, None])
def test_un_json_escalar_con_extension_json_es_ilegible_con_el_motivo(valor) -> None:
    with pytest.raises(ExtensionNoCoincide, match="no coincide con el contenido"):
        leer(json_de(valor), "datos.json")


def test_una_lista_de_algo_que_no_son_objetos_dice_cual_elemento() -> None:
    with pytest.raises(ArchivoIlegible, match="elemento 2"):
        leer(json_de([{"a": 1}, 5, {"a": 3}]), "datos.json")
    with pytest.raises(ArchivoIlegible, match="elemento 1"):
        leer(json_de([[1, 2]]), "datos.json")


def test_un_json_mal_formado_dice_donde() -> None:
    with pytest.raises(ArchivoIlegible, match=r"no es válido.*línea 2, columna"):
        leer(b'[\n{"a": 1,}]', "datos.json")


def test_un_json_que_no_esta_en_utf_8_es_ilegible() -> None:
    with pytest.raises(ArchivoIlegible, match="UTF-8"):
        leer('[{"a": "ñ"}]'.encode("latin-1"), "datos.json")


def test_un_json_con_bom_se_lee() -> None:
    assert leer(b"\xef\xbb\xbf" + json_de([{"a": 1}]), "datos.json").cabeceras == ["a"]


@pytest.mark.parametrize("valor", [[], [{}], [{}, {}]])
def test_un_json_sin_ninguna_clave_es_hoja_vacia(valor) -> None:
    with pytest.raises(HojaVacia):
        leer(json_de(valor), "datos.json")


def test_el_json_detectado_por_contenido_sin_extension() -> None:
    assert leer(json_de([{"a": 1}]), "").cabeceras == ["a"]


# --- Propiedad con semilla: un CSV al azar se lee con las mismas celdas ---------------------------

ALFABETO = list("abcXYZ019 áéíóúñÑ;,\t\"'\n\r-.")  # todos caben en Latin-1 y en Windows-1252
SOLO_WINDOWS = list("\u201c\u201d\u2013\u2014\u2026\u20ac")  # 0x80-0x9F de Windows-1252


def _celda_al_azar(azar: random.Random, extra: list[str] | None = None) -> str:
    alfabeto = ALFABETO + (extra or [])
    return "".join(azar.choice(alfabeto) for _ in range(azar.randint(0, 6)))


def _es_utf_8(contenido: bytes) -> bool:
    try:
        contenido.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _esperado(filas: list[list[str]]):
    """Lo que debe leerse: sin las celdas vacias del final ni las filas vacias, con el numero de
    registro de cada fila (base 1). Las celdas son las que se escribieron."""

    def sin_cola(celdas):
        fin = len(celdas)
        while fin and celdas[fin - 1].strip() == "":
            fin -= 1
        return celdas[:fin]

    registros = [(n, sin_cola(f)) for n, f in enumerate(filas, 1)]
    registros = [(n, f) for n, f in registros if f]
    return registros[0], registros[1:]


def test_un_csv_al_azar_se_lee_con_las_mismas_celdas() -> None:
    azar = random.Random(SEMILLA)
    for _ in range(400):
        separador = azar.choice(",;\t")
        codificacion = azar.choice(["utf-8", "utf-8-sig", "cp1252", "latin-1"])
        extra = SOLO_WINDOWS if codificacion != "latin-1" else None
        columnas = azar.randint(1, 5)
        filas = [
            [_celda_al_azar(azar, extra) for _ in range(columnas)]
            for _ in range(azar.randint(1, 8))
        ]
        filas[0][0] = "h" + filas[0][0]  # que haya cabecera
        contenido = csv_de(filas, separador, codificacion, azar.choice(["\n", "\r\n"]))
        if codificacion in ("cp1252", "latin-1") and _es_utf_8(contenido):
            continue  # unos bytes de una codificacion de un byte que tambien son UTF-8: ambiguo

        tabla = leer(contenido, "datos.csv", separador=separador)

        cabecera, datos = _esperado(filas)
        assert (tabla.fila_cabecera, tabla.cabeceras) == cabecera, (filas, separador, codificacion)
        assert [(f.numero_fila, f.celdas) for f in tabla.filas] == datos
        if codificacion == "utf-8-sig":
            assert tabla.codificacion == "utf-8-sig"
        elif any(ord(c) > 127 for fila in filas for c in "".join(fila)):
            assert tabla.codificacion == ("utf-8" if codificacion == "utf-8" else "windows-1252")


def test_un_csv_al_azar_tambien_se_lee_con_el_separador_y_la_codificacion_elegidos() -> None:
    azar = random.Random(SEMILLA + 1)
    for _ in range(200):
        separador = azar.choice(",;\t")
        codificacion = azar.choice(["utf-8", "windows-1252", "latin-1"])
        extra = SOLO_WINDOWS if codificacion != "latin-1" else None
        filas = [["h", "k"], *[[_celda_al_azar(azar, extra) for _ in range(2)] for _ in range(4)]]
        contenido = csv_de(filas, separador, codificacion)

        tabla = leer(contenido, "datos.csv", separador=separador, codificacion=codificacion)

        cabecera, datos = _esperado(filas)
        assert (tabla.separador, tabla.codificacion) == (separador, codificacion)
        assert (tabla.fila_cabecera, tabla.cabeceras) == cabecera
        assert [(f.numero_fila, f.celdas) for f in tabla.filas] == datos


def _numero_con_coma(azar: random.Random) -> str:
    return f"{azar.randint(0, 99999)},{azar.randint(0, 99):02d}"


def test_un_csv_con_coma_decimal_se_lee_sin_elegir_el_separador() -> None:
    azar = random.Random(SEMILLA + 2)
    palabras = ["Norte", "Sur", "Este", "Región", "Año", "al día", "Ñandú"]
    for _ in range(400):
        separador = azar.choice(";\t,")
        columnas = azar.randint(2, 5)
        codificacion = azar.choice(["utf-8", "utf-8-sig", "cp1252"])
        filas = [[azar.choice(palabras) for _ in range(columnas)]]
        for _ in range(azar.randint(1, 12)):
            filas.append(
                [
                    _numero_con_coma(azar) if azar.random() < 0.5 else azar.choice(palabras)
                    for _ in range(columnas)
                ]
            )
        contenido = csv_de(filas, separador, codificacion, azar.choice(["\n", "\r\n"]))

        tabla = leer(contenido, "datos.csv")  # sin elegir nada

        assert tabla.separador == separador, (filas, separador)
        assert tabla.cabeceras == filas[0]
        assert [f.celdas for f in tabla.filas] == filas[1:]


# --- Arquitectura ---------------------------------------------------------------------------------


def test_el_nucleo_de_la_lectura_no_depende_de_adaptadores_ni_del_mapeador() -> None:
    import ast
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1] / "app" / "core"
    for archivo in (
        raiz / "entities" / "lectura_tabla.py",
        raiz / "ports" / "lector_tabla_port.py",
        raiz / "services" / "lectura_tabla.py",
    ):
        modulos = {
            nombre
            for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8")))
            for nombre in (
                [a.name for a in nodo.names]
                if isinstance(nodo, ast.Import)
                else [nodo.module or ""]
                if isinstance(nodo, ast.ImportFrom)
                else []
            )
        }
        assert not [m for m in modulos if m.startswith(("app.adapters", "app.api"))], archivo.name
        assert not [m for m in modulos if "mapeador" in m or "ingesta_sabana" in m], archivo.name


# --- La muestra para el separador: lo que cuenta ---------------------------------------------


def test_los_registros_de_la_muestra_se_cuentan_por_campos() -> None:
    assert lector_csv._campos_por_registro("a;b;c\n1;2;3\n", ";", completa=True) == [3, 3]
    assert lector_csv._campos_por_registro("a;b;c\n1;2;3\n", ",", completa=True) == [1, 1]


def test_una_muestra_cortada_no_cuenta_su_ultimo_registro_que_puede_estar_partido() -> None:
    cortada = "a;b\nc;d\ne"

    assert lector_csv._campos_por_registro(cortada, ";", completa=False) == [2, 2]
    assert lector_csv._campos_por_registro(cortada, ";", completa=True) == [2, 2, 1]


def test_solo_se_cuentan_los_primeros_50_registros_de_la_muestra() -> None:
    muestra = "a;b\n" * 80

    assert len(lector_csv._campos_por_registro(muestra, ";", completa=True)) == 50
    assert len(lector_csv._campos_por_registro(muestra, ";", completa=False)) == 50
    assert lector_csv.REGISTROS_PARA_SEPARADOR == 50


def test_una_muestra_cortada_con_menos_de_50_registros_pierde_solo_el_ultimo() -> None:
    muestra = "a;b\n" * 49 + "c"

    assert len(lector_csv._campos_por_registro(muestra, ";", completa=False)) == 49


def test_los_registros_vacios_no_se_cuentan() -> None:
    assert lector_csv._campos_por_registro("a;b\n\n\nc;d\n", ";", completa=True) == [2, 2]
    assert lector_csv._campos_por_registro("\n\n", ";", completa=True) == []


def test_un_campo_mayor_que_el_limite_de_csv_deja_al_candidato_sin_cuenta() -> None:
    # Aunque antes haya registros buenos: si el candidato falla, no se usa a medias.
    assert lector_csv._campos_por_registro("a;b\n" + "x" * 200_000, ";", completa=True) == []


def test_el_registro_partido_por_el_corte_no_vuelve_inconsistente_al_punto_y_coma() -> None:
    # Cada registro mide 3 005 caracteres: el corte de los 64 KB cae dentro de la primera celda y
    # deja un registro de un solo campo. Con coma decimal, el Sniffer elegiria la coma.
    registro = "a" * 3000 + ";1,5\n"
    contenido = (registro * 30).encode()

    assert len(contenido) > lector_csv.MUESTRA_PARA_SEPARADOR
    assert leer(contenido, "datos.csv").separador == ";"
