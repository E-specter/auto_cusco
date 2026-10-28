"""Los endpoints de MOWA MES con campos adicionales (T-MM-B12, RF-64 a RF-66).

Sobre repositorios en memoria y los adicionales sinteticos de `campos_adicionales_memoria.py`.
- El speech v2: guardar sin tope es un 400 con su problema ubicado; la previsualizacion trae el
  ejemplo sintetico y los campos archivados que usa.
- La campana: la exclusion `falta_campo_adicional` trae los campos con su nombre tecnico y el
  legible (que se resuelve al leer: renombrar el campo cambia el legible y no lo guardado).
- El contexto `mowa_mes.speech` del editor ofrece los adicionales.
Datos sinteticos.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.adapters.output.plataformas.mowa_mes.archivo_carga import escribir_archivo_carga
from app.api.cartera import obtener_catalogo_cartera
from app.api.mowa_mes import obtener_servicio_mowa_mes
from app.api.mowa_mes_campanas import obtener_servicio_campanas
from app.core.entities.mowa_mes import VersionSpeech
from app.core.services.plataformas.mowa_mes.campana import CampanasMowaMesService, huella_de
from app.core.services.plataformas.mowa_mes.configuracion import ConfiguracionMowaMesService
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService
from app.core.services.texto_enriquecido.serializacion import expresion_a_dict
from app.main import app
from tests.campos_adicionales_memoria import (
    ARCHIVADO,
    FECHA,
    NUMERO,
    TEXTO,
    CamposAdicionalesEnMemoria,
    catalogo_con,
)
from tests.test_api_mowa_mes_campanas import CUERPO, Entorno
from tests.test_mowa_mes_adicionales import COMPLETO, ZONA_ACOTADA, _f, _v2, _var
from tests.test_mowa_mes_campana import MOMENTO, producto
from tests.test_mowa_mes_speech import WHATSAPP, RepositorioMowaMesFalso

ZONA, MONTO, VISITA, ANTIGUO = TEXTO.nombre, NUMERO.nombre, FECHA.nombre, ARCHIVADO.nombre


@pytest.fixture(autouse=True)
def _limpiar_dependencias():
    yield
    app.dependency_overrides.clear()


def _expresiones_json(datos) -> list[dict]:
    return [
        {"segmento": e.segmento.value, "expresion": expresion_a_dict(e.expresion)}
        for e in datos.expresiones
    ]


@pytest.fixture
def speech_api():
    repositorio = RepositorioMowaMesFalso(WHATSAPP)
    servicio = ConfiguracionMowaMesService(repositorio, catalogo_con())
    app.dependency_overrides[obtener_servicio_mowa_mes] = lambda: servicio
    return TestClient(app), repositorio


# --- El speech v2 -----------------------------------------------------------------------------


def test_guardar_un_adicional_sin_tope_es_un_400_con_el_problema_ubicado_y_no_se_guarda(
    speech_api,
) -> None:
    client, repositorio = speech_api
    sin_tope = _v2(_var(ZONA))

    respuesta = client.post(
        "/mowa-mes/speech", json={"nombre": "Sin tope", "expresiones": _expresiones_json(sin_tope)}
    )

    assert respuesta.status_code == 400
    problema = respuesta.json()["problemas"][0]
    assert (problema["codigo"], problema["catalogo"]) == ("sin_cota_variable", "texto")
    assert problema["ubicacion"]["nodo"] == 0 and problema["segmento"] == "preventiva"
    assert len(repositorio.versiones) == 1  # solo el Speech original


def test_guardar_una_v2_con_los_tres_tipos_acotados_da_201(speech_api) -> None:
    client, _ = speech_api

    respuesta = client.post(
        "/mowa-mes/speech", json={"nombre": "Acotada", "expresiones": _expresiones_json(COMPLETO)}
    )

    assert respuesta.status_code == 201, respuesta.text


def test_la_previsualizacion_usa_el_valor_sintetico_de_cada_tipo(speech_api) -> None:
    client, _ = speech_api

    cuerpo = client.post(
        "/mowa-mes/speech/previsualizacion", json={"expresiones": _expresiones_json(COMPLETO)}
    ).json()

    assert cuerpo["problemas"] == []
    assert cuerpo["segmentos"][0]["ejemplo"] == "Zona ZONA SINTETI monto 1250.50 visita 05/10/2026"
    assert Decimal("1250.50")  # el ejemplo numerico es el de la tabla sintetica


def test_la_previsualizacion_avisa_los_campos_archivados_con_su_etiqueta(speech_api) -> None:
    client, _ = speech_api
    datos = _v2(_var(ANTIGUO, _f("a_texto"), _f("primeros", 5)), ZONA_ACOTADA)

    cuerpo = client.post(
        "/mowa-mes/speech/previsualizacion", json={"expresiones": _expresiones_json(datos)}
    ).json()

    assert cuerpo["campos_archivados"] == [{"nombre": ANTIGUO, "etiqueta": "Campo antiguo"}]


def test_sin_archivados_o_en_una_v1_el_aviso_sale_vacio(speech_api) -> None:
    client, repositorio = speech_api
    v2 = client.post(
        "/mowa-mes/speech/previsualizacion", json={"expresiones": _expresiones_json(COMPLETO)}
    ).json()
    original = repositorio.versiones[1].datos.partes
    v1 = client.post(
        "/mowa-mes/speech/previsualizacion",
        json={
            "partes": [
                {"segmento": p.segmento.value, "parte_1": p.parte_1, "parte_2": p.parte_2}
                for p in original
            ]
        },
    ).json()

    assert v2["campos_archivados"] == [] and v1["campos_archivados"] == []


def test_guardar_una_v2_que_usa_un_archivado_se_permite(speech_api) -> None:
    client, _ = speech_api
    datos = _v2(_var(ANTIGUO, _f("a_texto"), _f("primeros", 5)))

    respuesta = client.post(
        "/mowa-mes/speech",
        json={"nombre": "Con archivado", "expresiones": _expresiones_json(datos)},
    )

    assert respuesta.status_code == 201


# --- La campana: la exclusion con sus campos --------------------------------------------------


def _campanas_api(productos, repositorio_adicionales=None, datos=COMPLETO):
    entorno = Entorno(productos=productos)
    repositorio = repositorio_adicionales or CamposAdicionalesEnMemoria()
    entorno.mowa_mes.versiones[2] = VersionSpeech(2, datos, False, None, None, MOMENTO)

    def servicio():
        # Un catalogo por peticion, como la API: renombrar el campo se nota en la siguiente.
        return CampanasMowaMesService(
            ConsultaCarteraService(entorno.cartera, CatalogoCartera(repositorio)),
            entorno.mowa_mes,
            entorno.supervision,
            entorno.campanas,
            escribir_archivo_carga,
            reloj=lambda: MOMENTO,
        )

    app.dependency_overrides[obtener_servicio_campanas] = servicio
    return TestClient(app), repositorio


def _con_speech_v2() -> dict:
    return {**CUERPO, "speech_id": 2}


def _previsualizar(client):
    return client.post("/mowa-mes/campanas/previsualizacion", json=_con_speech_v2()).json()


def test_la_exclusion_trae_el_nombre_tecnico_y_el_legible_de_cada_campo_vacio() -> None:
    client, _ = _campanas_api([producto(1, **{ZONA: None, MONTO: Decimal("5"), VISITA: None})])

    previa = _previsualizar(client)

    assert previa["exclusiones"]["exclusiones"] == [
        {
            "pagare": producto(1)["pagare"],
            "codigo": "falta_campo_adicional",
            "campos": [
                {"nombre": ZONA, "etiqueta": "Zona comercial"},
                {"nombre": VISITA, "etiqueta": "Fecha de visita"},
            ],
        }
    ]
    assert previa["exclusiones_por_codigo"] == [
        {"codigo": "falta_campo_adicional", "tipo": "exclusion", "cantidad": 1}
    ]


def test_renombrar_el_campo_cambia_la_etiqueta_pero_no_el_nombre_tecnico_guardado() -> None:
    client, repositorio = _campanas_api(
        [producto(1, **{ZONA: None, MONTO: Decimal("5"), VISITA: None})]
    )
    antes = _previsualizar(client)["exclusiones"]["exclusiones"][0]["campos"][0]
    repositorio.campos[0] = replace(TEXTO, nombre_legible="Otra zona")
    despues = _previsualizar(client)["exclusiones"]["exclusiones"][0]["campos"][0]

    assert antes == {"nombre": ZONA, "etiqueta": "Zona comercial"}
    assert despues == {"nombre": ZONA, "etiqueta": "Otra zona"}


def test_las_demas_exclusiones_salen_con_campos_vacios() -> None:
    client, _ = _campanas_api([producto(1, telefono=None)])

    exclusion = _previsualizar(client)["exclusiones"]["exclusiones"][0]

    assert exclusion["codigo"] == "telefono_invalido" and exclusion["campos"] == []


def test_la_lista_de_exclusiones_de_una_campana_creada_trae_los_campos() -> None:
    client, _ = _campanas_api(
        [
            producto(1, **{ZONA: "A", MONTO: Decimal("1"), VISITA: None}),
            producto(2, **{ZONA: "B", MONTO: Decimal("1"), VISITA: date(2026, 10, 5)}),
        ]
    )
    creada = client.post(
        "/mowa-mes/campanas", json={**_con_speech_v2(), "speech_huella": huella_de(COMPLETO)}
    )
    assert creada.status_code == 201, creada.text

    pagina = client.get(f"/mowa-mes/campanas/{creada.json()['id']}/exclusiones").json()

    assert [(e["pagare"], e["campos"]) for e in pagina["exclusiones"]] == [
        (producto(1)["pagare"], [{"nombre": VISITA, "etiqueta": "Fecha de visita"}])
    ]


# --- El contrato y el contexto del editor -----------------------------------------------------


def test_el_contrato_declara_los_campos_siempre_presentes() -> None:
    esquemas = app.openapi()["components"]["schemas"]

    assert "campos" in esquemas["ExclusionRespuesta"]["required"]
    con_aviso = [e for e in esquemas.values() if "campos_archivados" in e.get("properties", {})]
    # La previsualizacion del speech (B12) y la de la campana (B13): las dos lo llevan siempre.
    assert len(con_aviso) == 2
    assert all("campos_archivados" in e["required"] for e in con_aviso)
    assert set(esquemas["CampoNombradoRespuesta"]["required"]) == {"nombre", "etiqueta"}


def test_el_contexto_del_speech_del_editor_ofrece_los_adicionales() -> None:
    app.dependency_overrides[obtener_catalogo_cartera] = lambda: catalogo_con()
    client = TestClient(app)

    cuerpo = client.get(
        "/texto-enriquecido/catalogo", params={"contexto": "mowa_mes.speech"}
    ).json()

    variables = {v["nombre"]: v for v in cuerpo["contexto"]["variables"]}
    assert variables[ZONA]["etiqueta"] == "Zona comercial" and variables[ZONA]["adicional"] is True
    assert variables[ANTIGUO]["archivado"] is True
    assert variables["titular"]["adicional"] is False
