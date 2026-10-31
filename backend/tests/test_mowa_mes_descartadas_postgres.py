"""Campanas descartadas contra PostgreSQL (T-MM-C11, M-B1; RF-MM-31, RF-MM-32 y RF-MM-01). La corre
`architec`.

La misma cadena por HTTP que `test_mowa_mes_campanas_postgres.py`, con su fixture `cliente` (sabana
2099, supervisores, configuracion y limpieza). Lo que se comprueba, contra el SQL real:

- una descartada no suma en `cargados_en_mes`, ni en `costo_del_mes`, ni aparece en `listar`
  (un agregado por prueba: `_ACTIVA` es un solo predicado, pero cada consulta debe usarlo);
- `listar_descartadas` filtra por mes de gestion y trae los meses con descartadas;
- eliminar borra en cascada archivos, filas cargadas, exclusiones, reportes y filas de reporte, y
  la version de speech conserva su `usada_en`;
- eliminar una activa da 409 y no borra nada; importar a una descartada da 409 y no guarda nada;
- la columna `descartada_en`, como la deja la migracion.

La ida y vuelta de la migracion (`alembic downgrade -1` y `alembic upgrade head`) la corre architec
con `-ConBase`; el SQL se comprueba sin base en `test_mowa_mes_descartadas_migracion.py`.
Datos sinteticos; numeros 900000xxx.
"""

import os
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text

from app.adapters.persistence.modelos import (
    MowaMesArchivo,
    MowaMesCampana,
    MowaMesExclusion,
    MowaMesFilaCargada,
    MowaMesReporte,
    MowaMesReporteFila,
    MowaMesSpeechVersion,
)
from app.adapters.persistence.repositorio_campanas_mowa_mes_postgres import (
    RepositorioCampanasMowaMesPostgres,
)
from tests import test_mowa_mes_campanas_postgres as base

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

cliente = base.cliente

_CAMPANA = MowaMesCampana.__table__
_SPEECH = MowaMesSpeechVersion.__table__
_HIJAS = {
    "archivo": MowaMesArchivo.__table__,
    "fila cargada": MowaMesFilaCargada.__table__,
    "exclusion": MowaMesExclusion.__table__,
    "reporte": MowaMesReporte.__table__,
}
_REPORTE_FILA = MowaMesReporteFila.__table__
MES = date(2099, 6, 1)


def _crear_campana(client, **extra) -> dict:
    previa = base._previsualizar(client, **extra)
    creada = base._crear(client, previa["speech"]["huella"], **extra)
    assert creada.status_code == 201, creada.text
    return creada.json()


def _descartar(client, campana_id: int) -> dict:
    respuesta = client.post(f"/mowa-mes/campanas/{campana_id}/descartar")
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _importar_reporte(client, campana_id: int):
    descarga = client.get(f"/mowa-mes/campanas/{campana_id}/archivos/1")
    filas = base._filas_xlsx(descarga.content)
    contenido = base._reporte([(base.MES_IDS[0], fila) for fila in filas])
    return client.post(
        f"/mowa-mes/campanas/{campana_id}/reportes", files={"archivo": ("reporte.xlsx", contenido)}
    )


def _conteos(engine, campana_id: int) -> dict[str, int]:
    with engine.connect() as cx:
        conteos = {
            nombre: cx.execute(
                select(func.count()).select_from(tabla).where(tabla.c.campana_id == campana_id)
            ).scalar_one()
            for nombre, tabla in _HIJAS.items()
        }
        conteos["fila de reporte"] = cx.execute(
            select(func.count())
            .select_from(_REPORTE_FILA)
            .join(_HIJAS["reporte"], _HIJAS["reporte"].c.id == _REPORTE_FILA.c.reporte_id)
            .where(_HIJAS["reporte"].c.campana_id == campana_id)
        ).scalar_one()
    return conteos


# --- Un agregado por prueba ---------------------------------------------------


def test_una_descartada_no_suma_en_cargados_en_mes(cliente) -> None:
    client, engine = cliente
    repositorio = RepositorioCampanasMowaMesPostgres(engine)
    campana = _crear_campana(client)
    activa = repositorio.cargados_en_mes(MES)

    _descartar(client, campana["id"])

    assert activa == campana["total_cargados"] == 11
    assert repositorio.cargados_en_mes(MES) == 0
    limite = client.get("/mowa-mes/limite-mensual", params={"mes": "2099-06"}).json()
    assert limite["cargados_mes"] == 0


def test_una_descartada_no_suma_en_el_costo_del_mes(cliente) -> None:
    client, engine = cliente
    repositorio = RepositorioCampanasMowaMesPostgres(engine)
    campana = _crear_campana(client)
    activa = repositorio.costo_del_mes(MES)

    _descartar(client, campana["id"])
    descartada = repositorio.costo_del_mes(MES)

    assert Decimal(campana["costo_estimado"]) > 0
    assert activa.costo == Decimal(campana["costo_estimado"])
    assert (descartada.costo, descartada.campanas_sin_tarifa) == (Decimal(0), 0)
    limite = client.get("/mowa-mes/limite-mensual", params={"mes": "2099-06"}).json()
    assert limite["costo_mes"] == "0.0000"


def test_una_descartada_no_aparece_en_listar_pero_se_puede_ver(cliente) -> None:
    client, engine = cliente
    repositorio = RepositorioCampanasMowaMesPostgres(engine)
    campana = _crear_campana(client)
    antes = repositorio.listar(500, 0)

    _descartar(client, campana["id"])
    despues = repositorio.listar(500, 0)

    assert campana["id"] in [c.id for c in antes.campanas]
    assert campana["id"] not in [c.id for c in despues.campanas]
    assert despues.total == antes.total - 1
    vista = client.get(f"/mowa-mes/campanas/{campana['id']}").json()
    assert vista["descartada_en"] is not None  # RF-MM-32: ver una descartada se permite
    assert client.get(f"/mowa-mes/campanas/{campana['id']}/archivos/1").status_code == 200


def test_restaurar_la_devuelve_a_los_tres_agregados(cliente) -> None:
    client, engine = cliente
    repositorio = RepositorioCampanasMowaMesPostgres(engine)
    campana = _crear_campana(client)
    _descartar(client, campana["id"])

    restaurada = client.post(f"/mowa-mes/campanas/{campana['id']}/restaurar").json()

    assert restaurada["descartada_en"] is None
    assert repositorio.cargados_en_mes(MES) == 11
    assert repositorio.costo_del_mes(MES).costo == Decimal(campana["costo_estimado"])
    assert campana["id"] in [c.id for c in repositorio.listar(500, 0).campanas]


# --- Pendientes de reporte (RF-MM-33) -----------------------------------------------


def test_total_pendientes_cuenta_solo_las_activas_sin_reporte(cliente) -> None:
    client, engine = cliente
    repositorio = RepositorioCampanasMowaMesPostgres(engine)
    base_inicial = repositorio.listar(500, 0).total_pendientes
    con_reporte = _crear_campana(client)
    sin_reporte = _crear_campana(client)
    descartada = _crear_campana(client)
    assert _importar_reporte(client, con_reporte["id"]).status_code == 201

    pagina = repositorio.listar(500, 0)

    # Dos nuevas sin reporte (la que lo tiene ya no cuenta); ninguna descartada aun.
    assert pagina.total_pendientes == base_inicial + 2
    _descartar(client, descartada["id"])
    assert repositorio.listar(500, 0).total_pendientes == base_inicial + 1  # la descartada no
    por_id = {c.id: c.pendiente_reporte for c in pagina.campanas}
    assert por_id[con_reporte["id"]] is False and por_id[sin_reporte["id"]] is True


def test_el_total_de_pendientes_es_el_de_todas_las_activas_y_no_el_de_la_pagina(cliente) -> None:
    client, engine = cliente
    repositorio = RepositorioCampanasMowaMesPostgres(engine)
    for _ in range(3):
        _crear_campana(client)

    una = repositorio.listar(1, 0)
    todas = repositorio.listar(500, 0)

    assert len(una.campanas) == 1
    assert una.total_pendientes == todas.total_pendientes >= 3
    assert una.total == todas.total


def test_pendiente_reporte_de_la_fila_y_del_total_salen_de_la_misma_expresion(cliente) -> None:
    client, engine = cliente
    repositorio = RepositorioCampanasMowaMesPostgres(engine)
    campana = _crear_campana(client)

    antes = repositorio.obtener(campana["id"])
    _importar_reporte(client, campana["id"])
    despues = repositorio.obtener(campana["id"])

    assert (antes.pendiente_reporte, despues.pendiente_reporte) == (True, False)
    assert antes.enviados_conciliados is None and despues.enviados_conciliados is not None
    assert client.get(f"/mowa-mes/campanas/{campana['id']}").json()["pendiente_reporte"] is False


# --- Descartadas por mes ----------------------------------------------------------


def test_listar_descartadas_filtra_por_mes_y_trae_los_meses(cliente) -> None:
    client, _ = cliente
    junio = _crear_campana(client)
    julio = _crear_campana(client, envios=["2099-07-02T09:00:00"])
    activa = _crear_campana(client)
    _descartar(client, junio["id"])
    _descartar(client, julio["id"])

    todas = client.get("/mowa-mes/campanas/descartadas").json()
    de_julio = client.get("/mowa-mes/campanas/descartadas", params={"mes": "2099-07"}).json()

    ids_de_la_prueba = {junio["id"], julio["id"], activa["id"]}
    assert [c["id"] for c in de_julio["campanas"]] == [julio["id"]]
    assert {c["id"] for c in todas["campanas"]} & ids_de_la_prueba == {junio["id"], julio["id"]}
    assert todas["meses"].index("2099-07") < todas["meses"].index("2099-06")  # mas reciente primero
    assert de_julio["meses"] == todas["meses"] and "2099-07" in de_julio["meses"]
    assert todas["total_descartadas"] >= 2
    assert activa["id"] not in [c["id"] for c in todas["campanas"]]


# --- Eliminar ----------------------------------------------------------------------


def test_eliminar_borra_en_cascada_y_el_speech_conserva_su_uso(cliente) -> None:
    client, engine = cliente
    campana = _crear_campana(client)
    assert _importar_reporte(client, campana["id"]).status_code == 201
    antes = _conteos(engine, campana["id"])
    with engine.connect() as cx:
        speech_antes = cx.execute(
            select(_SPEECH.c.id, _SPEECH.c.usada_en).where(_SPEECH.c.id == campana["speech"]["id"])
        ).one()
    _descartar(client, campana["id"])

    eliminada = client.delete(f"/mowa-mes/campanas/{campana['id']}")

    assert all(cantidad > 0 for cantidad in antes.values()), antes  # habia de todo que borrar
    assert eliminada.status_code == 204
    assert _conteos(engine, campana["id"]) == dict.fromkeys(antes, 0)
    with engine.connect() as cx:
        existe = cx.execute(
            select(func.count()).select_from(_CAMPANA).where(_CAMPANA.c.id == campana["id"])
        ).scalar_one()
        speech_despues = cx.execute(
            select(_SPEECH.c.id, _SPEECH.c.usada_en).where(_SPEECH.c.id == speech_antes.id)
        ).one()
    assert existe == 0
    assert speech_despues.usada_en == speech_antes.usada_en is not None  # RF-MM-32
    assert client.get(f"/mowa-mes/campanas/{campana['id']}").status_code == 404


def test_eliminar_libera_los_id_de_mes_del_reporte(cliente) -> None:
    client, _ = cliente
    campana = _crear_campana(client)
    assert _importar_reporte(client, campana["id"]).status_code == 201
    _descartar(client, campana["id"])
    client.delete(f"/mowa-mes/campanas/{campana['id']}")
    otra = _crear_campana(client)

    assert _importar_reporte(client, otra["id"]).status_code == 201  # sin 409 de id ya importado


def test_eliminar_una_activa_es_409_y_no_borra_nada(cliente) -> None:
    client, engine = cliente
    campana = _crear_campana(client)
    antes = _conteos(engine, campana["id"])

    rechazada = client.delete(f"/mowa-mes/campanas/{campana['id']}")

    assert rechazada.status_code == 409 and rechazada.json()["codigo"] == "campana_no_descartada"
    assert _conteos(engine, campana["id"]) == antes
    assert client.get(f"/mowa-mes/campanas/{campana['id']}").status_code == 200


def test_eliminar_una_que_se_restauro_en_el_medio_no_borra(cliente) -> None:
    client, engine = cliente
    repositorio = RepositorioCampanasMowaMesPostgres(engine)
    campana = _crear_campana(client)
    _descartar(client, campana["id"])
    client.post(f"/mowa-mes/campanas/{campana['id']}/restaurar")

    # El DELETE lleva el predicado: aunque el servicio hubiera leido "descartada" antes, no borra.
    assert repositorio.eliminar(campana["id"]) is False
    assert client.get(f"/mowa-mes/campanas/{campana['id']}").status_code == 200


# --- Importar el reporte a una descartada ------------------------------------------


def test_importar_a_una_descartada_es_409_y_no_guarda_nada(cliente) -> None:
    client, engine = cliente
    campana = _crear_campana(client)
    _descartar(client, campana["id"])

    rechazado = _importar_reporte(client, campana["id"])

    assert rechazado.status_code == 409
    assert rechazado.json()["codigo"] == "campana_descartada"
    assert "restaurala primero" in rechazado.json()["detail"]
    assert _conteos(engine, campana["id"])["reporte"] == 0
    restaurada = client.post(f"/mowa-mes/campanas/{campana['id']}/restaurar")
    assert restaurada.status_code == 200
    assert _importar_reporte(client, campana["id"]).status_code == 201


# --- La columna ---------------------------------------------------------------------


def test_la_columna_es_timestamptz_nula_y_las_campanas_nuevas_nacen_activas(cliente) -> None:
    client, engine = cliente
    campana = _crear_campana(client)

    with engine.connect() as cx:
        columna = cx.execute(
            text(
                "SELECT data_type, is_nullable FROM information_schema.columns "
                "WHERE table_name = 'mowa_mes_campana' AND column_name = 'descartada_en'"
            )
        ).one()
        descartada = cx.execute(
            select(_CAMPANA.c.descartada_en).where(_CAMPANA.c.id == campana["id"])
        ).scalar_one()

    assert tuple(columna) == ("timestamp with time zone", "YES")
    assert descartada is None and campana["descartada_en"] is None
