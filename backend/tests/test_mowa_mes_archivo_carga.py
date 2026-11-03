"""El escritor del archivo de carga de MOWA MES sobre la definicion `mowa_mes` (T-MM-B15, paso 2).

`escribir_archivo_carga` aplica `DEFINICION_MOWA_MES` con `GeneradorCargas` y escribe con el
exportador comun. Estas pruebas fijan, sin base, que: da los mismos bytes que armar la tabla a mano
(como hasta T-MM-B15), los tipos de celda y la hoja, que el mensaje no se reinterpreta, y que un
fallo del generador lanza SIN datos de las filas. Los oros del archivo (`test_mowa_mes_archivo_oro`)
y de la exportacion (`test_exportacion_segura`) fijan los bytes contra constantes congeladas.

Datos sinteticos: telefonos 900000xxx, documentos y mensajes inventados.
"""

import io

import openpyxl
import pytest

from app.adapters.output.exportadores import exportador_xlsx
from app.adapters.output.plataformas.mowa_mes import archivo_carga
from app.adapters.output.plataformas.mowa_mes.archivo_carga import (
    ArchivoCargaInvalido,
    escribir_archivo_carga,
)
from app.core.entities.exportacion import OpcionesArchivo, Tabla
from app.core.entities.mapeo import ErrorGeneracion, FilaExcluida
from app.core.entities.mowa_mes_campana import CABECERAS_CARGA, HOJA_CARGA, FilaCarga
from app.core.services.mapeo_campos.generador import CargaGenerada
from tests.exportacion_seguridad_datos import huella_xlsx, largo_sin_comprimir_sin_core

FILAS = (
    FilaCarga("900000101", "ZZPRUEB vencio el 06/09/2026", "00000001", supervision=True),
    FilaCarga("900000102", "ZZPRUEB Mas INFO por https://wa.me/+51900000123", "20123456789"),
    FilaCarga("900000103", "ZZPRUEB (@titular) {x} 05/09/2026", "ZZCE123456"),
    FilaCarga("900000104", "=1+1 no es una formula", "123456789"),
    FilaCarga("900000105", "linea 1\nlinea 2", "00012345"),
)


def _hoja(contenido: bytes):
    return openpyxl.load_workbook(io.BytesIO(contenido))[HOJA_CARGA]


def _de_antes(filas) -> bytes:
    """El archivo tal como lo armaba `escribir_archivo_carga` antes de T-MM-B15: la tabla a mano."""
    tabla = Tabla(
        nombre="mowa_mes", cabeceras=CABECERAS_CARGA, filas=tuple(f.celdas() for f in filas)
    )
    return exportador_xlsx.exportar(
        tabla, OpcionesArchivo(hoja=HOJA_CARGA, con_cabeceras=True)
    ).contenido


def test_da_los_mismos_bytes_que_armar_la_tabla_a_mano() -> None:
    nuevo = escribir_archivo_carga(FILAS)
    antes = _de_antes(FILAS)

    assert huella_xlsx(nuevo) == huella_xlsx(antes)
    assert largo_sin_comprimir_sin_core(nuevo) == largo_sin_comprimir_sin_core(antes)


def test_una_carga_vacia_da_solo_las_cabeceras_como_antes() -> None:
    nuevo = escribir_archivo_carga(())

    assert huella_xlsx(nuevo) == huella_xlsx(_de_antes(()))
    assert [c.value for c in _hoja(nuevo)[1]] == ["numero", "mensaje", "dni"]


def test_la_hoja_y_las_cabeceras_son_las_de_la_carga() -> None:
    libro = openpyxl.load_workbook(io.BytesIO(escribir_archivo_carga(FILAS)))

    assert libro.sheetnames == ["Hoja1"]
    assert [c.value for c in libro["Hoja1"][1]] == list(CABECERAS_CARGA)


def test_los_tipos_de_celda_numero_numerico_y_dni_texto_con_sus_ceros() -> None:
    hoja = _hoja(escribir_archivo_carga(FILAS))
    leidas = list(hoja.iter_rows(min_row=2))

    assert len(leidas) == len(FILAS)
    for (numero, mensaje, dni), fila in zip(leidas, FILAS, strict=True):
        assert isinstance(numero.value, int) and numero.data_type == "n"
        assert numero.value == int(fila.numero)
        assert isinstance(mensaje.value, str) and mensaje.data_type == "s"
        assert isinstance(dni.value, str) and dni.data_type == "s"
        assert dni.value == fila.dni and mensaje.value == fila.mensaje
        assert dni.number_format == "General"  # sin formato de celda «Texto»: ninguna celda_texto
    assert [dni.value for _, _, dni in leidas] == [
        "00000001",
        "20123456789",
        "ZZCE123456",
        "123456789",
        "00012345",
    ]


@pytest.mark.parametrize(
    "mensaje",
    [
        "[@telefono]",
        "[@titular] {x}",
        "[@mensaje] y [@dni] [@numero]",
        "[@",
        "{{ [@x | primeros(2)] }}",
    ],
)
def test_el_mensaje_no_se_reinterpreta_sale_literal_en_la_celda(mensaje) -> None:
    # GSM-7 translitera los corchetes antes de llegar aqui, pero el escritor no depende de eso.
    filas = (FilaCarga("900000101", mensaje, "00000001"),)

    hoja = _hoja(escribir_archivo_carga(filas))

    assert hoja["B2"].value == mensaje and hoja["B2"].data_type == "s"
    assert (hoja["A2"].value, hoja["C2"].value) == (900000101, "00000001")


def test_un_mensaje_que_empieza_con_igual_sale_como_texto_y_no_como_formula() -> None:
    hoja = _hoja(escribir_archivo_carga((FilaCarga("900000101", "=1+1", "00000001"),)))

    assert hoja["B2"].value == "=1+1" and hoja["B2"].data_type == "s"


class _GeneradorFalso:
    def __init__(self, carga: CargaGenerada) -> None:
        self._carga = carga

    def generar(self, productos) -> CargaGenerada:
        list(productos)  # consume las filas como el real
        return self._carga


def _con_generador(monkeypatch, carga: CargaGenerada) -> None:
    monkeypatch.setattr(archivo_carga, "_GENERADOR", _GeneradorFalso(carga))


def _datos_de_las_filas() -> list[str]:
    return [dato for f in FILAS for dato in (f.numero, f.mensaje, f.dni)] + ["ZZPRUEB", "00000001"]


def test_si_el_generador_da_un_error_lanza_sin_datos_de_las_filas(monkeypatch) -> None:
    # El detalle del error del generador SI puede traer el valor: el escritor no debe copiarlo.
    error = ErrorGeneracion(2, "numero", "900000102 no es un numero", "valor_invalido")
    _con_generador(monkeypatch, CargaGenerada(("numero", "mensaje", "dni"), (), (error,)))

    with pytest.raises(ArchivoCargaInvalido) as capturado:
        escribir_archivo_carga(FILAS)

    texto = str(capturado.value)
    assert "fila 2" in texto and "'numero'" in texto and "valor_invalido" in texto
    assert not any(dato in texto for dato in _datos_de_las_filas())
    assert "no es un numero" not in texto  # tampoco el detalle


def test_si_el_generador_devuelve_menos_filas_lanza_sin_datos_de_las_filas(monkeypatch) -> None:
    una = {"numero": 900000101, "mensaje": "ZZPRUEB vencio el 06/09/2026", "dni": "00000001"}
    _con_generador(monkeypatch, CargaGenerada(("numero", "mensaje", "dni"), (una,), ()))

    with pytest.raises(ArchivoCargaInvalido) as capturado:
        escribir_archivo_carga(FILAS)

    texto = str(capturado.value)
    assert "1 filas de 5" in texto
    assert not any(dato in texto for dato in _datos_de_las_filas())


def test_si_el_generador_excluye_una_fila_lanza_aunque_la_cuenta_cierre(monkeypatch) -> None:
    exclusion = FilaExcluida(1, "sin_segmento", "detalle con 900000101", "000000000000000001")
    cinco = tuple(
        {"numero": 900000100 + i, "mensaje": "m", "dni": "0000000" + str(i)} for i in range(5)
    )
    carga = CargaGenerada(("numero", "mensaje", "dni"), cinco, (), (exclusion,))
    _con_generador(monkeypatch, carga)

    with pytest.raises(ArchivoCargaInvalido) as capturado:
        escribir_archivo_carga(FILAS)

    assert "900000101" not in str(capturado.value)


def test_el_generador_real_no_da_errores_con_las_filas_de_la_carga() -> None:
    carga = archivo_carga._GENERADOR.generar(f.celdas() for f in FILAS)

    assert carga.errores == () and carga.exclusiones == ()
    assert [tuple(fila.values()) for fila in carga.filas] == [
        (int(f.numero), f.mensaje, f.dni) for f in FILAS
    ]
