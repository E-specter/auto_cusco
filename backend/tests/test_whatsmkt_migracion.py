"""La migracion de WhatsMKT (T-WM-B1), sin base: su SQL en los dos sentidos, con `--sql`.

Lo que solo se ve con la base (ida y vuelta, siembra, restricciones) esta en
`test_whatsmkt_postgres.py`.
"""

import io
import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.adapters.persistence.modelos import Base
from app.adapters.persistence.repositorio_whatsmkt_postgres import _FK_DEFINICION

BACKEND = Path(__file__).resolve().parents[1]
REVISION_ANTERIOR = "e2c6b4a8d195"
REVISION = "b7e4c1a9d826"


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


def test_la_migracion_cuelga_de_la_anterior_y_el_arbol_tiene_una_sola_cabeza() -> None:
    directorio = ScriptDirectory.from_config(_configuracion())

    assert directorio.get_revision(REVISION).down_revision == REVISION_ANTERIOR
    assert len(directorio.get_heads()) == 1


def test_el_upgrade_crea_las_tres_tablas_y_siembra_la_configuracion_y_los_segmentos() -> None:
    sql = _sql(subir=True)

    for tabla in ("whatsmkt_configuracion", "whatsmkt_segmento", "whatsmkt_adjunto"):
        assert f"CREATE TABLE {tabla} (" in sql
    assert "INSERT INTO whatsmkt_configuracion" in sql
    assert sql.count("INSERT INTO whatsmkt_segmento") == 3
    assert "ck_ck_" not in sql  # `op.f`: el nombre ya trae el prefijo de la convencion
    assert "uq_whatsmkt_adjunto_huella" in sql
    assert "uq_whatsmkt_segmento_orden" not in sql  # `orden` se actualiza fila a fila: no es unico


def test_el_downgrade_quita_las_tres_tablas() -> None:
    sql = _sql(subir=False)

    orden = [
        sql.index(f"DROP TABLE {tabla};")
        for tabla in ("whatsmkt_adjunto", "whatsmkt_segmento", "whatsmkt_configuracion")
    ]
    assert orden == sorted(orden)


# PostgreSQL admite 63 caracteres por identificador. Un nombre mas largo lo trunca con un hash y
# `diag.constraint_name` deja de coincidir con el que el codigo espera; `alembic check` no lo ve
# porque el modelo y la migracion se acortan igual.
MAXIMO_IDENTIFICADOR = 63


def test_ningun_nombre_de_restriccion_de_la_migracion_pasa_de_63_caracteres() -> None:
    fuente = next((BACKEND / "migrations" / "versions").glob(f"{REVISION}_*.py")).read_text("utf-8")

    nombres = re.findall(r'op\.f\(\s*"([^"]+)"', fuente)

    assert len(nombres) > 10  # la expresion encuentra los nombres
    largos = {n: len(n) for n in nombres if len(n) > MAXIMO_IDENTIFICADOR}
    assert largos == {}


def test_ningun_nombre_de_restriccion_de_los_modelos_pasa_de_63_caracteres() -> None:
    # Un dialecto sin tope, para ver el nombre completo que arma la convencion antes de que
    # SQLAlchemy lo acorte con un hash.
    dialecto = postgresql.dialect()
    dialecto.max_identifier_length = 1000
    ddl = []
    for tabla in Base.metadata.sorted_tables:
        if tabla.name.startswith("whatsmkt_"):
            ddl.append(str(CreateTable(tabla).compile(dialect=dialecto)))
            ddl += [str(CreateIndex(i).compile(dialect=dialecto)) for i in tabla.indexes]

    nombres = re.findall(r"CONSTRAINT (\w+)|INDEX (\w+)", " ".join(ddl))
    nombres = [a or b for a, b in nombres]

    assert len(nombres) > 10
    largos = {n: len(n) for n in nombres if len(n) > MAXIMO_IDENTIFICADOR}
    assert largos == {}


def test_la_fk_de_la_definicion_se_llama_igual_en_el_repositorio_el_modelo_y_la_migracion() -> None:
    # El repositorio reconoce la FK por `diag.constraint_name`: si el nombre de la base difiere del
    # que busca, la IntegrityError sube cruda en vez de DefinicionDefectoNoExiste.
    fuente = next((BACKEND / "migrations" / "versions").glob(f"{REVISION}_*.py")).read_text("utf-8")
    [fk] = Base.metadata.tables["whatsmkt_configuracion"].foreign_keys

    assert fk.constraint.name == _FK_DEFINICION
    assert f'op.f("{_FK_DEFINICION}")' in fuente
