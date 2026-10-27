"""La API del mapeador de encabezados sin base de datos (T-MAP-B3b, RF-57 a RF-62).

Un mismo repositorio en memoria sirve al servicio de borradores y a la ingesta, y el lector real lee
los archivos; se sustituyen las dependencias de FastAPI. Cada codigo de estado tiene su prueba.
Archivos y valores sinteticos.
"""

import re

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.adapters.input.lector_csv import CANDIDATOS_DE_SEPARADOR, CODIFICACIONES
from app.api import mapeador as api_mapeador
from app.api.cargas import obtener_servicio
from app.api.mapeador import obtener_servicio_mapeador
from app.core.entities.lectura_tabla import OpcionesLectura
from app.core.services.borradores_carga.servicio import MapeadorService
from app.core.services.ingesta_sabana.catalogo import CATALOGO_SABANA
from app.core.services.ingesta_sabana.mapeable import CATALOGO_SABANA_MAPEABLE
from app.core.services.ingesta_sabana.servicio import IngestaSabanaService
from app.core.services.mapeador.similitud import alias_legibles
from app.main import app, configurar_cors
from tests.test_ingesta_mapeo_explicito import Espia, xlsx
from tests.test_ingesta_servicio import RepositorioEnMemoria
from tests.test_mapeador_ciclo import CSV_SABANA, Reloj, csv_de

FECHA = "2026-09-10"
NOMBRES = ["pagare", "titular", "telefono", "region", None]


class Entorno:
    def __init__(self) -> None:
        self.reloj = Reloj()
        self.repo = RepositorioEnMemoria()
        self.lector = Espia()
        self.mapeador = MapeadorService(
            self.repo, self.lector, [CATALOGO_SABANA_MAPEABLE], self.reloj
        )
        self.ingesta = IngestaSabanaService(self.repo, self.lector, self.reloj)
        self.cliente = TestClient(app)

    def subir(self, *, contenido: bytes = CSV_SABANA, nombre: str = "datos.csv", **formulario):
        return self.cliente.post(
            "/mapeador/sabana_vencida/borradores",
            files={"archivo": (nombre, contenido)},
            data=formulario,
        )

    def asignaciones(self, analisis: dict, **cambios) -> list[dict]:
        """Lo que manda la pantalla sin tocar nada, con los parecidos aceptados."""
        origenes = {
            "recordado": "recordado",
            "coincide": "coincide",
            "parecido": "parecido_aceptado",
            "sin_coincidencia": "manual",
        }
        return [
            {
                "indice": c["indice"],
                "campo": cambios.get(c["indice"], c["sugerido"]),
                "origen": origenes[c["estado"]],
            }
            for c in analisis["columnas"]
        ]

    def confirmar(self, borrador_id: int, asignaciones: list[dict], *, fecha: str = FECHA):
        return self.cliente.post(
            "/cargas/desde-borrador",
            json={"borrador_id": borrador_id, "fecha_corte": fecha, "asignaciones": asignaciones},
        )


@pytest.fixture
def api():
    entorno = Entorno()
    app.dependency_overrides[obtener_servicio_mapeador] = lambda: entorno.mapeador
    app.dependency_overrides[obtener_servicio] = lambda: entorno.ingesta
    try:
        yield entorno
    finally:
        app.dependency_overrides.clear()


# --- GET /mapeador/catalogos/{id} ---------------------------------------------------------------


def test_el_catalogo_trae_los_campos_y_las_codificaciones(api) -> None:
    respuesta = api.cliente.get("/mapeador/catalogos/sabana_vencida")

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200 and cuerpo["id"] == "sabana_vencida"
    pagare = next(c for c in cuerpo["campos"] if c["nombre"] == "pagare")
    assert pagare == {
        "nombre": "pagare",
        "clave_etiqueta": "campo.pagare",
        "tipo": "clave",
        "obligatorio": True,
        "alias": ["pagare"],
        "etiqueta": None,
        "adicional": False,
    }
    assert [c["nombre"] for c in cuerpo["campos"] if c["obligatorio"]] == ["pagare"]
    assert cuerpo["codificaciones"] == ["utf-8-sig", "utf-8", "windows-1252", "latin-1"]
    assert cuerpo["codificaciones"] == list(CODIFICACIONES)
    assert cuerpo["separadores"] == [";", "\t", ","] == list(CANDIDATOS_DE_SEPARADOR)


def test_el_catalogo_trae_los_alias_literales_en_forma_legible(api) -> None:
    campos = {
        c["nombre"]: c
        for c in api.cliente.get("/mapeador/catalogos/sabana_vencida").json()["campos"]
    }

    assert campos["dias_atraso"]["alias"] == ["dias atraso hoy"]
    assert campos["tipo_reprogramacion"]["alias"] == ["tipo de reprogramacion"]
    assert campos["saldo_soles_corte"]["alias"] == []  # su unico alias es una expresion regular
    # ninguno es una expresion regular, ni lleva guion bajo, y todos salen de la misma funcion
    for nombre, c in campos.items():
        assert all(re.search(r"[\.^$*+?{}\[\]|()_]", a) is None for a in c["alias"]), nombre
        catalogo = {x.nombre: x for x in CATALOGO_SABANA.campos}[nombre]
        assert c["alias"] == list(alias_legibles(catalogo)), nombre


def test_un_catalogo_que_no_existe_es_404(api) -> None:
    respuesta = api.cliente.get("/mapeador/catalogos/otro")

    assert respuesta.status_code == 404 and "otro" in respuesta.json()["detail"]
    assert respuesta.json() == {
        "detail": "No existe el catálogo de campos 'otro'",
        "codigo": "catalogo_desconocido",
    }


# --- POST /mapeador/{catalogo_id}/borradores ----------------------------------------------------


def test_subir_un_archivo_crea_el_borrador_y_devuelve_el_analisis(api) -> None:
    respuesta = api.subir()

    cuerpo = respuesta.json()
    assert respuesta.status_code == 201
    assert set(cuerpo) == {
        "borrador_id",
        "catalogo_id",
        "formato",
        "hojas",
        "hoja",
        "separador",
        "codificacion",
        "filas",
        "columnas",
        "problemas",
        "advertencias",
        "detectados",
    }
    assert (cuerpo["formato"], cuerpo["separador"], cuerpo["codificacion"]) == (
        "csv",
        ";",
        "windows-1252",
    )
    assert (cuerpo["hojas"], cuerpo["hoja"], cuerpo["filas"]) == ([], None, 2)
    assert cuerpo["catalogo_id"] == "sabana_vencida"
    assert cuerpo["problemas"] == [] and cuerpo["advertencias"] == []
    assert [c["indice"] for c in cuerpo["columnas"]] == [0, 1, 2, 3, 4]  # base 0
    assert [c["sugerido"] for c in cuerpo["columnas"]] == NOMBRES
    primera = cuerpo["columnas"][0]
    assert primera == {
        "indice": 0,
        "encabezado": "Pagare",
        "ejemplos": ["000000000000000001", "000000000000000002"],
        "estado": "coincide",
        "sugerido": "pagare",
        "similitud": None,
    }
    assert cuerpo["columnas"][4]["estado"] == "sin_coincidencia"
    assert len(api.repo.borradores) == 1


def test_un_parecido_llega_con_su_similitud_y_el_problema_de_revisarlo(api) -> None:
    contenido = csv_de([["Pagare", "Telefon"], ["000000000000000001", "900000001"]])

    cuerpo = api.subir(contenido=contenido).json()

    parecido = cuerpo["columnas"][1]
    assert (parecido["estado"], parecido["sugerido"]) == ("parecido", "telefono")
    assert 0.75 <= parecido["similitud"] <= 1.0
    assert [(p["indice"], p["codigo"], p["campo"]) for p in cuerpo["problemas"]] == [
        (1, "parecido_sin_revisar", "telefono")
    ]


def test_lo_elegido_en_el_formulario_gana_a_lo_detectado(api) -> None:
    contenido = csv_de([["Pagare", "Titular"], ["000000000000000001", "UNO"]], separador=",")

    cuerpo = api.subir(contenido=contenido, separador=";", codificacion="latin-1").json()

    assert (cuerpo["separador"], cuerpo["codificacion"]) == (";", "latin-1")
    assert [c["encabezado"] for c in cuerpo["columnas"]] == ["Pagare,Titular"]


def test_los_campos_en_blanco_del_formulario_se_detectan(api) -> None:
    cuerpo = api.subir(hoja="", separador="", codificacion="").json()

    assert (cuerpo["separador"], cuerpo["codificacion"]) == (";", "windows-1252")
    # lo que le llega al lector es «no elegido», no un texto vacio
    assert api.lector.pedidos[-1][1] == OpcionesLectura()


def test_detectados_son_las_opciones_que_el_usuario_no_eligio(api) -> None:
    sin_elegir = api.subir().json()
    separador = api.subir(separador=";").json()
    codificacion = api.subir(codificacion="windows-1252").json()
    ambas = api.subir(separador=";", codificacion="windows-1252").json()

    assert sin_elegir["detectados"] == ["separador", "codificacion"]
    assert separador["detectados"] == ["codificacion"]
    assert codificacion["detectados"] == ["separador"]
    assert ambas["detectados"] == []


def test_detectados_incluye_la_hoja_de_un_excel_solo_si_no_se_eligio(api) -> None:
    contenido = xlsx([["Pagare", "Titular"], ["1", "UNO"]], hoja="Septiembre")

    detectada = api.subir(contenido=contenido, nombre="sabana.xlsx").json()
    elegida = api.subir(contenido=contenido, nombre="sabana.xlsx", hoja="Septiembre").json()

    assert detectada["detectados"] == ["hoja"] and elegida["detectados"] == []


def test_un_json_no_detecta_ninguna_opcion(api) -> None:
    cuerpo = api.subir(contenido=b'[{"Pagare": "1"}]', nombre="datos.json").json()

    assert cuerpo["detectados"] == []


def test_volver_a_analizar_recalcula_los_detectados_con_lo_que_se_eligio(api) -> None:
    creado = api.subir(separador=";").json()
    assert creado["detectados"] == ["codificacion"]

    eligiendo = api.cliente.post(
        f"/mapeador/borradores/{creado['borrador_id']}/analisis",
        json={"separador": ",", "codificacion": "latin-1"},
    ).json()
    sin_elegir = api.cliente.post(
        f"/mapeador/borradores/{creado['borrador_id']}/analisis", json={}
    ).json()

    assert eligiendo["detectados"] == []
    assert sin_elegir["detectados"] == ["separador", "codificacion"]


def test_un_excel_lista_sus_hojas_y_lee_la_elegida(api) -> None:
    contenido = xlsx([["Pagare", "Titular"], ["000000000000000001", "UNO"]], hoja="Septiembre")

    cuerpo = api.subir(contenido=contenido, nombre="sabana.xlsx").json()
    otra = api.subir(contenido=contenido, nombre="sabana.xlsx", hoja="Septiembre").json()

    assert cuerpo["formato"] == "xlsx" and cuerpo["hojas"] == ["Septiembre"]
    assert cuerpo["hoja"] == otra["hoja"] == "Septiembre"
    assert (cuerpo["separador"], cuerpo["codificacion"]) == (None, None)


def test_un_json_avisa_del_valor_no_escalar(api) -> None:
    contenido = b'[{"Pagare": "000000000000000001", "Detalle": {"a": 1}}]'

    cuerpo = api.subir(contenido=contenido, nombre="datos.json").json()

    assert cuerpo["formato"] == "json"
    assert cuerpo["advertencias"] == [
        {"numero_fila": 2, "columna": "Detalle", "codigo": "valor_no_escalar"}
    ]


def test_un_archivo_vacio_es_400_con_su_codigo(api) -> None:
    respuesta = api.subir(contenido=b"")

    assert respuesta.status_code == 400
    assert respuesta.json() == {"detail": "El archivo está vacío", "codigo": "archivo_vacio"}
    assert api.repo.borradores == {}


@pytest.mark.parametrize(
    ("contenido", "nombre", "codigo", "fragmento"),
    [
        (b"  \n ", "datos", "archivo_vacio", "vacío"),
        (b"esto no es una hoja", "datos.xlsx", "extension_no_coincide", "no coincide"),
        (xlsx([["Pagare"], ["1"]]), "datos.csv", "extension_no_coincide", "es una hoja"),
        (b"\n\n,,\n", "datos.csv", "archivo_sin_datos", "no tiene cabecera"),
        (b'{"a": 1}', "datos.json", "archivo_ilegible", "lista de objetos"),
        (b'[{"a": 1,}]', "datos.json", "archivo_ilegible", "no es válido"),
    ],
)
def test_un_archivo_que_no_se_lee_es_400_con_su_codigo_y_sin_datos_de_mas(
    api, contenido, nombre, codigo, fragmento
) -> None:
    respuesta = api.subir(contenido=contenido, nombre=nombre)

    cuerpo = respuesta.json()
    assert respuesta.status_code == 400 and cuerpo["codigo"] == codigo
    assert set(cuerpo) == {"detail", "codigo"} and fragmento in cuerpo["detail"]
    assert api.repo.borradores == {}


def test_un_json_con_una_mitad_suelta_de_un_par_sustituto_es_400_y_no_500(api) -> None:
    # T-API-B1: el escape de la mitad alta, escrito en el archivo (no en la peticion)
    escape = "".join(["\\", "ud800"])
    contenido = ('[{"Pagare": "1", "Nombre": "a' + escape + 'b"}]').encode("ascii")

    respuesta = api.subir(contenido=contenido, nombre="datos.json")

    assert respuesta.status_code == 400
    assert (
        respuesta.json()["codigo"] == "archivo_ilegible" and "U+D800" in respuesta.json()["detail"]
    )
    assert api.repo.borradores == {}


@pytest.mark.parametrize(
    ("contenido", "nombre"),
    [
        ('"xALTA"', "datos.json"),  # la raiz es un texto con una mitad suelta
        ('{"a": "ALTA"}', "datos.json"),  # un objeto con una mitad suelta en un valor
        ('{"aBAJA": 1}', "datos.json"),  # y en una clave
        ('{"a": "ALTA"}', "datos"),  # sin extension: se reconoce por el contenido
        ("5", "datos.json"),
        ("null", "datos.json"),
    ],
)
def test_un_json_cuya_raiz_no_es_una_lista_es_400_y_nunca_500(api, contenido, nombre) -> None:
    barra = chr(92)  # los escapes se arman aqui: no se escriben en el codigo
    contenido = contenido.replace("ALTA", barra + "ud800").replace("BAJA", barra + "udc00")
    contenido = contenido.encode("ascii")

    respuesta = api.subir(contenido=contenido, nombre=nombre)

    assert respuesta.status_code == 400, respuesta.text
    assert respuesta.json()["codigo"] in ("archivo_ilegible", "extension_no_coincide")
    assert api.repo.borradores == {}


def test_una_hoja_que_no_existe_es_400_con_la_lista_como_dato(api) -> None:
    contenido = xlsx([["Pagare"], ["1"]], hoja="Septiembre")

    respuesta = api.subir(contenido=contenido, nombre="sabana.xlsx", hoja="Octubre")

    cuerpo = respuesta.json()
    assert respuesta.status_code == 400
    assert cuerpo["codigo"] == "hoja_inexistente"
    assert (cuerpo["hoja"], cuerpo["hojas"]) == ("Octubre", ["Septiembre"])
    assert "Octubre" in cuerpo["detail"] and "Septiembre" in cuerpo["detail"]


def test_una_codificacion_o_un_separador_invalidos_son_400_con_su_codigo(api) -> None:
    desconocida = api.subir(codificacion="klingon")
    no_decodifica = api.subir(contenido="Región\n".encode("latin-1"), codificacion="utf-8")
    separador = api.subir(separador="ab")

    assert [r.status_code for r in (desconocida, no_decodifica, separador)] == [400] * 3
    assert desconocida.json()["codigo"] == "codificacion_invalida"
    assert no_decodifica.json()["codigo"] == "codificacion_no_coincide"
    assert separador.json()["codigo"] == "separador_invalido"
    assert "klingon" in desconocida.json()["detail"] and "carácter" in separador.json()["detail"]
    for respuesta in (desconocida, no_decodifica, separador):
        assert set(respuesta.json()) == {"detail", "codigo"}


def test_un_archivo_mas_grande_que_el_maximo_es_413_con_el_maximo_en_mb(api, monkeypatch) -> None:
    monkeypatch.setattr(api_mapeador, "TAMANO_MAXIMO_BYTES", 2 * 1024 * 1024)

    respuesta = api.subir(contenido=b"a;b\n" + b"x" * (2 * 1024 * 1024))

    assert respuesta.status_code == 413
    assert respuesta.json() == {
        "detail": "El archivo supera el máximo de 2 MB",
        "codigo": "archivo_demasiado_grande",
        "maximo_mb": 2,
    }
    assert api.repo.borradores == {}


def test_el_limite_de_tamano_es_inclusivo(api, monkeypatch) -> None:
    monkeypatch.setattr(api_mapeador, "TAMANO_MAXIMO_BYTES", len(CSV_SABANA))
    justo = api.subir()
    monkeypatch.setattr(api_mapeador, "TAMANO_MAXIMO_BYTES", len(CSV_SABANA) - 1)
    pasado = api.subir()

    assert (justo.status_code, pasado.status_code) == (201, 413)


def test_un_catalogo_que_no_existe_al_subir_es_404(api) -> None:
    respuesta = api.cliente.post(
        "/mapeador/otro/borradores", files={"archivo": ("datos.csv", CSV_SABANA)}
    )

    assert respuesta.status_code == 404 and api.repo.borradores == {}
    assert respuesta.json()["codigo"] == "catalogo_desconocido"


def test_subir_sin_archivo_es_422(api) -> None:
    assert api.cliente.post("/mapeador/sabana_vencida/borradores").status_code == 422


# --- POST /mapeador/borradores/{id}/analisis ----------------------------------------------------


def test_volver_a_analizar_no_vuelve_a_subir_el_archivo(api) -> None:
    contenido = csv_de([["Pagare", "Titular"], ["000000000000000001", "UNO"]], separador=";")
    creado = api.subir(contenido=contenido).json()
    pedidos_antes = len(api.lector.pedidos)

    respuesta = api.cliente.post(
        f"/mapeador/borradores/{creado['borrador_id']}/analisis", json={"separador": ","}
    )

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200 and cuerpo["borrador_id"] == creado["borrador_id"]
    assert [c["encabezado"] for c in cuerpo["columnas"]] == ["Pagare;Titular"]
    assert cuerpo["separador"] == ","
    assert len(api.repo.borradores) == 1  # el mismo borrador: no hay otro archivo
    nombre, opciones = api.lector.pedidos[-1]
    assert len(api.lector.pedidos) == pedidos_antes + 1 and nombre == "datos.csv"
    assert opciones.separador == "," and opciones.hoja is None
    assert api.repo.contenidos_de_borradores[creado["borrador_id"]] == contenido


def test_volver_a_analizar_con_una_hoja_que_no_existe_trae_las_que_hay(api) -> None:
    creado = api.subir(
        contenido=xlsx([["Pagare"], ["1"]], hoja="Septiembre"), nombre="sabana.xlsx"
    ).json()

    respuesta = api.cliente.post(
        f"/mapeador/borradores/{creado['borrador_id']}/analisis", json={"hoja": "Octubre"}
    )

    assert respuesta.status_code == 400
    assert (respuesta.json()["codigo"], respuesta.json()["hojas"]) == (
        "hoja_inexistente",
        ["Septiembre"],
    )


def test_volver_a_analizar_con_campos_en_blanco_detecta_de_nuevo(api) -> None:
    creado = api.subir(separador=",").json()

    cuerpo = api.cliente.post(
        f"/mapeador/borradores/{creado['borrador_id']}/analisis",
        json={"hoja": "", "separador": "", "codificacion": ""},
    ).json()

    assert (cuerpo["separador"], cuerpo["codificacion"]) == (";", "windows-1252")
    assert api.lector.pedidos[-1][1] == OpcionesLectura()


def test_volver_a_analizar_sin_opciones_detecta_de_nuevo(api) -> None:
    creado = api.subir(separador=",").json()
    assert creado["separador"] == ","

    cuerpo = api.cliente.post(
        f"/mapeador/borradores/{creado['borrador_id']}/analisis", json={}
    ).json()

    assert cuerpo["separador"] == ";"


def test_volver_a_analizar_un_borrador_que_no_existe_o_vencio_es_404(api) -> None:
    inexistente = api.cliente.post("/mapeador/borradores/999/analisis", json={})
    assert inexistente.status_code == 404
    assert inexistente.json() == {
        "detail": "No existe el borrador 999",
        "codigo": "borrador_no_encontrado",
    }
    creado = api.subir().json()
    api.reloj.avanzar(hours=24)

    respuesta = api.cliente.post(f"/mapeador/borradores/{creado['borrador_id']}/analisis", json={})

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "borrador_no_encontrado"


def test_volver_a_analizar_con_opciones_que_no_sirven_es_400(api) -> None:
    creado = api.subir().json()

    respuesta = api.cliente.post(
        f"/mapeador/borradores/{creado['borrador_id']}/analisis", json={"codificacion": "klingon"}
    )

    assert respuesta.status_code == 400


# --- POST /mapeador/borradores/{id}/validacion --------------------------------------------------


def test_validar_unas_asignaciones_sin_problemas(api) -> None:
    creado = api.subir().json()

    respuesta = api.cliente.post(
        f"/mapeador/borradores/{creado['borrador_id']}/validacion",
        json={"asignaciones": api.asignaciones(creado)},
    )

    assert respuesta.status_code == 200 and respuesta.json() == {"problemas": []}


def test_validar_informa_cada_problema_con_su_codigo(api) -> None:
    creado = api.subir().json()
    asignaciones = api.asignaciones(creado)
    asignaciones[0]["campo"] = None  # sin pagare
    asignaciones[4]["campo"] = "titular"  # y titular repetido

    problemas = api.cliente.post(
        f"/mapeador/borradores/{creado['borrador_id']}/validacion",
        json={"asignaciones": asignaciones},
    ).json()["problemas"]

    assert [(p["indice"], p["codigo"], p["campo"]) for p in problemas] == [
        (1, "campo_repetido", "titular"),
        (4, "campo_repetido", "titular"),
        (None, "obligatorio_sin_columna", "pagare"),
    ]
    assert all(set(p) == {"indice", "codigo", "detalle", "campo"} for p in problemas)


def test_validar_contra_el_analisis_guardado_aunque_cambien_los_recordados(api) -> None:
    creado = api.subir().json()
    asignaciones = api.asignaciones(creado)
    api.repo.guardar_recordados(
        "sabana_vencida", {("observacion libre", 1): "agencia"}, api.reloj()
    )

    respuesta = api.cliente.post(
        f"/mapeador/borradores/{creado['borrador_id']}/validacion",
        json={"asignaciones": asignaciones},
    )

    assert respuesta.json() == {"problemas": []}


def test_validar_un_borrador_que_no_existe_o_vencio_es_404(api) -> None:
    cuerpo = {"asignaciones": []}
    assert api.cliente.post("/mapeador/borradores/999/validacion", json=cuerpo).status_code == 404
    creado = api.subir().json()
    api.reloj.avanzar(hours=25)

    respuesta = api.cliente.post(
        f"/mapeador/borradores/{creado['borrador_id']}/validacion", json=cuerpo
    )

    assert respuesta.status_code == 404


def test_validar_con_un_origen_que_no_existe_es_422(api) -> None:
    creado = api.subir().json()

    respuesta = api.cliente.post(
        f"/mapeador/borradores/{creado['borrador_id']}/validacion",
        json={"asignaciones": [{"indice": 0, "campo": "pagare", "origen": "inventado"}]},
    )

    assert respuesta.status_code == 422


# --- DELETE /mapeador/borradores/{id} -----------------------------------------------------------


def test_descartar_un_borrador_es_204_y_la_segunda_vez_404(api) -> None:
    creado = api.subir().json()

    primera = api.cliente.delete(f"/mapeador/borradores/{creado['borrador_id']}")
    segunda = api.cliente.delete(f"/mapeador/borradores/{creado['borrador_id']}")

    assert (primera.status_code, primera.content) == (204, b"")
    assert segunda.status_code == 404
    assert api.repo.borradores == {} and api.repo.contenidos_de_borradores == {}


# --- POST /cargas/desde-borrador ----------------------------------------------------------------


def test_confirmar_es_202_como_subir_una_sabana_y_la_carga_se_procesa(api) -> None:
    creado = api.subir().json()

    respuesta = api.confirmar(creado["borrador_id"], api.asignaciones(creado))

    cuerpo = respuesta.json()
    assert respuesta.status_code == 202
    assert set(cuerpo) == {"id", "fecha_corte", "version", "estado", "versiones_identicas", "aviso"}
    assert (cuerpo["fecha_corte"], cuerpo["version"], cuerpo["estado"]) == (FECHA, 1, "en_cola")
    assert api.repo.borradores == {}
    # El procesamiento sigue en segundo plano (el cliente de prueba lo corre al responder).
    assert api.repo.cargas[cuerpo["id"]]["estado"].value == "terminada"
    assert [f.valores["pagare"] for f in api.repo.filas[cuerpo["id"]]] == [
        "000000000000000001",
        "000000000000000002",
    ]


def test_confirmar_con_problemas_es_422_con_la_lista_y_no_crea_nada(api) -> None:
    creado = api.subir().json()
    asignaciones = api.asignaciones(creado)
    asignaciones[0]["campo"] = None

    respuesta = api.confirmar(creado["borrador_id"], asignaciones)

    cuerpo = respuesta.json()
    assert respuesta.status_code == 422
    assert set(cuerpo) == {"detail", "codigo", "problemas"} and cuerpo["detail"].strip()
    assert cuerpo["codigo"] == "mapeo_con_problemas"
    assert [(p["indice"], p["codigo"], p["campo"]) for p in cuerpo["problemas"]] == [
        (None, "obligatorio_sin_columna", "pagare")
    ]
    assert api.repo.cargas == {} and api.repo.mapeos_recordados == {}
    assert list(api.repo.borradores) == [creado["borrador_id"]]  # se puede corregir y reintentar


def test_confirmar_con_varios_problemas_los_trae_todos(api) -> None:
    creado = api.subir().json()
    asignaciones = api.asignaciones(creado)[:-1]  # falta la ultima
    asignaciones[0]["campo"] = None  # y el campo obligatorio no tiene columna

    respuesta = api.confirmar(creado["borrador_id"], asignaciones)

    assert respuesta.status_code == 422
    assert sorted(p["codigo"] for p in respuesta.json()["problemas"]) == [
        "asignacion_faltante",
        "obligatorio_sin_columna",
    ]


def test_un_parecido_sin_revisar_es_un_problema_y_aceptado_no(api) -> None:
    contenido = csv_de([["Pagare", "Titulares"], ["000000000000000001", "UNO"]])
    creado = api.subir(contenido=contenido).json()
    asignaciones = api.asignaciones(creado)
    assert creado["columnas"][1]["estado"] == "parecido"
    asignaciones[1]["origen"] = "coincide"  # la etiqueta no la acepta: sigue sin revisar

    sin_revisar = api.confirmar(creado["borrador_id"], asignaciones)
    asignaciones[1]["origen"] = "parecido_aceptado"
    aceptado = api.confirmar(creado["borrador_id"], asignaciones)

    assert sin_revisar.status_code == 422
    assert [(p["indice"], p["codigo"]) for p in sin_revisar.json()["problemas"]] == [
        (1, "parecido_sin_revisar")
    ]
    assert aceptado.status_code == 202
    guardadas = api.repo.cargas[aceptado.json()["id"]]["asignaciones"]
    assert [a["origen"] for a in guardadas] == ["coincide", "parecido_aceptado"]


def test_el_origen_de_cada_asignacion_se_guarda_con_la_carga(api) -> None:
    creado = api.subir().json()
    asignaciones = api.asignaciones(creado)

    respuesta = api.confirmar(creado["borrador_id"], asignaciones)

    guardadas = api.repo.cargas[respuesta.json()["id"]]["asignaciones"]
    assert [a["origen"] for a in guardadas] == [a["origen"] for a in asignaciones]
    assert {"coincide"} <= {a["origen"] for a in guardadas}


def test_confirmar_con_una_asignacion_que_falta_dice_cual(api) -> None:
    creado = api.subir().json()

    respuesta = api.confirmar(creado["borrador_id"], api.asignaciones(creado)[:-1])

    assert respuesta.status_code == 422
    assert [(p["indice"], p["codigo"]) for p in respuesta.json()["problemas"]] == [
        (4, "asignacion_faltante")
    ]


def test_confirmar_un_borrador_que_no_existe_es_404(api) -> None:
    assert api.confirmar(999, []).status_code == 404


def test_confirmar_un_borrador_vencido_es_404(api) -> None:
    creado = api.subir().json()
    asignaciones = api.asignaciones(creado)
    api.reloj.avanzar(hours=24)

    respuesta = api.confirmar(creado["borrador_id"], asignaciones)

    assert respuesta.status_code == 404 and api.repo.cargas == {}


def test_confirmar_dos_veces_el_mismo_borrador_la_segunda_es_404(api) -> None:
    creado = api.subir().json()
    asignaciones = api.asignaciones(creado)
    primera = api.confirmar(creado["borrador_id"], asignaciones)

    segunda = api.confirmar(creado["borrador_id"], asignaciones)

    assert (primera.status_code, segunda.status_code) == (202, 404)
    assert len(api.repo.cargas) == 1


def test_confirmar_con_una_fecha_que_no_es_fecha_es_422_de_validacion(api) -> None:
    creado = api.subir().json()

    respuesta = api.confirmar(creado["borrador_id"], api.asignaciones(creado), fecha="ayer")

    assert respuesta.status_code == 422 and "problemas" not in respuesta.json()
    assert list(api.repo.borradores) == [creado["borrador_id"]]


def test_el_mismo_archivo_confirmado_dos_veces_avisa_que_es_identico(api) -> None:
    primero = api.subir().json()
    api.confirmar(primero["borrador_id"], api.asignaciones(primero))
    segundo = api.subir().json()

    respuesta = api.confirmar(segundo["borrador_id"], api.asignaciones(segundo))

    assert (
        respuesta.json()["versiones_identicas"] == [1] and "identico" in respuesta.json()["aviso"]
    )


# --- El ciclo completo por HTTP -----------------------------------------------------------------


def test_crear_validar_confirmar_y_el_siguiente_llega_recordado(api) -> None:
    primero = api.subir().json()
    asignaciones = api.asignaciones(primero)
    asignaciones[4]["campo"] = "agencia"  # el usuario manda la observacion a otro campo
    asignaciones[4]["origen"] = "manual"
    validacion = api.cliente.post(
        f"/mapeador/borradores/{primero['borrador_id']}/validacion",
        json={"asignaciones": asignaciones},
    )
    assert validacion.json() == {"problemas": []}

    assert api.confirmar(primero["borrador_id"], asignaciones).status_code == 202
    segundo = api.subir().json()

    assert [c["estado"] for c in segundo["columnas"]] == ["recordado"] * 5
    assert segundo["columnas"][4]["sugerido"] == "agencia"
    assert segundo["problemas"] == []


def test_los_dos_pagare_por_http_llegan_recordados_la_segunda_vez(api) -> None:
    contenido = csv_de(
        [["Pagare", "Zona", "Pagare"], ["000000000000000001", "x", "000000000000000001"]]
    )
    primero = api.subir(contenido=contenido).json()
    api.confirmar(primero["borrador_id"], api.asignaciones(primero))

    segundo = api.subir(contenido=contenido).json()

    assert [(c["estado"], c["sugerido"]) for c in segundo["columnas"]] == [
        ("recordado", "pagare"),
        ("recordado", None),
        ("recordado", "pagare_duplicado"),
    ]


def test_un_borrador_vencido_no_se_puede_usar_en_ninguna_ruta(api) -> None:
    creado = api.subir().json()
    id_ = creado["borrador_id"]
    api.reloj.avanzar(hours=24)

    respuestas = [
        api.cliente.post(f"/mapeador/borradores/{id_}/analisis", json={}),
        api.cliente.post(f"/mapeador/borradores/{id_}/validacion", json={"asignaciones": []}),
        api.confirmar(id_, api.asignaciones(creado)),
    ]

    assert [r.status_code for r in respuestas] == [404, 404, 404]
    assert {r.json()["codigo"] for r in respuestas} == {"borrador_no_encontrado"}


# --- CORS: DELETE -------------------------------------------------------------------------------


def test_cors_deja_pasar_delete_para_cancelar_un_borrador() -> None:
    aplicacion = FastAPI()
    configurar_cors(aplicacion, ["http://localhost:4321"])

    @aplicacion.delete("/x")
    def borrar() -> None:
        return None

    respuesta = TestClient(aplicacion).options(
        "/x",
        headers={
            "Origin": "http://localhost:4321",
            "Access-Control-Request-Method": "DELETE",
        },
    )

    assert respuesta.status_code == 200
    assert "DELETE" in respuesta.headers["access-control-allow-methods"]
    assert any(m.cls is CORSMiddleware for m in aplicacion.user_middleware)


def test_la_subida_del_borrador_es_multipart_y_declara_los_campos_opcionales() -> None:
    operacion = app.openapi()["paths"]["/mapeador/{catalogo_id}/borradores"]["post"]
    referencia = operacion["requestBody"]["content"]["multipart/form-data"]["schema"]["$ref"]
    esquema = app.openapi()["components"]["schemas"][referencia.rsplit("/", 1)[-1]]

    assert esquema["required"] == ["archivo"]
    assert set(esquema["properties"]) == {"archivo", "hoja", "separador", "codificacion"}
