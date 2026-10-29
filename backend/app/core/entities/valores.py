"""Predicados sobre valores sueltos que comparten el nucleo y los adaptadores."""

from typing import Any


def vacia(valor: Any) -> bool:
    """`None` o un texto en blanco: lo que una celda, una columna o un campo dan por vacio.

    Un cero, un `False` o una lista vacia NO son vacios: son datos.
    """
    return valor is None or (isinstance(valor, str) and not valor.strip())
