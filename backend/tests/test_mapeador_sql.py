"""Las sentencias del mapeador compiladas al dialecto de PostgreSQL, y la migracion, sin base.

Lo que escribe nulos y JSON se compila con el dialecto de PostgreSQL y no con el generico: un
`None` en una columna JSONB puede guardarse como el JSON `null` en lugar de NULL (la leccion de
B4b y de B6). Las pruebas con la base real estan en `test_mapeador_postgres.py`.
"""

import io
from datetime import UTC, date, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateColumn, CreateTable

from app.adapters.persistence.modelos import (
    BorradorCargaArchivo,
    Carga,
    MapeoRecordado,
)
from app.adapters.persistence.repositorio_mapeador_postgres import (
    SesionMapeadorPostgres,
    sentencia_de_recordados,
)
from app.core.entities.borrador import NuevoBorrador
from tests.mapeador_postgres_comun import sentencias_de_limpieza

DIALECTO = postgresql.dialect()
AHORA = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)
BACKEND = Path(__file__).resolve().parents[1]
REVISION_ANTERIOR = "f2c8a4d7b915"
REVISION = "b6e1d9c4a728"


def compilar(sentencia):
    return sentencia.compile(dialect=DIALECTO)


# --- El upsert de los recordados ----------------------------------------------------------------


def test_el_upsert_de_recordados_actualiza_por_la_clave_del_recordado() -> None:
    compilada = compilar(
        sentencia_de_recordados(
            "sabana_vencida", {("pagare", 1): "pagare", ("pagare", 2): None}, AHORA
        )
    )

    texto = str(compilada)
    assert texto.startswith("INSERT INTO mapeo_recordado")
    assert "ON CONFLICT (catalogo_id, encabezado_normalizado, ocurrencia) DO UPDATE" in texto
    assert "campo = excluded.campo" in texto and "actualizado_en = excluded.actualizado_en" in texto
    assert texto.count("(%(catalogo_id_m") == 2  # una fila por asignacion, en un solo lote


def test_un_no_cargar_se_guarda_como_null_y_no_como_texto() -> None:
    compilada = compilar(
        sentencia_de_recordados("sabana_vencida", {("pagare", 1): "pagare", ("x", 1): None}, AHORA)
    )

    campos = [v for k, v in compilada.params.items() if k.startswith("campo_m")]
    assert campos == ["pagare", None]
    assert MapeoRecordado.__table__.c.campo.nullable
    assert not isinstance(MapeoRecordado.__table__.c.campo.type, postgresql.JSONB)


# --- JSONB: None es NULL ------------------------------------------------------------------------


def _bind(columna, valor):
    return columna.type.dialect_impl(DIALECTO).bind_processor(DIALECTO)(valor)


def test_las_asignaciones_de_una_carga_sin_mapeo_explicito_son_null_y_no_json_null() -> None:
    columna = Carga.__table__.c.asignaciones

    assert columna.type.none_as_null is True
    assert _bind(columna, None) is None  # NULL de SQL
    assert _bind(columna, [{"indice": 0, "campo": None}]) == '[{"indice": 0, "campo": null}]'


def test_el_json_null_de_un_campo_dentro_de_las_asignaciones_se_conserva() -> None:
    # Un `campo: null` (No cargar) es parte del documento: no se confunde con la columna vacia.
    texto = _bind(
        Carga.__table__.c.asignaciones, [{"indice": 1, "campo": None, "origen": "manual"}]
    )

    assert '"campo": null' in texto


def test_las_opciones_de_lectura_se_guardan_como_json() -> None:
    columna = Carga.__table__.c.opciones_lectura

    assert _bind(columna, {"hoja": "VENCIDA"}) == '{"hoja": "VENCIDA"}'
    assert not columna.nullable and "'{}'::jsonb" in str(columna.server_default.arg)


def test_el_borrador_guarda_opciones_y_analisis_como_json_no_nulos() -> None:
    for nombre in ("opciones", "analisis"):
        columna = BorradorCargaArchivo.__table__.c[nombre]
        assert isinstance(columna.type, postgresql.JSONB) and not columna.nullable


# --- Las sentencias de la sesion ----------------------------------------------------------------


class _Resultado:
    def one_or_none(self):
        return None

    def one(self):
        raise AssertionError("no se esperaba una fila")

    def __iter__(self):
        return iter([])

    @property
    def rowcount(self):
        return 0

    def scalar_one(self):
        return b""


class _ConexionFalsa:
    def __init__(self) -> None:
        self.sentencias: list = []

    def execute(self, sentencia, *args, **kwargs):
        self.sentencias.append(sentencia)
        return _Resultado()


def _sesion():
    cx = _ConexionFalsa()
    return SesionMapeadorPostgres(cx), cx


def test_obtener_un_borrador_para_confirmarlo_lo_toma_con_for_update() -> None:
    sesion, cx = _sesion()

    sesion.obtener_borrador(7, bloquear=True)
    sesion.obtener_borrador(7)

    con_bloqueo, sin_bloqueo = (str(compilar(s)) for s in cx.sentencias)
    assert con_bloqueo.rstrip().endswith("FOR UPDATE")
    assert "FOR UPDATE" not in sin_bloqueo
    assert "WHERE borrador_carga_archivo.id = %(id_1)s" in con_bloqueo
    assert "contenido" not in con_bloqueo  # el archivo se pide aparte


def test_crear_un_borrador_devuelve_las_columnas_sin_el_contenido() -> None:
    sesion, cx = _sesion()
    nuevo = NuevoBorrador(
        "sabana_vencida", "a.csv", "h" * 64, 3, {"hoja": None}, {"columnas": []}, AHORA
    )

    try:
        sesion.crear_borrador(nuevo, b"abc")
    except AssertionError:
        pass  # la conexion falsa no devuelve filas

    compilada = compilar(cx.sentencias[0])
    texto = str(compilada)
    assert texto.startswith("INSERT INTO borrador_carga_archivo")
    assert "RETURNING" in texto
    returning = texto.split("RETURNING", 1)[1]
    assert "contenido" not in returning and "creado_en" in returning
    assert compilada.params["creado_en"] == AHORA  # el reloj es del servicio, no de la base
    assert compilada.params["contenido"] == b"abc"


def test_borrar_los_vencidos_compara_la_fecha_de_creacion() -> None:
    sesion, cx = _sesion()

    sesion.borrar_borradores_vencidos(AHORA)

    compilada = compilar(cx.sentencias[0])
    assert str(compilada).startswith("DELETE FROM borrador_carga_archivo")
    assert "creado_en < %(creado_en_1)s" in str(compilada)
    assert compilada.params == {"creado_en_1": AHORA}


def test_volver_a_analizar_reemplaza_solo_opciones_y_analisis() -> None:
    sesion, cx = _sesion()

    sesion.reemplazar_analisis(3, {"hoja": "A"}, {"columnas": []})

    compilada = compilar(cx.sentencias[0])
    assert str(compilada).startswith("UPDATE borrador_carga_archivo SET opciones=")
    assert set(compilada.params) >= {"opciones", "analisis", "id_1"}
    assert "contenido" not in str(compilada).split("WHERE")[0]


def test_los_recordados_se_leen_por_catalogo() -> None:
    sesion, cx = _sesion()

    sesion.recordados("sabana_vencida")

    compilada = compilar(cx.sentencias[0])
    assert "WHERE mapeo_recordado.catalogo_id = %(catalogo_id_1)s" in str(compilada)
    assert compilada.params == {"catalogo_id_1": "sabana_vencida"}


def test_guardar_cero_recordados_no_ejecuta_nada() -> None:
    sesion, cx = _sesion()

    sesion.guardar_recordados("sabana_vencida", {}, AHORA)

    assert cx.sentencias == []


# --- La migracion --------------------------------------------------------------------------------


def _sql_de_la_migracion(subir: bool) -> str:
    configuracion = Config(str(BACKEND / "alembic.ini"))
    configuracion.set_main_option("script_location", str(BACKEND / "migrations"))
    configuracion.output_buffer = io.StringIO()
    if subir:
        command.upgrade(configuracion, f"{REVISION_ANTERIOR}:{REVISION}", sql=True)
    else:
        command.downgrade(configuracion, f"{REVISION}:{REVISION_ANTERIOR}", sql=True)
    return configuracion.output_buffer.getvalue()


def _cuerpo(texto: str) -> set[str]:
    """Las lineas de un CREATE TABLE: columnas y restricciones, sin el encabezado ni el cierre."""
    lineas = {linea.strip().rstrip(",") for linea in texto.splitlines() if linea.strip()}
    return {x for x in lineas if not x.startswith("CREATE TABLE") and x not in (")", ");")}


def _lineas(texto: str) -> set[str]:
    return {linea.strip().rstrip(",") for linea in texto.splitlines() if linea.strip()}


def _create_table_de(sql: str, tabla: str) -> set[str]:
    inicio = sql.index(f"CREATE TABLE {tabla} (")
    return _cuerpo(sql[inicio : sql.index(");", inicio) + 2])


def test_la_migracion_crea_las_tablas_como_las_declaran_los_modelos() -> None:
    sql = _sql_de_la_migracion(subir=True)

    for modelo in (BorradorCargaArchivo, MapeoRecordado):
        tabla = modelo.__table__
        esperado = _cuerpo(str(CreateTable(tabla).compile(dialect=DIALECTO)))
        assert _create_table_de(sql, tabla.name) == esperado, tabla.name


def test_la_migracion_suma_a_carga_las_columnas_del_modelo() -> None:
    sql = _sql_de_la_migracion(subir=True)

    for nombre in ("opciones_lectura", "asignaciones"):
        columna = Carga.__table__.c[nombre]
        definicion = str(CreateColumn(columna).compile(dialect=DIALECTO)).strip()
        assert f"ALTER TABLE carga ADD COLUMN {definicion};" in sql, nombre


def test_la_migracion_rellena_las_opciones_de_lectura_de_las_cargas_existentes() -> None:
    sql = _sql_de_la_migracion(subir=True)

    relleno = "UPDATE carga SET opciones_lectura = jsonb_build_object('hoja', hoja);"
    assert relleno in sql
    # El relleno va despues de crear la columna y antes de que nadie la lea.
    assert sql.index("ADD COLUMN opciones_lectura") < sql.index(relleno)
    assert "UPDATE alembic_version SET version_num='b6e1d9c4a728'" in sql


def test_la_migracion_se_deshace_por_completo() -> None:
    sql = _sql_de_la_migracion(subir=False)

    assert _lineas(sql) >= {
        "ALTER TABLE carga DROP COLUMN asignaciones;",
        "ALTER TABLE carga DROP COLUMN opciones_lectura;",
        "DROP TABLE mapeo_recordado;",
        "DROP INDEX ix_borrador_carga_archivo_creado_en;",
        "DROP TABLE borrador_carga_archivo;",
    }
    assert "UPDATE alembic_version SET version_num='f2c8a4d7b915'" in sql
    # y en el orden inverso al de subir: el indice antes que su tabla
    assert sql.index("DROP INDEX") < sql.index("DROP TABLE borrador_carga_archivo")


def test_el_modelo_declara_la_clave_y_los_chequeos_del_recordado() -> None:
    tabla = MapeoRecordado.__table__

    assert [c.name for c in tabla.primary_key.columns] == [
        "catalogo_id",
        "encabezado_normalizado",
        "ocurrencia",
    ]
    assert {c.name for c in tabla.constraints if c.name} >= {
        "pk_mapeo_recordado",
        "ck_mapeo_recordado_ocurrencia_positiva",
    }


# --- La limpieza de las pruebas con base -------------------------------------------------------
# Un `date` comparado con un texto lo rechaza PostgreSQL (`date = character varying`) y solo se ve
# al correr contra la base: aqui se compila lo que ejecutan los ayudantes de `test_*_postgres.py`.

FECHA_DE_PRUEBA = date(2099, 8, 2)


def _limpieza(**opciones):
    return [compilar(s) for s in sentencias_de_limpieza(FECHA_DE_PRUEBA, "b3b-", **opciones)]


def test_la_limpieza_compara_la_fecha_de_corte_como_fecha() -> None:
    compiladas = _limpieza()

    por_fecha = [c for c in compiladas if "fecha_corte" in str(c)]
    assert len(por_fecha) == 2  # las versiones y su auditoria
    for compilada in por_fecha:
        valores = [v for v in compilada.params.values() if isinstance(v, (date, str))]
        assert valores == [FECHA_DE_PRUEBA] and type(valores[0]) is date
        assert "fecha_corte = %(fecha_corte_1)s" in str(compilada)


def test_toda_sentencia_de_limpieza_tiene_un_where() -> None:
    for compilada in _limpieza(catalogos_de_prueba=["b3b_prueba"]):
        assert str(compilada).startswith("DELETE FROM ") and " WHERE " in str(compilada)


def test_la_limpieza_borra_de_lo_recordado_solo_los_encabezados_con_el_prefijo() -> None:
    sabana = next(c for c in _limpieza() if "mapeo_recordado" in str(c))

    assert "encabezado_normalizado LIKE" in str(sabana) and "ESCAPE" in str(sabana)
    assert "catalogo_id = %(catalogo_id_1)s" in str(sabana)
    assert sabana.params["catalogo_id_1"] == "sabana_vencida"
    assert "|| '%%'" in str(sabana)  # empieza por el prefijo (%% es el % de psycopg)
    assert sabana.params["encabezado_normalizado_1"] == "b3b-"  # y el prefijo es solo ese


def test_los_borradores_se_borran_por_el_prefijo_del_archivo() -> None:
    borradores = next(c for c in _limpieza() if "borrador_carga_archivo" in str(c))

    assert "nombre_archivo LIKE" in str(borradores)
    assert borradores.params["nombre_archivo_1"] == "b3b-"


def test_el_catalogo_inventado_por_la_prueba_se_borra_entero_y_solo_ese() -> None:
    sentencias = _limpieza(catalogos_de_prueba=["b3b_prueba"])

    propias = [c for c in sentencias if "catalogo_id IN" in str(c)]
    assert len(propias) == 1 and propias[0].params["catalogo_id_1"] == ["b3b_prueba"]
    assert len(sentencias) == 5 and len(_limpieza()) == 4
