# ruff: noqa: E501  (las huellas SHA-256 son constantes de 64 caracteres)
"""Prueba de oro de MOWA MES M1 (B5, RF-54): el speech evaluado con el motor de texto enriquecido
da exactamente lo mismo que el camino de antes.

Se compara de dos maneras. Contra CONSTANTES congeladas en HEAD 3e567d7 con el codigo viejo
(`oro_mowa_mes_congelados.py`: los 6 mensajes del Speech original y un SHA-256 de toda la matriz),
siempre: sobreviven al retiro del camino viejo. Y contra el camino viejo EN VIVO
(`plantilla_mensaje` + `GeneradorCargas` + `contexto_fila`), que sigue en el codigo solo como
referencia hasta cerrar M2: al retirarlo (B6) se borran solo las comparaciones en vivo (las pruebas
marcadas "en vivo"). `previsualizar` se compara contra una copia textual de su aritmetica anterior y
contra los valores del Speech original congelados en HEAD.

Titulares, numeros y textos sinteticos.
"""

from dataclasses import replace
from datetime import date

import pytest

from app.core.entities.mapeo import CampoSalida, DefinicionCarga
from app.core.entities.mowa_mes import (
    LARGO_NUMERO_WHATSAPP,
    LARGO_TITULAR,
    LARGO_VENCIMIENTO,
    PREFIJO_WHATSAPP,
    RANGOS_SEGMENTO,
    VARIABLE_WHATSAPP,
    CodigoMowaMes,
    DatosSpeech,
    FaltaWhatsapp,
    MensajeNoGenerable,
    PartesSegmento,
    Segmento,
)
from app.core.entities.texto_enriquecido import PREFIJO_WHATSAPP as PREFIJO_DEL_NUCLEO
from app.core.entities.texto_enriquecido import (
    CodigoTexto,
    Expresion,
    LlamadaFuncion,
    NodoTexto,
    NodoVariable,
    TipoValor,
)
from app.core.services.mapeo_campos.generador import GeneradorCargas
from app.core.services.plataformas.mowa_mes import speech
from app.core.services.plataformas.mowa_mes.campana import (
    Exclusion,
    FilaCarga,
    evaluar_producto,
    huella_speech,
)
from app.core.services.texto_enriquecido import evaluador
from tests.oro_mowa_mes_congelados import (
    MATRIZ_CASOS,
    MATRIZ_CASOS_SIN_WHATSAPP,
    MATRIZ_HUELLA,
    MENSAJES_DEL_ORIGINAL,
)
from tests.oro_mowa_mes_datos import (
    NUMEROS,
    ORIGINAL,
    TITULARES,
    TODAS_LAS_VERSIONES,
    VENCIMIENTO,
    VENCIMIENTOS,
    VERSIONES_SINTETICAS,
    WHATSAPP,
    huella_de_la_matriz,
    mensajes_de_la_matriz,
)

# --- Huellas (RF-MM-17): fijadas en HEAD 3e567d7 antes de tocar speech.py -------------------

HUELLA_DEL_SPEECH_ORIGINAL = "297c227cfdd0bb5e1636e08d4ed6cebab971d724c84223acfdb0cfebc2fcf88a"
HUELLAS_SINTETICAS = {
    "espacios_extremos": "b4f741b91fdc7e6378197f409dad4fe76e0212b79ee8f06b6bb42656860533cc",
    "tildes_y_enes": "765d52eef7f613cf1b51b1a696d0d6cd41adf5d69f91d4b75ece2965aed53835",
    "corchetes_sueltos": "5918bb4a364481894925e0e5d527af4377f49612775e37c86d2c34d11a3e2a87",
    "whatsapp_repetido_y_en_ambas": "b909a709c1db93586dce41a67f40874647ed9b5cef2fbd4b4d3caed71a1a358e",
    "whatsapp_solo_en_parte_1": "4d54d09558321f3d798b819bb39131af57f007cbe5abcdb375f2fea81fed4951",
    "whatsapp_solo_en_parte_2": "ee584eaaa0a7ba3e614f4d8732bb540e5f05a074e7bea0d9ca45fbbadcba54eb",
    "solo_whatsapp": "14fe4f86746cfd6844b3d064fcba46ffc321b8c2229b0d77048bcaec34fccc08",
    "otra_escritura_de_whatsapp": "ad5498556d468d433a82d85ec73ceb5b52b433722b7254f4fd741d4e405eddf9",
    "vacias": "a7731a26d8bf74a9c55bd3112cd407f0bed1c3e6f1f853335cb591cd067ebe9d",
    "saltos_de_linea": "2354bd735579948d8582dd1ac9106b584bbffffbc762352b5a711dba79202d07",
    "arrobas_sin_corchete": "3714f66fef18f826a4c7aea227c25810667f9a0f104b70cfffbe2400e9757506",
    "un_texto_distinto_por_segmento": (
        "6ddcbca14ba8905b0b9559add00ea4d09d51c5a4d992b9fd0c31cf959e2b5421"
    ),
}

# Speech original con el WhatsApp del documento: (largo maximo, codigo, usa_whatsapp),
# congelado en HEAD 3e567d7. `9 a 30` da 156 y `31 a 60` justo 150.
LARGOS_DEL_ORIGINAL = {
    Segmento.PREVENTIVA: (100, None, False),
    Segmento.DE_1_A_8: (143, None, False),
    Segmento.DE_9_A_30: (156, CodigoMowaMes.MENSAJE_EXCEDE_150, False),
    Segmento.DE_31_A_60: (150, None, True),
    Segmento.DE_61_A_90: (144, None, True),
    Segmento.DE_91_A_120: (144, None, True),
}


def test_las_huellas_del_speech_original_y_de_las_partes_sinteticas_no_cambian() -> None:
    assert huella_speech(ORIGINAL) == HUELLA_DEL_SPEECH_ORIGINAL
    assert set(HUELLAS_SINTETICAS) == set(VERSIONES_SINTETICAS)
    for nombre, version in VERSIONES_SINTETICAS.items():
        assert huella_speech(version) == HUELLAS_SINTETICAS[nombre], nombre


# --- Referencias: el camino de antes -----------------------------------------------------------


def _mensaje_de_antes(
    partes: PartesSegmento, whatsapp: str | None, titular, vencimiento
) -> str | FaltaWhatsapp:
    try:
        plantilla = speech.plantilla_mensaje(partes, whatsapp)
    except FaltaWhatsapp as error:
        return error
    definicion = DefinicionCarga(
        nombre="referencia", campos=(CampoSalida(speech.CAMPO_MENSAJE, plantilla),)
    )
    generador = GeneradorCargas(definicion, speech.CAMPOS_CONTEXTO)
    fila, _ = generador.generar_fila(speech.contexto_fila(titular, vencimiento, whatsapp), 1)
    return fila[speech.CAMPO_MENSAJE]


def _previsualizar_de_antes(partes, whatsapp):
    """Copia textual de `previsualizar` antes de M1: aritmetica fija de 8 + 10 + texto + enlace."""
    por_segmento = {p.segmento: p for p in partes}
    largo_enlace = len(PREFIJO_WHATSAPP) + LARGO_NUMERO_WHATSAPP
    resultado = []
    for rango in RANGOS_SEGMENTO:
        segmento = por_segmento.get(rango.segmento)
        if segmento is None:
            continue
        texto = segmento.parte_1 + segmento.parte_2
        cantidad_variables = texto.count(VARIABLE_WHATSAPP)
        largo = (
            LARGO_TITULAR
            + LARGO_VENCIMIENTO
            + len(texto)
            - cantidad_variables * (len(VARIABLE_WHATSAPP) - largo_enlace)
        )
        ejemplo = None
        if not cantidad_variables or whatsapp:
            enlace = speech.enlace_whatsapp(whatsapp) if whatsapp else ""
            ejemplo = (
                "X" * LARGO_TITULAR
                + segmento.parte_1.replace(VARIABLE_WHATSAPP, enlace)
                + "dd/mm/yyyy"
                + segmento.parte_2.replace(VARIABLE_WHATSAPP, enlace)
            )
        resultado.append(
            (rango, cantidad_variables > 0, largo, speech.codigo_por_largo(largo), ejemplo)
        )
    return tuple(resultado)


def _de_ahora(largos):
    return tuple((x.rango, x.usa_whatsapp, x.largo_maximo, x.codigo, x.ejemplo) for x in largos)


# --- Mensajes: byte a byte contra el camino de antes --------------------------------------------


@pytest.mark.parametrize("nombre", list(TODAS_LAS_VERSIONES))
def test_en_vivo_el_mensaje_es_identico_byte_a_byte_al_camino_de_antes(nombre) -> None:
    version = TODAS_LAS_VERSIONES[nombre]
    comparados = 0

    for whatsapp in NUMEROS:
        constructor = speech.ConstructorMensajes(version, whatsapp)
        for partes in version:
            for titular in TITULARES:
                for vencimiento in VENCIMIENTOS:
                    esperado = _mensaje_de_antes(partes, whatsapp, titular, vencimiento)
                    if isinstance(esperado, FaltaWhatsapp):
                        with pytest.raises(FaltaWhatsapp):
                            constructor.mensaje_de(partes.segmento, titular, vencimiento)
                        assert constructor.requiere_whatsapp_faltante(partes.segmento)
                        continue
                    obtenido = constructor.mensaje_de(partes.segmento, titular, vencimiento)

                    assert obtenido == esperado, (nombre, partes.segmento, whatsapp, titular)
                    assert obtenido.encode("utf-8") == esperado.encode("utf-8")
                    comparados += 1

    assert comparados > 100  # la comparacion se ejercita de verdad


def test_los_seis_mensajes_del_speech_original_son_los_congelados_en_head() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, WHATSAPP)

    obtenidos = {
        partes.segmento.value: constructor.mensaje_de(
            partes.segmento, "ZZPRUEBA SINTETICO", VENCIMIENTO
        )
        for partes in ORIGINAL
    }

    assert obtenidos == MENSAJES_DEL_ORIGINAL
    assert len(MENSAJES_DEL_ORIGINAL) == len(RANGOS_SEGMENTO)


def test_toda_la_matriz_de_mensajes_da_la_huella_congelada_en_head() -> None:
    # Versiones x segmentos x numeros x titulares x vencimientos, en orden estable. Calculada en
    # HEAD 3e567d7 con el codigo viejo; aqui con el motor.
    filas = mensajes_de_la_matriz(speech.ConstructorMensajes)

    assert len(filas) == MATRIZ_CASOS
    assert sum(fila[-1] is None for fila in filas) == MATRIZ_CASOS_SIN_WHATSAPP
    assert huella_de_la_matriz(filas) == MATRIZ_HUELLA


def test_el_mensaje_del_speech_original_conserva_su_texto_conocido() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, WHATSAPP)

    assert constructor.mensaje_de(Segmento.DE_1_A_8, "ZZPRUEBA SINTETICO", VENCIMIENTO) == (
        "ZZPRUEBA Caja Cusco te informa que tu cuota venció el 05/09/2026, acércate a pagar"
        " a nuestras agencias, agentes KASNET o a través de Wayki app."
    )
    assert constructor.mensaje_de(Segmento.DE_31_A_60, "ZZPRUEBA", VENCIMIENTO).endswith(
        "INFO por https://wa.me/+51900000123"
    )


def test_los_segmentos_con_whatsapp_sin_numero_quedan_sin_compilar() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, None)

    con_whatsapp = {p.segmento for p in ORIGINAL if speech.usa_whatsapp(p)}
    assert con_whatsapp == {Segmento.DE_31_A_60, Segmento.DE_61_A_90, Segmento.DE_91_A_120}
    for partes in ORIGINAL:
        assert constructor.requiere_whatsapp_faltante(partes.segmento) == (
            partes.segmento in con_whatsapp
        )
        if partes.segmento in con_whatsapp:
            with pytest.raises(FaltaWhatsapp) as error:
                constructor.mensaje_de(partes.segmento, "ZZPRUEBA", VENCIMIENTO)
            assert error.value.segmentos == (partes.segmento,)


def test_el_texto_del_usuario_con_corchetes_no_se_interpreta_nunca() -> None:
    # `problemas_de` rechaza '[@' al guardar; aunque llegara una version asi, el motor la recibe
    # como texto fijo (la expresion se arma sin pasar por la sintaxis de texto).
    partes = replace(ORIGINAL[0], parte_1=" [@titular] [@@] [@ ", parte_2=" [@")
    constructor = speech.ConstructorMensajes((partes,), WHATSAPP)

    mensaje = constructor.mensaje_de(partes.segmento, "ZZPRUEBA", VENCIMIENTO)

    assert mensaje == "ZZPRUEBA [@titular] [@@] [@ 05/09/2026 [@"


def test_problemas_de_sigue_rechazando_la_referencia_a_campos() -> None:
    for texto in ("[@x]", " [@", "a[@@]b", "[titular] [fecha] [@"):
        version = DatosSpeech("con referencia", tuple(replace(p, parte_2=texto) for p in ORIGINAL))

        problemas = speech.problemas_de(version)

        assert {(p.segmento, p.campo) for p in problemas} == {
            (p.segmento, "parte_2") for p in ORIGINAL
        }


def test_un_titular_en_blanco_no_llega_al_mensaje_y_si_llegara_el_motor_lo_da_por_vacio() -> None:
    # Camino real: campana.py excluye un titular en blanco (falta_titular) antes de armar el
    # mensaje. Solo si se llamara directo, el motor lo trata como vacio (D10) en lugar de conservar
    # los espacios como hacia `titular[:8]`.
    constructor = speech.ConstructorMensajes(ORIGINAL, WHATSAPP)

    mensaje = constructor.mensaje_de(Segmento.DE_1_A_8, "   ", VENCIMIENTO)

    assert mensaje.startswith(ORIGINAL[1].parte_1)


def test_un_whatsapp_invalido_no_sale_como_un_sms_sin_enlace_sino_como_error() -> None:
    # La configuracion y la campana validan el numero (RF-02) antes de construir. Si uno invalido
    # llegara igual, el motor lo informa y el constructor lanza: no sale un SMS sin enlace en silencio.
    constructor = speech.ConstructorMensajes(ORIGINAL, "51900000456")

    with pytest.raises(MensajeNoGenerable) as error:
        constructor.mensaje_de(Segmento.DE_31_A_60, "ZZPRUEBA", VENCIMIENTO)

    assert error.value.segmento is Segmento.DE_31_A_60
    assert error.value.codigos == (CodigoTexto.TELEFONO_INVALIDO,)
    assert [p.codigo for p in error.value.problemas] == [CodigoTexto.TELEFONO_INVALIDO]
    assert "telefono_invalido" in str(error.value)
    assert Segmento.DE_31_A_60.value in str(error.value)
    assert not isinstance(error.value, ValueError)  # una excepcion propia, con nombre


def test_un_segmento_sin_whatsapp_no_se_ve_afectado_por_un_numero_invalido() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, "51900000456")

    mensaje = constructor.mensaje_de(Segmento.DE_9_A_30, "ZZPRUEBA", VENCIMIENTO)

    assert mensaje.startswith("ZZPRUEBA Caja Cusco")


def test_un_dato_que_no_es_del_tipo_del_campo_lanza_en_lugar_de_dejar_un_hueco() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, WHATSAPP)

    with pytest.raises(MensajeNoGenerable) as error:
        constructor.mensaje_de(Segmento.DE_9_A_30, "ZZPRUEBA", "no es una fecha")

    assert error.value.codigos == (CodigoTexto.NO_ES_FECHA,)


def test_los_datos_validos_y_los_vacios_no_lanzan() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, WHATSAPP)

    for titular in TITULARES:
        for vencimiento in VENCIMIENTOS:
            constructor.mensaje_de(Segmento.DE_31_A_60, titular, vencimiento)


def test_partes_muy_largas_y_con_muchos_whatsapp_no_topan_con_los_limites_del_motor() -> None:
    parte_1 = ("x" * 40 + VARIABLE_WHATSAPP) * 300  # 300 variables y 12 000 caracteres de texto
    parte_2 = "y" * 20_000
    partes = PartesSegmento(Segmento.DE_9_A_30, parte_1, parte_2)
    constructor = speech.ConstructorMensajes((partes,), WHATSAPP)

    mensaje = constructor.mensaje_de(partes.segmento, "ZZPRUEBA", VENCIMIENTO)

    assert mensaje == _mensaje_de_antes(partes, WHATSAPP, "ZZPRUEBA", VENCIMIENTO)
    largo = speech.previsualizar((partes,), WHATSAPP)[0]
    assert largo.largo_maximo == len(mensaje)


# --- Previsualizacion: largo, codigo, usa_whatsapp y ejemplo ------------------------------------


@pytest.mark.parametrize("nombre", list(TODAS_LAS_VERSIONES))
@pytest.mark.parametrize("whatsapp", NUMEROS)
def test_previsualizar_entero_es_identico_al_de_antes(nombre, whatsapp) -> None:
    version = TODAS_LAS_VERSIONES[nombre]

    ahora = _de_ahora(speech.previsualizar(version, whatsapp))

    assert ahora == _previsualizar_de_antes(version, whatsapp)


def test_previsualizar_el_speech_original_da_los_valores_congelados_en_head() -> None:
    largos = {x.rango.segmento: x for x in speech.previsualizar(ORIGINAL, WHATSAPP)}

    assert {
        segmento: (x.largo_maximo, x.codigo, x.usa_whatsapp) for segmento, x in largos.items()
    } == LARGOS_DEL_ORIGINAL
    assert largos[Segmento.DE_9_A_30].largo_maximo == 156


def test_el_largo_previsto_es_el_del_mensaje_mas_largo_que_se_construye() -> None:
    for nombre, version in TODAS_LAS_VERSIONES.items():
        constructor = speech.ConstructorMensajes(version, WHATSAPP)
        for largo in speech.previsualizar(version, WHATSAPP):
            mensaje = constructor.mensaje_de(largo.rango.segmento, "12345678", date(2026, 12, 31))
            assert largo.largo_maximo == len(mensaje), (nombre, largo.rango.segmento)


def _con_parte_2(largo_total: int) -> tuple[PartesSegmento, ...]:
    # mensaje = titular 8 + parte 1 + fecha 10 + parte 2, en el segmento 1 a 8 (sin whatsapp)
    base = ORIGINAL[1]
    relleno = "x" * (largo_total - LARGO_TITULAR - len(base.parte_1) - LARGO_VENCIMIENTO)
    return tuple(
        replace(p, parte_2=relleno) if p.segmento is base.segmento else p for p in ORIGINAL
    )


@pytest.mark.parametrize(
    ("largo", "codigo"),
    [
        (149, None),
        (150, None),
        (151, CodigoMowaMes.MENSAJE_EXCEDE_150),
        (159, CodigoMowaMes.MENSAJE_EXCEDE_150),
        (160, CodigoMowaMes.MENSAJE_EXCEDE_150),
        (161, CodigoMowaMes.MENSAJE_EXCEDE_160),
    ],
)
def test_los_bordes_de_150_y_160_por_previsualizar_y_por_el_mensaje(largo, codigo) -> None:
    version = _con_parte_2(largo)

    previsto = {x.rango.segmento: x for x in speech.previsualizar(version, WHATSAPP)}[
        Segmento.DE_1_A_8
    ]
    fila = _evaluar(speech.ConstructorMensajes(version, WHATSAPP))

    assert (previsto.largo_maximo, previsto.codigo) == (largo, codigo)
    if codigo is CodigoMowaMes.MENSAJE_EXCEDE_160:
        assert fila == Exclusion("000000000000000001", codigo)
    else:
        assert isinstance(fila, FilaCarga)
        assert len(fila.mensaje) == largo
        assert fila.advertencias == (() if codigo is None else (codigo,))


# --- Exclusiones: el orden lo sigue fijando campana.py ------------------------------------------


def _producto(**cambios) -> dict:
    producto = {
        "pagare": "000000000000000001",
        "telefono": "987654321",
        "documento_numero": "12345678",
        "documento_tipo": "dni",
        "dias_atraso": 4,
        "titular": "ZZPRUEBA SINTETICO",
        "fecha_vencimiento_cuota": date(2026, 9, 5),
    }
    return {**producto, **cambios}


def _evaluar(constructor, **cambios):
    # corte y envio el mismo dia: los dias ajustados son los de atraso
    dia = date(2026, 9, 14)
    return evaluar_producto(_producto(**cambios), dia, dia, constructor)


@pytest.mark.parametrize("titular", [None, "", "   ", "\t\n"])
def test_un_titular_vacio_o_en_blanco_se_excluye_antes_del_mensaje(titular) -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, WHATSAPP)

    assert _evaluar(constructor, titular=titular) == Exclusion(
        "000000000000000001", CodigoMowaMes.FALTA_TITULAR
    )


def test_un_vencimiento_vacio_se_excluye_despues_del_titular() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, WHATSAPP)

    assert _evaluar(constructor, fecha_vencimiento_cuota=None) == Exclusion(
        "000000000000000001", CodigoMowaMes.FALTA_VENCIMIENTO
    )
    assert _evaluar(constructor, titular="  ", fecha_vencimiento_cuota=None) == Exclusion(
        "000000000000000001", CodigoMowaMes.FALTA_TITULAR
    )


def test_la_falta_de_whatsapp_va_despues_del_titular_y_del_vencimiento() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, None)
    # 45 dias de atraso: segmento 31 a 60, que usa [whatsapp]
    con_whatsapp = {"dias_atraso": 45}

    assert _evaluar(constructor, **con_whatsapp) is Segmento.DE_31_A_60
    assert _evaluar(constructor, titular="", **con_whatsapp) == Exclusion(
        "000000000000000001", CodigoMowaMes.FALTA_TITULAR
    )
    assert _evaluar(constructor, fecha_vencimiento_cuota=None, **con_whatsapp) == Exclusion(
        "000000000000000001", CodigoMowaMes.FALTA_VENCIMIENTO
    )
    assert isinstance(_evaluar(constructor), FilaCarga)  # 4 dias: segmento sin whatsapp


def test_una_fila_cargada_lleva_el_mismo_mensaje_que_el_camino_de_antes() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, WHATSAPP)

    fila = _evaluar(constructor, dias_atraso=45, titular="  Peña Ruiz Jose")

    esperado = _mensaje_de_antes(ORIGINAL[3], WHATSAPP, "  Peña Ruiz Jose", VENCIMIENTO)
    assert fila.segmento is Segmento.DE_31_A_60
    assert fila.mensaje == esperado


# --- El enlace de WhatsApp: el dueño del prefijo es el nucleo ------------------------------------


def test_el_prefijo_de_whatsapp_tiene_un_solo_dueno_y_mide_26_con_el_numero() -> None:
    from app.core.entities import mowa_mes
    from app.core.services.texto_enriquecido.funciones import enlaces

    assert mowa_mes.PREFIJO_WHATSAPP is PREFIJO_DEL_NUCLEO
    assert enlaces.PREFIJO_WHATSAPP is PREFIJO_DEL_NUCLEO
    assert PREFIJO_WHATSAPP == "https://wa.me/+51"
    assert len(PREFIJO_WHATSAPP) + LARGO_NUMERO_WHATSAPP == 26
    assert LARGO_NUMERO_WHATSAPP == enlaces.LARGO_TELEFONO
    assert speech.enlace_whatsapp(WHATSAPP) == "https://wa.me/+51900000123"


def test_la_cota_de_enlace_whatsapp_con_el_prefijo_por_defecto_es_26() -> None:
    compilada = evaluador.compilar_texto(
        "[@telefono | enlace_whatsapp]", {"telefono": TipoValor.TEXTO}
    )

    assert compilada.cota == 26
    assert len(compilada.evaluar({"telefono": WHATSAPP}).texto) == 26


# --- La expresion de un segmento -----------------------------------------------------------------

_TITULAR = NodoVariable("titular", (LlamadaFuncion("primeros", (8,)),))
_FECHA = NodoVariable(
    "fecha_vencimiento_cuota", (LlamadaFuncion("formato_fecha", ("dd/mm/aaaa",)),)
)
_ENLACE = NodoVariable("whatsapp_contacto", (LlamadaFuncion("enlace_whatsapp"),))


def test_cada_segmento_se_convierte_a_una_expresion_en_orden() -> None:
    partes = PartesSegmento(Segmento.DE_31_A_60, " a [whatsapp] b ", " c [whatsapp][whatsapp] ")

    expresion = speech.expresion_de(partes)

    assert expresion == Expresion(
        (
            _TITULAR,
            NodoTexto(" a "),
            _ENLACE,
            NodoTexto(" b "),
            _FECHA,
            NodoTexto(" c "),
            _ENLACE,
            _ENLACE,
            NodoTexto(" "),
        )
    )


def test_una_parte_vacia_no_deja_nodos_de_texto_vacios() -> None:
    expresion = speech.expresion_de(PartesSegmento(Segmento.PREVENTIVA, "", ""))

    assert expresion == Expresion((_TITULAR, _FECHA))


def test_el_espacio_de_los_extremos_y_los_corchetes_sueltos_se_conservan_en_el_texto_fijo() -> None:
    partes = PartesSegmento(Segmento.PREVENTIVA, "  [ ]  [whatsapp ", "[whatsapp]x]")

    expresion = speech.expresion_de(partes)

    assert expresion.nodos[1] == NodoTexto("  [ ]  [whatsapp ")
    assert expresion.nodos[-2:] == (_ENLACE, NodoTexto("x]"))


def test_la_expresion_valida_contra_las_variables_del_mensaje() -> None:
    for partes in (*ORIGINAL, *VERSIONES_SINTETICAS["corchetes_sueltos"]):
        compilada = evaluador.compilar(speech.expresion_de(partes), speech.VARIABLES_DEL_MENSAJE)

        assert compilada.cota is not None
        assert set(compilada.variables) <= {
            "titular",
            "fecha_vencimiento_cuota",
            "whatsapp_contacto",
        }


def test_el_motor_no_informa_problemas_con_un_whatsapp_valido() -> None:
    compilada = evaluador.compilar(speech.expresion_de(ORIGINAL[3]), speech.VARIABLES_DEL_MENSAJE)
    contexto = {
        "titular": "ZZPRUEBA",
        "fecha_vencimiento_cuota": VENCIMIENTO,
        "whatsapp_contacto": WHATSAPP,
    }

    resultado = compilada.evaluar(contexto)

    assert resultado.problemas == ()
    assert len(resultado.texto) <= compilada.cota

    sin_numero = compilada.evaluar({**contexto, "whatsapp_contacto": None})
    assert sin_numero.problemas == ()  # un vacio deja el enlace vacio; no es un problema
    assert CodigoTexto.TELEFONO_INVALIDO not in {p.codigo for p in sin_numero.problemas}


# --- campana.py excluye antes de pedir el mensaje: el error del constructor no se alcanza -------


class ConstructorEspia(speech.ConstructorMensajes):
    """Un constructor real que cuenta cuantas veces se le pide un mensaje."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.pedidos: list[tuple] = []

    def mensaje_de(self, segmento, titular, vencimiento):
        self.pedidos.append((segmento, titular, vencimiento))
        return super().mensaje_de(segmento, titular, vencimiento)


@pytest.mark.parametrize("titular", [None, "", "   ", "\t\n "])
def test_un_titular_vacio_o_en_blanco_no_llega_nunca_a_pedir_el_mensaje(titular) -> None:
    constructor = ConstructorEspia(ORIGINAL, WHATSAPP)

    resultado = _evaluar(constructor, titular=titular)

    assert resultado == Exclusion("000000000000000001", CodigoMowaMes.FALTA_TITULAR)
    assert constructor.pedidos == []


def test_un_vencimiento_vacio_no_llega_nunca_a_pedir_el_mensaje() -> None:
    constructor = ConstructorEspia(ORIGINAL, WHATSAPP)

    resultado = _evaluar(constructor, fecha_vencimiento_cuota=None)

    assert resultado == Exclusion("000000000000000001", CodigoMowaMes.FALTA_VENCIMIENTO)
    assert constructor.pedidos == []


def test_solo_un_producto_completo_pide_el_mensaje_y_lo_pide_una_vez() -> None:
    constructor = ConstructorEspia(ORIGINAL, WHATSAPP)

    resultado = _evaluar(constructor, dias_atraso=45)

    assert isinstance(resultado, FilaCarga)
    assert constructor.pedidos == [(Segmento.DE_31_A_60, "ZZPRUEBA SINTETICO", VENCIMIENTO)]


def test_sin_whatsapp_el_segmento_que_lo_usa_tampoco_pide_el_mensaje() -> None:
    constructor = ConstructorEspia(ORIGINAL, None)

    resultado = _evaluar(constructor, dias_atraso=45)

    assert resultado is Segmento.DE_31_A_60
    assert constructor.pedidos == []
