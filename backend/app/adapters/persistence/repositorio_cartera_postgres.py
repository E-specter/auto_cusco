"""Consulta de cartera sobre PostgreSQL: filtros, orden, metricas y segmentacion.

Todo se resuelve contra la version vigente de la fecha pedida, uniendo
`carga_fila` con `carga`. Los filtros llegan validados por el caso de uso y se
traducen a expresiones de SQLAlchemy, nunca a SQL armado con texto.

Un campo adicional (RF-64 a RF-66) no tiene columna propia: vive en el JSONB `adicionales` de
`carga_fila` (`{nombre: valor}`, ya normalizado por tipo al ingestar) y se lee como
`adicionales ->> 'ad_x'` con un CAST segun su tipo (`NUMERIC` o `DATE`; el texto, tal cual). Asi
filtros, orden, indicadores, segmentacion y las filas que salen (para las columnas de carga) lo
tratan igual que a un campo base. La columna llega con la migracion de T-CA-B2: hasta entonces solo
se arma el SQL (probado compilado al dialecto de PostgreSQL, sin base).
"""

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Date,
    Engine,
    FromClause,
    Numeric,
    Select,
    and_,
    cast,
    column,
    func,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB

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
    TipoDato,
    ValorDeFiltro,
)
from app.core.ports.repositorio_cartera_port import RepositorioCarteraPort
from app.core.services.seleccion_cartera.campos import CatalogoCartera

_FILA = CargaFila.__table__
_CARGA = Carga.__table__
# El JSON `adicionales` no es un campo ni sale tal cual: cada adicional se lee por su nombre.
_COLUMNAS = {c.name: c for c in _FILA.columns if c.name != "adicionales"}
_COLUMNAS_PRODUCTO = [c for c in _FILA.columns if c.name not in {"carga_id", "adicionales"}]

CAMPO_CAPITAL = "saldo_capital_pendiente"
CAMPO_CUOTA = "monto_cuota"
CAMPO_SEGMENTO = "segmento_financiero"
SIN_SEGMENTO = "(sin segmento)"


def _expresion_adicional(nombre: str, tipo: TipoDato) -> ColumnElement:
    """`adicionales ->> 'ad_x'` con el CAST de su tipo. El formato lo garantiza la ingesta
    (numero: texto decimal; fecha: ISO), asi que el CAST es seguro."""
    # La columna la crea la migracion de T-CA-B2; mientras tanto se nombra sin pasar por el modelo.
    adicionales = _FILA.c.get("adicionales")
    if adicionales is None:
        adicionales = column("adicionales", JSONB, _selectable=_FILA)
    texto = adicionales[nombre].astext
    if tipo is TipoDato.NUMERO:
        return cast(texto, Numeric)
    if tipo is TipoDato.FECHA:
        return cast(texto, Date)
    return texto


def _condicion_de_lista(
    columna: ColumnElement, valores: Sequence[Any], excluir: bool
) -> ColumnElement[bool]:
    """`en` y `no_en`, con el elemento vacio (`None`) como NULL.

    - `en`: `IN (reales)`, o `IN (reales) OR IS NULL` con vacio; solo el vacio: `IS NULL`.
    - `no_en`: `IS NULL OR NOT IN (reales)` (un producto sin valor no tiene ninguno de los
      marcados); con vacio, `IS NOT NULL AND NOT IN (reales)`; solo el vacio: `IS NOT NULL`.

    Con y sin el vacio, `en` y `no_en` parten la cartera: sin repetir ni perder productos.
    """
    reales = [v for v in valores if v is not None]
    con_vacio = len(reales) != len(valores)
    if not excluir:
        if not reales:
            return columna.is_(None)
        return or_(columna.in_(reales), columna.is_(None)) if con_vacio else columna.in_(reales)
    if not reales:
        return columna.is_not(None)
    if con_vacio:
        return and_(columna.is_not(None), columna.not_in(reales))
    return or_(columna.is_(None), columna.not_in(reales))


def _condicion(filtro: Filtro, columnas: Mapping[str, ColumnElement]) -> ColumnElement[bool]:
    columna = columnas[filtro.campo]
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
        case Operador.EN | Operador.NO_EN:
            return _condicion_de_lista(columna, valores, excluir=filtro.operador is Operador.NO_EN)
        case Operador.ENTRE:
            return columna.between(valores[0], valores[1])
        case Operador.VACIO:
            return columna.is_(None)
        case Operador.NO_VACIO:
            return columna.is_not(None)
    raise ValueError(f"Operador no soportado: {filtro.operador}")  # pragma: no cover


def _ordenar(
    consulta: Select, orden: Orden | None, columnas: Mapping[str, ColumnElement] = _COLUMNAS
) -> Select:
    """Orden pedido con los nulos al final y desempate estable por pagare.

    Es el mismo para la lista, los primeros n de las metricas y el archivo de
    carga: si difiriera, las metricas de la seleccion describirian otros productos.
    """
    if orden is not None:
        columna = columnas[orden.campo]
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
    def __init__(self, engine: Engine, catalogo: CatalogoCartera | None = None) -> None:
        self._engine = engine
        self._catalogo = catalogo or CatalogoCartera()

    @staticmethod
    def _origen():
        return _FILA.join(_CARGA, _CARGA.c.id == _FILA.c.carga_id)

    def _adicionales(self) -> dict[str, ColumnElement]:
        """Los campos adicionales (archivados incluidos: se leen) como expresiones."""
        return {
            nombre: _expresion_adicional(nombre, campo.tipo)
            for nombre, campo in self._catalogo.campos().items()
            if campo.adicional
        }

    def _columnas(self) -> dict[str, ColumnElement]:
        """Cada campo de la cartera por nombre: la columna del base o la expresion del adicional."""
        return {**_COLUMNAS, **self._adicionales()}

    def _columnas_producto(self) -> list[ColumnElement]:
        """Lo que sale de un producto: sus columnas y, rotulados con su nombre, los adicionales."""
        return [*_COLUMNAS_PRODUCTO, *(e.label(n) for n, e in self._adicionales().items())]

    def _condiciones(
        self, fecha_corte: date, filtros: Sequence[Filtro]
    ) -> list[ColumnElement[bool]]:
        columnas = self._columnas()
        return [
            _CARGA.c.fecha_corte == fecha_corte,
            _CARGA.c.vigente,
            *(_condicion(filtro, columnas) for filtro in filtros),
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
        cuenta, consulta = self._sentencias_de_consultar(
            fecha_corte, filtros, orden, limite, desplazamiento
        )
        with self._engine.connect() as cx:
            total = cx.execute(cuenta).scalar_one()
            filas = [dict(fila._mapping) for fila in cx.execute(consulta)]
        return total, filas

    def _sentencias_de_consultar(
        self,
        fecha_corte: date,
        filtros: Sequence[Filtro],
        orden: Orden | None,
        limite: int,
        desplazamiento: int,
    ) -> tuple[Select, Select]:
        condiciones = self._condiciones(fecha_corte, filtros)
        consulta = (
            select(*self._columnas_producto()).select_from(self._origen()).where(*condiciones)
        )
        consulta = _ordenar(consulta, orden, self._columnas()).limit(limite).offset(desplazamiento)
        cuenta = select(func.count()).select_from(self._origen()).where(*condiciones)
        return cuenta, consulta

    def _fuente(
        self, fecha_corte: date, filtros: Sequence[Filtro], recorte: Recorte | None
    ) -> tuple[FromClause, list[ColumnElement[bool]], Mapping[str, ColumnElement]]:
        """De donde se agrega: el universo filtrado o, con recorte, sus primeros n.

        El recorte es una subconsulta con el mismo orden y LIMIT que la lista; las
        metricas se calculan sobre sus columnas.
        """
        condiciones = self._condiciones(fecha_corte, filtros)
        if recorte is None:
            return self._origen(), condiciones, self._columnas()
        seleccion = (
            select(*self._columnas_producto()).select_from(self._origen()).where(*condiciones)
        )
        ordenada = _ordenar(seleccion, recorte.orden, self._columnas())
        primeros = ordenada.limit(recorte.cantidad).subquery("primeros")
        return primeros, [], {columna.name: columna for columna in primeros.c}

    def metricas(
        self,
        fecha_corte: date,
        filtros: Sequence[Filtro],
        indicadores: Sequence[Indicador],
        recorte: Recorte | None = None,
    ) -> MetricasCartera:
        base, por_segmento = self._sentencias_de_metricas(
            fecha_corte, filtros, indicadores, recorte
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

    def _sentencias_de_metricas(
        self,
        fecha_corte: date,
        filtros: Sequence[Filtro],
        indicadores: Sequence[Indicador],
        recorte: Recorte | None,
    ) -> tuple[Select, Select]:
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
        return base, por_segmento

    def segmentar(
        self,
        fecha_corte: date,
        campo: str,
        filtros: Sequence[Filtro],
        recorte: Recorte | None = None,
    ) -> list[Grupo]:
        consulta = self._sentencia_de_segmentar(fecha_corte, campo, filtros, recorte)
        with self._engine.connect() as cx:
            filas = cx.execute(consulta).all()
        return [
            Grupo(valor=valor, cuentas=cuentas, capital=Decimal(total))
            for valor, cuentas, total in filas
        ]

    def distintos_hasta(self, fecha_corte: date, campo: str, tope: int) -> int:
        with self._engine.connect() as cx:
            return cx.execute(self._sentencia_de_distintos(fecha_corte, campo, tope)).scalar_one()

    def _sentencia_de_distintos(self, fecha_corte: date, campo: str, tope: int) -> Select:
        """`SELECT count(*) FROM (SELECT DISTINCT campo ... LIMIT tope)`: la fecha entera, sin
        filtros, y corta en cuanto junta `tope` distintos."""
        columna = self._columnas()[campo]
        distintos = (
            select(columna.label("valor"))
            .select_from(self._origen())
            .where(*self._condiciones(fecha_corte, []), columna.is_not(None))
            .distinct()
            .limit(tope)
            .subquery("distintos")
        )
        return select(func.count()).select_from(distintos)

    def valores_de(
        self, fecha_corte: date, campo: str, filtros: Sequence[Filtro]
    ) -> list[ValorDeFiltro]:
        consulta = self._sentencia_de_segmentar(
            fecha_corte, campo, filtros, None, con_capital=False
        )
        with self._engine.connect() as cx:
            return [ValorDeFiltro(valor, cantidad) for valor, cantidad in cx.execute(consulta)]

    def _sentencia_de_segmentar(
        self,
        fecha_corte: date,
        campo: str,
        filtros: Sequence[Filtro],
        recorte: Recorte | None,
        con_capital: bool = True,
    ) -> Select:
        """La agrupacion de un campo con sus cantidades (y su capital, salvo `con_capital=False`:
        la lista de valores de un filtro no lo necesita)."""
        origen, condiciones, columnas = self._fuente(fecha_corte, filtros, recorte)
        columna = columnas[campo]
        medidas = [func.count()]
        if con_capital:
            medidas.append(func.coalesce(func.sum(columnas[CAMPO_CAPITAL]), 0))
        return (
            select(columna, *medidas)
            .select_from(origen)
            .where(*condiciones)
            .group_by(columna)
            .order_by(func.count().desc(), columna)
        )
