"""Pruebas del speech de MOWA MES (RF-MM-14 a RF-MM-19) y de la configuracion del conector.

Titulares y numeros sinteticos; WhatsApp del rango 900000xxx.
"""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from app.core.entities.mowa_mes import (
    RANGOS_SEGMENTO,
    CodigoMowaMes,
    ConfiguracionInvalida,
    ConfiguracionMowaMes,
    DatosSpeech,
    FaltaWhatsapp,
    NombreDeSpeechRepetido,
    PartesSegmento,
    Programacion,
    Segmento,
    SpeechInmutable,
    SpeechInvalido,
    SpeechNoEncontrado,
    VersionSpeech,
)
from app.core.services.plataformas.mowa_mes import segmentos, speech
from app.core.services.plataformas.mowa_mes.configuracion import (
    ConfiguracionMowaMesService,
    nombre_siguiente,
)
from tests.test_speech_original import speech_de_la_migracion

MOMENTO = datetime(2026, 9, 13, 10, 0, tzinfo=UTC)
WHATSAPP = "900000123"
ORIGINAL = speech_de_la_migracion()
VENCIMIENTO = date(2026, 9, 5)


class RepositorioMowaMesFalso:
    def __init__(self, whatsapp: str | None = None) -> None:
        self.configuracion = ConfiguracionMowaMes(2_500_000, whatsapp, MOMENTO)
        self.versiones: dict[int, VersionSpeech] = {
            1: VersionSpeech(1, DatosSpeech("Speech original", ORIGINAL), True, None, None, MOMENTO)
        }
        self.escrituras = 0

    def obtener_configuracion(self):
        return self.configuracion

    def guardar_configuracion(self, configuracion):
        self.escrituras += 1
        self.configuracion = replace(configuracion, actualizado_en=MOMENTO)
        return self.configuracion

    def listar_speech(self):
        return list(self.versiones.values())

    def obtener_speech(self, speech_id):
        return self.versiones.get(speech_id)

    def _repetido(self, nombre, excepto=None):
        return any(
            v.datos.nombre.casefold() == nombre.casefold() and v.id != excepto
            for v in self.versiones.values()
        )

    def crear_speech(self, datos, basada_en_id):
        if self._repetido(datos.nombre):
            raise NombreDeSpeechRepetido(datos.nombre)
        self.escrituras += 1
        nuevo_id = max(self.versiones) + 1
        self.versiones[nuevo_id] = VersionSpeech(
            nuevo_id, datos, False, basada_en_id, None, MOMENTO
        )
        return self.versiones[nuevo_id]

    def actualizar_speech(self, speech_id, datos):
        version = self.versiones.get(speech_id)
        if version is None or not version.editable:
            return None
        if self._repetido(datos.nombre, excepto=speech_id):
            raise NombreDeSpeechRepetido(datos.nombre)
        self.escrituras += 1
        self.versiones[speech_id] = replace(version, datos=datos)
        return self.versiones[speech_id]

    def marcar_speech_usado(self, speech_id):
        self.versiones[speech_id] = replace(self.versiones[speech_id], usada_en=MOMENTO)


def _servicio(
    whatsapp: str | None = WHATSAPP,
) -> tuple[ConfiguracionMowaMesService, RepositorioMowaMesFalso]:
    repositorio = RepositorioMowaMesFalso(whatsapp)
    return ConfiguracionMowaMesService(repositorio), repositorio


def _partes(segmento: Segmento) -> PartesSegmento:
    return next(p for p in ORIGINAL if p.segmento is segmento)


# --- Dias ajustados y segmento (RF-MM-15) -------------------------------


def test_dias_ajustados_suma_los_dias_entre_corte_y_envio() -> None:
    corte = date(2026, 9, 10)

    dias = segmentos.dias_ajustados(4, corte, date(2026, 9, 13))

    assert dias == 7
    assert segmentos.rango_de(dias).segmento is Segmento.DE_1_A_8


@pytest.mark.parametrize(
    ("dias", "segmento"),
    [
        (-30, Segmento.PREVENTIVA),
        (0, Segmento.PREVENTIVA),  # S-MM-6
        (1, Segmento.DE_1_A_8),
        (8, Segmento.DE_1_A_8),
        (9, Segmento.DE_9_A_30),
        (30, Segmento.DE_9_A_30),
        (31, Segmento.DE_31_A_60),
        (60, Segmento.DE_31_A_60),
        (61, Segmento.DE_61_A_90),
        (90, Segmento.DE_61_A_90),
        (91, Segmento.DE_91_A_120),
        (120, Segmento.DE_91_A_120),
    ],
)
def test_bordes_de_los_segmentos(dias, segmento) -> None:
    assert segmentos.rango_de(dias).segmento is segmento


@pytest.mark.parametrize("dias", [121, 5000, None])
def test_sin_speech_fuera_de_rango_o_sin_dias(dias) -> None:
    assert segmentos.rango_de(dias) is None


def test_los_rangos_cubren_sin_huecos_ni_solapes() -> None:
    for anterior, siguiente in zip(RANGOS_SEGMENTO, RANGOS_SEGMENTO[1:], strict=False):
        assert siguiente.desde == anterior.hasta + 1


def test_fecha_de_envio_segun_la_programacion() -> None:
    generacion = date(2026, 9, 13)
    fechas = [date(2026, 9, 16), date(2026, 9, 15), date(2026, 9, 18)]

    assert segmentos.fecha_envio(Programacion.ENVIAR_AHORA, generacion) == generacion
    assert segmentos.fecha_envio(Programacion.HORA_DETERMINADA, generacion, fechas[:1]) == fechas[0]
    # S-MM-5: la mas temprana.
    assert segmentos.fecha_envio(Programacion.DIFERENTES_HORAS, generacion, fechas) == fechas[1]


@pytest.mark.parametrize(
    ("programacion", "fechas"),
    [
        (Programacion.HORA_DETERMINADA, []),
        (Programacion.HORA_DETERMINADA, [date(2026, 9, 14), date(2026, 9, 15)]),
        (Programacion.DIFERENTES_HORAS, []),
    ],
)
def test_programacion_sin_las_fechas_que_corresponden(programacion, fechas) -> None:
    with pytest.raises(segmentos.ProgramacionInvalida):
        segmentos.fecha_envio(programacion, date(2026, 9, 13), fechas)


# --- Mensaje (RF-MM-14, RF-MM-16) ---------------------------------------


def test_el_mensaje_une_titular_8_parte_1_fecha_y_parte_2() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, WHATSAPP)

    mensaje = constructor.mensaje_de(Segmento.DE_1_A_8, "ZZPRUEBA SINTETICO", VENCIMIENTO)

    assert mensaje == (
        "ZZPRUEBA Caja Cusco te informa que tu cuota venció el 05/09/2026, acércate a pagar"
        " a nuestras agencias, agentes KASNET o a través de Wayki app."
    )


def test_un_titular_corto_se_usa_completo() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, WHATSAPP)

    mensaje = constructor.mensaje_de(Segmento.PREVENTIVA, "ZZ", VENCIMIENTO)

    assert mensaje.startswith("ZZ Caja Cusco te recuerda que tu cuota Vence el 05/09/2026.")


def test_la_variable_de_whatsapp_se_reemplaza_por_el_enlace() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, WHATSAPP)

    mensaje = constructor.mensaje_de(Segmento.DE_31_A_60, "ZZPRUEBA", VENCIMIENTO)

    assert mensaje.endswith("INFO por https://wa.me/+51900000123")
    assert "[whatsapp]" not in mensaje


def test_sin_whatsapp_los_segmentos_que_lo_usan_no_generan_enlace_roto() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, None)

    assert constructor.requiere_whatsapp_faltante(Segmento.DE_61_A_90)
    assert not constructor.requiere_whatsapp_faltante(Segmento.DE_9_A_30)
    assert constructor.mensaje_de(Segmento.DE_9_A_30, "ZZPRUEBA", VENCIMIENTO).startswith(
        "ZZPRUEBA Caja"
    )
    with pytest.raises(FaltaWhatsapp):
        constructor.mensaje_de(Segmento.DE_61_A_90, "ZZPRUEBA", VENCIMIENTO)


def test_el_texto_del_usuario_con_corchetes_no_se_interpreta_como_campo() -> None:
    partes = [replace(p, parte_2=" [titular] [fecha] [@") for p in ORIGINAL]

    problemas = speech.problemas_de(DatosSpeech("con referencia", tuple(partes)))

    assert {(p.segmento, p.campo) for p in problemas} == {(p.segmento, "parte_2") for p in ORIGINAL}


@pytest.mark.parametrize(
    ("largo", "codigo"),
    [
        (150, None),
        (151, CodigoMowaMes.MENSAJE_EXCEDE_150),
        (160, CodigoMowaMes.MENSAJE_EXCEDE_150),
        (161, CodigoMowaMes.MENSAJE_EXCEDE_160),
    ],
)
def test_bordes_del_largo(largo, codigo) -> None:
    assert speech.codigo_por_largo(largo) is codigo


# --- Previsualizacion del largo (RF-MM-19) ------------------------------


def test_el_largo_previsto_es_el_del_mensaje_mas_largo_que_se_construye() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, WHATSAPP)

    for largo in speech.previsualizar(ORIGINAL, WHATSAPP):
        mensaje = constructor.mensaje_de(largo.rango.segmento, "ZZPRUEBA SINTETICO", VENCIMIENTO)
        assert largo.largo_maximo == len(mensaje), largo.rango.segmento


def test_con_el_speech_original_solo_9_a_30_pasa_de_150() -> None:
    largos = {largo.rango.segmento: largo for largo in speech.previsualizar(ORIGINAL, WHATSAPP)}

    assert largos[Segmento.DE_9_A_30].largo_maximo == 156
    assert {s: largo.codigo for s, largo in largos.items() if largo.codigo} == {
        Segmento.DE_9_A_30: CodigoMowaMes.MENSAJE_EXCEDE_150
    }


def test_sin_whatsapp_la_previsualizacion_mide_igual_pero_no_da_ejemplo() -> None:
    con = {largo.rango.segmento: largo for largo in speech.previsualizar(ORIGINAL, WHATSAPP)}
    sin = {largo.rango.segmento: largo for largo in speech.previsualizar(ORIGINAL, None)}

    assert {s: largo.largo_maximo for s, largo in sin.items()} == {
        s: largo.largo_maximo for s, largo in con.items()
    }
    assert sin[Segmento.DE_31_A_60].ejemplo is None
    assert sin[Segmento.PREVENTIVA].ejemplo.startswith("XXXXXXXX Caja Cusco")
    assert con[Segmento.DE_31_A_60].ejemplo.endswith("https://wa.me/+51900000123")


# --- Validacion de versiones --------------------------------------------


def test_faltan_o_se_repiten_segmentos() -> None:
    partes = (*ORIGINAL[:-1], ORIGINAL[0])

    (problema,) = speech.problemas_de(DatosSpeech("incompleta", partes))

    assert problema.campo == "segmentos"
    assert "faltan: 91_a_120" in problema.detalle
    assert "repetidos: preventiva" in problema.detalle


@pytest.mark.parametrize(
    ("nombres", "siguiente"),
    [
        ([], "Speech 2"),
        (["Speech original"], "Speech 2"),
        (["Speech original", "Speech 2", "speech 7", "Campana de prueba"], "Speech 8"),
    ],
)
def test_nombre_siguiente(nombres, siguiente) -> None:
    assert nombre_siguiente(nombres) == siguiente


def test_crear_sin_nombre_asigna_el_siguiente_y_conserva_los_espacios_de_las_partes() -> None:
    servicio, _ = _servicio()
    desordenadas = tuple(reversed(ORIGINAL))

    creada = servicio.crear_speech("  ", desordenadas, basada_en_id=1)

    assert creada.datos.nombre == "Speech 2"
    assert creada.datos.partes == ORIGINAL  # ordenadas por segmento, sin recortar
    assert creada.basada_en_id == 1


def test_crear_basada_en_una_version_que_no_existe() -> None:
    servicio, repositorio = _servicio()

    with pytest.raises(SpeechNoEncontrado):
        servicio.crear_speech("Nueva", ORIGINAL, basada_en_id=99)
    assert repositorio.escrituras == 0


def test_crear_con_partes_invalidas_no_escribe() -> None:
    servicio, repositorio = _servicio()
    partes = (replace(ORIGINAL[0], parte_1=" [@titular]"), *ORIGINAL[1:])

    with pytest.raises(SpeechInvalido):
        servicio.crear_speech("Nueva", partes, basada_en_id=None)
    assert repositorio.escrituras == 0


def test_el_speech_original_no_se_modifica() -> None:
    servicio, repositorio = _servicio()

    with pytest.raises(SpeechInmutable, match="Speech original"):
        servicio.actualizar_speech(1, DatosSpeech("Otro nombre", ORIGINAL))
    assert repositorio.escrituras == 0


def test_una_version_usada_no_se_modifica_y_una_sin_usar_si() -> None:
    servicio, repositorio = _servicio()
    creada = servicio.crear_speech("Prueba", ORIGINAL, basada_en_id=None)
    corregida = (replace(ORIGINAL[0], parte_2=". Mensaje corregido."), *ORIGINAL[1:])

    actualizada = servicio.actualizar_speech(creada.id, DatosSpeech("Prueba", corregida))
    repositorio.marcar_speech_usado(creada.id)

    assert actualizada.datos.partes[0].parte_2 == ". Mensaje corregido."
    with pytest.raises(SpeechInmutable, match="ya se uso"):
        servicio.actualizar_speech(creada.id, DatosSpeech("Prueba", ORIGINAL))


def test_si_la_version_se_usa_entre_la_lectura_y_la_escritura_tambien_es_inmutable() -> None:
    servicio, repositorio = _servicio()
    creada = servicio.crear_speech("Prueba", ORIGINAL, basada_en_id=None)
    escribir = repositorio.actualizar_speech

    def usada_justo_antes(speech_id, datos):
        repositorio.marcar_speech_usado(speech_id)
        return escribir(speech_id, datos)

    repositorio.actualizar_speech = usada_justo_antes

    with pytest.raises(SpeechInmutable):
        servicio.actualizar_speech(creada.id, DatosSpeech("Prueba", ORIGINAL))


# --- Configuracion del conector -----------------------------------------


def test_guardar_configuracion_valida_el_whatsapp_con_rf02() -> None:
    servicio, repositorio = _servicio(None)

    guardada = servicio.guardar_configuracion(ConfiguracionMowaMes(3_000_000, " 900000123 "))
    sin_numero = servicio.guardar_configuracion(ConfiguracionMowaMes(3_000_000, ""))

    assert guardada.whatsapp_contacto == WHATSAPP
    assert sin_numero.whatsapp_contacto is None
    with pytest.raises(ConfiguracionInvalida):
        servicio.guardar_configuracion(ConfiguracionMowaMes(3_000_000, "51900000123"))
    with pytest.raises(ConfiguracionInvalida):
        servicio.guardar_configuracion(ConfiguracionMowaMes(0, None))
    assert repositorio.escrituras == 2


def test_la_previsualizacion_usa_el_whatsapp_configurado_si_no_se_indica_otro() -> None:
    servicio, _ = _servicio(WHATSAPP)

    numero, problemas, largos = servicio.previsualizar_speech(ORIGINAL, None)
    otro, _, _ = servicio.previsualizar_speech(ORIGINAL, "900000456")

    assert (numero, problemas, otro) == (WHATSAPP, (), "900000456")
    assert len(largos) == 6
    with pytest.raises(ConfiguracionInvalida):
        servicio.previsualizar_speech(ORIGINAL, "123")
