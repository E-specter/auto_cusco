"""La fecha de envio de una carga y los dias de atraso ajustados a ella (RF-55, T-MTE-B13).

El reloj se inyecta siempre: ninguna prueba depende de la hora de la maquina ni de su zona.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.core.entities.cartera import PaginaCartera
from app.core.entities.mapeo import (
    CampoSalida,
    DefinicionCarga,
    TipoSalida,
    VarianteCampo,
)
from app.core.entities.segmentacion import (
    CriterioCalculado,
    PoliticaSinSegmento,
    Segmentacion,
)
from app.core.services import fecha_envio as modulo
from app.core.services.contextos_texto import RegistroContextos, contexto_cartera
from app.core.services.fecha_envio import (
    EnvioDeCarga,
    FechaEnvioAnterior,
    hoy_en_lima,
    resolver_fecha_envio,
)
from app.core.services.generacion_cargas.servicio import GeneracionCargasService
from app.core.services.plataformas.mowa_mes import segmentos
from app.core.services.plataformas.mowa_mes.contexto_texto import contexto_speech
from app.core.services.previsualizar_texto import (
    MuestraEjemplo,
    MuestraEjemplosPorSegmento,
    MuestraPrimerosDeSeleccion,
    MuestraProductoReal,
    PrevisualizacionTextoService,
)
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService

CORTE = date(2026, 9, 10)
HOY = date(2026, 9, 15)  # cinco dias despues de la fecha de corte


def _reloj(fecha: date):
    return lambda: fecha


# --- «Hoy» en Lima ---------------------------------------------------------------------------


def test_hoy_en_lima_es_la_fecha_de_lima_aunque_en_utc_ya_sea_manana(monkeypatch) -> None:
    # 03:00 UTC del 22 son las 22:00 del 21 en Lima (UTC-5, sin horario de verano).
    monkeypatch.setattr(modulo, "ahora_en_lima", lambda: datetime(2026, 10, 22, 3, 0, tzinfo=UTC))

    assert hoy_en_lima() == date(2026, 10, 21)


def test_hoy_en_lima_pasa_de_dia_a_las_cero_horas_de_lima(monkeypatch) -> None:
    monkeypatch.setattr(modulo, "ahora_en_lima", lambda: datetime(2026, 10, 22, 4, 59, tzinfo=UTC))
    antes = hoy_en_lima()
    monkeypatch.setattr(modulo, "ahora_en_lima", lambda: datetime(2026, 10, 22, 5, 0, tzinfo=UTC))

    assert (antes, hoy_en_lima()) == (date(2026, 10, 21), date(2026, 10, 22))


# --- La fecha y su validacion ----------------------------------------------------------------


def test_sin_fecha_de_envio_es_hoy() -> None:
    assert resolver_fecha_envio(CORTE, None, _reloj(HOY)) == HOY


def test_la_fecha_pedida_manda_sobre_hoy() -> None:
    assert resolver_fecha_envio(CORTE, date(2026, 9, 20), _reloj(HOY)) == date(2026, 9, 20)


def test_una_fecha_igual_a_la_de_corte_es_valida() -> None:
    assert resolver_fecha_envio(CORTE, CORTE, _reloj(HOY)) == CORTE


def test_una_fecha_anterior_a_la_de_corte_se_rechaza_con_las_dos_fechas() -> None:
    with pytest.raises(FechaEnvioAnterior) as error:
        resolver_fecha_envio(CORTE, date(2026, 9, 9), _reloj(HOY))

    assert (error.value.fecha_envio, error.value.fecha_corte) == (date(2026, 9, 9), CORTE)
    assert "2026-09-09" in str(error.value) and "2026-09-10" in str(error.value)


def test_si_hoy_es_anterior_a_la_fecha_de_corte_tambien_se_rechaza() -> None:
    with pytest.raises(FechaEnvioAnterior) as error:
        resolver_fecha_envio(date(2026, 9, 30), None, _reloj(HOY))

    assert error.value.fecha_envio == HOY


# --- Los dias ajustados ----------------------------------------------------------------------


def test_los_dias_ajustados_suman_los_dias_calendario_entre_corte_y_envio() -> None:
    envio = EnvioDeCarga.de(CORTE, HOY)

    assert envio.dias_extra == 5
    assert envio.ajustar({"dias_atraso": 20})["dias_atraso_ajustados"] == 25
    assert envio.ajustar({"dias_atraso": -3})["dias_atraso_ajustados"] == 2


def test_con_la_fecha_de_corte_los_dias_extra_son_cero() -> None:
    envio = EnvioDeCarga.de(CORTE, CORTE)

    assert envio.dias_extra == 0
    assert envio.ajustar({"dias_atraso": 20})["dias_atraso_ajustados"] == 20


def test_los_dias_cuentan_por_calendario_aunque_cambie_el_mes_o_el_anio() -> None:
    envio = EnvioDeCarga(date(2026, 12, 30), date(2027, 1, 2))

    assert envio.ajustar({"dias_atraso": 1})["dias_atraso_ajustados"] == 4


@pytest.mark.parametrize("dias", [None, "12", 12.5, True])
def test_sin_dias_de_atraso_validos_los_ajustados_quedan_vacios(dias) -> None:
    producto = {"pagare": "P", "dias_atraso": dias}

    assert EnvioDeCarga.de(CORTE, HOY).ajustar(producto)["dias_atraso_ajustados"] is None
    assert EnvioDeCarga.de(CORTE, HOY).ajustar({"pagare": "P"})["dias_atraso_ajustados"] is None


def test_un_decimal_de_dias_conserva_su_tipo() -> None:
    ajustado = EnvioDeCarga.de(CORTE, HOY).ajustar({"dias_atraso": Decimal("20")})

    assert ajustado["dias_atraso_ajustados"] == Decimal("25")


def test_ajustar_no_modifica_el_producto_original() -> None:
    producto = {"dias_atraso": 20}

    EnvioDeCarga.de(CORTE, HOY).ajustar(producto)

    assert producto == {"dias_atraso": 20}


# --- La generacion de cargas -----------------------------------------------------------------


class RepositorioFalso:
    """Tres productos sinteticos con 0, 5 y 28 dias de atraso a la fecha de corte; el cuarto no
    trae dias."""

    DIAS = (0, 5, 28, None)

    def __init__(self) -> None:
        self.paginas: list[tuple[int, int]] = []

    def hay_version_vigente(self, fecha_corte):
        return True

    def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento):
        self.paginas.append((limite, desplazamiento))
        filas = [
            {"pagare": f"{i:018d}", "dias_atraso": dias}
            for i, dias in enumerate(self.DIAS)
            if desplazamiento <= i < desplazamiento + limite
        ]
        return len(self.DIAS), filas


def _servicio(hoy: date = HOY):
    repositorio = RepositorioFalso()
    return GeneracionCargasService(ConsultaCarteraService(repositorio), _reloj(hoy)), repositorio


def _segmentada(variable_dias: str, **campos) -> DefinicionCarga:
    return DefinicionCarga(
        nombre="Por segmento",
        campos=(
            CampoSalida(nombre="pagare", plantilla="[@pagare]"),
            CampoSalida(
                nombre="segmento",
                plantilla="otro",
                variantes=tuple(
                    VarianteCampo(clave, plantilla=clave)
                    for clave in ("preventiva", "1_a_8", "9_a_30", "31_a_60")
                ),
            ),
            *campos.get("extra", ()),
        ),
        segmentacion=Segmentacion(
            CriterioCalculado(variable_dias=variable_dias), PoliticaSinSegmento.EXCLUIR
        ),
    )


def _segmentos(resultado) -> list[str]:
    return [fila["segmento"] for fila in resultado.tabla.filas]


def test_una_definicion_nueva_segmenta_por_los_dias_ajustados() -> None:
    servicio, _ = _servicio()
    definicion = _segmentada("dias_atraso_ajustados")

    resultado = servicio.generar(CORTE, definicion, cantidad=3, fecha_envio=HOY)

    # 0+5, 5+5 y 28+5 dias: de «preventiva», «1 a 8» y «9 a 30» a «1 a 8», «9 a 30» y «31 a 60»
    assert _segmentos(resultado) == ["1_a_8", "9_a_30", "31_a_60"]


def test_con_la_fecha_de_corte_los_ajustados_no_cambian_el_segmento() -> None:
    servicio, _ = _servicio()

    resultado = servicio.generar(
        CORTE, _segmentada("dias_atraso_ajustados"), cantidad=3, fecha_envio=CORTE
    )

    assert _segmentos(resultado) == ["preventiva", "1_a_8", "9_a_30"]


def test_una_definicion_vieja_con_dias_atraso_da_lo_mismo_con_cualquier_fecha_de_envio() -> None:
    servicio, _ = _servicio()
    vieja = _segmentada("dias_atraso")

    en_el_corte = servicio.generar(CORTE, vieja, cantidad=3, fecha_envio=CORTE)
    sesenta_dias_despues = servicio.generar(CORTE, vieja, cantidad=3, fecha_envio=date(2026, 11, 9))

    assert _segmentos(en_el_corte) == ["preventiva", "1_a_8", "9_a_30"]
    assert en_el_corte.tabla.filas == sesenta_dias_despues.tabla.filas
    assert en_el_corte.exclusiones == sesenta_dias_despues.exclusiones


def test_sin_segmentacion_calculada_el_resultado_no_depende_de_la_fecha_de_envio() -> None:
    # Paridad con RF-54: lo que funcionaba sin fecha de envio sale igual con cualquiera.
    servicio, _ = _servicio()
    definicion = DefinicionCarga(
        nombre="Plana",
        campos=(
            CampoSalida(nombre="pagare", plantilla="[@pagare]"),
            CampoSalida(nombre="dias", plantilla="[@dias_atraso]", tipo=TipoSalida.NUMERO),
        ),
    )

    tablas = [
        servicio.generar(CORTE, definicion, cantidad=4, fecha_envio=envio).tabla.filas
        for envio in (CORTE, HOY, date(2027, 3, 1))
    ]

    assert tablas[0] == tablas[1] == tablas[2]


def test_las_variables_de_envio_se_usan_como_cualquier_otra() -> None:
    servicio, _ = _servicio()
    definicion = DefinicionCarga(
        nombre="Con variables",
        campos=(
            CampoSalida(
                nombre="ajustados", plantilla="[@dias_atraso_ajustados]", tipo=TipoSalida.NUMERO
            ),
            CampoSalida(nombre="envio", plantilla="[@fecha_envio]", tipo=TipoSalida.FECHA),
            CampoSalida(
                nombre="texto", plantilla='hasta el [@fecha_envio | formato_fecha("dd/mm/aaaa")]'
            ),
        ),
    )

    resultado = servicio.generar(CORTE, definicion, cantidad=4, fecha_envio=HOY)

    assert resultado.completa, resultado.errores
    assert [fila["ajustados"] for fila in resultado.tabla.filas] == [5, 10, 33, None]
    assert {fila["envio"] for fila in resultado.tabla.filas} == {HOY}
    assert {fila["texto"] for fila in resultado.tabla.filas} == {"hasta el 15/09/2026"}


def test_un_producto_sin_dias_se_excluye_diciendo_que_falta_la_variable_ajustada() -> None:
    servicio, _ = _servicio()

    resultado = servicio.generar(
        CORTE, _segmentada("dias_atraso_ajustados"), cantidad=4, fecha_envio=HOY
    )

    [exclusion] = resultado.exclusiones
    assert exclusion.pagare == f"{3:018d}"
    assert "no tiene dias en 'dias_atraso_ajustados'" in exclusion.detalle


def test_sin_fecha_de_envio_la_carga_usa_hoy_y_lo_informa() -> None:
    servicio, _ = _servicio(hoy=HOY)

    resultado = servicio.generar(CORTE, _segmentada("dias_atraso_ajustados"), cantidad=3)

    assert resultado.fecha_envio == HOY
    assert _segmentos(resultado) == ["1_a_8", "9_a_30", "31_a_60"]


def test_la_fecha_pedida_queda_en_el_resultado() -> None:
    servicio, _ = _servicio(hoy=HOY)

    assert (
        servicio.generar(CORTE, _segmentada("dias_atraso"), fecha_envio=CORTE).fecha_envio == CORTE
    )


def test_una_fecha_anterior_se_rechaza_antes_de_consultar_la_cartera() -> None:
    servicio, repositorio = _servicio()

    with pytest.raises(FechaEnvioAnterior) as error:
        servicio.generar(CORTE, _segmentada("dias_atraso_ajustados"), fecha_envio=date(2026, 9, 1))

    assert (error.value.fecha_envio, error.value.fecha_corte) == (date(2026, 9, 1), CORTE)
    assert repositorio.paginas == []


def test_los_dias_se_ajustan_solo_si_la_definicion_los_usa(monkeypatch) -> None:
    # Rendimiento: el ajuste es una suma por producto, y no se paga si nadie la lee.
    llamadas: list[int] = []
    original = EnvioDeCarga.ajustar

    def contar(self, producto):
        llamadas.append(1)
        return original(self, producto)

    monkeypatch.setattr(EnvioDeCarga, "ajustar", contar)
    servicio, _ = _servicio()
    plana = DefinicionCarga("Plana", (CampoSalida(nombre="pagare", plantilla="[@pagare]"),))

    servicio.generar(CORTE, plana, cantidad=4, fecha_envio=HOY)
    servicio.generar(CORTE, _segmentada("dias_atraso"), cantidad=4, fecha_envio=HOY)
    assert llamadas == []

    servicio.generar(CORTE, _segmentada("dias_atraso_ajustados"), cantidad=4, fecha_envio=HOY)
    assert len(llamadas) == 4


# --- La previsualizacion del motor de texto --------------------------------------------------


class _Cartera:
    def __init__(self) -> None:
        self.llamadas = 0

    def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento=0):
        self.llamadas += 1
        fila = {
            "pagare": "P1",
            "titular": "UNO",
            "dias_atraso": 33,
            "fecha_vencimiento_cuota": date(2026, 9, 1),
        }
        return PaginaCartera(total=1, filas=(fila,), limite=limite)


def _previsualizador(cartera=None, hoy: date = HOY) -> PrevisualizacionTextoService:
    contextos = RegistroContextos([contexto_cartera(), contexto_speech()])
    return PrevisualizacionTextoService(contextos, cartera or _Cartera(), hoy=_reloj(hoy))


def _nodos(*nombres: str) -> dict:
    nodos: list[dict] = []
    for nombre in nombres:
        nodos += [{"tipo": "variable", "nombre": nombre}, {"tipo": "texto", "valor": " "}]
    return {"nodos": nodos[:-1]}


def test_el_speech_se_previsualiza_con_los_dias_ajustados_a_hoy_en_lima() -> None:
    previa = _previsualizador().previsualizar(
        "mowa_mes.speech",
        MuestraProductoReal(CORTE, "P1"),
        expresion=_nodos("titular", "dias_atraso_ajustados"),
    )

    assert previa.filas[0].columnas[0].texto == "UNO 38"  # 33 + 5 dias
    assert previa.fecha_envio == HOY


def test_el_speech_con_una_fecha_pedida_usa_esa_fecha() -> None:
    previa = _previsualizador().previsualizar(
        "mowa_mes.speech",
        MuestraPrimerosDeSeleccion(CORTE, fecha_envio=date(2026, 9, 11)),
        expresion=_nodos("dias_atraso_ajustados"),
    )

    assert previa.filas[0].columnas[0].texto == "34"
    assert previa.fecha_envio == date(2026, 9, 11)


def test_la_cartera_se_previsualiza_con_fecha_envio_y_dias_ajustados() -> None:
    previa = _previsualizador().previsualizar(
        "cartera",
        MuestraProductoReal(CORTE, "P1"),
        expresion=_nodos("dias_atraso", "dias_atraso_ajustados", "fecha_envio"),
    )

    assert previa.filas[0].columnas[0].texto == "33 38 2026-09-15"


def test_la_cartera_segmenta_una_definicion_nueva_por_los_dias_ajustados() -> None:
    definicion = {
        "columnas": [{"nombre": "a", "orden": 0, "expresion": _nodos("dias_atraso_ajustados")}],
        "segmentacion": {"criterio": {"tipo": "calculado"}},
    }

    previa = _previsualizador().previsualizar(
        "cartera", MuestraProductoReal(CORTE, "P1"), definicion=definicion
    )

    # 33 dias de atraso: «31 a 60» con o sin ajuste; con 5 dias de envio son 38: sigue en «31 a 60»
    assert previa.filas[0].segmento == "31_a_60"
    envio_lejano = _previsualizador().previsualizar(
        "cartera", MuestraProductoReal(CORTE, "P1", date(2026, 11, 9)), definicion=definicion
    )
    assert envio_lejano.filas[0].segmento == "91_a_120"  # 33 + 60 = 93


def test_una_definicion_con_dias_atraso_guardada_no_se_mueve_con_la_fecha_de_envio() -> None:
    definicion = {
        "columnas": [{"nombre": "a", "orden": 0, "expresion": _nodos("dias_atraso")}],
        "segmentacion": {"criterio": {"tipo": "calculado", "variable_dias": "dias_atraso"}},
    }

    segmentos = {
        _previsualizador()
        .previsualizar("cartera", MuestraProductoReal(CORTE, "P1", envio), definicion=definicion)
        .filas[0]
        .segmento
        for envio in (CORTE, HOY, date(2026, 11, 9))
    }

    assert segmentos == {"31_a_60"}


def test_una_fecha_anterior_se_rechaza_sin_tocar_la_cartera() -> None:
    cartera = _Cartera()

    with pytest.raises(FechaEnvioAnterior) as error:
        _previsualizador(cartera).previsualizar(
            "cartera",
            MuestraProductoReal(CORTE, "P1", date(2026, 9, 9)),
            expresion=_nodos("titular"),
        )

    assert (error.value.fecha_envio, error.value.fecha_corte) == (date(2026, 9, 9), CORTE)
    assert cartera.llamadas == 0


@pytest.mark.parametrize("muestra", [MuestraEjemplo(), MuestraEjemplosPorSegmento()])
def test_las_muestras_de_ejemplo_no_tienen_fecha_de_envio(muestra) -> None:
    previa = _previsualizador().previsualizar(
        "cartera", muestra, expresion=_nodos("dias_atraso_ajustados", "fecha_envio")
    )

    assert previa.fecha_envio is None
    assert previa.filas[0].columnas[0].texto.endswith("2026-10-05")  # el de ejemplo del contexto


def test_los_ejemplos_por_segmento_muestran_los_mismos_dias_en_las_dos_variables() -> None:
    definicion = {
        "columnas": [
            {"nombre": "a", "orden": 0, "expresion": _nodos("dias_atraso", "dias_atraso_ajustados")}
        ],
        "segmentacion": {"criterio": {"tipo": "calculado"}},
    }

    previa = _previsualizador().previsualizar(
        "cartera", MuestraEjemplosPorSegmento(), definicion=definicion
    )

    textos = [f.columnas[0].texto.split() for f in previa.filas]
    assert all(dias == ajustados for dias, ajustados in textos)
    assert [f.segmento for f in previa.filas][:2] == ["preventiva", "1_a_8"]


def test_una_expresion_con_problemas_tambien_informa_la_fecha_usada() -> None:
    previa = _previsualizador().previsualizar(
        "cartera",
        MuestraProductoReal(CORTE, "P1"),
        expresion={"nodos": [{"tipo": "variable", "nombre": "no_existe"}]},
    )

    assert previa.problemas and previa.fecha_envio == HOY


# --- Paridad con la campana de MOWA MES (RF-MM-15) -------------------------------------------


class _CarteraDe:
    """Un producto sintetico por cada valor de dias de atraso."""

    def __init__(self, *dias: int | None) -> None:
        self.dias = dias

    def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento=0):
        filas = tuple(
            {
                "pagare": f"P{i}",
                "titular": "UNO",
                "dias_atraso": dias,
                "fecha_vencimiento_cuota": date(2026, 9, 1),
            }
            for i, dias in enumerate(self.dias)
        )
        return PaginaCartera(total=len(filas), filas=filas[:limite], limite=limite)


SEGMENTACION_DEL_SPEECH = {
    "columnas": [{"nombre": "a", "orden": 0, "expresion": _nodos("dias_atraso_ajustados")}],
    "segmentacion": {"criterio": {"tipo": "calculado"}},
}
CORTE_SPEECH = date(2026, 9, 5)  # diez dias antes de HOY


def _segmentos_de_la_previa(muestra, *dias) -> list[str | None]:
    previa = _previsualizador(_CarteraDe(*dias)).previsualizar(
        "mowa_mes.speech", muestra, definicion=SEGMENTACION_DEL_SPEECH
    )
    return [fila.segmento for fila in previa.filas]


def _segmento_de_la_campana(dias, corte: date, envio: date) -> str | None:
    rango = segmentos.rango_de(segmentos.dias_ajustados(dias, corte, envio))
    return None if rango is None else rango.segmento.value


def test_el_speech_cae_en_el_segmento_de_los_dias_ajustados_y_no_en_el_de_corte() -> None:
    # 25 dias a la fecha de corte son «9 a 30»; diez dias despues son 35: «31 a 60».
    [segmento] = _segmentos_de_la_previa(MuestraProductoReal(CORTE_SPEECH, "P0"), 25)

    assert segmento == "31_a_60"


def test_la_seleccion_del_speech_tambien_cae_en_el_segmento_ajustado() -> None:
    segmentos_ = _segmentos_de_la_previa(
        MuestraPrimerosDeSeleccion(CORTE_SPEECH, cantidad=3), 25, 0, 112
    )

    assert segmentos_ == ["31_a_60", "9_a_30", None]  # 35, 10 y 122 dias: sin speech arriba de 120


@pytest.mark.parametrize("envio", [date(2026, 9, 5), HOY, date(2026, 10, 25), date(2027, 1, 1)])
def test_la_previsualizacion_da_el_mismo_segmento_que_la_campana(envio) -> None:
    dias = [-3, 0, 1, 8, 9, 30, 31, 60, 61, 90, 91, 110, 120, 121, 300]

    previa = _segmentos_de_la_previa(
        MuestraPrimerosDeSeleccion(CORTE_SPEECH, fecha_envio=envio, cantidad=5), *dias[:5]
    )
    previa += _segmentos_de_la_previa(
        MuestraPrimerosDeSeleccion(CORTE_SPEECH, fecha_envio=envio, cantidad=5), *dias[5:10]
    )
    previa += _segmentos_de_la_previa(
        MuestraPrimerosDeSeleccion(CORTE_SPEECH, fecha_envio=envio, cantidad=5), *dias[10:]
    )

    assert previa == [_segmento_de_la_campana(d, CORTE_SPEECH, envio) for d in dias]


def test_sin_dias_de_atraso_el_speech_no_tiene_segmento_como_en_la_campana() -> None:
    [segmento] = _segmentos_de_la_previa(MuestraProductoReal(CORTE_SPEECH, "P0"), None)

    assert segmento is None
