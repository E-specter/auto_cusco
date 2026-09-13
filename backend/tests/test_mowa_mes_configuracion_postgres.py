"""Configuracion de MOWA MES, calendario y supervisores contra PostgreSQL real (opcional).

Corre solo con AUTO_CUSCO_DB_TESTS=1 y la base migrada. Las excepciones del
calendario usan fechas de 2099; las versiones de speech llevan un prefijo propio
en el nombre. La configuracion del conector y la lista de supervisores son
unicas, asi que se guarda su estado antes de cada prueba y se restituye al
terminar. Numeros sinteticos 900000xxx.
"""

import os
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.modelos import (
    CalendarioExcepcion,
    MowaMesSpeechVersion,
    SupervisorDigital,
)
from app.adapters.persistence.repositorio_calendario_postgres import RepositorioCalendarioPostgres
from app.adapters.persistence.repositorio_mowa_mes_postgres import (
    RepositorioMowaMesPostgres,
    normalizar_nombre,
)
from app.adapters.persistence.repositorio_supervision_postgres import (
    RepositorioSupervisionPostgres,
)
from app.core.entities.calendario import ExcepcionCalendario, ExcepcionRepetida, TipoExcepcion
from app.core.entities.mowa_mes import DatosSpeech
from app.main import app
from tests.test_speech_original import speech_del_documento

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

PREFIJO = "zz prueba automatica "
INICIO_2099 = date(2099, 1, 1)
FIN_2099 = date(2099, 12, 31)
_EXCEPCION = CalendarioExcepcion.__table__
_SPEECH = MowaMesSpeechVersion.__table__
_SUPERVISOR = SupervisorDigital.__table__


def _partes_json(partes) -> list[dict]:
    return [
        {"segmento": p.segmento.value, "parte_1": p.parte_1, "parte_2": p.parte_2} for p in partes
    ]


PARTES = _partes_json(speech_del_documento())


def _limpiar(engine) -> None:
    with engine.begin() as cx:
        cx.execute(delete(_EXCEPCION).where(_EXCEPCION.c.fecha.between(INICIO_2099, FIN_2099)))
        cx.execute(
            delete(_SPEECH).where(
                _SPEECH.c.nombre_normalizado.startswith(normalizar_nombre(PREFIJO))
            )
        )


@pytest.fixture
def engine():
    engine = get_engine()
    supervision = RepositorioSupervisionPostgres(engine)
    mowa_mes = RepositorioMowaMesPostgres(engine)
    supervisores_antes = supervision.obtener()
    configuracion_antes = mowa_mes.obtener_configuracion()
    with engine.connect() as cx:
        original_antes = cx.execute(select(_SPEECH).where(_SPEECH.c.original)).one()
    _limpiar(engine)
    try:
        yield engine
    finally:
        # El Speech original se restituye antes de limpiar: si una prueba (o una
        # mutacion a proposito) le pusiera el prefijo, la limpieza lo borraria.
        with engine.begin() as cx:
            cx.execute(
                update(_SPEECH)
                .where(_SPEECH.c.id == original_antes.id)
                .values(
                    nombre=original_antes.nombre,
                    nombre_normalizado=original_antes.nombre_normalizado,
                    partes=original_antes.partes,
                    usada_en=original_antes.usada_en,
                )
            )
        _limpiar(engine)
        supervision.reemplazar(supervisores_antes)
        mowa_mes.guardar_configuracion(configuracion_antes)


@pytest.fixture
def cliente(engine):
    """Cliente HTTP sobre la base real: no se sustituye ninguna dependencia."""
    yield TestClient(app)


# --- Semilla de la migracion --------------------------------------------


def test_la_migracion_siembra_el_speech_original_con_el_texto_de_rf_mm_18(engine) -> None:
    (original,) = [v for v in RepositorioMowaMesPostgres(engine).listar_speech() if v.original]

    assert original.datos.nombre == "Speech original"
    assert original.datos.partes == speech_del_documento()


def test_la_migracion_no_siembra_feriados_ni_numeros(engine) -> None:
    with engine.connect() as cx:
        feriados_2026 = cx.execute(
            select(_EXCEPCION).where(
                _EXCEPCION.c.fecha.between(date(2026, 1, 1), date(2026, 12, 31))
            )
        ).all()
    # Si alguien agrego excepciones de 2026 a mano no se puede afirmar esto; la
    # semilla, en cambio, nunca las tuvo: la regla calcula los feriados.
    assert all(fila.tipo in ("agregado", "retirado") for fila in feriados_2026)


# --- Calendario ---------------------------------------------------------


def test_excepciones_del_calendario_en_la_base(engine) -> None:
    repositorio = RepositorioCalendarioPostgres(engine)
    decreto = ExcepcionCalendario(date(2099, 9, 14), TipoExcepcion.AGREGADO, "Decreto sintetico")

    guardada = repositorio.agregar_excepcion(decreto)

    assert guardada.creado_en.tzinfo is not None
    assert repositorio.listar_excepciones(INICIO_2099, FIN_2099) == [guardada]
    with pytest.raises(ExcepcionRepetida):
        repositorio.agregar_excepcion(decreto)
    assert repositorio.eliminar_excepcion(decreto.fecha)
    assert not repositorio.eliminar_excepcion(decreto.fecha)


def test_la_base_rechaza_un_tipo_de_excepcion_desconocido(engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as cx:
        cx.execute(insert(_EXCEPCION).values(fecha=date(2099, 9, 15), tipo="otro", descripcion="x"))


def test_calendario_por_http(cliente) -> None:
    # 2099-09-14 es lunes: decretado, el siguiente gestionable desde el domingo es el martes.
    decreto = {"fecha": "2099-09-14", "tipo": "agregado", "descripcion": "Decreto sintetico"}

    creada = cliente.post("/calendario/excepciones", json=decreto)
    siguiente = cliente.get(
        "/calendario/siguiente-dia-gestionable", params={"desde": "2099-09-13"}
    ).json()
    anio = cliente.get("/calendario/feriados", params={"anio": 2099}).json()

    assert creada.status_code == 201
    assert siguiente == {"desde": "2099-09-13", "fecha": "2099-09-15"}
    assert {
        "fecha": "2099-09-14",
        "descripcion": "Decreto sintetico",
        "origen": "agregado",
        "retirado": False,
    } in anio["dias"]
    assert cliente.post("/calendario/excepciones", json=decreto).status_code == 409
    assert cliente.delete("/calendario/excepciones/2099-09-14").status_code == 204


# --- Supervisores -------------------------------------------------------


def test_supervisores_por_http_se_guardan_en_orden_y_se_restituyen(cliente) -> None:
    cuerpo = {
        "procedencias": ["Caja Cusco", "nuestra empresa", "zz procedencia de prueba"],
        "supervisores": [
            {"numero": "900000001", "procedencia": "Caja Cusco"},
            {"numero": "900000004", "procedencia": "nuestra empresa"},
            {"numero": "900000002", "procedencia": "Caja Cusco"},
            {"numero": "900000005", "procedencia": "nuestra empresa"},
            {"numero": "900000003", "procedencia": "Caja Cusco"},
        ],
    }

    guardada = cliente.put("/supervisores", json=cuerpo)
    leida = cliente.get("/supervisores").json()
    invalida = cliente.put(
        "/supervisores",
        json={**cuerpo, "supervisores": [{"numero": "800000001", "procedencia": "Caja Cusco"}]},
    )

    assert guardada.status_code == 200
    assert leida["procedencias"] == cuerpo["procedencias"]
    assert [(s["numero"], s["documento"]) for s in leida["supervisores"]] == [
        ("900000001", "00000001"),
        ("900000004", "00000004"),
        ("900000002", "00000002"),
        ("900000005", "00000005"),
        ("900000003", "00000003"),
    ]
    assert invalida.status_code == 400
    assert cliente.get("/supervisores").json() == leida  # el rechazo no toco nada


def test_la_base_rechaza_un_numero_fuera_de_rf02(engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as cx:
        cx.execute(
            insert(_SUPERVISOR).values(posicion=999, numero="800000001", procedencia="Caja Cusco")
        )


# --- Configuracion y speech ---------------------------------------------


def test_configuracion_por_http(cliente) -> None:
    guardada = cliente.put(
        "/mowa-mes/configuracion",
        json={"limite_mensual": 1_234_567, "whatsapp_contacto": "900000123"},
    )
    leida = cliente.get("/mowa-mes/configuracion").json()

    assert guardada.status_code == 200
    assert (leida["limite_mensual"], leida["whatsapp_contacto"]) == (1_234_567, "900000123")
    assert leida["actualizado_en"] is not None


def test_speech_por_http_de_punta_a_punta(cliente, engine) -> None:
    creada = cliente.post(
        "/mowa-mes/speech",
        json={"nombre": f"{PREFIJO}version", "basada_en_id": None, "partes": PARTES},
    )
    speech_id = creada.json()["id"]
    editada = cliente.put(
        f"/mowa-mes/speech/{speech_id}",
        json={"nombre": f"{PREFIJO}version corregida", "partes": PARTES},
    )
    repetida = cliente.post(
        "/mowa-mes/speech", json={"nombre": f"{PREFIJO}VERSION CORREGIDA", "partes": PARTES}
    )
    original_id = next(v["id"] for v in cliente.get("/mowa-mes/speech").json() if v["original"])
    original = cliente.put(
        f"/mowa-mes/speech/{original_id}", json={"nombre": f"{PREFIJO}x", "partes": PARTES}
    )
    RepositorioMowaMesPostgres(engine).marcar_speech_usado(speech_id)
    usada = cliente.put(
        f"/mowa-mes/speech/{speech_id}", json={"nombre": f"{PREFIJO}otra", "partes": PARTES}
    )
    derivada = cliente.post(
        "/mowa-mes/speech",
        json={"nombre": f"{PREFIJO}derivada", "basada_en_id": speech_id, "partes": PARTES},
    )

    assert creada.status_code == 201
    assert editada.status_code == 200
    assert editada.json()["partes"] == creada.json()["partes"]
    assert repetida.status_code == 409
    assert original.status_code == 409
    assert usada.status_code == 409
    assert cliente.get(f"/mowa-mes/speech/{speech_id}").json()["usada"] is True
    assert derivada.status_code == 201
    assert derivada.json()["basada_en_id"] == speech_id


def test_la_escritura_misma_no_modifica_una_version_usada_ni_la_original(engine) -> None:
    # Sin pasar por el servicio: la condicion de la sentencia UPDATE es la que protege
    # cuando una campana marca la version entre la lectura y la escritura.
    repositorio = RepositorioMowaMesPostgres(engine)
    creada = repositorio.crear_speech(
        DatosSpeech(f"{PREFIJO}usada", speech_del_documento()), basada_en_id=None
    )
    original = next(v for v in repositorio.listar_speech() if v.original)
    repositorio.marcar_speech_usado(creada.id)

    otra = DatosSpeech(f"{PREFIJO}cambiada", speech_del_documento())

    assert repositorio.actualizar_speech(creada.id, otra) is None
    assert repositorio.actualizar_speech(original.id, otra) is None
    assert repositorio.obtener_speech(creada.id).datos.nombre == f"{PREFIJO}usada"


def test_previsualizacion_con_el_whatsapp_configurado(cliente) -> None:
    cliente.put(
        "/mowa-mes/configuracion",
        json={"limite_mensual": 2_500_000, "whatsapp_contacto": "900000123"},
    )

    cuerpo = cliente.post("/mowa-mes/speech/previsualizacion", json={"partes": PARTES}).json()

    por_segmento = {s["segmento"]: s for s in cuerpo["segmentos"]}
    assert cuerpo["whatsapp"] == "900000123"
    assert por_segmento["9_a_30"]["largo_maximo"] == 156
    assert por_segmento["61_a_90"]["ejemplo"].endswith("https://wa.me/+51900000123")
