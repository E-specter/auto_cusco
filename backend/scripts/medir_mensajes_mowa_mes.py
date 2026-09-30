"""Microbench del mensaje del speech de MOWA MES: costo por fila de `ConstructorMensajes`.

Sin base de datos. Mide solo la construccion del mensaje de 46 000 filas sinteticas con el Speech
original (los 6 segmentos, con WhatsApp), y sirve igual para el camino de antes (HEAD) que para el
del motor: usa solo la API publica (`ConstructorMensajes.mensaje_de`).

Uso, desde backend/ de cada copia del codigo:

    uv run python scripts/medir_mensajes_mowa_mes.py

La comparacion del corte B5 (docs/motor-texto-enriquecido.md, M1) corre este mismo archivo dentro
del backend de HEAD y del de la rama.
"""

import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))  # `tests.test_speech_original` del backend en el que se corre

from app.core.entities.mowa_mes import RANGOS_SEGMENTO  # noqa: E402
from app.core.services.plataformas.mowa_mes import speech  # noqa: E402
from tests.test_speech_original import speech_del_documento  # noqa: E402

FILAS = 46_000
REPETICIONES = 5
WHATSAPP = "900000123"
APELLIDOS = ["Quispe", "Huaman", "Ñahui", "Condori", "Mamani", "Pérez", "Rojas", "Sánchez"]
NOMBRES = ["Ana", "José", "María", "Luis", "Carmen", "Ñusta", "Pedro", "Rosa"]


def _titulares(azar: random.Random) -> list[str]:
    return [
        f"{azar.choice(APELLIDOS)}/{azar.choice(APELLIDOS)},{azar.choice(NOMBRES)}"
        for _ in range(FILAS)
    ]


def main() -> None:
    azar = random.Random(20260930)
    titulares = _titulares(azar)
    vencimientos = [date(2026, 1, 1) + timedelta(days=azar.randint(0, 600)) for _ in range(FILAS)]
    segmentos = [RANGOS_SEGMENTO[i % len(RANGOS_SEGMENTO)].segmento for i in range(FILAS)]
    constructor = speech.ConstructorMensajes(speech_del_documento(), WHATSAPP)
    mensaje_de = constructor.mensaje_de

    tiempos = []
    total = 0
    for _ in range(REPETICIONES):
        inicio = time.perf_counter()
        for segmento, titular, vencimiento in zip(segmentos, titulares, vencimientos, strict=True):
            total += len(mensaje_de(segmento, titular, vencimiento))
        tiempos.append(time.perf_counter() - inicio)

    mejor = min(tiempos)
    print(
        f"{FILAS} mensajes: mejor de {REPETICIONES} = {mejor:.3f} s "
        f"({mejor / FILAS * 1e6:.2f} us por fila); tiempos = "
        + ", ".join(f"{t:.3f}" for t in tiempos)
        + f"; suma de largos = {total // REPETICIONES}"
    )


main()
