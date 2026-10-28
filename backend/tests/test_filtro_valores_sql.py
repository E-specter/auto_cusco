"""El SQL de `en` y `no_en` (T-FV-B1, RF-67/RF-68): compilado, ejecutado en SQLite y en PostgreSQL.

- El SQL compilado al dialecto de PostgreSQL, con el elemento vacio como NULL.
- La PROPIEDAD de la particion: para cualquier conjunto marcado, con o sin vacio, `en` y `no_en`
  parten la cartera, sin repetir ni perder productos. Se ejecuta la MISMA condicion que arma el
  repositorio (`_condicion`) sobre una tabla con NULL: en memoria con SQLite y, marcada @postgres,
  sobre una tabla temporal de la base de pruebas (la logica de tres valores del NULL es la que
  importa, y la de PostgreSQL es la real).
- Dos ordenes de los mismos filtros dan el mismo total y los mismos productos.

No hay `hypothesis` en el proyecto: casos aleatorios con semilla fija. Datos sinteticos.
"""

import os
import random
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import Column, Date, Integer, MetaData, Numeric, Table, Text, create_engine, select
from sqlalchemy.dialects import postgresql

from app.adapters.persistence.repositorio_cartera_postgres import (
    RepositorioCarteraPostgres,
    _condicion,
)
from app.core.entities.cartera import Filtro, Operador

FECHA = date(2099, 8, 3)
TEXTOS = ["Primera asignacion", "Segunda asignacion", "Tercera", "CON'COMILLA", "50% / _x"]
NUMEROS = [Decimal(0), Decimal(5), Decimal("7.5"), Decimal(100)]
FECHAS = [date(2099, 1, 2), date(2099, 8, 3), date(2100, 1, 1)]


def sql(filtro: Filtro) -> str:
    condicion = RepositorioCarteraPostgres(None)._condiciones(FECHA, [filtro])[2]  # type: ignore[arg-type]
    return str(
        condicion.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )


# --- El SQL compilado ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("filtro", "esperado"),
    [
        (Filtro("region", Operador.EN, ("A", "B")), "carga_fila.region IN ('A', 'B')"),
        (
            Filtro("region", Operador.EN, ("A", None)),
            "carga_fila.region IN ('A') OR carga_fila.region IS NULL",
        ),
        (
            Filtro("region", Operador.EN, (None, "A")),
            "carga_fila.region IN ('A') OR carga_fila.region IS NULL",
        ),
        (Filtro("region", Operador.EN, (None,)), "carga_fila.region IS NULL"),
        (
            Filtro("region", Operador.NO_EN, ("A", "B")),
            "carga_fila.region IS NULL OR (carga_fila.region NOT IN ('A', 'B'))",
        ),
        (
            Filtro("region", Operador.NO_EN, ("A", None)),
            "carga_fila.region IS NOT NULL AND (carga_fila.region NOT IN ('A'))",
        ),
        (Filtro("region", Operador.NO_EN, (None,)), "carga_fila.region IS NOT NULL"),
        (
            Filtro("dias_atraso", Operador.NO_EN, (Decimal(5), Decimal(9))),
            "carga_fila.dias_atraso IS NULL OR (carga_fila.dias_atraso NOT IN (5, 9))",
        ),
        (
            Filtro("fecha_vencimiento_cuota", Operador.NO_EN, (date(2099, 1, 2),)),
            "carga_fila.fecha_vencimiento_cuota IS NULL OR "
            "(carga_fila.fecha_vencimiento_cuota NOT IN ('2099-01-02'))",
        ),
    ],
)
def test_el_sql_de_en_y_no_en(filtro, esperado) -> None:
    assert sql(filtro) == esperado


def test_un_producto_sin_valor_queda_en_no_en_y_el_not_in_solo_lo_perderia() -> None:
    """La razon de ser de `no_en`: `NOT IN` a secas descarta los NULL (NULL NOT IN (...) no es
    verdadero); `no_en` los conserva, salvo que se marque el vacio."""
    texto = sql(Filtro("region", Operador.NO_EN, ("A",)))

    assert texto.startswith("carga_fila.region IS NULL OR ")


def test_los_valores_de_la_lista_van_como_parametros_y_nunca_pegados_al_sql() -> None:
    filtro = Filtro("region", Operador.NO_EN, ("x'); DROP TABLE carga_fila; --", None))
    condicion = RepositorioCarteraPostgres(None)._condiciones(FECHA, [filtro])[2]  # type: ignore[arg-type]

    compilada = condicion.compile(dialect=postgresql.dialect())

    assert "DROP" not in str(compilada)
    assert "x'); DROP TABLE carga_fila; --" in str(list(compilada.params.values()))


def test_una_condicion_con_or_se_encierra_en_parentesis_junto_a_las_demas() -> None:
    repo = RepositorioCarteraPostgres(None)  # type: ignore[arg-type]
    condiciones = repo._condiciones(
        FECHA,
        [
            Filtro("region", Operador.EN, ("A", None)),
            Filtro("dias_atraso", Operador.MAYOR, (Decimal(5),)),
        ],
    )

    texto = str(
        select(1)
        .where(*condiciones)
        .compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )

    assert (
        "(carga_fila.region IN ('A') OR carga_fila.region IS NULL) AND carga_fila.dias_atraso > 5"
        in texto
    )


# --- La particion: en SQLite y en PostgreSQL ------------------------------------------------------

TIPOS = {
    "texto": (Text, TEXTOS, True),
    "numero": (Numeric(14, 2), NUMEROS, False),
    "fecha": (Date, FECHAS, False),
}


def _tabla(tipo: str, nombre: str = "producto_prueba") -> Table:
    columna_tipo, _, _ = TIPOS[tipo]
    return Table(
        nombre,
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("valor", columna_tipo),
        prefixes=["TEMPORARY"],
    )


def _casos(tipo: str, semilla: int, cuantos: int = 60):
    """(valores de la tabla, valores marcados) al azar: con NULL, repetidos y fuera de la tabla."""
    _, pool, admite_vacio = TIPOS[tipo]
    azar = random.Random(semilla)
    for _ in range(cuantos):
        filas = [azar.choice([*pool, None, None]) for _ in range(azar.randint(0, 25))]
        marcados = azar.sample(pool, azar.randint(1, len(pool)))
        if admite_vacio and azar.random() < 0.5:
            marcados.insert(azar.randint(0, len(marcados)), None)  # el vacio, en cualquier lugar
        yield filas, tuple(marcados)


def _ids(conexion, tabla: Table, operador: Operador, marcados: tuple) -> set[int]:
    condicion = _condicion(Filtro("valor", operador, marcados), {"valor": tabla.c.valor})
    return {fila.id for fila in conexion.execute(select(tabla.c.id).where(condicion))}


def _comprobar_particion(conexion, tabla: Table, filas: list, marcados: tuple) -> None:
    conexion.execute(tabla.delete())
    if filas:
        conexion.execute(tabla.insert(), [{"id": i, "valor": v} for i, v in enumerate(filas, 1)])
    todos = set(range(1, len(filas) + 1))

    dentro = _ids(conexion, tabla, Operador.EN, marcados)
    fuera = _ids(conexion, tabla, Operador.NO_EN, marcados)

    assert dentro & fuera == set(), (filas, marcados)  # sin repetir
    assert dentro | fuera == todos, (filas, marcados)  # sin perder
    reales = {v for v in marcados if v is not None}
    esperado = {
        i for i, v in enumerate(filas, 1) if (v in reales) or (v is None and None in marcados)
    }
    assert dentro == esperado, (filas, marcados)  # y `en` es lo que dice la regla


@pytest.mark.parametrize("tipo", list(TIPOS))
def test_en_y_no_en_parten_la_cartera_en_memoria(tipo) -> None:
    motor = create_engine("sqlite://")
    tabla = _tabla(tipo)
    with motor.connect() as conexion:
        tabla.create(conexion)
        casos = list(_casos(tipo, semilla=20261028))
        for filas, marcados in casos:
            _comprobar_particion(conexion, tabla, filas, marcados)
    assert len(casos) == 60


def test_el_solo_vacio_parte_la_cartera_entre_los_que_tienen_y_no_tienen_valor() -> None:
    motor = create_engine("sqlite://")
    tabla = _tabla("texto")
    with motor.connect() as conexion:
        tabla.create(conexion)
        _comprobar_particion(conexion, tabla, ["A", None, "B", None, "A"], (None,))
        sin_valor = _ids(conexion, tabla, Operador.EN, (None,))
        con_valor = _ids(conexion, tabla, Operador.NO_EN, (None,))

    assert (sin_valor, con_valor) == ({2, 4}, {1, 3, 5})


def test_una_cartera_vacia_o_toda_con_valor_tambien_se_parte() -> None:
    motor = create_engine("sqlite://")
    tabla = _tabla("texto")
    with motor.connect() as conexion:
        tabla.create(conexion)
        for filas in ([], ["A", "A"], [None, None]):
            for marcados in (("A",), (None,), ("A", None), ("Z",)):
                _comprobar_particion(conexion, tabla, filas, marcados)


@pytest.mark.parametrize("tipo", ["texto", "numero", "fecha"])
def test_dos_ordenes_de_los_mismos_filtros_dan_el_mismo_total_y_los_mismos_productos(tipo) -> None:
    """Los filtros son un AND: el orden en que se guardan no cambia el resultado."""
    motor = create_engine("sqlite://")
    columnas = {"texto": Text, "numero": Numeric(14, 2), "fecha": Date}
    tabla = Table(
        "cartera_prueba",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("a", columnas[tipo]),
        Column("b", Text),
    )
    _, pool, _ = TIPOS[tipo]
    azar = random.Random(7)
    with motor.connect() as conexion:
        tabla.create(conexion)
        conexion.execute(
            tabla.insert(),
            [
                {"id": i, "a": azar.choice([*pool, None]), "b": azar.choice([*TEXTOS, None])}
                for i in range(1, 80)
            ],
        )
        columnas_por_campo = {"a": tabla.c.a, "b": tabla.c.b}
        primero = Filtro("a", Operador.NO_EN, tuple(pool[:2]))
        segundo = Filtro("b", Operador.EN, (TEXTOS[0], None))
        tercero = Filtro("a", Operador.EN, tuple(pool[1:]))

        def ejecutar(orden):
            condiciones = [_condicion(f, columnas_por_campo) for f in orden]
            filas = conexion.execute(
                select(tabla.c.id).where(*condiciones).order_by(tabla.c.id)
            ).all()
            return len(filas), [f.id for f in filas]

        base = ejecutar([primero, segundo, tercero])
        for orden in (
            [tercero, segundo, primero],
            [segundo, primero, tercero],
            [tercero, primero, segundo],
        ):
            assert ejecutar(orden) == base


postgres = pytest.mark.skipif(
    os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
    reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
)


@pytest.mark.postgres
@postgres
@pytest.mark.parametrize("tipo", list(TIPOS))
def test_en_y_no_en_parten_la_cartera_contra_postgres(tipo) -> None:
    """La misma propiedad, con la logica de NULL de PostgreSQL, sobre una tabla TEMPORAL: no deja
    nada en la base y no toca la cartera."""
    from app.adapters.persistence.db import get_engine

    tabla = _tabla(tipo, "producto_prueba_fv_b1")
    with get_engine().connect() as conexion:
        transaccion = conexion.begin()
        try:
            tabla.create(conexion)
            for filas, marcados in _casos(tipo, semilla=20261029, cuantos=40):
                _comprobar_particion(conexion, tabla, filas, marcados)
        finally:
            transaccion.rollback()


def test_en_un_adicional_de_texto_el_vacio_y_no_en_leen_el_json() -> None:
    from tests.campos_adicionales_memoria import catalogo_con

    repo = RepositorioCarteraPostgres(None, catalogo_con())  # type: ignore[arg-type]
    filtro = Filtro("ad_zona_comercial", Operador.NO_EN, ("SUR", None))
    condicion = repo._condiciones(FECHA, [filtro])[2]

    texto = str(
        condicion.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )

    expresion = "(carga_fila.adicionales ->> 'ad_zona_comercial')"
    assert texto == f"{expresion} IS NOT NULL AND ({expresion} NOT IN ('SUR'))"
