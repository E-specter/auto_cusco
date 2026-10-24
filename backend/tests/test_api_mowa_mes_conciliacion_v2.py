"""Una campana con speech v2 hasta la conciliacion, sobre repositorios en memoria (B8).

Es la versión que corre en todos los entornos de `test_mowa_mes_conciliacion_v2_postgres.py`: los
mismos dos escenarios y las mismas cifras, con los servicios reales, el archivo .xlsx escrito y el
reporte leido de verdad, pero sin base de datos. Lo que solo se ve con PostgreSQL (las tablas
`mowa_mes_fila_cargada` y `mowa_mes_reporte_fila`, `enviados_conciliados` en la fila de la campana)
queda en la prueba de integracion.

La cartera trae un producto SIN titular (el 10). Con una v2 creada por `como-v2` desde el Speech
original, que usa el titular, se excluye con `falta_titular`, igual que con la v1; con una v2 que no
lo usa se carga (RF-MM-13) y la conciliacion lo empareja con su fila del reporte. Datos sinteticos.
"""

import io
import re
import unicodedata
from collections import Counter

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.api.mowa_mes import obtener_servicio_mowa_mes
from app.core.entities.mowa_mes_reporte import COLUMNAS_REPORTE
from app.core.services.plataformas.mowa_mes.configuracion import ConfiguracionMowaMesService
from app.core.services.texto_enriquecido.gsm7 import a_gsm7
from app.main import app
from tests.test_api_mowa_mes_campanas import CUERPO, Entorno, _cliente
from tests.test_mowa_mes_campana import producto

IDS = (990_000_001, 990_000_002)
SEGMENTOS = ["preventiva", "1_a_8", "9_a_30", "31_a_60", "61_a_90", "91_a_120"]
SIN_TITULAR = [
    {"tipo": "texto", "valor": "  Cobranza: su cuota venció el "},
    {
        "tipo": "variable",
        "nombre": "fecha_vencimiento_cuota",
        "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
    },
    {"tipo": "texto", "valor": ". ¡Regularice hoy, gracias! "},
]
# El mensaje sale normalizado a GSM-7 (RF-MM-27, T-MM-B9): "venció" sale "vencio". El patron se
# arma con a_gsm7 del texto fijo escrito en SIN_TITULAR, no con un literal copiado de la salida.
MENSAJE_SIN_TITULAR = re.compile(
    re.escape(a_gsm7(SIN_TITULAR[0]["valor"]))
    + r"\d{2}/\d{2}/\d{4}"
    + re.escape(a_gsm7(SIN_TITULAR[2]["valor"]))
)


@pytest.fixture
def entorno() -> Entorno:
    productos = [
        producto(1),
        producto(2, dias_atraso=40),  # 31 a 60: el Speech original usa [whatsapp]
        producto(3),
        producto(4, telefono="12345"),  # telefono_invalido
        producto(5, documento_numero=None),  # falta_documento
        producto(6),
        producto(7),
        producto(8),
        producto(10, titular=None),  # sin titular
    ]
    return Entorno(productos=productos)


@pytest.fixture
def client(entorno: Entorno):
    cliente = _cliente(entorno)
    configuracion = ConfiguracionMowaMesService(entorno.mowa_mes)
    app.dependency_overrides[obtener_servicio_mowa_mes] = lambda: configuracion
    return cliente


def _como_mes(texto: str) -> str:
    """Lo que hace MES al enviar: sin tildes y sin espacios en los extremos."""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c)
    ).strip()


def _guardar_v2(client: TestClient, nombre: str, expresiones: list[dict], **extra) -> int:
    respuesta = client.post(
        "/mowa-mes/speech", json={"nombre": nombre, "expresiones": expresiones, **extra}
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["id"]


def _v2_desde_el_original(client: TestClient) -> int:
    original = next(v for v in client.get("/mowa-mes/speech").json() if v["original"])
    borrador = client.get(f"/mowa-mes/speech/{original['id']}/como-v2").json()
    expresiones = [
        {"segmento": e["segmento"], "expresion": e["expresion"]} for e in borrador["expresiones"]
    ]
    return _guardar_v2(client, "como v2", expresiones, basada_en_id=original["id"])


def _v2_sin_titular(client: TestClient) -> int:
    expresiones = [{"segmento": s, "expresion": {"nodos": SIN_TITULAR}} for s in SEGMENTOS]
    return _guardar_v2(client, "sin titular", expresiones)


def _crear_campana(client: TestClient, speech_id: int | None = None) -> dict:
    extra = {} if speech_id is None else {"speech_id": speech_id}
    previa = client.post("/mowa-mes/campanas/previsualizacion", json={**CUERPO, **extra})
    assert previa.status_code == 200, previa.text
    assert previa.json()["errores"] == [] and previa.json()["puede_crear"] is True
    creada = client.post(
        "/mowa-mes/campanas",
        json={**CUERPO, "speech_huella": previa.json()["speech"]["huella"], **extra},
    )
    assert creada.status_code == 201, creada.text
    return creada.json()


def _por_pagare(filas) -> dict:
    return {int(f.pagare): f for f in filas if f.pagare is not None}


def _reporte_desde_lo_cargado(cargadas, estados: dict, crudos: set) -> tuple[bytes, list]:
    """Una fila de reporte por fila cargada, en dos ids, como `medir_campana_mowa_mes.py`."""
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "Hoja1"
    hoja.append(list(COLUMNAS_REPORTE))
    mitad = len(cargadas) // 2
    filas = []
    for posicion, fila in enumerate(cargadas):
        pagare = None if fila.pagare is None else int(fila.pagare)
        mensaje = fila.mensaje if pagare in crudos else _como_mes(fila.mensaje)
        estado = estados.get(pagare, "enviado")
        mes_id = IDS[0] if posicion < mitad else IDS[1]
        filas.append(
            [mes_id, str(fila.numero), mensaje, "14/09/26", fila.dni, estado, "Nro. LARGO", "u"]
        )
    for fila in filas:
        hoja.append(fila)
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue(), filas


def _importar_y_conciliar(client, entorno, campana, estados, crudos=frozenset()):
    cargadas = entorno.campanas.filas_cargadas(campana["id"])
    contenido, enviadas = _reporte_desde_lo_cargado(cargadas, estados, set(crudos))
    importado = client.post(
        f"/mowa-mes/campanas/{campana['id']}/reportes", files={"archivo": ("r.xlsx", contenido)}
    )
    conciliacion = client.get(f"/mowa-mes/campanas/{campana['id']}/conciliacion")
    assert importado.status_code == 201, importado.text
    assert conciliacion.status_code == 200, conciliacion.text
    return conciliacion.json(), enviadas


def _por_id_esperado(enviadas) -> list[dict]:
    filas = Counter(f[0] for f in enviadas)
    return [{"mes_id": i, "filas": n, "con_correspondencia": n} for i, n in sorted(filas.items())]


def _exclusiones(client, campana) -> list[tuple[int, str]]:
    cuerpo = client.get(f"/mowa-mes/campanas/{campana['id']}/exclusiones").json()
    return sorted((int(e["pagare"]), e["codigo"]) for e in cuerpo["exclusiones"])


def test_una_v2_por_como_v2_sale_como_la_v1_y_se_concilia_entera(client, entorno) -> None:
    de_la_v1 = _crear_campana(client)  # el Speech original: el punto de comparacion
    v2_id = _v2_desde_el_original(client)

    campana = _crear_campana(client, speech_id=v2_id)
    cargadas = entorno.campanas.filas_cargadas(campana["id"])

    # Las mismas filas, mensajes y exclusiones que la v1; la v2 convertida usa el titular, asi que
    # el producto sin titular se excluye igual (RF-MM-13).
    assert (campana["productos_cargados"], campana["supervision_cargados"]) == (6, 5)
    assert campana["total_cargados"] == de_la_v1["total_cargados"] == 11
    assert cargadas == entorno.campanas.filas_cargadas(de_la_v1["id"])
    assert _exclusiones(client, campana) == [
        (4, "telefono_invalido"),
        (5, "falta_documento"),
        (10, "falta_titular"),
    ]
    assert _por_pagare(cargadas)[2].mensaje.endswith("https://wa.me/+51900000123")

    # E-1: con otro estado empatan, cuentan como cargados y no como enviados.
    estados = {2: "fallido", 3: "Enviado ", 6: "pendiente"}
    conciliacion, enviadas = _importar_y_conciliar(client, entorno, campana, estados)

    assert conciliacion["sin_correspondencia"] == 0 and conciliacion["advertencias"] == []
    assert conciliacion["por_id"] == _por_id_esperado(enviadas)
    assert conciliacion["supervision"]["cargados"] == conciliacion["supervision"]["enviados"] == 5
    assert (
        conciliacion["productos"]["cargados"],
        conciliacion["productos"]["enviados"],
        conciliacion["productos"]["no_enviados"],
    ) == (6, 4, 2)
    assert conciliacion["productos"]["por_estado"] == [
        {"estado": "Enviado", "cantidad": 1},
        {"estado": "enviado", "cantidad": 3},
        {"estado": "fallido", "cantidad": 1},
        {"estado": "pendiente", "cantidad": 1},
    ]
    assert (conciliacion["total"]["cargados"], conciliacion["total"]["enviados"]) == (11, 9)
    assert conciliacion["total"]["no_enviados"] == 2


def test_una_v2_sin_titular_carga_un_producto_sin_titular_y_se_concilia_entera(
    client, entorno
) -> None:
    v2_id = _v2_sin_titular(client)

    campana = _crear_campana(client, speech_id=v2_id)
    cargadas = entorno.campanas.filas_cargadas(campana["id"])
    por_pagare = _por_pagare(cargadas)

    # El producto 10 no tiene titular y esta cargado: RF-MM-13 mira lo que la v2 usa.
    assert (campana["productos_cargados"], campana["supervision_cargados"]) == (7, 5)
    assert campana["total_cargados"] == 12
    assert _exclusiones(client, campana) == [(4, "telefono_invalido"), (5, "falta_documento")]
    sin_titular = por_pagare[10]
    assert sin_titular.supervision is False
    assert MENSAJE_SIN_TITULAR.fullmatch(sin_titular.mensaje)
    assert sin_titular.mensaje != _como_mes(sin_titular.mensaje)  # tildes y espacios de extremos
    assert sin_titular.mensaje == por_pagare[1].mensaje  # no lleva titular: igual al del segmento

    # Dos fallidos y uno en mayusculas con espacios; los productos 7 y 10 con su mensaje sin
    # normalizar (la normalizacion es de los dos lados).
    estados = {2: "fallido", 3: "Enviado ", 8: "fallido"}
    conciliacion, enviadas = _importar_y_conciliar(
        client, entorno, campana, estados, crudos={7, 10}
    )

    assert conciliacion["sin_correspondencia"] == 0 and conciliacion["advertencias"] == []
    assert conciliacion["por_id"] == _por_id_esperado(enviadas)
    assert conciliacion["supervision"]["cargados"] == conciliacion["supervision"]["enviados"] == 5
    assert (
        conciliacion["productos"]["cargados"],
        conciliacion["productos"]["enviados"],
        conciliacion["productos"]["no_enviados"],
    ) == (7, 5, 2)  # enviados: 1, 3 («Enviado »), 6, 7 y 10; fallidos: 2 y 8
    assert conciliacion["productos"]["por_estado"] == [
        {"estado": "Enviado", "cantidad": 1},
        {"estado": "enviado", "cantidad": 4},
        {"estado": "fallido", "cantidad": 2},
    ]
    assert (conciliacion["total"]["cargados"], conciliacion["total"]["enviados"]) == (12, 10)
    assert conciliacion["total"]["no_enviados"] == 2
    # El producto sin titular quedo emparejado con su fila: sin esa fila serian 9 enviados.
    fila_del_10 = next(f for f in enviadas if f[1] == str(sin_titular.numero))
    assert (fila_del_10[4], fila_del_10[5]) == (sin_titular.dni, "enviado")
