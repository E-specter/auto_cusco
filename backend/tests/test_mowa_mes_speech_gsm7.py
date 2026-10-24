"""El mensaje de MOWA MES en GSM-7 (RF-MM-27, RF-MM-19 ampliado; T-MM-B9).

Lo que se prueba, sobre el constructor, la previsualizacion y la campana (nada de PostgreSQL):
- el mensaje de una v1 y de una v2 sale normalizado, con `a_gsm7` aplicada al texto YA evaluado y no
  a las variables (el titular se recorta a 8 caracteres antes de normalizarse);
- el largo se mide DESPUES de normalizar y en unidades GSM-7: la elipsis mide 3 y un extendido 2,
  para el control de los 150 y los 160 y para la cota de la previsualizacion;
- la previsualizacion devuelve el ejemplo normalizado y lo que se borra del texto fijo, por grafema;
- la supervision hereda el mensaje normalizado;
- la version se guarda como se escribio: las huellas no cambian.

Los caracteres especiales van con su nombre Unicode (`\\N{...}`): el archivo es ASCII. Datos
sinteticos; WhatsApp 900000xxx.
"""

import random
from datetime import date

import pytest

from app.core.entities.mowa_mes import (
    LARGO_MAXIMO,
    CodigoMowaMes,
    DatosSpeech,
    ExpresionSegmento,
    FormatoSpeech,
    PartesSegmento,
    Segmento,
    VersionSpeech,
)
from app.core.entities.texto_enriquecido import Expresion, LlamadaFuncion, NodoTexto, NodoVariable
from app.core.services.plataformas.mowa_mes import speech
from app.core.services.plataformas.mowa_mes.campana import Exclusion, FilaCarga, evaluar_producto
from app.core.services.texto_enriquecido.gsm7 import a_gsm7, largo_gsm7
from tests.oro_mowa_mes_datos import ORIGINAL
from tests.test_mowa_mes_campana import (
    MOMENTO,
    armar_servicio,
    peticion,
    producto,
)

WHATSAPP = "900000123"
VENCIMIENTO = date(2026, 9, 6)
CORTE = date(2026, 9, 14)

O_TILDE = "\N{LATIN SMALL LETTER O WITH ACUTE}"
N_TILDE = "\N{LATIN SMALL LETTER N WITH TILDE}"
EMOJI = "\N{THUMBS UP SIGN}"
ELIPSIS = "\N{HORIZONTAL ELLIPSIS}"
ANGULAR_I = "\N{LEFT-POINTING DOUBLE ANGLE QUOTATION MARK}"
ANGULAR_D = "\N{RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK}"
ESP_DURO = "\N{NO-BREAK SPACE}"
EURO = "\N{EURO SIGN}"
REGIONAL_P = "\N{REGIONAL INDICATOR SYMBOL LETTER P}"
REGIONAL_E = "\N{REGIONAL INDICATOR SYMBOL LETTER E}"
TONO_DE_PIEL = "\N{EMOJI MODIFIER FITZPATRICK TYPE-4}"


def _v1(**por_segmento: tuple[str, str]) -> tuple[PartesSegmento, ...]:
    """Las partes del Speech original, cambiando las de los segmentos dados por nombre."""
    return tuple(
        PartesSegmento(p.segmento, *por_segmento.get(p.segmento.name, (p.parte_1, p.parte_2)))
        for p in ORIGINAL
    )


def _titular() -> NodoVariable:
    return NodoVariable("titular", (LlamadaFuncion("primeros", (8,)),))


def _fecha() -> NodoVariable:
    return NodoVariable(
        "fecha_vencimiento_cuota", (LlamadaFuncion("formato_fecha", ("dd/mm/aaaa",)),)
    )


def _v2(*nodos) -> DatosSpeech:
    expresiones = tuple(ExpresionSegmento(p.segmento, Expresion(tuple(nodos))) for p in ORIGINAL)
    return DatosSpeech("v2", expresiones=expresiones, formato=FormatoSpeech.V2)


def _mensaje(version, segmento=Segmento.DE_1_A_8, titular="ZZPRUEBA", whatsapp=WHATSAPP):
    return speech.ConstructorMensajes(version, whatsapp).mensaje_de(
        segmento, titular, VENCIMIENTO, dias_ajustados=4
    )


# --- El mensaje sale normalizado -----------------------------------------------------------------


def test_el_mensaje_de_una_v1_sale_normalizado() -> None:
    version = _v1(
        DE_1_A_8=(f" venci{O_TILDE} {EMOJI}{ANGULAR_I}ma{N_TILDE}ana{ANGULAR_D}{ESP_DURO}", ".")
    )

    mensaje = _mensaje(version)

    assert mensaje == 'ZZPRUEBA vencio "manana" 06/09/2026.'  # el emoji se borra


def test_el_mensaje_de_una_v2_sale_normalizado() -> None:
    nodos = (
        NodoTexto(f"Hola {ELIPSIS} {EMOJI}"),
        _titular(),
        NodoTexto(f" venci{O_TILDE} el "),
        _fecha(),
    )

    mensaje = _mensaje(_v2(*nodos))

    assert mensaje == "Hola ... ZZPRUEBA vencio el 06/09/2026"


def test_se_normaliza_el_texto_ya_evaluado_no_las_variables() -> None:
    # `primeros(8)` corta el titular a 8 caracteres CONTANDO la ene con virgulilla como uno
    # ("  Pena R"); recien despues se quita la virgulilla. Antes de recortar daria "  Pena Ru".
    version = _v1(DE_1_A_8=(" x", "."))

    assert _mensaje(version, titular=f"  Pe{N_TILDE}a Ruiz Jose") == "  Pena R x06/09/2026."


def test_el_titular_con_emoji_pierde_el_emoji_despues_de_recortarse() -> None:
    version = _v1(DE_1_A_8=(" x", "."))

    assert _mensaje(version, titular=f"AB{EMOJI}CDEFGHIJ") == "ABCDEFG x06/09/2026."


def test_los_extendidos_se_conservan_en_el_mensaje() -> None:
    version = _v1(DE_1_A_8=(f" paga {EURO}10 [ya]", "."))

    assert _mensaje(version) == f"ZZPRUEBA paga {EURO}10 [ya]06/09/2026."


def test_la_supervision_hereda_el_mensaje_normalizado_de_la_primera_fila() -> None:
    servicio, _, _ = armar_servicio([producto(1), producto(2)])

    armada = servicio.previsualizar(peticion())

    productos = [f for f in armada.filas if not f.supervision]
    supervision = [f for f in armada.filas if f.supervision]
    assert supervision and productos
    assert all(f.mensaje == productos[0].mensaje for f in supervision)
    assert all(a_gsm7(f.mensaje) == f.mensaje for f in armada.filas)  # ya esta en GSM-7
    assert O_TILDE not in productos[0].mensaje  # "vencio" con la o sin tilde


def test_la_version_se_guarda_como_se_escribio_y_su_huella_no_cambia() -> None:
    from app.core.services.plataformas.mowa_mes.campana import huella_speech

    version = _v1(DE_1_A_8=(f" venci{O_TILDE} {EMOJI}", "."))
    antes = huella_speech(version)

    _mensaje(version)  # armar mensajes no toca la version

    assert huella_speech(version) == antes
    assert O_TILDE in version[1].parte_1 and EMOJI in version[1].parte_1


# --- Se mide despues de normalizar y en unidades GSM-7 -----------------------------------------


def _con_parte_2(relleno: str):
    # titular 8 + parte 1 + fecha 10 + parte 2, en el segmento 1 a 8 (sin whatsapp)
    return _v1(DE_1_A_8=(" x", relleno))


def _largo_total(relleno: str) -> int:
    return 8 + len(" x") + 10 + len(relleno)


@pytest.mark.parametrize(
    ("relleno", "unidades", "codigo"),
    [
        ("y" * 130, 150, None),
        ("y" * 129 + EURO, 151, CodigoMowaMes.MENSAJE_EXCEDE_150),  # el extendido cuenta 2
        ("y" * 138 + EURO, 160, CodigoMowaMes.MENSAJE_EXCEDE_150),
        ("y" * 139 + EURO, 161, CodigoMowaMes.MENSAJE_EXCEDE_160),
        ("y" * 127 + ELIPSIS, 150, None),  # la elipsis mide 3 al transliterarse
        ("y" * 128 + ELIPSIS, 151, CodigoMowaMes.MENSAJE_EXCEDE_150),
        ("y" * 137 + ELIPSIS, 160, CodigoMowaMes.MENSAJE_EXCEDE_150),
        ("y" * 138 + ELIPSIS, 161, CodigoMowaMes.MENSAJE_EXCEDE_160),
    ],
)
def test_los_150_y_los_160_se_miden_en_unidades_gsm7_del_mensaje_normalizado(
    relleno, unidades, codigo
) -> None:
    version = _con_parte_2(relleno)
    constructor = speech.ConstructorMensajes(version, WHATSAPP)

    fila = evaluar_producto(_producto(), CORTE, CORTE, constructor)
    previsto = {x.rango.segmento: x for x in speech.previsualizar(version, WHATSAPP)}[
        Segmento.DE_1_A_8
    ]

    assert (previsto.largo_maximo, previsto.codigo) == (unidades, codigo)
    if codigo is CodigoMowaMes.MENSAJE_EXCEDE_160:
        assert fila == Exclusion("000000000000000001", codigo)
    else:
        assert isinstance(fila, FilaCarga)
        assert largo_gsm7(fila.mensaje) == unidades
        assert fila.advertencias == (() if codigo is None else (codigo,))


def test_el_texto_con_la_elipsis_no_pasa_de_160_caracteres_pero_si_en_gsm7() -> None:
    # 158 caracteres crudos con una elipsis: antes de normalizar parecen 158, el SMS real mide 160.
    relleno = "y" * 137 + ELIPSIS
    assert _largo_total(relleno) == 158 < LARGO_MAXIMO

    fila = evaluar_producto(
        _producto(), CORTE, CORTE, speech.ConstructorMensajes(_con_parte_2(relleno), WHATSAPP)
    )

    assert isinstance(fila, FilaCarga) and len(fila.mensaje) == 160
    assert largo_gsm7(fila.mensaje) == 160


def _producto(**cambios) -> dict:
    datos = {
        "pagare": "000000000000000001",
        "telefono": "900000101",
        "documento_numero": "00000001",
        "documento_tipo": "dni",
        "dias_atraso": 4,
        "titular": "ZZPRUEBA",
        "fecha_vencimiento_cuota": VENCIMIENTO,
    }
    return {**datos, **cambios}


def test_la_cota_de_una_v2_se_cuenta_en_unidades_gsm7() -> None:
    # texto fijo "Hola ..." (la elipsis mide 3) + un extendido (2) + titular 8 + fecha 10
    version = _v2(NodoTexto(f"Hola {ELIPSIS} {EURO} "), _titular(), _fecha())

    largos = {x.rango.segmento: x for x in speech.previsualizar_v2(version.expresiones, WHATSAPP)}

    esperado = largo_gsm7(a_gsm7(f"Hola {ELIPSIS} {EURO} ")) + 8 + 10
    assert esperado == len("Hola ... ") + 2 + len(" ") + 8 + 10  # el euro cuenta 2
    assert largos[Segmento.DE_1_A_8].largo_maximo == esperado


def test_la_cota_del_speech_original_sigue_en_156_para_9_a_30() -> None:
    largos = {x.rango.segmento: x for x in speech.previsualizar(ORIGINAL, WHATSAPP)}

    assert largos[Segmento.DE_9_A_30].largo_maximo == 156  # no se cuelga a_gsm7 de las variables
    assert largos[Segmento.DE_9_A_30].codigo is CodigoMowaMes.MENSAJE_EXCEDE_150


def test_propiedad_el_largo_maximo_de_una_v1_es_el_del_mensaje_con_variables_al_maximo() -> None:
    """Con un titular de 8 caracteres y una fecha de 10 (sin extendidos ni elipsis en las
    variables), el largo en unidades GSM-7 del mensaje real es exactamente la cota."""
    azar = random.Random(20261022)
    alfabeto = list("abc XYZ.,:\n") + [
        O_TILDE,
        N_TILDE,
        EMOJI,
        ELIPSIS,
        ANGULAR_I,
        ESP_DURO,
        EURO,
        "[",
        "]",
        "{",
        "|",
        "\\",
        "^",
        "~",
    ]

    for _ in range(600):
        parte_1 = "".join(azar.choice(alfabeto) for _ in range(azar.randint(0, 30)))
        parte_2 = "".join(azar.choice(alfabeto) for _ in range(azar.randint(0, 30)))
        if "[@" in parte_1 + parte_2:
            continue
        version = _v1(DE_1_A_8=(parte_1, parte_2))
        previsto = {x.rango.segmento: x for x in speech.previsualizar(version, None)}
        mensaje = _mensaje(version, titular="ABCDEFGH", whatsapp=None)

        assert a_gsm7(mensaje) == mensaje, repr(mensaje)
        assert largo_gsm7(mensaje) == previsto[Segmento.DE_1_A_8].largo_maximo, (
            repr(parte_1),
            repr(parte_2),
        )


# --- Previsualizacion: ejemplo normalizado y lo que se borra -------------------------------------


def test_el_ejemplo_de_una_v1_sale_normalizado_y_sin_sus_borrados() -> None:
    version = _v1(DE_1_A_8=(f" venci{O_TILDE} {EMOJI}", f" {ELIPSIS}"))

    previsto = {x.rango.segmento: x for x in speech.previsualizar(version, WHATSAPP)}[
        Segmento.DE_1_A_8
    ]

    assert previsto.ejemplo == "XXXXXXXX vencio dd/mm/yyyy ..."
    assert previsto.caracteres_quitados == (EMOJI,)  # la elipsis se transliteran: no se pierde


def test_sin_borrados_la_lista_esta_vacia() -> None:
    for largo in speech.previsualizar(ORIGINAL, WHATSAPP):
        assert largo.caracteres_quitados == (), largo.rango.segmento


def test_los_borrados_salen_aunque_no_haya_ejemplo_por_falta_de_whatsapp() -> None:
    version = _v1(DE_31_A_60=(f" mira {EMOJI} [whatsapp]", f" y {EMOJI}{EMOJI}"))

    previsto = {x.rango.segmento: x for x in speech.previsualizar(version, None)}[
        Segmento.DE_31_A_60
    ]

    assert previsto.ejemplo is None
    assert previsto.caracteres_quitados == (EMOJI,)  # sin repetir


def test_los_borrados_de_una_v1_no_incluyen_lo_que_solo_pierde_su_tilde() -> None:
    version = _v1(DE_1_A_8=(f" venci{O_TILDE} ma{N_TILDE}ana", "."))

    previsto = {x.rango.segmento: x for x in speech.previsualizar(version, WHATSAPP)}[
        Segmento.DE_1_A_8
    ]

    assert previsto.caracteres_quitados == ()


def test_el_ejemplo_y_los_borrados_de_una_v2() -> None:
    version = _v2(NodoTexto(f"Hola {EMOJI} {ELIPSIS}"), _titular(), _fecha())

    previsto = {x.rango.segmento: x for x in speech.previsualizar_v2(version.expresiones, None)}[
        Segmento.DE_1_A_8
    ]

    assert previsto.ejemplo == "Hola  ...XXXXXXXX05/10/2026"
    assert previsto.caracteres_quitados == (EMOJI,)


def test_los_borrados_de_una_v2_sin_ejemplo_salen_del_texto_fijo() -> None:
    contacto = NodoVariable("whatsapp_contacto", (LlamadaFuncion("enlace_whatsapp"),))
    version = _v2(NodoTexto(f"Escribe {EMOJI} a "), contacto)

    previsto = {x.rango.segmento: x for x in speech.previsualizar_v2(version.expresiones, None)}[
        Segmento.DE_1_A_8
    ]

    assert previsto.ejemplo is None
    assert previsto.caracteres_quitados == (EMOJI,)


# --- Los trozos que en el mensaje no van pegados no forman grafemas ---------------------------


def test_dos_partes_de_una_v1_no_fingen_una_bandera_que_la_fecha_separa() -> None:
    # La parte 1 termina en la P y la parte 2 empieza con la E: entre las dos va la fecha.
    version = _v1(DE_1_A_8=(f" a {REGIONAL_P}", f"{REGIONAL_E} b"))

    previsto = {x.rango.segmento: x for x in speech.previsualizar(version, WHATSAPP)}[
        Segmento.DE_1_A_8
    ]

    assert previsto.caracteres_quitados == (REGIONAL_P, REGIONAL_E)


def test_el_enlace_entre_dos_trozos_de_una_v1_tampoco_los_une() -> None:
    version = _v1(DE_31_A_60=(f" {REGIONAL_P}[whatsapp]{REGIONAL_E}", "."))

    for numero in (None, WHATSAPP):  # con ejemplo y sin el
        previsto = {x.rango.segmento: x for x in speech.previsualizar(version, numero)}[
            Segmento.DE_31_A_60
        ]
        assert previsto.caracteres_quitados == (REGIONAL_P, REGIONAL_E), numero


def test_un_emoji_y_un_tono_de_piel_en_trozos_separados_son_dos_elementos() -> None:
    version = _v1(DE_1_A_8=(f" a {EMOJI}", f"{TONO_DE_PIEL} b"))

    previsto = {x.rango.segmento: x for x in speech.previsualizar(version, WHATSAPP)}[
        Segmento.DE_1_A_8
    ]

    assert previsto.caracteres_quitados == (EMOJI, TONO_DE_PIEL)


def test_los_textos_fijos_de_una_v2_sin_ejemplo_se_agrupan_cada_uno_por_su_lado() -> None:
    contacto = NodoVariable("whatsapp_contacto", (LlamadaFuncion("enlace_whatsapp"),))
    version = _v2(NodoTexto(f"a {REGIONAL_P}"), contacto, NodoTexto(f"{REGIONAL_E} b"))

    previsto = {x.rango.segmento: x for x in speech.previsualizar_v2(version.expresiones, None)}[
        Segmento.DE_1_A_8
    ]

    assert previsto.ejemplo is None
    assert previsto.caracteres_quitados == (REGIONAL_P, REGIONAL_E)


def test_un_grafema_completo_dentro_de_un_trozo_sigue_siendo_uno_solo() -> None:
    version = _v1(DE_1_A_8=(f" a {EMOJI}{TONO_DE_PIEL}", f" {REGIONAL_P}{REGIONAL_E}"))

    previsto = {x.rango.segmento: x for x in speech.previsualizar(version, WHATSAPP)}[
        Segmento.DE_1_A_8
    ]

    assert previsto.caracteres_quitados == (EMOJI + TONO_DE_PIEL, REGIONAL_P + REGIONAL_E)


def test_las_versiones_guardadas_siguen_con_sus_huellas() -> None:
    from app.core.services.plataformas.mowa_mes.campana import huella_speech

    assert huella_speech(ORIGINAL) == (
        "297c227cfdd0bb5e1636e08d4ed6cebab971d724c84223acfdb0cfebc2fcf88a"
    )
    assert VersionSpeech is not None and MOMENTO is not None  # imports usados por otras pruebas
