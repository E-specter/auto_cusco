"""Lector de archivos tabulares: elige el formato y delega (RF-57, docs/mapeador-encabezados.md §4).

El formato se decide por la extension del nombre y, si falta o no se conoce, por el contenido. Las
hojas de calculo las lee `LectorCalamine`; el CSV y el JSON, sus propios modulos.
"""

from app.adapters.input.lector_calamine import LectorCalamine
from app.adapters.input.lector_csv import leer_csv
from app.adapters.input.lector_json import leer_json
from app.core.entities.lectura_tabla import FormatoTabla, OpcionesLectura, TablaLeida
from app.core.ports.lector_tabla_port import LectorTablaPort
from app.core.services.lectura_tabla import detectar_formato


class LectorTabla(LectorTablaPort):
    def __init__(self, calamine: LectorCalamine | None = None) -> None:
        self._calamine = calamine or LectorCalamine()

    def leer(
        self,
        contenido: bytes,
        nombre_archivo: str,
        opciones: OpcionesLectura = OpcionesLectura(),  # noqa: B008
    ) -> TablaLeida:
        formato = detectar_formato(contenido, nombre_archivo)
        if formato is FormatoTabla.CSV:
            return leer_csv(contenido, opciones)
        if formato is FormatoTabla.JSON:
            return leer_json(contenido, opciones)
        return self._calamine.leer_tabla(contenido, opciones, formato)
