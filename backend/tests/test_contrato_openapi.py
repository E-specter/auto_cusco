"""Prueba de contrato: contratos/openapi.json coincide con la API real.

El frontend comprueba sus tipos contra ese archivo (docs/contrato-api.md). Si un
endpoint cambia y el archivo no se regenera, el frontend seguiria validando
contra una API que ya no existe. Estas pruebas lo impiden, y ademas cuidan que
el contrato diga algo util: que cada respuesta declare su forma, que los
errores tengan el cuerpo comun y que la descarga describa lo que de verdad
envia.
"""

from fastapi.testclient import TestClient

from app.api import contrato
from app.api.archivos_carga import CABECERAS_RESUMEN
from app.api.cartera import obtener_servicio_cartera
from app.core.entities.exportacion import TIPOS_MIME
from app.main import app
from tests.test_api_archivos_carga import DEFINICION, ConsultaFalsa

ESQUEMA = contrato.generar()


def _respuestas():
    for ruta, metodos in ESQUEMA["paths"].items():
        for metodo, operacion in metodos.items():
            for codigo, respuesta in operacion["responses"].items():
                yield f"{metodo.upper()} {ruta} -> {codigo}", codigo, respuesta


def _resolver_propiedades(esquema: dict) -> tuple[dict, set[str]]:
    """Sigue `$ref` y aplana `allOf`: junta las propiedades y los obligatorios
    de un esquema y de todo lo que extiende, sin asumir que la extension se
    declaro con `allOf` (una subclase de Pydantic sin composicion explicita
    genera un esquema propio, plano, con sus propias `properties`)."""
    esquemas = ESQUEMA["components"]["schemas"]
    propiedades: dict = {}
    requeridos: set[str] = set()
    pendientes = [esquema]
    while pendientes:
        nodo = pendientes.pop()
        referencia = nodo.get("$ref")
        if referencia:
            pendientes.append(esquemas[referencia.rsplit("/", 1)[-1]])
            continue
        pendientes.extend(nodo.get("allOf", []))
        propiedades.update(nodo.get("properties", {}))
        requeridos.update(nodo.get("required", []))
    return propiedades, requeridos


def _es_forma_libre(esquema: dict) -> bool:
    """Un esquema vacio o un objeto sin propiedades no le dice nada al frontend."""
    if not esquema:
        return True
    return (
        esquema.get("type") == "object"
        and esquema.get("additionalProperties") is True
        and "properties" not in esquema
    )


def test_el_contrato_versionado_coincide_con_la_api() -> None:
    versionado = contrato.leer()

    assert versionado is not None, (
        f"Falta {contrato.RUTA_CONTRATO}. Generalo con: {contrato.COMANDO_REGENERAR}"
    )
    assert versionado == ESQUEMA, (
        f"La API cambio y el contrato no. Regeneralo con: {contrato.COMANDO_REGENERAR}"
    )


def test_la_exportacion_es_estable() -> None:
    assert contrato.serializar(contrato.generar()) == contrato.serializar(ESQUEMA)


def test_toda_respuesta_exitosa_declara_su_forma() -> None:
    sin_forma = [
        nombre
        for nombre, codigo, respuesta in _respuestas()
        if codigo.startswith("2")
        for contenido in respuesta.get("content", {}).values()
        if _es_forma_libre(contenido.get("schema", {}))
    ]

    assert sin_forma == [], (
        f"Respuestas sin forma declarada, el frontend no puede tiparlas: {sin_forma}"
    )


def test_los_errores_declarados_traen_detail_obligatorio() -> None:
    # 422 lo declara FastAPI con su propio esquema de validacion. Un endpoint
    # puede declarar en el 4xx su propio modelo en vez de DetalleError (por
    # ejemplo para agregar un `codigo`, ver mowa-mes.md §15), siempre que
    # conserve `detail` como string obligatorio: el cliente compartido
    # (frontend/src/lib/api.ts) lo usa para el mensaje. Sin excepciones por
    # nombre de endpoint (docs/contrato-api.md, seccion 3).
    sin_detail = []
    for nombre, codigo, respuesta in _respuestas():
        if not codigo.startswith("4") or codigo == "422":
            continue
        propiedades, requeridos = _resolver_propiedades(
            respuesta["content"]["application/json"]["schema"]
        )
        detail = propiedades.get("detail")
        if detail is None or detail.get("type") != "string" or "detail" not in requeridos:
            sin_detail.append(nombre)

    assert sin_detail == [], f"Errores sin 'detail' obligatorio de tipo string: {sin_detail}"


def test_la_descarga_declara_el_archivo_y_su_resumen() -> None:
    respuesta = ESQUEMA["paths"]["/archivos-carga"]["post"]["responses"]["200"]

    assert set(respuesta["content"]) == set(TIPOS_MIME.values())
    assert all(c["schema"]["format"] == "binary" for c in respuesta["content"].values())
    assert set(respuesta["headers"]) == {"Content-Disposition", *CABECERAS_RESUMEN}


def test_las_cabeceras_que_envia_la_descarga_son_las_declaradas() -> None:
    app.dependency_overrides[obtener_servicio_cartera] = lambda: ConsultaFalsa()
    try:
        respuesta = TestClient(app).post(
            "/archivos-carga",
            json={"fecha_corte": "2026-09-10", "definicion": DEFINICION, "formato": "csv"},
        )
    finally:
        app.dependency_overrides.clear()

    enviadas = {nombre for nombre in respuesta.headers if nombre.startswith("x-carga-")}
    assert respuesta.status_code == 200
    assert enviadas == {nombre.lower() for nombre in CABECERAS_RESUMEN}


def _esquemas_de_respuesta() -> set[str]:
    """Nombres de los esquemas alcanzables desde alguna respuesta exitosa."""
    esquemas = ESQUEMA["components"]["schemas"]
    pendientes: list = [
        contenido.get("schema", {})
        for _, codigo, respuesta in _respuestas()
        if codigo.startswith("2")
        for contenido in respuesta.get("content", {}).values()
    ]
    vistos: set[str] = set()
    while pendientes:
        nodo = pendientes.pop()
        if isinstance(nodo, list):
            pendientes.extend(nodo)
        elif isinstance(nodo, dict):
            referencia = nodo.get("$ref", "")
            nombre = referencia.rsplit("/", 1)[-1]
            if referencia and nombre not in vistos:
                vistos.add(nombre)
                pendientes.append(esquemas[nombre])
            pendientes.extend(nodo.values())
    return vistos


def test_todo_campo_de_una_respuesta_es_obligatorio() -> None:
    # Opcional en el contrato significa "a veces no viene". Un campo que el backend
    # siempre envia va obligatorio, con null en su tipo si puede venir vacio; si no,
    # el frontend tiene que tratarlo como si pudiera faltar. Ver ModeloRespuesta.
    esquemas = ESQUEMA["components"]["schemas"]

    opcionales = sorted(
        f"{nombre}.{campo}"
        for nombre in _esquemas_de_respuesta()
        for campo in esquemas[nombre].get("properties", {})
        if campo not in esquemas[nombre].get("required", [])
    )

    assert opcionales == [], f"Campos de respuesta opcionales en el contrato: {opcionales}"
