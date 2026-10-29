"""El telefono de RF-02 (T-MM-C10, L-B4): una sola definicion para la sabana, la supervision, el
WhatsApp de MOWA MES y el enlace del motor.

`numero_valido` antes era `normalizar_telefono(numero).valor == numero`; la tabla compara la nueva
contra esa definicion y se queda como regresion. Datos sinteticos.
"""

import pytest

from app.core.entities.telefono import LARGO_TELEFONO, numero_valido
from app.core.services.ingesta_sabana.reglas import normalizar_telefono
from app.core.services.texto_enriquecido.funciones.enlaces import enlace_whatsapp

VALIDOS = ["900000001", "900000123", "900000999", "900000000"]
INVALIDOS = [
    "",
    " ",
    "null",
    "NULL",
    "90000001",  # 8 digitos
    "9000000011",  # 10 digitos
    "800000001",  # no empieza con 9
    "90000000a",
    " 900000001",  # no corrige espacios
    "900000001 ",
    "900000001\n",
    "900000001 ",
    "900000001.0",  # ni un .0 final
    "+51900000001",
    "9 00000001",
    "９" + "０" * 8,  # digitos de ancho completo
    "9" + "١" * 8,  # digitos arabigo-indicos
]


@pytest.mark.parametrize("numero", VALIDOS)
def test_un_telefono_de_9_digitos_que_empieza_con_9_es_valido(numero) -> None:
    assert numero_valido(numero) is True


@pytest.mark.parametrize("numero", INVALIDOS, ids=repr)
def test_cualquier_otra_cosa_no_es_valida(numero) -> None:
    assert numero_valido(numero) is False


@pytest.mark.parametrize("numero", [*VALIDOS, *INVALIDOS], ids=repr)
def test_numero_valido_da_lo_mismo_que_la_definicion_anterior(numero) -> None:
    assert numero_valido(numero) == (normalizar_telefono(numero).valor == numero)


def test_el_largo_de_la_regla_es_9() -> None:
    assert LARGO_TELEFONO == 9
    assert all(len(n) == LARGO_TELEFONO for n in VALIDOS)


def test_el_enlace_lleva_el_prefijo_por_defecto_y_el_que_se_pida() -> None:
    assert enlace_whatsapp("900000123") == "https://wa.me/+51900000123"
    assert enlace_whatsapp("900000123", "https://x.test/") == "https://x.test/900000123"


def test_el_enlace_rechaza_un_telefono_invalido() -> None:
    from app.core.services.texto_enriquecido.funciones.base import ValorInvalido

    with pytest.raises(ValorInvalido):
        enlace_whatsapp("90000012")
