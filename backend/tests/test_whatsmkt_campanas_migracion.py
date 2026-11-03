"""La migracion de las campanas de WhatsMKT, sin base (T-WM-B4b1, parte 2): su SQL con `--sql`.

La ida y vuelta con filas, los CHECK y las FK se ven con la base en
`test_whatsmkt_campanas_postgres.py`.
El vigia de 63 caracteres sobre TODA la metadata `whatsmkt_*` esta en `test_whatsmkt_migracion.py`.
"""

import io
import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[1]
REVISION_ANTERIOR = "d3f7a1b9c524"
REVISION = "e8a2c6f1b937"
TABLAS = (
    "whatsmkt_lote",
    "whatsmkt_campana",
    "whatsmkt_archivo",
    "whatsmkt_fila_cargada",
    "whatsmkt_exclusion",
)


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


def _tabla(sql: str, nombre: str) -> str:
    """El CREATE TABLE de una tabla, hasta el siguiente CREATE."""
    inicio = sql.index(f"CREATE TABLE {nombre} (")
    fin = sql.find("CREATE ", inicio + 1)
    return sql[inicio : len(sql) if fin == -1 else fin]


def test_la_migracion_cuelga_de_la_del_mensaje_y_el_arbol_tiene_una_sola_cabeza() -> None:
    directorio = ScriptDirectory.from_config(_configuracion())

    assert directorio.get_revision(REVISION).down_revision == REVISION_ANTERIOR
    assert len(directorio.get_heads()) == 1


def test_el_upgrade_crea_las_cinco_tablas_de_las_madres_a_las_hijas() -> None:
    sql = _sql(subir=True)

    posiciones = [sql.index(f"CREATE TABLE {tabla} (") for tabla in TABLAS]
    assert posiciones == sorted(posiciones)
    assert "ck_ck_" not in sql  # `op.f`: el nombre ya trae el prefijo de la convencion
    assert "INSERT INTO" not in sql  # sin siembra


def test_las_claves_foraneas_borran_en_cascada_las_hijas_y_sueltan_las_referencias_sueltas() -> (
    None
):
    sql = _sql(subir=True)

    for tabla in ("whatsmkt_archivo", "whatsmkt_fila_cargada"):
        assert re.search(
            rf"CREATE TABLE {tabla} \(.*?REFERENCES whatsmkt_campana \(id\) ON DELETE CASCADE",
            sql,
            re.S,
        )
    # La definicion y el texto pueden borrarse: la campana conserva su nombre, version y copia.
    assert "REFERENCES definicion_carga (id) ON DELETE SET NULL" in sql
    assert "REFERENCES texto_guardado (id) ON DELETE SET NULL" in sql
    # La foto y el adjunto son de la biblioteca, que archiva y no borra.
    assert sql.count("REFERENCES whatsmkt_adjunto (id)") == 2
    assert "REFERENCES whatsmkt_adjunto (id) ON DELETE" not in sql


def test_la_exclusion_cuelga_del_lote_y_su_campana_es_nula() -> None:
    sql = _sql(subir=True)
    tabla = _tabla(sql, "whatsmkt_exclusion")

    assert "lote_id BIGINT NOT NULL" in tabla
    assert "campana_id BIGINT," in tabla  # nula: las que quedan fuera de todas las campanas
    assert "REFERENCES whatsmkt_lote (id) ON DELETE CASCADE" in tabla


def test_la_campana_congela_lo_que_uso_y_el_lote_es_obligatorio() -> None:
    sql = _sql(subir=True)
    campana = _tabla(sql, "whatsmkt_campana")

    for columna in (
        "lote_id BIGINT NOT NULL",
        "definicion_version INTEGER NOT NULL",
        "texto_version INTEGER NOT NULL",
        "mensaje_texto TEXT NOT NULL",
        "fecha_envio DATE NOT NULL",
        "horarios JSONB NOT NULL",
        "supervisores JSONB NOT NULL",
        "descartada_en TIMESTAMP WITH TIME ZONE,",
    ):
        assert columna in campana, columna


def test_los_jsonb_exigen_su_forma() -> None:
    sql = _sql(subir=True)

    for restriccion in (
        "ck_whatsmkt_fila_cargada_macros_es_una_lista",
        "ck_whatsmkt_campana_horarios_con_al_menos_uno",
        "ck_whatsmkt_campana_supervisores_es_una_lista",
        "ck_whatsmkt_campana_filtros_es_una_lista",
    ):
        assert restriccion in sql
    assert "jsonb_typeof(macros) = 'array'" in sql


def test_el_downgrade_quita_las_cinco_tablas_de_las_hijas_a_las_madres() -> None:
    sql = _sql(subir=False)

    posiciones = [sql.index(f"DROP TABLE {tabla};") for tabla in reversed(TABLAS)]
    assert posiciones == sorted(posiciones)


def test_los_nombres_de_las_restricciones_de_la_migracion_miden_63_o_menos() -> None:
    fuente = next((BACKEND / "migrations" / "versions").glob(f"{REVISION}_*.py")).read_text("utf-8")

    nombres = re.findall(r'op\.f\(\s*"([^"]+)"', fuente)

    assert len(nombres) > 25
    assert {n: len(n) for n in nombres if len(n) > 63} == {}
