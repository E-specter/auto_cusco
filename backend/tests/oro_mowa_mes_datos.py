"""Partes sinteticas del speech para la prueba de oro de MOWA MES M1 (B5).

Solo datos, sin logica: los usan `test_mowa_mes_speech_oro.py` y el microbench.
Ningun texto es real: son frases inventadas para ejercitar espacios, tildes, corchetes y
la variable `[whatsapp]`. Cada conjunto reparte los mismos dos textos en los 6 segmentos.
"""

from app.core.entities.mowa_mes import RANGOS_SEGMENTO, PartesSegmento

# nombre -> (parte_1, parte_2)
TEXTOS_SINTETICOS: dict[str, tuple[str, str]] = {
    "espacios_extremos": ("  hola  ", "  chau  "),
    "tildes_y_enes": (
        " Señor(a): tu cuota de Ñuñoa venció el ",
        ", acércate a pagar — ¡gracias! ñandú ÁÉÍÓÚ",
    ),
    "corchetes_sueltos": (" [ ] [whatsapp sin cerrar whatsapp] [ ", " ]] [[ [whatsapp"),
    "whatsapp_repetido_y_en_ambas": (
        " info [whatsapp] o [whatsapp] ",
        " escribe a [whatsapp][whatsapp] ",
    ),
    "whatsapp_solo_en_parte_1": (" INFO [whatsapp] vence el ", "."),
    "whatsapp_solo_en_parte_2": ("vence el ", ". INFO [whatsapp]"),
    "solo_whatsapp": ("[whatsapp]", "[whatsapp]"),
    "otra_escritura_de_whatsapp": ("[WhatsApp] [Whatsapp]", "[ whatsapp ] [whatsapp ]"),
    "vacias": ("", ""),
    "saltos_de_linea": ("línea 1\n", "\tlínea 2\r\n"),
    "arrobas_sin_corchete": (" a@b.pe ", " @titular @ "),
}


def version_con(parte_1: str, parte_2: str) -> tuple[PartesSegmento, ...]:
    """Una version completa: los dos textos en cada uno de los 6 segmentos."""
    return tuple(PartesSegmento(rango.segmento, parte_1, parte_2) for rango in RANGOS_SEGMENTO)


def version_por_segmento() -> tuple[PartesSegmento, ...]:
    """Una version con un texto distinto por segmento, algunos con [whatsapp] y otros sin."""
    textos = list(TEXTOS_SINTETICOS.values())
    return tuple(
        PartesSegmento(rango.segmento, *textos[posicion * 2 % len(textos)])
        for posicion, rango in enumerate(RANGOS_SEGMENTO)
    )


VERSIONES_SINTETICAS: dict[str, tuple[PartesSegmento, ...]] = {
    **{nombre: version_con(*textos) for nombre, textos in TEXTOS_SINTETICOS.items()},
    "un_texto_distinto_por_segmento": version_por_segmento(),
}


# --- La matriz de la prueba de oro --------------------------------------------------------------
# versiones x segmentos x numeros x titulares x vencimientos. La recorren la prueba de oro y el
# calculo de las constantes congeladas en HEAD 3e567d7, con el mismo orden y la misma forma.

import hashlib  # noqa: E402
import json  # noqa: E402
from collections.abc import Callable  # noqa: E402
from datetime import date  # noqa: E402
from typing import Any  # noqa: E402

from app.core.entities.mowa_mes import FaltaWhatsapp  # noqa: E402
from tests.test_speech_original import speech_del_documento  # noqa: E402

WHATSAPP = "900000123"
VENCIMIENTO = date(2026, 9, 5)
ORIGINAL = speech_del_documento()
TODAS_LAS_VERSIONES: dict[str, tuple[PartesSegmento, ...]] = {
    "original": ORIGINAL,
    **VERSIONES_SINTETICAS,
}
TITULARES = [
    "APELLIDO/NOMBRE LARGO",  # largo
    "AB",  # corto: menos de 8
    "12345678",  # justo 8
    "123456789",  # 9
    "Ñandú Pérez López",  # tildes y ñ
    "   Perez Ruiz",  # espacios al inicio
    None,
    "",
]
VENCIMIENTOS = [VENCIMIENTO, date(2026, 12, 31), date(2027, 1, 1), None]
NUMEROS = [WHATSAPP, None]


def mensajes_de_la_matriz(constructor_de: Callable[[Any, str | None], Any]) -> list[list]:
    """Cada mensaje de la matriz, en orden estable; `None` donde falta el WhatsApp del segmento."""
    filas: list[list] = []
    for nombre, version in TODAS_LAS_VERSIONES.items():
        for whatsapp in NUMEROS:
            constructor = constructor_de(version, whatsapp)
            for partes in version:
                for titular in TITULARES:
                    for vencimiento in VENCIMIENTOS:
                        try:
                            mensaje = constructor.mensaje_de(partes.segmento, titular, vencimiento)
                        except FaltaWhatsapp:
                            mensaje = None
                        fecha = vencimiento.isoformat() if vencimiento else None
                        filas.append(
                            [nombre, partes.segmento.value, whatsapp, titular, fecha, mensaje]
                        )
    return filas


def huella_de_la_matriz(filas: list[list]) -> str:
    """SHA-256 de la matriz serializada de forma determinista (JSON compacto, UTF-8)."""
    texto = json.dumps(filas, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()
