"""Pruebas de la conciliacion de cargados y enviados (RF-MM-22, C-3, C-5), con datos sinteticos."""

from datetime import date

import pytest

from app.core.entities.mowa_mes import CodigoMowaMes, PartesSegmento, Segmento
from app.core.entities.mowa_mes_campana import FilaCarga
from app.core.entities.mowa_mes_reporte import FilaReporte
from app.core.services.plataformas.mowa_mes import speech
from app.core.services.plataformas.mowa_mes.conciliacion import conciliar, normalizar_mensaje
from app.core.services.texto_enriquecido.gsm7 import a_gsm7

MES_ID = 70001


def _enviada(fila: int, cargada: FilaCarga, mes_id: int = MES_ID, **cambios) -> FilaReporte:
    datos = {
        "fila": fila,
        "mes_id": mes_id,
        "celular": cargada.numero,
        "mensaje": cargada.mensaje,
        "fecha_envio": "14/09/26",
        "dni": cargada.dni,
        "estado": "enviado",
        "salida": "Nro. LARGO",
        "usuario": "usuario_sintetico",
    }
    datos.update(cambios)
    return FilaReporte(**datos)


SUPERVISION = FilaCarga("900000001", "ZZPRUEBA te informa que tu cuota venció", "00000001", True)
PRODUCTO = FilaCarga("900000101", "ZZPRUEBA te informa que tu cuota venció", "12345678")
OTRO = FilaCarga("900000102", " ZZPRUEBA acércate, Más INFO", "87654321")


@pytest.mark.parametrize(
    ("texto", "normalizado"),
    [
        ("venció acércate a través Más día", "vencio acercate a traves Mas dia"),
        ("  ZZPRUEBA pingüino  ", "ZZPRUEBA pinguino"),
        ("Muñoz ÑANDÚ", "Munoz NANDU"),  # C-3: la n con virgulilla queda n
        ("sin cambios", "sin cambios"),
    ],
)
def test_normalizar_mensaje(texto, normalizado) -> None:
    assert normalizar_mensaje(texto) == normalizado


def test_mes_quita_tildes_y_recorta_espacios_y_aun_asi_coincide() -> None:
    enviada = _enviada(2, OTRO, mensaje="ZZPRUEBA acercate, Mas INFO")

    resultado = conciliar([OTRO], [enviada])

    assert (resultado.total.enviados, resultado.sin_correspondencia) == (1, 0)


def test_la_normalizacion_se_aplica_a_los_dos_lados() -> None:
    sin_tilde_cargado = FilaCarga("900000103", "ZZPRUEBA vencio", "11111111")

    resultado = conciliar(
        [sin_tilde_cargado], [_enviada(2, sin_tilde_cargado, mensaje="ZZPRUEBA venció")]
    )

    assert resultado.total.enviados == 1


# --- Mensaje en GSM-7 (RF-MM-27, T-MM-B9): la conciliacion no cambia de codigo -------------------
#
# Los mensajes nuevos se guardan ya normalizados y `normalizar_mensaje` es idempotente sobre ellos;
# una campana anterior, con tildes guardadas, sigue conciliando como siempre.

_EMOJI = "\N{THUMBS UP SIGN}"
_NBSP = "\N{NO-BREAK SPACE}"
_ANGULAR_I = "\N{LEFT-POINTING DOUBLE ANGLE QUOTATION MARK}"
_ANGULAR_D = "\N{RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK}"
_EURO = "\N{EURO SIGN}"


def _mensaje_nuevo_de_mowa_mes() -> str:
    """El mensaje tal como lo arma MOWA MES hoy: un emoji que se borra, una guillemet que se
    transliteran, un espacio duro, tildes y un extendido (el euro)."""
    partes = PartesSegmento(
        Segmento.DE_1_A_8,
        f" tu cuota venció {_EMOJI}{_ANGULAR_I}mañana{_ANGULAR_D}{_NBSP}paga {_EURO}10",
        " gracias",
    )
    return speech.ConstructorMensajes((partes,), None).mensaje_de(
        Segmento.DE_1_A_8, "ZZPRUEBA", date(2026, 9, 5)
    )


def test_la_campana_nueva_normalizada_concilia_contra_un_reporte_con_el_mismo_texto() -> None:
    mensaje = _mensaje_nuevo_de_mowa_mes()
    nueva = FilaCarga("900000104", mensaje, "22222222")

    resultado = conciliar([nueva], [_enviada(2, nueva)])

    assert mensaje == 'ZZPRUEBA tu cuota vencio "manana" paga €10' + "05/09/2026 gracias"
    assert (resultado.total.enviados, resultado.sin_correspondencia) == (1, 0)


def test_la_campana_nueva_y_la_anterior_con_tildes_concilian_igual() -> None:
    texto_enviado = "ZZPRUEBA te informa que tu cuota vencio, acercate"  # lo que MES devuelve
    anterior = FilaCarga("900000105", "ZZPRUEBA te informa que tu cuota venció, acércate", "1")
    nueva = FilaCarga("900000106", a_gsm7(anterior.mensaje), "2")
    reporte = [
        _enviada(2, anterior, mensaje=texto_enviado),
        _enviada(3, nueva, mensaje=texto_enviado),
    ]

    resultado = conciliar([anterior, nueva], reporte)

    assert nueva.mensaje != anterior.mensaje  # una se guardo con tildes y la otra normalizada
    assert (resultado.total.enviados, resultado.sin_correspondencia) == (2, 0)


def test_normalizar_mensaje_es_idempotente_sobre_un_mensaje_ya_normalizado() -> None:
    mensaje = _mensaje_nuevo_de_mowa_mes()

    assert normalizar_mensaje(mensaje) == normalizar_mensaje(normalizar_mensaje(mensaje))
    assert normalizar_mensaje(mensaje) == mensaje.strip()


def test_un_mismo_telefono_con_el_mismo_mensaje_se_empareja_una_fila_por_fila() -> None:
    cargadas = [PRODUCTO, PRODUCTO]

    resultado = conciliar(cargadas, [_enviada(2, PRODUCTO)])

    assert (resultado.productos.cargados, resultado.productos.enviados) == (2, 1)
    assert resultado.productos.no_enviados == 1
    assert resultado.sin_correspondencia == 0


def test_supervision_y_productos_van_aparte_y_suman_el_total() -> None:
    cargadas = [SUPERVISION, PRODUCTO, OTRO]
    reporte = [_enviada(2, SUPERVISION), _enviada(3, PRODUCTO, estado="fallido")]

    resultado = conciliar(cargadas, reporte)

    assert (resultado.supervision.cargados, resultado.supervision.enviados) == (1, 1)
    # E-1: el producto emparejado como fallido no cuenta como enviado.
    assert (resultado.productos.cargados, resultado.productos.enviados) == (2, 0)
    assert resultado.productos.por_estado == {"fallido": 1}
    assert (resultado.total.cargados, resultado.total.enviados) == (3, 1)
    assert resultado.total.por_estado == {"enviado": 1, "fallido": 1}


def test_filas_del_reporte_sin_correspondencia() -> None:
    ajena = FilaCarga("900000999", "ZZPRUEBA de otra campana", "99999999")

    resultado = conciliar(
        [PRODUCTO], [_enviada(2, PRODUCTO), _enviada(3, ajena, estado="rechazado")]
    )

    assert resultado.sin_correspondencia == 1
    assert resultado.sin_correspondencia_por_estado == {"rechazado": 1}


def test_el_dni_y_el_numero_tambien_cuentan() -> None:
    reporte = [_enviada(2, PRODUCTO, dni="00000000"), _enviada(3, PRODUCTO, celular="900000555")]

    resultado = conciliar([PRODUCTO], reporte)

    assert (resultado.total.enviados, resultado.sin_correspondencia) == (0, 2)


def test_varios_id_se_cuentan_por_separado_y_se_advierte_el_que_no_coincide() -> None:
    ajena = FilaCarga("900000999", "ZZPRUEBA de otra campana", "99999999")
    reporte = [
        _enviada(2, SUPERVISION, mes_id=70001),
        _enviada(3, PRODUCTO, mes_id=70002),
        _enviada(4, ajena, mes_id=70003),
    ]

    resultado = conciliar([SUPERVISION, PRODUCTO], reporte)

    assert [(i.mes_id, i.filas, i.con_correspondencia) for i in resultado.por_id] == [
        (70001, 1, 1),
        (70002, 1, 1),
        (70003, 1, 0),
    ]
    (advertencia,) = resultado.advertencias
    assert (advertencia.codigo, advertencia.mes_id) == (CodigoMowaMes.ID_SIN_CORRESPONDENCIA, 70003)


def test_sin_reporte_nada_se_envio() -> None:
    resultado = conciliar([SUPERVISION, PRODUCTO], [])

    assert (resultado.total.cargados, resultado.total.enviados, resultado.total.no_enviados) == (
        2,
        0,
        2,
    )
    assert resultado.por_id == () and resultado.advertencias == ()


# --- Que cuenta como enviado (E-1) --------------------------------------


def test_una_fila_emparejada_con_otro_estado_no_cuenta_como_enviada() -> None:
    reporte = [
        _enviada(2, SUPERVISION, estado="fallido"),
        _enviada(3, PRODUCTO, estado=" Enviado "),
        _enviada(4, OTRO, estado="rechazado"),
    ]

    resultado = conciliar([SUPERVISION, PRODUCTO, OTRO], reporte)

    assert (resultado.supervision.enviados, resultado.supervision.no_enviados) == (0, 1)
    assert resultado.supervision.por_estado == {"fallido": 1}
    assert (resultado.productos.enviados, resultado.productos.no_enviados) == (1, 1)
    assert resultado.productos.por_estado == {"Enviado": 1, "rechazado": 1}
    assert (resultado.total.cargados, resultado.total.enviados) == (3, 1)
    assert resultado.total.no_enviados == 2
    assert resultado.sin_correspondencia == 0


def test_las_cifras_por_id_cuentan_las_emparejadas_con_cualquier_estado() -> None:
    reporte = [_enviada(2, PRODUCTO, estado="fallido")]

    resultado = conciliar([PRODUCTO], reporte)

    assert [(i.mes_id, i.filas, i.con_correspondencia) for i in resultado.por_id] == [
        (MES_ID, 1, 1)
    ]
    assert resultado.advertencias == ()
