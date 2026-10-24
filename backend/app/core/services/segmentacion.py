"""Segmento de un producto segun el criterio de la definicion (RF-50).

Nucleo compartido: no conoce MOWA MES ni nombra campos de la sabana. La fecha de envio tampoco
entra aqui (la aporta cada modulo, ya aplicada, como una variable numerica: la cartera con
`services/fecha_envio.py`, MOWA MES con su campana); solo esta `dias_ajustados`, que MOWA MES
reexporta.
"""

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Any, TypeVar

from app.core.entities.segmentacion import (
    ConLimitesDeDias,
    CriterioCalculado,
    CriterioCampo,
    RangoDias,
    Segmentacion,
    SegmentacionInvalida,
)


def dias_ajustados(
    dias_atraso: int | Decimal, fecha_corte: date, fecha_envio: date
) -> int | Decimal:
    """dias_atraso de la sabana + dias calendario entre la fecha de corte y la de envio."""
    return dias_atraso + (fecha_envio - fecha_corte).days


_R = TypeVar("_R", bound=ConLimitesDeDias)


def rango_de(dias: int | Decimal | None, tabla: Sequence[_R]) -> _R | None:
    """Rango que cubre los dias; None si no hay dias o caen fuera de la tabla."""
    if dias is None:
        return None
    for rango in tabla:
        if (rango.desde is None or rango.desde <= dias) and (
            rango.hasta is None or dias <= rango.hasta
        ):
            return rango
    return None


def _numero(valor: Any) -> int | Decimal | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, Decimal)):
        return None
    return valor


def _vacio(valor: Any) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def segmento_de(segmentacion: Segmentacion, producto: Mapping[str, Any]) -> str | None:
    """Clave del segmento del producto, o None si no cae en ninguno (o no tiene el dato)."""
    criterio = segmentacion.criterio
    if isinstance(criterio, CriterioCampo):
        valor = producto.get(criterio.campo)
        return None if _vacio(valor) else str(valor)
    rango = rango_de(_numero(producto.get(criterio.variable_dias)), criterio.tabla)
    return None if rango is None else rango.clave


def segmentos_posibles(segmentacion: Segmentacion) -> tuple[str, ...] | None:
    """Las claves que admite el criterio, o None si no se conocen (un campo categorico)."""
    criterio = segmentacion.criterio
    if isinstance(criterio, CriterioCalculado):
        return tuple(rango.clave for rango in criterio.tabla)
    return None


def validar_tabla(tabla: Sequence[RangoDias]) -> None:
    """Claves y etiquetas con texto, sin repetir, y rangos que no se pisan (puede haber huecos)."""
    if not tabla:
        raise SegmentacionInvalida("La tabla de rangos esta vacia")
    claves: set[str] = set()
    for rango in tabla:
        if not rango.clave.strip():
            raise SegmentacionInvalida("Cada rango necesita una clave")
        if not rango.etiqueta.strip():
            raise SegmentacionInvalida(f"El rango {rango.clave!r} necesita una etiqueta")
        if rango.clave in claves:
            raise SegmentacionInvalida(f"La clave {rango.clave!r} esta repetida")
        claves.add(rango.clave)
        if rango.desde is not None and rango.hasta is not None and rango.desde > rango.hasta:
            raise SegmentacionInvalida(f"El rango {rango.clave!r} tiene desde mayor que hasta")
    for i, uno in enumerate(tabla):
        for otro in tabla[i + 1 :]:
            if _se_pisan(uno, otro):
                raise SegmentacionInvalida(f"Los rangos {uno.clave!r} y {otro.clave!r} se pisan")


def _se_pisan(a: RangoDias, b: RangoDias) -> bool:
    a_termina_antes = a.hasta is not None and b.desde is not None and a.hasta < b.desde
    b_termina_antes = b.hasta is not None and a.desde is not None and b.hasta < a.desde
    return not (a_termina_antes or b_termina_antes)


def validar(segmentacion: Segmentacion) -> None:
    criterio = segmentacion.criterio
    if isinstance(criterio, CriterioCampo):
        if not criterio.campo.strip():
            raise SegmentacionInvalida("El criterio por campo necesita el nombre del campo")
        return
    if not criterio.variable_dias.strip():
        raise SegmentacionInvalida("El criterio calculado necesita la variable de dias")
    validar_tabla(criterio.tabla)
