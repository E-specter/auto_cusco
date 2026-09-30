"""MOWA MES con el WhatsApp como constante de la campana (B7): una prueba por criterio.

El numero se pliega al compilar: el enlace se arma y se valida una vez. Nada de lo observable
cambia: el oro de B5 (`test_mowa_mes_speech_oro.py`) sigue intacto y en verde.
Titulares y numeros sinteticos.
"""

from datetime import date

import pytest

from app.core.entities.mowa_mes import (
    CodigoMowaMes,
    FaltaWhatsapp,
    MensajeNoGenerable,
    Segmento,
)
from app.core.entities.texto_enriquecido import CodigoTexto
from app.core.services.plataformas.mowa_mes import speech
from app.core.services.plataformas.mowa_mes.campana import FilaCarga, evaluar_producto
from tests.test_api_mowa_mes_configuracion import PARTES, cliente  # noqa: F401
from tests.test_mowa_mes_campana import armar_servicio, peticion, producto
from tests.test_mowa_mes_speech import ORIGINAL

WHATSAPP = "900000123"
INVALIDO = "51900000456"  # 11 digitos: no es un numero de RF-02
VENCIMIENTO = date(2026, 9, 5)
CON_WHATSAPP = {Segmento.DE_31_A_60, Segmento.DE_61_A_90, Segmento.DE_91_A_120}
SIN_WHATSAPP = {Segmento.PREVENTIVA, Segmento.DE_1_A_8, Segmento.DE_9_A_30}


def test_una_campana_sin_productos_en_segmentos_con_whatsapp_se_genera_sin_numero() -> None:
    servicio, campanas, _ = armar_servicio(
        [producto(1), producto(2, dias_atraso=10)], whatsapp=None
    )

    armada = servicio.previsualizar(peticion())
    servicio.crear(peticion())

    assert armada.errores == () and armada.productos_cargados == 2
    assert len(campanas.campanas) == 1


def test_sin_numero_sigue_siendo_sin_whatsapp_y_no_un_error_de_mensaje() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, None)

    for segmento in CON_WHATSAPP:
        assert constructor.requiere_whatsapp_faltante(segmento)
        with pytest.raises(FaltaWhatsapp) as error:
            constructor.mensaje_de(segmento, "ZZPRUEBA", VENCIMIENTO)
        assert not isinstance(error.value, MensajeNoGenerable)
    for segmento in SIN_WHATSAPP:
        assert not constructor.requiere_whatsapp_faltante(segmento)
        assert constructor.mensaje_de(segmento, "ZZPRUEBA", VENCIMIENTO)


def test_sin_numero_un_producto_en_un_segmento_con_whatsapp_da_falta_whatsapp() -> None:
    servicio, _, _ = armar_servicio([producto(1), producto(2, dias_atraso=40)], whatsapp=None)

    armada = servicio.previsualizar(peticion())

    assert [e.codigo for e in armada.errores] == [CodigoMowaMes.FALTA_WHATSAPP]
    assert armada.productos_cargados == 1


def test_previsualizar_el_speech_con_un_numero_invalido_sigue_dando_400_y_no_un_500(
    cliente,  # noqa: F811
) -> None:
    client, _ = cliente

    for numero in ("123", INVALIDO, "800000123", "9000001234"):
        respuesta = client.post(
            "/mowa-mes/speech/previsualizacion", json={"partes": PARTES, "whatsapp": numero}
        )

        assert respuesta.status_code == 400, numero
        assert "detail" in respuesta.json()


def test_previsualizar_el_speech_no_depende_del_numero_y_no_pliega_nada() -> None:
    con = speech.previsualizar(ORIGINAL, WHATSAPP)
    sin = speech.previsualizar(ORIGINAL, None)

    assert [x.largo_maximo for x in con] == [x.largo_maximo for x in sin]
    assert speech.compilar_segmento(ORIGINAL[3]).nodos_plegados == 0  # sin numero: sin constante
    assert speech.compilar_segmento(ORIGINAL[3], WHATSAPP).nodos_plegados == 1


def test_dos_filas_del_mismo_segmento_solo_difieren_por_titular_y_vencimiento() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, WHATSAPP)
    enlace = "https://wa.me/+51" + WHATSAPP

    a = constructor.mensaje_de(Segmento.DE_31_A_60, "AAAAAAAA", date(2026, 9, 5))
    b = constructor.mensaje_de(Segmento.DE_31_A_60, "BBBBBBBB", date(2026, 12, 31))
    de_nuevo = constructor.mensaje_de(Segmento.DE_31_A_60, "AAAAAAAA", date(2026, 9, 5))

    assert a != b and a == de_nuevo  # la segunda llamada no arrastra nada de la anterior
    assert a.replace("AAAAAAAA", "BBBBBBBB", 1).replace("05/09/2026", "31/12/2026") == b
    assert a.endswith(enlace) and b.endswith(enlace)


def test_un_numero_invalido_afecta_solo_a_los_segmentos_que_lo_usan() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, INVALIDO)  # no rompe el constructor

    for segmento in SIN_WHATSAPP:
        assert not constructor.requiere_whatsapp_faltante(segmento)
        assert constructor.mensaje_de(segmento, "ZZPRUEBA", VENCIMIENTO).startswith("ZZPRUEBA")
    for segmento in CON_WHATSAPP:
        assert not constructor.requiere_whatsapp_faltante(segmento)  # hay numero, pero no sirve
        with pytest.raises(MensajeNoGenerable) as error:
            constructor.mensaje_de(segmento, "ZZPRUEBA", VENCIMIENTO)
        assert error.value.segmento is segmento
        assert error.value.codigos == (CodigoTexto.TELEFONO_INVALIDO,)


def test_el_problema_del_numero_se_detecta_al_construir_y_no_en_cada_fila() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, INVALIDO)

    primera = _problemas_de(constructor, Segmento.DE_61_A_90)
    segunda = _problemas_de(constructor, Segmento.DE_61_A_90)

    assert primera == segunda and primera  # los mismos problemas, guardados al compilar


def _problemas_de(constructor, segmento):
    with pytest.raises(MensajeNoGenerable) as error:
        constructor.mensaje_de(segmento, "ZZPRUEBA", VENCIMIENTO)
    return error.value.problemas


def test_un_producto_en_un_segmento_con_numero_invalido_no_sale_como_fila_cargada() -> None:
    # Inalcanzable hoy (configuracion y campana validan el numero); si se colara, `evaluar_producto`
    # lanza en lugar de entregar un SMS sin enlace.
    constructor = speech.ConstructorMensajes(ORIGINAL, INVALIDO)
    datos = producto(1, dias_atraso=40)

    with pytest.raises(MensajeNoGenerable):
        evaluar_producto(datos, date(2026, 9, 1), date(2026, 9, 1), constructor)
    sin_enlace = producto(1, dias_atraso=4)
    assert isinstance(
        evaluar_producto(sin_enlace, date(2026, 9, 1), date(2026, 9, 1), constructor), FilaCarga
    )


def test_el_numero_de_la_fila_ya_no_cuenta_porque_la_constante_manda() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, WHATSAPP)

    mensaje = constructor.mensaje(
        Segmento.DE_31_A_60,
        {"titular": "ZZPRUEBA", "fecha_vencimiento_cuota": VENCIMIENTO, "whatsapp_contacto": "999"},
    )

    assert mensaje.endswith("https://wa.me/+51" + WHATSAPP)


def test_el_problema_se_detecta_al_construir_y_pedir_el_mensaje_no_evalua_nada(monkeypatch) -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, INVALIDO)

    def _no_debe_evaluar(self, producto):
        raise AssertionError("se evaluo una fila de un segmento que ya se sabe no generable")

    monkeypatch.setattr(speech.Compilada, "evaluar", _no_debe_evaluar)

    for segmento in CON_WHATSAPP:
        with pytest.raises(MensajeNoGenerable):
            constructor.mensaje_de(segmento, "ZZPRUEBA", VENCIMIENTO)


def test_previsualizar_compila_los_segmentos_sin_pasar_el_numero(monkeypatch) -> None:
    recibidos = []
    original = speech.compilar_segmento

    def _espia(partes, whatsapp=None):
        recibidos.append(whatsapp)
        return original(partes, whatsapp)

    monkeypatch.setattr(speech, "compilar_segmento", _espia)

    speech.previsualizar(ORIGINAL, WHATSAPP)

    assert recibidos == [None] * len(ORIGINAL)
