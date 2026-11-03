"""POST /whatsmkt/campanas/previsualizacion, sin base (T-WM-B4a; RF-WM-35).

El servicio real sobre dobles en memoria: se prueba la traduccion HTTP (forma, cortes en 20 y 100
con el total exacto, problemas con 200, errores 404 y 400, contrato). Telefonos 900000xxx.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.whatsmkt_campanas import (
    EXCLUSIONES_EN_PREVIA,
    FILAS_DE_MUESTRA,
    obtener_servicio_previa_whatsmkt,
)
from app.main import app
from tests.ayudas.previa_whatsmkt_falsos import DEFINICION_ID, servicio_de_previa
from tests.test_whatsmkt_contactos import SUPERVISORES, definicion, producto

RUTA = "/whatsmkt/campanas/previsualizacion"


@pytest.fixture
def cliente():
    estado = {"productos": [], "plataforma": "whatsmkt", "supervisores": SUPERVISORES}
    app.dependency_overrides[obtener_servicio_previa_whatsmkt] = lambda: servicio_de_previa(
        estado["productos"],
        definicion(),
        plataforma=estado["plataforma"],
        supervisores=estado["supervisores"],
    )
    try:
        yield TestClient(app), estado
    finally:
        app.dependency_overrides.clear()


def cuerpo(**cambios) -> dict:
    base = {
        "fecha_corte": "2026-11-02",
        "fecha_envio": "2026-11-02",
        "cantidad": 1000,
        "definicion": {"id": DEFINICION_ID},
        "modo": "global",
    }
    return {**base, **cambios}


def pedir(cliente, productos, **cambios):
    client, estado = cliente
    estado["productos"] = productos
    return client.post(RUTA, json=cuerpo(**cambios))


# --- La forma ---------------------------------------------------------------------------------


def test_una_campana_global_trae_cifras_cabeceras_muestra_y_exclusiones(cliente) -> None:
    respuesta = pedir(cliente, [producto(1, titular="Ana"), producto(2, telefono=None)])

    assert respuesta.status_code == 200
    cuerpo_ = respuesta.json()
    [campana] = cuerpo_["campanas"]
    assert campana["segmento"] is None and campana["etiqueta_segmento"] is None
    assert (campana["cantidad"], campana["productos"], campana["supervisores"]) == (3, 1, 2)
    assert campana["cabeceras"] == [
        {"nombre": "número", "etiqueta": None},
        {"nombre": "[$MARCRO1$]", "etiqueta": "Nombres del titular"},
        {"nombre": "[$MARCRO2$]", "etiqueta": None},
    ]
    assert [(f["supervision"], f["celdas"][0]) for f in campana["muestra"]] == [
        (True, "51900000902"),
        (True, "51900000901"),
        (False, "51900000001"),
    ]
    assert campana["muestra"][2]["celdas"] == ["51900000001", "Ana", f"{1:018d}"]
    assert campana["total_exclusiones"] == 1
    assert campana["exclusiones"] == [
        {
            "codigo": "sin_telefono",
            "fila": 2,
            "pagare": f"{2:018d}",
            "detalle": "El producto no tiene telefono",
            "macro": None,
            "etiqueta": None,
        }
    ]
    assert cuerpo_["problemas"] == []
    assert (cuerpo_["disponibles"], cuerpo_["solicitados"]) == (2, 1000)
    assert cuerpo_["total_exclusiones"] == 1
    assert cuerpo_["total_exclusiones_sin_campana"] == 0


def test_una_macro_vacia_trae_su_numero_y_etiqueta(cliente) -> None:
    respuesta = pedir(cliente, [producto(1), producto(2, titular=None)])

    [exclusion] = respuesta.json()["campanas"][0]["exclusiones"]
    assert exclusion["codigo"] == "macro_vacia"
    assert (exclusion["macro"], exclusion["etiqueta"]) == (1, "Nombres del titular")


def test_por_segmento_trae_una_campana_por_segmento_con_su_etiqueta(cliente) -> None:
    respuesta = pedir(
        cliente, [producto(1, 20), producto(2, -3), producto(3, 5)], modo="por_segmento"
    )

    assert [
        (c["segmento"], c["etiqueta_segmento"], c["productos"])
        for c in respuesta.json()["campanas"]
    ] == [
        ("preventivo", "Preventivo", 1),
        ("tramo_2", "Tramo 2", 1),
        ("mayores_2", "Tramos mayores al 2", 1),
    ]


# --- Los cortes -------------------------------------------------------------------------------


def test_la_muestra_corta_en_20_y_las_exclusiones_en_100_con_el_total_exacto(cliente) -> None:
    validos = [producto(i) for i in range(1, 31)]
    sin_telefono = [producto(i, telefono=None) for i in range(31, 151)]

    respuesta = pedir(cliente, validos + sin_telefono)

    [campana] = respuesta.json()["campanas"]
    assert len(campana["muestra"]) == FILAS_DE_MUESTRA == 20
    assert campana["cantidad"] == 32  # 30 productos y 2 supervisores: la muestra no la acota
    assert campana["total_exclusiones"] == 120
    assert len(campana["exclusiones"]) == EXCLUSIONES_EN_PREVIA == 100
    assert [e["fila"] for e in campana["exclusiones"]] == list(range(31, 131))
    assert respuesta.json()["total_exclusiones"] == 120


def test_con_exactamente_20_filas_y_100_exclusiones_no_se_corta_nada(cliente) -> None:
    validos = [producto(i) for i in range(1, 19)]  # 18 + 2 supervisores = 20
    sin_telefono = [producto(i, telefono=None) for i in range(19, 119)]

    [campana] = pedir(cliente, validos + sin_telefono).json()["campanas"]

    assert (len(campana["muestra"]), campana["cantidad"]) == (20, 20)
    assert (len(campana["exclusiones"]), campana["total_exclusiones"]) == (100, 100)


# --- Problemas con 200 ------------------------------------------------------------------------


def test_sin_supervisores_es_un_problema_con_200_y_la_previa_igual_viene(cliente) -> None:
    client, estado = cliente
    estado["supervisores"] = ()

    respuesta = pedir(cliente, [producto(1)])

    assert respuesta.status_code == 200
    cuerpo_ = respuesta.json()
    assert [p["codigo"] for p in cuerpo_["problemas"]] == ["sin_supervisores"]
    assert isinstance(cuerpo_["problemas"][0]["detalle"], str)
    assert cuerpo_["campanas"][0]["supervisores"] == 0


def test_sin_productos_es_un_problema_con_200(cliente) -> None:
    respuesta = pedir(cliente, [producto(1, telefono=None)])

    assert respuesta.status_code == 200
    cuerpo_ = respuesta.json()
    assert cuerpo_["campanas"] == []
    assert [p["codigo"] for p in cuerpo_["problemas"]] == ["sin_productos"]
    assert cuerpo_["total_exclusiones"] == cuerpo_["total_exclusiones_sin_campana"] == 1


def test_una_definicion_que_no_es_de_whatsmkt_es_un_problema_con_200(cliente) -> None:
    client, estado = cliente
    estado["plataforma"] = "mowa_mes"

    respuesta = pedir(cliente, [producto(1)])

    assert respuesta.status_code == 200
    assert respuesta.json()["campanas"] == []
    assert [p["codigo"] for p in respuesta.json()["problemas"]] == ["definicion_no_whatsmkt"]


def test_sin_dias_de_atraso_es_exclusion_solo_por_segmento(cliente) -> None:
    productos = [producto(1, None), producto(2, 5)]

    por_segmento = pedir(cliente, productos, modo="por_segmento").json()
    global_ = pedir(cliente, productos, modo="global").json()

    [sin_dias] = por_segmento["exclusiones_sin_campana"]
    assert (sin_dias["codigo"], sin_dias["fila"]) == ("sin_dias_atraso", 1)
    assert por_segmento["total_exclusiones_sin_campana"] == 1
    assert global_["total_exclusiones"] == 0 and global_["campanas"][0]["productos"] == 2


# --- La fecha de envio ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dias", "envio", "segmento"),
    [
        (0, "2026-11-02", "preventivo"),
        (0, "2026-11-03", "tramo_2"),
        (7, "2026-11-03", "tramo_2"),
        (7, "2026-11-04", "mayores_2"),
    ],
)
def test_la_fecha_de_envio_cambia_el_segmento_en_los_bordes(cliente, dias, envio, segmento) -> None:
    respuesta = pedir(cliente, [producto(1, dias)], modo="por_segmento", fecha_envio=envio)

    assert [c["segmento"] for c in respuesta.json()["campanas"]] == [segmento]


def test_la_fecha_de_envio_se_usa_tal_como_llega_aunque_sea_domingo(cliente) -> None:
    # shortcut de B4a: sin validar contra RF-70; B4b la valida. Hoy un domingo no se rechaza.
    respuesta = pedir(cliente, [producto(1, 3)], modo="por_segmento", fecha_envio="2026-11-08")

    assert respuesta.status_code == 200
    assert [c["segmento"] for c in respuesta.json()["campanas"]] == ["mayores_2"]


def test_una_fecha_de_envio_anterior_al_corte_responde_400_con_su_codigo(cliente) -> None:
    respuesta = pedir(cliente, [producto(1)], fecha_envio="2026-11-01")

    assert respuesta.status_code == 400
    cuerpo_ = respuesta.json()
    assert cuerpo_["codigo"] == "fecha_envio_anterior"
    assert (cuerpo_["fecha_envio"], cuerpo_["fecha_corte"]) == ("2026-11-01", "2026-11-02")


# --- Errores ----------------------------------------------------------------------------------


def test_una_definicion_que_no_existe_responde_404(cliente) -> None:
    respuesta = pedir(cliente, [producto(1)], definicion={"id": 99})

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "definicion_no_encontrada"


def test_una_version_que_no_existe_responde_404(cliente) -> None:
    respuesta = pedir(cliente, [producto(1)], definicion={"id": DEFINICION_ID, "version": 7})

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "version_no_encontrada"


def test_un_filtro_mal_escrito_responde_400(cliente) -> None:
    respuesta = pedir(cliente, [producto(1)], filtros=["sin_forma"])

    assert respuesta.status_code == 400
    assert isinstance(respuesta.json()["detail"], str)


@pytest.mark.parametrize(
    "cambios",
    [{"cantidad": 0}, {"modo": "otro"}, {"definicion": {}}, {"fecha_corte": "ayer"}],
)
def test_un_pedido_mal_formado_responde_el_422_de_validacion(cliente, cambios) -> None:
    respuesta = pedir(cliente, [producto(1)], **cambios)

    assert respuesta.status_code == 422
    assert isinstance(respuesta.json()["detail"], list)


# --- Contrato ---------------------------------------------------------------------------------


def test_el_contrato_declara_la_previsualizacion() -> None:
    esquema = app.openapi()
    operacion = esquema["paths"][RUTA]["post"]

    assert operacion["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/PrevisualizacionCampanasWhatsmktRespuesta"
    )
    assert {"400", "404"} <= set(operacion["responses"])
    schemas = esquema["components"]["schemas"]
    respuesta = schemas["PrevisualizacionCampanasWhatsmktRespuesta"]
    assert {"campanas", "problemas", "total_exclusiones"} <= set(respuesta["required"])
    # B4b le suma campos; estos nombres no cambian.
    campana = schemas["CampanaPrevistaWhatsmktRespuesta"]
    assert {"segmento", "cantidad", "total_exclusiones", "exclusiones", "muestra"} <= set(
        campana["required"]
    )
