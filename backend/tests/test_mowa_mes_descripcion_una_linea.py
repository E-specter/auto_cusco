"""La descripcion de campana de MOWA MES es de UNA sola linea (RF-MM-04; T-MM-B11).

El campo "Descripcion de Campana" de MES no admite saltos. Cinco se cambian por UN espacio: CRLF
(que cuenta como uno), CR, LF, U+2028 y U+2029. La API lo hace ANTES de medir los 100 y devuelve el
valor ya cambiado, asi que la campana registrada nunca lleva saltos. VT, FF y U+0085 no se tocan
(nadie los decidio). Tambien la sugerida: un valor de filtro de texto puede traer un salto adentro.

Los caracteres especiales van con su nombre Unicode: el archivo es ASCII. Datos sinteticos.
"""

import random

import pytest
from fastapi.testclient import TestClient

from app.core.entities.mowa_mes_campana import LARGO_MAXIMO_DESCRIPCION, largo_utf16, una_linea
from app.core.services.plataformas.mowa_mes.campana import descripcion_sugerida, resumen_filtro
from app.core.services.seleccion_cartera import expresiones
from app.main import app
from tests.test_api_mowa_mes_campanas import CUERPO, Entorno, _cliente, _crear

CR, LF, CRLF = "\r", "\n", "\r\n"
LS = "\N{LINE SEPARATOR}"  # U+2028
PS = "\N{PARAGRAPH SEPARATOR}"  # U+2029
NEL = "\N{NEXT LINE}"  # U+0085: no se toca
VT, FF = "\x0b", "\x0c"  # no se tocan
CINCO = [CR, LF, CRLF, LS, PS]
PREFIJO = "CajaCusco"


@pytest.fixture(autouse=True)
def _limpiar_dependencias():
    yield
    app.dependency_overrides.clear()


def _previsualizar(client: TestClient, descripcion, **extra):
    return client.post(
        "/mowa-mes/campanas/previsualizacion", json={**CUERPO, "descripcion": descripcion, **extra}
    )


def _crear_con(client: TestClient, descripcion, **extra):
    return _crear(client, descripcion=descripcion, **extra)


# --- La regla ------------------------------------------------------------------------------------


@pytest.mark.parametrize("salto", CINCO)
def test_cada_uno_de_los_cinco_saltos_pasa_a_un_espacio(salto: str) -> None:
    assert una_linea(f"a{salto}b") == "a b"


def test_crlf_es_un_solo_espacio_y_no_dos() -> None:
    assert una_linea("a\r\nb") == "a b"
    assert una_linea("a\n\rb") == "a  b"  # al reves no es CRLF: son dos saltos
    assert una_linea("a\r\r\nb") == "a  b"  # un CR suelto y despues un CRLF


def test_los_espacios_seguidos_no_se_juntan() -> None:
    assert una_linea("a\n\nb") == "a  b"
    assert una_linea("a \n b") == "a   b"


@pytest.mark.parametrize("caracter", [VT, FF, NEL, "\t", "\x1c", "\x1f"])
def test_lo_que_nadie_decidio_queda_como_esta(caracter: str) -> None:
    assert una_linea(f"a{caracter}b") == f"a{caracter}b"


def test_una_linea_es_idempotente_y_no_toca_el_resto() -> None:
    texto = f"Campana{LF}sin{CRLF}tildes{PS}x{CR}y{LS}"

    assert una_linea(una_linea(texto)) == una_linea(texto)
    assert una_linea("Cobranza 2026: 9 <= dias") == "Cobranza 2026: 9 <= dias"


def test_propiedad_nunca_queda_un_salto_y_solo_crlf_pierde_un_caracter() -> None:
    azar = random.Random(20261029)
    alfabeto = ["a", "b", " ", VT, FF, NEL, *CINCO[:2], LS, PS]
    for _ in range(3_000):
        texto = "".join(azar.choice(alfabeto) for _ in range(azar.randint(0, 30)))

        salida = una_linea(texto)

        assert not any(s in salida for s in (CR, LF, LS, PS)), repr(texto)
        assert len(salida) == len(texto) - texto.count(CRLF), repr(texto)


# --- La API: se cambia antes de medir y se devuelve cambiado ------------------------------------


@pytest.mark.parametrize("salto", CINCO)
def test_la_campana_se_registra_sin_el_salto_con_cada_uno_de_los_cinco(salto: str) -> None:
    client = _cliente(Entorno())

    previa = _previsualizar(client, f"Campana{salto}uno").json()
    creada = _crear_con(client, f"Campana{salto}uno")
    consultada = client.get(f"/mowa-mes/campanas/{creada.json()['id']}").json()

    assert creada.status_code == 201
    assert previa["descripcion"] == creada.json()["descripcion"] == "Campana uno"
    assert consultada["descripcion"] == "Campana uno"


def test_los_saltos_de_los_extremos_desaparecen_con_el_strip() -> None:
    client = _cliente(Entorno())

    creada = _crear_con(client, f"{LF}{LF}abc{CRLF}").json()

    assert creada["descripcion"] == "abc"


def test_un_texto_de_100_con_un_crlf_adentro_mide_99_y_se_acepta() -> None:
    client = _cliente(Entorno())
    descripcion = "a" * 49 + CRLF + "b" * 49  # 100 caracteres crudos, 99 ya cambiado

    assert len(descripcion) == 100
    assert _previsualizar(client, descripcion).status_code == 200
    assert _crear_con(client, descripcion).json()["descripcion"] == "a" * 49 + " " + "b" * 49


def test_se_mide_despues_de_cambiar_los_saltos_no_antes() -> None:
    client = _cliente(Entorno())
    # 101 crudos con un CRLF adentro, pero 100 ya cambiado: se acepta; antes se rechazaba.
    cabe = "a" * 49 + CRLF + "b" * 50
    # Con un LF son 101 tambien cambiado: se rechaza.
    no_cabe = "a" * 50 + LF + "b" * 50

    assert len(cabe) == 101 and largo_utf16(una_linea(cabe)) == 100
    assert _previsualizar(client, cabe).status_code == 200
    assert _crear_con(client, no_cabe).status_code == 422
    assert _previsualizar(client, no_cabe).status_code == 422


def test_100_con_un_salto_al_final_se_acepta_y_se_guarda_sin_el() -> None:
    client = _cliente(Entorno())

    creada = _crear_con(client, "a" * 100 + LF)

    assert creada.status_code == 201
    assert creada.json()["descripcion"] == "a" * 100


@pytest.mark.parametrize("caracter", [VT, NEL])
def test_vt_y_u0085_adentro_no_se_tocan_ni_en_lo_guardado(caracter: str) -> None:
    client = _cliente(Entorno())

    creada = _crear_con(client, f"a{caracter}b").json()

    assert creada["descripcion"] == f"a{caracter}b"


def test_una_descripcion_en_blanco_con_saltos_cae_en_la_sugerida() -> None:
    client = _cliente(Entorno())

    creada = _crear_con(client, f"{LF}{CRLF}{LS}").json()

    assert creada["descripcion"] == PREFIJO


def test_el_contrato_dice_que_los_saltos_pasan_a_un_espacio() -> None:
    campo = app.openapi()["components"]["schemas"]["PeticionCampanaEntrada"]["properties"][
        "descripcion"
    ]

    assert "salto" in campo["description"] and "espacio" in campo["description"]


# --- La sugerida tampoco lleva saltos ------------------------------------------------------------


def _filtro(texto: str):
    return expresiones.parsear_filtro(texto)


def test_un_valor_de_filtro_con_un_salto_da_una_sugerida_de_una_linea() -> None:
    filtro = _filtro(f"titular:contiene:a{LF}b")

    assert f"a{LF}b" in resumen_filtro(filtro)  # el resumen en si todavia lo trae
    assert descripcion_sugerida([filtro]) == f"{PREFIJO} titular contiene a b"


def test_el_operador_en_con_un_salto_en_un_valor_une_con_barra_sin_salto() -> None:
    filtro = _filtro(f"titular:en:a{CRLF}b|c")

    assert descripcion_sugerida([filtro]) == f"{PREFIJO} titular en a b/c"


def test_la_sugerida_con_un_salto_se_previsualiza_y_se_guarda_sin_el() -> None:
    client = _cliente(Entorno())
    filtros = [f"titular:distinto:a{LF}b"]  # un filtro valido que no deja fuera a nadie

    previa = _previsualizar(client, None, filtros=filtros).json()
    creada = _crear_con(client, None, filtros=filtros)

    esperada = f"{PREFIJO} titular <> a b"
    assert previa["descripcion_sugerida"] == previa["descripcion"] == esperada
    assert creada.status_code == 201 and creada.json()["descripcion"] == esperada


def test_los_100_de_la_sugerida_se_miden_despues_de_cambiar_el_salto() -> None:
    # Resumenes de 90 y 91 caracteres ya cambiado el CRLF (en crudo, uno mas): con "CajaCusco "
    # (10) el primero queda en 100 justo y NO se acorta; el segundo pasa de 100 y si.
    justo = _filtro(f"titular:contiene:{'x' * 70}{CRLF}yy")  # 17 + 70 + 1 + 2 = 90
    uno_mas = _filtro(f"titular:contiene:{'x' * 71}{CRLF}yy")  # 91

    assert descripcion_sugerida([justo]) == f"{PREFIJO} {una_linea(resumen_filtro(justo))}"
    assert largo_utf16(descripcion_sugerida([justo])) == LARGO_MAXIMO_DESCRIPCION
    assert descripcion_sugerida([uno_mas]).endswith("...")


def test_propiedad_la_sugerida_nunca_lleva_un_salto_y_siempre_cabe() -> None:
    azar = random.Random(20261030)
    saltos = [LF, CRLF, CR, LS, PS]
    for _ in range(2_000):
        filtros = [
            _filtro(
                "titular:contiene:"
                + "x" * azar.randint(1, 40)
                + azar.choice(saltos)
                + "y" * azar.randint(1, 40)
            )
            for _ in range(azar.randint(0, 5))
        ]

        sugerida = descripcion_sugerida(filtros)

        assert not any(s in sugerida for s in (CR, LF, LS, PS)), repr(sugerida)
        assert largo_utf16(sugerida) <= LARGO_MAXIMO_DESCRIPCION
