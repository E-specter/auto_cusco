"""La migracion de `mowa_mes_campana.descartada_en` contra el modelo, sin base (T-MM-C11, M-B1)."""

import io
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateColumn

from app.adapters.persistence.modelos import MowaMesCampana

DIALECTO = postgresql.dialect()
BACKEND = Path(__file__).resolve().parents[1]
REVISION_ANTERIOR = "e9b3d2a7c561"  # los campos de la exclusion (T-MM-B12)
REVISION = "b4e7a1c9d352"


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


def test_la_migracion_se_encadena_a_la_anterior() -> None:
    directorio = ScriptDirectory.from_config(_configuracion())

    assert directorio.get_revision(REVISION).down_revision == REVISION_ANTERIOR
    assert REVISION in directorio.get_heads()


def test_la_migracion_suma_la_columna_que_declara_el_modelo() -> None:
    columna = MowaMesCampana.__table__.c["descartada_en"]
    definicion = str(CreateColumn(columna).compile(dialect=DIALECTO)).strip()

    assert f"ALTER TABLE mowa_mes_campana ADD COLUMN {definicion};" in _sql(subir=True)
    assert definicion == "descartada_en TIMESTAMP WITH TIME ZONE"
    assert columna.nullable  # toda campana que ya existe queda activa, sin relleno


def test_la_migracion_no_toca_los_datos_existentes() -> None:
    sql = _sql(subir=True)

    assert "UPDATE" not in sql.replace("UPDATE alembic_version", "")
    assert "INSERT" not in sql.replace("INSERT INTO alembic", "")


def test_el_downgrade_quita_solo_la_columna() -> None:
    sql = _sql(subir=False)

    assert "ALTER TABLE mowa_mes_campana DROP COLUMN descartada_en;" in sql
    assert "DELETE" not in sql and "DROP TABLE" not in sql
