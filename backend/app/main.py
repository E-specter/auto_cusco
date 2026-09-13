"""Punto de entrada de la API REST de auto_cusco.

Arranque en desarrollo (desde backend/, con el entorno uv sincronizado):

    uv run fastapi dev app/main.py

Ver docs/architecture.md para el mapa general y docs/modules.md para el
desglose de modulos y el enfoque de puertos/adaptadores con vertical
slicing (RF-30) que sigue esta app.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.archivos_carga import CABECERAS_RESUMEN
from app.api.archivos_carga import router as archivos_carga_router
from app.api.calendario import router as calendario_router
from app.api.cargas import crear_servicio_ingesta
from app.api.cargas import router as cargas_router
from app.api.cartera import router as cartera_router
from app.api.health import router as health_router
from app.api.mowa_mes import router as mowa_mes_router
from app.api.selecciones import router as selecciones_router
from app.api.supervisores import router as supervisores_router
from app.core.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Al arrancar, devuelve a la cola las versiones que quedaron a medio procesar.

    Asume un solo proceso de la aplicacion: si mas adelante corren varios, esto
    debe moverse a un sistema de colas (ver docs/versionado-sabanas.md).
    """
    try:
        crear_servicio_ingesta().recuperar_interrumpidas()
    except Exception as exc:
        logger.warning(
            "No se pudo revisar las versiones interrumpidas al arrancar (%s)", type(exc).__name__
        )
    yield


def configurar_cors(aplicacion: FastAPI, origenes: list[str]) -> None:
    """Permite que un frontend servido en otro origen consuma la API.

    Sin origenes configurados no se agrega el middleware y la API no envia
    cabeceras CORS. En desarrollo no hacen falta: el dev server de Astro
    redirige /api al backend, asi que el navegador ve un solo origen. Se
    activa completando CORS_ORIGENES en /.env.
    """
    if not origenes:
        return
    aplicacion.add_middleware(
        CORSMiddleware,
        allow_origins=origenes,
        allow_credentials=False,  # la API aun no usa cookies ni sesiones
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
        # Sin esto el navegador no deja leer el nombre del archivo generado ni
        # el resumen de la carga cuando el frontend corre en otro origen.
        expose_headers=["Content-Disposition", *CABECERAS_RESUMEN],
    )
    logger.info("CORS habilitado para %s", origenes)


app = FastAPI(
    title="auto_cusco API",
    description=(
        "API REST del backend de auto_cusco: ingesta de sabanas, seleccion "
        "y segmentacion de cartera, generacion de cargas (digitales y VoIP) "
        "y reportes de cobranza."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

configurar_cors(app, get_settings().origenes_cors)

app.include_router(health_router)
app.include_router(cargas_router)
app.include_router(cartera_router)
app.include_router(archivos_carga_router)
app.include_router(selecciones_router)
app.include_router(calendario_router)
app.include_router(supervisores_router)
app.include_router(mowa_mes_router)
