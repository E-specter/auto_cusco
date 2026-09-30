"""Propiedades del motor de texto enriquecido, con semilla fija (diseno, seccion 12).

El proyecto no tiene Hypothesis configurado: son generadores propios con `random.Random`
y una semilla fija, asi una falla se reproduce exactamente. Cada propiedad corre sobre
miles de entradas generadas, no sobre las que imaginé al escribir la prueba.
"""

import random
import unicodedata
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.core.entities.texto_enriquecido import (
    ArgumentoVariable,
    Expresion,
    ExpresionInvalida,
    LimitesExpresion,
    LlamadaFuncion,
    NodoTexto,
    NodoVariable,
    TipoValor,
)
from app.core.services.plataformas.mowa_mes.conciliacion import normalizar_mensaje
from app.core.services.texto_enriquecido import evaluador, sintaxis

SEMILLA = 20260929
T, N, F = TipoValor.TEXTO, TipoValor.NUMERO, TipoValor.FECHA
VARIABLES = {"t": T, "u": T, "n": N, "m": N, "f": F, "tel": T}

# Caracteres que estresan la sintaxis y los textos.
CARACTERES_SINTAXIS = list('[]@|(),"\\ \n\t-.0123456789abcxyzñ_')
LETRAS = list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ñÑáéíóúüÁÉÍÓÚÜ.,-/'0123456789")
CON_MARCAS = LETRAS + list("ãõçàèìòùâêîôûëïÿåøßİǆ̧́̈") + ["가", "각", "😀", "Å", "ǅ"]


def _texto_al_azar(azar: random.Random, alfabeto: list[str], maximo: int) -> str:
    return "".join(azar.choice(alfabeto) for _ in range(azar.randint(0, maximo)))


# --- sintaxis ---


def _nombre(azar: random.Random) -> str:
    return "".join(azar.choice("abcdefghij_xyz0123456789") for _ in range(azar.randint(1, 8)))


def _argumento(azar: random.Random):
    tipo = azar.choice(["entero", "decimal", "texto", "variable"])
    if tipo == "entero":
        return azar.randint(-1000, 1000)
    if tipo == "decimal":
        return Decimal(azar.randint(-99999, 99999)) / Decimal(azar.choice([10, 100, 1000]))
    if tipo == "texto":
        return _texto_al_azar(azar, CARACTERES_SINTAXIS, 12)
    return ArgumentoVariable(_nombre(azar))


def _expresion_al_azar(azar: random.Random) -> Expresion:
    nodos = []
    for _ in range(azar.randint(0, 6)):
        if azar.random() < 0.5 and not (nodos and isinstance(nodos[-1], NodoTexto)):
            valor = _texto_al_azar(azar, CARACTERES_SINTAXIS + ["[@", "[@", "@]"], 10)
            if valor:
                nodos.append(NodoTexto(valor))
        else:
            funciones = tuple(
                LlamadaFuncion(
                    _nombre(azar).lstrip("0123456789") or "f",
                    tuple(_argumento(azar) for _ in range(azar.randint(0, 3))),
                )
                for _ in range(azar.randint(0, 3))
            )
            nodos.append(NodoVariable(_nombre(azar), funciones))
    return Expresion(tuple(nodos))


def _normalizada(expresion: Expresion) -> Expresion:
    """Une los textos contiguos y quita los vacios: la forma que produce el lector."""
    nodos: list = []
    for nodo in expresion.nodos:
        if isinstance(nodo, NodoTexto):
            if not nodo.valor:
                continue
            if nodos and isinstance(nodos[-1], NodoTexto):
                nodos[-1] = NodoTexto(nodos[-1].valor + nodo.valor)
                continue
        nodos.append(nodo)
    return Expresion(tuple(nodos))


LIMITES_AMPLIOS = LimitesExpresion(nodos=1000, funciones_por_nodo=100, argumentos_por_funcion=100)


def test_ida_y_vuelta_de_expresiones_al_azar() -> None:
    azar = random.Random(SEMILLA)

    for _ in range(4000):
        expresion = _normalizada(_expresion_al_azar(azar))

        texto = sintaxis.escribir(expresion)

        assert sintaxis.leer(texto, LIMITES_AMPLIOS) == expresion, texto
        assert sintaxis.escribir(sintaxis.leer(texto, LIMITES_AMPLIOS)) == texto


def test_un_texto_al_azar_se_rechaza_con_un_problema_o_da_una_forma_estable() -> None:
    azar = random.Random(SEMILLA + 1)
    aceptados = rechazados = 0

    for _ in range(6000):
        texto = _texto_al_azar(azar, CARACTERES_SINTAXIS + ["[@", "[@", "|", "]", "@"], 30)
        try:
            expresion = sintaxis.leer(texto, LIMITES_AMPLIOS)
        except ExpresionInvalida as error:
            rechazados += 1
            assert error.problemas and "posicion" in error.problemas[0].detalle
            continue
        aceptados += 1
        canonico = sintaxis.escribir(expresion)

        assert sintaxis.leer(canonico, LIMITES_AMPLIOS) == expresion, (texto, canonico)
        assert sintaxis.escribir(sintaxis.leer(canonico, LIMITES_AMPLIOS)) == canonico

    assert aceptados > 500 and rechazados > 500  # el generador ejercita ambos caminos


def test_un_texto_sin_apertura_es_siempre_un_solo_nodo_texto_igual_al_original() -> None:
    azar = random.Random(SEMILLA + 2)

    for _ in range(2000):
        texto = _texto_al_azar(azar, CARACTERES_SINTAXIS + ["[", "@", "]"], 40).replace("[@", "[ @")

        esperado = Expresion((NodoTexto(texto),)) if texto else Expresion(())
        assert sintaxis.leer(texto) == esperado


def test_el_escape_de_la_apertura_da_ida_y_vuelta_en_cualquier_texto() -> None:
    azar = random.Random(SEMILLA + 3)

    for _ in range(3000):
        literal = _texto_al_azar(azar, list("[@]|x "), 12)
        expresion = Expresion((NodoTexto(literal),)) if literal else Expresion(())

        assert sintaxis.leer(sintaxis.escribir(expresion)) == expresion, literal


# --- primeros ---


def _evaluar(plantilla: str, **producto):
    return evaluador.compilar_texto(plantilla, VARIABLES).evaluar(producto)


def test_primeros_es_el_prefijo_de_largo_n() -> None:
    azar = random.Random(SEMILLA + 4)

    for _ in range(3000):
        texto = _texto_al_azar(azar, CON_MARCAS, 30)
        n = azar.randint(1, 40)

        resultado = _evaluar(f"[@t | primeros({n})]", t=texto)

        assert resultado.problemas == ()
        if texto.strip():
            assert resultado.texto == texto[:n]
            assert len(resultado.texto) == min(n, len(texto))
            assert texto.startswith(resultado.texto)


def test_primeros_es_idempotente_y_encadenar_da_el_menor() -> None:
    azar = random.Random(SEMILLA + 5)

    for _ in range(2000):
        texto = _texto_al_azar(azar, CON_MARCAS, 30)
        n, m = azar.randint(1, 40), azar.randint(1, 40)

        una = _evaluar(f"[@t | primeros({n}) | primeros({n})]", t=texto).texto
        dos = _evaluar(f"[@t | primeros({n}) | primeros({m})]", t=texto).texto

        assert una == _evaluar(f"[@t | primeros({n})]", t=texto).texto
        assert dos == _evaluar(f"[@t | primeros({min(n, m)})]", t=texto).texto


def test_ultimos_es_el_sufijo_de_largo_n() -> None:
    azar = random.Random(SEMILLA + 6)

    for _ in range(2000):
        texto = _texto_al_azar(azar, CON_MARCAS, 30)
        n = azar.randint(1, 40)

        resultado = _evaluar(f"[@t | ultimos({n})]", t=texto).texto

        if texto.strip():
            assert resultado == texto[-n:]
            assert texto.endswith(resultado)


# --- sin_tildes ---


def _sin_marcas_de_referencia(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c))


def test_sin_tildes_no_deja_marcas_no_alarga_y_es_idempotente() -> None:
    azar = random.Random(SEMILLA + 7)

    for _ in range(4000):
        texto = _texto_al_azar(azar, CON_MARCAS, 25)
        if not texto.strip():
            continue

        resultado = _evaluar("[@t | sin_tildes]", t=texto).texto

        assert not any(unicodedata.combining(c) for c in resultado), (texto, resultado)
        assert len(resultado) <= len(texto)
        assert _evaluar("[@t | sin_tildes]", t=resultado).texto == resultado


def test_sin_tildes_no_toca_el_texto_ascii() -> None:
    azar = random.Random(SEMILLA + 8)
    ascii_puro = list(" abcXYZ019.,;:-_/'\"!?()[]@|\\")

    for _ in range(2000):
        texto = _texto_al_azar(azar, ascii_puro, 30)
        if texto.strip():
            assert _evaluar("[@t | sin_tildes]", t=texto).texto == texto


def test_sin_tildes_da_lo_mismo_que_la_conciliacion_en_el_alfabeto_latino() -> None:
    azar = random.Random(SEMILLA + 9)
    latino = LETRAS + list("ãõçàèìòùâêîôûëïÿåøǺ̈")

    for _ in range(4000):
        texto = _texto_al_azar(azar, latino, 25)
        if not texto.strip():
            continue

        assert _evaluar("[@t | sin_tildes]", t=texto).texto.strip() == normalizar_mensaje(texto)


def test_sin_tildes_quita_las_mismas_marcas_que_nfd_en_texto_precompuesto() -> None:
    azar = random.Random(SEMILLA + 10)
    precompuesto = list("abcáéíóúñüÁÉÍÓÚÑÜ ãõç")

    for _ in range(2000):
        texto = _texto_al_azar(azar, precompuesto, 25)
        if texto.strip():
            assert _evaluar("[@t | sin_tildes]", t=texto).texto == _sin_marcas_de_referencia(texto)


# --- otras funciones de texto ---


def test_mayusculas_minusculas_y_recortar_no_alargan_el_texto() -> None:
    azar = random.Random(SEMILLA + 11)

    for _ in range(3000):
        texto = _texto_al_azar(azar, CON_MARCAS, 25)
        if not texto.strip():
            continue

        for funcion in ("mayusculas", "minusculas", "capitalizar", "recortar"):
            assert len(_evaluar(f"[@t | {funcion}]", t=texto).texto) <= len(texto), funcion


def test_recortar_no_deja_espacios_en_los_extremos_ni_repetidos() -> None:
    azar = random.Random(SEMILLA + 12)

    for _ in range(3000):
        texto = _texto_al_azar(azar, list("ab \t\n"), 20)

        resultado = _evaluar("[@t | recortar]", t=texto).texto

        assert resultado == resultado.strip()
        assert "  " not in resultado
        assert _evaluar("[@t | recortar | recortar]", t=texto).texto == resultado


# --- cota ---


def _cadena_al_azar(azar: random.Random, tipo: TipoValor) -> list[str]:
    texto = [
        "primeros({n})",
        "ultimos({n})",
        "mayusculas",
        "minusculas",
        "recortar",
        "sin_tildes",
        'reemplazar("a", "{s}")',
        'rellenar_izquierda({n}, "0")',
        'si_vacio("{s}")',
    ]
    cadena: list[str] = []
    if tipo is F:
        cadena.append(
            azar.choice(['formato_fecha("dd/mm/aaaa")', 'formato_fecha("nombre_mes")', "a_texto"])
        )
    elif tipo is N:
        cadena.append(azar.choice(["a_texto", 'formato_numero(2, ".", ",")']))
    cadena += [
        azar.choice(texto).format(n=azar.randint(1, 12), s="x" * azar.randint(0, 6))
        for _ in range(azar.randint(0, 3))
    ]
    return cadena


def test_la_cota_es_siempre_un_tope_verdadero() -> None:
    azar = random.Random(SEMILLA + 13)
    valores = {
        "t": lambda: azar.choice([None, "", "  ", _texto_al_azar(azar, CON_MARCAS, 40)]),
        "n": lambda: azar.choice([None, Decimal(azar.randint(-(10**9), 10**9)) / 100]),
        "f": lambda: azar.choice(
            [None, date(2026, 1, 1) + timedelta(days=azar.randint(-700_000, 700_000))]
        ),
        "tel": lambda: azar.choice([None, "987654321", "12"]),
    }
    con_cota = 0

    for _ in range(4000):
        partes = []
        for _ in range(azar.randint(1, 4)):
            if azar.random() < 0.4:
                partes.append(_texto_al_azar(azar, list("abc ñ.,"), 8))
                continue
            nombre = azar.choice(["t", "n", "f", "tel"])
            cadena = (
                ["enlace_whatsapp"] if nombre == "tel" else _cadena_al_azar(azar, VARIABLES[nombre])
            )
            partes.append("[@" + " | ".join([nombre, *cadena]) + "]")
        compilada = evaluador.compilar_texto("".join(partes), VARIABLES)
        producto = {n: valor() for n, valor in valores.items()}

        resultado = compilada.evaluar(producto)

        if compilada.cota is not None and not resultado.problemas:
            con_cota += 1
            assert len(resultado.texto) <= compilada.cota, ("".join(partes), producto)

    assert con_cota > 500  # la propiedad se ejercita de verdad


# --- numeros y fechas ---


def test_redondear_queda_a_la_mitad_de_un_paso_y_con_los_decimales_pedidos() -> None:
    azar = random.Random(SEMILLA + 14)

    for _ in range(3000):
        x = Decimal(azar.randint(-(10**9), 10**9)) / Decimal(10 ** azar.randint(0, 8))
        d = azar.randint(0, 6)

        resultado = _evaluar(f"[@n | redondear({d})]", n=x).valor

        assert abs(resultado - x) <= Decimal(5) / Decimal(10) ** (d + 1)
        assert resultado.as_tuple().exponent == -d
        assert _evaluar(f"[@n | redondear({d}) | redondear({d})]", n=x).valor == resultado


def test_sumar_y_restar_se_deshacen_con_decimal_exacto() -> None:
    azar = random.Random(SEMILLA + 15)

    for _ in range(3000):
        x = Decimal(azar.randint(-(10**8), 10**8)) / 100
        y = Decimal(azar.randint(-(10**8), 10**8)) / 100

        assert _evaluar("[@n | sumar(@m) | restar(@m)]", n=x, m=y).valor == x


def test_formato_fecha_y_a_fecha_son_inversas_para_patrones_completos() -> None:
    azar = random.Random(SEMILLA + 16)
    patrones = ["dd/mm/aaaa", "aaaa-mm-dd", "dd de nombre_mes de aaaa", "aaaammdd"]

    for _ in range(3000):
        dia = date.fromordinal(azar.randint(1, date.max.toordinal()))
        patron = azar.choice(patrones)

        ida = _evaluar(f'[@f | formato_fecha("{patron}") | a_fecha("{patron}")]', f=dia)

        assert ida.problemas == (), (dia, patron)
        assert ida.valor == dia


def test_sumar_dias_y_restar_dias_se_deshacen() -> None:
    azar = random.Random(SEMILLA + 17)

    for _ in range(3000):
        dia = date(2026, 1, 1) + timedelta(days=azar.randint(-20_000, 20_000))
        dias = azar.randint(-5000, 5000)

        assert _evaluar(f"[@f | sumar_dias({dias}) | restar_dias({dias})]", f=dia).valor == dia


@pytest.mark.parametrize("semilla_distinta", [1, 2])
def test_una_semilla_distinta_no_cambia_la_conclusion(semilla_distinta) -> None:
    azar = random.Random(SEMILLA + 100 * semilla_distinta)

    for _ in range(1500):
        expresion = _normalizada(_expresion_al_azar(azar))
        assert sintaxis.leer(sintaxis.escribir(expresion), LIMITES_AMPLIOS) == expresion
