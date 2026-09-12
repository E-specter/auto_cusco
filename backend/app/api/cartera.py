"""Adaptador de entrada HTTP para la seleccion y las metricas de cartera.

Los filtros viajan como parametros repetidos con la forma
`campo:operador:valor`, y los valores multiples se separan con `|`:

    ?filtro=segmento_financiero:igual:1. Preventiva
    ?filtro=dias_atraso:entre:0|30
    ?filtro=telefono:no_vacio

Los indicadores adicionales (RF-27) usan `nombre:funcion:campo`:

    ?indicador=capital promedio:promedio:saldo_capital_pendiente

La lectura de esa sintaxis vive en `app/api/consultas.py`, compartida con la
generacion de archivos de carga. Los montos se devuelven como texto para no
perder precision al pasar por JSON.
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_cartera_postgres import RepositorioCarteraPostgres
from app.api.consultas import (
    parsear_filtro,
    parsear_indicador,
    parsear_orden,
    texto_si_es_monto,
    traducir_errores,
)
from app.api.errores import respuestas_de_error
from app.core.entities.cartera import ConsultaInvalida, SinVersionVigente
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService

router = APIRouter(prefix="/cartera", tags=["cartera"])


def crear_servicio_cartera() -> ConsultaCarteraService:
    return ConsultaCarteraService(RepositorioCarteraPostgres(get_engine()))


def obtener_servicio_cartera() -> ConsultaCarteraService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return crear_servicio_cartera()


class CampoRespuesta(BaseModel):
    tipo: str
    operadores: list[str]


class GrupoRespuesta(BaseModel):
    valor: Any
    cuentas: int
    capital: str


class SegmentacionRespuesta(BaseModel):
    campo: str
    grupos: list[GrupoRespuesta]


class PaginaRespuesta(BaseModel):
    total: int
    limite: int
    desplazamiento: int
    suficiente: bool
    productos: list[dict[str, Any]]


class MetricasRespuesta(BaseModel):
    cuentas: int
    capital_total: str
    cuota_minima: str | None
    cuota_maxima: str | None
    cuentas_por_segmento: dict[str, int]
    adicionales: dict[str, Any]


def _producto(fila: dict[str, Any]) -> dict[str, Any]:
    return {clave: texto_si_es_monto(valor) for clave, valor in fila.items()}


@router.get("/campos", response_model=dict[str, CampoRespuesta])
def listar_campos(
    servicio: ConsultaCarteraService = Depends(obtener_servicio_cartera),
) -> dict[str, dict]:
    """Campos consultables con su tipo y los operadores que admite cada uno."""
    return servicio.campos_disponibles()


@router.get("", response_model=PaginaRespuesta, responses=respuestas_de_error(400, 404))
def consultar_cartera(
    fecha_corte: date,
    filtro: list[str] = Query(default=[]),
    orden: str | None = Query(default=None, description="campo, o -campo para descendente"),
    limite: int = Query(default=50, ge=1, le=5000),
    desplazamiento: int = Query(default=0, ge=0),
    servicio: ConsultaCarteraService = Depends(obtener_servicio_cartera),
) -> PaginaRespuesta:
    """Productos de la version vigente de la fecha (RF-04, RF-05, RF-08)."""
    try:
        pagina = servicio.consultar(
            fecha_corte,
            [parsear_filtro(crudo) for crudo in filtro],
            parsear_orden(orden),
            limite,
            desplazamiento,
        )
    except (ConsultaInvalida, SinVersionVigente) as exc:
        raise traducir_errores(exc) from exc
    return PaginaRespuesta(
        total=pagina.total,
        limite=pagina.limite,
        desplazamiento=pagina.desplazamiento,
        suficiente=pagina.suficiente,
        productos=[_producto(fila) for fila in pagina.filas],
    )


@router.get("/metricas", response_model=MetricasRespuesta, responses=respuestas_de_error(400, 404))
def metricas_cartera(
    fecha_corte: date,
    filtro: list[str] = Query(default=[]),
    indicador: list[str] = Query(default=[]),
    servicio: ConsultaCarteraService = Depends(obtener_servicio_cartera),
) -> MetricasRespuesta:
    """Capital, cuentas, segmentos y cuotas de la seleccion (RF-26), mas RF-27."""
    try:
        metricas = servicio.metricas(
            fecha_corte,
            [parsear_filtro(crudo) for crudo in filtro],
            [parsear_indicador(crudo) for crudo in indicador],
        )
    except (ConsultaInvalida, SinVersionVigente) as exc:
        raise traducir_errores(exc) from exc
    return MetricasRespuesta(
        cuentas=metricas.cuentas,
        capital_total=str(metricas.capital_total),
        cuota_minima=None if metricas.cuota_minima is None else str(metricas.cuota_minima),
        cuota_maxima=None if metricas.cuota_maxima is None else str(metricas.cuota_maxima),
        cuentas_por_segmento=metricas.cuentas_por_segmento,
        adicionales={
            nombre: texto_si_es_monto(valor) for nombre, valor in metricas.adicionales.items()
        },
    )


@router.get(
    "/segmentacion",
    response_model=SegmentacionRespuesta,
    responses=respuestas_de_error(400, 404),
)
def segmentar_cartera(
    fecha_corte: date,
    campo: str,
    filtro: list[str] = Query(default=[]),
    servicio: ConsultaCarteraService = Depends(obtener_servicio_cartera),
) -> SegmentacionRespuesta:
    """Cuentas y capital por cada valor de un atributo (RF-06)."""
    try:
        segmentacion = servicio.segmentar(
            fecha_corte, campo, [parsear_filtro(crudo) for crudo in filtro]
        )
    except (ConsultaInvalida, SinVersionVigente) as exc:
        raise traducir_errores(exc) from exc
    return SegmentacionRespuesta(
        campo=segmentacion.campo,
        grupos=[
            GrupoRespuesta(valor=grupo.valor, cuentas=grupo.cuentas, capital=str(grupo.capital))
            for grupo in segmentacion.grupos
        ],
    )
