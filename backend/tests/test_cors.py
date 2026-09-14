"""Pruebas de CORS: desactivado por defecto, activo solo con CORS_ORIGENES."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.archivos_carga import CABECERAS_RESUMEN
from app.api.mowa_mes_campanas import CABECERAS_ARCHIVO
from app.core.config import Settings
from app.main import app, configurar_cors

ORIGEN = "https://app.ejemplo.pe"
OTRO_ORIGEN = "https://otro.ejemplo.pe"


def _cliente_con_cors(origenes: list[str]) -> TestClient:
    aplicacion = FastAPI()
    configurar_cors(aplicacion, origenes)

    @aplicacion.get("/prueba")
    def prueba() -> dict:
        return {"ok": True}

    return TestClient(aplicacion)


def test_sin_origenes_configurados_la_api_no_envia_cabeceras_cors() -> None:
    # La app real: CORS_ORIGENES esta vacio salvo que se configure en /.env.
    respuesta = TestClient(app).get("/ruta-inexistente", headers={"Origin": ORIGEN})

    assert "access-control-allow-origin" not in respuesta.headers


def test_un_origen_permitido_recibe_la_cabecera() -> None:
    respuesta = _cliente_con_cors([ORIGEN]).get("/prueba", headers={"Origin": ORIGEN})

    assert respuesta.headers["access-control-allow-origin"] == ORIGEN


def test_un_origen_no_permitido_no_recibe_la_cabecera() -> None:
    respuesta = _cliente_con_cors([ORIGEN]).get("/prueba", headers={"Origin": OTRO_ORIGEN})

    assert "access-control-allow-origin" not in respuesta.headers


def test_la_consulta_previa_permite_los_metodos_que_usa_la_api() -> None:
    respuesta = _cliente_con_cors([ORIGEN]).options(
        "/prueba",
        headers={
            "Origin": ORIGEN,
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    permitidos = {m.strip() for m in respuesta.headers["access-control-allow-methods"].split(",")}
    assert respuesta.status_code == 200
    assert {"GET", "POST", "DELETE"} <= permitidos


def test_el_navegador_puede_leer_el_nombre_y_el_resumen_de_la_descarga() -> None:
    # Las cabeceras expuestas salen de la misma lista que declara el contrato OpenAPI.
    respuesta = _cliente_con_cors([ORIGEN]).get("/prueba", headers={"Origin": ORIGEN})

    expuestas = {c.strip() for c in respuesta.headers["access-control-expose-headers"].split(",")}
    assert expuestas == {"Content-Disposition", *CABECERAS_RESUMEN, *CABECERAS_ARCHIVO}


def test_los_origenes_se_leen_separados_por_comas() -> None:
    ajustes = Settings(cors_origenes=" http://localhost:4321 , https://app.ejemplo.pe ,, ")

    assert ajustes.origenes_cors == ["http://localhost:4321", "https://app.ejemplo.pe"]


def test_sin_configuracion_no_hay_origenes() -> None:
    assert Settings(cors_origenes="").origenes_cors == []
