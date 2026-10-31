"""Contrato: cada codigo de MOWA MES tiene su traduccion en el frontend.

Lee los diccionarios de verdad (`frontend/src/i18n/es.json` y `en.json`), no una
copia. El frontend traduce por codigo con la clave plana
`mowaMes.codigo.<codigo>`; las claves las agrega `dev_frontend_modulo_mowa_mes`
en su bloque `mowaMes.*`. La prueba espejo del frontend comprueba la otra
direccion: que no queden claves de codigos que ya no existen.
"""

from app.core.entities.mowa_mes import TIPO_CODIGO, CodigoErrorSpeech, CodigoMowaMes, TipoCodigo
from app.core.entities.mowa_mes_campana import CodigoErrorCampana
from tests.ayudas.espejo_i18n import assert_cubre


def test_cada_codigo_tiene_su_traduccion() -> None:
    assert_cubre(
        CodigoMowaMes,
        "mowaMes.codigo",
        ayuda=(
            "Las agrega dev_frontend en el bloque mowaMes.* del diccionario "
            "(ver docs/mowa-mes.md, catalogo de codigos)."
        ),
    )


def test_cada_codigo_de_error_de_campana_tiene_su_traduccion() -> None:
    assert_cubre(CodigoErrorCampana, "mowaMes.errorCampana")


def test_cada_codigo_de_error_de_speech_tiene_su_traduccion() -> None:
    assert_cubre(CodigoErrorSpeech, "mowaMes.errorSpeech")


def test_cada_codigo_tiene_tipo() -> None:
    assert set(TIPO_CODIGO) == set(CodigoMowaMes)


def test_las_exclusiones_siguen_el_orden_de_evaluacion() -> None:
    exclusiones = [c for c in CodigoMowaMes if TIPO_CODIGO[c] is TipoCodigo.EXCLUSION]

    assert exclusiones == [
        CodigoMowaMes.TELEFONO_INVALIDO,
        CodigoMowaMes.FALTA_DOCUMENTO,
        CodigoMowaMes.SIN_SPEECH,
        CodigoMowaMes.FALTA_TITULAR,
        CodigoMowaMes.FALTA_VENCIMIENTO,
        CodigoMowaMes.FALTA_CAMPO_ADICIONAL,
        CodigoMowaMes.MENSAJE_EXCEDE_160,
    ]
