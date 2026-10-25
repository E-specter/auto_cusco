"""Lo que comparten los lectores de tablas sobre las celdas: que es una celda vacia y como se
recorta una fila."""

from typing import Any


def vacia(celda: Any) -> bool:
    return celda is None or (isinstance(celda, str) and celda.strip() == "")


def recortar(celdas: list[Any]) -> list[Any]:
    """La fila sin las celdas vacias del final."""
    fin = len(celdas)
    while fin and vacia(celdas[fin - 1]):
        fin -= 1
    return celdas[:fin]
