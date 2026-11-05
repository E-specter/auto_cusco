"""El contexto `whatsmkt.mensaje` del motor de texto enriquecido, sin base (T-WM-B9; RF-WM-45).

El contexto sale de la definicion por defecto y del tope de la configuracion, por peticion. Sin
funciones hasta la fase B (§13.7 del motor): una variable con funcion es `funcion_no_admitida`.
Datos sinteticos; el telefono del ejemplo es del rango 900000xxx.
"""

from dataclasses import replace
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.texto_enriquecido import obtener_registro_contextos, registro_de_contextos
from app.core.entities.contexto_texto import TemaVariable
from app.core.entities.definiciones_columnas import DefinicionGuardada, VersionDefinicion
from app.core.entities.mapeo import CampoSalida, DefinicionCarga
from app.core.entities.texto_enriquecido import CodigoTexto, Expresion, NodoTexto, TipoValor
from app.core.services.contextos_texto import ContextoDisponible
from app.core.services.mapeo_campos.serializacion import DefinicionLeida, definicion_a_dict
from app.core.services.plataformas.whatsmkt import mensaje
from app.core.services.plataformas.whatsmkt.contexto_texto import (
    ConstructorContextoMensaje,
    contexto_mensaje_texto,
)
from app.core.services.previsualizar_texto import MuestraEjemplo, PrevisualizacionTextoService
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.main import app
from tests.ayudas.previa_whatsmkt_falsos import RepositorioWhatsmktFalso

AHORA = datetime(2026, 11, 5, 10, 0)
NOMBRE = "whatsmkt.mensaje"


def _texto(valor: str) -> dict:
    return {"tipo": "texto", "valor": valor}


def _variable(nombre: str, *funciones: dict) -> dict:
    return {"tipo": "variable", "nombre": nombre, "funciones": list(funciones)}


def _funcion(nombre: str, *args) -> dict:
    return {"nombre": nombre, "args": list(args)}


def _expresion(*nodos: dict) -> dict:
    return {"nodos": list(nodos)}


def _definicion(id_: int, *etiquetas: str | None) -> DefinicionGuardada:
    """`número` y una columna de macro por etiqueta, en la forma JSON que se guarda."""
    campos = (
        CampoSalida(nombre="número", plantilla="", expresion=Expresion((NodoTexto("x"),))),
    ) + tuple(
        CampoSalida(
            nombre=f"[$MARCRO{n}$]",
            plantilla="",
            expresion=Expresion((NodoTexto("x"),)),
            etiqueta=e,
        )
        for n, e in enumerate(etiquetas, 1)
    )
    posiciones = tuple(range(len(campos)))
    contenido = definicion_a_dict(
        DefinicionLeida(DefinicionCarga("WhatsMKT", campos), posiciones, posiciones),
        con_nombre=False,
    )
    version = VersionDefinicion(1, contenido, None, AHORA)
    return DefinicionGuardada(id_, "WhatsMKT", AHORA, AHORA, (version,), "whatsmkt")


class DefinicionesFalsas:
    def __init__(self, *guardadas: DefinicionGuardada) -> None:
        self.guardadas = {g.id: g for g in guardadas}

    def obtener(self, definicion_id: int):
        return self.guardadas.get(definicion_id)


def _constructor(definiciones: DefinicionesFalsas, **configuracion) -> ConstructorContextoMensaje:
    repositorio = RepositorioWhatsmktFalso()
    repositorio.configuracion = replace(repositorio.configuracion, **configuracion)
    return ConstructorContextoMensaje(repositorio, definiciones)


# --- Las variables ----------------------------------------------------------------------------


def test_sin_macros_el_contexto_solo_ofrece_el_enlace_de_whatsapp() -> None:
    contexto = contexto_mensaje_texto()

    assert [v.nombre for v in contexto.variables] == ["whatsapp"]
    assert set(contexto.ejemplo) == {"whatsapp"}


def test_una_macro_con_etiqueta_se_llama_macro1_y_se_muestra_con_ella() -> None:
    contexto = contexto_mensaje_texto(("Nombres del titular",))

    macro, whatsapp = contexto.variables
    assert (macro.nombre, macro.tipo, macro.etiqueta) == (
        "macro1",
        TipoValor.TEXTO,
        "MACRO1 · Nombres del titular",
    )
    assert whatsapp.nombre == "whatsapp"
    assert contexto.tipos == {"macro1": TipoValor.TEXTO, "whatsapp": TipoValor.TEXTO}


def test_tres_macros_con_y_sin_etiqueta() -> None:
    contexto = contexto_mensaje_texto(("Nombres del titular", None, "Vencimiento de la cuota"))

    assert [(v.nombre, v.etiqueta) for v in contexto.variables[:3]] == [
        ("macro1", "MACRO1 · Nombres del titular"),
        ("macro2", "MACRO2"),  # sin etiqueta, solo el numero
        ("macro3", "MACRO3 · Vencimiento de la cuota"),
    ]
    assert contexto.variables[-1].nombre == "whatsapp"


def test_una_etiqueta_vacia_se_trata_como_sin_etiqueta() -> None:
    assert contexto_mensaje_texto(("",)).variables[0].etiqueta == "MACRO1"


def test_el_ejemplo_de_cada_macro_es_su_marcador_literal() -> None:
    contexto = contexto_mensaje_texto(("A", "B", "C"))

    assert [contexto.ejemplo[f"macro{n}"] for n in (1, 2, 3)] == [
        "[$MACRO1$]",
        "[$MACRO2$]",
        "[$MACRO3$]",
    ]


def test_el_ejemplo_de_whatsapp_es_un_enlace_sintetico_de_26_caracteres() -> None:
    ejemplo = contexto_mensaje_texto().ejemplo["whatsapp"]

    assert ejemplo == "https://wa.me/+51900000000"
    assert len(ejemplo) == 26 == mensaje.largo_del_mensaje("[whatsapp]")


def test_las_macros_van_en_el_tema_columnas_del_archivo_y_whatsapp_en_persona() -> None:
    contexto = contexto_mensaje_texto(("A", None))

    assert [v.tema for v in contexto.variables] == [
        TemaVariable.ARCHIVO,
        TemaVariable.ARCHIVO,
        TemaVariable.PERSONA,
    ]


def test_whatsapp_es_texto_con_su_clave_y_su_tema() -> None:
    whatsapp = contexto_mensaje_texto().variables[-1]

    assert whatsapp.tipo is TipoValor.TEXTO
    assert whatsapp.clave_nombre == "textoEnriquecido.variable.whatsapp"
    assert whatsapp.tema is TemaVariable.PERSONA
    assert not whatsapp.adicional and not whatsapp.archivado


# --- Los limites del contexto -----------------------------------------------------------------


def test_el_limite_es_el_tope_de_la_configuracion_y_no_hay_umbral_de_advertencia() -> None:
    contexto = contexto_mensaje_texto(("A",), tope=500)

    assert contexto.limite_largo == 500
    assert contexto.umbral_advertencia is None  # WhatsMKT no muestra «Cerca del tope»
    assert contexto.nombre == NOMBRE
    assert contexto.clave_nombre == "textoEnriquecido.contexto.whatsmkt.mensaje"
    assert contexto.clave_alcance == "textoEnriquecido.alcance.whatsmkt.mensaje"
    assert contexto.admite_funciones is False


# --- Armado por peticion desde la configuracion -----------------------------------------------


def test_el_contexto_se_arma_con_las_etiquetas_de_la_definicion_por_defecto_y_el_tope() -> None:
    definiciones = DefinicionesFalsas(_definicion(7, "Nombres del titular", None))

    contexto = _constructor(definiciones, definicion_defecto_id=7, tope_mensaje=300)()

    assert [(v.nombre, v.etiqueta) for v in contexto.variables[:2]] == [
        ("macro1", "MACRO1 · Nombres del titular"),
        ("macro2", "MACRO2"),
    ]
    assert contexto.limite_largo == 300


def test_si_cambia_la_definicion_cambia_el_contexto_en_la_siguiente_peticion() -> None:
    definiciones = DefinicionesFalsas(_definicion(7, "A"))
    constructor = _constructor(definiciones, definicion_defecto_id=7)
    antes = constructor()

    definiciones.guardadas[7] = _definicion(7, "A", "B", "C")
    despues = constructor()

    assert [v.nombre for v in antes.variables] == ["macro1", "whatsapp"]
    assert [v.nombre for v in despues.variables] == ["macro1", "macro2", "macro3", "whatsapp"]


def test_si_cambia_el_tope_cambia_el_limite() -> None:
    repositorio = RepositorioWhatsmktFalso()
    constructor = ConstructorContextoMensaje(repositorio, DefinicionesFalsas())
    antes = constructor().limite_largo

    repositorio.configuracion = replace(repositorio.configuracion, tope_mensaje=123)

    assert (antes, constructor().limite_largo) == (4096, 123)


def test_sin_definicion_por_defecto_no_hay_macros_y_no_falla() -> None:
    contexto = _constructor(DefinicionesFalsas(_definicion(7, "A")), definicion_defecto_id=None)()

    assert [v.nombre for v in contexto.variables] == ["whatsapp"]


def test_con_una_definicion_que_ya_no_existe_no_hay_macros_y_no_falla() -> None:
    contexto = _constructor(DefinicionesFalsas(), definicion_defecto_id=99)()

    assert [v.nombre for v in contexto.variables] == ["whatsapp"]


def test_con_una_definicion_que_no_se_lee_no_hay_macros_y_no_falla() -> None:
    rota = replace(
        _definicion(7, "A"),
        versiones=(VersionDefinicion(1, {"columnas": "no es una lista"}, None, AHORA),),
    )

    contexto = _constructor(DefinicionesFalsas(rota), definicion_defecto_id=7)()

    assert [v.nombre for v in contexto.variables] == ["whatsapp"]


# --- El registro y el catalogo ----------------------------------------------------------------


def test_el_registro_ofrece_el_contexto_del_mensaje_aunque_no_se_arme_con_la_configuracion() -> (
    None
):
    registro = registro_de_contextos(CatalogoCartera())

    assert [c.nombre for c in registro.disponibles()] == ["cartera", "mowa_mes.speech", NOMBRE]
    assert [v.nombre for v in registro.obtener(NOMBRE).variables] == ["whatsapp"]


def test_el_registro_usa_el_contexto_armado_por_peticion() -> None:
    contexto = contexto_mensaje_texto(("Nombres del titular",), tope=77)

    registro = registro_de_contextos(CatalogoCartera(), lambda: contexto)

    assert registro.obtener(NOMBRE) is contexto


def test_solo_el_mensaje_de_whatsmkt_deja_de_admitir_funciones() -> None:
    admiten = {
        c.nombre: c.admite_funciones for c in registro_de_contextos(CatalogoCartera()).disponibles()
    }

    assert admiten == {"cartera": True, "mowa_mes.speech": True, NOMBRE: False}


@pytest.fixture
def cliente():
    contexto = contexto_mensaje_texto(("Nombres del titular", "Vencimiento"), tope=500)
    app.dependency_overrides[obtener_registro_contextos] = lambda: registro_de_contextos(
        CatalogoCartera(), lambda: contexto
    )
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_el_catalogo_por_la_api_trae_el_contexto_con_sus_macros_y_sin_funciones(cliente) -> None:
    respuesta = cliente.get("/texto-enriquecido/catalogo", params={"contexto": NOMBRE})

    assert respuesta.status_code == 200
    contexto = respuesta.json()["contexto"]
    assert contexto["nombre"] == NOMBRE
    assert contexto["admite_funciones"] is False
    assert (contexto["limite_largo"], contexto["umbral_advertencia"]) == (500, None)
    assert contexto["clave_alcance"] == "textoEnriquecido.alcance.whatsmkt.mensaje"
    assert [(v["nombre"], v["tipo"], v["etiqueta"]) for v in contexto["variables"]] == [
        ("macro1", "texto", "MACRO1 · Nombres del titular"),
        ("macro2", "texto", "MACRO2 · Vencimiento"),
        ("whatsapp", "texto", None),
    ]
    assert contexto["ejemplo"] == {
        "macro1": "[$MACRO1$]",
        "macro2": "[$MACRO2$]",
        "whatsapp": "https://wa.me/+51900000000",
    }
    assert {c["nombre"] for c in respuesta.json()["contextos"]} >= {NOMBRE}


@pytest.mark.parametrize("contexto", ["cartera", "mowa_mes.speech"])
def test_el_catalogo_de_los_demas_contextos_sigue_admitiendo_funciones(cliente, contexto) -> None:
    respuesta = cliente.get("/texto-enriquecido/catalogo", params={"contexto": contexto})

    assert respuesta.json()["contexto"]["admite_funciones"] is True


# --- Perezoso: solo se consulta a WhatsMKT cuando se pide ese contexto -------------------------


class WhatsmktContado(RepositorioWhatsmktFalso):
    """Cuenta las lecturas de la configuracion: lo que el contexto del mensaje le pide a la base."""

    def __init__(self) -> None:
        super().__init__()
        self.lecturas = 0

    def obtener_configuracion(self):
        self.lecturas += 1
        return super().obtener_configuracion()


class WhatsmktCaido(RepositorioWhatsmktFalso):
    def obtener_configuracion(self):
        raise SQLAlchemyError("sin conexion")


def _es_el_500_normal_de_la_api(respuesta) -> None:
    """Un fallo de la base sale como todo 500 de la API: el cliente lo lee como cualquier respuesta
    no exitosa y el editor muestra su aviso. Aqui solo se fija el estado y que no traiga un
    catalogo; el cuerpo de los 500 no es de WhatsMKT."""
    assert respuesta.status_code == 500
    assert "variables" not in respuesta.text  # ni un catalogo a medias


def _con_constructor(constructor, **opciones) -> TestClient:
    app.dependency_overrides[obtener_registro_contextos] = lambda: registro_de_contextos(
        CatalogoCartera(), constructor
    )
    return TestClient(app, **opciones)


@pytest.fixture
def limpia():
    yield
    app.dependency_overrides.clear()


def test_listar_los_contextos_no_arma_el_del_mensaje(limpia) -> None:
    repositorio = WhatsmktContado()
    registro = registro_de_contextos(
        CatalogoCartera(), ConstructorContextoMensaje(repositorio, DefinicionesFalsas())
    )

    assert registro.listado() == (
        ContextoDisponible("cartera", "textoEnriquecido.contexto.cartera"),
        ContextoDisponible("mowa_mes.speech", "textoEnriquecido.contexto.mowa_mes.speech"),
        ContextoDisponible(NOMBRE, "textoEnriquecido.contexto.whatsmkt.mensaje"),
    )
    assert repositorio.lecturas == 0


def test_los_otros_contextos_no_consultan_a_whatsmkt(limpia) -> None:
    repositorio = WhatsmktContado()
    cliente = _con_constructor(ConstructorContextoMensaje(repositorio, DefinicionesFalsas()))
    expresion = _expresion(_variable("titular"))

    for contexto in ("cartera", "mowa_mes.speech"):
        catalogo = cliente.get("/texto-enriquecido/catalogo", params={"contexto": contexto})
        validacion = cliente.post(
            "/texto-enriquecido/validacion", json={"contexto": contexto, "expresion": expresion}
        )
        previa = cliente.post(
            "/texto-enriquecido/previsualizacion",
            json={"contexto": contexto, "expresion": expresion},
        )
        assert (catalogo.status_code, validacion.status_code, previa.status_code) == (200, 200, 200)

    # El catalogo lista tambien el del mensaje, sin armarlo.
    nombres = [c["nombre"] for c in catalogo.json()["contextos"]]
    assert nombres == ["cartera", "mowa_mes.speech", NOMBRE]
    assert repositorio.lecturas == 0


def test_pedir_el_contexto_del_mensaje_si_consulta_la_configuracion(limpia) -> None:
    repositorio = WhatsmktContado()
    cliente = _con_constructor(ConstructorContextoMensaje(repositorio, DefinicionesFalsas()))

    respuesta = cliente.get("/texto-enriquecido/catalogo", params={"contexto": NOMBRE})

    assert respuesta.status_code == 200
    assert repositorio.lecturas == 1


def test_un_fallo_de_la_base_no_se_disimula_el_catalogo_del_mensaje_falla(limpia) -> None:
    constructor = ConstructorContextoMensaje(WhatsmktCaido(), DefinicionesFalsas())
    cliente = _con_constructor(constructor, raise_server_exceptions=False)

    respuesta = cliente.get("/texto-enriquecido/catalogo", params={"contexto": NOMBRE})

    assert respuesta.status_code == 500  # y no un 200 con un editor sin macros
    _es_el_500_normal_de_la_api(respuesta)
    with pytest.raises(SQLAlchemyError):
        registro_de_contextos(CatalogoCartera(), constructor).obtener(NOMBRE)


def test_un_fallo_de_la_base_tampoco_se_disimula_al_validar_el_mensaje(limpia) -> None:
    constructor = ConstructorContextoMensaje(WhatsmktCaido(), DefinicionesFalsas())
    cliente = _con_constructor(constructor, raise_server_exceptions=False)

    respuesta = cliente.post(
        "/texto-enriquecido/validacion",
        json={"contexto": NOMBRE, "expresion": _expresion(_variable("whatsapp"))},
    )

    assert respuesta.status_code == 500
    _es_el_500_normal_de_la_api(respuesta)


# --- El largo del editor es el del mensaje ----------------------------------------------------


def _servicio(*etiquetas: str | None) -> PrevisualizacionTextoService:
    registro = registro_de_contextos(CatalogoCartera(), lambda: contexto_mensaje_texto(etiquetas))
    return PrevisualizacionTextoService(registro)


def test_el_largo_del_editor_con_whatsapp_es_el_largo_del_mensaje() -> None:
    guardado = "Hola [$MACRO1$], tu pagare vence. Escribenos por [whatsapp] o llama."
    expresion = _expresion(
        _texto("Hola "),
        _variable("macro1"),
        _texto(", tu pagare vence. Escribenos por "),
        _variable("whatsapp"),
        _texto(" o llama."),
    )

    previa = _servicio("Nombres del titular").previsualizar(NOMBRE, MuestraEjemplo(), expresion)

    columna = previa.filas[0].columnas[0]
    assert columna.largo == mensaje.largo_del_mensaje(guardado)
    assert columna.texto == guardado.replace("[whatsapp]", "https://wa.me/+51900000000")
    assert (previa.limite_largo, previa.umbral_advertencia) == (4096, None)


# --- Sin funciones ----------------------------------------------------------------------------

CON_FUNCION = _expresion(
    _texto("Hola "), _variable("macro1"), _texto(" "), _variable("macro1", _funcion("primeros", 3))
)


def test_una_funcion_en_el_mensaje_es_funcion_no_admitida_ubicada_en_su_nodo_y_su_funcion() -> None:
    validacion = _servicio("Nombres del titular").validar(NOMBRE, CON_FUNCION)

    [problema] = validacion.problemas
    assert problema.codigo is CodigoTexto.FUNCION_NO_ADMITIDA
    assert (problema.nodo, problema.funcion, problema.nombre) == (3, 0, "primeros")
    assert (validacion.tipo, validacion.cota, validacion.variables) == (None, None, ())


def test_cada_funcion_de_la_cadena_es_su_propio_problema() -> None:
    expresion = _expresion(
        _variable("macro1", _funcion("primeros", 3), _funcion("primeros", 2)), _variable("whatsapp")
    )

    validacion = _servicio("A").validar(NOMBRE, expresion)

    assert [(p.nodo, p.funcion) for p in validacion.problemas] == [(0, 0), (0, 1)]


def test_la_previsualizacion_tambien_rechaza_la_funcion_con_su_ubicacion() -> None:
    previa = _servicio("Nombres del titular").previsualizar(NOMBRE, MuestraEjemplo(), CON_FUNCION)

    assert previa.filas == ()
    [rechazo] = previa.problemas
    assert rechazo.problema.codigo is CodigoTexto.FUNCION_NO_ADMITIDA
    assert (rechazo.problema.nodo, rechazo.problema.funcion) == (3, 0)
    assert rechazo.columna is None  # una expresion suelta no tiene columnas


def test_sin_funciones_el_mensaje_es_valido() -> None:
    validacion = _servicio("A").validar(
        NOMBRE, _expresion(_texto("Hola "), _variable("macro1"), _variable("whatsapp"))
    )

    assert validacion.problemas == ()
    assert validacion.tipo is TipoValor.TEXTO


@pytest.mark.parametrize("contexto", ["cartera", "mowa_mes.speech"])
def test_los_demas_contextos_siguen_admitiendo_funciones(contexto) -> None:
    servicio = PrevisualizacionTextoService(registro_de_contextos(CatalogoCartera()))
    expresion = _expresion(_variable("titular", _funcion("primeros", 3)))

    validacion = servicio.validar(contexto, expresion)
    previa = servicio.previsualizar(contexto, MuestraEjemplo(), expresion)

    assert validacion.problemas == ()
    assert all(p.problema.codigo is not CodigoTexto.FUNCION_NO_ADMITIDA for p in previa.problemas)
    assert previa.filas  # se evaluo: hay filas


def test_la_api_valida_y_previsualiza_con_funcion_no_admitida(cliente) -> None:
    validacion = cliente.post(
        "/texto-enriquecido/validacion", json={"contexto": NOMBRE, "expresion": CON_FUNCION}
    )
    previa = cliente.post(
        "/texto-enriquecido/previsualizacion", json={"contexto": NOMBRE, "expresion": CON_FUNCION}
    )

    assert validacion.status_code == previa.status_code == 200
    for problemas in (validacion.json()["problemas"], previa.json()["problemas"]):
        [problema] = problemas
        assert problema["codigo"] == "funcion_no_admitida"
        assert problema["ubicacion"] == {"nodo": 3, "funcion": 0, "parametro": None}
        assert problema["nombre"] == "primeros"
    assert previa.json()["filas"] == []
