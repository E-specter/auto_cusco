"""Biblioteca de adjuntos de WhatsMKT por HTTP (T-WM-B5; RF-WM-28 a 32).

    POST /whatsmkt/adjuntos                    sube un archivo (multipart); 201 con el adjunto
    GET  /whatsmkt/adjuntos?archivados=        la biblioteca, sin contenido
    GET  /whatsmkt/adjuntos/{id}/contenido     descarga el archivo con su nombre original
    POST /whatsmkt/adjuntos/{id}/archivar      deja de ofrecerse en campanas nuevas
    POST /whatsmkt/adjuntos/{id}/desarchivar

El tipo se reconoce por la firma del archivo, el tamano se controla antes de leerlo entero y las
imagenes se guardan sin metadatos. `proposito=foto` valida ademas que sirva de foto de perfil
(JPEG de 200 x 200 y hasta 1 MB, RF-WM-29) y responde `foto_formato`, `foto_peso` o `foto_medidas`.
Una regla rota responde `422` con `{detail, codigo, ...parametros}` como el resto del modulo.
"""

import os
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi.responses import JSONResponse

from app.adapters.output.exportadores.comunes import disposicion_de_descarga
from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_whatsmkt_postgres import RepositorioWhatsmktPostgres
from app.api.errores import respuestas_de_error
from app.api.respuestas import ModeloRespuesta
from app.api.whatsmkt import RESPUESTA_422, error_whatsmkt
from app.core.entities.whatsmkt import (
    AdjuntoNoEncontrado,
    AdjuntoWhatsmkt,
    ErrorWhatsmkt,
    TipoAdjunto,
)
from app.core.services.plataformas.whatsmkt.adjuntos import LARGO_CABECERA
from app.core.services.plataformas.whatsmkt.biblioteca import BibliotecaWhatsmktService

router = APIRouter(prefix="/whatsmkt/adjuntos", tags=["whatsmkt"])

# Video y audio llegan en muchos contenedores: se descargan sin prometer un subtipo.
_TIPO_MIME = {
    TipoAdjunto.IMAGEN_JPEG: "image/jpeg",
    TipoAdjunto.IMAGEN_PNG: "image/png",
    TipoAdjunto.PDF: "application/pdf",
}


def obtener_servicio_biblioteca() -> BibliotecaWhatsmktService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return BibliotecaWhatsmktService(RepositorioWhatsmktPostgres(get_engine()))


class AdjuntoWhatsmktRespuesta(ModeloRespuesta):
    id: int
    tipo: TipoAdjunto
    nombre: str
    tamano: int
    huella: str
    creado_en: datetime
    archivado_en: datetime | None


class AdjuntoSubidoRespuesta(AdjuntoWhatsmktRespuesta):
    ya_existia: bool


def _adjunto(a: AdjuntoWhatsmkt) -> AdjuntoWhatsmktRespuesta:
    return AdjuntoWhatsmktRespuesta(**vars(a))


def _no_encontrado(exc: AdjuntoNoEncontrado) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@router.post(
    "",
    status_code=201,
    summary="Subir un adjunto a la biblioteca",
    response_model=AdjuntoSubidoRespuesta,
    responses=RESPUESTA_422,
)
def subir_adjunto(
    archivo: UploadFile = File(description="Imagen JPEG o PNG, video, audio o PDF"),
    proposito: Literal["adjunto", "foto"] = Form(
        default="adjunto",
        description="`foto` ademas valida que sirva de foto de perfil: JPEG, 200 x 200, hasta 1 MB",
    ),
    servicio: BibliotecaWhatsmktService = Depends(obtener_servicio_biblioteca),
) -> AdjuntoSubidoRespuesta:
    """Valida, limpia y guarda el archivo; uno con la misma huella (despues de limpiarlo) devuelve
    el que ya estaba, con `ya_existia`. Un adjunto archivado que se vuelve a subir sigue archivado.
    """
    como_foto = proposito == "foto"
    # El tamano sale del propio archivo ya recibido, sin leerlo: un archivo demasiado grande se
    # rechaza solo con su cabecera en memoria (RF-WM-31).
    contenido = archivo.file
    contenido.seek(0, os.SEEK_END)
    tamano = contenido.tell()
    contenido.seek(0)
    try:
        servicio.admitir(contenido.read(LARGO_CABECERA), tamano, como_foto)
        contenido.seek(0)
        adjunto, ya_existia = servicio.guardar(archivo.filename, contenido.read(), como_foto)
    except ErrorWhatsmkt as exc:
        raise error_whatsmkt(exc) from exc
    return AdjuntoSubidoRespuesta(**_adjunto(adjunto).model_dump(), ya_existia=ya_existia)


@router.get("", summary="La biblioteca de adjuntos", response_model=list[AdjuntoWhatsmktRespuesta])
def listar_adjuntos(
    archivados: bool = Query(
        default=False, description="true: los archivados, en vez de los activos"
    ),
    servicio: BibliotecaWhatsmktService = Depends(obtener_servicio_biblioteca),
) -> list[AdjuntoWhatsmktRespuesta]:
    return [_adjunto(a) for a in servicio.listar(archivados)]


@router.get(
    "/{adjunto_id}/contenido",
    summary="Descargar un adjunto",
    response_class=Response,
    responses={
        200: {
            "description": "El archivo tal como se guardo (las imagenes, sin metadatos)",
            "content": {"*/*": {"schema": {"type": "string", "format": "binary"}}},
            "headers": {
                "Content-Disposition": {
                    "description": (
                        'attachment; filename="<nombre en ASCII>"; '
                        "filename*=UTF-8''<nombre original> (RFC 5987)"
                    ),
                    "schema": {"type": "string"},
                }
            },
        },
        **respuestas_de_error(404),
    },
)
def descargar_adjunto(
    adjunto_id: int, servicio: BibliotecaWhatsmktService = Depends(obtener_servicio_biblioteca)
) -> Response:
    try:
        adjunto, contenido = servicio.contenido(adjunto_id)
    except AdjuntoNoEncontrado as exc:
        return _no_encontrado(exc)
    return Response(
        content=contenido,
        media_type=_TIPO_MIME.get(adjunto.tipo, "application/octet-stream"),
        headers={"Content-Disposition": disposicion_de_descarga(adjunto.nombre)},
    )


@router.post(
    "/{adjunto_id}/archivar",
    summary="Archivar un adjunto",
    response_model=AdjuntoWhatsmktRespuesta,
    responses=respuestas_de_error(404),
)
def archivar_adjunto(
    adjunto_id: int, servicio: BibliotecaWhatsmktService = Depends(obtener_servicio_biblioteca)
) -> AdjuntoWhatsmktRespuesta | JSONResponse:
    """Deja de ofrecerse en campanas nuevas; las que lo usaron lo conservan. Repetirlo no cambia
    la fecha."""
    try:
        return _adjunto(servicio.archivar(adjunto_id))
    except AdjuntoNoEncontrado as exc:
        return _no_encontrado(exc)


@router.post(
    "/{adjunto_id}/desarchivar",
    summary="Restaurar un adjunto archivado",
    response_model=AdjuntoWhatsmktRespuesta,
    responses=respuestas_de_error(404),
)
def desarchivar_adjunto(
    adjunto_id: int, servicio: BibliotecaWhatsmktService = Depends(obtener_servicio_biblioteca)
) -> AdjuntoWhatsmktRespuesta | JSONResponse:
    try:
        return _adjunto(servicio.desarchivar(adjunto_id))
    except AdjuntoNoEncontrado as exc:
        return _no_encontrado(exc)
