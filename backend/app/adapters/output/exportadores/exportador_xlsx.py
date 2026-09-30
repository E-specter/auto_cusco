"""Exportador a XLSX (RF-13), con openpyxl en modo de escritura por filas.

El modo `write_only` escribe cada fila y la suelta, en vez de mantener el libro
entero en memoria: una carga de decenas de miles de productos no se guarda dos
veces.

Los tipos se respetan: un importe va como numero (openpyxl escribe Decimal sin
pasar por float), una fecha como fecha de Excel, y un texto como texto aunque
parezca un numero, que es lo que salva los ceros a la izquierda del pagare y
del documento.

Proteccion contra formulas (RF-53): un texto que empieza con `=` se escribe con el tipo de
texto explicito, igual que el resto de los textos (`inlineStr`), y no como formula. El
contenido no cambia nunca: sin apostrofo y sin `quotePrefix`. No es una opcion.
"""

import io
import re
from typing import Any

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.utils.exceptions import IllegalCharacterError

from app.adapters.output.exportadores import comunes
from app.core.entities.exportacion import (
    OPCIONES_POR_DEFECTO,
    TIPOS_MIME,
    ArchivoGenerado,
    ExportacionInvalida,
    FormatoArchivo,
    OpcionesArchivo,
    Tabla,
)

FORMATO = FormatoArchivo.XLSX
LARGO_MAXIMO_HOJA = 31  # limite de Excel
HOJA_POR_DEFECTO = "Carga"

_PROHIBIDOS_EN_HOJA = re.compile(r"[\\/*?:\[\]]")


def exportar(tabla: Tabla, opciones: OpcionesArchivo = OPCIONES_POR_DEFECTO) -> ArchivoGenerado:
    libro = Workbook(write_only=True)
    hoja = libro.create_sheet(title=nombre_de_hoja(opciones.hoja))
    buffer = io.BytesIO()
    try:
        if opciones.con_cabeceras:
            hoja.append([_celda(hoja, cabecera) for cabecera in tabla.cabeceras])
        for fila in tabla.filas:
            hoja.append([_celda(hoja, valor) for valor in comunes.columnas(fila, tabla.cabeceras)])
        libro.save(buffer)
    except IllegalCharacterError as exc:
        # Caracteres de control que Excel no puede guardar; se avisa en vez de
        # entregar un archivo con el dato alterado.
        raise ExportacionInvalida(
            "La carga tiene un caracter que Excel no admite en una celda"
        ) from exc
    return ArchivoGenerado(
        nombre=comunes.nombre_de_archivo(tabla.nombre, FORMATO),
        contenido=buffer.getvalue(),
        tipo_mime=TIPOS_MIME[FORMATO],
        formato=FORMATO,
    )


def _celda(hoja: Any, valor: Any) -> Any:
    """Un texto que empieza con `=` va como texto literal; todo lo demas, como siempre."""
    if isinstance(valor, str) and valor.startswith("="):
        celda = WriteOnlyCell(hoja, value=valor)
        celda.data_type = "s"  # sin esto openpyxl lo escribe como formula
        return celda
    return valor


def nombre_de_hoja(nombre: str) -> str:
    """Ajusta el nombre a lo que Excel acepta: sin `\\/*?:[]` y hasta 31 caracteres."""
    limpio = _PROHIBIDOS_EN_HOJA.sub(" ", nombre).strip()[:LARGO_MAXIMO_HOJA].strip()
    return limpio or HOJA_POR_DEFECTO
