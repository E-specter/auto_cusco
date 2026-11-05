"""El speech de MOWA MES con TODOS los campos de la cartera (T-HI-B7, parte 2, D-CA-2 opcion a).

Un campo base (`saldo_soles_corte`, `region`...) se lee como un adicional: llega con el producto y
sigue la regla Obligatoria del motor (RF-45). Marcada y vacia, excluye con `falta_campo_adicional`
y `campos=...`; sin marcar, sale vacia o con su valor por defecto; un campo que el segmento no usa
no excluye. Un speech sin campos nuevos sale igual (lo cubren el oro y `test_mowa_mes_adicionales`).
Datos sinteticos (telefonos 900000xxx).
"""

from datetime import date
from decimal import Decimal

import pytest

from app.core.entities.mowa_mes import (
    CodigoMowaMes,
    DatosSpeech,
    ExpresionSegmento,
    Segmento,
    SpeechInvalido,
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
from app.core.services.plataformas.mowa_mes.campana import Exclusion, FilaCarga, evaluar_producto
from app.core.services.plataformas.mowa_mes.configuracion import ConfiguracionMowaMesService
from app.core.services.plataformas.mowa_mes.contexto_texto import contexto_speech
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from tests.test_mowa_mes_adicionales import _peticion_v2, _servicio
from tests.test_mowa_mes_campana import FECHA_CORTE, producto
from tests.test_mowa_mes_speech import WHATSAPP, RepositorioMowaMesFalso

SALDO, REGION = "saldo_soles_corte", "region"
ENVIO = date(2026, 9, 14)  # + 4 dias de atraso = 8: segmento 1 a 8


def _var(nombre: str, obligatoria: bool = False, *funciones: LlamadaFuncion) -> NodoVariable:
    return NodoVariable(nombre, tuple(funciones), obligatoria)


def _f(nombre: str, *args) -> LlamadaFuncion:
    return LlamadaFuncion(nombre, tuple(args))


def _v2(*nodos, segmentos=tuple(Segmento)) -> DatosSpeech:
    return DatosSpeech(
        "Con campos de la cartera",
        expresiones=tuple(ExpresionSegmento(s, Expresion(tuple(nodos))) for s in segmentos),
    )


def _constructor(datos: DatosSpeech):
    return speech.ConstructorMensajes(
        datos, WHATSAPP, adicionales=speech.campos_de(CatalogoCartera())
    )


def _evaluar(datos: DatosSpeech, **cambios):
    base = {SALDO: Decimal("1620.75"), REGION: "CUSCO"}
    return evaluar_producto(
        producto(1, **{**base, **cambios}), FECHA_CORTE, ENVIO, _constructor(datos)
    )


def _problemas(*nodos) -> list:
    return list(speech.problemas_de(_v2(*nodos), adicionales=speech.campos_de(CatalogoCartera())))


# --- Lo que el speech ofrece ----------------------------------------------------------------------


def test_el_producto_de_la_cartera_trae_todos_los_campos_que_el_speech_ofrece() -> None:
    # `consultar` devuelve cada columna de la fila del producto (menos `carga_id` y el JSON de los
    # adicionales, que salen rotulados): todo campo base que el speech puede leer esta ahi.
    from app.adapters.persistence.repositorio_cartera_postgres import _COLUMNAS_PRODUCTO

    columnas = {c.name for c in _COLUMNAS_PRODUCTO}

    assert set(speech.campos_de(CatalogoCartera())) <= columnas


def test_campos_de_trae_los_base_y_deja_fuera_las_variables_propias() -> None:
    campos = speech.campos_de(CatalogoCartera())

    assert campos[SALDO] is TipoValor.NUMERO and campos[REGION] is TipoValor.TEXTO
    assert not set(campos) & set(speech.VARIABLES_V2)  # titular, vencimiento, contacto, dias
    assert speech.campos_de(None) == {}


def test_el_contexto_del_editor_ofrece_todo_y_ya_no_trae_linea_de_alcance() -> None:
    contexto = contexto_speech()

    assert {SALDO, REGION, "titular", speech.VARIABLE_CONTACTO} <= {
        v.nombre for v in contexto.variables
    }
    assert contexto.clave_alcance is None  # ofrece todo: como Columnas, sin linea
    assert contexto.ejemplo[SALDO] == Decimal("1620.75")
    assert contexto.registro_de_producto({SALDO: Decimal("10.00")})[SALDO] == Decimal("10.00")


# --- Obligatoria (RF-45) ------------------------------------------------------------------------


def test_un_campo_base_con_valor_se_carga_con_su_valor() -> None:
    datos = _v2(NodoTexto("Saldo "), _var(SALDO, True, _f("a_texto"), _f("primeros", 8)))

    resultado = _evaluar(datos)

    assert isinstance(resultado, FilaCarga) and resultado.mensaje == "Saldo 1620.75"


@pytest.mark.parametrize("vacio", [None, "", "  "])
def test_marcada_y_vacia_excluye_con_su_motivo_y_el_campo(vacio) -> None:
    datos = _v2(NodoTexto("Saldo "), _var(SALDO, True, _f("a_texto"), _f("primeros", 8)))

    resultado = _evaluar(datos, **{SALDO: vacio})

    assert isinstance(resultado, Exclusion)
    assert (resultado.codigo, resultado.campos) == (CodigoMowaMes.FALTA_CAMPO_ADICIONAL, (SALDO,))


def test_sin_marcar_y_vacia_sale_vacia() -> None:
    datos = _v2(NodoTexto("Region: "), _var(REGION, False, _f("primeros", 10)), NodoTexto("."))

    resultado = _evaluar(datos, **{REGION: None})

    assert isinstance(resultado, FilaCarga) and resultado.mensaje == "Region: ."


def test_sin_marcar_y_vacia_sale_con_su_valor_por_defecto() -> None:
    datos = _v2(
        NodoTexto("Region: "), _var(REGION, False, _f("si_vacio", "SIN REGION"), _f("primeros", 10))
    )

    resultado = _evaluar(datos, **{REGION: "  "})

    assert isinstance(resultado, FilaCarga) and resultado.mensaje == "Region: SIN REGION"


def test_un_campo_vacio_que_el_segmento_no_usa_no_excluye() -> None:
    # El campo marcado solo esta en 9 a 30; el producto cae en 1 a 8.
    datos = DatosSpeech(
        "Por segmento",
        expresiones=(
            ExpresionSegmento(Segmento.DE_1_A_8, Expresion((NodoTexto("Hola"),))),
            ExpresionSegmento(
                Segmento.DE_9_A_30,
                Expresion((_var(SALDO, True, _f("a_texto"), _f("primeros", 8)),)),
            ),
        ),
    )

    resultado = _evaluar(datos, **{SALDO: None})

    assert isinstance(resultado, FilaCarga) and resultado.mensaje == "Hola"


def test_un_campo_leido_como_argumento_se_exige_siempre_aunque_nada_este_marcado() -> None:
    # `titular | si_vacio(@region)`: un argumento no se puede marcar y deja un hueco si llega vacio.
    datos = _v2(
        _var("titular", False, _f("si_vacio", ArgumentoVariable(REGION)), _f("primeros", 10))
    )

    resultado = _evaluar(datos, **{REGION: None})

    assert isinstance(resultado, Exclusion)
    assert (resultado.codigo, resultado.campos) == (CodigoMowaMes.FALTA_CAMPO_ADICIONAL, (REGION,))


def test_los_obligatorios_salen_en_el_orden_de_los_nodos_sin_repetir() -> None:
    datos = _v2(
        _var(REGION, True, _f("primeros", 5)),
        NodoTexto(" "),
        _var(SALDO, True, _f("a_texto"), _f("primeros", 8)),
        _var(REGION, True, _f("primeros", 5)),
    )

    constructor = _constructor(datos)

    assert constructor.obligatorios_usados(Segmento.DE_1_A_8) == (REGION, SALDO)
    assert constructor.adicionales_usados(Segmento.DE_1_A_8) == (REGION, SALDO)


def test_los_campos_si_no_no_se_ofrecen_en_ningun_lado() -> None:
    # El motor escribe un booleano con `str` («True»): un SMS no puede salir asi (decision del
    # usuario). Se filtra solo en `campos_de` y el contexto del editor lo hereda.
    campos = speech.campos_de(CatalogoCartera())
    booleanos = {n for n, t in CatalogoCartera().tipos().items() if t.value == "booleano"}

    assert booleanos >= {"cliente_fallecido", "descuento_planilla"}
    assert not booleanos & set(campos)
    assert not booleanos & {v.nombre for v in contexto_speech().variables}


def test_un_speech_con_un_campo_si_no_da_variable_desconocida_al_guardar_y_al_previsualizar() -> (
    None
):
    servicio = ConfiguracionMowaMesService(RepositorioMowaMesFalso(WHATSAPP), CatalogoCartera())
    datos = _v2(NodoTexto("Fallecido: "), _var("cliente_fallecido"))

    _, problemas, _, _ = servicio.previsualizar_speech_v2(datos.expresiones, None)

    assert {p.problema.codigo for p in problemas} == {CodigoTexto.VARIABLE_DESCONOCIDA}
    with pytest.raises(SpeechInvalido) as error:
        servicio.crear_speech_v2("Con si/no", datos.expresiones, None)
    assert {p.problema.codigo for p in error.value.problemas} == {CodigoTexto.VARIABLE_DESCONOCIDA}


def test_titular_y_vencimiento_siguen_excluyendo_con_sus_motivos_de_siempre() -> None:
    datos = _v2(_var("titular", True, _f("primeros", 8)))

    resultado = _evaluar(datos, titular=None)

    assert isinstance(resultado, Exclusion) and resultado.codigo is CodigoMowaMes.FALTA_TITULAR


# --- Los 160 se miden con el valor por defecto aplicado -----------------------------------------


def test_los_160_se_miden_despues_del_valor_por_defecto() -> None:
    relleno = "x" * 150
    datos = _v2(NodoTexto(relleno), _var(REGION, False, _f("si_vacio", "0123456789AB")))

    sin_defecto = _evaluar(datos, **{REGION: "CUSCO"})  # 150 + 5 = 155
    con_defecto = _evaluar(datos, **{REGION: None})  # 150 + 12 = 162

    assert isinstance(sin_defecto, FilaCarga)
    assert isinstance(con_defecto, Exclusion)
    assert con_defecto.codigo is CodigoMowaMes.MENSAJE_EXCEDE_160


# --- D-CA-1 se extiende a los campos base de texto o numero -------------------------------------


def test_un_campo_base_de_texto_o_numero_sin_tope_da_sin_cota_variable() -> None:
    for nombre in (REGION, SALDO):
        problemas = _problemas(_var(nombre))
        assert len(problemas) == 6  # un problema por segmento
        assert all(p.problema.codigo is CodigoTexto.SIN_COTA_VARIABLE for p in problemas)
        assert {p.problema.nombre for p in problemas} == {nombre}


def test_un_campo_base_acotado_no_da_el_problema() -> None:
    assert _problemas(_var(REGION, False, _f("primeros", 10))) == []
    assert _problemas(_var(SALDO, False, _f("a_texto"), _f("primeros", 8))) == []


# --- La vista previa usa un valor sintetico por tipo --------------------------------------------


def test_la_vista_previa_usa_un_valor_sintetico_por_tipo() -> None:
    campos = speech.campos_de(CatalogoCartera())
    datos = _v2(
        _var(REGION, False, _f("primeros", 14)),
        NodoTexto(" "),
        _var(SALDO, False, _f("a_texto"), _f("primeros", 8)),
    )

    [primero, *_] = speech.previsualizar_v2(datos.expresiones, WHATSAPP, adicionales=campos)

    assert "ZONA SINTETI" in primero.ejemplo and "1250.50" in primero.ejemplo
    assert "CUSCO" not in primero.ejemplo  # nunca un dato de la cartera


def test_la_vista_previa_con_un_campo_marcado_obligatorio_no_da_problemas() -> None:
    campos = speech.campos_de(CatalogoCartera())
    datos = _v2(_var(REGION, True, _f("primeros", 10)))

    largos = speech.previsualizar_v2(datos.expresiones, WHATSAPP, adicionales=campos)

    assert len(largos) == 6 and all(item.ejemplo for item in largos)


# --- Los servicios usan todos los campos (la campana y la configuracion) --------------------------


def test_la_campana_lee_los_campos_base_del_producto_y_excluye_al_que_no_los_trae() -> None:
    datos = _v2(NodoTexto("Region "), _var(REGION, True, _f("primeros", 10)))
    servicio, _ = _servicio(
        [producto(1, **{REGION: "CUSCO"}), producto(2, **{REGION: None})], datos=datos
    )

    armada = servicio.previsualizar(_peticion_v2(datos))

    assert [f.mensaje for f in armada.filas if not f.supervision] == ["Region CUSCO"]
    assert armada.exclusiones == (
        Exclusion(producto(2)["pagare"], CodigoMowaMes.FALTA_CAMPO_ADICIONAL, campos=(REGION,)),
    )


def test_guardar_y_previsualizar_aceptan_un_campo_base_acotado_y_rechazan_uno_sin_tope() -> None:
    servicio = ConfiguracionMowaMesService(RepositorioMowaMesFalso(WHATSAPP), CatalogoCartera())
    acotado = _v2(_var(REGION, False, _f("primeros", 10)))
    sin_tope = _v2(_var(REGION))

    _, problemas, largos, _ = servicio.previsualizar_speech_v2(acotado.expresiones, None)
    _, sin_cota, _, _ = servicio.previsualizar_speech_v2(sin_tope.expresiones, None)

    assert problemas == () and len(largos) == 6
    assert {p.problema.codigo for p in sin_cota} == {CodigoTexto.SIN_COTA_VARIABLE}
    assert servicio.crear_speech_v2("Con region", acotado.expresiones, None).datos.nombre
    with pytest.raises(SpeechInvalido):
        servicio.crear_speech_v2("Sin tope", sin_tope.expresiones, None)
