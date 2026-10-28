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

PRESUPUESTO (plan.md §29): p95 menor de 150 ms por lista, con las dos consultas. Si no se cumple,
la primera opcion es guardar en memoria la decision del umbral por (carga vigente, campo), que no
cambia mientras la version vigente sea la misma. Solo imprime tiempos y cantidades: ningun valor.
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
    accion()  # calienta: el plan y la cache de la base no son lo que se mide
    medidos = []
    for _ in range(repeticiones):
        inicio = time.perf_counter()
        accion()
        medidos.append((time.perf_counter() - inicio) * 1000)
    return medidos


def _p(medidos: list[float], percentil: int) -> float:
    ordenados = sorted(medidos)
    return ordenados[min(len(ordenados) - 1, round(percentil / 100 * (len(ordenados) - 1)))]


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
        servicio = ConsultaCarteraService(repo, catalogo, umbral_valores=opciones.umbral)
        arriba = [
            Filtro("dias_atraso", Operador.MAYOR, (-10,)),
            Filtro("telefono", Operador.NO_VACIO),
            Filtro("region", Operador.NO_EN, ("TACNA", None)),
        ]
        tope = opciones.umbral + 1
        n = opciones.repeticiones
        casos = [
            ("umbral: campo base (~10)", lambda: repo.distintos_hasta(FECHA, BASE_DE_10, tope)),
            (
                "umbral: adicional (~50)",
                lambda: repo.distintos_hasta(FECHA, NOMBRE_ADICIONAL, tope),
            ),
            (
                "umbral: supera (documento)",
                lambda: repo.distintos_hasta(FECHA, SUPERA_EL_UMBRAL, tope),
            ),
            ("lista: base sin filtros", lambda: servicio.valores(FECHA, BASE_DE_10)),
            ("lista: base con 3 filtros", lambda: servicio.valores(FECHA, BASE_DE_10, arriba)),
            ("lista: adicional sin filtros", lambda: servicio.valores(FECHA, NOMBRE_ADICIONAL)),
            (
                "lista: adicional con 3 filtros",
                lambda: servicio.valores(FECHA, NOMBRE_ADICIONAL, arriba),
            ),
            ("lista: campo que supera", lambda: servicio.valores(FECHA, SUPERA_EL_UMBRAL)),
        ]
        total = repo.consultar(FECHA, (), None, 1, 0)[0]
        print(f"productos: {total}; umbral: {opciones.umbral}; repeticiones: {n}\n")
        print(f"{'caso':34} {'p50 ms':>8} {'p95 ms':>8}  presupuesto")
        fuera = []
        for nombre, accion in casos:
            medidos = _tiempos(accion, n)
            p50, p95 = statistics.median(medidos), _p(medidos, 95)
            es_lista = nombre.startswith("lista")
            marca = ""
            if es_lista:
                marca = "ok" if p95 < PRESUPUESTO_P95_MS else "FUERA (> 150 ms)"
                if p95 >= PRESUPUESTO_P95_MS:
                    fuera.append(nombre)
            print(f"{nombre:34} {p50:8.1f} {p95:8.1f}  {marca}")
        print(
            "\nPresupuesto cumplido (p95 < 150 ms por lista)"
            if not fuera
            else f"\nFuera de presupuesto: {', '.join(fuera)}. Primera opcion: guardar en memoria "
            "la decision del umbral por (carga vigente, campo)."
        )
    finally:
        _limpiar(engine)


if __name__ == "__main__":
    main()
