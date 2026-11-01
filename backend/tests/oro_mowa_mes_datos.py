"""Textos v1 sinteticos del speech para la prueba de oro de MOWA MES (B5; T-MM-C11, M-B4).

Los usan `test_mowa_mes_speech_oro.py` y el microbench. Ningun texto es real: son frases inventadas
para ejercitar espacios, tildes, corchetes y la variable `[whatsapp]`. Cada conjunto reparte los
mismos dos textos en los 6 segmentos.

Desde M-B4 una version v1 es solo un DATO (una lista de `{"segmento", "parte_1", "parte_2"}`): la
app ya no la lee. Se pasa a v2 con el convertidor congelado de la migracion (`speech_congelado`).
"""

from app.core.entities.mowa_mes import RANGOS_SEGMENTO, Segmento

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


Version = tuple[dict[str, str], ...]


def _parte(segmento: Segmento, parte_1: str, parte_2: str) -> dict[str, str]:
    return {"segmento": segmento.value, "parte_1": parte_1, "parte_2": parte_2}


def version_con(parte_1: str, parte_2: str) -> Version:
    """Una version completa: los dos textos en cada uno de los 6 segmentos."""
    return tuple(_parte(rango.segmento, parte_1, parte_2) for rango in RANGOS_SEGMENTO)


def version_por_segmento() -> Version:
    """Una version con un texto distinto por segmento, algunos con [whatsapp] y otros sin."""
    textos = list(TEXTOS_SINTETICOS.values())
    return tuple(
        _parte(rango.segmento, *textos[posicion * 2 % len(textos)])
        for posicion, rango in enumerate(RANGOS_SEGMENTO)
    )


VERSIONES_SINTETICAS: dict[str, Version] = {
    **{nombre: version_con(*textos) for nombre, textos in TEXTOS_SINTETICOS.items()},
    "un_texto_distinto_por_segmento": version_por_segmento(),
}


# --- La matriz de la prueba de oro --------------------------------------------------------------
# versiones x segmentos x numeros x titulares x vencimientos. La recorren la prueba de oro y el
# calculo de las constantes congeladas (HEAD 3e567d7 y, por version, 9818e8d), con el mismo orden y
# la misma forma.

import hashlib  # noqa: E402
import json  # noqa: E402
from collections.abc import Callable  # noqa: E402
from datetime import date  # noqa: E402
from typing import Any  # noqa: E402

from app.core.entities.mowa_mes import (  # noqa: E402
    DatosSpeech,
    FaltaWhatsapp,
    MensajeNoGenerable,
)
from app.core.services.plataformas.mowa_mes import speech  # noqa: E402
from tests.speech_congelado import a_expresiones  # noqa: E402
from tests.test_speech_original import speech_del_documento  # noqa: E402

WHATSAPP = "900000123"
VENCIMIENTO = date(2026, 9, 5)
ORIGINAL = speech_del_documento()
TODAS_LAS_VERSIONES: dict[str, Version] = {
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


SIN_MENSAJE = "<sin mensaje: dato obligatorio vacio>"


class ConvertidaALaV2:
    """El constructor de una v1 convertida a v2 (con el convertidor congelado de la migracion).

    Con el titular o la fecha vacios la v2 convertida no arma mensaje (sus variables son
    obligatorias): en la matriz esa fila lleva `SIN_MENSAJE`; en la campana el producto ya se
    excluyo.
    """

    def __init__(
        self,
        version: Version,
        whatsapp: str | None,
        constructor: type[speech.ConstructorMensajes] = speech.ConstructorMensajes,
    ) -> None:
        convertida = DatosSpeech("convertida", a_expresiones(version))
        self._constructor = constructor(convertida, whatsapp)

    def mensaje_de(self, segmento, titular, vencimiento):
        try:
            return self._constructor.mensaje_de(segmento, titular, vencimiento)
        except MensajeNoGenerable:
            return SIN_MENSAJE


def mensajes_de_la_matriz(constructor_de: Callable[[Any, str | None], Any]) -> list[list]:
    """Cada mensaje de la matriz, en orden estable; `None` donde falta el WhatsApp del segmento."""
    filas: list[list] = []
    for nombre, version in TODAS_LAS_VERSIONES.items():
        for whatsapp in NUMEROS:
            constructor = constructor_de(version, whatsapp)
            for partes in version:
                segmento = Segmento(partes["segmento"])
                for titular in TITULARES:
                    for vencimiento in VENCIMIENTOS:
                        try:
                            mensaje = constructor.mensaje_de(segmento, titular, vencimiento)
                        except FaltaWhatsapp:
                            mensaje = None
                        fecha = vencimiento.isoformat() if vencimiento else None
                        filas.append([nombre, segmento.value, whatsapp, titular, fecha, mensaje])
    return filas


def huella_de_la_matriz(filas: list[list]) -> str:
    """SHA-256 de la matriz serializada de forma determinista (JSON compacto, UTF-8)."""
    texto = json.dumps(filas, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()
