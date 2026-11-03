"""Endpoints de configuracion y segmentos de WhatsMKT, sin base (T-WM-B1).

Sustituyen la dependencia del caso de uso por el servicio real sobre un repositorio en memoria:
se prueba la traduccion HTTP (parcial, 422 con codigo, forma de la respuesta), no la base.
"""

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.whatsmkt import obtener_servicio_whatsmkt
from app.core.entities.whatsmkt import (
    SEGMENTOS_POR_DEFECTO,
    ConfiguracionWhatsmkt,
    DefinicionDefectoNoExiste,
)
from app.core.services.plataformas.whatsmkt.administracion import ConfiguracionWhatsmktService
from app.main import app

MOMENTO = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


class RepositorioWhatsmktFalso:
    def __init__(self) -> None:
        self.configuracion = ConfiguracionWhatsmkt(actualizado_en=MOMENTO)
        self.segmentos = list(SEGMENTOS_POR_DEFECTO)
        self.definiciones = {7}
        self.escrituras = 0

    def obtener_configuracion(self):
        return self.configuracion

    def guardar_configuracion(self, configuracion):
        id_ = configuracion.definicion_defecto_id
        if id_ is not None and id_ not in self.definiciones:
            raise DefinicionDefectoNoExiste(id_)
        self.escrituras += 1
        self.configuracion = replace(configuracion, actualizado_en=MOMENTO)
        return self.configuracion

    def listar_segmentos(self):
        return list(self.segmentos)

    def reemplazar_segmentos(self, segmentos):
        self.escrituras += 1
        self.segmentos = list(segmentos)
        return list(self.segmentos)


class DefinicionesFalsas:
    """Las definiciones guardadas con su plataforma (RF-72): 7 es de WhatsMKT, 8 es libre y 9 es
    de otra plataforma."""

    def __init__(self) -> None:
        self.plataformas = {7: "whatsmkt", 8: None, 9: "mowa_mes"}

    def obtener(self, definicion_id):
        if definicion_id not in self.plataformas:
            return None
        return SimpleNamespace(
            nombre=f"Definicion {definicion_id}", plataforma=self.plataformas[definicion_id]
        )


@pytest.fixture
def cliente():
    repositorio = RepositorioWhatsmktFalso()
    app.dependency_overrides[obtener_servicio_whatsmkt] = lambda: ConfiguracionWhatsmktService(
        repositorio, DefinicionesFalsas()
    )
    try:
        yield TestClient(app), repositorio
    finally:
        app.dependency_overrides.clear()


def _segmento(clave: str, desde: int | None, hasta: int | None) -> dict:
    return {"clave": clave, "etiqueta": clave.title(), "desde": desde, "hasta": hasta}


# --- GET /whatsmkt/configuracion ------------------------------------------------------------


def test_la_configuracion_se_lee_con_sus_valores_por_defecto(cliente) -> None:
    client, _ = cliente

    respuesta = client.get("/whatsmkt/configuracion")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "horario_1": {"inicio": "08:00", "fin": "14:00"},
        "horario_2": {"inicio": "14:00", "fin": "20:00"},
        "plantilla_nombre": "CUZCO_Vencida ({segmento}) whatsapp {fecha_corte}",
        "definicion_defecto_id": None,
        "tope_mensaje": 4096,
        "tope_video": 16_000_000,
        "tope_audio": 16_000_000,
        "tope_pdf": 16_000_000,
        "actualizado_en": "2026-11-02T12:00:00Z",
        "variables_plantilla": ["fecha_corte", "segmento"],
    }


# --- PUT /whatsmkt/configuracion (parcial) --------------------------------------------------


def test_un_put_vacio_no_cambia_nada(cliente) -> None:
    client, repositorio = cliente
    antes = repositorio.configuracion

    respuesta = client.put("/whatsmkt/configuracion", json={})

    assert respuesta.status_code == 200
    assert repositorio.configuracion == antes


def test_un_campo_omitido_conserva_el_guardado_y_los_enviados_cambian(cliente) -> None:
    client, repositorio = cliente

    respuesta = client.put(
        "/whatsmkt/configuracion",
        json={
            "horario_1": {"inicio": "09:30", "fin": "13:00"},
            "tope_mensaje": 1000,
            "plantilla_nombre": "Cobranza {segmento} {fecha_corte}",
        },
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["horario_1"] == {"inicio": "09:30", "fin": "13:00"}
    assert cuerpo["tope_mensaje"] == 1000
    assert cuerpo["plantilla_nombre"] == "Cobranza {segmento} {fecha_corte}"
    assert cuerpo["horario_2"] == {"inicio": "14:00", "fin": "20:00"}  # lo omitido se conserva
    assert cuerpo["tope_pdf"] == 16_000_000
    assert repositorio.escrituras == 1


def test_la_plantilla_vacia_vuelve_la_de_por_defecto(cliente) -> None:
    client, _ = cliente
    client.put("/whatsmkt/configuracion", json={"plantilla_nombre": "otra"})

    respuesta = client.put("/whatsmkt/configuracion", json={"plantilla_nombre": " "})

    assert (
        respuesta.json()["plantilla_nombre"] == "CUZCO_Vencida ({segmento}) whatsapp {fecha_corte}"
    )


@pytest.mark.parametrize(
    "campo",
    [
        "horario_1",
        "horario_2",
        "plantilla_nombre",
        "tope_mensaje",
        "tope_video",
        "tope_audio",
        "tope_pdf",
    ],
)
def test_un_null_en_un_campo_que_no_admite_vacio_responde_422_sin_guardar(
    cliente, campo: str
) -> None:
    client, repositorio = cliente

    respuesta = client.put("/whatsmkt/configuracion", json={campo: None})

    assert respuesta.status_code == 422
    assert repositorio.escrituras == 0


def test_la_definicion_por_defecto_se_elige_y_se_quita_con_null(cliente) -> None:
    client, _ = cliente

    elegida = client.put("/whatsmkt/configuracion", json={"definicion_defecto_id": 7})
    quitada = client.put("/whatsmkt/configuracion", json={"definicion_defecto_id": None})

    assert elegida.json()["definicion_defecto_id"] == 7
    assert quitada.json()["definicion_defecto_id"] is None


@pytest.mark.parametrize("definicion_id", [8, 9])
def test_una_definicion_que_no_es_de_whatsmkt_responde_422_con_su_codigo_sin_guardar(
    cliente, definicion_id: int
) -> None:
    client, repositorio = cliente

    respuesta = client.put("/whatsmkt/configuracion", json={"definicion_defecto_id": definicion_id})

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "definicion_no_whatsmkt"
    assert isinstance(respuesta.json()["detail"], str)
    assert repositorio.escrituras == 0
    assert repositorio.configuracion.definicion_defecto_id is None


def test_la_definicion_de_whatsmkt_se_acepta_y_un_put_posterior_la_conserva(cliente) -> None:
    client, _ = cliente
    client.put("/whatsmkt/configuracion", json={"definicion_defecto_id": 7})

    otro = client.put("/whatsmkt/configuracion", json={"tope_mensaje": 100})

    assert otro.status_code == 200
    assert otro.json()["definicion_defecto_id"] == 7


def test_una_definicion_que_no_existe_responde_404_sin_guardar(cliente) -> None:
    client, repositorio = cliente

    respuesta = client.put("/whatsmkt/configuracion", json={"definicion_defecto_id": 99})

    assert respuesta.status_code == 404
    assert isinstance(respuesta.json()["detail"], str)
    assert repositorio.escrituras == 0


PARAMETROS_NULOS = {"horarios": None, "variable": None, "segmento": None, "fila": None}
PARAMETROS_NULOS |= {"desde": None, "hasta": None, "peso": None, "maximo": None}
PARAMETROS_NULOS |= {"tipo": None, "ancho": None, "alto": None}


@pytest.mark.parametrize(
    ("cuerpo", "codigo", "parametros"),
    [
        (
            {"horario_1": {"inicio": "14:00", "fin": "08:00"}},
            "horario_invalido",
            {"horarios": ["horario_1"]},
        ),
        (
            {"horario_2": {"inicio": "10:00", "fin": "10:00"}},
            "horario_invalido",
            {"horarios": ["horario_2"]},
        ),
        (
            {
                "horario_1": {"inicio": "09:00", "fin": "08:00"},
                "horario_2": {"inicio": "21:00", "fin": "20:00"},
            },
            "horario_invalido",
            {"horarios": ["horario_1", "horario_2"]},
        ),
        (
            {"plantilla_nombre": "{segmento} {horario}"},
            "variable_inexistente",
            {"variable": "{horario}"},
        ),
        ({"plantilla_nombre": "{segmento"}, "variable_inexistente", {"variable": "{segmento"}),
    ],
)
def test_una_regla_rota_responde_422_con_su_codigo_y_parametros_sin_guardar(
    cliente, cuerpo: dict, codigo: str, parametros: dict
) -> None:
    client, repositorio = cliente

    respuesta = client.put("/whatsmkt/configuracion", json=cuerpo)

    assert respuesta.status_code == 422
    cuerpo_error = respuesta.json()
    assert cuerpo_error["codigo"] == codigo
    assert isinstance(cuerpo_error["detail"], str)
    assert {k: v for k, v in cuerpo_error.items() if k not in ("detail", "codigo")} == {
        **PARAMETROS_NULOS,
        **parametros,
    }  # los parametros siempre viajan, nulos si el codigo no los usa
    assert repositorio.escrituras == 0


@pytest.mark.parametrize("campo", ["tope_mensaje", "tope_video", "tope_audio", "tope_pdf"])
@pytest.mark.parametrize("valor", [0, -1])
def test_un_tope_menor_o_igual_a_cero_responde_el_422_generico_sin_codigo(
    cliente, campo: str, valor: int
) -> None:
    client, repositorio = cliente

    respuesta = client.put("/whatsmkt/configuracion", json={campo: valor})

    assert respuesta.status_code == 422
    assert isinstance(respuesta.json()["detail"], list)
    assert repositorio.escrituras == 0


@pytest.mark.parametrize("hora", ["8:00", "24:00", "08:60", "08:00:00", "ocho", ""])
def test_una_hora_que_no_es_hh_mm_responde_el_422_de_validacion(cliente, hora: str) -> None:
    client, _ = cliente

    respuesta = client.put(
        "/whatsmkt/configuracion", json={"horario_1": {"inicio": hora, "fin": "14:00"}}
    )

    assert respuesta.status_code == 422
    assert isinstance(respuesta.json()["detail"], list)  # la validacion de FastAPI, sin codigo


# --- GET y PUT /whatsmkt/segmentos ------------------------------------------------------------


def test_los_segmentos_se_leen_de_menor_a_mayor(cliente) -> None:
    client, _ = cliente

    respuesta = client.get("/whatsmkt/segmentos")

    assert respuesta.status_code == 200
    assert respuesta.json() == [
        {"clave": "preventivo", "etiqueta": "Preventivo", "desde": None, "hasta": 0, "orden": 0},
        {"clave": "tramo_2", "etiqueta": "Tramo 2", "desde": 1, "hasta": 8, "orden": 1},
        {
            "clave": "mayores_2",
            "etiqueta": "Tramos mayores al 2",
            "desde": 9,
            "hasta": None,
            "orden": 2,
        },
    ]


def _tres(**cambios: dict) -> list[dict]:
    base = {
        "preventivo": _segmento("preventivo", None, 0),
        "tramo_2": _segmento("tramo_2", 1, 8),
        "mayores_2": _segmento("mayores_2", 9, None),
    }
    return [{**fila, **cambios.get(clave, {})} for clave, fila in base.items()]


def test_el_put_edita_etiqueta_y_limites_de_los_3_y_fija_el_orden(cliente) -> None:
    client, repositorio = cliente

    respuesta = client.put(
        "/whatsmkt/segmentos",
        json=list(
            reversed(
                _tres(
                    preventivo={"etiqueta": "  Al dia ", "hasta": 2},
                    tramo_2={"desde": 3, "hasta": 10},
                    mayores_2={"desde": 11},
                )
            )
        ),
    )

    assert respuesta.status_code == 200
    assert [
        (s["clave"], s["etiqueta"], s["desde"], s["hasta"], s["orden"]) for s in respuesta.json()
    ] == [
        ("preventivo", "Al dia", None, 2, 0),
        ("tramo_2", "Tramo_2", 3, 10, 1),
        ("mayores_2", "Mayores_2", 11, None, 2),
    ]
    assert [s.clave for s in repositorio.segmentos] == ["preventivo", "tramo_2", "mayores_2"]
    assert client.get("/whatsmkt/segmentos").json() == respuesta.json()


@pytest.mark.parametrize(
    ("tabla", "codigo", "parametros"),
    [
        (
            _tres(tramo_2={"desde": 3}),
            "segmentos_con_hueco",
            {"desde": 1, "hasta": 2},
        ),
        (
            _tres(preventivo={"hasta": 5}),
            "segmentos_superpuestos",
            {"segmento": "preventivo", "fila": "tramo_2"},
        ),
    ],
)
def test_una_tabla_rota_responde_422_con_su_codigo_y_deja_la_anterior(
    cliente, tabla: list[dict], codigo: str, parametros: dict
) -> None:
    client, repositorio = cliente

    respuesta = client.put("/whatsmkt/segmentos", json=tabla)

    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == codigo
    assert {k: cuerpo[k] for k in parametros} == parametros
    assert repositorio.segmentos == list(SEGMENTOS_POR_DEFECTO)


@pytest.mark.parametrize(
    "cuerpo",
    [
        [],
        _tres()[:2],  # falta uno
        [*_tres(), _segmento("extra", 100, None)],  # sobra uno
        [*_tres()[:2], _segmento("tramo_2", 9, None)],  # una clave repetida
        [*_tres()[:2], _segmento("otra", 9, None)],  # una clave que no es de las 3
        _tres(preventivo={"etiqueta": "  "}),
        _tres(tramo_2={"desde": 9, "hasta": 1}),
        [{"clave": "preventivo", "etiqueta": "A", "desde": None}],
        {"segmentos": _tres()},
    ],
)
def test_un_cuerpo_que_no_es_el_de_los_3_fijos_responde_el_422_generico(cliente, cuerpo) -> None:
    client, repositorio = cliente

    respuesta = client.put("/whatsmkt/segmentos", json=cuerpo)

    assert respuesta.status_code == 422
    assert isinstance(respuesta.json()["detail"], list)  # validacion de FastAPI, sin codigo
    assert repositorio.segmentos == list(SEGMENTOS_POR_DEFECTO)


def test_el_contrato_declara_el_422_con_codigo_en_los_dos_put() -> None:
    esquemas = app.openapi()
    for ruta in ("/whatsmkt/configuracion", "/whatsmkt/segmentos"):
        ref = esquemas["paths"][ruta]["put"]["responses"]["422"]["content"]["application/json"]
        assert ref["schema"]["$ref"].endswith("/ErrorWhatsmktRespuesta")
    error = esquemas["components"]["schemas"]["ErrorWhatsmktRespuesta"]
    assert set(error["required"]) == {"detail", "codigo", *PARAMETROS_NULOS}
