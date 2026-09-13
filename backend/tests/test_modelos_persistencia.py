"""Pruebas de los modelos de persistencia, sin base de datos real.

Protegen contra la deriva entre el normalizador (lo que se produce) y la
tabla carga_fila (donde se guarda), y fijan las reglas de versionado que
impone la base (docs/versionado-sabanas.md).
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Integer, Numeric, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.adapters.persistence.modelos import Base, Carga, CargaFila, CargaIncidencia
from app.core.entities.carga import EstadoCarga
from app.core.entities.sabana import Severidad, TipoDocumento
from app.core.services.ingesta_sabana.normalizador import normalizar_fila
from tests.test_sabana_normalizador import MAPEO, _fila_sintetica

COLUMNAS_TECNICAS = {"carga_id", "numero_fila", "extras"}


def _valores_normalizados() -> dict:
    return normalizar_fila(_fila_sintetica(), MAPEO, numero_fila=2).valores


def test_carga_fila_tiene_exactamente_las_columnas_del_normalizador() -> None:
    columnas = set(CargaFila.__table__.columns.keys()) - COLUMNAS_TECNICAS

    assert columnas == set(_valores_normalizados())


def test_tipos_de_columna_compatibles_con_los_valores_normalizados() -> None:
    esperado = {bool: Boolean, int: Integer, Decimal: Numeric, date: Date, str: String}
    for nombre, valor in _valores_normalizados().items():
        if valor is None:
            continue
        tipo_python = next(t for t in (bool, int, Decimal, date, str) if isinstance(valor, t))
        tipo_columna = CargaFila.__table__.columns[nombre].type
        assert isinstance(tipo_columna, esperado[tipo_python]), (nombre, tipo_columna)


def test_una_sola_version_vigente_por_fecha() -> None:
    indice = next(i for i in Carga.__table__.indexes if i.name == "uq_carga_vigente_por_fecha")
    ddl = str(CreateIndex(indice).compile(dialect=postgresql.dialect()))

    assert indice.unique
    assert "WHERE vigente" in ddl


def test_restricciones_usan_los_valores_del_dominio() -> None:
    def ddl(tabla) -> str:
        return str(CreateTable(tabla.__table__).compile(dialect=postgresql.dialect()))

    carga, fila, incidencia = ddl(Carga), ddl(CargaFila), ddl(CargaIncidencia)
    assert all(f"'{e.value}'" in carga for e in EstadoCarga)
    assert f"NOT vigente OR estado = '{EstadoCarga.TERMINADA.value}'" in carga
    assert all(f"'{t.value}'" in fila for t in TipoDocumento)
    assert all(f"'{s.value}'" in incidencia for s in Severidad)


def test_filas_e_incidencias_se_eliminan_con_su_version() -> None:
    for tabla in ("carga_archivo", "carga_fila", "carga_incidencia"):
        (fk,) = Base.metadata.tables[tabla].foreign_keys
        assert fk.column.table.name == "carga"
        assert fk.ondelete == "CASCADE"


def test_auditoria_sobrevive_a_la_eliminacion_de_la_version() -> None:
    assert not Base.metadata.tables["carga_auditoria"].foreign_keys


def test_el_nombre_de_una_seleccion_es_unico_y_la_cantidad_positiva() -> None:
    ddl = str(CreateTable(Base.metadata.tables["seleccion"]).compile(dialect=postgresql.dialect()))

    assert "CONSTRAINT uq_seleccion_nombre_normalizado UNIQUE (nombre_normalizado)" in ddl
    assert "cantidad IS NULL OR cantidad >= 1" in ddl
