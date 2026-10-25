"""El salto de linea dentro de un texto sale siempre como LF en el XLSX (T-MTE-B17).

En modo `write_only`, openpyxl escribe cada hoja en un archivo temporal abierto en modo texto y en
Windows cada LF sale CR LF. El exportador lo deshace. Estas pruebas no dependen de `os.linesep`: la
fixture `windows` simula el modo texto de Windows en cualquier sistema (abre ese archivo con
`newline="\\r\\n"`), asi que el CI de Linux tambien cubre el caso de Windows.
"""

import builtins
import io
import zipfile

import openpyxl
import pytest
from et_xmlfile import incremental_tree

from app.adapters.output.exportadores import exportador_xlsx
from app.core.entities.exportacion import Tabla

TEXTOS = {
    "uno": "linea 1\nlinea 2",
    "dos": "con\r\nretorno de carro",
    "tres": "\nal principio y al final\n",
    "cuatro": "seguidos\n\n\nvarios",
    "cinco": "un\rsuelto",
}
TABLA = Tabla(
    nombre="saltos",
    cabeceras=("cabecera\ncon salto", *TEXTOS),
    filas=({"cabecera\ncon salto": "x", **TEXTOS},),
)


def _hoja(contenido: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(contenido)) as libro:
        return libro.read("xl/worksheets/sheet1.xml")


def _abrir_como_windows(archivo, modo="r", **opciones):
    """`open` con el modo texto de Windows: cada LF escrito sale CR LF."""
    return builtins.open(archivo, modo, newline="\r\n", **opciones)


@pytest.fixture
def windows(monkeypatch):
    """El modo texto de Windows en openpyxl y el salto del sistema que el exportador deshace."""
    monkeypatch.setattr(incremental_tree, "open", _abrir_como_windows, raising=False)
    monkeypatch.setattr(exportador_xlsx, "_SALTO_DEL_SISTEMA", b"\r\n")


@pytest.fixture
def windows_sin_arreglo(windows, monkeypatch):
    """Lo mismo, pero el exportador no deshace nada: reproduce el comportamiento de antes."""
    monkeypatch.setattr(exportador_xlsx, "_SALTO_DEL_SISTEMA", b"\n")


# --- En el sistema en que corre -----------------------------------------------------------------


def test_un_salto_de_linea_sale_como_lf_en_la_hoja() -> None:
    hoja = _hoja(exportador_xlsx.exportar(TABLA).contenido)

    assert b"linea 1\nlinea 2" in hoja
    assert b"cabecera\ncon salto" in hoja
    assert b"seguidos\n\n\nvarios" in hoja
    assert b"\r\n" not in hoja.replace(b"con\r\nretorno", b"")  # solo el CR LF que traia el dato


def test_la_hoja_se_lee_de_vuelta_con_sus_saltos() -> None:
    libro = openpyxl.load_workbook(io.BytesIO(exportador_xlsx.exportar(TABLA).contenido))

    valores = [celda.value for celda in libro.active[2]]

    # Un lector XML normaliza CR LF y CR a LF (XML 1.0, 2.11): es lo que ve Excel.
    assert valores == [
        "x",
        "linea 1\nlinea 2",
        "con\nretorno de carro",
        "\nal principio y al final\n",
        "seguidos\n\n\nvarios",
        "un\nsuelto",
    ]


# --- Simulando Windows en cualquier sistema -----------------------------------------------------


def test_la_simulacion_reproduce_el_problema_de_antes(windows_sin_arreglo) -> None:
    hoja = _hoja(exportador_xlsx.exportar(TABLA).contenido)

    assert b"linea 1\r\nlinea 2" in hoja  # sin el arreglo, el LF sale CR LF
    assert b"con\r\r\nretorno" in hoja  # y el CR LF del dato, CR CR LF


def test_en_windows_el_salto_sale_como_lf(windows) -> None:
    hoja = _hoja(exportador_xlsx.exportar(TABLA).contenido)

    assert b"linea 1\nlinea 2" in hoja
    assert b"cabecera\ncon salto" in hoja
    assert b"\r\r" not in hoja


def test_la_hoja_es_identica_en_windows_y_en_linux(monkeypatch) -> None:
    linux = _hoja(exportador_xlsx.exportar(TABLA).contenido)
    with monkeypatch.context() as simulado:
        simulado.setattr(incremental_tree, "open", _abrir_como_windows, raising=False)
        simulado.setattr(exportador_xlsx, "_SALTO_DEL_SISTEMA", b"\r\n")
        windows = _hoja(exportador_xlsx.exportar(TABLA).contenido)

    assert windows == linux
    assert b"con\r\nretorno de carro" in linux  # el CR LF del dato se conserva en los dos


def test_las_demas_partes_del_zip_no_cambian_en_windows(monkeypatch) -> None:
    def partes(contenido: bytes) -> dict[str, tuple[bytes, int]]:
        with zipfile.ZipFile(io.BytesIO(contenido)) as libro:
            return {
                i.filename: (libro.read(i), i.compress_type)
                for i in libro.infolist()
                if not i.filename.startswith("xl/worksheets/") and i.filename != "docProps/core.xml"
            }

    linux = partes(exportador_xlsx.exportar(TABLA).contenido)
    with monkeypatch.context() as simulado:
        simulado.setattr(incremental_tree, "open", _abrir_como_windows, raising=False)
        simulado.setattr(exportador_xlsx, "_SALTO_DEL_SISTEMA", b"\r\n")
        windows = partes(exportador_xlsx.exportar(TABLA).contenido)

    assert windows == linux


def test_el_libro_de_windows_se_abre_y_conserva_el_orden_de_las_partes(windows) -> None:
    contenido = exportador_xlsx.exportar(TABLA).contenido

    with zipfile.ZipFile(io.BytesIO(contenido)) as libro:
        assert libro.testzip() is None
        nombres = libro.namelist()
    assert "xl/worksheets/sheet1.xml" in nombres and "[Content_Types].xml" in nombres
    assert openpyxl.load_workbook(io.BytesIO(contenido)).active["A2"].value == "x"


# --- La reescritura del zip ---------------------------------------------------------------------


def _zip(**partes: bytes) -> bytes:
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as libro:
        for nombre, datos in partes.items():
            libro.writestr(nombre.replace("__", "/").replace("_xml", ".xml"), datos)
    return salida.getvalue()


def test_solo_se_reescriben_las_hojas(monkeypatch) -> None:
    monkeypatch.setattr(exportador_xlsx, "_SALTO_DEL_SISTEMA", b"\r\n")
    original = _zip(
        xl__worksheets__sheet1_xml=b"<t>a\r\nb</t>",
        xl__worksheets__sheet2_xml=b"<t>c\r\r\nd</t>",
        xl__sharedStrings_xml=b"<t>e\r\nf</t>",
        docProps__app_xml=b"<t>g\r\nh</t>",
    )

    with zipfile.ZipFile(io.BytesIO(exportador_xlsx._con_saltos_lf(original))) as libro:
        assert libro.read("xl/worksheets/sheet1.xml") == b"<t>a\nb</t>"
        assert libro.read("xl/worksheets/sheet2.xml") == b"<t>c\r\nd</t>"
        assert libro.read("xl/sharedStrings.xml") == b"<t>e\r\nf</t>"
        assert libro.read("docProps/app.xml") == b"<t>g\r\nh</t>"
        assert [i.compress_type for i in libro.infolist()] == [zipfile.ZIP_DEFLATED] * 4


def test_en_linux_el_archivo_se_devuelve_tal_cual(monkeypatch) -> None:
    monkeypatch.setattr(exportador_xlsx, "_SALTO_DEL_SISTEMA", b"\n")
    original = _zip(xl__worksheets__sheet1_xml=b"<t>a\r\nb</t>")

    assert exportador_xlsx._con_saltos_lf(original) is original


# --- El atajo: sin saltos no se reescribe nada --------------------------------------------------

SIN_SALTOS = Tabla(
    nombre="planos",
    cabeceras=("a", "b"),
    filas=({"a": "uno", "b": 2}, {"a": "dos", "b": 3}),
)


def _libro_de_windows(tabla: Tabla, monkeypatch) -> bytes:
    """El .xlsx tal como lo deja openpyxl con el modo texto de Windows, antes de deshacer nada."""
    with monkeypatch.context() as simulado:
        simulado.setattr(incremental_tree, "open", _abrir_como_windows, raising=False)
        simulado.setattr(exportador_xlsx, "_SALTO_DEL_SISTEMA", b"\n")
        return exportador_xlsx.exportar(tabla).contenido


def test_con_windows_simulado_y_sin_saltos_en_los_datos_se_devuelve_el_mismo_objeto(
    monkeypatch,
) -> None:
    contenido = _libro_de_windows(SIN_SALTOS, monkeypatch)
    monkeypatch.setattr(exportador_xlsx, "_SALTO_DEL_SISTEMA", b"\r\n")

    assert exportador_xlsx._con_saltos_lf(contenido) is contenido


def test_sin_saltos_en_los_datos_el_exportador_no_recomprime(windows, monkeypatch) -> None:
    recomprimidos: list[int] = []
    escribir = zipfile.ZipFile.writestr

    def espia(self, *args, **kwargs):
        recomprimidos.append(1)
        return escribir(self, *args, **kwargs)

    # El zip de openpyxl tambien usa writestr: se cuenta solo lo que pasa dentro del arreglo.
    contenido = _libro_de_windows(SIN_SALTOS, monkeypatch)
    monkeypatch.setattr(zipfile.ZipFile, "writestr", espia)

    assert exportador_xlsx._con_saltos_lf(contenido) is contenido
    assert recomprimidos == []


def test_con_saltos_en_los_datos_si_se_reescribe(monkeypatch) -> None:
    contenido = _libro_de_windows(TABLA, monkeypatch)
    monkeypatch.setattr(exportador_xlsx, "_SALTO_DEL_SISTEMA", b"\r\n")

    arreglado = exportador_xlsx._con_saltos_lf(contenido)

    assert arreglado is not contenido
    assert b"linea 1\r\nlinea 2" in _hoja(contenido)
    assert b"linea 1\nlinea 2" in _hoja(arreglado)


def test_un_cr_lf_propio_del_dato_vuelve_intacto_con_windows_simulado(monkeypatch) -> None:
    tabla = Tabla(nombre="crlf", cabeceras=("a",), filas=({"a": "con\r\nretorno"},))
    contenido = _libro_de_windows(tabla, monkeypatch)
    monkeypatch.setattr(exportador_xlsx, "_SALTO_DEL_SISTEMA", b"\r\n")

    assert b"con\r\r\nretorno" in _hoja(
        contenido
    )  # el modo texto lo dejo CR CR LF: hay que arreglarlo
    arreglado = exportador_xlsx._con_saltos_lf(contenido)

    assert arreglado is not contenido
    assert b"con\r\nretorno" in _hoja(arreglado)
    assert b"\r\r" not in _hoja(arreglado)


def test_basta_un_salto_en_una_de_las_hojas_para_reescribir_todas_las_que_lo_traen(
    monkeypatch,
) -> None:
    monkeypatch.setattr(exportador_xlsx, "_SALTO_DEL_SISTEMA", b"\r\n")
    original = _zip(
        xl__worksheets__sheet1_xml=b"<t>sin saltos</t>",
        xl__worksheets__sheet2_xml=b"<t>a\r\nb</t>",
    )

    with zipfile.ZipFile(io.BytesIO(exportador_xlsx._con_saltos_lf(original))) as libro:
        assert libro.read("xl/worksheets/sheet1.xml") == b"<t>sin saltos</t>"
        assert libro.read("xl/worksheets/sheet2.xml") == b"<t>a\nb</t>"


def test_un_salto_fuera_de_las_hojas_no_obliga_a_reescribir(monkeypatch) -> None:
    monkeypatch.setattr(exportador_xlsx, "_SALTO_DEL_SISTEMA", b"\r\n")
    original = _zip(
        xl__worksheets__sheet1_xml=b"<t>sin saltos</t>", xl__sharedStrings_xml=b"<t>a\r\nb</t>"
    )

    assert exportador_xlsx._con_saltos_lf(original) is original


def test_una_hoja_con_lf_sueltos_y_sin_cr_lf_no_se_reescribe(monkeypatch) -> None:
    # En Windows lo que se deshace es el CR LF, no el LF: un LF solo ya esta como debe estar.
    monkeypatch.setattr(exportador_xlsx, "_SALTO_DEL_SISTEMA", b"\r\n")
    original = _zip(xl__worksheets__sheet1_xml=b"<t>a\nb\nc</t>")

    assert exportador_xlsx._con_saltos_lf(original) is original
