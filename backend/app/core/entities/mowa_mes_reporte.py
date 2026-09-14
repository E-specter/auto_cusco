"""Reporte de enviados de MES y conciliacion con lo cargado (RF-MM-02, RF-MM-20 a RF-MM-22)."""

from dataclasses import dataclass
from datetime import datetime

from app.core.entities.mowa_mes import CodigoMowaMes

# RF-MM-20, en este orden y con estos nombres (sin distinguir mayusculas ni tildes).
COLUMNAS_REPORTE = (
    "id",
    "celular",
    "mensaje",
    "fecha de envio",
    "dni",
    "estado",
    "salida",
    "usuario",
)


@dataclass(frozen=True)
class FilaReporte:
    """Una fila del reporte tal como la entrega MES; `fila` es el numero de fila de Excel."""

    fila: int
    mes_id: int
    celular: str
    mensaje: str
    fecha_envio: str
    dni: str
    estado: str
    salida: str
    usuario: str


@dataclass(frozen=True)
class ReporteImportado:
    mes_id: int
    nombre_archivo: str
    filas: int
    importado_en: datetime


@dataclass(frozen=True)
class CifrasGrupo:
    """Cargados y enviados de un grupo: productos, supervision o el total."""

    cargados: int
    enviados: int
    por_estado: dict[str, int]

    @property
    def no_enviados(self) -> int:
        return self.cargados - self.enviados


@dataclass(frozen=True)
class CifrasId:
    """Filas de un `id` de MES y cuantas encontraron su fila cargada (C-5)."""

    mes_id: int
    filas: int
    con_correspondencia: int


@dataclass(frozen=True)
class AdvertenciaReporte:
    codigo: CodigoMowaMes
    mes_id: int
    detalle: str


@dataclass(frozen=True)
class Conciliacion:
    productos: CifrasGrupo
    supervision: CifrasGrupo
    total: CifrasGrupo
    sin_correspondencia: int
    sin_correspondencia_por_estado: dict[str, int]
    por_id: tuple[CifrasId, ...]
    advertencias: tuple[AdvertenciaReporte, ...]


class ReporteInvalido(Exception):
    """El archivo no es un reporte de enviados que se pueda importar; el motivo va en el texto."""


class ReporteYaImportado(Exception):
    def __init__(self, mes_ids: tuple[int, ...]) -> None:
        ids = ", ".join(str(i) for i in mes_ids)
        super().__init__(
            f"Ya se importo el reporte de los id de MES {ids}; confirma para reemplazarlo"
        )
        self.mes_ids = mes_ids
