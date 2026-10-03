"""Definiciones de columnas guardadas y versionadas (RF-51).

Una definicion es lo que arma el constructor de columnas: columnas con su contenido como
expresion, la segmentacion y `proteger_formulas`. Se guarda con un nombre unico, compartida entre
usuarios y modulos, y versionada: un cambio crea una version nueva y ninguna version se modifica
(la API no tiene como). `usada_en` marca la primera vez que una carga se genero con la version.

El contenido que se guarda es la forma JSON canonica del constructor, con la tabla de rangos y la
variable de dias resueltas: una definicion guardada no cambia porque cambie un valor por defecto.
El diseno esta en docs/motor-texto-enriquecido.md (secciones 8, 10 y 22).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

LARGO_MAXIMO_NOMBRE = 120
# Limites que la interfaz recibe en el catalogo para no ofrecer lo que se rechazaria (C-9).
MAXIMO_COLUMNAS = 100
MAXIMO_VARIANTES = 50


def normalizar_nombre(nombre: str) -> str:
    """Sin espacios en los extremos y en minusculas: la unicidad no distingue mayusculas."""
    return nombre.strip().casefold()


@dataclass(frozen=True)
class VersionDefinicion:
    """Una version: `contenido` es la forma JSON canonica, sin el nombre."""

    numero: int
    contenido: Mapping[str, Any]
    usada_en: datetime | None
    creado_en: datetime

    @property
    def usada(self) -> bool:
        return self.usada_en is not None


@dataclass(frozen=True)
class DefinicionGuardada:
    """La definicion con todas sus versiones, de la primera a la ultima (la vigente)."""

    id: int
    nombre: str
    creado_en: datetime
    actualizado_en: datetime
    versiones: tuple[VersionDefinicion, ...]

    @property
    def vigente(self) -> VersionDefinicion:
        return max(self.versiones, key=lambda version: version.numero)

    def version(self, numero: int | None) -> VersionDefinicion | None:
        """La version `numero`, o la vigente si no se pide una; None si no existe."""
        if numero is None:
            return self.vigente
        return next((v for v in self.versiones if v.numero == numero), None)


@dataclass(frozen=True)
class ResumenDefinicion:
    """Una fila del listado (C-7): sin el contenido de las versiones."""

    id: int
    nombre: str
    version_vigente: int
    cantidad_versiones: int
    actualizado_en: datetime
    vigente_usada: bool


class DefinicionNoEncontrada(Exception):
    def __init__(self, definicion_id: int) -> None:
        super().__init__(f"No existe la definicion {definicion_id}")
        self.definicion_id = definicion_id


class VersionNoEncontrada(Exception):
    def __init__(self, definicion_id: int, numero: int) -> None:
        super().__init__(f"La definicion {definicion_id} no tiene la version {numero}")
        self.definicion_id = definicion_id
        self.numero = numero


class NombreDeDefinicionRepetido(Exception):
    def __init__(self, nombre: str) -> None:
        super().__init__(f"Ya existe una definicion llamada {nombre!r}")
        self.nombre = nombre
