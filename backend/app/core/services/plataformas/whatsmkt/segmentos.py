"""Tabla de segmentos de WhatsMKT y segmento de un producto (RF-WM-20)."""

from collections.abc import Sequence
from dataclasses import replace
from decimal import Decimal

from app.core.entities.whatsmkt import CodigoWhatsmkt, ErrorWhatsmkt, SegmentoWhatsmkt
from app.core.services import segmentacion


def segmento_de(
    dias_ajustados: int | Decimal | None, segmentos: Sequence[SegmentoWhatsmkt]
) -> SegmentoWhatsmkt | None:
    """Segmento que cubre los dias; None si no hay dias.

    Los dias ya vienen ajustados a la fecha de envio: quien llama los calcula con
    `segmentacion.dias_ajustados` (RF-55), que no se copia aqui.
    """
    return segmentacion.rango_de(dias_ajustados, segmentos)


def segmentos_validos(segmentos: Sequence[SegmentoWhatsmkt]) -> tuple[SegmentoWhatsmkt, ...]:
    """Valida la tabla y la devuelve ordenada de menor a mayor, con `orden` 0, 1, 2...

    Sin superposicion ni huecos, del piso abierto al tope abierto (RF-WM-20). Que las claves sean
    las 3 fijas lo exige la API (validacion del modelo).
    """
    if not segmentos:
        raise ErrorWhatsmkt(CodigoWhatsmkt.SEGMENTOS_CON_HUECO, "Falta al menos un segmento")
    for segmento in segmentos:
        if (
            segmento.desde is not None
            and segmento.hasta is not None
            and segmento.desde > segmento.hasta
        ):
            raise ErrorWhatsmkt(
                CodigoWhatsmkt.SEGMENTOS_SUPERPUESTOS,
                f"El segmento {segmento.clave!r} tiene el desde mayor que el hasta",
                segmento=segmento.clave,
                fila=segmento.clave,
            )
    limpios = [replace(s, etiqueta=s.etiqueta.strip()) for s in segmentos]
    # Los sin piso primero (si hay mas de uno, se pisan en la comprobacion de abajo).
    ordenados = sorted(limpios, key=lambda s: (s.desde is not None, s.desde or 0))
    if ordenados[0].desde is not None:
        raise ErrorWhatsmkt(
            CodigoWhatsmkt.SEGMENTOS_CON_HUECO,
            f"Ningun segmento cubre los dias menores a {ordenados[0].desde}",
            desde=None,
            hasta=ordenados[0].desde - 1,
        )
    for anterior, siguiente in zip(ordenados, ordenados[1:], strict=False):
        if anterior.hasta is None or siguiente.desde is None or siguiente.desde <= anterior.hasta:
            raise ErrorWhatsmkt(
                CodigoWhatsmkt.SEGMENTOS_SUPERPUESTOS,
                f"Los segmentos {anterior.clave!r} y {siguiente.clave!r} se superponen",
                segmento=anterior.clave,
                fila=siguiente.clave,
            )
        if siguiente.desde > anterior.hasta + 1:
            raise ErrorWhatsmkt(
                CodigoWhatsmkt.SEGMENTOS_CON_HUECO,
                f"Entre {anterior.clave!r} y {siguiente.clave!r} quedan dias sin segmento",
                desde=anterior.hasta + 1,
                hasta=siguiente.desde - 1,
            )
    if ordenados[-1].hasta is not None:
        raise ErrorWhatsmkt(
            CodigoWhatsmkt.SEGMENTOS_CON_HUECO,
            f"Ningun segmento cubre los dias mayores a {ordenados[-1].hasta}",
            desde=ordenados[-1].hasta + 1,
            hasta=None,
        )
    return tuple(replace(s, orden=i) for i, s in enumerate(ordenados))
