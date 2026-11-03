"""El mensaje en la previsualizacion de la campana de WhatsMKT, sin base (T-WM-B4b1, parte 1).

El servicio real sobre dobles en memoria (`tests/ayudas/previa_whatsmkt_falsos.py`). Telefonos
sinteticos 900000xxx.
"""

from dataclasses import replace

import pytest

from app.core.entities.textos_guardados import TextoNoEncontrado, VersionDeTextoNoEncontrada
from app.core.entities.whatsmkt import CodigoWhatsmkt, ConfiguracionWhatsmkt, ModoCampana
from app.core.services.plataformas.whatsmkt.archivo_contactos import SeleccionCampana
from app.core.services.plataformas.whatsmkt.previa import MensajePedido, PeticionPrevia
from tests.ayudas.previa_whatsmkt_falsos import (
    DEFINICION_ID,
    MOMENTO,
    RepositorioWhatsmktFalso,
    TextosFalsos,
    servicio_de_previa,
)
from tests.test_whatsmkt_contactos import CORTE, definicion, producto

GLOBAL, POR_SEGMENTO = ModoCampana.GLOBAL, ModoCampana.POR_SEGMENTO
HOLA = "Hola [$MACRO1$], tu pagare es [$MACRO2$]. INFO por [whatsapp]"


def previa(
    productos,
    *,
    modo=GLOBAL,
    mensaje=None,
    mensajes=None,
    textos=None,
    whatsmkt=None,
    **servicio,
):
    peticion = PeticionPrevia(
        SeleccionCampana(fecha_corte=CORTE, fecha_envio=CORTE, cantidad=1000),
        DEFINICION_ID,
        None,
        modo,
        mensaje=mensaje,
        mensajes_por_segmento=mensajes or {},
    )
    return servicio_de_previa(
        productos, definicion(), textos=textos, whatsmkt=whatsmkt, **servicio
    ).previsualizar(peticion)


def con_whatsapp(numero="900000123", **cambios) -> RepositorioWhatsmktFalso:
    configuracion = ConfiguracionWhatsmkt(
        actualizado_en=MOMENTO, whatsapp_contacto=numero, **cambios
    )
    return RepositorioWhatsmktFalso(configuracion=configuracion)


def codigos(resultado) -> list[CodigoWhatsmkt]:
    return [p.codigo for p in resultado.problemas]


# --- El ejemplo -------------------------------------------------------------------------------


def test_el_ejemplo_reemplaza_las_macros_con_la_primera_fila_de_productos_y_el_whatsapp() -> None:
    textos = TextosFalsos()
    textos.agregar(10, HOLA)

    resultado = previa(
        [producto(1, titular="Ana"), producto(2, titular="Bea")],
        mensaje=MensajePedido(10),
        textos=textos,
        whatsmkt=con_whatsapp(),
    )

    [campana] = resultado.campanas
    assert campana.mensaje.ejemplo == (
        f"Hola Ana, tu pagare es {1:018d}. INFO por https://wa.me/+51900000123"
    )
    assert (campana.mensaje.texto_id, campana.mensaje.nombre, campana.mensaje.version) == (
        10,
        "Mensaje 10",
        1,
    )
    assert campana.mensaje.texto == HOLA
    assert resultado.problemas == ()


def test_el_ejemplo_usa_la_primera_fila_de_productos_que_si_sale_no_la_de_un_supervisor() -> None:
    textos = TextosFalsos()
    textos.agregar(10, "Hola [$MACRO1$]")

    resultado = previa(
        [producto(1, telefono=None, titular="Ana"), producto(2, titular="Bea")],
        mensaje=MensajePedido(10),
        textos=textos,
    )

    assert resultado.campanas[0].mensaje.ejemplo == "Hola Bea"


def test_sin_whatsapp_de_contacto_el_marcador_queda_tal_cual() -> None:
    textos = TextosFalsos()
    textos.agregar(10, "Hola. INFO por [whatsapp]")

    resultado = previa([producto(1)], mensaje=MensajePedido(10), textos=textos)

    assert resultado.campanas[0].mensaje.ejemplo == "Hola. INFO por [whatsapp]"


def test_sin_mensaje_la_campana_va_sin_mensaje_y_es_el_problema_sin_mensaje() -> None:
    resultado = previa([producto(1)])

    assert resultado.campanas[0].mensaje is None
    [problema] = resultado.problemas
    assert (problema.codigo, problema.segmento) == (CodigoWhatsmkt.SIN_MENSAJE, None)


# --- La version y el texto elegido ------------------------------------------------------------


def test_sin_version_se_usa_la_vigente_y_con_version_la_pedida() -> None:
    textos = TextosFalsos()
    textos.agregar(10, "Primera", "Segunda", "Tercera")

    vigente = previa([producto(1)], mensaje=MensajePedido(10), textos=textos)
    primera = previa([producto(1)], mensaje=MensajePedido(10, 1), textos=textos)

    assert (vigente.campanas[0].mensaje.version, vigente.campanas[0].mensaje.texto) == (
        3,
        "Tercera",
    )
    assert (primera.campanas[0].mensaje.version, primera.campanas[0].mensaje.ejemplo) == (
        1,
        "Primera",
    )


def test_un_texto_que_no_existe_lanza_texto_no_encontrado() -> None:
    with pytest.raises(TextoNoEncontrado):
        previa([producto(1)], mensaje=MensajePedido(99), textos=TextosFalsos())


def test_un_texto_de_otro_contexto_es_para_whatsmkt_un_texto_que_no_existe() -> None:
    textos = TextosFalsos()
    textos.agregar(11, "Hola", contexto="mowa_mes.otro")

    with pytest.raises(TextoNoEncontrado):
        previa([producto(1)], mensaje=MensajePedido(11), textos=textos)


def test_una_version_que_no_existe_lanza_version_de_texto_no_encontrada() -> None:
    textos = TextosFalsos()
    textos.agregar(10, "Hola", "Hola 2")

    with pytest.raises(VersionDeTextoNoEncontrada):
        previa([producto(1)], mensaje=MensajePedido(10, 7), textos=textos)


# --- Los problemas del mensaje ----------------------------------------------------------------


def test_una_macro_inexistente_es_un_problema_con_la_macro_y_la_cantidad() -> None:
    textos = TextosFalsos()
    textos.agregar(10, "Hola [$MACRO1$] y [$MACRO3$]")  # la definicion tiene 2 macros

    resultado = previa([producto(1)], mensaje=MensajePedido(10), textos=textos)

    [problema] = resultado.problemas
    assert problema.codigo is CodigoWhatsmkt.MACRO_INEXISTENTE
    assert dict(problema.parametros) == {"macro": "[$MACRO3$]", "n": 2}
    assert problema.segmento is None  # modo global


def test_el_mensaje_con_emoji_es_un_problema_con_el_caracter_y_la_posicion() -> None:
    textos = TextosFalsos()
    textos.agregar(10, "Hola 😀")

    [problema] = previa([producto(1)], mensaje=MensajePedido(10), textos=textos).problemas

    assert problema.codigo is CodigoWhatsmkt.MENSAJE_CON_EMOJI
    assert dict(problema.parametros) == {"caracter": "😀", "posicion": 6}


def test_el_largo_se_mide_con_el_tope_vigente_de_la_configuracion_y_whatsapp_como_26() -> None:
    textos = TextosFalsos()
    textos.agregar(10, "a" * 75 + "[whatsapp]")  # 101 contados como 26
    whatsmkt = con_whatsapp(tope_mensaje=100)

    pasado = previa([producto(1)], mensaje=MensajePedido(10), textos=textos, whatsmkt=whatsmkt)
    whatsmkt.configuracion = replace(whatsmkt.configuracion, tope_mensaje=101)  # cambia el tope
    cabe = previa([producto(1)], mensaje=MensajePedido(10), textos=textos, whatsmkt=whatsmkt)

    [problema] = pasado.problemas
    assert problema.codigo is CodigoWhatsmkt.MENSAJE_LARGO
    assert dict(problema.parametros) == {"largo": 101, "maximo": 100}
    assert cabe.problemas == ()


def test_un_mensaje_deshabilitado_es_un_problema_pero_se_previsualiza() -> None:
    textos = TextosFalsos()
    textos.agregar(10, "Hola", nombre="Viejo", deshabilitado=True)

    resultado = previa([producto(1)], mensaje=MensajePedido(10), textos=textos)

    [problema] = resultado.problemas
    assert problema.codigo is CodigoWhatsmkt.MENSAJE_DESHABILITADO
    assert resultado.campanas[0].mensaje.deshabilitado is True
    assert resultado.campanas[0].mensaje.ejemplo == "Hola"


def test_usar_whatsapp_sin_numero_de_contacto_es_sin_whatsapp() -> None:
    textos = TextosFalsos()
    textos.agregar(10, "INFO por [whatsapp]")

    sin_numero = previa([producto(1)], mensaje=MensajePedido(10), textos=textos)
    con_numero = previa(
        [producto(1)], mensaje=MensajePedido(10), textos=textos, whatsmkt=con_whatsapp()
    )

    assert codigos(sin_numero) == [CodigoWhatsmkt.SIN_WHATSAPP]
    assert con_numero.problemas == ()


def test_un_mensaje_sin_whatsapp_no_pide_el_numero() -> None:
    textos = TextosFalsos()
    textos.agregar(10, "Hola [$MACRO1$]")

    assert previa([producto(1)], mensaje=MensajePedido(10), textos=textos).problemas == ()


def test_varios_problemas_del_mensaje_se_informan_todos_en_este_orden() -> None:
    textos = TextosFalsos()
    textos.agregar(10, "😀 [$MACRO9$] " + "a" * 30 + " [whatsapp]", deshabilitado=True)

    resultado = previa(
        [producto(1)],
        mensaje=MensajePedido(10),
        textos=textos,
        whatsmkt=RepositorioWhatsmktFalso(
            configuracion=ConfiguracionWhatsmkt(actualizado_en=MOMENTO, tope_mensaje=20)
        ),
    )

    assert codigos(resultado) == [
        CodigoWhatsmkt.MENSAJE_DESHABILITADO,
        CodigoWhatsmkt.MACRO_INEXISTENTE,
        CodigoWhatsmkt.MENSAJE_CON_EMOJI,
        CodigoWhatsmkt.MENSAJE_LARGO,
        CodigoWhatsmkt.SIN_WHATSAPP,
    ]


def test_los_problemas_del_mensaje_van_despues_de_los_de_la_campana() -> None:
    textos = TextosFalsos()
    textos.agregar(10, "Hola [$MACRO9$]")

    resultado = previa([producto(1)], mensaje=MensajePedido(10), textos=textos, supervisores=())

    assert codigos(resultado) == [CodigoWhatsmkt.SIN_SUPERVISORES, CodigoWhatsmkt.MACRO_INEXISTENTE]


# --- Por segmento -----------------------------------------------------------------------------


def test_por_segmento_cada_campana_usa_el_mensaje_pedido_o_el_de_su_segmento() -> None:
    textos = TextosFalsos()
    textos.agregar(10, "Preventivo [$MACRO1$]")
    textos.agregar(11, "Tramo dos [$MACRO1$]")
    textos.agregar(12, "Pedido para mayores [$MACRO1$]")
    whatsmkt = RepositorioWhatsmktFalso()
    whatsmkt.con_texto_en("preventivo", 10)
    whatsmkt.con_texto_en("tramo_2", 11)
    productos = [
        producto(1, -3, titular="A"),
        producto(2, 5, titular="B"),
        producto(3, 20, titular="C"),
    ]

    resultado = previa(
        productos,
        modo=POR_SEGMENTO,
        mensajes={"mayores_2": MensajePedido(12)},
        textos=textos,
        whatsmkt=whatsmkt,
    )

    assert [
        (c.segmento.clave, c.mensaje.texto_id, c.mensaje.ejemplo) for c in resultado.campanas
    ] == [
        ("preventivo", 10, "Preventivo A"),
        ("tramo_2", 11, "Tramo dos B"),
        ("mayores_2", 12, "Pedido para mayores C"),
    ]


def test_lo_pedido_para_un_segmento_gana_al_de_su_configuracion() -> None:
    textos = TextosFalsos()
    textos.agregar(10, "De la configuracion")
    textos.agregar(12, "Elegido ahora")
    whatsmkt = RepositorioWhatsmktFalso()
    whatsmkt.con_texto_en("tramo_2", 10)

    resultado = previa(
        [producto(1, 5)],
        modo=POR_SEGMENTO,
        mensajes={"tramo_2": MensajePedido(12)},
        textos=textos,
        whatsmkt=whatsmkt,
    )

    assert resultado.campanas[0].mensaje.texto == "Elegido ahora"


def test_un_segmento_sin_mensaje_pedido_ni_configurado_va_sin_mensaje() -> None:
    textos = TextosFalsos()
    textos.agregar(10, "Solo para el tramo 2")
    productos = [producto(1, 5), producto(2, 20)]

    resultado = previa(
        productos,
        modo=POR_SEGMENTO,
        mensajes={"tramo_2": MensajePedido(10)},
        textos=textos,
    )

    assert [(c.segmento.clave, c.mensaje is None) for c in resultado.campanas] == [
        ("tramo_2", False),
        ("mayores_2", True),
    ]
    assert [(p.codigo, p.segmento) for p in resultado.problemas] == [
        (CodigoWhatsmkt.SIN_MENSAJE, "mayores_2")
    ]


def test_los_problemas_del_mensaje_dicen_a_que_segmento_se_refieren() -> None:
    textos = TextosFalsos()
    textos.agregar(10, "Bien")
    textos.agregar(11, "Mal [$MACRO9$]")
    textos.agregar(12, "Peor 😀")
    productos = [producto(1, -3), producto(2, 5), producto(3, 20)]

    resultado = previa(
        productos,
        modo=POR_SEGMENTO,
        mensajes={
            "preventivo": MensajePedido(10),
            "tramo_2": MensajePedido(11),
            "mayores_2": MensajePedido(12),
        },
        textos=textos,
    )

    assert [(p.codigo, p.segmento) for p in resultado.problemas] == [
        (CodigoWhatsmkt.MACRO_INEXISTENTE, "tramo_2"),
        (CodigoWhatsmkt.MENSAJE_CON_EMOJI, "mayores_2"),
    ]


def test_el_mensaje_global_se_ignora_en_modo_por_segmento_y_el_mapa_en_modo_global() -> None:
    textos = TextosFalsos()
    textos.agregar(10, "Global")
    textos.agregar(11, "De un segmento")

    por_segmento = previa(
        [producto(1, 5)], modo=POR_SEGMENTO, mensaje=MensajePedido(10), textos=textos
    )
    en_global = previa([producto(1, 5)], mensajes={"tramo_2": MensajePedido(11)}, textos=textos)

    assert por_segmento.campanas[0].mensaje is None
    assert en_global.campanas[0].mensaje is None


def test_un_segmento_sin_productos_no_resuelve_su_mensaje() -> None:
    # `mayores_2` no tiene productos: aunque su texto no exista, no se busca ni da error.
    whatsmkt = RepositorioWhatsmktFalso()
    whatsmkt.con_texto_en("mayores_2", 999)

    resultado = previa([producto(1, 5)], modo=POR_SEGMENTO, whatsmkt=whatsmkt)

    assert [c.segmento.clave for c in resultado.campanas] == ["tramo_2"]
