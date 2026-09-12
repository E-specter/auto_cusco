"""Adaptador de entrada HTTP para la seleccion y las metricas de cartera.

Los filtros viajan como parametros repetidos con la forma
`campo:operador:valor`, y los valores multiples se separan con `|`:

    ?filtro=segmento_financiero:igual:1. Preventiva
    ?filtro=dias_atraso:entre:0|30
    ?filtro=telefono:no_vacio

Los indicadores adicionales (RF-27) usan `nombre:funcion:campo`:

    ?indicador=capital promedio:promedio:saldo_capital_pendiente

Los montos se devuelven como texto para no perder precision al pasar por JSON.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_cartera_postgres import RepositorioCarteraPostgres
from app.core.entities.cartera import (
    ConsultaInvalida,
    Filtro,
    Funcion,
    Indicador,
    Operador,
    Orden,
    SinVersionVigente,
)
from app.core.services.seleccion_cartera import campos
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService

router = APIRouter(prefix="/cartera", tags=["cartera"])

SEPARADOR_VALORES = "|"


def crear_servicio_cartera() -> ConsultaCarteraService:
    return ConsultaCarteraService(RepositorioCarteraPostgres(get_engine()))


def obtener_servicio_cartera() -> ConsultaCarteraService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return crear_servicio_cartera()


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


def _texto_si_es_monto(valor: Any) -> Any:
    return str(valor) if isinstance(valor, Decimal) else valor


def _producto(fila: dict[str, Any]) -> dict[str, Any]:
    return {clave: _texto_si_es_monto(valor) for clave, valor in fila.items()}


def _parsear_filtro(crudo: str) -> Filtro:
    partes = crudo.split(":", 2)
    if len(partes) < 2:
        raise ConsultaInvalida(
            f"El filtro {crudo!r} debe tener la forma campo:operador o campo:operador:valor"
        )
    campo, operador_crudo = partes[0].strip(), partes[1].strip()
    try:
        operador = Operador(operador_crudo)
    except ValueError as exc:
        permitidos = ", ".join(sorted(o.value for o in Operador))
        raise ConsultaInvalida(
            f"El operador {operador_crudo!r} no existe; permitidos: {permitidos}"
        ) from exc
    if len(partes) == 2:
        return Filtro(campo=campo, operador=operador)
    valores = tuple(campos.convertir(campo, valor) for valor in partes[2].split(SEPARADOR_VALORES))
    return Filtro(campo=campo, operador=operador, valores=valores)


def _parsear_orden(crudo: str | None) -> Orden | None:
    if not crudo:
        return None
    descendente = crudo.startswith("-")
    return Orden(campo=crudo.lstrip("-").strip(), descendente=descendente)


def _parsear_indicador(crudo: str) -> Indicador:
    partes = [parte.strip() for parte in crudo.split(":")]
    if len(partes) not in (2, 3):
        raise ConsultaInvalida(
            f"El indicador {crudo!r} debe tener la forma nombre:funcion o nombre:funcion:campo"
        )
    try:
        funcion = Funcion(partes[1])
    except ValueError as exc:
        permitidas = ", ".join(sorted(f.value for f in Funcion))
        raise ConsultaInvalida(
            f"La funcion {partes[1]!r} no existe; permitidas: {permitidas}"
        ) from exc
    return Indicador(
        nombre=partes[0], funcion=funcion, campo=partes[2] if len(partes) == 3 else None
    )


def _traducir_errores(exc: Exception) -> HTTPException:
    if isinstance(exc, SinVersionVigente):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/campos")
def listar_campos(
    servicio: ConsultaCarteraService = Depends(obtener_servicio_cartera),
) -> dict[str, dict]:
    """Campos consultables con su tipo y los operadores que admite cada uno."""
    return servicio.campos_disponibles()


@router.get("", response_model=PaginaRespuesta)
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
            [_parsear_filtro(crudo) for crudo in filtro],
            _parsear_orden(orden),
            limite,
            desplazamiento,
        )
    except (ConsultaInvalida, SinVersionVigente) as exc:
        raise _traducir_errores(exc) from exc
    return PaginaRespuesta(
        total=pagina.total,
        limite=pagina.limite,
        desplazamiento=pagina.desplazamiento,
        suficiente=pagina.suficiente,
        productos=[_producto(fila) for fila in pagina.filas],
    )


@router.get("/metricas", response_model=MetricasRespuesta)
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
            [_parsear_filtro(crudo) for crudo in filtro],
            [_parsear_indicador(crudo) for crudo in indicador],
        )
    except (ConsultaInvalida, SinVersionVigente) as exc:
        raise _traducir_errores(exc) from exc
    return MetricasRespuesta(
        cuentas=metricas.cuentas,
        capital_total=str(metricas.capital_total),
        cuota_minima=None if metricas.cuota_minima is None else str(metricas.cuota_minima),
        cuota_maxima=None if metricas.cuota_maxima is None else str(metricas.cuota_maxima),
        cuentas_por_segmento=metricas.cuentas_por_segmento,
        adicionales={
            nombre: _texto_si_es_monto(valor) for nombre, valor in metricas.adicionales.items()
        },
    )


@router.get("/segmentacion", response_model=SegmentacionRespuesta)
def segmentar_cartera(
    fecha_corte: date,
    campo: str,
    filtro: list[str] = Query(default=[]),
    servicio: ConsultaCarteraService = Depends(obtener_servicio_cartera),
) -> SegmentacionRespuesta:
    """Cuentas y capital por cada valor de un atributo (RF-06)."""
    try:
        segmentacion = servicio.segmentar(
            fecha_corte, campo, [_parsear_filtro(crudo) for crudo in filtro]
        )
    except (ConsultaInvalida, SinVersionVigente) as exc:
        raise _traducir_errores(exc) from exc
    return SegmentacionRespuesta(
        campo=segmentacion.campo,
        grupos=[
            GrupoRespuesta(valor=grupo.valor, cuentas=grupo.cuentas, capital=str(grupo.capital))
            for grupo in segmentacion.grupos
        ],
    )
