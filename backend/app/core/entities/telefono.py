"""El telefono de RF-02: 9 digitos que empiezan con 9.

Una sola definicion para la ingesta de la sabana (`normalizar_telefono`), la supervision, el
WhatsApp de contacto de MOWA MES y el enlace `enlace_whatsapp` del motor de texto.
"""

import re

LARGO_TELEFONO = 9
TELEFONO_VALIDO = re.compile(r"9[0-9]{8}")


def numero_valido(numero: str) -> bool:
    """Si `numero` es un telefono de RF-02 tal cual esta: no corrige espacios ni un `.0` final."""
    return TELEFONO_VALIDO.fullmatch(numero) is not None
