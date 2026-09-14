"""Archivo de carga de MOWA MES en .xlsx (RF-MM-10), sobre el exportador XLSX existente.

Hoja `Hoja1` con `numero`, `mensaje` y `dni`. El exportador escribe el entero
como numero y el texto como texto, asi el `dni` conserva sus ceros a la izquierda.
"""

from collections.abc import Sequence

from app.adapters.output.exportadores import exportador_xlsx
from app.core.entities.exportacion import OpcionesArchivo, Tabla
from app.core.entities.mowa_mes_campana import CABECERAS_CARGA, HOJA_CARGA, FilaCarga

_OPCIONES = OpcionesArchivo(hoja=HOJA_CARGA, con_cabeceras=True)


def escribir_archivo_carga(filas: Sequence[FilaCarga]) -> bytes:
    tabla = Tabla(
        nombre="mowa_mes", cabeceras=CABECERAS_CARGA, filas=tuple(f.celdas() for f in filas)
    )
    return exportador_xlsx.exportar(tabla, _OPCIONES).contenido
