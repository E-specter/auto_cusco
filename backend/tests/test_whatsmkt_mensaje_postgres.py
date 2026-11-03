"""El mensaje de WhatsMKT contra PostgreSQL real (T-WM-B3; RF-WM-19 a RF-WM-21, DU-WM-11).

La corre `architec` con `-ConBase` (AUTO_CUSCO_DB_TESTS=1 y la base `_test` migrada, que
`conftest.py` exige). Cubre lo que el SQL de `--sql` no ve: la ida y vuelta con filas, la siembra
leida de la base, la FK `ON DELETE SET NULL` y el CHECK del WhatsApp. Datos sinteticos.
"""

import os
from dataclasses import replace
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_whatsmkt_postgres import RepositorioWhatsmktPostgres
from app.core.services.plataformas.whatsmkt.contexto import contexto_mensaje
from tests.test_whatsmkt_mensaje_migracion import MIGRACION, REVISION_ANTERIOR

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

BACKEND = Path(__file__).resolve().parents[1]
SEMBRADOS = {clave: (nombre, texto) for clave, nombre, texto in MIGRACION.MENSAJES}


def _alembic() -> Config:
    configuracion = Config(str(BACKEND / "alembic.ini"))
    configuracion.set_main_option("script_location", str(BACKEND / "migrations"))
    return configuracion


def _mensajes_de_los_segmentos(engine) -> dict[str, tuple[str, str, int, dict]]:
    """clave -> (nombre, contexto, numero de version, contenido) del texto al que apunta."""
    with engine.connect() as cx:
        filas = cx.execute(
            text(
                "SELECT s.clave, t.nombre, t.contexto, v.numero, v.contenido "
                "FROM whatsmkt_segmento s JOIN texto_guardado t ON t.id = s.texto_guardado_id "
                "JOIN texto_guardado_version v ON v.texto_id = t.id"
            )
        ).all()
    return {f.clave: (f.nombre, f.contexto, f.numero, f.contenido) for f in filas}


@pytest.fixture
def estado():
    """El repositorio real. Al terminar la base vuelve a `head` con los tres mensajes sembrados y
    sin WhatsApp: lo que una prueba cambie (borrar un texto, apuntar un segmento a otro lado) se
    deshace con una ida y vuelta de la migracion, que es lo que la resiembra."""
    engine = get_engine()
    try:
        yield engine, RepositorioWhatsmktPostgres(engine)
    finally:
        command.downgrade(_alembic(), REVISION_ANTERIOR)
        command.upgrade(_alembic(), "head")


# --- La siembra -------------------------------------------------------------------------------


def test_cada_segmento_apunta_a_su_mensaje_sembrado_como_version_1(estado) -> None:
    engine, _ = estado

    mensajes = _mensajes_de_los_segmentos(engine)

    assert set(mensajes) == set(SEMBRADOS)
    for clave, (nombre, contexto, numero, contenido) in mensajes.items():
        assert (nombre, contexto, numero) == (SEMBRADOS[clave][0], "whatsmkt.mensaje", 1)
        assert contenido == {"texto": SEMBRADOS[clave][1]}  # textual, con sus espacios dobles


def test_los_mensajes_sembrados_los_acepta_el_validador_del_contexto(estado) -> None:
    engine, _ = estado

    for _, _, _, contenido in _mensajes_de_los_segmentos(engine).values():
        assert contexto_mensaje(lambda: 4096).validar(contenido) == ()


def test_los_segmentos_se_leen_con_su_texto_guardado_id(estado) -> None:
    _, repo = estado

    segmentos = repo.listar_segmentos()

    assert [s.clave for s in segmentos] == ["preventivo", "tramo_2", "mayores_2"]
    assert all(s.texto_guardado_id is not None for s in segmentos)


# --- La ida y vuelta --------------------------------------------------------------------------


def test_la_migracion_va_y_vuelve_y_resiembra_los_mensajes(estado) -> None:
    engine, _ = estado
    try:
        command.downgrade(_alembic(), REVISION_ANTERIOR)

        columnas_segmento = {c["name"] for c in inspect(engine).get_columns("whatsmkt_segmento")}
        columnas_config = {c["name"] for c in inspect(engine).get_columns("whatsmkt_configuracion")}
        with engine.connect() as cx:
            quedan = cx.execute(
                text("SELECT count(*) FROM texto_guardado WHERE contexto = 'whatsmkt.mensaje'")
            ).scalar_one()
        assert "texto_guardado_id" not in columnas_segmento
        assert "whatsapp_contacto" not in columnas_config
        assert quedan == 0  # los sembrados se fueron, con sus versiones

        command.upgrade(_alembic(), "head")
        assert {c["name"] for c in inspect(engine).get_columns("whatsmkt_segmento")} >= {
            "texto_guardado_id"
        }
        assert set(_mensajes_de_los_segmentos(engine)) == set(SEMBRADOS)
    finally:
        command.upgrade(_alembic(), "head")


def test_el_downgrade_no_borra_los_textos_propios_del_contexto(estado) -> None:
    engine, _ = estado
    with engine.begin() as cx:
        cx.execute(
            text(
                "INSERT INTO texto_guardado (contexto, nombre, nombre_normalizado) "
                "VALUES ('whatsmkt.mensaje', 'zz prueba propio', 'zz prueba propio')"
            )
        )
    try:
        command.downgrade(_alembic(), REVISION_ANTERIOR)
        with engine.connect() as cx:
            quedan = cx.execute(
                text(
                    "SELECT count(*) FROM texto_guardado "
                    "WHERE contexto = 'whatsmkt.mensaje' AND nombre = 'zz prueba propio'"
                )
            ).scalar_one()
        assert quedan == 1
    finally:
        command.upgrade(_alembic(), "head")
        with engine.begin() as cx:
            cx.execute(text("DELETE FROM texto_guardado WHERE nombre = 'zz prueba propio'"))


# --- La FK y el CHECK -------------------------------------------------------------------------


def test_borrar_el_texto_de_un_segmento_deja_al_segmento_sin_mensaje(estado) -> None:
    engine, repo = estado
    with engine.begin() as cx:
        cx.execute(
            text(
                "DELETE FROM texto_guardado WHERE id = "
                "(SELECT texto_guardado_id FROM whatsmkt_segmento WHERE clave = 'tramo_2')"
            )
        )

    por_clave = {s.clave: s.texto_guardado_id for s in repo.listar_segmentos()}

    assert por_clave["tramo_2"] is None
    assert por_clave["preventivo"] is not None and por_clave["mayores_2"] is not None


def test_el_whatsapp_de_contacto_se_guarda_y_la_base_rechaza_uno_mal_escrito(estado) -> None:
    engine, repo = estado
    actual = repo.obtener_configuracion()

    guardada = repo.guardar_configuracion(replace(actual, whatsapp_contacto="900000123"))
    sin_numero = repo.guardar_configuracion(replace(actual, whatsapp_contacto=None))

    assert guardada.whatsapp_contacto == "900000123"
    assert sin_numero.whatsapp_contacto is None
    for malo in ("812345678", "90000012", "abc"):
        with pytest.raises(IntegrityError):
            repo.guardar_configuracion(replace(actual, whatsapp_contacto=malo))


def test_un_segmento_apunta_a_un_texto_que_existe_o_a_ninguno(estado) -> None:
    engine, repo = estado
    segmentos = repo.listar_segmentos()

    with pytest.raises(IntegrityError):
        repo.reemplazar_segmentos(
            [replace(segmentos[0], texto_guardado_id=2_000_000_000), *segmentos[1:]]
        )

    sin_mensaje = repo.reemplazar_segmentos([replace(s, texto_guardado_id=None) for s in segmentos])
    assert all(s.texto_guardado_id is None for s in sin_mensaje)
