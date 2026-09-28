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
import threading
import unicodedata
from datetime import date
from decimal import Decimal

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError

from app.adapters.input.lector_calamine import LectorCalamine
from app.adapters.persistence.db import get_engine
from app.adapters.persistence.modelos import (
    Carga,
    CargaAuditoria,
    MowaMesArchivo,
    MowaMesCampana,
    MowaMesSpeechVersion,
)
from app.adapters.persistence.repositorio_campanas_mowa_mes_postgres import (
    CLAVE_BLOQUEO_IMPORTACION_REPORTES,
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
from app.core.entities.mowa_mes_reporte import COLUMNAS_REPORTE, FilaReporte
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
                "tarifa_sms": "0.02",
                "plantilla_nombre_archivo": "",  # vacia: la de por defecto
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


def _reporte(filas: list[tuple[int, tuple]], estado_de=None) -> bytes:
    """El reporte de MES; `estado_de(posicion)` da el estado de cada fila (por defecto enviado)."""
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "Hoja1"
    hoja.append(list(COLUMNAS_REPORTE))
    for posicion, (mes_id, (numero, mensaje, dni)) in enumerate(filas):
        estado = "enviado" if estado_de is None else estado_de(posicion)
        hoja.append(
            [mes_id, str(numero), _como_mes(mensaje), "02/06/99", dni, estado, "Nro. LARGO", "u"]
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
    assert sin_confirmar.json()["codigo"] == "limite_excedido"
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
    assert rechazada.json()["codigo"] == "huella_cambiada"
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


def test_cadena_completa_con_estados_distintos_de_enviado(cliente) -> None:
    # E-1 de punta a punta: lo que MES reporta con otro estado empareja, pero no
    # cuenta como enviado; las cifras por id siguen contando lo emparejado.
    client, _ = cliente
    previa = _previsualizar(client)
    campana = _crear(client, previa["speech"]["huella"]).json()
    filas = _filas_xlsx(client.get(f"/mowa-mes/campanas/{campana['id']}/archivos/1").content)
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "Hoja1"
    hoja.append(list(COLUMNAS_REPORTE))
    for posicion, (numero, mensaje, dni) in enumerate(filas):
        estado = "enviado" if posicion < 5 else ("fallido" if posicion % 2 else "Enviado ")
        hoja.append(
            [MES_IDS[0], str(numero), _como_mes(mensaje), "02/06/99", dni, estado, "L", "u"]
        )
    buffer = io.BytesIO()
    libro.save(buffer)

    importado = client.post(
        f"/mowa-mes/campanas/{campana['id']}/reportes",
        files={"archivo": ("reporte.xlsx", buffer.getvalue())},
    )
    conciliacion = client.get(f"/mowa-mes/campanas/{campana['id']}/conciliacion").json()

    assert importado.status_code == 201, importado.text
    assert (conciliacion["supervision"]["cargados"], conciliacion["supervision"]["enviados"]) == (
        5,
        5,
    )
    assert (
        conciliacion["productos"]["cargados"],
        conciliacion["productos"]["enviados"],
        conciliacion["productos"]["no_enviados"],
    ) == (6, 3, 3)
    assert conciliacion["productos"]["por_estado"] == [
        {"estado": "Enviado", "cantidad": 3},
        {"estado": "fallido", "cantidad": 3},
    ]
    assert (conciliacion["total"]["enviados"], conciliacion["total"]["no_enviados"]) == (8, 3)
    assert conciliacion["sin_correspondencia"] == 0
    assert conciliacion["por_id"] == [
        {"mes_id": MES_IDS[0], "filas": 11, "con_correspondencia": 11}
    ]
    assert conciliacion["advertencias"] == []


def test_limite_mensual_de_un_mes_sin_campanas(cliente) -> None:
    client, _ = cliente

    cuerpo = client.get("/mowa-mes/limite-mensual", params={"mes": "2099-07"}).json()

    assert cuerpo == {
        "mes": "2099-07",
        "limite": 2_500_000,
        "cargados_mes": 0,
        "esta_campana": 0,
        "total": 0,
        "disponible": 2_500_000,
        "excedido": False,
        "costo_mes": "0.0000",
        "campanas_sin_tarifa": 0,
        "costo_esta_campana": None,
        "costo_total": "0.0000",
    }


def test_la_muestra_de_la_previsualizacion_trae_la_supervision_primero(cliente) -> None:
    # P1: lo que ve la pantalla antes de crear nada, no el archivo ya escrito.
    client, _ = cliente

    previa = _previsualizar(client)
    muestra = previa["muestra"]

    assert len(muestra) == 11  # 5 de supervision + 6 productos, todo cabe en la muestra de 20
    assert [f["supervision"] for f in muestra] == [True] * 5 + [False] * 6
    assert [f["dni"] for f in muestra[:5]] == [f"0000000{i}" for i in range(1, 6)]
    assert {f["mensaje"] for f in muestra[:5]} == {muestra[5]["mensaje"]}
    assert all(f["largo"] == len(f["mensaje"]) for f in muestra)
    assert muestra[5]["pagare"] == "000000000000000001"


def test_sin_supervisores_la_previsualizacion_avisa_y_la_creacion_responde_400(cliente) -> None:
    # P2: la campana no se crea sin supervisores (RF-37), pero la previsualizacion no es 4xx.
    client, _ = cliente
    assert (
        client.put(
            "/supervisores",
            json={"procedencias": ["Caja Cusco", "nuestra empresa"], "supervisores": []},
        ).status_code
        == 200
    )

    previa = _previsualizar(client)
    creada = _crear(client, previa["speech"]["huella"])

    assert previa["puede_crear"] is False
    assert [e["codigo"] for e in previa["errores"]] == ["sin_supervisores"]
    assert previa["supervision_cargados"] == 0
    assert creada.status_code == 400


def test_sin_productos_cargables_la_previsualizacion_avisa_y_la_creacion_responde_400(
    cliente,
) -> None:
    # P2: una seleccion sin ningun producto cargable tampoco genera supervision (RF-37).
    client, _ = cliente
    sin_productos = {"filtros": ["pagare:igual:999999999999999999"]}

    previa = _previsualizar(client, **sin_productos)
    creada = _crear(client, previa["speech"]["huella"], **sin_productos)

    assert (previa["disponibles"], previa["evaluados"]) == (0, 0)
    assert previa["puede_crear"] is False
    assert [e["codigo"] for e in previa["errores"]] == ["sin_productos_cargables"]
    assert previa["muestra"] == []
    assert creada.status_code == 400


def test_sin_version_vigente_para_la_fecha_de_corte_responde_404(cliente) -> None:
    # P8: una fecha de corte sin ingesta, contra el repositorio de cartera real.
    client, _ = cliente
    sin_sabana = date(2099, 8, 1)
    assert sin_sabana != FECHA

    respuesta = client.post(
        "/mowa-mes/campanas/previsualizacion",
        json={**CUERPO, "fecha_corte": sin_sabana.isoformat()},
    )

    assert respuesta.status_code == 404
    assert str(sin_sabana) in respuesta.json()["detail"]


# --- B8: tarifa, costos y nombre de los archivos (RF-MM-23 a RF-MM-25) ----


def _guardado(engine, campana_id: int) -> dict:
    """Lo que dejo la base en la fila de la campana, sin pasar por la API."""
    with engine.connect() as cx:
        fila = cx.execute(select(_CAMPANA).where(_CAMPANA.c.id == campana_id)).one()
    return {
        "tarifa_sms": fila.tarifa_sms,
        "costo_estimado": fila.costo_estimado,
        "enviados_conciliados": fila.enviados_conciliados,
    }


def _campana_anterior(engine, mes_envio: date = date(2099, 6, 2)) -> int:
    """Una campana como las de antes de RF-MM-23: sin tarifa ni costo. Fecha de corte 2099."""
    with engine.begin() as cx:
        speech = cx.execute(select(_SPEECH.c.id).where(_SPEECH.c.original)).scalar_one()
        return cx.execute(
            insert(_CAMPANA)
            .values(
                fecha_corte=FECHA,
                cantidad=1,
                tipo_carga="masiva",
                descripcion="zz campana anterior",
                salida="numero_largo",
                herramientas={},
                programacion="hora_determinada",
                fecha_generacion=FECHA,
                fecha_envio=mes_envio,
                mes_imputacion=mes_envio.replace(day=1),
                speech_version_id=speech,
                speech_huella="0" * 64,
                supervisores=[],
                disponibles=1,
                evaluados=1,
                productos_cargados=1,
                supervision_cargados=0,
                total_cargados=1,
                excluidos=0,
                advertencias=0,
            )
            .returning(_CAMPANA.c.id)
        ).scalar_one()


def _crear_campana(client, **extra) -> dict:
    previa = _previsualizar(client, **extra)
    creada = _crear(client, previa["speech"]["huella"], **extra)
    assert creada.status_code == 201, creada.text
    return creada.json()


def _filas_de_la_campana(client, campana: dict) -> list[tuple[int, tuple]]:
    """Las filas cargadas de cada archivo, listas para armar un reporte de MES."""
    filas: list[tuple] = []
    for archivo in campana["archivos"]:
        descarga = client.get(f"/mowa-mes/campanas/{campana['id']}/archivos/{archivo['numero']}")
        filas.extend(_filas_xlsx(descarga.content))
    return filas


def _importar(client, campana_id: int, contenido: bytes, reemplazar: bool = False):
    return client.post(
        f"/mowa-mes/campanas/{campana_id}/reportes",
        files={"archivo": ("reporte.xlsx", contenido)},
        data={"reemplazar": "true"} if reemplazar else {},
    )


def _configurar(client, **cambios) -> None:
    respuesta = client.put("/mowa-mes/configuracion", json={"limite_mensual": 2_500_000, **cambios})
    assert respuesta.status_code == 200, respuesta.text


def test_la_base_tiene_los_defectos_de_la_tarifa_y_la_plantilla(cliente) -> None:
    _, engine = cliente

    with engine.connect() as cx:
        defectos = dict(
            cx.execute(
                text(
                    "SELECT column_name, column_default FROM information_schema.columns "
                    "WHERE table_name = 'mowa_mes_configuracion' "
                    "AND column_name IN ('tarifa_sms', 'plantilla_nombre_archivo')"
                )
            ).all()
        )

    assert defectos["tarifa_sms"] == "0.02"
    assert defectos["plantilla_nombre_archivo"].startswith(
        "'mowa_mes_campana_{campana}_{archivo}_de_{total}'"
    )


def test_la_tarifa_y_la_plantilla_se_guardan_exactas(cliente) -> None:
    client, engine = cliente

    _configurar(client, tarifa_sms="0.0125", plantilla_nombre_archivo="Caja_{campana}")
    leida = client.get("/mowa-mes/configuracion").json()

    assert (leida["tarifa_sms"], leida["plantilla_nombre_archivo"]) == ("0.0125", "Caja_{campana}")
    with engine.connect() as cx:
        guardada = cx.execute(text("SELECT tarifa_sms FROM mowa_mes_configuracion")).scalar_one()
    assert guardada == Decimal("0.0125")  # NUMERIC exacto, sin float de por medio
    # Un PUT sin esos campos los conserva; la base rechaza una tarifa negativa aunque la API no.
    _configurar(client)
    assert client.get("/mowa-mes/configuracion").json()["tarifa_sms"] == "0.0125"
    with pytest.raises(IntegrityError), engine.begin() as cx:
        cx.execute(text("UPDATE mowa_mes_configuracion SET tarifa_sms = -0.01"))


def test_crear_congela_la_tarifa_y_el_costo_y_el_costo_del_mes_no_se_recalcula(cliente) -> None:
    client, engine = cliente
    _configurar(client, tarifa_sms="0.05")

    campana = _crear_campana(client)
    _configurar(client, tarifa_sms="0.10")
    leida = client.get(f"/mowa-mes/campanas/{campana['id']}").json()
    lista = [
        c for c in client.get("/mowa-mes/campanas").json()["campanas"] if c["id"] == campana["id"]
    ]
    limite = client.get("/mowa-mes/limite-mensual", params={"mes": "2099-06"}).json()
    nueva = _previsualizar(client)

    assert campana["total_cargados"] == 11
    for cuerpo in (campana, leida, lista[0]):
        assert cuerpo["tarifa_sms"] == "0.0500"
        assert cuerpo["costo_estimado"] == "0.5500"  # 11 SMS a 0.05
        assert cuerpo["costo_estimado_estado"] == "calculado"
    assert _guardado(engine, campana["id"])["tarifa_sms"] == Decimal("0.0500")
    assert _guardado(engine, campana["id"])["costo_estimado"] == Decimal("0.5500")
    # Con la tarifa actual (0.10) el mes saldria 1.1000: se suma lo guardado.
    assert limite["costo_mes"] == "0.5500"
    assert (nueva["tarifa_sms"], nueva["costo_estimado"]) == ("0.1000", "1.1000")
    assert nueva["limite"]["costo_mes"] == "0.5500"
    assert nueva["limite"]["costo_total"] == "1.6500"


def test_el_costo_del_mes_omite_las_campanas_sin_tarifa_y_dice_cuantas(cliente) -> None:
    client, engine = cliente
    campana = _crear_campana(client)  # 11 SMS a 0.02 = 0.22
    antigua = _campana_anterior(engine)
    otra_antigua = _campana_anterior(engine)
    otro_mes = _campana_anterior(engine, mes_envio=date(2099, 7, 2))

    limite = client.get("/mowa-mes/limite-mensual", params={"mes": "2099-06"}).json()
    julio = client.get("/mowa-mes/limite-mensual", params={"mes": "2099-07"}).json()
    detalle = client.get(f"/mowa-mes/campanas/{antigua}").json()

    assert (limite["costo_mes"], limite["campanas_sin_tarifa"]) == ("0.2200", 2)
    assert (julio["costo_mes"], julio["campanas_sin_tarifa"]) == ("0.0000", 1)
    assert campana["costo_estimado"] == "0.2200"
    assert {antigua, otra_antigua, otro_mes}.isdisjoint({campana["id"]})
    assert (detalle["tarifa_sms"], detalle["costo_estimado"]) == (None, None)
    assert detalle["costo_estimado_estado"] == "no_disponible"
    assert detalle["costo_real_estado"] == "no_disponible"
    assert detalle["costo_real"] is None
    assert detalle["archivos"] == []


def test_una_campana_anterior_con_reporte_sigue_sin_costo_real_pero_su_conciliacion_cuenta(
    cliente,
) -> None:
    client, engine = cliente
    antigua = _campana_anterior(engine)
    contenido = _reporte([(MES_IDS[0], (900000777, "ZZPRUEBA sin correspondencia", "77777777"))])

    importado = _importar(client, antigua, contenido)
    leida = client.get(f"/mowa-mes/campanas/{antigua}").json()

    assert importado.status_code == 201, importado.text
    conciliacion = importado.json()
    assert (conciliacion["costo_real"], conciliacion["costo_real_estado"]) == (
        None,
        "no_disponible",
    )
    assert conciliacion["tarifa_sms"] is None
    assert conciliacion["sin_correspondencia"] == 1  # las cifras de enviados salen en vivo
    assert (leida["costo_real"], leida["costo_real_estado"]) == (None, "no_disponible")


def test_el_costo_real_es_pendiente_sin_reporte_y_es_enviados_por_la_tarifa_congelada(
    cliente,
) -> None:
    client, engine = cliente
    _configurar(client, tarifa_sms="0.05")
    campana = _crear_campana(client)
    _configurar(client, tarifa_sms="0.10")
    filas = _filas_de_la_campana(client, campana)
    assert client.get(f"/mowa-mes/campanas/{campana['id']}").json()["costo_real_estado"] == (
        "pendiente"
    )
    assert _guardado(engine, campana["id"])["enviados_conciliados"] is None  # nunca 0

    # 11 cargadas: 8 enviadas y 3 no. El costo real cuenta solo las 8, a la tarifa de 0.05.
    reporte = _reporte(
        [(MES_IDS[0], f) for f in filas], estado_de=lambda i: "enviado" if i < 8 else "fallido"
    )
    conciliacion = _importar(client, campana["id"], reporte).json()
    leida = client.get(f"/mowa-mes/campanas/{campana['id']}").json()

    assert conciliacion["total"]["enviados"] == 8
    assert (conciliacion["costo_real"], conciliacion["costo_real_estado"]) == (
        "0.4000",
        "calculado",
    )
    assert (leida["costo_real"], leida["costo_real_estado"]) == ("0.4000", "calculado")
    assert _guardado(engine, campana["id"])["enviados_conciliados"] == 8


def test_un_reporte_con_cero_enviados_guarda_cero_no_null(cliente) -> None:
    client, engine = cliente
    campana = _crear_campana(client)
    filas = _filas_de_la_campana(client, campana)

    _importar(
        client,
        campana["id"],
        _reporte([(MES_IDS[0], f) for f in filas], estado_de=lambda i: "fallido"),
    )
    leida = client.get(f"/mowa-mes/campanas/{campana['id']}").json()

    assert _guardado(engine, campana["id"])["enviados_conciliados"] == 0
    assert (leida["costo_real"], leida["costo_real_estado"]) == ("0.0000", "calculado")


def test_enviados_conciliados_siempre_coincide_con_la_conciliacion(cliente) -> None:
    """Importar, reemplazar, importar un segundo id de MES y mover un id a otra campana:
    despues de cada paso el conteo guardado es igual a los enviados de la conciliacion."""
    client, engine = cliente

    def guardado(campana_id: int):
        return _guardado(engine, campana_id)["enviados_conciliados"]

    def enviados(campana_id: int) -> int:
        cuerpo = client.get(f"/mowa-mes/campanas/{campana_id}/conciliacion").json()
        return cuerpo["total"]["enviados"]

    def costo_real(campana_id: int) -> tuple:
        cuerpo = client.get(f"/mowa-mes/campanas/{campana_id}").json()
        conciliacion = client.get(f"/mowa-mes/campanas/{campana_id}/conciliacion").json()
        assert (cuerpo["costo_real"], cuerpo["costo_real_estado"]) == (
            conciliacion["costo_real"],
            conciliacion["costo_real_estado"],
        )
        return cuerpo["costo_real"], cuerpo["costo_real_estado"]

    a = _crear_campana(client)
    b = _crear_campana(client)
    filas = _filas_de_la_campana(client, a)  # b tiene las mismas filas
    assert len(filas) == 11
    assert guardado(a["id"]) is None and costo_real(a["id"]) == (None, "pendiente")

    # 1) Importar el primer id: 6 filas, todas enviadas.
    _importar(client, a["id"], _reporte([(MES_IDS[0], f) for f in filas[:6]]))
    assert guardado(a["id"]) == enviados(a["id"]) == 6
    assert costo_real(a["id"]) == ("0.1200", "calculado")

    # 2) Un segundo id de MES para las otras 5 filas.
    _importar(client, a["id"], _reporte([(MES_IDS[1], f) for f in filas[6:]]))
    assert guardado(a["id"]) == enviados(a["id"]) == 11

    # 3) Reemplazar el primer id con solo 2 enviadas de sus 6.
    _importar(
        client,
        a["id"],
        _reporte(
            [(MES_IDS[0], f) for f in filas[:6]],
            estado_de=lambda i: "enviado" if i < 2 else "fallido",
        ),
        reemplazar=True,
    )
    assert guardado(a["id"]) == enviados(a["id"]) == 7
    assert costo_real(a["id"]) == ("0.1400", "calculado")

    # 4) Mover un id a otra campana: b se queda con MES_IDS[0] y a pierde 2 enviadas.
    _importar(client, b["id"], _reporte([(MES_IDS[0], f) for f in filas[:6]]), reemplazar=True)
    assert guardado(b["id"]) == enviados(b["id"]) == 6
    assert guardado(a["id"]) == enviados(a["id"]) == 5  # solo queda el segundo id
    assert costo_real(b["id"]) == ("0.1200", "calculado")

    # 5) Mover tambien el otro: a se queda sin reportes y vuelve a pendiente (null, no 0).
    _importar(client, b["id"], _reporte([(MES_IDS[1], f) for f in filas[6:]]), reemplazar=True)
    assert guardado(b["id"]) == enviados(b["id"]) == 11
    assert guardado(a["id"]) is None
    assert client.get(f"/mowa-mes/campanas/{a['id']}/conciliacion").json()["reportes"] == []
    assert costo_real(a["id"]) == (None, "pendiente")


def test_si_la_importacion_falla_no_queda_ni_el_reporte_ni_el_conteo_a_medias(cliente) -> None:
    client, engine = cliente
    campana = _crear_campana(client)
    repositorio = RepositorioCampanasMowaMesPostgres(engine)
    filas = _filas_de_la_campana(client, campana)
    reporte = _reporte([(MES_IDS[0], f) for f in filas])
    assert _importar(client, campana["id"], reporte).status_code == 201
    antes = _guardado(engine, campana["id"])["enviados_conciliados"]
    assert antes == 11

    def contar_y_fallar(cargadas, reportes):
        raise RuntimeError("falla despues de guardar las filas del reporte")

    nuevas = {
        MES_IDS[0]: [
            FilaReporte(
                2, MES_IDS[0], "900000101", "otro", "02/06/99", "10000001", "fallido", "L", "u"
            )
        ]
    }
    with pytest.raises(RuntimeError):
        repositorio.guardar_reportes(campana["id"], "roto.xlsx", nuevas, contar_y_fallar)

    assert _guardado(engine, campana["id"])["enviados_conciliados"] == antes
    assert [r.nombre_archivo for r in repositorio.reportes(campana["id"])] == ["reporte.xlsx"]
    assert len(repositorio.filas_reporte(campana["id"])) == 11


def test_una_segunda_importacion_espera_al_lock_global_y_no_falla(cliente) -> None:
    """Un id de MES es unico entre campanas: dos importaciones de campanas distintas pueden
    reclamar el mismo a la vez, asi que se serializan (docs/mowa-mes.md §16.1).

    La prueba espera 1,5 s a que la importacion NO termine. Solo puede fallar si el lock no
    funciona, pero si algun dia falla por tiempo en una maquina lenta, se corrige con una
    espera por evento o una sincronizacion explicita (por ejemplo, consultar
    `pg_stat_activity` hasta ver la sesion esperando el lock), no subiendo el tiempo.
    """
    client, engine = cliente
    campana = _crear_campana(client)
    reporte = _reporte([(MES_IDS[0], f) for f in _filas_de_la_campana(client, campana)])
    resultado: dict = {}

    def importar() -> None:
        resultado["respuesta"] = _importar(client, campana["id"], reporte)

    with engine.connect() as ocupada:
        # Otra importacion en curso: tiene el lock hasta que termina su transaccion.
        ocupada.execute(select(func.pg_advisory_xact_lock(CLAVE_BLOQUEO_IMPORTACION_REPORTES)))
        hilo = threading.Thread(target=importar)
        hilo.start()
        hilo.join(timeout=1.5)

        assert hilo.is_alive(), "la importacion debia esperar al lock, no seguir de largo"
        assert "respuesta" not in resultado
        assert _guardado(engine, campana["id"])["enviados_conciliados"] is None
        ocupada.rollback()  # termina la transaccion: suelta el lock

    hilo.join(timeout=30)

    assert not hilo.is_alive()
    assert resultado["respuesta"].status_code == 201, resultado["respuesta"].text
    assert _guardado(engine, campana["id"])["enviados_conciliados"] == 11


def test_el_conteo_de_enviados_no_puede_pasar_de_lo_cargado(cliente) -> None:
    client, engine = cliente
    campana = _crear_campana(client)

    with pytest.raises(IntegrityError), engine.begin() as cx:
        cx.execute(
            update(_CAMPANA)
            .where(_CAMPANA.c.id == campana["id"])
            .values(enviados_conciliados=campana["total_cargados"] + 1)
        )
    with pytest.raises(IntegrityError), engine.begin() as cx:
        cx.execute(
            update(_CAMPANA).where(_CAMPANA.c.id == campana["id"]).values(enviados_conciliados=-1)
        )


def test_los_nombres_se_guardan_con_cada_archivo_y_la_descarga_los_entrega(cliente) -> None:
    client, engine = cliente
    _configurar(client, registros_por_archivo=7)  # 11 filas: 7 y 4

    campana = _crear_campana(client)
    nombres = [a["nombre"] for a in campana["archivos"]]
    descargas = [client.get(f"/mowa-mes/campanas/{campana['id']}/archivos/{n}") for n in (1, 2)]

    assert nombres == [
        f"mowa_mes_campana_{campana['id']}_1_de_2.xlsx",
        f"mowa_mes_campana_{campana['id']}_2_de_2.xlsx",
    ]
    for nombre, descarga in zip(nombres, descargas, strict=True):
        assert descarga.headers["content-disposition"] == (
            f"attachment; filename=\"{nombre}\"; filename*=UTF-8''{nombre}"
        )
    with engine.connect() as cx:
        guardados = (
            cx.execute(
                select(MowaMesArchivo.__table__.c.nombre)
                .where(MowaMesArchivo.__table__.c.campana_id == campana["id"])
                .order_by(MowaMesArchivo.__table__.c.numero)
            )
            .scalars()
            .all()
        )
    assert guardados == nombres


def test_un_cambio_de_plantilla_en_la_configuracion_no_cambia_la_descarga_de_lo_ya_creado(
    cliente,
) -> None:
    client, _ = cliente
    _configurar(client, plantilla_nombre_archivo="Antes_{campana}")
    campana = _crear_campana(client)

    _configurar(client, plantilla_nombre_archivo="Despues_{campana}")
    descarga = client.get(f"/mowa-mes/campanas/{campana['id']}/archivos/1")
    otra = _crear_campana(client)

    assert campana["archivos"][0]["nombre"] == f"Antes_{campana['id']}.xlsx"
    assert f"Antes_{campana['id']}.xlsx" in descarga.headers["content-disposition"]
    assert client.get(f"/mowa-mes/campanas/{campana['id']}").json()["archivos"][0]["nombre"] == (
        f"Antes_{campana['id']}.xlsx"
    )
    assert otra["archivos"][0]["nombre"] == f"Despues_{otra['id']}.xlsx"


def test_la_plantilla_de_la_campana_con_tildes_se_descarga_con_los_dos_nombres(cliente) -> None:
    client, _ = cliente

    campana = _crear_campana(client, plantilla_nombre_archivo="Cobranza_mañana_{fecha_envio}")
    descarga = client.get(f"/mowa-mes/campanas/{campana['id']}/archivos/1")

    assert campana["archivos"][0]["nombre"] == "Cobranza_mañana_2099-06-02.xlsx"
    assert descarga.headers["content-disposition"] == (
        'attachment; filename="Cobranza_manana_2099-06-02.xlsx"; '
        "filename*=UTF-8''Cobranza_ma%C3%B1ana_2099-06-02.xlsx"
    )


def test_una_plantilla_invalida_en_la_campana_responde_400_y_no_crea_nada(cliente) -> None:
    client, engine = cliente
    previa = _previsualizar(client)

    creada = _crear(client, previa["speech"]["huella"], plantilla_nombre_archivo="caja_{nombre}")

    assert creada.status_code == 400
    assert "{nombre}" in creada.json()["detail"]
    with engine.connect() as cx:
        campanas = cx.execute(
            select(func.count()).select_from(_CAMPANA).where(_CAMPANA.c.fecha_corte == FECHA)
        ).scalar_one()
    assert campanas == 0


def test_la_base_impide_dos_archivos_de_una_campana_con_el_mismo_nombre(cliente) -> None:
    client, engine = cliente
    _configurar(client, registros_por_archivo=7)
    campana = _crear_campana(client)
    tabla = MowaMesArchivo.__table__

    with pytest.raises(IntegrityError), engine.begin() as cx:
        cx.execute(
            update(tabla)
            .where(tabla.c.campana_id == campana["id"], tabla.c.numero == 2)
            .values(nombre=campana["archivos"][0]["nombre"])
        )
    with pytest.raises(IntegrityError), engine.begin() as cx:
        cx.execute(
            update(tabla)
            .where(tabla.c.campana_id == campana["id"], tabla.c.numero == 2)
            .values(nombre="   ")
        )
