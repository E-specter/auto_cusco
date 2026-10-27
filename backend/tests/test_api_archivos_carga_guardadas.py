"""`/archivos-carga` con una definicion guardada (B4b, RF-51, D4): sobre el repositorio en memoria.

Lo unico simulado es la consulta a la cartera y el repositorio de definiciones. La definicion en
linea (RF-54) no cambia y la cubre `test_api_archivos_carga.py`.
"""

import io
from datetime import date
from decimal import Decimal

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.api.cartera import obtener_servicio_cartera
from app.api.definiciones_columnas import obtener_servicio_definiciones
from app.core.entities.cartera import PaginaCartera, SinVersionVigente
from app.core.services.contextos_texto import contexto_cartera
from app.core.services.definiciones_columnas.servicio import DefinicionesColumnasService
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.main import app
from tests.definiciones_memoria import RepositorioEnMemoria
from tests.test_api_archivos_carga import ConsultaFalsa, _definicion_con_formula, _peticion

FECHA = "2026-09-10"


@pytest.fixture
def cliente():
    consulta = ConsultaFalsa()
    servicio = DefinicionesColumnasService(
        RepositorioEnMemoria(), contexto_cartera(CatalogoCartera())
    )
    app.dependency_overrides[obtener_servicio_cartera] = lambda: consulta
    app.dependency_overrides[obtener_servicio_definiciones] = lambda: servicio
    try:
        yield TestClient(app), consulta, servicio
    finally:
        app.dependency_overrides.clear()


def _texto(valor: str) -> dict:
    return {"tipo": "texto", "valor": valor}


def _variable(nombre: str) -> dict:
    return {"tipo": "variable", "nombre": nombre, "funciones": []}


def _columna(nombre: str, orden: int, *nodos: dict, **extra) -> dict:
    return {"nombre": nombre, "orden": orden, "expresion": {"nodos": list(nodos)}, **extra}


def _guardada(nombre: str = "SMS preventiva", *, proteger: bool = True, extra: str = "") -> dict:
    return {
        "nombre": nombre,
        "proteger_formulas": proteger,
        "columnas": [
            _columna("anexo", 0, _texto("1010"), tipo="numero"),
            _columna("numero", 1, _texto("51"), _variable("telefono")),
            _columna(
                "deuda",
                2,
                _variable("saldo_capital_pendiente"),
                tipo="financiero",
                formato_financiero={
                    "separador_miles": ".",
                    "separador_decimal": ",",
                    "decimales": 2,
                },
            ),
            _columna(
                "vence",
                3,
                _variable("fecha_vencimiento_cuota"),
                tipo="fecha",
                formato_fecha="dd/mm/aaaa",
            ),
            _columna("nota", 4, _texto(extra or "=1+1")),
        ],
    }


def _pedido(id_: int, version: int | None = None, **extra) -> dict:
    guardada = {"id": id_} if version is None else {"id": id_, "version": version}
    # La fecha de envio va fija: sin ella seria hoy y los dias ajustados cambiarian cada dia.
    cuerpo = {
        "fecha_corte": FECHA,
        "fecha_envio": FECHA,
        "definicion_guardada": guardada,
        "cantidad": 2,
        **extra,
    }
    return cuerpo


# --- La definicion guardada genera lo mismo que la equivalente en linea ---------------------------


def test_la_previsualizacion_con_una_guardada_da_las_mismas_filas_que_la_en_linea(cliente) -> None:
    client, _, servicio = cliente
    id_ = servicio.crear(_guardada()).definicion.id

    guardada = client.post("/archivos-carga/previsualizacion", json=_pedido(id_)).json()
    en_linea = client.post(
        "/archivos-carga/previsualizacion",
        json=_peticion(definicion=_definicion_con_formula()),
    ).json()

    assert guardada["cabeceras"] == ["anexo", "numero", "deuda", "vence", "nota"]
    assert guardada["filas"] == en_linea["filas"]
    assert guardada["nombre_archivo"] == "SMS_preventiva.xlsx"
    assert (guardada["disponibles"], guardada["generados"], guardada["completa"]) == (2, 2, True)


def test_con_una_guardada_se_usa_la_version_pedida_o_la_vigente(cliente) -> None:
    client, _, servicio = cliente
    id_ = servicio.crear(_guardada(extra="uno")).definicion.id
    servicio.agregar_version(id_, _guardada(extra="dos"))

    vigente = client.post("/archivos-carga/previsualizacion", json=_pedido(id_)).json()
    primera = client.post("/archivos-carga/previsualizacion", json=_pedido(id_, 1)).json()
    segunda = client.post("/archivos-carga/previsualizacion", json=_pedido(id_, 2)).json()

    assert vigente["filas"][0]["nota"] == "dos"
    assert primera["filas"][0]["nota"] == "uno"
    assert segunda["filas"] == vigente["filas"]


def test_la_seleccion_y_el_formato_siguen_en_la_peticion(cliente) -> None:
    client, consulta, servicio = cliente
    id_ = servicio.crear(_guardada()).definicion.id

    respuesta = client.post(
        "/archivos-carga",
        json=_pedido(
            id_, filtros=["telefono:no_vacio"], orden="-saldo_capital_pendiente", formato="csv"
        ),
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/csv")
    assert consulta.recibido["filtros"][0].campo == "telefono"
    assert consulta.recibido["orden"].descendente


def test_una_guardada_renombrada_genera_el_archivo_con_el_nombre_nuevo(cliente) -> None:
    client, _, servicio = cliente
    id_ = servicio.crear(_guardada()).definicion.id
    servicio.renombrar(id_, "Cobranza de octubre")

    previa = client.post("/archivos-carga/previsualizacion", json=_pedido(id_)).json()
    descarga = client.post("/archivos-carga", json=_pedido(id_))

    assert previa["nombre_archivo"] == "Cobranza_de_octubre.xlsx"
    assert "Cobranza_de_octubre.xlsx" in descarga.headers["content-disposition"]


# --- usada_en -------------------------------------------------------------------------------------


def test_generar_el_archivo_marca_la_version_usada_y_solo_esa(cliente) -> None:
    client, _, servicio = cliente
    id_ = servicio.crear(_guardada()).definicion.id
    servicio.agregar_version(id_, _guardada())

    respuesta = client.post("/archivos-carga", json=_pedido(id_, 1, formato="csv"))

    assert respuesta.status_code == 200
    assert servicio.obtener(id_, 1).version.usada is True
    assert servicio.obtener(id_, 2).version.usada is False


def test_sin_version_se_marca_la_vigente(cliente) -> None:
    client, _, servicio = cliente
    id_ = servicio.crear(_guardada()).definicion.id
    servicio.agregar_version(id_, _guardada())

    client.post("/archivos-carga", json=_pedido(id_, formato="csv"))

    assert [servicio.obtener(id_, n).version.usada for n in (1, 2)] == [False, True]


def test_la_previsualizacion_no_marca_la_version_usada(cliente) -> None:
    client, _, servicio = cliente
    id_ = servicio.crear(_guardada()).definicion.id

    client.post("/archivos-carga/previsualizacion", json=_pedido(id_))

    assert servicio.obtener(id_).version.usada is False


def test_si_la_generacion_falla_la_version_no_queda_usada(cliente) -> None:
    client, consulta, servicio = cliente
    id_ = servicio.crear(_guardada()).definicion.id
    consulta.error = SinVersionVigente(date(2026, 9, 10))

    respuesta = client.post("/archivos-carga", json=_pedido(id_, formato="csv"))

    assert respuesta.status_code == 404
    assert servicio.obtener(id_).version.usada is False


def test_la_definicion_en_linea_no_toca_las_definiciones_guardadas(cliente) -> None:
    client, _, servicio = cliente
    servicio.crear(_guardada())

    client.post("/archivos-carga", json=_peticion(formato="csv"))

    assert servicio.listar()[0].vigente_usada is False


# --- proteger_formulas (D4) ----------------------------------------------------------------------


def _nota_del_csv(respuesta) -> list[str]:
    filas = respuesta.content.decode("utf-8").splitlines()
    return [fila.rsplit(",", 1)[1] for fila in filas[1:]]


def test_proteger_formulas_de_la_definicion_rige_el_csv(cliente) -> None:
    client, _, servicio = cliente
    protegida = servicio.crear(_guardada("protegida", proteger=True)).definicion.id
    libre = servicio.crear(_guardada("libre", proteger=False)).definicion.id

    con = client.post("/archivos-carga", json=_pedido(protegida, formato="csv"))
    sin = client.post("/archivos-carga", json=_pedido(libre, formato="csv"))

    assert _nota_del_csv(con) == ["'=1+1", "'=1+1"]
    assert _nota_del_csv(sin) == ["=1+1", "=1+1"]


def test_la_definicion_en_linea_sigue_protegiendo_por_defecto(cliente) -> None:
    client, _, _ = cliente

    respuesta = client.post(
        "/archivos-carga", json=_peticion(formato="csv", definicion=_definicion_con_formula())
    )

    assert _nota_del_csv(respuesta) == ["'=1+1", "'=1+1"]


# --- Errores --------------------------------------------------------------------------------------


@pytest.mark.parametrize("ruta", ["/archivos-carga", "/archivos-carga/previsualizacion"])
def test_exactamente_una_definicion_y_si_no_es_400_con_codigo(cliente, ruta) -> None:
    client, consulta, servicio = cliente
    id_ = servicio.crear(_guardada()).definicion.id

    con_las_dos = client.post(ruta, json={**_peticion(), **_pedido(id_)})
    con_ninguna = client.post(ruta, json={"fecha_corte": FECHA, "cantidad": 2})

    for respuesta in (con_las_dos, con_ninguna):
        assert respuesta.status_code == 400
        assert respuesta.json()["codigo"] == "definicion_invalida"
        assert respuesta.json()["detail"]
    assert consulta.recibido == {}


def test_una_definicion_guardada_inexistente_es_404_con_su_codigo(cliente) -> None:
    client, consulta, _ = cliente

    respuesta = client.post("/archivos-carga/previsualizacion", json=_pedido(999))

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "definicion_no_encontrada"
    assert consulta.recibido == {}


def test_una_version_inexistente_es_404_con_su_codigo(cliente) -> None:
    client, _, servicio = cliente
    id_ = servicio.crear(_guardada()).definicion.id

    respuesta = client.post("/archivos-carga", json=_pedido(id_, 7))

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "version_no_encontrada"


def test_los_errores_de_siempre_traen_codigo_nulo_y_el_mismo_detalle(cliente) -> None:
    client, _, _ = cliente
    definicion = {"nombre": "mala", "campos": [{"nombre": "x", "plantilla": "[@no_existe]"}]}

    respuesta = client.post("/archivos-carga", json=_peticion(definicion=definicion))

    assert respuesta.status_code == 400
    assert "no_existe" in respuesta.json()["detail"]
    assert respuesta.json()["codigo"] is None


def test_una_fecha_sin_version_vigente_trae_su_codigo(cliente) -> None:
    client, consulta, _ = cliente
    consulta.error = SinVersionVigente(date(2026, 9, 10))

    respuesta = client.post("/archivos-carga", json=_peticion())

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "sin_version_vigente"


def test_una_guardada_con_un_campo_que_ya_no_existe_es_400_sin_marcar_nada(cliente) -> None:
    """Si el catalogo de la cartera cambia, la generacion lo rechaza como antes."""
    client, _, servicio = cliente
    id_ = servicio.crear(_guardada()).definicion.id
    # Simula el cambio de catalogo: lo guardado nombra un campo que el catalogo ya no tiene.
    servicio._repositorio.reemplazar_contenido(  # noqa: SLF001
        id_, 1, {"columnas": [_columna("x", 0, _variable("campo_que_ya_no_existe"))]}
    )

    respuesta = client.post("/archivos-carga", json=_pedido(id_, formato="csv"))

    assert respuesta.status_code == 400
    assert servicio.obtener(id_).version.usada is False


# --- Los productos que no caen en ningun segmento se excluyen y se explican (B12, RF-50) ----------


class CarteraConDias:
    catalogo = CatalogoCartera()  # lo piden quienes parsean filtros o arman columnas

    """Productos con `dias_atraso`: el segmento sale de ahi (la tabla por defecto llega a 120)."""

    def __init__(self, dias: list) -> None:
        self.dias = dias

    def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento):
        filas = tuple(
            {
                "pagare": f"{i:018d}",
                "telefono": f"9{i:08d}",
                "saldo_capital_pendiente": Decimal("100"),
                "fecha_vencimiento_cuota": date(2026, 9, 18),
                "dias_atraso": dias,
            }
            for i, dias in enumerate(self.dias, start=1)
        )
        return PaginaCartera(
            total=len(filas),
            filas=filas[desplazamiento : desplazamiento + limite],
            limite=limite,
            desplazamiento=desplazamiento,
        )


@pytest.fixture
def segmentada():
    """Una definicion con segmentacion (excluir lo que no cae en un rango) y su cartera."""
    servicio = DefinicionesColumnasService(
        RepositorioEnMemoria(), contexto_cartera(CatalogoCartera())
    )
    cartera = CarteraConDias([5, 200, None, 40])  # el 2 y el 3 no caen en ningun segmento
    app.dependency_overrides[obtener_servicio_cartera] = lambda: cartera
    app.dependency_overrides[obtener_servicio_definiciones] = lambda: servicio
    try:
        id_ = servicio.crear({**_guardada(), "segmentacion": {}}).definicion.id
        yield TestClient(app), cartera, id_
    finally:
        app.dependency_overrides.clear()


def test_la_previsualizacion_lista_los_excluidos_con_fila_pagare_codigo_y_detalle(
    segmentada,
) -> None:
    client, _, id_ = segmentada

    cuerpo = client.post(
        "/archivos-carga/previsualizacion", json=_pedido(id_, cantidad=4, fecha_envio=FECHA)
    ).json()

    assert (cuerpo["generados"], cuerpo["excluidos"]) == (2, 2)
    assert [(e["fila"], e["pagare"], e["codigo"]) for e in cuerpo["exclusiones"]] == [
        (2, f"{2:018d}", "sin_segmento"),
        (3, f"{3:018d}", "sin_segmento"),
    ]
    assert "200" in cuerpo["exclusiones"][0]["detalle"]  # los dias que no caen en un rango
    assert "no tiene dias" in cuerpo["exclusiones"][1]["detalle"]
    # Sin datos personales nuevos: el producto se identifica por el pagare y nada mas.
    assert set(cuerpo["exclusiones"][0]) == {"fila", "pagare", "codigo", "detalle"}


def test_los_numeros_de_la_previsualizacion_cierran(segmentada) -> None:
    client, _, id_ = segmentada

    cuerpo = client.post("/archivos-carga/previsualizacion", json=_pedido(id_, cantidad=4)).json()

    # Se evaluan min(disponibles, muestra) productos y cada uno sale o se excluye.
    assert cuerpo["generados"] + cuerpo["excluidos"] == min(cuerpo["disponibles"], 4) == 4
    assert len(cuerpo["filas"]) == cuerpo["generados"]
    # `suficiente` habla de la seleccion, no de la tabla: hay 4 productos para los 4 pedidos y
    # aun asi salen 2 filas.
    assert (cuerpo["suficiente"], cuerpo["solicitados"], cuerpo["generados"]) == (True, 4, 2)


def test_si_faltan_productos_y_ademas_hay_excluidos_los_numeros_siguen_cerrando(segmentada) -> None:
    client, _, id_ = segmentada

    cuerpo = client.post("/archivos-carga/previsualizacion", json=_pedido(id_, cantidad=10)).json()

    assert (cuerpo["disponibles"], cuerpo["solicitados"], cuerpo["suficiente"]) == (4, 10, False)
    assert cuerpo["generados"] + cuerpo["excluidos"] == min(4, 10)


def test_la_descarga_resume_los_excluidos_en_la_cabecera(segmentada) -> None:
    client, _, id_ = segmentada

    respuesta = client.post("/archivos-carga", json=_pedido(id_, cantidad=4))

    cabeceras = respuesta.headers
    assert respuesta.status_code == 200
    assert (cabeceras["x-carga-generados"], cabeceras["x-carga-excluidos"]) == ("2", "2")
    assert int(cabeceras["x-carga-generados"]) + int(cabeceras["x-carga-excluidos"]) == min(
        int(cabeceras["x-carga-disponibles"]), int(cabeceras["x-carga-solicitados"])
    )
    filas = list(openpyxl.load_workbook(io.BytesIO(respuesta.content)).active.iter_rows())
    assert len(filas) == 1 + 2  # la cabecera y los 2 generados


def test_la_muestra_de_la_previsualizacion_no_es_la_carga_entera(segmentada) -> None:
    client, cartera, id_ = segmentada
    cartera.dias = [None] * 25  # ninguno cae en un segmento

    previa = client.post("/archivos-carga/previsualizacion", json=_pedido(id_, cantidad=100)).json()
    descarga = client.post("/archivos-carga", json=_pedido(id_, cantidad=100))

    # La previsualizacion evalua solo la muestra (20); la descarga, todos los disponibles.
    assert (previa["disponibles"], previa["generados"], previa["excluidos"]) == (25, 0, 20)
    assert len(previa["exclusiones"]) == 20
    assert descarga.headers["x-carga-excluidos"] == "25"
    assert descarga.headers["x-carga-generados"] == "0"
