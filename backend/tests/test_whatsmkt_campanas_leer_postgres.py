"""Leer las campanas de WhatsMKT contra PostgreSQL real (T-WM-B4b1, parte 3; RF-WM-36 y 40).

La corre `architec` con `-ConBase`. Cubre lo que el doble en memoria no ve: el orden y los filtros
de la consulta, el limite entre dos meses, el total contra la pagina y las dos listas de
exclusiones (las de la campana y las que quedaron fuera del lote). Los filtros por lote dejan los
resultados independientes de lo que ya hubiera en la base. Telefonos 900000xxx.
"""

import os
from datetime import date

import pytest

from app.core.entities.whatsmkt import CodigoWhatsmkt, ModoCampana
from app.core.services.plataformas.whatsmkt.archivo_contactos import ExclusionContacto
from tests.test_whatsmkt_campanas_postgres import PREFIJO, XLSX, Entorno

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

REMOTO = date(2099, 3, 1)  # un mes que ninguna otra prueba usa


@pytest.fixture
def entorno():
    e = Entorno()
    try:
        yield e
    finally:
        e.limpiar()


def con_exclusiones(entorno: Entorno, nombre: str, filas: list[int], **cambios):
    return entorno.campana(
        nombre=PREFIJO + nombre,
        exclusiones=tuple(
            ExclusionContacto(f, f"{f:018d}", CodigoWhatsmkt.SIN_TELEFONO, "Sin telefono")
            for f in filas
        ),
        **cambios,
    )


# --- La lista ---------------------------------------------------------------------------------


def test_las_mas_recientes_primero_y_dentro_de_un_lote_el_id_mayor(entorno) -> None:
    primero = entorno.crear(entorno.campana(nombre=PREFIJO + "a"))
    segundo = entorno.crear(
        entorno.campana(nombre=PREFIJO + "b"),
        entorno.campana(nombre=PREFIJO + "c"),
    )
    ids_primero = [c.id for c in primero.campanas]
    ids_segundo = [c.id for c in segundo.campanas]

    pagina = entorno.repo.listar(1000, 0)

    propias = [c.id for c in pagina.campanas if c.id in {*ids_primero, *ids_segundo}]
    assert propias == [*sorted(ids_segundo, reverse=True), *ids_primero]  # lote 2 antes que lote 1


def test_el_total_cuenta_todas_las_del_filtro_y_la_pagina_solo_las_pedidas(entorno) -> None:
    lote = entorno.crear(*(entorno.campana(nombre=PREFIJO + str(i)) for i in range(3)))
    ids = sorted((c.id for c in lote.campanas), reverse=True)

    pagina = entorno.repo.listar(2, 1, lote_id=lote.lote_id)

    assert pagina.total == 3
    assert [c.id for c in pagina.campanas] == ids[1:]
    assert entorno.repo.listar(2, 5, lote_id=lote.lote_id).campanas == ()
    assert entorno.repo.listar(10, 0, lote_id=2_000_000_000).total == 0


def test_la_fila_de_la_lista_conserva_lo_que_se_guardo(entorno) -> None:
    lote = entorno.crear(
        entorno.campana(nombre=PREFIJO + "x", segmento="tramo_2", segmento_etiqueta="Tramo 2")
    )

    [fila] = entorno.repo.listar(10, 0, lote_id=lote.lote_id).campanas

    assert fila == lote.campanas[0]
    assert (fila.segmento, fila.segmento_etiqueta, fila.descartada_en) == (
        "tramo_2",
        "Tramo 2",
        None,
    )
    assert fila.horarios == lote.campanas[0].horarios and fila.creado_en is not None


def test_el_filtro_por_mes_es_el_de_la_fecha_de_envio_y_respeta_el_limite_entre_meses(
    entorno,
) -> None:
    fechas = [date(2099, 2, 28), date(2099, 3, 1), date(2099, 3, 31), date(2099, 4, 1)]
    lote = entorno.crear(
        *(
            entorno.campana(
                nombre=PREFIJO + f.isoformat(), fecha_envio=f, fecha_corte=date(2099, 2, 1)
            )
            for f in fechas
        )
    )
    por_fecha = {c.fecha_envio: c.id for c in lote.campanas}

    marzo = entorno.repo.listar(100, 0, lote_id=lote.lote_id, mes=REMOTO)

    assert marzo.total == 2
    assert {c.id for c in marzo.campanas} == {
        por_fecha[date(2099, 3, 1)],
        por_fecha[date(2099, 3, 31)],
    }
    # Con cualquier dia del mes se pide el mismo mes.
    assert entorno.repo.listar(100, 0, lote_id=lote.lote_id, mes=date(2099, 3, 17)).total == 2
    assert entorno.repo.listar(100, 0, lote_id=lote.lote_id, mes=date(2099, 5, 1)).total == 0
    assert entorno.repo.listar(100, 0, lote_id=lote.lote_id).total == 4


# --- El detalle -------------------------------------------------------------------------------


def test_obtener_trae_la_campana_con_su_archivo_y_el_modo_del_lote(entorno) -> None:
    lote = entorno.crear(entorno.campana(nombre=PREFIJO + "d"))

    campana = entorno.repo.obtener(lote.campanas[0].id)

    assert campana == lote.campanas[0]
    assert (campana.archivo_nombre, campana.archivo_tamano) == (PREFIJO + "uno.xlsx", len(XLSX))
    assert entorno.repo.modo_del_lote(lote.lote_id) is ModoCampana.GLOBAL
    assert entorno.repo.obtener(2_000_000_000) is None


def test_las_exclusiones_de_la_campana_salen_por_fila_con_su_total_y_su_pagina(entorno) -> None:
    lote = entorno.crear(
        con_exclusiones(entorno, "e1", [6, 4, 5]),
        con_exclusiones(entorno, "e2", [9]),
    )
    uno, dos = lote.campanas

    todas = entorno.repo.listar_exclusiones(lote.lote_id, uno.id, 100, 0)
    segunda = entorno.repo.listar_exclusiones(lote.lote_id, uno.id, 1, 1)

    assert todas.total == 3 and [e.fila for e in todas.exclusiones] == [4, 5, 6]
    assert segunda.total == 3 and [e.fila for e in segunda.exclusiones] == [5]
    primera = todas.exclusiones[0]
    assert (primera.pagare, primera.codigo, primera.detalle) == (
        f"{4:018d}",
        CodigoWhatsmkt.SIN_TELEFONO,
        "Sin telefono",
    )
    assert [
        e.fila for e in entorno.repo.listar_exclusiones(lote.lote_id, dos.id, 100, 0).exclusiones
    ] == [9]


def test_las_exclusiones_fuera_del_lote_son_las_de_campana_nula_y_solo_de_ese_lote(entorno) -> None:
    fuera = [
        ExclusionContacto(f, f"{f:018d}", CodigoWhatsmkt.SIN_DIAS_ATRASO, "Sin dias")
        for f in (8, 7, 9)
    ]
    lote = entorno.crear(con_exclusiones(entorno, "f1", [4]), sin_campana=fuera)
    otro = entorno.crear(
        con_exclusiones(entorno, "f2", [4]),
        sin_campana=[ExclusionContacto(1, None, CodigoWhatsmkt.SIN_DIAS_ATRASO, "Sin dias")],
    )

    de_este = entorno.repo.listar_exclusiones(lote.lote_id, None, 100, 0)
    pagina = entorno.repo.listar_exclusiones(lote.lote_id, None, 2, 1)
    de_otro = entorno.repo.listar_exclusiones(otro.lote_id, None, 100, 0)

    assert de_este.total == 3 and [e.fila for e in de_este.exclusiones] == [7, 8, 9]
    assert pagina.total == 3 and [e.fila for e in pagina.exclusiones] == [8, 9]
    assert de_este.exclusiones[0].codigo is CodigoWhatsmkt.SIN_DIAS_ATRASO
    assert de_otro.total == 1 and de_otro.exclusiones[0].pagare is None
    # Las de la campana no incluyen las de fuera, y al reves.
    propias = entorno.repo.listar_exclusiones(lote.lote_id, lote.campanas[0].id, 100, 0)
    assert [e.fila for e in propias.exclusiones] == [4]


def test_en_un_lote_sin_exclusiones_fuera_el_total_es_cero(entorno) -> None:
    lote = entorno.crear(con_exclusiones(entorno, "g", [4]))

    fuera = entorno.repo.listar_exclusiones(lote.lote_id, None, 100, 0)

    assert (fuera.total, fuera.exclusiones) == (0, ())
