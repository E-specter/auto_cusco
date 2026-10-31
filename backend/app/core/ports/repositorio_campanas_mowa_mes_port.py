"""Puerto de persistencia de las campanas de MOWA MES y de sus reportes de enviados."""

from collections.abc import Callable, Mapping, Sequence
from datetime import date
from typing import Protocol

from app.core.entities.mowa_mes import CodigoMowaMes
from app.core.entities.mowa_mes_campana import (
    ArchivoCarga,
    CampanaArmada,
    CampanaRegistrada,
    CampanasDescartadas,
    Exclusion,
    FilaCarga,
    PaginaCampanas,
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
    # Solo las campanas ACTIVAS cuentan: `cargados_en_mes`, `costo_del_mes` y `listar` dejan
    # fuera las descartadas (RF-MM-31), con una sola regla en cada implementacion.

    def cargados_en_mes(self, mes: date) -> int:
        """Filas cargadas (productos y supervision) de las campanas activas imputadas a ese mes."""
        ...

    def costo_del_mes(self, mes: date) -> CostoMes:
        """Suma del costo estimado guardado de las campanas activas imputadas a ese mes, sin las
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

    def listar(self, limite: int, desplazamiento: int) -> PaginaCampanas:
        """Las activas, las mas recientes primero, con el total y cuantas estan pendientes de
        reporte (RF-MM-33): ambos de TODAS las activas, no solo de la pagina."""
        ...

    # --- Descartar, restaurar y eliminar (RF-MM-31, RF-MM-32) ---------------

    def descartar(self, campana_id: int) -> None:
        """Marca la campana como descartada ahora; si ya lo estaba, no cambia la fecha."""
        ...

    def restaurar(self, campana_id: int) -> None:
        """La devuelve a las activas; si ya lo estaba, no hace nada."""
        ...

    def eliminar(self, campana_id: int) -> bool:
        """Borra una campana DESCARTADA con todo lo suyo (archivos, filas, exclusiones y
        reportes). Devuelve False, sin borrar nada, si no existe o no esta descartada."""
        ...

    def listar_descartadas(self, mes: date | None) -> CampanasDescartadas:
        """Las descartadas imputadas a ese mes (todas si es None), las mas recientes primero,
        con los meses que tienen descartadas y cuantas hay en total."""
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
