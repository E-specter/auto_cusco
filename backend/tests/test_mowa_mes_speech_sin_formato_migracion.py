"""La migracion que quita el formato de las versiones de speech, sin base (T-MM-C11, M-B4).

Fija el SQL de `e2c6b4a8d195` en los dos sentidos, con `alembic upgrade/downgrade --sql`: los
nombres de los CHECK (sin el prefijo duplicado de la convencion de nombres), el orden de las
sentencias y que el downgrade deje la tabla como la dejo `d7a3e5b9c241` (M-B3). Lo que solo se ve
con filas y con el catalogo de PostgreSQL esta en `test_mowa_mes_speech_sin_formato_postgres.py`.
"""

import io
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.adapters.persistence.modelos import MowaMesSpeechVersion
from tests.speech_congelado import cargar_migracion

BACKEND = Path(__file__).resolve().parents[1]
REVISION_ANTERIOR = "d7a3e5b9c241"
REVISION = "e2c6b4a8d195"
TABLA = "mowa_mes_speech_version"
CK_FORMATO = "ck_mowa_mes_speech_version_formato_valido"
CK_CONTENIDO = "ck_mowa_mes_speech_version_contenido_segun_formato"
SOLO_V2 = cargar_migracion("d7a3e5b9c241_speech_solo_v2.py")
MIGRACION = cargar_migracion("e2c6b4a8d195_speech_sin_formato.py")


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


def _orden(sql: str, *sentencias: str) -> list[int]:
    """La posicion de cada sentencia en el SQL; falla si falta alguna."""
    return [sql.index(sentencia) for sentencia in sentencias]


def test_la_migracion_cuelga_de_la_de_solo_v2_y_es_la_cabeza() -> None:
    directorio = ScriptDirectory.from_config(_configuracion())

    assert directorio.get_revision(REVISION).down_revision == REVISION_ANTERIOR
    assert directorio.get_heads() == [REVISION]


def test_los_nombres_y_textos_de_los_check_son_los_que_dejo_m_b3() -> None:
    assert MIGRACION.CK_CONTENIDO == CK_CONTENIDO == SOLO_V2.CHECK
    assert MIGRACION.CK_FORMATO == CK_FORMATO
    assert MIGRACION.CK_CONTENIDO_TEXTO == SOLO_V2.CHECK_NUEVO  # el texto con que M-B3 lo dejo


def test_el_upgrade_quita_los_check_antes_que_la_columna_y_nombra_los_check_sin_duplicar() -> None:
    sql = _sql(subir=True)

    quitar_contenido, quitar_formato, quitar_columna = _orden(
        sql,
        f"ALTER TABLE {TABLA} DROP CONSTRAINT {CK_CONTENIDO};",
        f"ALTER TABLE {TABLA} DROP CONSTRAINT {CK_FORMATO};",
        f"ALTER TABLE {TABLA} DROP COLUMN formato;",
    )
    assert quitar_contenido < quitar_formato < quitar_columna
    assert "ck_ck_" not in sql  # `op.f`: el nombre ya trae el prefijo de la convencion


def test_el_upgrade_renombra_partes_la_deja_nulable_y_pasa_a_null_solo_las_vacias() -> None:
    sql = _sql(subir=True)

    nulable, renombrar, a_null, quitar_formato, no_nula = _orden(
        sql,
        f"ALTER TABLE {TABLA} ALTER COLUMN partes DROP NOT NULL;",
        f"ALTER TABLE {TABLA} RENAME partes TO texto_v1;",
        f"UPDATE {TABLA} SET texto_v1 = NULL WHERE texto_v1 = '[]'::jsonb;",
        f"ALTER TABLE {TABLA} DROP COLUMN formato;",
        f"ALTER TABLE {TABLA} ALTER COLUMN expresiones SET NOT NULL;",
    )
    assert nulable < renombrar < a_null < quitar_formato < no_nula
    assert sql.count("UPDATE " + TABLA) == 1  # nada mas se reescribe: ni expresiones ni formato
    assert "DELETE" not in sql and "DROP TABLE" not in sql
    assert sql.count("DROP COLUMN") == 1  # solo `formato`: ningun dato de las versiones se pierde


def test_el_downgrade_devuelve_la_tabla_como_la_dejo_m_b3() -> None:
    sql = _sql(subir=False)

    (
        expresiones_nulable,
        agregar_formato,
        check_formato,
        check_contenido,
        a_vacia,
        no_nula,
        nombre,
    ) = _orden(
        sql,
        f"ALTER TABLE {TABLA} ALTER COLUMN expresiones DROP NOT NULL;",
        f"ALTER TABLE {TABLA} ADD COLUMN formato VARCHAR(2) DEFAULT 'v2' NOT NULL;",
        f"ALTER TABLE {TABLA} ADD CONSTRAINT {CK_FORMATO} CHECK (formato IN ('v1', 'v2'));",
        f"ALTER TABLE {TABLA} ADD CONSTRAINT {CK_CONTENIDO} "
        "CHECK (formato = 'v2' AND expresiones IS NOT NULL);",
        f"UPDATE {TABLA} SET texto_v1 = '[]'::jsonb WHERE texto_v1 IS NULL;",
        f"ALTER TABLE {TABLA} ALTER COLUMN texto_v1 SET NOT NULL;",
        f"ALTER TABLE {TABLA} RENAME texto_v1 TO partes;",
    )
    # `formato` entra antes que los CHECK que lo nombran; los NULL se rellenan antes de NOT NULL
    assert expresiones_nulable < agregar_formato < check_formato < check_contenido
    assert check_contenido < a_vacia < no_nula < nombre
    assert "ck_ck_" not in sql
    assert "DROP COLUMN" not in sql  # el downgrade no pierde ninguna columna


def test_el_modelo_declara_lo_mismo_que_la_migracion_deja() -> None:
    tabla = MowaMesSpeechVersion.__table__

    assert "formato" not in tabla.c and "partes" not in tabla.c
    assert tabla.c["texto_v1"].nullable and not tabla.c["expresiones"].nullable
    nombres_de_check = {c.name for c in tabla.constraints if hasattr(c, "sqltext")}
    assert not {CK_FORMATO, CK_CONTENIDO} & nombres_de_check
