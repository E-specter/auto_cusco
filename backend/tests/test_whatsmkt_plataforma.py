"""Las reglas de la plataforma `whatsmkt` en el registro de RF-72 (T-WM-B2; RF-WM-09 a RF-WM-11).

El constructor no conoce WhatsMKT: lee estas reglas. Aqui se comprueban las reglas mismas, con los
problemas que da una definicion que las rompe, y que la aplicacion las tiene registradas.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.definiciones_columnas import obtener_registro_plataformas
from app.core.entities.mapeo import TipoSalida
from app.core.entities.texto_enriquecido import CodigoTexto
from app.core.services.plataformas.whatsmkt.plataforma import (
    COLUMNA_NUMERO,
    ENCABEZADO_MACRO,
    REGLAS_WHATSMKT,
)
from app.main import app
from tests.test_plataformas_definiciones import _columna, _dato, _problemas

AUSENTE = CodigoTexto.PLATAFORMA_COLUMNA_FIJA_AUSENTE
MOVIDA = CodigoTexto.PLATAFORMA_COLUMNA_FIJA_MOVIDA
TIPO_FIJA = CodigoTexto.PLATAFORMA_TIPO_DE_COLUMNA_FIJA
TIPO_RESTO = CodigoTexto.PLATAFORMA_TIPO_DEL_RESTO


def _referencia() -> dict:
    """La definicion de referencia de RF-WM-09: `número` y tres macros, todas de texto."""
    return _dato(
        _columna(COLUMNA_NUMERO, 0),
        _columna("[$MARCRO1$]", 1),
        _columna("[$MARCRO2$]", 2),
        _columna("[$MARCRO3$]", 3),
    )


def _problemas_whatsmkt(dato: dict) -> list[tuple]:
    return _problemas(dato, REGLAS_WHATSMKT)


# --- Lo que declara -----------------------------------------------------------------------------


def test_las_reglas_declaran_numero_y_las_macros_por_posicion() -> None:
    r = REGLAS_WHATSMKT

    assert (r.clave, r.etiqueta) == ("whatsmkt", "WhatsMKT")
    [numero] = r.columnas_fijas
    assert numero.posicion == 1
    assert numero.nombre == "número" == COLUMNA_NUMERO  # con tilde (RF-WM-10)
    assert numero.contenido_por_defecto == "51[@telefono]"
    assert numero.tipo is TipoSalida.TEXTO
    assert numero.celda_texto is True  # RF-73
    assert numero.contenido_editable is True
    assert r.encabezado_por_posicion == "[$MARCRO{n}$]" == ENCABEZADO_MACRO
    assert r.tipo_resto is TipoSalida.TEXTO
    assert r.admite_mas_columnas is True  # sin tope de macros (DU-WM-1)


def test_el_encabezado_por_defecto_se_renumera_por_posicion() -> None:
    # Solo es un valor por defecto: al reordenar, el constructor lo vuelve a calcular.
    nombres = [ENCABEZADO_MACRO.format(n=n) for n in (1, 2, 3)]

    assert nombres == ["[$MARCRO1$]", "[$MARCRO2$]", "[$MARCRO3$]"]


# --- Lo que valida ------------------------------------------------------------------------------


def test_la_definicion_de_referencia_cumple_las_reglas() -> None:
    assert _problemas_whatsmkt(_referencia()) == []


def test_numero_solo_y_cualquier_cantidad_de_macros_cumplen() -> None:
    solo_numero = _dato(_columna(COLUMNA_NUMERO, 0))
    muchas = _dato(
        _columna(COLUMNA_NUMERO, 0), *[_columna(f"[$MARCRO{n}$]", n) for n in range(1, 41)]
    )

    assert _problemas_whatsmkt(solo_numero) == []
    assert _problemas_whatsmkt(muchas) == []


def test_sin_numero_en_la_posicion_1_falta_la_columna_fija() -> None:
    dato = _dato(_columna("[$MARCRO1$]", 0), _columna("[$MARCRO2$]", 1))

    assert _problemas_whatsmkt(dato) == [(AUSENTE, 0, COLUMNA_NUMERO)]


def test_el_numero_sin_tilde_no_es_el_numero() -> None:
    dato = _dato(_columna("numero", 0), _columna("[$MARCRO1$]", 1))

    assert (AUSENTE, 0, COLUMNA_NUMERO) in _problemas_whatsmkt(dato)


def test_el_numero_movido_se_senala_en_su_columna() -> None:
    dato = _dato(_columna("[$MARCRO1$]", 0), _columna(COLUMNA_NUMERO, 1))

    assert _problemas_whatsmkt(dato) == [(MOVIDA, 1, COLUMNA_NUMERO)]


def test_el_numero_que_no_es_texto_se_senala() -> None:
    dato = _dato(_columna(COLUMNA_NUMERO, 0, "numero"), _columna("[$MARCRO1$]", 1))

    assert _problemas_whatsmkt(dato) == [(TIPO_FIJA, 0, COLUMNA_NUMERO)]


@pytest.mark.parametrize("tipo", ["numero", "fecha", "financiero"])
def test_una_macro_que_no_es_texto_se_senala_en_su_columna(tipo: str) -> None:
    dato = _dato(
        _columna(COLUMNA_NUMERO, 0),
        _columna("[$MARCRO1$]", 1),
        _columna("[$MARCRO2$]", 2, tipo),
    )

    assert _problemas_whatsmkt(dato) == [(TIPO_RESTO, 2, "[$MARCRO2$]")]


def test_el_encabezado_de_una_macro_es_libre_porque_se_toma_por_posicion() -> None:
    # WhatsMKT lee las macros por orden, no por nombre (P-4): el nombre no se valida.
    dato = _dato(
        _columna(COLUMNA_NUMERO, 0),
        _columna("Nombres", 1),
        _columna("[$MARCRO7$]", 2),  # numerada "mal" a proposito: es solo el valor por defecto
        _columna("x", 3),
    )

    assert _problemas_whatsmkt(dato) == []


def test_reordenar_las_macros_no_da_problemas() -> None:
    dato = _dato(
        _columna(COLUMNA_NUMERO, 0),
        _columna("[$MARCRO3$]", 1),
        _columna("[$MARCRO1$]", 2),
        _columna("[$MARCRO2$]", 3),
    )

    assert _problemas_whatsmkt(dato) == []


# --- Registrada en la aplicacion ----------------------------------------------------------------


def test_la_aplicacion_tiene_registrada_la_plataforma() -> None:
    registro = obtener_registro_plataformas()

    assert "whatsmkt" in registro
    assert registro.obtener("whatsmkt") is REGLAS_WHATSMKT


def test_el_endpoint_de_plataformas_anuncia_las_reglas_de_whatsmkt() -> None:
    respuesta = TestClient(app).get("/definiciones-columnas/plataformas")

    assert respuesta.status_code == 200
    [whatsmkt] = [p for p in respuesta.json() if p["clave"] == "whatsmkt"]
    assert whatsmkt["etiqueta"] == "WhatsMKT"
    assert whatsmkt["encabezado_por_posicion"] == "[$MARCRO{n}$]"
    assert whatsmkt["tipo_resto"] == "texto"
    assert whatsmkt["admite_mas_columnas"] is True
    [numero] = whatsmkt["columnas_fijas"]
    assert (numero["posicion"], numero["nombre"], numero["tipo"]) == (1, "número", "texto")
    assert numero["contenido_por_defecto"] == "51[@telefono]"
    assert numero["celda_texto"] is True
