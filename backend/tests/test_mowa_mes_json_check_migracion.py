"""Los CHECK de tipo JSON de las columnas JSONB NOT NULL de MOWA MES, sin base (T-MM-B14).

`c4f8a2d6b173` agrega un `jsonb_typeof(col) = '<tipo>'` por columna (NOT NULL no basta: el JSON
`null` no es NULL de SQL). Esta prueba compara la migracion con el modelo para que nadie cambie un
lado sin el otro, y fija su SQL offline en los dos sentidos. La ida y vuelta contra una base la
corre `architec`.
"""

import io
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.adapters.persistence.modelos import Base
from tests.speech_congelado import cargar_migracion

BACKEND = Path(__file__).resolve().parents[1]
REVISION = "c4f8a2d6b173"
MIGRACION = cargar_migracion("c4f8a2d6b173_json_de_mowa_mes_con_su_tipo.py")
CHECKS = MIGRACION.CHECKS


def _configuracion() -> Config:
    configuracion = Config(str(BACKEND / "alembic.ini"))
    configuracion.set_main_option("script_location", str(BACKEND / "migrations"))
    return configuracion


def _sql(subir: bool) -> str:
    configuracion = _configuracion()
    configuracion.output_buffer = io.StringIO()
    anterior = MIGRACION.down_revision
    if subir:
        command.upgrade(configuracion, f"{anterior}:{REVISION}", sql=True)
    else:
        command.downgrade(configuracion, f"{REVISION}:{anterior}", sql=True)
    return configuracion.output_buffer.getvalue()


def test_la_migracion_cuelga_del_head_anterior_y_la_historia_sigue_lineal() -> None:
    directorio = ScriptDirectory.from_config(_configuracion())

    assert directorio.get_revision(REVISION).down_revision == MIGRACION.down_revision
    assert len(directorio.get_heads()) == 1  # una sola cabeza; las siguientes cuelgan de esta
    assert REVISION in {revision.revision for revision in directorio.walk_revisions()}


def test_cubre_las_cinco_columnas_con_nombres_de_63_caracteres_o_menos() -> None:
    assert sorted((t, c, tipo) for t, c, tipo, _ in CHECKS) == [
        ("mowa_mes_campana", "envios", "array"),
        ("mowa_mes_campana", "filtros", "array"),
        ("mowa_mes_campana", "herramientas", "object"),
        ("mowa_mes_campana", "supervisores", "array"),
        ("mowa_mes_fila_cargada", "advertencias", "array"),
    ]
    assert all(len(nombre) <= 63 for *_, nombre in CHECKS)
    assert all(nombre.startswith(f"ck_{tabla}_") for tabla, _, _, nombre in CHECKS)


@pytest.mark.parametrize(("tabla", "columna", "tipo", "nombre"), CHECKS)
def test_el_modelo_declara_el_mismo_check_que_la_migracion(tabla, columna, tipo, nombre) -> None:
    cheques = {
        c.name: str(c.sqltext)
        for c in Base.metadata.tables[tabla].constraints
        if hasattr(c, "sqltext")
    }

    assert cheques[nombre] == f"jsonb_typeof({columna}) = '{tipo}'"


def test_el_upgrade_crea_un_check_por_columna_sin_duplicar_el_prefijo() -> None:
    sql = _sql(subir=True)

    for tabla, columna, tipo, nombre in CHECKS:
        assert (
            f"ALTER TABLE {tabla} ADD CONSTRAINT {nombre} "
            f"CHECK (jsonb_typeof({columna}) = '{tipo}');"
        ) in sql
    assert "ck_ck_" not in sql
    assert sql.count("ADD CONSTRAINT") == len(CHECKS)
    assert "UPDATE mowa_mes" not in sql and "DELETE" not in sql  # no reescribe ningun dato


def test_el_downgrade_quita_cada_check_y_nada_mas() -> None:
    sql = _sql(subir=False)

    for tabla, _, _, nombre in CHECKS:
        assert f"ALTER TABLE {tabla} DROP CONSTRAINT {nombre};" in sql
    assert sql.count("DROP CONSTRAINT") == len(CHECKS)
    assert "DROP COLUMN" not in sql and "DROP TABLE" not in sql
