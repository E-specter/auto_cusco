"""Lector de sabanas basado en python-calamine (.xlsb, .xlsx, .xls, .ods).

Elegido tras medirlo contra pyxlsb sobre las sabanas reales: ~10 veces mas
rapido con resultados normalizados identicos (docs/architecture.md, "Medicion
de lectores de sabana").

Tipos que entrega: str, float, int, bool, date/datetime y "" para celdas
vacias. El normalizador del nucleo acepta todos ellos.
"""

import io
from typing import Any

from python_calamine import CalamineError, CalamineWorkbook

from app.core.entities.sabana import (
    HOJA_DATOS_POR_DEFECTO,
    ArchivoIlegible,
    FilaCruda,
    HojaNoEncontrada,
    HojaSabana,
    HojaVacia,
)
from app.core.ports.lector_sabana_port import LectorSabanaPort


def _vacia(celda: Any) -> bool:
    return celda is None or (isinstance(celda, str) and celda.strip() == "")


def _recortar(celdas: list[Any]) -> list[Any]:
    fin = len(celdas)
    while fin and _vacia(celdas[fin - 1]):
        fin -= 1
    return celdas[:fin]


class LectorCalamine(LectorSabanaPort):
    def leer_hoja(self, contenido: bytes, hoja: str = HOJA_DATOS_POR_DEFECTO) -> HojaSabana:
        try:
            libro = CalamineWorkbook.from_filelike(io.BytesIO(contenido))
        except CalamineError as exc:
            raise ArchivoIlegible("El archivo no es una hoja de calculo legible") from exc
        try:
            if hoja not in libro.sheet_names:
                raise HojaNoEncontrada(hoja, list(libro.sheet_names))
            # skip_empty_area=False: la fila 0 de la lista es la fila 1 de la hoja,
            # asi los numeros de fila de las incidencias coinciden con Excel.
            filas = libro.get_sheet_by_name(hoja).to_python(skip_empty_area=False)
        except CalamineError as exc:
            raise ArchivoIlegible(f"No se pudo leer la hoja {hoja!r}") from exc
        finally:
            libro.close()

        indice_cabecera = next((i for i, f in enumerate(filas) if _recortar(list(f))), None)
        if indice_cabecera is None:
            raise HojaVacia(f"La hoja {hoja!r} no tiene cabecera ni datos")

        datos = []
        for indice in range(indice_cabecera + 1, len(filas)):
            celdas = _recortar(list(filas[indice]))
            if celdas:
                datos.append(FilaCruda(numero_fila=indice + 1, celdas=celdas))

        return HojaSabana(
            nombre=hoja,
            fila_cabecera=indice_cabecera + 1,
            cabeceras=_recortar(list(filas[indice_cabecera])),
            filas=datos,
        )
