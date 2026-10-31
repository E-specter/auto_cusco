"""Administracion de las versiones de speech contra PostgreSQL (T-MM-C11, M-B2; RF-MM-28 a
RF-MM-30). La corre `architec`.

La misma cadena por HTTP que `test_mowa_mes_speech_v2_postgres.py`, con su fixture `cliente` (sabana
2099, supervisores, configuracion y limpieza de las versiones con el prefijo de prueba, y la marca
de uso del Speech original que se restituye). Lo que se comprueba, contra el SQL real:

- renombrar respeta la unicidad de `nombre_normalizado` (sin distinguir mayusculas ni espacios en
  los extremos) y no cambia el contenido ni la huella, tampoco en una usada;
- deshabilitar y habilitar, y que repetirlo no pisa la fecha;
- los tres motivos para no eliminar (original, usada, habilitada) y el DELETE de la que se puede;
- una deshabilitada en `armar`: la previsualizacion la marca como error y la creacion se rechaza;
- la columna `deshabilitada_en`, como la deja la migracion.

La ida y vuelta de la migracion (`alembic downgrade -1` y `alembic upgrade head`) la corre architec
con `-ConBase`; el SQL se comprueba sin base en `test_mowa_mes_speech_administracion_migracion.py`.
Datos sinteticos; numeros 900000xxx.
"""

import os

import pytest
from sqlalchemy import func, select, text

from app.adapters.persistence.modelos import MowaMesCampana, MowaMesSpeechVersion
from app.adapters.persistence.repositorio_mowa_mes_postgres import (
    RepositorioMowaMesPostgres,
    datos_de_fila,
)
from app.core.services.plataformas.mowa_mes.campana import huella_de
from tests import test_mowa_mes_campanas_postgres as base
from tests.test_mowa_mes_campanas_postgres import PREFIJO, _crear, _previsualizar
from tests.test_mowa_mes_speech_v2_postgres import CUERPO_V2, _crear_v2

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

cliente = base.cliente
_SPEECH = MowaMesSpeechVersion.__table__
_CAMPANA = MowaMesCampana.__table__


def _nueva(client, nombre: str) -> dict:
    respuesta = _crear_v2(client, nombre)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _patch(client, speech_id: int, **cuerpo):
    return client.patch(f"/mowa-mes/speech/{speech_id}", json=cuerpo)


def _fila(engine, speech_id: int):
    with engine.connect() as cx:
        return cx.execute(select(_SPEECH).where(_SPEECH.c.id == speech_id)).one_or_none()


def _usar_en_una_campana(client, speech_id: int) -> dict:
    previa = _previsualizar(client, speech_id=speech_id)
    creada = _crear(client, previa["speech"]["huella"], speech_id=speech_id)
    assert creada.status_code == 201, creada.text
    return creada.json()


# --- Renombrar (RF-MM-28) ------------------------------------------------------------------------


def test_renombrar_no_cambia_el_contenido_ni_la_huella(cliente) -> None:
    client, engine = cliente
    version = _nueva(client, "para renombrar")
    antes = _fila(engine, version["id"])

    renombrada = _patch(client, version["id"], nombre=f"{PREFIJO}renombrada  ")
    despues = _fila(engine, version["id"])

    assert renombrada.status_code == 200
    assert renombrada.json()["nombre"] == f"{PREFIJO}renombrada"
    assert despues.nombre_normalizado == f"{PREFIJO}renombrada".strip().casefold()
    assert despues.expresiones == antes.expresiones and despues.formato == antes.formato
    assert despues.partes == antes.partes
    assert _huella(client, version["id"]) == _huella_de_fila(antes)


def _huella(client, speech_id: int) -> str:
    previa = _previsualizar(client, speech_id=speech_id)
    return previa["speech"]["huella"]


def _huella_de_fila(fila) -> str:
    return huella_de(datos_de_fila("", fila.partes, fila.formato, fila.expresiones))


def test_una_usada_y_el_original_se_renombran_y_la_usada_conserva_su_uso(cliente) -> None:
    client, engine = cliente
    version = _nueva(client, "usada para renombrar")
    _usar_en_una_campana(client, version["id"])
    uso_antes = _fila(engine, version["id"]).usada_en
    original = next(v for v in client.get("/mowa-mes/speech").json() if v["original"])

    usada = _patch(client, version["id"], nombre=f"{PREFIJO}usada renombrada")
    try:
        renombrado = _patch(client, original["id"], nombre=f"{PREFIJO}original renombrado")
        assert renombrado.status_code == 200 and renombrado.json()["original"] is True
    finally:
        _patch(client, original["id"], nombre=original["nombre"])  # vuelve a su nombre

    assert usada.status_code == 200 and usada.json()["usada"] is True
    assert _fila(engine, version["id"]).usada_en == uso_antes


def test_un_nombre_repetido_es_409_sin_distinguir_mayusculas_ni_espacios(cliente) -> None:
    client, _ = cliente
    _nueva(client, "Alfa unica")
    otra = _nueva(client, "Beta unica")

    repetido = _patch(client, otra["id"], nombre=f"  {PREFIJO.upper()}ALFA UNICA ")

    assert repetido.status_code == 409
    assert client.get(f"/mowa-mes/speech/{otra['id']}").json()["nombre"] == f"{PREFIJO}Beta unica"


def test_renombrar_a_su_propio_nombre_con_otras_mayusculas_se_permite(cliente) -> None:
    client, _ = cliente
    version = _nueva(client, "Mismo nombre")

    mayusculas = _patch(client, version["id"], nombre=f"{PREFIJO.upper()}MISMO NOMBRE")

    assert mayusculas.status_code == 200


# --- Deshabilitar y habilitar (RF-MM-29) ---------------------------------------------------------


def test_deshabilitar_habilitar_y_repetirlo(cliente) -> None:
    client, engine = cliente
    version = _nueva(client, "para deshabilitar")

    primera = _patch(client, version["id"], habilitada=False).json()
    segunda = _patch(client, version["id"], habilitada=False).json()
    habilitada = _patch(client, version["id"], habilitada=True).json()

    assert primera["deshabilitada_en"] is not None
    assert segunda["deshabilitada_en"] == primera["deshabilitada_en"]  # no se pisa
    assert habilitada["deshabilitada_en"] is None
    assert _fila(engine, version["id"]).deshabilitada_en is None


def test_la_lista_trae_la_marca_y_si_se_puede_eliminar(cliente) -> None:
    client, _ = cliente
    habilitada = _nueva(client, "habilitada")
    deshabilitada = _nueva(client, "deshabilitada")
    _patch(client, deshabilitada["id"], habilitada=False)

    lista = {v["id"]: v for v in client.get("/mowa-mes/speech").json()}

    assert (lista[habilitada["id"]]["eliminable"], lista[habilitada["id"]]["deshabilitada_en"]) == (
        False,
        None,
    )
    assert lista[deshabilitada["id"]]["eliminable"] is True
    assert lista[deshabilitada["id"]]["motivo_no_eliminable"] is None
    original = next(v for v in lista.values() if v["original"])
    assert (original["eliminable"], original["motivo_no_eliminable"]) == (False, "original")


# --- Eliminar (RF-MM-30) -------------------------------------------------------------------------


def test_se_elimina_una_deshabilitada_sin_uso(cliente) -> None:
    client, engine = cliente
    version = _nueva(client, "para eliminar")
    _patch(client, version["id"], habilitada=False)

    eliminada = client.delete(f"/mowa-mes/speech/{version['id']}")

    assert eliminada.status_code == 204
    assert _fila(engine, version["id"]) is None
    assert client.get(f"/mowa-mes/speech/{version['id']}").status_code == 404


def test_eliminar_una_habilitada_es_409_y_no_borra(cliente) -> None:
    client, engine = cliente
    version = _nueva(client, "habilitada no se elimina")

    rechazada = client.delete(f"/mowa-mes/speech/{version['id']}")

    assert rechazada.status_code == 409
    assert rechazada.json()["codigo"] == "speech_no_deshabilitado"
    assert _fila(engine, version["id"]) is not None


def test_eliminar_una_usada_es_409_aunque_este_deshabilitada(cliente) -> None:
    client, engine = cliente
    version = _nueva(client, "usada no se elimina")
    campana = _usar_en_una_campana(client, version["id"])
    _patch(client, version["id"], habilitada=False)

    rechazada = client.delete(f"/mowa-mes/speech/{version['id']}")

    assert rechazada.status_code == 409 and rechazada.json()["codigo"] == "speech_usado"
    assert _fila(engine, version["id"]) is not None
    assert client.get(f"/mowa-mes/campanas/{campana['id']}").json()["speech"]["id"] == version["id"]


def test_eliminar_el_original_es_409_aunque_este_deshabilitado(cliente) -> None:
    client, engine = cliente
    original_id = next(v["id"] for v in client.get("/mowa-mes/speech").json() if v["original"])
    try:
        _patch(client, original_id, habilitada=False)

        rechazada = client.delete(f"/mowa-mes/speech/{original_id}")

        assert rechazada.status_code == 409 and rechazada.json()["codigo"] == "speech_original"
        assert _fila(engine, original_id) is not None
    finally:
        _patch(client, original_id, habilitada=True)  # el original vuelve a quedar habilitado


def test_el_delete_de_una_que_se_habilito_en_el_medio_no_borra(cliente) -> None:
    client, engine = cliente
    version = _nueva(client, "habilitada en el medio")
    _patch(client, version["id"], habilitada=False)
    _patch(client, version["id"], habilitada=True)

    # El DELETE lleva las condiciones: aunque el servicio la hubiera leido deshabilitada, no borra.
    assert RepositorioMowaMesPostgres(engine).eliminar_speech(version["id"]) is False
    assert _fila(engine, version["id"]) is not None


def test_eliminar_no_toca_a_la_version_en_la_que_se_basaba(cliente) -> None:
    client, engine = cliente
    base_ = _nueva(client, "version base")
    derivada = client.post(
        "/mowa-mes/speech",
        json={
            "nombre": f"{PREFIJO}derivada",
            "expresiones": CUERPO_V2,
            "basada_en_id": base_["id"],
        },
    ).json()
    _patch(client, base_["id"], habilitada=False)

    assert client.delete(f"/mowa-mes/speech/{base_['id']}").status_code == 204
    assert client.get(f"/mowa-mes/speech/{derivada['id']}").json()["basada_en_id"] is None


# --- Una deshabilitada en armar (RF-MM-29) ----------------------------------------


def test_la_previsualizacion_y_la_creacion_rechazan_una_deshabilitada(cliente) -> None:
    client, engine = cliente
    version = _nueva(client, "deshabilitada en la campana")
    previa = _previsualizar(client, speech_id=version["id"])
    _patch(client, version["id"], habilitada=False)

    deshabilitada = client.post(
        "/mowa-mes/campanas/previsualizacion", json={**base.CUERPO, "speech_id": version["id"]}
    ).json()
    creada = _crear(client, previa["speech"]["huella"], speech_id=version["id"])

    assert deshabilitada["puede_crear"] is False
    assert [e["codigo"] for e in deshabilitada["errores"]] == ["speech_deshabilitado"]
    assert creada.status_code == 400
    with engine.connect() as cx:
        campanas = cx.execute(
            select(func.count())
            .select_from(_CAMPANA)
            .where(_CAMPANA.c.speech_version_id == version["id"])
        ).scalar_one()
    assert campanas == 0
    assert _fila(engine, version["id"]).usada_en is None  # no la marco como usada


def test_habilitada_de_nuevo_sirve_para_la_campana(cliente) -> None:
    client, _ = cliente
    version = _nueva(client, "habilitada de nuevo")
    _patch(client, version["id"], habilitada=False)
    _patch(client, version["id"], habilitada=True)

    previa = _previsualizar(client, speech_id=version["id"])

    assert previa["puede_crear"] is True and previa["errores"] == []


# --- La columna ----------------------------------------


def test_la_columna_es_timestamptz_nula_y_las_versiones_nuevas_nacen_habilitadas(cliente) -> None:
    client, engine = cliente
    version = _nueva(client, "columna")

    with engine.connect() as cx:
        columna = cx.execute(
            text(
                "SELECT data_type, is_nullable FROM information_schema.columns "
                "WHERE table_name = 'mowa_mes_speech_version' AND column_name = 'deshabilitada_en'"
            )
        ).one()

    assert tuple(columna) == ("timestamp with time zone", "YES")
    assert _fila(engine, version["id"]).deshabilitada_en is None
    assert version["deshabilitada_en"] is None
