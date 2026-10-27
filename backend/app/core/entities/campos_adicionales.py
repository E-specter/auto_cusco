"""Campos adicionales de la cartera (RF-64 a RF-66): los que crea el usuario desde el mapeo.

Un campo adicional es un campo de la cartera que no viene en el catalogo base de la sabana. Se
referencia SIEMPRE por su nombre tecnico (`ad_...`), estable y nunca reutilizado; el nombre legible
se puede cambiar. El tipo es fijo (supuesto de RF-65) y archivar no borra ningun dato.
"""

from dataclasses import dataclass
from enum import StrEnum


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
