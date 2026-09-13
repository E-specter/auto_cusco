"""Utilidades del adaptador HTTP para las consultas de cartera.

La lectura de filtros, orden e indicadores vive en el nucleo
(`app/core/services/seleccion_cartera/expresiones.py`) porque tambien la usan
las selecciones guardadas; se reexporta aqui para los routers.
"""

from decimal import Decimal
from typing import Any

from fastapi import HTTPException

from app.core.entities.cartera import SinVersionVigente
from app.core.services.seleccion_cartera.expresiones import (
    parsear_filtro,
    parsear_indicador,
    parsear_orden,
)

__all__ = [
    "parsear_filtro",
    "parsear_indicador",
    "parsear_orden",
    "texto_si_es_monto",
    "traducir_errores",
]


def texto_si_es_monto(valor: Any) -> Any:
    """Los montos viajan como texto para no perder precision al pasar por JSON."""
    return str(valor) if isinstance(valor, Decimal) else valor


def traducir_errores(exc: Exception) -> HTTPException:
    """Una fecha sin version vigente es un 404; una consulta mal armada, un 400."""
    if isinstance(exc, SinVersionVigente):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))
