"""Punto de entrada de la API REST de auto_cusco.

Arranque en desarrollo (desde backend/, con el entorno uv sincronizado):

    uv run fastapi dev app/main.py

Ver docs/architecture.md para el mapa general y docs/modules.md para el
desglose de modulos y el enfoque de puertos/adaptadores con vertical
slicing (RF-30) que sigue esta app.
"""

from fastapi import FastAPI

from app.api.health import router as health_router

app = FastAPI(
    title="auto_cusco API",
    description=(
        "API REST del backend de auto_cusco: ingesta de sabanas, seleccion "
        "y segmentacion de cartera, generacion de cargas (digitales y VoIP) "
        "y reportes de cobranza."
    ),
    version="0.1.0",
)

app.include_router(health_router)
