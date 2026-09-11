"""Entidades de la ingesta de sabanas (RF-01, RF-02).

Tipos puros, sin infraestructura. El esquema de referencia esta en
docs/sabana-schema.md.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

HOJA_DATOS_POR_DEFECTO = "VENCIDA"


class ArchivoSabanaError(Exception):
    """Error al leer el archivo de una sabana (no es un error de un dato puntual)."""


class ArchivoIlegible(ArchivoSabanaError):
    """El contenido no es una hoja de calculo legible (corrupto, otro formato, etc.)."""


class HojaNoEncontrada(ArchivoSabanaError):
    def __init__(self, hoja: str, disponibles: list[str]) -> None:
        super().__init__(f"No existe la hoja {hoja!r}; hojas disponibles: {disponibles}")
        self.hoja = hoja
        self.disponibles = disponibles


class HojaVacia(ArchivoSabanaError):
    """La hoja existe pero no tiene cabecera ni datos."""


@dataclass(frozen=True)
class FilaCruda:
    """Fila tal como la entrega el lector. `numero_fila` es la fila en la hoja (base 1)."""

    numero_fila: int
    celdas: list[Any]


@dataclass
class HojaSabana:
    """Contenido crudo de la hoja de datos: cabecera y filas no vacias."""

    nombre: str
    fila_cabecera: int
    cabeceras: list[Any]
    filas: list[FilaCruda]


class Severidad(StrEnum):
    """Gravedad de una incidencia detectada al normalizar."""

    ERROR = "error"  # dato clave invalido o columna requerida ausente
    ADVERTENCIA = "advertencia"  # dato invalido que no impide ingestar el producto
    INFO = "info"  # correccion automatica prevista por las reglas (p. ej. DNI completado)


class TipoDocumento(StrEnum):
    DNI = "dni"
    RUC = "ruc"
    EXTRANJERO = "extranjero"


@dataclass(frozen=True)
class Documento:
    tipo: TipoDocumento
    numero: str


@dataclass(frozen=True)
class Aviso:
    """Resultado no exitoso (o corregido) de aplicar una regla a un valor."""

    codigo: str
    severidad: Severidad
    detalle: str


@dataclass(frozen=True)
class Incidencia:
    """Aviso ubicado en el archivo: fila (None = nivel archivo) y columna.

    `valor_original` puede contener datos personales: mostrarlo solo al usuario
    en la interfaz, nunca escribirlo en logs.
    """

    fila: int | None
    columna: str | None
    codigo: str
    severidad: Severidad
    detalle: str
    valor_original: Any = None


class TipoCampo(StrEnum):
    """Tipo logico de una columna de la sabana (docs/sabana-schema.md, seccion 4)."""

    CLAVE = "clave"
    TEXTO = "texto"
    CATALOGO = "catalogo"
    DOCUMENTO = "documento"
    TELEFONO = "telefono"
    FINANCIERO = "financiero"
    ENTERO = "entero"
    FECHA = "fecha"
    BOOLEANO = "booleano"
    VENCIMIENTO_OPERATIVO = "vencimiento_operativo"
    SIN_VALOR = "sin_valor"  # se conserva solo en el registro crudo (N-9)


@dataclass(frozen=True)
class ColumnaSabana:
    """Definicion configurable de una columna esperada.

    `patrones` son expresiones regulares evaluadas con fullmatch sobre la
    cabecera normalizada (sin tildes, minusculas, espacios colapsados).
    """

    nombre: str
    tipo: TipoCampo
    patrones: tuple[str, ...]
    requerida: bool = False


@dataclass
class MapeoCabeceras:
    """Resultado de mapear las cabeceras de un archivo contra el catalogo (N-1)."""

    columnas: dict[int, ColumnaSabana]
    desconocidas: dict[int, str]
    faltantes: list[ColumnaSabana]
    incidencias: list[Incidencia] = field(default_factory=list)

    @property
    def bloqueante(self) -> bool:
        """True si el archivo no puede ingestarse (p. ej. falta la clave)."""
        return any(i.severidad is Severidad.ERROR for i in self.incidencias)


@dataclass
class FilaNormalizada:
    numero_fila: int
    valores: dict[str, Any]
    incidencias: list[Incidencia] = field(default_factory=list)

    @property
    def clave(self) -> str | None:
        return self.valores.get("pagare")

    @property
    def ingestable(self) -> bool:
        """Una fila sin pagare valido no puede registrarse como producto."""
        return self.clave is not None
