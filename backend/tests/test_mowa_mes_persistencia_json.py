"""Como SQLAlchemy manda a PostgreSQL el contenido de una version de speech (sin base).

Un `None` de Python en una columna JSONB se escribe por defecto como el JSON `null`, que para un
`IS NULL` no es NULL. La columna `texto_v1` (el texto de dos partes que tuvo una version antes de
convertirse a v2, M-B4) lleva `none_as_null`: el `None` es NULL de SQL, que es como se distingue una
version que nunca fue v1 o que se edito despues. Se razona con la sentencia compilada para el
dialecto de PostgreSQL porque la prueba contra la base (`test_mowa_mes_speech_v2_postgres.py`) no
corre en todos los entornos.
"""

import json

from sqlalchemy import insert, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

from app.adapters.persistence.modelos import MowaMesSpeechVersion
from app.adapters.persistence.repositorio_mowa_mes_postgres import _valores_de_contenido
from tests.test_mowa_mes_speech import DATOS_DEL_ORIGINAL
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

    assert [c.name for c in nulables] == ["texto_v1"]
    assert all(c.type.none_as_null for c in nulables)
    assert not _TABLA.c["expresiones"].nullable  # toda version es v2 (M-B4)


def test_guardar_una_version_deja_texto_v1_en_null_de_sql_y_las_expresiones_como_lista() -> None:
    valores = _valores_de_contenido(DATOS_DEL_ORIGINAL)

    insercion = insert(_TABLA).values(nombre="x", nombre_normalizado="x", **valores)
    edicion = update(_TABLA).values(**valores)

    for sentencia in (insercion, edicion):
        assert _como_viaja(sentencia, "texto_v1") is None  # NULL, no la cadena 'null'
        assert json.loads(_como_viaja(sentencia, "expresiones"))[0]["segmento"] == "preventiva"


def test_editar_una_version_borra_su_texto_v1_para_que_el_downgrade_no_lo_resucite() -> None:
    valores = _valores_de_contenido(_v2(TODOS=(_texto("a"),)))

    assert set(valores) == {"texto_v1", "expresiones"}
    assert valores["texto_v1"] is None
    assert [e["segmento"] for e in valores["expresiones"]][0] == "preventiva"


def test_el_modelo_ya_no_tiene_los_checks_de_formato() -> None:
    nombres = {str(getattr(c, "name", "")) for c in _TABLA.constraints}

    assert not any(n.endswith(("formato_valido", "contenido_segun_formato")) for n in nombres)
    assert "formato" not in _TABLA.c
