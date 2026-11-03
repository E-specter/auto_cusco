"""Adaptador de entrada HTTP de los textos guardados y versionados por contexto (RF-69, T-HI-B4).

    GET    /textos-guardados/contextos                  los contextos que los modulos registraron
    GET    /textos-guardados?contexto=&deshabilitados=  el listado de un contexto (C-7)
    POST   /textos-guardados                            guarda un texto nuevo (version 1)
    GET    /textos-guardados/{id}?version=N             un texto con su version vigente o la N
    POST   /textos-guardados/{id}/versiones             guarda un cambio como una version nueva
    PATCH  /textos-guardados/{id}                       cambia solo el nombre (RF-56)
    POST   /textos-guardados/{id}/deshabilitar          deja de ofrecerlo para lo nuevo
    POST   /textos-guardados/{id}/habilitar             lo vuelve a ofrecer (idempotente)
    DELETE /textos-guardados/{id}                       lo elimina; 409 si alguna version se uso

Como las definiciones de columnas (RF-51): ninguna version se modifica, un cambio es una version
nueva y la vigente es la ultima. El nombre es unico dentro del contexto, sin distinguir mayusculas
ni espacios en los extremos. El contenido es un objeto JSON cuya forma y validez declara el contexto
(una expresion del motor o un texto plano); si algo no vale, un `400` con `codigo` y los
`problemas`, cada uno con su campo (`nombre` o `contenido`). Un contexto que ningun modulo registro
es un `400`. Un texto deshabilitado no sale en el listado salvo con `deshabilitados=true`, ni admite
versiones nuevas (`409`); lo que ya lo uso lo sigue leyendo.
"""

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_textos_guardados_postgres import (
    RepositorioTextosGuardadosPostgres,
)
from app.api.respuestas import ModeloRespuesta
from app.api.texto_enriquecido import (
    DetalleErrorTexto,
    ProblemaTextoRespuesta,
    problema_respuesta,
    respuesta_de_error,
)
from app.core.entities.texto_enriquecido import CodigoTexto
from app.core.entities.textos_guardados import (
    NombreDeTextoRepetido,
    ResumenTexto,
    TextoConVersionesUsadas,
    TextoDeshabilitado,
    TextoGuardado,
    TextoNoEncontrado,
    VersionDeTextoNoEncontrada,
    VersionTexto,
)
from app.core.services.textos_guardados.contextos import (
    ContextoGuardado,
    ContextoGuardadoDesconocido,
    RegistroContextosGuardados,
)
from app.core.services.textos_guardados.servicio import (
    TextoInvalido,
    TextosGuardadosService,
    VistaTexto,
)

router = APIRouter(prefix="/textos-guardados", tags=["textos guardados"])

# Los contextos que la aplicacion conoce: cada modulo agrega aqui el suyo (RF-69). B4 no registra
# ninguno; `whatsmkt.mensaje` lo registra WhatsMKT. Los tests sustituyen la dependencia.
_REGISTRO_CONTEXTOS = RegistroContextosGuardados()


def obtener_registro_contextos_guardados() -> RegistroContextosGuardados:
    """Dependencia de FastAPI: los contextos registrados."""
    return _REGISTRO_CONTEXTOS


def obtener_servicio_textos_guardados(
    contextos: RegistroContextosGuardados = Depends(obtener_registro_contextos_guardados),
) -> TextosGuardadosService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return TextosGuardadosService(RepositorioTextosGuardadosPostgres(get_engine()), contextos)


# --- Errores ------------------------------------------------------------------------------------


class DetalleErrorTextoGuardado(DetalleErrorTexto):
    """Un `400` al guardar: el motivo, el `codigo` y los problemas con su campo."""

    problemas: list[ProblemaTextoRespuesta]


RESPUESTAS_ESCRITURA: dict[int | str, dict[str, Any]] = {
    400: {
        "model": DetalleErrorTextoGuardado,
        "description": "El texto no se puede guardar o el contexto no esta registrado",
    },
    404: {"model": DetalleErrorTexto, "description": "No existe el texto"},
    409: {
        "model": DetalleErrorTexto,
        "description": "El nombre ya existe en el contexto, el texto esta deshabilitado o "
        "alguna version se uso",
    },
}
RESPUESTAS_LECTURA: dict[int | str, dict[str, Any]] = {
    400: {"model": DetalleErrorTexto, "description": "El contexto no esta registrado"},
    404: {"model": DetalleErrorTexto, "description": "No existe el texto o su version"},
}


def _invalido(error: TextoInvalido) -> JSONResponse:
    problemas = [problema_respuesta(p.problema, p).model_dump() for p in error.problemas]
    return respuesta_de_error(
        400, CodigoTexto.TEXTO_GUARDADO_INVALIDO, str(error), problemas=problemas
    )


def _contexto_desconocido(error: ContextoGuardadoDesconocido) -> JSONResponse:
    return respuesta_de_error(400, CodigoTexto.CONTEXTO_GUARDADO_DESCONOCIDO, str(error))


def _no_existe(error: TextoNoEncontrado | VersionDeTextoNoEncontrada) -> JSONResponse:
    codigo = (
        CodigoTexto.TEXTO_GUARDADO_NO_ENCONTRADO
        if isinstance(error, TextoNoEncontrado)
        else CodigoTexto.VERSION_NO_ENCONTRADA
    )
    return respuesta_de_error(404, codigo, str(error))


def _repetido(error: NombreDeTextoRepetido) -> JSONResponse:
    return respuesta_de_error(409, CodigoTexto.NOMBRE_REPETIDO, str(error))


def _usado(error: TextoConVersionesUsadas) -> JSONResponse:
    return respuesta_de_error(409, CodigoTexto.TEXTO_GUARDADO_USADO, str(error))


def _deshabilitado(error: TextoDeshabilitado) -> JSONResponse:
    return respuesta_de_error(409, CodigoTexto.TEXTO_GUARDADO_DESHABILITADO, str(error))


# --- Respuestas ---------------------------------------------------------------------------------


class ContextoGuardadoRespuesta(ModeloRespuesta):
    clave: str
    etiqueta: str
    tipo: Literal["expresion", "texto_plano"]  # que es el contenido: {"expresion"} o {"texto"}


class VersionTextoResumenRespuesta(ModeloRespuesta):
    numero: int
    creado_en: datetime
    usada_en: datetime | None
    usada: bool


class VersionTextoRespuesta(VersionTextoResumenRespuesta):
    contenido: dict[str, Any]


class TextoRespuesta(ModeloRespuesta):
    """El texto, todas sus versiones (sin contenido) y la pedida (la vigente por defecto)."""

    id: int
    contexto: str
    nombre: str
    creado_en: datetime
    actualizado_en: datetime
    deshabilitado_en: datetime | None
    version_vigente: int
    versiones: list[VersionTextoResumenRespuesta]
    version: VersionTextoRespuesta


class ResumenTextoRespuesta(ModeloRespuesta):
    id: int
    contexto: str
    nombre: str
    version_vigente: int
    cantidad_versiones: int
    actualizado_en: datetime
    vigente_usada: bool
    deshabilitado_en: datetime | None


def _contexto(contexto: ContextoGuardado) -> ContextoGuardadoRespuesta:
    return ContextoGuardadoRespuesta(
        clave=contexto.clave, etiqueta=contexto.etiqueta, tipo=contexto.tipo.value
    )


def _resumen_de_version(version: VersionTexto) -> VersionTextoResumenRespuesta:
    return VersionTextoResumenRespuesta(
        numero=version.numero,
        creado_en=version.creado_en,
        usada_en=version.usada_en,
        usada=version.usada,
    )


def _texto(texto: TextoGuardado, version: VersionTexto) -> TextoRespuesta:
    return TextoRespuesta(
        id=texto.id,
        contexto=texto.contexto,
        nombre=texto.nombre,
        creado_en=texto.creado_en,
        actualizado_en=texto.actualizado_en,
        deshabilitado_en=texto.deshabilitado_en,
        version_vigente=texto.vigente.numero,
        versiones=[_resumen_de_version(v) for v in texto.versiones],
        version=VersionTextoRespuesta(
            **_resumen_de_version(version).model_dump(), contenido=dict(version.contenido)
        ),
    )


def _vista(vista: VistaTexto) -> TextoRespuesta:
    return _texto(vista.texto, vista.version)


def _resumen(resumen: ResumenTexto) -> ResumenTextoRespuesta:
    return ResumenTextoRespuesta(
        id=resumen.id,
        contexto=resumen.contexto,
        nombre=resumen.nombre,
        version_vigente=resumen.version_vigente,
        cantidad_versiones=resumen.cantidad_versiones,
        actualizado_en=resumen.actualizado_en,
        vigente_usada=resumen.vigente_usada,
        deshabilitado_en=resumen.deshabilitado_en,
    )


# --- Entrada ------------------------------------------------------------------------------------


class TextoEntrada(BaseModel):
    """Lo que no es texto o objeto llega al servicio tal cual y se informa como problema."""

    contexto: str
    nombre: Any = None
    contenido: Any = None


class ContenidoEntrada(BaseModel):
    contenido: Any = None


class RenombrarTextoEntrada(BaseModel):
    """RF-56: el nombre nuevo. Se recortan los espacios de los extremos."""

    nombre: Any = None


# --- Endpoints ----------------------------------------------------------------------------------


@router.get("/contextos", response_model=list[ContextoGuardadoRespuesta])
def listar_contextos(
    servicio: TextosGuardadosService = Depends(obtener_servicio_textos_guardados),
) -> list[ContextoGuardadoRespuesta]:
    """Los contextos que los modulos registraron, con la forma de su contenido."""
    return [_contexto(c) for c in servicio.contextos()]


@router.get("", response_model=list[ResumenTextoRespuesta], responses=RESPUESTAS_LECTURA)
def listar_textos(
    contexto: str,
    deshabilitados: bool = Query(default=False, description="Incluir los deshabilitados"),
    servicio: TextosGuardadosService = Depends(obtener_servicio_textos_guardados),
) -> Any:
    """Los textos del `contexto` ordenados por nombre, con su version vigente. Sin paginar."""
    try:
        return [_resumen(r) for r in servicio.listar(contexto, deshabilitados)]
    except ContextoGuardadoDesconocido as error:
        return _contexto_desconocido(error)


@router.post("", status_code=201, response_model=TextoRespuesta, responses=RESPUESTAS_ESCRITURA)
def crear_texto(
    entrada: TextoEntrada,
    servicio: TextosGuardadosService = Depends(obtener_servicio_textos_guardados),
) -> Any:
    """Guarda un texto nuevo con su version 1. El nombre es obligatorio y unico en el contexto."""
    try:
        return _vista(servicio.crear(entrada.contexto, entrada.nombre, entrada.contenido))
    except ContextoGuardadoDesconocido as error:
        return _contexto_desconocido(error)
    except TextoInvalido as error:
        return _invalido(error)
    except NombreDeTextoRepetido as error:
        return _repetido(error)


@router.get("/{texto_id}", response_model=TextoRespuesta, responses=RESPUESTAS_LECTURA)
def obtener_texto(
    texto_id: int,
    version: int | None = Query(default=None, ge=1, description="Por defecto, la vigente"),
    servicio: TextosGuardadosService = Depends(obtener_servicio_textos_guardados),
) -> Any:
    """Un texto con la version vigente o con la `version` pedida; tambien si esta deshabilitado."""
    try:
        return _vista(servicio.obtener(texto_id, version))
    except (TextoNoEncontrado, VersionDeTextoNoEncontrada) as error:
        return _no_existe(error)


@router.post(
    "/{texto_id}/versiones",
    status_code=201,
    response_model=TextoRespuesta,
    responses=RESPUESTAS_ESCRITURA,
)
def agregar_version(
    texto_id: int,
    entrada: ContenidoEntrada,
    servicio: TextosGuardadosService = Depends(obtener_servicio_textos_guardados),
) -> Any:
    """Guarda el contenido como una version nueva, que pasa a ser la vigente."""
    try:
        return _vista(servicio.agregar_version(texto_id, entrada.contenido))
    except TextoNoEncontrado as error:
        return _no_existe(error)
    except ContextoGuardadoDesconocido as error:
        return _contexto_desconocido(error)
    except TextoInvalido as error:
        return _invalido(error)
    except TextoDeshabilitado as error:
        return _deshabilitado(error)


@router.patch("/{texto_id}", response_model=TextoRespuesta, responses=RESPUESTAS_ESCRITURA)
def renombrar_texto(
    texto_id: int,
    entrada: RenombrarTextoEntrada,
    servicio: TextosGuardadosService = Depends(obtener_servicio_textos_guardados),
) -> Any:
    """Cambia solo el nombre (RF-56): no crea una version ni modifica ninguna, y mueve
    `actualizado_en`. Mismo nombre que el actual: sin error y sin cambios. Otro nombre ya en uso en
    el contexto es `409 nombre_repetido`; vacio o de mas de 120 caracteres, `400` con el problema en
    `campo = nombre`. Devuelve el texto con su version vigente."""
    try:
        renombrado = servicio.renombrar(texto_id, entrada.nombre)
    except TextoNoEncontrado as error:
        return _no_existe(error)
    except TextoInvalido as error:
        return _invalido(error)
    except NombreDeTextoRepetido as error:
        return _repetido(error)
    return _texto(renombrado, renombrado.vigente)


@router.post(
    "/{texto_id}/deshabilitar", response_model=TextoRespuesta, responses=RESPUESTAS_LECTURA
)
def deshabilitar_texto(
    texto_id: int,
    servicio: TextosGuardadosService = Depends(obtener_servicio_textos_guardados),
) -> Any:
    """Deja de ofrecerlo para lo nuevo; lo que ya lo uso lo sigue leyendo. Idempotente."""
    try:
        deshabilitado = servicio.deshabilitar(texto_id)
    except TextoNoEncontrado as error:
        return _no_existe(error)
    return _texto(deshabilitado, deshabilitado.vigente)


@router.post("/{texto_id}/habilitar", response_model=TextoRespuesta, responses=RESPUESTAS_LECTURA)
def habilitar_texto(
    texto_id: int,
    servicio: TextosGuardadosService = Depends(obtener_servicio_textos_guardados),
) -> Any:
    """Lo vuelve a ofrecer para lo nuevo y admite versiones nuevas. Si ya esta habilitado, 200 sin
    cambio."""
    try:
        habilitado = servicio.habilitar(texto_id)
    except TextoNoEncontrado as error:
        return _no_existe(error)
    return _texto(habilitado, habilitado.vigente)


@router.delete(
    "/{texto_id}",
    status_code=204,
    responses={
        404: RESPUESTAS_ESCRITURA[404],
        409: {
            "model": DetalleErrorTexto,
            "description": "Alguna version se uso: solo se deshabilita",
        },
    },
)
def eliminar_texto(
    texto_id: int,
    servicio: TextosGuardadosService = Depends(obtener_servicio_textos_guardados),
) -> Response:
    """Lo elimina con sus versiones; si alguna tiene `usada_en`, `409 texto_guardado_usado`."""
    try:
        servicio.eliminar(texto_id)
    except TextoNoEncontrado as error:
        return _no_existe(error)
    except TextoConVersionesUsadas as error:
        return _usado(error)
    return Response(status_code=204)
