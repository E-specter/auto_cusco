"""El calendario laboral con un reloj fijo, para las pruebas de la fecha de envio (T-WM-B4c).

Nunca se usa el reloj real: «hoy» es el que se le da. Por defecto es el lunes 26 de octubre de 2026,
asi que las fechas de envio que usan las pruebas (del 27 de octubre en adelante) son futuras.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.entities.calendario import MAXIMO_PROXIMOS_POR_DEFECTO, ExcepcionCalendario
from app.core.services.calendario.servicio import CalendarioService
from app.core.services.plataformas.whatsmkt.programacion import ProgramacionWhatsmktService
from tests.test_calendario import RepositorioCalendarioFalso

LIMA = ZoneInfo("America/Lima")
HOY_DE_PRUEBA = datetime(2026, 10, 26, 10, 0, tzinfo=LIMA)  # lunes


def calendario_de_prueba(
    *excepciones: ExcepcionCalendario,
    ahora: datetime = HOY_DE_PRUEBA,
    maximo_proximos: int = MAXIMO_PROXIMOS_POR_DEFECTO,
) -> CalendarioService:
    return CalendarioService(
        RepositorioCalendarioFalso(*excepciones),
        reloj=lambda: ahora,
        maximo_proximos=maximo_proximos,
    )


def programacion_de_prueba(
    *excepciones: ExcepcionCalendario, ahora: datetime = HOY_DE_PRUEBA
) -> ProgramacionWhatsmktService:
    return ProgramacionWhatsmktService(calendario_de_prueba(*excepciones, ahora=ahora))
