"""RF-54: toda plantilla `[@campo]` de hoy, pasada por el motor, da el texto de `aplicar`.

Las plantillas no se copian aqui: se leen de las pruebas de RF-12 que ya existen
(`test_mapeo_plantillas.py`, `test_mapeo_generador.py`, `test_generacion_cargas*.py`), asi
una plantilla nueva en esos archivos entra sola en esta comparacion. Si dejaran de
encontrarse, la prueba falla con un mensaje en lugar de pasar en verde vacia.

Se comparan tambien las que hoy se rechazan: el motor las rechaza igual.
"""

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.entities.cartera import TipoDato
from app.core.entities.mapeo import PlantillaInvalida
from app.core.entities.texto_enriquecido import ExpresionInvalida
from app.core.services.mapeo_campos import plantillas
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.core.services.texto_enriquecido import evaluador
from app.core.services.texto_enriquecido.tipos import variables_desde_campos

CAMPOS_CARTERA = CatalogoCartera().tipos()  # la base: sin campos adicionales

CARPETA = Path(__file__).resolve().parent
ARCHIVOS = (
    "test_mapeo_plantillas.py",
    "test_mapeo_generador.py",
    "test_generacion_cargas.py",
    "test_generacion_cargas_postgres.py",
    "test_api_archivos_carga.py",
)
DISPONIBLES = tuple(CAMPOS_CARTERA)
VARIABLES = variables_desde_campos(CAMPOS_CARTERA)


def _constante(nodo: ast.AST) -> str | None:
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return nodo.value
    return None


def _plantillas_de(ruta: Path) -> set[str]:
    encontradas: set[str] = set()
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.keyword) and nodo.arg == "plantilla":
            if (valor := _constante(nodo.value)) is not None:
                encontradas.add(valor)
        elif isinstance(nodo, ast.Dict):
            for clave, valor in zip(nodo.keys, nodo.values, strict=True):
                if clave is not None and _constante(clave) == "plantilla":
                    if (texto := _constante(valor)) is not None:
                        encontradas.add(texto)
        elif isinstance(nodo, ast.Call):
            nombre = (
                nodo.func.id if isinstance(nodo.func, ast.Name) else getattr(nodo.func, "attr", "")
            )
            if nombre in ("_compilar", "compilar") and nodo.args:
                if (texto := _constante(nodo.args[0])) is not None:
                    encontradas.add(texto)
        elif isinstance(nodo, ast.FunctionDef):
            encontradas |= _plantillas_de_parametrize(nodo)
    return encontradas


def _plantillas_de_parametrize(funcion: ast.FunctionDef) -> set[str]:
    encontradas: set[str] = set()
    for decorador in funcion.decorator_list:
        if not (
            isinstance(decorador, ast.Call) and getattr(decorador.func, "attr", "") == "parametrize"
        ):
            continue
        nombres, casos = decorador.args[0], decorador.args[1]
        if isinstance(nombres, ast.Tuple):
            posiciones = [_constante(n) for n in nombres.elts]
        else:
            posiciones = [_constante(nombres)]
        if "plantilla" not in posiciones or not isinstance(casos, (ast.List, ast.Tuple)):
            continue
        indice = posiciones.index("plantilla")
        for caso in casos.elts:
            if isinstance(caso, ast.Tuple):
                caso = caso.elts[indice]
            if (texto := _constante(caso)) is not None:
                encontradas.add(texto)
    return encontradas


def _todas_las_plantillas() -> list[str]:
    encontradas: set[str] = set()
    for nombre in ARCHIVOS:
        ruta = CARPETA / nombre
        assert ruta.exists(), f"No se encontro {ruta}: RF-54 se comprueba contra sus plantillas"
        encontradas |= _plantillas_de(ruta)
    return sorted(encontradas)


PLANTILLAS_DE_LAS_PRUEBAS = _todas_las_plantillas()

# Casos de RF-12 que ninguna prueba actual nombra, pero que hoy tienen un significado.
PLANTILLAS_ADICIONALES = [
    "[@ telefono ]",
    "[@\ttelefono\n]",
    "C:\\[@telefono]",
    "[@telefono]]",
    "[ [@telefono] ]",
    "@[@telefono]@",
    "[@telefono][@telefono]",
    "línea 1\nlínea 2 [@titular] ñ",
    "[@fecha_vencimiento_cuota][@monto_cuota]",
    "[@saldo_capital_pendiente] al [@fecha_vencimiento_cuota]",
    "[@dias_atraso]",
    # se rechazan hoy
    "[@ ]",
    "[@",
    "[@telefono",
    "[@a[@b]",
    "[@telefono[",
    "[@telefono] [@",
    "[@telefono.] ",
    "[@TELEFONO]",
    "[@no existe]",
]

TODAS = [*PLANTILLAS_DE_LAS_PRUEBAS, *PLANTILLAS_ADICIONALES]


def _valor_de_ejemplo(tipo: TipoDato, variante: str):
    if variante == "vacio":
        return None
    if variante == "en_blanco":
        return "  " if tipo is TipoDato.TEXTO else None
    if variante == "enteros":
        return {
            TipoDato.TEXTO: "0123",
            TipoDato.NUMERO: 7,
            TipoDato.FECHA: date(2027, 1, 31),
            TipoDato.BOOLEANO: False,
        }[tipo]
    return {
        TipoDato.TEXTO: 'Ñandú [x] ] | "q"',
        TipoDato.NUMERO: Decimal("1500.50"),
        TipoDato.FECHA: date(2026, 9, 18),
        TipoDato.BOOLEANO: True,
    }[tipo]


def _productos() -> dict[str, dict]:
    productos = {
        variante: {
            campo: _valor_de_ejemplo(tipo, variante) for campo, tipo in CAMPOS_CARTERA.items()
        }
        for variante in ("lleno", "vacio", "en_blanco", "enteros")
    }
    productos["sin_claves"] = {}
    return productos


PRODUCTOS = _productos()


def test_se_encontraron_las_plantillas_de_las_pruebas_actuales() -> None:
    assert len(PLANTILLAS_DE_LAS_PRUEBAS) >= 15
    for esperada in ("1010", "[@telefono]", "51[@telefono]", "[@]", "51[@telefono", ""):
        assert esperada in PLANTILLAS_DE_LAS_PRUEBAS, esperada
    assert "Pagare [@pagare] vence el [@fecha_vencimiento_cuota]" in PLANTILLAS_DE_LAS_PRUEBAS
    assert "documento=[@documento_numero]; pagare=[@pagare]" in PLANTILLAS_DE_LAS_PRUEBAS
    assert "x[@telefono]" in PLANTILLAS_DE_LAS_PRUEBAS  # de test_generacion_cargas.py
    assert "[@campo_inventado]" in PLANTILLAS_DE_LAS_PRUEBAS  # de un parametrize


def _hoy(plantilla: str):
    try:
        return plantillas.compilar(plantilla, DISPONIBLES)
    except PlantillaInvalida:
        return None


VALIDAS = [p for p in TODAS if _hoy(p) is not None]
INVALIDAS = [p for p in TODAS if _hoy(p) is None]


def test_hay_plantillas_validas_e_invalidas_que_comparar() -> None:
    assert len(VALIDAS) >= 25
    assert len(INVALIDAS) >= 10


@pytest.mark.parametrize("plantilla", VALIDAS, ids=repr)
def test_el_motor_da_el_mismo_texto_que_plantillas_aplicar(plantilla) -> None:
    hoy = _hoy(plantilla)
    motor = evaluador.compilar_texto(plantilla, VARIABLES)

    for nombre, producto in PRODUCTOS.items():
        resultado = motor.evaluar(producto)

        assert resultado.texto == plantillas.aplicar(hoy, producto), nombre
        assert resultado.problemas == (), nombre


@pytest.mark.parametrize("plantilla", INVALIDAS, ids=repr)
def test_el_motor_rechaza_lo_que_hoy_se_rechaza(plantilla) -> None:
    with pytest.raises(ExpresionInvalida):
        evaluador.compilar_texto(plantilla, VARIABLES)


@pytest.mark.parametrize("plantilla", VALIDAS, ids=repr)
def test_el_valor_tipado_de_una_referencia_simple_es_el_valor_crudo_de_hoy(plantilla) -> None:
    hoy = _hoy(plantilla)
    motor = evaluador.compilar_texto(plantilla, VARIABLES)

    for nombre, producto in PRODUCTOS.items():
        assert motor.evaluar(producto).valor == plantillas.valor_crudo(hoy, producto), nombre
    assert motor.es_variable_unica == hoy.es_referencia_simple


@pytest.mark.parametrize("plantilla", VALIDAS, ids=repr)
def test_el_motor_lee_los_mismos_campos_que_la_plantilla(plantilla) -> None:
    hoy = _hoy(plantilla)

    assert evaluador.compilar_texto(plantilla, VARIABLES).variables == tuple(
        dict.fromkeys(hoy.campos)
    )


def test_cubre_todos_los_tipos_de_campo_del_catalogo() -> None:
    assert {tipo for tipo in CAMPOS_CARTERA.values()} == set(TipoDato)
