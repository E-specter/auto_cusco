"""Dias de atraso ajustados al dia de envio y segmento del speech (RF-MM-15)."""

from collections.abc import Sequence
from datetime import date

from app.core.entities.mowa_mes import RANGOS_SEGMENTO, Programacion, RangoSegmento
from app.core.services import segmentacion
from app.core.services.segmentacion import dias_ajustados  # noqa: F401  (se reexporta)


class ProgramacionInvalida(Exception):
    """Las fechas no corresponden a la modalidad de envio."""


def rango_de(
    dias: int | None, rangos: Sequence[RangoSegmento] = RANGOS_SEGMENTO
) -> RangoSegmento | None:
    """Segmento que cubre los dias ajustados; None si no hay speech (vacio o fuera de rango)."""
    return segmentacion.rango_de(dias, rangos)


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
