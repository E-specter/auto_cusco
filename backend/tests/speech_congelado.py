"""El texto v1 congelado de las pruebas y su paso a v2 (T-MM-C11, M-B4; RF-MM-17).

Desde M-B4 la aplicacion no tiene codigo que lea ni arme versiones de dos partes. Las pruebas que
necesitan un speech con un texto conocido (el Speech original, las versiones sinteticas de la prueba
de oro) lo guardan como DATO, una lista de `{"segmento", "parte_1", "parte_2"}`, y lo pasan a v2 con
el convertidor CONGELADO de la migracion `d7a3e5b9c241` (`_convertir`), que no importa nada de
`app`.
Asi no queda codigo v1 vivo solo para las pruebas.
"""

import hashlib
import importlib.util
import json
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

from app.core.entities.mowa_mes import DatosSpeech, ExpresionSegmento, Segmento
from app.core.services.texto_enriquecido.serializacion import expresion_desde_dict

VERSIONES = Path(__file__).resolve().parents[1] / "migrations" / "versions"


def cargar_migracion(archivo: str) -> ModuleType:
    """Una migracion por su archivo: su nombre empieza con el id de la revision, no se importa."""
    spec = importlib.util.spec_from_file_location(archivo.removesuffix(".py"), VERSIONES / archivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


SOLO_V2 = cargar_migracion("d7a3e5b9c241_speech_solo_v2.py")  # el convertidor congelado
SIEMBRA = cargar_migracion("a4c8e2f6b913_configuracion_mowa_mes.py")  # donde nace el original


def a_expresiones(partes: Sequence[dict]) -> tuple[ExpresionSegmento, ...]:
    """Las expresiones que da el convertidor congelado para un texto v1."""
    return tuple(
        ExpresionSegmento(Segmento(e["segmento"]), expresion_desde_dict(e["expresion"]))
        for e in SOLO_V2._convertir(partes)
    )


def a_v2(partes: Sequence[dict], nombre: str = "Speech de prueba") -> DatosSpeech:
    return DatosSpeech(nombre, a_expresiones(partes))


def huella_del_texto_v1(partes: Sequence[dict]) -> str:
    """La huella que tenia una v1 (SHA-256 del texto de sus partes): el algoritmo de `huella_speech`
    antes de M-B4, que ya no existe en la app. Sirve para comprobar que el texto v1 guardado en
    `texto_v1` sigue siendo el de siempre."""
    datos = [[p["segmento"], p["parte_1"], p["parte_2"]] for p in partes]
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()
