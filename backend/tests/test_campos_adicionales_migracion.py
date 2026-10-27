"""La migracion de los campos adicionales contra los modelos, sin base (T-CA-B2)."""

import io
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateColumn, CreateTable

from app.adapters.persistence.modelos import CampoAdicional, CargaFila
from app.adapters.persistence.repositorio_mapeador_postgres import sentencia_de_adicionales

DIALECTO = postgresql.dialect()
BACKEND = Path(__file__).resolve().parents[1]
REVISION_ANTERIOR = "b6e1d9c4a728"
REVISION = "c8f1a3d6e254"


def _sql(subir: bool) -> str:
    configuracion = Config(str(BACKEND / "alembic.ini"))
    configuracion.set_main_option("script_location", str(BACKEND / "migrations"))
    configuracion.output_buffer = io.StringIO()
    if subir:
        command.upgrade(configuracion, f"{REVISION_ANTERIOR}:{REVISION}", sql=True)
    else:
        command.downgrade(configuracion, f"{REVISION}:{REVISION_ANTERIOR}", sql=True)
    return configuracion.output_buffer.getvalue()


def _lineas(texto: str) -> set[str]:
    return {linea.strip().rstrip(",") for linea in texto.splitlines() if linea.strip()}


def _cuerpo(texto: str) -> set[str]:
    return {x for x in _lineas(texto) if not x.startswith("CREATE TABLE") and x not in (")", ");")}


def test_la_migracion_crea_la_tabla_como_la_declara_el_modelo() -> None:
    sql = _sql(subir=True)
    tabla = CampoAdicional.__table__

    inicio = sql.index(f"CREATE TABLE {tabla.name} (")
    creada = _cuerpo(sql[inicio : sql.index(");", inicio) + 2])

    assert creada == _cuerpo(str(CreateTable(tabla).compile(dialect=DIALECTO)))


def test_la_migracion_suma_a_la_fila_la_columna_del_modelo() -> None:
    columna = CargaFila.__table__.c["adicionales"]
    definicion = str(CreateColumn(columna).compile(dialect=DIALECTO)).strip()

    assert f"ALTER TABLE carga_fila ADD COLUMN {definicion};" in _sql(subir=True)
    assert columna.nullable  # las versiones que ya existen quedan en NULL, sin relleno


def test_la_migracion_no_toca_los_datos_existentes() -> None:
    sql = _sql(subir=True)

    assert "UPDATE carga_fila" not in sql and "INSERT" not in sql.replace("INSERT INTO alembic", "")


def test_la_migracion_se_deshace_por_completo_y_en_orden_inverso() -> None:
    sql = _sql(subir=False)

    assert _lineas(sql) >= {
        "ALTER TABLE carga_fila DROP COLUMN adicionales;",
        "DROP TABLE campo_adicional;",
    }
    assert f"UPDATE alembic_version SET version_num='{REVISION_ANTERIOR}'" in sql


def test_el_modelo_declara_la_clave_el_tipo_y_la_unicidad_del_nombre_legible() -> None:
    tabla = CampoAdicional.__table__

    assert [c.name for c in tabla.primary_key.columns] == ["nombre"]
    assert {c.name for c in tabla.constraints if c.name} >= {
        "pk_campo_adicional",
        "ck_campo_adicional_tipo_valido",
        "uq_campo_adicional_catalogo_id_nombre_legible_normalizado",
    }
    assert "'texto', 'numero', 'fecha'" in str(
        [c.sqltext for c in tabla.constraints if c.name == "ck_campo_adicional_tipo_valido"][0]
    )


def test_las_definiciones_se_leen_por_catalogo_y_en_el_orden_en_que_se_crearon() -> None:
    sentencia = sentencia_de_adicionales("sabana_vencida")

    texto = str(sentencia.compile(dialect=DIALECTO, compile_kwargs={"literal_binds": True}))

    assert "WHERE campo_adicional.catalogo_id = 'sabana_vencida'" in texto
    assert texto.rstrip().endswith("ORDER BY campo_adicional.orden")
