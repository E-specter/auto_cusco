"""Adaptador de entrada HTTP del calendario laboral (RF-MM-08).

    GET    /calendario/feriados?anio=           dias no laborables del ano (ley y agregados)
    GET    /calendario/excepciones              excepciones guardadas
    POST   /calendario/excepciones              agregar un dia decretado o retirar un feriado
    DELETE /calendario/excepciones/{fecha}      quitar una excepcion
    GET    /calendario/siguiente-dia-gestionable?desde=

Los feriados de ley se calculan para cualquier ano; solo las excepciones se
guardan. Sin `anio` ni `desde`, se usa la fecha actual en America/Lima.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_calendario_postgres import RepositorioCalendarioPostgres
from app.api.errores import respuestas_de_error
from app.api.respuestas import ModeloRespuesta
from app.core.entities.calendario import (
    LARGO_MAXIMO_DESCRIPCION,
    ExcepcionCalendario,
    ExcepcionInvalida,
    ExcepcionNoEncontrada,
    ExcepcionRepetida,
    OrigenDia,
    TipoExcepcion,
)
from app.core.services.calendario.servicio import CalendarioService

router = APIRouter(prefix="/calendario", tags=["calendario"])

ANIO_MINIMO = 1900
ANIO_MAXIMO = 2999


def obtener_servicio_calendario() -> CalendarioService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return CalendarioService(RepositorioCalendarioPostgres(get_engine()))


class DiaNoLaborableRespuesta(ModeloRespuesta):
    fecha: date
    descripcion: str
    origen: OrigenDia
    retirado: bool


class FeriadosRespuesta(ModeloRespuesta):
    anio: int
    dias: list[DiaNoLaborableRespuesta]


class ExcepcionEntrada(BaseModel):
    fecha: date
    tipo: TipoExcepcion
    descripcion: str = Field(min_length=1, max_length=LARGO_MAXIMO_DESCRIPCION)


class ExcepcionRespuesta(ModeloRespuesta):
    fecha: date
    tipo: TipoExcepcion
    descripcion: str
    creado_en: datetime | None


class SiguienteDiaRespuesta(ModeloRespuesta):
    desde: date
    fecha: date


def _excepcion(excepcion: ExcepcionCalendario) -> ExcepcionRespuesta:
    return ExcepcionRespuesta(
        fecha=excepcion.fecha,
        tipo=excepcion.tipo,
        descripcion=excepcion.descripcion,
        creado_en=excepcion.creado_en,
    )


@router.get("/feriados", response_model=FeriadosRespuesta)
def listar_feriados(
    anio: int | None = Query(default=None, ge=ANIO_MINIMO, le=ANIO_MAXIMO),
    servicio: CalendarioService = Depends(obtener_servicio_calendario),
) -> FeriadosRespuesta:
    """Feriados de ley del ano (los retirados, marcados) y los dias agregados."""
    anio = anio or servicio.hoy().year
    return FeriadosRespuesta(
        anio=anio,
        dias=[
            DiaNoLaborableRespuesta(
                fecha=dia.fecha,
                descripcion=dia.descripcion,
                origen=dia.origen,
                retirado=dia.retirado,
            )
            for dia in servicio.dias_no_laborables(anio)
        ],
    )


@router.get("/excepciones", response_model=list[ExcepcionRespuesta])
def listar_excepciones(
    servicio: CalendarioService = Depends(obtener_servicio_calendario),
) -> list[ExcepcionRespuesta]:
    return [_excepcion(excepcion) for excepcion in servicio.listar_excepciones()]


@router.post(
    "/excepciones",
    status_code=201,
    response_model=ExcepcionRespuesta,
    responses=respuestas_de_error(400, 409),
)
def agregar_excepcion(
    entrada: ExcepcionEntrada,
    servicio: CalendarioService = Depends(obtener_servicio_calendario),
) -> ExcepcionRespuesta:
    """Agrega un dia no laborable decretado o retira un feriado de ley de ese ano."""
    try:
        return _excepcion(
            servicio.agregar_excepcion(
                ExcepcionCalendario(entrada.fecha, entrada.tipo, entrada.descripcion)
            )
        )
    except ExcepcionInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ExcepcionRepetida as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/excepciones/{fecha}", status_code=204, responses=respuestas_de_error(404))
def eliminar_excepcion(
    fecha: date,
    servicio: CalendarioService = Depends(obtener_servicio_calendario),
) -> Response:
    try:
        servicio.eliminar_excepcion(fecha)
    except ExcepcionNoEncontrada as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


@router.get("/siguiente-dia-gestionable", response_model=SiguienteDiaRespuesta)
def siguiente_dia_gestionable(
    desde: date | None = None,
    servicio: CalendarioService = Depends(obtener_servicio_calendario),
) -> SiguienteDiaRespuesta:
    """Primer dia de lunes a viernes, posterior a `desde`, que no es feriado ni decretado."""
    desde = desde or servicio.hoy()
    return SiguienteDiaRespuesta(desde=desde, fecha=servicio.siguiente_dia_gestionable(desde))
