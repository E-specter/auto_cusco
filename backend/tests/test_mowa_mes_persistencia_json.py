"""Como SQLAlchemy manda a PostgreSQL el contenido de una version de speech (sin base).

Un `None` de Python en una columna JSONB se escribe por defecto como el JSON `null`, que para un
`IS NULL` no es NULL. La columna `texto_v1` (el texto de dos partes que tuvo una version antes de
convertirse a v2, M-B4) lleva `none_as_null`: el `None` es NULL de SQL, que es como se distingue una
version que nunca fue v1 o que se edito despues. `expresiones` es NOT NULL y TAMBIEN la lleva: sin
ella, un `None` se guardaria como el JSON `null`, que pasa el NOT NULL y deja una version sin
expresiones (el fallo que encontro `-ConBase` en M-B4). Se razona con la sentencia compilada para el
dialecto de PostgreSQL porque la prueba contra la base (`test_mowa_mes_speech_v2_postgres.py`) no
corre en todos los entornos.
"""

import json

import pytest
from sqlalchemy import insert, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

from app.adapters.persistence.modelos import Base, MowaMesSpeechVersion
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


# JSONB que no llevan `none_as_null`, fuera de la version del speech y de las de MOWA MES
# (inventario de M-B4; las 5 de campana y fila cargada ya la llevan, T-MM-B14). No se tocan:
# cambiarlas cambia la semantica de NULL frente a JSON null en datos que ya existen. En una
# columna NOT NULL de la lista un `None` se colaria pasando el NOT NULL como JSON `null`; en una
# nulable quedaria como JSON `null` y no como NULL. Una columna nueva NO puede sumarse a la lista
# sin decidirlo a proposito, y si una de la lista recibe la opcion, hay que quitarla de aqui.
JSONB_SIN_NONE_AS_NULL = {
    # NOT NULL
    "borrador_carga_archivo.opciones",
    "borrador_carga_archivo.analisis",
    "carga.opciones_lectura",
    "definicion_carga_version.contenido",
    "seleccion.filtros",
    "seleccion.indicadores",
    # nulables
    "carga.cabeceras_originales",
    "carga.mapeo",
    "carga_auditoria.detalle",
    "carga_fila.extras",
}


def _jsonb_del_modelo() -> dict[str, JSONB]:
    return {
        f"{tabla.name}.{c.name}": c
        for tabla in Base.metadata.tables.values()
        for c in tabla.columns
        if isinstance(c.type, JSONB)
    }


def test_las_columnas_jsonb_de_la_version_escriben_none_como_null_de_sql() -> None:
    columnas = [c for c in _TABLA.columns if isinstance(c.type, JSONB)]

    assert {c.name for c in columnas} == {"texto_v1", "expresiones"}
    assert all(c.type.none_as_null for c in columnas)  # nulables o no: ver el docstring
    assert [c.name for c in columnas if c.nullable] == ["texto_v1"]
    assert not _TABLA.c["expresiones"].nullable  # toda version es v2 (M-B4)


def test_un_none_en_expresiones_viaja_como_null_de_sql_y_no_como_json_null() -> None:
    # Lo que el NOT NULL rechaza; como JSON `null` pasaria y dejaria `expresiones = null`.
    insercion = insert(_TABLA).values(nombre="x", nombre_normalizado="x", expresiones=None)
    edicion = update(_TABLA).values(expresiones=None)

    for sentencia in (insercion, edicion):
        assert _como_viaja(sentencia, "expresiones") is None


def test_toda_jsonb_not_null_del_modelo_lleva_none_as_null_salvo_las_conocidas() -> None:
    sin_la_opcion = {n for n, c in _jsonb_del_modelo().items() if not c.type.none_as_null}

    # Ninguna JSONB NOT NULL nueva sin la opcion; y la lista no guarda columnas que ya la tienen.
    assert sin_la_opcion == JSONB_SIN_NONE_AS_NULL
    assert not any(n.startswith("mowa_mes_speech_version.") for n in sin_la_opcion)


# Las JSONB NOT NULL de MOWA MES (T-MM-B14): un `None` no puede llegar como JSON `null`.
JSONB_NOT_NULL_DE_MOWA_MES = [
    "mowa_mes_campana.filtros",
    "mowa_mes_campana.herramientas",
    "mowa_mes_campana.envios",
    "mowa_mes_campana.supervisores",
    "mowa_mes_fila_cargada.advertencias",
]


@pytest.mark.parametrize("nombre", JSONB_NOT_NULL_DE_MOWA_MES)
def test_un_none_en_las_jsonb_not_null_de_mowa_mes_viaja_como_null_de_sql(nombre) -> None:
    columna = _jsonb_del_modelo()[nombre]
    tabla = columna.table
    claves = {c.name: 1 for c in tabla.primary_key.columns}  # sin aviso de clave sin valor

    assert columna.type.none_as_null and not columna.nullable
    for sentencia in (
        insert(tabla).values(**{**claves, columna.name: None}),
        update(tabla).values(**{columna.name: None}),
    ):
        assert _como_viaja(sentencia, columna.name) is None  # NULL de SQL: lo rechaza el NOT NULL


def test_el_modelo_declara_el_check_de_que_expresiones_es_una_lista() -> None:
    cheques = {c.name: str(c.sqltext) for c in _TABLA.constraints if hasattr(c, "sqltext")}

    assert cheques["ck_mowa_mes_speech_version_expresiones_es_una_lista"] == (
        "jsonb_typeof(expresiones) = 'array'"
    )


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
