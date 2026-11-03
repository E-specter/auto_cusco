"""Textos guardados contra PostgreSQL real, de punta a punta (opcional; T-HI-B4, RF-69).

Corre solo con AUTO_CUSCO_DB_TESTS=1 y la base migrada (`alembic upgrade head`). Los contextos
llevan un prefijo propio y todo lo que se crea se borra al terminar (borrar el texto borra sus
versiones en cascada).

Lo que solo aqui se verifica: la unicidad de (contexto, nombre normalizado) y de (texto, numero) en
la base, el CHECK de que el contenido sea un objeto, la numeracion de versiones con varias
escrituras a la vez, `usada_en` que se marca una vez, que eliminar con una version usada no borra
nada, el borrado en cascada y el round trip del contenido por JSONB.
"""

import os
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.modelos import TextoGuardado, TextoGuardadoVersion
from app.adapters.persistence.repositorio_textos_guardados_postgres import (
    RepositorioTextosGuardadosPostgres,
)
from app.api.textos_guardados import obtener_registro_contextos_guardados
from app.core.entities.textos_guardados import (
    NombreDeTextoRepetido,
    TextoConVersionesUsadas,
    TextoDeshabilitado,
)
from app.core.services.textos_guardados.contextos import (
    ContextoGuardado,
    RegistroContextosGuardados,
    TipoContenido,
    validador_de_texto_plano,
)
from app.main import app

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

CONTEXTO = "zz prueba textos"
OTRO_CONTEXTO = "zz prueba textos otro"
_TEXTO = TextoGuardado.__table__
_VERSION = TextoGuardadoVersion.__table__
CONTENIDO = {"texto": "Cuota de S/ 1.5 — ñandú\nsegunda línea [$MACRO1$]", "n": [1, None, 2.5]}


def _limpiar(engine) -> None:
    with engine.begin() as cx:
        cx.execute(delete(_TEXTO).where(_TEXTO.c.contexto.like("zz prueba textos%")))


@pytest.fixture
def repositorio():
    engine = get_engine()
    _limpiar(engine)
    try:
        yield RepositorioTextosGuardadosPostgres(engine), engine
    finally:
        _limpiar(engine)


# --- Repositorio --------------------------------------------------------------------------------


def test_guardar_y_leer_conserva_el_contenido_tal_cual(repositorio) -> None:
    repo, _ = repositorio

    creado = repo.crear(CONTEXTO, "ida y vuelta", CONTENIDO)
    leido = repo.obtener(creado.id)

    assert (leido.contexto, leido.nombre) == (CONTEXTO, "ida y vuelta")
    assert [v.numero for v in leido.versiones] == [1]
    assert dict(leido.versiones[0].contenido) == CONTENIDO  # JSONB: textos, nulos, numeros, listas
    assert leido.versiones[0].usada_en is None and leido.deshabilitado_en is None
    assert leido.creado_en.tzinfo is not None and leido.creado_en == leido.actualizado_en


def test_el_nombre_es_unico_por_contexto_sin_distinguir_mayusculas(repositorio) -> None:
    repo, _ = repositorio
    repo.crear(CONTEXTO, "Cobranza", CONTENIDO)

    with pytest.raises(NombreDeTextoRepetido):
        repo.crear(CONTEXTO, "  COBRANZA ", CONTENIDO)
    assert repo.crear(OTRO_CONTEXTO, "Cobranza", CONTENIDO).id  # otro contexto: vale
    assert len(repo.listar(CONTEXTO, incluir_deshabilitados=True)) == 1  # sin filas a medias


def test_las_versiones_se_numeran_desde_1_y_la_ultima_es_la_vigente(repositorio) -> None:
    repo, _ = repositorio
    creado = repo.crear(CONTEXTO, "versiones", CONTENIDO)

    dos = repo.agregar_version(creado.id, {"texto": "dos"})
    tres = repo.agregar_version(creado.id, {"texto": "tres"})

    assert (dos.numero, tres.numero) == (2, 3)
    leido = repo.obtener(creado.id)
    assert leido.vigente.numero == 3 and leido.actualizado_en > leido.creado_en
    assert repo.agregar_version(99_999_999, CONTENIDO) is None


def test_varias_versiones_nuevas_a_la_vez_toman_numeros_distintos(repositorio) -> None:
    repo, _ = repositorio
    creado = repo.crear(CONTEXTO, "concurrencia", CONTENIDO)
    numeros: list[int] = []
    errores: list[Exception] = []

    def agregar() -> None:
        try:
            numeros.append(repo.agregar_version(creado.id, CONTENIDO).numero)
        except Exception as exc:  # noqa: BLE001
            errores.append(exc)

    hilos = [threading.Thread(target=agregar) for _ in range(8)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert errores == []
    assert sorted(numeros) == list(range(2, 10))
    assert [v.numero for v in repo.obtener(creado.id).versiones] == list(range(1, 10))


def test_la_base_no_admite_dos_versiones_con_el_mismo_numero_ni_numero_menor_que_1(
    repositorio,
) -> None:
    repo, engine = repositorio
    creado = repo.crear(CONTEXTO, "numeros", CONTENIDO)

    for numero in (1, 0):
        with pytest.raises(IntegrityError), engine.begin() as cx:
            cx.execute(
                insert(_VERSION).values(texto_id=creado.id, numero=numero, contenido=CONTENIDO)
            )


@pytest.mark.parametrize("contenido", [None, [], [1], 3, "texto", True])
def test_la_base_solo_admite_un_objeto_como_contenido(repositorio, contenido) -> None:
    repo, engine = repositorio
    creado = repo.crear(CONTEXTO, "objeto", CONTENIDO)

    # `none_as_null`: un None es NULL de SQL (lo rechaza NOT NULL), no el JSON `null`; el CHECK
    # rechaza el resto de lo que no es un objeto, tambien por SQL directo.
    with pytest.raises(IntegrityError), engine.begin() as cx:
        cx.execute(insert(_VERSION).values(texto_id=creado.id, numero=2, contenido=contenido))


def test_la_base_admite_un_objeto_vacio_como_contenido(repositorio) -> None:
    repo, engine = repositorio
    creado = repo.crear(CONTEXTO, "vacio", CONTENIDO)

    with engine.begin() as cx:
        cx.execute(insert(_VERSION).values(texto_id=creado.id, numero=2, contenido={}))

    assert dict(repo.obtener(creado.id).vigente.contenido) == {}


def test_renombrar_cambia_el_nombre_y_deja_las_versiones_intactas(repositorio) -> None:
    repo, _ = repositorio
    creado = repo.crear(CONTEXTO, "Antes", CONTENIDO)
    repo.agregar_version(creado.id, {"texto": "dos"})
    antes = repo.obtener(creado.id)

    despues = repo.renombrar(creado.id, "Despues")

    assert despues.nombre == "Despues" and despues.actualizado_en > antes.actualizado_en
    assert despues.versiones == antes.versiones
    assert repo.renombrar(creado.id, "Despues").actualizado_en == despues.actualizado_en
    assert repo.renombrar(99_999_999, "x") is None


def test_renombrar_a_un_nombre_ajeno_lo_rechaza_la_base_y_solo_la_caja_no_choca(
    repositorio,
) -> None:
    repo, _ = repositorio
    uno = repo.crear(CONTEXTO, "Uno", CONTENIDO)
    repo.crear(CONTEXTO, "Dos", CONTENIDO)

    with pytest.raises(NombreDeTextoRepetido):
        repo.renombrar(uno.id, " DOS")
    assert repo.renombrar(uno.id, "UNO").nombre == "UNO"
    assert repo.obtener(uno.id).nombre == "UNO"


def test_deshabilitar_marca_la_fecha_una_vez_y_el_listado_lo_oculta(repositorio) -> None:
    repo, _ = repositorio
    uno = repo.crear(CONTEXTO, "Uno", CONTENIDO)
    repo.crear(CONTEXTO, "Dos", CONTENIDO)

    primera = repo.deshabilitar(uno.id).deshabilitado_en
    segunda = repo.deshabilitar(uno.id).deshabilitado_en

    assert primera is not None and primera == segunda
    assert [r.nombre for r in repo.listar(CONTEXTO)] == ["Dos"]
    todos = repo.listar(CONTEXTO, incluir_deshabilitados=True)
    assert [(r.nombre, r.deshabilitado_en is not None) for r in todos] == [
        ("Dos", False),
        ("Uno", True),
    ]
    with pytest.raises(TextoDeshabilitado):
        repo.agregar_version(uno.id, CONTENIDO)
    assert repo.deshabilitar(99_999_999) is None


def test_habilitar_limpia_la_fecha_es_idempotente_y_el_listado_lo_incluye(repositorio) -> None:
    repo, _ = repositorio
    uno = repo.crear(CONTEXTO, "Uno", CONTENIDO)
    repo.deshabilitar(uno.id)
    assert repo.listar(CONTEXTO) == []

    habilitado = repo.habilitar(uno.id)
    otra_vez = repo.habilitar(uno.id)

    assert habilitado.deshabilitado_en is None
    assert otra_vez.actualizado_en == habilitado.actualizado_en  # ya habilitado: no escribe
    assert [r.nombre for r in repo.listar(CONTEXTO)] == ["Uno"]
    assert repo.agregar_version(uno.id, CONTENIDO).numero == 2
    assert repo.habilitar(99_999_999) is None


def test_el_listado_es_del_contexto_ordenado_y_marca_si_la_vigente_se_uso(repositorio) -> None:
    repo, _ = repositorio
    b = repo.crear(CONTEXTO, "b segundo", CONTENIDO)
    a = repo.crear(CONTEXTO, "A primero", CONTENIDO)
    repo.crear(OTRO_CONTEXTO, "ajeno", CONTENIDO)
    repo.agregar_version(a.id, CONTENIDO)
    repo.marcar_version_usada(a.id, 1)  # la vigente es la 2 y no se uso

    listado = repo.listar(CONTEXTO)

    assert [
        (r.nombre, r.version_vigente, r.cantidad_versiones, r.vigente_usada) for r in listado
    ] == [
        ("A primero", 2, 2, False),
        ("b segundo", 1, 1, False),
    ]
    repo.marcar_version_usada(b.id, 1)
    assert [r.vigente_usada for r in repo.listar(CONTEXTO)] == [False, True]


def test_eliminable_es_falso_si_se_uso_cualquier_version_aunque_no_sea_la_vigente(
    repositorio,
) -> None:
    repo, _ = repositorio
    vieja = repo.crear(CONTEXTO, "Vieja usada", CONTENIDO)
    repo.agregar_version(vieja.id, CONTENIDO)
    repo.marcar_version_usada(vieja.id, 1)
    repo.crear(CONTEXTO, "Sin usar", CONTENIDO)

    listado = {r.nombre: r for r in repo.listar(CONTEXTO)}

    assert (listado["Vieja usada"].vigente_usada, listado["Vieja usada"].eliminable) == (
        False,
        False,
    )
    assert listado["Sin usar"].eliminable is True


def test_usada_en_se_marca_la_primera_vez_y_no_cambia_despues(repositorio) -> None:
    repo, _ = repositorio
    creado = repo.crear(CONTEXTO, "usada", CONTENIDO)

    assert repo.marcar_version_usada(creado.id, 1) is True
    primera = repo.obtener(creado.id).versiones[0].usada_en
    assert repo.marcar_version_usada(creado.id, 1) is True

    assert primera is not None and repo.obtener(creado.id).versiones[0].usada_en == primera
    assert repo.marcar_version_usada(creado.id, 9) is False
    assert repo.marcar_version_usada(99_999_999, 1) is False


def test_eliminar_borra_el_texto_y_sus_versiones_en_cascada(repositorio) -> None:
    repo, engine = repositorio
    creado = repo.crear(CONTEXTO, "borrar", CONTENIDO)
    repo.agregar_version(creado.id, CONTENIDO)

    assert repo.eliminar(creado.id) is True

    assert repo.obtener(creado.id) is None
    with engine.connect() as cx:
        restantes = cx.execute(select(_VERSION).where(_VERSION.c.texto_id == creado.id)).all()
    assert restantes == []
    assert repo.eliminar(creado.id) is False
    assert repo.crear(CONTEXTO, "borrar", CONTENIDO).id  # el nombre queda libre


def test_eliminar_con_una_version_usada_lo_rechaza_y_no_borra_nada(repositorio) -> None:
    repo, _ = repositorio
    creado = repo.crear(CONTEXTO, "usado", CONTENIDO)
    repo.agregar_version(creado.id, CONTENIDO)
    repo.marcar_version_usada(creado.id, 1)

    with pytest.raises(TextoConVersionesUsadas):
        repo.eliminar(creado.id)

    assert [v.numero for v in repo.obtener(creado.id).versiones] == [1, 2]
    assert repo.deshabilitar(creado.id).deshabilitado_en is not None  # lo que si se puede


# --- Por HTTP, con la base real y un contexto sintetico -----------------------------------------


@pytest.fixture
def cliente(repositorio):
    registro = RegistroContextosGuardados(
        [
            ContextoGuardado(
                CONTEXTO, "Prueba", TipoContenido.TEXTO_PLANO, validador_de_texto_plano(200)
            )
        ]
    )
    app.dependency_overrides[obtener_registro_contextos_guardados] = lambda: registro
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(obtener_registro_contextos_guardados, None)


def test_el_ciclo_completo_por_http(cliente) -> None:
    creado = cliente.post(
        "/textos-guardados",
        json={"contexto": CONTEXTO, "nombre": "Cobranza", "contenido": {"texto": "Hola ñ"}},
    )
    assert creado.status_code == 201
    id_ = creado.json()["id"]

    repetido = cliente.post(
        "/textos-guardados",
        json={"contexto": CONTEXTO, "nombre": "cobranza ", "contenido": {"texto": "x"}},
    )
    assert repetido.status_code == 409 and repetido.json()["codigo"] == "nombre_repetido"

    nueva = cliente.post(f"/textos-guardados/{id_}/versiones", json={"contenido": {"texto": "Dos"}})
    assert nueva.json()["version"]["numero"] == 2
    primera = cliente.get(f"/textos-guardados/{id_}", params={"version": 1}).json()
    assert primera["version"]["contenido"] == {"texto": "Hola ñ"}

    renombrado = cliente.patch(f"/textos-guardados/{id_}", json={"nombre": "Recordatorio"})
    assert (
        renombrado.json()["nombre"] == "Recordatorio" and len(renombrado.json()["versiones"]) == 2
    )
    listado = cliente.get("/textos-guardados", params={"contexto": CONTEXTO}).json()
    assert [(t["nombre"], t["cantidad_versiones"]) for t in listado] == [("Recordatorio", 2)]

    assert cliente.post(f"/textos-guardados/{id_}/deshabilitar").status_code == 200
    assert cliente.get("/textos-guardados", params={"contexto": CONTEXTO}).json() == []
    assert cliente.delete(f"/textos-guardados/{id_}").status_code == 204
    assert cliente.get(f"/textos-guardados/{id_}").status_code == 404
