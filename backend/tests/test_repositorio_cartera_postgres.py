"""Integracion de la consulta de cartera con PostgreSQL real (opcional).

Corre solo con AUTO_CUSCO_DB_TESTS=1 y la base migrada. Ingesta una sabana
sintetica de tres productos por la via normal, consulta sobre ella y borra todo
al terminar. Fecha del ano 2099 para no cruzarse con datos de trabajo.
"""

import io
import os
from datetime import date
from decimal import Decimal

import openpyxl
import pytest
from sqlalchemy import delete, select

from app.adapters.input.lector_calamine import LectorCalamine
from app.adapters.persistence.db import get_engine
from app.adapters.persistence.modelos import Carga, CargaAuditoria
from app.adapters.persistence.repositorio_cargas_postgres import RepositorioCargasPostgres
from app.adapters.persistence.repositorio_cartera_postgres import RepositorioCarteraPostgres
from app.core.entities.cartera import Filtro, Funcion, Indicador, Operador, Orden, SinVersionVigente
from app.core.services.ingesta_sabana.servicio import IngestaSabanaService
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService
from tests.test_sabana_cabeceras import CABECERAS_10_09
from tests.test_sabana_normalizador import _fila_sintetica

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

FECHA = date(2099, 3, 1)
CARGA, AUDITORIA = Carga.__table__, CargaAuditoria.__table__

PRODUCTOS = [
    {
        "Pagare": "000000000000000001",
        "PAGARE": "000000000000000001",
        "Región": "CUSCO SUR",
        "SEGMENTO FINACIERO": "1. Preventiva",
        "Saldo Capital Pendiente": 1000.00,
        "Monto Cuota": 100.00,
        "Dias Atraso Hoy": -5.0,
        "DÍAS SICMAC-C": -5.0,
    },
    {
        "Pagare": "000000000000000002",
        "PAGARE": "000000000000000002",
        "Región": "TACNA",
        "SEGMENTO FINACIERO": "2. 1 a 8",
        "Saldo Capital Pendiente": 2000.50,
        "Monto Cuota": 250.25,
        "Dias Atraso Hoy": 10.0,
        "DÍAS SICMAC-C": 10.0,
    },
    {
        "Pagare": "000000000000000003",
        "PAGARE": "000000000000000003",
        "Región": "CUSCO SUR",
        "SEGMENTO FINACIERO": "1. Preventiva",
        "Saldo Capital Pendiente": 500.25,
        "Monto Cuota": 50.00,
        "Dias Atraso Hoy": 3.0,
        "DÍAS SICMAC-C": 3.0,
    },
]


def _sabana() -> bytes:
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "VENCIDA"
    hoja.append(CABECERAS_10_09)
    for cambios in PRODUCTOS:
        hoja.append(_fila_sintetica(**cambios))
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def _limpiar(engine) -> None:
    with engine.begin() as cx:
        cx.execute(delete(CARGA).where(CARGA.c.fecha_corte == FECHA))
        cx.execute(delete(AUDITORIA).where(AUDITORIA.c.fecha_corte == FECHA))


@pytest.fixture
def cartera():
    engine = get_engine()
    _limpiar(engine)
    ingesta = IngestaSabanaService(RepositorioCargasPostgres(engine), LectorCalamine())
    carga = ingesta.registrar_carga(FECHA, "sintetica.xlsx", _sabana()).carga
    resultado = ingesta.procesar_carga(carga.id)
    assert resultado.vigente, "la primera version de la fecha debe quedar vigente"
    try:
        yield ConsultaCarteraService(RepositorioCarteraPostgres(engine)), engine
    finally:
        _limpiar(engine)


def test_consultar_la_cartera_del_dia_con_filtro_y_orden(cartera) -> None:
    servicio, _ = cartera

    pagina = servicio.consultar(
        FECHA,
        [Filtro("region", Operador.IGUAL, ("CUSCO SUR",))],
        Orden("saldo_capital_pendiente", descendente=True),
        limite=10,
    )

    assert pagina.total == 2
    assert [f["pagare"] for f in pagina.filas] == [
        "000000000000000001",
        "000000000000000003",
    ]
    assert pagina.filas[0]["saldo_capital_pendiente"] == Decimal("1000.00")
    assert not pagina.suficiente  # se pidieron 10 y solo hay 2 (RF-08)


def test_filtros_por_rango_y_texto(cartera) -> None:
    servicio, _ = cartera

    vencidos = servicio.consultar(FECHA, [Filtro("dias_atraso", Operador.MAYOR, (Decimal(0),))])
    rango = servicio.consultar(
        FECHA, [Filtro("dias_atraso", Operador.ENTRE, (Decimal(-6), Decimal(4)))]
    )
    contiene = servicio.consultar(FECHA, [Filtro("region", Operador.CONTIENE, ("cusco",))])
    sin_telefono = servicio.consultar(FECHA, [Filtro("telefono", Operador.VACIO)])

    assert vencidos.total == 2
    assert rango.total == 2
    assert contiene.total == 2  # la busqueda no distingue mayusculas
    assert sin_telefono.total == 0


def test_metricas_de_la_seleccion(cartera) -> None:
    servicio, _ = cartera

    metricas = servicio.metricas(
        FECHA, indicadores=[Indicador("atraso promedio", Funcion.PROMEDIO, "dias_atraso")]
    )

    assert metricas.cuentas == 3
    assert metricas.capital_total == Decimal("3500.75")
    assert (metricas.cuota_minima, metricas.cuota_maxima) == (Decimal("50.00"), Decimal("250.25"))
    assert metricas.cuentas_por_segmento == {"1. Preventiva": 2, "2. 1 a 8": 1}
    assert round(Decimal(metricas.adicionales["atraso promedio"]), 2) == Decimal("2.67")


def test_metricas_sobre_una_seleccion_filtrada(cartera) -> None:
    servicio, _ = cartera

    metricas = servicio.metricas(FECHA, [Filtro("region", Operador.IGUAL, ("TACNA",))])

    assert metricas.cuentas == 1
    assert metricas.capital_total == Decimal("2000.50")


def test_segmentar_por_region(cartera) -> None:
    servicio, _ = cartera

    segmentacion = servicio.segmentar(FECHA, "region")

    assert [(g.valor, g.cuentas, g.capital) for g in segmentacion.grupos] == [
        ("CUSCO SUR", 2, Decimal("1500.25")),
        ("TACNA", 1, Decimal("2000.50")),
    ]


def test_una_fecha_sin_sabana_no_tiene_cartera(cartera) -> None:
    servicio, _ = cartera

    with pytest.raises(SinVersionVigente):
        servicio.consultar(date(2099, 3, 2))


def test_la_cartera_sigue_a_la_version_vigente(cartera) -> None:
    servicio, engine = cartera
    ingesta = IngestaSabanaService(RepositorioCargasPostgres(engine), LectorCalamine())
    solo_uno = [PRODUCTOS[0]]
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "VENCIDA"
    hoja.append(CABECERAS_10_09)
    for cambios in solo_uno:
        hoja.append(_fila_sintetica(**cambios))
    buffer = io.BytesIO()
    libro.save(buffer)

    correccion = ingesta.registrar_carga(FECHA, "correccion.xlsx", buffer.getvalue()).carga
    ingesta.procesar_carga(correccion.id)
    antes = servicio.consultar(FECHA).total
    ingesta.asignar_vigente(correccion.id)
    despues = servicio.consultar(FECHA).total

    assert (antes, despues) == (3, 1)
    with engine.connect() as cx:
        vigentes = (
            cx.execute(select(CARGA.c.id).where(CARGA.c.fecha_corte == FECHA, CARGA.c.vigente))
            .scalars()
            .all()
        )
    assert vigentes == [correccion.id]


def test_resumen_de_los_primeros_n_segun_el_orden(cartera) -> None:
    servicio, _ = cartera

    resumen = servicio.resumen(
        FECHA,
        orden=Orden("saldo_capital_pendiente", descendente=True),
        cantidad=2,
        indicadores=[Indicador("cuota mayor", Funcion.MAXIMO, "monto_cuota")],
        segmento="region",
    )

    seleccion = resumen.seleccion
    assert (resumen.disponibles, resumen.solicitados, resumen.suficiente) == (3, 2, True)
    assert resumen.universo.metricas.capital_total == Decimal("3500.75")
    # Los dos de mayor saldo: 2000.50 (TACNA) y 1000.00 (CUSCO SUR).
    assert seleccion.metricas.cuentas == 2
    assert seleccion.metricas.capital_total == Decimal("3000.50")
    assert (seleccion.metricas.cuota_minima, seleccion.metricas.cuota_maxima) == (
        Decimal("100.00"),
        Decimal("250.25"),
    )
    assert seleccion.metricas.cuentas_por_segmento == {"1. Preventiva": 1, "2. 1 a 8": 1}
    assert seleccion.metricas.adicionales["cuota mayor"] == Decimal("250.25")
    assert sorted((g.valor, g.cuentas) for g in seleccion.segmentacion.grupos) == [
        ("CUSCO SUR", 1),
        ("TACNA", 1),
    ]


def test_las_metricas_de_la_seleccion_describen_los_productos_de_la_lista(cartera) -> None:
    servicio, _ = cartera
    # Orden con empates: dos productos comparten region. El desempate por pagare
    # tiene que ser el mismo en la lista y en las metricas.
    orden = Orden("region")

    pagina = servicio.consultar(FECHA, orden=orden, limite=2)
    resumen = servicio.resumen(FECHA, orden=orden, cantidad=2)

    assert [fila["pagare"] for fila in pagina.filas] == [
        "000000000000000001",
        "000000000000000003",
    ]
    assert resumen.seleccion.metricas.capital_total == sum(
        fila["saldo_capital_pendiente"] for fila in pagina.filas
    )


def test_pedir_mas_de_los_que_hay_resume_lo_disponible(cartera) -> None:
    servicio, _ = cartera

    resumen = servicio.resumen(FECHA, [Filtro("region", Operador.IGUAL, ("TACNA",))], cantidad=10)

    assert (resumen.disponibles, resumen.suficiente) == (1, False)
    assert resumen.seleccion.metricas.capital_total == Decimal("2000.50")
