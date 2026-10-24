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

from app.api.cartera import obtener_servicio_cartera
from app.api.definiciones_columnas import obtener_servicio_definiciones
from app.api.selecciones import obtener_servicio_selecciones
from app.core.entities import texto_enriquecido as entidades
from app.core.entities.cartera import PaginaCartera, SinVersionVigente
from app.core.entities.selecciones import SeleccionNoEncontrada
from app.core.entities.texto_enriquecido import (
    CodigoTexto,
    Expresion,
    ExpresionInvalida,
    ExpresionNoEscribible,
    LimitesExpresion,
    NodoVariable,
    TipoValor,
)
from app.core.services.contextos_texto import contexto_cartera
from app.core.services.definiciones_columnas.servicio import DefinicionesColumnasService
from app.core.services.texto_enriquecido import evaluador, sintaxis
from app.main import app
from tests.definiciones_memoria import RepositorioEnMemoria

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
    definiciones = DefinicionesColumnasService(RepositorioEnMemoria(), contexto_cartera())
    app.dependency_overrides[obtener_servicio_cartera] = lambda: cartera
    app.dependency_overrides[obtener_servicio_definiciones] = lambda: definiciones
    app.dependency_overrides[obtener_servicio_selecciones] = lambda: _SeleccionesVacias()
    try:
        return _pedir_a_la_api(TestClient(app), cartera)
    finally:
        for dependencia in (
            obtener_servicio_cartera,
            obtener_servicio_definiciones,
            obtener_servicio_selecciones,
        ):
            app.dependency_overrides.pop(dependencia, None)


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
    return emitidos


def test_todos_los_codigos_del_catalogo_se_emiten_y_ninguno_sobra() -> None:
    assert _emitidos() == set(CodigoTexto)
