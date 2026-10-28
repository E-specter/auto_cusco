"""La migracion de `mowa_mes_exclusion.campos` contra el modelo, sin base (T-MM-B12, D-CA-2)."""

import io
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateColumn

from app.adapters.persistence.modelos import MowaMesExclusion
from app.adapters.persistence.repositorio_campanas_mowa_mes_postgres import _filas_de_exclusiones
from app.core.entities.mowa_mes import CodigoMowaMes
from app.core.entities.mowa_mes_campana import Exclusion

DIALECTO = postgresql.dialect()
BACKEND = Path(__file__).resolve().parents[1]
REVISION_ANTERIOR = "c8f1a3d6e254"  # la de los campos adicionales (T-CA-B2)
REVISION = "e9b3d2a7c561"


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


def test_la_migracion_se_encadena_a_la_de_los_adicionales_y_es_la_cabeza() -> None:
    directorio = ScriptDirectory.from_config(_configuracion())

    assert directorio.get_revision(REVISION).down_revision == REVISION_ANTERIOR
    assert directorio.get_heads() == [REVISION]


def test_la_migracion_suma_la_columna_que_declara_el_modelo() -> None:
    columna = MowaMesExclusion.__table__.c["campos"]
    definicion = str(CreateColumn(columna).compile(dialect=DIALECTO)).strip()

    assert f"ALTER TABLE mowa_mes_exclusion ADD COLUMN {definicion};" in _sql(subir=True)
    assert definicion == "campos TEXT[]"
    assert columna.nullable  # las exclusiones que ya existen quedan en NULL, sin relleno


def test_la_migracion_no_toca_los_datos_existentes() -> None:
    sql = _sql(subir=True)

    assert "UPDATE" not in sql.replace("UPDATE alembic_version", "")
    assert "INSERT" not in sql.replace("INSERT INTO alembic", "")


def test_la_migracion_se_deshace_quitando_la_columna() -> None:
    sql = _sql(subir=False)

    assert "ALTER TABLE mowa_mes_exclusion DROP COLUMN campos;" in sql
    assert f"UPDATE alembic_version SET version_num='{REVISION_ANTERIOR}'" in sql


def test_el_repositorio_escribe_los_campos_como_lista_y_null_si_no_hay() -> None:
    # Sin base: lo que se inserta. Perder `campos` aqui dejaria las exclusiones sin sus nombres.
    exclusiones = [
        Exclusion("1", CodigoMowaMes.FALTA_CAMPO_ADICIONAL, campos=("ad_a", "ad_b")),
        Exclusion("2", CodigoMowaMes.TELEFONO_INVALIDO),
    ]

    filas = list(_filas_de_exclusiones(7, exclusiones))

    assert filas == [
        {
            "campana_id": 7,
            "pagare": "1",
            "orden": 1,
            "codigo": CodigoMowaMes.FALTA_CAMPO_ADICIONAL,
            "campos": ["ad_a", "ad_b"],
        },
        {
            "campana_id": 7,
            "pagare": "2",
            "orden": 2,
            "codigo": CodigoMowaMes.TELEFONO_INVALIDO,
            "campos": None,
        },
    ]
