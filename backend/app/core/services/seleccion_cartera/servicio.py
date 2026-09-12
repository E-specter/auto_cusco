"""Caso de uso: consultar la cartera de una fecha de corte.

Valida la consulta contra el catalogo de campos y la delega al repositorio.
La cartera siempre sale de la version vigente de esa fecha (RF-04).
"""

from collections.abc import Sequence
from datetime import date

from app.core.entities.cartera import (
    ConsultaInvalida,
    Filtro,
    Indicador,
    MetricasCartera,
    Orden,
    PaginaCartera,
    Segmentacion,
    SinVersionVigente,
)
from app.core.ports.repositorio_cartera_port import RepositorioCarteraPort
from app.core.services.seleccion_cartera import campos

LIMITE_MAXIMO = 5000


class ConsultaCarteraService:
    def __init__(self, repositorio: RepositorioCarteraPort) -> None:
        self._repositorio = repositorio

    def campos_disponibles(self) -> dict[str, dict]:
        return campos.catalogo_publico()

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
            campos.validar_orden(orden)
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
        nombres: set[str] = set()
        for indicador in indicadores:
            campos.validar_indicador(indicador)
            if indicador.nombre in nombres:
                raise ConsultaInvalida(f"El indicador {indicador.nombre!r} esta repetido")
            nombres.add(indicador.nombre)
        return self._repositorio.metricas(fecha_corte, tuple(filtros), tuple(indicadores))

    def segmentar(
        self, fecha_corte: date, campo: str, filtros: Sequence[Filtro] = ()
    ) -> Segmentacion:
        """Cuentas y capital por cada valor de un atributo (RF-06)."""
        self._validar(fecha_corte, filtros)
        campos.tipo_de(campo)
        grupos = self._repositorio.segmentar(fecha_corte, campo, tuple(filtros))
        return Segmentacion(campo=campo, grupos=tuple(grupos))

    def _validar(self, fecha_corte: date, filtros: Sequence[Filtro]) -> None:
        for filtro in filtros:
            campos.validar_filtro(filtro)
        if not self._repositorio.hay_version_vigente(fecha_corte):
            raise SinVersionVigente(fecha_corte)

    @staticmethod
    def _validar_paginacion(limite: int, desplazamiento: int) -> None:
        if not 1 <= limite <= LIMITE_MAXIMO:
            raise ConsultaInvalida(f"El limite debe estar entre 1 y {LIMITE_MAXIMO}")
        if desplazamiento < 0:
            raise ConsultaInvalida("El desplazamiento no puede ser negativo")
