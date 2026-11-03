"""La fecha de envio de una campana de WhatsMKT (RF-WM-06, RF-70 y RF-71; T-WM-B4c).

El dia de envio es gestionable de lunes a sabado, sin feriados ni dias no laborables registrados, y
SIEMPRE posterior a hoy en America/Lima: hoy nunca sirve. Todo el calculo es del calendario comun
(`CalendarioService`, T-HI-B5); aqui solo se pregunta, no se repite.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from app.core.services.calendario.servicio import CalendarioService


class FechaNoGestionable(Exception):
    """La fecha de envio no es un dia gestionable. `sugerida` es el siguiente que si lo es."""

    def __init__(self, fecha: date, sugerida: date) -> None:
        super().__init__(
            f"El {fecha.isoformat()} no es un dia gestionable: el siguiente es el "
            f"{sugerida.isoformat()}"
        )
        self.fecha = fecha
        self.sugerida = sugerida


@dataclass(frozen=True)
class Programacion:
    """Lo que la pantalla ofrece para elegir la fecha: la sugerida, la primera que admite (el
    `min` del campo) y los proximos N dias gestionables."""

    sugerida: date
    minima: date
    proximas: tuple[date, ...]


class ProgramacionWhatsmktService:
    def __init__(self, calendario: CalendarioService) -> None:
        self._calendario = calendario

    def sugerida(self) -> date:
        """El siguiente dia gestionable despues de hoy en Lima (RF-WM-06)."""
        return self._calendario.siguiente_dia_gestionable(self._calendario.hoy())

    def programacion(self, n: int) -> Programacion:
        """Lanza `ProximosFueraDeRango` si `n` no esta entre 1 y el tope (RF-71)."""
        proximas = tuple(self._calendario.proximos_dias_gestionables(n, self._calendario.hoy()))
        return Programacion(sugerida=proximas[0], minima=proximas[0], proximas=proximas)

    def validar(self, fecha_envio: date) -> None:
        """Lanza `FechaNoGestionable` si no es un dia gestionable posterior a hoy.

        La sugerida es el siguiente dia gestionable despues de la fecha elegida o, si esa es de hoy
        o anterior, despues de hoy: nunca una fecha que tampoco serviria.
        """
        hoy = self._calendario.hoy()
        # Una fecha es gestionable si es la siguiente gestionable de la vispera: el calculo es el
        # del calendario comun.
        es_gestionable = (
            self._calendario.siguiente_dia_gestionable(fecha_envio - timedelta(days=1))
            == fecha_envio
        )
        if fecha_envio > hoy and es_gestionable:
            return
        raise FechaNoGestionable(
            fecha_envio, self._calendario.siguiente_dia_gestionable(max(fecha_envio, hoy))
        )
