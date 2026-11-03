"""Contrato: cada codigo de WhatsMKT tiene su traduccion en el frontend (T-WM-B1).

Lee los diccionarios de verdad (`frontend/src/i18n/es.json` y `en.json`): el frontend traduce por
codigo con la clave plana `whatsmkt.codigo.<codigo>`. Cada corte que agrega codigos al enum
agrega aqui su clave.
"""

from app.core.entities.whatsmkt import CodigoWhatsmkt
from tests.ayudas.espejo_i18n import assert_cubre, diccionario


def test_cada_codigo_tiene_su_traduccion() -> None:
    assert_cubre(
        CodigoWhatsmkt,
        "whatsmkt.codigo",
        ayuda="Se agregan en es.json y en.json junto al bloque whatsmkt.* del frontend.",
    )


def test_son_29_codigos_y_los_de_la_previsualizacion_estan_entre_ellos() -> None:
    assert len(CodigoWhatsmkt) == 29
    assert {"sin_dias_atraso", "sin_supervisores"} <= {c.value for c in CodigoWhatsmkt}


def test_el_detalle_de_sin_dias_atraso_y_el_enlace_a_supervisores_estan_en_los_dos_idiomas() -> (
    None
):
    for idioma in ("es", "en"):
        diccionario_ = diccionario(idioma)
        for clave in ("whatsmkt.exclusiones.sin_dias_atraso", "whatsmkt.previa.irSupervisores"):
            assert diccionario_.get(clave), f"Falta {clave} en {idioma}.json"
