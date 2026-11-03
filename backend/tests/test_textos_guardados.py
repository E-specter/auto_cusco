"""Textos guardados y versionados por contexto (T-HI-B4, RF-69), sin base.

B4 no registra ningun contexto real: aqui hay dos sinteticos, uno de texto plano (`prueba.plano`,
hasta 20 caracteres y sin `!`) y uno de expresion del motor (`prueba.expresion`, contra el contexto
`cartera`). El repositorio es el doble en memoria (`tests/textos_memoria.py`); PostgreSQL tiene sus
pruebas en `test_textos_guardados_postgres.py`.
"""

import io
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.adapters.persistence.modelos import Base
from app.api.textos_guardados import (
    obtener_registro_contextos_guardados,
    obtener_servicio_textos_guardados,
)
from app.core.entities.texto_enriquecido import CodigoTexto, Problema
from app.core.entities.textos_guardados import (
    LARGO_MAXIMO_NOMBRE,
    NombreDeTextoRepetido,
    TextoConVersionesUsadas,
    TextoDeshabilitado,
    TextoNoEncontrado,
    VersionDeTextoNoEncontrada,
)
from app.core.services.contextos_texto import contexto_cartera
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.core.services.textos_guardados.contextos import (
    ContextoGuardado,
    ContextoGuardadoDesconocido,
    RegistroContextosGuardados,
    TipoContenido,
    validador_de_expresion,
    validador_de_texto_plano,
)
from app.core.services.textos_guardados.servicio import TextoInvalido, TextosGuardadosService
from app.main import app
from tests.textos_memoria import RepositorioTextosEnMemoria

CARTERA = contexto_cartera(CatalogoCartera())
PLANO = "prueba.plano"
EXPRESION = "prueba.expresion"


def _sin_admiracion(texto: str) -> list[Problema]:
    if "!" in texto:
        return [Problema(CodigoTexto.TEXTO_GUARDADO_INVALIDO, "No admite `!`")]
    return []


def _registro() -> RegistroContextosGuardados:
    return RegistroContextosGuardados(
        [
            ContextoGuardado(
                PLANO,
                "Plano",
                TipoContenido.TEXTO_PLANO,
                validador_de_texto_plano(20, _sin_admiracion),
            ),
            ContextoGuardado(
                EXPRESION, "Expresion", TipoContenido.EXPRESION, validador_de_expresion(CARTERA)
            ),
        ]
    )


def _servicio() -> tuple[TextosGuardadosService, RepositorioTextosEnMemoria]:
    repositorio = RepositorioTextosEnMemoria()
    return TextosGuardadosService(repositorio, _registro()), repositorio


def _plano(texto: str = "Hola") -> dict:
    return {"texto": texto}


def _expresion(*nodos: dict) -> dict:
    return {"expresion": {"nodos": list(nodos) or [{"tipo": "texto", "valor": "Hola"}]}}


def _problemas(error: TextoInvalido) -> list[tuple]:
    return [(p.problema.codigo, p.campo) for p in error.problemas]


# --- El registro y los validadores --------------------------------------------------------------


def test_el_registro_conserva_el_orden_y_no_repite_ni_inventa_contextos() -> None:
    registro = _registro()

    assert [c.clave for c in registro.disponibles()] == [PLANO, EXPRESION]
    assert PLANO in registro and "otro" not in registro
    with pytest.raises(ContextoGuardadoDesconocido) as error:
        registro.obtener("otro")
    assert error.value.clave == "otro"
    with pytest.raises(ValueError):
        registro.registrar(registro.obtener(PLANO))
    with pytest.raises(ValueError):
        ContextoGuardado(" ", "Algo", TipoContenido.TEXTO_PLANO, validador_de_texto_plano(5))


@pytest.mark.parametrize(
    "contenido",
    [{}, {"texto": 3}, {"texto": ""}, {"texto": "   "}, {"texto": "x" * 21}]
    + [{"texto": "a", "otro": 1}, {"expresion": {"nodos": []}}],
)
def test_el_texto_plano_exige_un_texto_de_1_al_maximo(contenido) -> None:
    assert validador_de_texto_plano(20)(contenido)


def test_el_texto_plano_de_exactamente_el_maximo_cabe() -> None:
    assert validador_de_texto_plano(20)(_plano("x" * 20)) == ()
    assert validador_de_texto_plano(20)(_plano("x" * 21))


def test_el_texto_plano_aplica_las_reglas_del_modulo() -> None:
    validar = validador_de_texto_plano(20, _sin_admiracion)

    assert validar(_plano("Hola")) == ()
    assert [p.codigo for p in validar(_plano("Hola!"))] == [CodigoTexto.TEXTO_GUARDADO_INVALIDO]


def test_la_expresion_se_valida_con_el_motor_y_las_variables_del_contexto() -> None:
    validar = validador_de_expresion(CARTERA)
    titular = {"tipo": "variable", "nombre": "titular", "funciones": []}
    inventada = {"tipo": "variable", "nombre": "no_existe", "funciones": []}

    assert validar(_expresion(titular)) == ()
    assert [p.codigo for p in validar(_expresion(inventada))] == [CodigoTexto.VARIABLE_DESCONOCIDA]
    assert validar({"texto": "no es una expresion"})  # la clave es `expresion`
    assert validar({"expresion": {"nodos": "mal"}})


# --- Crear --------------------------------------------------------------------------------------


def test_crear_guarda_la_version_1_con_el_nombre_recortado() -> None:
    servicio, _ = _servicio()

    vista = servicio.crear(PLANO, "  Cobranza amable  ", _plano())

    assert (vista.texto.contexto, vista.texto.nombre) == (PLANO, "Cobranza amable")
    assert vista.version.numero == 1 and vista.version.contenido == _plano()
    assert vista.texto.deshabilitado_en is None and vista.version.usada_en is None


def test_crear_en_un_contexto_no_registrado_se_rechaza() -> None:
    servicio, repositorio = _servicio()

    with pytest.raises(ContextoGuardadoDesconocido):
        servicio.crear("inventado", "Nombre", _plano())
    with pytest.raises(ContextoGuardadoDesconocido):
        servicio.listar("inventado")
    assert repositorio.textos == {}


@pytest.mark.parametrize("nombre", [None, "", "   ", 7, "x" * (LARGO_MAXIMO_NOMBRE + 1)])
def test_un_nombre_vacio_largo_o_que_no_es_texto_es_un_problema_del_campo_nombre(nombre) -> None:
    servicio, repositorio = _servicio()

    with pytest.raises(TextoInvalido) as error:
        servicio.crear(PLANO, nombre, _plano())

    assert _problemas(error.value) == [(CodigoTexto.TEXTO_GUARDADO_INVALIDO, "nombre")]
    assert repositorio.textos == {}


def test_el_nombre_de_120_caracteres_cabe() -> None:
    servicio, _ = _servicio()

    assert servicio.crear(PLANO, "x" * LARGO_MAXIMO_NOMBRE, _plano()).texto.id == 1


def test_el_nombre_y_el_contenido_se_informan_juntos() -> None:
    servicio, _ = _servicio()

    with pytest.raises(TextoInvalido) as error:
        servicio.crear(PLANO, " ", _plano("con !"))

    assert sorted(_problemas(error.value), key=lambda p: p[1]) == [
        (CodigoTexto.TEXTO_GUARDADO_INVALIDO, "contenido"),
        (CodigoTexto.TEXTO_GUARDADO_INVALIDO, "nombre"),
    ]


@pytest.mark.parametrize("contenido", [None, [], "texto", 3])
def test_un_contenido_que_no_es_un_objeto_es_un_problema_del_campo_contenido(contenido) -> None:
    servicio, _ = _servicio()

    with pytest.raises(TextoInvalido) as error:
        servicio.crear(PLANO, "Nombre", contenido)

    assert _problemas(error.value) == [(CodigoTexto.TEXTO_GUARDADO_INVALIDO, "contenido")]


def test_el_nombre_es_unico_por_contexto_sin_distinguir_mayusculas_ni_extremos() -> None:
    servicio, _ = _servicio()
    servicio.crear(PLANO, "Cobranza", _plano())

    with pytest.raises(NombreDeTextoRepetido):
        servicio.crear(PLANO, "  COBRANZA ", _plano("otro"))
    # en otro contexto el mismo nombre vale
    assert servicio.crear(EXPRESION, "Cobranza", _expresion()).texto.contexto == EXPRESION


def test_una_tilde_distingue_nombres() -> None:
    servicio, _ = _servicio()
    servicio.crear(PLANO, "Cobranza", _plano())

    assert servicio.crear(PLANO, "Cobranzá", _plano()).texto.id == 2


# --- Versionar ----------------------------------------------------------------------------------


def test_una_version_nueva_es_la_vigente_y_no_toca_las_anteriores() -> None:
    servicio, _ = _servicio()
    texto = servicio.crear(PLANO, "Cobranza", _plano("uno")).texto

    vista = servicio.agregar_version(texto.id, _plano("dos"))

    assert vista.version.numero == 2 and vista.texto.vigente.numero == 2
    assert [v.contenido for v in vista.texto.versiones] == [_plano("uno"), _plano("dos")]
    assert servicio.obtener(texto.id, 1).version.contenido == _plano("uno")
    assert servicio.obtener(texto.id).version.numero == 2


def test_la_version_nueva_se_valida_con_el_contexto_del_texto() -> None:
    servicio, _ = _servicio()
    texto = servicio.crear(PLANO, "Cobranza", _plano()).texto

    with pytest.raises(TextoInvalido) as error:
        servicio.agregar_version(texto.id, _plano("con !"))

    assert _problemas(error.value) == [(CodigoTexto.TEXTO_GUARDADO_INVALIDO, "contenido")]
    assert len(servicio.obtener(texto.id).texto.versiones) == 1


def test_versionar_un_texto_inexistente_o_de_un_contexto_ya_no_registrado() -> None:
    servicio, repositorio = _servicio()
    texto = servicio.crear(PLANO, "Cobranza", _plano()).texto
    sin_contextos = TextosGuardadosService(repositorio, RegistroContextosGuardados())

    with pytest.raises(TextoNoEncontrado):
        servicio.agregar_version(99, _plano())
    with pytest.raises(ContextoGuardadoDesconocido):
        sin_contextos.agregar_version(texto.id, _plano())
    # leerlo, renombrarlo, deshabilitarlo y eliminarlo no necesitan el contexto
    assert sin_contextos.obtener(texto.id).version.numero == 1
    assert sin_contextos.renombrar(texto.id, "Otro").nombre == "Otro"
    assert sin_contextos.deshabilitar(texto.id).deshabilitado
    sin_contextos.eliminar(texto.id)


def test_versionar_un_deshabilitado_se_rechaza_antes_de_validar_el_contenido() -> None:
    servicio, _ = _servicio()
    texto = servicio.crear(PLANO, "Cobranza", _plano()).texto
    servicio.deshabilitar(texto.id)

    with pytest.raises(TextoDeshabilitado):  # no TextoInvalido, aunque el contenido no valga
        servicio.agregar_version(texto.id, _plano("con !"))


def test_pedir_una_version_que_no_existe() -> None:
    servicio, _ = _servicio()
    texto = servicio.crear(PLANO, "Cobranza", _plano()).texto

    with pytest.raises(VersionDeTextoNoEncontrada):
        servicio.obtener(texto.id, 5)
    with pytest.raises(TextoNoEncontrado):
        servicio.obtener(99)


# --- Renombrar (RF-56) --------------------------------------------------------------------------


def test_renombrar_cambia_solo_el_nombre_y_no_crea_version() -> None:
    servicio, _ = _servicio()
    texto = servicio.crear(PLANO, "Cobranza", _plano()).texto

    renombrado = servicio.renombrar(texto.id, "  Recordatorio ")

    assert renombrado.nombre == "Recordatorio"
    assert renombrado.versiones == texto.versiones
    assert renombrado.actualizado_en > texto.actualizado_en


def test_renombrar_al_mismo_nombre_ni_siquiera_llega_al_repositorio() -> None:
    servicio, repositorio = _servicio()
    texto = servicio.crear(PLANO, "Cobranza", _plano()).texto
    llamadas = []
    repositorio.renombrar = lambda *args: llamadas.append(args)  # type: ignore[method-assign]

    assert servicio.renombrar(texto.id, "  Cobranza ") == texto
    assert llamadas == []


def test_renombrar_al_mismo_nombre_no_cambia_nada_y_a_otro_ya_en_uso_se_rechaza() -> None:
    servicio, _ = _servicio()
    uno = servicio.crear(PLANO, "Uno", _plano()).texto
    servicio.crear(PLANO, "Dos", _plano())

    assert servicio.renombrar(uno.id, "Uno") == uno  # sin error y sin mover actualizado_en
    assert servicio.renombrar(uno.id, "UNO").nombre == "UNO"  # solo la caja si es un cambio
    with pytest.raises(NombreDeTextoRepetido):
        servicio.renombrar(uno.id, " dos ")
    with pytest.raises(TextoInvalido):
        servicio.renombrar(uno.id, "  ")
    with pytest.raises(TextoNoEncontrado):
        servicio.renombrar(99, "Tres")


# --- Deshabilitar -------------------------------------------------------------------------------


def test_un_texto_deshabilitado_deja_de_ofrecerse_pero_se_sigue_leyendo() -> None:
    servicio, _ = _servicio()
    texto = servicio.crear(PLANO, "Cobranza", _plano()).texto
    servicio.crear(PLANO, "Otro", _plano())

    deshabilitado = servicio.deshabilitar(texto.id)

    assert deshabilitado.deshabilitado_en is not None
    assert [r.nombre for r in servicio.listar(PLANO)] == ["Otro"]
    todos = servicio.listar(PLANO, incluir_deshabilitados=True)
    assert [(r.nombre, r.deshabilitado_en is not None) for r in todos] == [
        ("Cobranza", True),
        ("Otro", False),
    ]
    assert servicio.obtener(texto.id).version.contenido == _plano()  # lo que lo uso lo lee


def test_deshabilitar_es_idempotente_y_no_admite_versiones_nuevas() -> None:
    servicio, _ = _servicio()
    texto = servicio.crear(PLANO, "Cobranza", _plano()).texto

    primera = servicio.deshabilitar(texto.id).deshabilitado_en
    segunda = servicio.deshabilitar(texto.id).deshabilitado_en

    assert primera == segunda
    with pytest.raises(TextoDeshabilitado):
        servicio.agregar_version(texto.id, _plano("dos"))
    with pytest.raises(TextoNoEncontrado):
        servicio.deshabilitar(99)


def test_habilitar_vuelve_a_ofrecerlo_y_admite_versiones_otra_vez() -> None:
    servicio, _ = _servicio()
    texto = servicio.crear(PLANO, "Cobranza", _plano()).texto
    servicio.deshabilitar(texto.id)
    assert servicio.listar(PLANO) == []

    habilitado = servicio.habilitar(texto.id)

    assert habilitado.deshabilitado_en is None
    assert [r.nombre for r in servicio.listar(PLANO)] == ["Cobranza"]
    assert servicio.agregar_version(texto.id, _plano("dos")).version.numero == 2


def test_habilitar_uno_habilitado_es_idempotente_y_uno_inexistente_no_existe() -> None:
    servicio, _ = _servicio()
    texto = servicio.crear(PLANO, "Cobranza", _plano()).texto

    assert servicio.habilitar(texto.id) == texto  # sin cambio, ni siquiera actualizado_en
    with pytest.raises(TextoNoEncontrado):
        servicio.habilitar(99)


def test_el_nombre_de_un_deshabilitado_sigue_ocupado() -> None:
    servicio, _ = _servicio()
    texto = servicio.crear(PLANO, "Cobranza", _plano()).texto
    servicio.deshabilitar(texto.id)

    with pytest.raises(NombreDeTextoRepetido):
        servicio.crear(PLANO, "Cobranza", _plano())


# --- Eliminar y usar ----------------------------------------------------------------------------


def test_eliminar_un_texto_sin_versiones_usadas_lo_borra_con_sus_versiones() -> None:
    servicio, repositorio = _servicio()
    texto = servicio.crear(PLANO, "Cobranza", _plano()).texto
    servicio.agregar_version(texto.id, _plano("dos"))

    servicio.eliminar(texto.id)

    assert repositorio.textos == {}
    with pytest.raises(TextoNoEncontrado):
        servicio.eliminar(texto.id)
    assert servicio.crear(PLANO, "Cobranza", _plano()).texto.nombre == "Cobranza"  # nombre libre


def test_con_alguna_version_usada_no_se_elimina_solo_se_deshabilita() -> None:
    servicio, repositorio = _servicio()
    texto = servicio.crear(PLANO, "Cobranza", _plano()).texto
    servicio.agregar_version(texto.id, _plano("dos"))
    servicio.marcar_usada(texto.id, 1)  # la vigente es la 2: basta que se use cualquiera

    with pytest.raises(TextoConVersionesUsadas):
        servicio.eliminar(texto.id)
    assert texto.id in repositorio.textos
    assert servicio.deshabilitar(texto.id).deshabilitado


def test_usada_en_se_marca_la_primera_vez_y_no_cambia_despues() -> None:
    servicio, _ = _servicio()
    texto = servicio.crear(PLANO, "Cobranza", _plano()).texto

    servicio.marcar_usada(texto.id, 1)
    primera = servicio.obtener(texto.id).version.usada_en
    servicio.marcar_usada(texto.id, 1)

    assert primera is not None and servicio.obtener(texto.id).version.usada_en == primera
    with pytest.raises(VersionDeTextoNoEncontrada):
        servicio.marcar_usada(texto.id, 9)


def test_eliminable_es_falso_si_se_uso_cualquier_version_aunque_no_sea_la_vigente() -> None:
    servicio, _ = _servicio()
    vieja = servicio.crear(PLANO, "Vieja usada", _plano()).texto
    servicio.agregar_version(vieja.id, _plano("dos"))
    servicio.marcar_usada(vieja.id, 1)  # la vigente es la 2 y no se uso
    servicio.crear(PLANO, "Sin usar", _plano())

    listado = {r.nombre: r for r in servicio.listar(PLANO)}

    assert (listado["Vieja usada"].vigente_usada, listado["Vieja usada"].eliminable) == (
        False,
        False,
    )
    assert (listado["Sin usar"].vigente_usada, listado["Sin usar"].eliminable) == (False, True)
    with pytest.raises(TextoConVersionesUsadas):  # y es lo que el 409 confirmaria
        servicio.eliminar(vieja.id)


def test_el_listado_trae_lo_necesario_ordenado_por_nombre_y_solo_del_contexto() -> None:
    servicio, _ = _servicio()
    servicio.crear(PLANO, "b segundo", _plano())
    primero = servicio.crear(PLANO, "A primero", _plano()).texto
    servicio.crear(EXPRESION, "ajeno", _expresion())
    servicio.agregar_version(primero.id, _plano("dos"))
    servicio.marcar_usada(primero.id, 2)

    listado = servicio.listar(PLANO)

    assert [
        (r.nombre, r.version_vigente, r.cantidad_versiones, r.vigente_usada) for r in listado
    ] == [
        ("A primero", 2, 2, True),
        ("b segundo", 1, 1, False),
    ]


# --- La API -------------------------------------------------------------------------------------


@pytest.fixture
def cliente():
    registro = _registro()
    servicio = TextosGuardadosService(RepositorioTextosEnMemoria(), registro)
    app.dependency_overrides[obtener_servicio_textos_guardados] = lambda: servicio
    app.dependency_overrides[obtener_registro_contextos_guardados] = lambda: registro
    try:
        yield TestClient(app), servicio
    finally:
        app.dependency_overrides.clear()


def _crear(http, nombre="Cobranza", contexto=PLANO, contenido=None):
    return http.post(
        "/textos-guardados",
        json={"contexto": contexto, "nombre": nombre, "contenido": contenido or _plano()},
    )


def test_el_listado_por_http_dice_si_se_puede_eliminar_con_una_version_vieja_usada(cliente) -> None:
    http, servicio = cliente
    vieja = _crear(http, "Vieja usada").json()["id"]
    http.post(f"/textos-guardados/{vieja}/versiones", json={"contenido": _plano("dos")})
    servicio.marcar_usada(vieja, 1)
    _crear(http, "Sin usar")

    listado = {
        t["nombre"]: t for t in http.get("/textos-guardados", params={"contexto": PLANO}).json()
    }

    assert (listado["Vieja usada"]["vigente_usada"], listado["Vieja usada"]["eliminable"]) == (
        False,
        False,
    )
    assert listado["Sin usar"]["eliminable"] is True
    assert http.delete(f"/textos-guardados/{vieja}").status_code == 409


def test_get_contextos_trae_lo_que_los_modulos_registraron(cliente) -> None:
    http, _ = cliente

    respuesta = http.get("/textos-guardados/contextos")

    assert respuesta.status_code == 200
    assert respuesta.json() == [
        {"clave": PLANO, "etiqueta": "Plano", "tipo": "texto_plano"},
        {"clave": EXPRESION, "etiqueta": "Expresion", "tipo": "expresion"},
    ]


def test_el_ciclo_completo_por_http(cliente) -> None:
    http, _ = cliente

    creado = _crear(http)
    assert creado.status_code == 201
    cuerpo = creado.json()
    id_ = cuerpo["id"]
    assert (cuerpo["contexto"], cuerpo["nombre"], cuerpo["version_vigente"]) == (
        PLANO,
        "Cobranza",
        1,
    )
    assert cuerpo["version"]["contenido"] == _plano() and cuerpo["deshabilitado_en"] is None

    nueva = http.post(f"/textos-guardados/{id_}/versiones", json={"contenido": _plano("dos")})
    assert nueva.status_code == 201 and nueva.json()["version"]["numero"] == 2
    primera = http.get(f"/textos-guardados/{id_}", params={"version": 1}).json()
    assert (primera["version"]["contenido"], primera["version_vigente"]) == (_plano(), 2)
    assert [v["numero"] for v in primera["versiones"]] == [1, 2]

    renombrado = http.patch(f"/textos-guardados/{id_}", json={"nombre": "Recordatorio"})
    assert renombrado.status_code == 200 and renombrado.json()["nombre"] == "Recordatorio"
    assert len(renombrado.json()["versiones"]) == 2  # sin version nueva

    listado = http.get("/textos-guardados", params={"contexto": PLANO}).json()
    assert [(t["nombre"], t["version_vigente"], t["cantidad_versiones"]) for t in listado] == [
        ("Recordatorio", 2, 2)
    ]

    deshabilitado = http.post(f"/textos-guardados/{id_}/deshabilitar")
    assert deshabilitado.status_code == 200 and deshabilitado.json()["deshabilitado_en"]
    assert http.get("/textos-guardados", params={"contexto": PLANO}).json() == []
    con = http.get("/textos-guardados", params={"contexto": PLANO, "deshabilitados": True}).json()
    assert [t["id"] for t in con] == [id_]

    assert http.delete(f"/textos-guardados/{id_}").status_code == 204
    assert http.get(f"/textos-guardados/{id_}").status_code == 404


def test_un_contexto_desconocido_es_400_con_su_codigo(cliente) -> None:
    http, _ = cliente

    creado = _crear(http, contexto="inventado")
    listado = http.get("/textos-guardados", params={"contexto": "inventado"})

    for respuesta in (creado, listado):
        assert respuesta.status_code == 400
        assert respuesta.json()["codigo"] == "contexto_guardado_desconocido"


def test_el_listado_pide_el_contexto(cliente) -> None:
    http, _ = cliente

    assert http.get("/textos-guardados").status_code == 422


def test_un_contenido_invalido_es_400_con_los_problemas_por_campo(cliente) -> None:
    http, _ = cliente

    respuesta = http.post(
        "/textos-guardados", json={"contexto": PLANO, "nombre": " ", "contenido": _plano("con !")}
    )

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "texto_guardado_invalido"
    assert sorted(p["campo"] for p in cuerpo["problemas"]) == ["contenido", "nombre"]
    assert http.get("/textos-guardados", params={"contexto": PLANO}).json() == []


def test_un_contenido_de_expresion_con_una_variable_desconocida_trae_su_ubicacion(cliente) -> None:
    http, _ = cliente
    inventada = {"tipo": "variable", "nombre": "no_existe", "funciones": []}

    respuesta = _crear(http, contexto=EXPRESION, contenido=_expresion(inventada))

    assert respuesta.status_code == 400
    [problema] = respuesta.json()["problemas"]
    assert (problema["codigo"], problema["ubicacion"]["nodo"]) == ("variable_desconocida", 0)


def test_el_nombre_repetido_es_409(cliente) -> None:
    http, _ = cliente
    _crear(http)

    repetido = _crear(http, nombre="  COBRANZA")

    assert repetido.status_code == 409 and repetido.json()["codigo"] == "nombre_repetido"
    otro = _crear(http, nombre="Otro")
    renombrar = http.patch(f"/textos-guardados/{otro.json()['id']}", json={"nombre": "cobranza"})
    assert renombrar.status_code == 409


def test_renombrar_con_un_nombre_invalido_es_400_en_el_campo_nombre(cliente) -> None:
    http, _ = cliente
    id_ = _crear(http).json()["id"]

    respuesta = http.patch(f"/textos-guardados/{id_}", json={"nombre": ""})

    assert respuesta.status_code == 400
    assert [p["campo"] for p in respuesta.json()["problemas"]] == ["nombre"]


def test_un_texto_que_no_existe_es_404_con_su_codigo(cliente) -> None:
    http, _ = cliente

    assert http.get("/textos-guardados/99").json()["codigo"] == "texto_guardado_no_encontrado"
    id_ = _crear(http).json()["id"]
    version = http.get(f"/textos-guardados/{id_}", params={"version": 9})
    assert (version.status_code, version.json()["codigo"]) == (404, "version_no_encontrada")
    for respuesta in (
        http.post("/textos-guardados/99/versiones", json={"contenido": _plano()}),
        http.patch("/textos-guardados/99", json={"nombre": "x"}),
        http.post("/textos-guardados/99/deshabilitar"),
        http.post("/textos-guardados/99/habilitar"),
        http.delete("/textos-guardados/99"),
    ):
        assert respuesta.status_code == 404


def test_deshabilitar_habilitar_y_versionar_por_http(cliente) -> None:
    http, _ = cliente
    id_ = _crear(http).json()["id"]
    http.post(f"/textos-guardados/{id_}/deshabilitar")
    bloqueada = http.post(f"/textos-guardados/{id_}/versiones", json={"contenido": _plano("dos")})
    assert bloqueada.status_code == 409

    habilitado = http.post(f"/textos-guardados/{id_}/habilitar")
    otra_vez = http.post(f"/textos-guardados/{id_}/habilitar")

    assert habilitado.status_code == 200 and habilitado.json()["deshabilitado_en"] is None
    assert otra_vez.status_code == 200 and otra_vez.json() == habilitado.json()
    assert [t["id"] for t in http.get("/textos-guardados", params={"contexto": PLANO}).json()] == [
        id_
    ]
    nueva = http.post(f"/textos-guardados/{id_}/versiones", json={"contenido": _plano("dos")})
    assert nueva.status_code == 201 and nueva.json()["version"]["numero"] == 2


def test_versionar_un_deshabilitado_es_409(cliente) -> None:
    http, _ = cliente
    id_ = _crear(http).json()["id"]
    http.post(f"/textos-guardados/{id_}/deshabilitar")

    respuesta = http.post(f"/textos-guardados/{id_}/versiones", json={"contenido": _plano("dos")})

    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "texto_guardado_deshabilitado"


def test_eliminar_con_una_version_usada_es_409_y_no_borra(cliente) -> None:
    http, servicio = cliente
    id_ = _crear(http).json()["id"]
    servicio.marcar_usada(id_, 1)

    respuesta = http.delete(f"/textos-guardados/{id_}")

    assert respuesta.status_code == 409 and respuesta.json()["codigo"] == "texto_guardado_usado"
    assert http.get(f"/textos-guardados/{id_}").json()["version"]["usada"] is True


# --- Reglas propias del contexto (T-HI-B6) ------------------------------------------------------


def _macro_desconocida(texto: str) -> list[Problema]:
    """Una regla del modulo: solo existen las macros 1 a 3. Lo hace como lo hara WhatsMKT."""
    return [
        Problema(
            CodigoTexto.REGLA_DEL_CONTEXTO,
            f"La macro {macro} no existe",
            codigo_contexto="macro_desconocida",
            parametros={"macro": macro, "maximo": 3},
        )
        for macro in re.findall(r"\[\$MACRO(?:[4-9]|\d\d+)\$\]", texto)
    ]


def test_el_maximo_de_un_texto_plano_puede_ser_una_funcion_que_se_lee_en_cada_validacion() -> None:
    tope = {"valor": 5}
    validar = validador_de_texto_plano(lambda: tope["valor"])

    assert validar(_plano("x" * 5)) == ()
    assert validar(_plano("x" * 6))
    tope["valor"] = 8  # la configuracion cambio: sin reiniciar nada
    assert validar(_plano("x" * 6)) == ()
    assert validar(_plano("x" * 9))


def test_sin_maximo_no_se_mide_el_largo_pero_el_texto_no_puede_estar_vacio() -> None:
    validar = validador_de_texto_plano(None)

    assert validar(_plano("x" * 10_000)) == ()
    assert validar(_plano(""))
    assert validar(_plano("   "))
    assert validar({"texto": 3})


def test_un_maximo_entero_se_comporta_como_siempre() -> None:
    validar = validador_de_texto_plano(20)

    assert validar(_plano("x" * 20)) == ()
    assert [p.codigo for p in validar(_plano("x" * 21))] == [CodigoTexto.TEXTO_GUARDADO_INVALIDO]
    assert [p.codigo for p in validar(_plano(""))] == [CodigoTexto.TEXTO_GUARDADO_INVALIDO]


@pytest.fixture
def cliente_con_reglas():
    registro = RegistroContextosGuardados(
        [
            ContextoGuardado(
                "prueba.reglas",
                "Con reglas",
                TipoContenido.TEXTO_PLANO,
                validador_de_texto_plano(None, _macro_desconocida),
            )
        ]
    )
    servicio = TextosGuardadosService(RepositorioTextosEnMemoria(), registro)
    app.dependency_overrides[obtener_servicio_textos_guardados] = lambda: servicio
    app.dependency_overrides[obtener_registro_contextos_guardados] = lambda: registro
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_una_regla_del_contexto_llega_a_la_api_con_su_codigo_y_sus_parametros(
    cliente_con_reglas,
) -> None:
    respuesta = cliente_con_reglas.post(
        "/textos-guardados",
        json={
            "contexto": "prueba.reglas",
            "nombre": "Mensaje",
            "contenido": _plano("Hola [$MACRO9$]"),
        },
    )

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "texto_guardado_invalido"
    [problema] = cuerpo["problemas"]
    assert problema == {
        "codigo": "regla_del_contexto",
        "detalle": "La macro [$MACRO9$] no existe",
        "ubicacion": None,
        "nombre": None,
        "columna": None,
        "segmento": None,
        "campo": "contenido",
        "codigo_contexto": "macro_desconocida",
        "parametros": {"macro": "[$MACRO9$]", "maximo": 3},
    }


def test_un_texto_que_cumple_las_reglas_del_contexto_se_guarda(cliente_con_reglas) -> None:
    respuesta = cliente_con_reglas.post(
        "/textos-guardados",
        json={
            "contexto": "prueba.reglas",
            "nombre": "Mensaje",
            "contenido": _plano("Hola [$MACRO1$]"),
        },
    )

    assert respuesta.status_code == 201


def test_los_problemas_de_hoy_se_serializan_exactamente_igual_sin_los_campos_nuevos(
    cliente,
) -> None:
    http, _ = cliente

    nombre = http.post(
        "/textos-guardados", json={"contexto": PLANO, "nombre": " ", "contenido": _plano()}
    ).json()["problemas"]
    motor = http.post(
        "/textos-guardados",
        json={
            "contexto": EXPRESION,
            "nombre": "x",
            "contenido": _expresion({"tipo": "variable", "nombre": "no_existe", "funciones": []}),
        },
    ).json()["problemas"]

    assert nombre == [
        {
            "codigo": "texto_guardado_invalido",
            "detalle": "El nombre debe tener entre 1 y 120 caracteres",
            "ubicacion": None,
            "nombre": None,
            "columna": None,
            "segmento": None,
            "campo": "nombre",
        }
    ]
    [problema] = motor
    assert set(problema) == {
        "codigo",
        "detalle",
        "ubicacion",
        "nombre",
        "columna",
        "segmento",
        "campo",
    }  # ni `codigo_contexto` ni `parametros`, ni siquiera en null


def test_los_campos_del_contexto_son_opcionales_en_el_contrato() -> None:
    esquemas = app.openapi()["components"]["schemas"]
    problemas = {n: e for n, e in esquemas.items() if n.startswith("ProblemaTextoRespuesta")}

    assert problemas
    for esquema in problemas.values():
        assert {"codigo_contexto", "parametros"} <= set(esquema["properties"])
        assert not {"codigo_contexto", "parametros"} & set(esquema["required"])
        assert {"codigo", "detalle", "ubicacion", "campo"} <= set(esquema["required"])


# --- La migracion y los nombres (<= 63 caracteres) ----------------------------------------------

BACKEND = Path(__file__).resolve().parents[1]
REVISION_ANTERIOR = "a4d8f2b6c713"
REVISION = "c9e5a1d7b384"
MAXIMO_IDENTIFICADOR = 63


def _configuracion() -> Config:
    configuracion = Config(str(BACKEND / "alembic.ini"))
    configuracion.set_main_option("script_location", str(BACKEND / "migrations"))
    return configuracion


def _sql(subir: bool) -> str:
    configuracion = _configuracion()
    configuracion.output_buffer = io.StringIO()
    if subir:
        command.upgrade(configuracion, f"{REVISION_ANTERIOR}:{REVISION}", sql=True)
    else:
        command.downgrade(configuracion, f"{REVISION}:{REVISION_ANTERIOR}", sql=True)
    return configuracion.output_buffer.getvalue()


def test_la_migracion_cuelga_de_la_anterior_y_el_arbol_tiene_una_sola_cabeza() -> None:
    directorio = ScriptDirectory.from_config(_configuracion())

    assert directorio.get_revision(REVISION).down_revision == REVISION_ANTERIOR
    assert len(directorio.get_heads()) == 1


def test_el_upgrade_crea_las_dos_tablas_con_sus_restricciones() -> None:
    sql = _sql(subir=True)

    for tabla in ("texto_guardado", "texto_guardado_version"):
        assert f"CREATE TABLE {tabla} (" in sql
    assert (
        "uq_texto_guardado_contexto_nombre_normalizado UNIQUE (contexto, nombre_normalizado)" in sql
    )
    assert "uq_texto_guardado_version_texto_id_numero UNIQUE (texto_id, numero)" in sql
    assert "contenido JSONB NOT NULL" in sql
    assert "jsonb_typeof(contenido) = 'object'" in sql
    assert "ON DELETE CASCADE" in sql
    assert "ck_ck_" not in sql  # `op.f`: el nombre ya trae el prefijo de la convencion
    assert "INSERT INTO texto_guardado" not in sql  # no siembra nada


def test_el_downgrade_quita_las_versiones_antes_que_el_texto() -> None:
    sql = _sql(subir=False)

    assert sql.index("DROP TABLE texto_guardado_version;") < sql.index("DROP TABLE texto_guardado;")


def test_ningun_nombre_de_restriccion_de_la_migracion_pasa_de_63_caracteres() -> None:
    fuente = next((BACKEND / "migrations" / "versions").glob(f"{REVISION}_*.py")).read_text("utf-8")

    nombres = re.findall(r'op\.f\(\s*"([^"]+)"', fuente)

    assert len(nombres) >= 9  # la expresion encuentra los nombres
    assert {n: len(n) for n in nombres if len(n) > MAXIMO_IDENTIFICADOR} == {}


def test_ningun_nombre_de_restriccion_ni_de_indice_de_la_metadata_pasa_de_63_caracteres() -> None:
    # TODAS las tablas, no solo las de textos guardados: atrapa tambien lo que venga. Un dialecto
    # sin tope, para ver el nombre completo que arma la convencion antes de que SQLAlchemy lo
    # acorte con un hash.
    dialecto = postgresql.dialect()
    dialecto.max_identifier_length = 1000
    ddl = []
    for tabla in Base.metadata.sorted_tables:
        ddl.append(str(CreateTable(tabla).compile(dialect=dialecto)))
        ddl += [str(CreateIndex(i).compile(dialect=dialecto)) for i in tabla.indexes]

    nombres = [a or b for a, b in re.findall(r"CONSTRAINT (\w+)|INDEX (\w+)", " ".join(ddl))]

    assert len(nombres) > 50  # la expresion encuentra los nombres
    assert "ck_texto_guardado_version_contenido_es_un_objeto" in nombres
    assert {n: len(n) for n in nombres if len(n) > MAXIMO_IDENTIFICADOR} == {}


def test_el_contenido_es_not_null_y_exige_un_objeto_en_el_modelo() -> None:
    tabla = Base.metadata.tables["texto_guardado_version"]
    ddl = str(CreateTable(tabla).compile(dialect=postgresql.dialect()))

    assert tabla.c.contenido.nullable is False
    assert tabla.c.contenido.type.none_as_null is True
    assert "jsonb_typeof(contenido) = 'object'" in ddl
