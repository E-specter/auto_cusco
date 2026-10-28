"""El SQL de la lista de valores compilado al dialecto de PostgreSQL (T-FV-B2, RF-67).

Dos sentencias: la decision del umbral (`DISTINCT ... LIMIT umbral + 1` sobre la fecha entera, sin
contar todo) y la lista contextual, que es la agrupacion de `segmentar` sin el capital.
"""

import re
from datetime import date

from sqlalchemy.dialects import postgresql

from app.adapters.persistence.repositorio_cartera_postgres import RepositorioCarteraPostgres
from app.core.entities.cartera import Filtro, Operador
from tests.campos_adicionales_memoria import catalogo_con

FECHA = date(2099, 8, 3)
ORIGEN = "FROM carga_fila JOIN carga ON carga.id = carga_fila.carga_id"
VIGENTE = "WHERE carga.fecha_corte = '2099-08-03' AND carga.vigente"


def sql(sentencia) -> str:
    texto = sentencia.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    return re.sub(r"\s+", " ", str(texto)).strip()


def repo() -> RepositorioCarteraPostgres:
    return RepositorioCarteraPostgres(None, catalogo_con())  # type: ignore[arg-type]


def test_la_decision_del_umbral_cuenta_distintos_no_nulos_con_limit_y_sin_filtros() -> None:
    texto = sql(repo()._sentencia_de_distintos(FECHA, "region", 101))

    assert texto == (
        "SELECT count(*) AS count_1 FROM (SELECT DISTINCT carga_fila.region AS valor "
        f"{ORIGEN} {VIGENTE} AND carga_fila.region IS NOT NULL LIMIT 101) AS distintos"
    )


def test_la_decision_no_recibe_filtros_ni_usa_group_by_ni_cuenta_todo() -> None:
    texto = sql(repo()._sentencia_de_distintos(FECHA, "region", 11))

    assert "GROUP BY" not in texto and "ORDER BY" not in texto
    assert texto.count("LIMIT 11") == 1  # corta en cuanto junta umbral + 1
    assert "DISTINCT" in texto


def test_la_decision_de_un_adicional_lee_el_json() -> None:
    texto = sql(repo()._sentencia_de_distintos(FECHA, "ad_zona_comercial", 11))

    expresion = "carga_fila.adicionales ->> 'ad_zona_comercial'"
    assert f"SELECT DISTINCT {expresion} AS valor" in texto
    assert f"({expresion}) IS NOT NULL" in texto


def test_el_tope_va_como_parametro_en_la_sentencia_real() -> None:
    sentencia = repo()._sentencia_de_distintos(FECHA, "region", 101)

    compilada = sentencia.compile(dialect=postgresql.dialect())

    assert 101 in compilada.params.values()


def test_la_lista_es_la_agrupacion_de_segmentar_sin_el_capital() -> None:
    texto = sql(repo()._sentencia_de_segmentar(FECHA, "region", [], None, con_capital=False))

    assert texto == (
        "SELECT carga_fila.region, count(*) AS count_1 "
        f"{ORIGEN} {VIGENTE} GROUP BY carga_fila.region "
        "ORDER BY count(*) DESC, carga_fila.region"
    )
    assert "sum(" not in texto


def test_la_lista_contextual_aplica_los_filtros_de_arriba() -> None:
    arriba = [
        Filtro("agencia", Operador.NO_EN, ("A", None)),
        Filtro("dias_atraso", Operador.MAYOR, (5,)),
    ]

    texto = sql(repo()._sentencia_de_segmentar(FECHA, "region", arriba, None, con_capital=False))

    assert (
        f"{VIGENTE} AND carga_fila.agencia IS NOT NULL AND (carga_fila.agencia NOT IN ('A')) "
        "AND carga_fila.dias_atraso > 5 GROUP BY carga_fila.region"
    ) in texto


def test_el_vacio_sale_como_el_grupo_null_de_la_agrupacion() -> None:
    """`GROUP BY` agrupa los NULL en un solo grupo: es el «(vacio)» de la lista."""
    texto = sql(repo()._sentencia_de_segmentar(FECHA, "region", [], None, con_capital=False))

    assert "IS NOT NULL" not in texto  # la lista NO descarta los productos sin valor


def test_la_lista_de_un_adicional_agrupa_por_el_json() -> None:
    texto = sql(
        repo()._sentencia_de_segmentar(FECHA, "ad_zona_comercial", [], None, con_capital=False)
    )

    expresion = "carga_fila.adicionales ->> 'ad_zona_comercial'"
    assert f"GROUP BY {expresion}" in texto


def test_segmentar_sigue_trayendo_el_capital() -> None:
    texto = sql(repo()._sentencia_de_segmentar(FECHA, "region", [], None))

    assert "coalesce(sum(carga_fila.saldo_capital_pendiente), 0)" in texto


class _Resultado:
    def __init__(self, filas):
        self._filas = filas

    def __iter__(self):
        return iter(self._filas)

    def scalar_one(self):
        return self._filas[0][0]


class _MotorFalso:
    """Un motor que no se conecta: guarda la sentencia que le llega y contesta con `filas`."""

    def __init__(self, filas):
        self.filas = filas
        self.sentencias = []

    def connect(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sentencia):
        self.sentencias.append(sentencia)
        return _Resultado(self.filas)


def test_valores_de_ejecuta_la_agrupacion_con_los_filtros_de_arriba_y_devuelve_los_valores() -> (
    None
):
    from app.core.entities.cartera import ValorDeFiltro

    motor = _MotorFalso([("CUSCO SUR", 5), (None, 2)])
    repositorio = RepositorioCarteraPostgres(motor, catalogo_con())  # type: ignore[arg-type]

    valores = repositorio.valores_de(FECHA, "region", [Filtro("agencia", Operador.EN, ("AG 1",))])

    assert valores == [ValorDeFiltro("CUSCO SUR", 5), ValorDeFiltro(None, 2)]
    [sentencia] = motor.sentencias
    assert "carga_fila.agencia IN ('AG 1')" in sql(sentencia)
    assert "GROUP BY carga_fila.region" in sql(sentencia) and "sum(" not in sql(sentencia)


def test_distintos_hasta_ejecuta_la_decision_con_el_tope_y_devuelve_el_conteo() -> None:
    motor = _MotorFalso([(101,)])
    repositorio = RepositorioCarteraPostgres(motor, catalogo_con())  # type: ignore[arg-type]

    cuantos = repositorio.distintos_hasta(FECHA, "region", 101)

    assert cuantos == 101
    assert "LIMIT 101" in sql(motor.sentencias[0])
