"""El analisis y las asignaciones del mapeador como JSON, y el arranque de la aplicacion (B3a)."""

import asyncio
import json

import pytest

from app import main
from app.core.entities.mapeador import Asignacion, EstadoEncabezado, OrigenAsignacion
from app.core.services.ingesta_sabana.catalogo import CATALOGO_SABANA
from app.core.services.mapeador.analisis import analizar
from app.core.services.mapeador.serializacion import (
    analisis_a_dict,
    analisis_desde_dict,
    asignaciones_a_dict,
    asignaciones_desde_dict,
    recordados_de,
)

O = OrigenAsignacion  # noqa: E741
CABECERAS = ["Pagare", "Zona", "Pagare", "Telefon", None, "Titular"]
ANALISIS = analizar(
    CABECERAS, [["1", "x", "2", "9", "", "ab"]], CATALOGO_SABANA, {("zona", 1): None}
)


def test_el_analisis_sobrevive_a_json() -> None:
    texto = json.dumps(analisis_a_dict(ANALISIS))

    vuelto = analisis_desde_dict(json.loads(texto))

    assert vuelto.columnas == ANALISIS.columnas
    assert vuelto.campos == ANALISIS.campos
    assert vuelto.catalogo_id == ANALISIS.catalogo_id == "sabana_vencida"


def test_el_analisis_guardado_no_trae_los_problemas_que_se_recalculan() -> None:
    assert "problemas_iniciales" not in analisis_a_dict(ANALISIS)
    assert analisis_desde_dict(analisis_a_dict(ANALISIS)).problemas_iniciales == ()


def test_el_analisis_guardado_conserva_estados_y_similitudes() -> None:
    parecido = [c for c in ANALISIS.columnas if c.estado is EstadoEncabezado.PARECIDO]
    assert parecido and parecido[0].similitud is not None  # «Telefon» se parece a telefono

    dicho = analisis_a_dict(ANALISIS)

    assert [c["estado"] for c in dicho["columnas"]] == [c.estado.value for c in ANALISIS.columnas]
    assert all(isinstance(c["estado"], str) for c in dicho["columnas"])


def _asignaciones() -> list[Asignacion]:
    return [
        Asignacion(c.indice, c.sugerido, O.COINCIDE if c.sugerido else O.MANUAL)
        for c in ANALISIS.columnas
    ]


def test_las_asignaciones_se_guardan_con_el_encabezado_normalizado_de_cada_columna() -> None:
    guardadas = asignaciones_a_dict(_asignaciones(), ANALISIS)

    assert guardadas[0] == {
        "indice": 0,
        "encabezado_normalizado": "pagare",
        "campo": "pagare",
        "origen": "coincide",
    }
    assert set(guardadas[0]) == {"indice", "encabezado_normalizado", "campo", "origen"}
    assert [a["indice"] for a in guardadas] == [0, 1, 2, 3, 5]  # el 4 era un encabezado vacio
    assert guardadas[1]["campo"] is None and guardadas[1]["origen"] == "manual"
    json.dumps(guardadas)


def test_las_asignaciones_guardadas_vuelven_como_asignaciones() -> None:
    guardadas = asignaciones_a_dict(_asignaciones(), ANALISIS)

    assert asignaciones_desde_dict(guardadas) == tuple(_asignaciones())


def test_lo_que_se_recuerda_es_encabezado_y_ocurrencia_no_solo_encabezado() -> None:
    recordados = recordados_de(_asignaciones(), ANALISIS)

    assert recordados[("pagare", 1)] == "pagare"
    assert recordados[("pagare", 2)] == "pagare_duplicado"  # M-1: los dos «Pagare»
    assert recordados[("zona", 1)] is None
    assert len(recordados) == 5


# --- El arranque ---------------------------------------------------------------------------


class _Servicio:
    def __init__(self, error: Exception | None = None, borrados: int = 0) -> None:
        self.llamadas = 0
        self.error = error
        self.borrados = borrados

    def recuperar_interrumpidas(self):
        self.llamadas += 1
        return []

    def descartar_vencidos(self) -> int:
        self.llamadas += 1
        if self.error:
            raise self.error
        return self.borrados


def _arrancar() -> None:
    async def correr():
        async with main.lifespan(main.app):
            pass

    asyncio.run(correr())


def test_al_arrancar_se_borran_los_borradores_vencidos_junto_a_las_interrumpidas(
    monkeypatch,
) -> None:
    ingesta, mapeador = _Servicio(), _Servicio(borrados=2)
    monkeypatch.setattr(main, "crear_servicio_ingesta", lambda: ingesta)
    monkeypatch.setattr(main, "crear_servicio_mapeador", lambda: mapeador)

    _arrancar()

    assert (ingesta.llamadas, mapeador.llamadas) == (1, 1)


def test_si_no_se_puede_limpiar_la_aplicacion_arranca_igual(monkeypatch) -> None:
    ingesta = _Servicio()
    mapeador = _Servicio(error=RuntimeError("sin base"))
    monkeypatch.setattr(main, "crear_servicio_ingesta", lambda: ingesta)
    monkeypatch.setattr(main, "crear_servicio_mapeador", lambda: mapeador)

    _arrancar()  # no lanza

    assert mapeador.llamadas == 1


def test_si_falla_la_ingesta_igual_se_intenta_la_limpieza_de_borradores(monkeypatch) -> None:
    def sin_base():
        raise RuntimeError("sin base")

    mapeador = _Servicio()
    monkeypatch.setattr(main, "crear_servicio_ingesta", sin_base)
    monkeypatch.setattr(main, "crear_servicio_mapeador", lambda: mapeador)

    _arrancar()

    assert mapeador.llamadas == 1


@pytest.mark.parametrize("nombre", ["crear_servicio_ingesta", "crear_servicio_mapeador"])
def test_el_arranque_usa_las_funciones_de_composicion(nombre) -> None:
    assert callable(getattr(main, nombre))
