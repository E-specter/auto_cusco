"""Catalogo `CodigoTexto`: forma que lee la prueba espejo del frontend y codigos emitidos.

La prueba espejo con `frontend/src/i18n/*.json` (`textoEnriquecido.codigo.<codigo>`) llega con el
contrato de la API (B4a); aqui se fija la forma que necesita (un codigo por linea, `NOMBRE =
"codigo"`, igual que `CodigoMowaMes`) y que no haya codigos muertos.
"""

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.core.entities import texto_enriquecido as entidades
from app.core.entities.texto_enriquecido import (
    CodigoTexto,
    Expresion,
    ExpresionInvalida,
    ExpresionNoEscribible,
    LimitesExpresion,
    NodoVariable,
    TipoValor,
)
from app.core.services.texto_enriquecido import evaluador, sintaxis

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
        coincidencia = re.fullmatch(r'    ([A-Z_]+) = "([a-z_]+)"', linea)
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
    return emitidos


def test_todos_los_codigos_del_catalogo_se_emiten_y_ninguno_sobra() -> None:
    assert _emitidos() == set(CodigoTexto)
