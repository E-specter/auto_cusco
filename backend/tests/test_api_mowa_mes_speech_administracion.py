"""API de la administracion de speeches (T-MM-C11, M-B2; RF-MM-28 a RF-MM-30).

Sobre el repositorio en memoria, como `test_api_mowa_mes_speech_v2.py`; la previsualizacion y la
creacion de campanas con una version deshabilitada usan el entorno de las campanas. Datos
sinteticos.
"""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.api import contrato
from app.api.mowa_mes import obtener_servicio_mowa_mes
from app.core.services.plataformas.mowa_mes.configuracion import ConfiguracionMowaMesService
from app.main import app
from tests.test_api_mowa_mes_campanas import CUERPO, Entorno, _cliente
from tests.test_api_mowa_mes_speech_v2 import CUERPO_V2
from tests.test_mowa_mes_campana import HUELLA_ORIGINAL, MOMENTO
from tests.test_mowa_mes_speech import WHATSAPP, RepositorioMowaMesFalso


@pytest.fixture
def cliente():
    repositorio = RepositorioMowaMesFalso(WHATSAPP)
    servicio = ConfiguracionMowaMesService(repositorio)
    app.dependency_overrides[obtener_servicio_mowa_mes] = lambda: servicio
    try:
        yield TestClient(app), repositorio
    finally:
        app.dependency_overrides.clear()


def _crear(client, nombre="Version de prueba") -> dict:
    respuesta = client.post("/mowa-mes/speech", json={"nombre": nombre, "expresiones": CUERPO_V2})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _usar(repositorio, speech_id: int) -> None:
    repositorio.versiones[speech_id] = replace(repositorio.versiones[speech_id], usada_en=MOMENTO)


# --- La lista trae la marca, eliminable y el motivo ----------------------------------------------


def test_cada_version_trae_su_marca_y_si_se_puede_eliminar(cliente) -> None:
    client, repositorio = cliente
    habilitada = _crear(client, "Habilitada")
    deshabilitada = _crear(client, "Deshabilitada")
    usada = _crear(client, "Usada")
    client.patch(f"/mowa-mes/speech/{deshabilitada['id']}", json={"habilitada": False})
    client.patch(f"/mowa-mes/speech/{usada['id']}", json={"habilitada": False})
    _usar(repositorio, usada["id"])

    lista = {v["nombre"]: v for v in client.get("/mowa-mes/speech").json()}

    resumen = {
        nombre: (v["deshabilitada_en"] is not None, v["eliminable"], v["motivo_no_eliminable"])
        for nombre, v in lista.items()
    }
    assert resumen == {
        "Speech original": (False, False, "original"),
        "Habilitada": (False, False, None),  # basta deshabilitarla
        "Deshabilitada": (True, True, None),
        "Usada": (True, False, "usada"),
    }
    assert habilitada["eliminable"] is False and habilitada["editable"] is True
    assert lista["Deshabilitada"]["editable"] is False  # se ve en solo lectura


# --- Renombrar (RF-MM-28) ------------------------------------------------------------------------


def test_se_renombra_y_el_contenido_no_cambia(cliente) -> None:
    client, _ = cliente
    antes = _crear(client)

    renombrada = client.patch(f"/mowa-mes/speech/{antes['id']}", json={"nombre": "  Nuevo  "})

    cuerpo = renombrada.json()
    assert renombrada.status_code == 200 and cuerpo["nombre"] == "Nuevo"
    assert cuerpo["expresiones"] == antes["expresiones"]
    assert client.get(f"/mowa-mes/speech/{antes['id']}").json() == cuerpo


def test_se_renombra_el_original_y_una_usada(cliente) -> None:
    client, repositorio = cliente
    usada = _crear(client)
    _usar(repositorio, usada["id"])

    original = client.patch("/mowa-mes/speech/1", json={"nombre": "El de siempre"})
    renombrada = client.patch(f"/mowa-mes/speech/{usada['id']}", json={"nombre": "Usada nueva"})

    assert (original.status_code, original.json()["nombre"]) == (200, "El de siempre")
    assert (renombrada.status_code, renombrada.json()["nombre"]) == (200, "Usada nueva")
    assert renombrada.json()["usada"] is True


def test_un_nombre_repetido_es_409_y_no_cambia_nada(cliente) -> None:
    client, _ = cliente
    _crear(client, "Alfa")
    otra = _crear(client, "Beta")

    repetido = client.patch(
        f"/mowa-mes/speech/{otra['id']}", json={"nombre": "ALFA", "habilitada": False}
    )

    assert repetido.status_code == 409 and "ALFA" in repetido.json()["detail"]
    assert client.get(f"/mowa-mes/speech/{otra['id']}").json()["nombre"] == "Beta"
    # Con los dos campos, primero renombra: si falla, tampoco se deshabilita.
    assert client.get(f"/mowa-mes/speech/{otra['id']}").json()["deshabilitada_en"] is None


def test_un_nombre_en_blanco_es_400_con_su_problema(cliente) -> None:
    client, _ = cliente
    version = _crear(client)

    respuesta = client.patch(f"/mowa-mes/speech/{version['id']}", json={"nombre": "   "})

    assert respuesta.status_code == 400
    assert [(p["campo"], p["segmento"]) for p in respuesta.json()["problemas"]] == [
        ("nombre", None)
    ]


def test_un_nombre_vacio_o_demasiado_largo_es_422(cliente) -> None:
    client, _ = cliente
    version = _crear(client)

    assert client.patch(f"/mowa-mes/speech/{version['id']}", json={"nombre": ""}).status_code == 422
    largo = client.patch(f"/mowa-mes/speech/{version['id']}", json={"nombre": "x" * 500})
    assert largo.status_code == 422


# --- Deshabilitar y habilitar (RF-MM-29) ---------------------------------------------------------


def test_se_deshabilita_y_se_habilita(cliente) -> None:
    client, _ = cliente
    version = _crear(client)

    deshabilitada = client.patch(f"/mowa-mes/speech/{version['id']}", json={"habilitada": False})
    habilitada = client.patch(f"/mowa-mes/speech/{version['id']}", json={"habilitada": True})

    assert deshabilitada.status_code == 200 and deshabilitada.json()["deshabilitada_en"]
    assert deshabilitada.json()["editable"] is False
    assert habilitada.status_code == 200 and habilitada.json()["deshabilitada_en"] is None
    assert habilitada.json()["editable"] is True


def test_deshabilitar_dos_veces_conserva_la_primera_fecha(cliente) -> None:
    client, _ = cliente
    version = _crear(client)

    primera = client.patch(f"/mowa-mes/speech/{version['id']}", json={"habilitada": False}).json()
    segunda = client.patch(f"/mowa-mes/speech/{version['id']}", json={"habilitada": False}).json()

    assert segunda["deshabilitada_en"] == primera["deshabilitada_en"]


def test_se_renombra_y_deshabilita_en_una_sola_llamada(cliente) -> None:
    client, _ = cliente
    version = _crear(client)

    respuesta = client.patch(
        f"/mowa-mes/speech/{version['id']}", json={"nombre": "Nuevo", "habilitada": False}
    ).json()

    assert (respuesta["nombre"], respuesta["deshabilitada_en"] is not None) == ("Nuevo", True)


def test_sin_campos_devuelve_la_version_tal_cual(cliente) -> None:
    client, _ = cliente
    version = _crear(client)

    assert client.patch(f"/mowa-mes/speech/{version['id']}", json={}).json() == version


def test_una_deshabilitada_no_se_edita_con_put(cliente) -> None:
    client, _ = cliente
    version = _crear(client)
    client.patch(f"/mowa-mes/speech/{version['id']}", json={"habilitada": False})

    editada = client.put(
        f"/mowa-mes/speech/{version['id']}", json={"nombre": "Otro", "expresiones": CUERPO_V2}
    )

    assert editada.status_code == 409 and "deshabilitada" in editada.json()["detail"]

    # Al habilitarla de nuevo vuelve a ser editable: no esta usada ni es el original.
    client.patch(f"/mowa-mes/speech/{version['id']}", json={"habilitada": True})
    reeditada = client.put(
        f"/mowa-mes/speech/{version['id']}", json={"nombre": "Otro", "expresiones": CUERPO_V2}
    )
    assert reeditada.status_code == 200 and reeditada.json()["nombre"] == "Otro"


def test_patch_de_una_que_no_existe_es_404(cliente) -> None:
    client, _ = cliente

    assert client.patch("/mowa-mes/speech/99", json={"habilitada": False}).status_code == 404
    assert client.patch("/mowa-mes/speech/99", json={"nombre": "x"}).status_code == 404


# --- Eliminar (RF-MM-30) -------------------------------------------------------------------------


def test_se_elimina_una_deshabilitada_sin_uso(cliente) -> None:
    client, _ = cliente
    version = _crear(client)
    client.patch(f"/mowa-mes/speech/{version['id']}", json={"habilitada": False})

    eliminada = client.delete(f"/mowa-mes/speech/{version['id']}")

    assert eliminada.status_code == 204 and eliminada.content == b""
    assert client.get(f"/mowa-mes/speech/{version['id']}").status_code == 404
    assert version["id"] not in [v["id"] for v in client.get("/mowa-mes/speech").json()]


def test_eliminar_una_habilitada_es_409_speech_no_deshabilitado(cliente) -> None:
    client, _ = cliente
    version = _crear(client)

    rechazada = client.delete(f"/mowa-mes/speech/{version['id']}")

    assert rechazada.status_code == 409
    assert rechazada.json()["codigo"] == "speech_no_deshabilitado"
    assert client.get(f"/mowa-mes/speech/{version['id']}").status_code == 200


def test_eliminar_una_usada_es_409_speech_usado(cliente) -> None:
    client, repositorio = cliente
    version = _crear(client)
    client.patch(f"/mowa-mes/speech/{version['id']}", json={"habilitada": False})
    _usar(repositorio, version["id"])

    rechazada = client.delete(f"/mowa-mes/speech/{version['id']}")

    assert rechazada.status_code == 409 and rechazada.json()["codigo"] == "speech_usado"
    assert client.get(f"/mowa-mes/speech/{version['id']}").status_code == 200


def test_eliminar_el_original_es_409_speech_original_aun_deshabilitado(cliente) -> None:
    client, _ = cliente
    client.patch("/mowa-mes/speech/1", json={"habilitada": False})

    rechazada = client.delete("/mowa-mes/speech/1")

    assert rechazada.status_code == 409 and rechazada.json()["codigo"] == "speech_original"
    assert client.get("/mowa-mes/speech/1").status_code == 200


def test_eliminar_una_que_no_existe_es_404(cliente) -> None:
    client, _ = cliente

    assert client.delete("/mowa-mes/speech/99").status_code == 404


# --- Una deshabilitada en la campana (RF-MM-29) --------------------------------------------------


def test_la_previsualizacion_y_la_creacion_rechazan_una_deshabilitada() -> None:
    entorno = Entorno()
    client = _cliente(entorno)
    entorno.mowa_mes.versiones[1] = replace(entorno.mowa_mes.versiones[1], deshabilitada_en=MOMENTO)
    try:
        previa = client.post("/mowa-mes/campanas/previsualizacion", json=CUERPO)
        creada = client.post(
            "/mowa-mes/campanas", json={**CUERPO, "speech_huella": HUELLA_ORIGINAL}
        )
    finally:
        app.dependency_overrides.clear()

    assert previa.status_code == 200 and previa.json()["puede_crear"] is False
    assert [(e["codigo"], e["tipo"]) for e in previa.json()["errores"]] == [
        ("speech_deshabilitado", "error")
    ]
    assert creada.status_code == 400
    assert entorno.campanas.campanas == {}


# --- Contrato ------------------------------------------------------------------------------------


def test_el_contrato_declara_los_campos_las_rutas_y_los_codigos() -> None:
    esquema = contrato.generar()
    esquemas = esquema["components"]["schemas"]
    version = esquemas["VersionSpeechRespuesta"]

    assert {"deshabilitada_en", "eliminable", "motivo_no_eliminable"} <= set(version["required"])
    assert set(esquemas["CodigoErrorSpeech"]["enum"]) == {
        "speech_original",
        "speech_usado",
        "speech_no_deshabilitado",
    }
    assert set(esquemas["MotivoNoEliminable"]["enum"]) == {"original", "usada"}
    ruta = esquema["paths"]["/mowa-mes/speech/{speech_id}"]
    assert {"get", "put", "patch", "delete"} <= set(ruta)
    assert "speech_deshabilitado" in esquemas["CodigoMowaMes"]["enum"]
