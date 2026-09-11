"""Reglas de normalizacion por valor (docs/sabana-schema.md, seccion 6).

Funciones puras. Reciben el valor tal como lo entrega un lector de hojas de
calculo (str, float, int, bool, date/datetime o None) y devuelven un
`Resultado`: el valor normalizado (o None) y, si corresponde, un `Aviso`.
Ninguna regla corrige datos invalidos por su cuenta salvo las correcciones
confirmadas por el usuario (DNI completado con ceros, decision D-1).
"""

import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Generic, TypeVar

from app.core.entities.sabana import Aviso, Documento, Severidad, TipoDocumento

T = TypeVar("T")

_TEXTOS_NULOS = frozenset({"", "null"})
_SOLO_DIGITOS = re.compile(r"[0-9]+")
_ENTERO_CON_CERO_DECIMAL = re.compile(r"([0-9]+)\.0+")
_TELEFONO_VALIDO = re.compile(r"9[0-9]{8}")
_FECHA_DMY = re.compile(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})")

PREFIJOS_RUC = frozenset({"10", "15", "16", "17", "20"})
_PESOS_RUC = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)

# Excel (sistema 1900) cuenta dias desde 1899-12-30 para seriales >= 61; los
# anteriores arrastran el bug del 29/02/1900 y no son fechas validas de negocio.
_EPOCA_EXCEL = date(1899, 12, 30)
_SERIAL_MINIMO = 61
_SERIAL_MAXIMO = 2958465  # 9999-12-31

_VERDADEROS = frozenset({"si", "true", "verdadero", "1"})
_FALSOS = frozenset({"no", "false", "falso", "0"})
_CENTIMOS = Decimal("0.01")


@dataclass(frozen=True)
class Resultado(Generic[T]):
    valor: T | None
    aviso: Aviso | None = None


def es_vacio(valor: Any) -> bool:
    """None, texto en blanco o el literal NULL (N-2)."""
    if valor is None:
        return True
    return isinstance(valor, str) and valor.strip().casefold() in _TEXTOS_NULOS


def sin_tildes(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def normalizar_cabecera(cabecera: str) -> str:
    """Forma canonica de una cabecera para compararla con el catalogo (N-1)."""
    return re.sub(r"\s+", " ", sin_tildes(cabecera)).strip().casefold()


def _entero_como_texto(valor: Any) -> str | None:
    """Numero entero no negativo (int/float) o texto, como str sin decimales.

    Devuelve None si el valor no puede representar un codigo numerico.
    """
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return str(valor) if valor >= 0 else None
    if isinstance(valor, float):
        if not math.isfinite(valor) or not valor.is_integer() or valor < 0:
            return None
        return str(int(valor))
    if isinstance(valor, str):
        texto = valor.strip()
        coincidencia = _ENTERO_CON_CERO_DECIMAL.fullmatch(texto)
        return coincidencia.group(1) if coincidencia else texto
    return None


# ---------- N-2: texto ----------


def normalizar_texto(valor: Any, colapsar_espacios: bool = False) -> Resultado[str]:
    if es_vacio(valor):
        return Resultado(None)
    if isinstance(valor, float) and valor.is_integer():
        texto = str(int(valor))
    else:
        texto = str(valor)
    texto = texto.strip()
    if colapsar_espacios:
        texto = re.sub(r"\s+", " ", texto)
    return Resultado(texto)


# ---------- N-3: documento de identidad ----------


def es_ruc_valido(numero: str) -> bool:
    """11 digitos, prefijo SUNAT valido y digito verificador modulo 11."""
    if len(numero) != 11 or not _SOLO_DIGITOS.fullmatch(numero):
        return False
    if numero[:2] not in PREFIJOS_RUC:
        return False
    suma = sum(int(d) * p for d, p in zip(numero[:10], _PESOS_RUC, strict=True))
    verificador = 11 - (suma % 11)
    if verificador == 10:
        verificador = 0
    elif verificador == 11:
        verificador = 1
    return verificador == int(numero[10])


def normalizar_documento(valor: Any) -> Resultado[Documento]:
    """Infiere DNI, RUC o documento extranjero (decision D-1)."""
    if es_vacio(valor):
        return Resultado(None, Aviso("documento_vacio", Severidad.ERROR, "Documento vacio"))
    texto = _entero_como_texto(valor)
    if not texto:
        return Resultado(
            None,
            Aviso(
                "documento_formato_invalido",
                Severidad.ERROR,
                "El documento no es un numero entero no negativo ni un texto",
            ),
        )
    if _SOLO_DIGITOS.fullmatch(texto):
        if len(texto) == 11:
            if es_ruc_valido(texto):
                return Resultado(Documento(TipoDocumento.RUC, texto))
            return Resultado(
                None,
                Aviso(
                    "ruc_invalido",
                    Severidad.ERROR,
                    "11 digitos con prefijo o digito verificador de RUC invalido",
                ),
            )
        if len(texto) <= 8:
            if set(texto) == {"0"}:
                return Resultado(
                    None, Aviso("documento_solo_ceros", Severidad.ERROR, "Documento con solo ceros")
                )
            aviso = None
            if len(texto) < 8:
                aviso = Aviso(
                    "dni_completado_con_ceros",
                    Severidad.INFO,
                    f"DNI de {len(texto)} digitos completado a 8 con ceros a la izquierda",
                )
            return Resultado(Documento(TipoDocumento.DNI, texto.zfill(8)), aviso)
    return Resultado(Documento(TipoDocumento.EXTRANJERO, texto))


# ---------- N-4: telefono ----------


def normalizar_telefono(valor: Any) -> Resultado[str]:
    """9 digitos que empiezan con 9 (RF-02). Los invalidos se reportan, no se corrigen."""
    if es_vacio(valor):
        return Resultado(None, Aviso("telefono_vacio", Severidad.ADVERTENCIA, "Telefono vacio"))
    texto = _entero_como_texto(valor)
    if texto and _TELEFONO_VALIDO.fullmatch(texto):
        return Resultado(texto)
    largo = len(texto) if texto else 0
    return Resultado(
        None,
        Aviso(
            "telefono_invalido",
            Severidad.ADVERTENCIA,
            f"Se esperaban 9 digitos iniciando en 9; se recibieron {largo} caracteres",
        ),
    )


# ---------- N-5: fechas ----------


def _aviso_fecha(detalle: str) -> Aviso:
    return Aviso("fecha_invalida", Severidad.ADVERTENCIA, detalle)


def normalizar_fecha(valor: Any) -> Resultado[date]:
    """Serial de Excel, date/datetime o texto dd/mm/aaaa."""
    if es_vacio(valor):
        return Resultado(None)
    if isinstance(valor, datetime):
        return Resultado(valor.date())
    if isinstance(valor, date):
        return Resultado(valor)
    if isinstance(valor, str) and (coincidencia := _FECHA_DMY.fullmatch(valor.strip())):
        dia, mes, anio = (int(g) for g in coincidencia.groups())
        try:
            return Resultado(date(anio, mes, dia))
        except ValueError:
            return Resultado(None, _aviso_fecha("Fecha dd/mm/aaaa inexistente"))
    serial: float | None = None
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        serial = float(valor)
    elif isinstance(valor, str) and _SOLO_DIGITOS.fullmatch(valor.strip()):
        serial = float(valor.strip())
    if serial is None or not math.isfinite(serial):
        return Resultado(None, _aviso_fecha("No es una fecha ni un serial de Excel"))
    if not _SERIAL_MINIMO <= serial <= _SERIAL_MAXIMO:
        return Resultado(None, _aviso_fecha("Serial de Excel fuera de rango"))
    return Resultado(_EPOCA_EXCEL + timedelta(days=int(serial)))


def normalizar_vencimiento_operativo(valor: Any) -> Resultado[tuple[bool, date | None]]:
    """Columna mixta: texto NO o una fecha (N-5)."""
    if es_vacio(valor):
        return Resultado(
            None,
            Aviso(
                "vencimiento_operativo_vacio",
                Severidad.ADVERTENCIA,
                "Se esperaba NO o una fecha",
            ),
        )
    if isinstance(valor, str) and sin_tildes(valor).strip().casefold() == "no":
        return Resultado((False, None))
    fecha = normalizar_fecha(valor)
    if fecha.valor is None:
        return Resultado(
            None,
            Aviso(
                "vencimiento_operativo_invalido",
                Severidad.ADVERTENCIA,
                "Se esperaba NO o una fecha",
            ),
        )
    return Resultado((True, fecha.valor))


# ---------- N-6: booleanos ----------


def normalizar_booleano(valor: Any) -> Resultado[bool]:
    if es_vacio(valor):
        return Resultado(None)
    if isinstance(valor, bool):
        return Resultado(valor)
    if isinstance(valor, (int, float)) and valor in (0, 1):
        return Resultado(bool(valor))
    if isinstance(valor, str):
        texto = sin_tildes(valor).strip().casefold()
        if texto in _VERDADEROS:
            return Resultado(True)
        if texto in _FALSOS:
            return Resultado(False)
    return Resultado(
        None,
        Aviso("booleano_invalido", Severidad.ADVERTENCIA, "Se esperaba SI/NO o verdadero/falso"),
    )


# ---------- numeros ----------


def normalizar_financiero(valor: Any) -> Resultado[Decimal]:
    """Monto en PEN (supuesto S-1) redondeado a centimos."""
    invalido = Resultado(
        None, Aviso("monto_invalido", Severidad.ADVERTENCIA, "Se esperaba un monto numerico")
    )
    if es_vacio(valor):
        return Resultado(None)
    if isinstance(valor, bool):
        return invalido
    if isinstance(valor, float) and not math.isfinite(valor):
        return invalido
    try:
        monto = Decimal(str(valor).strip()) if isinstance(valor, str) else Decimal(str(valor))
    except InvalidOperation:
        return invalido
    if not monto.is_finite():
        return invalido
    return Resultado(monto.quantize(_CENTIMOS, rounding=ROUND_HALF_UP))


def normalizar_entero(valor: Any) -> Resultado[int]:
    invalido = Resultado(
        None, Aviso("entero_invalido", Severidad.ADVERTENCIA, "Se esperaba un numero entero")
    )
    if es_vacio(valor):
        return Resultado(None)
    if isinstance(valor, bool):
        return invalido
    if isinstance(valor, int):
        return Resultado(valor)
    if isinstance(valor, float):
        return Resultado(int(valor)) if math.isfinite(valor) and valor.is_integer() else invalido
    if isinstance(valor, str) and re.fullmatch(r"-?[0-9]+", valor.strip()):
        return Resultado(int(valor.strip()))
    return invalido
