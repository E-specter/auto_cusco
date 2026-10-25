"""Entidades de la lectura de archivos tabulares (Excel, ODS, CSV y JSON; RF-57).

Disenio: `docs/mapeador-encabezados.md` §4.

Un lector entrega una `TablaLeida`: la cabecera, las filas con datos y lo que detecto (formato,
hojas, separador, codificacion), para mostrarlo y poder cambiarlo. Los numeros de fila van en
base 1, como Excel. Se reusan `FilaCruda` y los errores de `entities/sabana.py` (`ArchivoIlegible`,
`HojaNoEncontrada`, `HojaVacia`): son lo que ya comparten la ingesta y los lectores.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from app.core.entities.sabana import FilaCruda


class FormatoTabla(StrEnum):
    XLSX = "xlsx"
    XLSB = "xlsb"
    XLS = "xls"
    ODS = "ods"
    CSV = "csv"
    JSON = "json"

    @property
    def es_hoja_de_calculo(self) -> bool:
        return self in HOJAS_DE_CALCULO


HOJAS_DE_CALCULO = frozenset(
    {FormatoTabla.XLSX, FormatoTabla.XLSB, FormatoTabla.XLS, FormatoTabla.ODS}
)


class CodigoAdvertenciaLectura(StrEnum):
    """Lo que un lector avisa de una fila sin impedir leerla."""

    VALOR_NO_ESCALAR = "valor_no_escalar"  # un objeto o una lista JSON, guardado como texto JSON


class OpcionDetectable(StrEnum):
    """Una opcion de lectura que se puede elegir y, si no, se detecta (los campos de
    `OpcionesLectura`)."""

    HOJA = "hoja"
    SEPARADOR = "separador"
    CODIFICACION = "codificacion"


@dataclass(frozen=True)
class OpcionesLectura:
    """Lo que el usuario elige; todo opcional, y lo que falte se detecta.

    `hoja` es de una hoja de calculo; `separador` (un caracter) y `codificacion` (el nombre de un
    codec de Python), de un CSV. Lo elegido gana a lo detectado.
    """

    hoja: str | None = None
    separador: str | None = None
    codificacion: str | None = None


@dataclass(frozen=True)
class AdvertenciaLectura:
    """Una advertencia de una fila (`numero_fila` en base 1) y de la columna (`columna`: el
    encabezado) que la causa."""

    numero_fila: int
    columna: str
    codigo: CodigoAdvertenciaLectura


@dataclass(frozen=True)
class TablaLeida:
    """La cabecera (la primera fila no vacia) y las filas con datos de un archivo.

    - `hojas` y `hoja`: las de una hoja de calculo (la elegida o la detectada); vacios en CSV y
      JSON.
    - `separador` y `codificacion`: lo usado en un CSV (`utf-8-sig` es UTF-8 con BOM); nulos en
      el resto.
    - `fila_cabecera`: la fila de los encabezados (base 1). En un JSON es la 1: los objetos son las
      filas 2 en adelante.
    - `cabeceras` y las celdas de `filas` sin las celdas vacias del final; una fila sin ningun valor
      no se incluye. Una celda de CSV es siempre texto; una de JSON conserva su tipo (numero,
      booleano o texto) y un valor objeto o lista va como texto JSON.
    """

    formato: FormatoTabla
    hojas: tuple[str, ...]
    hoja: str | None
    separador: str | None
    codificacion: str | None
    fila_cabecera: int
    cabeceras: list
    filas: list[FilaCruda]
    advertencias: tuple[AdvertenciaLectura, ...] = field(default=())
