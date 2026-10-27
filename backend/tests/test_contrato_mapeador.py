"""Los enums del mapeador son un enum en el contrato y tienen su traduccion (T-MAP-B3b).

Como `CodigoTexto` en el motor de texto: que el estado, el origen y el codigo de problema sean un
enum en el OpenAPI (y una union de literales en los tipos del frontend) hace que un valor mal
escrito no compile. Estas pruebas exigen que el enum del esquema sea exactamente el de la entidad,
que los campos de las respuestas lo usen y que cada valor tenga su texto en los dos idiomas. Un
valor nuevo aparece solo si se regenera `contratos/openapi.json` (y los tipos) y se traduce.
"""

import json
import re
from pathlib import Path

import pytest

from app.core.entities.lectura_tabla import CodigoAdvertenciaLectura, FormatoTabla, OpcionDetectable
from app.core.entities.mapeador import (
    CodigoErrorMapeador,
    CodigoMapeo,
    EstadoEncabezado,
    OrigenAsignacion,
)
from app.core.services.ingesta_sabana.catalogo import CATALOGO_SABANA
from app.main import app

RAIZ = Path(__file__).resolve().parents[2]
CONTRATO = RAIZ / "contratos" / "openapi.json"
I18N = RAIZ / "frontend" / "src" / "i18n"
IDIOMAS = ["es", "en"]

# esquema -> enum de la entidad
ENUMS = {
    "EstadoEncabezado": EstadoEncabezado,
    "OrigenAsignacion": OrigenAsignacion,
    "CodigoMapeo": CodigoMapeo,
    "CodigoAdvertenciaLectura": CodigoAdvertenciaLectura,
    "FormatoTabla": FormatoTabla,
    "OpcionDetectable": OpcionDetectable,
    "CodigoErrorMapeador": CodigoErrorMapeador,
}
# (esquema, propiedad) -> el enum que tiene que usar
USOS = {
    ("ColumnaAnalizadaRespuesta", "estado"): "EstadoEncabezado",
    ("ProblemaMapeoRespuesta", "codigo"): "CodigoMapeo",
    ("AsignacionEntrada", "origen"): "OrigenAsignacion",
    ("AdvertenciaLecturaRespuesta", "codigo"): "CodigoAdvertenciaLectura",
    ("AnalisisRespuesta", "formato"): "FormatoTabla",
    ("DetalleErrorMapeador", "codigo"): "CodigoErrorMapeador",
    ("DetalleErrorMapeo", "codigo"): "CodigoErrorMapeador",
}
# Las claves de la pantalla: prefijo -> enum que las genera (FormatoTabla y OpcionDetectable no se
# muestran por clave: los nombres de las opciones los pone la pantalla).
PREFIJOS = {
    "mapeador.estado.": EstadoEncabezado,
    "mapeador.origen.": OrigenAsignacion,
    "mapeador.problema.": CodigoMapeo,
    "mapeador.advertencia.": CodigoAdvertenciaLectura,
    "mapeador.error.": CodigoErrorMapeador,
}


def _esquemas(origen: str) -> dict:
    if origen == "api":
        return app.openapi()["components"]["schemas"]
    return json.loads(CONTRATO.read_text(encoding="utf-8"))["components"]["schemas"]


@pytest.fixture(params=["api", "contrato versionado"])
def esquemas(request) -> dict:
    return _esquemas("api" if request.param == "api" else "archivo")


def _diccionario(idioma: str) -> dict[str, str]:
    return json.loads((I18N / f"{idioma}.json").read_text(encoding="utf-8"))


# --- El contrato ---------------------------------------------------------------------------------


@pytest.mark.parametrize("nombre", ENUMS)
def test_el_enum_del_esquema_es_exactamente_el_de_la_entidad(esquemas, nombre) -> None:
    assert esquemas[nombre]["type"] == "string"
    assert esquemas[nombre]["enum"] == [valor.value for valor in ENUMS[nombre]]


@pytest.mark.parametrize(("esquema", "propiedad"), USOS)
def test_los_campos_de_las_respuestas_usan_el_enum_y_no_texto_libre(
    esquemas, esquema, propiedad
) -> None:
    referencia = {"$ref": f"#/components/schemas/{USOS[(esquema, propiedad)]}"}

    assert esquemas[esquema]["properties"][propiedad] == referencia
    assert propiedad in esquemas[esquema]["required"]


def test_los_esquemas_del_mapeador_tienen_nombre_propio_en_el_contrato(esquemas) -> None:
    # Un nombre repetido entre modulos hace que FastAPI publique `app__api__<modulo>__Nombre`, y
    # esos nombres llegan feos a los tipos del frontend.
    con_prefijo = sorted(n for n in esquemas if n.startswith("app__api__mapeador__"))

    assert con_prefijo == []


def test_el_contrato_declara_las_rutas_del_mapeador_con_sus_codigos(esquemas) -> None:
    rutas = json.loads(CONTRATO.read_text(encoding="utf-8"))["paths"]

    esperadas = {
        ("get", "/mapeador/catalogos/{catalogo_id}"): {"200", "404"},
        ("post", "/mapeador/{catalogo_id}/borradores"): {"201", "400", "404", "413"},
        ("post", "/mapeador/borradores/{borrador_id}/analisis"): {"200", "400", "404"},
        ("post", "/mapeador/borradores/{borrador_id}/validacion"): {"200", "404"},
        ("delete", "/mapeador/borradores/{borrador_id}"): {"204", "404"},
        ("post", "/cargas/desde-borrador"): {"202", "404", "422"},
    }
    for (metodo, ruta), codigos in esperadas.items():
        assert codigos <= set(rutas[ruta][metodo]["responses"]), (metodo, ruta)


def test_el_422_de_confirmar_declara_los_problemas(esquemas) -> None:
    rutas = app.openapi()["paths"]
    respuesta = rutas["/cargas/desde-borrador"]["post"]["responses"]["422"]

    referencia = respuesta["content"]["application/json"]["schema"]["$ref"]
    assert referencia.endswith("/DetalleErrorMapeo")
    assert set(esquemas["DetalleErrorMapeo"]["required"]) == {"detail", "codigo", "problemas"}
    assert esquemas["DetalleErrorMapeo"]["properties"]["detail"]["type"] == "string"


def test_el_analisis_declara_los_detectados_como_lista_del_enum(esquemas) -> None:
    detectados = esquemas["AnalisisRespuesta"]["properties"]["detectados"]

    assert detectados["items"] == {"$ref": "#/components/schemas/OpcionDetectable"}
    assert "detectados" in esquemas["AnalisisRespuesta"]["required"]


def test_el_catalogo_declara_las_codificaciones_y_los_separadores(esquemas) -> None:
    catalogo = esquemas["CatalogoMapeadorRespuesta"]

    assert {"codificaciones", "separadores"} <= set(catalogo["required"])
    assert catalogo["properties"]["separadores"]["items"] == {"type": "string"}


def test_los_errores_del_mapeador_declaran_su_codigo_y_sus_datos_opcionales(esquemas) -> None:
    error = esquemas["DetalleErrorMapeador"]

    assert set(error["required"]) == {"detail", "codigo"}
    assert {"hoja", "hojas", "maximo_mb"} <= set(error["properties"])
    assert not {"hoja", "hojas", "maximo_mb"} & set(error["required"])


def test_cada_400_404_y_413_del_mapeador_es_un_detalle_con_codigo() -> None:
    rutas = app.openapi()["paths"]
    errores = {
        (ruta, metodo, estado): operacion["responses"][estado]
        for ruta, metodos in rutas.items()
        if ruta.startswith("/mapeador") or ruta == "/cargas/desde-borrador"
        for metodo, operacion in metodos.items()
        for estado in operacion["responses"]
        if estado in {"400", "404", "413"}
    }

    assert errores  # hay errores declarados
    for clave, respuesta in errores.items():
        referencia = respuesta["content"]["application/json"]["schema"]["$ref"]
        assert referencia.endswith("/DetalleErrorMapeador"), clave


# --- Las traducciones ----------------------------------------------------------------------------


def _claves_esperadas() -> set[str]:
    return {f"{prefijo}{valor.value}" for prefijo, enum in PREFIJOS.items() for valor in enum}


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_cada_valor_de_los_enums_tiene_su_texto(idioma) -> None:
    diccionario = _diccionario(idioma)

    faltan = sorted(
        clave for clave in _claves_esperadas() if not diccionario.get(clave, "").strip()
    )

    assert faltan == [], f"Faltan en {idioma}.json: {faltan}"


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_no_quedan_textos_de_valores_que_ya_no_existen(idioma) -> None:
    sobran = sorted(
        clave
        for clave in _diccionario(idioma)
        if clave.startswith(tuple(PREFIJOS)) and clave not in _claves_esperadas()
    )

    assert sobran == [], f"Sobran en {idioma}.json: {sobran}"


def test_los_marcadores_de_los_problemas_son_los_mismos_en_los_dos_idiomas() -> None:
    es, en = _diccionario("es"), _diccionario("en")

    for valor in CodigoMapeo:
        clave = f"mapeador.problema.{valor.value}"
        assert set(re.findall(r"\{(\w+)\}", es[clave])) == set(re.findall(r"\{(\w+)\}", en[clave]))
    # y solo usan marcadores que la API envia en el problema (`campo`)
    usados = {
        m
        for clave, texto in es.items()
        if clave.startswith("mapeador.problema.")
        for m in re.findall(r"\{(\w+)\}", texto)
    }
    assert usados <= {"campo"}


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_cada_campo_del_catalogo_tiene_su_etiqueta(idioma) -> None:
    diccionario = _diccionario(idioma)

    faltan = {
        c.clave_etiqueta for c in CATALOGO_SABANA.campos if c.clave_etiqueta not in diccionario
    }

    assert faltan == set()


# Los datos que la API envia con cada codigo de error (`DetalleErrorMapeador`): el texto solo puede
# usar algunos de esos marcadores (los datos que no se usan en el texto igual viajan en el cuerpo).
DATOS_DE_ERROR = {
    CodigoErrorMapeador.ARCHIVO_DEMASIADO_GRANDE: {"maximo_mb"},
    CodigoErrorMapeador.HOJA_INEXISTENTE: {"hoja", "hojas"},
}


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_los_textos_de_error_usan_solo_los_datos_que_trae_su_codigo(idioma) -> None:
    diccionario = _diccionario(idioma)

    for codigo in CodigoErrorMapeador:
        marcadores = set(re.findall(r"\{(\w+)\}", diccionario[f"mapeador.error.{codigo.value}"]))
        assert marcadores <= DATOS_DE_ERROR.get(codigo, set()), codigo
