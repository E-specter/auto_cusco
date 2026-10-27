r"""La API no acepta una mitad suelta de un par sustituto en ninguna ruta (T-API-B1).

Un JSON con `"\ud800"` (o los tres bytes CESU-8 de la mitad) pasaba la validacion y la respuesta
reventaba con un 500. Lo que se prueba:

- el buscador y el escritor de texto seguro, sin HTTP;
- el filtro (`RechazaMitadesSueltas`) y el manejador de 422 sobre una aplicacion minima: valores,
  claves, rutas anidadas, el par completo que pasa, el cuerpo que llega intacto, que no se lee un
  cuerpo sin sospechas y que ningun otro cuerpo roto da 500;
- que las demas entradas (consulta, ruta, formulario, multipart y cabecera) no pueden traer una
  mitad suelta;
- las dos rutas de MOWA MES donde se encontro (`descripcion`);
- un recorrido de TODAS las rutas con cuerpo JSON de la aplicacion real.

Las mitades sueltas se mandan como TEXTO CRUDO (`content=`): el cliente de pruebas tampoco puede
codificar una. Datos sinteticos.
"""

import asyncio
import json
from typing import Any

import pytest
from fastapi import FastAPI, File, Form, Header, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel, field_validator

from app.api import texto_valido as filtro
from app.api.texto_valido import RechazaMitadesSueltas, manejar_validacion
from app.core.entities.mowa_mes_campana import LARGO_MAXIMO_DESCRIPCION
from app.core.services.texto_valido import (
    MITAD_SUELTA,
    a_texto_seguro,
    buscar_mitad_suelta,
)
from app.main import app
from tests.test_api_mowa_mes_campanas import (  # noqa: F401
    CUERPO,
    HUELLA_ORIGINAL,
    _cliente,
    _limpiar_dependencias,
)
from tests.test_api_mowa_mes_campanas import Entorno as EntornoMowaMes

JSON = {"content-type": "application/json"}
ALTA, BAJA = "\\ud800", "\\udc00"  # escapes de JSON, tal como los escribe quien manda el cuerpo
PAR = "\\ud83d\\ude00"  # el par COMPLETO de una carita sonriente
CESU = b"\xed\xa0\x80"  # la mitad alta U+D800 codificada a la fuerza como si fuera UTF-8


def _crudo(cliente: TestClient, ruta: str, cuerpo: str | bytes, **cabeceras):
    contenido = cuerpo.encode("utf-8") if isinstance(cuerpo, str) else cuerpo
    return cliente.post(ruta, content=contenido, headers={**JSON, **cabeceras})


# --- El buscador y el escritor de texto seguro ----------------------------------------------------


def test_un_texto_con_una_mitad_suelta_se_encuentra_y_uno_sin_ella_no() -> None:
    assert buscar_mitad_suelta("hola") is None
    assert buscar_mitad_suelta("peña ñandú 😀") is None  # un emoji completo es un solo caracter
    hallazgo = buscar_mitad_suelta("a\udc00b")
    assert (hallazgo.ruta, hallazgo.en_clave, hallazgo.codigo) == ((), False, "U+DC00")


def test_la_ruta_de_la_mitad_suelta_cuenta_diccionarios_y_listas() -> None:
    valor = {"a": [1, {"b": ["x", "y\ud800"]}], "c": "z"}

    hallazgo = buscar_mitad_suelta(valor)

    assert (hallazgo.ruta, hallazgo.en_clave) == (("a", 1, "b", 1), False)


def test_tambien_se_revisan_las_claves_y_el_primero_en_el_orden_del_documento_gana() -> None:
    en_clave = buscar_mitad_suelta({"ok": "x", "m\udc00al": 1, "otro": "\ud800"})
    en_valor = buscar_mitad_suelta({"ok": "\ud800", "m\udc00al": 1})

    assert (en_clave.ruta, en_clave.en_clave) == (("m\udc00al",), True)
    assert (en_valor.ruta, en_valor.en_clave) == (("ok",), False)


def test_un_json_muy_anidado_no_agota_la_pila() -> None:
    valor: Any = "\ud800"
    for _ in range(20_000):
        valor = [valor]

    hallazgo = buscar_mitad_suelta(valor)

    assert hallazgo is not None and len(hallazgo.ruta) == 20_000


def test_a_texto_seguro_escribe_las_mitades_como_texto_en_valores_claves_y_listas() -> None:
    sucio = {"c\ud800": ["a\udc00", ("b", 1)], "n": 3, "texto": "😀 ñ"}

    seguro = a_texto_seguro(sucio)

    assert seguro == {"c\\ud800": ["a\\udc00", ["b", 1]], "n": 3, "texto": "😀 ñ"}
    assert not MITAD_SUELTA.search(json.dumps(seguro, ensure_ascii=False))
    json.dumps(seguro, ensure_ascii=False).encode("utf-8")  # se puede escribir


# --- El filtro, sobre una aplicacion minima -------------------------------------------------------


class Cuerpo(BaseModel):
    texto: str = ""
    datos: dict[str, Any] = {}
    lista: list[Any] = []
    corto: str = ""

    @field_validator("corto")
    @classmethod
    def _cabe(cls, valor: str) -> str:
        if len(valor) > 3:
            raise ValueError("demasiado largo")
        return valor


def _mini(con_filtro: bool = True) -> FastAPI:
    mini = FastAPI()
    if con_filtro:
        mini.add_middleware(RechazaMitadesSueltas)
    mini.add_exception_handler(RequestValidationError, manejar_validacion)

    @mini.post("/eco")
    def eco(cuerpo: Cuerpo) -> dict:
        return cuerpo.model_dump()

    @mini.post("/tamano")
    async def tamano(cuerpo: dict[str, Any]) -> dict:
        return {"claves": len(cuerpo)}

    @mini.get("/q")
    def consulta(t: str = Query("")) -> dict:
        return {"hay_mitad": bool(MITAD_SUELTA.search(t)), "t": ascii(t)}

    @mini.get("/p/{t}")
    def ruta(t: str) -> dict:
        return {"hay_mitad": bool(MITAD_SUELTA.search(t))}

    @mini.post("/form")
    def formulario(t: str = Form(...)) -> dict:
        return {"hay_mitad": bool(MITAD_SUELTA.search(t))}

    @mini.post("/multipart")
    async def multipart(t: str = Form(...), a: UploadFile = File(...)) -> dict:
        return {"hay_mitad": bool(MITAD_SUELTA.search(t) or MITAD_SUELTA.search(a.filename or ""))}

    @mini.get("/h")
    def cabecera(x: str = Header("")) -> dict:
        return {"hay_mitad": bool(MITAD_SUELTA.search(x))}

    return mini


@pytest.fixture
def mini() -> TestClient:
    return TestClient(_mini(), raise_server_exceptions=False)


def _422(respuesta) -> dict:
    assert respuesta.status_code == 422, respuesta.text
    return respuesta.json()["detail"][0]


def test_un_valor_con_una_mitad_suelta_es_422_con_la_ruta_del_campo(mini) -> None:
    detalle = _422(_crudo(mini, "/eco", f'{{"texto": "a{ALTA}b"}}'))

    assert (detalle["type"], detalle["loc"]) == ("mitad_suelta", ["body", "texto"])
    assert "U+D800" in detalle["msg"] and detalle["ctx"] == {"punto_de_codigo": "U+D800"}
    assert "input" not in detalle  # nunca repite lo que mando


def test_la_ruta_llega_hasta_un_texto_anidado_en_listas_y_diccionarios(mini) -> None:
    cuerpo = f'{{"datos": {{"uno": [1, {{"dos": ["x", "y{BAJA}"]}}]}}}}'

    detalle = _422(_crudo(mini, "/eco", cuerpo))

    assert detalle["loc"] == ["body", "datos", "uno", 1, "dos", 1]
    assert "U+DC00" in detalle["msg"]


def test_una_clave_con_una_mitad_suelta_tambien_es_422_y_la_clave_sale_escapada(mini) -> None:
    detalle = _422(_crudo(mini, "/eco", f'{{"datos": {{"mal{ALTA}": 1}}}}'))

    assert detalle["loc"] == ["body", "datos", "mal\\ud800"]  # escrita, no repetida
    assert "nombre de campo" in detalle["msg"]


def test_los_bytes_de_una_mitad_en_cesu_8_tambien_se_rechazan(mini) -> None:
    detalle = _422(_crudo(mini, "/eco", b'{"texto": "a' + CESU + b'"}'))

    assert detalle["loc"] == ["body", "texto"]


def test_un_par_completo_escrito_con_escapes_pasa_y_llega_como_un_caracter(mini) -> None:
    respuesta = _crudo(mini, "/eco", f'{{"texto": "{PAR}", "datos": {{"{PAR}": "{PAR}"}}}}')

    assert respuesta.status_code == 200
    assert respuesta.json()["texto"] == "\U0001f600"
    assert respuesta.json()["datos"] == {"\U0001f600": "\U0001f600"}


def test_el_emoji_escrito_directo_y_el_texto_que_parece_un_escape_pasan(mini) -> None:
    directo = _crudo(mini, "/eco", '{"texto": "😀 ñ"}')
    como_texto = _crudo(mini, "/eco", r'{"texto": "\\ud800"}')  # una barra y «ud800», no un escape

    assert directo.status_code == 200 and directo.json()["texto"] == "😀 ñ"
    assert como_texto.status_code == 200 and como_texto.json()["texto"] == "\\ud800"


def test_una_mitad_alta_seguida_de_otra_alta_o_de_una_baja_sola_es_suelta(mini) -> None:
    for cuerpo in (f"{ALTA}{ALTA}", f"{BAJA}{ALTA}", f"{BAJA}", f"x{ALTA}x"):
        assert _422(_crudo(mini, "/eco", f'{{"texto": "{cuerpo}"}}'))["type"] == "mitad_suelta"


def test_el_cuerpo_llega_intacto_aunque_se_haya_leido_y_en_trozos(mini) -> None:
    # con un par completo escapado: el filtro lo lee (hay un escape sospechoso) y debe devolverlo
    cuerpo = (
        '{"texto": "uno ' + PAR + '", "lista": ' + json.dumps(list(range(500))) + "}"
    ).encode()

    def trozos():
        for i in range(0, len(cuerpo), 7):
            yield cuerpo[i : i + 7]

    respuesta = mini.post("/eco", content=trozos(), headers=JSON)  # Transfer-Encoding: chunked

    assert respuesta.status_code == 200
    assert respuesta.json()["lista"] == list(range(500))


def test_una_mitad_suelta_en_un_cuerpo_en_trozos_tambien_se_rechaza(mini) -> None:
    cuerpo = f'{{"texto": "{ALTA}"}}'.encode()

    respuesta = mini.post(
        "/eco", content=(cuerpo[i : i + 5] for i in range(0, len(cuerpo), 5)), headers=JSON
    )

    assert _422(respuesta)["loc"] == ["body", "texto"]


def test_un_cuerpo_sin_nada_sospechoso_no_se_lee(mini, monkeypatch) -> None:
    def no_deberia(*args, **kwargs):
        raise AssertionError("se recorrio un cuerpo sin sospechas")

    monkeypatch.setattr(filtro, "buscar_mitad_suelta", no_deberia)
    barra = chr(92)  # escapes que no son mitades: salto de linea, n con tilde y e con tilde
    cuerpo = '{"texto": "peña 😀 ñandú ' + barra + "n " + barra + "u00f1 " + barra + 'u00e9"}'

    respuesta = _crudo(mini, "/eco", cuerpo)

    assert respuesta.status_code == 200  # ni una mitad ni un escape que pueda serlo


def test_un_json_roto_lo_responde_fastapi_como_siempre_y_no_da_500(mini) -> None:
    roto = _crudo(mini, "/eco", f'{{"texto": "{ALTA}')  # sin cerrar y con una mitad
    otro = _crudo(mini, "/eco", '{"texto": ')

    assert roto.status_code == 422 and roto.json()["detail"][0]["type"] == "json_invalid"
    assert otro.status_code == 422 and otro.json()["detail"][0]["type"] == "json_invalid"


def test_un_cuerpo_que_no_es_utf_8_ni_cesu_no_da_500(mini) -> None:
    respuesta = _crudo(mini, "/eco", b'{"texto": "\xff\xfe"}')

    assert respuesta.status_code in (400, 422)


def test_un_json_anidado_mas_alla_de_lo_que_lee_json_no_da_500(mini) -> None:
    cuerpo = ("[" * 200_000 + f'"{ALTA}"' + "]" * 200_000).encode()

    respuesta = _crudo(mini, "/tamano", cuerpo)

    assert respuesta.status_code in (400, 422)


def test_solo_se_miran_los_cuerpos_json(mini) -> None:
    texto = _crudo(mini, "/eco", f'{{"texto": "{ALTA}"}}', **{"content-type": "text/plain"})
    json_raro = _crudo(
        mini, "/eco", f'{{"texto": "{ALTA}"}}', **{"content-type": "application/vnd.x+json"}
    )

    assert texto.status_code == 422 and texto.json()["detail"][0]["type"] != "mitad_suelta"
    assert json_raro.json()["detail"][0]["type"] == "mitad_suelta"


def test_una_peticion_sin_cuerpo_pasa_sin_tocarse(mini) -> None:
    assert mini.get("/q", params={"t": "hola"}).json()["t"] == "'hola'"


# --- Las demas entradas no pueden traer una mitad suelta ------------------------------------------


def test_la_consulta_la_ruta_y_el_formulario_no_traen_mitades_sueltas(mini) -> None:
    assert mini.get("/q?t=%ED%A0%80").json()["hay_mitad"] is False  # llega como U+FFFD
    assert mini.get("/p/%ED%A0%80").json()["hay_mitad"] is False
    formulario = mini.post(
        "/form",
        content=b"t=%ED%A0%80",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    crudo = mini.post(
        "/form", content=b"t=" + CESU, headers={"content-type": "application/x-www-form-urlencoded"}
    )
    assert formulario.json()["hay_mitad"] is False and crudo.json()["hay_mitad"] is False


def test_el_multipart_y_las_cabeceras_no_traen_mitades_sueltas(mini) -> None:
    cuerpo = (
        b'--B\r\nContent-Disposition: form-data; name="t"\r\n\r\n' + CESU + b"\r\n"
        b'--B\r\nContent-Disposition: form-data; name="a"; filename="' + CESU + b'.csv"\r\n'
        b"Content-Type: text/csv\r\n\r\nx\r\n--B--\r\n"
    )
    respuesta = mini.post(
        "/multipart", content=cuerpo, headers={"content-type": "multipart/form-data; boundary=B"}
    )

    assert respuesta.status_code == 200 and respuesta.json()["hay_mitad"] is False
    assert mini.get("/h", headers={"x": CESU}).json()["hay_mitad"] is False


# --- El manejador de 422 nunca repite una mitad suelta --------------------------------------------


def test_aunque_una_mitad_se_colara_el_422_se_puede_serializar() -> None:
    # Sin el filtro: el valor llega a pydantic, que rechaza el largo y repite el `input`.
    sin_filtro = TestClient(_mini(con_filtro=False), raise_server_exceptions=False)

    respuesta = _crudo(sin_filtro, "/eco", f'{{"corto": "x{ALTA}yyyy"}}')

    assert respuesta.status_code == 422
    detalle = respuesta.json()["detail"][0]
    assert detalle["loc"] == ["body", "corto"] and "demasiado largo" in detalle["msg"]
    assert detalle["input"] == "x\\ud800yyyy"  # escrita como texto, no repetida


def test_sin_el_manejador_ese_mismo_422_revienta() -> None:
    # La prueba de que el manejador hace falta: el de FastAPI da 500 con la misma mitad.
    por_defecto = FastAPI()

    @por_defecto.post("/eco")
    def eco(cuerpo: Cuerpo) -> dict:
        return {}

    cliente = TestClient(por_defecto, raise_server_exceptions=False)

    assert _crudo(cliente, "/eco", f'{{"corto": "x{ALTA}yyyy"}}').status_code == 500


def test_el_manejador_no_cambia_un_422_normal() -> None:
    mini = TestClient(_mini(), raise_server_exceptions=False)

    detalle = _422(_crudo(mini, "/eco", '{"corto": "abcdef"}'))

    assert (detalle["type"], detalle["loc"], detalle["input"]) == (
        "value_error",
        ["body", "corto"],
        "abcdef",
    )


# --- Las dos rutas de MOWA MES donde se encontro --------------------------------------------------

RUTAS_DE_CAMPANA = ["/mowa-mes/campanas/previsualizacion", "/mowa-mes/campanas"]


def _cuerpo_de_campana(descripcion_json: str, **extra) -> str:
    """El cuerpo de una campana como TEXTO: la descripcion va tal cual, con sus escapes."""
    cuerpo = json.dumps({**CUERPO, **extra})[:-1]
    return f'{cuerpo}, "descripcion": "{descripcion_json}"}}'


@pytest.mark.parametrize("ruta", RUTAS_DE_CAMPANA)
def test_la_descripcion_con_una_mitad_suelta_es_422_con_el_campo_nombrado(ruta) -> None:
    client = _cliente(EntornoMowaMes())

    respuesta = _crudo(client, ruta, _cuerpo_de_campana(f"Campana {ALTA}"))

    detalle = _422(respuesta)
    assert (detalle["type"], detalle["loc"]) == ("mitad_suelta", ["body", "descripcion"])


@pytest.mark.parametrize("ruta", RUTAS_DE_CAMPANA)
def test_una_descripcion_larga_con_una_mitad_suelta_tambien_es_422_y_no_500(ruta) -> None:
    client = _cliente(EntornoMowaMes())
    larga = "a" * (LARGO_MAXIMO_DESCRIPCION + 10) + ALTA

    respuesta = _crudo(client, ruta, _cuerpo_de_campana(larga))

    detalle = _422(respuesta)
    assert detalle["loc"] == ["body", "descripcion"] and "input" not in detalle


def test_un_emoji_completo_en_la_descripcion_pasa_y_mide_dos() -> None:
    client = _cliente(EntornoMowaMes())
    cabe = "a" * (LARGO_MAXIMO_DESCRIPCION - 2) + PAR  # el emoji son 2 unidades UTF-16: justo
    pasa = "a" * (LARGO_MAXIMO_DESCRIPCION - 1) + PAR  # 1 + 2 = una unidad de mas

    justo = _crudo(client, RUTAS_DE_CAMPANA[0], _cuerpo_de_campana(cabe))
    de_mas = _crudo(client, RUTAS_DE_CAMPANA[0], _cuerpo_de_campana(pasa))

    assert justo.status_code == 200
    assert justo.json()["descripcion"].endswith("\U0001f600")
    assert de_mas.status_code == 422 and de_mas.json()["detail"][0]["type"] == "value_error"
    assert de_mas.json()["detail"][0]["loc"] == ["body", "descripcion"]  # lo dice B10, no el filtro


def test_la_creacion_con_un_emoji_completo_guarda_la_descripcion() -> None:
    client = _cliente(EntornoMowaMes())

    creada = _crudo(
        client,
        "/mowa-mes/campanas",
        _cuerpo_de_campana("Campana " + PAR, speech_huella=HUELLA_ORIGINAL),
    )

    assert creada.status_code == 201, creada.text
    assert creada.json()["descripcion"] == "Campana \U0001f600"


# --- El recorrido de todas las rutas con cuerpo JSON ----------------------------------------------


def _resolver(esquema: dict, componentes: dict) -> dict:
    while True:
        if "$ref" in esquema:
            esquema = componentes[esquema["$ref"].rsplit("/", 1)[-1]]
        elif "allOf" in esquema and len(esquema["allOf"]) == 1:
            esquema = esquema["allOf"][0]
        elif "anyOf" in esquema or "oneOf" in esquema:
            opciones = esquema.get("anyOf") or esquema["oneOf"]
            esquema = next((o for o in opciones if o.get("type") != "null"), opciones[0])
        else:
            return esquema


def _minimo(esquema: dict, componentes: dict, profundidad: int = 0) -> Any:
    """Un valor que cumple el esquema, el mas chico que se arma sin pensar (no hace falta que la
    ruta lo acepte: el filtro responde antes; sirve para que el cuerpo tenga la forma real)."""
    esquema = _resolver(esquema, componentes)
    if "enum" in esquema:
        return esquema["enum"][0]
    tipo = esquema.get("type")
    if tipo == "object" or "properties" in esquema:
        if profundidad > 6:
            return {}
        propiedades = esquema.get("properties", {})
        return {
            nombre: _minimo(propiedades[nombre], componentes, profundidad + 1)
            for nombre in esquema.get("required", [])
            if nombre in propiedades
        }
    if tipo == "array":
        return []
    if tipo == "string":
        return {"date": "2026-09-10", "date-time": "2026-09-10T09:00:00"}.get(
            esquema.get("format"), "x" * max(1, esquema.get("minLength", 1))
        )
    if tipo == "integer":
        return int(esquema.get("minimum", 1))
    if tipo == "number":
        return float(esquema.get("minimum", 1))
    if tipo == "boolean":
        return False
    return None


def _campos_de_texto(esquema: dict, componentes: dict, ruta: tuple = (), vistos=None) -> list:
    """Las rutas (de claves) a los campos `string` libres del cuerpo, hasta cuatro niveles."""
    esquema = _resolver(esquema, componentes)
    if len(ruta) > 4:
        return []
    if esquema.get("type") == "string" and "enum" not in esquema and "format" not in esquema:
        return [ruta]
    encontrados: list = []
    for nombre, hijo in esquema.get("properties", {}).items():
        encontrados += _campos_de_texto(hijo, componentes, (*ruta, nombre))
    return encontrados


def _rutas_con_cuerpo_json() -> list[tuple[str, str, dict]]:
    esquema = app.openapi()
    componentes = esquema["components"]["schemas"]
    rutas = []
    for camino, metodos in sorted(esquema["paths"].items()):
        for metodo, operacion in sorted(metodos.items()):
            contenido = operacion.get("requestBody", {}).get("content", {})
            if "application/json" in contenido:
                cuerpo = _resolver(contenido["application/json"]["schema"], componentes)
                rutas.append((metodo.upper(), camino, cuerpo))
    return rutas


RUTAS_JSON = _rutas_con_cuerpo_json()


MARCA = "ZZMITAD"  # se cambia, ya escrito el JSON, por el escape de una mitad suelta


def _con_marca(cuerpo: dict, ruta: tuple) -> dict:
    destino = cuerpo
    for nombre in ruta[:-1]:
        destino = destino.setdefault(nombre, {})
    destino[ruta[-1]] = MARCA
    return cuerpo


def _camino(camino: str) -> str:
    return "".join("1" if parte.startswith("{") else parte for parte in camino.split("/"))


def test_el_recorrido_encuentra_las_rutas_con_cuerpo_json() -> None:
    caminos = {c for _, c, _ in RUTAS_JSON}

    assert len(RUTAS_JSON) >= 20, len(RUTAS_JSON)
    assert "/mowa-mes/campanas" in caminos and "/texto-enriquecido/validacion" in caminos
    assert "/mapeador/borradores/{borrador_id}/validacion" in caminos


@pytest.mark.parametrize(("metodo", "camino", "cuerpo"), RUTAS_JSON, ids=lambda v: str(v)[:40])
def test_cada_ruta_con_cuerpo_json_rechaza_una_mitad_suelta_en_un_texto(
    metodo, camino, cuerpo
) -> None:
    componentes = app.openapi()["components"]["schemas"]
    minimo = _minimo(cuerpo, componentes)
    campos = _campos_de_texto(cuerpo, componentes)
    # un campo de texto del esquema; si no hay ninguno, uno cualquiera (no se mira el esquema)
    ruta = campos[0] if campos else ("campo_sin_esquema",)
    enviado = _con_marca(minimo if isinstance(minimo, dict) else {}, ruta)
    contenido = json.dumps(enviado).replace(MARCA, "x" + ALTA).encode("ascii")
    cliente = TestClient(app, raise_server_exceptions=False)

    respuesta = cliente.request(metodo, _camino(camino), content=contenido, headers=JSON)

    detalle = _422(respuesta)
    assert detalle["type"] == "mitad_suelta", (metodo, camino, respuesta.text[:200])
    assert detalle["loc"] == ["body", *ruta]


@pytest.mark.parametrize(("metodo", "camino", "cuerpo"), RUTAS_JSON, ids=lambda v: str(v)[:40])
def test_cada_ruta_con_cuerpo_json_rechaza_una_mitad_suelta_en_una_clave(
    metodo, camino, cuerpo
) -> None:
    cliente = TestClient(app, raise_server_exceptions=False)
    contenido = ('{"clave' + ALTA + '": 1}').encode()

    respuesta = cliente.request(metodo, _camino(camino), content=contenido, headers=JSON)

    detalle = _422(respuesta)
    assert detalle["type"] == "mitad_suelta"
    assert detalle["loc"] == ["body", "clave\\ud800"]


def test_ninguna_ruta_con_cuerpo_json_quedo_sin_armar() -> None:
    componentes = app.openapi()["components"]["schemas"]
    sin_texto = [
        f"{metodo} {camino}"
        for metodo, camino, cuerpo in RUTAS_JSON
        if not _campos_de_texto(cuerpo, componentes)
    ]

    # Las que no tienen un campo de texto en su esquema se cubren por la clave (la prueba de
    # arriba): se listan para que alguien las vea si cambia el esquema.
    assert sin_texto == [] or all(" /" in ruta for ruta in sin_texto), sin_texto


# --- La aplicacion real lo tiene conectado -------------------------------------------------------


def test_la_aplicacion_real_tiene_el_filtro_y_el_manejador_de_422() -> None:
    assert any(m.cls is RechazaMitadesSueltas for m in app.user_middleware)
    assert app.exception_handlers[RequestValidationError] is manejar_validacion


def test_un_422_normal_de_la_aplicacion_real_conserva_su_forma() -> None:
    cliente = TestClient(app, raise_server_exceptions=False)

    respuesta = _crudo(cliente, "/mowa-mes/campanas/previsualizacion", '{"cantidad": 0}')

    detalle = respuesta.json()["detail"]
    assert respuesta.status_code == 422
    assert {"type", "loc", "msg", "input"} <= set(detalle[0])  # lo de siempre, con su `input`


# --- Un multipart no se lee: solo se miran los cuerpos JSON --------------------------------------


@pytest.mark.parametrize(
    "tipo",
    [
        "multipart/form-data; boundary=B",
        "application/x-www-form-urlencoded",
        "application/octet-stream",
        "text/csv",
        "application/vnd.ms-excel",
        "",
    ],
)
def test_el_filtro_ni_lee_ni_acumula_un_cuerpo_que_no_es_json(tipo) -> None:
    """Una sabana o un archivo del mapeador (hasta 64 MB) llega como multipart: el filtro lo deja
    pasar con el `receive` ORIGINAL, sin pedirle ni un trozo. Lo que se lee, lo lee la ruta."""
    pedidos = []
    entregado = []

    async def receive():
        pedidos.append(1)
        return {"type": "http.request", "body": b"x" * (1024 * 1024), "more_body": True}

    async def interna(scope, receive_recibido, send):
        entregado.append(receive_recibido)

    cabeceras = [(b"content-type", tipo.encode())] if tipo else []
    filtro_asgi = RechazaMitadesSueltas(interna)

    asyncio.run(filtro_asgi({"type": "http", "headers": cabeceras}, receive, None))

    assert pedidos == [] and entregado == [receive]


def test_un_multipart_grande_pasa_por_la_aplicacion_sin_que_el_filtro_lo_acumule(mini) -> None:
    contenido = b"fila;x\n" * 600_000  # unos 4 MB, con la secuencia de una mitad dentro
    contenido += ALTA.encode() + b" " + CESU + b"\n"  # no es JSON: el multipart no se revisa
    cuerpo = (
        b'--B\r\nContent-Disposition: form-data; name="t"\r\n\r\nx\r\n'
        b'--B\r\nContent-Disposition: form-data; name="a"; filename="g.csv"\r\n'
        b"Content-Type: text/csv\r\n\r\n" + contenido + b"\r\n--B--\r\n"
    )

    respuesta = mini.post(
        "/multipart", content=cuerpo, headers={"content-type": "multipart/form-data; boundary=B"}
    )

    assert respuesta.status_code == 200 and respuesta.json()["hay_mitad"] is False


# --- Un cuerpo que llega en varios mensajes del servidor -----------------------------------------
# El cliente de pruebas junta todo el cuerpo en un solo mensaje: aqui se arma `receive` a mano.


def _correr_filtro(trozos: list[bytes]):
    pendientes = [
        {"type": "http.request", "body": t, "more_body": i < len(trozos) - 1}
        for i, t in enumerate(trozos)
    ]
    respondio, recibio_la_aplicacion = [], []

    async def receive():
        return pendientes.pop(0) if pendientes else {"type": "http.disconnect"}

    async def send(mensaje):
        respondio.append(mensaje)

    async def interna(scope, receive_recibido, send_recibido):
        while True:
            mensaje = await receive_recibido()
            if mensaje["type"] != "http.request":
                break
            recibio_la_aplicacion.append(mensaje["body"])
            if not mensaje.get("more_body", False):
                break

    scope = {"type": "http", "headers": [(b"content-type", b"application/json")]}
    asyncio.run(RechazaMitadesSueltas(interna)(scope, receive, send))
    return respondio, recibio_la_aplicacion


def test_una_mitad_suelta_en_el_primer_trozo_de_un_cuerpo_se_rechaza() -> None:
    cuerpo = ('{"texto": "x' + ALTA + '", "lista": [1, 2, 3]}').encode()
    trozos = [cuerpo[:14], cuerpo[14:30], cuerpo[30:]]  # la mitad queda en el primero o el segundo

    respondio, recibio = _correr_filtro(trozos)

    assert respondio[0]["status"] == 422 and recibio == []  # y la aplicacion no corre


def test_la_aplicacion_recibe_todos_los_trozos_del_cuerpo_en_orden() -> None:
    cuerpo = ('{"texto": "uno ' + PAR + '", "lista": [1, 2, 3]}').encode()
    trozos = [cuerpo[:10], cuerpo[10:25], cuerpo[25:]]

    respondio, recibio = _correr_filtro(trozos)

    assert respondio == [] and recibio == trozos
