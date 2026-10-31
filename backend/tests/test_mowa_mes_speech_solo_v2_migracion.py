"""La migracion que deja todas las versiones de speech en v2, sin base (T-MM-C11, M-B3; RF-MM-17).

La migracion no importa nada de `app`: lleva su propia copia congelada de la conversion. Estas
pruebas la comparan contra la de la aplicacion (`speech.convertir_a_v2`), fijan el SQL del upgrade y
del downgrade, y simulan sobre un doble de la conexion lo que hace con las filas. Datos sinteticos;
las partes generadas usan una semilla fija.
"""

import importlib.util
import io
import random
from pathlib import Path
from types import ModuleType

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.adapters.persistence.modelos import MowaMesSpeechVersion
from app.core.entities.mowa_mes import ExpresionSegmento, PartesSegmento, Segmento
from app.core.services.plataformas.mowa_mes.campana import huella_expresiones
from app.core.services.plataformas.mowa_mes.speech import convertir_a_v2
from app.core.services.texto_enriquecido.serializacion import expresion_a_dict, expresion_desde_dict

BACKEND = Path(__file__).resolve().parents[1]
VERSIONES = BACKEND / "migrations" / "versions"
REVISION_ANTERIOR = "c5d9f2a8e714"  # las versiones deshabilitadas (M-B2)
REVISION = "d7a3e5b9c241"
SEGMENTOS = [s.value for s in Segmento]


def _cargar(archivo: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(archivo.removesuffix(".py"), VERSIONES / archivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


MIGRACION = _cargar("d7a3e5b9c241_speech_solo_v2.py")
SIEMBRA = _cargar("a4c8e2f6b913_configuracion_mowa_mes.py")  # donde nace el original, como v1


def _de_la_app(partes: list[dict]) -> list[dict]:
    """Lo que hoy da la aplicacion: `convertir_a_v2` y la forma que `_expresiones_a_json` guarda."""
    objetos = [PartesSegmento(Segmento(p["segmento"]), p["parte_1"], p["parte_2"]) for p in partes]
    return [
        {"segmento": e.segmento.value, "expresion": expresion_a_dict(e.expresion)}
        for e in convertir_a_v2(objetos)
    ]


# --- El convertidor congelado contra el de la aplicacion -----------------------------------------


def test_el_literal_del_original_es_la_conversion_del_original() -> None:
    assert MIGRACION.EXPRESIONES_ORIGINAL == MIGRACION._convertir(SIEMBRA.SPEECH_ORIGINAL)


def test_la_huella_del_original_convertido_es_la_de_las_campanas_nuevas() -> None:
    # Congelada: el mensaje es el mismo que el de la v1 (297c...), la huella no.
    expresiones = tuple(
        ExpresionSegmento(Segmento(e["segmento"]), expresion_desde_dict(e["expresion"]))
        for e in MIGRACION.EXPRESIONES_ORIGINAL
    )

    assert huella_expresiones(expresiones) == (
        "5b1c556c283ceccd59007114c0da16df3f323ef98b4122d5dc1628b0ef1992b1"
    )


def test_el_convertidor_de_la_migracion_da_lo_mismo_que_la_aplicacion_para_el_original() -> None:
    assert MIGRACION._convertir(SIEMBRA.SPEECH_ORIGINAL) == _de_la_app(
        list(SIEMBRA.SPEECH_ORIGINAL)
    )
    assert MIGRACION.EXPRESIONES_ORIGINAL == _de_la_app(list(SIEMBRA.SPEECH_ORIGINAL))


_TROZOS = [
    "",
    " ",
    "  ",
    "Hola",
    " cuota ",
    "[whatsapp]",
    "[whatsapp][whatsapp]",
    " INFO por [whatsapp]",
    "[",
    "]",
    "[@campo]",
    "[titular]",
    "ñandú — ",
    "€10",
    "…",
    "a\tb",
    "1. Preventiva",
    "x" * 90,
]


def _juego_sintetico(azar: random.Random) -> list[dict]:
    def parte() -> str:
        return "".join(azar.choice(_TROZOS) for _ in range(azar.randint(0, 6)))

    return [{"segmento": s, "parte_1": parte(), "parte_2": parte()} for s in SEGMENTOS]


def test_el_convertidor_da_lo_mismo_que_la_aplicacion_en_200_juegos_sinteticos() -> None:
    azar = random.Random(20261031)

    for _ in range(200):
        juego = _juego_sintetico(azar)

        assert MIGRACION._convertir(juego) == _de_la_app(juego), juego


def test_lo_que_convierte_la_migracion_lo_lee_la_aplicacion_y_es_una_expresion_valida() -> None:
    azar = random.Random(7)

    for _ in range(50):
        for segmento in MIGRACION._convertir(_juego_sintetico(azar)):
            expresion = expresion_desde_dict(segmento["expresion"])  # no lanza
            assert expresion_a_dict(expresion) == segmento["expresion"]


def test_el_titular_y_la_fecha_son_obligatorios_y_el_enlace_no() -> None:
    (segmento, *_) = MIGRACION._convertir(
        [{"segmento": "31_a_60", "parte_1": " a [whatsapp] b", "parte_2": "c"}]
    )

    nodos = {n["nombre"]: n for n in segmento["expresion"]["nodos"] if n["tipo"] == "variable"}
    assert nodos["titular"]["obligatoria"] is True
    assert nodos["fecha_vencimiento_cuota"]["obligatoria"] is True
    assert nodos["whatsapp_contacto"]["obligatoria"] is False
    assert nodos["titular"]["funciones"] == [{"nombre": "primeros", "args": [8]}]
    assert nodos["whatsapp_contacto"]["funciones"] == [{"nombre": "enlace_whatsapp", "args": []}]


def test_cada_whatsapp_del_texto_pasa_a_ser_el_enlace_y_el_resto_queda_tal_cual() -> None:
    (segmento,) = MIGRACION._convertir(
        [{"segmento": "61_a_90", "parte_1": " a [whatsapp][whatsapp] b", "parte_2": ""}]
    )

    resumen = [
        n["valor"] if n["tipo"] == "texto" else n["nombre"] for n in segmento["expresion"]["nodos"]
    ]
    assert resumen == [
        "titular",
        " a ",
        "whatsapp_contacto",
        "whatsapp_contacto",
        " b",
        "fecha_vencimiento_cuota",
    ]  # una parte 2 vacia no deja un nodo de texto vacio


# --- El SQL, sin base -----------------------------------------------------------------------------


def _configuracion() -> Config:
    configuracion = Config(str(BACKEND / "alembic.ini"))
    configuracion.set_main_option("script_location", str(BACKEND / "migrations"))
    return configuracion


def _sql(subir: bool) -> str:
    configuracion = _configuracion()
    configuracion.output_buffer = io.StringIO()
    if subir:
        command.upgrade(configuracion, f"{REVISION_ANTERIOR}:{REVISION}", sql=True)
    else:
        command.downgrade(configuracion, f"{REVISION}:{REVISION_ANTERIOR}", sql=True)
    return configuracion.output_buffer.getvalue()


def test_la_migracion_cuelga_de_la_de_las_versiones_deshabilitadas_y_es_la_cabeza() -> None:
    directorio = ScriptDirectory.from_config(_configuracion())

    assert directorio.get_revision(REVISION).down_revision == REVISION_ANTERIOR
    assert len(directorio.get_heads()) == 1
    assert REVISION in {revision.revision for revision in directorio.walk_revisions()}


def test_el_upgrade_cambia_el_check_y_el_formato_por_defecto() -> None:
    sql = _sql(subir=True)

    asegurar = "ALTER TABLE mowa_mes_speech_version DROP CONSTRAINT"
    assert f"{asegurar} ck_mowa_mes_speech_version_contenido_segun_formato;" in sql
    assert (
        "ALTER TABLE mowa_mes_speech_version ADD CONSTRAINT "
        "ck_mowa_mes_speech_version_contenido_segun_formato "
        "CHECK (formato = 'v2' AND expresiones IS NOT NULL);"
    ) in sql
    assert "ALTER TABLE mowa_mes_speech_version ALTER COLUMN formato SET DEFAULT 'v2';" in sql


def test_el_downgrade_quita_el_check_nuevo_pone_el_viejo_y_despues_el_formato_por_defecto() -> None:
    sql = _sql(subir=False)

    quitar = sql.index("DROP CONSTRAINT ck_mowa_mes_speech_version_contenido_segun_formato")
    poner = sql.index("ADD CONSTRAINT ck_mowa_mes_speech_version_contenido_segun_formato")
    por_defecto = sql.index("ALTER COLUMN formato SET DEFAULT 'v1'")
    assert quitar < poner < por_defecto  # las filas se devuelven entre quitar y poner (con base)
    assert (
        "CHECK ((formato = 'v1' AND expresiones IS NULL) "
        "OR (formato = 'v2' AND expresiones IS NOT NULL))"
    ) in sql


def test_en_modo_offline_solo_emite_ddl_no_toca_filas_ni_borra() -> None:
    for subir in (True, False):
        sql = _sql(subir)

        assert "UPDATE mowa_mes_speech_version" not in sql
        assert "DELETE" not in sql and "DROP TABLE" not in sql and "DROP COLUMN" not in sql


def test_el_modelo_declara_lo_mismo_que_la_migracion() -> None:
    tabla = MowaMesSpeechVersion.__table__
    cheques = {c.name: str(c.sqltext) for c in tabla.constraints if hasattr(c, "sqltext")}

    assert cheques[MIGRACION.CHECK] == MIGRACION.CHECK_NUEVO
    assert tabla.c["formato"].server_default.arg == "v2"


# --- Lo que hace con las filas, sobre un doble de la conexion ------------------------------


class _Fila:
    def __init__(self, id, original, partes) -> None:
        self.id, self.original, self.partes = id, original, partes


class _Resultado:
    def __init__(self, filas) -> None:
        self._filas = filas

    def all(self):
        return self._filas


class _Conexion:
    """Anota cada sentencia y sus parametros; el SELECT devuelve las filas v1 que se le dieron."""

    def __init__(self, filas=()) -> None:
        self.filas = list(filas)
        self.sentencias: list[tuple[str, dict | None]] = []

    def execute(self, sentencia, parametros=None):
        self.sentencias.append((str(sentencia), parametros))
        return _Resultado(self.filas)


PARTES_V1 = [{"segmento": s, "parte_1": f" a {s} ", "parte_2": " [whatsapp]"} for s in SEGMENTOS]


def test_el_upgrade_convierte_cada_v1_y_no_escribe_partes_ni_nada_mas() -> None:
    conexion = _Conexion(
        [_Fila(5, False, PARTES_V1), _Fila(1, True, list(SIEMBRA.SPEECH_ORIGINAL))]
    )

    MIGRACION._pasar_filas_a_v2(conexion)

    seleccion, *actualizaciones = conexion.sentencias
    assert "WHERE formato = 'v1'" in seleccion[0]
    assert len(actualizaciones) == 2
    for sql, _ in actualizaciones:
        assert sql == (
            "UPDATE mowa_mes_speech_version SET formato = 'v2', expresiones = :expresiones "
            "WHERE id = :id"
        )  # solo esas dos columnas: id, nombre, usada_en, partes... no se tocan
    (_, por_normal), (_, por_original) = actualizaciones
    assert por_normal == {"id": 5, "expresiones": MIGRACION._convertir(PARTES_V1)}
    assert por_original == {"id": 1, "expresiones": MIGRACION.EXPRESIONES_ORIGINAL}


def test_el_upgrade_sin_v1_no_actualiza_nada() -> None:
    conexion = _Conexion([])

    MIGRACION._pasar_filas_a_v2(conexion)

    assert len(conexion.sentencias) == 1  # solo el SELECT


def test_el_downgrade_vuelve_a_v1_solo_lo_que_tiene_partes_y_pone_expresiones_en_null() -> None:
    conexion = _Conexion()

    MIGRACION._devolver_filas_a_v1(conexion)

    ((sql, _),) = conexion.sentencias
    assert "SET formato = 'v1', expresiones = NULL" in sql
    assert "WHERE formato = 'v2' AND partes <> CAST('[]' AS jsonb)" in sql
    assert "partes =" not in sql.replace("partes <>", "")  # nunca se escribe `partes`
