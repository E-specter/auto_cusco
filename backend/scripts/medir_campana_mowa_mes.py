r"""Mide una campana de MOWA MES con una sabana sintetica de volumen real.

Uso, desde backend/ y con la base migrada:

    uv run python scripts/generar_sabana_sintetica.py sabana_46k.xlsx --filas 46000
    uv run python scripts/medir_campana_mowa_mes.py sabana_46k.xlsx

Ingesta la sabana en una fecha de 2099, arma la campana completa (todos los
productos), la crea (division, archivos .xlsx y guardado en PostgreSQL), descarga
sus archivos, importa un reporte de enviados construido desde lo cargado y
concilia. Solo imprime agregados. Al terminar borra todo y restituye supervisores,
configuracion y la marca de uso del Speech original. Numeros 900000xxx.
"""

import sys
import time
import tracemalloc
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select, update  # noqa: E402

from app.adapters.input.lector_calamine import LectorCalamine  # noqa: E402
from app.adapters.output.plataformas.mowa_mes.archivo_carga import (  # noqa: E402
    escribir_archivo_carga,
)
from app.adapters.persistence.db import get_engine  # noqa: E402
from app.adapters.persistence.modelos import (  # noqa: E402
    Carga,
    CargaAuditoria,
    MowaMesCampana,
    MowaMesSpeechVersion,
)
from app.adapters.persistence.repositorio_campanas_mowa_mes_postgres import (  # noqa: E402
    RepositorioCampanasMowaMesPostgres,
)
from app.adapters.persistence.repositorio_cargas_postgres import (  # noqa: E402
    RepositorioCargasPostgres,
)
from app.adapters.persistence.repositorio_cartera_postgres import (  # noqa: E402
    RepositorioCarteraPostgres,
)
from app.adapters.persistence.repositorio_mowa_mes_postgres import (  # noqa: E402
    RepositorioMowaMesPostgres,
)
from app.adapters.persistence.repositorio_supervision_postgres import (  # noqa: E402
    RepositorioSupervisionPostgres,
)
from app.core.entities.gestiones_digitales import ConfiguracionSupervision, Supervisor  # noqa: E402
from app.core.entities.mowa_mes import Programacion  # noqa: E402
from app.core.entities.mowa_mes_campana import PeticionCampana  # noqa: E402
from app.core.entities.mowa_mes_reporte import FilaReporte  # noqa: E402
from app.core.services.ingesta_sabana.servicio import IngestaSabanaService  # noqa: E402
from app.core.services.plataformas.mowa_mes.campana import CampanasMowaMesService  # noqa: E402
from app.core.services.plataformas.mowa_mes.conciliacion import conciliar  # noqa: E402
from app.core.services.seleccion_cartera.servicio import (  # noqa: E402
    CANTIDAD_MAXIMA,
    ConsultaCarteraService,
)

FECHA = date(2099, 5, 2)
CARGA, AUDITORIA = Carga.__table__, CargaAuditoria.__table__
CAMPANA, SPEECH = MowaMesCampana.__table__, MowaMesSpeechVersion.__table__
SUPERVISORES = ConfiguracionSupervision(
    ("Caja Cusco", "nuestra empresa"),
    tuple(
        Supervisor(f"90000000{i}", "Caja Cusco" if i <= 3 else "nuestra empresa")
        for i in range(1, 6)
    ),
)


def _limpiar(engine) -> None:
    with engine.begin() as cx:
        cx.execute(delete(CAMPANA).where(CAMPANA.c.fecha_corte == FECHA))
        cx.execute(delete(CARGA).where(CARGA.c.fecha_corte == FECHA))
        cx.execute(delete(AUDITORIA).where(AUDITORIA.c.fecha_corte == FECHA))


def _medir(nombre: str, accion):
    inicio = time.perf_counter()
    resultado = accion()
    print(f"{nombre:<32} {time.perf_counter() - inicio:7.2f}s")
    return resultado


def main() -> None:
    sabana = Path(sys.argv[1])
    engine = get_engine()
    supervision = RepositorioSupervisionPostgres(engine)
    mowa_mes = RepositorioMowaMesPostgres(engine)
    campanas = RepositorioCampanasMowaMesPostgres(engine)
    supervisores_antes = supervision.obtener()
    configuracion_antes = mowa_mes.obtener_configuracion()
    with engine.connect() as cx:
        original = cx.execute(select(SPEECH.c.id, SPEECH.c.usada_en).where(SPEECH.c.original)).one()
    _limpiar(engine)
    try:
        ingesta = IngestaSabanaService(RepositorioCargasPostgres(engine), LectorCalamine())
        carga = ingesta.registrar_carga(FECHA, sabana.name, sabana.read_bytes()).carga
        _medir("ingesta", lambda: ingesta.procesar_carga(carga.id))
        supervision.reemplazar(SUPERVISORES)
        mowa_mes.guardar_configuracion(
            ConfiguracionMowaMes_con(configuracion_antes, whatsapp_contacto="900000123")
        )
        servicio = CampanasMowaMesService(
            ConsultaCarteraService(RepositorioCarteraPostgres(engine)),
            mowa_mes,
            supervision,
            campanas,
            escribir_archivo_carga,
        )
        peticion = PeticionCampana(
            fecha_corte=FECHA,
            cantidad=CANTIDAD_MAXIMA,
            programacion=Programacion.HORA_DETERMINADA,
            envios=(datetime(2099, 5, 4, 9, 0),),
        )

        tracemalloc.start()
        armada = _medir("previsualizacion (armar)", lambda: servicio.previsualizar(peticion))
        _, pico = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        print(
            f"disponibles={armada.disponibles} evaluados={armada.evaluados} "
            f"productos={armada.productos_cargados} supervision={armada.supervision_cargados} "
            f"excluidos={len(armada.exclusiones)} "
            f"errores={[e.codigo.value for e in armada.errores]}"
        )
        print("exclusiones:", {c.value: n for c, n in armada.exclusiones_por_codigo().items()})
        print("advertencias:", {c.value: n for c, n in armada.advertencias_por_codigo().items()})
        print(f"memoria pico de Python al armar: {pico / 1e6:.0f}MB")

        todo = _medir(
            "xlsx de toda la carga (1 archivo)", lambda: escribir_archivo_carga(armada.filas)
        )
        por_fila = len(todo) / len(armada.filas)
        print(
            f"bytes de toda la carga en un solo xlsx: {len(todo) / 1e6:.2f}MB "
            f"({por_fila:.1f} bytes por fila); filas que entran en 2 000 000 bytes: "
            f"{int(2_000_000 / por_fila)}"
        )

        creada = _medir(
            "crear (dividir, escribir, guardar)",
            lambda: servicio.crear(replace_huella(peticion, armada.speech_huella)),
        )
        print("archivos:", [(a.numero, a.filas, a.supervision, a.bytes) for a in creada.archivos])

        _medir(
            "descargar todos los archivos",
            lambda: [campanas.archivo(creada.id, a.numero) for a in creada.archivos],
        )
        cargadas = _medir("leer filas cargadas", lambda: campanas.filas_cargadas(creada.id))
        reporte = [
            FilaReporte(
                i, 990_100_000, f.numero, f.mensaje, "04/05/99", f.dni, "enviado", "Nro. LARGO", "u"
            )
            for i, f in enumerate(cargadas, start=2)
        ]
        _medir(
            "guardar reporte de enviados",
            lambda: campanas.guardar_reportes(creada.id, "reporte.xlsx", {990_100_000: reporte}),
        )
        conciliacion = _medir(
            "conciliar (leer y emparejar)",
            lambda: conciliar(
                campanas.filas_cargadas(creada.id), campanas.filas_reporte(creada.id)
            ),
        )
        print(f"conciliados: {conciliacion.total.enviados} de {conciliacion.total.cargados}")
    finally:
        _limpiar(engine)
        with engine.begin() as cx:
            cx.execute(
                update(SPEECH).where(SPEECH.c.id == original.id).values(usada_en=original.usada_en)
            )
        supervision.reemplazar(supervisores_antes)
        mowa_mes.guardar_configuracion(configuracion_antes)


def ConfiguracionMowaMes_con(configuracion, **cambios):  # noqa: N802
    from dataclasses import replace

    return replace(configuracion, **cambios)


def replace_huella(peticion: PeticionCampana, huella: str) -> PeticionCampana:
    from dataclasses import replace

    return replace(peticion, speech_huella=huella)


if __name__ == "__main__":
    main()
