"""Adaptador de entrada HTTP para las selecciones de cartera guardadas.

    GET    /selecciones             todas, cada una revisada contra el catalogo actual
    POST   /selecciones             guardar una nueva
    POST   /selecciones/revision    revisar sin guardar, para marcar errores al editar
    GET    /selecciones/{id}        una
    PUT    /selecciones/{id}        reemplazarla
    DELETE /selecciones/{id}        borrarla

Filtros, orden e indicadores en la misma sintaxis que `/cartera`. Sin usuarios
(decision C-3): cualquiera puede editar o borrar cualquier seleccion.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_selecciones_postgres import RepositorioSeleccionesPostgres
from app.api.errores import respuestas_de_error
from app.api.respuestas import ModeloRespuesta
from app.core.entities.selecciones import (
    LARGO_MAXIMO_NOMBRE,
    DatosSeleccion,
    NombreDeSeleccionRepetido,
    ParteSeleccion,
    ProblemaSeleccion,
    SeleccionInvalida,
    SeleccionNoEncontrada,
    SeleccionRevisada,
)
from app.core.services.seleccion_cartera.servicio import CANTIDAD_MAXIMA
from app.core.services.selecciones.servicio import SeleccionesService

router = APIRouter(prefix="/selecciones", tags=["selecciones"])


def obtener_servicio_selecciones() -> SeleccionesService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return SeleccionesService(RepositorioSeleccionesPostgres(get_engine()))


class SeleccionEntrada(BaseModel):
    nombre: str = Field(min_length=1, max_length=LARGO_MAXIMO_NOMBRE)
    filtros: list[str] = []
    orden: str | None = None
    cantidad: int | None = Field(default=None, ge=1, le=CANTIDAD_MAXIMA)
    indicadores: list[str] = []

    def datos(self) -> DatosSeleccion:
        return DatosSeleccion(
            nombre=self.nombre,
            filtros=tuple(self.filtros),
            orden=self.orden,
            cantidad=self.cantidad,
            indicadores=tuple(self.indicadores),
        )


class ProblemaRespuesta(ModeloRespuesta):
    parte: ParteSeleccion
    expresion: str
    detalle: str


class RevisionRespuesta(ModeloRespuesta):
    aplicable: bool
    problemas: list[ProblemaRespuesta]


class SeleccionRespuesta(ModeloRespuesta):
    id: int
    nombre: str
    filtros: list[str]
    orden: str | None
    cantidad: int | None
    indicadores: list[str]
    creado_en: datetime
    actualizado_en: datetime
    aplicable: bool
    problemas: list[ProblemaRespuesta]


def _problemas(problemas: tuple[ProblemaSeleccion, ...]) -> list[ProblemaRespuesta]:
    return [
        ProblemaRespuesta(parte=p.parte, expresion=p.expresion, detalle=p.detalle)
        for p in problemas
    ]


def _respuesta(revisada: SeleccionRevisada) -> SeleccionRespuesta:
    seleccion = revisada.seleccion
    datos = seleccion.datos
    return SeleccionRespuesta(
        id=seleccion.id,
        nombre=datos.nombre,
        filtros=list(datos.filtros),
        orden=datos.orden,
        cantidad=datos.cantidad,
        indicadores=list(datos.indicadores),
        creado_en=seleccion.creado_en,
        actualizado_en=seleccion.actualizado_en,
        aplicable=revisada.aplicable,
        problemas=_problemas(revisada.problemas),
    )


def _traducir(exc: Exception) -> HTTPException:
    if isinstance(exc, SeleccionNoEncontrada):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, NombreDeSeleccionRepetido):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("", response_model=list[SeleccionRespuesta])
def listar_selecciones(
    servicio: SeleccionesService = Depends(obtener_servicio_selecciones),
) -> list[SeleccionRespuesta]:
    """Todas las selecciones, ordenadas por nombre y revisadas contra el catalogo actual."""
    return [_respuesta(revisada) for revisada in servicio.listar()]


@router.post(
    "", status_code=201, response_model=SeleccionRespuesta, responses=respuestas_de_error(400, 409)
)
def crear_seleccion(
    entrada: SeleccionEntrada,
    servicio: SeleccionesService = Depends(obtener_servicio_selecciones),
) -> SeleccionRespuesta:
    """Guarda una seleccion nueva. Si alguna parte no aplica, se rechaza con el motivo."""
    try:
        return _respuesta(servicio.crear(entrada.datos()))
    except (SeleccionInvalida, NombreDeSeleccionRepetido) as exc:
        raise _traducir(exc) from exc


@router.post("/revision", response_model=RevisionRespuesta)
def revisar_seleccion(
    entrada: SeleccionEntrada,
    servicio: SeleccionesService = Depends(obtener_servicio_selecciones),
) -> RevisionRespuesta:
    """Que partes no aplican, sin guardar nada: para marcar errores mientras se edita."""
    problemas = servicio.revisar(entrada.datos())
    return RevisionRespuesta(aplicable=not problemas, problemas=_problemas(problemas))


@router.get(
    "/{seleccion_id}", response_model=SeleccionRespuesta, responses=respuestas_de_error(404)
)
def obtener_seleccion(
    seleccion_id: int,
    servicio: SeleccionesService = Depends(obtener_servicio_selecciones),
) -> SeleccionRespuesta:
    """Una seleccion. Si perdio validez se devuelve igual, con sus problemas marcados."""
    try:
        return _respuesta(servicio.obtener(seleccion_id))
    except SeleccionNoEncontrada as exc:
        raise _traducir(exc) from exc


@router.put(
    "/{seleccion_id}",
    response_model=SeleccionRespuesta,
    responses=respuestas_de_error(400, 404, 409),
)
def actualizar_seleccion(
    seleccion_id: int,
    entrada: SeleccionEntrada,
    servicio: SeleccionesService = Depends(obtener_servicio_selecciones),
) -> SeleccionRespuesta:
    """Reemplaza la seleccion completa."""
    try:
        return _respuesta(servicio.actualizar(seleccion_id, entrada.datos()))
    except (SeleccionInvalida, SeleccionNoEncontrada, NombreDeSeleccionRepetido) as exc:
        raise _traducir(exc) from exc


@router.delete("/{seleccion_id}", status_code=204, responses=respuestas_de_error(404))
def eliminar_seleccion(
    seleccion_id: int,
    servicio: SeleccionesService = Depends(obtener_servicio_selecciones),
) -> Response:
    try:
        servicio.eliminar(seleccion_id)
    except SeleccionNoEncontrada as exc:
        raise _traducir(exc) from exc
    return Response(status_code=204)
