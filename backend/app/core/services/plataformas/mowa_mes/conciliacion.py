"""Conciliacion de filas cargadas con el reporte de enviados (RF-MM-22, C-3, C-5).

Emparejamiento multiconjunto por (numero, dni, mensaje normalizado): un mismo
telefono puede recibir el mismo mensaje por dos productos, y cada fila del
reporte cuenta para una sola fila cargada. La normalizacion se aplica igual a
los dos lados, porque MES quita tildes y recorta espacios al enviar.

"Enviado" es una fila cargada que aparece en el reporte con estado `enviado`
(decision E-1, sin distinguir mayusculas ni espacios). Una fila emparejada con
otro estado cuenta como cargada no enviada y aparece en el conteo por estado.
Las cifras por `id` cuentan todas las filas emparejadas, con cualquier estado:
dicen si el `id` es de esta campana, no cuanto se envio.
"""

import unicodedata
from collections import Counter, defaultdict, deque
from collections.abc import Iterable, Sequence

from app.core.entities.mowa_mes import CodigoMowaMes
from app.core.entities.mowa_mes_campana import FilaCarga
from app.core.entities.mowa_mes_reporte import (
    AdvertenciaReporte,
    CifrasGrupo,
    CifrasId,
    Conciliacion,
    FilaReporte,
)

ESTADO_ENVIADO = "enviado"


def es_enviado(estado: str) -> bool:
    return estado.strip().casefold() == ESTADO_ENVIADO


def normalizar_mensaje(texto: str) -> str:
    """Sin marcas diacriticas (NFD: tildes, dieresis, la de la n) ni espacios en los extremos."""
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c)).strip()


def _clave(numero: str, dni: str, mensaje: str) -> tuple[str, str, str]:
    return numero.strip(), dni.strip(), normalizar_mensaje(mensaje)


def conciliar(cargadas: Sequence[FilaCarga], reporte: Sequence[FilaReporte]) -> Conciliacion:
    pendientes: dict[tuple[str, str, str], deque[FilaReporte]] = defaultdict(deque)
    for fila in reporte:
        pendientes[_clave(fila.celular, fila.dni, fila.mensaje)].append(fila)

    emparejadas: dict[bool, list[FilaReporte]] = {False: [], True: []}
    cargadas_por_grupo = Counter(fila.supervision for fila in cargadas)
    for cargada in cargadas:
        cola = pendientes.get(_clave(cargada.numero, cargada.dni, cargada.mensaje))
        if cola:
            emparejadas[cargada.supervision].append(cola.popleft())

    sobrantes = [fila for cola in pendientes.values() for fila in cola]
    productos = _cifras(cargadas_por_grupo[False], emparejadas[False])
    supervision = _cifras(cargadas_por_grupo[True], emparejadas[True])
    total = _cifras(len(cargadas), [*emparejadas[False], *emparejadas[True]])

    por_id = _por_id(reporte, [*emparejadas[False], *emparejadas[True]])
    return Conciliacion(
        productos=productos,
        supervision=supervision,
        total=total,
        sin_correspondencia=len(sobrantes),
        sin_correspondencia_por_estado=_por_estado(sobrantes),
        por_id=por_id,
        advertencias=tuple(
            AdvertenciaReporte(
                codigo=CodigoMowaMes.ID_SIN_CORRESPONDENCIA,
                mes_id=cifras.mes_id,
                detalle=(
                    f"Ninguna de las {cifras.filas} filas del id {cifras.mes_id} coincide con lo "
                    "cargado en esta campana; probablemente es de otra"
                ),
            )
            for cifras in por_id
            if cifras.con_correspondencia == 0
        ),
    )


def _cifras(cargados: int, enviadas: Sequence[FilaReporte]) -> CifrasGrupo:
    return CifrasGrupo(
        cargados=cargados,
        enviados=sum(1 for fila in enviadas if es_enviado(fila.estado)),
        por_estado=_por_estado(enviadas),
    )


def _por_estado(filas: Iterable[FilaReporte]) -> dict[str, int]:
    return dict(sorted(Counter(fila.estado.strip() for fila in filas).items()))


def _por_id(
    reporte: Sequence[FilaReporte], emparejadas: Sequence[FilaReporte]
) -> tuple[CifrasId, ...]:
    filas = Counter(fila.mes_id for fila in reporte)
    # Se cuenta por identidad de fila: dos filas identicas del reporte son dos envios.
    con_correspondencia = Counter(fila.mes_id for fila in emparejadas)
    return tuple(
        CifrasId(mes_id=mes_id, filas=cantidad, con_correspondencia=con_correspondencia[mes_id])
        for mes_id, cantidad in sorted(filas.items())
    )
