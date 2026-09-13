"""Consulta de cartera sobre PostgreSQL: filtros, orden, metricas y segmentacion.

Todo se resuelve contra la version vigente de la fecha pedida, uniendo
`carga_fila` con `carga`. Los filtros llegan validados por el caso de uso y se
traducen a expresiones de SQLAlchemy, nunca a SQL armado con texto.
"""

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, Engine, FromClause, Select, func, select

from app.adapters.persistence.modelos import Carga, CargaFila
from app.core.entities.cartera import (
    Filtro,
    Funcion,
    Grupo,
    Indicador,
    MetricasCartera,
    Operador,
    Orden,
    Recorte,
)
from app.core.ports.repositorio_cartera_port import RepositorioCarteraPort

_FILA = CargaFila.__table__
_CARGA = Carga.__table__
_COLUMNAS = {columna.name: columna for columna in _FILA.columns}
_COLUMNAS_PRODUCTO = [c for c in _FILA.columns if c.name != "carga_id"]

CAMPO_CAPITAL = "saldo_capital_pendiente"
CAMPO_CUOTA = "monto_cuota"
CAMPO_SEGMENTO = "segmento_financiero"
SIN_SEGMENTO = "(sin segmento)"


def _condicion(filtro: Filtro) -> ColumnElement[bool]:
    columna = _COLUMNAS[filtro.campo]
    valores = filtro.valores
    match filtro.operador:
        case Operador.IGUAL:
            return columna == valores[0]
        case Operador.DISTINTO:
            return columna.is_distinct_from(valores[0])
        case Operador.MAYOR:
            return columna > valores[0]
        case Operador.MAYOR_IGUAL:
            return columna >= valores[0]
        case Operador.MENOR:
            return columna < valores[0]
        case Operador.MENOR_IGUAL:
            return columna <= valores[0]
        case Operador.CONTIENE:
            return columna.icontains(valores[0], autoescape=True)
        case Operador.EMPIEZA_CON:
            return columna.istartswith(valores[0], autoescape=True)
        case Operador.EN:
            return columna.in_(valores)
        case Operador.ENTRE:
            return columna.between(valores[0], valores[1])
        case Operador.VACIO:
            return columna.is_(None)
        case Operador.NO_VACIO:
            return columna.is_not(None)
    raise ValueError(f"Operador no soportado: {filtro.operador}")  # pragma: no cover


def _ordenar(consulta: Select, orden: Orden | None) -> Select:
    """Orden pedido con los nulos al final y desempate estable por pagare.

    Es el mismo para la lista, los primeros n de las metricas y el archivo de
    carga: si difiriera, las metricas de la seleccion describirian otros productos.
    """
    if orden is not None:
        columna = _COLUMNAS[orden.campo]
        criterio = columna.desc() if orden.descendente else columna.asc()
        consulta = consulta.order_by(criterio.nulls_last())
    return consulta.order_by(_FILA.c.pagare)


def _agregado(indicador: Indicador, columnas: Mapping[str, ColumnElement]):
    if indicador.campo is None:  # solo CONTEO llega sin campo (validado en el nucleo)
        return func.count()
    columna = columnas[indicador.campo]
    match indicador.funcion:
        case Funcion.SUMA:
            return func.sum(columna)
        case Funcion.CONTEO:
            return func.count(columna)
        case Funcion.PROMEDIO:
            return func.avg(columna)
        case Funcion.MINIMO:
            return func.min(columna)
        case Funcion.MAXIMO:
            return func.max(columna)
    raise ValueError(f"Funcion no soportada: {indicador.funcion}")  # pragma: no cover


class RepositorioCarteraPostgres(RepositorioCarteraPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @staticmethod
    def _origen():
        return _FILA.join(_CARGA, _CARGA.c.id == _FILA.c.carga_id)

    @staticmethod
    def _condiciones(fecha_corte: date, filtros: Sequence[Filtro]) -> list[ColumnElement[bool]]:
        return [
            _CARGA.c.fecha_corte == fecha_corte,
            _CARGA.c.vigente,
            *(_condicion(filtro) for filtro in filtros),
        ]

    def hay_version_vigente(self, fecha_corte: date) -> bool:
        with self._engine.connect() as cx:
            return (
                cx.execute(
                    select(_CARGA.c.id).where(_CARGA.c.fecha_corte == fecha_corte, _CARGA.c.vigente)
                ).scalar_one_or_none()
                is not None
            )

    def consultar(
        self,
        fecha_corte: date,
        filtros: Sequence[Filtro],
        orden: Orden | None,
        limite: int,
        desplazamiento: int,
    ) -> tuple[int, list[dict[str, Any]]]:
        condiciones = self._condiciones(fecha_corte, filtros)
        consulta = select(*_COLUMNAS_PRODUCTO).select_from(self._origen()).where(*condiciones)
        consulta = _ordenar(consulta, orden).limit(limite).offset(desplazamiento)
        with self._engine.connect() as cx:
            total = cx.execute(
                select(func.count()).select_from(self._origen()).where(*condiciones)
            ).scalar_one()
            filas = [dict(fila._mapping) for fila in cx.execute(consulta)]
        return total, filas

    def _fuente(
        self, fecha_corte: date, filtros: Sequence[Filtro], recorte: Recorte | None
    ) -> tuple[FromClause, list[ColumnElement[bool]], Mapping[str, ColumnElement]]:
        """De donde se agrega: el universo filtrado o, con recorte, sus primeros n.

        El recorte es una subconsulta con el mismo orden y LIMIT que la lista; las
        metricas se calculan sobre sus columnas.
        """
        condiciones = self._condiciones(fecha_corte, filtros)
        if recorte is None:
            return self._origen(), condiciones, _COLUMNAS
        seleccion = select(*_COLUMNAS_PRODUCTO).select_from(self._origen()).where(*condiciones)
        primeros = _ordenar(seleccion, recorte.orden).limit(recorte.cantidad).subquery("primeros")
        return primeros, [], {columna.name: columna for columna in primeros.c}

    def metricas(
        self,
        fecha_corte: date,
        filtros: Sequence[Filtro],
        indicadores: Sequence[Indicador],
        recorte: Recorte | None = None,
    ) -> MetricasCartera:
        origen, condiciones, columnas = self._fuente(fecha_corte, filtros, recorte)
        capital = columnas[CAMPO_CAPITAL]
        cuota = columnas[CAMPO_CUOTA]
        segmento = columnas[CAMPO_SEGMENTO]
        base = (
            select(
                func.count(),
                func.coalesce(func.sum(capital), 0),
                func.min(cuota),
                func.max(cuota),
                *(_agregado(indicador, columnas) for indicador in indicadores),
            )
            .select_from(origen)
            .where(*condiciones)
        )
        por_segmento = (
            select(segmento, func.count())
            .select_from(origen)
            .where(*condiciones)
            .group_by(segmento)
            .order_by(segmento)
        )
        with self._engine.connect() as cx:
            cuentas, capital_total, cuota_minima, cuota_maxima, *valores = cx.execute(base).one()
            segmentos = cx.execute(por_segmento).all()
        return MetricasCartera(
            cuentas=cuentas,
            capital_total=Decimal(capital_total),
            cuota_minima=cuota_minima,
            cuota_maxima=cuota_maxima,
            cuentas_por_segmento={
                (valor if valor is not None else SIN_SEGMENTO): conteo
                for valor, conteo in segmentos
            },
            adicionales={
                indicador.nombre: valor
                for indicador, valor in zip(indicadores, valores, strict=True)
            },
        )

    def segmentar(
        self,
        fecha_corte: date,
        campo: str,
        filtros: Sequence[Filtro],
        recorte: Recorte | None = None,
    ) -> list[Grupo]:
        origen, condiciones, columnas = self._fuente(fecha_corte, filtros, recorte)
        columna = columnas[campo]
        capital = columnas[CAMPO_CAPITAL]
        consulta = (
            select(columna, func.count(), func.coalesce(func.sum(capital), 0))
            .select_from(origen)
            .where(*condiciones)
            .group_by(columna)
            .order_by(func.count().desc(), columna)
        )
        with self._engine.connect() as cx:
            filas = cx.execute(consulta).all()
        return [
            Grupo(valor=valor, cuentas=cuentas, capital=Decimal(total))
            for valor, cuentas, total in filas
        ]
