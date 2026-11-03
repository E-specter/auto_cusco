"""Las funciones `nombres` y `apellidos` del motor de texto (T-HI-B1, RF-44 ampliado).

Parten por la PRIMERA coma un `APELLIDOS,NOMBRES` (el titular de la sabana) y recortan los espacios
de los extremos de cada parte; nada mas cambia (la `/` entre apellidos se conserva). Sin coma,
`nombres` devuelve el texto completo recortado y `apellidos` devuelve vacio (supuesto de RF-44).
Datos sinteticos: «APELLIDO1/APELLIDO2,NOMBRE1 NOMBRE2», nunca nombres reales.
"""

import random

import pytest

from app.core.entities.texto_enriquecido import CodigoTexto, ExpresionInvalida, TipoValor
from app.core.services.texto_enriquecido import evaluador
from app.core.services.texto_enriquecido.funciones import REGISTRO
from tests.test_texto_enriquecido_funciones import VARIABLES, _evaluar, _texto

TITULAR = "APELLIDO1/APELLIDO2,NOMBRE1 NOMBRE2"
SEMILLA = 20261102


def _cota(plantilla: str) -> int | None:
    return evaluador.compilar_texto(plantilla, VARIABLES).cota


# --- Lo basico ----------------------------------------


def test_el_ejemplo_de_rf_44() -> None:
    assert _texto("[@t | nombres]", t=TITULAR) == "NOMBRE1 NOMBRE2"
    assert _texto("[@t | apellidos]", t=TITULAR) == "APELLIDO1/APELLIDO2"


@pytest.mark.parametrize(
    ("entrada", "nombres", "apellidos"),
    [
        ("A,B", "B", "A"),
        ("  A1 A2  ,  B1 B2  ", "B1 B2", "A1 A2"),  # espacios alrededor de cada parte
        ("A1/A2,B1", "B1", "A1/A2"),  # la `/` se conserva
        ("A1 / A2,B1", "B1", "A1 / A2"),  # y los espacios de adentro tambien
        ("A,B,C", "B,C", "A"),  # varias comas: corta en la PRIMERA
        ("A,,B", ",B", "A"),
        ("A,", "", "A"),  # coma al final: no hay nombres
        (",B", "B", ""),  # coma al principio: no hay apellidos
        (",", "", ""),
        ("A  B , C   D", "C   D", "A  B"),  # nada mas cambia: los espacios internos se quedan
        ("\tA,\nB \n", "B", "A"),  # tabuladores y saltos de los extremos tambien se recortan
    ],
)
def test_con_coma_parte_por_la_primera_y_recorta_los_extremos(entrada, nombres, apellidos) -> None:
    assert _texto("[@t | nombres]", t=entrada) == nombres
    assert _texto("[@t | apellidos]", t=entrada) == apellidos


@pytest.mark.parametrize(
    ("entrada", "nombres"),
    [("NOMBRE1 NOMBRE2", "NOMBRE1 NOMBRE2"), ("  NOMBRE1  ", "NOMBRE1"), ("A/B", "A/B")],
)
def test_sin_coma_nombres_es_todo_el_texto_recortado_y_apellidos_queda_vacio(
    entrada, nombres
) -> None:
    assert _texto("[@t | nombres]", t=entrada) == nombres
    assert _texto("[@t | apellidos]", t=entrada) == ""


def test_solo_cambia_lo_que_dice_ni_tildes_ni_mayusculas() -> None:
    assert _texto("[@t | nombres]", t="Peña/Núñez, José Ñandú") == "José Ñandú"
    assert _texto("[@t | apellidos]", t="Peña/Núñez, José Ñandú") == "Peña/Núñez"


# --- Vacio (RF-45) y encadenado ----------------------------------------


@pytest.mark.parametrize("funcion", ["nombres", "apellidos"])
@pytest.mark.parametrize("vacio", ["", None])
def test_una_entrada_vacia_se_trata_como_con_las_demas_funciones_de_texto(funcion, vacio) -> None:
    igual_que = _evaluar("[@t | mayusculas]", t=vacio)

    resultado = _evaluar(f"[@t | {funcion}]", t=vacio)

    assert resultado.texto == igual_que.texto == ""
    assert resultado.problemas == igual_que.problemas == ()


@pytest.mark.parametrize("funcion", ["nombres", "apellidos"])
def test_una_entrada_de_solo_espacios_queda_vacia(funcion) -> None:
    assert _texto(f"[@t | {funcion}]", t="   ") == ""


def test_una_variable_vacia_deja_vacia_su_parte_y_conserva_el_resto_del_texto() -> None:
    assert _texto("Estimado [@t | nombres], buenos dias", t=None) == "Estimado , buenos dias"
    assert _texto("Estimado [@t | nombres], buenos dias", t=TITULAR) == (
        "Estimado NOMBRE1 NOMBRE2, buenos dias"
    )


def test_con_si_vacio_el_valor_alternativo_cubre_el_vacio() -> None:
    assert _texto('[@t | nombres | si_vacio("cliente")]', t="APELLIDO1,") == "cliente"
    assert _texto('[@t | apellidos | si_vacio("cliente")]', t="NOMBRE1 NOMBRE2") == "cliente"


def test_se_encadena_con_otras_funciones_de_texto() -> None:
    assert _texto("[@t | nombres | mayusculas]", t="apellido1,nombre1 nombre2") == "NOMBRE1 NOMBRE2"
    assert _texto("[@t | nombres | capitalizar]", t=TITULAR) == "Nombre1 nombre2"
    assert _texto("[@t | apellidos | primeros(9)]", t=TITULAR) == "APELLIDO1"
    assert _texto('[@t | apellidos | reemplazar("/", " ")]', t=TITULAR) == "APELLIDO1 APELLIDO2"
    assert _texto("[@t | nombres | primeros(7) | minusculas]", t=TITULAR) == "nombre1"


def test_se_pueden_usar_las_dos_en_el_mismo_texto() -> None:
    plantilla = '[@t | nombres] [@t | apellidos | reemplazar("/", " ")]'

    assert _texto(plantilla, t=TITULAR) == "NOMBRE1 NOMBRE2 APELLIDO1 APELLIDO2"


# --- Tipos (RF-46) y catalogo ----------------------------------------


@pytest.mark.parametrize("funcion", ["nombres", "apellidos"])
@pytest.mark.parametrize("variable", ["n", "f", "b"])
def test_solo_aceptan_texto_y_se_validan_como_las_demas(funcion, variable) -> None:
    with pytest.raises(ExpresionInvalida) as error:
        evaluador.compilar_texto(f"[@{variable} | {funcion}]", VARIABLES)

    assert error.value.problemas[0].codigo is CodigoTexto.TIPO_INCOMPATIBLE


@pytest.mark.parametrize("funcion", ["nombres", "apellidos"])
def test_no_llevan_parametros_y_uno_sobra(funcion) -> None:
    with pytest.raises(ExpresionInvalida):
        evaluador.compilar_texto(f"[@t | {funcion}(2)]", VARIABLES)


@pytest.mark.parametrize("funcion", ["nombres", "apellidos"])
def test_estan_en_el_registro_con_su_ficha(funcion) -> None:
    ficha = REGISTRO[funcion]

    assert ficha.familia == "texto"
    assert ficha.recibe == (TipoValor.TEXTO,) and ficha.devuelve is TipoValor.TEXTO
    assert ficha.parametros == ()
    assert ficha.clave_nombre == f"textoEnriquecido.funcion.{funcion}.nombre"
    assert ficha.clave_descripcion == f"textoEnriquecido.funcion.{funcion}.descripcion"


# --- La cota de largo ----------------------------------------


@pytest.mark.parametrize("funcion", ["nombres", "apellidos"])
def test_la_cota_es_la_de_la_entrada(funcion) -> None:
    assert _cota(f"[@t | {funcion}]") is None  # sin cota de entrada, sin cota de salida
    assert _cota(f"[@t | primeros(12) | {funcion}]") == 12
    assert _cota(f"[@t | {funcion} | primeros(5)]") == 5
    assert _cota(f"[@t | primeros(12) | {funcion} | mayusculas]") == 12


# --- Propiedades ----------------------------------------


def _texto_al_azar(azar: random.Random, largo: int) -> str:
    alfabeto = ["A", "b", "ñ", " ", " ", "/", ",", ",", "\t", "1"]
    return "".join(azar.choice(alfabeto) for _ in range(azar.randint(0, largo)))


def test_con_coma_apellidos_coma_nombres_reconstruye_la_entrada_sin_extremos() -> None:
    azar = random.Random(SEMILLA)
    casos = 0
    for _ in range(3000):
        texto = _texto_al_azar(azar, 25)
        if "," not in texto:
            continue
        casos += 1
        antes, _, despues = texto.partition(",")

        apellidos = _evaluar("[@t | apellidos]", t=texto).texto
        nombres = _evaluar("[@t | nombres]", t=texto).texto

        assert f"{apellidos},{nombres}" == f"{antes.strip()},{despues.strip()}", texto
        assert apellidos == apellidos.strip() and nombres == nombres.strip()
    assert casos > 1000  # la propiedad se probo de verdad


def test_la_cota_nunca_es_menor_que_el_largo_del_resultado() -> None:
    azar = random.Random(SEMILLA + 1)
    for _ in range(2000):
        texto = _texto_al_azar(azar, 30)
        n = azar.randint(1, 30)
        for funcion in ("nombres", "apellidos"):
            compilado = evaluador.compilar_texto(f"[@t | primeros({n}) | {funcion}]", VARIABLES)

            resultado = compilado.evaluar({"t": texto})

            assert compilado.cota == n
            assert len(resultado.texto) <= compilado.cota, (texto, n, funcion)


def test_nunca_alargan_el_texto_y_sus_partes_caben_en_la_entrada() -> None:
    azar = random.Random(SEMILLA + 2)
    for _ in range(2000):
        texto = _texto_al_azar(azar, 30)
        if not texto.strip():
            continue
        nombres = _evaluar("[@t | nombres]", t=texto).texto
        apellidos = _evaluar("[@t | apellidos]", t=texto).texto

        assert len(nombres) <= len(texto) and len(apellidos) <= len(texto)
        assert len(nombres) + len(apellidos) <= len(texto) - ("," in texto)


def test_sin_coma_las_dos_partes_son_el_texto_recortado_y_vacio() -> None:
    azar = random.Random(SEMILLA + 3)
    for _ in range(1000):
        texto = _texto_al_azar(azar, 20).replace(",", "")
        if not texto.strip():
            continue

        assert _evaluar("[@t | nombres]", t=texto).texto == texto.strip()
        assert _evaluar("[@t | apellidos]", t=texto).texto == ""
