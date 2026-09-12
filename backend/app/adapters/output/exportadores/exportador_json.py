"""Exportador a JSON (RF-13).

El archivo es una lista de objetos, uno por fila, con las claves en el orden de
las cabeceras. Un campo vacio sale como `null`, no como cadena vacia: en JSON
esa distincion si la entienden las plataformas.

Sobre los numeros: los enteros salen como enteros y los decimales como numero
JSON. Un numero JSON no conserva los ceros a la derecha, asi que un importe que
deba verse siempre con dos decimales corresponde declararlo `financiero` en la
definicion, que produce texto con el formato exacto (ver docs/mapeo-campos.md).
"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

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

FORMATO = FormatoArchivo.JSON


def exportar(tabla: Tabla, opciones: OpcionesArchivo = OPCIONES_POR_DEFECTO) -> ArchivoGenerado:
    filas = [
        {
            cabecera: _valor(valor)
            for cabecera, valor in zip(
                tabla.cabeceras, comunes.columnas(fila, tabla.cabeceras), strict=True
            )
        }
        for fila in tabla.filas
    ]
    texto = json.dumps(filas, ensure_ascii=False, indent=opciones.sangria)
    try:
        contenido = texto.encode(opciones.codificacion)
    except LookupError as exc:
        raise ExportacionInvalida(f"La codificacion {opciones.codificacion!r} no existe") from exc
    except UnicodeEncodeError as exc:
        raise ExportacionInvalida(
            f"El texto {exc.object[exc.start : exc.end]!r} no se puede escribir "
            f"en {opciones.codificacion!r}"
        ) from exc
    return ArchivoGenerado(
        nombre=comunes.nombre_de_archivo(tabla.nombre, FORMATO),
        contenido=contenido,
        tipo_mime=f"{TIPOS_MIME[FORMATO]}; charset={opciones.codificacion}",
        formato=FORMATO,
    )


def _valor(valor: Any) -> Any:
    """Lleva el valor a un tipo que JSON entienda, sin inventar datos."""
    if valor is None or isinstance(valor, (str, int, bool)):
        return valor
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor)
