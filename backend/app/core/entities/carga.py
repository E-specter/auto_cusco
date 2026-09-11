"""Entidades del versionado de sabanas por fecha de corte.

Diseno y reglas V-1 a V-10 en docs/versionado-sabanas.md.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any


class EstadoCarga(StrEnum):
    """Estado de procesamiento de una version (la ingesta corre en segundo plano)."""

    EN_COLA = "en_cola"
    PROCESANDO = "procesando"
    TERMINADA = "terminada"  # unica que puede ser vigente (V-5)
    FALLIDA = "fallida"


class EventoAuditoria(StrEnum):
    """Eventos que se registran sin datos de la sabana (V-8).

    Por ahora sin usuario: la app aun no tiene autenticacion (decision C-3).
    """

    CARGA_CREADA = "carga_creada"
    PROCESAMIENTO_TERMINADO = "procesamiento_terminado"
    PROCESAMIENTO_FALLIDO = "procesamiento_fallido"
    VIGENTE_ASIGNADA = "vigente_asignada"
    VIGENTE_RETIRADA = "vigente_retirada"
    CARGA_ELIMINADA = "carga_eliminada"


# Decision C-1: al procesar una nueva version de una fecha que ya tiene vigente,
# la opcion preseleccionada es mantener la vigente actual.
REEMPLAZAR_VIGENTE_POR_DEFECTO = False


class CargaError(Exception):
    """Operacion de versionado no permitida."""


class CargaNoEncontrada(CargaError):
    def __init__(self, carga_id: int) -> None:
        super().__init__(f"No existe la carga {carga_id}")
        self.carga_id = carga_id


class CargaNoProcesable(CargaError):
    """La version no esta en cola: ya se proceso, se esta procesando o fallo."""


class VigenciaNoPermitida(CargaError):
    """Solo una version terminada puede ser vigente (V-5)."""


@dataclass(frozen=True)
class NuevaCarga:
    fecha_corte: date
    version: int
    nombre_archivo: str
    huella_archivo: str  # SHA-256 hex del archivo (V-6)
    tamano_bytes: int
    hoja: str


@dataclass(frozen=True)
class DatosCarga:
    """Datos de una version sin su contenido (filas, archivo, incidencias)."""

    id: int
    fecha_corte: date
    version: int
    estado: EstadoCarga
    vigente: bool
    nombre_archivo: str
    huella_archivo: str
    hoja: str


@dataclass(frozen=True)
class FilaParaGuardar:
    """Fila normalizada lista para persistir.

    `valores` usa los nombres de columna de la tabla de filas; `extras` guarda
    las columnas del archivo que no estan en el catalogo (normalmente None).
    """

    numero_fila: int
    valores: dict[str, Any]
    extras: dict[str, Any] | None = None


@dataclass(frozen=True)
class FormatoCarga:
    """Trazabilidad del formato del archivo (V-9)."""

    fila_cabecera: int
    cabeceras_originales: list[str]
    huella_formato: str
    mapeo: dict[str, Any]


@dataclass
class ResumenProcesamiento:
    filas_total: int = 0
    filas_ingestadas: int = 0
    incidencias_error: int = 0
    incidencias_advertencia: int = 0
    incidencias_info: int = 0


@dataclass(frozen=True)
class CargaRegistrada:
    carga: DatosCarga
    # V-6: otras versiones de la misma fecha con un archivo identico.
    versiones_identicas: list[int]


@dataclass(frozen=True)
class ResultadoProcesamiento:
    carga_id: int
    estado: EstadoCarga
    vigente: bool
    resumen: ResumenProcesamiento
    motivo_fallo: str | None = None
    # Version que era vigente para la fecha al terminar de procesar (None si no habia).
    id_vigente_actual: int | None = None

    @property
    def requiere_confirmacion(self) -> bool:
        """V-4: la fecha ya tenia otra vigente, asi que hay que preguntar al usuario."""
        return (
            self.estado is EstadoCarga.TERMINADA
            and not self.vigente
            and self.id_vigente_actual is not None
        )
