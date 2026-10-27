"""La descripcion de campana de MOWA MES admite 100 caracteres (RF-MM-04, S-MM-3; T-MM-B10).

- La API rechaza (422) una descripcion de mas de 100 UNIDADES UTF-16 (las que cuenta `.length` en el
  navegador: un emoji son 2), medidas sobre el texto SIN los espacios de los extremos, que es lo que
  la campana registra. Lo hacen la previsualizacion y la creacion: no hay otro camino de entrada.
- La descripcion sugerida (cartera y resumen de filtros) tambien cabe en 100: se acorta por filtros
  enteros, cerrada con `...`; si ni el primero cabe, salen las primeras 97 unidades y `...`.

Los caracteres especiales van con su nombre Unicode: el archivo es ASCII. Datos sinteticos.
"""

import random

import pytest
from fastapi.testclient import TestClient

from app.core.entities.mowa_mes_campana import LARGO_MAXIMO_DESCRIPCION, largo_utf16
from app.core.services.plataformas.mowa_mes.campana import descripcion_sugerida, resumen_filtro
from app.core.services.seleccion_cartera import expresiones
from app.main import app
from tests.test_api_mowa_mes_campanas import CUERPO, Entorno, _cliente, _crear

EMOJI = "\N{GRINNING FACE}"  # fuera del plano basico: 2 unidades UTF-16
O_TILDE = "\N{LATIN SMALL LETTER O WITH ACUTE}"  # 1 unidad
PREFIJO = "CajaCusco"


@pytest.fixture(autouse=True)
def _limpiar_dependencias():
    yield
    app.dependency_overrides.clear()


def _previsualizar(client: TestClient, descripcion):
    return client.post(
        "/mowa-mes/campanas/previsualizacion", json={**CUERPO, "descripcion": descripcion}
    )


def _crear_con(client: TestClient, descripcion):
    return _crear(client, descripcion=descripcion)


# --- El largo en unidades UTF-16 ----------------------------------------------------------------


def test_largo_utf16_cuenta_las_unidades_del_navegador() -> None:
    assert largo_utf16("") == 0
    assert largo_utf16("abc") == 3
    assert largo_utf16(O_TILDE * 5) == 5  # con tildes da lo mismo que len
    assert largo_utf16(EMOJI) == 2 and len(EMOJI) == 1
    assert largo_utf16("a" + EMOJI + "b") == 4
    assert largo_utf16("\ud800") == 1  # una mitad suelta (JSON la deja pasar) mide 1 y no falla


def test_el_tope_es_100() -> None:
    assert LARGO_MAXIMO_DESCRIPCION == 100


# --- La API rechaza la descripcion de mas de 100 --------------------------------------------------


@pytest.mark.parametrize(
    ("descripcion", "estado"),
    [
        ("a" * 100, 200),
        ("a" * 101, 422),
        ("  " + "a" * 100 + "  ", 200),  # los espacios de los extremos no cuentan
        ("  " + "a" * 101 + "  ", 422),
        (O_TILDE * 100, 200),
        (O_TILDE * 101, 422),
        (EMOJI * 50, 200),  # 100 unidades
        (EMOJI * 51, 422),  # 102 unidades, aunque sean 51 caracteres
        ("a" * 98 + EMOJI, 200),  # 100 unidades, 99 caracteres
        ("a" * 99 + EMOJI, 422),  # 101 unidades, 100 caracteres: len() lo dejaria pasar
        ("a b " * 25 + "z" * 1, 422),  # 101 con espacios en el medio
    ],
)
def test_la_api_acepta_hasta_100_unidades_y_rechaza_mas(descripcion: str, estado: int) -> None:
    client = _cliente(Entorno())

    previa = _previsualizar(client, descripcion)
    creada = _crear_con(client, descripcion)

    assert previa.status_code == estado, previa.text
    assert creada.status_code == (201 if estado == 200 else 422), creada.text


def test_se_registra_la_descripcion_sin_los_espacios_de_los_extremos() -> None:
    client = _cliente(Entorno())

    creada = _crear_con(client, "   " + "a" * 100 + " ")

    assert creada.status_code == 201
    assert creada.json()["descripcion"] == "a" * 100


@pytest.mark.parametrize("descripcion", [None, "", "   ", "\t\n"])
def test_una_descripcion_vacia_o_en_blanco_sigue_cayendo_en_la_sugerida(descripcion) -> None:
    client = _cliente(Entorno())

    previa = _previsualizar(client, descripcion).json()
    creada = _crear_con(client, descripcion).json()

    assert previa["descripcion"] == previa["descripcion_sugerida"] == PREFIJO
    assert creada["descripcion"] == PREFIJO


def test_el_rechazo_es_un_422_de_validacion_sobre_el_campo_descripcion() -> None:
    client = _cliente(Entorno())

    respuesta = _previsualizar(client, "a" * 101)

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"][0]["loc"] == ["body", "descripcion"]


def test_el_contrato_dice_el_tope_y_la_unidad() -> None:
    campo = app.openapi()["components"]["schemas"]["PeticionCampanaEntrada"]["properties"][
        "descripcion"
    ]

    assert "100" in campo["description"] and "UTF-16" in campo["description"]
    assert "maxLength" not in str(campo)  # el tope no es de puntos de codigo: lo dice el texto


# --- La descripcion sugerida cabe en 100 ---------------------------------------------------------


def _filtro_con(equis: int, valor_extra: str = ""):
    """Un filtro `titular contiene xxx...<extra>`: su resumen son 17 caracteres y el valor."""
    return expresiones.parsear_filtro(f"titular:contiene:{'x' * equis}{valor_extra}")


def _filtro(resumen_largo: int, valor_extra: str = ""):
    """Un filtro cuyo resumen mide `resumen_largo` CARACTERES (el emoji, de extra, cuenta 1)."""
    return _filtro_con(resumen_largo - 17 - len(valor_extra), valor_extra)


def _resumenes(filtros) -> list[str]:
    return [resumen_filtro(f) for f in filtros]


def test_exactamente_100_sale_igual_que_antes_sin_los_tres_puntos() -> None:
    filtros = [_filtro(90)]  # "CajaCusco " (10) + 90 = 100

    sugerida = descripcion_sugerida(filtros)

    assert len(sugerida) == 100 and not sugerida.endswith("...")
    assert sugerida == f"{PREFIJO} {resumen_filtro(filtros[0])}"


def test_101_con_un_solo_filtro_que_no_cabe_sale_el_corte_de_97_y_los_tres_puntos() -> None:
    filtros = [_filtro(91)]  # 101 en total
    completa = f"{PREFIJO} {resumen_filtro(filtros[0])}"

    sugerida = descripcion_sugerida(filtros)

    assert sugerida == completa[:97] + "..." and len(sugerida) == 100


def test_sin_filtros_es_solo_el_prefijo() -> None:
    assert descripcion_sugerida([]) == PREFIJO


def test_el_corte_justo_despues_del_segundo_filtro_y_justo_antes_del_segundo() -> None:
    primero, tercero = _filtro(40), _filtro(30)
    # "CajaCusco " + 40 + ", " + 45 + "..." = 100: caben los dos primeros.
    cabe = [primero, _filtro(45), tercero]
    # Con 46 el segundo ya no cabe junto al primero: sale solo el primero.
    no_cabe = [primero, _filtro(46), tercero]

    con_dos = descripcion_sugerida(cabe)
    con_uno = descripcion_sugerida(no_cabe)

    assert con_dos == f"{PREFIJO} {', '.join(_resumenes(cabe[:2]))}..." and len(con_dos) == 100
    assert con_uno == f"{PREFIJO} {resumen_filtro(primero)}..." and len(con_uno) == 53


def test_se_corta_en_el_primer_filtro_que_no_cabe_y_no_salta_a_uno_posterior_mas_corto() -> None:
    filtros = [_filtro(40), _filtro(80), _filtro(5)]  # el tercero cabria solo, el segundo no

    sugerida = descripcion_sugerida(filtros)

    assert sugerida == f"{PREFIJO} {resumen_filtro(filtros[0])}..."


def test_el_primer_filtro_de_mas_de_97_sale_cortado_a_97_unidades() -> None:
    filtros = [_filtro(120)]

    sugerida = descripcion_sugerida(filtros)

    assert sugerida == f"{PREFIJO} {resumen_filtro(filtros[0])}"[:97] + "..."
    assert largo_utf16(sugerida) == 100


def test_un_emoji_que_cae_en_el_corte_no_se_parte() -> None:
    # "CajaCusco " + "titular contiene " son 27 unidades; 69 x's llegan a 96 y el emoji (2) pasaria
    # de 97: queda fuera entero. Con 68 x's el emoji termina justo en la unidad 97 y entra.
    resto = "y" * 40
    afuera = descripcion_sugerida([_filtro_con(69, EMOJI + resto)])
    adentro = descripcion_sugerida([_filtro_con(68, EMOJI + resto)])

    assert afuera == PREFIJO + " titular contiene " + "x" * 69 + "..." and largo_utf16(afuera) == 99
    assert adentro.endswith(EMOJI + "...") and largo_utf16(adentro) == 100
    for texto in (afuera, adentro):
        texto.encode("utf-16-le")  # sin mitades sueltas: no lanza


def test_un_emoji_en_un_filtro_entero_cuenta_dos_para_que_quepa() -> None:
    # Dos filtros de 46 y 40 unidades (el primero con un emoji): 10 + 46 + 2 + 40 + 3 = 101.
    primero = _filtro(45, EMOJI)  # 45 caracteres = 46 unidades con el emoji
    segundo = _filtro(40)
    tercero = _filtro(40)

    sugerida = descripcion_sugerida([primero, segundo, tercero])

    assert sugerida == f"{PREFIJO} {resumen_filtro(primero)}..."  # el segundo ya no cabe


def test_propiedad_la_sugerida_siempre_cabe_y_solo_se_acorta_cuando_hace_falta() -> None:
    azar = random.Random(20261027)
    for _ in range(3_000):
        filtros = [
            _filtro(azar.randint(22, 130), (EMOJI + O_TILDE) if azar.random() < 0.3 else "")
            for _ in range(azar.randint(0, 6))
        ]
        resumenes = _resumenes(filtros)
        completa = f"{PREFIJO} {', '.join(resumenes)}" if resumenes else PREFIJO

        sugerida = descripcion_sugerida(filtros)

        assert largo_utf16(sugerida) <= LARGO_MAXIMO_DESCRIPCION, repr(sugerida)
        sugerida.encode("utf-16-le")  # nunca una mitad de par suelta
        if largo_utf16(completa) <= LARGO_MAXIMO_DESCRIPCION:
            assert sugerida == completa
            continue
        assert sugerida.endswith("..."), repr(sugerida)
        assert not sugerida.endswith(", ...") and not sugerida.endswith(",...")
        sin_puntos = sugerida[:-3]
        assert completa.startswith(sin_puntos), repr(sugerida)  # sin los tres puntos, un prefijo
        enteros = [
            n
            for n in range(1, len(resumenes) + 1)
            if sugerida == f"{PREFIJO} {', '.join(resumenes[:n])}..."
        ]
        if enteros:  # filtros enteros: y el siguiente ya no cabria
            n = enteros[0]
            siguiente = f"{PREFIJO} {', '.join(resumenes[: n + 1])}..."
            assert n == len(resumenes) or largo_utf16(siguiente) > LARGO_MAXIMO_DESCRIPCION
        else:  # el corte de 97: ni el primer filtro entero cabe
            assert largo_utf16(f"{PREFIJO} {resumenes[0]}...") > LARGO_MAXIMO_DESCRIPCION
            assert largo_utf16(sugerida) in (99, 100)
