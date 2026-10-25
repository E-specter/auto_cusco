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

Saltos de linea: un salto dentro de un texto sale siempre como LF en la hoja, en Windows y en
Linux. En modo `write_only` openpyxl escribe cada hoja en un archivo temporal abierto en modo
texto, y en Windows ese modo cambia cada LF por CR LF. Se deshace al terminar, con la API publica
del zip y sin tocar nada de openpyxl (`_con_saltos_lf`).
"""

import io
import os
import re
import zipfile
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
_PARTES_DE_HOJA = re.compile(r"xl/worksheets/[^/]+\.xml")
# El salto que el modo texto del sistema agrega: LF en Linux, CR LF en Windows. Una constante para
# que las pruebas puedan simular el otro sistema.
_SALTO_DEL_SISTEMA = os.linesep.encode("ascii")


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
        contenido=_con_saltos_lf(buffer.getvalue()),
        tipo_mime=TIPOS_MIME[FORMATO],
        formato=FORMATO,
    )


def _con_saltos_lf(contenido: bytes) -> bytes:
    """El .xlsx con los saltos de linea de las hojas tal como los escribe Linux: solo LF.

    Es la inversa exacta de lo que agrega el sistema: un LF del valor sale como `_SALTO_DEL_SISTEMA`
    y un CR LF del valor, como CR CR LF, que vuelve a CR LF. En Linux no hay nada que deshacer y el
    archivo se devuelve tal cual. En Windows se descomprimen las hojas para buscar el salto y,
    si ninguna lo trae (lo normal: openpyxl no escribe saltos estructurales en la hoja, solo los de
    los datos), se devuelve el MISMO `contenido`, sin recomprimir nada. Solo si alguna lo trae se
    reescribe el zip; entonces solo cambian esas hojas y las demas partes conservan su contenido,
    su fecha y su compresion.
    """
    if _SALTO_DEL_SISTEMA == b"\n":
        return contenido
    with zipfile.ZipFile(io.BytesIO(contenido)) as origen:
        reescritas = {}
        for parte in origen.infolist():
            if _PARTES_DE_HOJA.fullmatch(parte.filename):
                datos = origen.read(parte)
                if _SALTO_DEL_SISTEMA in datos:
                    reescritas[parte.filename] = datos.replace(_SALTO_DEL_SISTEMA, b"\n")
        if not reescritas:
            return contenido
        salida = io.BytesIO()
        with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as destino:
            for parte in origen.infolist():
                datos = reescritas.get(parte.filename)
                if datos is None:
                    datos = origen.read(parte)
                destino.writestr(parte, datos, compress_type=parte.compress_type)
    return salida.getvalue()


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
