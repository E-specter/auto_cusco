"""Division de la carga de MES en archivos (RF-MM-11).

El algoritmo es el comun (`core/services/division_archivos.py`); aqui se arman las entidades de
MES con su resultado. Los maximos (registros y bytes por archivo, `entities/mowa_mes.py`) los trae
la configuracion de la campana. La supervision va al inicio de la carga, asi que cuenta dentro del
primer archivo.
"""

from collections.abc import Callable, Sequence

from app.core.entities.mowa_mes_campana import ArchivoCarga, ArchivoPrevisto, FilaCarga
from app.core.services import division_archivos
from app.core.services.division_archivos import tramos_por_filas as tramos_por_filas

EscritorArchivo = Callable[[Sequence[FilaCarga]], bytes]


def previstos_por_filas(filas: Sequence[FilaCarga], maximo: int) -> list[ArchivoPrevisto]:
    """Estimacion sin escribir: al crear pueden salir mas archivos por el limite de bytes."""
    return [
        ArchivoPrevisto(numero=t.numero, filas=t.filas, supervision=t.supervision)
        for t in division_archivos.previstos_por_filas(filas, maximo)
    ]


def dividir(
    filas: Sequence[FilaCarga],
    maximo_filas: int,
    maximo_bytes: int,
    escribir: EscritorArchivo,
) -> list[ArchivoCarga]:
    tramos = division_archivos.dividir(filas, escribir, maximo_filas, maximo_bytes)
    return [
        ArchivoCarga(
            numero=numero,
            filas=len(tramo.filas),
            supervision=tramo.supervision,
            contenido=tramo.contenido,
        )
        for numero, tramo in enumerate(tramos, start=1)
    ]
