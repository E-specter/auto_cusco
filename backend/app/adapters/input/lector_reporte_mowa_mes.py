"""Lector del reporte "Campanas de enviados" de MES (RF-MM-20), sobre el lector general (RF-57).

El archivo lo lee `LectorTablaPort` en cualquiera de los formatos de la sabana (hoja de calculo,
CSV, JSON), con sus opciones por defecto: el formato se reconoce solo, por la extension y el
contenido. Aqui se toma la primera hoja, se exigen las 8 columnas de RF-MM-20 (sin distinguir
mayusculas, tildes ni espacios de los extremos) y se le da su tipo a cada valor. Si falta alguna
columna o no hay filas, rechaza el archivo con el motivo.

Tipos: MES entrega `celular` y `dni` como texto, pero si alguien abre y guarda el
archivo en Excel pueden quedar como numero; se vuelven texto sin decimales, y un
`dni` numerico de hasta 8 digitos recupera los ceros a la izquierda. En un CSV todo viene como
texto: el `dni` se queda tal cual, con sus ceros.
"""

from datetime import date, datetime
from typing import Any

from app.adapters.input.lector_tabla import LectorTabla
from app.core.entities.lectura_tabla import OpcionesLectura, TablaLeida
from app.core.entities.mowa_mes_reporte import COLUMNAS_REPORTE, FilaReporte, ReporteInvalido
from app.core.entities.sabana import ArchivoIlegible, HojaVacia
from app.core.ports.lector_tabla_port import LectorTablaPort
from app.core.services.mapeador.similitud import normalizar_cabecera

LARGO_DNI = 8
NOMBRE_POR_DEFECTO = "reporte.xlsx"

_NO_LEGIBLE = "El archivo no es una hoja de calculo legible"
_SIN_HOJAS = "El archivo no tiene hojas"
_HOJA_NO_LEIBLE = "No se pudo leer la primera hoja del archivo"


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
        raise ReporteInvalido(f"La fila {fila} no tiene un ID campaña numérico en la columna «id».")
    return int(texto)


def _motivo(error: ArchivoIlegible) -> str:
    """El motivo del rechazo: el de siempre para una hoja de calculo (se reconoce por su mensaje) y,
    para lo demas (extension que no coincide, CSV o JSON ilegible), el del lector general."""
    mensaje = str(error)
    if mensaje.startswith("No se pudo leer la hoja"):
        return _HOJA_NO_LEIBLE
    if mensaje.endswith("no tiene hojas"):
        return _SIN_HOJAS
    if mensaje == "El archivo no es una hoja de cálculo legible":
        return _NO_LEGIBLE
    return mensaje


class LectorReporteMowaMes:
    def __init__(self, lector: LectorTablaPort | None = None) -> None:
        self._lector = lector or LectorTabla()

    def leer(
        self, contenido: bytes, nombre_archivo: str = NOMBRE_POR_DEFECTO
    ) -> tuple[FilaReporte, ...]:
        tabla = self._tabla(contenido, nombre_archivo)
        cabeceras = [normalizar_cabecera(str(c or "")) for c in tabla.cabeceras]
        faltan = [nombre for nombre in COLUMNAS_REPORTE if nombre not in cabeceras]
        if faltan:
            raise ReporteInvalido(f"Faltan columnas del reporte de enviados: {', '.join(faltan)}")
        posicion = {nombre: cabeceras.index(nombre) for nombre in COLUMNAS_REPORTE}

        resultado: list[FilaReporte] = []
        for cruda in tabla.filas:

            def celda(nombre: str, celdas=cruda.celdas) -> Any:
                i = posicion[nombre]
                return celdas[i] if i < len(celdas) else None

            resultado.append(
                FilaReporte(
                    fila=cruda.numero_fila,
                    mes_id=_mes_id(celda("id"), cruda.numero_fila),
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

    def _tabla(self, contenido: bytes, nombre_archivo: str) -> TablaLeida:
        """La primera hoja del archivo (RF-MM-20); el lector general prefiere `VENCIDA`."""
        try:
            tabla = self._lector.leer(contenido, nombre_archivo)
            if tabla.hojas and tabla.hoja != tabla.hojas[0]:
                tabla = self._lector.leer(
                    contenido, nombre_archivo, OpcionesLectura(hoja=tabla.hojas[0])
                )
        except HojaVacia as exc:
            raise ReporteInvalido("La hoja no tiene cabecera ni filas") from exc
        except ArchivoIlegible as exc:
            raise ReporteInvalido(_motivo(exc)) from exc
        return tabla
