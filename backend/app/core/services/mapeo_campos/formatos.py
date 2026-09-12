"""Tipado explicito de los campos generados (RF-12): texto, numero, fecha, financiero."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.entities.mapeo import CampoSalida, FormatoFinanciero, TipoSalida, ValorNoGenerable


def _a_decimal(campo: str, texto: str) -> Decimal:
    try:
        return Decimal(texto.strip())
    except InvalidOperation as exc:
        raise ValorNoGenerable(campo, f"{texto!r} no es un numero") from exc


def _a_fecha(campo: str, valor: Any, texto: str) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(texto.strip())
    except ValueError as exc:
        raise ValorNoGenerable(campo, f"{texto!r} no es una fecha") from exc


def formatear_importe(monto: Decimal, formato: FormatoFinanciero) -> str:
    """Aplica separadores configurables, por ejemplo 1,234.56 o 1.234,56."""
    cuantizado = round(monto, formato.decimales)
    entero, _, decimal = f"{abs(cuantizado):.{formato.decimales}f}".partition(".")
    grupos = []
    while len(entero) > 3:
        grupos.insert(0, entero[-3:])
        entero = entero[:-3]
    grupos.insert(0, entero)
    texto = formato.separador_miles.join(grupos)
    if formato.decimales:
        texto = f"{texto}{formato.separador_decimal}{decimal}"
    return f"-{texto}" if cuantizado < 0 else texto


def convertir(campo: CampoSalida, texto: str, crudo: Any) -> Any:
    """Devuelve el valor final del campo segun su tipo.

    `texto` es el resultado de aplicar la plantilla; `crudo` es el valor original
    del producto cuando la plantilla era una sola referencia, para no perder el
    tipo por el camino.
    """
    if campo.tipo is TipoSalida.TEXTO:
        return texto
    if texto == "":
        return None  # sin dato de origen: la celda queda vacia
    if campo.tipo is TipoSalida.NUMERO:
        numero = crudo if isinstance(crudo, (int, Decimal)) else _a_decimal(campo.nombre, texto)
        if isinstance(numero, Decimal) and numero == numero.to_integral_value():
            return int(numero)
        return numero
    if campo.tipo is TipoSalida.FINANCIERO:
        monto = crudo if isinstance(crudo, Decimal) else _a_decimal(campo.nombre, texto)
        return formatear_importe(Decimal(monto), campo.formato_financiero)
    fecha = _a_fecha(campo.nombre, crudo, texto)
    return fecha.strftime(campo.formato_fecha) if campo.formato_fecha else fecha
