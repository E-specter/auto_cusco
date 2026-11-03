"""Los informes y el ciclo de vida de las campanas de WhatsMKT contra PostgreSQL real (T-WM-B6).

La corre `architec` con `-ConBase`. Cubre lo que los dobles no ven: la ida y vuelta de la
migracion, el reemplazo atomico del informe, el borrado en cascada (y lo que NO se borra), el
borrado del lote al eliminar la ultima campana, y el estado y los pendientes de la lista.
Telefonos 900000xxx; los del informe, 51900000xxx.
"""

import os
from datetime import datetime

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import DataError, IntegrityError

from app.core.entities.whatsmkt import CodigoWhatsmkt, TipoEnvio
from app.core.entities.whatsmkt_campana import EstadoCampana
from app.core.entities.whatsmkt_informe import InformeWhatsmkt, ReporteNuevo
from app.core.services.plataformas.whatsmkt.archivo_contactos import ExclusionContacto
from tests.test_whatsmkt_campanas_postgres import PREFIJO, Entorno, _alembic

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

REVISION_ANTERIOR = "e8a2c6f1b937"
TABLAS = ("whatsmkt_reporte", "whatsmkt_reporte_fila")
HUELLA = "a" * 64


@pytest.fixture
def entorno():
    e = Entorno()
    try:
        yield e
    finally:
        e.limpiar()


def informe(*numeros: str, total: int | None = None) -> ReporteNuevo:
    return ReporteNuevo(
        "informe.xlsx",
        HUELLA,
        InformeWhatsmkt(
            fecha_informada=datetime(2026, 10, 30).date(),
            total_informado=len(numeros) if total is None else total,
            campana="CUZCO_Vencida (sintetica)",
            tipo_envio="CAMPAÑA DE IMAGEN + TEXTO",
            numeros=numeros,
        ),
    )


def contar(entorno: Entorno, tabla: str, donde: str = "TRUE", **parametros) -> int:
    return entorno.contar(tabla, donde, **parametros)


def con_exclusiones(entorno: Entorno, nombre: str, **cambios):
    return entorno.campana(
        nombre=PREFIJO + nombre,
        exclusiones=(
            ExclusionContacto(4, f"{4:018d}", CodigoWhatsmkt.SIN_TELEFONO, "Sin telefono"),
        ),
        **cambios,
    )


# --- El informe -------------------------------------------------------------------------------


def test_el_informe_se_guarda_y_se_lee_igual_con_sus_numeros_en_orden_y_repetidos(entorno) -> None:
    [campana] = entorno.crear().campanas
    nuevo = informe("51900000003", "51900000001", "51900000003")

    guardado = entorno.repo.reemplazar_reporte(campana.id, nuevo)
    leido = entorno.repo.obtener_reporte(campana.id)

    assert leido == guardado
    assert leido.informe == nuevo.informe
    assert leido.informe.numeros == ("51900000003", "51900000001", "51900000003")
    assert (leido.archivo_nombre, leido.huella) == ("informe.xlsx", HUELLA)
    assert entorno.repo.obtener_reporte(2_000_000_000) is None


def test_un_informe_sin_fecha_ni_total_se_guarda_con_nulos(entorno) -> None:
    [campana] = entorno.crear().campanas
    sin_nada = ReporteNuevo(
        "informe.xlsx",
        HUELLA,
        InformeWhatsmkt(None, None, None, None, ("51900000001",)),
    )

    leido = entorno.repo.reemplazar_reporte(campana.id, sin_nada)

    assert (leido.informe.fecha_informada, leido.informe.total_informado) == (None, None)
    assert (leido.informe.campana, leido.informe.tipo_envio) == (None, None)


def test_reemplazar_deja_un_solo_informe_y_borra_las_filas_del_anterior(entorno) -> None:
    [campana] = entorno.crear().campanas
    primero = entorno.repo.reemplazar_reporte(campana.id, informe("51900000001", "51900000002"))

    segundo = entorno.repo.reemplazar_reporte(campana.id, informe("51900000009"))

    assert segundo.id != primero.id
    assert contar(entorno, "whatsmkt_reporte", "campana_id = :c", c=campana.id) == 1
    assert contar(entorno, "whatsmkt_reporte_fila", "reporte_id = :r", r=primero.id) == 0
    assert entorno.repo.obtener_reporte(campana.id).informe.numeros == ("51900000009",)


def test_si_el_reemplazo_falla_a_la_mitad_queda_el_informe_anterior_intacto(entorno) -> None:
    [campana] = entorno.crear().campanas
    entorno.repo.reemplazar_reporte(campana.id, informe("51900000001", "51900000002"))

    with pytest.raises(IntegrityError):  # un numero que no es de digitos viola su CHECK
        entorno.repo.reemplazar_reporte(campana.id, informe("51900000009", "no-es-un-numero"))

    vigente = entorno.repo.obtener_reporte(campana.id)
    assert vigente.informe.numeros == ("51900000001", "51900000002")
    assert contar(entorno, "whatsmkt_reporte", "campana_id = :c", c=campana.id) == 1


def test_la_base_rechaza_un_segundo_informe_para_la_misma_campana(entorno) -> None:
    [campana] = entorno.crear().campanas
    entorno.repo.reemplazar_reporte(campana.id, informe("51900000001"))

    with pytest.raises(IntegrityError), entorno.engine.begin() as cx:
        cx.execute(
            text(
                "INSERT INTO whatsmkt_reporte (campana_id, archivo_nombre, huella) "
                "VALUES (:c, 'otro.xlsx', :h)"
            ),
            {"c": campana.id, "h": HUELLA},
        )


@pytest.mark.parametrize(
    ("huella", "error"),
    [
        ("corta", IntegrityError),  # la rechaza el CHECK de largo
        ("a" * 65, DataError),  # PostgreSQL la corta en el String(64) antes de llegar al CHECK
    ],
    ids=["corta", "larga"],
)
def test_la_huella_debe_medir_64_caracteres(entorno, huella, error) -> None:
    [campana] = entorno.crear().campanas

    with pytest.raises(error), entorno.engine.begin() as cx:
        cx.execute(
            text(
                "INSERT INTO whatsmkt_reporte (campana_id, archivo_nombre, huella) "
                "VALUES (:c, 'x.xlsx', :h)"
            ),
            {"c": campana.id, "h": huella},
        )


def test_las_filas_cargadas_salen_en_orden_con_su_supervision(entorno) -> None:
    [campana] = entorno.crear().campanas

    filas = entorno.repo.filas_cargadas(campana.id)

    assert [(f.numero, f.pagare is None, f.supervision) for f in filas] == [
        ("51900000901", True, True),
        ("51900000902", True, True),
        ("51900000001", False, False),
    ]


# --- Descartar y restaurar --------------------------------------------------------------------


def test_descartar_pone_la_fecha_una_sola_vez_y_restaurar_la_limpia(entorno) -> None:
    [campana] = entorno.crear().campanas

    descartada = entorno.repo.descartar(campana.id)
    de_nuevo = entorno.repo.descartar(campana.id)
    restaurada = entorno.repo.restaurar(campana.id)

    assert descartada.descartada_en is not None
    assert de_nuevo.descartada_en == descartada.descartada_en  # no cambia la fecha
    assert restaurada.descartada_en is None
    assert entorno.repo.descartar(2_000_000_000) is None
    assert entorno.repo.restaurar(2_000_000_000) is None


def test_la_lista_separa_activas_y_descartadas_y_cuenta_los_pendientes(entorno) -> None:
    lote = entorno.crear(*(entorno.campana(nombre=PREFIJO + str(i)) for i in range(3)))
    a, b, c = (x.id for x in lote.campanas)
    entorno.repo.reemplazar_reporte(a, informe("51900000001"))
    entorno.repo.descartar(c)  # descartada sin informe: no es un pendiente

    activas = entorno.repo.listar(100, 0, lote_id=lote.lote_id)
    descartadas = entorno.repo.listar(
        100, 0, lote_id=lote.lote_id, estado=EstadoCampana.DESCARTADAS
    )

    assert sorted(x.id for x in activas.campanas) == [a, b]
    assert {x.id: x.con_informe for x in activas.campanas} == {a: True, b: False}
    assert [x.id for x in descartadas.campanas] == [c] and descartadas.total == 1
    # Los contadores son de toda la base: por lo menos lo nuestro.
    assert activas.total_activas >= 2 and activas.total_descartadas >= 1
    assert activas.total_pendientes >= 1


def test_obtener_trae_si_tiene_informe(entorno) -> None:
    [campana] = entorno.crear().campanas
    assert entorno.repo.obtener(campana.id).con_informe is False

    entorno.repo.reemplazar_reporte(campana.id, informe("51900000001"))

    assert entorno.repo.obtener(campana.id).con_informe is True


# --- Eliminar ---------------------------------------------------------------------------------


def test_una_campana_activa_no_se_elimina(entorno) -> None:
    [campana] = entorno.crear().campanas

    assert entorno.repo.eliminar_descartada(campana.id) is False
    assert entorno.repo.eliminar_descartada(2_000_000_000) is False
    assert entorno.repo.obtener(campana.id) is not None


def test_eliminar_borra_la_campana_con_todo_lo_suyo_y_no_toca_lo_de_otra(entorno) -> None:
    lote = entorno.crear(
        con_exclusiones(entorno, "borrar"),
        con_exclusiones(entorno, "queda"),
        sin_campana=[ExclusionContacto(9, None, CodigoWhatsmkt.SIN_DIAS_ATRASO, "Sin dias")],
    )
    borrar, queda = lote.campanas
    for c in (borrar, queda):
        entorno.repo.reemplazar_reporte(c.id, informe("51900000001", "51900000002"))
    entorno.repo.descartar(borrar.id)

    assert entorno.repo.eliminar_descartada(borrar.id) is True

    for tabla in ("whatsmkt_archivo", "whatsmkt_fila_cargada", "whatsmkt_reporte"):
        assert contar(entorno, tabla, "campana_id = :c", c=borrar.id) == 0, tabla
    assert contar(entorno, "whatsmkt_exclusion", "campana_id = :c", c=borrar.id) == 0
    assert (
        contar(
            entorno,
            "whatsmkt_reporte_fila",
            "reporte_id IN (SELECT id FROM whatsmkt_reporte WHERE campana_id = :c)",
            c=queda.id,
        )
        == 2
    )
    # Lo de la hermana y lo del lote siguen: el lote tiene otra campana.
    assert entorno.repo.obtener(queda.id) is not None
    assert contar(entorno, "whatsmkt_archivo", "campana_id = :c", c=queda.id) == 1
    assert contar(entorno, "whatsmkt_fila_cargada", "campana_id = :c", c=queda.id) == 3
    assert contar(entorno, "whatsmkt_exclusion", "campana_id = :c", c=queda.id) == 1
    assert contar(entorno, "whatsmkt_lote", "id = :l", l=lote.lote_id) == 1
    assert (
        contar(entorno, "whatsmkt_exclusion", "lote_id = :l AND campana_id IS NULL", l=lote.lote_id)
        == 1
    )


def test_eliminar_no_borra_los_adjuntos_ni_las_versiones_del_mensaje_ni_la_definicion(
    entorno,
) -> None:
    lote = entorno.crear(
        entorno.campana(tipo_envio=TipoEnvio.ARCHIVO, adjunto_id=entorno.adjunto.id)
    )
    [campana] = lote.campanas
    entorno.repo.descartar(campana.id)

    assert entorno.repo.eliminar_descartada(campana.id) is True

    assert contar(entorno, "whatsmkt_adjunto", "id = :a", a=entorno.adjunto.id) == 1
    assert contar(entorno, "texto_guardado_version", "texto_id = :t", t=entorno.texto_id) == 1
    assert (
        contar(entorno, "definicion_carga_version", "definicion_id = :d", d=entorno.definicion_id)
        == 1
    )


def test_eliminar_la_ultima_campana_del_lote_borra_el_lote_y_sus_exclusiones_de_fuera(
    entorno,
) -> None:
    lote = entorno.crear(
        con_exclusiones(entorno, "u1"),
        con_exclusiones(entorno, "u2"),
        sin_campana=[
            ExclusionContacto(f, None, CodigoWhatsmkt.SIN_DIAS_ATRASO, "Sin dias") for f in (8, 9)
        ],
    )
    otro = entorno.crear(
        con_exclusiones(entorno, "otro"),
        sin_campana=[ExclusionContacto(7, None, CodigoWhatsmkt.SIN_DIAS_ATRASO, "Sin dias")],
    )
    uno, dos = lote.campanas

    entorno.repo.descartar(uno.id)
    entorno.repo.eliminar_descartada(uno.id)
    assert contar(entorno, "whatsmkt_lote", "id = :l", l=lote.lote_id) == 1  # queda `dos`

    entorno.repo.descartar(dos.id)
    entorno.repo.eliminar_descartada(dos.id)

    assert contar(entorno, "whatsmkt_lote", "id = :l", l=lote.lote_id) == 0
    assert contar(entorno, "whatsmkt_exclusion", "lote_id = :l", l=lote.lote_id) == 0
    # El otro lote queda entero.
    assert contar(entorno, "whatsmkt_lote", "id = :l", l=otro.lote_id) == 1
    assert contar(entorno, "whatsmkt_exclusion", "lote_id = :l", l=otro.lote_id) == 2


# --- La ida y vuelta --------------------------------------------------------------------------


def test_la_migracion_va_y_vuelve(entorno) -> None:
    engine = entorno.engine
    entorno.limpiar()  # no hay filas que bajar con la migracion
    try:
        command.downgrade(_alembic(), REVISION_ANTERIOR)
        assert not set(TABLAS) & set(inspect(engine).get_table_names())

        command.upgrade(_alembic(), "head")
        assert set(TABLAS) <= set(inspect(engine).get_table_names())
    finally:
        command.upgrade(_alembic(), "head")
