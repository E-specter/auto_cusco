"""Entidades de la exportacion de una tabla a archivo (RF-13).

Una tabla ya generada (cabeceras y filas) se escribe en el formato que pida la
plataforma de destino: XLSX, CSV o JSON. Agregar un formato nuevo es agregar un
adaptador, sin tocar el nucleo (RF-14).

Es un modulo generico a proposito: lo usan las cargas digitales y VoIP, y mas
adelante tambien los reportes (RF-24).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class FormatoArchivo(StrEnum):
    """Formatos de archivo soportados (RF-13)."""

    XLSX = "xlsx"
    CSV = "csv"
    JSON = "json"


# Extension y tipo de contenido de cada formato, para nombrar y servir el archivo.
EXTENSIONES: dict[FormatoArchivo, str] = {
    FormatoArchivo.XLSX: "xlsx",
    FormatoArchivo.CSV: "csv",
    FormatoArchivo.JSON: "json",
}

TIPOS_MIME: dict[FormatoArchivo, str] = {
    FormatoArchivo.XLSX: ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    FormatoArchivo.CSV: "text/csv",
    FormatoArchivo.JSON: "application/json",
}


@dataclass(frozen=True)
class OpcionesArchivo:
    """Lo que cambia entre plataformas dentro de un mismo formato.

    Cada opcion la usa el formato al que pertenece; las demas la ignoran:

    - `delimitador` y `codificacion`: CSV (y `codificacion` tambien en JSON).
    - `con_cabeceras`: CSV y XLSX.
    - `hoja`: XLSX.
    - `sangria`: JSON; `None` deja el archivo en una sola linea.

    `codificacion` admite `utf-8-sig` para que Excel abra el CSV con las tildes
    correctas, y codificaciones heredadas como `latin-1` cuando la plataforma de
    destino no acepta UTF-8.
    """

    delimitador: str = ","
    codificacion: str = "utf-8"
    con_cabeceras: bool = True
    hoja: str = "Carga"
    sangria: int | None = None


OPCIONES_POR_DEFECTO = OpcionesArchivo()


@dataclass(frozen=True)
class Tabla:
    """Lo que se va a escribir: un nombre, unas cabeceras y sus filas.

    Las cabeceras mandan: definen el orden de las columnas y que claves de cada
    fila salen al archivo.
    """

    nombre: str
    cabeceras: tuple[str, ...]
    filas: tuple[Mapping[str, Any], ...]

    @property
    def cantidad(self) -> int:
        return len(self.filas)


@dataclass(frozen=True)
class ArchivoGenerado:
    """El archivo listo para descargar o guardar."""

    nombre: str
    contenido: bytes
    tipo_mime: str
    formato: FormatoArchivo

    @property
    def tamano(self) -> int:
        return len(self.contenido)


class ExportacionInvalida(Exception):
    """La tabla o las opciones no permiten producir el archivo."""


class FormatoNoSoportado(ExportacionInvalida):
    """Se pidio un formato que ningun adaptador sabe escribir."""

    def __init__(self, formato: Any, soportados: Sequence[str]) -> None:
        super().__init__(
            f"El formato {formato!r} no esta soportado; disponibles: {', '.join(soportados)}"
        )
        self.formato = formato
