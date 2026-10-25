"""Speech v2 de MOWA MES (B6, M2): una expresion del motor de texto enriquecido por segmento.

Cubre lo que decidieron el usuario y architec para M2:
- una v2 convertida desde una v1 da los mismos mensajes, largos, exclusiones y orden que la v1,
  sobre la matriz completa del oro de B5 (el Speech original y las 12 versiones sinteticas);
- `falta_titular` y `falta_vencimiento` solo si la expresion del segmento USA la variable (se
  decide sobre los nodos, nunca buscando el nombre en el texto), en los dos sentidos y sin cambiar
  el orden;
- el mensaje de un segmento que no usa una variable sale sin huecos;
- la huella de una v2 es propia y la de una v1 no cambia;
- el largo maximo (la cota), el nivel y el ejemplo de la previsualizacion, y "sin maximo calculable"
  con su motivo, mientras `mensaje_excede_160` sigue excluyendo por fila sobre el mensaje real.

Titulares, numeros y textos sinteticos.
"""

import json
from dataclasses import replace
from datetime import date

import pytest

from app.core.entities.mowa_mes import (
    LARGO_MAXIMO,
    RANGOS_SEGMENTO,
    CodigoMowaMes,
    DatosSpeech,
    ExpresionSegmento,
    FaltaWhatsapp,
    FormatoSpeech,
    MensajeNoGenerable,
    Segmento,
)
from app.core.entities.texto_enriquecido import (
    ArgumentoVariable,
    CodigoTexto,
    Expresion,
    LlamadaFuncion,
    NodoTexto,
    NodoVariable,
)
from app.core.services.plataformas.mowa_mes import speech
from app.core.services.plataformas.mowa_mes.campana import (
    Exclusion,
    FilaCarga,
    evaluar_producto,
    huella_de,
    huella_expresiones,
    huella_speech,
)
from app.core.services.texto_enriquecido.uso import variables_usadas
from tests.oro_mowa_mes_datos import (
    NUMEROS,
    ORIGINAL,
    TITULARES,
    TODAS_LAS_VERSIONES,
    VENCIMIENTOS,
    WHATSAPP,
)

CORTE = date(2026, 9, 14)
VENCIMIENTO = date(2026, 9, 6)
HUELLA_DEL_SPEECH_ORIGINAL = "297c227cfdd0bb5e1636e08d4ed6cebab971d724c84223acfdb0cfebc2fcf88a"
HUELLA_V2_FIJADA = "cab702335fdd2be3f5b731c300baf875dd45903a48b8f01ce7cdeb5984b5be49"


def _texto(valor: str) -> NodoTexto:
    return NodoTexto(valor)


def _titular(*funciones: LlamadaFuncion) -> NodoVariable:
    return NodoVariable("titular", funciones)


def _fecha() -> NodoVariable:
    return NodoVariable(
        "fecha_vencimiento_cuota", (LlamadaFuncion("formato_fecha", ("dd/mm/aaaa",)),)
    )


def _v2(nombre: str = "v2", **por_segmento: tuple) -> DatosSpeech:
    """Una v2: el mismo contenido en los 6 segmentos, salvo los que se den por nombre de enum."""
    expresiones = []
    for rango in RANGOS_SEGMENTO:
        nodos = por_segmento.get(rango.segmento.name, por_segmento.get("TODOS", ()))
        expresiones.append(ExpresionSegmento(rango.segmento, Expresion(tuple(nodos))))
    return DatosSpeech(nombre, expresiones=tuple(expresiones), formato=FormatoSpeech.V2)


def _convertida(version) -> DatosSpeech:
    return DatosSpeech(
        "convertida", expresiones=speech.convertir_a_v2(version), formato=FormatoSpeech.V2
    )


def _producto(**cambios) -> dict:
    producto = {
        "pagare": "000000000000000001",
        "telefono": "900000001",
        "documento_numero": "12345678",
        "documento_tipo": "dni",
        "dias_atraso": 4,  # corte = envio: los dias ajustados son los de atraso (4: 1 a 8)
        "titular": "ZZPRUEBA SINTETICO",
        "fecha_vencimiento_cuota": VENCIMIENTO,
    }
    return {**producto, **cambios}


def _evaluar(datos: DatosSpeech, whatsapp: str | None = WHATSAPP, **cambios):
    constructor = speech.ConstructorMensajes(datos, whatsapp)
    return evaluar_producto(_producto(**cambios), CORTE, CORTE, constructor)


# --- Huellas --------------------------------------------------------------------------------------


def test_la_huella_de_una_v1_es_la_de_siempre() -> None:
    v1 = DatosSpeech("Speech original", ORIGINAL)

    assert huella_speech(ORIGINAL) == HUELLA_DEL_SPEECH_ORIGINAL
    assert huella_de(v1) == HUELLA_DEL_SPEECH_ORIGINAL


def test_la_huella_de_una_v2_es_propia_estable_y_depende_del_contenido() -> None:
    uno = _v2(TODOS=(_texto("a"), _titular()))
    igual = _v2(TODOS=(_texto("a"), _titular()))
    otro_texto = _v2(TODOS=(_texto("b"), _titular()))
    otro_segmento = _v2(TODOS=(_texto("a"), _titular()), PREVENTIVA=(_texto("a"),))

    assert huella_de(uno) == huella_de(igual)
    assert len({huella_de(x) for x in (uno, otro_texto, otro_segmento)}) == 3
    assert len(huella_de(uno)) == 64


def test_la_huella_de_una_v2_no_depende_del_orden_de_los_segmentos() -> None:
    datos = _v2(TODOS=(_texto("a"), _titular()))

    al_reves = tuple(reversed(datos.expresiones))

    assert huella_expresiones(al_reves) == huella_expresiones(datos.expresiones)


def test_la_huella_de_una_v2_cambia_con_la_marca_obligatoria_o_los_argumentos() -> None:
    base = _v2(TODOS=(NodoVariable("titular", ()),))
    obligatoria = _v2(TODOS=(NodoVariable("titular", (), obligatoria=True),))
    con_funcion = _v2(TODOS=(_titular(LlamadaFuncion("primeros", (8,))),))
    con_otro_argumento = _v2(TODOS=(_titular(LlamadaFuncion("primeros", (9,))),))

    assert len({huella_de(x) for x in (base, obligatoria, con_funcion, con_otro_argumento)}) == 4


def test_la_huella_de_una_v2_esta_fijada() -> None:
    """Una campana ya creada guarda esta huella: si el calculo cambia, se rompe la comparacion."""
    datos = _v2(TODOS=(_texto("a"), _titular()), PREVENTIVA=(_texto("b"), _fecha()))

    assert huella_de(datos) == HUELLA_V2_FIJADA


def test_una_v2_convertida_tiene_huella_distinta_de_la_v1_de_la_que_sale() -> None:
    v1 = DatosSpeech("Speech original", ORIGINAL)

    assert huella_de(_convertida(ORIGINAL)) != huella_de(v1)


# --- Una v2 convertida desde una v1 es la misma v1 (C-5) ------------------------------------------


def _resultados_por_producto(datos: DatosSpeech, whatsapp: str | None):
    """Lo que la campana hace con cada producto de la matriz: fila, exclusion o falta de numero."""
    constructor = speech.ConstructorMensajes(datos, whatsapp)
    resultados = []
    for rango in RANGOS_SEGMENTO:
        dias = rango.desde if rango.desde is not None else rango.hasta
        for titular in TITULARES:
            for vencimiento in VENCIMIENTOS:
                producto = _producto(
                    dias_atraso=dias, titular=titular, fecha_vencimiento_cuota=vencimiento
                )
                resultados.append(evaluar_producto(producto, CORTE, CORTE, constructor))
    return resultados


@pytest.mark.parametrize("nombre", list(TODAS_LAS_VERSIONES))
def test_la_v2_convertida_da_las_mismas_filas_exclusiones_y_advertencias_que_la_v1(nombre) -> None:
    version = TODAS_LAS_VERSIONES[nombre]
    v1 = DatosSpeech(nombre, version)
    v2 = _convertida(version)

    comparados: list = []
    for whatsapp in NUMEROS:
        de_v1 = _resultados_por_producto(v1, whatsapp)
        de_v2 = _resultados_por_producto(v2, whatsapp)

        assert de_v2 == de_v1, (nombre, whatsapp)
        comparados += de_v1
    assert any(isinstance(r, FilaCarga) for r in comparados)  # se comparan filas de verdad
    assert any(isinstance(r, Exclusion) for r in comparados)  # exclusiones


@pytest.mark.parametrize("nombre", list(TODAS_LAS_VERSIONES))
def test_la_v2_convertida_da_los_mismos_mensajes_byte_a_byte(nombre) -> None:
    version = TODAS_LAS_VERSIONES[nombre]
    comparados = 0

    for whatsapp in NUMEROS:
        de_v1 = speech.ConstructorMensajes(DatosSpeech(nombre, version), whatsapp)
        de_v2 = speech.ConstructorMensajes(_convertida(version), whatsapp)
        for partes in version:
            for titular in TITULARES:
                for vencimiento in VENCIMIENTOS:
                    if not (titular and titular.strip()) or vencimiento is None:
                        continue  # sin dato, la campana excluye antes de pedir el mensaje
                    try:
                        esperado = de_v1.mensaje_de(partes.segmento, titular, vencimiento)
                    except FaltaWhatsapp:
                        with pytest.raises(FaltaWhatsapp):
                            de_v2.mensaje_de(partes.segmento, titular, vencimiento)
                        assert de_v2.requiere_whatsapp_faltante(partes.segmento)
                        continue
                    obtenido = de_v2.mensaje_de(partes.segmento, titular, vencimiento)
                    assert obtenido.encode("utf-8") == esperado.encode("utf-8")
                    comparados += 1

    assert comparados > 100


@pytest.mark.parametrize("nombre", list(TODAS_LAS_VERSIONES))
@pytest.mark.parametrize("whatsapp", NUMEROS)
def test_la_v2_convertida_da_los_mismos_largos_niveles_y_uso_de_whatsapp(nombre, whatsapp) -> None:
    version = TODAS_LAS_VERSIONES[nombre]

    de_v1 = speech.previsualizar(version, whatsapp)
    de_v2 = speech.previsualizar_v2(speech.convertir_a_v2(version), whatsapp)

    campos = lambda largos: [  # noqa: E731
        (x.rango.segmento, x.usa_whatsapp, x.largo_maximo, x.codigo) for x in largos
    ]
    assert campos(de_v2) == campos(de_v1)
    assert all(x.motivo_sin_cota is None for x in de_v2)


def test_la_conversion_marca_obligatorios_el_titular_y_la_fecha_y_nada_mas() -> None:
    for convertida in speech.convertir_a_v2(ORIGINAL):
        variables = [n for n in convertida.expresion.nodos if isinstance(n, NodoVariable)]
        obligatorias = {n.nombre for n in variables if n.obligatoria}

        assert obligatorias == {"titular", "fecha_vencimiento_cuota"}
        assert not any(n.obligatoria for n in variables if n.nombre == "whatsapp_contacto")


def test_convertir_no_toca_la_expresion_de_una_v1() -> None:
    antes = speech.expresion_de(ORIGINAL[0])

    speech.convertir_a_v2(ORIGINAL)

    assert speech.expresion_de(ORIGINAL[0]) == antes
    assert not any(isinstance(n, NodoVariable) and n.obligatoria for n in antes.nodos)


# --- Exclusiones: solo si la expresion del segmento usa la variable -------------------------------


SIN_TITULAR = (_texto("Tu cuota vence el "), _fecha(), _texto(". Paga hoy."))
SIN_FECHA = (_titular(), _texto(", tu cuota esta vencida. Paga hoy."))
CON_AMBAS = (_titular(), _texto(" vence el "), _fecha())


def test_una_v2_que_no_usa_el_titular_carga_un_producto_sin_titular_con_el_mensaje_exacto() -> None:
    for titular in (None, "", "   "):
        fila = _evaluar(_v2(TODOS=SIN_TITULAR), titular=titular)

        assert isinstance(fila, FilaCarga), titular
        assert fila.mensaje == "Tu cuota vence el 06/09/2026. Paga hoy."  # sin None ni huecos


def test_una_v2_que_usa_el_titular_lo_excluye_igual_que_hoy() -> None:
    for titular in (None, "", "   ", "\t\n"):
        resultado = _evaluar(_v2(TODOS=CON_AMBAS), titular=titular)

        assert resultado == Exclusion("000000000000000001", CodigoMowaMes.FALTA_TITULAR), titular


def test_una_v2_que_no_usa_la_fecha_carga_un_producto_sin_vencimiento_con_el_mensaje_exacto() -> (
    None
):
    fila = _evaluar(_v2(TODOS=SIN_FECHA), fecha_vencimiento_cuota=None)

    assert isinstance(fila, FilaCarga)
    assert fila.mensaje == "ZZPRUEBA SINTETICO, tu cuota esta vencida. Paga hoy."


def test_una_v2_que_usa_la_fecha_excluye_un_producto_sin_vencimiento() -> None:
    resultado = _evaluar(_v2(TODOS=CON_AMBAS), fecha_vencimiento_cuota=None)

    assert resultado == Exclusion("000000000000000001", CodigoMowaMes.FALTA_VENCIMIENTO)


def test_el_titular_largo_se_recorta_y_el_corto_no_deja_huecos() -> None:
    datos = _v2(TODOS=(_titular(LlamadaFuncion("primeros", (4,))), _texto("|"), _fecha()))

    largo = _evaluar(datos, titular="ABCDEFGH")
    corto = _evaluar(datos, titular="AB")

    assert (largo.mensaje, corto.mensaje) == ("ABCD|06/09/2026", "AB|06/09/2026")


def test_nombrar_la_variable_en_el_texto_fijo_no_cuenta_como_usarla() -> None:
    """Se decide sobre los nodos, nunca buscando el nombre en el texto."""
    texto = (_texto("Estimado titular "), _texto("[@titular] fecha_vencimiento_cuota"), _fecha())
    datos = _v2(TODOS=texto)

    fila = _evaluar(datos, titular=None)

    assert isinstance(fila, FilaCarga)
    assert fila.mensaje == "Estimado titular [@titular] fecha_vencimiento_cuota06/09/2026"
    constructor = speech.ConstructorMensajes(datos, WHATSAPP)
    assert not constructor.usa_titular(Segmento.DE_1_A_8)
    assert constructor.usa_vencimiento(Segmento.DE_1_A_8)


def test_una_variable_usada_solo_como_argumento_de_una_funcion_cuenta() -> None:
    como_argumento = NodoVariable(
        "whatsapp_contacto", (LlamadaFuncion("si_vacio", (ArgumentoVariable("titular"),)),)
    )
    datos = _v2(TODOS=(_texto("Cuota "), _fecha(), _texto(" "), como_argumento))
    constructor = speech.ConstructorMensajes(datos, WHATSAPP)

    resultado = _evaluar(datos, titular=None)

    assert constructor.usa_titular(Segmento.DE_1_A_8)
    assert resultado == Exclusion("000000000000000001", CodigoMowaMes.FALTA_TITULAR)


def test_el_uso_se_decide_por_segmento() -> None:
    datos = _v2(TODOS=SIN_TITULAR, DE_9_A_30=CON_AMBAS)
    constructor = speech.ConstructorMensajes(datos, WHATSAPP)

    sin_titular_1_a_8 = _evaluar(datos, titular=None, dias_atraso=4)
    sin_titular_9_a_30 = _evaluar(datos, titular=None, dias_atraso=10)

    assert isinstance(sin_titular_1_a_8, FilaCarga)
    assert isinstance(sin_titular_9_a_30, Exclusion)
    assert sin_titular_9_a_30.codigo is CodigoMowaMes.FALTA_TITULAR
    assert [constructor.usa_titular(r.segmento) for r in RANGOS_SEGMENTO] == [
        False,
        False,
        True,
        False,
        False,
        False,
    ]


def test_una_v1_siempre_necesita_el_titular_y_la_fecha() -> None:
    constructor = speech.ConstructorMensajes(DatosSpeech("v1", ORIGINAL), WHATSAPP)

    assert all(constructor.usa_titular(r.segmento) for r in RANGOS_SEGMENTO)
    assert all(constructor.usa_vencimiento(r.segmento) for r in RANGOS_SEGMENTO)
    assert all(constructor.usa_titular(r.segmento) for r in RANGOS_SEGMENTO)


# --- El orden de las exclusiones no cambia --------------------------------------------------------


def test_el_orden_de_las_exclusiones_de_una_v2_es_el_de_siempre() -> None:
    datos = _v2(TODOS=CON_AMBAS)
    sin_todo = dict(
        telefono=None, documento_numero=None, titular=None, fecha_vencimiento_cuota=None
    )
    pagare = "000000000000000001"

    orden = [
        (sin_todo, CodigoMowaMes.TELEFONO_INVALIDO),
        ({**sin_todo, "telefono": "900000001"}, CodigoMowaMes.FALTA_DOCUMENTO),
        (
            {**sin_todo, "telefono": "900000001", "documento_numero": "1", "dias_atraso": 500},
            CodigoMowaMes.SIN_SPEECH,
        ),
        (
            {**sin_todo, "telefono": "900000001", "documento_numero": "1"},
            CodigoMowaMes.FALTA_TITULAR,
        ),
        (
            {**sin_todo, "telefono": "900000001", "documento_numero": "1", "titular": "Z"},
            CodigoMowaMes.FALTA_VENCIMIENTO,
        ),
    ]
    for cambios, codigo in orden:
        assert _evaluar(datos, **cambios) == Exclusion(pagare, codigo), codigo


def test_la_falta_de_whatsapp_va_despues_de_titular_y_fecha_tambien_en_una_v2() -> None:
    con_enlace = NodoVariable("whatsapp_contacto", (LlamadaFuncion("enlace_whatsapp"),))
    datos = _v2(TODOS=(*CON_AMBAS, _texto(" "), con_enlace))

    sin_titular = _evaluar(datos, whatsapp=None, titular=None)
    completo = _evaluar(datos, whatsapp=None)

    assert sin_titular == Exclusion("000000000000000001", CodigoMowaMes.FALTA_TITULAR)
    assert completo is Segmento.DE_1_A_8


def test_un_segmento_que_no_usa_el_whatsapp_se_genera_sin_numero_en_una_v2() -> None:
    con_enlace = NodoVariable("whatsapp_contacto", (LlamadaFuncion("enlace_whatsapp"),))
    datos = _v2(TODOS=CON_AMBAS, DE_31_A_60=(*CON_AMBAS, con_enlace))

    sin_enlace = _evaluar(datos, whatsapp=None, dias_atraso=4)
    con_enlace_pedido = _evaluar(datos, whatsapp=None, dias_atraso=40)

    assert isinstance(sin_enlace, FilaCarga)
    assert con_enlace_pedido is Segmento.DE_31_A_60


# --- Los dias ajustados llegan a la expresion -----------------------------------------------------


def test_una_v2_puede_usar_los_dias_ajustados_a_la_fecha_de_envio() -> None:
    dias = NodoVariable("dias_atraso_ajustados", ())
    datos = _v2(TODOS=(_texto("Dias: "), dias))
    constructor = speech.ConstructorMensajes(datos, WHATSAPP)
    envio = date(2026, 9, 17)  # tres dias despues del corte

    resultado = evaluar_producto(_producto(dias_atraso=4), CORTE, envio, constructor)

    assert isinstance(resultado, FilaCarga)
    assert resultado.mensaje == "Dias: 7"  # 4 de la sabana + 3 hasta el envio


# --- Previsualizacion: cota, nivel, ejemplo y "sin maximo calculable" -----------------------------


def test_la_previsualizacion_v2_da_cota_nivel_y_ejemplo_por_segmento() -> None:
    cuerpo = (_titular(LlamadaFuncion("primeros", (8,))), _texto(" vence el "), _fecha())
    por_segmento = speech.previsualizar_v2(_v2(TODOS=cuerpo).expresiones, WHATSAPP)

    assert [x.rango.segmento for x in por_segmento] == [r.segmento for r in RANGOS_SEGMENTO]
    primero = por_segmento[0]
    assert (primero.largo_maximo, primero.codigo, primero.usa_whatsapp) == (28, None, False)
    assert primero.ejemplo == "XXXXXXXX vence el 05/10/2026"
    assert primero.motivo_sin_cota is None


def test_la_cota_cruza_los_150_y_los_160_con_su_codigo() -> None:
    def largo(n: int):
        return _v2(TODOS=(_texto("x" * n),)).expresiones

    por_largo = {n: speech.previsualizar_v2(largo(n), WHATSAPP)[0] for n in (150, 151, 160, 161)}

    assert [por_largo[n].codigo for n in (150, 151, 160, 161)] == [
        None,
        CodigoMowaMes.MENSAJE_EXCEDE_150,
        CodigoMowaMes.MENSAJE_EXCEDE_150,
        CodigoMowaMes.MENSAJE_EXCEDE_160,
    ]


def test_sin_cota_se_informa_sin_maximo_calculable_con_su_motivo_y_sin_codigo() -> None:
    sin_cota = (_titular(), _texto(" vence"))  # el titular completo: su largo depende del dato
    por_segmento = speech.previsualizar_v2(_v2(TODOS=sin_cota).expresiones, WHATSAPP)

    primero = por_segmento[0]
    assert primero.largo_maximo is None
    assert primero.codigo is None
    assert primero.motivo_sin_cota.codigo is CodigoTexto.SIN_COTA_VARIABLE  # type: ignore[union-attr]
    assert primero.motivo_sin_cota.nodo == 0  # type: ignore[union-attr]
    assert primero.ejemplo == "XXXXXXXX vence"


def test_con_un_speech_sin_cota_mensaje_excede_160_sigue_excluyendo_por_fila() -> None:
    """El control por fila es sobre el mensaje real, aunque no se pueda calcular el maximo."""
    largo_fijo = "x" * (LARGO_MAXIMO - 5)
    datos = _v2(TODOS=(_titular(), _texto(largo_fijo)))

    cabe = _evaluar(datos, titular="ABC")  # 3 + 155 = 158
    excede = _evaluar(datos, titular="ABCDEFGHIJ")  # 10 + 155 = 165

    assert isinstance(cabe, FilaCarga) and len(cabe.mensaje) == 158
    assert excede == Exclusion("000000000000000001", CodigoMowaMes.MENSAJE_EXCEDE_160)
    assert speech.previsualizar_v2(datos.expresiones, WHATSAPP)[0].largo_maximo is None


def test_los_150_se_advierten_en_la_fila_de_una_v2() -> None:
    datos = _v2(TODOS=(_texto("x" * 155),))

    fila = _evaluar(datos)

    assert isinstance(fila, FilaCarga)
    assert fila.advertencias == (CodigoMowaMes.MENSAJE_EXCEDE_150,)


def test_el_ejemplo_de_un_segmento_que_usa_el_whatsapp_sin_numero_es_none() -> None:
    enlace = NodoVariable("whatsapp_contacto", (LlamadaFuncion("enlace_whatsapp"),))
    expresiones = _v2(TODOS=(_texto("Info "), enlace)).expresiones

    sin_numero = speech.previsualizar_v2(expresiones, None)[0]
    con_numero = speech.previsualizar_v2(expresiones, WHATSAPP)[0]

    assert (sin_numero.usa_whatsapp, sin_numero.ejemplo) == (True, None)
    assert con_numero.ejemplo == "Info https://wa.me/+51900000123"
    assert sin_numero.largo_maximo == con_numero.largo_maximo == 31  # el enlace mide 26


def test_el_ejemplo_usa_los_dias_del_inicio_del_rango_de_cada_segmento() -> None:
    expresiones = _v2(TODOS=(NodoVariable("dias_atraso_ajustados", ()),)).expresiones

    ejemplos = [x.ejemplo for x in speech.previsualizar_v2(expresiones, WHATSAPP)]

    assert ejemplos == ["0", "1", "9", "31", "61", "91"]


def test_un_segmento_que_no_compila_no_aparece_en_la_previsualizacion() -> None:
    mal = NodoVariable("inventada", ())
    expresiones = _v2(TODOS=(_texto("ok"),), DE_9_A_30=(mal,)).expresiones

    segmentos = [x.rango.segmento for x in speech.previsualizar_v2(expresiones, WHATSAPP)]

    assert Segmento.DE_9_A_30 not in segmentos and len(segmentos) == 5


def test_un_segmento_fuera_de_los_limites_no_aparece_en_la_previsualizacion() -> None:
    demasiados = tuple(_texto("a") for _ in range(201))
    expresiones = _v2(TODOS=(_texto("ok"),), PREVENTIVA=demasiados).expresiones

    segmentos = [x.rango.segmento for x in speech.previsualizar_v2(expresiones, WHATSAPP)]

    assert Segmento.PREVENTIVA not in segmentos and len(segmentos) == 5


def test_si_el_ejemplo_no_se_puede_evaluar_no_se_muestra() -> None:
    """Dividir por cero falla al evaluar: el segmento sigue en la lista, sin ejemplo."""
    dividir = NodoVariable(
        "dias_atraso_ajustados", (LlamadaFuncion("dividir", (0,)), LlamadaFuncion("a_texto"))
    )
    expresiones = _v2(TODOS=(_texto("ok"),), DE_9_A_30=(dividir,)).expresiones

    por_segmento = {x.rango.segmento: x for x in speech.previsualizar_v2(expresiones, WHATSAPP)}

    assert (
        por_segmento[Segmento.DE_9_A_30].largo_maximo,
        por_segmento[Segmento.DE_9_A_30].ejemplo,
    ) == (None, None)
    assert por_segmento[Segmento.DE_1_A_8].ejemplo == "ok"


# --- Validar una v2 al guardar (RF-46) ------------------------------------------------------------


def _problemas(datos: DatosSpeech) -> list[tuple]:
    return [
        (p.segmento, p.campo, p.problema.codigo if p.problema else None)
        for p in speech.problemas_de(datos)
    ]


def test_una_v2_valida_no_tiene_problemas() -> None:
    assert speech.problemas_de(_v2(TODOS=CON_AMBAS)) == ()


def test_una_v2_necesita_los_6_segmentos_una_vez_cada_uno() -> None:
    datos = _v2(TODOS=CON_AMBAS)
    sin_uno = replace(datos, expresiones=datos.expresiones[1:])
    repetido = replace(datos, expresiones=(*datos.expresiones, datos.expresiones[0]))

    assert _problemas(sin_uno) == [(None, "segmentos", None)]
    assert _problemas(repetido) == [(None, "segmentos", None)]


def test_un_segmento_sin_contenido_no_se_guarda() -> None:
    datos = _v2(TODOS=CON_AMBAS, DE_9_A_30=())

    assert _problemas(datos) == [(Segmento.DE_9_A_30, "expresion", None)]


def test_los_problemas_del_motor_viajan_con_su_codigo_y_su_ubicacion() -> None:
    mal = NodoVariable("inventada", ())
    con_parametro_malo = _titular(LlamadaFuncion("primeros", (0,)))
    datos = _v2(TODOS=CON_AMBAS, DE_1_A_8=(_texto("a"), mal), DE_61_A_90=(con_parametro_malo,))

    por_segmento = {p.segmento: p for p in speech.problemas_de(datos)}

    uno = por_segmento[Segmento.DE_1_A_8]
    assert (uno.campo, uno.problema.codigo, uno.problema.nodo) == (
        "expresion",
        CodigoTexto.VARIABLE_DESCONOCIDA,
        1,
    )
    otro = por_segmento[Segmento.DE_61_A_90]
    assert (otro.problema.codigo, otro.problema.funcion, otro.problema.parametro) == (
        CodigoTexto.PARAMETRO_INVALIDO,
        0,
        "n",
    )


def test_el_limite_de_nodos_del_motor_aplica_a_una_v2() -> None:
    demasiados = tuple(_texto("a") for _ in range(201))

    assert _problemas(_v2(TODOS=CON_AMBAS, PREVENTIVA=demasiados)) == [
        (Segmento.PREVENTIVA, "expresion", CodigoTexto.LIMITE_EXCEDIDO)
    ]


def test_el_nombre_de_una_v2_se_valida_como_el_de_una_v1() -> None:
    assert _problemas(replace(_v2(TODOS=CON_AMBAS), nombre="  ")) == [(None, "nombre", None)]


def test_una_v1_con_expresiones_o_una_v2_con_partes_es_un_problema_de_formato() -> None:
    v1_con_expresiones = DatosSpeech("x", ORIGINAL, _v2(TODOS=CON_AMBAS).expresiones)
    v2_con_partes = replace(_v2(TODOS=CON_AMBAS), partes=ORIGINAL)

    assert (None, "formato", None) in _problemas(v1_con_expresiones)
    assert (None, "formato", None) in _problemas(v2_con_partes)


def test_una_v2_puede_usar_funciones_y_los_problemas_de_una_v1_no_cambian() -> None:
    v1_mala = DatosSpeech("v1", tuple(replace(p, parte_1="a [@titular]") for p in ORIGINAL))

    assert {p.campo for p in speech.problemas_de(v1_mala)} == {"parte_1"}
    assert all(p.problema is None for p in speech.problemas_de(v1_mala))


# --- El constructor de una v2 ---------------------------------------------------------------------


def test_una_expresion_v2_que_no_compila_queda_en_su_segmento_y_no_rompe_al_constructor() -> None:
    mal = NodoVariable("inventada", ())
    datos = _v2(TODOS=CON_AMBAS, DE_9_A_30=(mal,))
    constructor = speech.ConstructorMensajes(datos, WHATSAPP)

    ok = constructor.mensaje_de(Segmento.DE_1_A_8, "ZZPRUEBA", VENCIMIENTO)
    with pytest.raises(MensajeNoGenerable) as error:
        constructor.mensaje_de(Segmento.DE_9_A_30, "ZZPRUEBA", VENCIMIENTO)

    assert ok == "ZZPRUEBA vence el 06/09/2026"
    assert error.value.codigos == (CodigoTexto.VARIABLE_DESCONOCIDA,)


def test_el_whatsapp_de_una_v2_es_una_constante_plegada_al_compilar() -> None:
    enlace = NodoVariable("whatsapp_contacto", (LlamadaFuncion("enlace_whatsapp"),))
    constructor = speech.ConstructorMensajes(_v2(TODOS=(_texto("Info "), enlace)), WHATSAPP)

    mensaje = constructor.mensaje_de(Segmento.DE_1_A_8, None, None)

    assert mensaje == "Info https://wa.me/+51900000123"


def test_un_whatsapp_invalido_en_una_v2_queda_en_los_segmentos_que_lo_usan() -> None:
    enlace = NodoVariable("whatsapp_contacto", (LlamadaFuncion("enlace_whatsapp"),))
    datos = _v2(TODOS=CON_AMBAS, DE_31_A_60=(*CON_AMBAS, enlace))
    constructor = speech.ConstructorMensajes(datos, "123")

    assert constructor.mensaje_de(Segmento.DE_1_A_8, "Z", VENCIMIENTO) == "Z vence el 06/09/2026"
    with pytest.raises(MensajeNoGenerable) as error:
        constructor.mensaje_de(Segmento.DE_31_A_60, "Z", VENCIMIENTO)
    assert error.value.codigos == (CodigoTexto.TELEFONO_INVALIDO,)


# --- variables_usadas -----------------------------------------------------------------------------


def test_variables_usadas_mira_nodos_y_argumentos_y_no_el_texto() -> None:
    expresion = Expresion(
        (
            _texto("titular fecha_vencimiento_cuota [@whatsapp_contacto]"),
            NodoVariable(
                "dias_atraso_ajustados", (LlamadaFuncion("sumar", (ArgumentoVariable("x"), 3)),)
            ),
            NodoVariable("titular", (LlamadaFuncion("primeros", (4,)),)),
        )
    )

    assert variables_usadas(expresion) == {"dias_atraso_ajustados", "x", "titular"}
    assert variables_usadas(Expresion()) == frozenset()
    assert variables_usadas(Expresion((_texto("solo texto"),))) == frozenset()


# --- Lo que el repositorio guarda, sin base ---------------------------------------------------


def test_el_repositorio_guarda_una_v1_con_partes_y_una_v2_con_expresiones() -> None:
    from app.adapters.persistence.repositorio_mowa_mes_postgres import (
        _valores_de_contenido,
        datos_de_fila,
    )

    v1 = _valores_de_contenido(DatosSpeech("v1", ORIGINAL))
    datos_v2 = _v2(TODOS=(_texto("a"), _titular()))
    v2 = _valores_de_contenido(datos_v2)

    assert (v1["formato"], v1["expresiones"], len(v1["partes"])) == ("v1", None, 6)
    assert (v2["formato"], v2["partes"], len(v2["expresiones"])) == ("v2", [], 6)
    assert datos_de_fila("v2", v2["partes"], v2["formato"], v2["expresiones"]) == replace(
        datos_v2, nombre="v2"
    )
    assert datos_de_fila("v1", v1["partes"], v1["formato"], v1["expresiones"]).partes == ORIGINAL


def test_una_v2_con_tildes_argumentos_y_obligatoria_sobrevive_al_viaje_por_json() -> None:
    """Lo que hace JSONB: serializa y relee, con tildes sin escapar y los argumentos como lista."""
    from app.adapters.persistence.repositorio_mowa_mes_postgres import (
        _valores_de_contenido,
        datos_de_fila,
    )

    datos = _v2(
        TODOS=(
            NodoVariable("titular", (LlamadaFuncion("primeros", (8,)),), obligatoria=True),
            _texto(" ñandú — vence el "),
            _fecha(),
        )
    )
    valores = _valores_de_contenido(datos)

    de_la_base = json.loads(json.dumps(valores["expresiones"], ensure_ascii=False))
    leidos = datos_de_fila("v2", json.loads(json.dumps(valores["partes"])), "v2", de_la_base)

    assert leidos == replace(datos, nombre="v2")
    assert huella_de(leidos) == huella_de(datos)
