"""Puerto de persistencia de las campanas de MOWA MES y de sus reportes de enviados."""

from collections.abc import Callable, Mapping, Sequence
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
from app.core.entities.mowa_mes_costo import CostoMes
from app.core.entities.mowa_mes_reporte import FilaReporte, ReporteImportado

# Dado el id de la campana recien insertada, el nombre de cada archivo en orden. El nombre
# lleva `{campana}`, que solo existe una vez guardada la campana.
NombradorDeArchivos = Callable[[int], Sequence[str]]

# Dadas las filas cargadas de una campana y las de sus reportes, los enviados (E-1) de la
# conciliacion. El nucleo pone la regla; el repositorio la aplica dentro de su transaccion.
ContadorDeEnviados = Callable[[Sequence[FilaCarga], Sequence[FilaReporte]], int]


class RepositorioCampanasMowaMesPort(Protocol):
    def cargados_en_mes(self, mes: date) -> int:
        """Filas cargadas (productos y supervision) de las campanas imputadas a ese mes."""
        ...

    def costo_del_mes(self, mes: date) -> CostoMes:
        """Suma del costo estimado guardado de las campanas imputadas a ese mes, sin las
        que no tienen tarifa, y cuantas fueron."""
        ...

    def crear(
        self,
        armada: CampanaArmada,
        archivos: Sequence[ArchivoCarga],
        nombrar: NombradorDeArchivos,
    ) -> CampanaRegistrada:
        """Guarda la campana, sus archivos, filas y exclusiones en una sola transaccion.

        En esa misma transaccion bloquea la version de speech, comprueba que su
        huella siga siendo `armada.speech_huella` (si no, SpeechCambiado) y la
        marca como usada. Congela `armada.tarifa_sms` y el costo estimado con la
        campana, y guarda con cada archivo el nombre que devuelve `nombrar`.
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
        contar_enviados: ContadorDeEnviados,
    ) -> None:
        """Reemplaza cada id que ya existiera y guarda los nuevos, en una transaccion.

        En esa misma transaccion recalcula `enviados_conciliados` con `contar_enviados`
        de la campana elegida y de cada campana a la que se le quito un id de MES por
        el reemplazo: si algo falla, ninguno queda a medio actualizar.
        """
        ...

    def reportes(self, campana_id: int) -> list[ReporteImportado]: ...

    def filas_reporte(self, campana_id: int) -> list[FilaReporte]: ...
