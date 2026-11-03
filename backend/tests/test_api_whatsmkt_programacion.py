"""GET /whatsmkt/programacion y la fecha de envio al crear, sin base (T-WM-B4c; RF-WM-06, 70, 71).

Siempre con un reloj fijo (`tests/ayudas/calendario_falso.py`). Telefonos 900000xxx.
"""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.whatsmkt_campanas import (
    obtener_repositorio_campanas_whatsmkt,
    obtener_servicio_creacion_whatsmkt,
)
from app.api.whatsmkt_programacion import obtener_servicio_programacion_whatsmkt
from app.core.entities.calendario import ExcepcionCalendario, TipoExcepcion
from app.main import app
from tests.ayudas.calendario_falso import LIMA, calendario_de_prueba, programacion_de_prueba
from tests.ayudas.campanas_whatsmkt_falsas import Entorno
from tests.test_api_whatsmkt_campanas_crear import HOLA, RUTA, cuerpo
from tests.test_whatsmkt_contactos import producto

PROGRAMACION = "/whatsmkt/programacion"


@pytest.fixture
def cliente():
    e = Entorno([producto(1), producto(2)])
    e.textos.agregar(10, HOLA, nombre="Cobranza")
    e.whatsmkt.configuracion = replace(e.whatsmkt.configuracion, whatsapp_contacto="900000123")
    app.dependency_overrides[obtener_servicio_creacion_whatsmkt] = e.servicio
    app.dependency_overrides[obtener_repositorio_campanas_whatsmkt] = lambda: e.campanas
    app.dependency_overrides[obtener_servicio_programacion_whatsmkt] = lambda: (
        programacion_de_prueba()
    )
    try:
        yield TestClient(app), e
    finally:
        app.dependency_overrides.clear()


def con_reloj(ahora: datetime):
    """Sustituye el reloj de la programacion HTTP (la creacion usa el del entorno)."""
    app.dependency_overrides[obtener_servicio_programacion_whatsmkt] = lambda: (
        programacion_de_prueba(ahora=ahora)
    )


# --- GET /whatsmkt/programacion ---------------------------------------------------------------


def test_la_programacion_trae_la_sugerida_la_minima_y_los_proximos_7_por_defecto(cliente) -> None:
    client, _ = cliente

    respuesta = client.get(PROGRAMACION)

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "sugerida": "2026-10-27",
        "minima": "2026-10-27",
        "proximas": [
            "2026-10-27",
            "2026-10-28",
            "2026-10-29",
            "2026-10-30",
            "2026-10-31",  # sabado
            "2026-11-02",  # el domingo 1 no esta
            "2026-11-03",
        ],
    }


def test_proximas_trae_n_dias_y_la_primera_es_la_sugerida(cliente) -> None:
    client, _ = cliente

    respuesta = client.get(PROGRAMACION, params={"n": 3}).json()

    assert respuesta["proximas"] == ["2026-10-27", "2026-10-28", "2026-10-29"]
    assert respuesta["proximas"][0] == respuesta["sugerida"]
    assert len(client.get(PROGRAMACION, params={"n": 1}).json()["proximas"]) == 1


def test_a_las_23_30_de_lima_del_sabado_la_sugerida_es_el_lunes(cliente) -> None:
    client, _ = cliente
    # Las 04:30 UTC del domingo: en el servidor ya es domingo, en Lima todavia es sabado.
    con_reloj(datetime(2026, 11, 8, 4, 30, tzinfo=UTC))

    respuesta = client.get(PROGRAMACION, params={"n": 2}).json()

    assert respuesta["sugerida"] == "2026-11-09"
    assert respuesta["proximas"] == ["2026-11-09", "2026-11-10"]


def test_los_feriados_no_estan_en_los_proximos(cliente) -> None:
    client, _ = cliente
    con_reloj(datetime(2026, 12, 4, 10, 0, tzinfo=LIMA))

    respuesta = client.get(PROGRAMACION, params={"n": 4}).json()

    assert respuesta["proximas"] == ["2026-12-05", "2026-12-07", "2026-12-10", "2026-12-11"]


@pytest.mark.parametrize("n", [0, -1, 32, 1000])
def test_un_n_fuera_de_rango_responde_400_con_el_rango(cliente, n) -> None:
    client, _ = cliente

    respuesta = client.get(PROGRAMACION, params={"n": n})

    assert respuesta.status_code == 400
    cuerpo_ = respuesta.json()
    assert cuerpo_["codigo"] == "proximos_fuera_de_rango"
    assert (cuerpo_["minimo"], cuerpo_["maximo"]) == (1, 31)


def test_un_n_que_no_es_un_entero_responde_el_422_de_validacion(cliente) -> None:
    client, _ = cliente

    respuesta = client.get(PROGRAMACION, params={"n": "muchos"})

    assert respuesta.status_code == 422
    assert isinstance(respuesta.json()["detail"], list)


# --- Crear: la fecha ya no sirve --------------------------------------------------------------


def crear(cliente, **cambios):
    client, _ = cliente
    return client.post(RUTA, json=cuerpo(**cambios))


@pytest.mark.parametrize(
    ("fecha", "sugerida"),
    [
        ("2026-11-08", "2026-11-09"),  # domingo
        ("2026-12-08", "2026-12-10"),  # feriado de ley (y el 9 tambien)
        ("2026-10-26", "2026-10-27"),  # hoy
        ("2026-10-20", "2026-10-27"),  # el pasado
    ],
    ids=["domingo", "feriado", "hoy", "pasado"],
)
def test_crear_con_una_fecha_que_no_es_gestionable_responde_409_y_no_guarda_nada(
    cliente, fecha, sugerida
) -> None:
    _, e = cliente

    respuesta = crear(cliente, fecha_corte="2026-10-01", fecha_envio=fecha)

    assert respuesta.status_code == 409
    cuerpo_ = respuesta.json()
    assert cuerpo_["codigo"] == "fecha_no_gestionable"
    assert (cuerpo_["fecha"], cuerpo_["sugerida"]) == (fecha, sugerida)
    assert fecha in cuerpo_["detail"] and sugerida in cuerpo_["detail"]
    assert e.campanas.lotes == []


def test_una_fecha_que_dejo_de_valer_por_la_medianoche_se_rechaza_con_la_nueva_sugerida(
    cliente,
) -> None:
    _, e = cliente
    assert crear(cliente, fecha_envio="2026-11-03").status_code == 201

    # Pasan los dias: hoy es el 3 de noviembre en Lima y esa fecha ya no puede ser la de envio.
    e.calendario = calendario_de_prueba(ahora=datetime(2026, 11, 3, 9, 0, tzinfo=LIMA))
    respuesta = crear(cliente, fecha_envio="2026-11-03")

    assert respuesta.status_code == 409
    assert respuesta.json()["sugerida"] == "2026-11-04"
    assert len(e.campanas.lotes) == 1  # solo el primero


def test_a_las_23_30_de_lima_del_sabado_el_sabado_ya_no_se_puede_elegir(cliente) -> None:
    _, e = cliente
    e.calendario = calendario_de_prueba(ahora=datetime(2026, 11, 8, 4, 30, tzinfo=UTC))

    respuesta = crear(cliente, fecha_corte="2026-11-01", fecha_envio="2026-11-07")

    assert respuesta.status_code == 409
    assert respuesta.json()["sugerida"] == "2026-11-09"


def test_una_excepcion_registrada_tambien_rechaza_el_dia(cliente) -> None:
    _, e = cliente
    decretado = ExcepcionCalendario(date(2026, 11, 3), TipoExcepcion.AGREGADO, "Decretado")
    e.calendario = calendario_de_prueba(decretado)

    respuesta = crear(cliente, fecha_envio="2026-11-03")

    assert respuesta.status_code == 409
    assert respuesta.json()["sugerida"] == "2026-11-04"


def test_la_fecha_no_gestionable_se_avisa_antes_que_los_demas_problemas(cliente) -> None:
    _, e = cliente

    # Sin horarios tambien falla (422), pero la fecha es lo primero que se contesta.
    respuesta = crear(cliente, fecha_envio="2026-11-08", horarios=[])

    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "fecha_no_gestionable"
    assert e.campanas.lotes == []


def test_un_sabado_y_un_lunes_se_aceptan(cliente) -> None:
    assert crear(cliente, fecha_envio="2026-11-07").status_code == 201
    assert crear(cliente, fecha_envio="2026-11-09").status_code == 201


# --- Contrato ---------------------------------------------------------------------------------


def test_el_contrato_declara_la_programacion_y_el_409_de_crear() -> None:
    esquema = app.openapi()
    schemas = esquema["components"]["schemas"]
    programacion = esquema["paths"][PROGRAMACION]["get"]
    crear_ = esquema["paths"][RUTA]["post"]

    assert {"200", "400"} <= set(programacion["responses"])
    assert set(schemas["ProgramacionWhatsmktRespuesta"]["required"]) == {
        "sugerida",
        "minima",
        "proximas",
    }
    assert "409" in crear_["responses"]
    assert crear_["responses"]["409"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ErrorFechaNoGestionableWhatsmktRespuesta"
    )
    assert {"detail", "codigo", "fecha", "sugerida"} <= set(
        schemas["ErrorFechaNoGestionableWhatsmktRespuesta"]["required"]
    )
