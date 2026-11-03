"""La plataforma `mowa_mes` y su definicion (T-MM-B15, paso 2; RF-MM-37 y RF-72).

`mowa_mes` NO esta en el registro publico de plataformas (decision del usuario, 2026-11-02): las
reglas viven en el paquete de MOWA y esta prueba valida `DEFINICION_MOWA_MES` contra ellas con las
mismas funciones que validan cualquier definicion con plataforma. Sin base de datos.
"""

from dataclasses import replace

import pytest

from app.core.entities.mapeo import CampoSalida, TipoSalida
from app.core.entities.mowa_mes_campana import CABECERAS_CARGA
from app.core.entities.texto_enriquecido import CodigoTexto
from app.core.services.definiciones_columnas.plataformas import problemas_de_plataforma
from app.core.services.mapeo_campos.serializacion import DefinicionLeida
from app.core.services.plataformas.mowa_mes.plataforma import (
    DEFINICION_MOWA_MES,
    PLATAFORMA,
    REGLAS_MOWA_MES,
    TIPOS_DE_LA_FILA,
)

NUMERO, MENSAJE, DNI = DEFINICION_MOWA_MES.campos


def _codigos(campos) -> list[CodigoTexto]:
    """Los codigos de los problemas de una definicion con esas columnas contra las reglas."""
    definicion = replace(DEFINICION_MOWA_MES, campos=tuple(campos))
    leida = DefinicionLeida(definicion, tuple(range(len(campos))), plataforma=PLATAFORMA)
    return [p.problema.codigo for p in problemas_de_plataforma(leida, REGLAS_MOWA_MES)]


def test_las_reglas_fijan_numero_mensaje_y_dni_sin_mas_columnas() -> None:
    assert (REGLAS_MOWA_MES.clave, REGLAS_MOWA_MES.etiqueta) == ("mowa_mes", "MOWA MES")
    assert [(f.posicion, f.nombre, f.tipo) for f in REGLAS_MOWA_MES.columnas_fijas] == [
        (1, "numero", TipoSalida.NUMERO),
        (2, "mensaje", TipoSalida.TEXTO),
        (3, "dni", TipoSalida.TEXTO),
    ]
    assert REGLAS_MOWA_MES.admite_mas_columnas is False
    assert REGLAS_MOWA_MES.tipo_resto is None
    assert not any(f.celda_texto for f in REGLAS_MOWA_MES.columnas_fijas)


def test_la_definicion_declara_la_plataforma_mowa_mes_y_cumple_sus_reglas() -> None:
    assert PLATAFORMA == REGLAS_MOWA_MES.clave == "mowa_mes"
    assert _codigos(DEFINICION_MOWA_MES.campos) == []


def test_las_cabeceras_de_la_definicion_son_las_del_archivo_de_carga() -> None:
    assert tuple(campo.nombre for campo in DEFINICION_MOWA_MES.campos) == CABECERAS_CARGA


def test_ninguna_columna_va_en_celda_de_texto_ni_es_un_valor_por_defecto() -> None:
    assert DEFINICION_MOWA_MES.columnas_texto == frozenset()
    assert not any(campo.celda_texto for campo in DEFINICION_MOWA_MES.campos)
    assert all(campo.valor_por_defecto is None for campo in DEFINICION_MOWA_MES.campos)
    assert all(not campo.variantes for campo in DEFINICION_MOWA_MES.campos)
    assert DEFINICION_MOWA_MES.segmentacion is None


def test_cada_columna_es_una_referencia_directa_al_campo_de_la_fila() -> None:
    assert [(c.nombre, c.plantilla) for c in DEFINICION_MOWA_MES.campos] == [
        ("numero", "[@numero]"),
        ("mensaje", "[@mensaje]"),
        ("dni", "[@dni]"),
    ]
    assert {n: t.value for n, t in TIPOS_DE_LA_FILA.items()} == {
        "numero": "numero",
        "mensaje": "texto",
        "dni": "texto",
    }


@pytest.mark.parametrize(
    ("campos", "codigos"),
    [
        (
            [NUMERO, MENSAJE, DNI, CampoSalida("extra", "[@dni]")],
            {CodigoTexto.PLATAFORMA_COLUMNAS_DE_MAS},
        ),
        ([NUMERO, DNI, MENSAJE], {CodigoTexto.PLATAFORMA_COLUMNA_FIJA_MOVIDA}),
        ([MENSAJE, NUMERO, DNI], {CodigoTexto.PLATAFORMA_COLUMNA_FIJA_MOVIDA}),
        (
            [replace(NUMERO, tipo=TipoSalida.TEXTO), MENSAJE, DNI],
            {CodigoTexto.PLATAFORMA_TIPO_DE_COLUMNA_FIJA},
        ),
        (
            [NUMERO, MENSAJE, replace(DNI, tipo=TipoSalida.NUMERO)],
            {CodigoTexto.PLATAFORMA_TIPO_DE_COLUMNA_FIJA},
        ),
        ([NUMERO, MENSAJE], {CodigoTexto.PLATAFORMA_COLUMNA_FIJA_AUSENTE}),
        (
            [NUMERO, replace(MENSAJE, nombre="texto"), DNI],
            {CodigoTexto.PLATAFORMA_COLUMNA_FIJA_AUSENTE, CodigoTexto.PLATAFORMA_COLUMNAS_DE_MAS},
        ),
    ],
    ids=[
        "una_de_mas",
        "dni_antes_del_mensaje",
        "numero_despues",
        "numero_texto",
        "dni_numero",
        "sin_dni",
        "renombrada",
    ],
)
def test_lo_que_rompe_las_reglas_se_detecta(campos, codigos) -> None:
    assert set(_codigos(campos)) == codigos
