"""POST /whatsmkt/campanas y GET /whatsmkt/campanas/{id}/archivo, sin base (T-WM-B4b1, parte 2).

El servicio real sobre dobles en memoria (`tests/ayudas/campanas_whatsmkt_falsas.py`): se prueba la
traduccion HTTP (el 201 con la ficha, el 422 con todos los problemas y los parametros del primero,
los 404, la descarga byte a byte despues de cambiar la configuracion y el mensaje, y el contrato).
Telefonos 900000xxx.
"""

from dataclasses import replace
from datetime import time

import pytest
from fastapi.testclient import TestClient

from app.api.whatsmkt_campanas import (
    obtener_repositorio_campanas_whatsmkt,
    obtener_servicio_creacion_whatsmkt,
)
from app.core.entities.whatsmkt import Horario
from app.main import app
from tests.ayudas import adjuntos_sinteticos as sint
from tests.ayudas.campanas_whatsmkt_falsas import Entorno
from tests.ayudas.previa_whatsmkt_falsos import DEFINICION_ID
from tests.test_whatsmkt_contactos import producto

RUTA = "/whatsmkt/campanas"
HOLA = "Hola [$MACRO1$], tu pagare es [$MACRO2$]. INFO por [whatsapp]"


@pytest.fixture
def cliente():
    e = Entorno([producto(1, titular="Ana"), producto(2, titular="Bea")])
    e.textos.agregar(10, HOLA, nombre="Cobranza")
    e.whatsmkt.configuracion = replace(e.whatsmkt.configuracion, whatsapp_contacto="900000123")
    app.dependency_overrides[obtener_servicio_creacion_whatsmkt] = e.servicio
    app.dependency_overrides[obtener_repositorio_campanas_whatsmkt] = lambda: e.campanas
    try:
        yield TestClient(app), e
    finally:
        app.dependency_overrides.clear()


def cuerpo(**cambios) -> dict:
    base = {
        "fecha_corte": "2026-11-02",
        "fecha_envio": "2026-11-03",
        "cantidad": 1000,
        "filtros": ["dias_atraso:mayor_igual:0"],
        "orden": "-dias_atraso",
        "definicion": {"id": DEFINICION_ID},
        "modo": "global",
        "mensaje": {"texto_guardado_id": 10},
        "horarios": ["horario_1"],
    }
    return {**base, **cambios}


def crear(cliente, **cambios):
    client, _ = cliente
    return client.post(RUTA, json=cuerpo(**cambios))


# --- 201 con la ficha -------------------------------------------------------------------------


def test_crear_responde_201_con_cada_campana_su_archivo_y_su_ficha(cliente) -> None:
    respuesta = crear(cliente, horarios=["horario_1", "horario_2"], lo_antes_posible=True)

    assert respuesta.status_code == 201
    [campana] = respuesta.json()
    assert (campana["id"], campana["lote_id"], campana["segmento"]) == (1, 1, None)
    assert campana["nombre"] == "CUZCO_Vencida whatsapp 2026.11.02"
    assert campana["archivo"]["nombre"] == "CUZCO_Vencida whatsapp 2026.11.02.xlsx"
    assert campana["archivo"]["filas"] == 4 and campana["archivo"]["tamano"] > 0
    ficha = campana["ficha"]
    assert ficha["nombre"] == campana["nombre"]
    assert ficha["fecha_envio"] == "2026-11-03"
    assert ficha["horarios"] == [
        {"nombre": "horario_1", "inicio": "08:00", "fin": "14:00"},
        {"nombre": "horario_2", "inicio": "14:00", "fin": "20:00"},
    ]
    assert (ficha["lo_antes_posible"], ficha["pais"], ficha["cantidad"]) == (True, "Perú", 4)
    assert ficha["tipo_envio"] == "solo_texto"
    assert (ficha["foto_id"], ficha["adjunto_id"], ficha["etiqueta_vcard"]) == (None, None, None)
    # El mensaje para copiar: [whatsapp] ya es el enlace; las macros quedan tal cual.
    assert ficha["mensaje"] == (
        "Hola [$MACRO1$], tu pagare es [$MACRO2$]. INFO por https://wa.me/+51900000123"
    )


def test_un_lote_por_segmento_responde_una_campana_por_segmento(cliente) -> None:
    _, e = cliente
    e.productos = [producto(1, -3), producto(2, 5)]
    segmentos = dict.fromkeys(("preventivo", "tramo_2", "mayores_2"), {"texto_guardado_id": 10})

    respuesta = crear(cliente, modo="por_segmento", mensaje=None, mensajes=segmentos)

    assert respuesta.status_code == 201
    assert [(c["id"], c["lote_id"], c["segmento"]) for c in respuesta.json()] == [
        (1, 1, "preventivo"),
        (2, 1, "tramo_2"),
    ]


def test_el_nombre_pedido_y_los_nombres_por_segmento(cliente) -> None:
    _, e = cliente
    e.productos = [producto(1, -3), producto(2, 5)]
    segmentos = dict.fromkeys(("preventivo", "tramo_2", "mayores_2"), {"texto_guardado_id": 10})

    global_ = crear(cliente, nombre="  Mi campana  ")
    lote = crear(
        cliente,
        modo="por_segmento",
        mensaje=None,
        mensajes=segmentos,
        nombres={"tramo_2": "Dos"},
    )

    assert global_.json()[0]["nombre"] == "Mi campana"
    assert [c["nombre"] for c in lote.json()] == [
        "CUZCO_Vencida (Preventivo) whatsapp 2026.11.02",
        "Dos",
    ]


def test_el_tipo_archivo_la_foto_y_la_vcard_se_guardan_en_la_ficha(cliente) -> None:
    _, e = cliente
    from app.core.services.plataformas.whatsmkt.biblioteca import BibliotecaWhatsmktService

    biblioteca = BibliotecaWhatsmktService(e.adjuntos)
    foto, _ = biblioteca.guardar("yo.jpg", sint.jpeg(200, 200), como_foto=True)
    pdf, _ = biblioteca.guardar("informe.pdf", sint.PDF)

    con_archivo = crear(cliente, tipo_envio="archivo", adjunto_id=pdf.id, foto_id=foto.id)
    con_vcard = crear(cliente, tipo_envio="vcard", etiqueta_vcard="  Caja Cusco ")

    f1, f2 = con_archivo.json()[0]["ficha"], con_vcard.json()[0]["ficha"]
    assert (f1["tipo_envio"], f1["adjunto_id"], f1["foto_id"]) == ("archivo", pdf.id, foto.id)
    assert (f2["tipo_envio"], f2["etiqueta_vcard"], f2["adjunto_id"]) == (
        "vcard",
        "Caja Cusco",
        None,
    )


def test_solo_se_manda_lo_del_tipo_elegido(cliente) -> None:
    # Cambiar de tipo conserva lo escrito en la pantalla, pero la API solo guarda lo del tipo.
    respuesta = crear(cliente, tipo_envio="solo_texto", adjunto_id=7, etiqueta_vcard="Sobra")

    ficha = respuesta.json()[0]["ficha"]
    assert (ficha["adjunto_id"], ficha["etiqueta_vcard"]) == (None, None)


def test_un_sabado_se_acepta_como_fecha_de_envio(cliente) -> None:
    respuesta = crear(cliente, fecha_envio="2026-11-07")

    assert respuesta.status_code == 201
    assert respuesta.json()[0]["ficha"]["fecha_envio"] == "2026-11-07"


# --- 422 con todos los problemas --------------------------------------------------------------


def test_sin_horario_responde_422_con_su_codigo_y_no_guarda_nada(cliente) -> None:
    _, e = cliente

    respuesta = crear(cliente, horarios=[])

    assert respuesta.status_code == 422
    cuerpo_ = respuesta.json()
    assert cuerpo_["codigo"] == "sin_horario"
    assert [p["codigo"] for p in cuerpo_["problemas"]] == ["sin_horario"]
    assert isinstance(cuerpo_["detail"], str)
    assert e.campanas.lotes == []


def test_el_422_trae_todos_los_problemas_y_los_parametros_del_primero(cliente) -> None:
    _, e = cliente
    e.textos.agregar(11, "Hola [$MACRO9$]")

    respuesta = crear(cliente, horarios=[], mensaje={"texto_guardado_id": 11})

    cuerpo_ = respuesta.json()
    assert cuerpo_["codigo"] == "sin_horario"
    assert [p["codigo"] for p in cuerpo_["problemas"]] == ["sin_horario", "macro_inexistente"]
    macro = cuerpo_["problemas"][1]
    assert macro["parametros"] == {"macro": "[$MACRO9$]", "n": 2}
    # Los parametros del primero siempre viajan (nulos si no los usa).
    assert cuerpo_["peso"] is None and cuerpo_["ancho"] is None and cuerpo_["horarios"] is None


def test_sin_mensaje_responde_422(cliente) -> None:
    respuesta = crear(cliente, mensaje=None)

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "sin_mensaje"


def test_sin_supervisores_responde_422(cliente) -> None:
    _, e = cliente
    e.supervisores = ()

    assert crear(cliente).json()["codigo"] == "sin_supervisores"


def test_un_mensaje_que_usa_whatsapp_sin_numero_de_contacto_responde_422(cliente) -> None:
    _, e = cliente
    e.whatsmkt.configuracion = replace(e.whatsmkt.configuracion, whatsapp_contacto=None)

    assert crear(cliente).json()["codigo"] == "sin_whatsapp"


def test_un_nombre_largo_trae_el_largo_en_los_parametros(cliente) -> None:
    respuesta = crear(cliente, nombre="a" * 80)

    [problema] = respuesta.json()["problemas"]
    assert (problema["codigo"], problema["parametros"]) == ("nombre_largo", {"largo": 80})


def test_una_foto_invalida_responde_422_con_sus_medidas(cliente) -> None:
    _, e = cliente
    from app.core.services.plataformas.whatsmkt.biblioteca import BibliotecaWhatsmktService

    foto, _ = BibliotecaWhatsmktService(e.adjuntos).guardar("x.jpg", sint.jpeg(300, 150))

    respuesta = crear(cliente, foto_id=foto.id)

    assert respuesta.status_code == 422
    cuerpo_ = respuesta.json()
    assert cuerpo_["codigo"] == "foto_medidas"
    assert (cuerpo_["ancho"], cuerpo_["alto"]) == (300, 150)
    assert e.campanas.lotes == []


# --- 404 y 422 de validacion ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cambios", "codigo"),
    [
        ({"foto_id": 99}, None),
        ({"definicion": {"id": 99}}, "definicion_no_encontrada"),
        ({"mensaje": {"texto_guardado_id": 99}}, "texto_guardado_no_encontrado"),
        ({"mensaje": {"texto_guardado_id": 10, "version": 9}}, "version_no_encontrada"),
        ({"tipo_envio": "archivo", "adjunto_id": 99}, None),
    ],
)
def test_lo_que_no_existe_responde_404_y_no_guarda_nada(cliente, cambios, codigo) -> None:
    _, e = cliente

    respuesta = crear(cliente, **cambios)

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == codigo
    assert e.campanas.lotes == []


@pytest.mark.parametrize(
    "cambios",
    [
        {"tipo_envio": "archivo"},  # sin adjunto_id
        {"tipo_envio": "vcard"},  # sin etiqueta
        {"tipo_envio": "vcard", "etiqueta_vcard": "   "},
        {"tipo_envio": "otro"},
        {"horarios": ["horario_3"]},
        {"nombres": 5},
    ],
)
def test_un_pedido_mal_formado_responde_el_422_de_validacion(cliente, cambios) -> None:
    respuesta = crear(cliente, **cambios)

    assert respuesta.status_code == 422
    assert isinstance(respuesta.json()["detail"], list)


# --- La descarga ------------------------------------------------------------------------------


def test_la_descarga_da_los_bytes_guardados_aunque_cambien_la_configuracion_y_el_mensaje(
    cliente,
) -> None:
    client, e = cliente
    creada = crear(cliente).json()[0]
    primera = client.get(f"{RUTA}/{creada['id']}/archivo")

    # Cambia la configuracion (horarios, WhatsApp, tope, plantilla) Y el mensaje (version nueva y
    # el texto de la anterior).
    e.whatsmkt.configuracion = replace(
        e.whatsmkt.configuracion,
        horario_1=Horario(time(9), time(10)),
        whatsapp_contacto="900000999",
        tope_mensaje=5,
        plantilla_nombre="Otra {fecha_corte}",
    )
    e.textos.agregar(10, "Otro texto", "Otro mas", nombre="Cobranza cambiada")
    segunda = client.get(f"{RUTA}/{creada['id']}/archivo")

    assert primera.status_code == 200
    assert primera.content[:2] == b"PK"
    assert len(primera.content) == creada["archivo"]["tamano"]
    assert segunda.content == primera.content  # byte a byte
    assert primera.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert (
        'filename="CUZCO_Vencida whatsapp 2026.11.02.xlsx"'
        in primera.headers["content-disposition"]
    )


def test_la_descarga_de_una_campana_que_no_existe_responde_404(cliente) -> None:
    client, _ = cliente

    respuesta = client.get(f"{RUTA}/99/archivo")

    assert respuesta.status_code == 404
    assert isinstance(respuesta.json()["detail"], str)


# --- Contrato ---------------------------------------------------------------------------------


def test_el_contrato_declara_la_creacion_y_la_descarga() -> None:
    esquema = app.openapi()
    crear_ = esquema["paths"][RUTA]["post"]
    schemas = esquema["components"]["schemas"]

    assert crear_["responses"]["201"]["content"]["application/json"]["schema"]["items"][
        "$ref"
    ].endswith("/CampanaCreadaWhatsmktRespuesta")
    assert {"201", "400", "404", "422"} <= set(crear_["responses"])
    assert crear_["responses"]["422"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ErrorCreacionWhatsmktRespuesta"
    )
    assert {"detail", "codigo", "problemas"} <= set(
        schemas["ErrorCreacionWhatsmktRespuesta"]["required"]
    )
    assert {"id", "lote_id", "nombre", "segmento", "archivo", "ficha"} <= set(
        schemas["CampanaCreadaWhatsmktRespuesta"]["required"]
    )
    assert {"horarios", "tipo_envio"} <= set(
        schemas["CreacionCampanasWhatsmktEntrada"]["properties"]
    )
    descarga = esquema["paths"][f"{RUTA}/{{campana_id}}/archivo"]["get"]["responses"]
    assert {"200", "404"} <= set(descarga)
    assert "Content-Disposition" in descarga["200"]["headers"]
