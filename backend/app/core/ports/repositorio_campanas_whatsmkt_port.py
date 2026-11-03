"""Puerto de persistencia de las campanas de WhatsMKT (T-WM-B4b1)."""

from datetime import date
from typing import Protocol

from app.core.entities.whatsmkt import ModoCampana
from app.core.entities.whatsmkt_campana import (
    ArchivoGuardado,
    CampanaWhatsmkt,
    LoteCreado,
    LoteNuevo,
    PaginaCampanas,
    PaginaExclusiones,
)


class RepositorioCampanasWhatsmktPort(Protocol):
    def crear_lote(self, lote: LoteNuevo) -> LoteCreado:
        """Guarda el lote COMPLETO en una sola transaccion: el lote, cada campana con su archivo,
        sus filas y sus exclusiones, y las exclusiones sin campana. Marca como usadas la version
        del texto y la de la definicion. Si algo falla no queda nada."""
        ...

    def obtener_archivo(self, campana_id: int) -> ArchivoGuardado | None:
        """Los bytes guardados al crear la campana, o None si no existe."""
        ...

    def listar(
        self,
        limite: int,
        desplazamiento: int,
        lote_id: int | None = None,
        mes: date | None = None,
    ) -> PaginaCampanas:
        """Las campanas, las mas recientes primero (desempate por id). `mes` es el primer dia del
        mes de la fecha de envio; ambos filtros son opcionales. `total` cuenta las que cumplen
        los filtros, no solo las de la pagina."""
        ...

    def obtener(self, campana_id: int) -> CampanaWhatsmkt | None: ...

    def modo_del_lote(self, lote_id: int) -> ModoCampana: ...

    def listar_exclusiones(
        self, lote_id: int, campana_id: int | None, limite: int, desplazamiento: int
    ) -> PaginaExclusiones:
        """Las exclusiones de una campana o, con `campana_id=None`, las del lote que quedaron
        fuera de todas sus campanas. En el orden de la seleccion."""
        ...
