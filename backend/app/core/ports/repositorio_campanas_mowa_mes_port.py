"""Puerto de persistencia de las campanas de MOWA MES y de sus reportes de enviados."""

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Protocol

from app.core.entities.mowa_mes import CodigoMowaMes
from app.core.entities.mowa_mes_campana import (
    ArchivoCarga,
    CampanaArmada,
    CampanaRegistrada,
    Exclusion,
    FilaCarga,
)
from app.core.entities.mowa_mes_reporte import FilaReporte, ReporteImportado


class RepositorioCampanasMowaMesPort(Protocol):
    def cargados_en_mes(self, mes: date) -> int:
        """Filas cargadas (productos y supervision) de las campanas imputadas a ese mes."""
        ...

    def crear(self, armada: CampanaArmada, archivos: Sequence[ArchivoCarga]) -> CampanaRegistrada:
        """Guarda la campana, sus archivos, filas y exclusiones en una sola transaccion.

        En esa misma transaccion bloquea la version de speech, comprueba que su
        huella siga siendo `armada.speech_huella` (si no, SpeechCambiado) y la
        marca como usada.
        """
        ...

    def listar(self, limite: int, desplazamiento: int) -> tuple[int, list[CampanaRegistrada]]:
        """Las mas recientes primero."""
        ...

    def obtener(self, campana_id: int) -> CampanaRegistrada | None: ...

    def exclusiones(
        self,
        campana_id: int,
        codigo: CodigoMowaMes | None,
        limite: int,
        desplazamiento: int,
    ) -> tuple[int, list[Exclusion]]: ...

    def archivo(self, campana_id: int, numero: int) -> ArchivoCarga | None: ...

    def filas_cargadas(self, campana_id: int) -> list[FilaCarga]:
        """En el orden en que se cargaron, supervision incluida."""
        ...

    # --- Reporte de enviados ------------------------------------------

    def reportes_ya_importados(self, mes_ids: Sequence[int]) -> tuple[int, ...]:
        """Cuales de esos id de MES ya estan importados, en cualquier campana."""
        ...

    def guardar_reportes(
        self,
        campana_id: int,
        nombre_archivo: str,
        filas_por_id: Mapping[int, Sequence[FilaReporte]],
    ) -> None:
        """Reemplaza cada id que ya existiera y guarda los nuevos, en una transaccion."""
        ...

    def reportes(self, campana_id: int) -> list[ReporteImportado]: ...

    def filas_reporte(self, campana_id: int) -> list[FilaReporte]: ...
