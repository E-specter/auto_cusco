"""Los codigos del motor de texto enriquecido son un enum en el contrato (B9).

Que `codigo` sea un enum en el OpenAPI (y una union de literales en los tipos del frontend) hace
que un codigo mal escrito no compile. Estas pruebas exigen que el enum del esquema sea exactamente
`CodigoTexto` y que ningun `codigo` del catalogo del motor vuelva a ser texto libre. Un codigo
nuevo en `CodigoTexto` aparece solo si se regenera `contratos/openapi.json` (y los tipos).
"""

import json
from pathlib import Path

import pytest

from app.core.entities.mowa_mes import CodigoMowaMes
from app.core.entities.texto_enriquecido import CodigoTexto
from app.main import app

CONTRATO = Path(__file__).resolve().parents[2] / "contratos" / "openapi.json"
REF_TEXTO = {"$ref": "#/components/schemas/CodigoTexto"}
REF_MOWA_MES = {"$ref": "#/components/schemas/CodigoMowaMes"}

# `codigo` que es siempre de `CodigoTexto` (los 404/409 del motor y de las definiciones incluidos).
SIEMPRE_DE_TEXTO = (
    "ProblemaTextoRespuesta",
    "SinCotaRespuesta",
    "ExclusionFilaRespuesta",
    "ExclusionCargaRespuesta",
    "DetalleErrorTexto",
    "DetalleErrorDefinicion",
)
# `codigo` de otro catalogo que no es de este motor y sigue siendo texto: las incidencias de la
# ingesta de la sabana. Cualquier otro `codigo` en texto libre es un hueco nuevo.
TEXTO_LIBRE_PERMITIDO = {"IncidenciaRespuesta"}


def _esquemas(origen: str) -> dict:
    if origen == "api":
        return app.openapi()["components"]["schemas"]
    return json.loads(CONTRATO.read_text(encoding="utf-8"))["components"]["schemas"]


@pytest.fixture(params=["api", "contrato versionado"])
def esquemas(request) -> dict:
    return _esquemas("api" if request.param == "api" else "archivo")


def test_el_enum_del_esquema_es_exactamente_codigo_texto(esquemas) -> None:
    assert esquemas["CodigoTexto"]["type"] == "string"
    assert esquemas["CodigoTexto"]["enum"] == [codigo.value for codigo in CodigoTexto]


def test_el_enum_de_mowa_mes_tambien_es_el_de_su_catalogo(esquemas) -> None:
    assert esquemas["CodigoMowaMes"]["enum"] == [codigo.value for codigo in CodigoMowaMes]


@pytest.mark.parametrize("modelo", SIEMPRE_DE_TEXTO)
def test_el_codigo_de_estos_modelos_es_el_enum_y_no_texto_libre(esquemas, modelo) -> None:
    assert esquemas[modelo]["properties"]["codigo"] == REF_TEXTO


def test_los_errores_con_codigo_aceptan_un_codigo_del_motor_o_null(esquemas) -> None:
    codigo = esquemas["DetalleErrorConCodigo"]["properties"]["codigo"]

    assert codigo["anyOf"] == [REF_TEXTO, {"type": "null"}]
    assert "codigo" in esquemas["DetalleErrorConCodigo"]["required"]  # siempre viaja


def test_el_codigo_de_un_problema_de_speech_es_de_uno_de_los_dos_catalogos(esquemas) -> None:
    propiedades = esquemas["ProblemaSpeechRespuesta"]["properties"]

    assert propiedades["codigo"]["anyOf"] == [REF_TEXTO, REF_MOWA_MES, {"type": "null"}]
    # `catalogo` no cambia: dice en cual i18n se traduce
    assert propiedades["catalogo"]["anyOf"][0]["enum"] == ["texto", "mowa_mes"]
    assert {"codigo", "catalogo"} <= set(esquemas["ProblemaSpeechRespuesta"]["required"])


def test_ningun_otro_codigo_del_contrato_es_texto_libre(esquemas) -> None:
    en_texto_libre = {
        nombre
        for nombre, esquema in esquemas.items()
        if "codigo" in esquema.get("properties", {})
        and _es_texto_libre(esquema["properties"]["codigo"])
    }

    assert en_texto_libre == TEXTO_LIBRE_PERMITIDO


def _es_texto_libre(propiedad: dict) -> bool:
    """`string` sin enum, solo o dentro de un `anyOf`."""
    variantes = propiedad.get("anyOf", [propiedad])
    return any(v.get("type") == "string" and "enum" not in v for v in variantes)
