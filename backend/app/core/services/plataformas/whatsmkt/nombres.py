"""El nombre de la campana y el de su archivo (RF-WM-33, DU-WM-6, DU-WM-10), reglas puras.

El nombre sale de una plantilla de texto fijo con `{fecha_corte}` (AAAA.MM.DD) y `{segmento}` (la
etiqueta del segmento; vacio en una campana global). Tiene hasta 75 caracteres. Si el lote tiene
mas de una campana y la plantilla no usa `{segmento}`, se agrega ` {segmento}` al final para que
los nombres no se repitan. El archivo se llama como la campana mas `.xlsx`, con los caracteres que
Windows no admite cambiados por `_`.
"""

import re
from datetime import date

from app.core.entities.whatsmkt import CodigoWhatsmkt, ErrorWhatsmkt

LARGO_MAXIMO_NOMBRE = 75
EXTENSION = ".xlsx"
_PARENTESIS_VACIOS = re.compile(r"\(\s*\)")
# Lo que Windows no admite en un nombre de archivo, y los caracteres de control.
_NO_ADMITIDOS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def nombre_de_campana(
    plantilla: str, fecha_corte: date, etiqueta_segmento: str | None, varias: bool
) -> str:
    """El nombre propuesto. Sin segmento (campana global) los parentesis que quedan vacios se
    quitan; los espacios de mas se compactan."""
    if varias and "{segmento}" not in plantilla:
        plantilla = f"{plantilla} {{segmento}}"
    texto = plantilla.replace("{fecha_corte}", fecha_corte.strftime("%Y.%m.%d"))
    texto = texto.replace("{segmento}", etiqueta_segmento or "")
    if not etiqueta_segmento:
        texto = _PARENTESIS_VACIOS.sub("", texto)
    return " ".join(texto.split())


def validar_nombre(nombre: str) -> str:
    """El nombre sin espacios de mas, o `nombre_largo` si pasa de 75 caracteres (RF-WM-33)."""
    limpio = " ".join(nombre.split())
    if len(limpio) > LARGO_MAXIMO_NOMBRE:
        raise ErrorWhatsmkt(
            CodigoWhatsmkt.NOMBRE_LARGO,
            f"El nombre tiene {len(limpio)} caracteres: el maximo es {LARGO_MAXIMO_NOMBRE}",
            largo=len(limpio),
        )
    return limpio


def nombre_del_archivo(nombre_de_la_campana: str) -> str:
    """El nombre del archivo: el de la campana mas `.xlsx`, sin los caracteres que Windows no
    admite ni espacios ni puntos al final del nombre."""
    base = _NO_ADMITIDOS.sub("_", nombre_de_la_campana).strip(" .") or "campana"
    return base + EXTENSION
