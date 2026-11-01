"""Los endpoints del speech de MOWA MES (B6, M2; desde M-B4 solo v2): crear, editar, previsualizar.

Sobre el repositorio en memoria; la campana con una v2 (previsualizar, crear y el 409 de la huella)
usa el entorno de `test_api_mowa_mes_campanas.py`. La integracion con PostgreSQL esta en
`test_mowa_mes_speech_v2_postgres.py`. Datos sinteticos.
"""

from dataclasses import replace
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api.mowa_mes import obtener_servicio_mowa_mes
from app.core.entities.mowa_mes import RANGOS_SEGMENTO, DatosSpeech
from app.core.services.plataformas.mowa_mes.campana import huella_de
from app.core.services.plataformas.mowa_mes.configuracion import ConfiguracionMowaMesService
from app.main import app
from tests.test_api_mowa_mes_campanas import CUERPO, Entorno, _cliente, producto
from tests.test_mowa_mes_speech import ORIGINAL, WHATSAPP, RepositorioMowaMesFalso

SEGMENTOS = [rango.segmento.value for rango in RANGOS_SEGMENTO]


@pytest.fixture
def cliente():
    repositorio = RepositorioMowaMesFalso(WHATSAPP)
    servicio = ConfiguracionMowaMesService(repositorio)
    app.dependency_overrides[obtener_servicio_mowa_mes] = lambda: servicio
    try:
        yield TestClient(app), repositorio
    finally:
        app.dependency_overrides.clear()


def _texto(valor: str) -> dict:
    return {"tipo": "texto", "valor": valor}


def _variable(nombre: str, *funciones: dict) -> dict:
    return {"tipo": "variable", "nombre": nombre, "funciones": list(funciones)}


def _funcion(nombre: str, *args) -> dict:
    return {"nombre": nombre, "args": list(args)}


def _fecha() -> dict:
    return _variable("fecha_vencimiento_cuota", _funcion("formato_fecha", "dd/mm/aaaa"))


def _por_segmento(*nodos: dict, **distintos: tuple) -> list[dict]:
    """El mismo contenido en los 6 segmentos, salvo los que se den por clave de segmento."""
    return [
        {"segmento": s, "expresion": {"nodos": list(distintos.get(f"s_{s}", nodos))}}
        for s in SEGMENTOS
    ]


CUERPO_V2 = _por_segmento(
    _variable("titular", _funcion("primeros", 8)), _texto(" vence el "), _fecha()
)


def _crear(client, expresiones=None, **extra):
    cuerpo = {"nombre": "Mi speech v2", "expresiones": expresiones or CUERPO_V2, **extra}
    return client.post("/mowa-mes/speech", json=cuerpo)


# --- Crear ----------------------------------------------------------------------------------------


def test_se_crea_una_v2_con_una_expresion_por_segmento(cliente) -> None:
    client, _ = cliente

    respuesta = _crear(client)

    cuerpo = respuesta.json()
    assert respuesta.status_code == 201
    assert cuerpo["nombre"] == "Mi speech v2"
    assert "formato" not in cuerpo and "partes" not in cuerpo  # M-B4: solo hay v2
    assert [e["segmento"] for e in cuerpo["expresiones"]] == SEGMENTOS
    assert (cuerpo["original"], cuerpo["usada"], cuerpo["editable"]) == (False, False, True)
    primero = cuerpo["expresiones"][0]
    assert (primero["etiqueta"], primero["dias_desde"], primero["dias_hasta"]) == (
        "Preventiva",
        None,
        0,
    )
    assert (primero["usa_titular"], primero["usa_vencimiento"], primero["usa_whatsapp"]) == (
        True,
        True,
        False,
    )
    assert [n["tipo"] for n in primero["expresion"]["nodos"]] == ["variable", "texto", "variable"]


def test_los_segmentos_se_guardan_en_el_orden_del_negocio_aunque_lleguen_al_reves(cliente) -> None:
    client, _ = cliente

    creada = _crear(client, expresiones=list(reversed(CUERPO_V2))).json()

    assert [e["segmento"] for e in creada["expresiones"]] == SEGMENTOS
    assert client.get(f"/mowa-mes/speech/{creada['id']}").json() == creada


def test_la_v2_creada_se_lee_y_se_lista_igual(cliente) -> None:
    client, _ = cliente
    creada = _crear(client).json()

    leida = client.get(f"/mowa-mes/speech/{creada['id']}").json()
    listada = [v for v in client.get("/mowa-mes/speech").json() if v["id"] == creada["id"]]

    assert leida == creada
    assert listada == [creada]


def test_una_v2_sin_nombre_recibe_el_siguiente_speech_n(cliente) -> None:
    client, _ = cliente

    cuerpo = client.post("/mowa-mes/speech", json={"expresiones": CUERPO_V2}).json()

    assert cuerpo["nombre"] == "Speech 2"


def test_se_marca_de_cual_se_basa(cliente) -> None:
    client, _ = cliente

    cuerpo = _crear(client, basada_en_id=1).json()

    assert cuerpo["basada_en_id"] == 1


def test_el_speech_original_es_una_version_con_seis_expresiones(cliente) -> None:
    client, _ = cliente

    original = client.get("/mowa-mes/speech/1").json()

    assert [e["segmento"] for e in original["expresiones"]] == SEGMENTOS
    assert "formato" not in original and "partes" not in original


def test_un_pedido_sin_expresiones_es_422_aunque_traiga_partes(cliente) -> None:
    # M-B4: ya no hay versiones de dos partes; `partes` no es un campo del pedido.
    client, _ = cliente
    partes = [{"segmento": s, "parte_1": "a", "parte_2": "b"} for s in SEGMENTOS]

    for cuerpo in ({"nombre": "x", "partes": partes}, {"nombre": "x"}):
        creada = client.post("/mowa-mes/speech", json=cuerpo)
        editada = client.put("/mowa-mes/speech/1", json=cuerpo)
        previa = client.post("/mowa-mes/speech/previsualizacion", json=cuerpo)

        assert (creada.status_code, editada.status_code, previa.status_code) == (422, 422, 422)


def test_una_forma_imposible_es_un_problema_con_su_segmento_y_su_nodo_no_un_422(cliente) -> None:
    client, _ = cliente
    expresiones = _por_segmento(_texto("ok"), s_1_a_8=({"tipo": "imagen"},))

    respuesta = _crear(client, expresiones)

    assert respuesta.status_code == 400
    [problema] = respuesta.json()["problemas"]
    assert (problema["segmento"], problema["campo"], problema["codigo"]) == (
        "1_a_8",
        "expresion",
        "expresion_invalida",
    )
    assert problema["ubicacion"] == {"nodo": 0, "funcion": None, "parametro": None}


def test_los_problemas_del_motor_traen_codigo_y_ubicacion_por_segmento(cliente) -> None:
    client, _ = cliente
    expresiones = _por_segmento(
        _texto("ok"),
        s_preventiva=(_texto("a"), _variable("inventada")),
        s_61_a_90=(_variable("titular", _funcion("primeros", 0)),),
    )

    problemas = _crear(client, expresiones).json()["problemas"]

    por_segmento = {p["segmento"]: p for p in problemas}
    assert por_segmento["preventiva"]["codigo"] == "variable_desconocida"
    assert por_segmento["preventiva"]["catalogo"] == "texto"
    assert por_segmento["preventiva"]["campo"] == "expresion"
    assert por_segmento["preventiva"]["ubicacion"]["nodo"] == 1
    assert por_segmento["61_a_90"]["codigo"] == "parametro_invalido"
    assert por_segmento["61_a_90"]["ubicacion"] == {"nodo": 0, "funcion": 0, "parametro": "n"}


def test_faltan_segmentos_y_un_segmento_vacio_se_informan(cliente) -> None:
    client, _ = cliente

    sin_uno = _crear(client, CUERPO_V2[1:])
    con_vacio = _crear(client, _por_segmento(_texto("ok"), s_9_a_30=()))

    assert [(p["segmento"], p["campo"]) for p in sin_uno.json()["problemas"]] == [
        (None, "segmentos")
    ]
    assert [(p["segmento"], p["campo"]) for p in con_vacio.json()["problemas"]] == [
        ("9_a_30", "expresion")
    ]


def test_un_nombre_repetido_es_409_y_una_base_inexistente_404(cliente) -> None:
    client, _ = cliente
    _crear(client)

    repetido = _crear(client, nombre="mi SPEECH v2")
    sin_base = _crear(client, nombre="otro", basada_en_id=99)

    assert (repetido.status_code, sin_base.status_code) == (409, 404)


# --- Lo que M-B4 quito ----------------------------------------------------------------------------


def test_como_v2_ya_no_existe(cliente) -> None:
    client, _ = cliente

    assert client.get("/mowa-mes/speech/1/como-v2").status_code == 404


# --- Editar ---------------------------------------------------------------------------------------


def test_una_v2_sin_usar_se_edita(cliente) -> None:
    client, _ = cliente
    id_ = _crear(client).json()["id"]
    nuevas = _por_segmento(_texto("Cuota vencida"))

    respuesta = client.put(
        f"/mowa-mes/speech/{id_}", json={"nombre": "Renombrada", "expresiones": nuevas}
    )

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert cuerpo["nombre"] == "Renombrada"
    assert cuerpo["expresiones"][0]["usa_titular"] is False


def test_una_v2_usada_no_se_modifica_y_el_original_tampoco(cliente) -> None:
    client, repositorio = cliente
    id_ = _crear(client).json()["id"]
    repositorio.marcar_speech_usado(id_)

    usada = client.put(f"/mowa-mes/speech/{id_}", json={"nombre": "z", "expresiones": CUERPO_V2})
    original = client.put("/mowa-mes/speech/1", json={"nombre": "z", "expresiones": CUERPO_V2})

    assert (usada.status_code, original.status_code) == (409, 409)
    assert client.get(f"/mowa-mes/speech/{id_}").json()["nombre"] == "Mi speech v2"


def test_editar_una_v2_con_problemas_es_400_y_no_cambia_nada(cliente) -> None:
    client, _ = cliente
    id_ = _crear(client).json()["id"]

    respuesta = client.put(
        f"/mowa-mes/speech/{id_}",
        json={"nombre": "x", "expresiones": _por_segmento(_variable("inventada"))},
    )

    assert respuesta.status_code == 400
    assert client.get(f"/mowa-mes/speech/{id_}").json()["nombre"] == "Mi speech v2"


# --- Previsualizar --------------------------------------------------------------------------------


def test_la_previsualizacion_v2_da_largo_nivel_y_ejemplo_por_segmento(cliente) -> None:
    client, _ = cliente

    cuerpo = client.post(
        "/mowa-mes/speech/previsualizacion", json={"expresiones": CUERPO_V2, "whatsapp": WHATSAPP}
    ).json()

    assert (cuerpo["largo_advertencia"], cuerpo["largo_maximo"]) == (150, 160)
    assert cuerpo["problemas"] == []
    primero = cuerpo["segmentos"][0]
    assert (primero["segmento"], primero["largo_maximo"], primero["codigo"]) == (
        "preventiva",
        28,
        None,
    )
    assert primero["sin_maximo"] is None
    assert primero["ejemplo"] == "XXXXXXXX vence el 05/10/2026"


_EMOJI = "\N{THUMBS UP SIGN}"
_TONO = "\N{EMOJI MODIFIER FITZPATRICK TYPE-4}"
_ELIPSIS = "\N{HORIZONTAL ELLIPSIS}"
_EURO = "\N{EURO SIGN}"


def test_la_previsualizacion_v2_normaliza_el_ejemplo_y_avisa_lo_que_se_borra(cliente) -> None:
    client, _ = cliente
    expresiones = _por_segmento(_texto(f"Hola {_EMOJI}{_TONO} {_ELIPSIS} {_EURO} {_EMOJI}"))

    segmento = client.post(
        "/mowa-mes/speech/previsualizacion", json={"expresiones": expresiones}
    ).json()["segmentos"][0]

    assert segmento["ejemplo"] == "Hola  ... EUR "  # el ejemplo sale como se enviaria
    assert segmento["caracteres_quitados"] == [
        {"caracter": _EMOJI + _TONO, "punto_de_codigo": "U+1F44D U+1F3FD"},
        {"caracter": _EMOJI, "punto_de_codigo": "U+1F44D"},
    ]
    # la elipsis y el euro miden 3 cada uno (unidades GSM-7) y no queda ningun extendido: el largo
    # es el del texto ya normalizado
    assert segmento["largo_maximo"] == len(segmento["ejemplo"])


def test_la_previsualizacion_v2_trae_la_lista_vacia_si_no_se_borra_nada(cliente) -> None:
    client, _ = cliente

    segmentos = client.post(
        "/mowa-mes/speech/previsualizacion", json={"expresiones": CUERPO_V2}
    ).json()["segmentos"]

    assert [s["caracteres_quitados"] for s in segmentos] == [[]] * 6


def test_sin_whatsapp_el_aviso_de_lo_borrado_sale_aunque_no_haya_ejemplo(cliente) -> None:
    client, repositorio = cliente
    repositorio.configuracion = replace(repositorio.configuracion, whatsapp_contacto=None)
    contacto = _variable("whatsapp_contacto", _funcion("enlace_whatsapp"))
    expresiones = _por_segmento(_texto(f"Escribe {_EMOJI} a "), contacto)

    segmento = client.post(
        "/mowa-mes/speech/previsualizacion", json={"expresiones": expresiones}
    ).json()["segmentos"][0]

    assert segmento["falta_whatsapp"] is True and segmento["ejemplo"] is None
    assert segmento["caracteres_quitados"] == [{"caracter": _EMOJI, "punto_de_codigo": "U+1F44D"}]


def test_sin_maximo_calculable_trae_el_motivo_y_el_ejemplo(cliente) -> None:
    client, _ = cliente
    expresiones = _por_segmento(_variable("titular"), _texto(" vence"))

    segmento = client.post(
        "/mowa-mes/speech/previsualizacion", json={"expresiones": expresiones}
    ).json()["segmentos"][0]

    assert segmento["largo_maximo"] is None and segmento["codigo"] is None
    assert segmento["sin_maximo"]["codigo"] == "sin_cota_variable"
    assert segmento["sin_maximo"]["ubicacion"] == {"nodo": 0, "funcion": None, "parametro": None}
    assert segmento["ejemplo"] == "XXXXXXXX vence"


def test_el_nivel_sale_con_el_codigo_de_mowa_mes(cliente) -> None:
    client, _ = cliente
    por_largo = {150: None, 151: "mensaje_excede_150", 161: "mensaje_excede_160"}

    for largo, codigo in por_largo.items():
        cuerpo = client.post(
            "/mowa-mes/speech/previsualizacion",
            json={"expresiones": _por_segmento(_texto("x" * largo))},
        ).json()

        assert cuerpo["segmentos"][0]["codigo"] == codigo, largo


def test_un_segmento_que_usa_el_whatsapp_sin_numero_se_marca_y_no_tiene_ejemplo() -> None:
    repositorio = RepositorioMowaMesFalso(whatsapp=None)
    servicio = ConfiguracionMowaMesService(repositorio)
    app.dependency_overrides[obtener_servicio_mowa_mes] = lambda: servicio
    try:
        client = TestClient(app)
        enlace = _variable("whatsapp_contacto", _funcion("enlace_whatsapp"))
        expresiones = _por_segmento(_texto("Info "), enlace)

        sin_numero = client.post(
            "/mowa-mes/speech/previsualizacion", json={"expresiones": expresiones}
        ).json()["segmentos"][0]
        con_numero = client.post(
            "/mowa-mes/speech/previsualizacion",
            json={"expresiones": expresiones, "whatsapp": WHATSAPP},
        ).json()["segmentos"][0]
    finally:
        app.dependency_overrides.clear()

    assert (sin_numero["usa_whatsapp"], sin_numero["falta_whatsapp"], sin_numero["ejemplo"]) == (
        True,
        True,
        None,
    )
    assert con_numero["ejemplo"] == "Info https://wa.me/+51900000123"
    assert sin_numero["largo_maximo"] == con_numero["largo_maximo"] == 31


def test_un_whatsapp_invalido_o_una_forma_imposible_en_la_previsualizacion_son_400(cliente) -> None:
    client, _ = cliente

    invalido = client.post(
        "/mowa-mes/speech/previsualizacion", json={"expresiones": CUERPO_V2, "whatsapp": "123"}
    )
    imposible = client.post(
        "/mowa-mes/speech/previsualizacion",
        json={"expresiones": _por_segmento({"tipo": "imagen"})},
    )

    assert (invalido.status_code, imposible.status_code) == (400, 400)
    assert invalido.json()["problemas"] == []
    assert imposible.json()["problemas"][0]["codigo"] == "expresion_invalida"


# --- Una campana con una v2 -----------------------------------------------------------------------


def _entorno_con_v2(expresiones=None, productos=None) -> tuple[Entorno, TestClient, int]:
    entorno = Entorno(productos)
    servicio = ConfiguracionMowaMesService(entorno.mowa_mes)
    app.dependency_overrides[obtener_servicio_mowa_mes] = lambda: servicio
    cliente_http = _cliente(entorno)
    id_ = cliente_http.post(
        "/mowa-mes/speech",
        json={"nombre": "v2 de campana", "expresiones": expresiones or CUERPO_V2},
    ).json()["id"]
    return entorno, cliente_http, id_


def test_la_campana_con_una_v2_previsualiza_con_su_huella() -> None:
    entorno, client, id_ = _entorno_con_v2()

    cuerpo = client.post(
        "/mowa-mes/campanas/previsualizacion", json={**CUERPO, "speech_id": id_}
    ).json()

    version = entorno.mowa_mes.versiones[id_]
    assert cuerpo["speech"] == {
        "id": id_,
        "nombre": "v2 de campana",
        "huella": huella_de(version.datos),
    }
    assert cuerpo["productos_cargados"] == 1
    assert cuerpo["muestra"][-1]["mensaje"].endswith(" vence el 06/09/2026")


def test_la_campana_con_una_v2_que_no_usa_el_titular_carga_el_producto_sin_titular() -> None:
    sin_titular = _por_segmento(_texto("Tu cuota vence el "), _fecha())
    productos = [producto(1, titular=None), producto(2)]
    _, client, id_ = _entorno_con_v2(sin_titular, productos)

    cuerpo = client.post(
        "/mowa-mes/campanas/previsualizacion", json={**CUERPO, "speech_id": id_}
    ).json()

    assert cuerpo["productos_cargados"] == 2
    assert cuerpo["exclusiones_por_codigo"] == []
    assert {m["mensaje"] for m in cuerpo["muestra"] if not m["supervision"]} == {
        "Tu cuota vence el 06/09/2026"
    }


def test_la_campana_con_una_v2_que_usa_el_titular_lo_excluye() -> None:
    productos = [producto(1, titular=None), producto(2)]
    _, client, id_ = _entorno_con_v2(productos=productos)

    cuerpo = client.post(
        "/mowa-mes/campanas/previsualizacion", json={**CUERPO, "speech_id": id_}
    ).json()

    assert cuerpo["productos_cargados"] == 1
    assert cuerpo["exclusiones_por_codigo"] == [
        {"codigo": "falta_titular", "tipo": "exclusion", "cantidad": 1}
    ]


def test_se_crea_la_campana_con_la_huella_de_la_v2_y_si_la_v2_cambia_antes_es_409() -> None:
    entorno, client, id_ = _entorno_con_v2()
    previa = client.post(
        "/mowa-mes/campanas/previsualizacion", json={**CUERPO, "speech_id": id_}
    ).json()
    huella = previa["speech"]["huella"]
    # La v2 se edita entre previsualizar y crear (aun no se uso).
    editada = client.put(
        f"/mowa-mes/speech/{id_}",
        json={"nombre": "v2 de campana", "expresiones": _por_segmento(_texto("Otra cosa"))},
    )

    cambiada = client.post(
        "/mowa-mes/campanas", json={**CUERPO, "speech_id": id_, "speech_huella": huella}
    )

    assert editada.status_code == 200
    assert cambiada.status_code == 409
    assert cambiada.json()["codigo"] == "huella_cambiada"
    assert entorno.campanas.campanas == {}  # no se creo nada


def test_se_crea_la_campana_con_la_huella_vigente_de_la_v2_y_la_marca_usada() -> None:
    entorno, client, id_ = _entorno_con_v2()
    huella = client.post(
        "/mowa-mes/campanas/previsualizacion", json={**CUERPO, "speech_id": id_}
    ).json()["speech"]["huella"]

    creada = client.post(
        "/mowa-mes/campanas", json={**CUERPO, "speech_id": id_, "speech_huella": huella}
    )

    assert creada.status_code == 201
    assert creada.json()["speech"] == {"id": id_, "nombre": "v2 de campana"}
    assert len(entorno.campanas.campanas) == 1


def test_la_huella_del_original_no_vale_para_otra_version() -> None:
    entorno, client, id_ = _entorno_con_v2()
    huella_original = client.post("/mowa-mes/campanas/previsualizacion", json=CUERPO).json()[
        "speech"
    ]["huella"]

    creada = client.post(
        "/mowa-mes/campanas", json={**CUERPO, "speech_id": id_, "speech_huella": huella_original}
    )

    assert creada.status_code == 409 and creada.json()["codigo"] == "huella_cambiada"
    assert huella_original == huella_de(DatosSpeech("Speech original", ORIGINAL))


def test_el_dia_de_atraso_ajustado_llega_a_la_expresion_de_la_campana() -> None:
    dias = _variable("dias_atraso_ajustados")
    _, client, id_ = _entorno_con_v2(_por_segmento(_texto("Atraso: "), dias))

    cuerpo = client.post(
        "/mowa-mes/campanas/previsualizacion",
        json={**CUERPO, "speech_id": id_, "envios": [f"{date(2026, 9, 17)}T09:00:00"]},
    ).json()

    # 4 dias de la sabana (producto) + 7 entre el corte (10/09) y el envio (17/09) = 11
    assert cuerpo["muestra"][-1]["mensaje"] == "Atraso: 11"
