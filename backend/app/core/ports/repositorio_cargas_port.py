"""Puerto de persistencia de versiones de sabana (docs/versionado-sabanas.md)."""

from collections.abc import Iterable
from contextlib import AbstractContextManager
from datetime import date
from typing import Any, Protocol

from app.core.entities.carga import (
    DatosCarga,
    EstadoCarga,
    EventoAuditoria,
    FilaParaGuardar,
    FormatoCarga,
    NuevaCarga,
    ResumenProcesamiento,
)
from app.core.entities.sabana import Incidencia


class SesionCargasPort(Protocol):
    """Operaciones dentro de una transaccion.

    Todo lo hecho en una sesion se confirma junto al salir sin error, o se
    revierte completo si ocurre cualquier excepcion.
    """

    def bloquear_fecha(self, fecha_corte: date) -> None:
        """Serializa las operaciones sobre una fecha (numero de version y vigencia)
        hasta el fin de la transaccion."""
        ...

    def siguiente_version(self, fecha_corte: date) -> int: ...

    def versiones_con_huella(self, fecha_corte: date, huella_archivo: str) -> list[int]: ...

    def crear_carga(self, nueva: NuevaCarga) -> DatosCarga: ...

    def guardar_archivo(self, carga_id: int, contenido: bytes) -> None: ...

    def obtener_carga(self, carga_id: int) -> DatosCarga | None: ...

    def tomar_para_procesar(self, carga_id: int) -> DatosCarga | None:
        """Pasa la version de en_cola a procesando. None si no estaba en cola."""
        ...

    def obtener_archivo(self, carga_id: int) -> bytes: ...

    def guardar_filas(self, carga_id: int, filas: Iterable[FilaParaGuardar]) -> int:
        """Guarda las filas consumiendo el iterable una sola vez. Devuelve cuantas guardo."""
        ...

    def guardar_incidencias(self, carga_id: int, incidencias: Iterable[Incidencia]) -> int: ...

    def finalizar_carga(
        self,
        carga_id: int,
        estado: EstadoCarga,
        resumen: ResumenProcesamiento,
        formato: FormatoCarga | None = None,
        motivo_fallo: str | None = None,
    ) -> None: ...

    def id_vigente(self, fecha_corte: date) -> int | None: ...

    def marcar_vigente(self, carga_id: int, vigente: bool) -> None: ...

    def auditar(
        self,
        carga: DatosCarga,
        evento: EventoAuditoria,
        filas_total: int | None = None,
        detalle: dict[str, Any] | None = None,
    ) -> None: ...


class RepositorioCargasPort(Protocol):
    def transaccion(self) -> AbstractContextManager[SesionCargasPort]:
        """Abre una transaccion: confirma al salir sin error, revierte si hay excepcion."""
        ...
