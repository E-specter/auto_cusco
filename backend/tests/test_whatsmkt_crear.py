"""Crear el lote de campanas de WhatsMKT, sin base (T-WM-B4b1, parte 2; RF-WM-23, 33 a 36).

El servicio real sobre dobles en memoria (`tests/ayudas/campanas_whatsmkt_falsas.py`). Lo que se
prueba: que el lote se crea entero o no se crea, lo que cada campana congela, los problemas que
impiden crear, los nombres, la foto y el adjunto. Datos sinteticos (telefonos 900000xxx).
"""

from dataclasses import replace
from datetime import date, time

import pytest

from app.core.entities.textos_guardados import TextoNoEncontrado
from app.core.entities.whatsmkt import (
    AdjuntoNoEncontrado,
    CodigoWhatsmkt,
    Horario,
    ModoCampana,
    TipoEnvio,
)
from app.core.services.plataformas.whatsmkt.archivo_contactos import SeleccionCampana
from app.core.services.plataformas.whatsmkt.crear import CreacionInvalida, PeticionCreacion
from app.core.services.plataformas.whatsmkt.previa import MensajePedido, PeticionPrevia
from tests.ayudas import adjuntos_sinteticos as sint
from tests.ayudas.campanas_whatsmkt_falsas import Entorno
from tests.ayudas.previa_whatsmkt_falsos import DEFINICION_ID
from tests.test_whatsmkt_contactos import CORTE, producto

GLOBAL, POR_SEGMENTO = ModoCampana.GLOBAL, ModoCampana.POR_SEGMENTO
HOLA = "Hola [$MACRO1$], tu pagare es [$MACRO2$]. INFO por [whatsapp]"


def entorno(productos=None, **kwargs) -> Entorno:
    e = Entorno(productos if productos is not None else [producto(1), producto(2)], **kwargs)
    e.textos.agregar(10, HOLA, "Hola [$MACRO1$] version 2 [whatsapp]")
    e.whatsmkt.configuracion = replace(e.whatsmkt.configuracion, whatsapp_contacto="900000123")
    return e


def pedido(
    modo=GLOBAL,
    *,
    mensaje=MensajePedido(10),
    mensajes=None,
    fecha_envio=CORTE,
    **creacion,
) -> PeticionCreacion:
    creacion.setdefault("horarios", ("horario_1",))
    return PeticionCreacion(
        previa=PeticionPrevia(
            SeleccionCampana(fecha_corte=CORTE, fecha_envio=fecha_envio, cantidad=1000),
            DEFINICION_ID,
            None,
            modo,
            mensaje=mensaje,
            mensajes_por_segmento=mensajes or {},
        ),
        filtros=("dias_atraso:mayor_igual:0",),
        orden="-dias_atraso",
        **creacion,
    )


def todos_los_segmentos(texto_id=10) -> dict:
    return dict.fromkeys(("preventivo", "tramo_2", "mayores_2"), MensajePedido(texto_id))


def problemas_de(entorno_, peticion) -> list[CodigoWhatsmkt]:
    with pytest.raises(CreacionInvalida) as error:
        entorno_.servicio().crear(peticion)
    return [p.codigo for p in error.value.problemas]


# --- Lo que se crea y lo que se congela -------------------------------------------------------


def test_un_lote_global_crea_una_campana_con_todo_congelado() -> None:
    e = entorno([producto(1, titular="Ana"), producto(2, telefono=None)])

    lote = e.servicio().crear(
        pedido(
            horarios=("horario_1", "horario_2"),
            lo_antes_posible=True,
            fecha_envio=date(2026, 11, 3),
        )
    )

    assert (lote.lote_id, lote.modo) == (1, GLOBAL)
    [c] = lote.campanas
    assert (c.segmento, c.segmento_etiqueta) == (None, None)
    assert c.nombre == "CUZCO_Vencida whatsapp 2026.11.02"
    assert (c.definicion_id, c.definicion_version) == (DEFINICION_ID, 1)
    assert c.definicion_nombre == "WhatsMKT prueba"
    assert (c.texto_guardado_id, c.texto_version, c.mensaje_texto) == (
        10,
        2,
        e.textos.obtener(10).versiones[1].contenido["texto"],
    )
    assert c.whatsapp_contacto == "900000123"
    assert (c.fecha_corte, c.fecha_envio) == (CORTE, date(2026, 11, 3))
    assert [(h.nombre, h.inicio, h.fin) for h in c.horarios] == [
        ("horario_1", time(8), time(14)),
        ("horario_2", time(14), time(20)),
    ]
    assert c.lo_antes_posible is True
    assert c.tipo_envio is TipoEnvio.SOLO_TEXTO
    assert (c.foto_id, c.adjunto_id, c.etiqueta_vcard) == (None, None, None)
    assert c.supervisores == ("51900000902", "51900000901")
    assert (c.cantidad, c.productos) == (3, 1)
    assert c.filtros == ("dias_atraso:mayor_igual:0",) and c.orden == "-dias_atraso"
    assert c.cantidad_pedida == 1000


def test_las_filas_van_en_orden_con_los_supervisores_primero_y_sin_pagare() -> None:
    e = entorno([producto(1, titular="Ana"), producto(2, titular="Bea")])

    e.servicio().crear(pedido())

    [campana] = e.campanas.lotes[0].campanas
    assert [(f.posicion, f.numero, f.supervision) for f in campana.filas] == [
        (1, "51900000902", True),
        (2, "51900000901", True),
        (3, "51900000001", False),
        (4, "51900000002", False),
    ]
    assert [f.pagare for f in campana.filas] == [None, None, f"{1:018d}", f"{2:018d}"]
    assert campana.filas[2].macros == ("Ana", f"{1:018d}")
    assert campana.filas[0].macros == campana.filas[2].macros  # los supervisores copian la primera


def test_sin_version_se_congela_la_vigente_y_con_version_la_exacta() -> None:
    e = entorno()

    vigente = e.servicio().crear(pedido(mensaje=MensajePedido(10)))
    exacta = e.servicio().crear(pedido(mensaje=MensajePedido(10, 1)))

    assert vigente.campanas[0].texto_version == 2
    assert exacta.campanas[0].texto_version == 1
    assert exacta.campanas[0].mensaje_texto == HOLA


def test_un_lote_por_segmento_crea_una_campana_por_segmento_con_productos() -> None:
    productos = [producto(1, -3), producto(2, 5), producto(3, 20), producto(4, 20)]
    e = entorno(productos)

    lote = e.servicio().crear(pedido(POR_SEGMENTO, mensaje=None, mensajes=todos_los_segmentos()))

    assert [(c.segmento, c.segmento_etiqueta, c.productos) for c in lote.campanas] == [
        ("preventivo", "Preventivo", 1),
        ("tramo_2", "Tramo 2", 1),
        ("mayores_2", "Tramos mayores al 2", 2),
    ]
    assert {c.lote_id for c in lote.campanas} == {1}
    assert [c.nombre for c in lote.campanas] == [
        "CUZCO_Vencida (Preventivo) whatsapp 2026.11.02",
        "CUZCO_Vencida (Tramo 2) whatsapp 2026.11.02",
        "CUZCO_Vencida (Tramos mayores al 2) whatsapp 2026.11.02",
    ]


def test_las_exclusiones_van_a_su_campana_y_las_de_fuera_del_lote_sin_campana() -> None:
    productos = [
        producto(1, 5),
        producto(2, 5, telefono=None),
        producto(3, None),
        producto(4, 20, telefono=None),
    ]
    e = entorno(productos)

    e.servicio().crear(pedido(POR_SEGMENTO, mensaje=None, mensajes=todos_los_segmentos()))

    [lote] = e.campanas.lotes
    [campana] = lote.campanas
    assert campana.segmento == "tramo_2"
    assert [x.fila for x in campana.exclusiones] == [2]
    assert sorted(x.fila for x in lote.exclusiones_sin_campana) == [
        3,
        4,
    ]  # sin dias, y mayores_2 sin productos


def test_el_archivo_se_llama_como_la_campana_mas_xlsx_y_son_los_bytes_del_xlsx() -> None:
    e = entorno()

    [c] = e.servicio().crear(pedido(nombres={None: 'Cobranza: "uno"'})).campanas

    assert c.archivo_nombre == "Cobranza_ _uno_.xlsx"
    guardado = e.campanas.archivos[c.id]
    assert guardado.nombre == c.archivo_nombre
    assert guardado.contenido[:2] == b"PK"  # un xlsx es un zip
    assert c.archivo_tamano == len(guardado.contenido)


# --- Lo que impide crear: nada se guarda ------------------------------------------------------


def test_sin_horario_no_se_crea_nada() -> None:
    e = entorno()

    assert problemas_de(e, pedido(horarios=())) == [CodigoWhatsmkt.SIN_HORARIO]
    assert e.campanas.lotes == []


def test_sin_supervisores_sin_mensaje_o_sin_productos_no_se_crea_nada() -> None:
    sin_supervisores = entorno(supervisores=())
    sin_mensaje = entorno()
    sin_productos = entorno([producto(1, telefono=None)])

    assert problemas_de(sin_supervisores, pedido()) == [CodigoWhatsmkt.SIN_SUPERVISORES]
    assert problemas_de(sin_mensaje, pedido(mensaje=None)) == [CodigoWhatsmkt.SIN_MENSAJE]
    assert CodigoWhatsmkt.SIN_PRODUCTOS in problemas_de(sin_productos, pedido())
    for e in (sin_supervisores, sin_mensaje, sin_productos):
        assert e.campanas.lotes == []


def test_los_problemas_del_mensaje_impiden_crear() -> None:
    e = entorno()
    e.textos.agregar(11, "Hola 😀 [$MACRO9$] [whatsapp]")
    e.whatsmkt.configuracion = replace(e.whatsmkt.configuracion, whatsapp_contacto=None)

    codigos = problemas_de(e, pedido(mensaje=MensajePedido(11)))

    assert codigos == [
        CodigoWhatsmkt.MACRO_INEXISTENTE,
        CodigoWhatsmkt.MENSAJE_CON_EMOJI,
        CodigoWhatsmkt.SIN_WHATSAPP,
    ]
    assert e.campanas.lotes == []


def test_todos_los_problemas_se_informan_juntos_y_en_el_orden_del_servicio() -> None:
    e = entorno(supervisores=())

    codigos = problemas_de(e, pedido(horarios=(), mensaje=None))

    assert codigos == [
        CodigoWhatsmkt.SIN_HORARIO,
        CodigoWhatsmkt.SIN_SUPERVISORES,
        CodigoWhatsmkt.SIN_MENSAJE,
    ]


def test_un_mensaje_que_no_existe_lanza_su_error_y_no_se_crea_nada() -> None:
    e = entorno()

    with pytest.raises(TextoNoEncontrado):
        e.servicio().crear(pedido(mensaje=MensajePedido(99)))

    assert e.campanas.lotes == []


def test_si_el_guardado_falla_no_queda_ningun_lote() -> None:
    e = entorno()
    e.campanas.falla = RuntimeError("se cayo la base a mitad del lote")

    with pytest.raises(RuntimeError):
        e.servicio().crear(pedido())

    assert e.campanas.lotes == [] and e.campanas.campanas == {}


# --- Nombres ----------------------------------------------------------------------------------


def test_el_nombre_pedido_gana_a_la_plantilla_y_se_limpia() -> None:
    e = entorno()

    [c] = e.servicio().crear(pedido(nombres={None: "   Mi   campana   "})).campanas

    assert c.nombre == "Mi campana"


def test_en_un_lote_con_varias_campanas_y_una_plantilla_sin_segmento_se_agrega_el_segmento() -> (
    None
):
    productos = [producto(1, -3), producto(2, 5)]
    e = entorno(productos)
    e.whatsmkt.configuracion = replace(
        e.whatsmkt.configuracion, plantilla_nombre="Cobranza {fecha_corte}"
    )

    lote = e.servicio().crear(pedido(POR_SEGMENTO, mensaje=None, mensajes=todos_los_segmentos()))

    assert [c.nombre for c in lote.campanas] == [
        "Cobranza 2026.11.02 Preventivo",
        "Cobranza 2026.11.02 Tramo 2",
    ]


def test_un_nombre_de_75_caracteres_se_crea_y_uno_de_76_es_nombre_largo() -> None:
    e = entorno()

    [c] = e.servicio().crear(pedido(nombres={None: "a" * 75})).campanas
    with pytest.raises(CreacionInvalida) as error:
        entorno().servicio().crear(pedido(nombres={None: "a" * 76}))

    assert len(c.nombre) == 75
    [problema] = error.value.problemas
    assert problema.codigo is CodigoWhatsmkt.NOMBRE_LARGO
    assert dict(problema.parametros) == {"largo": 76}
    assert problema.segmento is None


def test_un_nombre_largo_dice_a_que_segmento_se_refiere() -> None:
    productos = [producto(1, -3), producto(2, 5)]
    e = entorno(productos)

    with pytest.raises(CreacionInvalida) as error:
        e.servicio().crear(
            pedido(
                POR_SEGMENTO,
                mensaje=None,
                mensajes=todos_los_segmentos(),
                nombres={"preventivo": "ok", "tramo_2": "b" * 80},
            )
        )

    [problema] = error.value.problemas
    assert (problema.codigo, problema.segmento) == (CodigoWhatsmkt.NOMBRE_LARGO, "tramo_2")
    assert e.campanas.lotes == []


# --- Foto, adjunto y vCard --------------------------------------------------------------------


def test_una_foto_valida_se_congela() -> None:
    e = entorno()
    foto, _ = _biblioteca(e).guardar("yo.jpg", sint.jpeg(200, 200), como_foto=True)

    [c] = e.servicio().crear(pedido(foto_id=foto.id)).campanas

    assert c.foto_id == foto.id


@pytest.mark.parametrize(
    ("contenido", "codigo"),
    [
        (sint.jpeg(201, 200), CodigoWhatsmkt.FOTO_MEDIDAS),
        (sint.png(200, 200), CodigoWhatsmkt.FOTO_FORMATO),
        (sint.PDF, CodigoWhatsmkt.FOTO_FORMATO),
    ],
)
def test_una_foto_invalida_impide_crear(contenido, codigo) -> None:
    e = entorno()
    adjunto, _ = _biblioteca(e).guardar("x", contenido)

    assert problemas_de(e, pedido(foto_id=adjunto.id)) == [codigo]
    assert e.campanas.lotes == []


def test_una_foto_que_no_existe_lanza_adjunto_no_encontrado() -> None:
    e = entorno()

    with pytest.raises(AdjuntoNoEncontrado):
        e.servicio().crear(pedido(foto_id=99))

    assert e.campanas.lotes == []


def test_el_tipo_archivo_congela_el_adjunto_y_uno_archivado_o_inexistente_no_se_acepta() -> None:
    e = entorno()
    biblioteca = _biblioteca(e)
    activo, _ = biblioteca.guardar("a.pdf", sint.PDF)
    archivado, _ = biblioteca.guardar("b.mp4", sint.MP4)
    biblioteca.archivar(archivado.id)

    [c] = e.servicio().crear(pedido(tipo_envio=TipoEnvio.ARCHIVO, adjunto_id=activo.id)).campanas
    for malo in (archivado.id, 99):
        with pytest.raises(AdjuntoNoEncontrado):
            e.servicio().crear(pedido(tipo_envio=TipoEnvio.ARCHIVO, adjunto_id=malo))

    assert (c.tipo_envio, c.adjunto_id) == (TipoEnvio.ARCHIVO, activo.id)
    assert len(e.campanas.lotes) == 1


def test_el_tipo_vcard_congela_la_etiqueta() -> None:
    e = entorno()

    [c] = (
        e.servicio().crear(pedido(tipo_envio=TipoEnvio.VCARD, etiqueta_vcard="Caja Cusco")).campanas
    )

    assert (c.tipo_envio, c.etiqueta_vcard, c.adjunto_id) == (TipoEnvio.VCARD, "Caja Cusco", None)


# --- Los horarios y la fecha ------------------------------------------------------------------


def test_los_horarios_se_congelan_con_las_horas_de_la_configuracion_del_momento() -> None:
    e = entorno()
    e.whatsmkt.configuracion = replace(
        e.whatsmkt.configuracion, horario_2=Horario(time(15), time(19))
    )

    [c] = e.servicio().crear(pedido(horarios=("horario_2",))).campanas
    e.whatsmkt.configuracion = replace(
        e.whatsmkt.configuracion, horario_2=Horario(time(9), time(10))
    )

    assert [(h.nombre, h.inicio, h.fin) for h in c.horarios] == [("horario_2", time(15), time(19))]
    assert e.campanas.campanas[c.id].horarios == c.horarios  # lo guardado no cambia


def test_la_fecha_de_envio_se_acepta_tal_como_llega_aunque_sea_domingo() -> None:
    # shortcut de B4b1: sin validar contra RF-70 (lunes a sabado); B4c la valida.
    domingo = date(2026, 11, 8)
    assert domingo.weekday() == 6

    [c] = entorno().servicio().crear(pedido(fecha_envio=domingo)).campanas

    assert c.fecha_envio == domingo


def _biblioteca(e: Entorno):
    from app.core.services.plataformas.whatsmkt.biblioteca import BibliotecaWhatsmktService

    return BibliotecaWhatsmktService(e.adjuntos)
