"""API de las campanas descartadas (T-MM-C11, M-B1; RF-MM-31, RF-MM-32 y RF-MM-33).

Los mismos servicios reales sobre repositorios en memoria que `test_api_mowa_mes_campanas.py`.
Datos sinteticos.
"""

import pytest
from fastapi.testclient import TestClient

from app.api import contrato
from app.main import app
from tests.test_api_mowa_mes_campanas import Entorno, _cliente, _crear, _reporte


@pytest.fixture(autouse=True)
def _limpiar_dependencias():
    yield
    app.dependency_overrides.clear()


def _descartar(client: TestClient, campana_id: int):
    return client.post(f"/mowa-mes/campanas/{campana_id}/descartar")


def _importar(client: TestClient, entorno: Entorno, campana_id: int):
    contenido = _reporte(entorno.campanas.filas_cargadas(campana_id), 990001)
    return client.post(
        f"/mowa-mes/campanas/{campana_id}/reportes", files={"archivo": ("reporte.xlsx", contenido)}
    )


# --- La respuesta de la campana ------------------------------------------


def test_una_campana_nueva_esta_activa_y_pendiente_de_reporte() -> None:
    client = _cliente(Entorno())

    creada = _crear(client).json()

    assert creada["descartada_en"] is None
    assert creada["pendiente_reporte"] is True
    assert "enviados_conciliados" not in creada  # el derivado no se expone (mowa-mes.md, §16)


def test_con_reporte_importado_ya_no_esta_pendiente() -> None:
    entorno = Entorno()
    client = _cliente(entorno)
    campana_id = _crear(client).json()["id"]

    importado = _importar(client, entorno, campana_id)

    assert importado.status_code == 201
    assert client.get(f"/mowa-mes/campanas/{campana_id}").json()["pendiente_reporte"] is False
    assert client.get("/mowa-mes/campanas").json()["campanas"][0]["pendiente_reporte"] is False


def test_el_listado_trae_el_total_de_pendientes_de_todas_las_activas() -> None:
    entorno = Entorno()
    client = _cliente(entorno)
    con_reporte = _crear(client).json()["id"]
    sin_reporte = _crear(client).json()["id"]
    descartada = _crear(client).json()["id"]
    _importar(client, entorno, con_reporte)
    _descartar(client, descartada)

    completo = client.get("/mowa-mes/campanas").json()
    una_sola = client.get("/mowa-mes/campanas", params={"limite": 1}).json()

    assert (completo["total"], completo["total_pendientes"]) == (2, 1)
    assert [(c["id"], c["pendiente_reporte"]) for c in completo["campanas"]] == [
        (sin_reporte, True),
        (con_reporte, False),
    ]
    # El total no depende de la pagina que se ve.
    assert len(una_sola["campanas"]) == 1 and una_sola["total_pendientes"] == 1


def test_sin_campanas_el_total_de_pendientes_es_cero() -> None:
    assert _cliente(Entorno()).get("/mowa-mes/campanas").json()["total_pendientes"] == 0


# --- Descartar y restaurar -----------------------------------------------


def test_descartar_devuelve_la_campana_con_su_fecha_y_la_saca_del_listado() -> None:
    client = _cliente(Entorno())
    campana_id = _crear(client).json()["id"]
    otra_id = _crear(client).json()["id"]

    descartada = _descartar(client, campana_id)
    activas = client.get("/mowa-mes/campanas").json()

    assert descartada.status_code == 200
    assert descartada.json()["id"] == campana_id and descartada.json()["descartada_en"] is not None
    assert (activas["total"], [c["id"] for c in activas["campanas"]]) == (1, [otra_id])
    assert client.get(f"/mowa-mes/campanas/{campana_id}").json()["descartada_en"] is not None


def test_descartar_dos_veces_no_falla_ni_cambia_la_fecha() -> None:
    client = _cliente(Entorno())
    campana_id = _crear(client).json()["id"]

    primera = _descartar(client, campana_id).json()
    segunda = _descartar(client, campana_id)

    assert segunda.status_code == 200
    assert segunda.json()["descartada_en"] == primera["descartada_en"]


def test_una_descartada_no_suma_al_limite_del_mes() -> None:
    client = _cliente(Entorno())
    campana_id = _crear(client).json()["id"]
    antes = client.get("/mowa-mes/limite-mensual", params={"mes": "2026-09"}).json()

    _descartar(client, campana_id)
    despues = client.get("/mowa-mes/limite-mensual", params={"mes": "2026-09"}).json()

    assert antes["cargados_mes"] == 6 and despues["cargados_mes"] == 0


def test_restaurar_la_devuelve_a_las_activas_y_al_limite() -> None:
    client = _cliente(Entorno())
    campana_id = _crear(client).json()["id"]
    _descartar(client, campana_id)

    restaurada = client.post(f"/mowa-mes/campanas/{campana_id}/restaurar")
    limite = client.get("/mowa-mes/limite-mensual", params={"mes": "2026-09"}).json()

    assert restaurada.status_code == 200 and restaurada.json()["descartada_en"] is None
    assert [c["id"] for c in client.get("/mowa-mes/campanas").json()["campanas"]] == [campana_id]
    assert limite["cargados_mes"] == 6


@pytest.mark.parametrize("operacion", ["descartar", "restaurar"])
def test_descartar_o_restaurar_una_campana_inexistente_es_404(operacion) -> None:
    client = _cliente(Entorno())

    assert client.post(f"/mowa-mes/campanas/99/{operacion}").status_code == 404


# --- Eliminar --------------------------------------------------------------


def test_eliminar_una_activa_es_409_con_su_codigo() -> None:
    client = _cliente(Entorno())
    campana_id = _crear(client).json()["id"]

    rechazada = client.delete(f"/mowa-mes/campanas/{campana_id}")

    assert rechazada.status_code == 409
    assert rechazada.json()["codigo"] == "campana_no_descartada"
    assert client.get(f"/mowa-mes/campanas/{campana_id}").status_code == 200


def test_eliminar_una_descartada_da_204_y_la_borra() -> None:
    entorno = Entorno()
    client = _cliente(entorno)
    campana_id = _crear(client).json()["id"]
    _importar(client, entorno, campana_id)
    _descartar(client, campana_id)

    eliminada = client.delete(f"/mowa-mes/campanas/{campana_id}")

    assert eliminada.status_code == 204 and eliminada.content == b""
    assert client.get(f"/mowa-mes/campanas/{campana_id}").status_code == 404
    assert client.get(f"/mowa-mes/campanas/{campana_id}/archivos/1").status_code == 404
    assert client.get("/mowa-mes/campanas/descartadas").json()["total_descartadas"] == 0


def test_eliminar_una_campana_inexistente_es_404() -> None:
    assert _cliente(Entorno()).delete("/mowa-mes/campanas/99").status_code == 404


# --- Listado de descartadas --------------------------------------------------


def test_las_descartadas_traen_los_meses_y_el_total() -> None:
    client = _cliente(Entorno())
    septiembre = _crear(client).json()["id"]
    octubre = _crear(client, envios=["2026-10-02T09:00:00"]).json()["id"]
    _crear(client)  # esta sigue activa
    _descartar(client, septiembre)
    _descartar(client, octubre)

    todas = client.get("/mowa-mes/campanas/descartadas").json()
    de_octubre = client.get("/mowa-mes/campanas/descartadas", params={"mes": "2026-10"}).json()

    assert todas["meses"] == ["2026-10", "2026-09"] and todas["total_descartadas"] == 2
    assert [c["id"] for c in todas["campanas"]] == [octubre, septiembre]
    assert [c["id"] for c in de_octubre["campanas"]] == [octubre]
    assert de_octubre["meses"] == ["2026-10", "2026-09"]  # el filtro no recorta los meses
    assert de_octubre["total_descartadas"] == 2


@pytest.mark.parametrize("mes", ["2026-13", "septiembre", "2026-9"])
def test_el_mes_del_listado_se_valida(mes) -> None:
    client = _cliente(Entorno())

    assert client.get("/mowa-mes/campanas/descartadas", params={"mes": mes}).status_code == 422


def test_descartadas_no_se_confunde_con_el_id_de_una_campana() -> None:
    client = _cliente(Entorno())

    respuesta = client.get("/mowa-mes/campanas/descartadas")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"campanas": [], "meses": [], "total_descartadas": 0}


# --- Reporte a una descartada (U-1, A) ---------------------------------------


def test_importar_un_reporte_a_una_descartada_es_409_con_su_codigo_y_no_guarda_nada() -> None:
    entorno = Entorno()
    client = _cliente(entorno)
    campana_id = _crear(client).json()["id"]
    _descartar(client, campana_id)

    rechazado = _importar(client, entorno, campana_id)

    assert rechazado.status_code == 409
    assert rechazado.json()["codigo"] == "campana_descartada"
    assert "restaurala primero" in rechazado.json()["detail"]
    assert entorno.campanas.informes == {}


def test_restaurada_acepta_el_reporte() -> None:
    entorno = Entorno()
    client = _cliente(entorno)
    campana_id = _crear(client).json()["id"]
    _descartar(client, campana_id)
    client.post(f"/mowa-mes/campanas/{campana_id}/restaurar")

    assert _importar(client, entorno, campana_id).status_code == 201


def test_el_409_de_un_id_ya_importado_sigue_sin_codigo() -> None:
    entorno = Entorno()
    client = _cliente(entorno)
    campana_id = _crear(client).json()["id"]
    _importar(client, entorno, campana_id)

    repetido = _importar(client, entorno, campana_id)

    assert repetido.status_code == 409 and "codigo" not in repetido.json()


def test_ver_la_conciliacion_de_una_descartada_se_permite() -> None:
    entorno = Entorno()
    client = _cliente(entorno)
    campana_id = _crear(client).json()["id"]
    _importar(client, entorno, campana_id)
    _descartar(client, campana_id)

    assert client.get(f"/mowa-mes/campanas/{campana_id}/conciliacion").status_code == 200


# --- Contrato ------------------------------------------------------------------


def test_el_contrato_declara_los_codigos_y_los_campos_nuevos() -> None:
    esquemas = contrato.generar()["components"]["schemas"]

    assert set(esquemas["CodigoErrorCampana"]["enum"]) == {
        "huella_cambiada",
        "limite_excedido",
        "campana_descartada",
        "campana_no_descartada",
    }
    campana = esquemas["CampanaRespuesta"]
    assert {"descartada_en", "pendiente_reporte"} <= set(campana["required"])
    assert "enviados_conciliados" not in campana["properties"]
