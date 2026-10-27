"""El SQL de la cartera para los campos adicionales, compilado al dialecto de PostgreSQL (T-CA-B1).

Sin base de datos: la columna `carga_fila.adicionales` llega con la migracion de T-CA-B2, y aqui se
comprueba lo que el repositorio ARMA. Un adicional se lee como `adicionales ->> 'ad_x'` con un CAST
por tipo (`NUMERIC` o `DATE`; el texto, tal cual), en filtros, orden, indicadores, segmentacion y en
las filas que salen. Un campo base sigue saliendo de su columna, igual que antes.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.dialects import postgresql

from app.adapters.persistence.repositorio_cartera_postgres import (
    _COLUMNAS,
    _COLUMNAS_PRODUCTO,
    RepositorioCarteraPostgres,
)
from app.core.entities.cartera import Filtro, Funcion, Indicador, Operador, Orden, Recorte
from tests.campos_adicionales_memoria import catalogo_con

FECHA = date(2099, 8, 3)
NUMERO = "CAST((carga_fila.adicionales ->> 'ad_monto_extra') AS NUMERIC)"
FECHA_SQL = "CAST((carga_fila.adicionales ->> 'ad_fecha_visita') AS DATE)"
TEXTO = "(carga_fila.adicionales ->> 'ad_zona_comercial')"


def sql(elemento) -> str:
    return str(
        elemento.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )


@pytest.fixture
def repo() -> RepositorioCarteraPostgres:
    return RepositorioCarteraPostgres(None, catalogo_con())  # type: ignore[arg-type]


def condicion(repo, filtro: Filtro) -> str:
    return sql(repo._condiciones(FECHA, [filtro])[2])


# --- Filtros -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("filtro", "esperado"),
    [
        (Filtro("ad_monto_extra", Operador.MAYOR, (Decimal("150.5"),)), f"{NUMERO} > 150.5"),
        (Filtro("ad_monto_extra", Operador.IGUAL, (Decimal(7),)), f"{NUMERO} = 7"),
        (
            Filtro("ad_monto_extra", Operador.ENTRE, (Decimal(1), Decimal(9))),
            f"{NUMERO} BETWEEN 1 AND 9",
        ),
        (
            Filtro("ad_fecha_visita", Operador.ENTRE, (date(2099, 1, 1), date(2099, 2, 1))),
            f"{FECHA_SQL} BETWEEN '2099-01-01' AND '2099-02-01'",
        ),
        (
            Filtro("ad_fecha_visita", Operador.MENOR, (date(2099, 8, 1),)),
            f"{FECHA_SQL} < '2099-08-01'",
        ),
        (Filtro("ad_zona_comercial", Operador.IGUAL, ("SUR",)), f"{TEXTO} = 'SUR'"),
        (
            Filtro("ad_zona_comercial", Operador.EN, ("SUR", "NORTE")),
            f"{TEXTO} IN ('SUR', 'NORTE')",
        ),
        (Filtro("ad_zona_comercial", Operador.VACIO), f"{TEXTO} IS NULL"),
        (Filtro("ad_monto_extra", Operador.NO_VACIO), f"{NUMERO} IS NOT NULL"),
    ],
)
def test_un_filtro_sobre_un_adicional_lee_el_json_con_el_cast_de_su_tipo(
    repo, filtro, esperado
) -> None:
    assert condicion(repo, filtro) == esperado


def test_contiene_y_empieza_con_sobre_un_adicional_de_texto_escapan_el_comodin(repo) -> None:
    contiene = condicion(repo, Filtro("ad_zona_comercial", Operador.CONTIENE, ("50%",)))
    empieza = condicion(repo, Filtro("ad_zona_comercial", Operador.EMPIEZA_CON, ("su",)))

    assert contiene.startswith(f"{TEXTO} ILIKE") and "ESCAPE '/'" in contiene
    assert "50/%" in contiene  # el % del usuario no es comodin
    assert empieza.startswith(f"{TEXTO} ILIKE") and "ESCAPE '/'" in empieza


def test_el_valor_del_filtro_es_un_parametro_y_nunca_texto_pegado_al_sql(repo) -> None:
    filtro = Filtro("ad_zona_comercial", Operador.IGUAL, ("x'; DROP TABLE carga_fila; --",))

    condicion_ = repo._condiciones(FECHA, [filtro])[2]

    compilada = condicion_.compile(dialect=postgresql.dialect())
    assert "DROP" not in str(compilada)  # va como parametro
    assert "x'; DROP TABLE carga_fila; --" in compilada.params.values()


def test_el_nombre_del_adicional_tambien_va_como_parametro() -> None:
    repo = RepositorioCarteraPostgres(None, catalogo_con())  # type: ignore[arg-type]
    condicion_ = repo._condiciones(FECHA, [Filtro("ad_zona_comercial", Operador.VACIO)])[2]

    compilada = condicion_.compile(dialect=postgresql.dialect())

    assert "ad_zona_comercial" in compilada.params.values()


def test_un_campo_base_sigue_saliendo_de_su_columna(repo) -> None:
    assert condicion(repo, Filtro("dias_atraso", Operador.MAYOR, (Decimal(30),))) == (
        "carga_fila.dias_atraso > 30"
    )
    assert "adicionales" not in condicion(repo, Filtro("region", Operador.IGUAL, ("CUSCO SUR",)))


# --- Orden y filas que salen ---------------------------------------------------------------------


ORDEN = [
    ("ad_monto_extra", "CAST(carga_fila.adicionales ->> 'ad_monto_extra' AS NUMERIC)"),
    ("ad_fecha_visita", "CAST(carga_fila.adicionales ->> 'ad_fecha_visita' AS DATE)"),
    ("ad_zona_comercial", "carga_fila.adicionales ->> 'ad_zona_comercial'"),
]


@pytest.mark.parametrize(("campo", "expresion"), ORDEN)
def test_se_ordena_por_un_adicional_con_nulos_al_final_y_desempate_por_pagare(
    repo, campo, expresion
) -> None:
    _, consulta = repo._sentencias_de_consultar(FECHA, [], Orden(campo, True), 10, 0)

    texto = sql(consulta)
    assert f"ORDER BY {expresion} DESC NULLS LAST, carga_fila.pagare" in texto


def test_las_filas_que_salen_traen_cada_adicional_rotulado_con_su_nombre(repo) -> None:
    _, consulta = repo._sentencias_de_consultar(FECHA, [], None, 10, 0)

    texto = sql(consulta)
    assert "AS ad_monto_extra" in texto and "AS ad_fecha_visita" in texto
    assert "AS ad_zona_comercial" in texto
    assert "AS ad_antiguo" in texto  # un archivado se sigue leyendo


def test_sin_adicionales_las_filas_son_exactamente_las_columnas_de_siempre() -> None:
    repo = RepositorioCarteraPostgres(None)  # type: ignore[arg-type]

    assert repo._columnas_producto() == list(_COLUMNAS_PRODUCTO)
    _, consulta = repo._sentencias_de_consultar(FECHA, [], None, 10, 0)
    assert "adicionales" not in sql(consulta)


# --- Indicadores y segmentacion ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("funcion", "sql_funcion"),
    [
        (Funcion.SUMA, "sum"),
        (Funcion.PROMEDIO, "avg"),
        (Funcion.MINIMO, "min"),
        (Funcion.MAXIMO, "max"),
        (Funcion.CONTEO, "count"),
    ],
)
def test_los_indicadores_de_un_adicional_numero_agregan_el_valor_ya_convertido(
    repo, funcion, sql_funcion
) -> None:
    base, _ = repo._sentencias_de_metricas(
        FECHA, [], [Indicador("x", funcion, "ad_monto_extra")], None
    )

    assert f"{sql_funcion}(CAST(carga_fila.adicionales ->> 'ad_monto_extra' AS NUMERIC))" in sql(
        base
    )


def test_con_recorte_el_indicador_agrega_la_columna_ya_rotulada_de_los_primeros(repo) -> None:
    base, _ = repo._sentencias_de_metricas(
        FECHA,
        [],
        [Indicador("x", Funcion.MAXIMO, "ad_monto_extra")],
        Recorte(Orden("ad_fecha_visita"), 5),
    )

    texto = sql(base)
    assert "max(primeros.ad_monto_extra)" in texto
    assert "ORDER BY CAST(carga_fila.adicionales ->> 'ad_fecha_visita' AS DATE) ASC" in texto
    assert "LIMIT 5) AS primeros" in texto


@pytest.mark.parametrize(
    ("campo", "expresion"),
    [
        ("ad_zona_comercial", "carga_fila.adicionales ->> 'ad_zona_comercial'"),
        ("ad_monto_extra", "CAST(carga_fila.adicionales ->> 'ad_monto_extra' AS NUMERIC)"),
        ("ad_fecha_visita", "CAST(carga_fila.adicionales ->> 'ad_fecha_visita' AS DATE)"),
    ],
)
def test_se_segmenta_por_un_adicional_de_cada_tipo(repo, campo, expresion) -> None:
    consulta = repo._sentencia_de_segmentar(FECHA, campo, [], None)

    texto = sql(consulta)
    assert f"GROUP BY {expresion}" in texto
    assert f"ORDER BY count(*) DESC, {expresion}" in texto


def test_un_filtro_sobre_un_adicional_tambien_filtra_las_metricas(repo) -> None:
    base, por_segmento = repo._sentencias_de_metricas(
        FECHA, [Filtro("ad_zona_comercial", Operador.IGUAL, ("SUR",))], [], None
    )

    assert f"{TEXTO} = 'SUR'" in sql(base) and f"{TEXTO} = 'SUR'" in sql(por_segmento)


def test_el_json_de_adicionales_no_es_un_campo_ni_sale_en_las_filas() -> None:
    assert "adicionales" not in _COLUMNAS
    assert "adicionales" not in [c.name for c in _COLUMNAS_PRODUCTO]
