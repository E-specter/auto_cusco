"""Catalogo de funciones del motor de texto enriquecido (seccion 6): cada una con sus bordes.

Se prueban a traves de `evaluador.compilar_texto`, que es como las usa el motor:
compilar una vez la cadena y evaluar por fila.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.core.entities.texto_enriquecido import CodigoTexto, ExpresionInvalida, TipoValor
from app.core.services.texto_enriquecido import evaluador
from app.core.services.texto_enriquecido.funciones import REGISTRO

T, N, F, B = TipoValor.TEXTO, TipoValor.NUMERO, TipoValor.FECHA, TipoValor.BOOLEANO

VARIABLES = {
    "t": T,
    "n": N,
    "f": F,
    "b": B,
    "otro_n": N,
    "otro_t": T,
    "tel": T,
}


def _evaluar(plantilla: str, **producto):
    return evaluador.compilar_texto(plantilla, VARIABLES).evaluar(producto)


def _texto(plantilla: str, **producto) -> str:
    resultado = _evaluar(plantilla, **producto)
    assert resultado.problemas == ()
    return resultado.texto


def _codigo_de_fila(plantilla: str, **producto) -> CodigoTexto:
    resultado = _evaluar(plantilla, **producto)
    assert resultado.texto == ""
    assert len(resultado.problemas) == 1
    return resultado.problemas[0].codigo


# --- texto ---


@pytest.mark.parametrize(
    ("valor", "n", "esperado"),
    [
        ("ABCDEFGHIJ", 8, "ABCDEFGH"),
        ("ABC", 8, "ABC"),
        ("ABCDEFGH", 8, "ABCDEFGH"),
        ("ÁÉÍÓÚ", 2, "ÁÉ"),
        ("A", 1, "A"),
    ],
)
def test_primeros_recorta_por_la_derecha(valor, n, esperado) -> None:
    assert _texto(f"[@t | primeros({n})]", t=valor) == esperado


def test_ultimos_toma_del_final() -> None:
    assert _texto("[@t | ultimos(3)]", t="ABCDEFG") == "EFG"
    assert _texto("[@t | ultimos(3)]", t="AB") == "AB"


@pytest.mark.parametrize("funcion", ["primeros", "ultimos"])
@pytest.mark.parametrize("n", [0, -1])
def test_primeros_y_ultimos_piden_n_mayor_o_igual_a_uno(funcion, n) -> None:
    with pytest.raises(ExpresionInvalida) as error:
        evaluador.compilar_texto(f"[@t | {funcion}({n})]", VARIABLES)

    problema = error.value.problemas[0]
    assert problema.codigo is CodigoTexto.PARAMETRO_INVALIDO
    assert (problema.nodo, problema.funcion, problema.parametro) == (0, 0, "n")


def test_mayusculas_minusculas_y_capitalizar() -> None:
    assert _texto("[@t | mayusculas]", t="Pérez ñandú") == "PÉREZ ÑANDÚ"
    assert _texto("[@t | minusculas]", t="PÉREZ ÑANDÚ") == "pérez ñandú"
    assert _texto("[@t | capitalizar]", t="pÉREZ ñANDÚ") == "Pérez ñandú"


def test_las_mayusculas_y_minusculas_conservan_el_largo_para_poder_acotarlo() -> None:
    # `str.upper` convierte la ß en SS y `str.lower` la İ en dos caracteres: aqui no.
    assert _texto("[@t | mayusculas]", t="straße") == "STRAßE"
    assert len(_texto("[@t | minusculas]", t="İ")) == 1


def test_recortar_quita_los_extremos_y_colapsa_los_espacios_repetidos() -> None:
    assert _texto("[@t | recortar]", t="  APELLIDO   NOMBRE \t X\n") == "APELLIDO NOMBRE X"
    assert _texto("[@t | recortar]", t="   ") == ""


def test_sin_tildes_quita_marcas_diacriticas_y_conserva_lo_demas() -> None:
    assert (
        _texto("[@t | sin_tildes]", t="Camión ñandú Ü, ¡hola! 123") == "Camion nandu U, ¡hola! 123"
    )


def test_sin_tildes_da_lo_mismo_que_la_conciliacion_de_mowa_mes() -> None:
    from app.core.services.plataformas.mowa_mes.conciliacion import normalizar_mensaje

    texto = "Señor Ñuñez: acércate a pagar tu cuota, José."

    assert _texto("[@t | sin_tildes]", t=texto) == normalizar_mensaje(texto)


def test_sin_tildes_nunca_alarga_el_texto() -> None:
    hangul = "가나다"  # una silaba decompone en 2 o 3 jamos; no se toca

    assert _texto("[@t | sin_tildes]", t=hangul) == hangul
    assert _texto("[@t | sin_tildes]", t="é") == "e"


def test_reemplazar_es_literal_y_no_una_expresion_regular() -> None:
    assert _texto('[@t | reemplazar(".", "-")]', t="a.b.c") == "a-b-c"
    assert _texto('[@t | reemplazar("(", "")]', t="f(x)") == "fx)"
    assert _texto('[@t | reemplazar("a|b", "X")]', t="a|b ab") == "X ab"
    assert _texto('[@t | reemplazar("a", "")]', t="banana") == "bnn"


def test_reemplazar_no_admite_buscar_un_texto_vacio() -> None:
    with pytest.raises(ExpresionInvalida) as error:
        evaluador.compilar_texto('[@t | reemplazar("", "x")]', VARIABLES)

    assert error.value.problemas[0].parametro == "buscar"


def test_rellenar_izquierda_completa_hasta_n_y_no_recorta() -> None:
    assert _texto('[@t | rellenar_izquierda(8, "0")]', t="1234567") == "01234567"
    assert _texto('[@t | rellenar_izquierda(8, "0")]', t="12345678") == "12345678"
    assert _texto('[@t | rellenar_izquierda(8, "0")]', t="123456789") == "123456789"


@pytest.mark.parametrize("relleno", ["", "00"])
def test_rellenar_izquierda_pide_un_solo_caracter(relleno) -> None:
    with pytest.raises(ExpresionInvalida) as error:
        evaluador.compilar_texto(f'[@t | rellenar_izquierda(8, "{relleno}")]', VARIABLES)

    assert error.value.problemas[0].parametro == "relleno"


# --- numero ---


def test_sumar_restar_multiplicar_y_dividir_usan_decimal_exacto() -> None:
    assert _texto("[@n | sumar(0.1)]", n=Decimal("0.2")) == "0.3"
    assert _texto("[@n | restar(1)]", n=Decimal("10.50")) == "9.50"
    assert _texto("[@n | multiplicar(3)]", n=Decimal("1.10")) == "3.30"
    assert _texto("[@n | dividir(4)]", n=Decimal("10")) == "2.5"


def test_un_entero_del_producto_se_trata_como_numero() -> None:
    assert _texto("[@n | sumar(1)]", n=5) == "6"


def test_los_argumentos_numericos_pueden_ser_otra_variable() -> None:
    assert _texto("[@n | sumar(@otro_n)]", n=Decimal("1"), otro_n=Decimal("2.5")) == "3.5"
    assert _texto("[@n | multiplicar(@otro_n)]", n=Decimal("2"), otro_n=Decimal("3")) == "6"


def test_dividir_por_cero_es_un_problema_de_la_fila() -> None:
    assert _codigo_de_fila("[@n | dividir(0)]", n=Decimal("1")) is CodigoTexto.DIVISION_POR_CERO
    assert (
        _codigo_de_fila("[@n | dividir(@otro_n)]", n=Decimal("1"), otro_n=Decimal("0"))
        is CodigoTexto.DIVISION_POR_CERO
    )


def test_el_problema_de_fila_dice_donde_ocurrio() -> None:
    resultado = _evaluar("[@t] [@n | sumar(1) | dividir(0)]", t="x", n=Decimal(1))

    problema = resultado.problemas[0]
    assert (problema.nodo, problema.funcion) == (2, 1)
    assert resultado.texto == "x "


def test_un_argumento_variable_vacio_es_un_problema_de_la_fila() -> None:
    assert _codigo_de_fila("[@n | sumar(@otro_n)]", n=Decimal(1)) is CodigoTexto.ARGUMENTO_VACIO


def test_redondear_va_a_la_mitad_hacia_arriba() -> None:
    assert _texto("[@n | redondear(2)]", n=Decimal("1.005")) == "1.01"
    assert _texto("[@n | redondear(2)]", n=Decimal("1.004")) == "1.00"
    assert _texto("[@n | redondear(0)]", n=Decimal("2.5")) == "3"
    assert _texto("[@n | redondear(0)]", n=Decimal("0.5")) == "1"
    assert _texto("[@n | redondear(1)]", n=Decimal("-2.25")) == "-2.3"
    assert _texto("[@n | redondear(6)]", n=Decimal("1")) == "1.000000"


@pytest.mark.parametrize("d", [-1, 7])
def test_redondear_admite_de_0_a_6_decimales(d) -> None:
    with pytest.raises(ExpresionInvalida):
        evaluador.compilar_texto(f"[@n | redondear({d})]", VARIABLES)


def test_los_decimales_deben_ser_enteros() -> None:
    with pytest.raises(ExpresionInvalida):
        evaluador.compilar_texto("[@n | redondear(1.5)]", VARIABLES)


def test_formato_numero_reutiliza_los_separadores_del_importe() -> None:
    assert _texto("[@n | formato_numero(2)]", n=Decimal("1234567.5")) == "1,234,567.50"
    assert _texto('[@n | formato_numero(2, ".", ",")]', n=Decimal("1234.567")) == "1.234,57"
    assert _texto('[@n | formato_numero(0, " ", ",")]', n=Decimal("-1234")) == "-1 234"
    assert _texto('[@n | formato_numero(2, "", ".")]', n=Decimal("1234.5")) == "1234.50"


def test_formato_numero_redondea_a_la_mitad_hacia_arriba() -> None:
    assert _texto("[@n | formato_numero(2)]", n=Decimal("0.125")) == "0.13"
    assert _texto("[@n | formato_numero(0)]", n=Decimal("0.5")) == "1"


def test_a_numero_lee_texto_plano_y_rechaza_lo_demas() -> None:
    assert _texto("[@t | a_numero | sumar(1)]", t=" 41 ") == "42"
    assert _texto("[@t | a_numero]", t="-12.50") == "-12.50"
    assert _texto("[@t | a_numero]", t="+3") == "3"
    for texto in ["abc", "1,5", "1e3", "NaN", "Infinity", "1.", ".5", "--1", "١٢٣", "1 2"]:
        assert _codigo_de_fila("[@t | a_numero]", t=texto) is CodigoTexto.NO_ES_NUMERO, texto


def test_a_texto_da_una_representacion_estable() -> None:
    assert _texto("[@n | multiplicar(1) | a_texto]", n=Decimal("1E+2")) == "100"
    assert _texto("[@n | a_texto | primeros(2)]", n=Decimal("123.4")) == "12"
    assert _texto("[@f | a_texto]", f=date(2026, 9, 5)) == "2026-09-05"


# --- fecha ---


def test_sumar_y_restar_dias() -> None:
    assert _texto("[@f | sumar_dias(3) | a_texto]", f=date(2026, 9, 29)) == "2026-10-02"
    assert _texto("[@f | restar_dias(1) | a_texto]", f=date(2026, 3, 1)) == "2026-02-28"
    assert _texto("[@f | sumar_dias(@n) | a_texto]", f=date(2026, 1, 1), n=Decimal(30)) == (
        "2026-01-31"
    )
    assert _texto("[@f | sumar_dias(-1) | a_texto]", f=date(2026, 1, 1)) == "2025-12-31"


def test_una_fecha_con_hora_se_trata_como_fecha() -> None:
    assert _texto("[@f | sumar_dias(1) | a_texto]", f=datetime(2026, 9, 29, 23, 59)) == (
        "2026-09-30"
    )


def test_sumar_dias_con_un_numero_no_entero_es_un_problema_de_la_fila() -> None:
    assert (
        _codigo_de_fila("[@f | sumar_dias(@n)]", f=date(2026, 1, 1), n=Decimal("1.5"))
        is CodigoTexto.PARAMETRO_INVALIDO
    )


def test_sumar_dias_fuera_del_calendario_es_un_problema_de_la_fila() -> None:
    assert (
        _codigo_de_fila("[@f | sumar_dias(5)]", f=date(9999, 12, 30))
        is CodigoTexto.RESULTADO_FUERA_DE_RANGO
    )


def test_formato_fecha_con_marcas_legibles() -> None:
    dia = date(2026, 9, 5)

    assert _texto('[@f | formato_fecha("dd/mm/aaaa")]', f=dia) == "05/09/2026"
    assert _texto('[@f | formato_fecha("aaaa-mm-dd")]', f=dia) == "2026-09-05"
    assert _texto('[@f | formato_fecha("dd/mm/aa")]', f=dia) == "05/09/26"
    assert _texto('[@f | formato_fecha("dd de nombre_mes de aaaa")]', f=dia) == (
        "05 de septiembre de 2026"
    )
    assert _texto('[@f | formato_fecha("%dd/aaaa")]', f=dia) == "%05/2026"  # '%' es texto


def test_formato_fecha_no_depende_del_idioma_del_sistema() -> None:
    assert _texto('[@f | formato_fecha("nombre_mes")]', f=date(2026, 3, 1)) == "marzo"
    assert _texto('[@f | formato_fecha("nombre_mes")]', f=date(2026, 12, 1)) == "diciembre"


def test_formato_fecha_pide_al_menos_una_marca() -> None:
    with pytest.raises(ExpresionInvalida) as error:
        evaluador.compilar_texto('[@f | formato_fecha("yyyy")]', VARIABLES)

    assert error.value.problemas[0].codigo is CodigoTexto.PARAMETRO_INVALIDO
    assert error.value.problemas[0].parametro == "patron"


def test_a_fecha_lee_con_el_mismo_patron() -> None:
    assert _texto('[@t | a_fecha("dd/mm/aaaa") | a_texto]', t="05/09/2026") == "2026-09-05"
    assert _texto('[@t | a_fecha("aaaa-mm-dd") | sumar_dias(1) | a_texto]', t="2026-09-05") == (
        "2026-09-06"
    )
    assert _texto(
        '[@t | a_fecha("dd de nombre_mes de aaaa") | a_texto]', t="05 de Marzo de 2026"
    ) == ("2026-03-05")
    assert _texto('[@t | a_fecha("dd/mm/aa") | a_texto]', t="05/09/26") == "2026-09-05"


@pytest.mark.parametrize(
    "texto",
    ["31/02/2026", "5/9/2026", "05-09-2026", "05/09/2026x", "", "aa/bb/cccc", "05/13/2026"],
)
def test_a_fecha_rechaza_lo_que_no_calza_con_el_patron(texto) -> None:
    assert (
        _codigo_de_fila('[@t | a_fecha("dd/mm/aaaa")]', t=texto or "x") is CodigoTexto.NO_ES_FECHA
    )


def test_a_fecha_pide_dia_mes_y_anio_en_el_patron() -> None:
    with pytest.raises(ExpresionInvalida):
        evaluador.compilar_texto('[@t | a_fecha("dd/mm")]', VARIABLES)


# --- nulos ---


def test_si_vacio_reemplaza_solo_lo_vacio() -> None:
    assert _texto('[@t | si_vacio("-")]', t=None) == "-"
    assert _texto('[@t | si_vacio("-")]', t="   ") == "-"
    assert _texto('[@t | si_vacio("-")]', t="") == "-"
    assert _texto('[@t | si_vacio("-")]', t="x") == "x"
    assert _texto('[@t | si_vacio("-")]', t="0") == "0"
    assert _texto("[@n | si_vacio(0)]", n=None) == "0"
    assert _texto("[@n | si_vacio(0)]", n=Decimal(0)) == "0"


def test_si_vacio_puede_tomar_el_alternativo_de_otra_variable() -> None:
    assert _texto("[@t | si_vacio(@otro_t)]", t=None, otro_t="alt") == "alt"
    assert _texto("[@t | si_vacio(@otro_t)]", t="x", otro_t="alt") == "x"
    assert _texto("[@t | si_vacio(@otro_t)]", t=None, otro_t=None) == ""


def test_si_vacio_actua_aunque_las_funciones_anteriores_no_se_apliquen_al_vacio() -> None:
    assert _texto('[@f | formato_fecha("dd/mm/aaaa") | si_vacio("sin fecha")]', f=None) == (
        "sin fecha"
    )
    assert _texto('[@t | mayusculas | primeros(3) | si_vacio("N/D")]', t=None) == "N/D"


def test_si_vacio_exige_que_el_alternativo_sea_del_mismo_tipo() -> None:
    with pytest.raises(ExpresionInvalida) as error:
        evaluador.compilar_texto('[@n | si_vacio("x")]', VARIABLES)

    assert error.value.problemas[0].codigo is CodigoTexto.PARAMETRO_INVALIDO


# --- enlaces ---


def test_enlace_whatsapp_usa_el_prefijo_por_defecto() -> None:
    assert _texto("[@tel | enlace_whatsapp]", tel="987654321") == "https://wa.me/+51987654321"


def test_enlace_whatsapp_con_prefijo_propio() -> None:
    assert _texto('[@tel | enlace_whatsapp("https://x.test/")]', tel="987654321") == (
        "https://x.test/987654321"
    )


@pytest.mark.parametrize(
    "telefono", ["12345678", "887654321", "9876543210", "98765432a", " 987654321"]
)
def test_enlace_whatsapp_valida_el_telefono_con_la_regla_rf_02(telefono) -> None:
    assert (
        _codigo_de_fila("[@tel | enlace_whatsapp]", tel=telefono) is CodigoTexto.TELEFONO_INVALIDO
    )


def test_enlace_whatsapp_con_telefono_vacio_queda_vacio_sin_problema() -> None:
    resultado = _evaluar("[@tel | enlace_whatsapp]", tel=None)

    assert resultado.texto == ""
    assert resultado.problemas == ()


# --- el registro ---


def test_cada_funcion_declara_sus_metadatos_completos() -> None:
    assert len(REGISTRO) == 23
    for nombre, funcion in REGISTRO.items():
        assert funcion.nombre == nombre
        assert funcion.familia
        assert funcion.recibe
        assert funcion.devuelve in (*TipoValor, "entrada")
        assert funcion.clave_nombre == f"textoEnriquecido.funcion.{nombre}.nombre"
        assert funcion.clave_descripcion == f"textoEnriquecido.funcion.{nombre}.descripcion"


def test_el_catalogo_inicial_tiene_todas_las_funciones_de_la_seccion_6() -> None:
    esperadas = {
        "primeros", "ultimos", "mayusculas", "minusculas", "capitalizar", "recortar",
        "sin_tildes", "reemplazar", "rellenar_izquierda", "sumar", "restar", "multiplicar",
        "dividir", "redondear", "formato_numero", "a_numero", "a_texto", "sumar_dias",
        "restar_dias", "formato_fecha", "a_fecha", "si_vacio", "enlace_whatsapp",
    }  # fmt: skip

    assert esperadas <= set(REGISTRO)


def test_solo_si_vacio_acepta_nulo() -> None:
    assert {n for n, f in REGISTRO.items() if f.acepta_nulo} == {"si_vacio"}


def test_si_vacio_devuelve_el_mismo_tipo_que_recibe() -> None:
    assert REGISTRO["si_vacio"].devuelve == "entrada"
    assert REGISTRO["primeros"].devuelve is TipoValor.TEXTO
    assert REGISTRO["formato_fecha"].recibe == (TipoValor.FECHA,)
    assert REGISTRO["a_texto"].recibe == (TipoValor.NUMERO, TipoValor.FECHA)
