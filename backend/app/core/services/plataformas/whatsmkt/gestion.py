"""Descartar, restaurar y eliminar campanas de WhatsMKT (T-WM-B6; RF-WM-41 y RF-WM-42).

Las reglas de MOWA (RF-MM-31 y RF-MM-32): descartar y restaurar son logicos (`descartada_en`) y no
borran nada; solo una campana descartada se elimina del todo.
"""

from app.core.entities.whatsmkt_campana import (
    CampanaNoDescartada,
    CampanaNoEncontrada,
    CampanaWhatsmkt,
)
from app.core.ports.repositorio_campanas_whatsmkt_port import RepositorioCampanasWhatsmktPort


class GestionCampanasWhatsmktService:
    def __init__(self, campanas: RepositorioCampanasWhatsmktPort) -> None:
        self._campanas = campanas

    def descartar(self, campana_id: int) -> CampanaWhatsmkt:
        """La saca de las activas sin borrar nada. Descartar una ya descartada no cambia nada."""
        campana = self._campanas.descartar(campana_id)
        if campana is None:
            raise CampanaNoEncontrada(campana_id)
        return campana

    def restaurar(self, campana_id: int) -> CampanaWhatsmkt:
        campana = self._campanas.restaurar(campana_id)
        if campana is None:
            raise CampanaNoEncontrada(campana_id)
        return campana

    def eliminar(self, campana_id: int) -> None:
        """Borra del todo una campana DESCARTADA: su archivo, filas, exclusiones e informes, y el
        lote si era la ultima. No toca los adjuntos ni las versiones del mensaje."""
        campana = self._campanas.obtener(campana_id)
        if campana is None:
            raise CampanaNoEncontrada(campana_id)
        if campana.descartada_en is None:
            raise CampanaNoDescartada(campana_id)
        # El repositorio vuelve a comprobarlo al borrar: si la restauraron entre una cosa y otra,
        # no se borra nada.
        if not self._campanas.eliminar_descartada(campana_id):
            raise CampanaNoDescartada(campana_id)
