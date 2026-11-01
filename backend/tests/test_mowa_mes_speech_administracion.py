"""Administracion de las versiones de speech, nucleo (T-MM-C11, M-B2; RF-MM-28 a RF-MM-30).

Renombrar, deshabilitar y habilitar, y eliminar, con el repositorio en memoria; y la campana que se
niega a usar una version deshabilitada. Datos sinteticos.
"""

from dataclasses import replace
from datetime import datetime

import pytest

from app.core.entities.mowa_mes import (
    CodigoErrorSpeech,
    CodigoMowaMes,
    DatosSpeech,
    MotivoNoEliminable,
    NombreDeSpeechRepetido,
    Programacion,
    SpeechInmutable,
    SpeechInvalido,
    SpeechNoEliminable,
    SpeechNoEncontrado,
    VersionSpeech,
)
from app.core.entities.mowa_mes_campana import CampanaInvalida, PeticionCampana
from app.core.services.plataformas.mowa_mes.campana import huella_de
from app.core.services.plataformas.mowa_mes.configuracion import ConfiguracionMowaMesService
from tests.test_mowa_mes_campana import FECHA_CORTE, MOMENTO, armar_servicio, producto
from tests.test_mowa_mes_speech import ORIGINAL, WHATSAPP, RepositorioMowaMesFalso, _v2


def _servicio():
    repositorio = RepositorioMowaMesFalso(WHATSAPP)
    return ConfiguracionMowaMesService(repositorio), repositorio


def _nueva(servicio, nombre="Version de prueba") -> VersionSpeech:
    return servicio.crear_speech_v2(nombre, _v2(), None)


def _usar(repositorio, speech_id: int) -> None:
    repositorio.versiones[speech_id] = replace(repositorio.versiones[speech_id], usada_en=MOMENTO)


# --- Las propiedades de la version (un solo lugar) -----------------------------------------------


def _version(**cambios) -> VersionSpeech:
    base = VersionSpeech(7, DatosSpeech("Version", ORIGINAL), False, None, None, MOMENTO)
    return replace(base, **cambios)


@pytest.mark.parametrize(
    ("cambios", "bloqueo", "motivo", "eliminable"),
    [
        ({}, CodigoErrorSpeech.SPEECH_NO_DESHABILITADO, None, False),
        ({"deshabilitada_en": MOMENTO}, None, None, True),
        (
            {"deshabilitada_en": MOMENTO, "usada_en": MOMENTO},
            CodigoErrorSpeech.SPEECH_USADO,
            MotivoNoEliminable.USADA,
            False,
        ),
        (
            {"usada_en": MOMENTO},
            CodigoErrorSpeech.SPEECH_USADO,
            MotivoNoEliminable.USADA,
            False,
        ),
        (
            {"original": True, "deshabilitada_en": MOMENTO},
            CodigoErrorSpeech.SPEECH_ORIGINAL,
            MotivoNoEliminable.ORIGINAL,
            False,
        ),
        (  # el original gana al uso: es el motivo que no cambia nunca
            {"original": True, "usada_en": MOMENTO, "deshabilitada_en": MOMENTO},
            CodigoErrorSpeech.SPEECH_ORIGINAL,
            MotivoNoEliminable.ORIGINAL,
            False,
        ),
    ],
)
def test_eliminable_y_su_motivo_salen_de_la_misma_regla(
    cambios, bloqueo, motivo, eliminable
) -> None:
    version = _version(**cambios)

    assert version.bloqueo_para_eliminar == bloqueo
    assert version.motivo_no_eliminable == motivo
    assert version.eliminable is eliminable


def test_una_deshabilitada_no_es_editable() -> None:
    assert _version().editable is True
    assert _version(deshabilitada_en=MOMENTO).editable is False


# --- Renombrar (RF-MM-28) ------------------------------------------------------------------------


def test_se_renombra_una_version_sin_cambiar_su_contenido_ni_su_huella() -> None:
    servicio, _ = _servicio()
    version = _nueva(servicio)

    renombrada = servicio.renombrar_speech(version.id, "  Otro nombre  ")

    assert renombrada.datos.nombre == "Otro nombre"
    assert renombrada.datos.expresiones == version.datos.expresiones
    assert huella_de(renombrada.datos) == huella_de(version.datos)


def test_se_renombra_una_usada_y_el_original() -> None:
    servicio, repositorio = _servicio()
    version = _nueva(servicio)
    _usar(repositorio, version.id)

    usada = servicio.renombrar_speech(version.id, "Usada con otro nombre")
    original = servicio.renombrar_speech(1, "El de siempre")

    assert usada.datos.nombre == "Usada con otro nombre" and usada.usada
    assert original.datos.nombre == "El de siempre" and original.original
    assert huella_de(original.datos) == huella_de(ORIGINAL_DATOS)


ORIGINAL_DATOS = DatosSpeech("Speech original", ORIGINAL)


def test_el_nombre_repetido_no_distingue_mayusculas() -> None:
    servicio, _ = _servicio()
    _nueva(servicio, "Alfa")
    otra = _nueva(servicio, "Beta")

    with pytest.raises(NombreDeSpeechRepetido):
        servicio.renombrar_speech(otra.id, "ALFA")


def test_renombrar_a_su_propio_nombre_con_otras_mayusculas_se_permite() -> None:
    servicio, _ = _servicio()
    version = _nueva(servicio, "Alfa")

    assert servicio.renombrar_speech(version.id, "ALFA").datos.nombre == "ALFA"


@pytest.mark.parametrize("nombre", ["", "   ", "x" * 200])
def test_un_nombre_invalido_es_speech_invalido(nombre) -> None:
    servicio, _ = _servicio()
    version = _nueva(servicio)

    with pytest.raises(SpeechInvalido) as error:
        servicio.renombrar_speech(version.id, nombre)

    assert [(p.campo, p.segmento) for p in error.value.problemas] == [("nombre", None)]
    assert servicio.obtener_speech(version.id).datos.nombre == "Version de prueba"


def test_renombrar_una_que_no_existe() -> None:
    servicio, _ = _servicio()

    with pytest.raises(SpeechNoEncontrado):
        servicio.renombrar_speech(99, "Nombre")


# --- Deshabilitar y habilitar (RF-MM-29) ---------------------------------------------------------


def test_deshabilitar_y_habilitar_se_ven_en_la_lista() -> None:
    servicio, _ = _servicio()
    version = _nueva(servicio)

    servicio.deshabilitar_speech(version.id)
    deshabilitada = {v.id: v for v in servicio.listar_speech()}[version.id]
    servicio.habilitar_speech(version.id)
    habilitada = {v.id: v for v in servicio.listar_speech()}[version.id]

    assert deshabilitada.deshabilitada_en is not None and not deshabilitada.habilitada
    assert habilitada.deshabilitada_en is None and habilitada.habilitada


def test_deshabilitar_una_deshabilitada_conserva_la_fecha() -> None:
    servicio, repositorio = _servicio()
    version = _nueva(servicio)
    servicio.deshabilitar_speech(version.id)
    primera = datetime(2026, 9, 1, tzinfo=MOMENTO.tzinfo)
    repositorio.versiones[version.id] = replace(
        repositorio.versiones[version.id], deshabilitada_en=primera
    )

    assert servicio.deshabilitar_speech(version.id).deshabilitada_en == primera


def test_se_deshabilita_una_usada_y_se_conserva_todo() -> None:
    servicio, repositorio = _servicio()
    version = _nueva(servicio)
    _usar(repositorio, version.id)

    deshabilitada = servicio.deshabilitar_speech(version.id)

    assert deshabilitada.usada_en == MOMENTO
    assert huella_de(deshabilitada.datos) == huella_de(version.datos)


@pytest.mark.parametrize("operacion", ["deshabilitar_speech", "habilitar_speech"])
def test_habilitar_o_deshabilitar_una_que_no_existe(operacion) -> None:
    servicio, _ = _servicio()

    with pytest.raises(SpeechNoEncontrado):
        getattr(servicio, operacion)(99)


def test_una_deshabilitada_no_se_edita() -> None:
    servicio, _ = _servicio()
    version = _nueva(servicio)
    servicio.deshabilitar_speech(version.id)

    with pytest.raises(SpeechInmutable, match="deshabilitada"):
        servicio.actualizar_speech(
            version.id,
            DatosSpeech("Nuevo", expresiones=version.datos.expresiones),
        )

    servicio.habilitar_speech(version.id)
    assert (
        servicio.actualizar_speech(
            version.id,
            DatosSpeech("Nuevo", expresiones=version.datos.expresiones),
        ).datos.nombre
        == "Nuevo"
    )


# --- Eliminar (RF-MM-30) -------------------------------------------------------------------------


def test_se_elimina_una_deshabilitada_sin_uso() -> None:
    servicio, repositorio = _servicio()
    version = _nueva(servicio)
    servicio.deshabilitar_speech(version.id)

    servicio.eliminar_speech(version.id)

    assert version.id not in repositorio.versiones
    with pytest.raises(SpeechNoEncontrado):
        servicio.obtener_speech(version.id)


def test_una_habilitada_no_se_elimina() -> None:
    servicio, repositorio = _servicio()
    version = _nueva(servicio)

    with pytest.raises(SpeechNoEliminable) as error:
        servicio.eliminar_speech(version.id)

    assert error.value.codigo is CodigoErrorSpeech.SPEECH_NO_DESHABILITADO
    assert version.id in repositorio.versiones


def test_una_usada_no_se_elimina_ni_deshabilitada() -> None:
    servicio, repositorio = _servicio()
    version = _nueva(servicio)
    _usar(repositorio, version.id)
    servicio.deshabilitar_speech(version.id)

    with pytest.raises(SpeechNoEliminable) as error:
        servicio.eliminar_speech(version.id)

    assert error.value.codigo is CodigoErrorSpeech.SPEECH_USADO
    assert version.id in repositorio.versiones


def test_el_original_no_se_elimina_ni_deshabilitado() -> None:
    servicio, repositorio = _servicio()
    servicio.deshabilitar_speech(1)

    with pytest.raises(SpeechNoEliminable) as error:
        servicio.eliminar_speech(1)

    assert error.value.codigo is CodigoErrorSpeech.SPEECH_ORIGINAL
    assert 1 in repositorio.versiones


def test_eliminar_una_que_no_existe() -> None:
    servicio, _ = _servicio()

    with pytest.raises(SpeechNoEncontrado):
        servicio.eliminar_speech(99)


@pytest.mark.parametrize(
    ("caso", "codigo"),
    [
        ("habilitada", CodigoErrorSpeech.SPEECH_NO_DESHABILITADO),
        ("usada", CodigoErrorSpeech.SPEECH_USADO),
        ("original", CodigoErrorSpeech.SPEECH_ORIGINAL),
    ],
)
def test_el_servicio_no_elimina_aunque_el_repositorio_lo_permita(caso, codigo) -> None:
    # Defensa en profundidad: el DELETE del repositorio lleva las condiciones, pero el servicio no
    # depende de eso para negarse (ni para decir por que).
    servicio, repositorio = _servicio()
    version = _nueva(servicio)
    if caso == "usada":
        servicio.deshabilitar_speech(version.id)
        _usar(repositorio, version.id)
    objetivo = 1 if caso == "original" else version.id
    repositorio.eliminar_speech = lambda speech_id: True  # un repositorio sin condiciones

    with pytest.raises(SpeechNoEliminable) as error:
        servicio.eliminar_speech(objetivo)

    assert error.value.codigo is codigo


def test_si_la_habilitan_entre_la_lectura_y_el_borrado_no_se_elimina() -> None:
    servicio, repositorio = _servicio()
    version = _nueva(servicio)
    servicio.deshabilitar_speech(version.id)
    borrar = repositorio.eliminar_speech

    def habilitar_y_borrar(speech_id):
        servicio.habilitar_speech(speech_id)  # alguien la habilita justo antes del DELETE
        return borrar(speech_id)

    repositorio.eliminar_speech = habilitar_y_borrar

    with pytest.raises(SpeechNoEliminable) as error:
        servicio.eliminar_speech(version.id)

    assert error.value.codigo is CodigoErrorSpeech.SPEECH_NO_DESHABILITADO
    assert version.id in repositorio.versiones


# --- La campana no usa una deshabilitada (RF-MM-29) ----------------------------------------------


def _peticion() -> PeticionCampana:
    return PeticionCampana(
        fecha_corte=FECHA_CORTE,
        cantidad=100,
        programacion=Programacion.HORA_DETERMINADA,
        envios=(datetime(2026, 9, 14, 9, 0),),
    )


def test_la_previsualizacion_marca_una_deshabilitada_como_error() -> None:
    servicio, _, mowa_mes = armar_servicio([producto(1)])
    mowa_mes.versiones[1] = replace(mowa_mes.versiones[1], deshabilitada_en=MOMENTO)

    armada = servicio.previsualizar(_peticion())

    assert [e.codigo for e in armada.errores] == [CodigoMowaMes.SPEECH_DESHABILITADO]
    assert "deshabilitada" in armada.errores[0].detalle


def test_la_creacion_con_una_deshabilitada_se_rechaza_y_no_guarda_nada() -> None:
    servicio, campanas, mowa_mes = armar_servicio([producto(1)])
    previa = servicio.previsualizar(_peticion())
    mowa_mes.versiones[1] = replace(mowa_mes.versiones[1], deshabilitada_en=MOMENTO)

    with pytest.raises(CampanaInvalida) as error:
        servicio.crear(replace(_peticion(), speech_huella=previa.speech_huella))

    assert [e.codigo for e in error.value.errores] == [CodigoMowaMes.SPEECH_DESHABILITADO]
    assert campanas.campanas == {}


def test_una_habilitada_no_tiene_ese_error_y_al_habilitarla_vuelve_a_servir() -> None:
    servicio, _, mowa_mes = armar_servicio([producto(1)])
    mowa_mes.versiones[1] = replace(mowa_mes.versiones[1], deshabilitada_en=MOMENTO)
    mowa_mes.versiones[1] = replace(mowa_mes.versiones[1], deshabilitada_en=None)

    armada = servicio.previsualizar(_peticion())

    assert armada.errores == ()
