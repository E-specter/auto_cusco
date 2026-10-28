r"""Mide cuanto tarda la lista de valores de un filtro (T-FV-B2, RF-67) con una sabana sintetica.

Uso, desde backend/ y con la base de pruebas migrada (nunca la de trabajo: el script se detiene si
DB_NAME no termina en _test):

    uv run python scripts/generar_sabana_sintetica.py sabana_46k.xlsx --filas 46000
    $env:DB_NAME = "auto_cusco_test"
    uv run python scripts/medir_valores_filtro.py sabana_46k.xlsx
    uv run python scripts/medir_valores_filtro.py sabana_46k.xlsx --repeticiones 50 --umbral 100

Ingesta la sabana en una fecha de 2099, le pone a `tipo_producto` unos 10 valores y le agrega un
campo adicional de texto, `ad_medicion_valores`, con unos 50 (se crea y se borra aqui; las
definiciones y los valores no quedan en la base). Mide, con p50 y p95 sobre las repeticiones:

1. la decision del umbral (`DISTINCT ... LIMIT umbral + 1`, sobre la fecha entera);
2. la lista sin filtros y con tres filtros de arriba (las dos consultas del endpoint);
3. un campo que supera el umbral (el documento), que tiene que cortar pronto.

PRESUPUESTO (plan.md §29): p95 menor de 150 ms por pedido, sumando las dos consultas. Desde T-FV-B3
el caso de uso guarda en memoria la decision del umbral y las listas por (carga vigente, campo,
...), asi que se mide aparte la PRIMERA llamada (sin memoria: un servicio nuevo en cada
repeticion) y las SIGUIENTES (con la memoria llena), y despues las consultas sueltas, para
repartir el costo y comparar el orden «umbral primero» con agrupar primero (fila REFERENCIA).
Solo imprime tiempos y cantidades: ningun valor.
"""

import argparse
import statistics
import sys
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, insert, text  # noqa: E402

from app.adapters.input.lector_tabla import LectorTabla  # noqa: E402
from app.adapters.persistence.db import get_engine  # noqa: E402
from app.adapters.persistence.modelos import (  # noqa: E402
    CampoAdicional,
    Carga,
    CargaAuditoria,
)
from app.adapters.persistence.repositorio_cargas_postgres import (  # noqa: E402
    RepositorioCargasPostgres,
)
from app.adapters.persistence.repositorio_cartera_postgres import (  # noqa: E402
    RepositorioCarteraPostgres,
)
from app.adapters.persistence.repositorio_mapeador_postgres import (  # noqa: E402
    RepositorioCamposAdicionalesPostgres,
)
from app.core.config import (  # noqa: E402
    UMBRAL_VALORES_FILTRO_POR_DEFECTO,
    exigir_base_de_pruebas,
    get_settings,
)
from app.core.entities.cartera import Filtro, Operador  # noqa: E402
from app.core.services.ingesta_sabana.catalogo import CATALOGO_SABANA  # noqa: E402
from app.core.services.ingesta_sabana.servicio import IngestaSabanaService  # noqa: E402
from app.core.services.seleccion_cartera.cache_valores import CacheValoresFiltro  # noqa: E402
from app.core.services.seleccion_cartera.campos import CatalogoCartera  # noqa: E402
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService  # noqa: E402

FECHA = date(2099, 6, 1)
CARGA, AUDITORIA = Carga.__table__, CargaAuditoria.__table__
ADICIONAL = CampoAdicional.__table__
NOMBRE_ADICIONAL = "ad_medicion_valores"
PRESUPUESTO_P95_MS = 150.0
BASE_DE_10 = "tipo_producto"
SUPERA_EL_UMBRAL = "documento_numero"


def _limpiar(engine) -> None:
    with engine.begin() as cx:
        cx.execute(delete(CARGA).where(CARGA.c.fecha_corte == FECHA))
        cx.execute(delete(AUDITORIA).where(AUDITORIA.c.fecha_corte == FECHA))
        cx.execute(delete(ADICIONAL).where(ADICIONAL.c.nombre == NOMBRE_ADICIONAL))


def _preparar_valores(engine, carga_id: int) -> None:
    """Unos 10 valores en un campo base y unos 50 en un adicional, sin tocar nada fuera de la
    carga de la medicion."""
    with engine.begin() as cx:
        cx.execute(
            text(
                f"UPDATE carga_fila SET {BASE_DE_10} = 'TIPO ' || (numero_fila % 10) "
                "WHERE carga_id = :carga"
            ),
            {"carga": carga_id},
        )
        cx.execute(
            text(
                "UPDATE carga_fila SET adicionales = jsonb_build_object("
                f"'{NOMBRE_ADICIONAL}', 'VALOR ' || (numero_fila % 50)) WHERE carga_id = :carga"
            ),
            {"carga": carga_id},
        )
        cx.execute(
            insert(ADICIONAL).values(
                nombre=NOMBRE_ADICIONAL,
                catalogo_id=CATALOGO_SABANA.id,
                nombre_legible="Medicion de valores",
                nombre_legible_normalizado="medicion de valores",
                tipo="texto",
                encabezado_origen="medicion de valores",
            )
        )


def _tiempos(accion: Callable[[], object], repeticiones: int) -> list[float]:
    medidos = []
    for _ in range(repeticiones):
        inicio = time.perf_counter()
        accion()
        medidos.append((time.perf_counter() - inicio) * 1000)
    return medidos


def _p(medidos: list[float], percentil: int) -> float:
    ordenados = sorted(medidos)
    return ordenados[min(len(ordenados) - 1, round(percentil / 100 * (len(ordenados) - 1)))]


def _resumen(medidos: list[float]) -> tuple[float, float]:
    return statistics.median(medidos), _p(medidos, 95)


def main() -> None:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("sabana", type=Path)
    analizador.add_argument("--repeticiones", type=int, default=30)
    analizador.add_argument("--umbral", type=int, default=UMBRAL_VALORES_FILTRO_POR_DEFECTO)
    opciones = analizador.parse_args()

    motivo = exigir_base_de_pruebas(get_settings())
    if motivo:
        sys.exit(motivo)
    engine = get_engine()
    _limpiar(engine)
    try:
        ingesta = IngestaSabanaService(RepositorioCargasPostgres(engine), LectorTabla())
        inicio = time.perf_counter()
        carga = ingesta.registrar_carga(FECHA, opciones.sabana.name, opciones.sabana.read_bytes())
        resultado = ingesta.procesar_carga(carga.carga.id)
        print(f"ingesta: {time.perf_counter() - inicio:.1f}s vigente={resultado.vigente}")
        _preparar_valores(engine, carga.carga.id)

        catalogo = CatalogoCartera(RepositorioCamposAdicionalesPostgres(engine))
        repo = RepositorioCarteraPostgres(engine, catalogo)

        def servicio_nuevo() -> ConsultaCarteraService:
            """Como un pedido de la API sin memoria: un servicio con su memoria vacia."""
            return ConsultaCarteraService(
                repo, catalogo, umbral_valores=opciones.umbral, cache_valores=CacheValoresFiltro()
            )

        arriba = [
            Filtro("dias_atraso", Operador.MAYOR, (-10,)),
            Filtro("telefono", Operador.NO_VACIO),
            Filtro("region", Operador.NO_EN, ("TACNA", None)),
        ]
        tope = opciones.umbral + 1
        n = opciones.repeticiones
        total = repo.consultar(FECHA, (), None, 1, 0)[0]
        print(f"productos: {total}; umbral: {opciones.umbral}; repeticiones: {n}")
        servicio_nuevo().valores(FECHA, BASE_DE_10)  # calienta la base: no es lo que se mide

        # Los pedidos: (nombre, campo, filtros de arriba).
        pedidos = [
            ("base (~10), sin filtros", BASE_DE_10, []),
            ("base (~10), con 3 filtros", BASE_DE_10, arriba),
            ("adicional (~50), sin filtros", NOMBRE_ADICIONAL, []),
            ("adicional (~50), con 3 filtros", NOMBRE_ADICIONAL, arriba),
            ("campo que supera (documento)", SUPERA_EL_UMBRAL, []),
        ]
        print("\nPEDIDOS a /cartera/valores (decision + lista, como los atiende la API)")
        print(
            f"{'pedido':34} {'1.a p50':>8} {'1.a p95':>8} {'sig. p50':>9} {'sig. p95':>9}"
            "  p95 < 150"
        )
        fuera = []
        for nombre, campo, filtros in pedidos:
            # 1.a llamada: sin memoria. Un servicio nuevo en cada repeticion.
            primeras = _tiempos(lambda c=campo, f=filtros: servicio_nuevo().valores(FECHA, c, f), n)
            # Siguientes: con la memoria ya llena (la decision y la lista de esa cascada).
            servicio = servicio_nuevo()
            servicio.valores(FECHA, campo, filtros)
            siguientes = _tiempos(lambda s=servicio, c=campo, f=filtros: s.valores(FECHA, c, f), n)
            (p50a, p95a), (p50b, p95b) = _resumen(primeras), _resumen(siguientes)
            ok = p95a < PRESUPUESTO_P95_MS and p95b < PRESUPUESTO_P95_MS
            if not ok:
                fuera.append(nombre)
            marca = "ok" if ok else "FUERA (1.a)" if p95a >= PRESUPUESTO_P95_MS else "FUERA (sig.)"
            print(f"{nombre:34} {p50a:8.1f} {p95a:8.1f} {p50b:9.1f} {p95b:9.1f}  {marca}")

        # Las consultas sueltas, para repartir el costo de la 1.a llamada y elegir el orden:
        # umbral primero (corta pronto en un campo de alta cardinalidad) o agrupar primero.
        print("\nCONSULTAS SUELTAS (una sola, sin memoria)")
        print(f"{'consulta':44} {'p50 ms':>8} {'p95 ms':>8}")
        sueltas = [
            ("umbral: base (~10)", lambda: repo.distintos_hasta(FECHA, BASE_DE_10, tope)),
            (
                "umbral: adicional (~50)",
                lambda: repo.distintos_hasta(FECHA, NOMBRE_ADICIONAL, tope),
            ),
            (
                "umbral: supera (documento)",
                lambda: repo.distintos_hasta(FECHA, SUPERA_EL_UMBRAL, tope),
            ),
            ("lista: base, sin filtros", lambda: repo.valores_de(FECHA, BASE_DE_10, [])),
            ("lista: base, con 3 filtros", lambda: repo.valores_de(FECHA, BASE_DE_10, arriba)),
            ("lista: adicional, sin filtros", lambda: repo.valores_de(FECHA, NOMBRE_ADICIONAL, [])),
            (
                "REFERENCIA agrupar el que supera (documento)",
                lambda: repo.valores_de(FECHA, SUPERA_EL_UMBRAL, []),
            ),
        ]
        for nombre, accion in sueltas:
            accion()
            p50, p95 = _resumen(_tiempos(accion, n))
            print(f"{nombre:44} {p50:8.1f} {p95:8.1f}")
        print(
            "\n«REFERENCIA»: lo que costaria resolver la decision agrupando en una sola consulta "
            "un campo de alta cardinalidad (un GROUP BY no corta temprano como el DISTINCT ... "
            "LIMIT): si sale mucho mas que «umbral: supera», el orden «umbral primero» es el bueno."
        )
        print(
            "\nPresupuesto cumplido (p95 < 150 ms por pedido, en la 1.a llamada y en las demas)"
            if not fuera
            else f"\nFuera de presupuesto: {', '.join(fuera)}."
        )
    finally:
        _limpiar(engine)


if __name__ == "__main__":
    main()
