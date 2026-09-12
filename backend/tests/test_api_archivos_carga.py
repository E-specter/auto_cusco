"""Pruebas de los endpoints de generacion de archivos de carga (RF-09, RF-13, RF-15).

Van de punta a punta dentro del backend: leen la definicion y los filtros del
cuerpo, generan las filas y escriben el archivo. Lo unico simulado es la
consulta a la cartera.
"""

import io
import json
from datetime import date
from decimal import Decimal

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.api.cartera import obtener_servicio_cartera
from app.core.entities.cartera import PaginaCartera, SinVersionVigente
from app.main import app

FECHA = "2026-09-10"

DEFINICION = {
    "nombre": "SMS preventiva",
    "campos": [
        {"nombre": "anexo", "plantilla": "1010", "tipo": "numero"},
        {"nombre": "numero", "plantilla": "51[@telefono]"},
        {
            "nombre": "deuda",
            "plantilla": "[@saldo_capital_pendiente]",
            "tipo": "financiero",
            "formato_financiero": {"separador_miles": ".", "separador_decimal": ","},
        },
        {
            "nombre": "vence",
            "plantilla": "[@fecha_vencimiento_cuota]",
            "tipo": "fecha",
            "formato_fecha": "%d/%m/%Y",
        },
    ],
}


class ConsultaFalsa:
    def __init__(self, total: int = 2, error: Exception | None = None) -> None:
        self.total = total
        self.error = error
        self.recibido: dict = {}

    def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento):
        if self.error is not None:
            raise self.error
        self.recibido = {
            "fecha_corte": fecha_corte,
            "filtros": list(filtros),
            "orden": orden,
            "limite": limite,
        }
        filas = tuple(
            {
                "pagare": f"{i:018d}",
                "telefono": f"9{i:08d}" if i else None,  # el primero no tiene telefono
                "saldo_capital_pendiente": Decimal("1500.5"),
                "fecha_vencimiento_cuota": date(2026, 9, 18),
            }
            for i in range(desplazamiento, min(desplazamiento + limite, self.total))
        )
        return PaginaCartera(
            total=self.total, filas=filas, limite=limite, desplazamiento=desplazamiento
        )


@pytest.fixture
def cliente():
    consulta = ConsultaFalsa()
    app.dependency_overrides[obtener_servicio_cartera] = lambda: consulta
    try:
        yield TestClient(app), consulta
    finally:
        app.dependency_overrides.clear()


def _peticion(**extra) -> dict:
    return {"fecha_corte": FECHA, "definicion": DEFINICION, "cantidad": 2, **extra}


def test_listar_formatos_dice_que_opciones_admite_cada_uno(cliente) -> None:
    client, _ = cliente

    formatos = {f["formato"]: f for f in client.get("/archivos-carga/formatos").json()}

    assert set(formatos) == {"xlsx", "csv", "json"}
    assert formatos["csv"]["extension"] == "csv"
    assert "delimitador" in formatos["csv"]["opciones"]
    assert "hoja" in formatos["xlsx"]["opciones"]


def test_previsualizacion_devuelve_filas_y_el_total_de_la_seleccion(cliente) -> None:
    client, consulta = cliente

    cuerpo = client.post(
        "/archivos-carga/previsualizacion",
        json=_peticion(filtros=["telefono:no_vacio"], orden="-saldo_capital_pendiente"),
    ).json()

    assert cuerpo["cabeceras"] == ["anexo", "numero", "deuda", "vence"]
    assert cuerpo["filas"][1] == {
        "anexo": 1010,
        "numero": "51900000001",
        "deuda": "1.500,50",
        "vence": "18/09/2026",
    }
    assert cuerpo["filas"][0]["numero"] == "51"  # sin telefono queda el prefijo
    assert cuerpo["nombre_archivo"] == "SMS_preventiva.xlsx"
    assert (cuerpo["disponibles"], cuerpo["generados"], cuerpo["suficiente"]) == (2, 2, True)
    assert consulta.recibido["filtros"][0].campo == "telefono"
    assert consulta.recibido["orden"].descendente


def test_previsualizacion_reporta_los_errores_con_su_fila_y_su_campo(cliente) -> None:
    client, _ = cliente
    definicion = {
        "nombre": "con error",
        "campos": [{"nombre": "roto", "plantilla": "[@telefono]", "tipo": "fecha"}],
    }

    cuerpo = client.post(
        "/archivos-carga/previsualizacion", json=_peticion(definicion=definicion)
    ).json()

    assert not cuerpo["completa"]
    # El primer producto no tiene telefono: queda vacio, que no es un error. El
    # segundo si lo tiene, y un telefono no es una fecha.
    assert [(e["fila"], e["campo"]) for e in cuerpo["errores"]] == [(2, "roto")]
    assert cuerpo["filas"][0]["roto"] is None


def test_generar_csv_devuelve_el_archivo_y_el_resumen_en_cabeceras(cliente) -> None:
    client, _ = cliente

    respuesta = client.post(
        "/archivos-carga",
        json=_peticion(formato="csv", opciones={"delimitador": ";"}),
    )

    texto = respuesta.content.decode("utf-8")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/csv")
    assert respuesta.headers["content-disposition"] == 'attachment; filename="SMS_preventiva.csv"'
    assert respuesta.headers["x-carga-generados"] == "2"
    assert respuesta.headers["x-carga-suficiente"] == "1"
    assert respuesta.headers["x-carga-errores"] == "0"
    assert texto.startswith("anexo;numero;deuda;vence\r\n")
    assert "1010;51900000001;1.500,50;18/09/2026" in texto


def test_generar_xlsx_entrega_un_libro_que_se_puede_abrir(cliente) -> None:
    client, _ = cliente

    respuesta = client.post("/archivos-carga", json=_peticion(opciones={"hoja": "Campaña"}))

    hoja = openpyxl.load_workbook(io.BytesIO(respuesta.content)).active
    assert hoja.title == "Campaña"
    assert [c.value for c in hoja[1]] == ["anexo", "numero", "deuda", "vence"]
    assert hoja["A2"].value == 1010


def test_generar_json_entrega_una_lista_de_objetos(cliente) -> None:
    client, _ = cliente

    respuesta = client.post("/archivos-carga", json=_peticion(formato="json"))

    filas = json.loads(respuesta.content)
    assert [fila["numero"] for fila in filas] == ["51", "51900000001"]


def test_una_seleccion_insuficiente_se_avisa_sin_fallar(cliente) -> None:
    client, consulta = cliente
    consulta.total = 1

    respuesta = client.post("/archivos-carga", json=_peticion(cantidad=50))

    assert respuesta.status_code == 200
    assert respuesta.headers["x-carga-generados"] == "1"
    assert respuesta.headers["x-carga-disponibles"] == "1"
    assert respuesta.headers["x-carga-suficiente"] == "0"  # RF-08


def test_una_plantilla_que_nombra_un_campo_inexistente_es_un_400(cliente) -> None:
    client, _ = cliente
    definicion = {"nombre": "mala", "campos": [{"nombre": "x", "plantilla": "[@no_existe]"}]}

    respuesta = client.post("/archivos-carga", json=_peticion(definicion=definicion))

    assert respuesta.status_code == 400
    assert "no_existe" in respuesta.json()["detail"]


def test_un_filtro_mal_escrito_es_un_400(cliente) -> None:
    client, _ = cliente

    respuesta = client.post("/archivos-carga", json=_peticion(filtros=["telefono:parecido:9"]))

    assert respuesta.status_code == 400
    assert "operador" in respuesta.json()["detail"]


def test_una_fecha_sin_version_vigente_es_un_404() -> None:
    app.dependency_overrides[obtener_servicio_cartera] = lambda: ConsultaFalsa(
        error=SinVersionVigente(date(2026, 9, 10))
    )
    try:
        respuesta = TestClient(app).post("/archivos-carga", json=_peticion())
    finally:
        app.dependency_overrides.clear()

    assert respuesta.status_code == 404


@pytest.mark.parametrize(
    "peticion",
    [
        {"formato": "pdf"},
        {"cantidad": 0},
        {"definicion": {"nombre": "vacia", "campos": []}},
    ],
)
def test_peticiones_invalidas_se_rechazan_antes_de_generar(cliente, peticion) -> None:
    client, consulta = cliente

    respuesta = client.post("/archivos-carga", json=_peticion(**peticion))

    assert respuesta.status_code == 422
    assert consulta.recibido == {}
