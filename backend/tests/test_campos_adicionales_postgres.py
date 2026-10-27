r"""Los campos adicionales con PostgreSQL real (T-CA-B2, RF-64 a RF-66).

Corre solo con AUTO_CUSCO_DB_TESTS=1 y la base de pruebas migrada (sufijo _test). Usa la fecha de
corte 2099-08-05, encabezados y nombres con el prefijo `b2ca-` y archivos sinteticos, y al terminar
borra lo que creo. Las equivalentes sin base estan en `test_campos_adicionales_ciclo.py`, el SQL
compilado en `test_repositorio_cartera_adicionales_sql.py` y la migracion en
`test_campos_adicionales_migracion.py`.

    PowerShell:  .\scripts\verificar.ps1 -ConBase
"""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete, inspect, select, text

from app.adapters.input.lector_tabla import LectorTabla
from app.adapters.persistence.db import get_engine
from app.adapters.persistence.modelos import CampoAdicional as ModeloCampoAdicional
from app.adapters.persistence.modelos import CargaFila
from app.adapters.persistence.repositorio_cargas_postgres import RepositorioCargasPostgres
from app.adapters.persistence.repositorio_cartera_postgres import RepositorioCarteraPostgres
from app.adapters.persistence.repositorio_mapeador_postgres import (
    RepositorioCamposAdicionalesPostgres,
    RepositorioMapeadorPostgres,
)
from app.core.entities.campos_adicionales import NombreDeCampoRepetido, TipoAdicional
from app.core.entities.cartera import Filtro, Funcion, Indicador, Operador
from app.core.entities.mapeador import Asignacion, OrigenAsignacion
from app.core.services.borradores_carga.servicio import MapeadorService
from app.core.services.ingesta_sabana.mapeable import CATALOGO_SABANA_MAPEABLE
from app.core.services.ingesta_sabana.servicio import IngestaSabanaService
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from tests.mapeador_postgres_comun import sentencias_de_limpieza
from tests.test_mapeador_ciclo import SABANA, csv_de

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

FECHA = date(2099, 8, 5)
INICIO = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)
PREFIJO = "b2ca-"
ADICIONAL = ModeloCampoAdicional.__table__

CSV = csv_de(
    [
        [f"{PREFIJO}{h}" for h in ["Pagare", "Zona", "Monto", "Visita"]],
        ["000000000000000001", "SUR", "150.50", "03/08/2099"],
        ["000000000000000002", "NORTE", "7", "04/08/2099"],
        ["000000000000000003", "SUR", "", ""],
    ]
)


def _limpiar(engine) -> None:
    with engine.begin() as cx:
        for sentencia in sentencias_de_limpieza(FECHA, PREFIJO):
            cx.execute(sentencia)
        cx.execute(
            delete(ADICIONAL).where(ADICIONAL.c.nombre.startswith("ad_b2ca_", autoescape=True))
        )


@pytest.fixture
def engine():
    motor = get_engine()
    _limpiar(motor)
    try:
        yield motor
    finally:
        _limpiar(motor)


class Entorno:
    def __init__(self, engine) -> None:
        self.engine = engine
        self.definiciones = RepositorioCamposAdicionalesPostgres(engine)
        self.mapeador = MapeadorService(
            RepositorioMapeadorPostgres(engine),
            LectorTabla(),
            [CATALOGO_SABANA_MAPEABLE],
            lambda: INICIO,
        )
        self.ingesta = IngestaSabanaService(
            RepositorioCargasPostgres(engine),
            LectorTabla(),
            lambda: INICIO,
            adicionales=self.definiciones,
        )

    def borrador(self, nombre: str = "datos.csv"):
        return self.mapeador.crear_borrador(SABANA, f"{PREFIJO}{nombre}", CSV)

    def catalogo(self) -> CatalogoCartera:
        return CatalogoCartera(self.definiciones)

    def cartera(self) -> RepositorioCarteraPostgres:
        catalogo = self.catalogo()
        return RepositorioCarteraPostgres(self.engine, catalogo)


def _campos_del_ciclo(entorno: Entorno, analizado) -> list[str]:
    tecnicos = []
    for indice, nombre, tipo in (
        (1, f"{PREFIJO}Zona", TipoAdicional.TEXTO),
        (2, f"{PREFIJO}Monto", TipoAdicional.NUMERO),
        (3, f"{PREFIJO}Visita", TipoAdicional.FECHA),
    ):
        campo, _ = entorno.mapeador.crear_campo_adicional(
            analizado.borrador.id, indice, nombre + " extra", tipo
        )
        tecnicos.append(campo.nombre)
    return tecnicos


def _procesar(entorno: Entorno, analizado, tecnicos: list[str | None]):
    asignaciones = [
        Asignacion(0, "pagare", OrigenAsignacion.MANUAL),
        *(Asignacion(i + 1, nombre, OrigenAsignacion.MANUAL) for i, nombre in enumerate(tecnicos)),
    ]
    carga = entorno.ingesta.registrar_desde_borrador(
        analizado.borrador.id, FECHA, asignaciones
    ).carga
    entorno.ingesta.procesar_carga(carga.id)
    return carga


def test_la_base_migrada_tiene_la_tabla_y_la_columna(engine) -> None:
    inspector = inspect(engine)

    columnas = {c["name"]: c for c in inspector.get_columns("campo_adicional")}
    assert {"nombre", "orden", "catalogo_id", "nombre_legible_normalizado", "tipo"} <= set(columnas)
    fila = {c["name"]: c for c in inspector.get_columns("carga_fila")}
    assert fila["adicionales"]["nullable"] and "JSONB" in str(fila["adicionales"]["type"])
    unicos = {tuple(u["column_names"]) for u in inspector.get_unique_constraints("campo_adicional")}
    assert ("catalogo_id", "nombre_legible_normalizado") in unicos


def test_ciclo_completo_crear_asignar_confirmar_procesar_y_consultar(engine) -> None:
    entorno = Entorno(engine)
    analizado = entorno.borrador()
    zona, monto, visita = _campos_del_ciclo(entorno, analizado)

    carga = _procesar(entorno, analizado, [zona, monto, visita])

    with engine.connect() as cx:
        guardado = cx.execute(
            select(CargaFila.__table__.c.pagare, CargaFila.__table__.c.adicionales)
            .where(CargaFila.__table__.c.carga_id == carga.id)
            .order_by(CargaFila.__table__.c.pagare)
        ).all()
    assert [f.adicionales for f in guardado] == [
        {zona: "SUR", monto: "150.5", visita: "2099-08-03"},
        {zona: "NORTE", monto: "7", visita: "2099-08-04"},
        {zona: "SUR"},
    ]
    cartera = entorno.cartera()
    total, filas = cartera.consultar(
        FECHA, [Filtro(monto, Operador.MAYOR, (Decimal(100),))], None, 10, 0
    )
    assert total == 1 and filas[0][monto] == Decimal("150.5")
    entre_fechas = Filtro(visita, Operador.ENTRE, (date(2099, 8, 4), date(2099, 8, 9)))
    assert cartera.consultar(FECHA, [entre_fechas], None, 10, 0)[0] == 1
    assert cartera.consultar(FECHA, [Filtro(zona, Operador.IGUAL, ("SUR",))], None, 10, 0)[0] == 2
    assert cartera.consultar(FECHA, [Filtro(monto, Operador.VACIO)], None, 10, 0)[0] == 1
    metricas = cartera.metricas(
        FECHA,
        [],
        [Indicador("suma", Funcion.SUMA, monto), Indicador("maximo", Funcion.MAXIMO, monto)],
    )
    assert metricas.adicionales == {"suma": Decimal("157.5"), "maximo": Decimal("150.5")}
    grupos = cartera.segmentar(FECHA, zona, [])
    assert {g.valor: g.cuentas for g in grupos} == {"SUR": 2, "NORTE": 1}


def test_renombrar_no_rompe_una_consulta_y_archivar_la_deja_funcionando(engine) -> None:
    entorno = Entorno(engine)
    analizado = entorno.borrador()
    zona, monto, visita = _campos_del_ciclo(entorno, analizado)
    _procesar(entorno, analizado, [zona, monto, visita])
    filtro = Filtro(monto, Operador.MAYOR, (Decimal(100),))

    entorno.mapeador.cambiar_campo_adicional(SABANA, monto, "Otro nombre b2ca")
    renombrado = entorno.cartera().consultar(FECHA, [filtro], None, 10, 0)[0]
    entorno.mapeador.cambiar_campo_adicional(SABANA, monto, archivado=True)
    archivado = entorno.cartera().consultar(FECHA, [filtro], None, 10, 0)[0]

    assert (renombrado, archivado) == (1, 1)
    assert monto not in entorno.catalogo().ofrecidos()


def test_una_carga_sin_adicionales_deja_la_columna_en_null(engine) -> None:
    entorno = Entorno(engine)
    analizado = entorno.borrador()
    # Las otras tres columnas en «No cargar»: el mapeo exige decidir cada columna (RF-60).
    carga = _procesar(entorno, analizado, [None, None, None])

    with engine.connect() as cx:
        valores = cx.execute(
            text(
                "SELECT adicionales IS NULL, jsonb_typeof(adicionales) FROM carga_fila "
                "WHERE carga_id = :c"
            ),
            {"c": carga.id},
        ).all()

    assert valores and all(es_null and tipo is None for es_null, tipo in valores)


def test_dos_creaciones_a_la_vez_del_mismo_nombre_dejan_una_sola(engine) -> None:
    entorno = Entorno(engine)
    primero, segundo = entorno.borrador("a.csv"), entorno.borrador("b.csv")

    def crear(analizado):
        try:
            return entorno.mapeador.crear_campo_adicional(
                analizado.borrador.id, 1, f"{PREFIJO}Zona", TipoAdicional.TEXTO
            )[0]
        except NombreDeCampoRepetido as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(crear, [primero, segundo]))

    assert sum(isinstance(r, NombreDeCampoRepetido) for r in resultados) == 1
    with engine.connect() as cx:
        creados = cx.execute(
            select(ADICIONAL.c.nombre).where(ADICIONAL.c.nombre.startswith("ad_b2ca_"))
        ).all()
    assert len(creados) == 1


def test_dos_nombres_distintos_con_el_mismo_slug_a_la_vez_no_se_pisan(engine) -> None:
    entorno = Entorno(engine)
    primero, segundo = entorno.borrador("a.csv"), entorno.borrador("b.csv")
    nombres = [f"{PREFIJO}Zona-extra", f"{PREFIJO}Zona/extra"]

    def crear(args):
        analizado, nombre, indice = args
        return entorno.mapeador.crear_campo_adicional(
            analizado.borrador.id, indice, nombre, TipoAdicional.TEXTO
        )[0].nombre

    with ThreadPoolExecutor(max_workers=2) as pool:
        tecnicos = list(pool.map(crear, [(primero, nombres[0], 1), (segundo, nombres[1], 2)]))

    assert sorted(tecnicos) == ["ad_b2ca_zona_extra", "ad_b2ca_zona_extra_2"]


def test_el_nombre_legible_es_unico_por_catalogo_tambien_en_la_base(engine) -> None:
    entorno = Entorno(engine)
    analizado = entorno.borrador()
    entorno.mapeador.crear_campo_adicional(
        analizado.borrador.id, 1, f"{PREFIJO}Zona", TipoAdicional.TEXTO
    )

    with pytest.raises(NombreDeCampoRepetido):
        entorno.mapeador.crear_campo_adicional(
            analizado.borrador.id, 2, f"  {PREFIJO.upper()}ZONA ", TipoAdicional.TEXTO
        )
    assert len(entorno.definiciones.listar()) >= 1
