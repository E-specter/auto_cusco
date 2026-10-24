"""Una campana con speech v2 hasta la conciliacion, en PostgreSQL real (B8). ESCRITA, NO CORRIDA.

Corre solo con AUTO_CUSCO_DB_TESTS=1 y la base migrada. Cierra el hueco de
`test_cadena_completa_con_una_v2_por_http`, que crea la campana y descarga pero no importa el
reporte ni concilia: aqui, con una v2, se arma el reporte de enviados **desde lo cargado**
(`mowa_mes_fila_cargada`, como hace `scripts/medir_campana_mowa_mes.py`), se importa por HTTP y se
concilia.

Reusa el entorno de `test_mowa_mes_campanas_postgres.py` (sabana sintetica de la fecha 2099-06-01,
configuracion y supervisores que se restituyen, limpieza de las campanas de esa fecha y de las
versiones de speech con el prefijo de prueba) con una sabana propia: la de siempre sin el
producto 9 (el carne) y con el 10, que **no tiene titular**. Con el mismo dato:

- una v2 creada por `como-v2` desde el Speech original usa el titular, asi que el producto 10 se
  excluye con `falta_titular` (igual que la v1), y el resto sale igual que con la v1;
- una v2 que no usa el titular lo carga (RF-MM-13) y la conciliacion lo empareja con su fila.

Los mensajes de la v2 sin titular llevan tildes y espacios en los extremos; MES los quita al
enviar, asi que el reporte los trae normalizados (y una fila, tal cual: la normalizacion es de los
dos lados). Numeros 900000xxx y ids de MES 990000001 y 990000002.
"""

import io
import os
import re
from collections import Counter

import openpyxl
import pytest
from sqlalchemy import select, text

from app.adapters.persistence.modelos import MowaMesCampana
from app.adapters.persistence.repositorio_campanas_mowa_mes_postgres import (
    RepositorioCampanasMowaMesPostgres,
)
from app.core.entities.mowa_mes_reporte import COLUMNAS_REPORTE
from app.core.services.texto_enriquecido.gsm7 import a_gsm7
from tests import test_mowa_mes_campanas_postgres as base
from tests.test_mowa_mes_campanas_postgres import (
    MES_IDS,
    PREFIJO,
    _como_mes,
    _filas_xlsx,
    _producto,
)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

_CAMPANA = MowaMesCampana.__table__
PRODUCTOS_B8 = [
    _producto(1),
    _producto(2, **{"Dias Atraso Hoy": 40.0}),  # 31 a 60: el Speech original usa [whatsapp]
    _producto(3),
    _producto(4, **{"Teléfono": 12345.0}),  # telefono_invalido
    _producto(5, DniRuc=None),  # falta_documento
    _producto(6),
    _producto(7),
    _producto(8),
    _producto(10, Titular=None),  # sin titular: solo una v2 que no lo use lo carga
]
# Sin el filtro que apartaba al producto 9 (el carne): ya no esta en la sabana.
CUERPO = {k: v for k, v in base.CUERPO.items() if k != "filtros"}
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
# El mensaje sale normalizado a GSM-7 (RF-MM-27, T-MM-B9): "venció" sale "vencio" y "¡" se borra. El
# patron se arma con a_gsm7 del texto fijo escrito en SIN_TITULAR, no con un literal copiado de la
# salida (igual que en test_api_mowa_mes_conciliacion_v2.py).
MENSAJE_SIN_TITULAR = re.compile(
    re.escape(a_gsm7(SIN_TITULAR[0]["valor"]))
    + r"\d{2}/\d{2}/\d{4}"
    + re.escape(a_gsm7(SIN_TITULAR[2]["valor"]))
)

# La fixture `cliente` (sabana, supervisores, configuracion y limpieza) es la de las campanas.
cliente = base.cliente


@pytest.fixture(autouse=True)
def _sabana_con_un_producto_sin_titular(monkeypatch):
    """Antes que `cliente` (las autouse van primero): su `_sabana()` lee este PRODUCTOS."""
    monkeypatch.setattr(base, "PRODUCTOS", PRODUCTOS_B8)


# --- Ayudas -------------------------------------------------------------------------------------


def _previsualizar(client, **extra) -> dict:
    respuesta = client.post("/mowa-mes/campanas/previsualizacion", json={**CUERPO, **extra})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _crear_campana(client, speech_id: int | None = None) -> dict:
    extra = {} if speech_id is None else {"speech_id": speech_id}
    previa = _previsualizar(client, **extra)
    assert previa["errores"] == [] and previa["puede_crear"] is True
    creada = client.post(
        "/mowa-mes/campanas", json={**CUERPO, "speech_huella": previa["speech"]["huella"], **extra}
    )
    assert creada.status_code == 201, creada.text
    return creada.json()


def _guardar_v2(client, nombre: str, expresiones: list[dict], **extra) -> int:
    respuesta = client.post(
        "/mowa-mes/speech",
        json={"nombre": f"{PREFIJO}{nombre}", "expresiones": expresiones, **extra},
    )
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["formato"] == "v2"
    return respuesta.json()["id"]


def _v2_desde_el_original(client) -> int:
    """Una v2 por `como-v2` desde el Speech original, guardada como version nueva (C-5)."""
    original = next(v for v in client.get("/mowa-mes/speech").json() if v["original"])
    borrador = client.get(f"/mowa-mes/speech/{original['id']}/como-v2").json()
    expresiones = [
        {"segmento": e["segmento"], "expresion": e["expresion"]} for e in borrador["expresiones"]
    ]
    return _guardar_v2(client, "como v2", expresiones, basada_en_id=original["id"])


def _v2_sin_titular(client) -> int:
    expresiones = [{"segmento": s, "expresion": {"nodos": SIN_TITULAR}} for s in SEGMENTOS]
    return _guardar_v2(client, "sin titular", expresiones)


def _por_pagare(filas) -> dict:
    """Las filas de productos por el numero de su pagare (la supervision no tiene pagare)."""
    return {int(f.pagare): f for f in filas if f.pagare is not None}


def _libro_del_reporte(cargadas, estado_de_cada_producto: dict, crudos: set) -> tuple[bytes, list]:
    """El reporte de MES armado desde lo cargado: una fila por fila cargada, en dos ids.

    `estado_de_cada_producto` da el estado por numero de pagare (el resto, `enviado`) y `crudos`
    los pagares cuyo mensaje va tal cual, sin la normalizacion de MES.
    """
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "Hoja1"
    hoja.append(list(COLUMNAS_REPORTE))
    mitad = len(cargadas) // 2
    filas = []
    for posicion, fila in enumerate(cargadas):
        pagare = None if fila.pagare is None else int(fila.pagare)
        mensaje = fila.mensaje if pagare in crudos else _como_mes(fila.mensaje)
        estado = estado_de_cada_producto.get(pagare, "enviado")
        mes_id = MES_IDS[0] if posicion < mitad else MES_IDS[1]
        filas.append(
            [mes_id, str(fila.numero), mensaje, "02/06/99", fila.dni, estado, "Nro. LARGO", "u"]
        )
    for fila in filas:
        hoja.append(fila)
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue(), filas


_CARGADAS_EN_LA_BASE = text(
    "SELECT numero, dni, mensaje FROM mowa_mes_fila_cargada WHERE campana_id = :campana "
    "ORDER BY posicion"
)
_REPORTADAS_EN_LA_BASE = text(
    "SELECT f.celular, f.dni, f.mensaje, f.estado FROM mowa_mes_reporte_fila f "
    "JOIN mowa_mes_reporte r ON r.id = f.reporte_id WHERE r.campana_id = :campana "
    "ORDER BY r.mes_id, f.fila"
)


def _de_la_base(engine, consulta, campana_id: int) -> list:
    with engine.connect() as cx:
        return cx.execute(consulta, {"campana": campana_id}).all()


def _enviados_conciliados_guardados(engine, campana_id: int) -> int | None:
    with engine.connect() as cx:
        return cx.execute(
            select(_CAMPANA.c.enviados_conciliados).where(_CAMPANA.c.id == campana_id)
        ).scalar_one()


def _importar_y_conciliar(client, engine, campana: dict, estados: dict, crudos: set = frozenset()):
    """Arma el reporte desde `mowa_mes_fila_cargada`, lo importa por HTTP y concilia.

    Devuelve (conciliacion, filas del reporte enviadas, filas cargadas leidas de la base).
    """
    cargadas = RepositorioCampanasMowaMesPostgres(engine).filas_cargadas(campana["id"])
    contenido, enviadas = _libro_del_reporte(cargadas, estados, set(crudos))

    importado = client.post(
        f"/mowa-mes/campanas/{campana['id']}/reportes",
        files={"archivo": ("reporte.xlsx", contenido)},
    )
    conciliacion = client.get(f"/mowa-mes/campanas/{campana['id']}/conciliacion")

    assert importado.status_code == 201, importado.text
    assert conciliacion.status_code == 200, conciliacion.text
    return conciliacion.json(), enviadas, cargadas


def _comprobar_la_conciliacion_cuadra_con_la_base(engine, campana, cargadas, enviadas) -> None:
    """Lo reportado es lo cargado: mismo numero y dni, y el mismo mensaje ya normalizado."""
    en_cargadas = _de_la_base(engine, _CARGADAS_EN_LA_BASE, campana["id"])
    en_reporte = _de_la_base(engine, _REPORTADAS_EN_LA_BASE, campana["id"])

    assert len(en_cargadas) == len(en_reporte) == len(cargadas) == len(enviadas)
    del_reporte = {(f.celular, f.dni): _como_mes(f.mensaje) for f in en_reporte}
    de_lo_cargado = {(f.numero, f.dni): _como_mes(f.mensaje) for f in en_cargadas}
    assert len(del_reporte) == len(en_reporte)  # ningun numero + dni repetido
    assert del_reporte == de_lo_cargado
    # el reporte importado es lo que se envio, sin cambios (celular y dni como texto)
    assert [(str(c[1]), c[4]) for c in enviadas] == [(f.celular, f.dni) for f in en_reporte]


def _por_id_esperado(enviadas) -> list[dict]:
    filas = Counter(f[0] for f in enviadas)
    return [
        {"mes_id": mes_id, "filas": n, "con_correspondencia": n}
        for mes_id, n in sorted(filas.items())
    ]


# --- Una v2 desde el Speech original (como-v2) --------------------------------------------------


def test_una_v2_por_como_v2_sale_como_la_v1_y_se_concilia_entera(cliente) -> None:
    client, engine = cliente
    repositorio = RepositorioCampanasMowaMesPostgres(engine)
    de_la_v1 = _crear_campana(client)  # el Speech original, el punto de comparacion
    v2_id = _v2_desde_el_original(client)

    campana = _crear_campana(client, speech_id=v2_id)
    cargadas = repositorio.filas_cargadas(campana["id"])
    exclusiones = client.get(f"/mowa-mes/campanas/{campana['id']}/exclusiones").json()
    descarga = _filas_xlsx(client.get(f"/mowa-mes/campanas/{campana['id']}/archivos/1").content)

    # Las mismas filas, mensajes y exclusiones que la v1 de la que sale (RF-MM-13: la v2 convertida
    # usa el titular, asi que el producto sin titular se excluye igual).
    assert (campana["productos_cargados"], campana["supervision_cargados"]) == (6, 5)
    assert campana["total_cargados"] == 11 == de_la_v1["total_cargados"]
    assert cargadas == repositorio.filas_cargadas(de_la_v1["id"])
    assert sorted((int(e["pagare"]), e["codigo"]) for e in exclusiones["exclusiones"]) == [
        (4, "telefono_invalido"),
        (5, "falta_documento"),
        (10, "falta_titular"),
    ]
    assert [(str(f[0]), f[1], f[2]) for f in descarga] == [
        (f.numero, f.mensaje, f.dni) for f in cargadas
    ]
    # El producto 31 a 60 usa el WhatsApp: el enlace sale de la constante de la campana.
    assert _por_pagare(cargadas)[2].mensaje.endswith("https://wa.me/+51900000123")

    # E-1: los que MES reporta con otro estado empatan, cuentan como cargados y no como enviados.
    estados = {2: "fallido", 3: "Enviado ", 6: "pendiente"}
    conciliacion, enviadas, _ = _importar_y_conciliar(client, engine, campana, estados)

    _comprobar_la_conciliacion_cuadra_con_la_base(engine, campana, cargadas, enviadas)
    assert conciliacion["sin_correspondencia"] == 0 and conciliacion["advertencias"] == []
    assert conciliacion["por_id"] == _por_id_esperado(enviadas)
    assert conciliacion["supervision"]["cargados"] == conciliacion["supervision"]["enviados"] == 5
    assert (
        conciliacion["productos"]["cargados"],
        conciliacion["productos"]["enviados"],
        conciliacion["productos"]["no_enviados"],
    ) == (6, 4, 2)
    assert conciliacion["productos"]["por_estado"] == [
        {"estado": "Enviado", "cantidad": 1},  # " Enviado " del producto 3, recortado
        {"estado": "enviado", "cantidad": 3},
        {"estado": "fallido", "cantidad": 1},
        {"estado": "pendiente", "cantidad": 1},
    ]
    assert (conciliacion["total"]["cargados"], conciliacion["total"]["enviados"]) == (11, 9)
    assert conciliacion["total"]["no_enviados"] == 2
    assert _enviados_conciliados_guardados(engine, campana["id"]) == 9


# --- Una v2 que no usa el titular ---------------------------------------------------------------


def test_una_v2_sin_titular_carga_un_producto_sin_titular_y_se_concilia_entera(cliente) -> None:
    client, engine = cliente
    v2_id = _v2_sin_titular(client)

    campana = _crear_campana(client, speech_id=v2_id)
    cargadas = RepositorioCampanasMowaMesPostgres(engine).filas_cargadas(campana["id"])
    exclusiones = client.get(f"/mowa-mes/campanas/{campana['id']}/exclusiones").json()
    por_pagare = _por_pagare(cargadas)

    # El producto 10 no tiene titular y esta cargado: la regla de RF-MM-13 mira lo que la v2 usa.
    assert (campana["productos_cargados"], campana["supervision_cargados"]) == (7, 5)
    assert campana["total_cargados"] == 12
    assert sorted((int(e["pagare"]), e["codigo"]) for e in exclusiones["exclusiones"]) == [
        (4, "telefono_invalido"),
        (5, "falta_documento"),
    ]
    assert 10 in por_pagare and por_pagare[10].supervision is False
    # El mensaje no lleva titular: el del producto sin titular es el de cualquiera del segmento,
    # normalizado a GSM-7 pero con los espacios de los extremos tal cual los armo la v2.
    sin_titular = por_pagare[10]
    assert MENSAJE_SIN_TITULAR.fullmatch(sin_titular.mensaje)
    assert sin_titular.mensaje != _como_mes(sin_titular.mensaje)  # MES recorta los extremos
    assert sin_titular.mensaje == por_pagare[1].mensaje
    assert sin_titular.numero == "900000110" and sin_titular.dni == "10000010"

    # Estados: dos fallidos y uno en mayusculas con espacios; el producto 10 y el 7 se reportan
    # enviados, el 7 con su mensaje sin normalizar (la normalizacion es de los dos lados).
    estados = {2: "fallido", 3: "Enviado ", 8: "fallido"}
    conciliacion, enviadas, _ = _importar_y_conciliar(
        client, engine, campana, estados, crudos={7, 10}
    )

    _comprobar_la_conciliacion_cuadra_con_la_base(engine, campana, cargadas, enviadas)
    en_reporte = {
        (f.celular, f.dni): f for f in _de_la_base(engine, _REPORTADAS_EN_LA_BASE, campana["id"])
    }
    del_10 = en_reporte[(sin_titular.numero, sin_titular.dni)]
    # el producto sin titular tiene su fila en el reporte, reportada como enviada y conciliada
    assert del_10.estado == "enviado"
    assert _como_mes(del_10.mensaje) == _como_mes(sin_titular.mensaje)
    del_1 = en_reporte[(por_pagare[1].numero, por_pagare[1].dni)]
    # el reporte trae el mensaje como lo deja MES: sin los espacios de los extremos
    assert del_1.mensaje == _como_mes(por_pagare[1].mensaje) != por_pagare[1].mensaje
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
    assert _enviados_conciliados_guardados(engine, campana["id"]) == 10
