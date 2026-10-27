"""La fecha de envio en la API (RF-55, T-MTE-B13): `/archivos-carga` y `/texto-enriquecido`.

«Hoy» es siempre el de Lima con un reloj fijo: nada depende de la hora de la maquina.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.cartera import obtener_servicio_cartera
from app.core.entities.cartera import PaginaCartera
from app.core.services import fecha_envio as modulo
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.main import app

CORTE = "2026-09-10"
HOY_EN_LIMA = date(2026, 9, 15)


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    """03:00 UTC del 16 son las 22:00 del 15 en Lima: en UTC ya es «manana»."""
    monkeypatch.setattr(modulo, "ahora_en_lima", lambda: datetime(2026, 9, 16, 3, 0, tzinfo=UTC))


class Cartera:
    catalogo = CatalogoCartera()  # lo piden quienes parsean filtros o arman columnas

    def __init__(self) -> None:
        self.llamadas = 0

    def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento=0):
        self.llamadas += 1
        filas = tuple(
            {
                "pagare": f"{i:018d}",
                "titular": f"TITULAR/SINTETICO,{i}",
                "dias_atraso": dias,
                "telefono": f"9{i:08d}",
                "saldo_capital_pendiente": Decimal("100"),
                "fecha_vencimiento_cuota": date(2026, 9, 1),
            }
            for i, dias in enumerate((0, 5, 28))
            if i >= desplazamiento
        )
        return PaginaCartera(
            total=3, filas=filas[:limite], limite=limite, desplazamiento=desplazamiento
        )


@pytest.fixture
def cliente():
    cartera = Cartera()
    app.dependency_overrides[obtener_servicio_cartera] = lambda: cartera
    try:
        yield TestClient(app), cartera
    finally:
        app.dependency_overrides.clear()


DEFINICION = {
    "nombre": "Con envio",
    "campos": [
        {"nombre": "ajustados", "plantilla": "[@dias_atraso_ajustados]", "tipo": "numero"},
        {
            "nombre": "envio",
            "plantilla": "[@fecha_envio]",
            "tipo": "fecha",
            "formato_fecha": "%Y-%m-%d",
        },
    ],
}


def _carga(**extra) -> dict:
    return {"fecha_corte": CORTE, "definicion": DEFINICION, "cantidad": 3, **extra}


# --- /archivos-carga -------------------------------------------------------------------------


def test_sin_fecha_de_envio_la_previsualizacion_usa_hoy_en_lima_y_lo_dice(cliente) -> None:
    client, _ = cliente

    cuerpo = client.post("/archivos-carga/previsualizacion", json=_carga()).json()

    assert cuerpo["fecha_envio"] == "2026-09-15"  # no el 16, que es el UTC
    assert [fila["ajustados"] for fila in cuerpo["filas"]] == [5, 10, 33]
    assert {fila["envio"] for fila in cuerpo["filas"]} == {"2026-09-15"}


def test_la_fecha_pedida_manda_sobre_hoy(cliente) -> None:
    client, _ = cliente

    cuerpo = client.post(
        "/archivos-carga/previsualizacion", json=_carga(fecha_envio="2026-09-20")
    ).json()

    assert cuerpo["fecha_envio"] == "2026-09-20"
    assert [fila["ajustados"] for fila in cuerpo["filas"]] == [10, 15, 38]


def test_con_la_fecha_de_corte_no_se_suma_nada(cliente) -> None:
    client, _ = cliente

    cuerpo = client.post("/archivos-carga/previsualizacion", json=_carga(fecha_envio=CORTE)).json()

    assert [fila["ajustados"] for fila in cuerpo["filas"]] == [0, 5, 28]


@pytest.mark.parametrize("ruta", ["/archivos-carga/previsualizacion", "/archivos-carga"])
def test_una_fecha_anterior_a_la_de_corte_da_400_con_codigo_y_las_dos_fechas(cliente, ruta) -> None:
    client, cartera = cliente

    respuesta = client.post(ruta, json=_carga(fecha_envio="2026-09-09"))

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "fecha_envio_anterior"
    assert (cuerpo["fecha_envio"], cuerpo["fecha_corte"]) == ("2026-09-09", CORTE)
    assert "2026-09-09" in cuerpo["detail"] and CORTE in cuerpo["detail"]
    assert cartera.llamadas == 0  # se rechaza antes de leer la cartera


def test_la_descarga_usa_la_fecha_pedida_para_ajustar_los_dias(cliente) -> None:
    client, _ = cliente

    respuesta = client.post("/archivos-carga", json=_carga(formato="csv", fecha_envio="2026-09-11"))

    assert respuesta.status_code == 200
    assert "x-carga-fecha-envio" not in respuesta.headers  # la fecha viaja en la previsualizacion
    lineas = respuesta.content.decode("utf-8").splitlines()
    assert [linea.split(",")[0] for linea in lineas[1:]] == ["1", "6", "29"]


def test_una_fecha_que_no_es_fecha_da_422(cliente) -> None:
    client, _ = cliente

    assert client.post("/archivos-carga", json=_carga(fecha_envio="ayer")).status_code == 422


def test_otros_400_de_la_carga_no_traen_las_fechas(cliente) -> None:
    client, _ = cliente

    respuesta = client.post("/archivos-carga/previsualizacion", json=_carga(filtros=["x"]))

    assert respuesta.status_code == 400
    assert "fecha_envio" not in respuesta.json() and "fecha_corte" not in respuesta.json()


# --- /texto-enriquecido/previsualizacion -----------------------------------------------------

EXPRESION = {
    "nodos": [
        {"tipo": "variable", "nombre": "titular", "funciones": []},
        {"tipo": "texto", "valor": " "},
        {"tipo": "variable", "nombre": "dias_atraso_ajustados", "funciones": []},
    ]
}


def _texto(contexto: str, muestra: dict, expresion: dict = EXPRESION):
    return TestClient(app).post(
        "/texto-enriquecido/previsualizacion",
        json={"contexto": contexto, "expresion": expresion, "muestra": muestra},
    )


def test_el_speech_se_previsualiza_ajustado_a_hoy_en_lima(cliente) -> None:
    respuesta = _texto(
        "mowa_mes.speech", {"tipo": "primeros_de_seleccion", "fecha_corte": CORTE, "cantidad": 3}
    )

    cuerpo = respuesta.json()
    assert [f["columnas"][0]["texto"] for f in cuerpo["filas"]] == [
        "TITULAR/SINTETICO,0 5",
        "TITULAR/SINTETICO,1 10",
        "TITULAR/SINTETICO,2 33",
    ]
    assert cuerpo["fecha_envio"] == "2026-09-15"


def test_un_producto_real_con_fecha_de_envio_la_usa_y_la_informa(cliente) -> None:
    cuerpo = _texto(
        "cartera",
        {"tipo": "producto_real", "fecha_corte": CORTE, "pagare": "x", "fecha_envio": "2026-09-30"},
    ).json()

    assert cuerpo["filas"][0]["columnas"][0]["texto"] == "TITULAR/SINTETICO,0 20"
    assert cuerpo["fecha_envio"] == "2026-09-30"


def test_la_previsualizacion_del_texto_rechaza_una_fecha_anterior_con_las_dos_fechas(
    cliente,
) -> None:
    _, cartera = cliente

    respuesta = _texto(
        "cartera",
        {"tipo": "producto_real", "fecha_corte": CORTE, "pagare": "x", "fecha_envio": "2026-09-09"},
    )

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "fecha_envio_anterior"
    assert (cuerpo["fecha_envio"], cuerpo["fecha_corte"]) == ("2026-09-09", CORTE)
    assert cartera.llamadas == 0


def test_una_muestra_de_ejemplo_no_tiene_fecha_de_envio(cliente) -> None:
    cuerpo = _texto("cartera", {"tipo": "ejemplo"}).json()

    assert cuerpo["fecha_envio"] is None


def test_una_muestra_de_ejemplo_con_fecha_de_envio_se_rechaza(cliente) -> None:
    respuesta = _texto("cartera", {"tipo": "ejemplo", "fecha_envio": "2026-09-15"})

    assert respuesta.status_code == 422


def test_el_catalogo_de_la_cartera_ofrece_las_variables_y_segmenta_por_los_dias_ajustados(
    cliente,
) -> None:
    cuerpo = TestClient(app).get("/texto-enriquecido/catalogo?contexto=cartera").json()
    contexto = cuerpo["contexto"]

    variables = {v["nombre"]: v for v in contexto["variables"]}
    assert variables["fecha_envio"]["tipo"] == "fecha"
    assert variables["dias_atraso_ajustados"]["tipo"] == "numero"
    assert variables["fecha_envio"]["clave_nombre"] == "textoEnriquecido.variable.fecha_envio"
    assert contexto["variable_dias"] == "dias_atraso_ajustados"


def test_el_speech_de_punta_a_punta_segmenta_por_los_dias_a_hoy_en_lima(cliente) -> None:
    # Diez dias entre el corte y «hoy en Lima» (el 15): 25 dias de atraso son 35, «31 a 60».
    class CarteraDeUnProducto(Cartera):
        def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento=0):
            fila = {"pagare": "P", "titular": "UNO", "dias_atraso": 25}
            return PaginaCartera(total=1, filas=(fila,), limite=limite)

    app.dependency_overrides[obtener_servicio_cartera] = lambda: CarteraDeUnProducto()
    expresion = {
        "nodos": [{"tipo": "variable", "nombre": "dias_atraso_ajustados", "funciones": []}]
    }
    definicion = {
        "columnas": [{"nombre": "a", "orden": 0, "expresion": expresion}],
        "segmentacion": {"criterio": {"tipo": "calculado"}},
    }

    cuerpo = (
        TestClient(app)
        .post(
            "/texto-enriquecido/previsualizacion",
            json={
                "contexto": "mowa_mes.speech",
                "definicion": definicion,
                "muestra": {"tipo": "producto_real", "fecha_corte": "2026-09-05", "pagare": "P"},
            },
        )
        .json()
    )

    [fila] = cuerpo["filas"]
    assert (fila["segmento"], fila["columnas"][0]["texto"]) == ("31_a_60", "35")
    assert cuerpo["fecha_envio"] == "2026-09-15"


def test_una_muestra_de_cartera_sin_fecha_de_envio_informa_hoy_en_lima_y_no_null(cliente) -> None:
    for muestra in (
        {"tipo": "producto_real", "fecha_corte": CORTE, "pagare": "x"},
        {"tipo": "primeros_de_seleccion", "fecha_corte": CORTE},
    ):
        assert _texto("cartera", muestra).json()["fecha_envio"] == "2026-09-15"


# --- Un corte futuro (las sabanas sinteticas de las pruebas @postgres son de 2099) -------------

CORTE_FUTURO = "2099-04-01"


@pytest.mark.parametrize("ruta", ["/archivos-carga", "/archivos-carga/previsualizacion"])
def test_sin_fecha_de_envio_y_un_corte_futuro_es_400_con_las_dos_fechas(cliente, ruta) -> None:
    client, cartera = cliente

    respuesta = client.post(ruta, json=_carga(fecha_corte=CORTE_FUTURO))

    cuerpo = respuesta.json()
    assert respuesta.status_code == 400
    assert cuerpo["codigo"] == "fecha_envio_anterior"
    assert (cuerpo["fecha_envio"], cuerpo["fecha_corte"]) == ("2026-09-15", CORTE_FUTURO)
    assert cartera.llamadas == 0


def test_la_muestra_de_un_corte_futuro_sin_fecha_de_envio_es_400(cliente) -> None:
    respuesta = _texto("cartera", {"tipo": "primeros_de_seleccion", "fecha_corte": CORTE_FUTURO})

    cuerpo = respuesta.json()
    assert respuesta.status_code == 400
    assert (cuerpo["fecha_envio"], cuerpo["fecha_corte"]) == ("2026-09-15", CORTE_FUTURO)


def test_con_la_fecha_de_envio_igual_a_un_corte_futuro_se_genera(cliente) -> None:
    client, _ = cliente

    respuesta = client.post(
        "/archivos-carga/previsualizacion",
        json=_carga(fecha_corte=CORTE_FUTURO, fecha_envio=CORTE_FUTURO),
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["fecha_envio"] == CORTE_FUTURO
