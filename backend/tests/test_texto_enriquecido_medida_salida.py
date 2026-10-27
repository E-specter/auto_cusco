"""La unidad del largo y la salida de un contexto en los endpoints de /texto-enriquecido (T-MM-B9).

El speech de MOWA MES mide en unidades GSM-7 y envia el mensaje normalizado a GSM-7 (RF-MM-27). El
editor del motor y la tabla de MOWA MES tienen que decir lo mismo: el mismo texto da el mismo largo,
el mismo aviso de los 150 y el mismo tope de los 160. El resto de los contextos (la cartera) sigue
midiendo en caracteres y mostrando el texto tal cual.

Los caracteres especiales van con su nombre Unicode: el archivo es ASCII. Datos sinteticos.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.cartera import obtener_servicio_cartera
from app.api.selecciones import obtener_servicio_selecciones
from app.api.texto_enriquecido import obtener_registro_contextos
from app.core.entities.mapeo import CampoSalida, DefinicionCarga, TipoSalida
from app.core.entities.mowa_mes import (
    LARGO_ADVERTENCIA,
    LARGO_MAXIMO,
    CodigoMowaMes,
    ExpresionSegmento,
    Segmento,
)
from app.core.entities.texto_enriquecido import Expresion, NodoTexto, TipoValor
from app.core.services.contextos_texto import contexto_cartera
from app.core.services.mapeo_campos.generador import GeneradorCargas
from app.core.services.plataformas.mowa_mes import speech
from app.core.services.plataformas.mowa_mes.contexto_texto import NOMBRE, contexto_speech
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.core.services.texto_enriquecido.gsm7 import a_gsm7, largo_gsm7
from app.core.services.texto_enriquecido.serializacion import expresion_desde_dict
from app.main import app
from tests.test_api_texto_enriquecido_seleccion import CarteraFalsa, SeleccionesFalsas

CORTE = "2026-09-10"
ELIPSIS = "\N{HORIZONTAL ELLIPSIS}"
EMOJI = "\N{THUMBS UP SIGN}"
O_TILDE = "\N{LATIN SMALL LETTER O WITH ACUTE}"
EURO = "\N{EURO SIGN}"

# Lo que se envia de FIJO: la elipsis son 3 signos, el emoji se borra (deja dos espacios), la tilde
# se quita y el euro pasa a `EUR` (RF-MM-27, 2026-10-26: ya no hay extendidos que midan 2).
FIJO = f"Aviso {ELIPSIS} {EMOJI} pag{O_TILDE} {EURO} "
FIJO_ENVIADO = "Aviso ...  pago EUR "
TITULAR_DE_EJEMPLO = "TITULAR/"  # primeros(8) de TITULAR/SINTETICO,UNO
ENVIADO = FIJO_ENVIADO + TITULAR_DE_EJEMPLO
LARGO_ENVIADO = 28  # 16 + 3 (EUR) + 1 + 8: todo se mide en caracteres, sin extendidos


@pytest.fixture
def cliente():
    cartera = CarteraFalsa()
    app.dependency_overrides[obtener_servicio_cartera] = lambda: cartera
    app.dependency_overrides[obtener_servicio_selecciones] = lambda: SeleccionesFalsas()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _texto(valor: str) -> dict:
    return {"tipo": "texto", "valor": valor}


def _variable(nombre: str, *funciones: dict) -> dict:
    return {"tipo": "variable", "nombre": nombre, "funciones": list(funciones)}


def _expresion(*nodos: dict) -> dict:
    return {"nodos": list(nodos)}


def _con_titular(fijo: str = FIJO) -> dict:
    return _expresion(
        _texto(fijo),
        _variable("titular", {"nombre": "primeros", "args": [len(TITULAR_DE_EJEMPLO)]}),
    )


def _validar(cliente, contexto: str, expresion: dict) -> dict:
    respuesta = cliente.post(
        "/texto-enriquecido/validacion", json={"contexto": contexto, "expresion": expresion}
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _previsualizar(cliente, contexto: str, expresion: dict, muestra: dict | None = None) -> dict:
    cuerpo = {"contexto": contexto, "expresion": expresion}
    if muestra is not None:
        cuerpo["muestra"] = muestra
    respuesta = cliente.post("/texto-enriquecido/previsualizacion", json=cuerpo)
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _celdas(cuerpo: dict) -> list[dict]:
    return [fila["columnas"][0] for fila in cuerpo["filas"]]


def _comprobar_celda(celda: dict) -> None:
    assert celda["texto"] == ENVIADO
    assert "".join(n["texto"] for n in celda["nodos"]) == ENVIADO  # los nodos suman el texto
    assert celda["largo"] == largo_gsm7(ENVIADO) == LARGO_ENVIADO
    assert celda["cota"] == LARGO_ENVIADO
    assert celda["problemas"] == []


# --- La cota (validacion) -----------------------------------------------------------------------


def test_la_cota_del_speech_se_mide_en_unidades_gsm7_sobre_el_texto_normalizado(cliente) -> None:
    validacion = _validar(cliente, NOMBRE, _con_titular())

    assert validacion["cota"] == LARGO_ENVIADO


def test_la_cota_del_editor_es_la_largo_maximo_de_la_tabla_de_mowa_mes(cliente) -> None:
    expresion = _con_titular()
    en_la_tabla = speech.previsualizar_v2(
        [ExpresionSegmento(Segmento.DE_1_A_8, expresion_desde_dict(expresion))], None
    )

    assert en_la_tabla[0].largo_maximo == _validar(cliente, NOMBRE, expresion)["cota"]


def test_la_cartera_sigue_midiendo_en_caracteres(cliente) -> None:
    validacion = _validar(cliente, "cartera", _con_titular())

    assert validacion["cota"] == len(FIJO) + len(TITULAR_DE_EJEMPLO)  # sin normalizar ni GSM-7


def test_los_problemas_siguen_ubicados_en_lo_escrito_y_no_se_corren(cliente) -> None:
    # Despues de un texto cuya normalizacion cambia el largo, el problema esta en el nodo 1.
    expresion = _expresion(_texto(FIJO), _variable("no_existe"))

    del_speech = _validar(cliente, NOMBRE, expresion)
    de_la_cartera = _validar(cliente, "cartera", expresion)

    assert del_speech["problemas"] == de_la_cartera["problemas"]
    assert del_speech["problemas"][0]["ubicacion"]["nodo"] == 1


# --- El texto y su largo (previsualizacion) -----------------------------------------------------


def test_el_ejemplo_sale_normalizado_con_su_largo_en_gsm7(cliente) -> None:
    cuerpo = _previsualizar(cliente, NOMBRE, _con_titular(), {"tipo": "ejemplo"})

    assert [_comprobar_celda(c) for c in _celdas(cuerpo)] == [None]


def test_los_ejemplos_por_segmento_salen_todos_normalizados(cliente) -> None:
    cuerpo = _previsualizar(cliente, NOMBRE, _con_titular())

    assert len(cuerpo["filas"]) == 6
    for celda in _celdas(cuerpo):
        _comprobar_celda(celda)


def test_un_producto_real_sale_normalizado(cliente) -> None:
    muestra = {"tipo": "producto_real", "fecha_corte": CORTE, "pagare": "x"}

    cuerpo = _previsualizar(cliente, NOMBRE, _con_titular(), muestra)

    # El titular del producto real es TITULAR/SINTETICO,1: primeros(8).
    celda = _celdas(cuerpo)[0]
    assert celda["texto"] == FIJO_ENVIADO + "TITULAR/"
    assert celda["largo"] == LARGO_ENVIADO
    assert "".join(n["texto"] for n in celda["nodos"]) == celda["texto"]


def test_los_primeros_de_una_seleccion_salen_normalizados(cliente) -> None:
    muestra = {"tipo": "primeros_de_seleccion", "fecha_corte": CORTE, "cantidad": 3}

    cuerpo = _previsualizar(cliente, NOMBRE, _con_titular(), muestra)

    assert len(cuerpo["filas"]) == 3
    for celda in _celdas(cuerpo):
        assert celda["texto"] == ENVIADO
        assert celda["largo"] == LARGO_ENVIADO


def _definicion(expresion: dict) -> dict:
    columna = {"nombre": "mensaje", "orden": 0, "expresion": expresion}
    return {"nombre": "SMS", "columnas": [columna], "segmentacion": {}}


def test_una_definicion_tambien_sale_normalizada_y_con_su_largo(cliente) -> None:
    respuesta = cliente.post(
        "/texto-enriquecido/previsualizacion",
        json={"contexto": NOMBRE, "definicion": _definicion(_con_titular())},
    )
    assert respuesta.status_code == 200, respuesta.text

    for celda in _celdas(respuesta.json()):
        _comprobar_celda(celda)


def test_el_largo_de_la_cartera_es_en_caracteres_y_el_texto_no_se_toca(cliente) -> None:
    cuerpo = _previsualizar(cliente, "cartera", _con_titular(), {"tipo": "ejemplo"})

    celda = _celdas(cuerpo)[0]
    assert celda["texto"].startswith(FIJO)  # el emoji, la elipsis y la tilde siguen ahi
    assert celda["largo"] == len(celda["texto"])
    assert celda["cota"] == len(FIJO) + len(TITULAR_DE_EJEMPLO)


# --- Los 150 y los 160 dicen lo mismo en el editor y en la tabla --------------------------------


def _nivel(largo: int, umbral: int, limite: int) -> str | None:
    if largo > limite:
        return CodigoMowaMes.MENSAJE_EXCEDE_160.value
    return CodigoMowaMes.MENSAJE_EXCEDE_150.value if largo > umbral else None


@pytest.mark.parametrize("repeticiones", [147, 148, 157, 158])
def test_el_editor_y_la_tabla_miden_igual_y_avisan_igual_en_los_150_y_los_160(
    cliente, repeticiones: int
) -> None:
    # La elipsis cuenta 3: 147 -> 150 (sin aviso), 148 -> 151 (aviso), 157 -> 160, 158 -> 161.
    expresion = _expresion(_texto("y" * repeticiones + ELIPSIS))
    esperado = repeticiones + 3

    cuerpo = _previsualizar(cliente, NOMBRE, expresion, {"tipo": "ejemplo"})
    celda = _celdas(cuerpo)[0]
    en_la_tabla = speech.previsualizar_v2(
        [ExpresionSegmento(Segmento.DE_1_A_8, expresion_desde_dict(expresion))], None
    )[0]

    assert (cuerpo["umbral_advertencia"], cuerpo["limite_largo"]) == (
        LARGO_ADVERTENCIA,
        LARGO_MAXIMO,
    )
    assert celda["largo"] == celda["cota"] == en_la_tabla.largo_maximo == esperado
    assert celda["texto"] == "y" * repeticiones + "..."
    nivel = _nivel(celda["largo"], cuerpo["umbral_advertencia"], cuerpo["limite_largo"])
    assert (en_la_tabla.codigo.value if en_la_tabla.codigo else None) == nivel


# --- El comportamiento es del contexto, no del contrato -----------------------------------------


def test_solo_el_speech_declara_medida_y_salida() -> None:
    cartera, mowa = contexto_cartera(CatalogoCartera()), contexto_speech()

    assert cartera.medida is len
    assert cartera.salida(FIJO) == FIJO
    assert mowa.salida is a_gsm7
    assert mowa.medida(FIJO) == largo_gsm7(a_gsm7(FIJO))
    for contexto in obtener_registro_contextos().disponibles():
        if contexto.nombre != NOMBRE:
            assert contexto.medida is len, contexto.nombre
            assert contexto.salida(FIJO) == FIJO, contexto.nombre


def test_la_medida_y_la_salida_no_estan_en_el_catalogo_ni_en_el_contrato(cliente) -> None:
    catalogo = cliente.get("/texto-enriquecido/catalogo", params={"contexto": NOMBRE}).json()
    contexto = catalogo["contexto"]
    esquemas = app.openapi()["components"]["schemas"]

    assert not {"medida", "salida"} & set(contexto)
    assert not {"medida", "salida"} & set(esquemas["ContextoRespuesta"]["properties"])
    assert "medida" not in repr(contexto_speech()) and "salida" not in repr(contexto_speech())
    assert contexto_speech() == contexto_speech()  # el comportamiento no entra en la comparacion


def test_la_generacion_de_cargas_no_aplica_la_salida_solo_la_previsualizacion() -> None:
    campo = CampoSalida("mensaje", "", TipoSalida.TEXTO, expresion=Expresion((NodoTexto(FIJO),)))
    generador = GeneradorCargas(
        DefinicionCarga("d", (campo,)), {"titular": TipoValor.TEXTO}, salida=a_gsm7
    )

    producto = {"titular": "x"}

    assert generador.generar([producto]).filas[0]["mensaje"] == FIJO
    assert generador.detallar_fila(producto, 1).celdas[0].texto == a_gsm7(FIJO)


def test_una_variante_por_segmento_tambien_sale_normalizada(cliente) -> None:
    variante = {"segmento": "1_a_8", "expresion": _con_titular(FIJO + FIJO)}
    columna = {
        "nombre": "mensaje",
        "orden": 0,
        "expresion": _con_titular(),
        "variantes": [variante],
    }
    definicion = {"nombre": "SMS", "columnas": [columna], "segmentacion": {}}

    respuesta = cliente.post(
        "/texto-enriquecido/previsualizacion", json={"contexto": NOMBRE, "definicion": definicion}
    )

    assert respuesta.status_code == 200, respuesta.text
    celdas = _celdas(respuesta.json())
    assert [c["usa_variante"] for c in celdas] == [False, True, False, False, False, False]
    assert celdas[1]["texto"] == FIJO_ENVIADO * 2 + TITULAR_DE_EJEMPLO
    assert celdas[1]["largo"] == 2 * 20 + 8  # 20 = 16 de texto + 3 de EUR + 1 del espacio
    for indice in (0, 2, 3, 4, 5):
        _comprobar_celda(celdas[indice])


# --- El valor por defecto se decide sobre el texto crudo, antes de la salida ----------------------

POR_DEFECTO = "SIN DATO"


def _generador_con_defecto(texto: str, por_defecto: str = POR_DEFECTO) -> GeneradorCargas:
    campo = CampoSalida(
        "mensaje",
        "",
        TipoSalida.TEXTO,
        expresion=Expresion((NodoTexto(texto),)),
        valor_por_defecto=por_defecto,
    )
    return GeneradorCargas(DefinicionCarga("d", (campo,)), {}, salida=a_gsm7)


def test_un_texto_que_solo_trae_signos_que_la_salida_borra_no_es_un_texto_vacio() -> None:
    # La generacion (sin salida) escribe el emoji: el valor por defecto no entra. La
    # previsualizacion debe mostrar lo mismo, ya normalizado, y no el valor por defecto.
    generador = _generador_con_defecto(EMOJI)

    celda = generador.detallar_fila({}, 1).celdas[0]

    cargado = generador.generar([{}]).filas[0]["mensaje"]
    assert cargado == EMOJI
    assert (celda.texto, celda.valor) == ("", "")
    assert celda.texto == a_gsm7(cargado)  # paridad: lo que se muestra es la carga normalizada


def test_un_texto_vacio_usa_el_valor_por_defecto_y_la_salida_lo_normaliza() -> None:
    generador = _generador_con_defecto("", por_defecto=f"Sin d{O_TILDE}to")

    celda = generador.detallar_fila({}, 1).celdas[0]

    cargado = generador.generar([{}]).filas[0]["mensaje"]
    assert cargado == f"Sin d{O_TILDE}to"
    assert (celda.texto, celda.valor) == ("Sin doto", "Sin doto")
    assert celda.texto == a_gsm7(cargado)  # paridad con la carga, que tambien pasa por a_gsm7


def test_un_texto_vacio_sin_cambios_de_salida_usa_el_valor_por_defecto_tal_cual() -> None:
    generador = _generador_con_defecto("")

    celda = generador.detallar_fila({}, 1).celdas[0]

    assert (celda.texto, celda.valor) == (POR_DEFECTO, POR_DEFECTO)
    assert celda.texto == a_gsm7(generador.generar([{}]).filas[0]["mensaje"])


def test_una_plantilla_se_compila_tambien_con_la_medida_del_generador() -> None:
    # La rama de plantilla del generador (RF-54) no pasa por /texto-enriquecido (que solo manda
    # expresiones): se prueba directo. ab + elipsis (3) + EUR (3) = 8; len() daria 4.
    campo = CampoSalida("mensaje", f"ab{ELIPSIS}{EURO}", TipoSalida.TEXTO)
    generador = GeneradorCargas(
        DefinicionCarga("d", (campo,)),
        {"titular": TipoValor.TEXTO},
        medida=contexto_speech().medida,
        salida=a_gsm7,
    )

    celda = generador.detallar_fila({"titular": "x"}, 1).celdas[0]

    assert (celda.cota, celda.texto) == (8, "ab...EUR")
