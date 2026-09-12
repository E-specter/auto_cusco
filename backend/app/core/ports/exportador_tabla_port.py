"""Puerto de escritura de una tabla a archivo (RF-13, RF-14).

El nucleo pide "escribe esta tabla en este formato" y no sabe con que libreria
se hace. Cada formato vive en su propio adaptador en
`app/adapters/output/exportadores/`, asi incorporar uno nuevo no toca a los
demas ni al nucleo.
"""

from typing import Protocol

from app.core.entities.exportacion import ArchivoGenerado, OpcionesArchivo, Tabla


class ExportadorTablaPort(Protocol):
    """Escribe una tabla y devuelve el archivo resultante en memoria."""

    def __call__(self, tabla: Tabla, opciones: OpcionesArchivo) -> ArchivoGenerado: ...
