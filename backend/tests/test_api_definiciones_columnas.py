"""Los endpoints de definiciones guardadas (B4b, RF-51): sobre el repositorio en memoria.

La integracion con PostgreSQL esta en `test_definiciones_columnas_postgres.py`.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.definiciones_columnas import obtener_servicio_definiciones
from app.core.entities.definiciones_columnas import MAXIMO_COLUMNAS
from app.core.services.contextos_texto import contexto_cartera
from app.core.services.definiciones_columnas.servicio import DefinicionesColumnasService
from app.main import app
from tests.definiciones_memoria import RepositorioEnMemoria


@pytest.fixture
def cliente():
    servicio = DefinicionesColumnasService(RepositorioEnMemoria(), contexto_cartera())
    app.dependency_overrides[obtener_servicio_definiciones] = lambda: servicio
    try:
        yield TestClient(app), servicio
    finally:
        app.dependency_overrides.clear()


def _texto(valor: str) -> dict:
    return {"tipo": "texto", "valor": valor}


def _variable(nombre: str, *funciones: dict) -> dict:
    return {"tipo": "variable", "nombre": nombre, "funciones": list(funciones)}


def _columna(nombre: str, orden: int, *nodos: dict, **extra) -> dict:
    return {"nombre": nombre, "orden": orden, "expresion": {"nodos": list(nodos)}, **extra}


def _definicion(nombre: str | None = "SMS", *columnas: dict, **extra) -> dict:
    cuerpo = {"columnas": list(columnas) or [_columna("a", 0, _variable("titular"))], **extra}
    if nombre is not None:
        cuerpo["nombre"] = nombre
    return cuerpo


COMPLETA = _definicion(
    "SMS preventiva",
    _columna(
        "mensaje",
        1,
        _texto("Hola "),
        _variable("titular", {"nombre": "primeros", "args": [4]}),
        variantes=[{"segmento": "1_a_8", "expresion": {"nodos": [_texto("Pronto")]}}],
        valor_por_defecto="sin dato",
    ),
    _columna(
        "vence",
        0,
        _variable(
            "fecha_vencimiento_cuota",
            {"nombre": "sumar_dias", "args": [{"variable": "dias_atraso"}]},
        ),
        tipo="fecha",
        formato_fecha="dd/mm/aaaa",
    ),
    _columna(
        "monto",
        2,
        _variable("saldo_capital_pendiente"),
        tipo="financiero",
        formato_financiero={"separador_miles": ".", "separador_decimal": ",", "decimales": 2},
    ),
    segmentacion={},
    proteger_formulas=False,
)


# --- Guardar y leer -------------------------------------------------------------------------------


def test_se_guarda_y_se_devuelve_con_su_version_1(cliente) -> None:
    client, _ = cliente

    respuesta = client.post("/definiciones-columnas", json=COMPLETA)

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert (cuerpo["nombre"], cuerpo["version_vigente"]) == ("SMS preventiva", 1)
    assert [v["numero"] for v in cuerpo["versiones"]] == [1]
    assert cuerpo["version"]["numero"] == 1
    assert cuerpo["version"]["usada_en"] is None and cuerpo["version"]["usada"] is False
    assert cuerpo["creado_en"] and cuerpo["actualizado_en"]


def test_lo_que_se_devuelve_es_la_definicion_canonica_con_las_columnas_por_orden(cliente) -> None:
    client, _ = cliente

    contenido = client.post("/definiciones-columnas", json=COMPLETA).json()["version"]["contenido"]

    assert contenido["proteger_formulas"] is False
    assert [(c["nombre"], c["orden"]) for c in contenido["columnas"]] == [
        ("vence", 0),
        ("mensaje", 1),
        ("monto", 2),
    ]
    vence, mensaje, monto = contenido["columnas"]
    assert (vence["tipo"], vence["formato_fecha"]) == ("fecha", "dd/mm/aaaa")
    assert vence["expresion"]["nodos"][0]["funciones"] == [
        {"nombre": "sumar_dias", "args": [{"variable": "dias_atraso"}]}
    ]
    assert mensaje["expresion"]["nodos"][0] == {"tipo": "texto", "valor": "Hola "}
    assert mensaje["expresion"]["nodos"][1] == {
        "tipo": "variable",
        "nombre": "titular",
        "funciones": [{"nombre": "primeros", "args": [4]}],
        "obligatoria": False,
    }
    assert mensaje["valor_por_defecto"] == "sin dato"
    assert mensaje["variantes"][0]["segmento"] == "1_a_8"
    assert monto["formato_financiero"] == {
        "separador_miles": ".",
        "separador_decimal": ",",
        "decimales": 2,
    }


def test_la_segmentacion_se_devuelve_resuelta(cliente) -> None:
    client, _ = cliente

    segmentacion = client.post("/definiciones-columnas", json=COMPLETA).json()["version"][
        "contenido"
    ]["segmentacion"]

    assert segmentacion["politica"] == "excluir"
    assert segmentacion["criterio"]["tipo"] == "calculado"
    assert segmentacion["criterio"]["variable_dias"] == "dias_atraso_ajustados"
    assert segmentacion["criterio"]["tabla"][1] == {
        "clave": "1_a_8",
        "etiqueta": "1 a 8",
        "desde": 1,
        "hasta": 8,
    }


def test_sin_segmentacion_se_devuelve_nula_y_un_criterio_por_campo_se_conserva(cliente) -> None:
    client, _ = cliente

    sin = client.post("/definiciones-columnas", json=_definicion("sin")).json()
    campo = client.post(
        "/definiciones-columnas",
        json=_definicion(
            "por campo",
            _columna(
                "a",
                0,
                _texto("x"),
                variantes=[{"segmento": "CUSCO", "expresion": {"nodos": []}}],
            ),
            segmentacion={
                "criterio": {"tipo": "campo", "campo": "region"},
                "politica": "usar_por_defecto",
            },
        ),
    ).json()

    assert sin["version"]["contenido"]["segmentacion"] is None
    assert campo["version"]["contenido"]["segmentacion"] == {
        "criterio": {"tipo": "campo", "campo": "region"},
        "politica": "usar_por_defecto",
    }


def test_se_lee_por_id_con_la_version_vigente_o_la_pedida(cliente) -> None:
    client, _ = cliente
    id_ = client.post(
        "/definiciones-columnas", json=_definicion("SMS", _columna("v1", 0, _texto("a")))
    ).json()["id"]
    client.post(
        f"/definiciones-columnas/{id_}/versiones",
        json=_definicion(None, _columna("v2", 0, _texto("b"))),
    )

    vigente = client.get(f"/definiciones-columnas/{id_}").json()
    primera = client.get(f"/definiciones-columnas/{id_}", params={"version": 1}).json()

    assert (vigente["version"]["numero"], vigente["version_vigente"]) == (2, 2)
    assert vigente["version"]["contenido"]["columnas"][0]["nombre"] == "v2"
    assert (primera["version"]["numero"], primera["version_vigente"]) == (1, 2)
    assert primera["version"]["contenido"]["columnas"][0]["nombre"] == "v1"
    assert [v["numero"] for v in primera["versiones"]] == [1, 2]
    assert "contenido" not in primera["versiones"][0]  # el listado de versiones va sin contenido


def test_una_version_nueva_es_201_y_deja_las_anteriores_intactas(cliente) -> None:
    client, _ = cliente
    id_ = client.post("/definiciones-columnas", json=_definicion("SMS")).json()["id"]

    respuesta = client.post(
        f"/definiciones-columnas/{id_}/versiones",
        json=_definicion("sms", _columna("otra", 0, _texto("z"))),
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert (cuerpo["version"]["numero"], cuerpo["nombre"]) == (2, "SMS")
    assert (
        client.get(f"/definiciones-columnas/{id_}", params={"version": 1}).json()["version"][
            "contenido"
        ]["columnas"][0]["nombre"]
        == "a"
    )


def test_el_listado_trae_lo_de_c7_ordenado_por_nombre(cliente) -> None:
    client, servicio = cliente
    segunda = client.post("/definiciones-columnas", json=_definicion("b segunda")).json()["id"]
    client.post("/definiciones-columnas", json=_definicion("A primera"))
    client.post(f"/definiciones-columnas/{segunda}/versiones", json=_definicion(None))
    servicio.marcar_usada(segunda, 2)

    listado = client.get("/definiciones-columnas").json()

    assert [
        (d["nombre"], d["version_vigente"], d["cantidad_versiones"], d["vigente_usada"])
        for d in listado
    ] == [
        ("A primera", 1, 1, False),
        ("b segunda", 2, 2, True),
    ]
    assert set(listado[0]) == {
        "id",
        "nombre",
        "version_vigente",
        "cantidad_versiones",
        "actualizado_en",
        "vigente_usada",
    }


def test_usada_en_se_ve_en_la_version_usada(cliente) -> None:
    client, servicio = cliente
    id_ = client.post("/definiciones-columnas", json=_definicion("SMS")).json()["id"]
    servicio.marcar_usada(id_, 1)

    version = client.get(f"/definiciones-columnas/{id_}").json()["version"]

    assert version["usada"] is True and version["usada_en"] is not None


# --- Errores --------------------------------------------------------------------------------------


def test_un_nombre_repetido_es_409_con_su_codigo(cliente) -> None:
    client, _ = cliente
    client.post("/definiciones-columnas", json=_definicion("SMS"))

    respuesta = client.post("/definiciones-columnas", json=_definicion(" sms"))

    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "nombre_repetido"
    assert "detail" in respuesta.json()


def test_lo_que_no_existe_es_404_con_su_codigo(cliente) -> None:
    client, _ = cliente
    id_ = client.post("/definiciones-columnas", json=_definicion("SMS")).json()["id"]

    sin_definicion = client.get("/definiciones-columnas/999")
    sin_version = client.get(f"/definiciones-columnas/{id_}", params={"version": 9})
    nueva_sin_definicion = client.post(
        "/definiciones-columnas/999/versiones", json=_definicion(None)
    )

    assert [r.status_code for r in (sin_definicion, sin_version, nueva_sin_definicion)] == [
        404,
        404,
        404,
    ]
    assert sin_definicion.json()["codigo"] == "definicion_no_encontrada"
    assert sin_version.json()["codigo"] == "version_no_encontrada"
    assert nueva_sin_definicion.json()["codigo"] == "definicion_no_encontrada"


def test_una_definicion_con_problemas_es_400_con_los_problemas_ubicados(cliente) -> None:
    client, servicio = cliente
    dato = _definicion(
        "",
        _columna("ok", 0, _variable("titular")),
        _columna(
            "mal", 1, _texto("a"), _variable("inventada", {"nombre": "primeros", "args": [0]})
        ),
        _columna("otra", 2, _variable("inventada")),
    )

    respuesta = client.post("/definiciones-columnas", json=dato)

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "definicion_invalida" and cuerpo["detail"]
    problemas = [
        (p["codigo"], p["columna"], p["campo"], p["segmento"]) for p in cuerpo["problemas"]
    ]
    assert problemas[0] == ("definicion_invalida", None, "nombre", None)
    assert ("variable_desconocida", 1, None, None) in problemas
    assert ("variable_desconocida", 2, None, None) in problemas
    nodo = next(p for p in cuerpo["problemas"] if p["columna"] == 1)
    assert nodo["ubicacion"]["nodo"] == 1
    assert servicio.listar() == []  # con problemas no se guarda nada


def test_primero_se_informa_la_forma_y_despues_el_contenido(cliente) -> None:
    """Un problema de forma (fecha sin marcas) se informa antes de compilar el contenido."""
    client, _ = cliente
    dato = _definicion(
        "x",
        _columna("mal", 0, _variable("inventada")),
        _columna(
            "fecha", 1, _variable("fecha_vencimiento_cuota"), tipo="fecha", formato_fecha="%d/%m/%Y"
        ),
    )

    problemas = client.post("/definiciones-columnas", json=dato).json()["problemas"]

    assert [(p["codigo"], p["columna"], p["campo"]) for p in problemas] == [
        ("parametro_invalido", 1, "formato_fecha")
    ]


def test_los_problemas_de_una_variante_traen_su_segmento(cliente) -> None:
    client, _ = cliente
    dato = _definicion(
        "x",
        _columna(
            "a",
            0,
            _texto("x"),
            variantes=[{"segmento": "1_a_8", "expresion": {"nodos": [_variable("inventada")]}}],
        ),
        segmentacion={},
    )

    problema = client.post("/definiciones-columnas", json=dato).json()["problemas"][0]

    assert (problema["codigo"], problema["columna"], problema["segmento"]) == (
        "variable_desconocida",
        0,
        "1_a_8",
    )


def test_el_limite_de_columnas_es_un_400(cliente) -> None:
    client, _ = cliente
    columnas = [_columna(f"c{i}", i, _texto("x")) for i in range(MAXIMO_COLUMNAS + 1)]

    respuesta = client.post("/definiciones-columnas", json=_definicion("x", *columnas))

    assert respuesta.status_code == 400
    assert [p["codigo"] for p in respuesta.json()["problemas"]] == ["limite_excedido"]


def test_cambiar_el_nombre_en_una_version_es_400(cliente) -> None:
    client, _ = cliente
    id_ = client.post("/definiciones-columnas", json=_definicion("SMS")).json()["id"]

    respuesta = client.post(f"/definiciones-columnas/{id_}/versiones", json=_definicion("Otro"))

    assert respuesta.status_code == 400
    assert [(p["columna"], p["campo"]) for p in respuesta.json()["problemas"]] == [(None, "nombre")]


def test_una_forma_imposible_se_informa_como_problema_y_no_como_422(cliente) -> None:
    client, _ = cliente
    dato = _definicion("x", _columna("a", 0, {"tipo": "imagen"}))

    respuesta = client.post("/definiciones-columnas", json=dato)

    assert respuesta.status_code == 400
    assert respuesta.json()["problemas"][0]["codigo"] == "expresion_invalida"


def test_el_pedido_sin_columnas_o_sin_orden_es_422_del_esquema(cliente) -> None:
    client, _ = cliente

    sin_columnas = client.post("/definiciones-columnas", json={"nombre": "x"})
    sin_orden = client.post(
        "/definiciones-columnas",
        json={"nombre": "x", "columnas": [{"nombre": "a", "expresion": {"nodos": []}}]},
    )

    assert (sin_columnas.status_code, sin_orden.status_code) == (422, 422)


def test_una_columna_recien_creada_da_un_problema_ubicado_y_no_un_500(cliente) -> None:
    client, _ = cliente
    dato = _definicion(
        "x",
        _columna("a", 0, _variable("titular")),
        {"nombre": "", "orden": 1, "expresion": {"nodos": []}},
    )

    respuesta = client.post("/definiciones-columnas", json=dato)

    assert respuesta.status_code == 400
    assert [(p["columna"], p["campo"]) for p in respuesta.json()["problemas"]] == [(1, "nombre")]


def test_los_nulos_explicitos_equivalen_a_campos_ausentes(cliente) -> None:
    """El cliente tipado envia `null` en lo que no usa: no es una forma imposible."""
    client, _ = cliente
    dato = {
        "nombre": "con nulos",
        "proteger_formulas": None,
        "segmentacion": None,
        "columnas": [
            {
                "nombre": "a",
                "orden": 0,
                "expresion": {"nodos": [{"tipo": "texto", "valor": "x", "nombre": None}]},
                "tipo": None,
                "formato_fecha": None,
                "formato_financiero": None,
                "valor_por_defecto": None,
                "variantes": None,
            }
        ],
    }

    respuesta = client.post("/definiciones-columnas", json=dato)

    assert respuesta.status_code == 201
    contenido = respuesta.json()["version"]["contenido"]
    assert contenido["proteger_formulas"] is True
    assert contenido["columnas"][0]["tipo"] == "texto"


def test_el_orden_explicito_se_devuelve_tal_cual(cliente) -> None:
    client, _ = cliente
    dato = _definicion("x", _columna("b", 20, _texto("b")), _columna("a", 5, _texto("a")))

    columnas = client.post("/definiciones-columnas", json=dato).json()["version"]["contenido"][
        "columnas"
    ]

    assert [(c["nombre"], c["orden"]) for c in columnas] == [("a", 5), ("b", 20)]


# --- Renombrar (RF-56) -----------------------------------------------------------------------


def _renombrar(client, id_: int, nombre):
    return client.patch(f"/definiciones-columnas/{id_}", json={"nombre": nombre})


def test_renombrar_cambia_solo_el_nombre_y_las_versiones_quedan_igual(cliente) -> None:
    client, servicio = cliente
    id_ = client.post("/definiciones-columnas", json=_definicion("SMS")).json()["id"]
    client.post(f"/definiciones-columnas/{id_}/versiones", json=_definicion("SMS"))
    servicio.marcar_usada(id_, 1)
    antes = client.get(f"/definiciones-columnas/{id_}").json()
    primera_antes = client.get(f"/definiciones-columnas/{id_}", params={"version": 1}).json()

    respuesta = _renombrar(client, id_, "SMS preventiva")

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert cuerpo["nombre"] == "SMS preventiva"
    assert cuerpo["version_vigente"] == antes["version_vigente"] == 2
    assert cuerpo["versiones"] == antes["versiones"]  # mismos numeros, fechas y usada_en
    assert cuerpo["version"] == antes["version"]  # y el contenido de la vigente
    assert cuerpo["actualizado_en"] > antes["actualizado_en"]
    assert cuerpo["creado_en"] == antes["creado_en"]
    primera = client.get(f"/definiciones-columnas/{id_}", params={"version": 1}).json()
    assert primera["version"] == primera_antes["version"]
    assert primera["version"]["usada"] is True


def test_lo_renombrado_se_ve_en_el_listado_y_en_la_lectura(cliente) -> None:
    client, _ = cliente
    id_ = client.post("/definiciones-columnas", json=_definicion("SMS")).json()["id"]

    _renombrar(client, id_, "Cobranza")

    assert [d["nombre"] for d in client.get("/definiciones-columnas").json()] == ["Cobranza"]
    assert client.get(f"/definiciones-columnas/{id_}").json()["nombre"] == "Cobranza"


def test_renombrar_a_un_nombre_ajeno_es_409_con_su_codigo(cliente) -> None:
    client, _ = cliente
    client.post("/definiciones-columnas", json=_definicion("Preventiva"))
    id_ = client.post("/definiciones-columnas", json=_definicion("Mora")).json()["id"]

    respuesta = _renombrar(client, id_, " PREVENTIVA")

    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "nombre_repetido"
    assert client.get(f"/definiciones-columnas/{id_}").json()["nombre"] == "Mora"


def test_renombrar_a_si_misma_no_es_un_error_y_no_mueve_actualizado_en(cliente) -> None:
    client, _ = cliente
    id_ = client.post("/definiciones-columnas", json=_definicion("SMS")).json()["id"]
    antes = client.get(f"/definiciones-columnas/{id_}").json()

    mismo = _renombrar(client, id_, "SMS")
    mayusculas = _renombrar(client, id_, "sms")  # solo cambian las mayusculas: es un cambio

    assert mismo.status_code == 200 and mismo.json()["actualizado_en"] == antes["actualizado_en"]
    assert mayusculas.status_code == 200
    assert mayusculas.json()["nombre"] == "sms"
    assert mayusculas.json()["actualizado_en"] > antes["actualizado_en"]


def test_renombrar_algo_que_no_existe_es_404_con_su_codigo(cliente) -> None:
    client, _ = cliente

    respuesta = _renombrar(client, 999, "Otro")

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "definicion_no_encontrada"


@pytest.mark.parametrize("nombre", ["", "    ", "x" * 121])
def test_renombrar_con_un_nombre_vacio_o_largo_es_400_ubicado_en_el_nombre(cliente, nombre) -> None:
    client, _ = cliente
    id_ = client.post("/definiciones-columnas", json=_definicion("SMS")).json()["id"]

    respuesta = _renombrar(client, id_, nombre)

    cuerpo = respuesta.json()
    assert respuesta.status_code == 400
    assert cuerpo["codigo"] == "definicion_invalida"
    assert [(p["campo"], p["columna"], p["codigo"]) for p in cuerpo["problemas"]] == [
        ("nombre", None, "definicion_invalida")
    ]
    assert client.get(f"/definiciones-columnas/{id_}").json()["nombre"] == "SMS"


def test_renombrar_sin_nombre_o_con_algo_que_no_es_texto_es_422_del_esquema(cliente) -> None:
    client, _ = cliente
    id_ = client.post("/definiciones-columnas", json=_definicion("SMS")).json()["id"]

    sin_nombre = client.patch(f"/definiciones-columnas/{id_}", json={})
    no_texto = client.patch(f"/definiciones-columnas/{id_}", json={"nombre": 5})

    assert (sin_nombre.status_code, no_texto.status_code) == (422, 422)


def test_el_contrato_declara_el_patch_con_sus_errores(cliente) -> None:
    client, _ = cliente

    operacion = client.get("/openapi.json").json()["paths"][
        "/definiciones-columnas/{definicion_id}"
    ]["patch"]

    assert {"200", "400", "404", "409", "422"} <= set(operacion["responses"])
