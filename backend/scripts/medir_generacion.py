r"""Mide tiempo y memoria de la generacion de cargas con una sabana sintetica.

Uso, desde backend/ y con la base migrada:

    uv run python scripts/generar_sabana_sintetica.py sabana_120k.xlsx --filas 120000
    uv run python scripts/medir_generacion.py sabana_120k.xlsx 60000,120000

Ingesta la sabana en una fecha de 2099, genera con una definicion corta (6
columnas) y otra con todos los campos, escribe CSV y XLSX, y borra todo al
terminar. Solo imprime agregados. Los resultados de referencia estan en
docs/generacion-cargas.md, seccion 4.
"""

import gc
import sys
import time
import tracemalloc
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete  # noqa: E402

from app.adapters.input.lector_calamine import LectorCalamine  # noqa: E402
from app.adapters.output import exportadores  # noqa: E402
from app.adapters.persistence.db import get_engine  # noqa: E402
from app.adapters.persistence.modelos import Carga, CargaAuditoria  # noqa: E402
from app.adapters.persistence.repositorio_cargas_postgres import (  # noqa: E402
    RepositorioCargasPostgres,
)
from app.adapters.persistence.repositorio_cartera_postgres import (  # noqa: E402
    RepositorioCarteraPostgres,
)
from app.core.entities.mapeo import CampoSalida, DefinicionCarga, TipoSalida  # noqa: E402
from app.core.services.generacion_cargas import servicio as generacion  # noqa: E402
from app.core.services.ingesta_sabana.servicio import IngestaSabanaService  # noqa: E402
from app.core.services.seleccion_cartera.campos import CAMPOS_CARTERA  # noqa: E402
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService  # noqa: E402

FECHA = date(2099, 5, 1)
CARGA, AUDITORIA = Carga.__table__, CargaAuditoria.__table__

CORTA = DefinicionCarga(
    nombre="corta",
    campos=(
        CampoSalida(nombre="anexo", plantilla="1010", tipo=TipoSalida.NUMERO),
        CampoSalida(nombre="numero", plantilla="51[@telefono]"),
        CampoSalida(nombre="pagare", plantilla="[@pagare]"),
        CampoSalida(
            nombre="deuda", plantilla="[@saldo_capital_pendiente]", tipo=TipoSalida.FINANCIERO
        ),
        CampoSalida(
            nombre="vence",
            plantilla="[@fecha_vencimiento_cuota]",
            tipo=TipoSalida.FECHA,
            formato_fecha="%d/%m/%Y",
        ),
        CampoSalida(nombre="info", plantilla="doc=[@documento_numero] region=[@region]"),
    ),
)
# Peor caso: una columna por cada campo de la cartera.
COMPLETA = DefinicionCarga(
    nombre="completa",
    campos=tuple(CampoSalida(nombre=c, plantilla=f"[@{c}]") for c in CAMPOS_CARTERA),
)


def _limpiar(engine) -> None:
    with engine.begin() as cx:
        cx.execute(delete(CARGA).where(CARGA.c.fecha_corte == FECHA))
        cx.execute(delete(AUDITORIA).where(AUDITORIA.c.fecha_corte == FECHA))


def main() -> None:
    sabana = Path(sys.argv[1])
    cantidades = [int(x) for x in sys.argv[2].split(",")]
    engine = get_engine()
    _limpiar(engine)
    try:
        ingesta = IngestaSabanaService(RepositorioCargasPostgres(engine), LectorCalamine())
        inicio = time.perf_counter()
        carga = ingesta.registrar_carga(FECHA, sabana.name, sabana.read_bytes()).carga
        resultado = ingesta.procesar_carga(carga.id)
        print(f"ingesta: {time.perf_counter() - inicio:.1f}s vigente={resultado.vigente}")

        generacion.CANTIDAD_MAXIMA = max(generacion.CANTIDAD_MAXIMA, *cantidades)
        servicio = generacion.GeneracionCargasService(
            ConsultaCarteraService(RepositorioCarteraPostgres(engine))
        )
        for definicion in (CORTA, COMPLETA):
            for cantidad in cantidades:
                inicio = time.perf_counter()
                generada = servicio.generar(FECHA, definicion, cantidad=cantidad)
                t_generar = time.perf_counter() - inicio
                for formato in ("csv", "xlsx"):
                    inicio = time.perf_counter()
                    archivo = exportadores.exportar(generada.tabla, formato)
                    print(
                        f"{definicion.nombre:9} n={cantidad:>7} generados={generada.generados:>7} "
                        f"errores={len(generada.errores):>5} generar={t_generar:6.1f}s "
                        f"{formato}={time.perf_counter() - inicio:6.1f}s "
                        f"tam={archivo.tamano / 1e6:6.1f}MB"
                    )
                del generada, archivo
                gc.collect()
            tracemalloc.start()
            generada = servicio.generar(FECHA, definicion, cantidad=max(cantidades))
            exportadores.exportar(generada.tabla, "xlsx")
            _, pico = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            print(f"{definicion.nombre:9} memoria pico de Python con XLSX: {pico / 1e6:.0f}MB")
            del generada
            gc.collect()
    finally:
        _limpiar(engine)


if __name__ == "__main__":
    main()
