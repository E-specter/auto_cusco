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

El texto fijo se mide con `medida` (por defecto `len`, caracteres). MOWA MES pasa
`largo_gsm7_normalizado`: la cota queda en unidades GSM-7, exacta para el texto fijo (que se
transliteraba: `…` y `€` miden 3) y de 1 por caracter para las variables (B16).
"""

from collections.abc import Callable, Sequence

from app.core.entities.texto_enriquecido import CodigoTexto, MotivoSinCota

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


def _causa_de_nodo(nodo: NodoResuelto) -> tuple[CodigoTexto, int | None]:
    """Donde se pierde (o nunca existio) la cota de un nodo que no la tiene."""
    causa: tuple[CodigoTexto, int | None] | None = (CodigoTexto.SIN_COTA_VARIABLE, None)
    cota: int | None = None
    for posicion, paso in enumerate(nodo.pasos):
        if paso.funcion.cota is None:
            cota, causa = None, (CodigoTexto.SIN_COTA_FUNCION, posicion)
            continue
        args = tuple(a.literal if a.variable is None else None for a in paso.argumentos)
        cota = paso.funcion.cota(cota, args)
        if cota is not None:
            causa = None
    return causa or (CodigoTexto.SIN_COTA_VARIABLE, None)


def motivo_sin_cota(partes: Sequence[str | NodoResuelto]) -> MotivoSinCota | None:
    """Por que la expresion no tiene cota: el primer nodo que no la tiene. None si la tiene."""
    for indice, parte in enumerate(partes):
        if isinstance(parte, str) or cota_de_nodo(parte) is not None:
            continue
        codigo, funcion = _causa_de_nodo(parte)
        if codigo is CodigoTexto.SIN_COTA_VARIABLE:
            detalle = f"El largo de la variable {parte.nombre!r} depende del dato de cada producto"
        else:
            nombre = parte.pasos[funcion].funcion.nombre  # type: ignore[index]
            detalle = f"La funcion {nombre!r} no permite calcular un largo maximo"
        return MotivoSinCota(codigo, detalle, indice, funcion)
    return None


def cota_de_expresion(
    partes: Sequence[str | NodoResuelto], medida: Callable[[str], int] = len
) -> int | None:
    """Suma de las partes: texto fijo (lo que mide `medida`) o nodos de variable (su cota)."""
    total = 0
    for parte in partes:
        if isinstance(parte, str):
            total += medida(parte)
            continue
        cota = cota_de_nodo(parte)
        if cota is None:
            return None
        total += cota
    return total
