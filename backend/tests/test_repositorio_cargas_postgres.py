"""Integracion del caso de uso con PostgreSQL real (opcional).

Corre solo con AUTO_CUSCO_DB_TESTS=1 y la base de /.env migrada
(`uv run alembic upgrade head`). Usa una fecha de corte del ano 2099 y datos
sinteticos, y al terminar borra todo lo que creo, incluida la auditoria.

    PowerShell:  $env:AUTO_CUSCO_DB_TESTS = "1"; uv run pytest -m postgres
"""

import io
import os
from datetime import date
from decimal import Decimal

import openpyxl
import pytest
from sqlalchemy import delete, func, select

from app.adapters.input.lector_calamine import LectorCalamine
from app.adapters.persistence.db import get_engine
from app.adapters.persistence.modelos import Carga, CargaAuditoria, CargaFila, CargaIncidencia
from app.adapters.persistence.repositorio_cargas_postgres import RepositorioCargasPostgres
from app.core.entities.carga import EstadoCarga, EventoAuditoria
from app.core.services.ingesta_sabana.servicio import IngestaSabanaService
from tests.test_sabana_cabeceras import CABECERAS_10_09
from tests.test_sabana_normalizador import _fila_sintetica

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

FECHA = date(2099, 1, 15)
CARGA, FILA, INCIDENCIA, AUDITORIA = (
    Carga.__table__,
    CargaFila.__table__,
    CargaIncidencia.__table__,
    CargaAuditoria.__table__,
)


def _xlsx(filas: list[list]) -> bytes:
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "VENCIDA"
    for fila in filas:
        hoja.append(fila)
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def _limpiar(engine) -> None:
    with engine.begin() as cx:
        cx.execute(delete(CARGA).where(CARGA.c.fecha_corte == FECHA))
        cx.execute(delete(AUDITORIA).where(AUDITORIA.c.fecha_corte == FECHA))


@pytest.fixture
def entorno():
    engine = get_engine()
    _limpiar(engine)
    try:
        yield IngestaSabanaService(RepositorioCargasPostgres(engine), LectorCalamine()), engine
    finally:
        _limpiar(engine)


def test_flujo_completo_de_versiones_en_postgres(entorno) -> None:
    servicio, engine = entorno
    contenido = _xlsx(
        [
            CABECERAS_10_09,
            _fila_sintetica(Pagare="000000000000000001"),
            _fila_sintetica(Pagare="000000000000000002"),
            _fila_sintetica(Pagare="000000000000000002", **{"Monto Cuota": 999.0}),
        ]
    )

    v1 = servicio.registrar_carga(FECHA, "sintetica.xlsx", contenido).carga
    r1 = servicio.procesar_carga(v1.id)
    registro_v2 = servicio.registrar_carga(FECHA, "sintetica.xlsx", contenido)
    r2 = servicio.procesar_carga(registro_v2.carga.id)

    assert (r1.estado, r1.vigente) == (EstadoCarga.TERMINADA, True)
    assert (r1.resumen.filas_total, r1.resumen.filas_ingestadas) == (3, 2)
    assert registro_v2.versiones_identicas == [1]
    assert r2.requiere_confirmacion and r2.id_vigente_actual == v1.id

    with engine.connect() as cx:
        filas = cx.execute(
            select(FILA.c.pagare, FILA.c.numero_fila, FILA.c.monto_cuota, FILA.c.documento_numero)
            .where(FILA.c.carga_id == v1.id)
            .order_by(FILA.c.pagare)
        ).all()
        repetidas = cx.execute(
            select(func.count())
            .select_from(INCIDENCIA)
            .where(INCIDENCIA.c.carga_id == v1.id, INCIDENCIA.c.codigo == "pagare_repetido")
        ).scalar_one()
        carga = cx.execute(select(CARGA).where(CARGA.c.id == v1.id)).one()

    assert [(f.pagare, f.numero_fila) for f in filas] == [
        ("000000000000000001", 2),
        ("000000000000000002", 3),  # primera aparicion
    ]
    assert filas[1].monto_cuota == Decimal("210.35")
    assert filas[0].documento_numero == "01234567"
    assert repetidas == 1
    assert (carga.filas_ingestadas, carga.incidencias_error) == (2, 1)
    assert carga.huella_formato and carga.cabeceras_originales[6] == "Pagare"
    assert carga.procesado_en is not None

    servicio.asignar_vigente(registro_v2.carga.id)

    with engine.connect() as cx:
        vigentes = (
            cx.execute(select(CARGA.c.id).where(CARGA.c.fecha_corte == FECHA, CARGA.c.vigente))
            .scalars()
            .all()
        )
        eventos = cx.execute(
            select(AUDITORIA.c.carga_id, AUDITORIA.c.evento)
            .where(AUDITORIA.c.fecha_corte == FECHA)
            .order_by(AUDITORIA.c.id)
        ).all()

    assert vigentes == [registro_v2.carga.id]
    assert [(e.carga_id, e.evento) for e in eventos][-2:] == [
        (v1.id, EventoAuditoria.VIGENTE_RETIRADA.value),
        (registro_v2.carga.id, EventoAuditoria.VIGENTE_ASIGNADA.value),
    ]


def test_archivo_ilegible_queda_fallido_en_postgres(entorno) -> None:
    servicio, engine = entorno

    carga = servicio.registrar_carga(FECHA, "roto.xlsb", b"no es una hoja de calculo").carga
    resultado = servicio.procesar_carga(carga.id)

    with engine.connect() as cx:
        estado, motivo = cx.execute(
            select(CARGA.c.estado, CARGA.c.motivo_fallo).where(CARGA.c.id == carga.id)
        ).one()
    assert resultado.estado is EstadoCarga.FALLIDA
    assert estado == EstadoCarga.FALLIDA.value and motivo
