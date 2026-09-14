"""Recorrido paginado de una seleccion de cartera (RF-08, RF-09).

Lo usan la generacion de cargas y los conectores de plataforma (MOWA MES): todos
recorren los primeros `cantidad` productos con el mismo orden y el mismo
desempate por pagare que `/cartera` y `/cartera/resumen`, sin tener la cartera
entera en memoria.
"""

from collections.abc import Iterator, Mapping, Sequence
from datetime import date
from typing import Any

from app.core.entities.cartera import Filtro, Orden, PaginaCartera
from app.core.services.seleccion_cartera.servicio import LIMITE_MAXIMO, ConsultaCarteraService


class SeleccionPaginada:
    """Recorre la seleccion en paginas del tamano que admite la consulta.

    La consulta ya ordena con un desempate estable por pagare, asi que paginar
    no repite ni salta productos.
    """

    def __init__(
        self,
        consulta: ConsultaCarteraService,
        fecha_corte: date,
        filtros: Sequence[Filtro],
        orden: Orden | None,
        cantidad: int,
    ) -> None:
        self._consulta = consulta
        self._fecha_corte = fecha_corte
        self._filtros = tuple(filtros)
        self._orden = orden
        self._cantidad = cantidad
        # Primera pagina por adelantado: valida la consulta y deja el total
        # disponible a la vista antes de generar nada.
        self._primera = self._pagina(desplazamiento=0)
        self.disponibles: int = self._primera.total

    def __iter__(self) -> Iterator[Mapping[str, Any]]:
        entregados = 0
        pagina = self._primera
        while pagina.filas:
            for fila in pagina.filas:
                yield fila
                entregados += 1
            if entregados >= min(self._cantidad, self.disponibles):
                return
            pagina = self._pagina(desplazamiento=entregados)

    def _pagina(self, desplazamiento: int) -> PaginaCartera:
        limite = min(self._cantidad - desplazamiento, LIMITE_MAXIMO)
        return self._consulta.consultar(
            self._fecha_corte,
            self._filtros,
            self._orden,
            limite=max(limite, 1),
            desplazamiento=desplazamiento,
        )
