"""Enlaces (seccion 6): el de WhatsApp a partir de un telefono valido (RF-02)."""

from app.core.entities.texto_enriquecido import CodigoTexto, TipoValor
from app.core.services.gestiones_digitales.supervision import numero_valido

from .base import Funcion, Parametro, ValorInvalido

PREFIJO_WHATSAPP = "https://wa.me/+51"
LARGO_TELEFONO = 9  # 9 digitos que empiezan con 9 (RF-02)


def _enlace_whatsapp(telefono: str, prefijo: str) -> str:
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
        _enlace_whatsapp,
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
