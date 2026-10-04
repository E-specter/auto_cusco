"""El speech v2 de MOWA MES contra PostgreSQL real (opcional). ESCRITAS, NO CORRIDAS en B6.

Corre solo con AUTO_CUSCO_DB_TESTS=1 y la base migrada (`alembic upgrade head`, que agrega
`formato` y `expresiones` a `mowa_mes_speech_version`). Reusa el entorno de
`test_mowa_mes_campanas_postgres.py`: una sabana sintetica de la fecha 2099-06-01, la
configuracion y los supervisores que se restituyen al terminar, y las versiones de speech
con el prefijo de prueba que se borran. Numeros 900000xxx.

Lo que solo aqui se verifica: las versiones v1 que ya existian siguen siendo v1 con su huella, los
CHECK de la base (formato valido y contenido segun el formato), el round trip de las expresiones por
JSONB, que editar no cambia el formato, y la huella de una v2 comprobada dentro de la transaccion
de crear la campana.
"""

import os

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.exc import IntegrityError

from app.adapters.persistence.modelos import MowaMesCampana, MowaMesSpeechVersion
from app.adapters.persistence.repositorio_mowa_mes_postgres import RepositorioMowaMesPostgres
from app.core.entities.mowa_mes import ExpresionSegmento, FormatoSpeech, Segmento
from app.core.services.plataformas.mowa_mes.campana import huella_de
from app.core.services.texto_enriquecido.serializacion import expresion_desde_dict
from tests import test_mowa_mes_campanas_postgres as base
from tests.test_mowa_mes_campanas_postgres import (
    FECHA,
    PREFIJO,
    _crear,
    _previsualizar,
)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

cliente = base.cliente  # la fixture del entorno sintetico, la misma de las campanas
_SPEECH = MowaMesSpeechVersion.__table__
_CAMPANA = MowaMesCampana.__table__
HUELLA_DEL_SPEECH_ORIGINAL = "297c227cfdd0bb5e1636e08d4ed6cebab971d724c84223acfdb0cfebc2fcf88a"
SEGMENTOS = [s.value for s in Segmento]


def _nodo_titular() -> dict:
    return {
        "tipo": "variable",
        "nombre": "titular",
        "funciones": [{"nombre": "primeros", "args": [8]}],
    }


def _expresiones(*nodos: dict) -> list[dict]:
    return [{"segmento": s, "expresion": {"nodos": list(nodos)}} for s in SEGMENTOS]


CUERPO_V2 = _expresiones(
    _nodo_titular(),
    {"tipo": "texto", "valor": " ñandú — vence el "},
    {
        "tipo": "variable",
        "nombre": "fecha_vencimiento_cuota",
        "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
    },
)


def _crear_v2(client, nombre: str, expresiones=None, **extra):
    return client.post(
        "/mowa-mes/speech",
        json={"nombre": f"{PREFIJO}{nombre}", "expresiones": expresiones or CUERPO_V2, **extra},
    )


def _fila(engine, speech_id: int):
    with engine.connect() as cx:
        return cx.execute(select(_SPEECH).where(_SPEECH.c.id == speech_id)).one()


# --- Las versiones que ya existian ---------------------------------------------------------------


def test_todas_las_versiones_existentes_son_v1_con_partes_y_sin_expresiones(cliente) -> None:
    _, engine = cliente

    with engine.connect() as cx:
        filas = cx.execute(
            select(_SPEECH.c.nombre, _SPEECH.c.formato, _SPEECH.c.expresiones).where(
                ~_SPEECH.c.nombre_normalizado.startswith(PREFIJO.casefold())
            )
        ).all()

    assert filas, "falta el Speech original: aplica las migraciones"
    assert {(f.formato, f.expresiones) for f in filas} == {("v1", None)}


def test_el_speech_original_conserva_su_huella(cliente) -> None:
    _, engine = cliente
    repositorio = RepositorioMowaMesPostgres(engine)

    original = next(v for v in repositorio.listar_speech() if v.original)

    assert original.datos.formato is FormatoSpeech.V1
    assert huella_de(original.datos) == HUELLA_DEL_SPEECH_ORIGINAL


# --- Guardar y leer una v2 -----------------------------------------------------------------------


def test_una_v2_guardada_vuelve_igual_de_la_base(cliente) -> None:
    client, engine = cliente

    creada = _crear_v2(client, "ida y vuelta")
    repositorio = RepositorioMowaMesPostgres(engine)
    leida = repositorio.obtener_speech(creada.json()["id"])
    fila = _fila(engine, creada.json()["id"])

    assert creada.status_code == 201, creada.text
    assert leida.datos.formato is FormatoSpeech.V2
    assert leida.datos.partes == ()
    esperadas = tuple(
        ExpresionSegmento(Segmento(e["segmento"]), expresion_desde_dict(e["expresion"]))
        for e in CUERPO_V2
    )
    assert leida.datos.expresiones == esperadas  # nodos, textos con tildes y argumentos
    assert (fila.formato, fila.partes) == ("v2", [])
    assert [e["segmento"] for e in fila.expresiones] == SEGMENTOS


def test_la_huella_de_una_v2_sale_igual_antes_y_despues_de_guardarla(cliente) -> None:
    client, engine = cliente
    id_ = _crear_v2(client, "huella").json()["id"]

    previa = _previsualizar(client, speech_id=id_)
    guardada = RepositorioMowaMesPostgres(engine).obtener_speech(id_)

    assert previa["speech"]["formato"] == "v2"
    assert previa["speech"]["huella"] == huella_de(guardada.datos)


def test_un_nombre_repetido_entre_formatos_lo_rechaza_la_base(cliente) -> None:
    client, _ = cliente
    _crear_v2(client, "unico")

    partes = [{"segmento": s, "parte_1": "a", "parte_2": "b"} for s in SEGMENTOS]
    repetido = client.post("/mowa-mes/speech", json={"nombre": f"{PREFIJO}UNICO", "partes": partes})

    assert repetido.status_code == 409


# --- Lo que hay en la columna, leido con SQL crudo (sin el CHECK) ------------------------------


_CRUDO = text(
    "SELECT formato, expresiones IS NULL AS expresiones_nulas, "
    "jsonb_typeof(expresiones) AS tipo_expresiones, partes IS NULL AS partes_nulas, "
    "jsonb_typeof(partes) AS tipo_partes, partes = '[]'::jsonb AS partes_vacias "
    "FROM mowa_mes_speech_version WHERE id = :id"
)


def _crudo(engine, speech_id: int):
    with engine.connect() as cx:
        return cx.execute(_CRUDO, {"id": speech_id}).one()


def test_una_v1_guarda_expresiones_como_null_de_sql_y_las_partes_como_lista(cliente) -> None:
    client, engine = cliente
    partes = [{"segmento": s, "parte_1": "a", "parte_2": "b"} for s in SEGMENTOS]
    id_ = client.post(
        "/mowa-mes/speech", json={"nombre": f"{PREFIJO}crudo v1", "partes": partes}
    ).json()["id"]

    fila = _crudo(engine, id_)

    assert (fila.formato, fila.expresiones_nulas, fila.tipo_expresiones) == ("v1", True, None)
    assert (fila.partes_nulas, fila.tipo_partes, fila.partes_vacias) == (False, "array", False)


def test_una_v2_guarda_expresiones_como_lista_y_las_partes_como_lista_vacia(cliente) -> None:
    client, engine = cliente
    id_ = _crear_v2(client, "crudo v2").json()["id"]

    fila = _crudo(engine, id_)

    assert (fila.formato, fila.expresiones_nulas, fila.tipo_expresiones) == ("v2", False, "array")
    # `partes` es NOT NULL: en una v2 es la lista vacia, nunca NULL ni el JSON null
    assert (fila.partes_nulas, fila.tipo_partes, fila.partes_vacias) == (False, "array", True)


def test_editar_no_cambia_lo_que_hay_en_la_columna(cliente) -> None:
    client, engine = cliente
    partes = [{"segmento": s, "parte_1": "a", "parte_2": "b"} for s in SEGMENTOS]
    v1 = client.post(
        "/mowa-mes/speech", json={"nombre": f"{PREFIJO}crudo ed v1", "partes": partes}
    ).json()["id"]
    v2 = _crear_v2(client, "crudo ed v2").json()["id"]

    client.put(f"/mowa-mes/speech/{v1}", json={"nombre": f"{PREFIJO}crudo ed v1", "partes": partes})
    client.put(
        f"/mowa-mes/speech/{v2}",
        json={"nombre": f"{PREFIJO}crudo ed v2", "expresiones": _expresiones(_nodo_titular())},
    )

    uno, dos = _crudo(engine, v1), _crudo(engine, v2)
    assert (uno.expresiones_nulas, uno.tipo_expresiones) == (True, None)
    assert (dos.expresiones_nulas, dos.tipo_expresiones, dos.partes_vacias) == (
        False,
        "array",
        True,
    )


def test_el_speech_original_tiene_expresiones_null_de_sql(cliente) -> None:
    _, engine = cliente
    with engine.connect() as cx:
        id_ = cx.execute(select(_SPEECH.c.id).where(_SPEECH.c.original)).scalar_one()

    fila = _crudo(engine, id_)

    assert (fila.formato, fila.expresiones_nulas, fila.tipo_expresiones) == ("v1", True, None)
    assert fila.tipo_partes == "array" and fila.partes_vacias is False


def test_ninguna_fila_guarda_el_json_null_en_el_contenido(cliente) -> None:
    client, engine = cliente
    _crear_v2(client, "sin json null")

    with engine.connect() as cx:
        con_json_null = cx.execute(
            text(
                "SELECT count(*) FROM mowa_mes_speech_version "
                "WHERE jsonb_typeof(expresiones) = 'null' OR jsonb_typeof(partes) = 'null'"
            )
        ).scalar_one()

    assert con_json_null == 0


# --- Las restricciones de la base ----------------------------------------------------------------


def _insertar(engine, **valores):
    base = {
        "nombre": f"{PREFIJO}check",
        "nombre_normalizado": f"{PREFIJO}check".casefold(),
        "partes": [],
    }
    with engine.begin() as cx:
        cx.execute(insert(_SPEECH).values(**{**base, **valores}))


def test_la_base_rechaza_un_formato_que_no_es_v1_ni_v2(cliente) -> None:
    _, engine = cliente

    with pytest.raises(IntegrityError):
        _insertar(engine, formato="v3", expresiones=None)


def test_la_base_rechaza_una_v2_sin_expresiones_y_una_v1_con_expresiones(cliente) -> None:
    _, engine = cliente

    with pytest.raises(IntegrityError):
        _insertar(engine, formato="v2", expresiones=None)
    with pytest.raises(IntegrityError):
        _insertar(
            engine, nombre=f"{PREFIJO}otro", nombre_normalizado="otro", formato="v1", expresiones=[]
        )


def test_una_fila_sin_formato_es_v1(cliente) -> None:
    """El valor por defecto del servidor: lo que las filas existentes recibieron al migrar."""
    _, engine = cliente
    _insertar(engine, nombre=f"{PREFIJO}defecto", nombre_normalizado=f"{PREFIJO}defecto".casefold())

    with engine.connect() as cx:
        formato = cx.execute(
            select(_SPEECH.c.formato).where(_SPEECH.c.nombre == f"{PREFIJO}defecto")
        ).scalar_one()

    assert formato == "v1"


def test_las_restricciones_existen_con_el_nombre_de_la_migracion(cliente) -> None:
    _, engine = cliente

    with engine.connect() as cx:
        nombres = set(
            cx.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid = 'mowa_mes_speech_version'::regclass AND contype = 'c'"
                )
            ).scalars()
        )

    assert {
        "ck_mowa_mes_speech_version_formato_valido",
        "ck_mowa_mes_speech_version_contenido_segun_formato",
    } <= nombres


# --- Editar --------------------------------------------------------------------------------------


def test_editar_una_v2_sin_usar_la_reemplaza_y_sigue_siendo_v2(cliente) -> None:
    client, engine = cliente
    id_ = _crear_v2(client, "editable").json()["id"]
    nuevas = _expresiones({"tipo": "texto", "valor": "Cuota vencida"})

    respuesta = client.put(
        f"/mowa-mes/speech/{id_}", json={"nombre": f"{PREFIJO}editable", "expresiones": nuevas}
    )

    assert respuesta.status_code == 200, respuesta.text
    fila = _fila(engine, id_)
    assert fila.formato == "v2" and fila.partes == []
    assert fila.expresiones[0]["expresion"]["nodos"] == [
        {"tipo": "texto", "valor": "Cuota vencida"}
    ]


def test_la_base_no_deja_cambiar_el_formato_al_editar(cliente) -> None:
    client, engine = cliente
    id_ = _crear_v2(client, "formato fijo").json()["id"]
    partes = [{"segmento": s, "parte_1": "a", "parte_2": "b"} for s in SEGMENTOS]

    por_http = client.put(
        f"/mowa-mes/speech/{id_}", json={"nombre": f"{PREFIJO}formato fijo", "partes": partes}
    )

    assert por_http.status_code == 400
    assert _fila(engine, id_).formato == "v2"


# --- Una campana con una v2, de punta a punta ----------------------------------------------------


def test_cadena_completa_con_una_v2_por_http(cliente) -> None:
    client, engine = cliente
    id_ = _crear_v2(client, "campana").json()["id"]

    previa = _previsualizar(client, speech_id=id_)
    creada = _crear(client, previa["speech"]["huella"], speech_id=id_)
    campana = creada.json()
    descarga = client.get(f"/mowa-mes/campanas/{campana['id']}/archivos/1")
    speech = client.get(f"/mowa-mes/speech/{id_}").json()

    assert previa["errores"] == [] and previa["puede_crear"] is True
    assert creada.status_code == 201, creada.text
    assert campana["speech"]["id"] == id_
    assert descarga.status_code == 200
    assert speech["usada"] is True and speech["editable"] is False
    with engine.connect() as cx:
        usada = cx.execute(select(_SPEECH.c.usada_en).where(_SPEECH.c.id == id_)).scalar_one()
    assert usada is not None


def test_una_v2_usada_ya_no_se_edita(cliente) -> None:
    client, _ = cliente
    id_ = _crear_v2(client, "usada").json()["id"]
    huella = _previsualizar(client, speech_id=id_)["speech"]["huella"]
    assert _crear(client, huella, speech_id=id_).status_code == 201

    editada = client.put(
        f"/mowa-mes/speech/{id_}",
        json={
            "nombre": f"{PREFIJO}usada",
            "expresiones": _expresiones({"tipo": "texto", "valor": "x"}),
        },
    )

    assert editada.status_code == 409


def test_si_la_v2_cambia_entre_previsualizar_y_crear_es_409_huella_cambiada(cliente) -> None:
    client, engine = cliente
    id_ = _crear_v2(client, "cambia").json()["id"]
    huella = _previsualizar(client, speech_id=id_)["speech"]["huella"]
    client.put(
        f"/mowa-mes/speech/{id_}",
        json={
            "nombre": f"{PREFIJO}cambia",
            "expresiones": _expresiones({"tipo": "texto", "valor": "Otra cosa"}),
        },
    )

    cambiada = _crear(client, huella, speech_id=id_)

    assert cambiada.status_code == 409
    assert cambiada.json()["codigo"] == "huella_cambiada"
    with engine.connect() as cx:
        campanas = cx.execute(select(_CAMPANA.c.id).where(_CAMPANA.c.fecha_corte == FECHA)).all()
        usada = cx.execute(select(_SPEECH.c.usada_en).where(_SPEECH.c.id == id_)).scalar_one()
    assert campanas == [] and usada is None  # no se creo nada ni se marco la version


def test_la_huella_de_una_v1_no_sirve_para_crear_con_una_v2(cliente) -> None:
    client, _ = cliente
    id_ = _crear_v2(client, "otra huella").json()["id"]
    huella_original = _previsualizar(client)["speech"]["huella"]

    cruzada = _crear(client, huella_original, speech_id=id_)

    assert cruzada.status_code == 409 and cruzada.json()["codigo"] == "huella_cambiada"


def test_la_campana_con_la_v1_de_siempre_sigue_igual(cliente) -> None:
    client, _ = cliente

    previa = _previsualizar(client)
    creada = _crear(client, previa["speech"]["huella"])

    assert previa["speech"]["formato"] == "v1"
    assert previa["speech"]["huella"] == HUELLA_DEL_SPEECH_ORIGINAL
    assert creada.status_code == 201, creada.text
