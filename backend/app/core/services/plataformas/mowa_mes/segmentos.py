"""Dias de atraso ajustados al dia de envio y segmento del speech (RF-MM-15)."""

from collections.abc import Sequence
from datetime import date

from app.core.entities.mowa_mes import RANGOS_SEGMENTO, Programacion, RangoSegmento


class ProgramacionInvalida(Exception):
    """Las fechas no corresponden a la modalidad de envio."""


def dias_ajustados(dias_atraso: int, fecha_corte: date, fecha_envio: date) -> int:
    """dias_atraso de la sabana + dias calendario entre la fecha de corte y la de envio."""
    return dias_atraso + (fecha_envio - fecha_corte).days


def rango_de(
    dias: int | None, rangos: Sequence[RangoSegmento] = RANGOS_SEGMENTO
) -> RangoSegmento | None:
    """Segmento que cubre los dias ajustados; None si no hay speech (vacio o fuera de rango)."""
    if dias is None:
        return None
    for rango in rangos:
        if (rango.desde is None or rango.desde <= dias) and dias <= rango.hasta:
            return rango
    return None


def fecha_envio(
    programacion: Programacion, fecha_generacion: date, fechas_programadas: Sequence[date] = ()
) -> date:
    """Fecha de envio con la que se calculan los dias ajustados.

    Enviar ahora: la de generacion. Hora determinada: la programada. Diferentes
    horas: la mas temprana (supuesto S-MM-5).
    """
    if programacion is Programacion.ENVIAR_AHORA:
        return fecha_generacion
    if programacion is Programacion.HORA_DETERMINADA:
        if len(fechas_programadas) != 1:
            raise ProgramacionInvalida("Enviar en hora determinada lleva exactamente una fecha")
        return fechas_programadas[0]
    if not fechas_programadas:
        raise ProgramacionInvalida("Enviar en diferentes horas lleva al menos una fecha")
    return min(fechas_programadas)
