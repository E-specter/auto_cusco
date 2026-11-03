"""El archivo de contactos de WhatsMKT en `.xlsx`, con una sola hoja (RF-WM-16, S-WM-9).

Escribe con el exportador XLSX de siempre, asi lo que ya garantiza (los textos siempre como texto
literal, sin que una hoja de calculo los tome por formula, RF-53) vale tambien aqui. Lo propio de
WhatsMKT:

- la hoja se llama `Hoja1`, como el archivo del 29.10;
- `número` va SIEMPRE en celda de texto (formato `@`, RF-73), sin importar lo que diga la definicion
  guardada; las demas columnas de texto de la definicion que pidan `celda_texto` tambien;
- las macros son texto ya formateado: nunca una celda de fecha o de numero (RF-WM-11).

El nombre del archivo y su conservacion con la campana son de B4.
"""

from app.adapters.output.exportadores.exportador_xlsx import exportar
from app.core.entities.exportacion import ArchivoGenerado, OpcionesArchivo
from app.core.services.plataformas.whatsmkt.archivo_contactos import ArchivoContactos

HOJA = "Hoja1"


def exportar_contactos(archivo: ArchivoContactos) -> ArchivoGenerado:
    return exportar(
        archivo.tabla,
        OpcionesArchivo(hoja=HOJA, columnas_texto=archivo.columnas_texto),
    )
