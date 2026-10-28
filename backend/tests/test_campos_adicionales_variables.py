"""Las variables del motor de texto para los campos adicionales (T-CA-B2, RF-64 a RF-66).

Un adicional llega al editor con su nombre legible y su marca; uno archivado se sigue resolviendo
(lo que ya lo usa compila) pero viene marcado para que el editor no lo ofrezca. Datos sinteticos.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.texto_enriquecido import obtener_registro_contextos, registro_de_contextos
from app.core.services.contextos_texto import contexto_cartera
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.main import app
from tests.campos_adicionales_memoria import catalogo_con


def _variables(catalogo: CatalogoCartera) -> dict:
    return {v.nombre: v for v in contexto_cartera(catalogo).variables}


def test_un_adicional_lleva_su_nombre_legible_y_su_marca() -> None:
    variable = _variables(catalogo_con())["ad_monto_extra"]

    assert (variable.etiqueta, variable.adicional, variable.archivado) == (
        "Monto extra",
        True,
        False,
    )
    assert variable.clave_nombre is None and variable.origen == "cartera"


def test_un_archivado_sigue_en_las_variables_pero_marcado() -> None:
    variable = _variables(catalogo_con())["ad_antiguo"]

    assert (variable.etiqueta, variable.adicional, variable.archivado) == (
        "Campo antiguo",
        True,
        True,
    )


def test_los_campos_base_y_las_variables_de_envio_no_traen_marcas() -> None:
    variables = _variables(catalogo_con())

    for nombre in ("dias_atraso", "region", "fecha_envio", "dias_atraso_ajustados"):
        v = variables[nombre]
        assert (v.etiqueta, v.adicional, v.archivado) == (None, False, False), nombre


def test_el_ejemplo_y_el_tipo_de_un_adicional_siguen_a_su_tipo() -> None:
    contexto = contexto_cartera(catalogo_con())

    assert contexto.tipos["ad_monto_extra"].value == "numero"
    assert contexto.tipos["ad_fecha_visita"].value == "fecha"
    assert contexto.ejemplo["ad_zona_comercial"] == "EJEMPLO"


@pytest.fixture
def cliente():
    app.dependency_overrides[obtener_registro_contextos] = lambda: registro_de_contextos(
        catalogo_con()
    )
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(obtener_registro_contextos, None)


def test_el_catalogo_de_la_api_declara_las_marcas_de_cada_variable(cliente) -> None:
    cuerpo = cliente.get("/texto-enriquecido/catalogo", params={"contexto": "cartera"}).json()
    variables = {v["nombre"]: v for v in cuerpo["contexto"]["variables"]}

    assert variables["ad_zona_comercial"] == {
        "nombre": "ad_zona_comercial",
        "tipo": "texto",
        "clave_nombre": None,
        "origen": "cartera",
        "etiqueta": "Zona comercial",
        "adicional": True,
        "archivado": False,
    }
    assert variables["ad_antiguo"]["archivado"] is True
    assert variables["region"]["etiqueta"] is None and variables["region"]["adicional"] is False


def test_las_variables_propias_del_speech_van_con_los_valores_por_defecto(cliente) -> None:
    # Desde T-MM-B12 el contexto del speech suma los adicionales (D-CA-0); las variables que son
    # suyas (titular, vencimiento, WhatsApp, dias) siguen sin etiqueta ni marcas.
    cuerpo = cliente.get("/texto-enriquecido/catalogo", params={"contexto": "mowa_mes.speech"})
    variables = cuerpo.json()["contexto"]["variables"]
    propias = [v for v in variables if not v["nombre"].startswith("ad_")]

    assert propias
    assert all(
        (v["etiqueta"], v["adicional"], v["archivado"]) == (None, False, False) for v in propias
    )
    adicionales = {v["nombre"]: v for v in variables if v["nombre"].startswith("ad_")}
    assert adicionales["ad_zona_comercial"]["adicional"] is True
    assert adicionales["ad_antiguo"]["archivado"] is True
