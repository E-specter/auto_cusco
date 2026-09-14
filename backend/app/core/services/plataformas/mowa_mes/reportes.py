"""Caso de uso: importar el reporte de enviados y conciliarlo (RF-MM-20 a RF-MM-22).

El usuario elige la campana y sube el archivo; el `id` de MES se lee del
archivo. Si trae varios, cada uno se asocia a la campana elegida (C-5). Un `id`
ya importado solo se reemplaza con confirmacion.
"""

from collections import defaultdict
from dataclasses import dataclass

from app.core.entities.mowa_mes_campana import CampanaNoEncontrada
from app.core.entities.mowa_mes_reporte import (
    Conciliacion,
    FilaReporte,
    ReporteImportado,
    ReporteYaImportado,
)
from app.core.ports.lector_reporte_port import LectorReportePort
from app.core.ports.repositorio_campanas_mowa_mes_port import RepositorioCampanasMowaMesPort
from app.core.services.plataformas.mowa_mes.conciliacion import conciliar


@dataclass(frozen=True)
class EstadoConciliacion:
    reportes: tuple[ReporteImportado, ...]
    conciliacion: Conciliacion


class ReportesMowaMesService:
    def __init__(self, campanas: RepositorioCampanasMowaMesPort, lector: LectorReportePort) -> None:
        self._campanas = campanas
        self._lector = lector

    def importar(
        self, campana_id: int, nombre_archivo: str, contenido: bytes, reemplazar: bool = False
    ) -> EstadoConciliacion:
        self._existe(campana_id)
        filas = self._lector.leer(contenido)
        por_id: dict[int, list[FilaReporte]] = defaultdict(list)
        for fila in filas:
            por_id[fila.mes_id].append(fila)
        existentes = self._campanas.reportes_ya_importados(tuple(sorted(por_id)))
        if existentes and not reemplazar:
            raise ReporteYaImportado(tuple(existentes))
        self._campanas.guardar_reportes(campana_id, nombre_archivo, por_id)
        return self.conciliacion(campana_id)

    def conciliacion(self, campana_id: int) -> EstadoConciliacion:
        self._existe(campana_id)
        return EstadoConciliacion(
            reportes=tuple(self._campanas.reportes(campana_id)),
            conciliacion=conciliar(
                self._campanas.filas_cargadas(campana_id),
                self._campanas.filas_reporte(campana_id),
            ),
        )

    def _existe(self, campana_id: int) -> None:
        if self._campanas.obtener(campana_id) is None:
            raise CampanaNoEncontrada(campana_id)
