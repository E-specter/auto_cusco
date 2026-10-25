"""Variables de contexto constantes (B7): se evaluan una vez al compilar y quedan como texto fijo.

Lo que se cuida: con o sin plegado el resultado de cada fila es el mismo (texto, valor tipado y
problemas), la cota no cambia y sin constantes todo sigue igual que antes.
"""

import random
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.core.entities.texto_enriquecido import (
    ArgumentoVariable,
    CodigoTexto,
    Expresion,
    LlamadaFuncion,
    NodoTexto,
    NodoVariable,
    TipoValor,
)
from app.core.services.texto_enriquecido import evaluador, sintaxis
from app.core.services.texto_enriquecido.funciones import REGISTRO
from app.core.services.texto_enriquecido.funciones.base import Funcion

SEMILLA = 20260930
T, N, F = TipoValor.TEXTO, TipoValor.NUMERO, TipoValor.FECHA
VARIABLES = {"t": T, "u": T, "n": N, "m": N, "f": F, "tel": T}


def _compilar(plantilla: str, constantes=None):
    return evaluador.compilar_texto(plantilla, VARIABLES, constantes=constantes)


# --- cuando se pliega ---------------------------------------------------------------------------


def test_un_nodo_de_una_variable_constante_se_pliega_a_texto_fijo() -> None:
    compilada = _compilar("Hola [@t | mayusculas]!", {"t": "ana"})

    assert compilada.nodos_plegados == 1
    assert compilada.evaluar({}).texto == "Hola ANA!"
    assert compilada.variables == ()  # no lee nada de la fila
    assert compilada.es_valor_fijo


def test_una_variable_que_no_es_constante_no_se_pliega() -> None:
    compilada = _compilar("[@t] [@u]", {"t": "ana"})

    assert compilada.nodos_plegados == 1
    assert compilada.variables == ("u",)
    assert compilada.evaluar({"u": "luis"}).texto == "ana luis"
    assert not compilada.es_valor_fijo


def test_un_nodo_con_un_argumento_variable_no_constante_no_se_pliega() -> None:
    compilada = _compilar("[@n | sumar(@m)]", {"n": Decimal(1)})

    assert compilada.nodos_plegados == 0
    assert compilada.evaluar({"m": Decimal(2)}).texto == "3"


def test_un_nodo_con_argumentos_variables_tambien_constantes_se_pliega() -> None:
    compilada = _compilar("[@n | sumar(@m)]", {"n": Decimal(1), "m": Decimal(2)})

    assert compilada.nodos_plegados == 1
    assert compilada.evaluar({}).texto == "3"


def test_un_nodo_sin_funciones_de_una_constante_tambien_se_pliega() -> None:
    compilada = _compilar("[@f]", {"f": date(2026, 9, 5)})

    assert compilada.nodos_plegados == 1
    assert compilada.evaluar({}).texto == "2026-09-05"


def test_sin_constantes_no_se_pliega_nada_y_todo_sigue_igual() -> None:
    for constantes in (None, {}):
        compilada = _compilar("[@t | mayusculas] [@n | sumar(1)]", constantes)

        assert compilada.nodos_plegados == 0
        assert compilada.variables == ("t", "n")
        assert compilada.evaluar({"t": "a", "n": 1}).texto == "A 2"


def test_una_constante_vacia_se_pliega_a_vacio_y_si_vacio_actua() -> None:
    compilada = _compilar('[@t | si_vacio("sin dato")]|[@u | mayusculas]', {"t": None, "u": "  "})

    assert compilada.nodos_plegados == 2
    assert compilada.evaluar({}).texto == "sin dato|"


def test_la_constante_manda_sobre_el_valor_que_traiga_la_fila() -> None:
    compilada = _compilar("[@t | mayusculas]", {"t": "campana"})

    assert compilada.evaluar({"t": "otra"}).texto == "CAMPANA"


def test_una_constante_que_no_es_una_variable_del_catalogo_se_rechaza() -> None:
    with pytest.raises(ValueError, match="inventada"):
        _compilar("[@t]", {"inventada": "x"})


def test_se_evalua_una_sola_vez_al_compilar_y_no_por_fila() -> None:
    llamadas = []

    def _contar(valor: str) -> str:
        llamadas.append(valor)
        return valor.upper()

    registro = {
        **REGISTRO,
        "contar": Funcion("contar", "prueba", (T,), T, _contar),
    }
    expresion = sintaxis.leer("[@t | contar] [@u | contar]")

    plegada = evaluador.compilar(expresion, VARIABLES, registro=registro, constantes={"t": "a"})
    despues_de_compilar = len(llamadas)
    for _ in range(50):
        plegada.evaluar({"u": "b"})

    assert despues_de_compilar == 1  # el nodo constante, una vez
    assert len(llamadas) == 1 + 50  # y por fila solo el nodo de la fila
    llamadas.clear()
    sin_plegar = evaluador.compilar(expresion, VARIABLES, registro=registro)
    for _ in range(50):
        sin_plegar.evaluar({"t": "a", "u": "b"})
    assert len(llamadas) == 100


# --- problemas al compilar ------------------------------------------------------------------------


def test_un_problema_del_plegado_se_informa_al_compilar_con_su_ubicacion() -> None:
    compilada = _compilar("x [@n | sumar(1) | dividir(0)] y", {"n": Decimal(1)})

    (problema,) = compilada.problemas_plegados
    assert problema.codigo is CodigoTexto.DIVISION_POR_CERO
    assert (problema.nodo, problema.funcion) == (1, 1)


def test_un_problema_plegado_sale_igual_en_cada_fila_y_el_resto_del_texto_se_conserva() -> None:
    compilada = _compilar("x [@n | dividir(0)] [@u]", {"n": Decimal(1)})

    filas = [compilada.evaluar({"u": v}) for v in ("a", "b")]

    assert [f.texto for f in filas] == ["x  a", "x  b"]
    assert [f.problemas for f in filas] == [compilada.problemas_plegados] * 2


def test_una_constante_de_tipo_equivocado_es_un_problema_del_plegado() -> None:
    compilada = _compilar("[@n | sumar(1)]", {"n": "abc"})

    assert [p.codigo for p in compilada.problemas_plegados] == [CodigoTexto.NO_ES_NUMERO]
    assert compilada.evaluar({}).texto == ""


def test_una_constante_obligatoria_vacia_es_un_problema_del_plegado() -> None:
    expresion = Expresion((NodoVariable("t", (LlamadaFuncion("mayusculas"),), obligatoria=True),))

    compilada = evaluador.compilar(expresion, VARIABLES, constantes={"t": "   "})

    (problema,) = compilada.problemas_plegados
    assert problema.codigo is CodigoTexto.VARIABLE_OBLIGATORIA_VACIA
    assert problema.nodo == 0
    assert compilada.evaluar({}).problemas == (problema,)


def test_sin_problemas_no_hay_problemas_plegados() -> None:
    assert _compilar("[@t]", {"t": "a"}).problemas_plegados == ()
    assert _compilar("[@t]").problemas_plegados == ()


def test_un_telefono_invalido_como_constante_se_detecta_al_compilar_y_no_por_fila() -> None:
    compilada = _compilar("[@tel | enlace_whatsapp] hola", {"tel": "12345"})

    assert [p.codigo for p in compilada.problemas_plegados] == [CodigoTexto.TELEFONO_INVALIDO]
    assert compilada.evaluar({}).texto == " hola"


# --- lo que no cambia ---------------------------------------------------------------------------


def test_la_cota_no_cambia_por_plegar_el_enlace_sigue_midiendo_26() -> None:
    sin_plegar = _compilar("[@tel | enlace_whatsapp]")
    plegada = _compilar("[@tel | enlace_whatsapp]", {"tel": "900000123"})

    assert sin_plegar.cota == plegada.cota == 26
    assert len(plegada.evaluar({}).texto) == 26


def test_se_conserva_la_cota_del_nodo_no_el_largo_del_valor_plegado() -> None:
    sin_plegar = _compilar("[@t | primeros(8)]")
    plegada = _compilar("[@t | primeros(8)]", {"t": "ab"})

    assert plegada.evaluar({}).texto == "ab"
    assert sin_plegar.cota == plegada.cota == 8


def test_una_variable_sin_cota_sigue_sin_cota_aunque_este_plegada() -> None:
    assert _compilar("[@t]", {"t": "ab"}).cota is None


def test_el_valor_tipado_de_un_nodo_unico_plegado_es_el_de_siempre() -> None:
    plegada = _compilar("[@f | sumar_dias(3)]", {"f": date(2026, 9, 29)})
    sin_plegar = _compilar("[@f | sumar_dias(3)]")

    esperado = sin_plegar.evaluar({"f": date(2026, 9, 29)})
    obtenido = plegada.evaluar({})

    assert obtenido == esperado
    assert obtenido.valor == date(2026, 10, 2)
    assert plegada.es_variable_unica and plegada.tipo is F


def test_con_texto_alrededor_no_hay_valor_tipado_aunque_el_nodo_este_plegado() -> None:
    assert _compilar("S/ [@n]", {"n": Decimal(1)}).evaluar({}).valor is None


def test_la_cota_de_un_texto_con_partes_plegadas_es_la_de_antes() -> None:
    plantilla = (
        'a [@t | primeros(8)] b [@f | formato_fecha("dd/mm/aaaa")] c [@tel | enlace_whatsapp]'
    )
    constantes = {"t": "xy", "f": date(2026, 9, 5), "tel": "900000123"}

    assert _compilar(plantilla, constantes).cota == _compilar(plantilla).cota == 8 + 10 + 26 + 8


# --- propiedad: con y sin plegado, el mismo resultado -------------------------------------------

VALORES = {
    "t": [None, "", "  ", "abc", "Ñandú Pérez", "12"],
    "u": [None, "", "  ", "x", "luis"],
    "n": [None, Decimal(0), Decimal("2.5"), 3, "7", "abc", Decimal(-1)],
    "m": [None, Decimal(0), Decimal("2.5"), 3, Decimal("1E+2"), "no es numero"],
    "f": [None, date(2026, 9, 5), date(9999, 12, 31), "2026-01-02", "no es fecha"],
    "tel": [None, "900000001", "12", "  ", "900000123"],
}
# Por tipo de entrada: (funcion, tipo que devuelve). Los argumentos @u, @m y @n usan variables de
# la fila, que a veces son constantes y a veces no.
FUNCIONES_POR_TIPO = {
    T: [
        ("primeros(3)", T),
        ("mayusculas", T),
        ("recortar", T),
        ('si_vacio("x")', T),
        ("si_vacio(@u)", T),
        ("a_numero", N),
    ],
    N: [
        ("sumar(@m)", N),
        ("dividir(@m)", N),
        ("redondear(1)", N),
        ("multiplicar(2)", N),
        ("formato_numero(2)", T),
        ("a_texto", T),
    ],
    F: [
        ("sumar_dias(3)", F),
        ("sumar_dias(@n)", F),
        ('formato_fecha("dd/mm/aaaa")', T),
        ("a_texto", T),
    ],
}


def _cadena_al_azar(azar: random.Random, tipo: TipoValor) -> str:
    partes = []
    for _ in range(azar.randint(0, 3)):
        funcion, tipo = azar.choice(FUNCIONES_POR_TIPO[tipo])
        partes.append(funcion)
    return " | ".join(partes)


def _plantilla_al_azar(azar: random.Random) -> str:
    trozos = []
    for _ in range(azar.randint(1, 5)):
        if azar.random() < 0.35:
            trozos.append(azar.choice(["a", " ", "-", "| ", "x y"]))
            continue
        nombre = azar.choice(["t", "u", "n", "m", "f", "tel"])
        if nombre == "tel":
            cadena = azar.choice(["", "enlace_whatsapp", "enlace_whatsapp | primeros(12)"])
        else:
            cadena = _cadena_al_azar(azar, VARIABLES[nombre])
        trozos.append("[@" + " | ".join([nombre, *([cadena] if cadena else [])]) + "]")
    return "".join(trozos)


def _con_obligatorias(azar: random.Random, expresion: Expresion) -> Expresion:
    nodos = tuple(
        replace(n, obligatoria=True) if isinstance(n, NodoVariable) and azar.random() < 0.25 else n
        for n in expresion.nodos
    )
    return Expresion(nodos)


def test_con_y_sin_plegado_el_resultado_de_cada_fila_es_identico() -> None:
    azar = random.Random(SEMILLA)
    plegados = con_problema_plegado = comparadas = 0

    for _ in range(3000):
        plantilla = _plantilla_al_azar(azar)
        expresion = _con_obligatorias(azar, sintaxis.leer(plantilla))
        nombres = [n for n in VARIABLES if azar.random() < 0.5]
        constantes = {n: azar.choice(VALORES[n]) for n in nombres}
        sin_plegar = evaluador.compilar(expresion, VARIABLES)
        plegada = evaluador.compilar(expresion, VARIABLES, constantes=constantes)
        plegados += plegada.nodos_plegados
        con_problema_plegado += bool(plegada.problemas_plegados)

        assert plegada.cota == sin_plegar.cota
        assert plegada.tipo == sin_plegar.tipo
        assert plegada.es_variable_unica == sin_plegar.es_variable_unica
        for _ in range(4):
            fila = {n: azar.choice(VALORES[n]) for n in VARIABLES if n not in constantes}
            esperado = sin_plegar.evaluar({**fila, **constantes})
            obtenido = plegada.evaluar(fila)

            assert obtenido == esperado, (plantilla, constantes, fila)
            comparadas += 1

    assert plegados > 1000 and con_problema_plegado > 100 and comparadas == 12_000


def test_una_constante_repetida_por_fila_no_cambia_nada() -> None:
    # Pasar ademas la constante en la fila (como hacia MOWA MES) da lo mismo.
    plegada = _compilar("[@tel | enlace_whatsapp] [@t]", {"tel": "900000123"})

    con = plegada.evaluar({"t": "x", "tel": "900000123"})
    sin = plegada.evaluar({"t": "x"})

    assert con == sin
    assert con.texto == "https://wa.me/+51900000123 x"


def test_los_nodos_de_texto_no_se_tocan() -> None:
    expresion = Expresion(
        (
            NodoTexto("[@ no es variable"),
            NodoVariable("t"),
            NodoVariable("u", (LlamadaFuncion("primeros", (2,)),)),
        )
    )

    plegada = evaluador.compilar(expresion, VARIABLES, constantes={"t": "ab"})

    assert plegada.evaluar({"u": "xyz"}).texto == "[@ no es variableabxy"


def test_un_argumento_variable_constante_entre_nodos_no_constantes() -> None:
    plegada = _compilar("[@f | sumar_dias(@n)]", {"n": 2})

    assert plegada.nodos_plegados == 0  # la variable f no es constante
    assert plegada.variables == ("f",)  # `n` ya no se lee de la fila
    assert plegada.evaluar({"f": date(2026, 1, 1)}).texto == "2026-01-03"
    assert ArgumentoVariable("n") in plegada.expresion.nodos[0].funciones[0].args


def test_los_problemas_de_fila_conservan_el_indice_de_nodo_aunque_se_unan_textos_fijos() -> None:
    # Regresion hallada por la propiedad: al unir los textos fijos que quedan junto a un nodo
    # plegado, el indice del nodo siguiente se corria y el problema decia otro nodo.
    plantilla = "a[@t]b[@u | a_numero]c"
    sin_plegar = _compilar(plantilla)
    plegada = _compilar(plantilla, {"t": "x"})

    esperado = sin_plegar.evaluar({"t": "x", "u": "no es numero"})
    obtenido = plegada.evaluar({"u": "no es numero"})

    assert [p.nodo for p in obtenido.problemas] == [3]
    assert obtenido == esperado


def test_en_un_nodo_no_plegado_la_constante_tambien_manda_sobre_la_fila() -> None:
    plegada = _compilar("[@f | sumar_dias(@n)]", {"n": 2})

    resultado = plegada.evaluar({"f": date(2026, 1, 1), "n": 99})

    assert resultado.texto == "2026-01-03"  # n=2 de la constante, no 99 de la fila


def test_una_constante_vacia_sola_tambien_pliega() -> None:
    compilada = _compilar("a[@t]b", {"t": None})

    assert compilada.nodos_plegados == 1
    assert compilada.evaluar({"t": "de la fila"}).texto == "ab"


# --- Atajos para quien genera muchas filas (B2) ---------------------------------------------


@pytest.mark.parametrize(
    ("plantilla", "directa"),
    [
        ("[@t]", "t"),
        ("[@ n ]", "n"),
        ("a[@t]", None),
        ("[@t]b", None),
        ("[@t][@u]", None),
        ("[@t | mayusculas]", None),
        ("hola", None),
        ("", None),
    ],
)
def test_referencia_directa_solo_si_es_exactamente_una_variable_sin_funciones(
    plantilla, directa
) -> None:
    assert _compilar(plantilla).referencia_directa == directa


def test_una_variable_obligatoria_no_es_una_referencia_directa() -> None:
    expresion = Expresion((NodoVariable("t", obligatoria=True),))

    assert evaluador.compilar(expresion, VARIABLES).referencia_directa is None


def test_una_referencia_directa_da_str_del_valor_y_el_valor_sin_tocar() -> None:
    compilada = _compilar("[@n]")

    for valor in (None, Decimal("1.50"), 7, "x", date(2026, 1, 2), False):
        resultado = compilada.evaluar({"n": valor})
        assert resultado.texto == ("" if valor is None else str(valor))
        assert resultado.valor is valor or resultado.valor == valor


@pytest.mark.parametrize(
    ("plantilla", "constantes", "fijo"),
    [
        ("hola", None, "hola"),
        ("", None, ""),
        ("[@t]", None, None),
        ("a[@t]b", {"t": "X"}, "aXb"),  # plegado sin problemas y sin valor tipado que conservar
        ("[@t]", {"t": "X"}, None),  # un nodo unico plegado conserva su valor tipado
        ("a[@n | dividir(0)]b", {"n": 1}, None),  # con problema: nunca es fijo
    ],
)
def test_texto_fijo_solo_si_nada_depende_de_la_fila(plantilla, constantes, fijo) -> None:
    assert _compilar(plantilla, constantes).texto_fijo == fijo


def test_una_expresion_fija_da_siempre_el_mismo_resultado() -> None:
    compilada = _compilar("a[@t]b", {"t": "X"})

    assert compilada.evaluar({"u": 1}) == compilada.evaluar({"u": 2})
    assert compilada.evaluar({}).texto == "aXb"


def test_el_resultado_es_inmutable() -> None:
    resultado = _compilar("hola").evaluar({})

    with pytest.raises(AttributeError):
        resultado.texto = "otro"  # type: ignore[misc]
