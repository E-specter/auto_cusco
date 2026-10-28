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
from app.adapters.persistence.repositorio_mapeador_postgres import (
    RepositorioCamposAdicionalesPostgres,
)
from app.api.consultas import (
    parsear_filtro,
    parsear_indicador,
    parsear_orden,
    texto_si_es_monto,
    traducir_errores,
)
from app.api.errores import respuestas_de_error
from app.api.respuestas import ModeloRespuesta
from app.core.config import get_settings
from app.core.entities.cartera import (
    BloqueResumen,
    ConsultaInvalida,
    MetricasCartera,
    Segmentacion,
    SinVersionVigente,
)
from app.core.services.seleccion_cartera.cache_valores import CacheValoresFiltro
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.core.services.seleccion_cartera.servicio import CANTIDAD_MAXIMA, ConsultaCarteraService

router = APIRouter(prefix="/cartera", tags=["cartera"])


def crear_catalogo_cartera() -> CatalogoCartera:
    """El catalogo de campos de la cartera: la base y los adicionales guardados. Uno por peticion,
    porque lee las definiciones una sola vez."""
    return CatalogoCartera(RepositorioCamposAdicionalesPostgres(get_engine()))


def obtener_catalogo_cartera() -> CatalogoCartera:
    """Dependencia de FastAPI: el catalogo con el que se leen los filtros de la peticion."""
    return crear_catalogo_cartera()


# La memoria de las listas de valores es del proceso, no del pedido: la API crea un servicio por
# pedido, y una memoria por servicio no serviria de nada. Es acotada y se renueva sola cuando cambia
# la carga vigente (ver `cache_valores.py`).
CACHE_VALORES = CacheValoresFiltro()


def crear_servicio_cartera() -> ConsultaCarteraService:
    catalogo = crear_catalogo_cartera()
    return ConsultaCarteraService(
        RepositorioCarteraPostgres(get_engine(), catalogo),
        catalogo,
        get_settings().umbral_valores_filtro,
        CACHE_VALORES,
    )


def obtener_servicio_cartera() -> ConsultaCarteraService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return crear_servicio_cartera()


class CampoRespuesta(ModeloRespuesta):
    """Un campo filtrable. Uno `adicional` (RF-64) trae su nombre legible en `etiqueta`, un texto
    literal; en un campo base es nulo y el nombre sale de la clave `campo.<nombre>`. Uno `archivado`
    no se ofrece para filtros nuevos, pero se lista: una seleccion guardada que filtra por el
    necesita su etiqueta y su tipo."""

    tipo: str
    operadores: list[str]
    adicional: bool = False
    etiqueta: str | None = None
    archivado: bool = False


class ValorRespuesta(ModeloRespuesta):
    """Un valor del campo y cuantos productos lo tienen. `valor` nulo es «(vacio)»: los productos
    sin valor."""

    valor: str | None
    cantidad: int


class ValoresRespuesta(ModeloRespuesta):
    """La lista de valores de un campo de texto para el filtro (RF-67).

    `ofrece_lista` se decide sobre la fecha entera, sin filtros: es falso si el campo tiene mas de
    `umbral` valores distintos, y entonces `valores` va vacio (nunca se devuelve un valor). Con
    lista, `valores` sale por cantidad descendente, con desempate alfabetico y el vacio al final.
    `umbral` viaja para que la pantalla no lo duplique.
    """

    campo: str
    umbral: int
    ofrece_lista: bool
    valores: list[ValorRespuesta]


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
    catalogo: CatalogoCartera = Depends(obtener_catalogo_cartera),
) -> PaginaRespuesta:
    """Productos de la version vigente de la fecha (RF-04, RF-05, RF-08)."""
    try:
        pagina = servicio.consultar(
            fecha_corte,
            [parsear_filtro(crudo, catalogo) for crudo in filtro],
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
    catalogo: CatalogoCartera = Depends(obtener_catalogo_cartera),
) -> MetricasRespuesta:
    """Capital, cuentas, segmentos y cuotas de la seleccion (RF-26), mas RF-27."""
    try:
        metricas = servicio.metricas(
            fecha_corte,
            [parsear_filtro(crudo, catalogo) for crudo in filtro],
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
    catalogo: CatalogoCartera = Depends(obtener_catalogo_cartera),
) -> SegmentacionRespuesta:
    """Cuentas y capital por cada valor de un atributo (RF-06)."""
    try:
        segmentacion = servicio.segmentar(
            fecha_corte, campo, [parsear_filtro(crudo, catalogo) for crudo in filtro]
        )
    except (ConsultaInvalida, SinVersionVigente) as exc:
        raise traducir_errores(exc) from exc
    return _segmentacion_respuesta(segmentacion)


@router.get("/valores", response_model=ValoresRespuesta, responses=respuestas_de_error(400, 404))
def valores_de_un_campo(
    fecha_corte: date,
    campo: str,
    filtro: list[str] = Query(
        default=[], description="Los filtros de arriba, en la sintaxis de siempre (cascada)"
    ),
    servicio: ConsultaCarteraService = Depends(obtener_servicio_cartera),
    catalogo: CatalogoCartera = Depends(obtener_catalogo_cartera),
) -> ValoresRespuesta:
    """Los valores de un campo de TEXTO (base o adicional, archivados incluidos) con sus cantidades,
    entre los productos que cumplen los filtros de arriba (RF-67). Si el campo tiene mas valores
    distintos que el umbral en la fecha entera, `ofrece_lista` es falso y no se devuelve ninguno.
    `400` si el campo no existe o no es de texto; `404` si la fecha no tiene version vigente."""
    try:
        valores = servicio.valores(
            fecha_corte, campo, [parsear_filtro(crudo, catalogo) for crudo in filtro]
        )
    except (ConsultaInvalida, SinVersionVigente) as exc:
        raise traducir_errores(exc) from exc
    return ValoresRespuesta(
        campo=valores.campo,
        umbral=valores.umbral,
        ofrece_lista=valores.ofrece_lista,
        valores=[ValorRespuesta(valor=v.valor, cantidad=v.cantidad) for v in valores.valores],
    )


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
    catalogo: CatalogoCartera = Depends(obtener_catalogo_cartera),
) -> ResumenRespuesta:
    """Metricas del universo filtrado y de sus primeros n, lado a lado (RF-08, RF-26 a RF-28).

    Los primeros n son los mismos productos que devuelve `/cartera` con ese orden
    y los mismos que se escriben en el archivo de carga.
    """
    try:
        resumen = servicio.resumen(
            fecha_corte,
            [parsear_filtro(crudo, catalogo) for crudo in filtro],
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
