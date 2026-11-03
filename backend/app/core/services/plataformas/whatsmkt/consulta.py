"""Leer las campanas de WhatsMKT: la lista y el detalle (T-WM-B4b1, parte 3; RF-WM-36 y 40)."""

from dataclasses import dataclass
from datetime import date

from app.core.entities.whatsmkt import ModoCampana
from app.core.entities.whatsmkt_campana import (
    CampanaNoEncontrada,
    CampanaWhatsmkt,
    EstadoCampana,
    PaginaCampanas,
    PaginaExclusiones,
)
from app.core.ports.repositorio_campanas_whatsmkt_port import RepositorioCampanasWhatsmktPort
from app.core.ports.repositorio_whatsmkt_port import RepositorioWhatsmktPort
from app.core.services.plataformas.whatsmkt.ficha import FichaCampana, ficha_de


@dataclass(frozen=True)
class Paginacion:
    limite: int
    desplazamiento: int


@dataclass(frozen=True)
class DetalleCampana:
    campana: CampanaWhatsmkt
    modo: ModoCampana
    ficha: FichaCampana
    exclusiones: PaginaExclusiones
    # Las del lote que no cayeron en ninguna campana: se ven desde cualquiera del lote. En un
    # lote global no hay (cero y vacia).
    exclusiones_fuera_del_lote: PaginaExclusiones


class ConsultaCampanasWhatsmktService:
    def __init__(
        self, campanas: RepositorioCampanasWhatsmktPort, whatsmkt: RepositorioWhatsmktPort
    ) -> None:
        self._campanas = campanas
        self._whatsmkt = whatsmkt

    def listar(
        self,
        paginacion: Paginacion,
        lote_id: int | None = None,
        mes: date | None = None,
        estado: EstadoCampana = EstadoCampana.ACTIVAS,
    ) -> PaginaCampanas:
        return self._campanas.listar(
            paginacion.limite, paginacion.desplazamiento, lote_id, mes, estado
        )

    def detalle(
        self, campana_id: int, exclusiones: Paginacion, fuera_del_lote: Paginacion
    ) -> DetalleCampana:
        campana = self._campanas.obtener(campana_id)
        if campana is None:
            raise CampanaNoEncontrada(campana_id)
        whatsapp = self._whatsmkt.obtener_configuracion().whatsapp_contacto
        return DetalleCampana(
            campana=campana,
            modo=self._campanas.modo_del_lote(campana.lote_id),
            ficha=ficha_de(campana, whatsapp),
            exclusiones=self._campanas.listar_exclusiones(
                campana.lote_id, campana.id, exclusiones.limite, exclusiones.desplazamiento
            ),
            exclusiones_fuera_del_lote=self._campanas.listar_exclusiones(
                campana.lote_id, None, fuera_del_lote.limite, fuera_del_lote.desplazamiento
            ),
        )
