"""El mensaje en POST /whatsmkt/campanas/previsualizacion, sin base (T-WM-B4b1, parte 1).

El servicio real sobre dobles en memoria: se prueba la traduccion HTTP (el pedido con el mensaje,
la respuesta con `mensaje`, `mensaje_ejemplo` y los problemas con su segmento y sus parametros, el
404 de un mensaje que no es de WhatsMKT y el contrato). Telefonos 900000xxx.
"""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.api.whatsmkt_campanas import obtener_servicio_previa_whatsmkt
from app.core.entities.whatsmkt import ConfiguracionWhatsmkt
from app.main import app
from tests.ayudas.previa_whatsmkt_falsos import (
    DEFINICION_ID,
    MOMENTO,
    RepositorioWhatsmktFalso,
    TextosFalsos,
    servicio_de_previa,
)
from tests.test_whatsmkt_contactos import definicion, producto

RUTA = "/whatsmkt/campanas/previsualizacion"


@pytest.fixture
def cliente():
    estado = {
        "productos": [],
        "textos": TextosFalsos(),
        "whatsmkt": RepositorioWhatsmktFalso(
            configuracion=ConfiguracionWhatsmkt(
                actualizado_en=MOMENTO, whatsapp_contacto="900000123"
            )
        ),
    }
    app.dependency_overrides[obtener_servicio_previa_whatsmkt] = lambda: servicio_de_previa(
        estado["productos"],
        definicion(),
        textos=estado["textos"],
        whatsmkt=estado["whatsmkt"],
    )
    try:
        yield TestClient(app), estado
    finally:
        app.dependency_overrides.clear()


def pedir(cliente, productos, **cambios):
    client, estado = cliente
    estado["productos"] = productos
    cuerpo = {
        "fecha_corte": "2026-11-02",
        "fecha_envio": "2026-11-02",
        "cantidad": 1000,
        "definicion": {"id": DEFINICION_ID},
        "modo": "global",
        **cambios,
    }
    return client.post(RUTA, json=cuerpo)


# --- El mensaje elegido -----------------------------------------------------------------------


def test_el_mensaje_elegido_trae_su_resumen_y_el_ejemplo_con_la_primera_fila(cliente) -> None:
    _, estado = cliente
    estado["textos"].agregar(10, "Hola [$MACRO1$]. INFO por [whatsapp]", nombre="Cobranza")

    respuesta = pedir(cliente, [producto(1, titular="Ana")], mensaje={"texto_guardado_id": 10})

    assert respuesta.status_code == 200
    [campana] = respuesta.json()["campanas"]
    assert campana["mensaje"] == {
        "texto_guardado_id": 10,
        "nombre": "Cobranza",
        "version": 1,
        "deshabilitado": False,
    }
    assert campana["mensaje_ejemplo"] == "Hola Ana. INFO por https://wa.me/+51900000123"
    assert respuesta.json()["problemas"] == []


def test_la_version_pedida_y_la_vigente(cliente) -> None:
    _, estado = cliente
    estado["textos"].agregar(10, "Uno", "Dos")

    vigente = pedir(cliente, [producto(1)], mensaje={"texto_guardado_id": 10})
    primera = pedir(cliente, [producto(1)], mensaje={"texto_guardado_id": 10, "version": 1})

    assert vigente.json()["campanas"][0]["mensaje_ejemplo"] == "Dos"
    assert vigente.json()["campanas"][0]["mensaje"]["version"] == 2
    assert primera.json()["campanas"][0]["mensaje_ejemplo"] == "Uno"


def test_sin_mensaje_la_campana_trae_mensaje_nulo_y_el_pedido_de_antes_sigue_valiendo(
    cliente,
) -> None:
    respuesta = pedir(cliente, [producto(1)])

    [campana] = respuesta.json()["campanas"]
    assert campana["mensaje"] is None and campana["mensaje_ejemplo"] is None
    assert respuesta.json()["problemas"] == []


# --- Los problemas del mensaje ----------------------------------------------------------------


def test_cada_problema_del_mensaje_trae_su_codigo_su_segmento_y_sus_parametros(cliente) -> None:
    _, estado = cliente
    estado["textos"].agregar(10, "Hola [$MACRO7$] 😀")

    respuesta = pedir(cliente, [producto(1)], mensaje={"texto_guardado_id": 10})

    macro, emoji = respuesta.json()["problemas"]
    assert (macro["codigo"], macro["segmento"], macro["parametros"]) == (
        "macro_inexistente",
        None,
        {"macro": "[$MACRO7$]", "n": 2},
    )
    assert emoji["codigo"] == "mensaje_con_emoji"
    assert emoji["parametros"] == {"caracter": "😀", "posicion": 17}
    assert isinstance(emoji["detalle"], str)


def test_un_problema_de_la_campana_trae_segmento_nulo_y_parametros_vacios(cliente) -> None:
    respuesta = pedir(cliente, [producto(1, telefono=None)])

    [problema] = respuesta.json()["problemas"]
    assert problema["codigo"] == "sin_productos"
    assert problema["segmento"] is None and problema["parametros"] == {}


def test_el_largo_usa_el_tope_vigente_de_la_configuracion(cliente) -> None:
    _, estado = cliente
    estado["textos"].agregar(10, "a" * 80)

    cabe = pedir(cliente, [producto(1)], mensaje={"texto_guardado_id": 10})
    estado["whatsmkt"].configuracion = replace(estado["whatsmkt"].configuracion, tope_mensaje=79)
    pasa = pedir(cliente, [producto(1)], mensaje={"texto_guardado_id": 10})

    assert cabe.json()["problemas"] == []
    [problema] = pasa.json()["problemas"]
    assert (problema["codigo"], problema["parametros"]) == (
        "mensaje_largo",
        {"largo": 80, "maximo": 79},
    )


def test_whatsapp_sin_numero_de_contacto_es_sin_whatsapp_y_el_marcador_queda(cliente) -> None:
    _, estado = cliente
    estado["whatsmkt"].configuracion = replace(
        estado["whatsmkt"].configuracion, whatsapp_contacto=None
    )
    estado["textos"].agregar(10, "INFO por [whatsapp]")

    respuesta = pedir(cliente, [producto(1)], mensaje={"texto_guardado_id": 10})

    assert [p["codigo"] for p in respuesta.json()["problemas"]] == ["sin_whatsapp"]
    assert respuesta.json()["campanas"][0]["mensaje_ejemplo"] == "INFO por [whatsapp]"


def test_un_mensaje_deshabilitado_es_un_problema_y_se_previsualiza(cliente) -> None:
    _, estado = cliente
    estado["textos"].agregar(10, "Hola", deshabilitado=True)

    respuesta = pedir(cliente, [producto(1)], mensaje={"texto_guardado_id": 10})

    assert respuesta.status_code == 200
    assert [p["codigo"] for p in respuesta.json()["problemas"]] == ["mensaje_deshabilitado"]
    assert respuesta.json()["campanas"][0]["mensaje"]["deshabilitado"] is True


# --- Por segmento -----------------------------------------------------------------------------


def test_por_segmento_el_mapa_elige_el_mensaje_de_cada_segmento_y_los_problemas_dicen_cual(
    cliente,
) -> None:
    _, estado = cliente
    estado["textos"].agregar(10, "Bien [$MACRO1$]")
    estado["textos"].agregar(11, "Mal [$MACRO9$]")
    productos = [producto(1, -3, titular="A"), producto(2, 5, titular="B")]

    respuesta = pedir(
        cliente,
        productos,
        modo="por_segmento",
        mensajes={
            "preventivo": {"texto_guardado_id": 10},
            "tramo_2": {"texto_guardado_id": 11},
        },
    )

    cuerpo = respuesta.json()
    assert [(c["segmento"], c["mensaje_ejemplo"]) for c in cuerpo["campanas"]] == [
        ("preventivo", "Bien A"),
        ("tramo_2", "Mal [$MACRO9$]"),
    ]
    [problema] = cuerpo["problemas"]
    assert (problema["codigo"], problema["segmento"]) == ("macro_inexistente", "tramo_2")


def test_por_segmento_sin_mapa_cada_segmento_usa_el_mensaje_de_su_configuracion(cliente) -> None:
    _, estado = cliente
    estado["textos"].agregar(10, "Del segmento [$MACRO1$]")
    estado["whatsmkt"].con_texto_en("tramo_2", 10)

    respuesta = pedir(cliente, [producto(1, 5, titular="B")], modo="por_segmento")

    assert respuesta.json()["campanas"][0]["mensaje_ejemplo"] == "Del segmento B"


# --- Errores ----------------------------------------------------------------------------------


def test_un_mensaje_que_no_existe_responde_404_con_su_codigo(cliente) -> None:
    respuesta = pedir(cliente, [producto(1)], mensaje={"texto_guardado_id": 99})

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "texto_guardado_no_encontrado"


def test_un_texto_de_otro_contexto_responde_el_mismo_404(cliente) -> None:
    _, estado = cliente
    estado["textos"].agregar(11, "Hola", contexto="mowa_mes.otro")

    respuesta = pedir(cliente, [producto(1)], mensaje={"texto_guardado_id": 11})

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "texto_guardado_no_encontrado"


def test_una_version_que_no_existe_responde_404_con_su_codigo(cliente) -> None:
    _, estado = cliente
    estado["textos"].agregar(10, "Hola")

    respuesta = pedir(cliente, [producto(1)], mensaje={"texto_guardado_id": 10, "version": 5})

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "version_no_encontrada"


@pytest.mark.parametrize(
    "cambios",
    [
        {"mensajes": {"otro_segmento": {"texto_guardado_id": 10}}},
        {"mensaje": {"texto_guardado_id": 10, "version": 0}},
        {"mensaje": {"texto_guardado_id": "diez"}},
        {"mensaje": {}},
    ],
)
def test_un_pedido_mal_formado_responde_el_422_de_validacion(cliente, cambios) -> None:
    respuesta = pedir(cliente, [producto(1)], **cambios)

    assert respuesta.status_code == 422
    assert isinstance(respuesta.json()["detail"], list)


# --- Contrato ---------------------------------------------------------------------------------


def test_el_contrato_suma_el_mensaje_sin_renombrar_nada_de_la_b4a() -> None:
    esquemas = app.openapi()["components"]["schemas"]

    campana = esquemas["CampanaPrevistaWhatsmktRespuesta"]
    assert {"segmento", "cantidad", "total_exclusiones", "exclusiones", "muestra"} <= set(
        campana["required"]
    )
    assert {"mensaje", "mensaje_ejemplo"} <= set(campana["required"])
    problema = esquemas["ProblemaWhatsmktRespuesta"]
    assert {"codigo", "detalle", "segmento", "parametros"} <= set(problema["required"])
    assert esquemas["MensajeWhatsmktEntrada"]["required"] == ["texto_guardado_id"]
    entrada = esquemas["PrevisualizacionCampanasWhatsmktEntrada"]["properties"]
    assert {"mensaje", "mensajes"} <= set(entrada)
    assert "mensaje" not in esquemas["PrevisualizacionCampanasWhatsmktEntrada"].get("required", [])
