"""Campanas de MOWA MES contra PostgreSQL real, de punta a punta por HTTP (opcional).

Corre solo con AUTO_CUSCO_DB_TESTS=1 y la base migrada. La cadena completa:
sabana sintetica ingestada por la via normal (fecha 2099) -> previsualizacion ->
creacion -> descarga de archivos -> reporte de enviados -> conciliacion.

La base local es compartida: antes de cada prueba se guardan la lista de
supervisores, la configuracion del conector y la marca de uso del Speech
original, y al terminar se restituyen. Las campanas de la fecha 2099 y las
versiones de speech con el prefijo de prueba se borran. Numeros 900000xxx.
"""

import io
import os
import unicodedata
from datetime import date

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update

from app.adapters.input.lector_calamine import LectorCalamine
from app.adapters.persistence.db import get_engine
from app.adapters.persistence.modelos import (
    Carga,
    CargaAuditoria,
    MowaMesCampana,
    MowaMesSpeechVersion,
)
from app.adapters.persistence.repositorio_campanas_mowa_mes_postgres import (
    RepositorioCampanasMowaMesPostgres,
)
from app.adapters.persistence.repositorio_cargas_postgres import RepositorioCargasPostgres
from app.adapters.persistence.repositorio_mowa_mes_postgres import (
    RepositorioMowaMesPostgres,
    normalizar_nombre,
)
from app.adapters.persistence.repositorio_supervision_postgres import (
    RepositorioSupervisionPostgres,
)
from app.core.entities.gestiones_digitales import ConfiguracionSupervision, Supervisor
from app.core.entities.mowa_mes import CodigoMowaMes
from app.core.entities.mowa_mes_reporte import COLUMNAS_REPORTE
from app.core.services.ingesta_sabana.servicio import IngestaSabanaService
from app.main import app
from tests.test_sabana_cabeceras import CABECERAS_10_09
from tests.test_sabana_normalizador import _fila_sintetica
from tests.test_speech_original import speech_del_documento

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

FECHA = date(2099, 6, 1)
PREFIJO = "zz prueba automatica campana "
MES_IDS = (990000001, 990000002, 990000003)
_CARGA, _AUDITORIA = Carga.__table__, CargaAuditoria.__table__
_CAMPANA = MowaMesCampana.__table__
_SPEECH = MowaMesSpeechVersion.__table__
SERIAL_2099_05_28 = 73018.0  # fecha de Excel de la cuota vencida

SUPERVISORES = ConfiguracionSupervision(
    procedencias=("Caja Cusco", "nuestra empresa"),
    supervisores=tuple(
        Supervisor(f"90000000{i}", "Caja Cusco" if i <= 3 else "nuestra empresa")
        for i in range(1, 6)
    ),
)


def _producto(i: int, **cambios) -> dict:
    datos = {
        "Pagare": f"{i:018d}",
        "PAGARE": f"{i:018d}",
        "Titular": f"ZZPRUEBA/SINTETICO,NOMBRE {i}",
        "DniRuc": 10_000_000.0 + i,
        "Teléfono": 900_000_100.0 + i,
        "Dias Atraso Hoy": 4.0,  # + 1 dia hasta el envio: segmento 1 a 8
        "Vencimiento Cuota": SERIAL_2099_05_28,
    }
    datos.update(cambios)
    return datos


PRODUCTOS = [
    _producto(1),
    _producto(2, **{"Dias Atraso Hoy": 40.0}),  # 31 a 60: usa [whatsapp]
    _producto(3),
    _producto(4, **{"Teléfono": 12345.0}),  # telefono_invalido
    _producto(5, DniRuc=None),  # falta_documento
    _producto(6),
    _producto(7),
    _producto(8),
    _producto(9, DniRuc="ZZCE123456"),  # carne sintetico: se carga y se advierte
]


def _sabana() -> bytes:
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "VENCIDA"
    hoja.append(CABECERAS_10_09)
    for cambios in PRODUCTOS:
        hoja.append(_fila_sintetica(**cambios))
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def _limpiar(engine) -> None:
    with engine.begin() as cx:
        cx.execute(delete(_CAMPANA).where(_CAMPANA.c.fecha_corte == FECHA))
        cx.execute(
            delete(_SPEECH).where(
                _SPEECH.c.nombre_normalizado.startswith(normalizar_nombre(PREFIJO))
            )
        )
        cx.execute(delete(_CARGA).where(_CARGA.c.fecha_corte == FECHA))
        cx.execute(delete(_AUDITORIA).where(_AUDITORIA.c.fecha_corte == FECHA))


@pytest.fixture
def cliente():
    engine = get_engine()
    supervision = RepositorioSupervisionPostgres(engine)
    mowa_mes = RepositorioMowaMesPostgres(engine)
    supervisores_antes = supervision.obtener()
    configuracion_antes = mowa_mes.obtener_configuracion()
    with engine.connect() as cx:
        original = cx.execute(
            select(_SPEECH.c.id, _SPEECH.c.usada_en).where(_SPEECH.c.original)
        ).one()
    _limpiar(engine)
    try:
        ingesta = IngestaSabanaService(RepositorioCargasPostgres(engine), LectorCalamine())
        carga = ingesta.registrar_carga(FECHA, "sintetica.xlsx", _sabana()).carga
        assert ingesta.procesar_carga(carga.id).vigente
        supervision.reemplazar(SUPERVISORES)
        cliente = TestClient(app)
        respuesta = cliente.put(
            "/mowa-mes/configuracion",
            json={
                "limite_mensual": 2_500_000,
                "whatsapp_contacto": "900000123",
                "registros_por_archivo": 50_000,
                "bytes_por_archivo": 2_000_000,
            },
        )
        assert respuesta.status_code == 200
        yield cliente, engine
    finally:
        _limpiar(engine)
        with engine.begin() as cx:
            cx.execute(
                update(_SPEECH)
                .where(_SPEECH.c.id == original.id)
                .values(usada_en=original.usada_en)
            )
        supervision.reemplazar(supervisores_antes)
        mowa_mes.guardar_configuracion(configuracion_antes)


CUERPO = {
    "fecha_corte": FECHA.isoformat(),
    "cantidad": 100,
    "programacion": "hora_determinada",
    "envios": ["2099-06-02T09:00:00"],
    # El producto 9 (E-2) tiene su propia prueba; el resto de la cadena no lo incluye.
    "filtros": ["pagare:distinto:000000000000000009"],
}


def _previsualizar(cliente, **extra) -> dict:
    respuesta = cliente.post("/mowa-mes/campanas/previsualizacion", json={**CUERPO, **extra})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _crear(cliente, huella: str, **extra):
    return cliente.post("/mowa-mes/campanas", json={**CUERPO, "speech_huella": huella, **extra})


def _filas_xlsx(contenido: bytes) -> list[tuple]:
    hoja = openpyxl.load_workbook(io.BytesIO(contenido))["Hoja1"]
    return list(hoja.iter_rows(values_only=True))[1:]


def _como_mes(texto: str) -> str:
    """Lo que hace MES al enviar: sin tildes y sin espacios en los extremos."""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c)
    ).strip()


def _reporte(filas: list[tuple[int, tuple]]) -> bytes:
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "Hoja1"
    hoja.append(list(COLUMNAS_REPORTE))
    for mes_id, (numero, mensaje, dni) in filas:
        hoja.append(
            [mes_id, str(numero), _como_mes(mensaje), "02/06/99", dni, "enviado", "Nro. LARGO", "u"]
        )
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def test_cadena_completa_por_http(cliente) -> None:
    client, _ = cliente

    previa = _previsualizar(client)
    creada = _crear(client, previa["speech"]["huella"])
    campana = creada.json()
    descarga = client.get(f"/mowa-mes/campanas/{campana['id']}/archivos/1")
    filas = _filas_xlsx(descarga.content)
    exclusiones = client.get(f"/mowa-mes/campanas/{campana['id']}/exclusiones").json()
    limite = client.get("/mowa-mes/limite-mensual", params={"mes": "2099-06"}).json()
    speech = client.get(f"/mowa-mes/speech/{previa['speech']['id']}").json()

    assert previa["errores"] == [] and previa["puede_crear"] is True
    assert creada.status_code == 201, creada.text
    assert (campana["productos_cargados"], campana["supervision_cargados"]) == (6, 5)
    assert (campana["total_cargados"], campana["mes_imputacion"]) == (11, "2099-06")
    assert [(a["numero"], a["filas"], a["supervision"]) for a in campana["archivos"]] == [
        (1, 11, 5)
    ]
    assert descarga.headers["x-mowa-mes-bytes"] == str(len(descarga.content))
    # Supervision al inicio, con el mensaje de la primera fila cargada.
    assert [f[2] for f in filas[:5]] == [f"0000000{i}" for i in range(1, 6)]
    assert [f[0] for f in filas[:5]] == [900000001, 900000002, 900000003, 900000004, 900000005]
    assert {f[1] for f in filas[:5]} == {filas[5][1]}
    assert filas[5] == (900000101, filas[5][1], "10000001")
    assert filas[6][1].endswith("https://wa.me/+51900000123")  # el producto 2, segmento 31 a 60
    assert [(e["pagare"][-1], e["codigo"]) for e in exclusiones["exclusiones"]] == [
        ("4", "telefono_invalido"),
        ("5", "falta_documento"),
    ]
    assert limite["cargados_mes"] == 11
    assert speech["usada"] is True and speech["editable"] is False

    # Reporte de MES: dos id para la campana, uno ajeno y un producto que no salio.
    enviadas = [(MES_IDS[0], f) for f in filas[:6]] + [(MES_IDS[1], f) for f in filas[7:]]
    ajena = [(MES_IDS[2], (900000999, "ZZPRUEBA de otra campana", "99999999"))]
    contenido = _reporte(enviadas + ajena)

    def importar(**datos):
        return client.post(
            f"/mowa-mes/campanas/{campana['id']}/reportes",
            files={"archivo": ("reporte.xlsx", contenido)},
            data=datos,
        )

    importado = importar()
    repetido = importar()
    reemplazado = importar(reemplazar="true")
    conciliacion = client.get(f"/mowa-mes/campanas/{campana['id']}/conciliacion").json()

    assert importado.status_code == 201, importado.text
    assert repetido.status_code == 409
    assert reemplazado.status_code == 201
    assert (conciliacion["supervision"]["cargados"], conciliacion["supervision"]["enviados"]) == (
        5,
        5,
    )
    assert (
        conciliacion["productos"]["cargados"],
        conciliacion["productos"]["enviados"],
        conciliacion["productos"]["no_enviados"],
    ) == (6, 5, 1)
    assert conciliacion["sin_correspondencia"] == 1
    assert [
        (i["mes_id"], i["filas"], i["con_correspondencia"]) for i in conciliacion["por_id"]
    ] == [
        (MES_IDS[0], 6, 6),
        (MES_IDS[1], 4, 4),
        (MES_IDS[2], 1, 0),
    ]
    assert [(a["codigo"], a["mes_id"]) for a in conciliacion["advertencias"]] == [
        ("id_sin_correspondencia", MES_IDS[2])
    ]


def test_la_carga_se_divide_por_filas_y_conserva_el_orden(cliente) -> None:
    client, _ = cliente
    client.put(
        "/mowa-mes/configuracion",
        json={
            "limite_mensual": 2_500_000,
            "whatsapp_contacto": "900000123",
            "registros_por_archivo": 7,
        },
    )

    previa = _previsualizar(client)
    campana = _crear(client, previa["speech"]["huella"]).json()
    filas = [
        fila
        for archivo in campana["archivos"]
        for fila in _filas_xlsx(
            client.get(f"/mowa-mes/campanas/{campana['id']}/archivos/{archivo['numero']}").content
        )
    ]

    assert previa["archivos_previstos_por_filas"] == [
        {"numero": 1, "filas": 7, "supervision": 5},
        {"numero": 2, "filas": 4, "supervision": 0},
    ]
    assert [(a["filas"], a["supervision"]) for a in campana["archivos"]] == [(7, 5), (4, 0)]
    assert [f[2] for f in filas] == [
        *[f"0000000{i}" for i in range(1, 6)],
        "10000001",
        "10000002",
        "10000003",
        "10000006",
        "10000007",
        "10000008",
    ]


def test_limite_mensual_y_confirmacion(cliente) -> None:
    client, _ = cliente
    client.put(
        "/mowa-mes/configuracion", json={"limite_mensual": 5, "whatsapp_contacto": "900000123"}
    )

    previa = _previsualizar(client)
    sin_confirmar = _crear(client, previa["speech"]["huella"])
    confirmada = _crear(client, previa["speech"]["huella"], confirmar_limite=True)

    assert [a["codigo"] for a in previa["advertencias"]] == ["limite_mensual_excedido"]
    assert sin_confirmar.status_code == 409
    assert confirmada.status_code == 201
    assert confirmada.json()["confirmo_limite"] is True


def test_si_el_speech_cambia_despues_de_previsualizar_no_se_crea_nada(cliente) -> None:
    client, engine = cliente
    partes = [
        {"segmento": p.segmento.value, "parte_1": p.parte_1, "parte_2": p.parte_2}
        for p in speech_del_documento()
    ]
    version = client.post(
        "/mowa-mes/speech", json={"nombre": f"{PREFIJO}v1", "partes": partes}
    ).json()

    previa = _previsualizar(client, speech_id=version["id"])
    partes[0]["parte_2"] = ". Texto sintetico cambiado."
    editada = client.put(
        f"/mowa-mes/speech/{version['id']}", json={"nombre": f"{PREFIJO}v1", "partes": partes}
    )
    rechazada = _crear(client, previa["speech"]["huella"], speech_id=version["id"])

    assert editada.status_code == 200
    assert rechazada.status_code == 409
    with engine.connect() as cx:
        creadas = cx.execute(
            select(func.count()).select_from(_CAMPANA).where(_CAMPANA.c.fecha_corte == FECHA)
        ).scalar_one()
    assert creadas == 0
    assert client.get(f"/mowa-mes/speech/{version['id']}").json()["usada"] is False


def test_sin_whatsapp_la_creacion_responde_400(cliente) -> None:
    client, _ = cliente
    client.put(
        "/mowa-mes/configuracion", json={"limite_mensual": 2_500_000, "whatsapp_contacto": None}
    )

    previa = _previsualizar(client)
    creada = _crear(client, previa["speech"]["huella"])

    assert [e["codigo"] for e in previa["errores"]] == ["falta_whatsapp"]
    assert creada.status_code == 400


def test_un_documento_no_estandar_se_carga_se_advierte_y_se_guarda(cliente) -> None:
    client, engine = cliente
    solo_carne = {"filtros": ["pagare:igual:000000000000000009"]}

    previa = _previsualizar(client, **solo_carne)
    creada = _crear(client, previa["speech"]["huella"], **solo_carne).json()
    cargadas = RepositorioCampanasMowaMesPostgres(engine).filas_cargadas(creada["id"])

    assert previa["excluidos"] == 0
    assert previa["advertencias_por_codigo"] == [
        {"codigo": "documento_no_estandar", "tipo": "advertencia", "cantidad": 1}
    ]
    assert creada["advertencias"] == 1
    assert [(f.dni, f.advertencias) for f in cargadas if not f.supervision] == [
        ("ZZCE123456", (CodigoMowaMes.DOCUMENTO_NO_ESTANDAR,))
    ]
