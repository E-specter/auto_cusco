"""Puerto de lectura de archivos tabulares (Excel, ODS, CSV y JSON), RF-57."""

from typing import Protocol

from app.core.entities.lectura_tabla import OpcionesLectura, TablaLeida


class LectorTablaPort(Protocol):
    """Lee cualquier archivo tabular y devuelve su cabecera y sus filas."""

    def leer(
        self,
        contenido: bytes,
        nombre_archivo: str,
        opciones: OpcionesLectura = OpcionesLectura(),  # noqa: B008
    ) -> TablaLeida:
        """El formato se decide por la extension de `nombre_archivo` y, si falta o no la conoce, por
        el contenido. `opciones` gana a lo detectado.

        Lanza `ArchivoIlegible` (ilegible, vacio, extension que no coincide con el contenido, opcion
        invalida), `HojaNoEncontrada` (una hoja pedida que no existe) o `HojaVacia` (sin cabecera ni
        datos), de `app.core.entities.sabana`.
        """
        ...
