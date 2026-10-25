"""Entidades del mapeador de encabezados (RF-57 a RF-63, docs/mapeador-encabezados.md).

El mapeador relaciona las columnas de un archivo tabular con los campos de un catalogo, y no sabe
nada de la sabana: recibe un `CatalogoCampos` y una tabla leida y devuelve un `AnalisisEncabezados`.
Cada modulo aporta su catalogo. Este modulo no importa `entities/sabana.py`: el tipo de un campo es
un texto descriptivo, porque el mapeador no convierte valores (M-8).
"""

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class CampoDestino:
    """Un campo del catalogo.

    `alias` son expresiones regulares sobre el encabezado normalizado (`fullmatch`).
    `clave_etiqueta` es la clave i18n del nombre legible (`campo.<nombre>`). `tipo` es solo
    descriptivo.
    """

    nombre: str
    clave_etiqueta: str
    tipo: str
    obligatorio: bool
    alias: tuple[str, ...]


@dataclass(frozen=True)
class CatalogoCampos:
    """Los campos de un destino, en orden. `id` es estable (`sabana_vencida`): es la clave de los
    mapeos recordados (RF-63)."""

    id: str
    campos: tuple[CampoDestino, ...]


class EstadoEncabezado(StrEnum):
    RECORDADO = "recordado"
    COINCIDE = "coincide"
    PARECIDO = "parecido"
    SIN_COINCIDENCIA = "sin_coincidencia"


class OrigenAsignacion(StrEnum):
    """De donde sale la asignacion de una columna (RF-62)."""

    RECORDADO = "recordado"
    COINCIDE = "coincide"
    PARECIDO_ACEPTADO = "parecido_aceptado"
    MANUAL = "manual"


class CodigoMapeo(StrEnum):
    """Los problemas de una asignacion (RF-60)."""

    PARECIDO_SIN_REVISAR = "parecido_sin_revisar"  # un parecido que nadie acepto ni cambio
    OBLIGATORIO_SIN_COLUMNA = "obligatorio_sin_columna"  # ninguna columna para un campo obligatorio
    CAMPO_REPETIDO = "campo_repetido"  # dos columnas con el mismo campo; uno por columna
    CAMPO_DESCONOCIDO = "campo_desconocido"  # el campo no esta en el catalogo
    INDICE_FUERA_DE_RANGO = "indice_fuera_de_rango"  # la columna no esta entre las listadas
    ASIGNACION_FALTANTE = "asignacion_faltante"  # una columna listada sin asignacion
    INDICE_REPETIDO = "indice_repetido"  # dos asignaciones para la misma columna


@dataclass(frozen=True)
class ColumnaAnalizada:
    """Una columna del archivo con lo que el mapeador sugiere para ella.

    `indice` va en base 0 y es la posicion en el archivo (los encabezados vacios no se listan, pero
    el indice se conserva). `ocurrencia` cuenta desde 1 entre los encabezados con el mismo
    normalizado, de izquierda a derecha. `sugerido` es un campo o `None` («No cargar»). `similitud`
    solo la tiene un `parecido`.
    """

    indice: int
    encabezado: str
    normalizado: str
    ocurrencia: int
    ejemplos: tuple[str, ...]
    estado: EstadoEncabezado
    sugerido: str | None
    similitud: float | None = None


@dataclass(frozen=True)
class Asignacion:
    """Lo que se hace con una columna: `campo = None` es «No cargar esta columna»."""

    indice: int
    campo: str | None
    origen: OrigenAsignacion


@dataclass(frozen=True)
class ProblemaMapeo:
    """`indice` es de la columna del problema; `None` si es de todo el mapeo (un obligatorio)."""

    indice: int | None
    codigo: CodigoMapeo
    detalle: str
    campo: str | None = None


@dataclass(frozen=True)
class AnalisisEncabezados:
    """Lo que se le muestra al usuario. `campos` son los del catalogo con el que se analizo, para
    validar despues contra este mismo analisis (M-4)."""

    catalogo_id: str
    columnas: tuple[ColumnaAnalizada, ...]
    campos: tuple[CampoDestino, ...]
    problemas_iniciales: tuple[ProblemaMapeo, ...]
