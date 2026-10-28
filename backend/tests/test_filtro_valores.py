r"""El filtro de valores en el nucleo (T-FV-B1, RF-67/RF-68): `no_en`, el vacio y el escape.

- `no_en` («no es ninguno de»): uno o mas valores, en texto, numero y fecha.
- El ELEMENTO VACIO de una lista (`campo:en:A|`) es «(vacio)»: `None` en `Filtro.valores`, solo en
  `en`/`no_en` de un texto. En numero y fecha sigue siendo un 400, como hoy.
- Escape en la sintaxis: `\|` es una barra literal y `\\` una barra invertida. Es TOLERANTE: una `\`
  seguida de otro caracter, o al final, queda literal, para que un filtro guardado con una barra
  suelta se lea igual que antes.

Datos sinteticos.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.core.entities.cartera import (
    OPERADORES_DE_LISTA,
    OPERADORES_POR_TIPO,
    VALORES_POR_OPERADOR,
    ConsultaInvalida,
    Filtro,
    Operador,
    TipoDato,
)
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.core.services.seleccion_cartera.expresiones import (
    escapar_valor,
    parsear_filtro,
    partir_valores,
)
from tests.campos_adicionales_memoria import catalogo_con

BARRA = chr(92)  # la barra invertida
CATALOGO = CatalogoCartera()


def parsear(crudo: str, catalogo: CatalogoCartera = CATALOGO) -> Filtro:
    filtro = parsear_filtro(crudo, catalogo)
    catalogo.validar_filtro(filtro)
    return filtro


# --- El operador ---------------------------------------------------------------------------------


def test_no_en_existe_y_se_comporta_como_en_en_la_tabla_de_operadores() -> None:
    assert Operador("no_en") is Operador.NO_EN
    assert VALORES_POR_OPERADOR[Operador.NO_EN] is None  # uno o mas, igual que `en`
    assert OPERADORES_DE_LISTA == {Operador.EN, Operador.NO_EN}


@pytest.mark.parametrize(
    ("tipo", "admite"),
    [
        (TipoDato.TEXTO, True),
        (TipoDato.NUMERO, True),
        (TipoDato.FECHA, True),
        (TipoDato.BOOLEANO, False),  # un booleano solo tiene igual/vacio/no_vacio
    ],
)
def test_no_en_aplica_a_texto_numero_y_fecha_pero_no_a_un_booleano(tipo, admite) -> None:
    assert (Operador.NO_EN in OPERADORES_POR_TIPO[tipo]) is admite
    assert (Operador.EN in OPERADORES_POR_TIPO[tipo]) is admite


@pytest.mark.parametrize(
    ("crudo", "esperado"),
    [
        ("region:no_en:CUSCO SUR", ("CUSCO SUR",)),
        ("region:no_en:CUSCO SUR|PUNO SUR", ("CUSCO SUR", "PUNO SUR")),
        ("dias_atraso:no_en:5|9", (Decimal(5), Decimal(9))),
        ("fecha_vencimiento_cuota:no_en:2099-08-03", (date(2099, 8, 3),)),
    ],
)
def test_no_en_se_parsea_con_sus_valores_en_el_orden_escrito(crudo, esperado) -> None:
    filtro = parsear(crudo)

    assert filtro.operador is Operador.NO_EN and filtro.valores == esperado


def test_no_en_sin_valores_es_un_error() -> None:
    with pytest.raises(ConsultaInvalida, match="al menos un valor"):
        CATALOGO.validar_filtro(Filtro("region", Operador.NO_EN))


def test_no_en_sobre_un_booleano_no_aplica() -> None:
    with pytest.raises(ConsultaInvalida, match="no aplica"):
        CATALOGO.validar_filtro(Filtro("cliente_fallecido", Operador.NO_EN, (True,)))


def test_no_en_aparece_en_los_operadores_permitidos_de_un_error_de_operador() -> None:
    with pytest.raises(ConsultaInvalida) as error:
        parsear_filtro("region:inexistente:x", CATALOGO)

    assert "no_en" in str(error.value)


# --- El elemento vacio ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("crudo", "esperado"),
    [
        ("region:en:CUSCO SUR|", ("CUSCO SUR", None)),
        ("region:en:|CUSCO SUR", (None, "CUSCO SUR")),  # en cualquier posicion
        ("region:en:A||B", ("A", None, "B")),
        ("region:no_en:CUSCO SUR|", ("CUSCO SUR", None)),
        ("region:en:", (None,)),  # solo el vacio
        ("region:no_en:", (None,)),
        ("region:no_en:|", (None, None)),
        ("region:en:  ", (None,)),  # los espacios solos tambien son vacio, como en la ingesta
    ],
)
def test_un_elemento_vacio_de_la_lista_de_un_texto_es_none(crudo, esperado) -> None:
    filtro = parsear(crudo)

    assert filtro.valores == esperado
    assert "" not in filtro.valores  # la cartera no tiene «», solo NULL


def test_el_vacio_funciona_tambien_en_un_adicional_de_texto() -> None:
    catalogo = catalogo_con()

    filtro = parsear("ad_zona_comercial:no_en:SUR|", catalogo)

    assert filtro.valores == ("SUR", None)


@pytest.mark.parametrize(
    "crudo",
    [
        "dias_atraso:en:5|",  # numero
        "dias_atraso:no_en:",
        "fecha_vencimiento_cuota:en:2099-08-03|",  # fecha
        "fecha_vencimiento_cuota:no_en:",
    ],
)
def test_en_numero_y_fecha_un_elemento_vacio_sigue_siendo_un_error(crudo) -> None:
    with pytest.raises(ConsultaInvalida):
        parsear(crudo)


@pytest.mark.parametrize(
    "operador", [o for o in Operador if o not in OPERADORES_DE_LISTA], ids=lambda o: o.value
)
def test_el_vacio_solo_se_admite_en_un_en_y_un_no_en(operador) -> None:
    with pytest.raises(ConsultaInvalida, match="vacio"):
        CATALOGO.validar_filtro(Filtro("region", operador, (None,)))


def test_el_vacio_en_un_numero_o_una_fecha_ya_construidos_tambien_se_rechaza() -> None:
    with pytest.raises(ConsultaInvalida, match="vacio"):
        CATALOGO.validar_filtro(Filtro("dias_atraso", Operador.EN, (Decimal(5), None)))
    with pytest.raises(ConsultaInvalida, match="vacio"):
        CATALOGO.validar_filtro(Filtro("fecha_vencimiento_cuota", Operador.NO_EN, (None,)))


def test_la_conversion_del_catalogo_no_convierte_una_cadena_vacia_en_un_valor_de_lista() -> None:
    """`convertir` sigue siendo la de siempre; es el parseo quien decide que «» es el vacio."""
    assert CATALOGO.convertir("region", "") == ""
    assert parsear_filtro("region:igual:", CATALOGO).valores == ("",)  # otros operadores, igual
    assert parsear_filtro("region:en:", CATALOGO).valores == (None,)


# --- El escape -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("A|B", ["A", "B"]),
        ("A", ["A"]),
        ("", [""]),
        ("|", ["", ""]),
        (f"A{BARRA}|B", ["A|B"]),  # barra literal
        (f"A{BARRA}{BARRA}B", [f"A{BARRA}B"]),  # barra invertida
        (f"A{BARRA}{BARRA}|B", [f"A{BARRA}", "B"]),  # barra invertida y despues un separador
        (f"A{BARRA}{BARRA}{BARRA}|B", [f"A{BARRA}|B"]),
        (f"{BARRA}|", ["|"]),
        (f"{BARRA}|{BARRA}|", ["||"]),
        # tolerante: una barra suelta queda literal, sin error
        (f"A{BARRA}B", [f"A{BARRA}B"]),
        (f"A{BARRA}", [f"A{BARRA}"]),  # al final
        (f"A{BARRA}|", ["A|"]),  # ...salvo que sea el escape de la barra: queda literal
        (f"{BARRA}", [BARRA]),
        (f"A{BARRA}B|C{BARRA}", [f"A{BARRA}B", f"C{BARRA}"]),
        (f"C:{BARRA}carpeta|D", [f"C:{BARRA}carpeta", "D"]),
    ],
)
def test_partir_valores_respeta_el_escape_y_es_tolerante(texto, esperado) -> None:
    assert partir_valores(texto) == esperado


def test_un_valor_con_barra_literal_llega_entero_al_filtro() -> None:
    filtro = parsear(f"region:en:A{BARRA}|B|C")

    assert filtro.valores == ("A|B", "C")


def test_un_filtro_antiguo_con_una_barra_suelta_se_lee_igual_que_antes() -> None:
    filtro = parsear(f"region:igual:RUTA{BARRA}X")

    assert filtro.valores == (f"RUTA{BARRA}X",)  # sin 400


@pytest.mark.parametrize(
    "valor",
    [
        "simple",
        "con|barra",
        f"con{BARRA}invertida",
        f"mezcla{BARRA}|{BARRA}{BARRA}|",
        "|",
        BARRA,
        "||",
        "",
    ],
)
def test_escapar_y_partir_son_inversos(valor) -> None:
    lista = ["otro", valor, "ultimo"]

    escrita = "|".join(escapar_valor(v) for v in lista)

    assert partir_valores(escrita) == lista


def test_ida_y_vuelta_aleatoria_del_escape() -> None:
    import random

    azar = random.Random(20261028)
    alfabeto = ["a", "B", " ", "|", BARRA, ":", "ñ"]
    for _ in range(500):
        lista = [
            "".join(azar.choice(alfabeto) for _ in range(azar.randint(0, 6)))
            for _ in range(azar.randint(1, 4))
        ]

        assert partir_valores("|".join(escapar_valor(v) for v in lista)) == lista
