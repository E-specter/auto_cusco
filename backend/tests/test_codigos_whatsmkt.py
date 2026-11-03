"""Contrato: cada codigo de WhatsMKT tiene su traduccion en el frontend (T-WM-B1).

Lee los diccionarios de verdad (`frontend/src/i18n/es.json` y `en.json`): el frontend traduce por
codigo con la clave plana `whatsmkt.codigo.<codigo>`. Cada corte que agrega codigos al enum
agrega aqui su clave.
"""

from app.core.entities.whatsmkt import CodigoWhatsmkt
from tests.ayudas.espejo_i18n import assert_cubre


def test_cada_codigo_tiene_su_traduccion() -> None:
    assert_cubre(
        CodigoWhatsmkt,
        "whatsmkt.codigo",
        ayuda="Se agregan en es.json y en.json junto al bloque whatsmkt.* del frontend.",
    )
