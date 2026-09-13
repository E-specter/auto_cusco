"""Puerto de consulta de cartera sobre la version vigente de una fecha."""

from collections.abc import Sequence
from datetime import date
from typing import Any, Protocol

from app.core.entities.cartera import (
    Filtro,
    Grupo,
    Indicador,
    MetricasCartera,
    Orden,
    Recorte,
)


class RepositorioCarteraPort(Protocol):
    """Los filtros llegan ya validados por el caso de uso."""

    def hay_version_vigente(self, fecha_corte: date) -> bool: ...

    def consultar(
        self,
        fecha_corte: date,
        filtros: Sequence[Filtro],
        orden: Orden | None,
        limite: int,
        desplazamiento: int,
    ) -> tuple[int, list[dict[str, Any]]]:
        """Total de productos que cumplen los filtros y la pagina pedida."""
        ...

    def metricas(
        self,
        fecha_corte: date,
        filtros: Sequence[Filtro],
        indicadores: Sequence[Indicador],
        recorte: Recorte | None = None,
    ) -> MetricasCartera:
        """Sobre todos los que cumplen los filtros o, con recorte, sobre sus primeros n.

        Los primeros n deben salir con el mismo orden y desempate que `consultar`.
        """
        ...

    def segmentar(
        self,
        fecha_corte: date,
        campo: str,
        filtros: Sequence[Filtro],
        recorte: Recorte | None = None,
    ) -> list[Grupo]: ...
