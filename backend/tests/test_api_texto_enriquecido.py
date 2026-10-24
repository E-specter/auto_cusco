"""Los endpoints del motor de texto enriquecido (B4a, RF-44 y RF-47): catalogo, validacion y
previsualizacion. Solo lectura. Lo unico simulado es la consulta a la cartera.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.cartera import obtener_servicio_cartera
from app.core.entities.cartera import PaginaCartera, SinVersionVigente
from app.core.entities.texto_enriquecido import CodigoTexto
from app.main import app

CORTE = "2026-09-10"


class CarteraFalsa:
    def __init__(self, filas: tuple[dict, ...] = (), error: Exception | None = None) -> None:
        self.filas = filas
        self.error = error
        self.recibido: dict = {}

    def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento=0):
        if self.error is not None:
            raise self.error
        self.recibido = {"fecha_corte": fecha_corte, "filtros": list(filtros), "limite": limite}
        return PaginaCartera(
            total=len(self.filas), filas=self.filas[:limite], limite=limite, desplazamiento=0
        )


PRODUCTO = {
    "pagare": "000000000000000007",
    "titular": "TITULAR/SINTETICO,DOS",
    "fecha_vencimiento_cuota": date(2026, 9, 18),
    "dias_atraso": 45,
    "saldo_capital_pendiente": Decimal("1500.50"),
    "telefono": "987654321",
}


@pytest.fixture
def cliente():
    cartera = CarteraFalsa((PRODUCTO,))
    app.dependency_overrides[obtener_servicio_cartera] = lambda: cartera
    try:
        yield TestClient(app), cartera
    finally:
        app.dependency_overrides.clear()


def _texto(valor: str) -> dict:
    return {"tipo": "texto", "valor": valor}


def _variable(nombre: str, *funciones: dict, **extra) -> dict:
    return {"tipo": "variable", "nombre": nombre, "funciones": list(funciones), **extra}


def _funcion(nombre: str, *args) -> dict:
    return {"nombre": nombre, "args": list(args)}


def _expresion(*nodos: dict) -> dict:
    return {"nodos": list(nodos)}


SPEECH = _expresion(
    _texto("Hola "),
    _variable("titular", _funcion("primeros", 4)),
    _texto(" vence "),
    _variable("fecha_vencimiento_cuota", _funcion("formato_fecha", "dd/mm")),
    _texto(" "),
    _variable("whatsapp_contacto", _funcion("enlace_whatsapp")),
)


# --- Catalogo -----------------------------------------------------------------------------------


def test_el_catalogo_de_la_cartera_trae_variables_funciones_y_limites(cliente) -> None:
    client, _ = cliente

    respuesta = client.get("/texto-enriquecido/catalogo", params={"contexto": "cartera"})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["contexto"]["nombre"] == "cartera"
    assert cuerpo["contexto"]["limite_largo"] is None
    variables = {v["nombre"]: v for v in cuerpo["contexto"]["variables"]}
    assert variables["saldo_capital_pendiente"]["tipo"] == "numero"
    assert variables["fecha_vencimiento_cuota"]["tipo"] == "fecha"
    assert cuerpo["contexto"]["ejemplo"]["fecha_vencimiento_cuota"] == "2026-10-05"
    assert cuerpo["contexto"]["ejemplo"]["saldo_capital_pendiente"] == "1500.50"
    assert [s["clave"] for s in cuerpo["contexto"]["segmentos"]][:2] == ["preventiva", "1_a_8"]
    assert {f["nombre"] for f in cuerpo["funciones"]} >= {"primeros", "formato_fecha", "sumar"}
    assert cuerpo["limites"] == {
        "nodos": 200,
        "funciones_por_nodo": 10,
        "argumentos_por_funcion": 8,
        "largo_literal": 5000,
        "columnas_por_definicion": 100,
        "variantes_por_columna": 50,
        "largo_nombre_definicion": 120,
    }
    assert cuerpo["familias"] == ["texto", "numero", "conversion", "fecha", "nulos", "enlaces"]
    assert [c["nombre"] for c in cuerpo["contextos"]] == ["cartera", "mowa_mes.speech"]


def test_el_catalogo_sin_contexto_es_el_de_la_cartera(cliente) -> None:
    client, _ = cliente

    assert client.get("/texto-enriquecido/catalogo").json()["contexto"]["nombre"] == "cartera"


def test_el_catalogo_del_speech_trae_el_limite_y_la_advertencia_de_mowa_mes(cliente) -> None:
    client, _ = cliente

    contexto = client.get(
        "/texto-enriquecido/catalogo", params={"contexto": "mowa_mes.speech"}
    ).json()["contexto"]

    assert (contexto["limite_largo"], contexto["umbral_advertencia"]) == (160, 150)
    assert contexto["variable_dias"] == "dias_atraso_ajustados"
    assert {v["nombre"]: v["clave_nombre"] for v in contexto["variables"]} == {
        "titular": None,
        "fecha_vencimiento_cuota": None,
        "whatsapp_contacto": "textoEnriquecido.variable.whatsapp_contacto",
        "dias_atraso_ajustados": "textoEnriquecido.variable.dias_atraso_ajustados",
    }
    assert contexto["ejemplo"]["whatsapp_contacto"] == "900000123"


def test_una_funcion_del_catalogo_trae_sus_parametros_con_tipo_rango_y_opciones(cliente) -> None:
    client, _ = cliente

    funciones = {
        f["nombre"]: f for f in client.get("/texto-enriquecido/catalogo").json()["funciones"]
    }

    assert funciones["si_vacio"]["devuelve"] == "entrada"
    primeros = funciones["primeros"]
    assert primeros["devuelve"] == "texto"
    assert primeros["clave_nombre"] == "textoEnriquecido.funcion.primeros.nombre"
    n = primeros["parametros"][0]
    assert (n["nombre"], n["tipo"], n["entero"], n["obligatorio"]) == ("n", "numero", True, True)
    assert n["minimo"] is not None
    patron = funciones["formato_fecha"]["parametros"][0]
    assert patron["nombre"] == "patron"
    assert {"valor": "dd/mm/aaaa", "ejemplo": "05/10/2026"} in patron["opciones"]


def test_el_catalogo_trae_los_patrones_y_las_marcas_de_fecha_con_su_ejemplo(cliente) -> None:
    client, _ = cliente

    cuerpo = client.get("/texto-enriquecido/catalogo").json()

    assert {"patron": "dd/mm/aaaa", "ejemplo": "05/10/2026"} in cuerpo["patrones_fecha"]
    marcas = {m["marca"]: m for m in cuerpo["marcas_fecha"]}
    assert marcas["aaaa"]["ejemplo"] == "2026"
    assert marcas["dd"]["clave"] == "textoEnriquecido.marcaFecha.dd"


def test_un_contexto_desconocido_es_404_con_su_codigo(cliente) -> None:
    client, _ = cliente

    respuesta = client.get("/texto-enriquecido/catalogo", params={"contexto": "inventado"})

    assert respuesta.status_code == 404
    assert respuesta.json() == {
        "detail": "El contexto 'inventado' no existe",
        "codigo": CodigoTexto.CONTEXTO_DESCONOCIDO.value,
    }


# --- Validacion ---------------------------------------------------------------------------------


def test_una_expresion_valida_devuelve_su_tipo_su_cota_y_sus_variables(cliente) -> None:
    client, _ = cliente
    expresion = _expresion(_texto("Hola "), _variable("titular", _funcion("primeros", 4)))

    respuesta = client.post(
        "/texto-enriquecido/validacion", json={"contexto": "cartera", "expresion": expresion}
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "problemas": [],
        "tipo": "texto",
        "cota": 9,
        "sin_cota": None,
        "variables": ["titular"],
    }


def test_sin_cota_trae_el_motivo_con_su_codigo_y_su_nodo(cliente) -> None:
    client, _ = cliente
    expresion = _expresion(_texto("a"), _variable("titular"))

    cuerpo = client.post(
        "/texto-enriquecido/validacion", json={"contexto": "cartera", "expresion": expresion}
    ).json()

    assert cuerpo["cota"] is None
    assert cuerpo["sin_cota"]["codigo"] == "sin_cota_variable"
    assert cuerpo["sin_cota"]["ubicacion"] == {"nodo": 1, "funcion": None, "parametro": None}


def test_los_problemas_de_la_validacion_traen_nodo_funcion_y_parametro(cliente) -> None:
    client, _ = cliente
    expresion = _expresion(
        _texto("x"),
        _variable("titular", _funcion("primeros", 0)),
        _variable("inventada"),
    )

    respuesta = client.post(
        "/texto-enriquecido/validacion", json={"contexto": "cartera", "expresion": expresion}
    )

    assert respuesta.status_code == 200  # una expresion con problemas no es un error de la peticion
    cuerpo = respuesta.json()
    assert (cuerpo["tipo"], cuerpo["cota"], cuerpo["variables"]) == (None, None, [])
    por_codigo = {p["codigo"]: p for p in cuerpo["problemas"]}
    assert por_codigo["parametro_invalido"]["ubicacion"] == {
        "nodo": 1,
        "funcion": 0,
        "parametro": "n",
    }
    assert por_codigo["variable_desconocida"]["ubicacion"]["nodo"] == 2
    assert por_codigo["variable_desconocida"]["nombre"] == "inventada"
    assert all(p["columna"] is None and p["segmento"] is None for p in cuerpo["problemas"])


def test_un_limite_excedido_no_tiene_ubicacion(cliente) -> None:
    client, _ = cliente
    expresion = _expresion(*[_texto("a")] * 201)

    cuerpo = client.post(
        "/texto-enriquecido/validacion", json={"contexto": "cartera", "expresion": expresion}
    ).json()

    assert [(p["codigo"], p["ubicacion"]) for p in cuerpo["problemas"]] == [
        ("limite_excedido", None)
    ]


@pytest.mark.parametrize(
    "nodo",
    [
        {"tipo": "imagen"},
        {"tipo": "texto"},  # sin `valor`
        {"tipo": "texto", "valor": "a", "nombre": "x"},
        {
            "tipo": "variable",
            "nombre": "titular",
            "funciones": [{"nombre": "primeros", "args": [True]}],
        },
        {
            "tipo": "variable",
            "nombre": "titular",
            "funciones": [{"nombre": "primeros", "args": [None]}],
        },
        {"tipo": "variable", "nombre": "titular", "extra": 1},
    ],
)
def test_una_forma_imposible_es_un_problema_expresion_invalida_y_no_un_422(cliente, nodo) -> None:
    client, _ = cliente

    respuesta = client.post(
        "/texto-enriquecido/validacion",
        json={"contexto": "cartera", "expresion": _expresion(_texto("ok"), nodo)},
    )

    assert respuesta.status_code == 200
    problemas = respuesta.json()["problemas"]
    assert problemas and {p["codigo"] for p in problemas} == {"expresion_invalida"}
    assert all(p["ubicacion"]["nodo"] == 1 for p in problemas)


def test_el_argumento_variable_viaja_y_se_valida(cliente) -> None:
    client, _ = cliente
    expresion = _expresion(
        _variable("fecha_vencimiento_cuota", _funcion("sumar_dias", {"variable": "dias_atraso"}))
    )

    cuerpo = client.post(
        "/texto-enriquecido/validacion", json={"contexto": "cartera", "expresion": expresion}
    ).json()

    assert cuerpo["problemas"] == []
    assert cuerpo["variables"] == ["fecha_vencimiento_cuota", "dias_atraso"]
    assert cuerpo["tipo"] == "fecha"


def test_validar_en_un_contexto_desconocido_es_404(cliente) -> None:
    client, _ = cliente

    respuesta = client.post(
        "/texto-enriquecido/validacion",
        json={"contexto": "inventado", "expresion": _expresion(_texto("a"))},
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "contexto_desconocido"


def test_la_validacion_usa_las_variables_del_contexto(cliente) -> None:
    client, _ = cliente
    expresion = _expresion(_variable("telefono"))  # de la cartera, no del speech

    en_cartera = client.post(
        "/texto-enriquecido/validacion", json={"contexto": "cartera", "expresion": expresion}
    ).json()
    en_speech = client.post(
        "/texto-enriquecido/validacion",
        json={"contexto": "mowa_mes.speech", "expresion": expresion},
    ).json()

    assert en_cartera["problemas"] == []
    assert [p["codigo"] for p in en_speech["problemas"]] == ["variable_desconocida"]


# --- Previsualizacion de una expresion ----------------------------------------------------------


def _previsualizar(client, **cuerpo) -> dict:
    respuesta = client.post("/texto-enriquecido/previsualizacion", json=cuerpo)
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def test_los_ejemplos_por_segmento_son_la_muestra_por_defecto(cliente) -> None:
    client, _ = cliente

    cuerpo = _previsualizar(client, contexto="mowa_mes.speech", expresion=SPEECH)

    assert cuerpo["problemas"] == []
    assert (cuerpo["limite_largo"], cuerpo["umbral_advertencia"]) == (160, 150)
    assert [f["etiqueta"] for f in cuerpo["filas"]] == [
        "Preventiva",
        "1 a 8",
        "9 a 30",
        "31 a 60",
        "61 a 90",
        "91 a 120",
    ]
    assert [f["numero"] for f in cuerpo["filas"]] == [1, 2, 3, 4, 5, 6]


def test_cada_fila_trae_el_texto_total_el_de_cada_nodo_y_el_largo(cliente) -> None:
    client, _ = cliente

    fila = _previsualizar(client, contexto="mowa_mes.speech", expresion=SPEECH)["filas"][0]

    columna = fila["columnas"][0]
    assert columna["texto"] == "Hola TITU vence 05/10 https://wa.me/+51900000123"
    assert "".join(n["texto"] for n in columna["nodos"]) == columna["texto"]
    assert [n["tipo"] for n in columna["nodos"]] == ["texto", "variable"] * 2 + [
        "texto",
        "variable",
    ]
    assert columna["largo"] == len(columna["texto"])
    assert columna["cota"] is not None and columna["largo"] <= columna["cota"]
    assert columna["sin_cota"] is None
    assert columna["problemas"] == []
    assert (columna["nombre"], columna["tipo"], columna["usa_variante"]) == (
        "texto",
        "texto",
        False,
    )


def test_una_variable_sin_dato_se_distingue_de_un_texto_vacio(cliente) -> None:
    client, _ = cliente
    expresion = _expresion(_texto(""), _variable("titular"), _texto("-"))

    cuerpo = _previsualizar(
        client,
        contexto="mowa_mes.speech",
        muestra={"tipo": "producto_real", "fecha_corte": CORTE, "pagare": "x"},
        expresion=expresion,
    )
    # El producto tiene titular; con una variable de la cartera que el producto no trae:
    sin_dato = _previsualizar(
        client,
        contexto="cartera",
        muestra={"tipo": "producto_real", "fecha_corte": CORTE, "pagare": "x"},
        expresion=_expresion(_texto(""), _variable("cliente_fallecido"), _texto("-")),
    )

    nodos = sin_dato["filas"][0]["columnas"][0]["nodos"]
    assert [(n["tipo"], n["texto"], n["vacio"]) for n in nodos] == [
        ("texto", "", False),
        ("variable", "", True),
        ("texto", "-", False),
    ]
    assert not any(n["vacio"] for n in cuerpo["filas"][0]["columnas"][0]["nodos"])


def test_la_muestra_de_ejemplo_es_una_sola_fila_con_el_registro_del_contexto(cliente) -> None:
    client, _ = cliente

    cuerpo = _previsualizar(
        client,
        contexto="cartera",
        muestra={"tipo": "ejemplo"},
        expresion=_expresion(_variable("telefono")),
    )

    assert len(cuerpo["filas"]) == 1
    assert cuerpo["filas"][0]["columnas"][0]["texto"] == "987654321"
    assert cuerpo["filas"][0]["etiqueta"] is None


def test_un_producto_real_se_busca_por_fecha_de_corte_y_pagare(cliente) -> None:
    client, cartera = cliente

    cuerpo = _previsualizar(
        client,
        contexto="mowa_mes.speech",
        muestra={"tipo": "producto_real", "fecha_corte": CORTE, "pagare": "000000000000000007"},
        expresion=SPEECH,
    )

    assert cuerpo["filas"][0]["columnas"][0]["texto"] == (
        "Hola TITU vence 18/09 https://wa.me/+51900000123"
    )
    assert cartera.recibido["fecha_corte"] == date(2026, 9, 10)
    assert cartera.recibido["filtros"][0].campo == "pagare"
    assert cartera.recibido["filtros"][0].valores == ("000000000000000007",)
    assert cartera.recibido["limite"] == 1


def test_un_producto_real_trae_su_pagare_y_su_fecha_de_corte(cliente) -> None:
    client, _ = cliente

    fila = _previsualizar(
        client,
        contexto="mowa_mes.speech",
        muestra={"tipo": "producto_real", "fecha_corte": CORTE, "pagare": "000000000000000007"},
        expresion=SPEECH,
    )["filas"][0]

    assert (fila["pagare"], fila["fecha_corte"]) == ("000000000000000007", CORTE)


def test_las_muestras_de_ejemplo_traen_pagare_y_fecha_de_corte_en_null(cliente) -> None:
    client, _ = cliente

    por_defecto = _previsualizar(client, contexto="mowa_mes.speech", expresion=SPEECH)["filas"]
    ejemplo = _previsualizar(
        client, contexto="mowa_mes.speech", muestra={"tipo": "ejemplo"}, expresion=SPEECH
    )["filas"]

    # Siempre presentes (el contrato no omite campos), con null: no representan un producto real.
    for fila in [*por_defecto, *ejemplo]:
        assert "pagare" in fila and "fecha_corte" in fila
        assert (fila["pagare"], fila["fecha_corte"]) == (None, None)
    assert len(por_defecto) == 6 and len(ejemplo) == 1


def test_un_producto_real_inexistente_es_404_con_su_codigo(cliente) -> None:
    client, cartera = cliente
    cartera.filas = ()

    respuesta = client.post(
        "/texto-enriquecido/previsualizacion",
        json={
            "contexto": "cartera",
            "expresion": _expresion(_variable("titular")),
            "muestra": {"tipo": "producto_real", "fecha_corte": CORTE, "pagare": "nada"},
        },
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "producto_no_encontrado"


def test_una_fecha_sin_version_vigente_es_404_con_su_codigo(cliente) -> None:
    client, cartera = cliente
    cartera.error = SinVersionVigente(date(2026, 9, 10))

    respuesta = client.post(
        "/texto-enriquecido/previsualizacion",
        json={
            "contexto": "cartera",
            "expresion": _expresion(_texto("a")),
            "muestra": {"tipo": "producto_real", "fecha_corte": CORTE, "pagare": "x"},
        },
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "sin_version_vigente"


def test_una_expresion_con_problemas_no_trae_filas_y_si_los_problemas(cliente) -> None:
    client, _ = cliente

    cuerpo = _previsualizar(
        client, contexto="cartera", expresion=_expresion(_variable("inventada"))
    )

    assert cuerpo["filas"] == []
    assert [(p["codigo"], p["ubicacion"]["nodo"]) for p in cuerpo["problemas"]] == [
        ("variable_desconocida", 0)
    ]
    assert [(p["columna"], p["segmento"], p["campo"]) for p in cuerpo["problemas"]] == [
        (None, None, None)
    ]  # una expresion suelta no tiene columnas


def test_un_problema_de_fila_viaja_aparte_y_deja_el_valor_vacio(cliente) -> None:
    client, _ = cliente
    expresion = _expresion(_variable("saldo_capital_pendiente", _funcion("dividir", 0)))

    cuerpo = _previsualizar(
        client, contexto="cartera", muestra={"tipo": "ejemplo"}, expresion=expresion
    )

    assert cuerpo["problemas"] == []
    columna = cuerpo["filas"][0]["columnas"][0]
    assert [p["codigo"] for p in columna["problemas"]] == ["division_por_cero"]
    assert columna["problemas"][0]["ubicacion"] == {"nodo": 0, "funcion": 0, "parametro": "valor"}
    assert columna["valor"] is None


def test_una_variable_obligatoria_vacia_es_un_problema_de_fila(cliente) -> None:
    client, _ = cliente
    expresion = _expresion(_variable("cliente_fallecido", obligatoria=True))

    cuerpo = _previsualizar(
        client,
        contexto="cartera",
        muestra={"tipo": "producto_real", "fecha_corte": CORTE, "pagare": "x"},
        expresion=expresion,
    )

    assert [p["codigo"] for p in cuerpo["filas"][0]["columnas"][0]["problemas"]] == [
        "variable_obligatoria_vacia"
    ]


def test_se_pide_una_expresion_o_una_definicion_pero_no_ambas_ni_ninguna(cliente) -> None:
    client, _ = cliente
    definicion = {"columnas": [{"nombre": "a", "orden": 0, "expresion": {"nodos": []}}]}

    for cuerpo in (
        {"contexto": "cartera"},
        {"contexto": "cartera", "expresion": _expresion(), "definicion": definicion},
    ):
        assert client.post("/texto-enriquecido/previsualizacion", json=cuerpo).status_code == 422


def test_un_producto_real_pide_fecha_de_corte_y_pagare(cliente) -> None:
    client, _ = cliente

    respuesta = client.post(
        "/texto-enriquecido/previsualizacion",
        json={
            "contexto": "cartera",
            "expresion": _expresion(_texto("a")),
            "muestra": {"tipo": "producto_real", "pagare": "x"},
        },
    )

    assert respuesta.status_code == 422


# --- Previsualizacion de una definicion ---------------------------------------------------------


def _columna(nombre: str, orden: int, *nodos: dict, **extra) -> dict:
    return {"nombre": nombre, "orden": orden, "expresion": _expresion(*nodos), **extra}


def _definicion(*columnas: dict, **extra) -> dict:
    return {"columnas": list(columnas), **extra}


DEFINICION = {
    "nombre": "SMS",
    "columnas": [
        _columna(
            "mensaje",
            0,
            _texto("General "),
            _variable("titular", _funcion("primeros", 4)),
            variantes=[
                {
                    "segmento": "1_a_8",
                    "expresion": _expresion(
                        _texto("Pronto "), _variable("titular", _funcion("primeros", 4))
                    ),
                }
            ],
        ),
        _columna("monto", 1, _variable("saldo_capital_pendiente"), tipo="financiero"),
        _columna(
            "vence",
            2,
            _variable("fecha_vencimiento_cuota"),
            tipo="fecha",
            formato_fecha="dd/mm/aaaa",
        ),
    ],
    "segmentacion": {},
}


def test_una_definicion_se_previsualiza_con_una_fila_por_segmento(cliente) -> None:
    client, _ = cliente

    cuerpo = _previsualizar(client, contexto="cartera", definicion=DEFINICION)

    assert cuerpo["problemas"] == []
    filas = cuerpo["filas"]
    assert [f["segmento"] for f in filas] == [
        "preventiva",
        "1_a_8",
        "9_a_30",
        "31_a_60",
        "61_a_90",
        "91_a_120",
    ]
    mensajes = [f["columnas"][0] for f in filas]
    assert [m["texto"] for m in mensajes] == ["General TITU", "Pronto TITU"] + ["General TITU"] * 4
    assert [m["usa_variante"] for m in mensajes] == [False, True, False, False, False, False]
    assert filas[0]["columnas"][1]["valor"] == "1,500.50"
    assert filas[0]["columnas"][2]["valor"] == "05/10/2026"
    assert [c["tipo"] for c in filas[0]["columnas"]] == ["texto", "financiero", "fecha"]


def test_el_formato_de_fecha_con_marcas_se_aplica_y_no_sale_como_texto_literal(cliente) -> None:
    client, _ = cliente
    definicion = _definicion(
        _columna(
            "larga",
            0,
            _variable("fecha_vencimiento_cuota"),
            tipo="fecha",
            formato_fecha="dd de nombre_mes de aaaa",
        ),
        _columna(
            "corta",
            1,
            _variable("fecha_vencimiento_cuota"),
            tipo="fecha",
            formato_fecha="aaaa-mm-dd",
        ),
    )

    columnas = _previsualizar(
        client, contexto="cartera", definicion=definicion, muestra={"tipo": "ejemplo"}
    )["filas"][0]["columnas"]

    assert [c["valor"] for c in columnas] == ["05 de octubre de 2026", "2026-10-05"]


def test_un_formato_de_fecha_sin_marcas_es_un_problema_de_su_columna(cliente) -> None:
    client, _ = cliente
    definicion = _definicion(
        _columna("ok", 0, _variable("titular")),
        _columna(
            "vence", 1, _variable("fecha_vencimiento_cuota"), tipo="fecha", formato_fecha="%d/%m/%Y"
        ),
    )

    cuerpo = _previsualizar(client, contexto="cartera", definicion=definicion)

    assert cuerpo["filas"] == []
    [problema] = cuerpo["problemas"]
    assert problema["codigo"] == "parametro_invalido"
    assert (problema["columna"], problema["campo"], problema["segmento"]) == (
        1,
        "formato_fecha",
        None,
    )
    assert problema["ubicacion"] is None


def test_una_columna_recien_creada_da_problemas_ubicados_y_no_un_error(cliente) -> None:
    client, _ = cliente
    definicion = _definicion(
        _columna("a", 0, _variable("titular")),
        {"nombre": "", "orden": 1, "expresion": {"nodos": []}},
    )

    respuesta = client.post(
        "/texto-enriquecido/previsualizacion",
        json={"contexto": "cartera", "definicion": definicion},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["filas"] == []
    assert [(p["codigo"], p["columna"], p["campo"]) for p in cuerpo["problemas"]] == [
        ("definicion_invalida", 1, "nombre")
    ]


def test_una_columna_con_nombre_pero_sin_contenido_se_previsualiza_vacia(cliente) -> None:
    client, _ = cliente
    definicion = _definicion(_columna("nueva", 0))

    columna = _previsualizar(
        client, contexto="cartera", definicion=definicion, muestra={"tipo": "ejemplo"}
    )["filas"][0]["columnas"][0]

    assert (columna["texto"], columna["largo"], columna["nodos"], columna["problemas"]) == (
        "",
        0,
        [],
        [],
    )


def test_las_columnas_salen_en_el_orden_pedido_y_los_problemas_en_su_posicion(cliente) -> None:
    client, _ = cliente
    sana = _definicion(
        _columna("tercera", 20, _texto("c")),
        _columna("primera", 5, _texto("a")),
        _columna("segunda", 10, _texto("b")),
    )
    rota = _definicion(
        _columna("tercera", 20, _texto("c")),
        _columna("rota", 5, _variable("inventada")),
        _columna("segunda", 10, _texto("b")),
    )

    columnas = _previsualizar(
        client, contexto="cartera", definicion=sana, muestra={"tipo": "ejemplo"}
    )["filas"][0]["columnas"]
    problemas = _previsualizar(client, contexto="cartera", definicion=rota)["problemas"]

    assert [(c["nombre"], c["texto"]) for c in columnas] == [
        ("primera", "a"),
        ("segunda", "b"),
        ("tercera", "c"),
    ]
    assert [(p["codigo"], p["columna"]) for p in problemas] == [("variable_desconocida", 1)]


def test_los_dias_de_cada_ejemplo_caen_en_el_rango_de_su_fila(cliente) -> None:
    """Los dias salen de la tabla: la fila de `1 a 8` cae en `1_a_8`, no en otro rango."""
    client, _ = cliente
    definicion = _definicion(_columna("dias", 0, _variable("dias_atraso")), segmentacion={})

    filas = _previsualizar(client, contexto="cartera", definicion=definicion)["filas"]

    assert [(f["segmento"], f["columnas"][0]["texto"]) for f in filas] == [
        ("preventiva", "0"),
        ("1_a_8", "1"),
        ("9_a_30", "9"),
        ("31_a_60", "31"),
        ("61_a_90", "61"),
        ("91_a_120", "91"),
    ]


def test_sin_segmentacion_los_ejemplos_por_segmento_traen_igual_la_clave_de_su_rango(
    cliente,
) -> None:
    client, _ = cliente
    definicion = _definicion(_columna("a", 0, _variable("titular")))

    filas = _previsualizar(client, contexto="cartera", definicion=definicion)["filas"]

    assert [(f["etiqueta"], f["segmento"]) for f in filas] == CLAVES_DE_LA_TABLA


def test_los_problemas_de_una_definicion_traen_columna_y_segmento(cliente) -> None:
    client, _ = cliente
    definicion = _definicion(
        _columna("ok", 0, _variable("titular")),
        _columna(
            "rota",
            1,
            _variable("titular"),
            variantes=[{"segmento": "1_a_8", "expresion": _expresion(_variable("inventada"))}],
        ),
        segmentacion={},
    )

    cuerpo = _previsualizar(client, contexto="cartera", definicion=definicion)

    assert cuerpo["filas"] == []
    [problema] = cuerpo["problemas"]
    assert problema["codigo"] == "variable_desconocida"
    assert (problema["columna"], problema["segmento"], problema["campo"]) == (1, "1_a_8", None)
    assert problema["ubicacion"]["nodo"] == 0


def test_una_forma_imposible_en_la_definicion_es_definicion_invalida_con_su_ubicacion(
    cliente,
) -> None:
    client, _ = cliente
    definicion = _definicion(
        _columna("a", 0, _texto("x")),
        _columna("b", 1, _texto("x"), tipo="inventado"),
        segmentacion={"politica": "ninguna"},
    )

    cuerpo = _previsualizar(client, contexto="cartera", definicion=definicion)

    assert cuerpo["filas"] == []
    encontrados = {(p["codigo"], p["columna"], p["campo"]) for p in cuerpo["problemas"]}
    assert encontrados == {
        ("definicion_invalida", 1, "tipo"),
        ("definicion_invalida", None, "segmentacion"),
    }


def test_una_definicion_sin_columnas_es_definicion_invalida(cliente) -> None:
    client, _ = cliente

    cuerpo = _previsualizar(client, contexto="cartera", definicion={"columnas": []})

    assert [(p["codigo"], p["campo"]) for p in cuerpo["problemas"]] == [
        ("definicion_invalida", "definicion")
    ]


def test_el_orden_repetido_o_el_nombre_repetido_se_ubican_en_la_columna_repetida(cliente) -> None:
    client, _ = cliente
    definicion = _definicion(
        _columna("a", 0, _texto("x")),
        _columna("a", 0, _texto("y")),
    )

    cuerpo = _previsualizar(client, contexto="cartera", definicion=definicion)

    assert sorted((p["columna"], p["campo"]) for p in cuerpo["problemas"]) == [
        (1, "nombre"),
        (1, "orden"),
    ]


def test_la_definicion_acepta_proteger_formulas_y_lo_valida(cliente) -> None:
    client, _ = cliente
    columna = _columna("a", 0, _texto("x"))

    con = _previsualizar(
        client,
        contexto="cartera",
        definicion=_definicion(columna, proteger_formulas=False),
        muestra={"tipo": "ejemplo"},
    )
    sin = client.post(
        "/texto-enriquecido/previsualizacion",
        json={"contexto": "cartera", "definicion": _definicion(columna, proteger_formulas="si")},
    )

    assert con["problemas"] == [] and len(con["filas"]) == 1
    assert sin.status_code == 422  # el esquema del pedido solo admite verdadero o falso


def test_una_columna_con_valor_no_convertible_lo_informa_en_su_fila(cliente) -> None:
    client, _ = cliente
    definicion = _definicion(_columna("f", 0, _variable("titular"), tipo="fecha"))

    cuerpo = _previsualizar(
        client, contexto="cartera", definicion=definicion, muestra={"tipo": "ejemplo"}
    )

    columna = cuerpo["filas"][0]["columnas"][0]
    assert [p["codigo"] for p in columna["problemas"]] == ["valor_no_convertible"]
    assert columna["valor"] is None


def test_un_producto_sin_segmento_se_excluye_con_su_motivo(cliente) -> None:
    client, cartera = cliente
    cartera.filas = ({**PRODUCTO, "dias_atraso": 500},)  # pasa de 120: sin segmento

    cuerpo = _previsualizar(
        client,
        contexto="cartera",
        definicion=DEFINICION,
        muestra={"tipo": "producto_real", "fecha_corte": CORTE, "pagare": "x"},
    )

    [fila] = cuerpo["filas"]
    assert fila["excluida"]["codigo"] == "sin_segmento"
    assert fila["columnas"] == []


def test_un_criterio_por_campo_da_una_fila_por_cada_valor_con_variante(cliente) -> None:
    client, _ = cliente
    definicion = _definicion(
        _columna(
            "m",
            0,
            _texto("otro"),
            variantes=[
                {"segmento": "CUSCO", "expresion": _expresion(_texto("cusco"))},
                {"segmento": "LIMA", "expresion": _expresion(_texto("lima"))},
            ],
        ),
        segmentacion={"criterio": {"tipo": "campo", "campo": "region"}},
    )

    filas = _previsualizar(client, contexto="cartera", definicion=definicion)["filas"]

    assert [(f["segmento"], f["columnas"][0]["texto"]) for f in filas] == [
        ("CUSCO", "cusco"),
        ("LIMA", "lima"),
    ]


def test_la_previsualizacion_da_lo_mismo_que_la_carga(cliente) -> None:
    """La celda de la previsualizacion es la que escribe la carga, con el mismo tipado."""
    client, _ = cliente

    fila = _previsualizar(
        client,
        contexto="cartera",
        definicion=DEFINICION,
        muestra={
            "tipo": "producto_real",
            "fecha_corte": CORTE,
            "fecha_envio": CORTE,  # sin ajuste: la carga de abajo usa la misma fecha
            "pagare": "x",
        },
    )["filas"][0]

    assert [c["valor"] for c in fila["columnas"]] == [
        "General TITU",
        "1,500.50",
        "18/09/2026",
    ]
    assert fila["segmento"] == "31_a_60"


def test_un_nulo_explicito_es_lo_mismo_que_un_campo_ausente(cliente) -> None:
    """El cliente tipado envia `null` en lo que no usa: no es una forma imposible."""
    client, _ = cliente
    nodos = [
        {"tipo": "texto", "valor": "Hola ", "nombre": None, "funciones": None, "obligatoria": None},
        {"tipo": "variable", "nombre": "titular", "valor": None, "funciones": None},
        {
            "tipo": "variable",
            "nombre": "titular",
            "valor": None,
            "obligatoria": None,
            "funciones": [
                {"nombre": "primeros", "args": [2]},
                {"nombre": "mayusculas", "args": None},
            ],
        },
    ]

    cuerpo = client.post(
        "/texto-enriquecido/validacion",
        json={"contexto": "cartera", "expresion": {"nodos": nodos}},
    ).json()

    assert cuerpo["problemas"] == []
    assert cuerpo["variables"] == ["titular"]


def test_el_producto_real_se_busca_por_igualdad_del_pagare(cliente) -> None:
    from app.core.entities.cartera import Operador

    client, cartera = cliente

    _previsualizar(
        client,
        contexto="cartera",
        expresion=_expresion(_variable("titular")),
        muestra={"tipo": "producto_real", "fecha_corte": CORTE, "pagare": "000000000000000007"},
    )

    assert [f.operador for f in cartera.recibido["filtros"]] == [Operador.IGUAL]
    assert len(cartera.recibido["filtros"]) == 1


def test_un_producto_real_con_pagare_vacio_no_se_acepta(cliente) -> None:
    client, _ = cliente

    respuesta = client.post(
        "/texto-enriquecido/previsualizacion",
        json={
            "contexto": "cartera",
            "expresion": _expresion(_texto("a")),
            "muestra": {"tipo": "producto_real", "fecha_corte": CORTE, "pagare": ""},
        },
    )

    assert respuesta.status_code == 422


CLAVES_DE_LA_TABLA = [
    ("Preventiva", "preventiva"),
    ("1 a 8", "1_a_8"),
    ("9 a 30", "9_a_30"),
    ("31 a 60", "31_a_60"),
    ("61 a 90", "61_a_90"),
    ("91 a 120", "91_a_120"),
]


def test_una_expresion_suelta_trae_la_clave_del_segmento_de_cada_fila_de_ejemplo(cliente) -> None:
    client, _ = cliente

    filas = _previsualizar(client, contexto="mowa_mes.speech", expresion=SPEECH)["filas"]

    assert [(f["etiqueta"], f["segmento"]) for f in filas] == CLAVES_DE_LA_TABLA


def test_la_clave_de_la_fila_es_la_del_segmento_que_calcula_la_definicion(cliente) -> None:
    """La clave que se informa es la que la definicion usa para elegir la variante."""
    client, _ = cliente

    filas = _previsualizar(client, contexto="cartera", definicion=DEFINICION)["filas"]

    assert [f["segmento"] for f in filas] == [clave for _, clave in CLAVES_DE_LA_TABLA]
    assert [f["columnas"][0]["usa_variante"] for f in filas] == [False, True] + [False] * 4


def test_el_ejemplo_y_el_producto_real_sin_segmentacion_no_traen_segmento(cliente) -> None:
    client, _ = cliente
    expresion = _expresion(_variable("titular"))

    de_ejemplo = _previsualizar(
        client, contexto="cartera", muestra={"tipo": "ejemplo"}, expresion=expresion
    )
    real = _previsualizar(
        client,
        contexto="cartera",
        muestra={"tipo": "producto_real", "fecha_corte": CORTE, "pagare": "x"},
        expresion=expresion,
    )

    assert [f["segmento"] for f in de_ejemplo["filas"] + real["filas"]] == [None, None]


def test_cada_variable_del_catalogo_dice_que_contexto_la_aporta(cliente) -> None:
    client, _ = cliente

    cartera = client.get("/texto-enriquecido/catalogo", params={"contexto": "cartera"}).json()
    speech = client.get(
        "/texto-enriquecido/catalogo", params={"contexto": "mowa_mes.speech"}
    ).json()

    assert {v["origen"] for v in cartera["contexto"]["variables"]} == {"cartera"}
    assert {v["nombre"]: v["origen"] for v in speech["contexto"]["variables"]} == {
        "titular": "cartera",
        "fecha_vencimiento_cuota": "cartera",
        "whatsapp_contacto": "mowa_mes.speech",
        "dias_atraso_ajustados": "mowa_mes.speech",
    }
    nombres = {c["nombre"] for c in speech["contextos"]}
    assert {v["origen"] for v in speech["contexto"]["variables"]} <= nombres


def test_los_tipos_del_catalogo_son_uniones_cerradas_en_el_contrato() -> None:
    """El cliente generado recibe uniones y no `string`: un tipo nuevo no pasa sin avisar."""
    from app.core.entities.texto_enriquecido import TipoValor

    esquemas = app.openapi()["components"]["schemas"]
    tipos = [t.value for t in TipoValor if t is not TipoValor.NULO]

    assert esquemas["VariableRespuesta"]["properties"]["tipo"]["enum"] == tipos
    assert esquemas["FuncionRespuesta"]["properties"]["recibe"]["items"]["enum"] == tipos
    assert esquemas["FuncionRespuesta"]["properties"]["devuelve"]["enum"] == [*tipos, "entrada"]
    assert esquemas["ParametroRespuesta"]["properties"]["tipo"]["enum"] == [*tipos, "entrada"]
