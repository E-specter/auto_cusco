"""GET /whatsmkt/campanas y GET /whatsmkt/campanas/{id}, sin base (T-WM-B4b1, parte 3).

El servicio de lectura real sobre el repositorio en memoria (`tests/ayudas`): los filtros por lote
y por mes, el orden y la paginacion, la ficha con el WhatsApp vigente, las exclusiones de la
campana y las que quedaron fuera del lote, y el 404. Telefonos 900000xxx.
"""

from dataclasses import replace
from datetime import time

import pytest
from fastapi.testclient import TestClient

from app.api.whatsmkt_campanas import (
    obtener_servicio_consulta_whatsmkt,
    obtener_servicio_creacion_whatsmkt,
)
from app.core.entities.whatsmkt import Horario
from app.core.services.plataformas.whatsmkt.consulta import ConsultaCampanasWhatsmktService
from app.main import app
from tests.ayudas.campanas_whatsmkt_falsas import Entorno
from tests.test_api_whatsmkt_campanas_crear import HOLA, RUTA, cuerpo
from tests.test_whatsmkt_contactos import producto

SEGMENTOS = dict.fromkeys(("preventivo", "tramo_2", "mayores_2"), {"texto_guardado_id": 10})
POR_SEGMENTO = {"modo": "por_segmento", "mensaje": None, "mensajes": SEGMENTOS}


@pytest.fixture
def cliente():
    e = Entorno([producto(1, 0), producto(2, 0)])
    e.textos.agregar(10, HOLA, nombre="Cobranza")
    e.textos.agregar(11, "Hola [$MACRO1$]", nombre="Sin enlace")
    e.whatsmkt.configuracion = replace(e.whatsmkt.configuracion, whatsapp_contacto="900000123")
    app.dependency_overrides[obtener_servicio_creacion_whatsmkt] = e.servicio
    app.dependency_overrides[obtener_servicio_consulta_whatsmkt] = lambda: (
        ConsultaCampanasWhatsmktService(e.campanas, e.whatsmkt)
    )
    try:
        yield TestClient(app), e
    finally:
        app.dependency_overrides.clear()


def crear(cliente, **cambios):
    client, _ = cliente
    respuesta = client.post(RUTA, json=cuerpo(**cambios))
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def ids(respuesta) -> list[int]:
    return [c["id"] for c in respuesta.json()["campanas"]]


def tres_lotes(cliente) -> None:
    """Lote 1 (campana 1, global), lote 2 (campanas 2 y 3, por segmento) y lote 3 (campana 4)."""
    client, e = cliente
    crear(cliente)
    e.productos = [producto(1, -3), producto(2, 5)]
    crear(cliente, **POR_SEGMENTO)
    crear(cliente)


# --- La lista ---------------------------------------------------------------------------------


def test_cada_fila_de_la_lista_trae_sus_datos(cliente) -> None:
    client, _ = cliente
    crear(cliente, horarios=["horario_1", "horario_2"])

    respuesta = client.get(RUTA)

    assert respuesta.status_code == 200
    cuerpo_ = respuesta.json()
    assert (cuerpo_["total"], cuerpo_["limite"], cuerpo_["desplazamiento"]) == (1, 50, 0)
    [fila] = cuerpo_["campanas"]
    assert fila == {
        "id": 1,
        "nombre": "CUZCO_Vencida whatsapp 2026.11.02",
        "lote_id": 1,
        "segmento": None,
        "segmento_etiqueta": None,
        "fecha_envio": "2026-11-03",
        "horarios": [
            {"nombre": "horario_1", "inicio": "08:00", "fin": "14:00"},
            {"nombre": "horario_2", "inicio": "14:00", "fin": "20:00"},
        ],
        "cantidad": 4,
        "creada_en": fila["creada_en"],
        "descartada_en": None,
        "con_informe": False,
    }
    assert fila["creada_en"].startswith("2026-11-03T")


def test_una_campana_por_segmento_trae_su_clave_y_su_etiqueta(cliente) -> None:
    client, e = cliente
    e.productos = [producto(1, -3), producto(2, 5)]
    crear(cliente, **POR_SEGMENTO)

    filas = client.get(RUTA).json()["campanas"]

    assert sorted((f["segmento"], f["segmento_etiqueta"]) for f in filas) == [
        ("preventivo", "Preventivo"),
        ("tramo_2", "Tramo 2"),
    ]


def test_sin_campanas_la_lista_viene_vacia(cliente) -> None:
    client, _ = cliente

    assert client.get(RUTA).json() == {
        "total": 0,
        "limite": 50,
        "desplazamiento": 0,
        "campanas": [],
        "total_activas": 0,
        "total_descartadas": 0,
        "total_pendientes": 0,
    }


def test_las_mas_recientes_primero_y_a_igual_instante_el_id_mayor(cliente) -> None:
    client, _ = cliente
    tres_lotes(cliente)

    assert ids(client.get(RUTA)) == [4, 3, 2, 1]


def test_la_paginacion_devuelve_el_total_de_todas_y_la_pagina_pedida(cliente) -> None:
    client, _ = cliente
    tres_lotes(cliente)

    pagina = client.get(RUTA, params={"limite": 2, "desplazamiento": 1}).json()

    assert (pagina["total"], pagina["limite"], pagina["desplazamiento"]) == (4, 2, 1)
    assert [c["id"] for c in pagina["campanas"]] == [3, 2]
    assert ids(client.get(RUTA, params={"limite": 2, "desplazamiento": 3})) == [1]
    assert ids(client.get(RUTA, params={"desplazamiento": 9})) == []


@pytest.mark.parametrize(
    "params",
    [{"limite": 0}, {"limite": 501}, {"desplazamiento": -1}, {"lote_id": 0}, {"lote_id": "x"}],
)
def test_una_paginacion_o_un_lote_fuera_de_rango_responde_422(cliente, params) -> None:
    client, _ = cliente

    assert client.get(RUTA, params=params).status_code == 422


# --- Los filtros ------------------------------------------------------------------------------


def test_el_filtro_por_lote_deja_solo_las_campanas_de_ese_lote(cliente) -> None:
    client, _ = cliente
    tres_lotes(cliente)

    en_el_2 = client.get(RUTA, params={"lote_id": 2}).json()

    assert (en_el_2["total"], [c["id"] for c in en_el_2["campanas"]]) == (2, [3, 2])
    assert {c["lote_id"] for c in en_el_2["campanas"]} == {2}
    assert client.get(RUTA, params={"lote_id": 99}).json()["total"] == 0


def test_el_filtro_por_mes_usa_el_mes_de_la_fecha_de_envio(cliente) -> None:
    client, _ = cliente
    # 31 de octubre y 1 de noviembre: el limite entre un mes y el siguiente.
    crear(cliente, fecha_corte="2026-10-30", fecha_envio="2026-10-31")  # 1
    crear(cliente, fecha_corte="2026-10-30", fecha_envio="2026-11-01")  # 2
    crear(cliente, fecha_corte="2026-11-02", fecha_envio="2026-11-30")  # 3
    crear(cliente, fecha_corte="2026-11-02", fecha_envio="2026-12-01")  # 4

    def del_mes(mes: str) -> list[int]:
        return ids(client.get(RUTA, params={"mes": mes}))

    assert del_mes("2026-10") == [1]
    assert del_mes("2026-11") == [3, 2]
    assert del_mes("2026-12") == [4]
    assert del_mes("2027-01") == []
    assert client.get(RUTA, params={"mes": "2026-11"}).json()["total"] == 2


@pytest.mark.parametrize("mes", ["2026-13", "2026-00", "2026-1", "2026/11", "noviembre"])
def test_un_mes_mal_escrito_responde_422(cliente, mes) -> None:
    client, _ = cliente

    assert client.get(RUTA, params={"mes": mes}).status_code == 422


def test_los_filtros_de_lote_y_de_mes_se_combinan(cliente) -> None:
    client, _ = cliente
    crear(cliente, fecha_corte="2026-10-27", fecha_envio="2026-10-29")  # 1, lote 1
    crear(cliente)  # 2, lote 2
    crear(cliente, fecha_corte="2026-10-27", fecha_envio="2026-10-30")  # 3, lote 3

    assert ids(client.get(RUTA, params={"mes": "2026-10"})) == [3, 1]
    assert ids(client.get(RUTA, params={"mes": "2026-10", "lote_id": 3})) == [3]
    assert ids(client.get(RUTA, params={"mes": "2026-10", "lote_id": 2})) == []


# --- El detalle: la ficha ---------------------------------------------------------------------


def test_el_detalle_trae_la_ficha_completa_su_lote_y_su_archivo(cliente) -> None:
    client, _ = cliente
    crear(cliente, horarios=["horario_2"], lo_antes_posible=True)

    respuesta = client.get(f"{RUTA}/1")

    assert respuesta.status_code == 200
    d = respuesta.json()
    assert (d["id"], d["lote"], d["segmento"]) == (1, {"id": 1, "modo": "global"}, None)
    assert (d["fecha_corte"], d["fecha_envio"]) == ("2026-11-02", "2026-11-03")
    assert (d["productos"], d["supervisores"], d["cantidad"]) == (2, 2, 4)
    assert (d["definicion_nombre"], d["definicion_version"], d["texto_version"]) == (
        "WhatsMKT prueba",
        1,
        1,
    )
    assert d["archivo"]["nombre"] == "CUZCO_Vencida whatsapp 2026.11.02.xlsx"
    assert d["archivo"]["filas"] == 4 and d["archivo"]["tamano"] > 0
    assert d["ficha"] == {
        "nombre": "CUZCO_Vencida whatsapp 2026.11.02",
        "fecha_envio": "2026-11-03",
        "horarios": [{"nombre": "horario_2", "inicio": "14:00", "fin": "20:00"}],
        "lo_antes_posible": True,
        "pais": "Perú",
        "foto_id": None,
        "cantidad": 4,
        "tipo_envio": "solo_texto",
        "adjunto_id": None,
        "etiqueta_vcard": None,
        "mensaje": "Hola [$MACRO1$], tu pagare es [$MACRO2$]. INFO por https://wa.me/+51900000123",
        "avisos": [],
    }


def test_el_detalle_de_una_campana_por_segmento_trae_su_segmento_y_el_modo_del_lote(
    cliente,
) -> None:
    client, e = cliente
    e.productos = [producto(1, -3), producto(2, 5)]
    crear(cliente, **POR_SEGMENTO)

    d = client.get(f"{RUTA}/2").json()

    assert (d["segmento"], d["segmento_etiqueta"]) == ("tramo_2", "Tramo 2")
    assert d["lote"] == {"id": 1, "modo": "por_segmento"}
    assert d["nombre"] == "CUZCO_Vencida (Tramo 2) whatsapp 2026.11.02"


def test_el_mensaje_de_la_ficha_usa_el_whatsapp_vigente_no_el_del_dia_que_se_creo(
    cliente,
) -> None:
    client, e = cliente
    crear(cliente)

    e.whatsmkt.configuracion = replace(e.whatsmkt.configuracion, whatsapp_contacto="900000999")
    ficha = client.get(f"{RUTA}/1").json()["ficha"]

    assert ficha["mensaje"].endswith("INFO por https://wa.me/+51900000999")
    assert ficha["avisos"] == []


def test_sin_whatsapp_vigente_queda_el_marcador_y_la_ficha_trae_el_aviso(cliente) -> None:
    client, e = cliente
    crear(cliente)

    e.whatsmkt.configuracion = replace(e.whatsmkt.configuracion, whatsapp_contacto=None)
    ficha = client.get(f"{RUTA}/1").json()["ficha"]

    assert ficha["mensaje"].endswith("INFO por [whatsapp]")
    assert ficha["avisos"] == ["sin_whatsapp"]


def test_un_mensaje_que_no_usa_whatsapp_no_trae_aviso_aunque_no_haya_numero(cliente) -> None:
    client, e = cliente
    crear(cliente, mensaje={"texto_guardado_id": 11})

    e.whatsmkt.configuracion = replace(e.whatsmkt.configuracion, whatsapp_contacto=None)
    ficha = client.get(f"{RUTA}/1").json()["ficha"]

    assert ficha["mensaje"] == "Hola [$MACRO1$]"
    assert ficha["avisos"] == []


def test_lo_demas_de_la_ficha_queda_congelado_aunque_cambien_la_configuracion_y_el_mensaje(
    cliente,
) -> None:
    client, e = cliente
    crear(cliente)
    antes = client.get(f"{RUTA}/1").json()

    e.whatsmkt.configuracion = replace(
        e.whatsmkt.configuracion,
        horario_1=Horario(time(9), time(10)),
        plantilla_nombre="Otra {fecha_corte}",
    )
    e.textos.agregar(10, "Otro texto", "Otro mas", nombre="Cobranza cambiada")
    despues = client.get(f"{RUTA}/1").json()

    assert despues == antes


# --- El detalle: las exclusiones --------------------------------------------------------------


def lote_con_exclusiones(cliente) -> None:
    """Preventivo y tramo 2 con una exclusion cada uno, y dos productos sin dias de atraso."""
    _, e = cliente
    e.productos = [
        producto(1, -3),
        producto(2, -3, telefono=None),  # preventivo: sin telefono
        producto(3, 5),
        producto(4, 5, telefono=None),  # tramo 2: sin telefono
        producto(5, 5, telefono=None),  # tramo 2: sin telefono
        producto(6, None),  # sin dias de atraso: no cae en ninguna campana
        producto(7, None),
    ]
    crear(cliente, **POR_SEGMENTO)


def test_las_exclusiones_de_la_campana_son_las_suyas_y_traen_su_total(cliente) -> None:
    client, _ = cliente
    lote_con_exclusiones(cliente)

    preventivo = client.get(f"{RUTA}/1").json()
    tramo_2 = client.get(f"{RUTA}/2").json()

    assert (preventivo["segmento"], preventivo["exclusiones"]["total"]) == ("preventivo", 1)
    assert (tramo_2["segmento"], tramo_2["exclusiones"]["total"]) == ("tramo_2", 2)
    assert [(e["codigo"], e["pagare"]) for e in tramo_2["exclusiones"]["exclusiones"]] == [
        ("sin_telefono", f"{4:018d}"),
        ("sin_telefono", f"{5:018d}"),
    ]
    assert (tramo_2["exclusiones"]["limite"], tramo_2["exclusiones"]["desplazamiento"]) == (100, 0)


def test_las_exclusiones_de_la_campana_se_paginan_con_su_total_intacto(cliente) -> None:
    client, _ = cliente
    lote_con_exclusiones(cliente)

    pagina = client.get(
        f"{RUTA}/2", params={"exclusiones_limite": 1, "exclusiones_desplazamiento": 1}
    ).json()["exclusiones"]

    assert (pagina["total"], pagina["limite"], pagina["desplazamiento"]) == (2, 1, 1)
    assert [e["pagare"] for e in pagina["exclusiones"]] == [f"{5:018d}"]


def test_los_productos_fuera_del_lote_se_ven_desde_cualquier_campana_del_lote(cliente) -> None:
    client, _ = cliente
    lote_con_exclusiones(cliente)

    desde_preventivo = client.get(f"{RUTA}/1").json()["exclusiones_fuera_del_lote"]
    desde_tramo_2 = client.get(f"{RUTA}/2").json()["exclusiones_fuera_del_lote"]

    assert desde_preventivo == desde_tramo_2  # la misma lista: no es de ninguna campana
    assert desde_tramo_2["total"] == 2
    assert [(e["codigo"], e["pagare"]) for e in desde_tramo_2["exclusiones"]] == [
        ("sin_dias_atraso", f"{6:018d}"),
        ("sin_dias_atraso", f"{7:018d}"),
    ]
    # Y no se mezclan con las de la campana.
    propias = {e["pagare"] for e in client.get(f"{RUTA}/2").json()["exclusiones"]["exclusiones"]}
    assert propias.isdisjoint({e["pagare"] for e in desde_tramo_2["exclusiones"]})


def test_los_productos_fuera_del_lote_tienen_su_propia_paginacion(cliente) -> None:
    client, _ = cliente
    lote_con_exclusiones(cliente)

    d = client.get(
        f"{RUTA}/2",
        params={"fuera_del_lote_limite": 1, "fuera_del_lote_desplazamiento": 1},
    ).json()

    fuera = d["exclusiones_fuera_del_lote"]
    assert (fuera["total"], fuera["limite"], fuera["desplazamiento"]) == (2, 1, 1)
    assert [e["pagare"] for e in fuera["exclusiones"]] == [f"{7:018d}"]
    assert d["exclusiones"]["limite"] == 100  # la otra lista no se movio


def test_no_se_mezclan_los_productos_fuera_de_un_lote_con_los_de_otro(cliente) -> None:
    client, _ = cliente
    lote_con_exclusiones(cliente)  # lote 1: campanas 1 y 2, dos fuera
    _, e = cliente
    e.productos = [producto(1, -3), producto(2, None)]
    crear(cliente, **POR_SEGMENTO)  # lote 2: campana 3, uno fuera

    assert client.get(f"{RUTA}/2").json()["exclusiones_fuera_del_lote"]["total"] == 2
    assert client.get(f"{RUTA}/3").json()["exclusiones_fuera_del_lote"]["total"] == 1


def test_en_un_lote_global_no_hay_productos_fuera_del_lote(cliente) -> None:
    client, e = cliente
    e.productos = [producto(1, 0), producto(2, None, telefono=None), producto(3, None)]
    crear(cliente)

    d = client.get(f"{RUTA}/1").json()

    assert d["lote"]["modo"] == "global"
    assert d["exclusiones"]["total"] == 1  # el de sin telefono: es de la campana
    assert d["exclusiones_fuera_del_lote"] == {
        "total": 0,
        "limite": 100,
        "desplazamiento": 0,
        "exclusiones": [],
    }


# --- 404, validacion y contrato ---------------------------------------------------------------


def test_el_detalle_de_una_campana_que_no_existe_responde_404(cliente) -> None:
    client, _ = cliente

    respuesta = client.get(f"{RUTA}/99")

    assert respuesta.status_code == 404
    assert "99" in respuesta.json()["detail"]
    assert respuesta.json()["codigo"] is None


@pytest.mark.parametrize(
    "params",
    [
        {"exclusiones_limite": 0},
        {"exclusiones_limite": 1001},
        {"exclusiones_desplazamiento": -1},
        {"fuera_del_lote_limite": 0},
        {"fuera_del_lote_desplazamiento": -1},
    ],
)
def test_una_paginacion_de_exclusiones_fuera_de_rango_responde_422(cliente, params) -> None:
    client, _ = cliente
    crear(cliente)

    assert client.get(f"{RUTA}/1", params=params).status_code == 422


def test_el_contrato_declara_la_lista_y_el_detalle() -> None:
    esquema = app.openapi()
    lista = esquema["paths"][RUTA]["get"]
    detalle = esquema["paths"][f"{RUTA}/{{campana_id}}"]["get"]
    schemas = esquema["components"]["schemas"]

    assert {p["name"] for p in lista["parameters"]} == {
        "limite",
        "desplazamiento",
        "lote_id",
        "mes",
        "estado",
    }
    assert {p["name"] for p in detalle["parameters"]} == {
        "campana_id",
        "exclusiones_limite",
        "exclusiones_desplazamiento",
        "fuera_del_lote_limite",
        "fuera_del_lote_desplazamiento",
    }
    assert "404" in detalle["responses"]
    assert set(schemas["DetalleCampanaWhatsmktRespuesta"]["properties"]) >= {
        "lote",
        "ficha",
        "exclusiones",
        "exclusiones_fuera_del_lote",
    }
    assert "avisos" in schemas["FichaWhatsmktRespuesta"]["required"]
    assert "descartada_en" in schemas["ResumenCampanaWhatsmktRespuesta"]["required"]
