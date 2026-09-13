"""Pruebas de los endpoints de selecciones guardadas, con un doble del caso de uso."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.selecciones import obtener_servicio_selecciones
from app.core.entities.selecciones import (
    DatosSeleccion,
    NombreDeSeleccionRepetido,
    ParteSeleccion,
    ProblemaSeleccion,
    SeleccionGuardada,
    SeleccionInvalida,
    SeleccionNoEncontrada,
    SeleccionRevisada,
)
from app.core.services.seleccion_cartera.servicio import CANTIDAD_MAXIMA
from app.main import app

MOMENTO = datetime(2026, 9, 12, 10, 0, tzinfo=UTC)

CUERPO = {
    "nombre": "Preventiva con telefono",
    "filtros": ["segmento_financiero:igual:1. Preventiva", "telefono:no_vacio"],
    "orden": "-saldo_capital_pendiente",
    "cantidad": 500,
    "indicadores": ["cuota promedio:promedio:monto_cuota"],
}

PROBLEMA = ProblemaSeleccion(
    ParteSeleccion.FILTRO, "campo_retirado:igual:x", "El campo 'campo_retirado' no existe"
)


def _revisada(datos: DatosSeleccion, *problemas: ProblemaSeleccion) -> SeleccionRevisada:
    return SeleccionRevisada(SeleccionGuardada(7, datos, MOMENTO, MOMENTO), tuple(problemas))


class ServicioFalso:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.recibido = None

    def _quizas_fallar(self) -> None:
        if self.error is not None:
            raise self.error

    def listar(self):
        return [_revisada(DatosSeleccion(nombre="rota", filtros=(PROBLEMA.expresion,)), PROBLEMA)]

    def obtener(self, seleccion_id):
        self._quizas_fallar()
        self.recibido = seleccion_id
        return _revisada(DatosSeleccion(nombre="una"))

    def revisar(self, datos):
        self.recibido = datos
        return (PROBLEMA,)

    def crear(self, datos):
        self._quizas_fallar()
        self.recibido = datos
        return _revisada(datos)

    def actualizar(self, seleccion_id, datos):
        self._quizas_fallar()
        self.recibido = (seleccion_id, datos)
        return _revisada(datos)

    def eliminar(self, seleccion_id):
        self._quizas_fallar()
        self.recibido = seleccion_id


@pytest.fixture
def cliente():
    servicio = ServicioFalso()
    app.dependency_overrides[obtener_servicio_selecciones] = lambda: servicio
    try:
        yield TestClient(app), servicio
    finally:
        app.dependency_overrides.clear()


def _con_error(error: Exception) -> TestClient:
    app.dependency_overrides[obtener_servicio_selecciones] = lambda: ServicioFalso(error)
    return TestClient(app)


def test_crear_una_seleccion(cliente) -> None:
    client, servicio = cliente

    respuesta = client.post("/selecciones", json=CUERPO)

    cuerpo = respuesta.json()
    assert respuesta.status_code == 201
    assert servicio.recibido == DatosSeleccion(
        nombre=CUERPO["nombre"],
        filtros=tuple(CUERPO["filtros"]),
        orden=CUERPO["orden"],
        cantidad=500,
        indicadores=tuple(CUERPO["indicadores"]),
    )
    assert (cuerpo["id"], cuerpo["nombre"], cuerpo["aplicable"]) == (7, CUERPO["nombre"], True)
    assert cuerpo["filtros"] == CUERPO["filtros"]
    assert cuerpo["problemas"] == []


def test_la_lista_marca_lo_que_ya_no_aplica(cliente) -> None:
    client, _ = cliente

    (seleccion,) = client.get("/selecciones").json()

    assert seleccion["aplicable"] is False
    assert seleccion["problemas"] == [
        {"parte": "filtro", "expresion": PROBLEMA.expresion, "detalle": PROBLEMA.detalle}
    ]


def test_revisar_sin_guardar(cliente) -> None:
    client, servicio = cliente

    cuerpo = client.post("/selecciones/revision", json=CUERPO).json()

    assert cuerpo["aplicable"] is False
    assert cuerpo["problemas"][0]["parte"] == "filtro"
    assert servicio.recibido.nombre == CUERPO["nombre"]


def test_actualizar_y_eliminar(cliente) -> None:
    client, servicio = cliente

    actualizada = client.put("/selecciones/7", json={**CUERPO, "cantidad": 100})
    assert actualizada.status_code == 200
    assert servicio.recibido[0] == 7
    assert actualizada.json()["cantidad"] == 100

    eliminada = client.delete("/selecciones/7")
    assert eliminada.status_code == 204
    assert eliminada.content == b""


@pytest.mark.parametrize(
    ("error", "metodo", "ruta", "estado"),
    [
        (SeleccionInvalida((PROBLEMA,)), "post", "/selecciones", 400),
        (NombreDeSeleccionRepetido("Preventiva"), "post", "/selecciones", 409),
        (SeleccionInvalida((PROBLEMA,)), "put", "/selecciones/7", 400),
        (SeleccionNoEncontrada(7), "put", "/selecciones/7", 404),
        (NombreDeSeleccionRepetido("Preventiva"), "put", "/selecciones/7", 409),
        (SeleccionNoEncontrada(7), "get", "/selecciones/7", 404),
        (SeleccionNoEncontrada(7), "delete", "/selecciones/7", 404),
    ],
)
def test_errores_del_caso_de_uso(error, metodo, ruta, estado) -> None:
    client = _con_error(error)
    try:
        cuerpo = {"json": CUERPO} if metodo in ("post", "put") else {}
        respuesta = getattr(client, metodo)(ruta, **cuerpo)
    finally:
        app.dependency_overrides.clear()

    assert respuesta.status_code == estado
    assert respuesta.json()["detail"]


def test_una_seleccion_invalida_explica_que_parte_falla(cliente) -> None:
    client = _con_error(SeleccionInvalida((PROBLEMA,)))
    try:
        respuesta = client.post("/selecciones", json=CUERPO)
    finally:
        app.dependency_overrides.clear()

    assert PROBLEMA.expresion in respuesta.json()["detail"]


@pytest.mark.parametrize(
    "cambio",
    [{"nombre": ""}, {"nombre": "x" * 121}, {"cantidad": 0}, {"cantidad": CANTIDAD_MAXIMA + 1}],
)
def test_peticiones_mal_formadas_no_llegan_al_caso_de_uso(cliente, cambio) -> None:
    client, servicio = cliente

    respuesta = client.post("/selecciones", json={**CUERPO, **cambio})

    assert respuesta.status_code == 422
    assert servicio.recibido is None
