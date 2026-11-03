"""Conciliacion de lo cargado con el informe de WhatsMKT, por numero (RF-WM-39, RF-41).

Es por CONJUNTOS: un producto esta enviado si su numero aparece en el informe, sin importar el
orden ni cuantas veces aparezca. Si un numero cubre dos productos, el envio cuenta para los dos
(P-7). Los registros de supervision se concilian aparte de los productos.

Los numeros se comparan como texto de digitos, de los dos lados. El nombre de campana que trae el
informe no interviene: se escribe a mano en WhatsMKT y no sirve de clave.
"""

from collections.abc import Iterable, Sequence
from dataclasses import replace

from app.core.entities.whatsmkt_informe import (
    CifrasWhatsmkt,
    ConciliacionWhatsmkt,
    FilaCargadaWhatsmkt,
)
from app.core.services.plataformas.whatsmkt.informe import solo_digitos


def _cifras(enviados: Sequence, no_enviados: Sequence) -> CifrasWhatsmkt:
    return CifrasWhatsmkt(
        cargados=len(enviados) + len(no_enviados),
        enviados=len(enviados),
        no_enviados=len(no_enviados),
    )


def conciliar(
    cargadas: Iterable[FilaCargadaWhatsmkt], numeros_del_informe: Iterable[str]
) -> ConciliacionWhatsmkt:
    """Las cifras y las listas de la conciliacion de una campana."""
    informe = [solo_digitos(n) for n in numeros_del_informe]
    en_el_informe = {n for n in informe if n is not None}
    filas = [replace(f, numero=solo_digitos(f.numero) or f.numero) for f in cargadas]

    enviados = {True: [], False: []}  # por supervision
    no_enviados = {True: [], False: []}
    for fila in filas:
        (enviados if fila.numero in en_el_informe else no_enviados)[fila.supervision].append(fila)

    cargados = {f.numero for f in filas}
    sin_correspondencia = tuple(dict.fromkeys(n for n in informe if n and n not in cargados))
    return ConciliacionWhatsmkt(
        productos=_cifras(enviados[False], no_enviados[False]),
        supervision=_cifras(enviados[True], no_enviados[True]),
        total=_cifras(
            [*enviados[False], *enviados[True]], [*no_enviados[False], *no_enviados[True]]
        ),
        productos_enviados=tuple(enviados[False]),
        productos_no_enviados=tuple(no_enviados[False]),
        supervision_enviados=tuple(enviados[True]),
        supervision_no_enviados=tuple(no_enviados[True]),
        sin_correspondencia=sin_correspondencia,
    )
