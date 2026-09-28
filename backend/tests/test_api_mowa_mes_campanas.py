"""Pruebas de los endpoints de campanas y reportes de MOWA MES (corte B6b).

Sustituyen las dependencias por los servicios reales sobre repositorios en
memoria; el archivo se escribe con el adaptador .xlsx de verdad y el reporte se
lee con el lector de verdad. Datos sinteticos.
"""

import io
from dataclasses import replace
from decimal import Decimal

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.adapters.input.lector_reporte_mowa_mes import LectorReporteMowaMes
from app.adapters.output.plataformas.mowa_mes.archivo_carga import escribir_archivo_carga
from app.api import contrato
from app.api.mowa_mes_campanas import (
    CABECERAS_ARCHIVO,
    obtener_servicio_campanas,
    obtener_servicio_reportes,
)
from app.core.entities.gestiones_digitales import ConfiguracionSupervision
from app.core.entities.mowa_mes_reporte import COLUMNAS_REPORTE
from app.core.services.plataformas.mowa_mes.campana import CampanasMowaMesService
from app.core.services.plataformas.mowa_mes.reportes import ReportesMowaMesService
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService
from app.main import app
from tests.test_gestiones_digitales import PROCEDENCIAS, SUPERVISORES, RepositorioSupervisionFalso
from tests.test_mowa_mes_campana import (
    HUELLA_ORIGINAL,
    MOMENTO,
    RepositorioCampanasMemoria,
    RepositorioCarteraFalso,
    producto,
)
from tests.test_mowa_mes_speech import WHATSAPP, RepositorioMowaMesFalso

CUERPO = {
    "fecha_corte": "2026-09-10",
    "cantidad": 100,
    "programacion": "hora_determinada",
    "envios": ["2026-09-14T09:00:00"],
}


class Entorno:
    def __init__(self, productos=None, supervisores=SUPERVISORES, cargados_mes=0, vigente=True):
        self.cartera = RepositorioCarteraFalso(
            productos if productos is not None else [producto(1), producto(2, telefono=None)],
            vigente,
        )
        self.mowa_mes = RepositorioMowaMesFalso(WHATSAPP)
        self.supervision = RepositorioSupervisionFalso()
        self.supervision.configuracion = ConfiguracionSupervision(PROCEDENCIAS, tuple(supervisores))
        self.campanas = RepositorioCampanasMemoria(cargados_mes)

    def campanas_servicio(self):
        return CampanasMowaMesService(
            ConsultaCarteraService(self.cartera),
            self.mowa_mes,
            self.supervision,
            self.campanas,
            escribir_archivo_carga,
            reloj=lambda: MOMENTO,
        )

    def reportes_servicio(self):
        return ReportesMowaMesService(self.campanas, LectorReporteMowaMes())


def _cliente(entorno: Entorno) -> TestClient:
    app.dependency_overrides[obtener_servicio_campanas] = entorno.campanas_servicio
    app.dependency_overrides[obtener_servicio_reportes] = entorno.reportes_servicio
    return TestClient(app)


@pytest.fixture(autouse=True)
def _limpiar_dependencias():
    yield
    app.dependency_overrides.clear()


def _crear(client: TestClient, **extra):
    return client.post(
        "/mowa-mes/campanas", json={**CUERPO, "speech_huella": HUELLA_ORIGINAL, **extra}
    )


# --- Previsualizacion ---------------------------------------------------


def test_previsualizacion_de_una_campana_valida() -> None:
    client = _cliente(Entorno())

    respuesta = client.post("/mowa-mes/campanas/previsualizacion", json=CUERPO)

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert cuerpo["puede_crear"] is True and cuerpo["errores"] == []
    assert cuerpo["speech"] == {"id": 1, "nombre": "Speech original", "huella": HUELLA_ORIGINAL}
    assert (cuerpo["productos_cargados"], cuerpo["supervision_cargados"]) == (1, 5)
    assert cuerpo["exclusiones_por_codigo"] == [
        {"codigo": "telefono_invalido", "tipo": "exclusion", "cantidad": 1}
    ]
    assert cuerpo["exclusiones"]["exclusiones"] == [
        {"pagare": producto(2)["pagare"], "codigo": "telefono_invalido"}
    ]
    assert [m["supervision"] for m in cuerpo["muestra"]] == [True] * 5 + [False]
    assert cuerpo["muestra"][5]["largo"] == len(cuerpo["muestra"][5]["mensaje"])
    assert cuerpo["archivos_previstos_por_filas"] == [{"numero": 1, "filas": 6, "supervision": 5}]
    assert cuerpo["limite"]["mes"] == "2026-09" and cuerpo["limite"]["excedido"] is False
    assert cuerpo["fecha_envio"] == "2026-09-14"
    assert {s["segmento"]: s["cantidad"] for s in cuerpo["productos_por_segmento"]}["1_a_8"] == 1
    assert cuerpo["descripcion"] == cuerpo["descripcion_sugerida"] == "CajaCusco"


def test_los_errores_de_campana_se_listan_sin_responder_error() -> None:
    client = _cliente(Entorno(supervisores=()))

    cuerpo = client.post("/mowa-mes/campanas/previsualizacion", json=CUERPO).json()

    assert cuerpo["puede_crear"] is False
    assert [(e["codigo"], e["tipo"]) for e in cuerpo["errores"]] == [("sin_supervisores", "error")]


def test_la_advertencia_de_limite_mensual() -> None:
    client = _cliente(Entorno(cargados_mes=2_500_000))

    cuerpo = client.post("/mowa-mes/campanas/previsualizacion", json=CUERPO).json()

    assert [(a["codigo"], a["tipo"]) for a in cuerpo["advertencias"]] == [
        ("limite_mensual_excedido", "advertencia")
    ]
    assert cuerpo["puede_crear"] is True


@pytest.mark.parametrize(
    ("entorno", "cambio", "estado"),
    [
        ({"vigente": False}, {}, 404),
        ({}, {"tipo_carga": "personalizada"}, 400),
        ({}, {"filtros": ["campo_inventado:igual:x"]}, 400),
        ({}, {"speech_id": 99}, 404),
        ({}, {"cantidad": 0}, 422),
        ({}, {"salida": "otra"}, 422),
    ],
)
def test_peticiones_de_previsualizacion_rechazadas(entorno, cambio, estado) -> None:
    client = _cliente(Entorno(**entorno))

    respuesta = client.post("/mowa-mes/campanas/previsualizacion", json={**CUERPO, **cambio})

    assert respuesta.status_code == estado


# --- Creacion y consulta ------------------------------------------------


def test_crear_y_consultar_una_campana() -> None:
    client = _cliente(Entorno())

    creada = _crear(client, descripcion="Campana sintetica")
    campana_id = creada.json()["id"]
    leida = client.get(f"/mowa-mes/campanas/{campana_id}")
    lista = client.get("/mowa-mes/campanas").json()
    exclusiones = client.get(
        f"/mowa-mes/campanas/{campana_id}/exclusiones", params={"codigo": "telefono_invalido"}
    ).json()
    otras = client.get(
        f"/mowa-mes/campanas/{campana_id}/exclusiones", params={"codigo": "sin_speech"}
    ).json()

    assert creada.status_code == 201
    cuerpo = leida.json()
    assert (cuerpo["descripcion"], cuerpo["total_cargados"], cuerpo["mes_imputacion"]) == (
        "Campana sintetica",
        6,
        "2026-09",
    )
    assert cuerpo["archivos"] == [
        {
            "numero": 1,
            "filas": 6,
            "supervision": 5,
            "bytes": cuerpo["archivos"][0]["bytes"],
            "nombre": "mowa_mes_campana_1_1_de_1.xlsx",
        }
    ]
    assert cuerpo["speech"] == {"id": 1, "nombre": "Speech original"}
    # En el orden de la lista (entrelazada a proposito), cada uno con su DNI por procedencia.
    assert [s["documento"] for s in cuerpo["supervisores"]] == [
        "00000001",
        "00000004",
        "00000002",
        "00000005",
        "00000003",
    ]
    assert (lista["total"], lista["campanas"][0]["id"]) == (1, campana_id)
    assert exclusiones["total"] == 1 and otras["total"] == 0
    assert client.get("/mowa-mes/campanas/99").status_code == 404
    assert client.get("/mowa-mes/campanas/99/exclusiones").status_code == 404


@pytest.mark.parametrize(
    ("entorno", "extra", "estado"),
    [
        ({}, {"speech_huella": "0" * 64}, 409),
        ({"cargados_mes": 2_500_000}, {}, 409),
        ({"cargados_mes": 2_500_000}, {"confirmar_limite": True}, 201),
        ({"supervisores": ()}, {}, 400),
        ({}, {"speech_huella": "corta"}, 422),
    ],
)
def test_respuestas_de_la_creacion(entorno, extra, estado) -> None:
    client = _cliente(Entorno(**entorno))

    assert _crear(client, **extra).status_code == estado


@pytest.mark.parametrize(
    ("entorno", "extra", "codigo"),
    [
        ({}, {"speech_huella": "0" * 64}, "huella_cambiada"),
        ({"cargados_mes": 2_500_000}, {}, "limite_excedido"),
    ],
)
def test_el_409_de_la_creacion_trae_el_codigo_del_motivo(entorno, extra, codigo) -> None:
    client = _cliente(Entorno(**entorno))

    respuesta = _crear(client, **extra)

    assert respuesta.status_code == 409
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == codigo
    assert isinstance(cuerpo["detail"], str) and cuerpo["detail"]


def test_con_huella_cambiada_y_limite_excedido_el_409_es_huella_cambiada() -> None:
    """El orden no cambia (docs/mowa-mes.md §15): la huella se revisa antes que el limite."""
    client = _cliente(Entorno(cargados_mes=2_500_000))

    respuesta = _crear(client, speech_huella="0" * 64)

    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "huella_cambiada"


def test_crear_sin_huella_no_llega_al_caso_de_uso() -> None:
    client = _cliente(Entorno())

    assert client.post("/mowa-mes/campanas", json=CUERPO).status_code == 422


def test_limite_mensual_de_un_mes() -> None:
    client = _cliente(Entorno(cargados_mes=100))

    cuerpo = client.get("/mowa-mes/limite-mensual", params={"mes": "2026-09"}).json()

    assert cuerpo == {
        "mes": "2026-09",
        "limite": 2_500_000,
        "cargados_mes": 100,
        "esta_campana": 0,
        "total": 100,
        "disponible": 2_499_900,
        "excedido": False,
        "costo_mes": "0.0000",
        "campanas_sin_tarifa": 0,
        "costo_esta_campana": None,
        "costo_total": "0.0000",
    }
    assert client.get("/mowa-mes/limite-mensual").json()["mes"] == "2026-09"
    assert client.get("/mowa-mes/limite-mensual", params={"mes": "2026-13"}).status_code == 422


# --- Descarga -----------------------------------------------------------


def test_la_descarga_entrega_el_xlsx_y_las_cabeceras_declaradas() -> None:
    client = _cliente(Entorno())
    campana_id = _crear(client).json()["id"]

    respuesta = client.get(f"/mowa-mes/campanas/{campana_id}/archivos/1")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-disposition"] == (
        'attachment; filename="mowa_mes_campana_1_1_de_1.xlsx"; '
        "filename*=UTF-8''mowa_mes_campana_1_1_de_1.xlsx"
    )
    enviadas = {n for n in respuesta.headers if n.startswith("x-mowa-mes-")}
    assert enviadas == {nombre.lower() for nombre in CABECERAS_ARCHIVO}
    assert (respuesta.headers["x-mowa-mes-filas"], respuesta.headers["x-mowa-mes-supervision"]) == (
        "6",
        "5",
    )
    hoja = openpyxl.load_workbook(io.BytesIO(respuesta.content))["Hoja1"]
    assert next(hoja.iter_rows(values_only=True)) == ("numero", "mensaje", "dni")
    assert client.get(f"/mowa-mes/campanas/{campana_id}/archivos/2").status_code == 404
    assert client.get("/mowa-mes/campanas/99/archivos/1").status_code == 404


def test_el_contrato_declara_las_cabeceras_de_la_descarga() -> None:
    esquema = contrato.generar()
    respuesta = esquema["paths"]["/mowa-mes/campanas/{campana_id}/archivos/{numero}"]["get"][
        "responses"
    ]["200"]

    assert set(respuesta["headers"]) == {"Content-Disposition", *CABECERAS_ARCHIVO}
    assert list(respuesta["content"]) == [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ]


# --- Reporte de enviados ------------------------------------------------


def _reporte(filas, mes_id: int) -> bytes:
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "Hoja1"
    hoja.append(list(COLUMNAS_REPORTE))
    for fila in filas:
        hoja.append(
            [mes_id, fila.numero, fila.mensaje, "14/09/26", fila.dni, "enviado", "Nro. LARGO", "u"]
        )
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def test_importar_el_reporte_y_conciliar() -> None:
    entorno = Entorno()
    client = _cliente(entorno)
    campana_id = _crear(client).json()["id"]
    contenido = _reporte(entorno.campanas.filas_cargadas(campana_id), 990001)

    def importar(**datos):
        return client.post(
            f"/mowa-mes/campanas/{campana_id}/reportes",
            files={"archivo": ("reporte.xlsx", contenido)},
            data=datos,
        )

    importado = importar()
    repetido = importar()
    reemplazado = importar(reemplazar="true")
    conciliacion = client.get(f"/mowa-mes/campanas/{campana_id}/conciliacion").json()

    assert importado.status_code == 201
    assert repetido.status_code == 409
    assert reemplazado.status_code == 201
    assert (conciliacion["total"]["cargados"], conciliacion["total"]["enviados"]) == (6, 6)
    assert conciliacion["supervision"]["por_estado"] == [{"estado": "enviado", "cantidad": 5}]
    assert conciliacion["por_id"] == [{"mes_id": 990001, "filas": 6, "con_correspondencia": 6}]
    assert [r["mes_id"] for r in conciliacion["reportes"]] == [990001]
    assert conciliacion["advertencias"] == []


def test_importar_rechazos() -> None:
    client = _cliente(Entorno())
    campana_id = _crear(client).json()["id"]

    invalido = client.post(
        f"/mowa-mes/campanas/{campana_id}/reportes", files={"archivo": ("x.xlsx", b"no es xlsx")}
    )
    sin_campana = client.post(
        "/mowa-mes/campanas/99/reportes", files={"archivo": ("x.xlsx", b"no es xlsx")}
    )

    assert invalido.status_code == 400
    assert sin_campana.status_code == 404
    assert client.get("/mowa-mes/campanas/99/conciliacion").status_code == 404


# --- Decisiones E-1 y E-2 -----------------------------------------------


def test_la_previsualizacion_advierte_un_documento_no_estandar() -> None:
    carne = producto(2, documento_numero="ZZCE123456", documento_tipo="extranjero")
    client = _cliente(Entorno(productos=[producto(1), carne]))

    cuerpo = client.post("/mowa-mes/campanas/previsualizacion", json=CUERPO).json()

    assert cuerpo["excluidos"] == 0
    assert cuerpo["advertencias_por_codigo"] == [
        {"codigo": "documento_no_estandar", "tipo": "advertencia", "cantidad": 1}
    ]
    productos = [m for m in cuerpo["muestra"] if not m["supervision"]]
    assert [(m["dni"], m["advertencias"]) for m in productos] == [
        ("00000001", []),
        ("ZZCE123456", ["documento_no_estandar"]),
    ]


def test_un_estado_distinto_de_enviado_no_cuenta_en_la_conciliacion() -> None:
    entorno = Entorno()
    client = _cliente(entorno)
    campana_id = _crear(client).json()["id"]
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "Hoja1"
    hoja.append(list(COLUMNAS_REPORTE))
    for fila in entorno.campanas.filas_cargadas(campana_id):
        estado = "enviado" if fila.supervision else "fallido"
        hoja.append([990002, fila.numero, fila.mensaje, "14/09/26", fila.dni, estado, "L", "u"])
    buffer = io.BytesIO()
    libro.save(buffer)

    cuerpo = client.post(
        f"/mowa-mes/campanas/{campana_id}/reportes",
        files={"archivo": ("reporte.xlsx", buffer.getvalue())},
    ).json()

    assert cuerpo["productos"] == {
        "cargados": 1,
        "enviados": 0,
        "no_enviados": 1,
        "por_estado": [{"estado": "fallido", "cantidad": 1}],
    }
    assert (cuerpo["total"]["enviados"], cuerpo["total"]["no_enviados"]) == (5, 1)
    assert cuerpo["por_id"] == [{"mes_id": 990002, "filas": 6, "con_correspondencia": 6}]


# --- Revision de la API falsa de F3 (T-MM-B7) ---------------------------


def test_exclusiones_por_codigo_fuera_del_catalogo_o_que_no_es_exclusion() -> None:
    client = _cliente(Entorno())
    campana_id = _crear(client).json()["id"]
    ruta = f"/mowa-mes/campanas/{campana_id}/exclusiones"

    inventado = client.get(ruta, params={"codigo": "codigo_inventado"})
    advertencia = client.get(ruta, params={"codigo": "mensaje_excede_150"})

    assert inventado.status_code == 422
    assert isinstance(inventado.json()["detail"], list)
    assert advertencia.status_code == 200
    assert (advertencia.json()["total"], advertencia.json()["exclusiones"]) == (0, [])


def test_la_conciliacion_sin_reporte_da_todo_cargado_y_nada_enviado() -> None:
    client = _cliente(Entorno())
    campana = _crear(client).json()

    cuerpo = client.get(f"/mowa-mes/campanas/{campana['id']}/conciliacion").json()

    assert cuerpo["reportes"] == []
    for grupo, cargados in (
        ("productos", campana["productos_cargados"]),
        ("supervision", campana["supervision_cargados"]),
        ("total", campana["total_cargados"]),
    ):
        assert cuerpo[grupo] == {
            "cargados": cargados,
            "enviados": 0,
            "no_enviados": cargados,
            "por_estado": [],
        }
    assert (cuerpo["sin_correspondencia"], cuerpo["sin_correspondencia_por_estado"]) == (0, [])
    assert (cuerpo["por_id"], cuerpo["advertencias"]) == ([], [])


# --- Tarifa, costos y nombre de los archivos (B8: RF-MM-23 a RF-MM-25) ---


def _con_tarifa(entorno: Entorno, tarifa: str) -> None:
    entorno.mowa_mes.configuracion = replace(
        entorno.mowa_mes.configuracion, tarifa_sms=Decimal(tarifa)
    )


def test_la_previsualizacion_trae_tarifa_costo_y_nombre_del_primer_archivo() -> None:
    client = _cliente(Entorno())

    cuerpo = client.post("/mowa-mes/campanas/previsualizacion", json=CUERPO).json()

    assert cuerpo["tarifa_sms"] == "0.0200"
    assert cuerpo["costo_estimado"] == "0.1200"  # 6 SMS, supervision incluida, a 0.02
    assert cuerpo["plantilla_nombre_archivo"] == "mowa_mes_campana_{campana}_{archivo}_de_{total}"
    assert cuerpo["nombre_primer_archivo"] == "mowa_mes_campana_[campana]_1_de_1.xlsx"
    assert cuerpo["nombre_estimado"] is True
    assert cuerpo["limite"]["costo_esta_campana"] == "0.1200"
    assert cuerpo["limite"]["costo_total"] == "0.1200"


def test_los_montos_viajan_como_texto_nunca_como_numero() -> None:
    entorno = Entorno()
    client = _cliente(entorno)
    campana = _crear(client).json()

    previa = client.post("/mowa-mes/campanas/previsualizacion", json=CUERPO).json()
    limite = client.get("/mowa-mes/limite-mensual", params={"mes": "2026-09"}).json()

    for monto in (
        previa["tarifa_sms"],
        previa["costo_estimado"],
        previa["limite"]["costo_mes"],
        previa["limite"]["costo_esta_campana"],
        previa["limite"]["costo_total"],
        limite["costo_mes"],
        limite["costo_total"],
        campana["tarifa_sms"],
        campana["costo_estimado"],
    ):
        assert isinstance(monto, str) and monto.replace(".", "").isdigit(), monto


def test_la_creacion_congela_la_tarifa_y_el_costo_y_el_costo_real_queda_pendiente() -> None:
    entorno = Entorno()
    _con_tarifa(entorno, "0.05")
    client = _cliente(entorno)

    campana = _crear(client).json()
    _con_tarifa(entorno, "0.10")
    leida = client.get(f"/mowa-mes/campanas/{campana['id']}").json()

    for cuerpo in (campana, leida):
        assert cuerpo["tarifa_sms"] == "0.0500"
        assert cuerpo["costo_estimado"] == "0.3000"
        assert cuerpo["costo_estimado_estado"] == "calculado"
        assert cuerpo["costo_real"] is None
        assert cuerpo["costo_real_estado"] == "pendiente"
    assert "enviados_conciliados" not in leida  # derivado interno: no se expone


def test_el_costo_del_mes_suma_los_estimados_y_lo_dice_junto_al_limite() -> None:
    entorno = Entorno()
    client = _cliente(entorno)
    _crear(client)
    _con_tarifa(entorno, "0.10")
    _crear(client)  # 6 SMS a 0.10

    limite = client.get("/mowa-mes/limite-mensual", params={"mes": "2026-09"}).json()
    previa = client.post("/mowa-mes/campanas/previsualizacion", json=CUERPO).json()["limite"]

    assert limite["costo_mes"] == "0.7200"  # 0.12 + 0.60
    assert limite["costo_esta_campana"] is None
    assert previa["costo_mes"] == "0.7200"
    assert previa["costo_esta_campana"] == "0.6000"
    assert previa["costo_total"] == "1.3200"


def test_una_campana_sin_tarifa_dice_no_disponible_y_no_suma_pero_se_cuenta() -> None:
    entorno = Entorno()
    client = _cliente(entorno)
    campana_id = _crear(client).json()["id"]
    entorno.campanas.campanas[campana_id] = replace(
        entorno.campanas.campanas[campana_id], tarifa_sms=None, costo_estimado=None
    )

    leida = client.get(f"/mowa-mes/campanas/{campana_id}").json()
    lista = client.get("/mowa-mes/campanas").json()["campanas"][0]
    limite = client.get("/mowa-mes/limite-mensual", params={"mes": "2026-09"}).json()

    for cuerpo in (leida, lista):
        assert cuerpo["tarifa_sms"] is None
        assert cuerpo["costo_estimado"] is None
        assert cuerpo["costo_estimado_estado"] == "no_disponible"
        assert cuerpo["costo_real"] is None
        assert cuerpo["costo_real_estado"] == "no_disponible"
    assert (limite["costo_mes"], limite["campanas_sin_tarifa"]) == ("0.0000", 1)


def test_el_costo_real_sale_de_los_enviados_y_lo_muestran_la_conciliacion_y_el_listado() -> None:
    entorno = Entorno()
    _con_tarifa(entorno, "0.05")
    client = _cliente(entorno)
    campana_id = _crear(client).json()["id"]
    contenido = _reporte(entorno.campanas.filas_cargadas(campana_id), 990001)

    importado = client.post(
        f"/mowa-mes/campanas/{campana_id}/reportes", files={"archivo": ("reporte.xlsx", contenido)}
    ).json()
    conciliacion = client.get(f"/mowa-mes/campanas/{campana_id}/conciliacion").json()
    leida = client.get(f"/mowa-mes/campanas/{campana_id}").json()
    lista = client.get("/mowa-mes/campanas").json()["campanas"][0]

    for cuerpo in (importado, conciliacion):
        assert cuerpo["tarifa_sms"] == "0.0500"
        assert cuerpo["costo_real"] == "0.3000"  # 6 enviados
        assert cuerpo["costo_real_estado"] == "calculado"
    for cuerpo in (leida, lista):
        assert (cuerpo["costo_real"], cuerpo["costo_real_estado"]) == ("0.3000", "calculado")
    assert leida["costo_real"] == conciliacion["costo_real"]


def test_la_conciliacion_sin_reporte_da_costo_real_pendiente() -> None:
    client = _cliente(Entorno())
    campana_id = _crear(client).json()["id"]

    cuerpo = client.get(f"/mowa-mes/campanas/{campana_id}/conciliacion").json()

    assert (cuerpo["costo_real"], cuerpo["costo_real_estado"]) == (None, "pendiente")
    assert cuerpo["tarifa_sms"] == "0.0200"


def test_solo_los_enviados_cuentan_en_el_costo_real() -> None:
    entorno = Entorno()
    client = _cliente(entorno)
    campana_id = _crear(client).json()["id"]
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "Hoja1"
    hoja.append(list(COLUMNAS_REPORTE))
    for fila in entorno.campanas.filas_cargadas(campana_id):
        estado = "enviado" if fila.supervision else "fallido"
        hoja.append([990003, fila.numero, fila.mensaje, "14/09/26", fila.dni, estado, "L", "u"])
    buffer = io.BytesIO()
    libro.save(buffer)

    cuerpo = client.post(
        f"/mowa-mes/campanas/{campana_id}/reportes",
        files={"archivo": ("reporte.xlsx", buffer.getvalue())},
    ).json()

    assert cuerpo["costo_real"] == "0.1000"  # 5 enviados a 0.02, no los 6 cargados


def test_la_plantilla_de_la_campana_da_los_nombres_de_los_archivos() -> None:
    client = _cliente(Entorno())

    previa = client.post(
        "/mowa-mes/campanas/previsualizacion",
        json={**CUERPO, "plantilla_nombre_archivo": "CajaCusco_{fecha_envio}_{campana}"},
    ).json()
    creada = _crear(client, plantilla_nombre_archivo="CajaCusco_{fecha_envio}_{campana}").json()

    assert previa["plantilla_nombre_archivo"] == "CajaCusco_{fecha_envio}_{campana}"
    assert previa["nombre_primer_archivo"] == "CajaCusco_2026-09-14_[campana].xlsx"
    assert previa["nombre_estimado"] is False
    assert [a["nombre"] for a in creada["archivos"]] == ["CajaCusco_2026-09-14_1.xlsx"]


@pytest.mark.parametrize(
    ("plantilla", "dice"),
    [("caja_{nombre}", "{nombre}"), ("caja_{campana", "sin cerrar"), ("caja}", "sin abrir")],
)
def test_una_plantilla_de_campana_invalida_responde_400_con_el_motivo(plantilla, dice) -> None:
    client = _cliente(Entorno())

    previa = client.post(
        "/mowa-mes/campanas/previsualizacion",
        json={**CUERPO, "plantilla_nombre_archivo": plantilla},
    )
    creada = _crear(client, plantilla_nombre_archivo=plantilla)

    for respuesta in (previa, creada):
        assert respuesta.status_code == 400
        assert dice in respuesta.json()["detail"]
        assert respuesta.json()["campo"] == "plantilla_nombre_archivo"
        assert set(respuesta.json()) == {"detail", "campo"}


def test_un_400_que_no_es_de_un_campo_trae_campo_null_y_un_404_no_lo_trae() -> None:
    client = _cliente(Entorno(supervisores=()))
    otros = [
        client.post(
            "/mowa-mes/campanas/previsualizacion", json={**CUERPO, "tipo_carga": "personalizada"}
        ),
        client.post(
            "/mowa-mes/campanas/previsualizacion",
            json={**CUERPO, "filtros": ["campo_inventado:igual:x"]},
        ),
        _crear(client),  # sin supervisores: CampanaInvalida
    ]
    sin_version = _cliente(Entorno(vigente=False)).post(
        "/mowa-mes/campanas/previsualizacion", json=CUERPO
    )

    for respuesta in otros:
        assert respuesta.status_code == 400
        assert respuesta.json()["campo"] is None
        assert isinstance(respuesta.json()["detail"], str)
    assert sin_version.status_code == 404
    assert set(sin_version.json()) == {"detail"}


def test_el_contrato_declara_el_400_de_las_campanas_con_su_campo_opcional() -> None:
    esquema = contrato.generar()
    modelo = esquema["components"]["schemas"]["ErrorPeticionCampanaRespuesta"]

    assert set(modelo["required"]) == {"detail", "campo"}
    assert {"$ref": "#/components/schemas/CampoConfiguracion"} in modelo["properties"]["campo"][
        "anyOf"
    ]
    for ruta in ("/mowa-mes/campanas/previsualizacion", "/mowa-mes/campanas"):
        respuesta = esquema["paths"][ruta]["post"]["responses"]["400"]
        assert respuesta["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorPeticionCampanaRespuesta"
        }


def test_la_descarga_usa_el_nombre_guardado_con_filename_ascii_y_filename_utf8() -> None:
    entorno = Entorno()
    client = _cliente(entorno)
    campana_id = _crear(client, plantilla_nombre_archivo="Cobranza_mañana_{campana}").json()["id"]
    # El cambio posterior de la plantilla de la configuracion no toca lo ya guardado.
    entorno.mowa_mes.configuracion = replace(
        entorno.mowa_mes.configuracion, plantilla_nombre_archivo="otra_{campana}"
    )

    respuesta = client.get(f"/mowa-mes/campanas/{campana_id}/archivos/1")

    assert respuesta.headers["content-disposition"] == (
        'attachment; filename="Cobranza_manana_1.xlsx"; '
        "filename*=UTF-8''Cobranza_ma%C3%B1ana_1.xlsx"
    )


def test_el_contrato_declara_la_descarga_con_los_dos_nombres() -> None:
    esquema = contrato.generar()
    cabecera = esquema["paths"]["/mowa-mes/campanas/{campana_id}/archivos/{numero}"]["get"][
        "responses"
    ]["200"]["headers"]["Content-Disposition"]

    assert "filename*=UTF-8" in cabecera["description"]
    assert "ASCII" in cabecera["description"]
