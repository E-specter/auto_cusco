"""Division de una carga en archivos por filas y por bytes (RF-MM-11, T-MM-C10, L-B9).

Primero por cantidad de filas, contando la supervision dentro del primer archivo (va al inicio de
la carga). Despues se escribe cada tramo y se mide su tamano real: si pasa del maximo de bytes, se
parte en tantos pedazos como haga falta y se vuelve a medir. Cada archivo conserva el orden de la
carga.

Es generico: no sabe de ninguna plataforma. Quien lo usa pone los maximos y el escritor del archivo
(`escribir`, filas -> bytes), y arma sus propias entidades con el resultado.
"""

import math
from collections.abc import Callable, Sequence

from app.core.entities.division_archivos import (
    ArchivoDemasiadoGrande,
    F,
    Tramo,
    TramoPrevisto,
)

Escritor = Callable[[Sequence[F]], bytes]


def tramos_por_filas(total: int, maximo: int) -> list[tuple[int, int]]:
    """Rangos [inicio, fin) de hasta `maximo` filas cada uno."""
    if maximo < 1:
        raise ValueError("El maximo de filas por archivo debe ser positivo")
    return [(inicio, min(inicio + maximo, total)) for inicio in range(0, total, maximo)]


def previstos_por_filas(filas: Sequence[F], maximo: int) -> list[TramoPrevisto]:
    """Estimacion sin escribir: al crear pueden salir mas archivos por el limite de bytes."""
    return [
        TramoPrevisto(
            numero=numero,
            filas=fin - inicio,
            supervision=sum(1 for fila in filas[inicio:fin] if fila.supervision),
        )
        for numero, (inicio, fin) in enumerate(tramos_por_filas(len(filas), maximo), start=1)
    ]


def dividir(
    filas: Sequence[F], escribir: Escritor, max_filas: int, max_bytes: int
) -> list[Tramo[F]]:
    tramos: list[Tramo[F]] = []
    for inicio, fin in tramos_por_filas(len(filas), max_filas):
        tramos.extend(_por_bytes(filas[inicio:fin], max_bytes, escribir))
    return tramos


def _por_bytes(tramo: Sequence[F], max_bytes: int, escribir: Escritor) -> list[Tramo[F]]:
    contenido = escribir(tramo)
    if len(contenido) <= max_bytes:
        return [Tramo(tramo, contenido)]
    if len(tramo) == 1:
        raise ArchivoDemasiadoGrande(
            f"Una sola fila ocupa {len(contenido)} bytes, mas que el maximo de {max_bytes}"
        )
    # Una estimacion por proporcion evita partir a la mitad una y otra vez; si un
    # pedazo sigue pasando, se vuelve a partir.
    pedazos = max(2, math.ceil(len(contenido) / max_bytes))
    tamano = math.ceil(len(tramo) / pedazos)
    resultado: list[Tramo[F]] = []
    for inicio in range(0, len(tramo), tamano):
        resultado.extend(_por_bytes(tramo[inicio : inicio + tamano], max_bytes, escribir))
    return resultado
