"""La migracion a solo v2 contra PostgreSQL real, de ida y vuelta (T-MM-C11, M-B3; RF-MM-17).
La corre `architec` con `-ConBase`.

Baja la base de pruebas un paso (`alembic downgrade c5d9f2a8e714`: el mundo de antes, con versiones
v1), siembra lo que habia entonces, sube (`d7a3e5b9c241`), vuelve a bajar y sube a `head` al
terminar, pase lo que pase. Sigue el patron de `test_mapeador_postgres.py`: la sesion se niega a
correr contra una base que no sea `_test` (conftest.py).

Se usa una campana real: el Speech original ya la tiene como version usada, y ademas se siembra una
v1 usada, una v1 sin usar y una v2 nativa. Despues del upgrade quedan iguales el `id`, el nombre,
`usada_en`, `partes` (el texto v1) y el resto de las columnas; `formato` es v2 y `expresiones` sale
de la conversion. Despues del downgrade, cada fila es IDENTICA a la de antes. Datos sinteticos.
"""

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import insert, select, text
from sqlalchemy.exc import IntegrityError

from app.adapters.persistence.modelos import MowaMesCampana, MowaMesSpeechVersion
from tests import test_mowa_mes_campanas_postgres as base
from tests.test_mowa_mes_campanas_postgres import PREFIJO, _crear, _previsualizar
from tests.test_mowa_mes_speech_solo_v2_migracion import MIGRACION, SIEMBRA, normalizado
from tests.test_mowa_mes_speech_v2_postgres import CUERPO_V2

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

cliente = base.cliente
BACKEND = Path(__file__).resolve().parents[1]
REVISION_ANTERIOR = "c5d9f2a8e714"
REVISION = "d7a3e5b9c241"
_SPEECH = MowaMesSpeechVersion.__table__
_CAMPANA = MowaMesCampana.__table__
SEGMENTOS = ["preventiva", "1_a_8", "9_a_30", "31_a_60", "61_a_90", "91_a_120"]
PARTES_USADA = [
    {"segmento": s, "parte_1": f" Hola {s} el ", "parte_2": ", paga en [whatsapp] hoy."}
    for s in SEGMENTOS
]
PARTES_LIBRE = [{"segmento": s, "parte_1": " a ", "parte_2": " b"} for s in SEGMENTOS]
USADA_EN = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _configuracion() -> Config:
    configuracion = Config(str(BACKEND / "alembic.ini"))
    configuracion.set_main_option("script_location", str(BACKEND / "migrations"))
    return configuracion


def _fila(engine, speech_id: int) -> dict:
    with engine.connect() as cx:
        return dict(cx.execute(select(_SPEECH).where(_SPEECH.c.id == speech_id)).one()._mapping)


def _sembrar_v1(engine, nombre: str, partes: list[dict], usada_en) -> int:
    """Una v1 como las de antes de la migracion (el CHECK de entonces la admitia)."""
    with engine.begin() as cx:
        return cx.execute(
            insert(_SPEECH)
            .values(
                nombre=f"{PREFIJO}{nombre}",
                nombre_normalizado=f"{PREFIJO}{nombre}".casefold(),
                partes=partes,
                formato="v1",
                expresiones=None,
                usada_en=usada_en,
            )
            .returning(_SPEECH.c.id)
        ).scalar_one()


def test_ida_y_vuelta_con_una_v1_usada_por_una_campana(cliente) -> None:
    client, engine = cliente
    previa = _previsualizar(client)
    creada = _crear(client, previa["speech"]["huella"])
    assert creada.status_code == 201, creada.text
    original_id = creada.json()["speech"]["id"]  # el original: una campana real lo usa
    configuracion = _configuracion()
    command.downgrade(configuracion, REVISION_ANTERIOR)  # el mundo de antes
    try:
        usada = _sembrar_v1(engine, "v1 usada", PARTES_USADA, USADA_EN)
        libre = _sembrar_v1(engine, "v1 libre", PARTES_LIBRE, None)
        with engine.begin() as cx:
            nativa = cx.execute(
                insert(_SPEECH)
                .values(
                    nombre=f"{PREFIJO}v2 nativa",
                    nombre_normalizado=f"{PREFIJO}v2 nativa".casefold(),
                    partes=[],
                    formato="v2",
                    expresiones=CUERPO_V2,
                )
                .returning(_SPEECH.c.id)
            ).scalar_one()
        ids = (original_id, usada, libre, nativa)
        antes = {i: _fila(engine, i) for i in ids}
        assert [antes[i]["formato"] for i in ids] == ["v1", "v1", "v1", "v2"]
        assert antes[original_id]["expresiones"] is None and antes[original_id]["usada_en"]

        command.upgrade(configuracion, REVISION)
        despues = {i: _fila(engine, i) for i in ids}

        # Todo queda igual salvo `formato` y `expresiones`.
        for i in (original_id, usada, libre):
            esperado = {**antes[i], "formato": "v2", "expresiones": despues[i]["expresiones"]}
            assert despues[i] == esperado, i
        assert despues[nativa] == antes[nativa]  # la v2 nativa no se toca
        assert despues[original_id]["expresiones"] == MIGRACION.EXPRESIONES_ORIGINAL
        assert despues[usada]["expresiones"] == MIGRACION._convertir(PARTES_USADA)
        assert despues[libre]["expresiones"] == MIGRACION._convertir(PARTES_LIBRE)
        assert despues[original_id]["partes"] == list(SIEMBRA.SPEECH_ORIGINAL)  # texto v1 intacto
        assert despues[usada]["usada_en"] == USADA_EN
        with engine.connect() as cx:  # la campana sigue apuntando a la misma version
            apunta = cx.execute(
                select(_CAMPANA.c.speech_version_id).where(_CAMPANA.c.id == creada.json()["id"])
            ).scalar_one()
            por_defecto = cx.execute(
                text(
                    "SELECT column_default FROM information_schema.columns "
                    "WHERE table_name = 'mowa_mes_speech_version' AND column_name = 'formato'"
                )
            ).scalar_one()
        assert apunta == original_id
        assert "'v2'" in por_defecto
        with pytest.raises(IntegrityError):  # el CHECK nuevo: ninguna v1
            _sembrar_v1(engine, "v1 despues", PARTES_LIBRE, None)

        command.downgrade(configuracion, REVISION_ANTERIOR)
        de_vuelta = {i: _fila(engine, i) for i in ids}

        assert de_vuelta == antes  # cada fila, identica a la de antes (columna por columna)
        with engine.connect() as cx:
            por_defecto = cx.execute(
                text(
                    "SELECT column_default FROM information_schema.columns "
                    "WHERE table_name = 'mowa_mes_speech_version' AND column_name = 'formato'"
                )
            ).scalar_one()
        assert "'v1'" in por_defecto  # el formato por defecto vuelve a v1
    finally:
        command.upgrade(configuracion, "head")


def test_una_convertida_y_editada_se_queda_v2_en_el_downgrade(cliente) -> None:
    """Editar una convertida deja `partes = []`: ya no es la v1 de antes y no vuelve."""
    client, engine = cliente
    configuracion = _configuracion()
    command.downgrade(configuracion, REVISION_ANTERIOR)
    try:
        libre = _sembrar_v1(engine, "v1 para editar", PARTES_LIBRE, None)
        command.upgrade(configuracion, REVISION)
        editada = client.put(
            f"/mowa-mes/speech/{libre}",
            json={"nombre": f"{PREFIJO}v1 para editar", "expresiones": CUERPO_V2},
        )
        assert editada.status_code == 200, editada.text
        assert _fila(engine, libre)["partes"] == []

        command.downgrade(configuracion, REVISION_ANTERIOR)

        fila = _fila(engine, libre)
        assert (fila["formato"], fila["partes"]) == ("v2", [])
        # La fila trae la forma que serializa la app (con `obligatoria`), no el cuerpo del PUT.
        assert fila["expresiones"] == normalizado(CUERPO_V2)
    finally:
        command.upgrade(configuracion, "head")
