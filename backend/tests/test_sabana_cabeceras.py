"""Pruebas del mapeo de cabeceras (regla N-1).

Las cabeceras son las observadas en las sabanas reales (docs/sabana-schema.md,
seccion 4); no contienen datos personales.
"""

from app.core.entities.sabana import Severidad
from app.core.services.ingesta_sabana.cabeceras import mapear_cabeceras
from app.core.services.ingesta_sabana.catalogo import CATALOGO_VENCIDA

CABECERAS_10_09 = [
    "Región", "Agencia", "Analista", "Titular", "DniRuc", "Teléfono", "Pagare",
    "SaldoSoles 03/09", "TIPO DE REPROGRAMACIÓN", "Vencimientos Operativo", "Dias Atraso Hoy",
    "Analista Actual", "Saldo Capital Pendiente", "Monto Cuota", "Estado del Crédito",
    "Vencimiento Cuota", "Cliente Fallecido", "DÍAS SICMAC-C", "Cuotas Apro", "Cuotas pagadas",
    "Cuotas Pendientes", "TipoBasilea", "TipoProducto", "PAGARE", "VALIDADOR", "Segmento Saldo",
    "Moneda", " Días Cierre Mes Anterior", "Saldo CIERRE actual", "Cod.Tipo Basilea", "BPO  ",
    "TAG ", "MES DE GESTIÓN ", "SEGMENTO ACTUAL ", "SEGMENTO FINACIERO",
    "validacion descuento planilla", "Segmento", "Tramo Actual", "Provisión Actual",
    "Mora Impacto Actual", "Tramo Proyectado", "Provisión Proyectada", "Mora Impacto Proyectada",
    "Cant.Paralelos", "Celular Analista",
]  # fmt: skip


def _nombres(mapeo) -> list[str]:
    return [mapeo.columnas[i].nombre for i in sorted(mapeo.columnas)]


def test_cabeceras_reales_mapean_todo_el_catalogo_en_orden() -> None:
    mapeo = mapear_cabeceras(CABECERAS_10_09)

    assert _nombres(mapeo) == [col.nombre for col in CATALOGO_VENCIDA]
    assert mapeo.desconocidas == {}
    assert mapeo.faltantes == []
    assert mapeo.incidencias == []
    assert not mapeo.bloqueante


def test_pagare2_del_09_09_se_reconoce_como_duplicado() -> None:
    cabeceras = list(CABECERAS_10_09)
    cabeceras[23] = "PAGARE2"

    mapeo = mapear_cabeceras(cabeceras)

    assert mapeo.columnas[6].nombre == "pagare"
    assert mapeo.columnas[23].nombre == "pagare_duplicado"
    assert mapeo.incidencias == []


def test_mapeo_no_depende_de_la_posicion() -> None:
    cabeceras = list(reversed(CABECERAS_10_09))

    mapeo = mapear_cabeceras(cabeceras)

    assert {c.nombre for c in mapeo.columnas.values()} == {c.nombre for c in CATALOGO_VENCIDA}
    assert mapeo.faltantes == []


def test_falta_pagare_bloquea_el_archivo() -> None:
    cabeceras = [c for c in CABECERAS_10_09 if c.lower() != "pagare"]

    mapeo = mapear_cabeceras(cabeceras)

    assert mapeo.bloqueante
    errores = [i for i in mapeo.incidencias if i.severidad is Severidad.ERROR]
    assert [(i.codigo, i.columna) for i in errores] == [("columna_faltante", "pagare")]


def test_columna_no_requerida_faltante_es_advertencia() -> None:
    cabeceras = [c for c in CABECERAS_10_09 if c != "Moneda"]

    mapeo = mapear_cabeceras(cabeceras)

    assert not mapeo.bloqueante
    assert [(i.codigo, i.columna, i.severidad) for i in mapeo.incidencias] == [
        ("columna_faltante", "moneda", Severidad.ADVERTENCIA)
    ]


def test_cabecera_desconocida_y_duplicada() -> None:
    cabeceras = [*CABECERAS_10_09, "Columna Nueva", "Moneda"]

    mapeo = mapear_cabeceras(cabeceras)

    codigos = {(i.codigo, i.columna) for i in mapeo.incidencias}
    assert codigos == {("cabecera_desconocida", "Columna Nueva"), ("cabecera_duplicada", "Moneda")}
    assert set(mapeo.desconocidas.values()) == {"Columna Nueva", "Moneda"}


def test_cabecera_con_nombre_financiero_corregido_tambien_se_acepta() -> None:
    cabeceras = ["SEGMENTO FINANCIERO" if c == "SEGMENTO FINACIERO" else c for c in CABECERAS_10_09]

    mapeo = mapear_cabeceras(cabeceras)

    assert mapeo.columnas[34].nombre == "segmento_financiero"
