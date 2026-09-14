"""Lector del reporte "Campanas de enviados" de MES (RF-MM-20), con python-calamine.

Toma la primera hoja, busca la cabecera en la primera fila con datos y exige las
8 columnas de RF-MM-20 (sin distinguir mayusculas, tildes ni espacios de los
extremos). Si falta alguna o no hay filas, rechaza el archivo con el motivo.

Tipos: MES entrega `celular` y `dni` como texto, pero si alguien abre y guarda el
archivo en Excel pueden quedar como numero; se vuelven texto sin decimales, y un
`dni` numerico de hasta 8 digitos recupera los ceros a la izquierda.
"""

import io
import unicodedata
from datetime import date, datetime
from typing import Any

from python_calamine import CalamineError, CalamineWorkbook

from app.core.entities.mowa_mes_reporte import COLUMNAS_REPORTE, FilaReporte, ReporteInvalido

LARGO_DNI = 8


def _normalizar_cabecera(valor: Any) -> str:
    texto = unicodedata.normalize("NFD", str(valor or "").strip().lower())
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).split())


def _vacia(celda: Any) -> bool:
    return celda is None or (isinstance(celda, str) and not celda.strip())


def _entero_como_texto(valor: Any) -> str:
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    if isinstance(valor, int):
        return str(valor)
    return "" if valor is None else str(valor).strip()


def _dni(valor: Any) -> str:
    texto = _entero_como_texto(valor)
    if isinstance(valor, (int, float)) and texto.isdigit() and len(texto) < LARGO_DNI:
        return texto.zfill(LARGO_DNI)
    return texto


def _fecha(valor: Any) -> str:
    if isinstance(valor, datetime | date):
        return valor.strftime("%d/%m/%y")
    return _entero_como_texto(valor)


def _mes_id(valor: Any, fila: int) -> int:
    texto = _entero_como_texto(valor)
    if not texto.isdigit():
        raise ReporteInvalido(f"La fila {fila} no tiene un id de MES numerico")
    return int(texto)


class LectorReporteMowaMes:
    def leer(self, contenido: bytes) -> tuple[FilaReporte, ...]:
        try:
            libro = CalamineWorkbook.from_filelike(io.BytesIO(contenido))
        except CalamineError as exc:
            raise ReporteInvalido("El archivo no es una hoja de calculo legible") from exc
        try:
            if not libro.sheet_names:
                raise ReporteInvalido("El archivo no tiene hojas")
            filas = libro.get_sheet_by_index(0).to_python(skip_empty_area=False)
        except CalamineError as exc:
            raise ReporteInvalido("No se pudo leer la primera hoja del archivo") from exc
        finally:
            libro.close()

        indice = next((i for i, f in enumerate(filas) if any(not _vacia(c) for c in f)), None)
        if indice is None:
            raise ReporteInvalido("La hoja no tiene cabecera ni filas")
        cabeceras = [_normalizar_cabecera(c) for c in filas[indice]]
        faltan = [nombre for nombre in COLUMNAS_REPORTE if nombre not in cabeceras]
        if faltan:
            raise ReporteInvalido(f"Faltan columnas del reporte de enviados: {', '.join(faltan)}")
        posicion = {nombre: cabeceras.index(nombre) for nombre in COLUMNAS_REPORTE}

        resultado: list[FilaReporte] = []
        for numero, celdas in enumerate(filas[indice + 1 :], start=indice + 2):
            if all(_vacia(c) for c in celdas):
                continue

            def celda(nombre: str, celdas=celdas) -> Any:
                i = posicion[nombre]
                return celdas[i] if i < len(celdas) else None

            resultado.append(
                FilaReporte(
                    fila=numero,
                    mes_id=_mes_id(celda("id"), numero),
                    celular=_entero_como_texto(celda("celular")),
                    mensaje="" if celda("mensaje") is None else str(celda("mensaje")),
                    fecha_envio=_fecha(celda("fecha de envio")),
                    dni=_dni(celda("dni")),
                    estado=_entero_como_texto(celda("estado")),
                    salida=_entero_como_texto(celda("salida")),
                    usuario=_entero_como_texto(celda("usuario")),
                )
            )
        if not resultado:
            raise ReporteInvalido("El reporte no tiene filas")
        return tuple(resultado)
