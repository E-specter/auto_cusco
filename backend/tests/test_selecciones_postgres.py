"""Selecciones guardadas contra PostgreSQL real, de punta a punta (opcional).

Corre solo con AUTO_CUSCO_DB_TESTS=1 y la base migrada. Los nombres llevan un
prefijo propio y todo lo que se crea se borra al terminar. Los ultimos casos
entran por HTTP sin sustituir ninguna dependencia.
"""

import os
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, insert

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.modelos import Seleccion
from app.adapters.persistence.repositorio_selecciones_postgres import (
    RepositorioSeleccionesPostgres,
    normalizar_nombre,
)
from app.core.entities.selecciones import DatosSeleccion, NombreDeSeleccionRepetido
from app.main import app

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

PREFIJO = "zz prueba automatica "
_SELECCION = Seleccion.__table__

DATOS = DatosSeleccion(
    nombre=f"{PREFIJO}preventiva",
    filtros=("segmento_financiero:igual:1. Preventiva", "dias_atraso:entre:0|30"),
    orden="-saldo_capital_pendiente",
    cantidad=500,
    indicadores=("productos:conteo", "cuota promedio:promedio:monto_cuota"),
)


def _limpiar(engine) -> None:
    prefijo = normalizar_nombre(PREFIJO)
    with engine.begin() as cx:
        cx.execute(delete(_SELECCION).where(_SELECCION.c.nombre_normalizado.startswith(prefijo)))


@pytest.fixture
def repositorio():
    engine = get_engine()
    _limpiar(engine)
    try:
        yield RepositorioSeleccionesPostgres(engine), engine
    finally:
        _limpiar(engine)


@pytest.fixture
def cliente(repositorio):
    """Cliente HTTP sobre la base real: no se sustituye ninguna dependencia."""
    yield TestClient(app)


def _cuerpo(datos: DatosSeleccion = DATOS) -> dict:
    return {
        "nombre": datos.nombre,
        "filtros": list(datos.filtros),
        "orden": datos.orden,
        "cantidad": datos.cantidad,
        "indicadores": list(datos.indicadores),
    }


def test_guardar_y_leer_conserva_cada_parte_en_orden(repositorio) -> None:
    repo, _ = repositorio

    creada = repo.crear(DATOS)
    leida = repo.obtener(creada.id)

    assert leida.datos == DATOS
    assert leida.creado_en.tzinfo is not None
    assert leida.creado_en == leida.actualizado_en


def test_el_nombre_repetido_lo_rechaza_la_base_sin_distinguir_mayusculas(repositorio) -> None:
    repo, _ = repositorio
    repo.crear(DATOS)

    with pytest.raises(NombreDeSeleccionRepetido):
        repo.crear(replace(DATOS, nombre=DATOS.nombre.upper()))


def test_actualizar_registra_la_hora_del_cambio(repositorio) -> None:
    repo, _ = repositorio
    creada = repo.crear(DATOS)

    actualizada = repo.actualizar(creada.id, replace(DATOS, cantidad=100))

    assert actualizada.datos.cantidad == 100
    assert actualizada.creado_en == creada.creado_en
    assert actualizada.actualizado_en > creada.actualizado_en


def test_actualizar_con_el_nombre_de_otra_seleccion_choca(repositorio) -> None:
    repo, _ = repositorio
    repo.crear(DATOS)
    otra = repo.crear(replace(DATOS, nombre=f"{PREFIJO}otra"))

    with pytest.raises(NombreDeSeleccionRepetido):
        repo.actualizar(otra.id, DATOS)


def test_eliminar_y_buscar_una_que_no_existe(repositorio) -> None:
    repo, _ = repositorio
    creada = repo.crear(DATOS)

    assert repo.eliminar(creada.id)
    assert repo.obtener(creada.id) is None
    assert not repo.eliminar(creada.id)
    assert repo.actualizar(creada.id, DATOS) is None


# --- De punta a punta por HTTP ----------------------------------------


def test_ciclo_completo_por_http(cliente) -> None:
    creada = cliente.post("/selecciones", json=_cuerpo())
    assert creada.status_code == 201
    seleccion_id = creada.json()["id"]

    leida = cliente.get(f"/selecciones/{seleccion_id}").json()
    assert (leida["aplicable"], leida["filtros"]) == (True, list(DATOS.filtros))

    actualizada = cliente.put(f"/selecciones/{seleccion_id}", json={**_cuerpo(), "cantidad": 100})
    assert (actualizada.status_code, actualizada.json()["cantidad"]) == (200, 100)
    assert seleccion_id in [s["id"] for s in cliente.get("/selecciones").json()]

    repetida = cliente.post("/selecciones", json={**_cuerpo(), "nombre": DATOS.nombre.upper()})
    assert repetida.status_code == 409

    invalida = cliente.put(
        f"/selecciones/{seleccion_id}", json={**_cuerpo(), "filtros": ["campo_inventado:igual:x"]}
    )
    assert invalida.status_code == 400
    assert "campo_inventado:igual:x" in invalida.json()["detail"]

    assert cliente.delete(f"/selecciones/{seleccion_id}").status_code == 204
    assert cliente.get(f"/selecciones/{seleccion_id}").status_code == 404


def test_una_seleccion_que_perdio_validez_se_devuelve_marcada(cliente, repositorio) -> None:
    _, engine = repositorio
    nombre = f"{PREFIJO}con campo retirado"
    # Se inserta directo en la base: asi quedaria una seleccion guardada antes de que
    # el catalogo retirara un campo.
    with engine.begin() as cx:
        seleccion_id = cx.execute(
            insert(_SELECCION)
            .values(
                nombre=nombre,
                nombre_normalizado=normalizar_nombre(nombre),
                filtros=["campo_retirado:igual:x", "telefono:no_vacio"],
                indicadores=[],
            )
            .returning(_SELECCION.c.id)
        ).scalar_one()

    respuesta = cliente.get(f"/selecciones/{seleccion_id}")

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert cuerpo["aplicable"] is False
    assert [(p["parte"], p["expresion"]) for p in cuerpo["problemas"]] == [
        ("filtro", "campo_retirado:igual:x")
    ]
    assert cuerpo["filtros"] == ["campo_retirado:igual:x", "telefono:no_vacio"]
