"""Catalogo `CodigoTexto`: forma que lee la prueba espejo del frontend y codigos emitidos.

La prueba espejo con `frontend/src/i18n/*.json` (`textoEnriquecido.codigo.<codigo>`) esta en
`test_i18n_texto_enriquecido.py`; aqui se fija la forma que necesita (un codigo por linea, `NOMBRE =
"codigo"` y, si hace falta, un comentario al final, igual que `CodigoMowaMes`) y que no haya codigos
muertos: cada uno se emite de verdad, los de la API por la API.
"""

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.calendario import obtener_servicio_calendario
from app.api.cartera import obtener_servicio_cartera
from app.api.definiciones_columnas import obtener_servicio_definiciones
from app.api.selecciones import obtener_servicio_selecciones
from app.api.texto_enriquecido import obtener_constructor_contexto_mensaje_whatsmkt
from app.api.textos_guardados import obtener_servicio_textos_guardados
from app.core.entities import texto_enriquecido as entidades
from app.core.entities.cartera import PaginaCartera, SinVersionVigente
from app.core.entities.mapeo import TipoSalida
from app.core.entities.plataformas import ColumnaFija, ReglasPlataforma
from app.core.entities.selecciones import SeleccionNoEncontrada
from app.core.entities.texto_enriquecido import (
    CodigoTexto,
    Expresion,
    ExpresionInvalida,
    ExpresionNoEscribible,
    LimitesExpresion,
    NodoVariable,
    Problema,
    TipoValor,
)
from app.core.services.calendario.servicio import CalendarioService
from app.core.services.contextos_texto import contexto_cartera
from app.core.services.definiciones_columnas.plataformas import RegistroPlataformas
from app.core.services.definiciones_columnas.servicio import (
    DefinicionesColumnasService,
    DefinicionInvalida,
)
from app.core.services.plataformas.whatsmkt.contexto_texto import contexto_mensaje_texto
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.core.services.texto_enriquecido import evaluador, sintaxis
from app.core.services.textos_guardados.contextos import (
    ContextoGuardado,
    RegistroContextosGuardados,
    TipoContenido,
    validador_de_texto_plano,
)
from app.core.services.textos_guardados.servicio import TextosGuardadosService
from app.main import app
from tests.definiciones_memoria import RepositorioEnMemoria
from tests.test_calendario import RepositorioCalendarioFalso
from tests.textos_memoria import RepositorioTextosEnMemoria

VARIABLES = {
    "t": TipoValor.TEXTO,
    "n": TipoValor.NUMERO,
    "m": TipoValor.NUMERO,
    "f": TipoValor.FECHA,
    "tel": TipoValor.TEXTO,
}


def _bloque_de_codigos() -> list[str]:
    fuente = Path(entidades.__file__).read_text(encoding="utf-8")
    clase = fuente.split("class CodigoTexto(StrEnum):")[1].split("\n\n\n")[0]
    return [linea for linea in clase.splitlines() if re.match(r"^    [A-Z_]+ = ", linea)]


def test_cada_codigo_va_en_su_linea_con_la_forma_nombre_igual_a_codigo() -> None:
    lineas = _bloque_de_codigos()

    assert len(lineas) == len(CodigoTexto)
    for linea in lineas:
        coincidencia = re.fullmatch(r'    ([A-Z_]+) = "([a-z_]+)"(?:  # .+)?', linea)
        assert coincidencia, linea
        assert coincidencia.group(1).lower() == coincidencia.group(2), linea


def _emitidos_por_el_generador() -> set[CodigoTexto]:
    """`sin_segmento` lo emite GeneradorCargas al excluir un producto sin segmento (B2)."""
    from app.core.entities.mapeo import CampoSalida, DefinicionCarga
    from app.core.entities.segmentacion import Segmentacion
    from app.core.services.mapeo_campos.generador import GeneradorCargas

    definicion = DefinicionCarga("d", (CampoSalida("c", "x"),), Segmentacion())
    carga = GeneradorCargas(definicion, {"dias_atraso": "numero"}).generar([{"dias_atraso": 999}])
    return {CodigoTexto(e.codigo) for e in carga.exclusiones}


class _CarteraVacia:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento=0):
        if self.error is not None:
            raise self.error
        return PaginaCartera(total=0, filas=(), limite=limite)


class _SeleccionesVacias:
    def obtener(self, seleccion_id: int):
        raise SeleccionNoEncontrada(seleccion_id)


def _emitidos_por_la_api() -> set[CodigoTexto]:
    """Lo que solo informa la API del motor (B4a): se pide por HTTP, como lo hace la interfaz."""
    cartera = _CarteraVacia()
    definiciones = DefinicionesColumnasService(
        RepositorioEnMemoria(), contexto_cartera(CatalogoCartera())
    )
    app.dependency_overrides[obtener_servicio_cartera] = lambda: cartera
    app.dependency_overrides[obtener_servicio_definiciones] = lambda: definiciones
    app.dependency_overrides[obtener_servicio_selecciones] = lambda: _SeleccionesVacias()
    # El contexto del mensaje de WhatsMKT se arma desde la base: aqui, sin macros y sin base.
    app.dependency_overrides[obtener_constructor_contexto_mensaje_whatsmkt] = lambda: (
        contexto_mensaje_texto
    )
    try:
        return _pedir_a_la_api(TestClient(app), cartera)
    finally:
        for dependencia in (
            obtener_servicio_cartera,
            obtener_servicio_definiciones,
            obtener_servicio_selecciones,
            obtener_constructor_contexto_mensaje_whatsmkt,
        ):
            app.dependency_overrides.pop(dependencia, None)


def _emitidos_por_las_plataformas() -> set[CodigoTexto]:
    """Los codigos de las reglas de una plataforma (RF-72): se guarda contra una sintetica."""
    destino = ColumnaFija(1, "destino", None, TipoSalida.TEXTO)
    canal = ColumnaFija(2, "canal", None, TipoSalida.TEXTO)
    estricta = ReglasPlataforma(
        "estricta", "Estricta", (destino, canal), None, TipoSalida.TEXTO, False
    )
    abierta = ReglasPlataforma("abierta", "Abierta", (destino,), None, TipoSalida.TEXTO)

    def columna(nombre: str, orden: int, tipo: str) -> dict:
        texto = {"tipo": "texto", "valor": "x"}
        return {"nombre": nombre, "orden": orden, "tipo": tipo, "expresion": {"nodos": [texto]}}

    pedidos = [
        ("inventada", [columna("destino", 0, "texto")]),
        (
            "estricta",
            [
                columna("destino", 0, "numero"),
                columna("canal", 1, "texto"),
                columna("x", 2, "texto"),
            ],
        ),
        ("abierta", [columna("destino", 0, "texto"), columna("extra", 1, "numero")]),
        ("abierta", [columna("otra", 0, "texto")]),
        ("abierta", [columna("otra", 0, "texto"), columna("destino", 1, "texto")]),
    ]
    servicio = DefinicionesColumnasService(
        RepositorioEnMemoria(),
        contexto_cartera(CatalogoCartera()),
        RegistroPlataformas([estricta, abierta]),
    )
    emitidos: set[CodigoTexto] = set()
    for plataforma, columnas in pedidos:
        try:
            servicio.crear({"nombre": "n", "plataforma": plataforma, "columnas": columnas})
        except DefinicionInvalida as error:
            emitidos.update(p.problema.codigo for p in error.problemas)
    return emitidos


def _emitidos_por_los_textos_guardados() -> set[CodigoTexto]:
    """Los codigos de los textos guardados (RF-69), pedidos por HTTP a un contexto sintetico."""
    registro = RegistroContextosGuardados(
        [
            ContextoGuardado(
                "prueba", "Prueba", TipoContenido.TEXTO_PLANO, validador_de_texto_plano(20)
            )
        ]
    )
    registro.registrar(
        ContextoGuardado(
            "prueba.reglas",
            "Con reglas",
            TipoContenido.TEXTO_PLANO,
            validador_de_texto_plano(
                None,
                lambda texto: [
                    Problema(
                        CodigoTexto.REGLA_DEL_CONTEXTO,
                        "Una regla del modulo",
                        codigo_contexto="regla_de_prueba",
                        parametros={"valor": 1},
                    )
                ],
            ),
        )
    )
    servicio = TextosGuardadosService(RepositorioTextosEnMemoria(), registro)
    app.dependency_overrides[obtener_servicio_textos_guardados] = lambda: servicio
    emitidos: set[CodigoTexto] = set()
    try:
        http = TestClient(app)
        usado = http.post(
            "/textos-guardados",
            json={"contexto": "prueba", "nombre": "a", "contenido": {"texto": "x"}},
        ).json()["id"]
        deshabilitado = http.post(
            "/textos-guardados",
            json={"contexto": "prueba", "nombre": "b", "contenido": {"texto": "x"}},
        ).json()["id"]
        regla = http.post(
            "/textos-guardados",
            json={"contexto": "prueba.reglas", "nombre": "r", "contenido": {"texto": "x"}},
        ).json()
        servicio.marcar_usada(usado, 1)
        http.post(f"/textos-guardados/{deshabilitado}/deshabilitar")
        respuestas = [
            http.post(
                "/textos-guardados", json={"contexto": "prueba", "nombre": " ", "contenido": {}}
            ),
            http.post(
                "/textos-guardados", json={"contexto": "nada", "nombre": "c", "contenido": {}}
            ),
            http.get("/textos-guardados/999"),
            http.delete(f"/textos-guardados/{usado}"),
            http.post(
                f"/textos-guardados/{deshabilitado}/versiones", json={"contenido": {"texto": "y"}}
            ),
        ]
    finally:
        app.dependency_overrides.pop(obtener_servicio_textos_guardados, None)
    emitidos.update(CodigoTexto(r.json()["codigo"]) for r in respuestas)
    emitidos.update(CodigoTexto(p["codigo"]) for p in regla["problemas"])
    return emitidos


def _emitidos_por_el_calendario() -> set[CodigoTexto]:
    """El N fuera de rango de los proximos dias gestionables (RF-71), pedido por HTTP."""
    servicio = CalendarioService(RepositorioCalendarioFalso())
    app.dependency_overrides[obtener_servicio_calendario] = lambda: servicio
    try:
        respuesta = TestClient(app).get("/calendario/proximos", params={"n": 0})
    finally:
        app.dependency_overrides.pop(obtener_servicio_calendario, None)
    return {CodigoTexto(respuesta.json()["codigo"])}


def _pedir_a_la_api(cliente: TestClient, cartera: _CarteraVacia) -> set[CodigoTexto]:
    emitidos: set[CodigoTexto] = set()
    nodo = {"tipo": "variable", "nombre": "titular", "funciones": []}
    muestra = {"tipo": "producto_real", "fecha_corte": "2026-09-10", "pagare": "x"}
    definicion = {
        "columnas": [{"nombre": "c", "orden": 0, "expresion": {"nodos": [nodo]}, "tipo": "fecha"}]
    }

    def buscar(cuerpo, ruta: str, json: dict) -> None:
        if ruta.startswith("/texto-enriquecido/catalogo"):
            respuesta = cliente.get(ruta)
        else:
            respuesta = cliente.post(ruta, json=json)
        if respuesta.status_code in (400, 404, 409) and "codigo" in respuesta.json():
            emitidos.add(CodigoTexto(respuesta.json()["codigo"]))
            return
        cuerpo(respuesta.json())

    def desde_problemas(cuerpo: dict) -> None:
        for problema in cuerpo["problemas"]:
            emitidos.add(CodigoTexto(problema["codigo"]))
        for fila in cuerpo.get("filas", ()):
            for columna in fila["columnas"]:
                emitidos.update(CodigoTexto(p["codigo"]) for p in columna["problemas"])
        sin_cota = cuerpo.get("sin_cota")
        if sin_cota:
            emitidos.add(CodigoTexto(sin_cota["codigo"]))

    validacion = "/texto-enriquecido/validacion"
    previa = "/texto-enriquecido/previsualizacion"
    for contexto, nodos in [
        ("cartera", [{"tipo": "inventado"}]),  # expresion_invalida
        ("cartera", [nodo]),  # sin_cota_variable
        ("cartera", [{**nodo, "funciones": [{"nombre": "a_texto", "args": []}]}]),
    ]:
        buscar(desde_problemas, validacion, {"contexto": contexto, "expresion": {"nodos": nodos}})
    numero = {
        "tipo": "variable",
        "nombre": "saldo_capital_pendiente",
        "funciones": [{"nombre": "a_texto", "args": []}],
    }  # sin_cota_funcion
    buscar(desde_problemas, validacion, {"contexto": "cartera", "expresion": {"nodos": [numero]}})
    con_funcion = {
        "tipo": "variable",
        "nombre": "whatsapp",
        "funciones": [{"nombre": "a_texto", "args": []}],
    }
    buscar(  # funcion_no_admitida: el mensaje de WhatsMKT no admite funciones (§13.7)
        desde_problemas,
        validacion,
        {"contexto": "whatsmkt.mensaje", "expresion": {"nodos": [con_funcion]}},
    )
    buscar(desde_problemas, previa, {"contexto": "cartera", "definicion": {"columnas": []}})
    buscar(
        desde_problemas,
        previa,
        {"contexto": "cartera", "definicion": definicion, "muestra": {"tipo": "ejemplo"}},
    )  # valor_no_convertible
    buscar(desde_problemas, "/texto-enriquecido/catalogo?contexto=nada", {})
    expresion = {"nodos": [nodo]}
    buscar(  # producto_no_encontrado
        desde_problemas,
        previa,
        {"contexto": "cartera", "expresion": expresion, "muestra": muestra},
    )
    cartera.error = SinVersionVigente(date(2026, 9, 10))
    buscar(  # sin_version_vigente
        desde_problemas,
        previa,
        {"contexto": "cartera", "expresion": expresion, "muestra": muestra},
    )
    cartera.error = None
    buscar(  # seleccion_no_encontrada
        desde_problemas,
        previa,
        {
            "contexto": "cartera",
            "expresion": expresion,
            "muestra": {
                "tipo": "primeros_de_seleccion",
                "fecha_corte": "2026-09-10",
                "seleccion_id": 99,
            },
        },
    )
    buscar(  # fecha_envio_anterior
        desde_problemas,
        previa,
        {
            "contexto": "cartera",
            "expresion": expresion,
            "muestra": {**muestra, "fecha_envio": "2026-09-09"},
        },
    )
    guardada = {"nombre": "Una", "columnas": [{"nombre": "a", "orden": 0, "expresion": expresion}]}
    cliente.post("/definiciones-columnas", json=guardada)
    buscar(desde_problemas, "/definiciones-columnas", guardada)  # nombre_repetido
    buscar(
        desde_problemas, "/definiciones-columnas/999/versiones", guardada
    )  # definicion_no_encontrada
    respuesta = cliente.get(
        "/definiciones-columnas/1", params={"version": 9}
    )  # version_no_encontrada
    emitidos.add(CodigoTexto(respuesta.json()["codigo"]))
    return emitidos


def _emitidos() -> set[CodigoTexto]:
    emitidos: set[CodigoTexto] = set()

    def compilando(plantilla: str, limites: LimitesExpresion | None = None) -> None:
        try:
            evaluador.compilar_texto(plantilla, VARIABLES, *([limites] if limites else []))
        except ExpresionInvalida as error:
            emitidos.update(p.codigo for p in error.problemas)

    def evaluando(plantilla: str, **producto) -> None:
        resultado = evaluador.compilar_texto(plantilla, VARIABLES).evaluar(producto)
        emitidos.update(p.codigo for p in resultado.problemas)

    for plantilla in ["[@t", "[@]", "[@nada]", "[@t | nada]", "[@t | primeros(0)]"]:
        compilando(plantilla)
    compilando('[@t | formato_fecha("dd")]')
    compilando("[@t][@t]", LimitesExpresion(nodos=1))
    try:
        sintaxis.escribir(Expresion((NodoVariable("con espacio"),)))
    except ExpresionNoEscribible as error:
        emitidos.add(error.problema.codigo)
    obligatoria = evaluador.compilar(Expresion((NodoVariable("t", obligatoria=True),)), VARIABLES)
    emitidos.update(p.codigo for p in obligatoria.evaluar({}).problemas)
    evaluando("[@n | sumar(@m)]", n=Decimal(1), m=None)
    evaluando("[@n | dividir(0)]", n=Decimal(1))
    evaluando("[@t | a_numero]", t="x")
    evaluando('[@t | a_fecha("dd/mm/aaaa")]', t="x")
    evaluando("[@tel | enlace_whatsapp]", tel="1")
    evaluando("[@f | sumar_dias(1)]", f=date(9999, 12, 31))
    emitidos.update(_emitidos_por_el_generador())
    emitidos.update(_emitidos_por_la_api())
    emitidos.update(_emitidos_por_las_plataformas())
    emitidos.update(_emitidos_por_los_textos_guardados())
    emitidos.update(_emitidos_por_el_calendario())
    return emitidos


def test_todos_los_codigos_del_catalogo_se_emiten_y_ninguno_sobra() -> None:
    assert _emitidos() == set(CodigoTexto)
