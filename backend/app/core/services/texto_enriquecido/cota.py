"""Largo maximo que puede alcanzar una expresion, si se puede acotar (RF-47).

Sirve para mostrar en la previsualizacion el largo maximo de un mensaje contra un
limite (por ejemplo, el de un SMS). La cota es siempre un tope verdadero: nunca
menor que lo que el texto puede llegar a medir.

- Un texto fijo mide lo que mide.
- Una variable sin funciones no tiene cota: su largo depende del dato.
- Las funciones que fijan un largo (`primeros(n)` da n, `formato_fecha("dd/mm/aaaa")`
  da 10, `enlace_whatsapp` da el largo del prefijo mas 9) la crean; las que solo
  transforman (`mayusculas`, `recortar`) la conservan; las que pueden alargar sin
  tope (`formato_numero`, `a_texto` de un numero) la pierden.
- Una sola parte sin cota deja toda la expresion sin cota.
"""

from collections.abc import Sequence

from .tipos import NodoResuelto


def cota_de_nodo(nodo: NodoResuelto) -> int | None:
    cota: int | None = None
    for paso in nodo.pasos:
        if paso.funcion.cota is None:
            cota = None
            continue
        args = tuple(a.literal if a.variable is None else None for a in paso.argumentos)
        cota = paso.funcion.cota(cota, args)
    return cota


def cota_de_expresion(partes: Sequence[str | NodoResuelto]) -> int | None:
    """Suma de las partes: texto fijo (su largo) o nodos de variable (su cota)."""
    total = 0
    for parte in partes:
        if isinstance(parte, str):
            total += len(parte)
            continue
        cota = cota_de_nodo(parte)
        if cota is None:
            return None
        total += cota
    return total
