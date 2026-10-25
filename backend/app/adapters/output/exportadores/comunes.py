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
from urllib.parse import quote

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


def disposicion_de_descarga(nombre: str) -> str:
    """Cabecera `Content-Disposition` de un archivo cuyo nombre puede tener tildes o `ñ`.

    `filename` va en ASCII, con el mismo criterio de `nombre_de_archivo` (sin tildes y
    con `_` en lo que no es seguro), para los clientes que no leen `filename*`; este
    lleva el nombre exacto en UTF-8 (RFC 5987). El nombre ya viene saneado para el
    disco: aqui solo se prepara para viajar en una cabecera HTTP.
    """
    base, punto, extension = nombre.rpartition(".")
    if not punto:
        base, extension = nombre, ""
    sin_tildes = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    ascii_base = _PERMITIDOS.sub("_", sin_tildes).strip(" .") or "archivo"
    ascii_extension = _PERMITIDOS.sub("_", extension) if extension else ""
    nombre_ascii = f"{ascii_base}.{ascii_extension}" if ascii_extension else ascii_base
    return f"attachment; filename=\"{nombre_ascii}\"; filename*=UTF-8''{quote(nombre, safe='')}"


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


# RF-53: con lo que empieza un texto para que una hoja de calculo lo tome por formula.
INICIOS_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")
_DIGITOS = frozenset("0123456789")
_CARACTERES_DE_NUMERO = frozenset("0123456789.,")


def es_numero_con_signo(texto: str) -> bool:
    """`[+-]?` un digito y luego solo digitos, puntos y comas: `-1,234.56`, `+51900000001`, `3.5`.

    Un texto asi no es una formula y un apostrofo delante lo rompe en la plataforma. Equivale a
    la expresion regular `^[+-]?\\d[\\d.,]*$`, pero sin expresiones regulares, con digitos ASCII
    solamente (`\\d` acepta tambien digitos de otros alfabetos) y sin dejar pasar un salto de linea
    al final (`$` lo admite). Ambas diferencias son mas estrictas: protegen de mas, nunca de menos.
    """
    resto = texto[1:] if texto[:1] in ("+", "-") else texto
    return bool(resto) and resto[0] in _DIGITOS and all(c in _CARACTERES_DE_NUMERO for c in resto)


def parece_formula(texto: str) -> bool:
    """El texto empieza como una formula y no es solo un numero con signo (RF-53)."""
    return texto.startswith(INICIOS_DE_FORMULA) and not es_numero_con_signo(texto)


def texto_para_csv(valor: Any, proteger_formulas: bool = True) -> str:
    """Como `a_texto`, con un apostrofo delante de un TEXTO que parece formula (RF-53).

    Solo cuenta lo que en la tabla es `str`: un importe, un entero o una fecha no son formulas,
    aunque su representacion empiece con `-`.
    """
    texto = a_texto(valor)
    if proteger_formulas and isinstance(valor, str) and parece_formula(texto):
        return "'" + texto
    return texto


def _sin_hora(valor: datetime) -> bool:
    return (valor.hour, valor.minute, valor.second, valor.microsecond) == (0, 0, 0, 0)
