"""Entidades del borrador de carga del mapeador de encabezados (RF-57 a RF-62, §5 del diseno).

Un borrador es el archivo subido y analizado, a la espera de que el usuario revise las columnas y
confirme. Se confirma por su identificador (no se sube dos veces) y vence a las 24 horas.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.core.entities.mapeador import ProblemaMapeo

VIGENCIA_DEL_BORRADOR = timedelta(hours=24)


class BorradorNoEncontrado(Exception):
    """El borrador no existe, venció o ya se confirmó o descartó."""

    def __init__(self, borrador_id: int) -> None:
        super().__init__(f"No existe el borrador {borrador_id}")
        self.borrador_id = borrador_id


class CatalogoDesconocido(Exception):
    def __init__(self, catalogo_id: str) -> None:
        super().__init__(f"No existe el catálogo de campos {catalogo_id!r}")
        self.catalogo_id = catalogo_id


class MapeoConProblemas(Exception):
    """Las asignaciones no se pueden confirmar: trae la lista de problemas (RF-60)."""

    def __init__(self, problemas: tuple[ProblemaMapeo, ...]) -> None:
        super().__init__(f"El mapeo tiene {len(problemas)} problema(s)")
        self.problemas = problemas


@dataclass(frozen=True)
class NuevoBorrador:
    catalogo_id: str
    nombre_archivo: str
    huella: str  # SHA-256 hex del archivo
    tamano_bytes: int
    opciones: dict[str, Any]  # lo usado al leer: formato, hoja, separador y codificacion
    analisis: dict[str, Any]  # el analisis que se mostro, serializado
    creado_en: datetime


@dataclass(frozen=True)
class DatosBorrador:
    """El borrador sin su contenido (el archivo se pide aparte)."""

    id: int
    catalogo_id: str
    nombre_archivo: str
    huella: str
    tamano_bytes: int
    opciones: dict[str, Any] = field(default_factory=dict)
    analisis: dict[str, Any] = field(default_factory=dict)
    creado_en: datetime | None = None

    def vence_en(self) -> datetime | None:
        return None if self.creado_en is None else self.creado_en + VIGENCIA_DEL_BORRADOR
