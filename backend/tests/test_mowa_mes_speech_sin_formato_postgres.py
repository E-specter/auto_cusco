"""La migracion que quita el formato de las versiones de speech, contra PostgreSQL real, de ida y
vuelta (T-MM-C11, M-B4; RF-MM-17). La corre `architec` con `-ConBase`.

`e2c6b4a8d195` renombra `partes` a `texto_v1` (nulable), quita `formato` y sus dos CHECK y deja
`expresiones` NOT NULL. Esta prueba comprueba que el DOWNGRADE deja la base EXACTAMENTE como la dejo
`d7a3e5b9c241` (M-B3), y no solo las filas:

1. baja a `c5d9f2a8e714` y sube a `d7a3e5b9c241` con las migraciones reales: ese esquema es el que
   M-B3 dejo, no una reconstruccion;
2. siembra (SQL crudo, porque el modelo de la aplicacion ya no tiene `partes` ni `formato`) el
   Speech original usado por una campana real, dos convertidas (una usada, una sin usar) y una v2
   nativa (`partes = '[]'`);
3. fotografia el esquema (columnas con su tipo, nulabilidad y valor por defecto; restricciones con
   su nombre y su definicion; indices) y todas las filas;
4. sube a `head` y comprueba el esquema nuevo y las filas (`texto_v1` es el `partes` de antes, NULL
   en la v2 nativa; nada mas cambia);
5. baja a `d7a3e5b9c241` y exige que el esquema y las filas sean IGUALES a los del punto 3. Una sola
   diferencia admitida: el orden fisico de las columnas (`formato` vuelve al final de la tabla),
   que PostgreSQL no puede restituir sin reescribir la tabla y que ninguna consulta usa; por eso el
   esquema se compara por nombre de columna y no por posicion;
6. sube a `head`, pase lo que pase.

Sigue el patron de `test_mowa_mes_speech_solo_v2_postgres.py`: la sesion se niega a correr contra
una base que no sea `_test` (conftest.py). Datos sinteticos.
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests import test_mowa_mes_campanas_postgres as base
from tests.test_mowa_mes_campanas_postgres import PREFIJO, _crear, _previsualizar
from tests.test_mowa_mes_speech_solo_v2_migracion import MIGRACION
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
REVISION_ANTERIOR = "c5d9f2a8e714"  # las versiones deshabilitadas (M-B2)
REVISION_SOLO_V2 = "d7a3e5b9c241"  # M-B3: el esquema que el downgrade debe restituir
SEGMENTOS = ["preventiva", "1_a_8", "9_a_30", "31_a_60", "61_a_90", "91_a_120"]
TEXTO_USADA = [
    {"segmento": s, "parte_1": f" Hola {s} el ", "parte_2": ", paga en [whatsapp] hoy."}
    for s in SEGMENTOS
]
TEXTO_LIBRE = [{"segmento": s, "parte_1": " a ", "parte_2": " b"} for s in SEGMENTOS]
USADA_EN = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
TABLA = "mowa_mes_speech_version"


def _configuracion() -> Config:
    configuracion = Config(str(BACKEND / "alembic.ini"))
    configuracion.set_main_option("script_location", str(BACKEND / "migrations"))
    return configuracion


def _json(valor) -> str:
    return json.dumps(valor, ensure_ascii=False)


def _filas(engine) -> list[dict]:
    """Todas las filas con todas las columnas que la tabla tenga en la revision actual."""
    with engine.connect() as cx:
        filas = cx.execute(text(f"SELECT * FROM {TABLA} ORDER BY id")).all()
    return [dict(f._mapping) for f in filas]


def _esquema(engine) -> dict:
    """Lo que define la tabla: columnas (sin su posicion), restricciones e indices."""
    with engine.connect() as cx:
        columnas = {
            f.column_name: (
                f.data_type,
                f.character_maximum_length,
                f.is_nullable,
                f.column_default,
            )
            for f in cx.execute(
                text(
                    "SELECT column_name, data_type, character_maximum_length, is_nullable, "
                    "column_default FROM information_schema.columns "
                    "WHERE table_schema = current_schema() AND table_name = :tabla"
                ),
                {"tabla": TABLA},
            )
        }
        restricciones = {
            f.conname: (f.contype, f.definicion)
            for f in cx.execute(
                text(
                    "SELECT conname, contype, pg_get_constraintdef(oid) AS definicion "
                    "FROM pg_constraint WHERE conrelid = CAST(:tabla AS regclass) "
                    "OR confrelid = CAST(:tabla AS regclass)"
                ),
                {"tabla": TABLA},
            )
        }
        indices = {
            f.indexname: f.indexdef
            for f in cx.execute(
                text(
                    "SELECT indexname, indexdef FROM pg_indexes "
                    "WHERE schemaname = current_schema() AND tablename = :tabla"
                ),
                {"tabla": TABLA},
            )
        }
    return {"columnas": columnas, "restricciones": restricciones, "indices": indices}


def _sembrar(engine, nombre: str, partes: list[dict], expresiones, usada_en) -> int:
    """Una version como las deja M-B3: siempre v2, con el texto v1 en `partes` si fue convertida."""
    with engine.begin() as cx:
        return cx.execute(
            text(
                f"INSERT INTO {TABLA} "
                "(nombre, nombre_normalizado, partes, formato, expresiones, usada_en) "
                "VALUES (:nombre, :normalizado, CAST(:partes AS jsonb), 'v2', "
                "CAST(:expresiones AS jsonb), :usada_en) RETURNING id"
            ),
            {
                "nombre": f"{PREFIJO}{nombre}",
                "normalizado": f"{PREFIJO}{nombre}".casefold(),
                "partes": _json(partes),
                "expresiones": _json(expresiones),
                "usada_en": usada_en,
            },
        ).scalar_one()


def test_el_downgrade_deja_el_esquema_y_las_filas_como_los_dejo_m_b3(cliente) -> None:
    client, engine = cliente
    previa = _previsualizar(client)
    creada = _crear(client, previa["speech"]["huella"])
    assert creada.status_code == 201, creada.text  # una campana real usa el Speech original
    configuracion = _configuracion()
    try:
        # El esquema de M-B3, construido por las migraciones reales (no reconstruido a mano).
        command.downgrade(configuracion, REVISION_ANTERIOR)
        command.upgrade(configuracion, REVISION_SOLO_V2)
        usada = _sembrar(
            engine, "convertida usada", TEXTO_USADA, MIGRACION._convertir(TEXTO_USADA), USADA_EN
        )
        libre = _sembrar(
            engine, "convertida libre", TEXTO_LIBRE, MIGRACION._convertir(TEXTO_LIBRE), None
        )
        nativa = _sembrar(engine, "v2 nativa", [], CUERPO_V2, None)
        esquema_m_b3 = _esquema(engine)
        filas_m_b3 = _filas(engine)
        assert {"partes", "formato", "expresiones"} <= set(esquema_m_b3["columnas"])
        assert "texto_v1" not in esquema_m_b3["columnas"]
        assert any(f["original"] and f["partes"] for f in filas_m_b3)  # el original, con su texto

        command.upgrade(configuracion, "head")
        esquema_nuevo = _esquema(engine)
        filas_nuevas = _filas(engine)

        # El esquema nuevo: sin `formato` ni `partes`, sin sus CHECK; `expresiones` NOT NULL.
        assert not {"formato", "partes"} & set(esquema_nuevo["columnas"])
        assert esquema_nuevo["columnas"]["texto_v1"][2] == "YES"  # nulable
        assert esquema_nuevo["columnas"]["expresiones"][2] == "NO"
        assert not any("formato" in nombre for nombre in esquema_nuevo["restricciones"])
        # Las filas: `texto_v1` es el `partes` de antes (NULL en la v2 nativa); nada mas cambia.
        assert [f["id"] for f in filas_nuevas] == [f["id"] for f in filas_m_b3]
        for antes, ahora in zip(filas_m_b3, filas_nuevas, strict=True):
            esperado_texto = antes["partes"] or None
            assert ahora["texto_v1"] == esperado_texto, antes["id"]
            sin_lo_que_cambia = {k: v for k, v in antes.items() if k not in ("partes", "formato")}
            assert {k: v for k, v in ahora.items() if k != "texto_v1"} == sin_lo_que_cambia
        assert next(f for f in filas_nuevas if f["id"] == nativa)["texto_v1"] is None
        assert next(f for f in filas_nuevas if f["id"] == usada)["usada_en"] == USADA_EN
        assert next(f for f in filas_nuevas if f["id"] == libre)["texto_v1"] == TEXTO_LIBRE
        with pytest.raises(IntegrityError):  # NOT NULL: ya no hay version sin expresiones
            with engine.begin() as cx:
                cx.execute(
                    text(
                        f"INSERT INTO {TABLA} (nombre, nombre_normalizado, expresiones) "
                        "VALUES ('x', 'x', NULL)"
                    )
                )

        command.downgrade(configuracion, REVISION_SOLO_V2)

        # Exactamente lo de M-B3: mismas filas (columna por columna) y mismo esquema.
        assert _filas(engine) == filas_m_b3
        assert _esquema(engine) == esquema_m_b3
    finally:
        command.upgrade(configuracion, "head")


def test_el_downgrade_vuelve_a_poner_partes_en_lista_vacia_y_formato_v2(cliente) -> None:
    """La v2 nativa (`texto_v1` NULL) vuelve a `partes = '[]'`; toda fila queda `formato = 'v2'`."""
    _, engine = cliente
    configuracion = _configuracion()
    try:
        nativa = _sembrar_en_head(engine, "nativa")
        command.downgrade(configuracion, REVISION_SOLO_V2)

        with engine.connect() as cx:
            fila = cx.execute(
                text(f"SELECT partes, formato FROM {TABLA} WHERE id = :id"), {"id": nativa}
            ).one()
            formatos = set(cx.execute(text(f"SELECT DISTINCT formato FROM {TABLA}")).scalars())
        assert (fila.partes, fila.formato) == ([], "v2")
        assert formatos == {"v2"}
    finally:
        command.upgrade(configuracion, "head")


def _sembrar_en_head(engine, nombre: str) -> int:
    """Una v2 nativa tal como la guarda la aplicacion de M-B4: `texto_v1` NULL."""
    with engine.begin() as cx:
        return cx.execute(
            text(
                f"INSERT INTO {TABLA} (nombre, nombre_normalizado, texto_v1, expresiones) "
                "VALUES (:nombre, :normalizado, NULL, CAST(:expresiones AS jsonb)) RETURNING id"
            ),
            {
                "nombre": f"{PREFIJO}{nombre}",
                "normalizado": f"{PREFIJO}{nombre}".casefold(),
                "expresiones": _json(CUERPO_V2),
            },
        ).scalar_one()
