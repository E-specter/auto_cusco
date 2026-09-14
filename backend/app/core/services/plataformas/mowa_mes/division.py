"""Division de la carga en archivos (RF-MM-11).

Primero por cantidad de filas, contando la supervision dentro del primer archivo.
Despues se escribe cada tramo y se mide su tamano real: si pasa del maximo de
bytes, se parte en tantos pedazos como haga falta y se vuelve a medir. Cada
archivo conserva el orden de la carga.
"""

import math
from collections.abc import Callable, Sequence

from app.core.entities.mowa_mes_campana import (
    ArchivoCarga,
    ArchivoDemasiadoGrande,
    ArchivoPrevisto,
    FilaCarga,
)

EscritorArchivo = Callable[[Sequence[FilaCarga]], bytes]


def tramos_por_filas(total: int, maximo: int) -> list[tuple[int, int]]:
    """Rangos [inicio, fin) de hasta `maximo` filas cada uno."""
    if maximo < 1:
        raise ValueError("El maximo de filas por archivo debe ser positivo")
    return [(inicio, min(inicio + maximo, total)) for inicio in range(0, total, maximo)]


def previstos_por_filas(filas: Sequence[FilaCarga], maximo: int) -> list[ArchivoPrevisto]:
    """Estimacion sin escribir: al crear pueden salir mas archivos por el limite de bytes."""
    return [
        ArchivoPrevisto(
            numero=numero,
            filas=fin - inicio,
            supervision=sum(1 for fila in filas[inicio:fin] if fila.supervision),
        )
        for numero, (inicio, fin) in enumerate(tramos_por_filas(len(filas), maximo), start=1)
    ]


def dividir(
    filas: Sequence[FilaCarga],
    maximo_filas: int,
    maximo_bytes: int,
    escribir: EscritorArchivo,
) -> list[ArchivoCarga]:
    tramos: list[tuple[Sequence[FilaCarga], bytes]] = []
    for inicio, fin in tramos_por_filas(len(filas), maximo_filas):
        tramos.extend(_por_bytes(filas[inicio:fin], maximo_bytes, escribir))
    return [
        ArchivoCarga(
            numero=numero,
            filas=len(tramo),
            supervision=sum(1 for fila in tramo if fila.supervision),
            contenido=contenido,
        )
        for numero, (tramo, contenido) in enumerate(tramos, start=1)
    ]


def _por_bytes(
    tramo: Sequence[FilaCarga], maximo_bytes: int, escribir: EscritorArchivo
) -> list[tuple[Sequence[FilaCarga], bytes]]:
    contenido = escribir(tramo)
    if len(contenido) <= maximo_bytes:
        return [(tramo, contenido)]
    if len(tramo) == 1:
        raise ArchivoDemasiadoGrande(
            f"Una sola fila ocupa {len(contenido)} bytes, mas que el maximo de {maximo_bytes}"
        )
    # Una estimacion por proporcion evita partir a la mitad una y otra vez; si un
    # pedazo sigue pasando, se vuelve a partir.
    pedazos = max(2, math.ceil(len(contenido) / maximo_bytes))
    tamano = math.ceil(len(tramo) / pedazos)
    resultado: list[tuple[Sequence[FilaCarga], bytes]] = []
    for inicio in range(0, len(tramo), tamano):
        resultado.extend(_por_bytes(tramo[inicio : inicio + tamano], maximo_bytes, escribir))
    return resultado
