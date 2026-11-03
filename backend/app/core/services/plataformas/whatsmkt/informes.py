"""Importar el informe de WhatsMKT de una campana y conciliarlo (T-WM-B6; RF-WM-37 a RF-WM-39).

El archivo llega ya como bytes: `leer_tabla` (un adaptador, el lector de tablas comun) lo vuelve
`TablaLeida` y `leer_informe` lo entiende. El informe vigente de una campana es uno solo:
reemplazarlo pide confirmacion (`reemplazar`) y no guarda nada si no llega.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from app.core.entities.lectura_tabla import TablaLeida
from app.core.entities.whatsmkt_campana import (
    CampanaDescartada,
    CampanaNoEncontrada,
    CampanaWhatsmkt,
    InformeYaImportado,
)
from app.core.entities.whatsmkt_informe import (
    ConciliacionWhatsmkt,
    ReporteGuardado,
    ReporteNuevo,
)
from app.core.ports.repositorio_campanas_whatsmkt_port import RepositorioCampanasWhatsmktPort
from app.core.services.plataformas.whatsmkt.conciliacion import conciliar
from app.core.services.plataformas.whatsmkt.informe import leer_informe

LeerTabla = Callable[[bytes, str], TablaLeida]


@dataclass(frozen=True)
class EstadoInforme:
    """El informe vigente de una campana y su conciliacion; ambos nulos si esta pendiente."""

    reporte: ReporteGuardado | None
    conciliacion: ConciliacionWhatsmkt | None

    @property
    def pendiente(self) -> bool:
        return self.reporte is None


class InformesWhatsmktService:
    def __init__(self, campanas: RepositorioCampanasWhatsmktPort, leer_tabla: LeerTabla) -> None:
        self._campanas = campanas
        self._leer_tabla = leer_tabla

    def _campana(self, campana_id: int) -> CampanaWhatsmkt:
        campana = self._campanas.obtener(campana_id)
        if campana is None:
            raise CampanaNoEncontrada(campana_id)
        return campana

    def importar(
        self, campana_id: int, nombre_archivo: str, contenido: bytes, reemplazar: bool = False
    ) -> EstadoInforme:
        """Guarda el informe como el vigente de la campana y lo concilia.

        Lanza `CampanaNoEncontrada`, `CampanaDescartada` (hay que restaurarla primero),
        `ErrorWhatsmkt` (`informe_sin_encabezados` o `informe_sin_filas`: no se guarda nada) o
        `InformeYaImportado` si ya hay uno y no se pidio reemplazarlo.
        """
        campana = self._campana(campana_id)
        if campana.descartada_en is not None:
            raise CampanaDescartada(campana_id)
        informe = leer_informe(self._leer_tabla(contenido, nombre_archivo))
        if campana.con_informe and not reemplazar:
            raise InformeYaImportado(campana_id)
        reporte = self._campanas.reemplazar_reporte(
            campana_id,
            ReporteNuevo(nombre_archivo, hashlib.sha256(contenido).hexdigest(), informe),
        )
        return self._estado(campana_id, reporte)

    def estado(self, campana_id: int) -> EstadoInforme:
        """El informe vigente y su conciliacion, o pendiente si no hay."""
        self._campana(campana_id)
        reporte = self._campanas.obtener_reporte(campana_id)
        return EstadoInforme(None, None) if reporte is None else self._estado(campana_id, reporte)

    def _estado(self, campana_id: int, reporte: ReporteGuardado) -> EstadoInforme:
        cargadas = self._campanas.filas_cargadas(campana_id)
        return EstadoInforme(reporte, conciliar(cargadas, reporte.informe.numeros))
