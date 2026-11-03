"""La migracion de los informes de WhatsMKT, sin base: su SQL con `--sql` (T-WM-B6).

La ida y vuelta con filas, el reemplazo y el borrado en cascada se ven con la base en
`test_whatsmkt_informes_postgres.py`. El vigia de 63 caracteres sobre TODA la metadata `whatsmkt_*`
esta en `test_whatsmkt_migracion.py`.
"""

import io
import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[1]
REVISION_ANTERIOR = "e8a2c6f1b937"
REVISION = "a6c3e8d1f259"
TABLAS = ("whatsmkt_reporte", "whatsmkt_reporte_fila")


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


def test_la_migracion_cuelga_de_la_de_las_campanas_y_el_arbol_tiene_una_sola_cabeza() -> None:
    directorio = ScriptDirectory.from_config(_configuracion())

    assert directorio.get_revision(REVISION).down_revision == REVISION_ANTERIOR
    assert len(directorio.get_heads()) == 1


def test_el_upgrade_crea_las_dos_tablas_de_la_madre_a_la_hija() -> None:
    sql = _sql(subir=True)

    assert sql.index(f"CREATE TABLE {TABLAS[0]} (") < sql.index(f"CREATE TABLE {TABLAS[1]} (")
    assert "ck_ck_" not in sql  # `op.f`: el nombre ya trae el prefijo de la convencion
    assert "INSERT INTO" not in sql  # sin siembra


def test_un_solo_informe_vigente_por_campana() -> None:
    reporte = _tabla(_sql(subir=True), "whatsmkt_reporte")

    assert "CONSTRAINT uq_whatsmkt_reporte_campana_id UNIQUE (campana_id)" in reporte
    assert "campana_id BIGINT NOT NULL" in reporte
    assert "REFERENCES whatsmkt_campana (id) ON DELETE CASCADE" in reporte


def test_el_informe_guarda_lo_que_informa_y_la_huella_del_archivo() -> None:
    reporte = _tabla(_sql(subir=True), "whatsmkt_reporte")

    for columna in (
        "archivo_nombre TEXT NOT NULL",
        "huella VARCHAR(64) NOT NULL",
        "fecha_informada DATE,",
        "total_informado INTEGER,",
        "campana_informada TEXT,",
        "tipo_envio_informado TEXT,",
        "importado_en TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL",
    ):
        assert columna in reporte, columna
    assert "length(huella) = 64" in reporte


def test_las_filas_del_informe_conservan_el_orden_y_los_numeros_repetidos() -> None:
    fila = _tabla(_sql(subir=True), "whatsmkt_reporte_fila")

    assert "PRIMARY KEY (reporte_id, posicion)" in fila  # no es unica por numero
    assert "REFERENCES whatsmkt_reporte (id) ON DELETE CASCADE" in fila
    assert "numero ~ '^[0-9]+$'" in fila


def test_el_downgrade_quita_las_dos_tablas_de_la_hija_a_la_madre() -> None:
    sql = _sql(subir=False)

    assert sql.index(f"DROP TABLE {TABLAS[1]};") < sql.index(f"DROP TABLE {TABLAS[0]};")


def test_los_nombres_de_las_restricciones_de_la_migracion_miden_63_o_menos() -> None:
    fuente = next((BACKEND / "migrations" / "versions").glob(f"{REVISION}_*.py")).read_text("utf-8")

    nombres = re.findall(r'op\.f\(\s*"([^"]+)"', fuente)

    assert len(nombres) >= 8
    assert {n: len(n) for n in nombres if len(n) > 63} == {}
