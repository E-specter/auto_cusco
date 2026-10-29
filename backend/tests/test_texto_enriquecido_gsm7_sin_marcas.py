"""`sin_marcas`: el paso NFD de GSM-7 que tambien usa la conciliacion de MOWA MES (T-MM-C10, L-B5).

Es la funcion publica del primer paso de `a_gsm7`; antes era privado y la conciliacion lo repetia.
Datos sinteticos.
"""

import pytest

from app.core.services.plataformas.mowa_mes.conciliacion import normalizar_mensaje
from app.core.services.texto_enriquecido.gsm7 import a_gsm7, sin_marcas

CASOS = [
    ("Canción", "Cancion"),
    ("Año ünico", "Ano unico"),
    ("é", "e"),  # ya descompuesta: la marca suelta tambien se quita
    ("ñ", "n"),
    ("sin marcas", "sin marcas"),
    ("  con espacios  ", "  con espacios  "),  # no recorta: eso lo hace la conciliacion
    ("", ""),
    ("€ [ya]", "€ [ya]"),  # no translitera ni borra: eso es `a_gsm7`
]


@pytest.mark.parametrize(("entrada", "esperado"), CASOS)
def test_sin_marcas_quita_los_combinantes_y_nada_mas(entrada, esperado) -> None:
    assert sin_marcas(entrada) == esperado


@pytest.mark.parametrize(("entrada", "_"), CASOS)
def test_la_conciliacion_es_sin_marcas_mas_strip(entrada, _) -> None:
    assert normalizar_mensaje(entrada) == sin_marcas(entrada).strip()


@pytest.mark.parametrize(("entrada", "_"), CASOS)
def test_a_gsm7_de_un_texto_sin_marcas_da_lo_mismo_que_del_original(entrada, _) -> None:
    assert a_gsm7(sin_marcas(entrada)) == a_gsm7(entrada)
