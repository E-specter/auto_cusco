"""Exportador a CSV (RF-13).

El delimitador y la codificacion son configurables porque es justo lo que
cambia entre plataformas: coma o punto y coma, UTF-8 o una codificacion
heredada como latin-1.
"""

import csv
import io

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

FORMATO = FormatoArchivo.CSV
FIN_DE_LINEA = "\r\n"  # RFC 4180; es lo que esperan las plataformas de Windows


def exportar(tabla: Tabla, opciones: OpcionesArchivo = OPCIONES_POR_DEFECTO) -> ArchivoGenerado:
    if len(opciones.delimitador) != 1:
        raise ExportacionInvalida(
            f"El delimitador del CSV debe ser un solo caracter, no {opciones.delimitador!r}"
        )
    buffer = io.StringIO(newline="")
    escritor = csv.writer(
        buffer,
        delimiter=opciones.delimitador,
        lineterminator=FIN_DE_LINEA,
        quoting=csv.QUOTE_MINIMAL,
    )
    if opciones.con_cabeceras:
        escritor.writerow(tabla.cabeceras)
    for fila in tabla.filas:
        escritor.writerow(
            comunes.a_texto(valor) for valor in comunes.columnas(fila, tabla.cabeceras)
        )
    return ArchivoGenerado(
        nombre=comunes.nombre_de_archivo(tabla.nombre, FORMATO),
        contenido=_codificar(buffer.getvalue(), opciones.codificacion),
        tipo_mime=f"{TIPOS_MIME[FORMATO]}; charset={opciones.codificacion}",
        formato=FORMATO,
    )


def _codificar(texto: str, codificacion: str) -> bytes:
    """Codifica sin sustituir nada: un caracter que no cabe es un error visible.

    Si la plataforma pide latin-1 y la cartera trae un caracter fuera de ese
    juego, es mejor saberlo aqui que entregar un archivo con datos cambiados.
    """
    try:
        return texto.encode(codificacion)
    except LookupError as exc:
        raise ExportacionInvalida(f"La codificacion {codificacion!r} no existe") from exc
    except UnicodeEncodeError as exc:
        raise ExportacionInvalida(
            f"El texto {exc.object[exc.start : exc.end]!r} no se puede escribir en {codificacion!r}"
        ) from exc
