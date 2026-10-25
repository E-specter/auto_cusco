"""Lector de sabanas basado en python-calamine (.xlsb, .xlsx, .xls, .ods).

Elegido tras medirlo contra pyxlsb sobre las sabanas reales: ~10 veces mas
rapido con resultados normalizados identicos (docs/architecture.md, "Medicion
de lectores de sabana").

Tipos que entrega: str, float, int, bool, date/datetime y "" para celdas
vacias. El normalizador del nucleo acepta todos ellos.
"""

import io

from python_calamine import CalamineError, CalamineWorkbook

from app.adapters.input.celdas import recortar
from app.core.entities.lectura_tabla import FormatoTabla, OpcionesLectura, TablaLeida
from app.core.entities.sabana import (
    HOJA_DATOS_POR_DEFECTO,
    ArchivoIlegible,
    FilaCruda,
    HojaNoEncontrada,
    HojaSabana,
    HojaVacia,
)
from app.core.ports.lector_sabana_port import LectorSabanaPort
from app.core.services.lectura_tabla import formato_de_hoja_de_calculo


class LectorCalamine(LectorSabanaPort):
    def leer_hoja(self, contenido: bytes, hoja: str = HOJA_DATOS_POR_DEFECTO) -> HojaSabana:
        """La hoja pedida de una hoja de calculo; delega en `leer_tabla` (paridad con antes)."""
        tabla = self.leer_tabla(contenido, OpcionesLectura(hoja=hoja))
        return HojaSabana(
            nombre=tabla.hoja or hoja,
            fila_cabecera=tabla.fila_cabecera,
            cabeceras=tabla.cabeceras,
            filas=tabla.filas,
        )

    def leer_tabla(
        self,
        contenido: bytes,
        opciones: OpcionesLectura = OpcionesLectura(),  # noqa: B008
        formato: FormatoTabla | None = None,
    ) -> TablaLeida:
        """Lista las hojas y lee la elegida: `opciones.hoja` o, sin ella, `VENCIDA` si existe y, si
        no, la primera. Una hoja pedida que no existe es `HojaNoEncontrada`."""
        formato = formato or formato_de_hoja_de_calculo(contenido)
        if formato is None:
            raise ArchivoIlegible("El archivo no es una hoja de calculo legible")
        try:
            libro = CalamineWorkbook.from_filelike(io.BytesIO(contenido))
        except CalamineError as exc:
            raise ArchivoIlegible("El archivo no es una hoja de calculo legible") from exc
        try:
            hojas = tuple(libro.sheet_names)
            hoja = opciones.hoja or _hoja_por_defecto(hojas)
            if hoja not in hojas:
                if not hojas:
                    raise ArchivoIlegible("La hoja de calculo no tiene hojas")
                raise HojaNoEncontrada(hoja, list(hojas))
            # skip_empty_area=False: la fila 0 de la lista es la fila 1 de la hoja,
            # asi los numeros de fila de las incidencias coinciden con Excel.
            filas = libro.get_sheet_by_name(hoja).to_python(skip_empty_area=False)
        except CalamineError as exc:
            raise ArchivoIlegible(f"No se pudo leer la hoja {hoja!r}") from exc
        finally:
            libro.close()

        indice_cabecera = next((i for i, f in enumerate(filas) if recortar(list(f))), None)
        if indice_cabecera is None:
            raise HojaVacia(f"La hoja {hoja!r} no tiene cabecera ni datos")

        datos = []
        for indice in range(indice_cabecera + 1, len(filas)):
            celdas = recortar(list(filas[indice]))
            if celdas:
                datos.append(FilaCruda(numero_fila=indice + 1, celdas=celdas))

        return TablaLeida(
            formato=formato,
            hojas=hojas,
            hoja=hoja,
            separador=None,
            codificacion=None,
            fila_cabecera=indice_cabecera + 1,
            cabeceras=recortar(list(filas[indice_cabecera])),
            filas=datos,
        )


def _hoja_por_defecto(hojas: tuple[str, ...]) -> str:
    """`VENCIDA` si existe y, si no, la primera (RF-57)."""
    if HOJA_DATOS_POR_DEFECTO in hojas:
        return HOJA_DATOS_POR_DEFECTO
    return hojas[0] if hojas else HOJA_DATOS_POR_DEFECTO
