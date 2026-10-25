r"""El mapeador de encabezados con PostgreSQL real (T-MAP-B3a).

Corre solo con AUTO_CUSCO_DB_TESTS=1 y la base de pruebas migrada (sufijo _test; conftest.py se
niega a correr contra otra). Usa la fecha de corte 2099-08-01, un catalogo de prueba y archivos
sinteticos, y al terminar borra lo que creo.

    PowerShell:  .\scripts\verificar.ps1 -ConBase

Las equivalentes sin base (con el doble en memoria) estan en `test_mapeador_ciclo.py` y
`test_ingesta_mapeo_explicito.py`; las sentencias compiladas al dialecto de PostgreSQL, en
`test_mapeador_sql.py`.
"""

import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg.errors import LockNotAvailable
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import OperationalError

from app.adapters.input.lector_tabla import LectorTabla
from app.adapters.persistence.db import get_engine
from app.adapters.persistence.modelos import (
    BorradorCargaArchivo,
    Carga,
    CargaFila,
    MapeoRecordado,
)
from app.adapters.persistence.repositorio_cargas_postgres import (
    RepositorioCargasPostgres,
    SesionCargasPostgres,
)
from app.adapters.persistence.repositorio_mapeador_postgres import (
    RepositorioMapeadorPostgres,
    SesionMapeadorPostgres,
)
from app.core.entities.borrador import BorradorNoEncontrado, MapeoConProblemas, NuevoBorrador
from app.core.entities.carga import EstadoCarga
from app.core.entities.lectura_tabla import OpcionesLectura
from app.core.entities.mapeador import Asignacion, EstadoEncabezado, OrigenAsignacion
from app.core.services.borradores_carga.servicio import MapeadorService
from app.core.services.ingesta_sabana.mapeable import CATALOGO_SABANA_MAPEABLE
from app.core.services.ingesta_sabana.servicio import IngestaSabanaService
from tests.mapeador_postgres_comun import asignar, sentencias_de_limpieza
from tests.test_mapeador_ciclo import SABANA, aceptar_todo, csv_de

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

FECHA = date(2099, 8, 1)
INICIO = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)
PREFIJO = "b3a-"  # los archivos y los encabezados de estas pruebas
CATALOGO_DE_PRUEBA = "b3a_prueba"
CATALOGO_OTRO = "b3a_otro"
BACKEND = Path(__file__).resolve().parents[1]

BORRADOR = BorradorCargaArchivo.__table__
RECORDADO = MapeoRecordado.__table__
CARGA = Carga.__table__
FILA = CargaFila.__table__

CSV = csv_de(
    [
        [f"{PREFIJO}{h}" for h in ["Pagare", "Titular", "Teléfono", "Región", "Observación libre"]],
        [
            "000000000000000001",
            "APELLIDO/NOMBRE FICTICIO",
            "900000001",
            "REGIÓN PRUEBA",
            "nota uno",
        ],
    ]
)


# Los encabezados llevan el prefijo, asi que ninguno coincide con un alias: la prueba dice el campo
# de cada columna, y el origen lo recalcula el backend al confirmar.
CAMPOS = ["pagare", "titular", "telefono", "region", None]


def _limpiar(engine) -> None:
    """Borra lo que crean estas pruebas: sus archivos, sus versiones y lo recordado de sus
    encabezados con el prefijo (y de sus catalogos inventados). Lo demas no se toca."""
    with engine.begin() as cx:
        for sentencia in sentencias_de_limpieza(
            FECHA, PREFIJO, [CATALOGO_DE_PRUEBA, CATALOGO_OTRO]
        ):
            cx.execute(sentencia)


@pytest.fixture
def engine():
    motor = get_engine()
    _limpiar(motor)
    try:
        yield motor
    finally:
        _limpiar(motor)


class Entorno:
    def __init__(self, engine, ahora: datetime = INICIO) -> None:
        self.engine = engine
        self.ahora = ahora
        self.mapeador = MapeadorService(
            RepositorioMapeadorPostgres(engine),
            LectorTabla(),
            [CATALOGO_SABANA_MAPEABLE],
            lambda: self.ahora,
        )
        self.ingesta = IngestaSabanaService(
            RepositorioCargasPostgres(engine), LectorTabla(), lambda: self.ahora
        )

    def borrador(self, *, nombre: str = "datos.csv", contenido: bytes = CSV, **opciones):
        return self.mapeador.crear_borrador(
            SABANA, f"{PREFIJO}{nombre}", contenido, OpcionesLectura(**opciones)
        )

    def cuantos(self, tabla, *condiciones) -> int:
        with self.engine.connect() as cx:
            return cx.execute(
                select(func.count()).select_from(tabla).where(*condiciones)
            ).scalar_one()


@pytest.fixture
def entorno(engine) -> Entorno:
    return Entorno(engine)


# --- La migracion -------------------------------------------------------------------------------


def _configuracion() -> Config:
    configuracion = Config(str(BACKEND / "alembic.ini"))
    configuracion.set_main_option("script_location", str(BACKEND / "migrations"))
    return configuracion


def test_la_migracion_va_vuelve_y_rellena_las_opciones_de_lectura(engine) -> None:
    configuracion = _configuracion()
    command.downgrade(configuracion, "f2c8a4d7b915")
    try:
        insp = inspect(engine)
        assert "borrador_carga_archivo" not in insp.get_table_names()
        assert "mapeo_recordado" not in insp.get_table_names()
        assert {"opciones_lectura", "asignaciones"}.isdisjoint(
            c["name"] for c in insp.get_columns("carga")
        )
        with engine.begin() as cx:  # una version de antes de la migracion
            cx.execute(
                text(
                    "INSERT INTO carga (fecha_corte, version, nombre_archivo, huella_archivo, "
                    "tamano_bytes, hoja) VALUES (:f, 1, 'vieja.xlsx', :h, 10, 'OTRA')"
                ),
                {"f": FECHA, "h": "0" * 64},
            )
    finally:
        command.upgrade(configuracion, "head")

    with engine.connect() as cx:
        fila = cx.execute(
            select(CARGA.c.opciones_lectura, CARGA.c.asignaciones).where(
                CARGA.c.fecha_corte == FECHA
            )
        ).one()
    assert fila.opciones_lectura == {"hoja": "OTRA"}  # el relleno
    assert fila.asignaciones is None
    insp = inspect(engine)
    assert {"borrador_carga_archivo", "mapeo_recordado"} <= set(insp.get_table_names())
    assert {c["name"] for c in insp.get_columns("mapeo_recordado")} == {
        "catalogo_id",
        "encabezado_normalizado",
        "ocurrencia",
        "campo",
        "actualizado_en",
    }


def test_la_estructura_de_la_base_es_la_de_los_modelos(engine) -> None:
    insp = inspect(engine)

    for tabla in (BORRADOR, RECORDADO):
        columnas = {c["name"]: c for c in insp.get_columns(tabla.name)}
        assert set(columnas) == {c.name for c in tabla.columns}
        assert {n for n, c in columnas.items() if c["nullable"]} == {
            c.name for c in tabla.columns if c.nullable
        }
    assert insp.get_pk_constraint("mapeo_recordado")["constrained_columns"] == [
        "catalogo_id",
        "encabezado_normalizado",
        "ocurrencia",
    ]


# --- Borradores ----------------------------------------------------------------------------------


def test_un_borrador_se_crea_se_lee_se_reemplaza_y_se_borra(engine) -> None:
    repositorio = RepositorioMapeadorPostgres(engine)
    nuevo = NuevoBorrador(
        SABANA,
        f"{PREFIJO}a.csv",
        "a" * 64,
        5,
        {"hoja": None},
        {"columnas": [], "campos": []},
        INICIO,
    )

    with repositorio.transaccion() as sesion:
        creado = sesion.crear_borrador(nuevo, b"abcde")
    with repositorio.transaccion() as sesion:
        leido = sesion.obtener_borrador(creado.id)
        contenido = sesion.contenido_de_borrador(creado.id)
        actualizado = sesion.reemplazar_analisis(creado.id, {"hoja": "H"}, {"columnas": [1]})
    with repositorio.transaccion() as sesion:
        reemplazado = sesion.obtener_borrador(creado.id)
        borrado = sesion.borrar_borrador(creado.id)
        otra_vez = sesion.borrar_borrador(creado.id)
        sin_dato = sesion.obtener_borrador(creado.id)

    assert leido == creado and leido.creado_en == INICIO
    assert contenido == b"abcde"
    assert (actualizado.opciones, actualizado.analisis) == ({"hoja": "H"}, {"columnas": [1]})
    assert reemplazado == actualizado
    assert (borrado, otra_vez, sin_dato) == (True, False, None)


def test_los_borradores_vencidos_se_borran_y_los_vigentes_no(engine) -> None:
    repositorio = RepositorioMapeadorPostgres(engine)

    def nuevo(nombre, creado):
        return NuevoBorrador(SABANA, f"{PREFIJO}{nombre}", "b" * 64, 1, {}, {}, creado)

    with repositorio.transaccion() as sesion:
        sesion.crear_borrador(nuevo("viejo.csv", INICIO - timedelta(hours=30)), b"x")
        vigente = sesion.crear_borrador(nuevo("nuevo.csv", INICIO - timedelta(hours=2)), b"y")
        borrados = sesion.borrar_borradores_vencidos(INICIO - timedelta(hours=24))
        restantes = sesion.obtener_borrador(vigente.id)

    assert borrados == 1 and restantes is not None


def test_el_servicio_borra_los_vencidos_al_crear_y_al_arrancar(engine) -> None:
    pasado = Entorno(engine, INICIO - timedelta(hours=30))
    viejo = pasado.borrador(nombre="viejo.csv")
    ahora = Entorno(engine, INICIO)

    ahora.borrador(nombre="nuevo.csv")  # crear borra los vencidos

    with pytest.raises(BorradorNoEncontrado):
        ahora.mapeador.analisis_guardado(viejo.borrador.id)
    pasado.borrador(nombre="otro-viejo.csv")
    assert ahora.mapeador.descartar_vencidos() == 1  # al arrancar


def test_un_borrador_se_toma_con_for_update_hasta_el_fin_de_la_transaccion(engine) -> None:
    borrador = Entorno(engine).borrador()

    with engine.connect() as a:
        transaccion = a.begin()
        SesionMapeadorPostgres(a).obtener_borrador(borrador.borrador.id, bloquear=True)
        with engine.connect() as b, pytest.raises(OperationalError) as error:
            b.execute(
                text("SELECT id FROM borrador_carga_archivo WHERE id = :i FOR UPDATE NOWAIT"),
                {"i": borrador.borrador.id},
            )
        transaccion.rollback()
    # Se comprueba la clase y el codigo, no el mensaje: el servidor habla el idioma del usuario.
    assert isinstance(error.value.orig, LockNotAvailable)
    assert error.value.orig.sqlstate == "55P03"


# --- Recordados ----------------------------------------------------------------------------------


def test_los_recordados_se_guardan_por_lote_se_actualizan_y_se_separan_por_catalogo(engine) -> None:
    repositorio = RepositorioMapeadorPostgres(engine)
    with repositorio.transaccion() as sesion:
        sesion.guardar_recordados(
            CATALOGO_DE_PRUEBA,
            {("pagare", 1): "pagare", ("pagare", 2): "duplicado", ("x", 1): None},
            INICIO,
        )
        sesion.guardar_recordados(CATALOGO_OTRO, {("pagare", 1): "otro_campo"}, INICIO)
    with repositorio.transaccion() as sesion:
        sesion.guardar_recordados(
            CATALOGO_DE_PRUEBA,
            {("pagare", 2): None, ("y", 1): "campo_y"},
            INICIO + timedelta(hours=1),
        )
        recordados = sesion.recordados(CATALOGO_DE_PRUEBA)
        otro = sesion.recordados(CATALOGO_OTRO)
        sesion.guardar_recordados(CATALOGO_OTRO, {}, INICIO)  # un lote vacio no hace nada

    assert recordados == {
        ("pagare", 1): "pagare",
        ("pagare", 2): None,  # se actualizo: ya no es «duplicado»
        ("x", 1): None,
        ("y", 1): "campo_y",
    }
    assert otro == {("pagare", 1): "otro_campo"}


def test_un_no_cargar_recordado_es_null_de_sql_y_no_un_texto(entorno) -> None:
    with RepositorioMapeadorPostgres(entorno.engine).transaccion() as sesion:
        sesion.guardar_recordados(CATALOGO_DE_PRUEBA, {("x", 1): None}, INICIO)

    assert (
        entorno.cuantos(
            RECORDADO, RECORDADO.c.catalogo_id == CATALOGO_DE_PRUEBA, RECORDADO.c.campo.is_(None)
        )
        == 1
    )


# --- Confirmar un borrador: una transaccion ------------------------------------------------------


def _asignaciones(analizado, campos=None) -> list[Asignacion]:
    return asignar(analizado, CAMPOS if campos is None else campos)


def test_el_ciclo_completo_en_postgres_incluidos_los_dos_pagare(entorno) -> None:
    contenido = csv_de(
        [
            [f"{PREFIJO}Pagare", f"{PREFIJO}Zona", f"{PREFIJO}Pagare"],
            ["000000000000000001", "x", "000000000000000001"],
        ]
    )
    campos = ["pagare", None, "pagare_duplicado"]
    primero = entorno.borrador(nombre="pagare.csv", contenido=contenido)

    registrada = entorno.ingesta.registrar_desde_borrador(
        primero.borrador.id, FECHA, _asignaciones(primero, campos)
    )
    segundo = entorno.borrador(nombre="pagare.csv", contenido=contenido)

    assert [c.estado for c in segundo.analisis.columnas] == [EstadoEncabezado.RECORDADO] * 3
    assert [c.sugerido for c in segundo.analisis.columnas] == campos
    assert entorno.mapeador.validar(segundo.borrador.id, aceptar_todo(segundo)) == ()
    with entorno.engine.connect() as cx:
        carga = cx.execute(select(CARGA).where(CARGA.c.id == registrada.carga.id)).one()
    assert carga.estado == EstadoCarga.EN_COLA.value
    assert carga.opciones_lectura["separador"] == ";" and carga.hoja == ""
    assert [(a["indice"], a["campo"]) for a in carga.asignaciones] == [
        (0, "pagare"),
        (1, None),
        (2, "pagare_duplicado"),
    ]
    assert entorno.cuantos(BORRADOR, BORRADOR.c.id == primero.borrador.id) == 0


def test_la_segunda_confirmacion_del_mismo_borrador_no_lo_encuentra(entorno) -> None:
    analizado = entorno.borrador()
    asignaciones = _asignaciones(analizado)
    entorno.ingesta.registrar_desde_borrador(analizado.borrador.id, FECHA, asignaciones)

    with pytest.raises(BorradorNoEncontrado):
        entorno.ingesta.registrar_desde_borrador(analizado.borrador.id, FECHA, asignaciones)

    assert entorno.cuantos(CARGA, CARGA.c.fecha_corte == FECHA) == 1


def test_confirmar_con_problemas_no_crea_nada_en_postgres(entorno) -> None:
    analizado = entorno.borrador()
    sin_pagare = [Asignacion(0, None, OrigenAsignacion.MANUAL), *_asignaciones(analizado)[1:]]

    with pytest.raises(MapeoConProblemas):
        entorno.ingesta.registrar_desde_borrador(analizado.borrador.id, FECHA, sin_pagare)

    assert entorno.cuantos(CARGA, CARGA.c.fecha_corte == FECHA) == 0
    assert entorno.cuantos(BORRADOR, BORRADOR.c.id == analizado.borrador.id) == 1


def test_confirmar_es_todo_o_nada_en_postgres(entorno, monkeypatch) -> None:
    analizado = entorno.borrador()

    def falla(*args, **kwargs):
        raise RuntimeError("fallo simulado al guardar lo recordado")

    monkeypatch.setattr(SesionCargasPostgres, "guardar_recordados", falla)

    with pytest.raises(RuntimeError):
        entorno.ingesta.registrar_desde_borrador(
            analizado.borrador.id, FECHA, _asignaciones(analizado)
        )

    assert entorno.cuantos(CARGA, CARGA.c.fecha_corte == FECHA) == 0  # ni la carga ni su archivo
    assert entorno.cuantos(BORRADOR, BORRADOR.c.id == analizado.borrador.id) == 1


def test_una_carga_confirmada_se_procesa_con_su_separador_y_su_codificacion(entorno) -> None:
    analizado = entorno.borrador()
    carga = entorno.ingesta.registrar_desde_borrador(
        analizado.borrador.id, FECHA, _asignaciones(analizado)
    ).carga

    resultado = entorno.ingesta.procesar_carga(carga.id)

    assert resultado.estado is EstadoCarga.TERMINADA
    with entorno.engine.connect() as cx:
        fila = cx.execute(select(FILA).where(FILA.c.carga_id == carga.id)).one()
        mapeo = cx.execute(select(CARGA.c.mapeo).where(CARGA.c.id == carga.id)).scalar_one()
    assert fila.region == "REGIÓN PRUEBA"
    assert fila.extras == {f"{PREFIJO}Observación libre": "nota uno"}  # «No cargar» va al crudo
    assert mapeo["ignoradas"] == {"5": f"{PREFIJO}Observación libre"}
    assert set(mapeo) == {"columnas", "desconocidas", "faltantes", "origenes", "ignoradas"}


def test_una_carga_por_alias_guarda_las_asignaciones_como_null_de_sql(entorno) -> None:
    carga = entorno.ingesta.registrar_carga(FECHA, "sabana.xlsx", b"contenido").carga

    assert entorno.cuantos(CARGA, CARGA.c.id == carga.id, CARGA.c.asignaciones.is_(None)) == 1
    with entorno.engine.connect() as cx:
        opciones = cx.execute(
            select(CARGA.c.opciones_lectura).where(CARGA.c.id == carga.id)
        ).scalar_one()
    assert opciones == {"hoja": "VENCIDA"}
