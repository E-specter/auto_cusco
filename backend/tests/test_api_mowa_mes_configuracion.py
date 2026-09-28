"""Pruebas de los endpoints de configuracion de MOWA MES, calendario y supervisores.

Sustituyen la dependencia del caso de uso por el servicio real sobre un
repositorio en memoria: se prueba la traduccion HTTP, no la base.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.calendario import obtener_servicio_calendario
from app.api.mowa_mes import obtener_servicio_mowa_mes
from app.api.supervisores import obtener_servicio_supervision
from app.core.entities.calendario import ExcepcionCalendario, TipoExcepcion
from app.core.services.calendario.servicio import CalendarioService
from app.core.services.gestiones_digitales.servicio import SupervisionService
from app.core.services.plataformas.mowa_mes.configuracion import ConfiguracionMowaMesService
from app.main import app
from tests.test_calendario import RepositorioCalendarioFalso
from tests.test_gestiones_digitales import RepositorioSupervisionFalso
from tests.test_mowa_mes_speech import ORIGINAL, RepositorioMowaMesFalso

PARTES = [
    {"segmento": p.segmento.value, "parte_1": p.parte_1, "parte_2": p.parte_2} for p in ORIGINAL
]


@pytest.fixture
def cliente():
    calendario = CalendarioService(
        RepositorioCalendarioFalso(
            ExcepcionCalendario(date(2026, 9, 14), TipoExcepcion.AGREGADO, "Decreto sintetico")
        ),
        reloj=lambda: datetime(2026, 9, 13, 15, 0, tzinfo=UTC),
    )
    supervision = SupervisionService(RepositorioSupervisionFalso())
    mowa_mes = RepositorioMowaMesFalso(whatsapp=None)
    app.dependency_overrides[obtener_servicio_calendario] = lambda: calendario
    app.dependency_overrides[obtener_servicio_supervision] = lambda: supervision
    app.dependency_overrides[obtener_servicio_mowa_mes] = lambda: ConfiguracionMowaMesService(
        mowa_mes
    )
    try:
        yield TestClient(app), mowa_mes
    finally:
        app.dependency_overrides.clear()


# --- Calendario ---------------------------------------------------------


def test_feriados_del_anio_actual_en_lima(cliente) -> None:
    client, _ = cliente

    cuerpo = client.get("/calendario/feriados").json()

    assert cuerpo["anio"] == 2026
    assert {
        "fecha": "2026-04-02",
        "descripcion": "Jueves Santo",
        "origen": "ley",
        "retirado": False,
    } in cuerpo["dias"]
    assert {d["fecha"]: d["origen"] for d in cuerpo["dias"]}["2026-09-14"] == "agregado"


def test_feriados_de_otro_anio(cliente) -> None:
    client, _ = cliente

    cuerpo = client.get("/calendario/feriados", params={"anio": 2027}).json()

    assert "2027-03-25" in [d["fecha"] for d in cuerpo["dias"]]
    assert client.get("/calendario/feriados", params={"anio": 1800}).status_code == 422


def test_siguiente_dia_gestionable_desde_hoy_y_desde_una_fecha(cliente) -> None:
    client, _ = cliente

    hoy = client.get("/calendario/siguiente-dia-gestionable").json()
    semana_santa = client.get(
        "/calendario/siguiente-dia-gestionable", params={"desde": "2026-04-01"}
    ).json()

    assert hoy == {"desde": "2026-09-13", "fecha": "2026-09-15"}  # el 14 esta decretado
    assert semana_santa == {"desde": "2026-04-01", "fecha": "2026-04-06"}


def test_ciclo_de_excepciones(cliente) -> None:
    client, _ = cliente
    retiro = {"fecha": "2026-07-23", "tipo": "retirado", "descripcion": "Cambio de ley sintetico"}

    creada = client.post("/calendario/excepciones", json=retiro)
    repetida = client.post("/calendario/excepciones", json=retiro)
    sin_sentido = client.post("/calendario/excepciones", json={**retiro, "fecha": "2026-07-24"})
    listadas = client.get("/calendario/excepciones").json()

    assert creada.status_code == 201
    assert creada.json()["tipo"] == "retirado"
    assert repetida.status_code == 409
    assert sin_sentido.status_code == 400
    assert [e["fecha"] for e in listadas] == ["2026-07-23", "2026-09-14"]
    assert client.delete("/calendario/excepciones/2026-07-23").status_code == 204
    assert client.delete("/calendario/excepciones/2026-07-23").status_code == 404


# --- Supervisores -------------------------------------------------------


def test_reemplazar_supervisores_devuelve_el_documento_de_cada_uno(cliente) -> None:
    client, _ = cliente
    cuerpo = {
        "procedencias": ["Caja Cusco", "nuestra empresa"],
        "supervisores": [
            {"numero": "900000004", "procedencia": "nuestra empresa"},
            {"numero": "900000001", "procedencia": "Caja Cusco"},
        ],
    }

    respuesta = client.put("/supervisores", json=cuerpo)

    assert respuesta.status_code == 200
    assert [(s["numero"], s["documento"]) for s in respuesta.json()["supervisores"]] == [
        ("900000004", "00000002"),
        ("900000001", "00000001"),
    ]
    assert client.get("/supervisores").json() == respuesta.json()


def test_un_supervisor_con_numero_invalido_se_rechaza(cliente) -> None:
    client, _ = cliente

    respuesta = client.put(
        "/supervisores",
        json={
            "procedencias": ["Caja Cusco"],
            "supervisores": [{"numero": "12345", "procedencia": "Caja Cusco"}],
        },
    )

    assert respuesta.status_code == 400
    assert "9 digitos" in respuesta.json()["detail"]


# --- Configuracion del conector -----------------------------------------


def test_configuracion_del_conector(cliente) -> None:
    client, _ = cliente

    inicial = client.get("/mowa-mes/configuracion").json()
    guardada = client.put(
        "/mowa-mes/configuracion",
        json={"limite_mensual": 3_000_000, "whatsapp_contacto": "900000123"},
    )
    invalida = client.put(
        "/mowa-mes/configuracion", json={"limite_mensual": 1, "whatsapp_contacto": "800000123"}
    )

    assert (inicial["limite_mensual"], inicial["whatsapp_contacto"]) == (2_500_000, None)
    assert guardada.status_code == 200
    assert guardada.json()["whatsapp_contacto"] == "900000123"
    assert invalida.status_code == 400
    assert client.put("/mowa-mes/configuracion", json={"limite_mensual": 0}).status_code == 422


# --- Speech -------------------------------------------------------------


def test_listar_y_obtener_speech(cliente) -> None:
    client, _ = cliente

    (original,) = client.get("/mowa-mes/speech").json()
    no_existe = client.get("/mowa-mes/speech/99")

    assert (original["nombre"], original["original"], original["editable"]) == (
        "Speech original",
        True,
        False,
    )
    assert original["partes"][2] == {
        "segmento": "9_a_30",
        "etiqueta": "9 a 30",
        "dias_desde": 9,
        "dias_hasta": 30,
        "parte_1": ORIGINAL[2].parte_1,
        "parte_2": ORIGINAL[2].parte_2,
        "usa_whatsapp": False,
    }
    assert original["partes"][0]["dias_desde"] is None
    assert client.get("/mowa-mes/speech/1").json() == original
    assert no_existe.status_code == 404


def test_crear_editar_y_proteger_versiones(cliente) -> None:
    client, repositorio = cliente

    creada = client.post("/mowa-mes/speech", json={"basada_en_id": 1, "partes": PARTES})
    speech_id = creada.json()["id"]
    editada = client.put(
        f"/mowa-mes/speech/{speech_id}", json={"nombre": "Speech corregido", "partes": PARTES}
    )
    repetida = client.post(
        "/mowa-mes/speech", json={"nombre": "speech corregido", "partes": PARTES}
    )
    original = client.put("/mowa-mes/speech/1", json={"nombre": "Otro", "partes": PARTES})
    repositorio.marcar_speech_usado(speech_id)
    usada = client.put(
        f"/mowa-mes/speech/{speech_id}", json={"nombre": "Speech corregido", "partes": PARTES}
    )

    assert creada.status_code == 201
    assert (creada.json()["nombre"], creada.json()["basada_en_id"]) == ("Speech 2", 1)
    assert editada.status_code == 200
    assert repetida.status_code == 409
    assert original.status_code == 409
    assert usada.status_code == 409
    assert "version nueva" in usada.json()["detail"]
    assert client.get(f"/mowa-mes/speech/{speech_id}").json()["usada"] is True


@pytest.mark.parametrize(
    ("cuerpo", "estado"),
    [
        ({"partes": PARTES[:5]}, 400),
        ({"partes": [{**PARTES[0], "parte_1": " [@titular]"}, *PARTES[1:]]}, 400),
        ({"basada_en_id": 99, "partes": PARTES}, 404),
        ({"partes": [{**PARTES[0], "segmento": "inventado"}, *PARTES[1:]]}, 422),
    ],
)
def test_versiones_invalidas(cliente, cuerpo, estado) -> None:
    client, _ = cliente

    assert client.post("/mowa-mes/speech", json=cuerpo).status_code == estado


def test_previsualizacion_sin_whatsapp_marca_los_segmentos_que_lo_necesitan(cliente) -> None:
    client, _ = cliente

    cuerpo = client.post("/mowa-mes/speech/previsualizacion", json={"partes": PARTES}).json()

    por_segmento = {s["segmento"]: s for s in cuerpo["segmentos"]}
    assert (cuerpo["whatsapp"], cuerpo["largo_advertencia"], cuerpo["largo_maximo"]) == (
        None,
        150,
        160,
    )
    assert por_segmento["31_a_60"]["falta_whatsapp"] is True
    assert por_segmento["31_a_60"]["ejemplo"] is None
    assert por_segmento["9_a_30"]["codigo"] == "mensaje_excede_150"
    assert por_segmento["preventiva"]["falta_whatsapp"] is False


def test_previsualizacion_con_whatsapp_y_problemas(cliente) -> None:
    client, _ = cliente
    partes = [{**PARTES[0], "parte_2": " [@"}, *PARTES[1:]]

    cuerpo = client.post(
        "/mowa-mes/speech/previsualizacion", json={"partes": partes, "whatsapp": "900000123"}
    ).json()
    invalido = client.post(
        "/mowa-mes/speech/previsualizacion", json={"partes": PARTES, "whatsapp": "123"}
    )

    assert cuerpo["whatsapp"] == "900000123"
    assert cuerpo["problemas"] == [
        {"segmento": "preventiva", "campo": "parte_2", "detalle": "El texto no puede contener '[@'"}
    ]
    assert all(not s["falta_whatsapp"] for s in cuerpo["segmentos"])
    assert invalido.status_code == 400


GUARDADA = {
    "limite_mensual": 2_500_000,
    "whatsapp_contacto": "900000123",
    "registros_por_archivo": 40_000,
    "bytes_por_archivo": 1_500_000,
}


def _guardada(client: TestClient) -> None:
    assert client.put("/mowa-mes/configuracion", json=GUARDADA).status_code == 200


# PUT /mowa-mes/configuracion es una actualizacion parcial: omitido conserva.


@pytest.mark.parametrize(
    "campo", ["whatsapp_contacto", "registros_por_archivo", "bytes_por_archivo"]
)
def test_un_campo_omitido_conserva_su_valor(cliente, campo) -> None:
    client, _ = cliente
    _guardada(client)
    cuerpo = {k: v for k, v in GUARDADA.items() if k != campo}

    respuesta = client.put("/mowa-mes/configuracion", json=cuerpo)

    assert respuesta.status_code == 200
    assert respuesta.json()[campo] == GUARDADA[campo]


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("whatsapp_contacto", "900000456"),
        ("registros_por_archivo", 30_000),
        ("bytes_por_archivo", 1_000_000),
    ],
)
def test_un_campo_con_valor_lo_cambia(cliente, campo, valor) -> None:
    client, _ = cliente
    _guardada(client)

    respuesta = client.put("/mowa-mes/configuracion", json={**GUARDADA, campo: valor})

    assert respuesta.status_code == 200
    assert respuesta.json()[campo] == valor


def test_whatsapp_null_explicito_borra_el_numero(cliente) -> None:
    client, _ = cliente
    _guardada(client)

    cuerpo = client.put(
        "/mowa-mes/configuracion", json={**GUARDADA, "whatsapp_contacto": None}
    ).json()

    assert cuerpo["whatsapp_contacto"] is None
    assert (cuerpo["registros_por_archivo"], cuerpo["bytes_por_archivo"]) == (40_000, 1_500_000)


@pytest.mark.parametrize("campo", ["registros_por_archivo", "bytes_por_archivo"])
def test_null_en_un_campo_que_no_lo_admite_responde_422_sin_tratarse_como_omitido(
    cliente, campo
) -> None:
    client, repositorio = cliente
    _guardada(client)

    respuesta = client.put("/mowa-mes/configuracion", json={**GUARDADA, campo: None})

    assert respuesta.status_code == 422
    assert getattr(repositorio.configuracion, campo) == GUARDADA[campo]


def test_limite_mensual_es_obligatorio(cliente) -> None:
    client, _ = cliente

    assert client.put("/mowa-mes/configuracion", json={}).status_code == 422
    assert (
        client.put("/mowa-mes/configuracion", json={**GUARDADA, "limite_mensual": None}).status_code
        == 422
    )


# --- Tarifa por SMS y plantilla del nombre de los archivos (B8) ----------


def test_la_configuracion_trae_tarifa_plantilla_y_las_variables_validas(cliente) -> None:
    client, _ = cliente

    cuerpo = client.get("/mowa-mes/configuracion").json()

    assert cuerpo["tarifa_sms"] == "0.0200"
    assert cuerpo["plantilla_nombre_archivo"] == "mowa_mes_campana_{campana}_{archivo}_de_{total}"
    assert [v["nombre"] for v in cuerpo["variables_plantilla"]] == [
        "campana",
        "descripcion",
        "fecha_envio",
        "fecha_corte",
        "archivo",
        "total",
        "cantidad",
    ]
    assert all(v["descripcion"] for v in cuerpo["variables_plantilla"])


@pytest.mark.parametrize(
    ("enviada", "guardada"),
    [
        ("0.0125", "0.0125"),
        ("1", "1.0000"),
        ("0", "0.0000"),
        ("0.05", "0.0500"),
        (" 0.03 ", "0.0300"),
    ],
)
def test_la_tarifa_se_guarda_como_texto_decimal_exacto(cliente, enviada, guardada) -> None:
    client, repositorio = cliente

    respuesta = client.put("/mowa-mes/configuracion", json={**GUARDADA, "tarifa_sms": enviada})

    assert respuesta.status_code == 200
    assert respuesta.json()["tarifa_sms"] == guardada
    assert isinstance(repositorio.configuracion.tarifa_sms, Decimal)
    assert client.get("/mowa-mes/configuracion").json()["tarifa_sms"] == guardada


def test_una_tarifa_omitida_conserva_la_guardada(cliente) -> None:
    client, _ = cliente
    client.put("/mowa-mes/configuracion", json={**GUARDADA, "tarifa_sms": "0.0375"})

    respuesta = client.put("/mowa-mes/configuracion", json=GUARDADA)

    assert respuesta.json()["tarifa_sms"] == "0.0375"


@pytest.mark.parametrize(
    "invalida", ["-0.01", "0.00001", "abc", "", "1e2", "0,02", "NaN", "123456789"]
)
def test_una_tarifa_invalida_responde_400_con_el_motivo_y_no_guarda(cliente, invalida) -> None:
    client, repositorio = cliente

    respuesta = client.put("/mowa-mes/configuracion", json={**GUARDADA, "tarifa_sms": invalida})

    assert respuesta.status_code == 400
    assert "hasta 4 decimales" in respuesta.json()["detail"]
    assert repositorio.configuracion.tarifa_sms == Decimal("0.02")


@pytest.mark.parametrize("campo", ["tarifa_sms", "plantilla_nombre_archivo"])
def test_null_en_tarifa_o_plantilla_responde_422_y_no_se_trata_como_omitido(cliente, campo) -> None:
    client, repositorio = cliente
    antes = getattr(repositorio.configuracion, campo)

    respuesta = client.put("/mowa-mes/configuracion", json={**GUARDADA, campo: None})

    assert respuesta.status_code == 422
    assert getattr(repositorio.configuracion, campo) == antes


def test_la_tarifa_no_se_acepta_como_numero_de_json(cliente) -> None:
    # Un monto no pasa por float: 0.02 como numero JSON no es un texto decimal.
    client, repositorio = cliente

    respuesta = client.put("/mowa-mes/configuracion", json={**GUARDADA, "tarifa_sms": 0.02})

    assert respuesta.status_code == 422
    assert repositorio.configuracion.tarifa_sms == Decimal("0.02")


def test_la_plantilla_se_guarda_y_una_omitida_conserva_la_guardada(cliente) -> None:
    client, _ = cliente
    plantilla = "CajaCusco_{fecha_envio}_{archivo}de{total}"

    guardada = client.put(
        "/mowa-mes/configuracion", json={**GUARDADA, "plantilla_nombre_archivo": plantilla}
    )
    omitida = client.put("/mowa-mes/configuracion", json=GUARDADA)

    assert guardada.json()["plantilla_nombre_archivo"] == plantilla
    assert omitida.json()["plantilla_nombre_archivo"] == plantilla


def test_una_plantilla_vacia_vuelve_a_la_de_por_defecto(cliente) -> None:
    client, _ = cliente
    client.put("/mowa-mes/configuracion", json={**GUARDADA, "plantilla_nombre_archivo": "otra"})

    respuesta = client.put(
        "/mowa-mes/configuracion", json={**GUARDADA, "plantilla_nombre_archivo": ""}
    )

    assert respuesta.json()["plantilla_nombre_archivo"] == (
        "mowa_mes_campana_{campana}_{archivo}_de_{total}"
    )


@pytest.mark.parametrize(
    ("plantilla", "dice"),
    [("caja_{nombre}", "{nombre}"), ("caja_{campana", "sin cerrar"), ("caja}", "sin abrir")],
)
def test_una_plantilla_invalida_responde_400_nombrando_la_variable_y_no_guarda(
    cliente, plantilla, dice
) -> None:
    client, repositorio = cliente

    respuesta = client.put(
        "/mowa-mes/configuracion", json={**GUARDADA, "plantilla_nombre_archivo": plantilla}
    )

    assert respuesta.status_code == 400
    assert dice in respuesta.json()["detail"]
    assert repositorio.configuracion.plantilla_nombre_archivo.startswith("mowa_mes_campana_")


@pytest.mark.parametrize(
    ("cambio", "campo"),
    [
        ({"tarifa_sms": "-1"}, "tarifa_sms"),
        ({"tarifa_sms": "abc"}, "tarifa_sms"),
        ({"tarifa_sms": "0.00001"}, "tarifa_sms"),
        ({"plantilla_nombre_archivo": "a_{x}"}, "plantilla_nombre_archivo"),
        ({"plantilla_nombre_archivo": "a_{campana"}, "plantilla_nombre_archivo"),
        ({"plantilla_nombre_archivo": "a}"}, "plantilla_nombre_archivo"),
        ({"plantilla_nombre_archivo": "a" * 301}, "plantilla_nombre_archivo"),
        ({"whatsapp_contacto": "800000123"}, "whatsapp_contacto"),
    ],
)
def test_el_400_de_la_configuracion_trae_el_campo_al_que_pertenece(cliente, cambio, campo) -> None:
    # El frontend ubica el error bajo su campo por `campo`, no leyendo el texto del `detail`.
    client, repositorio = cliente

    respuesta = client.put("/mowa-mes/configuracion", json={**GUARDADA, **cambio})

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"detail", "campo"}
    assert cuerpo["campo"] == campo
    assert isinstance(cuerpo["detail"], str) and cuerpo["detail"]
    assert repositorio.escrituras == 0


def test_si_hay_dos_errores_el_400_habla_de_uno_solo_y_dice_de_cual(cliente) -> None:
    client, _ = cliente

    respuesta = client.put(
        "/mowa-mes/configuracion",
        json={**GUARDADA, "tarifa_sms": "abc", "plantilla_nombre_archivo": "a_{x}"},
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["campo"] == "tarifa_sms"  # la tarifa se lee antes que la plantilla


def test_el_contrato_declara_el_400_de_la_configuracion_con_su_campo() -> None:
    from app.api import contrato

    esquema = contrato.generar()
    campo = esquema["components"]["schemas"]["ErrorConfiguracionRespuesta"]["properties"]["campo"]
    enum = esquema["components"]["schemas"]["CampoConfiguracion"]["enum"]

    assert campo == {"$ref": "#/components/schemas/CampoConfiguracion"}
    assert enum == [
        "limite_mensual",
        "whatsapp_contacto",
        "registros_por_archivo",
        "bytes_por_archivo",
        "tarifa_sms",
        "plantilla_nombre_archivo",
    ]
    for ruta in ("/mowa-mes/configuracion", "/mowa-mes/plantilla-nombre-archivo/previsualizacion"):
        verbo = "put" if ruta == "/mowa-mes/configuracion" else "post"
        assert esquema["paths"][ruta][verbo]["responses"]["400"]["content"]["application/json"][
            "schema"
        ] == {"$ref": "#/components/schemas/ErrorConfiguracionRespuesta"}


def test_la_previsualizacion_de_la_plantilla_resuelve_con_datos_de_muestra(cliente) -> None:
    client, repositorio = cliente

    respuesta = client.post(
        "/mowa-mes/plantilla-nombre-archivo/previsualizacion",
        json={"plantilla": "CajaCusco_{fecha_envio}_{archivo}de{total}"},
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "plantilla": "CajaCusco_{fecha_envio}_{archivo}de{total}",
        "nombres_ejemplo": ["CajaCusco_2026-10-01_1de2.xlsx", "CajaCusco_2026-10-01_2de2.xlsx"],
    }
    assert repositorio.escrituras == 0  # no guarda nada


def test_la_previsualizacion_sin_variables_agrega_el_sufijo_y_una_vacia_usa_la_de_por_defecto(
    cliente,
) -> None:
    client, _ = cliente
    ruta = "/mowa-mes/plantilla-nombre-archivo/previsualizacion"

    sin_variables = client.post(ruta, json={"plantilla": "caja"}).json()
    vacia = client.post(ruta, json={"plantilla": "  "}).json()

    assert sin_variables["nombres_ejemplo"] == ["caja_1de2.xlsx", "caja_2de2.xlsx"]
    assert vacia["nombres_ejemplo"] == [
        "mowa_mes_campana_1234_1_de_2.xlsx",
        "mowa_mes_campana_1234_2_de_2.xlsx",
    ]


@pytest.mark.parametrize(
    ("plantilla", "dice"),
    [("a_{foo}_b", "{foo}"), ("a_{", "sin cerrar"), ("a_}", "sin abrir")],
)
def test_la_previsualizacion_de_una_plantilla_invalida_responde_400(
    cliente, plantilla, dice
) -> None:
    client, _ = cliente

    respuesta = client.post(
        "/mowa-mes/plantilla-nombre-archivo/previsualizacion", json={"plantilla": plantilla}
    )

    assert respuesta.status_code == 400
    assert dice in respuesta.json()["detail"]
    assert respuesta.json()["campo"] == "plantilla_nombre_archivo"


def test_la_previsualizacion_de_la_plantilla_exige_el_campo(cliente) -> None:
    client, _ = cliente
    ruta = "/mowa-mes/plantilla-nombre-archivo/previsualizacion"

    assert client.post(ruta, json={}).status_code == 422
    assert client.post(ruta, json={"plantilla": None}).status_code == 422


@pytest.mark.parametrize("vacio", ["", "   "])
def test_whatsapp_vacio_o_en_blanco_borra_el_numero_igual_que_null(cliente, vacio) -> None:
    client, _ = cliente
    _guardada(client)

    respuesta = client.put("/mowa-mes/configuracion", json={**GUARDADA, "whatsapp_contacto": vacio})

    assert respuesta.status_code == 200
    assert respuesta.json()["whatsapp_contacto"] is None
