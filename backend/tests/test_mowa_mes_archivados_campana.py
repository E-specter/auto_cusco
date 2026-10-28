"""El aviso de campos archivados en la previsualizacion de la campana (T-MM-B13, plan 8).

Un adicional archivado deja de encontrarse al analizar una sabana nueva: si el speech lo lee, los
productos de esos segmentos quedan fuera con `falta_campo_adicional`. La previsualizacion lo avisa,
mirando el speech ENTERO (no solo los segmentos con productos). Es solo un aviso: no cambia
`puede_crear`, las exclusiones ni nada mas. Adicionales sinteticos; datos sinteticos.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal

from app.core.entities.campos_adicionales import CampoAdicional, TipoAdicional
from app.core.entities.mowa_mes import DatosSpeech, ExpresionSegmento, FormatoSpeech, Segmento
from app.core.entities.texto_enriquecido import Expresion, NodoTexto
from app.core.services.plataformas.mowa_mes.campana import huella_de
from app.main import app
from tests.campos_adicionales_memoria import (
    ARCHIVADO,
    FECHA,
    NUMERO,
    TEXTO,
    CamposAdicionalesEnMemoria,
)
from tests.test_api_mowa_mes_adicionales import _campanas_api, _con_speech_v2
from tests.test_api_mowa_mes_campanas import CUERPO
from tests.test_mowa_mes_adicionales import (
    ANTIGUO,
    COMPLETO,
    MONTO,
    VISITA,
    ZONA,
    ZONA_ACOTADA,
    _f,
    _peticion_v2,
    _servicio,
    _v2,
    _var,
)
from tests.test_mowa_mes_campana import peticion, producto

OTRO_ARCHIVADO = CampoAdicional(
    "ad_viejo_dos", "Otro viejo", TipoAdicional.TEXTO, "otro viejo", archivado=True
)
VIEJO = OTRO_ARCHIVADO.nombre
CATALOGO = (TEXTO, NUMERO, FECHA, ARCHIVADO, OTRO_ARCHIVADO)
LEE_ANTIGUO = _var(ANTIGUO, _f("a_texto"), _f("primeros", 5))
LEE_VIEJO = _var(VIEJO, _f("primeros", 5))
PRODUCTO_COMPLETO = {ZONA: "ZONA UNO", MONTO: Decimal("5"), VISITA: date(2026, 10, 5)}


def _por_segmento(**expresiones: tuple) -> DatosSpeech:
    """Un speech v2 con un texto fijo en cada segmento, salvo los que se den (`s_<segmento>`)."""
    return DatosSpeech(
        "Por segmento",
        expresiones=tuple(
            ExpresionSegmento(s, Expresion(expresiones.get(f"s_{s.value}", (NodoTexto("x"),))))
            for s in Segmento
        ),
        formato=FormatoSpeech.V2,
    )


def _armar(datos, productos=None, adicionales=CATALOGO):
    servicio, repositorio = _servicio(
        productos if productos is not None else [producto(1, **PRODUCTO_COMPLETO)],
        adicionales,
        datos,
    )
    return servicio.previsualizar(_peticion_v2(datos)), repositorio


# --- El nucleo --------------------------------------------------------------------------------


def test_una_v2_que_lee_un_archivado_da_su_nombre_tecnico() -> None:
    armada, _ = _armar(_v2(LEE_ANTIGUO, NodoTexto(" "), ZONA_ACOTADA))

    assert armada.campos_archivados == (ANTIGUO,)


def test_el_mismo_archivado_en_dos_segmentos_sale_una_vez_y_en_el_orden_de_los_segmentos() -> None:
    datos = _por_segmento(
        s_preventiva=(LEE_ANTIGUO,),
        s_1_a_8=(LEE_ANTIGUO,),
        s_91_a_120=(LEE_VIEJO,),
    )

    armada, _ = _armar(datos)

    assert armada.campos_archivados == (ANTIGUO, VIEJO)


def test_dentro_de_un_segmento_salen_en_el_orden_de_sus_nodos() -> None:
    datos = _por_segmento(s_9_a_30=(LEE_VIEJO, NodoTexto(" "), LEE_ANTIGUO))

    armada, _ = _armar(datos)

    assert armada.campos_archivados == (VIEJO, ANTIGUO)


def test_se_mira_el_speech_entero_no_solo_los_segmentos_con_productos() -> None:
    # El unico producto cae en 1 a 8; el archivado solo se lee en 91 a 120.
    datos = _por_segmento(s_91_a_120=(LEE_ANTIGUO,))

    armada, _ = _armar(datos)

    assert armada.campos_archivados == (ANTIGUO,)


def test_un_adicional_que_no_esta_archivado_no_se_avisa() -> None:
    armada, _ = _armar(COMPLETO)  # lee texto, numero y fecha vigentes

    assert armada.campos_archivados == ()


def test_sin_adicionales_en_el_speech_da_vacio() -> None:
    armada, _ = _armar(_por_segmento())

    assert armada.campos_archivados == ()


def test_una_v1_no_lee_ninguno_y_da_vacio() -> None:
    servicio, _ = _servicio([producto(1)], CATALOGO)

    armada = servicio.previsualizar(peticion())  # el Speech original (v1)

    assert armada.campos_archivados == ()


def test_el_aviso_no_cambia_nada_mas_de_la_previsualizacion() -> None:
    productos = [
        producto(1, **{**PRODUCTO_COMPLETO, ANTIGUO: Decimal("7")}),
        producto(2, **{**PRODUCTO_COMPLETO, ANTIGUO: None}),  # queda fuera por el campo archivado
    ]
    datos = _v2(LEE_ANTIGUO, NodoTexto(" "), ZONA_ACOTADA)
    desarchivado = replace(ARCHIVADO, archivado=False)

    con_aviso, _ = _armar(datos, productos)
    sin_aviso, _ = _armar(datos, productos, (TEXTO, NUMERO, FECHA, desarchivado, OTRO_ARCHIVADO))

    assert con_aviso.campos_archivados == (ANTIGUO,) and sin_aviso.campos_archivados == ()
    assert replace(con_aviso, campos_archivados=()) == sin_aviso  # exclusiones, errores, todo igual
    assert [e.pagare for e in con_aviso.exclusiones] == [producto(2)["pagare"]]
    assert not con_aviso.errores


# --- La API -----------------------------------------------------------------------------------


def _previa(client):
    return client.post("/mowa-mes/campanas/previsualizacion", json=_con_speech_v2()).json()


def _productos_api():
    return [producto(1, **{**PRODUCTO_COMPLETO, ANTIGUO: Decimal("7")})]


def test_la_api_devuelve_el_archivado_con_su_nombre_tecnico_y_su_etiqueta() -> None:
    datos = _v2(LEE_ANTIGUO, NodoTexto(" "), ZONA_ACOTADA)
    client, _ = _campanas_api(_productos_api(), CamposAdicionalesEnMemoria(CATALOGO), datos)

    previa = _previa(client)

    assert previa["campos_archivados"] == [{"nombre": ANTIGUO, "etiqueta": "Campo antiguo"}]


def test_renombrar_el_archivado_cambia_la_etiqueta_y_no_el_nombre_tecnico() -> None:
    datos = _v2(LEE_ANTIGUO)
    repositorio = CamposAdicionalesEnMemoria(CATALOGO)
    client, _ = _campanas_api(_productos_api(), repositorio, datos)
    antes = _previa(client)["campos_archivados"]

    repositorio.campos[repositorio.campos.index(ARCHIVADO)] = replace(
        ARCHIVADO, nombre_legible="Nombre nuevo"
    )
    despues = _previa(client)["campos_archivados"]

    assert antes == [{"nombre": ANTIGUO, "etiqueta": "Campo antiguo"}]
    assert despues == [{"nombre": ANTIGUO, "etiqueta": "Nombre nuevo"}]


def test_sin_archivados_o_con_una_v1_la_api_da_lista_vacia() -> None:
    client, _ = _campanas_api(_productos_api(), CamposAdicionalesEnMemoria(CATALOGO), COMPLETO)
    con_v2 = _previa(client)
    con_v1 = client.post("/mowa-mes/campanas/previsualizacion", json=CUERPO).json()

    assert con_v2["campos_archivados"] == [] and con_v1["campos_archivados"] == []


def test_la_api_no_cambia_puede_crear_ni_las_exclusiones_por_el_aviso() -> None:
    datos = _v2(LEE_ANTIGUO, NodoTexto(" "), ZONA_ACOTADA)
    productos = [*_productos_api(), producto(2, **{**PRODUCTO_COMPLETO, ANTIGUO: None})]
    client, _ = _campanas_api(productos, CamposAdicionalesEnMemoria(CATALOGO), datos)
    con_aviso = _previa(client)
    vigente = replace(ARCHIVADO, archivado=False)
    client, _ = _campanas_api(
        productos,
        CamposAdicionalesEnMemoria((TEXTO, NUMERO, FECHA, vigente, OTRO_ARCHIVADO)),
        datos,
    )
    sin_aviso = _previa(client)

    def sin_el_campo(previa):
        return {k: v for k, v in previa.items() if k != "campos_archivados"}

    assert con_aviso["campos_archivados"] != sin_aviso["campos_archivados"] == []
    assert sin_el_campo(con_aviso) == sin_el_campo(sin_aviso)
    assert con_aviso["puede_crear"] is True
    assert [e["codigo"] for e in con_aviso["exclusiones"]["exclusiones"]] == [
        "falta_campo_adicional"
    ]


def test_crear_y_el_detalle_de_la_campana_no_llevan_el_aviso() -> None:
    datos = _v2(LEE_ANTIGUO, NodoTexto(" "), ZONA_ACOTADA)
    client, _ = _campanas_api(_productos_api(), CamposAdicionalesEnMemoria(CATALOGO), datos)

    creada = client.post(
        "/mowa-mes/campanas", json={**_con_speech_v2(), "speech_huella": huella_de(datos)}
    )
    detalle = client.get(f"/mowa-mes/campanas/{creada.json()['id']}")

    assert creada.status_code == 201, creada.text
    assert "campos_archivados" not in creada.json() and "campos_archivados" not in detalle.json()


def test_el_contrato_declara_el_aviso_solo_en_la_previsualizacion_de_la_campana() -> None:
    esquemas = app.openapi()["components"]["schemas"]

    previa = esquemas["PrevisualizacionCampanaRespuesta"]
    assert "campos_archivados" in previa["required"]
    assert "nunca bloquea" in previa["properties"]["campos_archivados"]["description"]
    assert "campos_archivados" not in esquemas["CampanaRespuesta"]["properties"]
