"""Campos adicionales de la cartera (RF-64 a RF-66): los que crea el usuario desde el mapeo.

Un campo adicional es un campo de la cartera que no viene en el catalogo base de la sabana. Se
referencia SIEMPRE por su nombre tecnico (`ad_...`), estable y nunca reutilizado; el nombre legible
se puede cambiar. El tipo es fijo (supuesto de RF-65) y archivar no borra ningun dato.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.core.entities.mapeador import CampoDestino


class TipoAdicional(StrEnum):
    TEXTO = "texto"
    NUMERO = "numero"
    FECHA = "fecha"


@dataclass(frozen=True)
class CampoAdicional:
    """Una definicion de campo adicional.

    `encabezado_origen` es el encabezado de la sabana, ya normalizado: es su alias literal en el
    mapeador. `archivado`: deja de ofrecerse en las listas pero se sigue resolviendo para leer.
    """

    nombre: str
    nombre_legible: str
    tipo: TipoAdicional
    encabezado_origen: str
    archivado: bool = False


class NombreDeCampoRepetido(Exception):
    """El nombre legible ya lo tiene, o lo cumple, otro campo (base o adicional, archivado o no).

    `campo` es el que choca: la pantalla lo muestra para que el usuario lo use en lugar de crear
    otro.
    """

    def __init__(self, nombre_legible: str, campo: CampoDestino) -> None:
        super().__init__(f"El nombre {nombre_legible!r} ya lo tiene el campo {campo.nombre!r}")
        self.campo = campo


class CampoAdicionalNoEncontrado(Exception):
    def __init__(self, nombre: str) -> None:
        super().__init__(f"No existe el campo adicional {nombre!r}")
        self.nombre = nombre


class ColumnaInexistente(Exception):
    """El indice no es una columna del analisis del borrador."""

    def __init__(self, indice: int) -> None:
        super().__init__(f"El analisis no tiene la columna {indice}")
        self.indice = indice
