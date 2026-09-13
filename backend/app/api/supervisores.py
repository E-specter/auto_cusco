"""Adaptador de entrada HTTP de la supervision de campanas digitales (RF-38, RF-39).

    GET /supervisores   lista por defecto y orden de procedencias
    PUT /supervisores   reemplazarlas completas

Transversal a toda plataforma digital. Cada supervisor devuelve el DNI no real
que le tocaria con esta lista (RF-39), para que la configuracion lo muestre.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_supervision_postgres import (
    RepositorioSupervisionPostgres,
)
from app.api.errores import respuestas_de_error
from app.api.respuestas import ModeloRespuesta
from app.core.entities.gestiones_digitales import (
    LARGO_MAXIMO_PROCEDENCIA,
    ConfiguracionSupervision,
    SupervisionInvalida,
    Supervisor,
)
from app.core.services.gestiones_digitales.servicio import SupervisionService
from app.core.services.gestiones_digitales.supervision import documentos_por_posicion

router = APIRouter(prefix="/supervisores", tags=["supervisores"])

MAXIMO_SUPERVISORES = 100


def obtener_servicio_supervision() -> SupervisionService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return SupervisionService(RepositorioSupervisionPostgres(get_engine()))


class SupervisorEntrada(BaseModel):
    numero: str = Field(max_length=20)
    procedencia: str = Field(max_length=LARGO_MAXIMO_PROCEDENCIA)


class ConfiguracionSupervisionEntrada(BaseModel):
    procedencias: list[str] = Field(max_length=MAXIMO_SUPERVISORES)
    supervisores: list[SupervisorEntrada] = Field(max_length=MAXIMO_SUPERVISORES)


class SupervisorRespuesta(ModeloRespuesta):
    numero: str
    procedencia: str
    documento: str


class ConfiguracionSupervisionRespuesta(ModeloRespuesta):
    procedencias: list[str]
    supervisores: list[SupervisorRespuesta]


def _respuesta(configuracion: ConfiguracionSupervision) -> ConfiguracionSupervisionRespuesta:
    documentos = documentos_por_posicion(configuracion.supervisores, configuracion.procedencias)
    return ConfiguracionSupervisionRespuesta(
        procedencias=list(configuracion.procedencias),
        supervisores=[
            SupervisorRespuesta(numero=s.numero, procedencia=s.procedencia, documento=documento)
            for s, documento in zip(configuracion.supervisores, documentos, strict=True)
        ],
    )


@router.get("", response_model=ConfiguracionSupervisionRespuesta)
def obtener_supervisores(
    servicio: SupervisionService = Depends(obtener_servicio_supervision),
) -> ConfiguracionSupervisionRespuesta:
    return _respuesta(servicio.obtener())


@router.put(
    "", response_model=ConfiguracionSupervisionRespuesta, responses=respuestas_de_error(400)
)
def reemplazar_supervisores(
    entrada: ConfiguracionSupervisionEntrada,
    servicio: SupervisionService = Depends(obtener_servicio_supervision),
) -> ConfiguracionSupervisionRespuesta:
    """Reemplaza procedencias y supervisores. Los numeros siguen RF-02."""
    configuracion = ConfiguracionSupervision(
        procedencias=tuple(entrada.procedencias),
        supervisores=tuple(Supervisor(s.numero, s.procedencia) for s in entrada.supervisores),
    )
    try:
        return _respuesta(servicio.reemplazar(configuracion))
    except SupervisionInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
