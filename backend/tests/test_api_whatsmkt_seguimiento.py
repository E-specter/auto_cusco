"""El seguimiento de las campanas de WhatsMKT, sin base (T-WM-B6; RF-WM-37 a RF-WM-42).

Importar el informe (con el lector de tablas real sobre un .xlsx sintetico), reemplazarlo con y sin
confirmacion, los rechazos, la conciliacion, descartar, restaurar y eliminar, y el filtro de estado
de la lista. Los servicios reales sobre el repositorio en memoria. Telefonos 900000xxx; los del
informe, 51900000xxx.
"""

from dataclasses import replace
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.adapters.input.lector_informe_whatsmkt import leer_tabla_del_informe
from app.api.whatsmkt_campanas import (
    obtener_repositorio_campanas_whatsmkt,
    obtener_servicio_consulta_whatsmkt,
    obtener_servicio_creacion_whatsmkt,
)
from app.api.whatsmkt_seguimiento import (
    obtener_servicio_gestion_whatsmkt,
    obtener_servicio_informes_whatsmkt,
)
from app.core.services.plataformas.whatsmkt.consulta import ConsultaCampanasWhatsmktService
from app.core.services.plataformas.whatsmkt.gestion import GestionCampanasWhatsmktService
from app.core.services.plataformas.whatsmkt.informes import InformesWhatsmktService
from app.main import app
from tests.ayudas.campanas_whatsmkt_falsas import DESCARTADA_EN, Entorno
from tests.ayudas.informe_whatsmkt_sintetico import (
    CAMPANA_INFORMADA,
    MIME_XLSX,
    TIPO_INFORMADO,
    informe_xlsx,
)
from tests.test_api_whatsmkt_campanas_crear import HOLA, RUTA, cuerpo
from tests.test_whatsmkt_contactos import producto

SEGMENTOS = dict.fromkeys(("preventivo", "tramo_2", "mayores_2"), {"texto_guardado_id": 10})
POR_SEGMENTO = {"modo": "por_segmento", "mensaje": None, "mensajes": SEGMENTOS}
# El archivo de la campana 1: dos supervisores y los productos 1 y 2.
SUPERVISORES = ("51900000901", "51900000902")
PRODUCTOS = ("51900000001", "51900000002")


@pytest.fixture
def cliente():
    e = Entorno([producto(1, 0), producto(2, 0)])
    e.textos.agregar(10, HOLA, nombre="Cobranza")
    e.whatsmkt.configuracion = replace(e.whatsmkt.configuracion, whatsapp_contacto="900000123")
    app.dependency_overrides[obtener_servicio_creacion_whatsmkt] = e.servicio
    app.dependency_overrides[obtener_repositorio_campanas_whatsmkt] = lambda: e.campanas
    app.dependency_overrides[obtener_servicio_consulta_whatsmkt] = lambda: (
        ConsultaCampanasWhatsmktService(e.campanas, e.whatsmkt)
    )
    app.dependency_overrides[obtener_servicio_informes_whatsmkt] = lambda: InformesWhatsmktService(
        e.campanas, leer_tabla_del_informe
    )
    app.dependency_overrides[obtener_servicio_gestion_whatsmkt] = lambda: (
        GestionCampanasWhatsmktService(e.campanas)
    )
    try:
        yield TestClient(app), e
    finally:
        app.dependency_overrides.clear()


def crear(cliente, **cambios):
    client, _ = cliente
    respuesta = client.post(RUTA, json=cuerpo(**cambios))
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def importar(cliente, campana_id=1, contenido=None, nombre="informe.xlsx", reemplazar=None):
    client, _ = cliente
    if contenido is None:
        contenido = informe_xlsx([*PRODUCTOS, *SUPERVISORES])
    datos = {} if reemplazar is None else {"reemplazar": "true" if reemplazar else "false"}
    return client.post(
        f"{RUTA}/{campana_id}/reportes",
        files={"archivo": (nombre, contenido, MIME_XLSX)},
        data=datos,
    )


def ids(respuesta) -> list[int]:
    return [c["id"] for c in respuesta.json()["campanas"]]


# --- Importar ---------------------------------------------------------------------------------


def test_importar_responde_201_con_el_resumen_y_la_conciliacion(cliente) -> None:
    crear(cliente)
    informe = informe_xlsx([*PRODUCTOS, "51900000901", "51900000777"])  # un supervisor, un ajeno

    respuesta = importar(cliente, contenido=informe)

    assert respuesta.status_code == 201
    cuerpo_ = respuesta.json()
    assert (cuerpo_["campana_id"], cuerpo_["pendiente"]) == (1, False)
    assert cuerpo_["informe"] == {
        "archivo_nombre": "informe.xlsx",
        "importado_en": DESCARTADA_EN.isoformat(),
        "fecha_informada": "2026-10-30",
        "total_informado": 4,
        "filas": 4,
        "coincide_total": True,
        "campana_informada": CAMPANA_INFORMADA,
        "tipo_envio_informado": TIPO_INFORMADO,
    }
    assert cuerpo_["conciliacion"] == {
        "productos": {"cargados": 2, "enviados": 2, "no_enviados": 0},
        "supervision": {"cargados": 2, "enviados": 1, "no_enviados": 1},
        "total": {"cargados": 4, "enviados": 3, "no_enviados": 1},
        "sin_correspondencia": ["51900000777"],
        "total_sin_correspondencia": 1,
    }


def test_el_informe_se_lee_de_la_hoja_informe_aunque_no_sea_la_primera(cliente) -> None:
    crear(cliente)

    respuesta = importar(cliente, contenido=informe_xlsx(PRODUCTOS, hojas_antes=("Resumen",)))

    assert respuesta.status_code == 201
    assert respuesta.json()["informe"]["filas"] == 2


def test_una_portada_vacia_antes_de_la_hoja_informe_no_hace_fallar_la_lectura(cliente) -> None:
    crear(cliente)

    respuesta = importar(
        cliente, contenido=informe_xlsx(PRODUCTOS, hojas_antes=("Portada", "Notas"))
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["conciliacion"]["productos"]["enviados"] == 2


def test_el_nombre_de_la_hoja_se_compara_sin_mayusculas_ni_tildes(cliente) -> None:
    crear(cliente)

    respuesta = importar(
        cliente, contenido=informe_xlsx(PRODUCTOS, hoja="INFORME", hojas_antes=("Portada",))
    )

    assert respuesta.status_code == 201


def test_sin_hoja_informe_y_con_la_primera_vacia_se_rechaza_con_su_codigo(cliente) -> None:
    crear(cliente)

    respuesta = importar(
        cliente, contenido=informe_xlsx(PRODUCTOS, hoja="Datos", hojas_antes=("Portada",))
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "informe_sin_encabezados"


def test_sin_una_hoja_llamada_informe_se_lee_la_primera(cliente) -> None:
    crear(cliente)

    respuesta = importar(cliente, contenido=informe_xlsx(PRODUCTOS, hoja="Hoja1"))

    assert respuesta.status_code == 201
    assert respuesta.json()["conciliacion"]["productos"]["enviados"] == 2


def test_un_numero_que_cubre_dos_productos_cuenta_el_envio_para_los_dos(cliente) -> None:
    _, e = cliente
    e.productos = [producto(1, 0), producto(2, 0, telefono="900000001")]  # mismo numero
    crear(cliente)

    respuesta = importar(cliente, contenido=informe_xlsx(["51900000001"]))

    productos = respuesta.json()["conciliacion"]["productos"]
    assert productos == {"cargados": 2, "enviados": 2, "no_enviados": 0}


def test_los_supervisores_se_concilian_aparte_de_los_productos(cliente) -> None:
    crear(cliente)

    respuesta = importar(cliente, contenido=informe_xlsx(SUPERVISORES))

    conciliacion = respuesta.json()["conciliacion"]
    assert conciliacion["productos"] == {"cargados": 2, "enviados": 0, "no_enviados": 2}
    assert conciliacion["supervision"] == {"cargados": 2, "enviados": 2, "no_enviados": 0}


def test_un_total_que_no_coincide_se_muestra_y_no_rechaza(cliente) -> None:
    crear(cliente)

    respuesta = importar(cliente, contenido=informe_xlsx(PRODUCTOS, total=10))

    assert respuesta.status_code == 201
    informe = respuesta.json()["informe"]
    assert (informe["total_informado"], informe["filas"], informe["coincide_total"]) == (
        10,
        2,
        False,
    )


def test_sin_fila_de_total_ni_de_fecha_el_informe_igual_se_importa(cliente) -> None:
    crear(cliente)

    respuesta = importar(cliente, contenido=informe_xlsx(PRODUCTOS, total=None, fecha=None))

    informe = respuesta.json()["informe"]
    assert (informe["fecha_informada"], informe["total_informado"], informe["coincide_total"]) == (
        None,
        None,
        None,
    )


# --- Reemplazar -------------------------------------------------------------------------------


def test_reemplazar_sin_confirmar_responde_409_y_no_cambia_el_informe(cliente) -> None:
    crear(cliente)
    importar(cliente, nombre="primero.xlsx")

    respuesta = importar(cliente, nombre="segundo.xlsx", contenido=informe_xlsx(["51900000001"]))

    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "informe_ya_importado"
    client, e = cliente
    vigente = client.get(f"{RUTA}/1/conciliacion").json()
    assert vigente["informe"]["archivo_nombre"] == "primero.xlsx"
    assert vigente["informe"]["filas"] == 4
    assert len(e.campanas.reportes) == 1


def test_el_mismo_archivo_sin_confirmar_tambien_pide_confirmacion(cliente) -> None:
    crear(cliente)
    importar(cliente)

    assert importar(cliente, reemplazar=False).status_code == 409


def test_reemplazar_confirmando_deja_un_solo_informe_el_nuevo(cliente) -> None:
    crear(cliente)
    importar(cliente, nombre="primero.xlsx")

    respuesta = importar(
        cliente, nombre="segundo.xlsx", contenido=informe_xlsx(["51900000001"]), reemplazar=True
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["informe"]["archivo_nombre"] == "segundo.xlsx"
    assert respuesta.json()["conciliacion"]["productos"] == {
        "cargados": 2,
        "enviados": 1,
        "no_enviados": 1,
    }
    client, e = cliente
    assert len(e.campanas.reportes) == 1
    assert (
        client.get(f"{RUTA}/1/conciliacion").json()["informe"]["archivo_nombre"] == "segundo.xlsx"
    )


def test_confirmar_el_reemplazo_con_un_informe_invalido_no_borra_el_vigente(cliente) -> None:
    crear(cliente)
    importar(cliente, nombre="primero.xlsx")

    respuesta = importar(cliente, contenido=informe_xlsx([]), reemplazar=True)

    assert respuesta.status_code == 422
    client, _ = cliente
    assert (
        client.get(f"{RUTA}/1/conciliacion").json()["informe"]["archivo_nombre"] == "primero.xlsx"
    )


def test_importar_con_reemplazar_un_informe_que_no_existia_tambien_funciona(cliente) -> None:
    crear(cliente)

    assert importar(cliente, reemplazar=True).status_code == 201


# --- Rechazos ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("contenido", "codigo"),
    [
        (
            informe_xlsx(PRODUCTOS, encabezados=("CAMPAÑA", "TIPO DE ENVIO", "TELEFONO")),
            "informe_sin_encabezados",
        ),
        (informe_xlsx(PRODUCTOS, encabezados=("A", "B", "C")), "informe_sin_encabezados"),
        (informe_xlsx([]), "informe_sin_filas"),
        (b"esto no es una hoja de calculo", "informe_sin_encabezados"),
        (b"", "informe_sin_encabezados"),
    ],
    ids=["falta-numero", "otra-tabla", "sin-filas", "ilegible", "vacio"],
)
def test_un_informe_invalido_responde_422_con_su_codigo_y_no_guarda_nada(
    cliente, contenido, codigo
) -> None:
    crear(cliente)

    respuesta = importar(cliente, contenido=contenido)

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == codigo
    assert isinstance(respuesta.json()["detail"], str)
    _, e = cliente
    assert e.campanas.reportes == {}


def test_el_422_del_informe_dice_que_encabezado_falta(cliente) -> None:
    crear(cliente)

    respuesta = importar(
        cliente,
        contenido=informe_xlsx(PRODUCTOS, encabezados=("CAMPAÑA", "TIPO DE ENVIO", "TELEFONO")),
    )

    assert "NUMERO" in respuesta.json()["detail"]


def test_una_campana_descartada_rechaza_el_informe_hasta_que_se_restaura(cliente) -> None:
    client, e = cliente
    crear(cliente)
    client.post(f"{RUTA}/1/descartar")

    rechazado = importar(cliente)

    assert rechazado.status_code == 409
    assert rechazado.json()["codigo"] == "campana_descartada"
    assert e.campanas.reportes == {}
    client.post(f"{RUTA}/1/restaurar")
    assert importar(cliente).status_code == 201


def test_importar_en_una_campana_que_no_existe_responde_404(cliente) -> None:
    respuesta = importar(cliente, campana_id=99)

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] is None


def test_un_informe_demasiado_grande_responde_413_sin_leerlo(cliente, monkeypatch) -> None:
    crear(cliente)
    monkeypatch.setattr("app.api.whatsmkt_seguimiento.TAMANO_MAXIMO_INFORME", 100)

    respuesta = importar(cliente)

    assert respuesta.status_code == 413
    _, e = cliente
    assert e.campanas.reportes == {}


def test_sin_archivo_responde_el_422_de_validacion(cliente) -> None:
    client, _ = cliente
    crear(cliente)

    respuesta = client.post(f"{RUTA}/1/reportes")

    assert respuesta.status_code == 422
    assert isinstance(respuesta.json()["detail"], list)


# --- La conciliacion --------------------------------------------------------------------------


def test_sin_informe_la_conciliacion_esta_pendiente_y_no_es_un_error(cliente) -> None:
    client, _ = cliente
    crear(cliente)

    respuesta = client.get(f"{RUTA}/1/conciliacion")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "campana_id": 1,
        "pendiente": True,
        "informe": None,
        "conciliacion": None,
    }


def test_la_conciliacion_de_una_campana_que_no_existe_responde_404(cliente) -> None:
    client, _ = cliente

    respuesta = client.get(f"{RUTA}/99/conciliacion")

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] is None


def test_la_conciliacion_se_consulta_igual_que_al_importar(cliente) -> None:
    client, _ = cliente
    crear(cliente)
    importado = importar(cliente, contenido=informe_xlsx([*PRODUCTOS, "51900000777"])).json()

    consultado = client.get(f"{RUTA}/1/conciliacion").json()

    assert consultado == importado


def test_la_conciliacion_de_una_descartada_se_puede_consultar(cliente) -> None:
    client, _ = cliente
    crear(cliente)
    importar(cliente)
    client.post(f"{RUTA}/1/descartar")

    assert client.get(f"{RUTA}/1/conciliacion").json()["pendiente"] is False


def test_cada_campana_concilia_con_su_propio_informe(cliente) -> None:
    client, e = cliente
    e.productos = [producto(1, -3), producto(2, 5)]
    crear(cliente, **POR_SEGMENTO)  # campanas 1 (preventivo) y 2 (tramo 2)
    importar(cliente, campana_id=2, contenido=informe_xlsx(["51900000002"]))

    assert client.get(f"{RUTA}/1/conciliacion").json()["pendiente"] is True
    assert client.get(f"{RUTA}/2/conciliacion").json()["conciliacion"]["productos"]["enviados"] == 1


# --- Descartar y restaurar --------------------------------------------------------------------


def test_descartar_la_saca_de_las_activas_sin_borrar_nada(cliente) -> None:
    client, e = cliente
    crear(cliente)
    importar(cliente)

    respuesta = client.post(f"{RUTA}/1/descartar")

    assert respuesta.status_code == 200
    assert respuesta.json()["descartada_en"] == DESCARTADA_EN.isoformat()
    assert ids(client.get(RUTA)) == []
    assert ids(client.get(RUTA, params={"estado": "descartadas"})) == [1]
    # Nada se borro: el archivo, el informe y el detalle siguen ahi.
    assert client.get(f"{RUTA}/1/archivo").status_code == 200
    assert client.get(f"{RUTA}/1/conciliacion").json()["pendiente"] is False
    assert client.get(f"{RUTA}/1").status_code == 200
    assert len(e.campanas.reportes) == 1


def test_descartar_una_ya_descartada_no_cambia_su_fecha(cliente) -> None:
    client, e = cliente
    crear(cliente)
    client.post(f"{RUTA}/1/descartar")

    e.campanas.ahora = datetime(2026, 12, 1, 8, 0)
    otra_vez = client.post(f"{RUTA}/1/descartar")

    assert otra_vez.status_code == 200
    assert otra_vez.json()["descartada_en"] == DESCARTADA_EN.isoformat()


def test_restaurar_la_devuelve_a_las_activas(cliente) -> None:
    client, _ = cliente
    crear(cliente)
    client.post(f"{RUTA}/1/descartar")

    respuesta = client.post(f"{RUTA}/1/restaurar")

    assert respuesta.status_code == 200
    assert respuesta.json()["descartada_en"] is None
    assert ids(client.get(RUTA)) == [1]
    assert ids(client.get(RUTA, params={"estado": "descartadas"})) == []


def test_restaurar_una_activa_no_cambia_nada(cliente) -> None:
    client, _ = cliente
    crear(cliente)

    respuesta = client.post(f"{RUTA}/1/restaurar")

    assert (respuesta.status_code, respuesta.json()["descartada_en"]) == (200, None)


@pytest.mark.parametrize("accion", ["descartar", "restaurar"])
def test_descartar_o_restaurar_una_campana_que_no_existe_responde_404(cliente, accion) -> None:
    client, _ = cliente

    respuesta = client.post(f"{RUTA}/99/{accion}")

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] is None


# --- Eliminar ---------------------------------------------------------------------------------


def test_una_campana_activa_no_se_elimina(cliente) -> None:
    client, e = cliente
    crear(cliente)

    respuesta = client.delete(f"{RUTA}/1")

    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "campana_no_descartada"
    assert 1 in e.campanas.campanas and 1 in e.campanas.archivos


def test_eliminar_una_descartada_borra_la_campana_su_archivo_sus_filas_y_sus_informes(
    cliente,
) -> None:
    client, e = cliente
    crear(cliente)
    importar(cliente)
    client.post(f"{RUTA}/1/descartar")

    respuesta = client.delete(f"{RUTA}/1")

    assert respuesta.status_code == 204
    assert respuesta.content == b""
    assert client.get(f"{RUTA}/1").status_code == 404
    assert client.get(f"{RUTA}/1/archivo").status_code == 404
    assert client.get(f"{RUTA}/1/conciliacion").status_code == 404
    assert (e.campanas.reportes, e.campanas.filas, e.campanas.archivos) == ({}, {}, {})
    assert ids(client.get(RUTA, params={"estado": "descartadas"})) == []


def test_eliminar_no_toca_los_mensajes_guardados(cliente) -> None:
    client, e = cliente
    crear(cliente)
    client.post(f"{RUTA}/1/descartar")

    client.delete(f"{RUTA}/1")

    assert 10 in e.textos.textos  # la version del mensaje que uso sigue ahi


def test_eliminar_una_campana_que_no_existe_responde_404(cliente) -> None:
    client, _ = cliente

    respuesta = client.delete(f"{RUTA}/99")

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] is None


def lote_con_exclusiones_fuera(cliente) -> None:
    """Lote 1 con las campanas 1 y 2 y dos productos fuera de ambas, y un lote 2 aparte."""
    _, e = cliente
    e.productos = [
        producto(1, -3),
        producto(3, 5),
        producto(6, None),  # sin dias de atraso: no cae en ninguna campana
        producto(7, None),
    ]
    crear(cliente, **POR_SEGMENTO)
    e.productos = [producto(1, 0)]
    crear(cliente)  # lote 2, campana 3


def test_eliminar_una_campana_de_un_lote_con_otras_deja_el_lote_y_sus_exclusiones(cliente) -> None:
    client, e = cliente
    lote_con_exclusiones_fuera(cliente)
    client.post(f"{RUTA}/1/descartar")

    client.delete(f"{RUTA}/1")

    assert 1 in e.campanas.modos
    fuera = client.get(f"{RUTA}/2").json()["exclusiones_fuera_del_lote"]
    assert fuera["total"] == 2


def test_eliminar_la_ultima_campana_del_lote_borra_el_lote_y_sus_exclusiones_de_fuera(
    cliente,
) -> None:
    client, e = cliente
    lote_con_exclusiones_fuera(cliente)
    for campana in (1, 2):
        client.post(f"{RUTA}/{campana}/descartar")
        client.delete(f"{RUTA}/{campana}")

    assert 1 not in e.campanas.modos
    assert [x for x in e.campanas.exclusiones if x[0] == 1] == []
    # El otro lote queda como estaba.
    assert 2 in e.campanas.modos and 3 in e.campanas.campanas
    assert client.get(f"{RUTA}/3").status_code == 200


def test_la_campana_restaurada_ya_no_se_puede_eliminar(cliente) -> None:
    client, _ = cliente
    crear(cliente)
    client.post(f"{RUTA}/1/descartar")
    client.post(f"{RUTA}/1/restaurar")

    assert client.delete(f"{RUTA}/1").status_code == 409


# --- La lista: estado y pendientes ------------------------------------------------------------


def tres_campanas(cliente) -> None:
    client, e = cliente
    for _ in range(3):
        crear(cliente)


def test_la_lista_trae_las_activas_por_defecto_y_si_cada_una_tiene_informe(cliente) -> None:
    client, _ = cliente
    tres_campanas(cliente)
    importar(cliente, campana_id=2)

    filas = {c["id"]: c["con_informe"] for c in client.get(RUTA).json()["campanas"]}

    assert filas == {3: False, 2: True, 1: False}


def test_el_filtro_de_estado_separa_activas_y_descartadas(cliente) -> None:
    client, _ = cliente
    tres_campanas(cliente)
    client.post(f"{RUTA}/2/descartar")

    activas = client.get(RUTA, params={"estado": "activas"})
    descartadas = client.get(RUTA, params={"estado": "descartadas"})

    assert ids(activas) == [3, 1] and activas.json()["total"] == 2
    assert ids(descartadas) == [2] and descartadas.json()["total"] == 1
    assert descartadas.json()["campanas"][0]["descartada_en"] == DESCARTADA_EN.isoformat()


def test_un_estado_que_no_existe_responde_422(cliente) -> None:
    client, _ = cliente

    assert client.get(RUTA, params={"estado": "todas"}).status_code == 422


def test_los_contadores_son_de_todas_las_campanas_y_no_de_la_pagina_ni_del_filtro(cliente) -> None:
    client, _ = cliente
    tres_campanas(cliente)
    importar(cliente, campana_id=1)  # con informe
    client.post(f"{RUTA}/3/descartar")  # descartada sin informe: no es un pendiente

    pagina = client.get(RUTA, params={"limite": 1, "lote_id": 2}).json()

    assert (pagina["total"], len(pagina["campanas"])) == (1, 1)
    assert (pagina["total_activas"], pagina["total_descartadas"]) == (2, 1)
    assert pagina["total_pendientes"] == 1  # solo la 2: activa y sin informe


def test_importar_el_informe_quita_la_campana_de_los_pendientes(cliente) -> None:
    client, _ = cliente
    tres_campanas(cliente)
    assert client.get(RUTA).json()["total_pendientes"] == 3

    importar(cliente, campana_id=2)

    assert client.get(RUTA).json()["total_pendientes"] == 2


def test_el_detalle_dice_si_tiene_informe(cliente) -> None:
    client, _ = cliente
    crear(cliente)
    assert client.get(f"{RUTA}/1").json()["con_informe"] is False

    importar(cliente)

    assert client.get(f"{RUTA}/1").json()["con_informe"] is True


# --- Contrato ---------------------------------------------------------------------------------


def test_el_contrato_declara_los_endpoints_del_seguimiento() -> None:
    esquema = app.openapi()
    paths = esquema["paths"]
    schemas = esquema["components"]["schemas"]

    importar_ = paths[f"{RUTA}/{{campana_id}}/reportes"]["post"]
    assert {"201", "404", "409", "413", "422"} <= set(importar_["responses"])
    assert "multipart/form-data" in importar_["requestBody"]["content"]
    assert "get" in paths[f"{RUTA}/{{campana_id}}/conciliacion"]
    assert "post" in paths[f"{RUTA}/{{campana_id}}/descartar"]
    assert "post" in paths[f"{RUTA}/{{campana_id}}/restaurar"]
    eliminar = paths[f"{RUTA}/{{campana_id}}"]["delete"]["responses"]
    assert {"204", "404", "409"} <= set(eliminar)
    assert {"campana_id", "pendiente", "informe", "conciliacion"} <= set(
        schemas["EstadoInformeWhatsmktRespuesta"]["required"]
    )
    assert {"total_activas", "total_descartadas", "total_pendientes"} <= set(
        schemas["ListaCampanasWhatsmktRespuesta"]["required"]
    )
    assert "con_informe" in schemas["ResumenCampanaWhatsmktRespuesta"]["required"]
