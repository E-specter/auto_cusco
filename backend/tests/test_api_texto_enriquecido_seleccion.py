"""La muestra «primeros N de una seleccion» de la previsualizacion (B4b, RF-47). Solo lectura.

Lo simulado: la consulta a la cartera (con el mismo `limite` y `desplazamiento` que la real) y el
servicio de selecciones guardadas.
"""

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.cartera import obtener_servicio_cartera
from app.api.selecciones import obtener_servicio_selecciones
from app.core.entities.cartera import ConsultaInvalida, PaginaCartera, SinVersionVigente
from app.core.entities.selecciones import (
    DatosSeleccion,
    SeleccionGuardada,
    SeleccionNoEncontrada,
    SeleccionRevisada,
)
from app.main import app

CORTE = "2026-09-10"
AHORA = datetime(2099, 1, 1)


def _producto(i: int) -> dict:
    return {
        "pagare": f"{i:018d}",
        "titular": f"TITULAR/SINTETICO,{i}",
        "dias_atraso": 10 * i,
        "fecha_vencimiento_cuota": date(2026, 9, 18),
        "telefono": f"9{i:08d}",
    }


class CarteraFalsa:
    def __init__(self, total: int = 8, error: Exception | None = None) -> None:
        self.total = total
        self.error = error
        self.llamadas: list[dict] = []

    def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento=0):
        if self.error is not None:
            raise self.error
        self.llamadas.append(
            {
                "fecha_corte": fecha_corte,
                "filtros": list(filtros),
                "orden": orden,
                "limite": limite,
                "desplazamiento": desplazamiento,
            }
        )
        filas = tuple(
            _producto(i)
            for i in range(1 + desplazamiento, min(self.total, desplazamiento + limite) + 1)
        )
        return PaginaCartera(
            total=self.total, filas=filas, limite=limite, desplazamiento=desplazamiento
        )


class SeleccionesFalsas:
    def __init__(self) -> None:
        self.guardadas = {
            7: DatosSeleccion(
                nombre="preventiva",
                filtros=("dias_atraso:entre:0|30",),
                orden="-saldo_capital_pendiente",
                cantidad=900,
            )
        }

    def obtener(self, seleccion_id: int) -> SeleccionRevisada:
        if seleccion_id not in self.guardadas:
            raise SeleccionNoEncontrada(seleccion_id)
        guardada = SeleccionGuardada(seleccion_id, self.guardadas[seleccion_id], AHORA, AHORA)
        return SeleccionRevisada(guardada, ())


@pytest.fixture
def cliente():
    cartera = CarteraFalsa()
    app.dependency_overrides[obtener_servicio_cartera] = lambda: cartera
    app.dependency_overrides[obtener_servicio_selecciones] = lambda: SeleccionesFalsas()
    try:
        yield TestClient(app), cartera
    finally:
        app.dependency_overrides.clear()


EXPRESION = {
    "nodos": [
        {
            "tipo": "variable",
            "nombre": "titular",
            "funciones": [{"nombre": "ultimos", "args": [1]}],
        },
        {"tipo": "texto", "valor": " "},
        {"tipo": "variable", "nombre": "dias_atraso", "funciones": []},
    ]
}


def _previsualizar(client, **muestra) -> dict:
    respuesta = client.post(
        "/texto-enriquecido/previsualizacion",
        json={"contexto": "cartera", "expresion": EXPRESION, "muestra": muestra},
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _textos(cuerpo: dict) -> list[str]:
    return [f["columnas"][0]["texto"] for f in cuerpo["filas"]]


def test_los_primeros_n_de_la_seleccion_con_el_total_disponible(cliente) -> None:
    client, _ = cliente

    cuerpo = _previsualizar(client, tipo="primeros_de_seleccion", fecha_corte=CORTE, cantidad=3)

    assert _textos(cuerpo) == ["1 10", "2 20", "3 30"]
    assert [f["numero"] for f in cuerpo["filas"]] == [1, 2, 3]
    assert cuerpo["disponibles"] == 8
    assert cuerpo["problemas"] == []


def test_cada_fila_trae_el_pagare_y_la_fecha_de_corte_del_producto_que_representa(
    cliente,
) -> None:
    client, _ = cliente

    cuerpo = _previsualizar(client, tipo="primeros_de_seleccion", fecha_corte=CORTE, cantidad=3)

    # El editor fija como muestra un producto real de la fila elegida (por su pagare y su corte).
    assert [(f["pagare"], f["fecha_corte"]) for f in cuerpo["filas"]] == [
        (f"{i:018d}", CORTE) for i in (1, 2, 3)
    ]


def test_una_seleccion_guardada_tambien_trae_el_pagare_y_la_fecha_de_corte(cliente) -> None:
    client, _ = cliente

    cuerpo = _previsualizar(
        client, tipo="primeros_de_seleccion", fecha_corte=CORTE, seleccion_id=7, cantidad=2
    )

    assert [(f["pagare"], f["fecha_corte"]) for f in cuerpo["filas"]] == [
        (f"{i:018d}", CORTE) for i in (1, 2)
    ]


def test_por_defecto_son_cinco(cliente) -> None:
    client, cartera = cliente

    cuerpo = _previsualizar(client, tipo="primeros_de_seleccion", fecha_corte=CORTE)

    assert len(cuerpo["filas"]) == 5
    assert cartera.llamadas[0]["limite"] == 5


def test_si_hay_menos_productos_que_n_salen_los_que_hay(cliente) -> None:
    client, cartera = cliente
    cartera.total = 2

    cuerpo = _previsualizar(client, tipo="primeros_de_seleccion", fecha_corte=CORTE, cantidad=5)

    assert len(cuerpo["filas"]) == 2
    assert cuerpo["disponibles"] == 2


def test_una_seleccion_sin_productos_da_cero_filas_y_no_falla(cliente) -> None:
    client, cartera = cliente
    cartera.total = 0

    cuerpo = _previsualizar(client, tipo="primeros_de_seleccion", fecha_corte=CORTE)

    assert (cuerpo["filas"], cuerpo["disponibles"]) == ([], 0)


def test_los_filtros_y_el_orden_se_piden_con_la_sintaxis_de_cartera(cliente) -> None:
    client, cartera = cliente

    _previsualizar(
        client,
        tipo="primeros_de_seleccion",
        fecha_corte=CORTE,
        filtros=["telefono:no_vacio", "dias_atraso:entre:0|30"],
        orden="-saldo_capital_pendiente",
        cantidad=2,
    )

    llamada = cartera.llamadas[0]
    assert llamada["fecha_corte"] == date(2026, 9, 10)
    assert [(f.campo, f.operador.value) for f in llamada["filtros"]] == [
        ("telefono", "no_vacio"),
        ("dias_atraso", "entre"),
    ]
    assert (llamada["orden"].campo, llamada["orden"].descendente) == (
        "saldo_capital_pendiente",
        True,
    )
    assert llamada["limite"] == 2


def test_una_seleccion_guardada_aporta_sus_filtros_y_su_orden_pero_no_su_cantidad(cliente) -> None:
    client, cartera = cliente

    cuerpo = _previsualizar(
        client, tipo="primeros_de_seleccion", fecha_corte=CORTE, seleccion_id=7, cantidad=2
    )

    llamada = cartera.llamadas[0]
    assert [f.campo for f in llamada["filtros"]] == ["dias_atraso"]
    assert llamada["orden"].descendente is True
    assert llamada["limite"] == 2  # la cantidad de la seleccion (900) no cuenta: es una muestra
    assert len(cuerpo["filas"]) == 2


def test_una_seleccion_guardada_inexistente_es_404_con_su_codigo(cliente) -> None:
    client, cartera = cliente

    respuesta = client.post(
        "/texto-enriquecido/previsualizacion",
        json={
            "contexto": "cartera",
            "expresion": EXPRESION,
            "muestra": {"tipo": "primeros_de_seleccion", "fecha_corte": CORTE, "seleccion_id": 99},
        },
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "seleccion_no_encontrada"
    assert cartera.llamadas == []


@pytest.mark.parametrize(
    "muestra",
    [
        {"filtros": ["malo"]},  # sin operador
        {"filtros": ["campo_que_no_existe:igual:1"]},
        {"orden": "-campo_que_no_existe"},
    ],
)
def test_un_filtro_o_un_orden_que_no_valen_son_400_sin_codigo(cliente, muestra) -> None:
    client, _ = cliente
    cartera_real = None
    from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService

    class Repositorio:
        def hay_version_vigente(self, fecha_corte):
            return True

        def consultar(self, *args):
            raise AssertionError("no debe llegar a la base")

    cartera_real = ConsultaCarteraService(Repositorio())
    app.dependency_overrides[obtener_servicio_cartera] = lambda: cartera_real

    respuesta = client.post(
        "/texto-enriquecido/previsualizacion",
        json={
            "contexto": "cartera",
            "expresion": EXPRESION,
            "muestra": {"tipo": "primeros_de_seleccion", "fecha_corte": CORTE, **muestra},
        },
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["codigo"] is None and respuesta.json()["detail"]


def test_una_fecha_sin_version_vigente_es_404_con_su_codigo(cliente) -> None:
    client, cartera = cliente
    cartera.error = SinVersionVigente(date(2026, 9, 10))

    respuesta = client.post(
        "/texto-enriquecido/previsualizacion",
        json={
            "contexto": "cartera",
            "expresion": EXPRESION,
            "muestra": {"tipo": "primeros_de_seleccion", "fecha_corte": CORTE},
        },
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "sin_version_vigente"


def test_una_consulta_invalida_de_la_cartera_es_400(cliente) -> None:
    client, cartera = cliente
    cartera.error = ConsultaInvalida("El campo x no existe")

    respuesta = client.post(
        "/texto-enriquecido/previsualizacion",
        json={
            "contexto": "cartera",
            "expresion": EXPRESION,
            "muestra": {"tipo": "primeros_de_seleccion", "fecha_corte": CORTE},
        },
    )

    assert respuesta.status_code == 400
    assert respuesta.json() == {"detail": "El campo x no existe", "codigo": None}


@pytest.mark.parametrize(
    "muestra",
    [
        {"tipo": "primeros_de_seleccion"},  # sin fecha de corte
        {"tipo": "primeros_de_seleccion", "fecha_corte": CORTE, "cantidad": 6},
        {"tipo": "primeros_de_seleccion", "fecha_corte": CORTE, "cantidad": 0},
        {
            "tipo": "primeros_de_seleccion",
            "fecha_corte": CORTE,
            "seleccion_id": 7,
            "filtros": ["telefono:no_vacio"],
        },
        {
            "tipo": "primeros_de_seleccion",
            "fecha_corte": CORTE,
            "seleccion_id": 7,
            "orden": "titular",
        },
    ],
)
def test_la_muestra_mal_pedida_es_422_y_no_toca_la_cartera(cliente, muestra) -> None:
    client, cartera = cliente

    respuesta = client.post(
        "/texto-enriquecido/previsualizacion",
        json={"contexto": "cartera", "expresion": EXPRESION, "muestra": muestra},
    )

    assert respuesta.status_code == 422
    assert cartera.llamadas == []


def test_el_recorrido_pide_paginas_con_el_mismo_desplazamiento_que_la_carga(cliente) -> None:
    """La muestra usa `SeleccionPaginada`: con N menor que el total, una sola pagina de N."""
    client, cartera = cliente

    _previsualizar(client, tipo="primeros_de_seleccion", fecha_corte=CORTE, cantidad=4)

    assert [(c["limite"], c["desplazamiento"]) for c in cartera.llamadas] == [(4, 0)]


def test_con_el_contexto_del_speech_cada_producto_pasa_por_su_registro(cliente) -> None:
    client, _ = cliente
    expresion = {
        "nodos": [
            {"tipo": "variable", "nombre": "titular", "funciones": []},
            {"tipo": "texto", "valor": " "},
            {"tipo": "variable", "nombre": "dias_atraso_ajustados", "funciones": []},
        ]
    }

    respuesta = client.post(
        "/texto-enriquecido/previsualizacion",
        json={
            "contexto": "mowa_mes.speech",
            "expresion": expresion,
            "muestra": {
                "tipo": "primeros_de_seleccion",
                "fecha_corte": CORTE,
                "fecha_envio": CORTE,
                "cantidad": 2,
            },
        },
    )

    assert [f["columnas"][0]["texto"] for f in respuesta.json()["filas"]] == [
        "TITULAR/SINTETICO,1 10",
        "TITULAR/SINTETICO,2 20",
    ]


def test_las_otras_muestras_no_traen_disponibles(cliente) -> None:
    client, _ = cliente

    cuerpo = _previsualizar(client, tipo="ejemplo")

    assert cuerpo["disponibles"] is None
