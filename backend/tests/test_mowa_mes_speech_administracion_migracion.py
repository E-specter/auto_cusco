"""La migracion de `mowa_mes_speech_version.deshabilitada_en` contra el modelo, sin base
(T-MM-C11, M-B2)."""

import io
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateColumn

from app.adapters.persistence.modelos import MowaMesSpeechVersion

DIALECTO = postgresql.dialect()
BACKEND = Path(__file__).resolve().parents[1]
REVISION_ANTERIOR = "b4e7a1c9d352"  # las campanas descartadas (M-B1)
REVISION = "c5d9f2a8e714"


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


def test_la_migracion_va_despues_de_la_de_las_campanas_descartadas() -> None:
    directorio = ScriptDirectory.from_config(_configuracion())

    assert directorio.get_revision(REVISION).down_revision == REVISION_ANTERIOR
    assert len(directorio.get_heads()) == 1
    assert REVISION in {revision.revision for revision in directorio.walk_revisions()}


def test_la_migracion_suma_la_columna_que_declara_el_modelo() -> None:
    columna = MowaMesSpeechVersion.__table__.c["deshabilitada_en"]
    definicion = str(CreateColumn(columna).compile(dialect=DIALECTO)).strip()

    assert f"ALTER TABLE mowa_mes_speech_version ADD COLUMN {definicion};" in _sql(subir=True)
    assert definicion == "deshabilitada_en TIMESTAMP WITH TIME ZONE"
    assert columna.nullable  # toda version que ya existe queda habilitada, sin relleno


def test_la_migracion_no_toca_los_datos_existentes() -> None:
    sql = _sql(subir=True)

    assert "UPDATE" not in sql.replace("UPDATE alembic_version", "")
    assert "INSERT" not in sql.replace("INSERT INTO alembic", "")


def test_el_downgrade_quita_solo_la_columna() -> None:
    sql = _sql(subir=False)

    assert "ALTER TABLE mowa_mes_speech_version DROP COLUMN deshabilitada_en;" in sql
    assert "DELETE" not in sql and "DROP TABLE" not in sql
