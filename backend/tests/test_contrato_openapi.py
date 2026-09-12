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
REFERENCIA_ERROR = "#/components/schemas/DetalleError"


def _respuestas():
    for ruta, metodos in ESQUEMA["paths"].items():
        for metodo, operacion in metodos.items():
            for codigo, respuesta in operacion["responses"].items():
                yield f"{metodo.upper()} {ruta} -> {codigo}", codigo, respuesta


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


def test_los_errores_declarados_usan_el_cuerpo_comun() -> None:
    # 422 lo declara FastAPI con su propio esquema de validacion.
    distintos = [
        nombre
        for nombre, codigo, respuesta in _respuestas()
        if codigo.startswith("4") and codigo != "422"
        if respuesta["content"]["application/json"]["schema"] != {"$ref": REFERENCIA_ERROR}
    ]

    assert distintos == []


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
