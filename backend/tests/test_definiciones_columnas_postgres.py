"""Definiciones de columnas guardadas contra PostgreSQL real, de punta a punta (opcional).

Corre solo con AUTO_CUSCO_DB_TESTS=1 y la base migrada (`alembic upgrade head`). Los nombres llevan
un prefijo propio y todo lo que se crea se borra al terminar (borrar la definicion borra sus
versiones en cascada). Los casos de HTTP entran sin sustituir ninguna dependencia y generan la
carga sobre una sabana sintetica de la fecha 2099-05-01, que tambien se borra.

Lo que solo aqui se verifica: la unicidad del nombre normalizado y de (definicion, numero) en la
base, la numeracion de versiones con varias escrituras a la vez, `usada_en` que se marca una vez, el
borrado en cascada, el round trip del contenido por JSONB y el camino completo hasta el archivo.
"""

import os
import threading
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError

from app.adapters.input.lector_calamine import LectorCalamine
from app.adapters.persistence.db import get_engine
from app.adapters.persistence.modelos import (
    Carga,
    CargaAuditoria,
    DefinicionCargaGuardada,
    DefinicionCargaVersion,
)
from app.adapters.persistence.repositorio_cargas_postgres import RepositorioCargasPostgres
from app.adapters.persistence.repositorio_definiciones_postgres import (
    RepositorioDefinicionesPostgres,
)
from app.core.entities.definiciones_columnas import NombreDeDefinicionRepetido, normalizar_nombre
from app.core.services.ingesta_sabana.servicio import IngestaSabanaService
from app.main import app
from tests.test_generacion_cargas_postgres import PRODUCTOS, _sabana

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

PREFIJO = "zz prueba definiciones "
FECHA = date(2099, 5, 1)
_DEFINICION = DefinicionCargaGuardada.__table__
_VERSION = DefinicionCargaVersion.__table__
CARGA, AUDITORIA = Carga.__table__, CargaAuditoria.__table__

CONTENIDO = {
    "proteger_formulas": True,
    "columnas": [
        {
            "nombre": "mensaje",
            "orden": 0,
            "expresion": {
                "nodos": [
                    {"tipo": "texto", "valor": "Cuota de S/ 1.5 — ñandú\nsegunda línea"},
                    {
                        "tipo": "variable",
                        "nombre": "titular",
                        "funciones": [{"nombre": "primeros", "args": [8]}],
                        "obligatoria": False,
                    },
                ]
            },
            "tipo": "texto",
            "formato_fecha": None,
            "formato_financiero": {
                "separador_miles": ",",
                "separador_decimal": ".",
                "decimales": 2,
            },
            "valor_por_defecto": None,
            "variantes": [],
        }
    ],
    "segmentacion": None,
}


def _limpiar(engine) -> None:
    prefijo = normalizar_nombre(PREFIJO)
    with engine.begin() as cx:
        cx.execute(delete(_DEFINICION).where(_DEFINICION.c.nombre_normalizado.startswith(prefijo)))


def _limpiar_cargas(engine) -> None:
    with engine.begin() as cx:
        cx.execute(delete(CARGA).where(CARGA.c.fecha_corte == FECHA))
        cx.execute(delete(AUDITORIA).where(AUDITORIA.c.fecha_corte == FECHA))


@pytest.fixture
def repositorio():
    engine = get_engine()
    _limpiar(engine)
    try:
        yield RepositorioDefinicionesPostgres(engine), engine
    finally:
        _limpiar(engine)


# --- Repositorio ----------------------------------------------------------------------------------


def test_guardar_y_leer_conserva_el_contenido_tal_cual(repositorio) -> None:
    repo, _ = repositorio

    creada = repo.crear(f"{PREFIJO}ida y vuelta", CONTENIDO)
    leida = repo.obtener(creada.id)

    assert leida.nombre == f"{PREFIJO}ida y vuelta"
    assert [v.numero for v in leida.versiones] == [1]
    assert dict(leida.versiones[0].contenido) == CONTENIDO  # JSONB: textos, nulos, numeros y listas
    assert leida.versiones[0].usada_en is None
    assert leida.creado_en.tzinfo is not None and leida.creado_en == leida.actualizado_en


def test_el_nombre_repetido_lo_rechaza_la_base_sin_distinguir_mayusculas(repositorio) -> None:
    repo, _ = repositorio
    repo.crear(f"{PREFIJO}Preventiva", CONTENIDO)

    with pytest.raises(NombreDeDefinicionRepetido):
        repo.crear(f"  {PREFIJO}PREVENTIVA  ", CONTENIDO)


def test_un_nombre_repetido_no_deja_una_definicion_a_medias(repositorio) -> None:
    repo, engine = repositorio
    repo.crear(f"{PREFIJO}una", CONTENIDO)

    with pytest.raises(NombreDeDefinicionRepetido):
        repo.crear(f"{PREFIJO}UNA", CONTENIDO)

    with engine.connect() as cx:
        definiciones = cx.execute(
            select(_DEFINICION.c.id).where(
                _DEFINICION.c.nombre_normalizado.startswith(normalizar_nombre(PREFIJO))
            )
        ).all()
    assert len(definiciones) == 1


def test_las_versiones_se_numeran_desde_1_y_la_ultima_es_la_vigente(repositorio) -> None:
    repo, _ = repositorio
    creada = repo.crear(f"{PREFIJO}versiones", CONTENIDO)

    dos = repo.agregar_version(creada.id, {**CONTENIDO, "proteger_formulas": False})
    tres = repo.agregar_version(creada.id, CONTENIDO)
    leida = repo.obtener(creada.id)

    assert (dos.numero, tres.numero) == (2, 3)
    assert [v.numero for v in leida.versiones] == [1, 2, 3]
    assert leida.vigente.numero == 3
    assert leida.versiones[1].contenido["proteger_formulas"] is False
    assert leida.versiones[0].contenido["proteger_formulas"] is True  # la anterior no cambia


def test_una_version_nueva_avanza_actualizado_en(repositorio) -> None:
    repo, _ = repositorio
    creada = repo.crear(f"{PREFIJO}reloj", CONTENIDO)

    repo.agregar_version(creada.id, CONTENIDO)

    assert repo.obtener(creada.id).actualizado_en > creada.actualizado_en


def test_agregar_una_version_a_una_definicion_inexistente_da_none(repositorio) -> None:
    repo, _ = repositorio

    assert repo.agregar_version(2**40, CONTENIDO) is None


def test_la_base_no_admite_dos_versiones_con_el_mismo_numero(repositorio) -> None:
    repo, engine = repositorio
    creada = repo.crear(f"{PREFIJO}unica", CONTENIDO)

    with pytest.raises(IntegrityError), engine.begin() as cx:
        cx.execute(insert(_VERSION).values(definicion_id=creada.id, numero=1, contenido=CONTENIDO))


def test_la_base_no_admite_un_numero_de_version_menor_que_1(repositorio) -> None:
    repo, engine = repositorio
    creada = repo.crear(f"{PREFIJO}positivo", CONTENIDO)

    with pytest.raises(IntegrityError), engine.begin() as cx:
        cx.execute(insert(_VERSION).values(definicion_id=creada.id, numero=0, contenido=CONTENIDO))


def test_varias_versiones_nuevas_a_la_vez_toman_numeros_distintos(repositorio) -> None:
    repo, _ = repositorio
    creada = repo.crear(f"{PREFIJO}concurrencia", CONTENIDO)
    numeros: list[int] = []
    errores: list[Exception] = []

    def agregar() -> None:
        try:
            numeros.append(repo.agregar_version(creada.id, CONTENIDO).numero)
        except Exception as exc:  # noqa: BLE001
            errores.append(exc)

    hilos = [threading.Thread(target=agregar) for _ in range(8)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert errores == []
    assert sorted(numeros) == list(range(2, 10))  # ninguna repetida y ninguna salteada
    assert [v.numero for v in repo.obtener(creada.id).versiones] == list(range(1, 10))


def test_usada_en_se_marca_la_primera_vez_y_no_cambia_despues(repositorio) -> None:
    repo, _ = repositorio
    creada = repo.crear(f"{PREFIJO}usada", CONTENIDO)
    repo.agregar_version(creada.id, CONTENIDO)

    assert repo.marcar_version_usada(creada.id, 1) is True
    primera = repo.obtener(creada.id).versiones[0].usada_en
    assert repo.marcar_version_usada(creada.id, 1) is True
    leida = repo.obtener(creada.id)

    assert primera is not None and primera.tzinfo is not None
    assert leida.versiones[0].usada_en == primera  # la segunda vez no la cambia
    assert leida.versiones[1].usada_en is None  # y solo marca la version pedida


def test_marcar_usada_una_version_inexistente_da_false(repositorio) -> None:
    repo, _ = repositorio
    creada = repo.crear(f"{PREFIJO}falta", CONTENIDO)

    assert repo.marcar_version_usada(creada.id, 5) is False
    assert repo.marcar_version_usada(2**40, 1) is False


def test_el_listado_trae_lo_de_c7_ordenado_por_nombre_normalizado(repositorio) -> None:
    repo, _ = repositorio
    b = repo.crear(f"{PREFIJO}b segunda", CONTENIDO)
    repo.crear(f"{PREFIJO}A primera", CONTENIDO)
    repo.agregar_version(b.id, CONTENIDO)
    repo.marcar_version_usada(b.id, 2)

    propias = [r for r in repo.listar() if r.nombre.startswith(PREFIJO)]

    assert [
        (r.nombre, r.version_vigente, r.cantidad_versiones, r.vigente_usada) for r in propias
    ] == [
        (f"{PREFIJO}A primera", 1, 1, False),
        (f"{PREFIJO}b segunda", 2, 2, True),
    ]
    assert propias[1].actualizado_en > propias[0].actualizado_en


def test_el_listado_marca_usada_solo_si_la_vigente_se_uso(repositorio) -> None:
    repo, _ = repositorio
    creada = repo.crear(f"{PREFIJO}vigente", CONTENIDO)
    repo.marcar_version_usada(creada.id, 1)
    repo.agregar_version(creada.id, CONTENIDO)  # la vigente (2) no se uso

    resumen = next(r for r in repo.listar() if r.id == creada.id)

    assert (resumen.version_vigente, resumen.vigente_usada) == (2, False)


def test_obtener_una_definicion_inexistente_da_none(repositorio) -> None:
    repo, _ = repositorio

    assert repo.obtener(2**40) is None


def test_borrar_la_definicion_borra_sus_versiones_en_cascada(repositorio) -> None:
    repo, engine = repositorio
    creada = repo.crear(f"{PREFIJO}cascada", CONTENIDO)
    repo.agregar_version(creada.id, CONTENIDO)

    with engine.begin() as cx:
        cx.execute(delete(_DEFINICION).where(_DEFINICION.c.id == creada.id))
        restantes = cx.execute(
            select(_VERSION.c.id).where(_VERSION.c.definicion_id == creada.id)
        ).all()

    assert restantes == []


# --- Por HTTP, sin sustituir ninguna dependencia ------------------------------------------------


@pytest.fixture
def cliente(repositorio):
    """Cliente HTTP sobre la base real, con la sabana sintetica de 2099-05-01 ingestada."""
    engine = get_engine()
    _limpiar_cargas(engine)
    ingesta = IngestaSabanaService(RepositorioCargasPostgres(engine), LectorCalamine())
    carga = ingesta.registrar_carga(FECHA, "sintetica.xlsx", _sabana(PRODUCTOS)).carga
    assert ingesta.procesar_carga(carga.id).vigente
    try:
        yield TestClient(app)
    finally:
        _limpiar_cargas(engine)


def _columna(nombre: str, orden: int, *nodos: dict, **extra) -> dict:
    return {"nombre": nombre, "orden": orden, "expresion": {"nodos": list(nodos)}, **extra}


def _definicion_http(nombre: str, **extra) -> dict:
    return {
        "nombre": nombre,
        "columnas": [
            _columna("anexo", 0, {"tipo": "texto", "valor": "1010"}, tipo="numero"),
            _columna(
                "numero",
                1,
                {"tipo": "texto", "valor": "51"},
                {"tipo": "variable", "nombre": "telefono", "funciones": []},
            ),
            _columna("pagare", 2, {"tipo": "variable", "nombre": "pagare", "funciones": []}),
            _columna(
                "deuda",
                3,
                {"tipo": "variable", "nombre": "saldo_capital_pendiente", "funciones": []},
                tipo="financiero",
                # Un formato explicito y distinto del de por defecto (`1,000.50`): lo que se
                # prueba es que el de la definicion es el que se aplica.
                formato_financiero={
                    "separador_miles": ".",
                    "separador_decimal": ",",
                    "decimales": 2,
                },
            ),
            _columna(
                "vence",
                4,
                {"tipo": "variable", "nombre": "fecha_vencimiento_cuota", "funciones": []},
                tipo="fecha",
                formato_fecha="dd/mm/aaaa",
            ),
        ],
        **extra,
    }


def test_guardar_leer_y_versionar_por_http(cliente) -> None:
    nombre = f"{PREFIJO}http"

    creada = cliente.post("/definiciones-columnas", json=_definicion_http(nombre))
    id_ = creada.json()["id"]
    nueva = cliente.post(
        f"/definiciones-columnas/{id_}/versiones", json=_definicion_http(nombre.upper())
    )
    leida = cliente.get(f"/definiciones-columnas/{id_}", params={"version": 1})
    listado = cliente.get("/definiciones-columnas").json()

    assert (creada.status_code, nueva.status_code, leida.status_code) == (201, 201, 200)
    assert nueva.json()["version"]["numero"] == 2
    assert leida.json()["version"]["numero"] == 1
    assert leida.json()["version_vigente"] == 2
    assert [d["version_vigente"] for d in listado if d["id"] == id_] == [2]
    assert cliente.post("/definiciones-columnas", json=_definicion_http(nombre)).status_code == 409


def test_generar_el_archivo_con_una_guardada_marca_usada_en_y_da_las_filas_de_la_cartera(
    cliente,
) -> None:
    id_ = cliente.post("/definiciones-columnas", json=_definicion_http(f"{PREFIJO}carga")).json()[
        "id"
    ]
    pedido = {
        "fecha_corte": FECHA.isoformat(),
        "definicion_guardada": {"id": id_},
        "cantidad": 10,
    }

    previa = cliente.post("/archivos-carga/previsualizacion", json=pedido).json()
    sin_marcar = cliente.get(f"/definiciones-columnas/{id_}").json()["version"]["usada"]
    archivo = cliente.post("/archivos-carga", json={**pedido, "formato": "csv"})
    marcada = cliente.get(f"/definiciones-columnas/{id_}").json()["version"]

    assert previa["cabeceras"] == ["anexo", "numero", "pagare", "deuda", "vence"]
    por_pagare = {fila["pagare"]: fila for fila in previa["filas"]}
    assert (
        por_pagare["000000000000000001"]["deuda"] == "1.000,50"
    )  # 1000.5 con el formato de la columna
    assert por_pagare["000000000000000001"]["vence"] == "14/09/2026"
    assert por_pagare["000000000000000003"]["numero"] == "51"  # telefono invalido: solo el prefijo
    assert sin_marcar is False  # la previsualizacion no marca
    assert archivo.status_code == 200
    assert marcada["usada"] is True and marcada["usada_en"] is not None


def test_la_muestra_de_los_primeros_de_una_seleccion_usa_la_cartera_real(cliente) -> None:
    respuesta = cliente.post(
        "/texto-enriquecido/previsualizacion",
        json={
            "contexto": "cartera",
            "expresion": {"nodos": [{"tipo": "variable", "nombre": "pagare", "funciones": []}]},
            "muestra": {
                "tipo": "primeros_de_seleccion",
                "fecha_corte": FECHA.isoformat(),
                "orden": "-saldo_capital_pendiente",
                "cantidad": 3,
            },
        },
    )

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert [f["columnas"][0]["texto"] for f in cuerpo["filas"]] == [
        "000000000000000005",
        "000000000000000004",
        "000000000000000003",
    ]
    assert cuerpo["disponibles"] == 5
