"""RF-54 a nivel de `GeneradorCargas` (B2): la `CargaGenerada` entera sale igual que antes.

Dos comparaciones: contra la huella congelada en HEAD b8b9025 con el generador original (cabeceras,
filas con el tipo de cada celda y errores con su fila, campo y texto) y contra el camino de antes en
vivo (`plantillas` + `formatos`, que siguen en el codigo como referencia). `formatos.convertir`
sigue siendo el unico que aplica el tipo de la columna: no hay dos caminos de tipado.
"""

import pytest

from app.core.entities.mapeo import DefinicionCarga, PlantillaInvalida, ValorNoGenerable
from app.core.services.mapeo_campos import formatos, plantillas
from app.core.services.mapeo_campos.generador import CargaGenerada, GeneradorCargas
from app.core.services.seleccion_cartera.campos import CAMPOS_CARTERA
from tests.paridad_generador_datos import (
    CAMPOS_DISPONIBLES,
    DEFINICIONES,
    PRODUCTOS,
    huella_de_la_matriz,
    serializar,
)

# SHA-256 de la matriz completa, calculado en HEAD b8b9025 con el generador original y sin tocar
# app/ (git diff vacio), antes de escribir una sola linea de B2.
# (2026-10-24, T-MTE-B18: los telefonos de PRODUCTOS pasaron al rango sintetico 900000xxx; la huella
# se recalculo con el generador de main sin tocarlo y se comprobo que devolver los telefonos viejos
# a la matriz serializada da exactamente la huella anterior,
# 882908f222530cfffda6443cbe5081d7d043b42cf0414b590bcd4b1b34e2ca50.)
HUELLA_CONGELADA = "b4b61b10e030cce8e8be65b43da579f8385c0d1d13f4f5f5b991180e541fe4b2"


def _de_antes(definicion: DefinicionCarga, disponibles, productos) -> CargaGenerada:
    """El generador de antes de B2, tal cual: plantillas.aplicar + valor_crudo + convertir."""
    compiladas = {
        c.nombre: plantillas.compilar(c.plantilla, disponibles) for c in definicion.campos
    }
    filas, errores = [], []
    for numero_fila, producto in enumerate(productos, start=1):
        fila = {}
        for campo in definicion.campos:
            compilada = compiladas[campo.nombre]
            texto = plantillas.aplicar(compilada, producto)
            crudo = plantillas.valor_crudo(compilada, producto)
            try:
                fila[campo.nombre] = formatos.convertir(campo, texto, crudo)
            except ValorNoGenerable as exc:
                fila[campo.nombre] = None
                from app.core.entities.mapeo import ErrorGeneracion

                errores.append(ErrorGeneracion(numero_fila, campo.nombre, exc.detalle))
        filas.append(fila)
    return CargaGenerada(
        cabeceras=tuple(c.nombre for c in definicion.campos),
        filas=tuple(filas),
        errores=tuple(errores),
    )


def _generar(definicion, disponibles=CAMPOS_DISPONIBLES) -> CargaGenerada:
    return GeneradorCargas(definicion, disponibles).generar(PRODUCTOS)


def test_la_matriz_entera_da_la_huella_congelada_en_head() -> None:
    cargas = {nombre: _generar(df) for nombre, df in DEFINICIONES.items()}

    assert huella_de_la_matriz(cargas) == HUELLA_CONGELADA


def test_la_matriz_es_lo_bastante_variada_para_que_la_huella_valga() -> None:
    cargas = {nombre: _generar(df) for nombre, df in DEFINICIONES.items()}

    assert len(DEFINICIONES) >= 7 and len(PRODUCTOS) >= 8
    assert sum(len(c.errores) for c in cargas.values()) > 40  # los errores tambien se comparan
    tipos = {type(v).__name__ for c in cargas.values() for f in c.filas for v in f.values()}
    assert {"str", "int", "Decimal", "date", "NoneType"} <= tipos


@pytest.mark.parametrize("nombre", list(DEFINICIONES))
def test_cada_definicion_sale_igual_que_en_el_camino_de_antes(nombre) -> None:
    definicion = DEFINICIONES[nombre]

    ahora = _generar(definicion)
    antes = _de_antes(definicion, CAMPOS_DISPONIBLES, PRODUCTOS)

    assert serializar(nombre, ahora) == serializar(nombre, antes)
    assert ahora.errores == antes.errores  # fila, campo y el mismo texto del detalle
    assert ahora.exclusiones == ()


@pytest.mark.parametrize("nombre", list(DEFINICIONES))
def test_con_el_catalogo_tipado_de_la_cartera_tambien_sale_igual(nombre) -> None:
    # `/archivos-carga` pasa CAMPOS_CARTERA (nombre -> tipo). Los campos de las definiciones de
    # la matriz que no existen en la cartera se agregan como texto.
    disponibles = {
        **{c: "texto" for c in CAMPOS_DISPONIBLES},
        **{c: t for c, t in CAMPOS_CARTERA.items() if c in CAMPOS_DISPONIBLES},
    }
    definicion = DEFINICIONES[nombre]

    tipado = GeneradorCargas(definicion, disponibles).generar(PRODUCTOS)
    antes = _de_antes(definicion, CAMPOS_DISPONIBLES, PRODUCTOS)

    assert serializar(nombre, tipado) == serializar(nombre, antes)


# --- Errores de la definicion: el mismo texto de antes ------------------------------------------


@pytest.mark.parametrize(
    "plantilla",
    [
        "[@campo_inventado]",
        "[@]",
        "[@   ]",
        "51[@telefono",
        "[@telefono] y [@otro_inventado]",
        "[@TELEFONO]",
        "x [@",
    ],
)
def test_una_plantilla_invalida_se_rechaza_con_el_mismo_texto_de_antes(plantilla) -> None:
    from app.core.entities.mapeo import CampoSalida

    definicion = DefinicionCarga("d", (CampoSalida("x", plantilla),))
    with pytest.raises(PlantillaInvalida) as antes:
        plantillas.compilar(plantilla, CAMPOS_DISPONIBLES)

    with pytest.raises(PlantillaInvalida) as ahora:
        GeneradorCargas(definicion, CAMPOS_DISPONIBLES)

    assert str(ahora.value) == str(antes.value)


def test_los_campos_de_origen_son_los_mismos_y_en_el_mismo_orden() -> None:
    generador = GeneradorCargas(DEFINICIONES["sms_de_prueba"], CAMPOS_DISPONIBLES)

    assert generador.campos_de_origen() == (
        "telefono",
        "titular",
        "saldo_capital_pendiente",
        "fecha_vencimiento_cuota",
        "pagare",
    )


def test_la_definicion_se_compila_una_vez_y_sirve_para_muchos_productos() -> None:
    generador = GeneradorCargas(DEFINICIONES["sms_de_prueba"], CAMPOS_DISPONIBLES)

    primera = generador.generar(PRODUCTOS)
    segunda = generador.generar(PRODUCTOS)

    assert serializar("x", primera) == serializar("x", segunda)


def test_una_plantilla_enorme_sigue_funcionando_como_antes() -> None:
    # Regresion hallada por el oro de MOWA MES: los limites de tamano del motor (RF-48) no se
    # aplican a una plantilla, que es la ruta de compatibilidad: lo que funcionaba sigue igual.
    from app.core.entities.mapeo import CampoSalida

    plantilla = ("x" * 40 + "[@titular]") * 300 + "y" * 20_000
    definicion = DefinicionCarga("d", (CampoSalida("c", plantilla),))

    ahora = _generar(definicion)
    antes = _de_antes(definicion, CAMPOS_DISPONIBLES, PRODUCTOS)

    assert serializar("d", ahora) == serializar("d", antes)


def test_una_expresion_explicita_conserva_los_limites_de_tamano() -> None:
    from app.core.entities.mapeo import CampoSalida
    from app.core.entities.texto_enriquecido import Expresion, NodoTexto

    demasiado = Expresion((NodoTexto("x" * 6000),))
    definicion = DefinicionCarga("d", (CampoSalida("c", "", expresion=demasiado),))

    with pytest.raises(PlantillaInvalida):
        GeneradorCargas(definicion, CAMPOS_DISPONIBLES)
