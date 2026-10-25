"""Que formato tiene un archivo tabular: por su extension y, si falta, por su contenido (RF-57).

Funciones puras sobre los bytes. Las firmas: un ZIP (`PK`) es un `.xlsx`, `.xlsb` o `.ods`, segun lo
que trae adentro; un documento OLE es un `.xls`; un texto que empieza con `[` o `{` es JSON; el
resto es CSV. Una extension que no coincide con el contenido es un `ArchivoIlegible` con el motivo.
"""

import io
import zipfile

from app.core.entities.lectura_tabla import HOJAS_DE_CALCULO, FormatoTabla
from app.core.entities.sabana import ArchivoIlegible

_FIRMA_ZIP = b"PK\x03\x04"
_FIRMA_OLE = bytes.fromhex("d0cf11e0a1b11ae1")
_BOM_UTF8 = b"\xef\xbb\xbf"
_MIME_ODS = b"application/vnd.oasis.opendocument.spreadsheet"

_POR_EXTENSION = {
    "xlsx": FormatoTabla.XLSX,
    "xlsm": FormatoTabla.XLSX,
    "xlsb": FormatoTabla.XLSB,
    "xls": FormatoTabla.XLS,
    "ods": FormatoTabla.ODS,
    "csv": FormatoTabla.CSV,
    "tsv": FormatoTabla.CSV,
    "txt": FormatoTabla.CSV,
    "json": FormatoTabla.JSON,
}


def formato_de_hoja_de_calculo(contenido: bytes) -> FormatoTabla | None:
    """El formato de una hoja de calculo por su firma, o `None` si no parece una.

    Un ZIP que no se reconoce por dentro se toma por `.xlsx`: quien lo lee decide si es legible.
    """
    if contenido.startswith(_FIRMA_OLE):
        return FormatoTabla.XLS
    if not contenido.startswith(_FIRMA_ZIP):
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as comprimido:
            nombres = set(comprimido.namelist())
            if "mimetype" in nombres and comprimido.read("mimetype").strip() == _MIME_ODS:
                return FormatoTabla.ODS
    except (zipfile.BadZipFile, OSError, KeyError, NotImplementedError):
        return FormatoTabla.XLSX
    if "xl/workbook.bin" in nombres:
        return FormatoTabla.XLSB
    return FormatoTabla.XLSX


def _parece_json(contenido: bytes) -> bool:
    inicio = contenido.removeprefix(_BOM_UTF8).lstrip()
    return inicio[:1] in (b"[", b"{")


def _extension(nombre_archivo: str | None) -> str:
    if not nombre_archivo or "." not in nombre_archivo:
        return ""
    return nombre_archivo.rsplit(".", 1)[1].strip().casefold()


def detectar_formato(contenido: bytes, nombre_archivo: str | None) -> FormatoTabla:
    """El formato del archivo; `ArchivoIlegible` si esta vacio o la extension no coincide."""
    por_extension = _POR_EXTENSION.get(_extension(nombre_archivo))
    hoja_de_calculo = formato_de_hoja_de_calculo(contenido)
    if por_extension is None:
        if not contenido.strip():
            raise ArchivoIlegible("El archivo esta vacio")
        if hoja_de_calculo is not None:
            return hoja_de_calculo
        return FormatoTabla.JSON if _parece_json(contenido) else FormatoTabla.CSV
    extension = _extension(nombre_archivo)
    if por_extension in HOJAS_DE_CALCULO:
        if hoja_de_calculo is None:
            raise ArchivoIlegible(
                f"La extension .{extension} no coincide con el contenido: no es una hoja de calculo"
            )
        return hoja_de_calculo
    if hoja_de_calculo is not None:
        raise ArchivoIlegible(
            f"La extension .{extension} no coincide con el contenido: es una hoja de calculo"
        )
    if por_extension is FormatoTabla.JSON and not _parece_json(contenido):
        raise ArchivoIlegible(
            f"La extension .{extension} no coincide con el contenido: "
            "un JSON debe empezar con [ o {"
        )
    return por_extension
