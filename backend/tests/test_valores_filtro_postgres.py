r"""La lista de valores con PostgreSQL real (T-FV-B2, RF-67). Opcional.

Corre solo con AUTO_CUSCO_DB_TESTS=1 y la base de pruebas migrada (sufijo _test; conftest.py se
niega a correr contra otra). Ingesta por la via normal una sabana sintetica de 12 productos
(telefonos 900000xxx) en la fecha 2099-03-02 y borra todo al terminar. Comprueba la cascada, el
umbral sobre la fecha entera y el vacio contra el SQL real.

    PowerShell:  .\scripts\verificar.ps1 -ConBase

Equivalentes con dobles: `test_valores_filtro.py`; el SQL compilado: `test_valores_filtro_sql.py`.
"""

import io
import os
from datetime import date

import openpyxl
import pytest
from sqlalchemy import delete

from app.adapters.input.lector_tabla import LectorTabla
from app.adapters.persistence.db import get_engine
from app.adapters.persistence.modelos import Carga, CargaAuditoria
from app.adapters.persistence.repositorio_cargas_postgres import RepositorioCargasPostgres
from app.adapters.persistence.repositorio_cartera_postgres import RepositorioCarteraPostgres
from app.core.entities.cartera import ConsultaInvalida, Filtro, Operador, SinVersionVigente
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

FECHA = date(2099, 3, 2)
OTRA_FECHA = date(2099, 3, 3)  # sin version vigente
CARGA, AUDITORIA = Carga.__table__, CargaAuditoria.__table__
UMBRAL = 4

# region: CUSCO SUR x5, TACNA x3, PUNO SUR x2, y 2 productos SIN region (el «vacio»).
# agencia: dos agencias, para filtrar por encima.
# telefono: uno distinto por producto (12 > UMBRAL): no ofrece lista.
REGIONES = ["CUSCO SUR"] * 5 + ["TACNA"] * 3 + ["PUNO SUR"] * 2 + ["", ""]
AGENCIAS = [
    "AG 1",
    "AG 1",
    "AG 2",
    "AG 2",
    "AG 2",
    "AG 1",
    "AG 2",
    "AG 2",
    "AG 1",
    "AG 1",
    "AG 2",
    "AG 2",
]


def _sabana() -> bytes:
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "VENCIDA"
    hoja.append(CABECERAS_10_09)
    for i, (region, agencia) in enumerate(zip(REGIONES, AGENCIAS, strict=True), start=1):
        pagare = f"{i:018d}"
        hoja.append(
            _fila_sintetica(
                **{
                    "Pagare": pagare,
                    "PAGARE": pagare,
                    "Región": region,
                    "Agencia": agencia,
                    "Teléfono": float(900_000_000 + i),
                }
            )
        )
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def _limpiar(engine) -> None:
    with engine.begin() as cx:
        cx.execute(delete(CARGA).where(CARGA.c.fecha_corte.in_([FECHA, OTRA_FECHA])))
        cx.execute(delete(AUDITORIA).where(AUDITORIA.c.fecha_corte.in_([FECHA, OTRA_FECHA])))


@pytest.fixture
def servicio():
    engine = get_engine()
    _limpiar(engine)
    ingesta = IngestaSabanaService(RepositorioCargasPostgres(engine), LectorTabla())
    carga = ingesta.registrar_carga(FECHA, "sintetica_fv_b2.xlsx", _sabana()).carga
    assert ingesta.procesar_carga(carga.id).vigente
    try:
        yield ConsultaCarteraService(RepositorioCarteraPostgres(engine), umbral_valores=UMBRAL)
    finally:
        _limpiar(engine)


def lista(valores):
    return [(v.valor, v.cantidad) for v in valores.valores]


def test_la_lista_trae_las_cantidades_con_el_vacio_al_final(servicio) -> None:
    valores = servicio.valores(FECHA, "region")

    assert (valores.umbral, valores.ofrece_lista) == (UMBRAL, True)
    assert lista(valores) == [("CUSCO SUR", 5), ("TACNA", 3), ("PUNO SUR", 2), (None, 2)]


def test_el_vacio_es_null_y_no_una_cadena_vacia(servicio) -> None:
    valores = servicio.valores(FECHA, "region")

    assert [v.valor for v in valores.valores][-1] is None
    assert "" not in [v.valor for v in valores.valores]


def test_la_cascada_cuenta_solo_lo_que_cumple_los_filtros_de_arriba(servicio) -> None:
    arriba = [Filtro("agencia", Operador.EN, ("AG 1",))]

    valores = servicio.valores(FECHA, "region", arriba)

    # AG 1: productos 1, 2, 6, 9, 10, 11? -> regiones por orden de AGENCIAS/REGIONES.
    esperado: dict = {}
    for region, agencia in zip(REGIONES, AGENCIAS, strict=True):
        if agencia == "AG 1":
            esperado[region or None] = esperado.get(region or None, 0) + 1
    assert dict(lista(valores)) == esperado
    assert sum(c for _, c in lista(valores)) == AGENCIAS.count("AG 1")


def test_la_cascada_con_no_en_deja_los_vacios_salvo_que_se_marquen(servicio) -> None:
    sin_tacna = servicio.valores(FECHA, "region", [Filtro("region", Operador.NO_EN, ("TACNA",))])
    sin_tacna_ni_vacio = servicio.valores(
        FECHA, "region", [Filtro("region", Operador.NO_EN, ("TACNA", None))]
    )

    assert lista(sin_tacna) == [("CUSCO SUR", 5), ("PUNO SUR", 2), (None, 2)]
    assert lista(sin_tacna_ni_vacio) == [("CUSCO SUR", 5), ("PUNO SUR", 2)]


def test_un_campo_con_mas_valores_que_el_umbral_no_ofrece_lista(servicio) -> None:
    valores = servicio.valores(FECHA, "telefono")

    assert (valores.ofrece_lista, valores.valores) == (False, ())  # 12 telefonos > 4


def test_el_umbral_se_decide_sobre_la_fecha_entera_y_no_sobre_lo_filtrado(servicio) -> None:
    un_solo_producto = [Filtro("telefono", Operador.EN, ("900000001",))]

    valores = servicio.valores(FECHA, "telefono", un_solo_producto)

    assert valores.ofrece_lista is False and valores.valores == ()  # aunque lo filtrado sea 1


def test_los_campos_con_pocos_valores_distintos_ofrecen_lista(servicio) -> None:
    # region tiene 3 valores distintos no nulos y agencia 2, ambos <= 4.
    assert servicio.valores(FECHA, "region").ofrece_lista is True
    assert servicio.valores(FECHA, "agencia").ofrece_lista is True


def test_un_campo_que_no_es_de_texto_y_una_fecha_sin_version(servicio) -> None:
    with pytest.raises(ConsultaInvalida):
        servicio.valores(FECHA, "dias_atraso")
    with pytest.raises(SinVersionVigente):
        servicio.valores(OTRA_FECHA, "region")
