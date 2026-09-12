"""Pruebas de los endpoints de cartera, con un doble de prueba del caso de uso.

Verifican sobre todo la lectura de los filtros, el orden y los indicadores que
llegan como texto en la URL, que es donde se puede colar una consulta invalida.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.cartera import obtener_servicio_cartera
from app.core.entities.cartera import (
    ConsultaInvalida,
    Funcion,
    Grupo,
    MetricasCartera,
    Operador,
    PaginaCartera,
    Segmentacion,
    SinVersionVigente,
)
from app.main import app

FECHA = date(2026, 9, 10)


class ServicioFalso:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.recibido: dict = {}

    def _quizas_fallar(self) -> None:
        if self.error is not None:
            raise self.error

    def campos_disponibles(self) -> dict:
        return {"region": {"tipo": "texto", "operadores": ["igual", "contiene"]}}

    def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento):
        self._quizas_fallar()
        self.recibido = {
            "fecha_corte": fecha_corte,
            "filtros": list(filtros),
            "orden": orden,
            "limite": limite,
            "desplazamiento": desplazamiento,
        }
        fila = {
            "pagare": "000000000000000001",
            "saldo_capital_pendiente": Decimal("1500.50"),
            "fecha_vencimiento_cuota": date(2026, 9, 18),
            "telefono": None,
        }
        return PaginaCartera(total=7, filas=(fila,), limite=limite, desplazamiento=desplazamiento)

    def metricas(self, fecha_corte, filtros, indicadores):
        self._quizas_fallar()
        self.recibido = {"filtros": list(filtros), "indicadores": list(indicadores)}
        return MetricasCartera(
            cuentas=7,
            capital_total=Decimal("10500.75"),
            cuota_minima=Decimal("50.00"),
            cuota_maxima=Decimal("900.00"),
            cuentas_por_segmento={"1. Preventiva": 5, "(sin segmento)": 2},
            adicionales={indicador.nombre: Decimal("2.5") for indicador in indicadores},
        )

    def segmentar(self, fecha_corte, campo, filtros):
        self._quizas_fallar()
        self.recibido = {"campo": campo, "filtros": list(filtros)}
        return Segmentacion(
            campo=campo, grupos=(Grupo(valor="CUSCO SUR", cuentas=4, capital=Decimal("8000.00")),)
        )


@pytest.fixture
def cliente():
    servicio = ServicioFalso()
    app.dependency_overrides[obtener_servicio_cartera] = lambda: servicio
    try:
        yield TestClient(app), servicio
    finally:
        app.dependency_overrides.clear()


def _con_error(error: Exception) -> TestClient:
    app.dependency_overrides[obtener_servicio_cartera] = lambda: ServicioFalso(error)
    return TestClient(app)


def test_consultar_con_filtros_orden_y_limite(cliente) -> None:
    client, servicio = cliente

    respuesta = client.get(
        "/cartera",
        params={
            "fecha_corte": "2026-09-10",
            "filtro": ["region:igual:CUSCO SUR", "dias_atraso:entre:0|30", "telefono:no_vacio"],
            "orden": "-saldo_capital_pendiente",
            "limite": 5,
        },
    )

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert servicio.recibido["fecha_corte"] == FECHA
    assert servicio.recibido["filtros"][0].valores == ("CUSCO SUR",)
    assert servicio.recibido["filtros"][1].valores == (Decimal(0), Decimal(30))
    assert servicio.recibido["filtros"][2].operador is Operador.NO_VACIO
    assert servicio.recibido["filtros"][2].valores == ()
    assert servicio.recibido["orden"].campo == "saldo_capital_pendiente"
    assert servicio.recibido["orden"].descendente
    assert (cuerpo["total"], cuerpo["limite"], cuerpo["suficiente"]) == (7, 5, True)
    assert cuerpo["productos"][0]["saldo_capital_pendiente"] == "1500.50"  # monto como texto
    assert cuerpo["productos"][0]["fecha_vencimiento_cuota"] == "2026-09-18"


def test_top_n_insuficiente_se_reporta(cliente) -> None:
    client, _ = cliente

    respuesta = client.get("/cartera", params={"fecha_corte": "2026-09-10", "limite": 10})

    assert respuesta.json()["suficiente"] is False


@pytest.mark.parametrize(
    "filtro",
    [
        "region",  # sin operador
        "region:parecido:x",  # operador inexistente
        "dias_atraso:igual:mucho",  # valor que no es numero
        "campo_inventado:igual:1",  # campo que no existe
    ],
)
def test_filtros_mal_escritos_son_peticiones_invalidas(cliente, filtro) -> None:
    client, _ = cliente

    respuesta = client.get("/cartera", params={"fecha_corte": "2026-09-10", "filtro": [filtro]})

    assert respuesta.status_code == 400


def test_una_fecha_sin_version_vigente_devuelve_no_encontrado() -> None:
    client = _con_error(SinVersionVigente(FECHA))
    try:
        respuesta = client.get("/cartera", params={"fecha_corte": "2026-09-10"})
    finally:
        app.dependency_overrides.clear()

    assert respuesta.status_code == 404


def test_una_consulta_invalida_del_nucleo_devuelve_peticion_invalida() -> None:
    client = _con_error(ConsultaInvalida("el limite debe estar entre 1 y 5000"))
    try:
        respuesta = client.get("/cartera", params={"fecha_corte": "2026-09-10"})
    finally:
        app.dependency_overrides.clear()

    assert respuesta.status_code == 400


def test_metricas_con_indicador_adicional(cliente) -> None:
    client, servicio = cliente

    respuesta = client.get(
        "/cartera/metricas",
        params={
            "fecha_corte": "2026-09-10",
            "filtro": ["segmento_financiero:igual:1. Preventiva"],
            "indicador": ["cuota promedio:promedio:monto_cuota", "productos:conteo"],
        },
    )

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert cuerpo["capital_total"] == "10500.75"
    assert cuerpo["cuota_minima"] == "50.00"
    assert cuerpo["cuentas_por_segmento"]["1. Preventiva"] == 5
    assert cuerpo["adicionales"]["cuota promedio"] == "2.5"
    indicadores = servicio.recibido["indicadores"]
    assert (indicadores[0].funcion, indicadores[0].campo) == (Funcion.PROMEDIO, "monto_cuota")
    assert (indicadores[1].funcion, indicadores[1].campo) == (Funcion.CONTEO, None)


@pytest.mark.parametrize("indicador", ["solo_nombre", "x:funcion_rara:monto_cuota"])
def test_indicadores_mal_escritos(cliente, indicador) -> None:
    client, _ = cliente

    respuesta = client.get(
        "/cartera/metricas", params={"fecha_corte": "2026-09-10", "indicador": [indicador]}
    )

    assert respuesta.status_code == 400


def test_segmentacion_por_atributo(cliente) -> None:
    client, servicio = cliente

    respuesta = client.get(
        "/cartera/segmentacion", params={"fecha_corte": "2026-09-10", "campo": "region"}
    )

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert servicio.recibido["campo"] == "region"
    assert cuerpo["grupos"][0] == {"valor": "CUSCO SUR", "cuentas": 4, "capital": "8000.00"}


def test_campos_disponibles(cliente) -> None:
    client, _ = cliente

    respuesta = client.get("/cartera/campos")

    assert respuesta.json()["region"]["tipo"] == "texto"
