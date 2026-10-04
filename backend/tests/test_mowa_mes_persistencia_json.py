"""Como SQLAlchemy manda a PostgreSQL el contenido de una version de speech (sin base).

Un `None` de Python en una columna JSONB se escribe por defecto como el JSON `null`, que para un
`IS NULL` no es NULL: el CHECK `contenido_segun_formato` rechazaria toda v1. La columna
`expresiones` lleva `none_as_null`, asi que el `None` es NULL de SQL y una lista vacia sigue siendo
`'[]'`. Se razona con la sentencia compilada para el dialecto de PostgreSQL porque la prueba contra
la base (`test_mowa_mes_speech_v2_postgres.py`) no corre en todos los entornos.
"""

import json

from sqlalchemy import insert, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

from app.adapters.persistence.modelos import MowaMesSpeechVersion
from app.adapters.persistence.repositorio_mowa_mes_postgres import _valores_de_contenido
from app.core.entities.mowa_mes import DatosSpeech
from tests.test_mowa_mes_speech import ORIGINAL
from tests.test_mowa_mes_speech_v2 import _texto, _v2

_TABLA = MowaMesSpeechVersion.__table__
_DIALECTO = postgresql.dialect()


def _como_viaja(sentencia, columna: str):
    """El valor de `columna` tal como se lo entrega el controlador a PostgreSQL."""
    compilada = sentencia.compile(dialect=_DIALECTO)
    valor = compilada.params[columna]
    procesador = compilada.binds[columna].type.bind_processor(_DIALECTO)
    return valor if procesador is None else procesador(valor)


def test_las_columnas_jsonb_que_aceptan_nulo_lo_escriben_como_null_de_sql() -> None:
    nulables = [c for c in _TABLA.columns if isinstance(c.type, JSONB) and c.nullable]

    assert [c.name for c in nulables] == ["expresiones"]
    assert all(c.type.none_as_null for c in nulables)


def test_una_v1_escribe_expresiones_como_null_de_sql_y_las_partes_como_lista() -> None:
    valores = _valores_de_contenido(DatosSpeech("v1", ORIGINAL))

    insercion = insert(_TABLA).values(nombre="x", nombre_normalizado="x", **valores)
    edicion = update(_TABLA).values(**valores)

    for sentencia in (insercion, edicion):
        assert _como_viaja(sentencia, "expresiones") is None  # NULL, no la cadena 'null'
        assert json.loads(_como_viaja(sentencia, "partes"))[0]["segmento"] == "preventiva"


def test_una_v2_escribe_las_partes_como_lista_vacia_y_las_expresiones_como_lista() -> None:
    valores = _valores_de_contenido(_v2(TODOS=(_texto("a"),)))

    for sentencia in (
        insert(_TABLA).values(nombre="x", nombre_normalizado="x", **valores),
        update(_TABLA).values(**valores),
    ):
        assert _como_viaja(sentencia, "partes") == "[]"  # vacia, nunca 'null'
        expresiones = json.loads(_como_viaja(sentencia, "expresiones"))
        assert [e["segmento"] for e in expresiones][0] == "preventiva"


def test_el_check_pregunta_por_nulo_de_sql_y_no_compara_con_el_json_null() -> None:
    sqltext = next(
        str(c.sqltext)
        for c in _TABLA.constraints
        if str(getattr(c, "name", "")).endswith("contenido_segun_formato")
    )

    assert "expresiones IS NULL" in sqltext and "expresiones IS NOT NULL" in sqltext
    sin_is_null = sqltext.replace("IS NOT NULL", "").replace("IS NULL", "")
    assert "null" not in sin_is_null.lower()  # ni `= 'null'::jsonb` ni `jsonb_typeof`
