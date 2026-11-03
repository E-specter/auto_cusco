"""Las campanas de WhatsMKT contra PostgreSQL real (T-WM-B4b1, parte 2; RF-WM-23, 35, 36).

La corre `architec` con `-ConBase` (AUTO_CUSCO_DB_TESTS=1 y la base `_test` migrada, que
`conftest.py` exige). Cubre lo que los dobles no ven: que el lote se crea entero o nada, el JSONB
con su CHECK, el archivo byte a byte, las versiones que quedan marcadas como usadas, los
`ON DELETE` y la ida y vuelta de la migracion. Datos sinteticos (telefonos 900000xxx).
"""

import os
from datetime import date, time
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.modelos import (
    DefinicionCargaGuardada,
    TextoGuardado,
    WhatsmktAdjunto,
    WhatsmktCampana,
)
from app.adapters.persistence.repositorio_campanas_whatsmkt_postgres import (
    RepositorioCampanasWhatsmktPostgres,
)
from app.adapters.persistence.repositorio_definiciones_postgres import (
    RepositorioDefinicionesPostgres,
)
from app.adapters.persistence.repositorio_whatsmkt_postgres import RepositorioWhatsmktPostgres
from app.core.entities.nombres import normalizar_nombre
from app.core.entities.whatsmkt import (
    CodigoWhatsmkt,
    ExclusionContacto,
    ModoCampana,
    TipoAdjunto,
    TipoEnvio,
)
from app.core.entities.whatsmkt_campana import (
    CampanaNueva,
    FilaNueva,
    HorarioElegido,
    LoteNuevo,
)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

BACKEND = Path(__file__).resolve().parents[1]
PREFIJO = "zz prueba campanas "
REVISION_ANTERIOR = "d3f7a1b9c524"
TABLAS = (
    "whatsmkt_lote",
    "whatsmkt_campana",
    "whatsmkt_archivo",
    "whatsmkt_fila_cargada",
    "whatsmkt_exclusion",
)
XLSX = b"PK\x03\x04\x00\x00" + bytes(range(256)) * 40  # con ceros y todos los bytes
CONTENIDO_DEFINICION = {
    "proteger_formulas": True,
    "columnas": [
        {
            "nombre": "número",
            "orden": 0,
            "tipo": "texto",
            "expresion": {"nodos": [{"tipo": "texto", "valor": "x"}]},
        }
    ],
}


def _alembic() -> Config:
    configuracion = Config(str(BACKEND / "alembic.ini"))
    configuracion.set_main_option("script_location", str(BACKEND / "migrations"))
    return configuracion


class Entorno:
    def __init__(self) -> None:
        self.engine = get_engine()
        self.repo = RepositorioCampanasWhatsmktPostgres(self.engine)
        self.lotes: list[int] = []
        with self.engine.begin() as cx:
            self.texto_id = cx.execute(
                text(
                    "INSERT INTO texto_guardado (contexto, nombre, nombre_normalizado) "
                    "VALUES ('whatsmkt.mensaje', :n, :nn) RETURNING id"
                ),
                {"n": PREFIJO + "mensaje", "nn": normalizar_nombre(PREFIJO + "mensaje")},
            ).scalar_one()
            cx.execute(
                text(
                    "INSERT INTO texto_guardado_version (texto_id, numero, contenido) "
                    "VALUES (:t, 1, CAST(:c AS jsonb))"
                ),
                {"t": self.texto_id, "c": '{"texto": "Hola [$MACRO1$]"}'},
            )
        definicion = RepositorioDefinicionesPostgres(self.engine).crear(
            PREFIJO + "definicion", CONTENIDO_DEFINICION, "whatsmkt"
        )
        self.definicion_id = definicion.id
        self.adjunto = RepositorioWhatsmktPostgres(self.engine).guardar_adjunto(
            TipoAdjunto.PDF, PREFIJO + "adjunto.pdf", b"%PDF-1.4 zz prueba campanas"
        )

    def campana(self, **cambios) -> CampanaNueva:
        base = {
            "nombre": PREFIJO + "uno",
            "segmento": None,
            "segmento_etiqueta": None,
            "definicion_id": self.definicion_id,
            "definicion_nombre": PREFIJO + "definicion",
            "definicion_version": 1,
            "texto_guardado_id": self.texto_id,
            "texto_version": 1,
            "mensaje_texto": "Hola [$MACRO1$]",
            "whatsapp_contacto": "900000123",
            "fecha_corte": date(2026, 11, 2),
            "filtros": ("dias_atraso:mayor_igual:0",),
            "orden": "-dias_atraso",
            "cantidad_pedida": 1000,
            "fecha_envio": date(2026, 11, 3),
            "horarios": (HorarioElegido("horario_1", time(8), time(14)),),
            "lo_antes_posible": False,
            "tipo_envio": TipoEnvio.SOLO_TEXTO,
            "foto_id": None,
            "adjunto_id": None,
            "etiqueta_vcard": None,
            "cantidad": 3,
            "productos": 1,
            "supervisores": ("51900000901", "51900000902"),
            "archivo_nombre": PREFIJO + "uno.xlsx",
            "archivo_contenido": XLSX,
            "filas": (
                FilaNueva(1, "51900000901", None, True, ("Ana", None)),
                FilaNueva(2, "51900000902", None, True, ("Ana", None)),
                FilaNueva(3, "51900000001", f"{1:018d}", False, ("Ana", None)),
            ),
            "exclusiones": (
                ExclusionContacto(4, f"{4:018d}", CodigoWhatsmkt.SIN_TELEFONO, "Sin telefono"),
            ),
        }
        return CampanaNueva(**{**base, **cambios})

    def crear(self, *campanas: CampanaNueva, sin_campana=()):
        lote = self.repo.crear_lote(
            LoteNuevo(ModoCampana.GLOBAL, campanas or (self.campana(),), tuple(sin_campana))
        )
        self.lotes.append(lote.lote_id)
        return lote

    def contar(self, tabla: str, donde: str = "TRUE", **parametros) -> int:
        with self.engine.connect() as cx:
            return cx.execute(
                text(f"SELECT count(*) FROM {tabla} WHERE {donde}"), parametros
            ).scalar_one()

    def limpiar(self) -> None:
        with self.engine.begin() as cx:
            cx.execute(
                delete(WhatsmktCampana.__table__).where(WhatsmktCampana.nombre.like(PREFIJO + "%"))
            )
            cx.execute(text("DELETE FROM whatsmkt_lote WHERE id = ANY(:ids)"), {"ids": self.lotes})
            cx.execute(
                delete(WhatsmktAdjunto.__table__).where(WhatsmktAdjunto.nombre.like(PREFIJO + "%"))
            )
            cx.execute(
                delete(TextoGuardado.__table__).where(TextoGuardado.nombre.like(PREFIJO + "%"))
            )
            cx.execute(
                delete(DefinicionCargaGuardada.__table__).where(
                    DefinicionCargaGuardada.nombre_normalizado.startswith(
                        normalizar_nombre(PREFIJO)
                    )
                )
            )


@pytest.fixture
def entorno():
    e = Entorno()
    try:
        yield e
    finally:
        e.limpiar()


# --- El lote se guarda entero -----------------------------------------------------------------


def test_el_lote_guarda_la_campana_el_archivo_las_filas_y_las_exclusiones(entorno) -> None:
    sin_campana = [ExclusionContacto(9, f"{9:018d}", CodigoWhatsmkt.SIN_DIAS_ATRASO, "Sin dias")]

    lote = entorno.crear(sin_campana=sin_campana)

    [campana] = lote.campanas
    assert (campana.lote_id, campana.nombre, campana.cantidad, campana.productos) == (
        lote.lote_id,
        PREFIJO + "uno",
        3,
        1,
    )
    assert campana.horarios == (HorarioElegido("horario_1", time(8), time(14)),)
    assert campana.supervisores == ("51900000901", "51900000902")
    assert campana.filtros == ("dias_atraso:mayor_igual:0",)
    assert (campana.fecha_corte, campana.fecha_envio) == (date(2026, 11, 2), date(2026, 11, 3))
    assert (campana.archivo_nombre, campana.archivo_tamano) == (PREFIJO + "uno.xlsx", len(XLSX))
    assert entorno.contar("whatsmkt_fila_cargada", "campana_id = :c", c=campana.id) == 3
    assert entorno.contar("whatsmkt_exclusion", "campana_id = :c", c=campana.id) == 1
    # La exclusion que queda fuera de todas las campanas cuelga del lote, con campana nula.
    assert (
        entorno.contar("whatsmkt_exclusion", "lote_id = :l AND campana_id IS NULL", l=lote.lote_id)
        == 1
    )


def test_el_archivo_se_guarda_y_se_descarga_byte_a_byte(entorno) -> None:
    [campana] = entorno.crear().campanas

    archivo = entorno.repo.obtener_archivo(campana.id)

    assert archivo.contenido == XLSX
    assert archivo.nombre == PREFIJO + "uno.xlsx"
    assert entorno.repo.obtener_archivo(2_000_000_000) is None


def test_las_filas_conservan_su_orden_los_supervisores_sin_pagare_y_las_macros_nulas(
    entorno,
) -> None:
    [campana] = entorno.crear().campanas

    with entorno.engine.connect() as cx:
        filas = cx.execute(
            text(
                "SELECT posicion, numero, pagare, supervision, macros "
                "FROM whatsmkt_fila_cargada WHERE campana_id = :c ORDER BY posicion"
            ),
            {"c": campana.id},
        ).all()

    assert [(f.posicion, f.numero, f.pagare, f.supervision) for f in filas] == [
        (1, "51900000901", None, True),
        (2, "51900000902", None, True),
        (3, "51900000001", f"{1:018d}", False),
    ]
    assert filas[2].macros == ["Ana", None]  # el nulo de una macro vacia es un null dentro del JSON


def test_una_campana_por_segmento_en_el_mismo_lote(entorno) -> None:
    uno = entorno.campana(
        nombre=PREFIJO + "preventivo", segmento="preventivo", segmento_etiqueta="Preventivo"
    )
    dos = entorno.campana(nombre=PREFIJO + "tramo", segmento="tramo_2", segmento_etiqueta="Tramo 2")

    lote = entorno.crear(uno, dos)

    assert {c.lote_id for c in lote.campanas} == {lote.lote_id}
    assert [c.segmento for c in lote.campanas] == ["preventivo", "tramo_2"]


# --- Entero o nada ----------------------------------------------------------------------------


def test_si_una_campana_del_lote_falla_no_queda_ninguna_ni_nada_de_lo_suyo(entorno) -> None:
    antes = {t: entorno.contar(t) for t in TABLAS}
    buena = entorno.campana(nombre=PREFIJO + "buena")
    mala = entorno.campana(nombre="n" * 76)  # viola ck_..._nombre_valido

    with pytest.raises(IntegrityError):
        entorno.repo.crear_lote(
            LoteNuevo(
                ModoCampana.POR_SEGMENTO,
                (buena, mala),
                (ExclusionContacto(7, None, CodigoWhatsmkt.SIN_DIAS_ATRASO, "x"),),
            )
        )

    assert {t: entorno.contar(t) for t in TABLAS} == antes
    # Y la version del texto que se iba a usar no quedo marcada como usada.
    assert (
        entorno.contar(
            "texto_guardado_version", "texto_id = :t AND usada_en IS NOT NULL", t=entorno.texto_id
        )
        == 0
    )


def test_al_crear_quedan_usadas_la_version_del_texto_y_la_de_la_definicion(entorno) -> None:
    entorno.crear()

    assert (
        entorno.contar(
            "texto_guardado_version", "texto_id = :t AND usada_en IS NOT NULL", t=entorno.texto_id
        )
        == 1
    )
    assert (
        entorno.contar(
            "definicion_carga_version",
            "definicion_id = :d AND usada_en IS NOT NULL",
            d=entorno.definicion_id,
        )
        == 1
    )


# --- Las restricciones ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cambios",
    [
        {"nombre": "   "},
        {"tipo_envio": TipoEnvio.ARCHIVO},  # sin adjunto
        {"tipo_envio": TipoEnvio.VCARD},  # sin etiqueta
        {"etiqueta_vcard": "sobra"},  # etiqueta con tipo solo_texto
        {"horarios": ()},
        {"cantidad": 99},  # no es productos + supervisores
        {"fecha_envio": date(2026, 11, 1)},  # anterior al corte
        {"whatsapp_contacto": "812345678"},
        {"texto_version": 0},
    ],
)
def test_la_base_rechaza_una_campana_incoherente(entorno, cambios) -> None:
    with pytest.raises(IntegrityError):
        entorno.crear(entorno.campana(**cambios))


def test_el_tipo_archivo_con_adjunto_y_el_vcard_con_etiqueta_si_se_guardan(entorno) -> None:
    con_archivo = entorno.campana(
        nombre=PREFIJO + "archivo", tipo_envio=TipoEnvio.ARCHIVO, adjunto_id=entorno.adjunto.id
    )
    con_vcard = entorno.campana(
        nombre=PREFIJO + "vcard", tipo_envio=TipoEnvio.VCARD, etiqueta_vcard="Caja"
    )

    lote = entorno.crear(con_archivo, con_vcard)

    assert [(c.tipo_envio, c.adjunto_id, c.etiqueta_vcard) for c in lote.campanas] == [
        (TipoEnvio.ARCHIVO, entorno.adjunto.id, None),
        (TipoEnvio.VCARD, None, "Caja"),
    ]


def test_el_jsonb_de_las_macros_no_admite_un_null_json_ni_un_objeto(entorno) -> None:
    [campana] = entorno.crear().campanas
    insertar = text(
        "INSERT INTO whatsmkt_fila_cargada "
        "(campana_id, posicion, numero, pagare, supervision, macros) "
        "VALUES (:c, 50, '51900000050', 'p', false, CAST(:m AS jsonb))"
    )

    for malo in ("null", "{}", "3"):
        with pytest.raises(IntegrityError), entorno.engine.begin() as cx:
            cx.execute(insertar, {"c": campana.id, "m": malo})


def test_un_supervisor_lleva_pagare_nulo_y_un_producto_no(entorno) -> None:
    [campana] = entorno.crear().campanas
    insertar = text(
        "INSERT INTO whatsmkt_fila_cargada "
        "(campana_id, posicion, numero, pagare, supervision, macros) "
        "VALUES (:c, 60, '51900000060', :p, :s, '[]')"
    )

    for pagare, supervision in (("p", True), (None, False)):
        with pytest.raises(IntegrityError), entorno.engine.begin() as cx:
            cx.execute(insertar, {"c": campana.id, "p": pagare, "s": supervision})


# --- ON DELETE --------------------------------------------------------------------------------


def test_borrar_el_texto_o_la_definicion_deja_la_campana_con_su_copia(entorno) -> None:
    [campana] = entorno.crear().campanas

    with entorno.engine.begin() as cx:
        cx.execute(delete(TextoGuardado.__table__).where(TextoGuardado.id == entorno.texto_id))
        cx.execute(
            delete(DefinicionCargaGuardada.__table__).where(
                DefinicionCargaGuardada.id == entorno.definicion_id
            )
        )
        fila = cx.execute(
            select(WhatsmktCampana.__table__).where(WhatsmktCampana.id == campana.id)
        ).one()

    assert (fila.texto_guardado_id, fila.definicion_id) == (None, None)
    assert fila.mensaje_texto == "Hola [$MACRO1$]"  # la copia queda
    assert fila.definicion_nombre == PREFIJO + "definicion" and fila.definicion_version == 1


def test_borrar_la_campana_borra_su_archivo_sus_filas_y_sus_exclusiones_pero_no_las_de_fuera(
    entorno,
) -> None:
    sin_campana = [ExclusionContacto(9, None, CodigoWhatsmkt.SIN_DIAS_ATRASO, "Sin dias")]
    lote = entorno.crear(sin_campana=sin_campana)
    [campana] = lote.campanas

    with entorno.engine.begin() as cx:
        cx.execute(delete(WhatsmktCampana.__table__).where(WhatsmktCampana.id == campana.id))

    for tabla in ("whatsmkt_archivo", "whatsmkt_fila_cargada"):
        assert entorno.contar(tabla, "campana_id = :c", c=campana.id) == 0
    assert entorno.contar("whatsmkt_exclusion", "campana_id = :c", c=campana.id) == 0
    assert entorno.contar("whatsmkt_exclusion", "lote_id = :l", l=lote.lote_id) == 1


def test_no_se_puede_borrar_un_adjunto_que_una_campana_usa(entorno) -> None:
    entorno.crear(entorno.campana(tipo_envio=TipoEnvio.ARCHIVO, adjunto_id=entorno.adjunto.id))

    with pytest.raises(IntegrityError), entorno.engine.begin() as cx:
        cx.execute(
            delete(WhatsmktAdjunto.__table__).where(WhatsmktAdjunto.id == entorno.adjunto.id)
        )


# --- La ida y vuelta --------------------------------------------------------------------------


def test_la_migracion_va_y_vuelve(entorno) -> None:
    engine = entorno.engine
    entorno.limpiar()  # no hay filas que bajar con la migracion
    try:
        command.downgrade(_alembic(), REVISION_ANTERIOR)
        assert not set(TABLAS) & set(inspect(engine).get_table_names())

        command.upgrade(_alembic(), "head")
        assert set(TABLAS) <= set(inspect(engine).get_table_names())
    finally:
        command.upgrade(_alembic(), "head")
