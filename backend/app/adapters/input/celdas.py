"""Lo que comparten los lectores de tablas sobre las celdas: que es una celda vacia y como se
recorta una fila."""

from typing import Any

from app.core.entities.valores import vacia


def recortar(celdas: list[Any]) -> list[Any]:
    """La fila sin las celdas vacias del final."""
    fin = len(celdas)
    while fin and vacia(celdas[fin - 1]):
        fin -= 1
    return celdas[:fin]
