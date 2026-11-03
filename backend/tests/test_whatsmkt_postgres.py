"""Configuracion, segmentos y adjuntos de WhatsMKT contra PostgreSQL real (T-WM-B1).

La corre `architec` con `-ConBase` (AUTO_CUSCO_DB_TESTS=1 y la base `_test` migrada, que
`conftest.py` exige). Cubre lo que los dobles en memoria no ven: la ida y vuelta de la migracion,
la siembra, el reemplazo atomico de segmentos, el adjunto repetido por huella y las restricciones.
La configuracion y los segmentos son unicos, asi que cada prueba guarda su estado antes y lo
restituye al terminar. Datos sinteticos.
"""

import hashlib
import os
from dataclasses import replace
from datetime import time
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_whatsmkt_postgres import RepositorioWhatsmktPostgres
from app.core.entities.whatsmkt import (
    SEGMENTOS_POR_DEFECTO,
    ConfiguracionWhatsmkt,
    DefinicionDefectoNoExiste,
    Horario,
    SegmentoWhatsmkt,
    TipoAdjunto,
)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

BACKEND = Path(__file__).resolve().parents[1]
REVISION_ANTERIOR = "e2c6b4a8d195"
TABLAS = ("whatsmkt_configuracion", "whatsmkt_segmento", "whatsmkt_adjunto")
INEXISTENTE = 2_000_000_000


@pytest.fixture
def repositorio():
    """El repositorio real, con la configuracion y los segmentos restituidos al terminar."""
    engine = get_engine()
    repo = RepositorioWhatsmktPostgres(engine)
    configuracion, segmentos = repo.obtener_configuracion(), repo.listar_segmentos()
    try:
        yield repo
    finally:
        repo.guardar_configuracion(configuracion)
        repo.reemplazar_segmentos(segmentos)
        with engine.begin() as cx:
            cx.execute(text("DELETE FROM whatsmkt_adjunto WHERE nombre LIKE 'zz prueba %'"))


def _alembic() -> Config:
    configuracion = Config(str(BACKEND / "alembic.ini"))
    configuracion.set_main_option("script_location", str(BACKEND / "migrations"))
    return configuracion


# --- Migracion ------------------------------------------------------------------------------


def test_la_migracion_va_y_vuelve_y_siembra_lo_de_s_wm_1() -> None:
    engine = get_engine()
    try:
        command.downgrade(_alembic(), REVISION_ANTERIOR)
        assert not set(TABLAS) & set(inspect(engine).get_table_names())

        command.upgrade(_alembic(), "head")
        assert set(TABLAS) <= set(inspect(engine).get_table_names())
        sembrado = RepositorioWhatsmktPostgres(engine)
        configuracion = sembrado.obtener_configuracion()
        assert replace(configuracion, actualizado_en=None) == ConfiguracionWhatsmkt()
        assert sembrado.listar_segmentos() == list(SEGMENTOS_POR_DEFECTO)
    finally:
        command.upgrade(_alembic(), "head")


# --- Configuracion --------------------------------------------------------------------------


def test_la_configuracion_se_guarda_y_se_lee(repositorio) -> None:
    nueva = replace(
        repositorio.obtener_configuracion(),
        horario_1=Horario(time(9, 30), time(13, 0)),
        plantilla_nombre="Prueba {segmento}",
        tope_mensaje=1000,
        tope_video=5_000_000,
    )

    guardada = repositorio.guardar_configuracion(nueva)

    assert replace(guardada, actualizado_en=None) == replace(nueva, actualizado_en=None)
    assert repositorio.obtener_configuracion() == guardada


def test_una_definicion_que_no_existe_se_rechaza_sin_guardar(repositorio) -> None:
    antes = repositorio.obtener_configuracion()

    with pytest.raises(DefinicionDefectoNoExiste):
        repositorio.guardar_configuracion(replace(antes, definicion_defecto_id=INEXISTENTE))

    assert repositorio.obtener_configuracion() == antes


@pytest.mark.parametrize(
    "cambio",
    [
        {"horario_1": Horario(time(14, 0), time(8, 0))},
        {"horario_2": Horario(time(10, 0), time(10, 0))},
        {"plantilla_nombre": "   "},
        {"tope_mensaje": 0},
        {"tope_video": 0},
        {"tope_audio": -1},
        {"tope_pdf": 0},
    ],
)
def test_la_base_rechaza_lo_que_las_reglas_ya_rechazan(repositorio, cambio: dict) -> None:
    with pytest.raises(IntegrityError):
        repositorio.guardar_configuracion(replace(repositorio.obtener_configuracion(), **cambio))


def test_la_configuracion_es_una_sola_fila() -> None:
    with pytest.raises(IntegrityError), get_engine().begin() as cx:
        cx.execute(
            text(
                "INSERT INTO whatsmkt_configuracion SELECT 2, horario_1_inicio, horario_1_fin, "
                "horario_2_inicio, horario_2_fin, plantilla_nombre, definicion_defecto_id, "
                "tope_mensaje, tope_video, tope_audio, tope_pdf, actualizado_en "
                "FROM whatsmkt_configuracion"
            )
        )


# --- Segmentos ------------------------------------------------------------------------------


def test_los_segmentos_se_editan_por_clave_y_se_leen_en_orden(repositorio) -> None:
    editados = [
        SegmentoWhatsmkt("preventivo", "Al dia", None, 2, 0),
        SegmentoWhatsmkt("tramo_2", "Tramo 2", 3, 10, 1),
        SegmentoWhatsmkt("mayores_2", "Mayores", 11, None, 2),
    ]

    devueltos = repositorio.reemplazar_segmentos(editados)

    assert devueltos == editados
    assert repositorio.listar_segmentos() == editados


def test_el_reemplazo_de_segmentos_es_atomico(repositorio) -> None:
    antes = repositorio.listar_segmentos()
    # El segundo viola `rango_valido` (desde > hasta): el primero, ya actualizado, debe deshacerse.
    mala = [
        SegmentoWhatsmkt("preventivo", "Cambiado", None, 5, 0),
        SegmentoWhatsmkt("tramo_2", "Roto", 9, 1, 1),
    ]

    with pytest.raises(IntegrityError):
        repositorio.reemplazar_segmentos(mala)

    assert repositorio.listar_segmentos() == antes


# --- Adjuntos -------------------------------------------------------------------------------


def test_un_adjunto_repetido_por_huella_devuelve_el_existente(repositorio) -> None:
    contenido = b"zz contenido sintetico del adjunto"

    primero = repositorio.guardar_adjunto(TipoAdjunto.PDF, "zz prueba uno.pdf", contenido)
    segundo = repositorio.guardar_adjunto(TipoAdjunto.PDF, "zz prueba otro.pdf", contenido)

    assert segundo == primero
    assert primero.huella == hashlib.sha256(contenido).hexdigest()
    assert primero.tamano == len(contenido)
    assert primero.nombre == "zz prueba uno.pdf"  # gana el primero
    with get_engine().connect() as cx:
        filas = cx.execute(
            text("SELECT count(*) FROM whatsmkt_adjunto WHERE huella = :h"), {"h": primero.huella}
        ).scalar_one()
    assert filas == 1


def test_el_adjunto_archivado_se_lista_aparte_y_se_puede_desarchivar(repositorio) -> None:
    contenido = b"zz video sintetico"
    adjunto = repositorio.guardar_adjunto(TipoAdjunto.VIDEO, "zz prueba v.mp4", contenido)

    archivado = repositorio.archivar_adjunto(adjunto.id)
    de_nuevo = repositorio.archivar_adjunto(adjunto.id)

    assert archivado.archivado_en is not None
    assert de_nuevo.archivado_en == archivado.archivado_en  # repetirlo conserva la primera fecha
    assert adjunto.id not in [a.id for a in repositorio.listar_adjuntos()]
    assert adjunto.id in [a.id for a in repositorio.listar_adjuntos(archivados=True)]
    # Subirlo otra vez devuelve el archivado, sin tocarlo.
    otra_vez = repositorio.guardar_adjunto(TipoAdjunto.VIDEO, "zz prueba w.mp4", contenido)
    assert otra_vez == archivado

    assert repositorio.desarchivar_adjunto(adjunto.id).archivado_en is None
    assert adjunto.id in [a.id for a in repositorio.listar_adjuntos()]


def test_buscar_por_huella_encuentra_el_activo_el_archivado_y_no_carga_contenido(
    repositorio,
) -> None:
    contenido = b"zz buscar por huella sintetico"
    huella = hashlib.sha256(contenido).hexdigest()
    assert repositorio.buscar_adjunto_por_huella(huella) is None

    adjunto = repositorio.guardar_adjunto(TipoAdjunto.PDF, "zz prueba h.pdf", contenido)
    activo = repositorio.buscar_adjunto_por_huella(huella)
    repositorio.archivar_adjunto(adjunto.id)
    archivado = repositorio.buscar_adjunto_por_huella(huella)

    assert activo == adjunto
    assert archivado.id == adjunto.id
    assert archivado.archivado_en is not None
    assert not hasattr(archivado, "contenido")


def test_el_contenido_se_lee_aparte_y_listar_no_lo_carga(repositorio) -> None:
    contenido = b"\x00\x01zz binario sintetico\xff"
    adjunto = repositorio.guardar_adjunto(TipoAdjunto.AUDIO, "zz prueba a.mp3", contenido)

    assert repositorio.leer_contenido_adjunto(adjunto.id) == contenido
    assert repositorio.obtener_adjunto(adjunto.id) == adjunto
    assert not hasattr(adjunto, "contenido")
    assert repositorio.leer_contenido_adjunto(INEXISTENTE) is None
    assert repositorio.obtener_adjunto(INEXISTENTE) is None
    assert repositorio.archivar_adjunto(INEXISTENTE) is None


@pytest.mark.parametrize(("tipo", "huella"), [("pdf", "no-es-sha256"), ("gif", "a" * 64)])
def test_la_base_rechaza_una_huella_mal_formada_y_un_tipo_desconocido(
    tipo: str, huella: str
) -> None:
    insertar = text(
        "INSERT INTO whatsmkt_adjunto (tipo, nombre, tamano, huella, contenido) "
        "VALUES (:tipo, 'zz prueba x', 1, :huella, '\\x00')"
    )

    with pytest.raises(IntegrityError), get_engine().begin() as cx:
        cx.execute(insertar, {"tipo": tipo, "huella": huella})
