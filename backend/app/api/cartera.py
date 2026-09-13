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
from app.api.respuestas import ModeloRespuesta
from app.core.entities.cartera import (
    BloqueResumen,
    ConsultaInvalida,
    MetricasCartera,
    Segmentacion,
    SinVersionVigente,
)
from app.core.services.seleccion_cartera.servicio import CANTIDAD_MAXIMA, ConsultaCarteraService

router = APIRouter(prefix="/cartera", tags=["cartera"])


def crear_servicio_cartera() -> ConsultaCarteraService:
    return ConsultaCarteraService(RepositorioCarteraPostgres(get_engine()))


def obtener_servicio_cartera() -> ConsultaCarteraService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return crear_servicio_cartera()


class CampoRespuesta(ModeloRespuesta):
    tipo: str
    operadores: list[str]


class GrupoRespuesta(ModeloRespuesta):
    valor: Any
    cuentas: int
    capital: str


class SegmentacionRespuesta(ModeloRespuesta):
    campo: str
    grupos: list[GrupoRespuesta]


class PaginaRespuesta(ModeloRespuesta):
    total: int
    limite: int
    desplazamiento: int
    suficiente: bool
    productos: list[dict[str, Any]]


class MetricasRespuesta(ModeloRespuesta):
    cuentas: int
    capital_total: str
    cuota_minima: str | None
    cuota_maxima: str | None
    cuentas_por_segmento: dict[str, int]
    adicionales: dict[str, Any]


class BloqueRespuesta(ModeloRespuesta):
    metricas: MetricasRespuesta
    segmentacion: SegmentacionRespuesta | None


class ResumenRespuesta(ModeloRespuesta):
    disponibles: int
    solicitados: int | None
    suficiente: bool
    universo: BloqueRespuesta
    seleccion: BloqueRespuesta | None


def _metricas_respuesta(metricas: MetricasCartera) -> MetricasRespuesta:
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


def _segmentacion_respuesta(segmentacion: Segmentacion) -> SegmentacionRespuesta:
    return SegmentacionRespuesta(
        campo=segmentacion.campo,
        grupos=[
            GrupoRespuesta(valor=grupo.valor, cuentas=grupo.cuentas, capital=str(grupo.capital))
            for grupo in segmentacion.grupos
        ],
    )


def _bloque_respuesta(bloque: BloqueResumen) -> BloqueRespuesta:
    return BloqueRespuesta(
        metricas=_metricas_respuesta(bloque.metricas),
        segmentacion=(
            None if bloque.segmentacion is None else _segmentacion_respuesta(bloque.segmentacion)
        ),
    )


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
    return _metricas_respuesta(metricas)


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
    return _segmentacion_respuesta(segmentacion)


@router.get("/resumen", response_model=ResumenRespuesta, responses=respuestas_de_error(400, 404))
def resumir_cartera(
    fecha_corte: date,
    filtro: list[str] = Query(default=[]),
    orden: str | None = Query(
        default=None, description="Que productos son los primeros: campo, o -campo"
    ),
    cantidad: int | None = Query(
        default=None,
        ge=1,
        le=CANTIDAD_MAXIMA,
        description="El n del top n. Sin ella no hay bloque de seleccion",
    ),
    indicador: list[str] = Query(default=[]),
    segmento: str | None = Query(
        default=None, description="Campo por el que segmentar los dos bloques"
    ),
    servicio: ConsultaCarteraService = Depends(obtener_servicio_cartera),
) -> ResumenRespuesta:
    """Metricas del universo filtrado y de sus primeros n, lado a lado (RF-08, RF-26 a RF-28).

    Los primeros n son los mismos productos que devuelve `/cartera` con ese orden
    y los mismos que se escriben en el archivo de carga.
    """
    try:
        resumen = servicio.resumen(
            fecha_corte,
            [parsear_filtro(crudo) for crudo in filtro],
            parsear_orden(orden),
            cantidad,
            [parsear_indicador(crudo) for crudo in indicador],
            segmento,
        )
    except (ConsultaInvalida, SinVersionVigente) as exc:
        raise traducir_errores(exc) from exc
    return ResumenRespuesta(
        disponibles=resumen.disponibles,
        solicitados=resumen.solicitados,
        suficiente=resumen.suficiente,
        universo=_bloque_respuesta(resumen.universo),
        seleccion=None if resumen.seleccion is None else _bloque_respuesta(resumen.seleccion),
    )
