"""`vacia` y `normalizar_nombre` dan lo mismo que las copias que reemplazaron (T-MM-C10, L-B1).

`normalizar_nombre` decide la unicidad de selecciones, definiciones y versiones de speech, y con
ella el 409; `vacia` decide que cuenta como dato en las celdas, la campana y la segmentacion.
Las referencias de abajo son el cuerpo de cada copia borrada: la tabla es la regresion de la nueva.
"""

import pytest

from app.core.entities.nombres import normalizar_nombre
from app.core.entities.valores import vacia

# Las cuatro copias de `vacia`: celdas.py (`== ""`) y las otras tres (`not strip()`).
COPIAS_DE_VACIA = (
    lambda v: v is None or (isinstance(v, str) and v.strip() == ""),
    lambda v: v is None or (isinstance(v, str) and not v.strip()),
)
# Las tres copias de `normalizar_nombre`: definiciones, selecciones y versiones de speech.
COPIA_DE_NORMALIZAR = lambda nombre: nombre.strip().casefold()  # noqa: E731

VALORES = [
    None,
    "",
    " ",
    "  ",
    "\t",
    "\n",
    " ",
    " ",
    "a",
    " a ",
    "0",
    0,
    0.0,
    False,
    True,
    1,
    [],
    (),
    {},
    b"",
]
NOMBRES = [
    "",
    " ",
    "Ana",
    " ANA ",
    "ana maria",
    "Ana  Maria",
    "Straße",
    "STRASSE",
    "Caña",
    "CAÑA",
    "cana",
    "é",
    "é",
    "İ",
    "ﬁ",
    "x\ty",
    "\t x \n",
]


@pytest.mark.parametrize("valor", VALORES, ids=repr)
def test_vacia_da_lo_mismo_que_cada_copia(valor) -> None:
    esperado = {copia(valor) for copia in COPIAS_DE_VACIA}

    assert esperado == {vacia(valor)}


def test_vacia_es_none_o_texto_en_blanco_y_nada_mas() -> None:
    assert [v for v in VALORES if vacia(v)] == [None, "", " ", "  ", "\t", "\n", " ", " "]


@pytest.mark.parametrize("nombre", NOMBRES, ids=repr)
def test_normalizar_nombre_da_lo_mismo_que_cada_copia(nombre) -> None:
    assert normalizar_nombre(nombre) == COPIA_DE_NORMALIZAR(nombre)


def test_normalizar_nombre_quita_los_extremos_pero_no_los_espacios_del_medio() -> None:
    assert normalizar_nombre("  Ana  Maria\t") == "ana  maria"


def test_normalizar_nombre_no_distingue_mayusculas_ni_la_eszett() -> None:
    assert normalizar_nombre("Straße") == normalizar_nombre("STRASSE") == "strasse"


def test_normalizar_nombre_distingue_las_tildes() -> None:
    assert normalizar_nombre("Caña") != normalizar_nombre("cana")
