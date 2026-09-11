"""Puerto para leer la hoja de datos de un archivo de sabana (RF-01)."""

from typing import Protocol

from app.core.entities.sabana import HOJA_DATOS_POR_DEFECTO, HojaSabana


class LectorSabanaPort(Protocol):
    """Cualquier lector de hojas de calculo (xlsb, xlsx, ...) que alimente la ingesta."""

    def leer_hoja(self, contenido: bytes, hoja: str = HOJA_DATOS_POR_DEFECTO) -> HojaSabana:
        """Devuelve la cabecera (primera fila no vacia) y las filas de datos no vacias.

        Lanza ArchivoIlegible, HojaNoEncontrada o HojaVacia (app.core.entities.sabana).
        """
        ...
