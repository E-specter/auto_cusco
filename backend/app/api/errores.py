"""Cuerpo de error comun de la API y su declaracion en el contrato OpenAPI.

Cuando un endpoint lanza `HTTPException`, FastAPI responde `{"detail": "..."}`,
pero no lo declara en el esquema. Declararlo en cada endpoint deja escrito en
el contrato que codigos puede recibir el frontend y con que forma, en vez de
que lo descubra en produccion.
"""

from typing import Any

from app.api.respuestas import ModeloRespuesta


class DetalleError(ModeloRespuesta):
    """Motivo legible por el que la API rechazo la peticion."""

    detail: str


_DESCRIPCIONES = {
    400: "La peticion no se puede atender tal como viene; el motivo esta en detail",
    404: "No existe lo pedido",
    409: "La operacion choca con el estado actual",
    413: "El archivo supera el tamano maximo",
}


def respuestas_de_error(*codigos: int) -> dict[int | str, dict[str, Any]]:
    """Declaracion OpenAPI de los errores que un endpoint puede devolver."""
    return {
        codigo: {"model": DetalleError, "description": _DESCRIPCIONES[codigo]} for codigo in codigos
    }
