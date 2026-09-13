"""Pruebas de los endpoints de configuracion de MOWA MES, calendario y supervisores.

Sustituyen la dependencia del caso de uso por el servicio real sobre un
repositorio en memoria: se prueba la traduccion HTTP, no la base.
"""

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.calendario import obtener_servicio_calendario
from app.api.mowa_mes import obtener_servicio_mowa_mes
from app.api.supervisores import obtener_servicio_supervision
from app.core.entities.calendario import ExcepcionCalendario, TipoExcepcion
from app.core.services.calendario.servicio import CalendarioService
from app.core.services.gestiones_digitales.servicio import SupervisionService
from app.core.services.plataformas.mowa_mes.configuracion import ConfiguracionMowaMesService
from app.main import app
from tests.test_calendario import RepositorioCalendarioFalso
from tests.test_gestiones_digitales import RepositorioSupervisionFalso
from tests.test_mowa_mes_speech import ORIGINAL, RepositorioMowaMesFalso

PARTES = [
    {"segmento": p.segmento.value, "parte_1": p.parte_1, "parte_2": p.parte_2} for p in ORIGINAL
]


@pytest.fixture
def cliente():
    calendario = CalendarioService(
        RepositorioCalendarioFalso(
            ExcepcionCalendario(date(2026, 9, 14), TipoExcepcion.AGREGADO, "Decreto sintetico")
        ),
        reloj=lambda: datetime(2026, 9, 13, 15, 0, tzinfo=UTC),
    )
    supervision = SupervisionService(RepositorioSupervisionFalso())
    mowa_mes = RepositorioMowaMesFalso(whatsapp=None)
    app.dependency_overrides[obtener_servicio_calendario] = lambda: calendario
    app.dependency_overrides[obtener_servicio_supervision] = lambda: supervision
    app.dependency_overrides[obtener_servicio_mowa_mes] = lambda: ConfiguracionMowaMesService(
        mowa_mes
    )
    try:
        yield TestClient(app), mowa_mes
    finally:
        app.dependency_overrides.clear()


# --- Calendario ---------------------------------------------------------


def test_feriados_del_anio_actual_en_lima(cliente) -> None:
    client, _ = cliente

    cuerpo = client.get("/calendario/feriados").json()

    assert cuerpo["anio"] == 2026
    assert {
        "fecha": "2026-04-02",
        "descripcion": "Jueves Santo",
        "origen": "ley",
        "retirado": False,
    } in cuerpo["dias"]
    assert {d["fecha"]: d["origen"] for d in cuerpo["dias"]}["2026-09-14"] == "agregado"


def test_feriados_de_otro_anio(cliente) -> None:
    client, _ = cliente

    cuerpo = client.get("/calendario/feriados", params={"anio": 2027}).json()

    assert "2027-03-25" in [d["fecha"] for d in cuerpo["dias"]]
    assert client.get("/calendario/feriados", params={"anio": 1800}).status_code == 422


def test_siguiente_dia_gestionable_desde_hoy_y_desde_una_fecha(cliente) -> None:
    client, _ = cliente

    hoy = client.get("/calendario/siguiente-dia-gestionable").json()
    semana_santa = client.get(
        "/calendario/siguiente-dia-gestionable", params={"desde": "2026-04-01"}
    ).json()

    assert hoy == {"desde": "2026-09-13", "fecha": "2026-09-15"}  # el 14 esta decretado
    assert semana_santa == {"desde": "2026-04-01", "fecha": "2026-04-06"}


def test_ciclo_de_excepciones(cliente) -> None:
    client, _ = cliente
    retiro = {"fecha": "2026-07-23", "tipo": "retirado", "descripcion": "Cambio de ley sintetico"}

    creada = client.post("/calendario/excepciones", json=retiro)
    repetida = client.post("/calendario/excepciones", json=retiro)
    sin_sentido = client.post("/calendario/excepciones", json={**retiro, "fecha": "2026-07-24"})
    listadas = client.get("/calendario/excepciones").json()

    assert creada.status_code == 201
    assert creada.json()["tipo"] == "retirado"
    assert repetida.status_code == 409
    assert sin_sentido.status_code == 400
    assert [e["fecha"] for e in listadas] == ["2026-07-23", "2026-09-14"]
    assert client.delete("/calendario/excepciones/2026-07-23").status_code == 204
    assert client.delete("/calendario/excepciones/2026-07-23").status_code == 404


# --- Supervisores -------------------------------------------------------


def test_reemplazar_supervisores_devuelve_el_documento_de_cada_uno(cliente) -> None:
    client, _ = cliente
    cuerpo = {
        "procedencias": ["Caja Cusco", "nuestra empresa"],
        "supervisores": [
            {"numero": "900000004", "procedencia": "nuestra empresa"},
            {"numero": "900000001", "procedencia": "Caja Cusco"},
        ],
    }

    respuesta = client.put("/supervisores", json=cuerpo)

    assert respuesta.status_code == 200
    assert [(s["numero"], s["documento"]) for s in respuesta.json()["supervisores"]] == [
        ("900000004", "00000002"),
        ("900000001", "00000001"),
    ]
    assert client.get("/supervisores").json() == respuesta.json()


def test_un_supervisor_con_numero_invalido_se_rechaza(cliente) -> None:
    client, _ = cliente

    respuesta = client.put(
        "/supervisores",
        json={
            "procedencias": ["Caja Cusco"],
            "supervisores": [{"numero": "12345", "procedencia": "Caja Cusco"}],
        },
    )

    assert respuesta.status_code == 400
    assert "9 digitos" in respuesta.json()["detail"]


# --- Configuracion del conector -----------------------------------------


def test_configuracion_del_conector(cliente) -> None:
    client, _ = cliente

    inicial = client.get("/mowa-mes/configuracion").json()
    guardada = client.put(
        "/mowa-mes/configuracion",
        json={"limite_mensual": 3_000_000, "whatsapp_contacto": "900000123"},
    )
    invalida = client.put(
        "/mowa-mes/configuracion", json={"limite_mensual": 1, "whatsapp_contacto": "800000123"}
    )

    assert (inicial["limite_mensual"], inicial["whatsapp_contacto"]) == (2_500_000, None)
    assert guardada.status_code == 200
    assert guardada.json()["whatsapp_contacto"] == "900000123"
    assert invalida.status_code == 400
    assert client.put("/mowa-mes/configuracion", json={"limite_mensual": 0}).status_code == 422


# --- Speech -------------------------------------------------------------


def test_listar_y_obtener_speech(cliente) -> None:
    client, _ = cliente

    (original,) = client.get("/mowa-mes/speech").json()
    no_existe = client.get("/mowa-mes/speech/99")

    assert (original["nombre"], original["original"], original["editable"]) == (
        "Speech original",
        True,
        False,
    )
    assert original["partes"][2] == {
        "segmento": "9_a_30",
        "etiqueta": "9 a 30",
        "dias_desde": 9,
        "dias_hasta": 30,
        "parte_1": ORIGINAL[2].parte_1,
        "parte_2": ORIGINAL[2].parte_2,
        "usa_whatsapp": False,
    }
    assert original["partes"][0]["dias_desde"] is None
    assert client.get("/mowa-mes/speech/1").json() == original
    assert no_existe.status_code == 404


def test_crear_editar_y_proteger_versiones(cliente) -> None:
    client, repositorio = cliente

    creada = client.post("/mowa-mes/speech", json={"basada_en_id": 1, "partes": PARTES})
    speech_id = creada.json()["id"]
    editada = client.put(
        f"/mowa-mes/speech/{speech_id}", json={"nombre": "Speech corregido", "partes": PARTES}
    )
    repetida = client.post(
        "/mowa-mes/speech", json={"nombre": "speech corregido", "partes": PARTES}
    )
    original = client.put("/mowa-mes/speech/1", json={"nombre": "Otro", "partes": PARTES})
    repositorio.marcar_speech_usado(speech_id)
    usada = client.put(
        f"/mowa-mes/speech/{speech_id}", json={"nombre": "Speech corregido", "partes": PARTES}
    )

    assert creada.status_code == 201
    assert (creada.json()["nombre"], creada.json()["basada_en_id"]) == ("Speech 2", 1)
    assert editada.status_code == 200
    assert repetida.status_code == 409
    assert original.status_code == 409
    assert usada.status_code == 409
    assert "version nueva" in usada.json()["detail"]
    assert client.get(f"/mowa-mes/speech/{speech_id}").json()["usada"] is True


@pytest.mark.parametrize(
    ("cuerpo", "estado"),
    [
        ({"partes": PARTES[:5]}, 400),
        ({"partes": [{**PARTES[0], "parte_1": " [@titular]"}, *PARTES[1:]]}, 400),
        ({"basada_en_id": 99, "partes": PARTES}, 404),
        ({"partes": [{**PARTES[0], "segmento": "inventado"}, *PARTES[1:]]}, 422),
    ],
)
def test_versiones_invalidas(cliente, cuerpo, estado) -> None:
    client, _ = cliente

    assert client.post("/mowa-mes/speech", json=cuerpo).status_code == estado


def test_previsualizacion_sin_whatsapp_marca_los_segmentos_que_lo_necesitan(cliente) -> None:
    client, _ = cliente

    cuerpo = client.post("/mowa-mes/speech/previsualizacion", json={"partes": PARTES}).json()

    por_segmento = {s["segmento"]: s for s in cuerpo["segmentos"]}
    assert (cuerpo["whatsapp"], cuerpo["largo_advertencia"], cuerpo["largo_maximo"]) == (
        None,
        150,
        160,
    )
    assert por_segmento["31_a_60"]["falta_whatsapp"] is True
    assert por_segmento["31_a_60"]["ejemplo"] is None
    assert por_segmento["9_a_30"]["codigo"] == "mensaje_excede_150"
    assert por_segmento["preventiva"]["falta_whatsapp"] is False


def test_previsualizacion_con_whatsapp_y_problemas(cliente) -> None:
    client, _ = cliente
    partes = [{**PARTES[0], "parte_2": " [@"}, *PARTES[1:]]

    cuerpo = client.post(
        "/mowa-mes/speech/previsualizacion", json={"partes": partes, "whatsapp": "900000123"}
    ).json()
    invalido = client.post(
        "/mowa-mes/speech/previsualizacion", json={"partes": PARTES, "whatsapp": "123"}
    )

    assert cuerpo["whatsapp"] == "900000123"
    assert cuerpo["problemas"] == [
        {"segmento": "preventiva", "campo": "parte_2", "detalle": "El texto no puede contener '[@'"}
    ]
    assert all(not s["falta_whatsapp"] for s in cuerpo["segmentos"])
    assert invalido.status_code == 400
