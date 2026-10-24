"""Cuerpo de error comun de la API y su declaracion en el contrato OpenAPI.

Cuando un endpoint lanza `HTTPException`, FastAPI responde `{"detail": "..."}`,
pero no lo declara en el esquema. Declararlo en cada endpoint deja escrito en
el contrato que codigos puede recibir el frontend y con que forma, en vez de
que lo descubra en produccion.
"""

from collections.abc import Mapping
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.api.respuestas import ModeloRespuesta
from app.core.entities.texto_enriquecido import CodigoTexto


class DetalleError(ModeloRespuesta):
    """Motivo legible por el que la API rechazo la peticion."""

    detail: str


_DESCRIPCIONES = {
    400: "La peticion no se puede atender tal como viene; el motivo esta en detail",
    404: "No existe lo pedido",
    409: "La operacion choca con el estado actual",
    413: "El archivo supera el tamano maximo",
}


class DetalleErrorConCodigo(DetalleError):
    """Un error que, ademas del motivo, puede traer el `codigo` que la interfaz traduce.

    `codigo` es nulo en los errores que todavia no tienen uno (una seleccion mal armada, una
    plantilla invalida); siempre viaja, para que el cliente no tenga que adivinar si falta. Cuando
    viaja es de `CodigoTexto`.
    """

    codigo: CodigoTexto | None


class ErrorConCodigo(Exception):
    """Se lanza desde un endpoint y el manejador de `main.py` lo responde con `codigo`.

    `HTTPException` solo sabe enviar `{"detail": ...}`. `extra` suma campos estructurados al
    cuerpo (las dos fechas de un rechazo por fecha de envio), para no obligar a leer la prosa.
    """

    def __init__(
        self,
        estado: int,
        detalle: str,
        codigo: CodigoTexto | None,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(detalle)
        self.estado = estado
        self.detalle = detalle
        self.codigo = codigo
        self.extra = dict(extra or {})


def manejar_error_con_codigo(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ErrorConCodigo)
    codigo = None if error.codigo is None else error.codigo.value
    return JSONResponse(
        status_code=error.estado,
        content={"detail": error.detalle, "codigo": codigo, **error.extra},
    )


def respuestas_de_error_con_codigo(*codigos: int) -> dict[int | str, dict[str, Any]]:
    """Como `respuestas_de_error`, para los endpoints que responden con `ErrorConCodigo`."""
    return {
        codigo: {"model": DetalleErrorConCodigo, "description": _DESCRIPCIONES[codigo]}
        for codigo in codigos
    }


def respuestas_de_error(*codigos: int) -> dict[int | str, dict[str, Any]]:
    """Declaracion OpenAPI de los errores que un endpoint puede devolver."""
    return {
        codigo: {"model": DetalleError, "description": _DESCRIPCIONES[codigo]} for codigo in codigos
    }
