"""Archivo de carga de MOWA MES en .xlsx (RF-MM-10), con la definicion `mowa_mes` (RF-MM-37).

Hoja `Hoja1` con `numero`, `mensaje` y `dni`. La forma del archivo (columnas, orden y tipos) sale de
`DEFINICION_MOWA_MES`, que se aplica a cada fila con `GeneradorCargas` y se escribe con el
exportador XLSX comun. El exportador escribe el entero como numero y el texto como texto, asi el
`dni` conserva sus ceros a la izquierda.

No pasa por `GeneracionCargasService` porque ese servicio lee la cartera; MOWA ya trae las filas
evaluadas (speech, exclusiones y supervision). Si la generacion falla o cambia la cantidad de filas,
se lanza `ArchivoCargaInvalido` SIN datos de las filas (ni telefono, ni dni, ni mensaje).
"""

from collections.abc import Sequence

from app.adapters.output.exportadores import exportador_xlsx
from app.core.entities.exportacion import OpcionesArchivo, Tabla
from app.core.entities.mowa_mes_campana import HOJA_CARGA, FilaCarga
from app.core.services.mapeo_campos.generador import GeneradorCargas
from app.core.services.plataformas.mowa_mes.plataforma import (
    DEFINICION_MOWA_MES,
    TIPOS_DE_LA_FILA,
)

_GENERADOR = GeneradorCargas(DEFINICION_MOWA_MES, TIPOS_DE_LA_FILA)
_OPCIONES = OpcionesArchivo(
    hoja=HOJA_CARGA,
    con_cabeceras=True,
    proteger_formulas=DEFINICION_MOWA_MES.proteger_formulas,
    columnas_texto=DEFINICION_MOWA_MES.columnas_texto,
)


class ArchivoCargaInvalido(Exception):
    """El generador no pudo armar el archivo. El mensaje dice donde, nunca con que datos."""


def escribir_archivo_carga(filas: Sequence[FilaCarga]) -> bytes:
    carga = _GENERADOR.generar(fila.celdas() for fila in filas)
    if carga.errores:
        primero = carga.errores[0]
        raise ArchivoCargaInvalido(
            f"No se pudo generar el archivo de carga: {len(carga.errores)} error(es); el primero "
            f"en la fila {primero.fila}, columna {primero.campo!r}, codigo {primero.codigo!r}"
        )
    if carga.exclusiones or len(carga.filas) != len(filas):
        raise ArchivoCargaInvalido(
            f"No se pudo generar el archivo de carga: el generador devolvio {len(carga.filas)} "
            f"filas de {len(filas)}"
        )
    tabla = Tabla(nombre=DEFINICION_MOWA_MES.nombre, cabeceras=carga.cabeceras, filas=carga.filas)
    return exportador_xlsx.exportar(tabla, _OPCIONES).contenido
