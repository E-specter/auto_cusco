"""La migracion del mensaje de WhatsMKT, sin base (T-WM-B3; RF-WM-19 a RF-WM-21, DU-WM-2).

Fija la siembra byte a byte frente a la tabla de RF-WM-21 y el SQL en los dos sentidos con
`--sql`. La ida y vuelta con filas esta en `test_whatsmkt_mensaje_postgres.py`.
"""

import io
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from tests.speech_congelado import cargar_migracion

BACKEND = Path(__file__).resolve().parents[1]
DOCUMENTO = BACKEND.parent / "docs" / "requerimientos-whatsmkt.md"
REVISION_ANTERIOR = "c9e5a1d7b384"
REVISION = "d3f7a1b9c524"
MIGRACION = cargar_migracion("d3f7a1b9c524_mensaje_de_whatsmkt.py")


def _configuracion() -> Config:
    configuracion = Config(str(BACKEND / "alembic.ini"))
    configuracion.set_main_option("script_location", str(BACKEND / "migrations"))
    return configuracion


def _sql(subir: bool) -> str:
    configuracion = _configuracion()
    configuracion.output_buffer = io.StringIO()
    if subir:
        command.upgrade(configuracion, f"{REVISION_ANTERIOR}:{REVISION}", sql=True)
    else:
        command.downgrade(configuracion, f"{REVISION}:{REVISION_ANTERIOR}", sql=True)
    return configuracion.output_buffer.getvalue()


def _textos_de_rf_wm_21() -> list[str]:
    """Los tres mensajes tal como estan escritos en RF-WM-21 (bloques de codigo, en orden)."""
    documento = DOCUMENTO.read_text(encoding="utf-8")
    seccion = documento[documento.index("RF-WM-21 —") : documento.index("RF-WM-22 —")]
    return re.findall(r"```[ \t]*\n[ \t]*(.*?)\n[ \t]*```", seccion, re.S)


# --- La siembra frente al documento -----------------------------------------------------------


def test_la_siembra_es_textual_frente_a_rf_wm_21() -> None:
    en_el_documento = _textos_de_rf_wm_21()

    assert len(en_el_documento) == 3
    assert [texto for _, _, texto in MIGRACION.MENSAJES] == en_el_documento


def test_cada_mensaje_va_a_su_segmento_con_su_nombre() -> None:
    assert [(clave, nombre) for clave, nombre, _ in MIGRACION.MENSAJES] == [
        ("preventivo", "Preventivo"),
        ("tramo_2", "Tramo 2"),
        ("mayores_2", "Tramos mayores al 2"),
    ]
    assert MIGRACION.CONTEXTO == "whatsmkt.mensaje"


def test_los_espacios_dobles_y_los_espacios_antes_de_una_coma_se_conservan_du_wm_2() -> None:
    preventivo, tramo_2, mayores_2 = (texto for _, _, texto in MIGRACION.MENSAJES)

    assert "vence  el" in preventivo and "agentes  KASNET" in preventivo
    assert "[$MACRO2$] ," in preventivo and "[$MACRO2$] ," in tramo_2
    assert "agencias , agentes" in mayores_2 and "[$MACRO3$] ," in mayores_2


def test_el_enlace_de_whatsapp_es_el_marcador_y_no_trae_ningun_numero() -> None:
    for _, _, texto in MIGRACION.MENSAJES:
        assert texto.count("[whatsapp]") == 1
        assert "wa.me" not in texto and "https://" not in texto
        assert not re.search(r"\d{9}", texto)  # ningun telefono: el real no va en el repositorio


def test_los_mensajes_cumplen_el_validador_del_contexto_y_las_reglas_del_mensaje() -> None:
    from app.core.services.plataformas.whatsmkt import mensaje
    from app.core.services.plataformas.whatsmkt.contexto import CONTEXTO_MENSAJE

    for _, _, texto in MIGRACION.MENSAJES:
        assert CONTEXTO_MENSAJE.validar({"texto": texto}) == ()
        mensaje.validar_sin_emojis(texto)
        mensaje.validar_largo(texto, 4096)
    # El de «Tramos mayores al 2» usa tres macros; los otros dos, dos.
    usadas = [mensaje.marcadores_del_texto(t).macros for _, _, t in MIGRACION.MENSAJES]
    assert usadas == [(1, 2), (1, 2), (1, 2, 3)]


# --- La cadena de migraciones -----------------------------------------------------------------


def test_la_migracion_cuelga_de_la_de_textos_guardados_y_el_arbol_tiene_una_sola_cabeza() -> None:
    directorio = ScriptDirectory.from_config(_configuracion())

    assert directorio.get_revision(REVISION).down_revision == REVISION_ANTERIOR
    assert len(directorio.get_heads()) == 1


def test_los_nombres_de_las_restricciones_miden_63_caracteres_o_menos() -> None:
    for nombre in (MIGRACION.CK_WHATSAPP, MIGRACION.FK_TEXTO):
        assert len(nombre) <= 63, nombre


# --- El SQL -----------------------------------------------------------------------------------


def test_el_upgrade_agrega_las_columnas_el_check_y_la_fk_con_set_null_antes_de_sembrar() -> None:
    sql = _sql(subir=True)

    posiciones = [
        sql.index("ADD COLUMN whatsapp_contacto VARCHAR(9)"),
        sql.index(MIGRACION.CK_WHATSAPP),
        sql.index("ADD COLUMN texto_guardado_id BIGINT"),
        sql.index(f"CONSTRAINT {MIGRACION.FK_TEXTO} FOREIGN KEY(texto_guardado_id)"),
        sql.index("INSERT INTO texto_guardado "),
    ]
    assert posiciones == sorted(posiciones)
    assert "REFERENCES texto_guardado (id) ON DELETE SET NULL" in sql
    assert "ck_ck_" not in sql  # `op.f`: el nombre ya trae el prefijo de la convencion


def test_el_upgrade_siembra_tres_textos_con_su_version_1_y_apunta_cada_segmento() -> None:
    sql = _sql(subir=True)

    assert sql.count("INSERT INTO texto_guardado ") == 3
    assert sql.count("INSERT INTO texto_guardado_version") == 3
    assert sql.count("UPDATE whatsmkt_segmento SET texto_guardado_id") == 3
    assert sql.count("jsonb_build_object('texto', ") == 3
    for _, _, texto in MIGRACION.MENSAJES:
        assert f"$wm${texto}$wm$" in sql  # el texto va tal cual, sin escapes
    for clave in ("preventivo", "tramo_2", "mayores_2"):
        assert f"WHERE clave = $wm${clave}$wm$" in sql


def test_el_downgrade_borra_lo_sembrado_antes_de_quitar_las_columnas() -> None:
    sql = _sql(subir=False)

    posiciones = [
        sql.index("DELETE FROM texto_guardado"),
        sql.index(f"DROP CONSTRAINT {MIGRACION.FK_TEXTO}"),
        sql.index("DROP COLUMN texto_guardado_id"),
        sql.index(f"DROP CONSTRAINT {MIGRACION.CK_WHATSAPP}"),
        sql.index("DROP COLUMN whatsapp_contacto"),
    ]
    assert posiciones == sorted(posiciones)
    for nombre in ("preventivo", "tramo 2", "tramos mayores al 2"):
        assert f"$wm${nombre}$wm$" in sql


@pytest.mark.parametrize("subir", [True, False])
def test_el_sql_no_deja_marcadores_de_parametro_sin_resolver(subir) -> None:
    sql = _sql(subir)

    assert "%(" not in sql
