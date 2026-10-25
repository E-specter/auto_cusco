r"""La API del mapeador de encabezados con PostgreSQL real (T-MAP-B3b).

Corre solo con AUTO_CUSCO_DB_TESTS=1 y la base de pruebas migrada (sufijo _test; conftest.py se
niega a correr contra otra). Usa la fecha de corte 2099-08-02 y archivos sinteticos; los archivos
y los encabezados llevan el prefijo `b3b-` y al terminar se borra solo lo que ellos crearon. El
procesamiento en segundo plano se sustituye por un registro de las cargas que se encolaron: su
efecto sobre la cartera tiene sus propias pruebas.

    PowerShell:  .\scripts\verificar.ps1 -ConBase

Las equivalentes sin base (con el doble en memoria) estan en `test_api_mapeador.py`. Los errores del
servidor de base de datos no se comparan por su mensaje: aqui no hace falta ninguno.
"""

import os
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.adapters.input.lector_tabla import LectorTabla
from app.adapters.persistence.db import get_engine
from app.adapters.persistence.modelos import BorradorCargaArchivo, Carga
from app.adapters.persistence.repositorio_cargas_postgres import RepositorioCargasPostgres
from app.adapters.persistence.repositorio_mapeador_postgres import RepositorioMapeadorPostgres
from app.api import cargas as api_cargas
from app.api.cargas import obtener_servicio
from app.api.mapeador import obtener_servicio_mapeador
from app.core.entities.carga import EstadoCarga
from app.core.services.borradores_carga.servicio import VIGENCIA_DEL_BORRADOR, MapeadorService
from app.core.services.ingesta_sabana.mapeable import CATALOGO_SABANA_MAPEABLE
from app.core.services.ingesta_sabana.servicio import IngestaSabanaService
from app.main import app
from tests.mapeador_postgres_comun import sentencias_de_limpieza
from tests.test_mapeador_ciclo import SABANA, csv_de

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

FECHA = date(2099, 8, 2)  # la de B3a es la 2099-08-01
INICIO = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)
PREFIJO = "b3b-"  # los archivos y los encabezados de estas pruebas

BORRADOR = BorradorCargaArchivo.__table__
CARGA = Carga.__table__

CSV = csv_de(
    [
        [f"{PREFIJO}{h}" for h in ["Pagare", "Titular", "Teléfono", "Región", "Observación libre"]],
        ["000000000000000001", "APELLIDO/NOMBRE FICTICIO", "900000001", "REGIÓN PRUEBA", "nota"],
    ]
)
# Los encabezados llevan el prefijo, asi que ninguno coincide con un alias: la prueba dice el campo
# de cada columna, y el origen lo recalcula el backend al confirmar.
CAMPOS = ["pagare", "titular", "telefono", "region", None]


def _limpiar(engine) -> None:
    with engine.begin() as cx:
        for sentencia in sentencias_de_limpieza(FECHA, PREFIJO):
            cx.execute(sentencia)


@pytest.fixture
def engine():
    motor = get_engine()
    _limpiar(motor)
    try:
        yield motor
    finally:
        _limpiar(motor)


class Entorno:
    def __init__(self, engine, monkeypatch) -> None:
        self.engine = engine
        self.ahora = INICIO
        self.encoladas: list[int] = []
        self.mapeador = MapeadorService(
            RepositorioMapeadorPostgres(engine),
            LectorTabla(),
            [CATALOGO_SABANA_MAPEABLE],
            lambda: self.ahora,
        )
        self.ingesta = IngestaSabanaService(
            RepositorioCargasPostgres(engine), LectorTabla(), lambda: self.ahora
        )
        monkeypatch.setattr(
            api_cargas,
            "_procesar_en_segundo_plano",
            lambda _s, carga_id: self.encoladas.append(carga_id),
        )
        self.cliente = TestClient(app)

    def subir(self, *, contenido: bytes = CSV, nombre: str = "datos.csv"):
        return self.cliente.post(
            f"/mapeador/{SABANA}/borradores", files={"archivo": (f"{PREFIJO}{nombre}", contenido)}
        )

    def asignaciones(self, analisis: dict) -> list[dict]:
        return [
            {"indice": c["indice"], "campo": CAMPOS[c["indice"]], "origen": "manual"}
            for c in analisis["columnas"]
        ]

    def confirmar(self, borrador_id: int, asignaciones: list[dict]):
        return self.cliente.post(
            "/cargas/desde-borrador",
            json={
                "borrador_id": borrador_id,
                "fecha_corte": FECHA.isoformat(),
                "asignaciones": asignaciones,
            },
        )

    def cuantos(self, tabla, *condiciones) -> int:
        with self.engine.connect() as cx:
            return cx.execute(
                select(func.count()).select_from(tabla).where(*condiciones)
            ).scalar_one()


@pytest.fixture
def api(engine, monkeypatch):
    entorno = Entorno(engine, monkeypatch)
    app.dependency_overrides[obtener_servicio_mapeador] = lambda: entorno.mapeador
    app.dependency_overrides[obtener_servicio] = lambda: entorno.ingesta
    try:
        yield entorno
    finally:
        app.dependency_overrides.clear()


def test_el_catalogo_y_el_analisis_salen_de_la_base_real(api) -> None:
    catalogo = api.cliente.get(f"/mapeador/catalogos/{SABANA}")
    subida = api.subir()

    analisis = subida.json()
    assert catalogo.status_code == 200 and subida.status_code == 201
    assert [c["indice"] for c in analisis["columnas"]] == [0, 1, 2, 3, 4]
    assert analisis["columnas"][0]["encabezado"] == f"{PREFIJO}Pagare"
    assert {c["estado"] for c in analisis["columnas"]} <= {"parecido", "sin_coincidencia"}
    assert api.cuantos(BORRADOR, BORRADOR.c.id == analisis["borrador_id"]) == 1


def test_el_ciclo_completo_por_http_y_el_siguiente_archivo_llega_recordado(api) -> None:
    primero = api.subir().json()
    asignaciones = api.asignaciones(primero)

    validacion = api.cliente.post(
        f"/mapeador/borradores/{primero['borrador_id']}/validacion",
        json={"asignaciones": asignaciones},
    )
    confirmada = api.confirmar(primero["borrador_id"], asignaciones)
    segundo = api.subir(nombre="otro.csv").json()

    assert validacion.status_code == 200 and validacion.json()["problemas"] == []
    assert confirmada.status_code == 202
    assert api.encoladas == [confirmada.json()["id"]]
    assert (
        api.cuantos(CARGA, CARGA.c.id == confirmada.json()["id"], CARGA.c.fecha_corte == FECHA) == 1
    )
    assert api.cuantos(BORRADOR, BORRADOR.c.id == primero["borrador_id"]) == 0
    assert (
        segundo["columnas"][0]["encabezado"] == f"{PREFIJO}Pagare"
    )  # el mismo archivo, otro nombre
    assert {c["estado"] for c in segundo["columnas"]} == {"recordado"}
    assert [c["sugerido"] for c in segundo["columnas"]] == CAMPOS


def test_la_carga_confirmada_queda_en_cola_con_su_mapeo(api) -> None:
    analisis = api.subir().json()

    respuesta = api.confirmar(analisis["borrador_id"], api.asignaciones(analisis))

    with api.engine.connect() as cx:
        carga = cx.execute(select(CARGA).where(CARGA.c.id == respuesta.json()["id"])).one()
    assert carga.estado == EstadoCarga.EN_COLA.value
    assert [(a["indice"], a["campo"]) for a in carga.asignaciones][0] == (0, "pagare")


def test_un_borrador_vencido_es_404_en_todas_las_rutas(api) -> None:
    analisis = api.subir().json()
    borrador = analisis["borrador_id"]
    api.ahora = INICIO + VIGENCIA_DEL_BORRADOR + timedelta(seconds=1)

    reanalisis = api.cliente.post(f"/mapeador/borradores/{borrador}/analisis", json={})
    validacion = api.cliente.post(
        f"/mapeador/borradores/{borrador}/validacion",
        json={"asignaciones": api.asignaciones(analisis)},
    )
    confirmacion = api.confirmar(borrador, api.asignaciones(analisis))

    assert [reanalisis.status_code, validacion.status_code, confirmacion.status_code] == [404] * 3
    assert {r.json()["codigo"] for r in (reanalisis, validacion, confirmacion)} == {
        "borrador_no_encontrado"
    }
    assert api.cuantos(CARGA, CARGA.c.fecha_corte == FECHA) == 0


def test_la_segunda_confirmacion_del_mismo_borrador_es_404(api) -> None:
    analisis = api.subir().json()
    asignaciones = api.asignaciones(analisis)
    api.confirmar(analisis["borrador_id"], asignaciones)

    segunda = api.confirmar(analisis["borrador_id"], asignaciones)

    assert segunda.status_code == 404 and segunda.json()["codigo"] == "borrador_no_encontrado"
    assert api.cuantos(CARGA, CARGA.c.fecha_corte == FECHA) == 1


def test_confirmar_con_problemas_es_422_con_la_lista_y_no_crea_nada(api) -> None:
    analisis = api.subir().json()
    asignaciones = api.asignaciones(analisis)
    asignaciones[0] = {"indice": 0, "campo": None, "origen": "manual"}  # sin el campo obligatorio

    respuesta = api.confirmar(analisis["borrador_id"], asignaciones)

    assert respuesta.status_code == 422 and respuesta.json()["codigo"] == "mapeo_con_problemas"
    assert [p["codigo"] for p in respuesta.json()["problemas"]] == ["obligatorio_sin_columna"]
    assert api.cuantos(CARGA, CARGA.c.fecha_corte == FECHA) == 0
    assert api.cuantos(BORRADOR, BORRADOR.c.id == analisis["borrador_id"]) == 1
    assert api.encoladas == []


def test_descartar_un_borrador_lo_borra_de_la_base(api) -> None:
    analisis = api.subir().json()

    borrado = api.cliente.delete(f"/mapeador/borradores/{analisis['borrador_id']}")
    otra_vez = api.cliente.delete(f"/mapeador/borradores/{analisis['borrador_id']}")

    assert borrado.status_code == 204 and otra_vez.status_code == 404
    assert api.cuantos(BORRADOR, BORRADOR.c.id == analisis["borrador_id"]) == 0
