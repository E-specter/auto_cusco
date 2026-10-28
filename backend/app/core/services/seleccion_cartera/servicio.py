"""Caso de uso: consultar la cartera de una fecha de corte.

Valida la consulta contra el catalogo de campos y la delega al repositorio.
La cartera siempre sale de la version vigente de esa fecha (RF-04).
"""

from collections.abc import Sequence
from datetime import date

from app.core.config import UMBRAL_VALORES_FILTRO_POR_DEFECTO
from app.core.entities.cartera import (
    BloqueResumen,
    ConsultaInvalida,
    Filtro,
    Indicador,
    MetricasCartera,
    Orden,
    PaginaCartera,
    Recorte,
    ResumenCartera,
    Segmentacion,
    SinVersionVigente,
    TipoDato,
    ValoresCartera,
)
from app.core.ports.repositorio_cartera_port import RepositorioCarteraPort
from app.core.services.seleccion_cartera.cache_valores import CacheValoresFiltro
from app.core.services.seleccion_cartera.campos import CatalogoCartera

LIMITE_MAXIMO = 5000
# Tope del "top n" de una seleccion, que es tambien el de un archivo de carga.
# Medido y no estimado: ha habido sabanas de mas de 55 000 filas, y con 120 000
# la generacion sigue siendo lineal en tiempo y razonable en memoria
# (docs/generacion-cargas.md, seccion 4). Volver a medir con
# scripts/medir_generacion.py antes de subirlo.
CANTIDAD_MAXIMA = 120_000


class ConsultaCarteraService:
    def __init__(
        self,
        repositorio: RepositorioCarteraPort,
        catalogo: CatalogoCartera | None = None,
        umbral_valores: int = UMBRAL_VALORES_FILTRO_POR_DEFECTO,
        cache_valores: CacheValoresFiltro | None = None,
    ) -> None:
        self._repositorio = repositorio
        self._catalogo = catalogo or CatalogoCartera()
        self._umbral_valores = umbral_valores
        # La API crea un servicio por pedido: para que la memoria sirva entre pedidos hay que
        # pasarle una compartida. Sin ella, cada servicio tiene la suya.
        self._cache_valores = cache_valores or CacheValoresFiltro()

    @property
    def catalogo(self) -> CatalogoCartera:
        """El catalogo de campos de esta consulta: lo reciben quienes parsean o arman columnas."""
        return self._catalogo

    def campos_disponibles(self) -> dict[str, dict]:
        return self._catalogo.catalogo_publico()

    def consultar(
        self,
        fecha_corte: date,
        filtros: Sequence[Filtro] = (),
        orden: Orden | None = None,
        limite: int = 50,
        desplazamiento: int = 0,
    ) -> PaginaCartera:
        """Productos de la fecha que cumplen los filtros (RF-04, RF-05, RF-08)."""
        self._validar(fecha_corte, filtros)
        if orden is not None:
            self._catalogo.validar_orden(orden)
        self._validar_paginacion(limite, desplazamiento)
        total, filas = self._repositorio.consultar(
            fecha_corte, tuple(filtros), orden, limite, desplazamiento
        )
        return PaginaCartera(
            total=total, filas=tuple(filas), limite=limite, desplazamiento=desplazamiento
        )

    def metricas(
        self,
        fecha_corte: date,
        filtros: Sequence[Filtro] = (),
        indicadores: Sequence[Indicador] = (),
    ) -> MetricasCartera:
        """Indicadores de RF-26 sobre la seleccion, mas los adicionales de RF-27."""
        self._validar(fecha_corte, filtros)
        self._validar_indicadores(indicadores)
        return self._repositorio.metricas(fecha_corte, tuple(filtros), tuple(indicadores))

    def segmentar(
        self, fecha_corte: date, campo: str, filtros: Sequence[Filtro] = ()
    ) -> Segmentacion:
        """Cuentas y capital por cada valor de un atributo (RF-06)."""
        self._validar(fecha_corte, filtros)
        self._catalogo.tipo_de(campo)
        grupos = self._repositorio.segmentar(fecha_corte, campo, tuple(filtros))
        return Segmentacion(campo=campo, grupos=tuple(grupos))

    def valores(
        self, fecha_corte: date, campo: str, filtros: Sequence[Filtro] = ()
    ) -> ValoresCartera:
        """La lista de valores de un campo de TEXTO para el filtro (RF-67), base o adicional,
        archivados incluidos.

        Si se ofrece la lista se decide sobre la fecha ENTERA (distintos no nulos <= umbral), asi un
        campo no cambia de control segun los filtros de arriba; con mas, no se devuelve ningun
        valor.
        La lista es contextual: cuenta los productos que cumplen `filtros` (los de arriba, en
        cascada). Orden (D-FV-2): cantidad descendente, desempate alfabetico, «(vacio)» al final.
        Los valores se comparan tal cual (D-FV-1).
        """
        tipo = self._catalogo.tipo_de(campo)
        if tipo is not TipoDato.TEXTO:
            raise ConsultaInvalida(
                f"El campo {campo!r} es {tipo.value}: solo los de texto tienen lista de valores"
            )
        for filtro in filtros:
            self._catalogo.validar_filtro(filtro)
        carga_id = self._repositorio.version_vigente(fecha_corte)
        if carga_id is None:
            raise SinVersionVigente(fecha_corte)
        umbral = self._umbral_valores
        cache = self._cache_valores

        # 1. La decision, una vez por (carga vigente, campo, umbral). Va PRIMERO y por separado,
        # aunque no haya filtros: `DISTINCT ... LIMIT umbral + 1` corta pronto en un campo de alta
        # cardinalidad (un documento), y una agrupacion no: tendria que agrupar todos los productos
        # de la fecha y traer decenas de miles de grupos solo para descubrir que no se ofrece.
        # Por la misma razon no hay atajo «la lista ya supera el umbral»: la lista se pide despues
        # de saber que el campo cabe, y lo filtrado esta siempre dentro de la fecha entera.
        clave_decision = (carga_id, campo, umbral)
        ofrece_lista = cache.decision(clave_decision)
        if ofrece_lista is None:
            ofrece_lista = (
                self._repositorio.distintos_hasta(fecha_corte, campo, umbral + 1) <= umbral
            )
            cache.guardar_decision(clave_decision, ofrece_lista)
        if not ofrece_lista:
            return ValoresCartera(campo=campo, umbral=umbral, ofrece_lista=False, valores=())

        # 2. La lista contextual: una agrupacion por (carga, campo, filtros de arriba). Se ordena
        # aqui (son <= umbral grupos): el vacio al final no lo da un ORDER BY sencillo.
        clave_lista = (carga_id, campo, tuple(filtros), umbral)
        ordenados = cache.lista(clave_lista)
        if ordenados is None:
            encontrados = self._repositorio.valores_de(fecha_corte, campo, tuple(filtros))
            ordenados = tuple(
                sorted(encontrados, key=lambda v: (v.valor is None, -v.cantidad, v.valor or ""))
            )
            cache.guardar_lista(clave_lista, ordenados)
        return ValoresCartera(campo=campo, umbral=umbral, ofrece_lista=True, valores=ordenados)

    def resumen(
        self,
        fecha_corte: date,
        filtros: Sequence[Filtro] = (),
        orden: Orden | None = None,
        cantidad: int | None = None,
        indicadores: Sequence[Indicador] = (),
        segmento: str | None = None,
    ) -> ResumenCartera:
        """Metricas del universo filtrado y, con cantidad, de sus primeros n.

        Los primeros n salen con el mismo orden y el mismo desempate por pagare que
        `consultar` y que la generacion del archivo de carga, asi que las metricas
        de la seleccion describen exactamente esos productos. Pensado para RF-28:
        un solo pedido por cada cambio de filtro.
        """
        if orden is not None:
            self._catalogo.validar_orden(orden)
        if cantidad is not None and not 1 <= cantidad <= CANTIDAD_MAXIMA:
            raise ConsultaInvalida(f"La cantidad debe estar entre 1 y {CANTIDAD_MAXIMA}")
        if segmento is not None:
            self._catalogo.tipo_de(segmento)
        self._validar_indicadores(indicadores)
        self._validar(fecha_corte, filtros)
        filtros, indicadores = tuple(filtros), tuple(indicadores)
        universo = self._bloque(fecha_corte, filtros, indicadores, segmento)
        seleccion = (
            None
            if cantidad is None
            else self._bloque(fecha_corte, filtros, indicadores, segmento, Recorte(orden, cantidad))
        )
        return ResumenCartera(
            disponibles=universo.metricas.cuentas,
            solicitados=cantidad,
            universo=universo,
            seleccion=seleccion,
        )

    def _bloque(
        self,
        fecha_corte: date,
        filtros: tuple[Filtro, ...],
        indicadores: tuple[Indicador, ...],
        segmento: str | None,
        recorte: Recorte | None = None,
    ) -> BloqueResumen:
        metricas = self._repositorio.metricas(fecha_corte, filtros, indicadores, recorte=recorte)
        if segmento is None:
            return BloqueResumen(metricas=metricas)
        grupos = self._repositorio.segmentar(fecha_corte, segmento, filtros, recorte=recorte)
        return BloqueResumen(
            metricas=metricas, segmentacion=Segmentacion(campo=segmento, grupos=tuple(grupos))
        )

    def _validar_indicadores(self, indicadores: Sequence[Indicador]) -> None:
        nombres: set[str] = set()
        for indicador in indicadores:
            self._catalogo.validar_indicador(indicador)
            if indicador.nombre in nombres:
                raise ConsultaInvalida(f"El indicador {indicador.nombre!r} esta repetido")
            nombres.add(indicador.nombre)

    def _validar(self, fecha_corte: date, filtros: Sequence[Filtro]) -> None:
        for filtro in filtros:
            self._catalogo.validar_filtro(filtro)
        if not self._repositorio.hay_version_vigente(fecha_corte):
            raise SinVersionVigente(fecha_corte)

    @staticmethod
    def _validar_paginacion(limite: int, desplazamiento: int) -> None:
        if not 1 <= limite <= LIMITE_MAXIMO:
            raise ConsultaInvalida(f"El limite debe estar entre 1 y {LIMITE_MAXIMO}")
        if desplazamiento < 0:
            raise ConsultaInvalida("El desplazamiento no puede ser negativo")
