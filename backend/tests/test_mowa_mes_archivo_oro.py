"""Oro del archivo .xlsx de una campana de MOWA MES (T-MM-B15, paso 1; RF-MM-10 a RF-MM-12).

Congela, con el codigo de HOY, lo que sale de `CampanasMowaMesService.crear` con el escritor REAL
que inyecta la API (`escribir_archivo_carga`, `app/api/mowa_mes_campanas.py`): una campana dividida
en 3 archivos POR FILAS, con los supervisores al inicio del primer archivo y con documentos que no
son DNI ni RUC. El paso 2 (generar este archivo con `GeneracionCargasService` y la plataforma
`mowa_mes`) tiene que dar lo mismo byte a byte; las constantes
(`oro_mowa_mes_archivo_congelados.py`) no se recalculan.

Por cada archivo se congelan `numero`, `filas`, `supervision`, la huella de todas las partes del zip
salvo la hora de `core.xml` (`huella_xlsx`) y el largo SIN comprimir de esas mismas partes
(`largo_sin_comprimir_sin_core`). La division es por filas (registros chicos, bytes al maximo) a
proposito: la division por bytes mide el zip comprimido, y ese largo cambia entre las zlib de
CPython 3.13 y 3.14 (ver el docstring de `largo_sin_comprimir_sin_core`), asi que no seria estable.

Datos sinteticos: telefonos 900000xxx, titulares y documentos inventados.
"""

import io
import zipfile
from dataclasses import replace
from datetime import date

import pytest

from app.adapters.output.plataformas.mowa_mes.archivo_carga import escribir_archivo_carga
from app.api import mowa_mes_campanas as api_campanas
from app.core.entities.gestiones_digitales import ConfiguracionSupervision
from app.core.entities.mowa_mes import CodigoMowaMes
from app.core.entities.mowa_mes_campana import ArchivoCarga
from app.core.services.plataformas.mowa_mes.campana import CampanasMowaMesService
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService
from tests.exportacion_seguridad_datos import huella_xlsx, largo_sin_comprimir_sin_core
from tests.oro_mowa_mes_archivo_congelados import ARCHIVOS_CONGELADOS
from tests.test_gestiones_digitales import PROCEDENCIAS, SUPERVISORES, RepositorioSupervisionFalso
from tests.test_mowa_mes_campana import (
    MOMENTO,
    RepositorioCampanasMemoria,
    RepositorioCarteraFalso,
    peticion,
    producto,
)
from tests.test_mowa_mes_speech import WHATSAPP, RepositorioMowaMesFalso

REGISTROS_POR_ARCHIVO = 6
BYTES_POR_ARCHIVO = 2_000_000  # el maximo de la configuracion: la division sale por filas

# Los 6 segmentos (dias de atraso + 4 hasta el envio), titulares con tilde, enie, espacios y largos
# distintos, un RUC y dos documentos que no son DNI ni RUC, y un producto que se excluye. 12 se
# cargan: con los 5 supervisores son 17 filas y, de 6 en 6, 3 archivos (6, 6 y 5).
PRODUCTOS = [
    producto(1, dias_atraso=-10),  # preventiva
    producto(2, dias_atraso=4, titular="Ñandú Pérez López"),  # 1 a 8
    producto(3, dias_atraso=10, titular="AB"),  # 9 a 30
    producto(4, dias_atraso=40, documento_numero="20123456789", documento_tipo="ruc"),  # 31 a 60
    producto(5, dias_atraso=70, fecha_vencimiento_cuota=date(2026, 12, 31)),  # 61 a 90
    producto(6, dias_atraso=100, titular="   Peña Ruiz"),  # 91 a 120
    producto(7, dias_atraso=4, documento_numero="ZZCE123456", documento_tipo="extranjero"),
    producto(8, dias_atraso=10, documento_numero="123456789", documento_tipo="extranjero"),
    producto(9, dias_atraso=40, titular="APELLIDO/NOMBRE LARGO"),
    producto(10, dias_atraso=70),
    producto(11, dias_atraso=100, fecha_vencimiento_cuota=date(2027, 1, 1)),
    producto(12, dias_atraso=4, titular="12345678"),
    producto(13, telefono="123"),  # excluido: telefono_invalido
]


def archivos_de_la_campana() -> tuple[object, list[ArchivoCarga]]:
    """La campana creada por el servicio real con el escritor real; devuelve sus archivos."""
    mowa_mes = RepositorioMowaMesFalso(WHATSAPP)
    mowa_mes.configuracion = replace(
        mowa_mes.configuracion,
        registros_por_archivo=REGISTROS_POR_ARCHIVO,
        bytes_por_archivo=BYTES_POR_ARCHIVO,
    )
    supervision = RepositorioSupervisionFalso()
    supervision.configuracion = ConfiguracionSupervision(PROCEDENCIAS, SUPERVISORES)
    campanas = RepositorioCampanasMemoria()
    servicio = CampanasMowaMesService(
        ConsultaCarteraService(RepositorioCarteraFalso(PRODUCTOS)),
        mowa_mes,
        supervision,
        campanas,
        escribir_archivo_carga,  # el REAL, el mismo que cablea la API
        reloj=lambda: MOMENTO,
    )
    creada = servicio.crear(peticion())
    armada, archivos = campanas.guardadas[creada.id]
    return armada, archivos


def _coincide(archivo: ArchivoCarga) -> bool:
    """Si el archivo es el congelado: numero, filas, supervision, huella y largo sin comprimir."""
    esperado = ARCHIVOS_CONGELADOS[archivo.numero]
    return esperado == (
        archivo.numero,
        archivo.filas,
        archivo.supervision,
        huella_xlsx(archivo.contenido),
        largo_sin_comprimir_sin_core(archivo.contenido),
    )


def test_la_api_cablea_el_mismo_escritor_que_usa_el_oro() -> None:
    assert api_campanas.escribir_archivo_carga is escribir_archivo_carga


def test_la_campana_cubre_lo_que_el_oro_promete() -> None:
    armada, archivos = archivos_de_la_campana()

    assert [a.numero for a in archivos] == [1, 2, 3]  # 3 archivos, divididos por filas
    assert [a.filas for a in archivos] == [6, 6, 5]
    # los supervisores al inicio del primer archivo, y solo ahi (RF-MM-12)
    assert [a.supervision for a in archivos] == [len(SUPERVISORES), 0, 0]
    assert [f.supervision for f in armada.filas[: len(SUPERVISORES)]] == [True] * len(SUPERVISORES)
    # documentos que no son DNI ni RUC (RF-MM-10): se cargan y se advierten
    advertidas = [f for f in armada.filas if CodigoMowaMes.DOCUMENTO_NO_ESTANDAR in f.advertencias]
    assert {f.dni for f in advertidas} == {"ZZCE123456", "123456789"}
    assert armada.productos_cargados == 12 and len(armada.exclusiones) == 1
    assert {f.segmento.value for f in armada.filas if f.segmento} == {
        "preventiva",
        "1_a_8",
        "9_a_30",
        "31_a_60",
        "61_a_90",
        "91_a_120",
    }


def test_cada_archivo_de_la_campana_es_el_congelado() -> None:
    _, archivos = archivos_de_la_campana()

    assert sorted(ARCHIVOS_CONGELADOS) == [a.numero for a in archivos]
    for archivo in archivos:
        assert _coincide(archivo), archivo.numero


def test_dos_corridas_dan_los_mismos_archivos() -> None:
    primera = [(a.numero, huella_xlsx(a.contenido)) for a in archivos_de_la_campana()[1]]
    segunda = [(a.numero, huella_xlsx(a.contenido)) for a in archivos_de_la_campana()[1]]

    assert primera == segunda


def _con_un_byte_cambiado(contenido: bytes) -> bytes:
    """El mismo .xlsx con UN byte de `xl/worksheets/sheet1.xml` distinto, reempaquetado."""
    salida = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(contenido)) as origen,
        zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as destino,
    ):
        for nombre in origen.namelist():
            datos = origen.read(nombre)
            if nombre == "xl/worksheets/sheet1.xml":
                alterado = bytearray(datos)
                alterado[len(alterado) // 2] ^= 0x01  # un solo bit, sin cambiar el largo
                datos = bytes(alterado)
            destino.writestr(nombre, datos)
    return salida.getvalue()


@pytest.mark.parametrize("numero", [1, 2, 3])
def test_cambiar_un_byte_de_la_hoja_de_cualquier_archivo_rompe_la_comparacion(numero) -> None:
    _, archivos = archivos_de_la_campana()
    original = next(a for a in archivos if a.numero == numero)
    alterado = replace(original, contenido=_con_un_byte_cambiado(original.contenido))

    assert _coincide(original)  # el control: sin tocar, coincide
    assert len(alterado.contenido) > 0 and alterado.contenido != original.contenido
    assert largo_sin_comprimir_sin_core(alterado.contenido) == largo_sin_comprimir_sin_core(
        original.contenido
    )  # el largo solo no lo ve: lo atrapa la huella
    assert not _coincide(alterado)
