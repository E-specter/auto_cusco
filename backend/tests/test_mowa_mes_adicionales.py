"""Los campos adicionales en el speech v2 de MOWA MES (D-CA-0 a D-CA-2; T-MM-B12, RF-64 a RF-66).

Sobre repositorios en memoria y los adicionales sinteticos de `campos_adicionales_memoria.py`
(texto, numero, fecha y un archivado). Datos sinteticos.

- D-CA-0: una v2 lee los adicionales con su tipo y la fila aporta su valor; el ejemplo usa uno
  sintetico por tipo; el contexto del editor los ofrece.
- D-CA-1: un adicional de texto o de numero exige tope, por nodo; una fecha no.
- D-CA-2: un adicional vacio que el segmento lee excluye al producto con `falta_campo_adicional`.
- El aviso de campo archivado.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.core.entities.gestiones_digitales import ConfiguracionSupervision
from app.core.entities.mowa_mes import (
    CodigoMowaMes,
    DatosSpeech,
    ExpresionSegmento,
    FormatoSpeech,
    Segmento,
    SpeechInvalido,
    VersionSpeech,
)
from app.core.entities.texto_enriquecido import (
    ArgumentoVariable,
    CodigoTexto,
    Expresion,
    LlamadaFuncion,
    NodoTexto,
    NodoVariable,
    TipoValor,
)
from app.core.services.plataformas.mowa_mes import speech
from app.core.services.plataformas.mowa_mes.campana import (
    CampanasMowaMesService,
    Exclusion,
    FilaCarga,
    evaluar_producto,
    huella_de,
)
from app.core.services.plataformas.mowa_mes.configuracion import ConfiguracionMowaMesService
from app.core.services.plataformas.mowa_mes.contexto_texto import contexto_speech
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService
from tests.campos_adicionales_memoria import (
    ARCHIVADO,
    FECHA,
    NUMERO,
    TEXTO,
    CamposAdicionalesEnMemoria,
    catalogo_con,
)
from tests.test_gestiones_digitales import PROCEDENCIAS, SUPERVISORES, RepositorioSupervisionFalso
from tests.test_mowa_mes_campana import (
    FECHA_CORTE,
    MOMENTO,
    VENCIMIENTO,
    RepositorioCampanasMemoria,
    RepositorioCarteraFalso,
    _escritor,
    peticion,
    producto,
)
from tests.test_mowa_mes_speech import WHATSAPP, RepositorioMowaMesFalso

ZONA, MONTO, VISITA, ANTIGUO = TEXTO.nombre, NUMERO.nombre, FECHA.nombre, ARCHIVADO.nombre
ENVIO = date(2026, 9, 14)  # + 4 dias de atraso hasta el envio = 8: segmento 1 a 8


def _var(nombre: str, *funciones: LlamadaFuncion) -> NodoVariable:
    return NodoVariable(nombre, tuple(funciones))


def _f(nombre: str, *args) -> LlamadaFuncion:
    return LlamadaFuncion(nombre, tuple(args))


def _v2(*nodos, nombre="Con adicionales") -> DatosSpeech:
    """La misma expresion en los 6 segmentos."""
    return DatosSpeech(
        nombre,
        expresiones=tuple(ExpresionSegmento(s, Expresion(tuple(nodos))) for s in Segmento),
        formato=FormatoSpeech.V2,
    )


def _adicionales() -> dict[str, TipoValor]:
    return speech.adicionales_de(catalogo_con())


# Un speech completo: los tres tipos, cada uno acotado como pide D-CA-1.
ZONA_ACOTADA = _var(ZONA, _f("primeros", 12))
MONTO_ACOTADO = _var(MONTO, _f("a_texto"), _f("primeros", 7))
VISITA_CON_FORMATO = _var(VISITA, _f("formato_fecha", "dd/mm/aaaa"))
COMPLETO = _v2(
    NodoTexto("Zona "),
    ZONA_ACOTADA,
    NodoTexto(" monto "),
    MONTO_ACOTADO,
    NodoTexto(" visita "),
    VISITA_CON_FORMATO,
)


# --- D-CA-0: los adicionales como variables de la v2 -------------------------------------------


def test_los_adicionales_salen_del_catalogo_con_su_tipo_y_los_archivados_incluidos() -> None:
    assert _adicionales() == {
        ZONA: TipoValor.TEXTO,
        MONTO: TipoValor.NUMERO,
        VISITA: TipoValor.FECHA,
        ANTIGUO: TipoValor.NUMERO,  # archivado: lo que ya lo usa tiene que seguir resolviendo
    }


def test_sin_catalogo_o_sin_adicionales_no_hay_ninguno_y_las_variables_de_hoy_no_cambian() -> None:
    assert speech.adicionales_de(None) == {}
    assert speech.adicionales_de(CatalogoCartera()) == {}
    assert set(speech.VARIABLES_V2) == {
        "titular",
        "fecha_vencimiento_cuota",
        "whatsapp_contacto",
        "dias_atraso_ajustados",
    }


def test_una_v2_con_un_adicional_de_cada_tipo_acotado_no_da_problemas() -> None:
    assert speech.problemas_de(COMPLETO, adicionales=_adicionales()) == ()


def test_sin_los_adicionales_la_misma_v2_da_variable_desconocida() -> None:
    problemas = speech.problemas_de(COMPLETO)

    assert problemas
    assert {p.problema.codigo for p in problemas if p.problema} == {
        CodigoTexto.VARIABLE_DESCONOCIDA
    }


def test_el_mensaje_lleva_el_valor_de_cada_adicional_de_la_fila() -> None:
    constructor = speech.ConstructorMensajes(COMPLETO, WHATSAPP, adicionales=_adicionales())

    mensaje = constructor.mensaje_de(
        Segmento.DE_1_A_8,
        "TITULAR",
        VENCIMIENTO,
        8,
        adicionales={
            ZONA: "ZONA NORTE EXTENSA",
            MONTO: Decimal("1250.50"),
            VISITA: date(2026, 10, 5),
        },
    )

    assert mensaje == "Zona ZONA NORTE E monto 1250.50 visita 05/10/2026"


def test_el_orden_de_los_adicionales_usados_es_el_de_los_nodos_no_el_del_catalogo() -> None:
    datos = _v2(MONTO_ACOTADO, NodoTexto(" "), ZONA_ACOTADA, NodoTexto(" "), MONTO_ACOTADO)

    constructor = speech.ConstructorMensajes(datos, WHATSAPP, adicionales=_adicionales())

    assert constructor.adicionales_usados(Segmento.DE_1_A_8) == (MONTO, ZONA)  # sin repetir


def test_una_v1_y_un_segmento_que_no_los_lee_no_usan_ninguno() -> None:
    sin_adicionales = _v2(_var("titular", _f("primeros", 8)))

    assert (
        speech.ConstructorMensajes(
            sin_adicionales, WHATSAPP, adicionales=_adicionales()
        ).adicionales_usados(Segmento.PREVENTIVA)
        == ()
    )


def test_la_muestra_de_la_previsualizacion_usa_un_valor_sintetico_por_tipo() -> None:
    largos = speech.previsualizar_v2(COMPLETO.expresiones, WHATSAPP, adicionales=_adicionales())

    ejemplo = largos[0].ejemplo
    assert ejemplo == "Zona ZONA SINTETI monto 1250.50 visita 05/10/2026"
    assert speech.EJEMPLO_ADICIONAL == {
        TipoValor.TEXTO: "ZONA SINTETICA",
        TipoValor.NUMERO: Decimal("1250.50"),
        TipoValor.FECHA: date(2026, 10, 5),
    }


def test_un_segmento_que_no_usa_adicionales_da_el_mismo_ejemplo_que_sin_catalogo() -> None:
    datos = _v2(
        _var("titular", _f("primeros", 8)),
        NodoTexto(" vence "),
        _var("fecha_vencimiento_cuota", _f("formato_fecha", "dd/mm/aaaa")),
    )

    con = speech.previsualizar_v2(datos.expresiones, WHATSAPP, adicionales=_adicionales())
    sin = speech.previsualizar_v2(datos.expresiones, WHATSAPP)

    assert [x.ejemplo for x in con] == [x.ejemplo for x in sin]


def test_el_contexto_del_editor_ofrece_los_adicionales_con_su_tipo_etiqueta_y_marcas() -> None:
    contexto = contexto_speech(catalogo_con())

    por_nombre = {v.nombre: v for v in contexto.variables}
    assert (
        por_nombre[ZONA].tipo is TipoValor.TEXTO and por_nombre[ZONA].etiqueta == "Zona comercial"
    )
    assert por_nombre[MONTO].tipo is TipoValor.NUMERO
    assert por_nombre[VISITA].tipo is TipoValor.FECHA
    assert (por_nombre[ZONA].adicional, por_nombre[ZONA].archivado) == (True, False)
    assert (por_nombre[ANTIGUO].adicional, por_nombre[ANTIGUO].archivado) == (True, True)
    assert contexto.ejemplo[ZONA] == "ZONA SINTETICA"
    assert contexto.ejemplo[MONTO] == Decimal("1250.50")
    assert contexto.ejemplo[VISITA] == date(2026, 10, 5)
    assert "titular" in por_nombre and por_nombre["titular"].adicional is False


def test_el_producto_de_la_muestra_trae_su_propio_valor_en_el_contexto() -> None:
    contexto = contexto_speech(catalogo_con())

    registro = contexto.registro_de_producto(
        {"titular": "X", ZONA: "ZONA REAL SINTETICA", MONTO: Decimal("3.00")}
    )

    assert registro[ZONA] == "ZONA REAL SINTETICA"
    assert registro[MONTO] == Decimal("3.00")
    assert registro[VISITA] is None  # el producto no lo trae


def test_el_contexto_sin_catalogo_es_el_de_hoy() -> None:
    contexto = contexto_speech()

    assert [v.nombre for v in contexto.variables] == list(speech.VARIABLES_V2)


# --- D-CA-1: el tope obligatorio -----------------------------------------------------------------


def _problemas(*nodos):
    return [
        p
        for p in speech.problemas_de(_v2(*nodos), adicionales=_adicionales())
        if p.problema and p.problema.codigo is CodigoTexto.SIN_COTA_VARIABLE
    ]


def test_un_adicional_de_texto_sin_tope_da_sin_cota_variable_en_su_nodo_y_con_su_nombre() -> None:
    problemas = _problemas(NodoTexto("Zona "), _var(ZONA))

    assert len(problemas) == 6  # uno por segmento
    motor = problemas[0].problema
    assert (motor.nodo, motor.nombre) == (1, ZONA)
    assert problemas[0].campo == "expresion" and problemas[0].detalle == motor.detalle


def test_un_adicional_de_numero_sin_tope_tambien() -> None:
    problemas = _problemas(_var(MONTO))

    assert [p.problema.nombre for p in problemas] == [MONTO] * 6


def test_un_numero_con_a_texto_y_primeros_no_da_el_problema() -> None:
    assert _problemas(_var(MONTO, _f("a_texto"), _f("primeros", 6))) == []


def test_un_nodo_con_el_adicional_como_argumento_y_sin_tope_da_el_problema() -> None:
    # `titular | si_vacio(ad_zona)`: el adicional entra como argumento y la cota depende del dato.
    nodo = _var("titular", _f("si_vacio", ArgumentoVariable(ZONA)))

    problemas = _problemas(nodo)

    assert len(problemas) == 6 and problemas[0].problema.nombre == ZONA


def test_el_mismo_nodo_acotado_al_final_ya_no_da_el_problema() -> None:
    nodo = _var("titular", _f("si_vacio", ArgumentoVariable(ZONA)), _f("primeros", 10))

    assert _problemas(nodo) == []


def test_una_fecha_sin_formato_fecha_no_da_el_problema_de_d_ca_1() -> None:
    assert _problemas(_var(VISITA)) == []


def test_el_titular_la_fecha_de_vencimiento_y_los_dias_siguen_sin_tope_obligatorio() -> None:
    assert (
        _problemas(_var("titular"), _var("dias_atraso_ajustados"), _var("fecha_vencimiento_cuota"))
        == []
    )


def test_el_tope_se_exige_por_nodo_aunque_otro_nodo_acote_el_mismo_campo() -> None:
    problemas = _problemas(ZONA_ACOTADA, NodoTexto(" "), _var(ZONA))

    assert {p.problema.nodo for p in problemas} == {2}


def test_guardar_una_v2_con_el_problema_no_la_guarda() -> None:
    repositorio = RepositorioMowaMesFalso(WHATSAPP)
    servicio = ConfiguracionMowaMesService(repositorio, catalogo_con())
    sin_tope = _v2(_var(ZONA))

    with pytest.raises(SpeechInvalido) as error:
        servicio.crear_speech_v2("Sin tope", sin_tope.expresiones, None)

    assert len(repositorio.versiones) == 1  # solo el Speech original
    assert all(p.problema.codigo is CodigoTexto.SIN_COTA_VARIABLE for p in error.value.problemas)


def test_guardar_una_v2_acotada_la_guarda_con_el_catalogo_y_no_sin_el() -> None:
    con = ConfiguracionMowaMesService(RepositorioMowaMesFalso(WHATSAPP), catalogo_con())
    sin = ConfiguracionMowaMesService(RepositorioMowaMesFalso(WHATSAPP))

    guardada = con.crear_speech_v2("Acotada", COMPLETO.expresiones, None)

    assert guardada.datos.formato is FormatoSpeech.V2
    with pytest.raises(SpeechInvalido):
        sin.crear_speech_v2("Acotada", COMPLETO.expresiones, None)


# --- D-CA-2: la exclusion ------------------------------------------------------------------------


def _constructor(datos: DatosSpeech = COMPLETO, whatsapp: str | None = WHATSAPP):
    return speech.ConstructorMensajes(datos, whatsapp, adicionales=_adicionales())


def _evaluar(constructor, **cambios):
    base = {ZONA: "ZONA SINTETICA", MONTO: Decimal("1250.50"), VISITA: date(2026, 10, 5)}
    return evaluar_producto(producto(1, **{**base, **cambios}), FECHA_CORTE, ENVIO, constructor)


def test_un_producto_con_todos_sus_adicionales_se_carga_con_sus_valores() -> None:
    resultado = _evaluar(_constructor())

    assert isinstance(resultado, FilaCarga)
    assert resultado.mensaje == "Zona ZONA SINTETI monto 1250.50 visita 05/10/2026"


@pytest.mark.parametrize("vacio", [None, "", "  "])
def test_none_vacio_y_en_blanco_excluyen_y_el_detalle_trae_el_campo(vacio) -> None:
    resultado = _evaluar(_constructor(), **{ZONA: vacio})

    assert resultado == Exclusion(
        producto(1)["pagare"], CodigoMowaMes.FALTA_CAMPO_ADICIONAL, campos=(ZONA,)
    )


def test_con_dos_vacios_salen_los_dos_en_el_orden_de_los_nodos() -> None:
    datos = _v2(MONTO_ACOTADO, NodoTexto(" "), ZONA_ACOTADA)

    resultado = _evaluar(_constructor(datos), **{ZONA: None, MONTO: None})

    assert resultado.campos == (MONTO, ZONA)  # el orden del speech, no el del catalogo


def test_un_numero_cero_y_una_fecha_no_estan_vacios() -> None:
    resultado = _evaluar(_constructor(), **{MONTO: Decimal(0)})

    assert isinstance(resultado, FilaCarga)


def test_un_adicional_vacio_que_el_segmento_no_usa_no_excluye_nada() -> None:
    datos = _v2(ZONA_ACOTADA)

    resultado = _evaluar(_constructor(datos), **{MONTO: None, VISITA: None})

    assert isinstance(resultado, FilaCarga)
    assert resultado.mensaje == "ZONA SINTETI"


def test_un_archivado_vacio_excluye_igual() -> None:
    datos = _v2(_var(ANTIGUO, _f("a_texto"), _f("primeros", 5)))

    resultado = _evaluar(_constructor(datos), **{ANTIGUO: None})

    assert resultado.codigo is CodigoMowaMes.FALTA_CAMPO_ADICIONAL and resultado.campos == (
        ANTIGUO,
    )


def test_falta_vencimiento_y_falta_titular_ganan_a_este_codigo() -> None:
    constructor = _constructor(
        _v2(
            _var("titular", _f("primeros", 8)),
            _var("fecha_vencimiento_cuota", _f("formato_fecha", "dd/mm/aaaa")),
            ZONA_ACOTADA,
        )
    )
    sin_vencimiento = _evaluar(constructor, fecha_vencimiento_cuota=None, **{ZONA: None})
    sin_titular = _evaluar(constructor, titular=None, **{ZONA: None})

    assert sin_vencimiento.codigo is CodigoMowaMes.FALTA_VENCIMIENTO
    assert sin_titular.codigo is CodigoMowaMes.FALTA_TITULAR


def test_este_codigo_gana_al_whatsapp_faltante() -> None:
    datos = _v2(ZONA_ACOTADA, NodoVariable("whatsapp_contacto", (_f("enlace_whatsapp"),)))
    constructor = _constructor(datos, whatsapp=None)

    con_campo_vacio = _evaluar(constructor, **{ZONA: None})
    con_campo = _evaluar(constructor)

    assert con_campo_vacio.codigo is CodigoMowaMes.FALTA_CAMPO_ADICIONAL
    assert con_campo is Segmento.DE_1_A_8  # sin campo vacio, el WhatsApp faltante manda


def test_este_codigo_gana_a_los_160() -> None:
    largo = _v2(NodoTexto("x" * 200), ZONA_ACOTADA)

    vacio = _evaluar(_constructor(largo), **{ZONA: None})
    lleno = _evaluar(_constructor(largo))

    assert vacio.codigo is CodigoMowaMes.FALTA_CAMPO_ADICIONAL
    assert lleno.codigo is CodigoMowaMes.MENSAJE_EXCEDE_160


def test_las_exclusiones_anteriores_ganan_a_este_codigo() -> None:
    constructor = _constructor()

    sin_telefono = _evaluar(constructor, telefono=None, **{ZONA: None})
    sin_documento = _evaluar(constructor, documento_numero=None, **{ZONA: None})

    assert sin_telefono.codigo is CodigoMowaMes.TELEFONO_INVALIDO
    assert sin_documento.codigo is CodigoMowaMes.FALTA_DOCUMENTO


# --- De punta a punta: la campana pasa los adicionales al constructor -----------------------------


def _servicio(productos, adicionales=None):
    repositorio_adicionales = CamposAdicionalesEnMemoria(
        adicionales or (TEXTO, NUMERO, FECHA, ARCHIVADO)
    )
    mowa_mes = RepositorioMowaMesFalso(WHATSAPP)
    supervision = RepositorioSupervisionFalso()
    supervision.configuracion = ConfiguracionSupervision(PROCEDENCIAS, tuple(SUPERVISORES))
    version = VersionSpeech(2, COMPLETO, False, None, None, MOMENTO)
    mowa_mes.versiones[2] = version
    consulta = ConsultaCarteraService(
        RepositorioCarteraFalso(productos), CatalogoCartera(repositorio_adicionales)
    )
    servicio = CampanasMowaMesService(
        consulta,
        mowa_mes,
        supervision,
        RepositorioCampanasMemoria(),
        _escritor,
        reloj=lambda: MOMENTO,
    )
    return servicio, repositorio_adicionales


def _peticion_v2(**cambios):
    return peticion(speech_id=2, speech_huella=huella_de(COMPLETO), **cambios)


def test_la_campana_arma_el_mensaje_con_el_valor_de_cada_adicional_de_la_fila() -> None:
    servicio, _ = _servicio(
        [
            producto(
                1,
                **{
                    ZONA: "ZONA NORTE EXTENSA",
                    MONTO: Decimal("1250.50"),
                    VISITA: date(2026, 10, 5),
                },
            ),
        ]
    )

    armada = servicio.previsualizar(_peticion_v2())

    productos = [f for f in armada.filas if not f.supervision]
    assert [f.mensaje for f in productos] == ["Zona ZONA NORTE E monto 1250.50 visita 05/10/2026"]
    assert armada.exclusiones == ()


def test_la_campana_excluye_al_producto_con_el_campo_vacio_y_guarda_sus_nombres_tecnicos() -> None:
    servicio, _ = _servicio(
        [
            producto(1, **{ZONA: "A", MONTO: Decimal("1"), VISITA: date(2026, 10, 5)}),
            producto(2, **{ZONA: None, MONTO: "", VISITA: date(2026, 10, 5)}),
        ]
    )

    armada = servicio.previsualizar(_peticion_v2())

    assert len([f for f in armada.filas if not f.supervision]) == 1
    assert armada.exclusiones == (
        Exclusion(producto(2)["pagare"], CodigoMowaMes.FALTA_CAMPO_ADICIONAL, campos=(ZONA, MONTO)),
    )


def test_renombrar_el_campo_cambia_lo_que_se_muestra_y_no_lo_guardado() -> None:
    servicio, repositorio = _servicio([producto(1, **{ZONA: None})])
    antes = servicio.etiqueta_de(ZONA)

    repositorio.campos[0] = replace(TEXTO, nombre_legible="Otra zona")
    servicio_nuevo, _ = _servicio([producto(1, **{ZONA: None})], adicionales=repositorio.campos)

    assert antes == "Zona comercial"
    assert servicio_nuevo.etiqueta_de(ZONA) == "Otra zona"


# --- El aviso de campo archivado ------------------------------------------------------------------


def test_con_un_archivado_en_la_expresion_sale_su_nombre_y_su_etiqueta() -> None:
    servicio = ConfiguracionMowaMesService(RepositorioMowaMesFalso(WHATSAPP), catalogo_con())
    datos = _v2(_var(ANTIGUO, _f("a_texto"), _f("primeros", 5)), NodoTexto(" "), ZONA_ACOTADA)

    *_, archivados = servicio.previsualizar_speech_v2(datos.expresiones, None)

    assert archivados == ((ANTIGUO, "Campo antiguo"),)


def test_sin_archivados_sale_vacio_y_nunca_bloquea() -> None:
    servicio = ConfiguracionMowaMesService(RepositorioMowaMesFalso(WHATSAPP), catalogo_con())

    *_, archivados = servicio.previsualizar_speech_v2(COMPLETO.expresiones, None)
    guardada = servicio.crear_speech_v2(
        "Con archivado", _v2(_var(ANTIGUO, _f("a_texto"), _f("primeros", 5))).expresiones, None
    )

    assert archivados == ()
    assert guardada.datos.formato is FormatoSpeech.V2  # guardar una que lo usa se permite
