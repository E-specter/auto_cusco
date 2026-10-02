"""Contrato: todo lo que el motor de texto enriquecido expone por clave tiene su traduccion.

Lee los diccionarios de verdad (`frontend/src/i18n/es.json` y `en.json`), no una copia. La API no
envia textos visibles, envia claves `textoEnriquecido.*`, y esta prueba comprueba las dos
direcciones: cada clave que el backend puede enviar existe en los dos idiomas con texto, y no
quedan claves de codigos, funciones, parametros, familias, marcas o contextos que ya no existen.

Las claves salen de la misma fuente que la API: el catalogo de funciones (`catalogo.py`, que sale
del registro), `CodigoTexto` y los contextos que registra `app/api/texto_enriquecido.py`. Una
funcion o un contexto nuevo sin su traduccion pone esta prueba en rojo.
"""

import json
from pathlib import Path

import pytest

from app.api.texto_enriquecido import obtener_registro_contextos
from app.core.entities.texto_enriquecido import CodigoTexto
from app.core.services.texto_enriquecido import catalogo

I18N = Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n"
PREFIJO = "textoEnriquecido."
IDIOMAS = ["es", "en"]


def _diccionario(idioma: str) -> dict[str, str]:
    ruta = I18N / f"{idioma}.json"
    assert ruta.exists(), f"No se encontro el diccionario del frontend {ruta}"
    return json.loads(ruta.read_text(encoding="utf-8"))


def _claves_esperadas() -> dict[str, str]:
    """Cada clave que la API puede enviar, con lo que es (para el mensaje de error)."""
    esperadas: dict[str, str] = {}
    for codigo in CodigoTexto:
        esperadas[f"{PREFIJO}codigo.{codigo.value}"] = f"el codigo {codigo.value!r}"
    for funcion in catalogo.catalogo_de_funciones():
        esperadas[funcion.clave_nombre] = f"el nombre de la funcion {funcion.nombre!r}"
        esperadas[funcion.clave_descripcion] = f"la descripcion de la funcion {funcion.nombre!r}"
        esperadas[funcion.clave_familia] = f"la familia {funcion.familia!r}"
        for parametro in funcion.parametros:
            esperadas[parametro.clave_nombre] = (
                f"el parametro {parametro.nombre!r} de la funcion {funcion.nombre!r}"
            )
    for marca in catalogo.marcas_de_fecha():
        esperadas[marca.clave] = f"la marca de fecha {marca.marca!r}"
    for familia in catalogo.familias():
        esperadas[f"{PREFIJO}familia.{familia}"] = f"la familia {familia!r}"
    for contexto in obtener_registro_contextos().disponibles():
        esperadas[contexto.clave_nombre] = f"el contexto {contexto.nombre!r}"
        for variable in contexto.variables:
            if variable.clave_nombre is not None:
                esperadas[variable.clave_nombre] = (
                    f"la variable {variable.nombre!r} del contexto {contexto.nombre!r}"
                )
    return esperadas


ESPERADAS = _claves_esperadas()


def test_se_leen_las_claves_del_motor() -> None:
    # Un catalogo que dejara de leerse haria pasar en verde todo lo de abajo.
    assert len(ESPERADAS) >= 100
    assert f"{PREFIJO}codigo.expresion_invalida" in ESPERADAS
    assert f"{PREFIJO}funcion.primeros.nombre" in ESPERADAS
    assert f"{PREFIJO}funcion.primeros.parametro.n" in ESPERADAS
    assert f"{PREFIJO}contexto.mowa_mes.speech" in ESPERADAS
    assert f"{PREFIJO}variable.whatsapp_contacto" in ESPERADAS


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_cada_clave_del_motor_esta_traducida(idioma: str) -> None:
    diccionario = _diccionario(idioma)

    faltan = {clave: que for clave, que in ESPERADAS.items() if clave not in diccionario}
    vacias = [
        clave for clave in ESPERADAS if clave in diccionario and not diccionario[clave].strip()
    ]

    assert not faltan, (
        f"Faltan en {idioma}.json las traducciones de: {faltan}. Las claves van junto con el "
        "codigo, la funcion o el contexto que las envia, en el mismo commit."
    )
    assert not vacias, f"Traducciones vacias en {idioma}.json: {vacias}"


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_no_quedan_claves_de_lo_que_el_motor_ya_no_expone(idioma: str) -> None:
    propias = {k for k in _diccionario(idioma) if k.startswith(PREFIJO)}

    sobrantes = sorted(propias - set(ESPERADAS))

    assert not sobrantes, (
        f"{idioma}.json trae claves que ninguna parte del motor envia: {sobrantes}. "
        "Si son de otra cosa, no van bajo `textoEnriquecido.`; si sobran, se quitan."
    )


def test_los_dos_idiomas_tienen_las_mismas_claves_del_motor() -> None:
    es = {k for k in _diccionario("es") if k.startswith(PREFIJO)}
    en = {k for k in _diccionario("en") if k.startswith(PREFIJO)}

    assert (sorted(es - en), sorted(en - es)) == ([], [])


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_las_traducciones_no_ensenan_la_sintaxis_de_corchetes(idioma: str) -> None:
    """La interfaz no muestra `[@...]`: el usuario arma con piezas (decision de diseno)."""
    diccionario = _diccionario(idioma)

    con_sintaxis = [
        clave
        for clave in ESPERADAS
        if clave.startswith(f"{PREFIJO}codigo.") and ("[@" in diccionario[clave])
    ]

    assert not con_sintaxis, con_sintaxis
