"""El speech v2 de MOWA MES contra PostgreSQL real (opcional). ESCRITAS, NO CORRIDAS en B6.

Corre solo con AUTO_CUSCO_DB_TESTS=1 y la base migrada (`alembic upgrade head`: desde M-B4,
`mowa_mes_speech_version` tiene `expresiones` NOT NULL y `texto_v1` nullable, sin `formato`). Reusa
el entorno de
`test_mowa_mes_campanas_postgres.py`: una sabana sintetica de la fecha 2099-06-01, la
configuracion y los supervisores que se restituyen al terminar, y las versiones de speech
con el prefijo de prueba que se borran. Numeros 900000xxx.

Lo que solo aqui se verifica: las versiones que ya existian son v2 (M-B3) y el original conserva su
texto v1 en `texto_v1` (M-B4), que la base ya no tiene `formato` ni sus CHECK, que `expresiones` es
NOT NULL, el round trip de las expresiones por JSONB, que guardar o editar deja `texto_v1` en NULL,
y la huella de una v2 comprobada dentro de la transaccion de crear la campana.
"""

import os

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.exc import IntegrityError

from app.adapters.persistence.modelos import MowaMesCampana, MowaMesSpeechVersion
from app.adapters.persistence.repositorio_mowa_mes_postgres import RepositorioMowaMesPostgres
from app.core.entities.mowa_mes import ExpresionSegmento, Segmento
from app.core.services.plataformas.mowa_mes.campana import huella_de
from app.core.services.texto_enriquecido.serializacion import expresion_desde_dict
from tests import test_mowa_mes_campanas_postgres as base
from tests.speech_congelado import huella_del_texto_v1
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
# La huella del texto v1 del original (la que registraron las campanas de antes de M-B3) y la de su
# conversion a v2 (la que registran desde entonces): el mensaje es el mismo, la huella no. Desde
# M-B4 la primera ya no la calcula la app: es la de `huella_del_texto_v1` sobre `texto_v1`.
HUELLA_DEL_TEXTO_V1_DEL_ORIGINAL = (
    "297c227cfdd0bb5e1636e08d4ed6cebab971d724c84223acfdb0cfebc2fcf88a"
)
HUELLA_DEL_SPEECH_ORIGINAL = "5b1c556c283ceccd59007114c0da16df3f323ef98b4122d5dc1628b0ef1992b1"
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


def test_todas_las_versiones_existentes_son_v2_con_expresiones(cliente) -> None:
    # T-MM-C11, M-B3 (RF-MM-17): la migracion pasa cada v1 a v2; antes eran todas v1 sin
    # expresiones.
    _, engine = cliente

    with engine.connect() as cx:
        filas = cx.execute(
            select(_SPEECH.c.nombre, _SPEECH.c.expresiones).where(
                ~_SPEECH.c.nombre_normalizado.startswith(PREFIJO.casefold())
            )
        ).all()

    assert filas, "falta el Speech original: aplica las migraciones"
    assert all(f.expresiones for f in filas)


def test_el_speech_original_es_v2_y_conserva_su_texto_v1_en_texto_v1(cliente) -> None:
    # Antes: formato v1 y huella 297c... Ahora: v2 convertido (otra huella, el mismo mensaje) y el
    # texto v1 intacto en `texto_v1` (antes `partes`), cuya huella v1 sigue siendo la de siempre.
    _, engine = cliente
    repositorio = RepositorioMowaMesPostgres(engine)

    original = next(v for v in repositorio.listar_speech() if v.original)
    with engine.connect() as cx:
        texto_v1 = cx.execute(select(_SPEECH.c.texto_v1).where(_SPEECH.c.original)).scalar_one()

    assert huella_de(original.datos) == HUELLA_DEL_SPEECH_ORIGINAL
    assert huella_del_texto_v1(texto_v1) == HUELLA_DEL_TEXTO_V1_DEL_ORIGINAL


# --- Guardar y leer una v2 -----------------------------------------------------------------------


def test_una_v2_guardada_vuelve_igual_de_la_base(cliente) -> None:
    client, engine = cliente

    creada = _crear_v2(client, "ida y vuelta")
    repositorio = RepositorioMowaMesPostgres(engine)
    leida = repositorio.obtener_speech(creada.json()["id"])
    fila = _fila(engine, creada.json()["id"])

    assert creada.status_code == 201, creada.text
    esperadas = tuple(
        ExpresionSegmento(Segmento(e["segmento"]), expresion_desde_dict(e["expresion"]))
        for e in CUERPO_V2
    )
    assert leida.datos.expresiones == esperadas  # nodos, textos con tildes y argumentos
    assert fila.texto_v1 is None  # una version nueva nunca fue v1
    assert [e["segmento"] for e in fila.expresiones] == SEGMENTOS


def test_la_huella_de_una_v2_sale_igual_antes_y_despues_de_guardarla(cliente) -> None:
    client, engine = cliente
    id_ = _crear_v2(client, "huella").json()["id"]

    previa = _previsualizar(client, speech_id=id_)
    guardada = RepositorioMowaMesPostgres(engine).obtener_speech(id_)

    assert previa["speech"]["huella"] == huella_de(guardada.datos)


def test_un_nombre_repetido_lo_rechaza_la_base_sin_distinguir_mayusculas(cliente) -> None:
    client, _ = cliente
    assert _crear_v2(client, "unico").status_code == 201

    repetido = _crear_v2(client, "UNICO")  # el mismo nombre, otra caja

    assert repetido.status_code == 409


# --- Lo que hay en la columna, leido con SQL crudo (sin el CHECK) ------------------------------


_CRUDO = text(
    "SELECT expresiones IS NULL AS expresiones_nulas, "
    "jsonb_typeof(expresiones) AS tipo_expresiones, texto_v1 IS NULL AS texto_nulo, "
    "jsonb_typeof(texto_v1) AS tipo_texto, texto_v1 = '[]'::jsonb AS texto_vacio "
    "FROM mowa_mes_speech_version WHERE id = :id"
)


def _crudo(engine, speech_id: int):
    with engine.connect() as cx:
        return cx.execute(_CRUDO, {"id": speech_id}).one()


def test_una_version_guarda_expresiones_como_lista_y_texto_v1_como_null_de_sql(cliente) -> None:
    client, engine = cliente
    id_ = _crear_v2(client, "crudo v2").json()["id"]

    fila = _crudo(engine, id_)

    assert (fila.expresiones_nulas, fila.tipo_expresiones) == (False, "array")
    # `texto_v1` es nullable: en una version nueva es NULL de SQL, ni el JSON null ni `[]`
    assert (fila.texto_nulo, fila.tipo_texto, fila.texto_vacio) == (True, None, None)


def test_editar_deja_expresiones_como_lista_y_texto_v1_en_null(cliente) -> None:
    client, engine = cliente
    v2 = _crear_v2(client, "crudo ed v2").json()["id"]

    client.put(
        f"/mowa-mes/speech/{v2}",
        json={"nombre": f"{PREFIJO}crudo ed v2", "expresiones": _expresiones(_nodo_titular())},
    )

    dos = _crudo(engine, v2)
    assert (dos.expresiones_nulas, dos.tipo_expresiones, dos.texto_nulo) == (False, "array", True)


def test_editar_una_version_convertida_le_borra_el_texto_v1(cliente) -> None:
    # Una version que la migracion convirtio (tiene `texto_v1`) y que nadie uso. Al editarla ya no
    # es la v1 que fue: si el texto v1 se quedara, un downgrade la volveria a v1 con el texto viejo.
    client, engine = cliente
    texto = [{"segmento": s, "parte_1": "viejo", "parte_2": "texto"} for s in SEGMENTOS]
    _insertar(engine, nombre=f"{PREFIJO}convertida", texto_v1=texto, expresiones=CUERPO_V2)
    with engine.connect() as cx:
        id_ = cx.execute(
            select(_SPEECH.c.id).where(_SPEECH.c.nombre == f"{PREFIJO}convertida")
        ).scalar_one()
    assert _crudo(engine, id_).texto_nulo is False

    editada = client.put(
        f"/mowa-mes/speech/{id_}",
        json={"nombre": f"{PREFIJO}convertida", "expresiones": _expresiones(_nodo_titular())},
    )

    assert editada.status_code == 200, editada.text
    assert _crudo(engine, id_).texto_nulo is True


def test_el_speech_original_tiene_expresiones_y_conserva_el_texto_v1(cliente) -> None:
    # Antes: formato v1, expresiones NULL. Ahora: v2 con expresiones y `texto_v1` con el texto.
    _, engine = cliente
    with engine.connect() as cx:
        id_ = cx.execute(select(_SPEECH.c.id).where(_SPEECH.c.original)).scalar_one()

    fila = _crudo(engine, id_)

    assert (fila.expresiones_nulas, fila.tipo_expresiones) == (False, "array")
    assert fila.tipo_texto == "array" and fila.texto_vacio is False


def test_ninguna_fila_guarda_el_json_null_en_el_contenido(cliente) -> None:
    client, engine = cliente
    _crear_v2(client, "sin json null")

    with engine.connect() as cx:
        con_json_null = cx.execute(
            text(
                "SELECT count(*) FROM mowa_mes_speech_version "
                "WHERE jsonb_typeof(expresiones) = 'null' OR jsonb_typeof(texto_v1) = 'null'"
            )
        ).scalar_one()

    assert con_json_null == 0


# --- Las restricciones de la base ----------------------------------------------------------------


def _insertar(engine, **valores):
    nombre = valores.setdefault("nombre", f"{PREFIJO}check")
    valores.setdefault("nombre_normalizado", nombre.casefold())
    valores.setdefault("expresiones", [])
    with engine.begin() as cx:
        cx.execute(insert(_SPEECH).values(**valores))


def test_la_base_rechaza_una_version_sin_expresiones(cliente) -> None:
    # M-B4: `expresiones` es NOT NULL: toda version es v2. Un None de Python viaja como NULL de SQL
    # (`none_as_null`); sin esa opcion se guardaria como el JSON `null` y pasaria el NOT NULL.
    _, engine = cliente

    with pytest.raises(IntegrityError):
        _insertar(engine, expresiones=None)


@pytest.mark.parametrize("contenido", ["null", "{}", '"texto"', "7"])
def test_la_base_rechaza_expresiones_que_no_sea_una_lista_json_aunque_no_sea_null(
    cliente, contenido
) -> None:
    # El JSON `null` no es NULL de SQL y pasa el NOT NULL: lo cierra el CHECK
    # `expresiones_es_una_lista`, tambien por SQL directo (sin pasar por el modelo).
    _, engine = cliente

    with pytest.raises(IntegrityError), engine.begin() as cx:
        cx.execute(
            text(
                "INSERT INTO mowa_mes_speech_version (nombre, nombre_normalizado, expresiones) "
                "VALUES (:nombre, :normalizado, CAST(:contenido AS jsonb))"
            ),
            {
                "nombre": f"{PREFIJO}no lista",
                "normalizado": f"{PREFIJO}no lista".casefold(),
                "contenido": contenido,
            },
        )


def test_la_base_ya_no_tiene_formato_ni_partes_ni_los_check_de_formato(cliente) -> None:
    _, engine = cliente

    with engine.connect() as cx:
        columnas = set(
            cx.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'mowa_mes_speech_version'"
                )
            ).scalars()
        )
        cheques = set(
            cx.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid = 'mowa_mes_speech_version'::regclass AND contype = 'c'"
                )
            ).scalars()
        )

    assert {"texto_v1", "expresiones"} <= columnas
    assert not {"formato", "partes"} & columnas
    assert not any("formato" in nombre for nombre in cheques)
    assert "ck_mowa_mes_speech_version_expresiones_es_una_lista" in cheques


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
    assert fila.texto_v1 is None
    assert fila.expresiones[0]["expresion"]["nodos"] == [
        {"tipo": "texto", "valor": "Cuota vencida"}
    ]


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


def test_la_huella_del_original_no_sirve_para_crear_con_otra_version(cliente) -> None:
    client, _ = cliente
    id_ = _crear_v2(client, "otra huella").json()["id"]
    huella_original = _previsualizar(client)["speech"]["huella"]

    cruzada = _crear(client, huella_original, speech_id=id_)

    assert cruzada.status_code == 409 and cruzada.json()["codigo"] == "huella_cambiada"


def test_la_campana_con_el_original_convertido_sigue_dando_los_mismos_mensajes(cliente) -> None:
    # Antes: previsualizaba como v1 con la huella 297c... Ahora: v2 convertido, otra huella.
    client, _ = cliente

    previa = _previsualizar(client)
    creada = _crear(client, previa["speech"]["huella"])

    assert previa["speech"]["huella"] == HUELLA_DEL_SPEECH_ORIGINAL
    assert creada.status_code == 201, creada.text
