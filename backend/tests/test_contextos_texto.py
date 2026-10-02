"""Contextos del motor de texto (B4a, RF-43): las variables que un modulo aporta, con su tipo.

El nucleo trae el registro generico y el contexto `cartera`; MOWA MES declara el suyo en su paquete
(`plataformas/mowa_mes/contexto_texto.py`) y la composicion de la API los registra.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.core.entities.contexto_texto import ContextoDesconocido
from app.core.entities.mowa_mes import LARGO_ADVERTENCIA, LARGO_MAXIMO, RANGOS_SEGMENTO, Segmento
from app.core.entities.texto_enriquecido import TipoValor
from app.core.services.contextos_texto import RegistroContextos, contexto_cartera
from app.core.services.plataformas.mowa_mes import speech
from app.core.services.plataformas.mowa_mes.contexto_texto import contexto_speech
from app.core.services.seleccion_cartera.campos import CAMPOS_CARTERA
from app.core.services.texto_enriquecido import evaluador
from tests.test_mowa_mes_speech import ORIGINAL

CARTERA = contexto_cartera()
SPEECH = contexto_speech()
REGISTRO = RegistroContextos([CARTERA, SPEECH])


def test_los_contextos_disponibles_salen_en_el_orden_de_registro() -> None:
    assert [c.nombre for c in REGISTRO.disponibles()] == ["cartera", "mowa_mes.speech"]
    assert [c.nombre for c in RegistroContextos([SPEECH, CARTERA]).disponibles()] == [
        "mowa_mes.speech",
        "cartera",
    ]


def test_el_registro_busca_por_nombre() -> None:
    assert REGISTRO.obtener("cartera") is CARTERA
    assert REGISTRO.obtener("mowa_mes.speech") is SPEECH


def test_un_contexto_desconocido_se_informa_con_su_nombre() -> None:
    with pytest.raises(ContextoDesconocido) as error:
        REGISTRO.obtener("inventado")

    assert error.value.nombre == "inventado"
    assert "inventado" in str(error.value)


def test_un_registro_sin_contextos_no_encuentra_ninguno() -> None:
    assert RegistroContextos([]).disponibles() == ()
    with pytest.raises(ContextoDesconocido):
        RegistroContextos([]).obtener("cartera")


def test_un_contexto_no_se_registra_dos_veces() -> None:
    with pytest.raises(ValueError, match="cartera"):
        RegistroContextos([CARTERA, contexto_cartera()])


def test_un_contexto_nuevo_se_suma_sin_tocar_el_registro_ni_el_nucleo() -> None:
    propio = replace(SPEECH, nombre="whatsapp.mensaje", clave_nombre="x.whatsapp")

    registro = RegistroContextos([CARTERA, propio])

    assert registro.obtener("whatsapp.mensaje") is propio


def test_cada_contexto_trae_su_clave_i18n() -> None:
    assert CARTERA.clave_nombre == "textoEnriquecido.contexto.cartera"
    assert SPEECH.clave_nombre == "textoEnriquecido.contexto.mowa_mes.speech"


# --- Cartera -------------------------------------------------------------------------------------


def test_las_variables_de_la_cartera_son_sus_campos_con_su_tipo() -> None:
    esperado = {nombre: TipoValor(tipo.value) for nombre, tipo in CAMPOS_CARTERA.items()}

    assert {v.nombre: v.tipo for v in CARTERA.variables} == esperado
    assert any(t is TipoValor.BOOLEANO for t in esperado.values())  # D2: tambien los booleanos


def test_la_cartera_no_pone_limite_de_largo() -> None:
    assert (CARTERA.limite_largo, CARTERA.umbral_advertencia) == (None, None)


def test_los_campos_de_la_cartera_no_llevan_clave_i18n_propia() -> None:
    assert all(v.clave_nombre is None for v in CARTERA.variables)


def test_el_registro_de_ejemplo_de_la_cartera_tiene_un_valor_del_tipo_de_cada_variable() -> None:
    for variable in CARTERA.variables:
        valor = CARTERA.ejemplo[variable.nombre]
        if variable.tipo is TipoValor.TEXTO:
            assert isinstance(valor, str) and valor.strip(), variable.nombre
        elif variable.tipo is TipoValor.NUMERO:
            assert isinstance(valor, (int, Decimal)) and not isinstance(valor, bool)
        elif variable.tipo is TipoValor.FECHA:
            assert isinstance(valor, date)
        else:
            assert isinstance(valor, bool)
    assert set(CARTERA.ejemplo) == {v.nombre for v in CARTERA.variables}


def test_el_ejemplo_de_la_cartera_usa_datos_sinteticos_conocidos() -> None:
    assert CARTERA.ejemplo["telefono"] == "987654321"
    assert CARTERA.ejemplo["pagare"] == "000000000000000001"
    assert CARTERA.ejemplo["fecha_vencimiento_cuota"] == date(2026, 10, 5)
    assert CARTERA.ejemplo["titular"] == "TITULAR/SINTETICO,UNO"


def test_el_registro_de_ejemplo_se_puede_evaluar_con_las_variables_del_contexto() -> None:
    variables = {v.nombre: v.tipo for v in CARTERA.variables}

    compilada = evaluador.compilar_texto(
        "[@titular | primeros(4)] [@telefono | enlace_whatsapp]", variables
    )

    assert compilada.evaluar(CARTERA.ejemplo).texto == "TITU https://wa.me/+51987654321"


def test_la_segmentacion_por_defecto_de_la_cartera_usa_dias_atraso_y_la_tabla_de_siempre() -> None:
    assert CARTERA.variable_dias == "dias_atraso"
    assert [r.clave for r in CARTERA.tabla_rangos] == [s.value for s in Segmento]
    assert "dias_atraso" in {v.nombre for v in CARTERA.variables}


def test_un_producto_de_la_cartera_es_su_propio_registro() -> None:
    producto = {"pagare": "P", "titular": "UNO", "saldo_capital_pendiente": Decimal("1")}

    assert CARTERA.registro_de_producto(producto) == producto
    assert CARTERA.registro_de_producto(producto) is not producto  # una copia


# --- MOWA MES: speech ----------------------------------------------------------------------------


def test_las_variables_del_speech_son_las_del_mensaje_mas_los_dias_ajustados() -> None:
    variables = {v.nombre: v.tipo for v in SPEECH.variables}

    assert variables == {
        **speech.VARIABLES_DEL_MENSAJE,
        "dias_atraso_ajustados": TipoValor.NUMERO,
    }


def test_solo_las_variables_que_aporta_el_modulo_llevan_clave_i18n() -> None:
    claves = {v.nombre: v.clave_nombre for v in SPEECH.variables}

    assert claves == {
        "titular": None,
        "fecha_vencimiento_cuota": None,
        "whatsapp_contacto": "textoEnriquecido.variable.whatsapp_contacto",
        "dias_atraso_ajustados": "textoEnriquecido.variable.dias_atraso_ajustados",
    }


def test_el_speech_trae_los_limites_de_150_y_160_de_mowa_mes() -> None:
    assert (SPEECH.limite_largo, SPEECH.umbral_advertencia) == (LARGO_MAXIMO, LARGO_ADVERTENCIA)
    assert (SPEECH.limite_largo, SPEECH.umbral_advertencia) == (160, 150)


def test_la_segmentacion_del_speech_usa_los_dias_ajustados_y_la_tabla_de_mowa_mes() -> None:
    assert SPEECH.variable_dias == "dias_atraso_ajustados"
    assert [(r.clave, r.etiqueta, r.desde, r.hasta) for r in SPEECH.tabla_rangos] == [
        (r.segmento.value, r.etiqueta, r.desde, r.hasta) for r in RANGOS_SEGMENTO
    ]


def test_el_ejemplo_del_speech_da_el_enlace_de_26_caracteres() -> None:
    variables = {v.nombre: v.tipo for v in SPEECH.variables}
    compilada = evaluador.compilar(speech.expresion_de(ORIGINAL[3]), variables)

    resultado = compilada.evaluar(SPEECH.ejemplo)

    assert resultado.problemas == ()
    assert resultado.texto.endswith("https://wa.me/+51" + SPEECH.ejemplo["whatsapp_contacto"])
    assert len(resultado.texto) <= compilada.cota
    assert SPEECH.ejemplo["whatsapp_contacto"] == "900000123"


def test_el_producto_se_convierte_al_registro_del_speech() -> None:
    producto = {
        "titular": "OTRO/SINTETICO,TRES",
        "fecha_vencimiento_cuota": date(2026, 9, 5),
        "dias_atraso": 45,
        "telefono": "987654321",
    }

    registro = SPEECH.registro_de_producto(producto)

    assert registro == {
        "titular": "OTRO/SINTETICO,TRES",
        "fecha_vencimiento_cuota": date(2026, 9, 5),
        "whatsapp_contacto": SPEECH.ejemplo["whatsapp_contacto"],
        "dias_atraso_ajustados": 45,
    }


def test_un_producto_sin_dias_de_atraso_queda_sin_dias_ajustados() -> None:
    registro = SPEECH.registro_de_producto({"titular": "X"})

    assert registro["dias_atraso_ajustados"] is None
    assert registro["fecha_vencimiento_cuota"] is None


# --- Origen de cada variable ---------------------------------------------------------------------


def test_los_campos_de_la_cartera_tienen_a_la_cartera_como_origen() -> None:
    assert {v.origen for v in CARTERA.variables} == {"cartera"}


def test_en_el_speech_solo_lo_que_aporta_el_modulo_lo_tiene_como_origen() -> None:
    assert {v.nombre: v.origen for v in SPEECH.variables} == {
        "titular": "cartera",
        "fecha_vencimiento_cuota": "cartera",
        "whatsapp_contacto": "mowa_mes.speech",
        "dias_atraso_ajustados": "mowa_mes.speech",
    }
