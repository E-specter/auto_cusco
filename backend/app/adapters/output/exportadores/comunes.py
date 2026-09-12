"""Piezas compartidas por los exportadores: nombres de archivo y valores.

Cada formato decide como escribe, pero todos parten de los mismos valores que
produce el motor de mapeo: texto, entero, Decimal, fecha o vacio.
"""

import re
import unicodedata
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.core.entities.exportacion import EXTENSIONES, FormatoArchivo

LARGO_MAXIMO_NOMBRE = 80
NOMBRE_POR_DEFECTO = "carga"

_PERMITIDOS = re.compile(r"[^A-Za-z0-9 ._-]+")
_ESPACIOS = re.compile(r"\s+")


def nombre_de_archivo(nombre: str, formato: FormatoArchivo) -> str:
    """Convierte el nombre de la definicion en un nombre de archivo seguro.

    Se queda en ASCII y sin separadores de ruta: el nombre lo escribe el usuario
    al definir la carga y termina en una cabecera HTTP y en el disco.
    """
    sin_tildes = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    limpio = _ESPACIOS.sub(" ", _PERMITIDOS.sub(" ", sin_tildes)).strip(" .")
    base = (limpio[:LARGO_MAXIMO_NOMBRE].strip(" .") or NOMBRE_POR_DEFECTO).replace(" ", "_")
    return f"{base}.{EXTENSIONES[formato]}"


def columnas(fila: Mapping[str, Any], cabeceras: tuple[str, ...]) -> list[Any]:
    """Valores de una fila en el orden de las cabeceras; lo que falta queda vacio."""
    return [fila.get(cabecera) for cabecera in cabeceras]


def a_texto(valor: Any) -> str:
    """Representacion textual estable de un valor, para los formatos de texto.

    Las fechas salen en ISO 8601, los importes con sus digitos exactos y los
    booleanos como 1 o 0, que es lo que aceptan las plataformas. Un valor vacio
    es cadena vacia, nunca "None" ni un cero inventado.
    """
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        return valor.date().isoformat() if _sin_hora(valor) else valor.isoformat(sep=" ")
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, bool):
        return "1" if valor else "0"
    return str(valor)


def _sin_hora(valor: datetime) -> bool:
    return (valor.hour, valor.minute, valor.second, valor.microsecond) == (0, 0, 0, 0)
