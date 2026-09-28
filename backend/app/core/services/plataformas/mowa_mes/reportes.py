"""Caso de uso: importar el reporte de enviados y conciliarlo (RF-MM-20 a RF-MM-22).

El usuario elige la campana y sube el archivo; el `id` de MES se lee del
archivo. Si trae varios, cada uno se asocia a la campana elegida (C-5). Un `id`
ya importado solo se reemplaza con confirmacion.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.core.entities.mowa_mes_campana import CampanaNoEncontrada, CampanaRegistrada, FilaCarga
from app.core.entities.mowa_mes_costo import CostoReal
from app.core.entities.mowa_mes_reporte import (
    Conciliacion,
    FilaReporte,
    ReporteImportado,
    ReporteYaImportado,
)
from app.core.ports.lector_reporte_port import LectorReportePort
from app.core.ports.repositorio_campanas_mowa_mes_port import RepositorioCampanasMowaMesPort
from app.core.services.plataformas.mowa_mes import costos
from app.core.services.plataformas.mowa_mes.conciliacion import conciliar


def enviados_de(cargadas: Sequence[FilaCarga], reportes: Sequence[FilaReporte]) -> int:
    """Los enviados de la conciliacion (E-1), supervision incluida.

    Es lo que el repositorio guarda como `enviados_conciliados` dentro de la transaccion
    que importa o reemplaza un reporte, con la misma funcion que arma las cifras de la
    conciliacion: no hay una segunda definicion de "enviado".
    """
    return conciliar(cargadas, reportes).total.enviados


@dataclass(frozen=True)
class EstadoConciliacion:
    reportes: tuple[ReporteImportado, ...]
    conciliacion: Conciliacion
    costo_real: CostoReal
    tarifa_sms: Decimal | None  # la congelada en la campana, la que multiplico


class ReportesMowaMesService:
    def __init__(self, campanas: RepositorioCampanasMowaMesPort, lector: LectorReportePort) -> None:
        self._campanas = campanas
        self._lector = lector

    def importar(
        self, campana_id: int, nombre_archivo: str, contenido: bytes, reemplazar: bool = False
    ) -> EstadoConciliacion:
        self._campana(campana_id)
        filas = self._lector.leer(contenido)
        por_id: dict[int, list[FilaReporte]] = defaultdict(list)
        for fila in filas:
            por_id[fila.mes_id].append(fila)
        existentes = self._campanas.reportes_ya_importados(tuple(sorted(por_id)))
        if existentes and not reemplazar:
            raise ReporteYaImportado(tuple(existentes))
        self._campanas.guardar_reportes(campana_id, nombre_archivo, por_id, enviados_de)
        return self.conciliacion(campana_id)

    def conciliacion(self, campana_id: int) -> EstadoConciliacion:
        campana = self._campana(campana_id)
        reportes = tuple(self._campanas.reportes(campana_id))
        cifras = conciliar(
            self._campanas.filas_cargadas(campana_id),
            self._campanas.filas_reporte(campana_id),
        )
        # El costo real no se guarda (D-3): sale de esta conciliacion, asi que un reporte
        # reemplazado lo recalcula solo. Enviados es el total de E-1, supervision incluida.
        return EstadoConciliacion(
            reportes=reportes,
            conciliacion=cifras,
            costo_real=costos.costo_real(campana.tarifa_sms, bool(reportes), cifras.total.enviados),
            tarifa_sms=campana.tarifa_sms,
        )

    def _campana(self, campana_id: int) -> CampanaRegistrada:
        campana = self._campanas.obtener(campana_id)
        if campana is None:
            raise CampanaNoEncontrada(campana_id)
        return campana
