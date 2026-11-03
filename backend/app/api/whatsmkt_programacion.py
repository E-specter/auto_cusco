"""La programacion del envio de WhatsMKT por HTTP (T-WM-B4c; RF-WM-06, RF-70 y RF-71).

    GET /whatsmkt/programacion?n=   la fecha sugerida, la minima y los proximos N dias gestionables

Todo sale del calendario laboral comun (`/calendario`): de lunes a sabado, sin feriados ni dias no
laborables registrados, y siempre posterior a hoy en America/Lima.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.calendario import DetalleErrorProximos, obtener_servicio_calendario
from app.api.errores import ErrorConCodigo
from app.api.respuestas import ModeloRespuesta
from app.core.entities.calendario import ProximosFueraDeRango
from app.core.entities.texto_enriquecido import CodigoTexto
from app.core.services.calendario.servicio import CalendarioService
from app.core.services.plataformas.whatsmkt.programacion import ProgramacionWhatsmktService

router = APIRouter(prefix="/whatsmkt/programacion", tags=["whatsmkt"])

PROXIMAS_POR_DEFECTO = 7  # una semana de opciones


def obtener_servicio_programacion_whatsmkt(
    calendario: CalendarioService = Depends(obtener_servicio_calendario),
) -> ProgramacionWhatsmktService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return ProgramacionWhatsmktService(calendario)


class ProgramacionWhatsmktRespuesta(ModeloRespuesta):
    sugerida: date
    minima: date
    proximas: list[date]


@router.get(
    "",
    summary="La fecha de envio sugerida y los proximos dias gestionables",
    response_model=ProgramacionWhatsmktRespuesta,
    responses={
        400: {
            "model": DetalleErrorProximos,
            "description": (
                "`n` fuera de rango: el codigo es proximos_fuera_de_rango y trae `minimo` y "
                "`maximo`"
            ),
        }
    },
)
def programacion(
    n: int = Query(
        default=PROXIMAS_POR_DEFECTO, description="Cuantos dias gestionables se piden (RF-71)"
    ),
    servicio: ProgramacionWhatsmktService = Depends(obtener_servicio_programacion_whatsmkt),
) -> ProgramacionWhatsmktRespuesta:
    """Para elegir la fecha de envio (RF-WM-06). `sugerida` es el siguiente dia gestionable despues
    de hoy en Lima; `minima` es la primera fecha que se admite (hoy nunca sirve) y hoy coincide con
    la sugerida; `proximas` son los `n` siguientes, de lunes a sabado, sin feriados ni dias no
    laborables registrados (RF-70 y RF-71)."""
    try:
        programada = servicio.programacion(n)
    except ProximosFueraDeRango as error:
        raise ErrorConCodigo(
            400,
            str(error),
            CodigoTexto.PROXIMOS_FUERA_DE_RANGO,
            {"minimo": error.minimo, "maximo": error.maximo},
        ) from error
    return ProgramacionWhatsmktRespuesta(
        sugerida=programada.sugerida,
        minima=programada.minima,
        proximas=list(programada.proximas),
    )
