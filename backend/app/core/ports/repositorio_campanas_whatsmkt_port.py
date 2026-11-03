"""Puerto de persistencia de las campanas de WhatsMKT (T-WM-B4b1)."""

from typing import Protocol

from app.core.entities.whatsmkt_campana import ArchivoGuardado, LoteCreado, LoteNuevo


class RepositorioCampanasWhatsmktPort(Protocol):
    def crear_lote(self, lote: LoteNuevo) -> LoteCreado:
        """Guarda el lote COMPLETO en una sola transaccion: el lote, cada campana con su archivo,
        sus filas y sus exclusiones, y las exclusiones sin campana. Marca como usadas la version
        del texto y la de la definicion. Si algo falla no queda nada."""
        ...

    def obtener_archivo(self, campana_id: int) -> ArchivoGuardado | None:
        """Los bytes guardados al crear la campana, o None si no existe."""
        ...
