"""La migracion que deja todas las versiones de speech en v2, sin base (T-MM-C11, M-B3; RF-MM-17).

La migracion no importa nada de `app`: lleva su propia copia congelada de la conversion. Hasta
M-B3 estas pruebas la comparaban contra la de la aplicacion (`speech.convertir_a_v2`); en M-B4 esa
funcion se borro con la v1 y la comparacion pasa a ser contra un ORACULO CONGELADO (ver abajo). Las
pruebas tambien fijan el SQL del upgrade y del downgrade, y simulan sobre un doble de la conexion lo
que hace con las filas. Datos sinteticos; las partes generadas usan una semilla fija.
"""

import hashlib
import importlib.util
import io
import json
import random
from pathlib import Path
from types import ModuleType

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.entities.mowa_mes import ExpresionSegmento, Segmento
from app.core.services.plataformas.mowa_mes.campana import huella_expresiones
from app.core.services.texto_enriquecido.serializacion import expresion_a_dict, expresion_desde_dict
from tests.test_mowa_mes_speech_v2_postgres import CUERPO_V2 as CUERPO_V2_DE_LAS_PRUEBAS_DE_BASE

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


def normalizado(cuerpo: list[dict]) -> list[dict]:
    """El cuerpo de un PUT tal como lo deja guardado la app: cada expresion pasa por
    `expresion_desde_dict` y `expresion_a_dict`, que agregan `obligatoria` (falso si no viene) y
    fijan el orden de las claves. Es lo que hay que comparar contra una fila leida de la base."""
    return [
        {
            "segmento": e["segmento"],
            "expresion": expresion_a_dict(expresion_desde_dict(e["expresion"])),
        }
        for e in cuerpo
    ]


# --- El convertidor congelado y su oraculo -------------------------------------------------------


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


# El ORACULO del convertidor (T-MM-C11, M-B4). Hasta M-B3 el convertidor congelado de la migracion
# se comparaba, en 200 juegos sinteticos y en vivo, con `speech.convertir_a_v2` de la aplicacion. Al
# borrarse esa funcion, la salida de entonces quedo congelada UNA vez, con el codigo v1 vivo en el
# commit 9818e8d, y es lo que se compara ahora:
#
# - `HUELLA_DEL_ORACULO`: SHA-256 de la salida de `convertir_a_v2` (cada segmento como lo guarda
#   la app: `{"segmento", "expresion": expresion_a_dict(..)}`) para los 200 juegos de
#   `_juego_sintetico` con la semilla 20261031, serializada con
#   `json.dumps([salida de cada juego, ...], ensure_ascii=False, sort_keys=True,
#   separators=(",", ":"))`, en UTF-8.
# - `CASOS_DE_BORDE`: la salida completa de 8 casos (un solo segmento, `31_a_60`) para leerla a ojo.
#
# Para regenerarlos: en un `git worktree add` de 9818e8d, desde `backend/`, correr la misma
# generacion (`_juego_sintetico` y `random.Random(20261031)`) aplicando `speech.convertir_a_v2` a
# `PartesSegmento(Segmento(..), parte_1, parte_2)`; nunca con el codigo actual.
SEMILLA_DEL_ORACULO = 20261031
HUELLA_DEL_ORACULO = "0330d59aab105fcc5fac3ce621cb4478a1845126baf73f42e2a3570ed373f18e"

CASOS_DE_BORDE = [
    (
        "vacio",
        "",
        "",
        [
            {
                "segmento": "31_a_60",
                "expresion": {
                    "nodos": [
                        {
                            "tipo": "variable",
                            "nombre": "titular",
                            "funciones": [{"nombre": "primeros", "args": [8]}],
                            "obligatoria": True,
                        },
                        {
                            "tipo": "variable",
                            "nombre": "fecha_vencimiento_cuota",
                            "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
                            "obligatoria": True,
                        },
                    ]
                },
            }
        ],
    ),
    (
        "solo espacios",
        "  ",
        " ",
        [
            {
                "segmento": "31_a_60",
                "expresion": {
                    "nodos": [
                        {
                            "tipo": "variable",
                            "nombre": "titular",
                            "funciones": [{"nombre": "primeros", "args": [8]}],
                            "obligatoria": True,
                        },
                        {"tipo": "texto", "valor": "  "},
                        {
                            "tipo": "variable",
                            "nombre": "fecha_vencimiento_cuota",
                            "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
                            "obligatoria": True,
                        },
                        {"tipo": "texto", "valor": " "},
                    ]
                },
            }
        ],
    ),
    (
        "un whatsapp",
        " INFO por [whatsapp]",
        "",
        [
            {
                "segmento": "31_a_60",
                "expresion": {
                    "nodos": [
                        {
                            "tipo": "variable",
                            "nombre": "titular",
                            "funciones": [{"nombre": "primeros", "args": [8]}],
                            "obligatoria": True,
                        },
                        {"tipo": "texto", "valor": " INFO por "},
                        {
                            "tipo": "variable",
                            "nombre": "whatsapp_contacto",
                            "funciones": [{"nombre": "enlace_whatsapp", "args": []}],
                            "obligatoria": False,
                        },
                        {
                            "tipo": "variable",
                            "nombre": "fecha_vencimiento_cuota",
                            "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
                            "obligatoria": True,
                        },
                    ]
                },
            }
        ],
    ),
    (
        "whatsapp doble",
        "[whatsapp][whatsapp]",
        " fin",
        [
            {
                "segmento": "31_a_60",
                "expresion": {
                    "nodos": [
                        {
                            "tipo": "variable",
                            "nombre": "titular",
                            "funciones": [{"nombre": "primeros", "args": [8]}],
                            "obligatoria": True,
                        },
                        {
                            "tipo": "variable",
                            "nombre": "whatsapp_contacto",
                            "funciones": [{"nombre": "enlace_whatsapp", "args": []}],
                            "obligatoria": False,
                        },
                        {
                            "tipo": "variable",
                            "nombre": "whatsapp_contacto",
                            "funciones": [{"nombre": "enlace_whatsapp", "args": []}],
                            "obligatoria": False,
                        },
                        {
                            "tipo": "variable",
                            "nombre": "fecha_vencimiento_cuota",
                            "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
                            "obligatoria": True,
                        },
                        {"tipo": "texto", "valor": " fin"},
                    ]
                },
            }
        ],
    ),
    (
        "corchetes sueltos",
        "[ y ] y [@campo]",
        "[titular]",
        [
            {
                "segmento": "31_a_60",
                "expresion": {
                    "nodos": [
                        {
                            "tipo": "variable",
                            "nombre": "titular",
                            "funciones": [{"nombre": "primeros", "args": [8]}],
                            "obligatoria": True,
                        },
                        {"tipo": "texto", "valor": "[ y ] y [@campo]"},
                        {
                            "tipo": "variable",
                            "nombre": "fecha_vencimiento_cuota",
                            "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
                            "obligatoria": True,
                        },
                        {"tipo": "texto", "valor": "[titular]"},
                    ]
                },
            }
        ],
    ),
    (
        "tilde y euro",
        "ñandú — €10",
        "…",
        [
            {
                "segmento": "31_a_60",
                "expresion": {
                    "nodos": [
                        {
                            "tipo": "variable",
                            "nombre": "titular",
                            "funciones": [{"nombre": "primeros", "args": [8]}],
                            "obligatoria": True,
                        },
                        {"tipo": "texto", "valor": "ñandú — €10"},
                        {
                            "tipo": "variable",
                            "nombre": "fecha_vencimiento_cuota",
                            "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
                            "obligatoria": True,
                        },
                        {"tipo": "texto", "valor": "…"},
                    ]
                },
            }
        ],
    ),
    (
        "tabulacion y espacio duro",
        "a\tb",
        "1.\xa0Preventiva",
        [
            {
                "segmento": "31_a_60",
                "expresion": {
                    "nodos": [
                        {
                            "tipo": "variable",
                            "nombre": "titular",
                            "funciones": [{"nombre": "primeros", "args": [8]}],
                            "obligatoria": True,
                        },
                        {"tipo": "texto", "valor": "a\tb"},
                        {
                            "tipo": "variable",
                            "nombre": "fecha_vencimiento_cuota",
                            "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
                            "obligatoria": True,
                        },
                        {"tipo": "texto", "valor": "1.\xa0Preventiva"},
                    ]
                },
            }
        ],
    ),
    (
        "texto largo",
        "x" * 90,
        "y",
        [
            {
                "segmento": "31_a_60",
                "expresion": {
                    "nodos": [
                        {
                            "tipo": "variable",
                            "nombre": "titular",
                            "funciones": [{"nombre": "primeros", "args": [8]}],
                            "obligatoria": True,
                        },
                        {
                            "tipo": "texto",
                            "valor": "x" * 90,
                        },
                        {
                            "tipo": "variable",
                            "nombre": "fecha_vencimiento_cuota",
                            "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
                            "obligatoria": True,
                        },
                        {"tipo": "texto", "valor": "y"},
                    ]
                },
            }
        ],
    ),
]


def test_el_convertidor_da_la_salida_congelada_en_200_juegos_sinteticos() -> None:
    azar = random.Random(SEMILLA_DEL_ORACULO)
    salidas = [MIGRACION._convertir(_juego_sintetico(azar)) for _ in range(200)]

    canonico = json.dumps(salidas, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(canonico.encode("utf-8")).hexdigest() == HUELLA_DEL_ORACULO


def test_el_convertidor_da_la_salida_congelada_en_los_casos_de_borde() -> None:
    assert len(CASOS_DE_BORDE) == 8
    for nombre, parte_1, parte_2, esperado in CASOS_DE_BORDE:
        partes = [{"segmento": "31_a_60", "parte_1": parte_1, "parte_2": parte_2}]

        assert MIGRACION._convertir(partes) == esperado, nombre


def test_lo_que_convierte_la_migracion_lo_lee_la_aplicacion_y_es_una_expresion_valida() -> None:
    azar = random.Random(7)

    for _ in range(50):
        for segmento in MIGRACION._convertir(_juego_sintetico(azar)):
            expresion = expresion_desde_dict(segmento["expresion"])  # no lanza
            assert expresion_a_dict(expresion) == segmento["expresion"]


def test_el_cuerpo_crudo_de_un_put_no_es_lo_que_guarda_la_app_pero_normalizado_se_lee_igual() -> (
    None
):
    crudo = CUERPO_V2_DE_LAS_PRUEBAS_DE_BASE
    guardado = normalizado(crudo)

    assert guardado != crudo  # la app agrega `obligatoria` a cada variable
    variables = [n for s in guardado for n in s["expresion"]["nodos"] if n["tipo"] == "variable"]
    assert variables and all(n["obligatoria"] is False for n in variables)
    assert not any("obligatoria" in n for s in crudo for n in s["expresion"]["nodos"])
    assert normalizado(guardado) == guardado  # idempotente: guardar de nuevo no lo cambia
    assert [expresion_desde_dict(e["expresion"]) for e in guardado] == [
        expresion_desde_dict(e["expresion"]) for e in crudo
    ]  # el mismo contenido para el motor


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
