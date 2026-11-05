"""El tema de cada variable y la linea de alcance del buscador (T-HI-B7, §13.3 del motor).

El tema lo manda el backend, una sola fuente. Un campo base sin tema cae en `otros`, y estas pruebas
fallan para que un campo nuevo no se pierda; un campo adicional es de `adicionales`.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.entities.campos_adicionales import CampoAdicional, TipoAdicional
from app.core.entities.contexto_texto import TemaVariable
from app.core.services.contextos_texto import contexto_cartera, tema_de
from app.core.services.plataformas.mowa_mes import speech
from app.core.services.plataformas.mowa_mes.contexto_texto import CLAVE_ALCANCE, contexto_speech
from app.core.services.seleccion_cartera.campos import CAMPOS_BASE, CatalogoCartera
from app.main import app


class _Adicionales:
    def __init__(self, *campos: CampoAdicional) -> None:
        self._campos = campos

    def listar(self):
        return self._campos


def _con_adicional() -> CatalogoCartera:
    campo = CampoAdicional(
        nombre="ad_monto_mora",
        nombre_legible="Monto en mora",
        tipo=TipoAdicional.NUMERO,
        encabezado_origen="monto en mora",
    )
    return CatalogoCartera(_Adicionales(campo))


def _tema(contexto, nombre: str) -> TemaVariable:
    return next(v.tema for v in contexto.variables if v.nombre == nombre)


def test_los_temas_salen_en_el_orden_del_buscador() -> None:
    assert [t.value for t in TemaVariable] == [
        "persona",
        "deuda",
        "fechas",
        "credito",
        "gestion",
        "riesgo",
        "adicionales",
        "otros",
    ]


def test_ningun_campo_base_de_la_cartera_queda_en_otros() -> None:
    # Un campo base nuevo sin tema asignado cae en `otros`: esta prueba avisa que le falta uno.
    variables = contexto_cartera(CatalogoCartera()).variables

    assert [v.nombre for v in variables if v.tema is TemaVariable.OTROS] == []
    assert (
        len(variables) == len(CAMPOS_BASE) + 2
    )  # los 44 de la base y las dos de la fecha de envio


def test_un_campo_base_sin_tema_asignado_cae_en_otros_y_uno_adicional_en_adicionales() -> None:
    assert tema_de("campo_base_nuevo") is TemaVariable.OTROS
    assert tema_de("lo_que_sea", adicional=True) is TemaVariable.ADICIONALES


@pytest.mark.parametrize(
    ("nombre", "tema"),
    [
        ("titular", TemaVariable.PERSONA),
        ("telefono", TemaVariable.PERSONA),
        ("saldo_soles_corte", TemaVariable.DEUDA),
        ("monto_cuota", TemaVariable.DEUDA),
        ("fecha_vencimiento_cuota", TemaVariable.FECHAS),
        ("fecha_envio", TemaVariable.FECHAS),
        ("dias_atraso_ajustados", TemaVariable.FECHAS),
        ("pagare", TemaVariable.CREDITO),
        ("agencia", TemaVariable.GESTION),
        ("segmento_saldo", TemaVariable.RIESGO),
        ("provision_proyectada", TemaVariable.RIESGO),
    ],
)
def test_el_tema_de_cada_variable_de_la_cartera(nombre, tema) -> None:
    assert _tema(contexto_cartera(CatalogoCartera()), nombre) is tema


def test_un_campo_adicional_es_del_tema_adicionales() -> None:
    assert _tema(contexto_cartera(_con_adicional()), "ad_monto_mora") is TemaVariable.ADICIONALES
    assert _tema(contexto_speech(_con_adicional()), "ad_monto_mora") is TemaVariable.ADICIONALES


def test_columnas_no_tiene_linea_de_alcance_porque_ofrece_todo() -> None:
    assert contexto_cartera(CatalogoCartera()).clave_alcance is None


# --- El speech de MOWA MES: lo de hoy, con tema y linea de alcance (parte 1) --------------------


def test_el_speech_ofrece_lo_de_hoy_sus_variables_y_los_adicionales_con_tema() -> None:
    contexto = contexto_speech(_con_adicional())

    assert {v.nombre for v in contexto.variables} == {*speech.VARIABLES_V2, "ad_monto_mora"}
    assert [v.nombre for v in contexto.variables if v.tema is TemaVariable.OTROS] == []
    # Los campos base de la cartera no se ofrecen todavia (parte 2 de T-HI-B7).
    assert "saldo_soles_corte" not in {v.nombre for v in contexto.variables}


def test_el_speech_conserva_sus_variables_propias_con_su_nombre_y_su_origen() -> None:
    propias = {v.nombre: v for v in contexto_speech().variables if v.origen == "mowa_mes.speech"}

    assert set(propias) == {speech.VARIABLE_CONTACTO, speech.VARIABLE_DIAS}
    assert propias[speech.VARIABLE_CONTACTO].tema is TemaVariable.PERSONA
    assert propias[speech.VARIABLE_DIAS].tema is TemaVariable.FECHAS
    assert _tema(contexto_speech(), speech.VARIABLE_TITULAR) is TemaVariable.PERSONA
    assert _tema(contexto_speech(), speech.VARIABLE_VENCIMIENTO) is TemaVariable.FECHAS


def test_el_speech_trae_su_linea_de_alcance() -> None:
    assert contexto_speech().clave_alcance == CLAVE_ALCANCE


# --- La API ------------------------------------------------------------------------------------


def test_el_catalogo_por_http_trae_el_tema_de_cada_variable_y_la_linea_de_alcance() -> None:
    http = TestClient(app)

    cartera = http.get("/texto-enriquecido/catalogo", params={"contexto": "cartera"}).json()
    mowa = http.get("/texto-enriquecido/catalogo", params={"contexto": "mowa_mes.speech"}).json()

    assert {v["tema"] for v in cartera["contexto"]["variables"]} <= {t.value for t in TemaVariable}
    assert [v["nombre"] for v in cartera["contexto"]["variables"] if v["tema"] == "otros"] == []
    assert cartera["contexto"]["clave_alcance"] is None
    assert mowa["contexto"]["clave_alcance"] == CLAVE_ALCANCE
    assert len(mowa["contexto"]["variables"]) == len(speech.VARIABLES_V2)  # sin adicionales
