"""La API no acepta una mitad suelta de un par sustituto, en ninguna ruta (T-API-B1).

Un JSON puede traer escrita (`"\\ud800"`) una mitad suelta de un par sustituto, o los tres bytes que
la codifican en CESU-8: `json.loads` la acepta, pydantic tambien, y despues la respuesta (o el
guardado, o el archivo) revienta con un 500. Es el unico camino por donde llega: el resto de las
entradas (consultas, rutas, formularios, multipart y cabeceras) se lee como UTF-8 o Latin-1 y no las
puede traer; `tests/test_api_texto_valido.py` lo comprueba con cada una.

Por eso un solo filtro para TODA la API, antes de las rutas, y no uno por ruta ni por modelo:

- `RechazaMitadesSueltas` (ASGI puro, en `main.py`) mira el cuerpo de una peticion JSON ANTES de que
  corra cualquier ruta o dependencia, asi que nunca hay nada guardado. Si el cuerpo no trae una
  secuencia que pueda ser una mitad suelta (casi siempre: una busqueda de bytes) no lo lee. Si la
  trae, lo lee, recorre valores Y claves y, ante una mitad suelta, responde 422 con la misma forma
  de siempre y la ruta del campo en `loc`. Un par completo (un emoji) pasa.
- `manejar_validacion` reemplaza el manejador de 422 de FastAPI: es el mismo, pero escribe como
  texto cualquier mitad suelta que se haya colado en `input`, `loc` o `ctx`, para que el 422 siempre
  se pueda serializar (un 422 que repite el valor era otro camino al 500).
"""

import json
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.services.texto_valido import (
    SOSPECHA_EN_BYTES,
    Hallazgo,
    a_texto_seguro,
    buscar_mitad_suelta,
)

TIPO_DE_ERROR = "mitad_suelta"


def _es_json(scope: Scope) -> bool:
    """Si FastAPI leera el cuerpo como JSON: `application/json` o `application/*+json`.

    Un cuerpo sin Content-Type no se mira: FastAPI (`strict_content_type=True` por defecto) no lo
    parsea como JSON. Si alguna ruta lo desactiva, el filtro tendria que mirar tambien esos cuerpos.
    """
    for nombre, valor in scope["headers"]:
        if nombre == b"content-type":
            tipo = valor.split(b";", 1)[0].strip().lower()
            return tipo == b"application/json" or (
                tipo.startswith(b"application/") and tipo.endswith(b"+json")
            )
    return False


def _error_de(hallazgo: Hallazgo) -> dict[str, Any]:
    donde = "un nombre de campo" if hallazgo.en_clave else "un texto"
    return {
        "type": TIPO_DE_ERROR,
        "loc": ["body", *hallazgo.ruta],
        "msg": (
            f"Hay {donde} con una mitad suelta de un par sustituto ({hallazgo.codigo}): "
            "no es texto valido"
        ),
        "ctx": {"punto_de_codigo": hallazgo.codigo},
    }


def respuesta_422(errores: list[Any]) -> JSONResponse:
    """El 422 de la API: `{"detail": [...]}` como el de FastAPI, siempre serializable."""
    return JSONResponse(status_code=422, content={"detail": a_texto_seguro(errores)})


async def manejar_validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
    return respuesta_422(jsonable_encoder(exc.errors()))


class RechazaMitadesSueltas:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not _es_json(scope):
            await self.app(scope, receive, send)
            return
        # Se lee todo el cuerpo (FastAPI lo lee igual) y se devuelve a la aplicacion tal cual.
        mensajes: list[Message] = []
        cuerpo = bytearray()
        while True:
            mensaje = await receive()
            mensajes.append(mensaje)
            if mensaje["type"] != "http.request":
                break
            cuerpo += mensaje.get("body", b"")
            if not mensaje.get("more_body", False):
                break

        pendientes = iter(mensajes)

        async def receive_de_nuevo() -> Message:
            return next(pendientes, None) or await receive()

        if SOSPECHA_EN_BYTES.search(cuerpo):
            try:
                valor = json.loads(cuerpo)
            except (ValueError, RecursionError):
                valor = None  # un JSON roto o en otra codificacion lo responde FastAPI como siempre
            hallazgo = buscar_mitad_suelta(valor)
            if hallazgo is not None:
                await respuesta_422([_error_de(hallazgo)])(scope, receive_de_nuevo, send)
                return
        await self.app(scope, receive_de_nuevo, send)
