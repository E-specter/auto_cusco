"""Enlaces (seccion 6): el de WhatsApp a partir de un telefono valido (RF-02)."""

from app.core.entities.telefono import LARGO_TELEFONO, numero_valido
from app.core.entities.texto_enriquecido import PREFIJO_WHATSAPP, CodigoTexto, TipoValor

from .base import Funcion, Parametro, ValorInvalido


def enlace_whatsapp(telefono: str, prefijo: str = PREFIJO_WHATSAPP) -> str:
    if not numero_valido(telefono):
        raise ValorInvalido(
            CodigoTexto.TELEFONO_INVALIDO,
            "Se esperaban 9 digitos iniciando en 9 para armar el enlace",
        )
    return f"{prefijo}{telefono}"


def _cota_enlace(_entrada: int | None, args: tuple) -> int | None:
    return len(args[0]) + LARGO_TELEFONO


FUNCIONES = (
    Funcion(
        "enlace_whatsapp",
        "enlaces",
        (TipoValor.TEXTO,),
        TipoValor.TEXTO,
        enlace_whatsapp,
        (
            Parametro(
                "prefijo",
                TipoValor.TEXTO,
                por_defecto=PREFIJO_WHATSAPP,
                largo_minimo=1,
                largo_maximo=200,
            ),
        ),
        cota=_cota_enlace,
    ),
)
