"""El `catalogo` y el `campo` de los problemas de speech que publica la API (B6).

`codigo` puede venir del motor de texto enriquecido (`textoEnriquecido.codigo.*`) o de MOWA MES
(`mowaMes.codigo.*`) y los dos catalogos comparten nombres con textos distintos
(`telefono_invalido`): el frontend necesita saber cual usar. `campo` es un `Literal` con todo lo que
el servicio puede senalar. Datos sinteticos.
"""

import ast
from dataclasses import replace
from pathlib import Path
from typing import get_args

from app.api.mowa_mes import ProblemaSpeechRespuesta, _problema
from app.core.entities.mowa_mes import (
    RANGOS_SEGMENTO,
    CampoProblemaSpeech,
    CodigoMowaMes,
    DatosSpeech,
    ExpresionSegmento,
    FormatoSpeech,
    PartesSegmento,
    ProblemaSpeech,
    Segmento,
)
from app.core.entities.texto_enriquecido import (
    CodigoTexto,
    Expresion,
    NodoTexto,
    NodoVariable,
    Problema,
)
from app.core.services.plataformas.mowa_mes import speech
from tests.test_mowa_mes_speech import ORIGINAL

APP = Path(__file__).resolve().parents[1] / "app"


# --- catalogo -------------------------------------------------------------------------------------


def test_un_problema_del_motor_va_con_el_catalogo_texto() -> None:
    motor = Problema(CodigoTexto.VARIABLE_DESCONOCIDA, "No existe", nodo=1)

    respuesta = _problema(ProblemaSpeech(Segmento.DE_1_A_8, "expresion", "No existe", motor))

    assert (respuesta.codigo, respuesta.catalogo) == ("variable_desconocida", "texto")
    assert respuesta.ubicacion is not None and respuesta.ubicacion.nodo == 1


def test_un_problema_de_mowa_mes_va_con_el_catalogo_mowa_mes() -> None:
    problema = ProblemaSpeech(
        None, "formato", "x", codigo_mowa_mes=CodigoMowaMes.MENSAJE_EXCEDE_160
    )

    respuesta = _problema(problema)

    assert (respuesta.codigo, respuesta.catalogo) == ("mensaje_excede_160", "mowa_mes")
    assert respuesta.ubicacion is None


def test_telefono_invalido_se_distingue_por_el_catalogo() -> None:
    """El mismo nombre en los dos catalogos: el discriminador es lo que dice cual traducir."""
    assert CodigoTexto.TELEFONO_INVALIDO.value == CodigoMowaMes.TELEFONO_INVALIDO.value
    del_motor = Problema(CodigoTexto.TELEFONO_INVALIDO, "Telefono fuera de RF-02", nodo=0)

    por_el_motor = _problema(ProblemaSpeech(Segmento.PREVENTIVA, "expresion", "x", del_motor))
    por_mowa_mes = _problema(
        ProblemaSpeech(None, "formato", "x", codigo_mowa_mes=CodigoMowaMes.TELEFONO_INVALIDO)
    )

    assert (por_el_motor.codigo, por_el_motor.catalogo) == ("telefono_invalido", "texto")
    assert (por_mowa_mes.codigo, por_mowa_mes.catalogo) == ("telefono_invalido", "mowa_mes")


def test_sin_codigo_tampoco_hay_catalogo() -> None:
    respuesta = _problema(ProblemaSpeech(None, "nombre", "El nombre debe tener..."))

    assert (respuesta.codigo, respuesta.catalogo) == (None, None)


def test_el_catalogo_solo_admite_texto_o_mowa_mes() -> None:
    anotacion = ProblemaSpeechRespuesta.model_fields["catalogo"].annotation

    valores = {v for argumento in get_args(anotacion) for v in get_args(argumento)}

    assert valores == {"texto", "mowa_mes"}


# --- campo ----------------------------------------------------------------------------------------


def _con_expresion(nodos) -> DatosSpeech:
    expresiones = tuple(
        ExpresionSegmento(rango.segmento, Expresion(tuple(nodos))) for rango in RANGOS_SEGMENTO
    )
    return DatosSpeech("v2", expresiones=expresiones, formato=FormatoSpeech.V2)


def _campos_que_el_servicio_emite() -> set[str]:
    v1 = DatosSpeech("v1", ORIGINAL)
    con_arroba = tuple(PartesSegmento(p.segmento, "hola [@x]", "chao [@y]") for p in ORIGINAL)
    v2 = _con_expresion([NodoTexto("ok")])
    escenarios = [
        replace(v1, nombre=""),  # nombre
        replace(v1, partes=ORIGINAL[1:]),  # segmentos
        replace(v1, partes=con_arroba),  # parte_1 y parte_2
        replace(v1, expresiones=v2.expresiones),  # formato (v1 con expresiones)
        replace(v2, partes=ORIGINAL),  # formato (v2 con partes)
        _con_expresion([]),  # expresion (sin contenido)
        _con_expresion([NodoVariable("inventada", ())]),  # expresion (el motor)
    ]
    return {p.campo for datos in escenarios for p in speech.problemas_de(datos)}


def test_el_literal_de_campo_cubre_todo_lo_que_el_servicio_emite() -> None:
    declarados = set(get_args(CampoProblemaSpeech))

    emitidos = _campos_que_el_servicio_emite()

    assert emitidos <= declarados
    assert emitidos == declarados  # y no declara campos que nadie emite


def test_todo_campo_escrito_a_mano_en_el_codigo_esta_en_el_literal() -> None:
    """Un `ProblemaSpeech(..., "campo", ...)` nuevo con un nombre fuera del Literal se ve aqui."""
    declarados = set(get_args(CampoProblemaSpeech))
    encontrados: set[str] = set()
    for ruta in APP.rglob("*.py"):
        for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
            if not (
                isinstance(nodo, ast.Call) and getattr(nodo.func, "id", "") == "ProblemaSpeech"
            ):
                continue
            candidatos = nodo.args[1:2] + [k.value for k in nodo.keywords if k.arg == "campo"]
            encontrados |= {
                c.value
                for c in candidatos
                if isinstance(c, ast.Constant) and isinstance(c.value, str)
            }

    assert encontrados and encontrados <= declarados


def test_la_respuesta_publica_el_campo_con_el_mismo_literal() -> None:
    anotacion = ProblemaSpeechRespuesta.model_fields["campo"].annotation

    assert set(get_args(anotacion)) == set(get_args(CampoProblemaSpeech))
