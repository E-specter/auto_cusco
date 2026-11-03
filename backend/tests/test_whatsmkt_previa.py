"""Previsualizacion de los archivos de la campana de WhatsMKT, sin base (T-WM-B4a; RF-WM-35).

El servicio real sobre dobles en memoria (`tests/ayudas/previa_whatsmkt_falsos.py`). Telefonos
sinteticos 900000xxx.
"""

from datetime import date

import pytest

from app.core.entities.definiciones_columnas import DefinicionNoEncontrada, VersionNoEncontrada
from app.core.entities.whatsmkt import CodigoWhatsmkt, ModoCampana
from app.core.services.plataformas.whatsmkt.archivo_contactos import SeleccionCampana
from app.core.services.plataformas.whatsmkt.previa import PeticionPrevia
from tests.ayudas.previa_whatsmkt_falsos import DEFINICION_ID, servicio_de_previa
from tests.test_whatsmkt_contactos import CORTE, definicion, producto

GLOBAL, POR_SEGMENTO = ModoCampana.GLOBAL, ModoCampana.POR_SEGMENTO


def previa(productos, modo=GLOBAL, *, fecha_envio=CORTE, version=None, **servicio):
    peticion = PeticionPrevia(
        SeleccionCampana(fecha_corte=CORTE, fecha_envio=fecha_envio, cantidad=1000),
        DEFINICION_ID,
        version,
        modo,
    )
    return servicio_de_previa(productos, definicion(), **servicio).previsualizar(peticion)


def codigos(problemas) -> list[CodigoWhatsmkt]:
    return [p.codigo for p in problemas]


# --- Global y por segmento --------------------------------------------------------------------


def test_en_modo_global_sale_una_campana_sin_segmento() -> None:
    resultado = previa([producto(1, 20), producto(2, -3), producto(3, 5)])

    [campana] = resultado.campanas
    assert campana.segmento is None
    assert (campana.archivo.productos, campana.archivo.supervisores) == (3, 2)
    assert campana.archivo.cantidad == 5  # con los supervisores (S-WM-4)
    assert resultado.problemas == ()


def test_por_segmento_sale_una_campana_por_segmento_con_productos() -> None:
    resultado = previa(
        [producto(1, 20), producto(2, -3), producto(3, 5), producto(4, 20)], POR_SEGMENTO
    )

    assert [
        (c.segmento.clave, c.segmento.etiqueta, c.archivo.productos) for c in resultado.campanas
    ] == [
        ("preventivo", "Preventivo", 1),
        ("tramo_2", "Tramo 2", 1),
        ("mayores_2", "Tramos mayores al 2", 2),
    ]
    assert all(c.archivo.supervisores == 2 for c in resultado.campanas)  # cada archivo, los suyos


def test_las_cabeceras_traen_la_etiqueta_de_cada_columna() -> None:
    [campana] = previa([producto(1)]).campanas

    assert [(h.nombre, h.etiqueta) for h in campana.cabeceras] == [
        ("número", None),
        ("[$MARCRO1$]", "Nombres del titular"),
        ("[$MARCRO2$]", None),
    ]


def test_disponibles_y_solicitados_salen_de_la_seleccion() -> None:
    resultado = previa([producto(1), producto(2)])

    assert (resultado.disponibles, resultado.solicitados) == (2, 1000)


# --- Exclusiones ------------------------------------------------------------------------------


def test_las_exclusiones_van_a_la_campana_de_su_segmento() -> None:
    productos = [
        producto(1, 5),
        producto(2, 5, telefono=None),  # tramo_2
        producto(3, 20),
        producto(4, 20, titular=None),  # mayores_2
        producto(5, 20, telefono="12345"),  # mayores_2
    ]

    resultado = previa(productos, POR_SEGMENTO)

    por_segmento = {c.segmento.clave: c for c in resultado.campanas}
    assert [e.codigo for e in por_segmento["tramo_2"].exclusiones] == [CodigoWhatsmkt.SIN_TELEFONO]
    assert [e.fila for e in por_segmento["mayores_2"].exclusiones] == [4, 5]
    assert resultado.exclusiones_sin_campana == ()
    assert resultado.total_exclusiones == 3


def test_en_modo_global_todas_las_exclusiones_son_de_la_unica_campana() -> None:
    resultado = previa([producto(1), producto(2, 20, telefono=None), producto(3, titular=None)])

    [campana] = resultado.campanas
    assert [e.fila for e in campana.exclusiones] == [2, 3]
    assert resultado.exclusiones_sin_campana == ()


def test_las_exclusiones_de_un_segmento_sin_productos_no_se_pierden() -> None:
    # El unico producto de `mayores_2` se excluye: no hay campana de ese segmento.
    resultado = previa([producto(1, 5), producto(2, 20, telefono=None)], POR_SEGMENTO)

    assert [c.segmento.clave for c in resultado.campanas] == ["tramo_2"]
    assert [(e.fila, e.codigo) for e in resultado.exclusiones_sin_campana] == [
        (2, CodigoWhatsmkt.SIN_TELEFONO)
    ]
    assert resultado.total_exclusiones == 1


# --- sin_dias_atraso --------------------------------------------------------------------------


def test_sin_dias_de_atraso_se_excluye_solo_en_modo_por_segmento() -> None:
    productos = [producto(1, None), producto(2, 5)]

    por_segmento = previa(productos, POR_SEGMENTO)
    global_ = previa(productos, GLOBAL)

    [exclusion] = por_segmento.exclusiones_sin_campana
    assert (exclusion.fila, exclusion.codigo) == (1, CodigoWhatsmkt.SIN_DIAS_ATRASO)
    assert exclusion.pagare == f"{1:018d}"
    assert [c.archivo.productos for c in por_segmento.campanas] == [1]
    # En modo global no aplica: el producto sale en el archivo.
    assert global_.total_exclusiones == 0
    assert global_.campanas[0].archivo.productos == 2


def test_sin_dias_de_atraso_y_otra_exclusion_reporta_la_del_catalogo_una_sola_vez() -> None:
    # Sin telefono Y sin dias: un solo codigo por producto, el del catalogo (RF-WM-15).
    resultado = previa([producto(1, None, telefono=None), producto(2, 5)], POR_SEGMENTO)

    assert [e.codigo for e in resultado.exclusiones_sin_campana] == [CodigoWhatsmkt.SIN_TELEFONO]


def test_las_exclusiones_van_en_el_orden_de_las_filas() -> None:
    productos = [
        producto(1, None),
        producto(2, 5, telefono=None),
        producto(3, None),
        producto(4, 5),
    ]

    resultado = previa(productos, POR_SEGMENTO)

    assert [e.fila for e in resultado.exclusiones_sin_campana] == [1, 3]
    assert [e.fila for e in resultado.campanas[0].exclusiones] == [2]


# --- Problemas --------------------------------------------------------------------------------


def test_sin_supervisores_es_un_problema_y_la_previa_igual_se_arma() -> None:
    resultado = previa([producto(1)], supervisores=())

    assert codigos(resultado.problemas) == [CodigoWhatsmkt.SIN_SUPERVISORES]
    assert isinstance(resultado.problemas[0].detalle, str)
    [campana] = resultado.campanas
    assert (campana.archivo.supervisores, campana.archivo.productos) == (0, 1)


def test_sin_productos_despues_de_las_exclusiones_es_un_problema() -> None:
    resultado = previa([producto(1, telefono=None), producto(2, titular=None)])

    assert resultado.campanas == ()
    assert codigos(resultado.problemas) == [CodigoWhatsmkt.SIN_PRODUCTOS]
    assert resultado.total_exclusiones == 2
    assert len(resultado.exclusiones_sin_campana) == 2


def test_una_seleccion_vacia_es_sin_productos() -> None:
    resultado = previa([])

    assert resultado.campanas == ()
    assert codigos(resultado.problemas) == [CodigoWhatsmkt.SIN_PRODUCTOS]


def test_sin_supervisores_y_sin_productos_se_informan_los_dos() -> None:
    resultado = previa([producto(1, telefono=None)], supervisores=())

    assert codigos(resultado.problemas) == [
        CodigoWhatsmkt.SIN_SUPERVISORES,
        CodigoWhatsmkt.SIN_PRODUCTOS,
    ]


def test_una_definicion_que_no_es_de_whatsmkt_es_un_problema_y_no_arma_nada() -> None:
    for plataforma in (None, "mowa_mes"):
        resultado = previa([producto(1)], plataforma=plataforma)

        assert resultado.campanas == ()
        assert codigos(resultado.problemas) == [CodigoWhatsmkt.DEFINICION_NO_WHATSMKT]


def test_una_definicion_o_version_que_no_existe_lanza_su_error() -> None:
    servicio = servicio_de_previa([producto(1)], definicion())
    seleccion = SeleccionCampana(fecha_corte=CORTE, fecha_envio=CORTE)

    with pytest.raises(DefinicionNoEncontrada):
        servicio.previsualizar(PeticionPrevia(seleccion, 99, None, GLOBAL))
    with pytest.raises(VersionNoEncontrada):
        servicio.previsualizar(PeticionPrevia(seleccion, DEFINICION_ID, 7, GLOBAL))


# --- fecha_envio tal como llega ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("dias", "dias_extra", "segmento"),
    [
        (0, 0, "preventivo"),  # 0 -> preventivo
        (0, 1, "tramo_2"),  # 1 -> tramo_2
        (7, 1, "tramo_2"),  # 8 -> tramo_2
        (7, 2, "mayores_2"),  # 9 -> mayores_2
        (-1, 1, "preventivo"),  # 0
        (-1, 2, "tramo_2"),  # 1
    ],
)
def test_la_fecha_de_envio_cambia_el_segmento_en_los_bordes(dias, dias_extra, segmento) -> None:
    envio = date(2026, 11, 2 + dias_extra)

    resultado = previa([producto(1, dias)], POR_SEGMENTO, fecha_envio=envio)

    assert [c.segmento.clave for c in resultado.campanas] == [segmento]


def test_la_fecha_de_envio_se_usa_tal_como_llega_aunque_no_sea_dia_de_envio() -> None:
    # shortcut de B4a: sin validar contra RF-70 (lunes a sabado). B4b la valida; hoy se usa asi.
    domingo = date(2026, 11, 8)
    assert domingo.weekday() == 6

    resultado = previa([producto(1, 3)], POR_SEGMENTO, fecha_envio=domingo)

    assert resultado.fecha_envio == domingo
    assert [c.segmento.clave for c in resultado.campanas] == ["mayores_2"]  # 3 + 6 dias = 9
