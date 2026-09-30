"""Catalogo de funciones del motor de texto enriquecido y su registro (RF-44).

Un modulo por familia; cada uno declara `FUNCIONES`. Agregar una funcion es
escribir su `Funcion` en el modulo que le toque (o en uno nuevo) y, si es un
modulo nuevo, sumarlo a `FAMILIAS`: el evaluador, el comprobador de tipos, el
catalogo de la API y la interfaz la toman de `REGISTRO`.
"""

from . import enlaces, fecha, nulos, numero, texto
from .base import Funcion, Parametro, ValorInvalido, normalizar_argumento

FAMILIAS = (texto, numero, fecha, nulos, enlaces)


def _registrar() -> dict[str, Funcion]:
    registro: dict[str, Funcion] = {}
    for familia in FAMILIAS:
        for funcion in familia.FUNCIONES:
            if funcion.nombre in registro:
                raise ValueError(f"La funcion {funcion.nombre!r} esta registrada dos veces")
            registro[funcion.nombre] = funcion
    return registro


REGISTRO: dict[str, Funcion] = _registrar()

__all__ = ["REGISTRO", "Funcion", "Parametro", "ValorInvalido", "normalizar_argumento"]
