"""Pruebas del caso de uso de consulta de cartera, con un repositorio en memoria."""

from datetime import date
from decimal import Decimal

import pytest

from app.core.entities.cartera import (
    ConsultaInvalida,
    Filtro,
    Funcion,
    Grupo,
    Indicador,
    MetricasCartera,
    Operador,
    Orden,
    SinVersionVigente,
)
from app.core.services.seleccion_cartera.servicio import LIMITE_MAXIMO, ConsultaCarteraService

FECHA = date(2026, 9, 10)


class RepositorioFalso:
    def __init__(self, total: int = 3, vigente: bool = True) -> None:
        self.total = total
        self.vigente = vigente
        self.consultas: list[tuple] = []

    def hay_version_vigente(self, fecha_corte):
        return self.vigente

    def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento):
        self.consultas.append((fecha_corte, filtros, orden, limite, desplazamiento))
        filas = [{"pagare": f"{i:018d}"} for i in range(min(limite, self.total))]
        return self.total, filas

    def metricas(self, fecha_corte, filtros, indicadores):
        self.consultas.append((fecha_corte, filtros, indicadores))
        return MetricasCartera(
            cuentas=self.total,
            capital_total=Decimal("1000.00"),
            cuota_minima=Decimal("10.00"),
            cuota_maxima=Decimal("500.00"),
            cuentas_por_segmento={"1. Preventiva": self.total},
            adicionales={i.nombre: Decimal("1") for i in indicadores},
        )

    def segmentar(self, fecha_corte, campo, filtros):
        self.consultas.append((fecha_corte, campo, filtros))
        return [Grupo(valor="CUSCO SUR", cuentas=2, capital=Decimal("800.00"))]


def _servicio(**kwargs):
    repositorio = RepositorioFalso(**kwargs)
    return ConsultaCarteraService(repositorio), repositorio


def test_consultar_pasa_los_filtros_al_repositorio() -> None:
    servicio, repositorio = _servicio()
    filtro = Filtro("region", Operador.IGUAL, ("CUSCO SUR",))

    pagina = servicio.consultar(FECHA, [filtro], Orden("dias_atraso", descendente=True), limite=2)

    assert [f["pagare"] for f in pagina.filas] == ["0" * 17 + "0", "0" * 17 + "1"]
    assert repositorio.consultas == [(FECHA, (filtro,), Orden("dias_atraso", True), 2, 0)]


def test_top_n_avisa_cuando_no_alcanzan_los_productos() -> None:
    servicio, _ = _servicio(total=3)

    suficiente = servicio.consultar(FECHA, limite=3)
    insuficiente = servicio.consultar(FECHA, limite=10)

    assert suficiente.suficiente
    assert not insuficiente.suficiente
    assert insuficiente.total == 3


def test_una_fecha_sin_version_vigente_no_tiene_cartera() -> None:
    servicio, _ = _servicio(vigente=False)

    with pytest.raises(SinVersionVigente):
        servicio.consultar(FECHA)


def test_la_consulta_se_valida_antes_de_llegar_al_repositorio() -> None:
    servicio, repositorio = _servicio()

    with pytest.raises(ConsultaInvalida):
        servicio.consultar(FECHA, [Filtro("inventado", Operador.IGUAL, ("x",))])
    with pytest.raises(ConsultaInvalida):
        servicio.consultar(FECHA, orden=Orden("inventado"))
    with pytest.raises(ConsultaInvalida):
        servicio.consultar(FECHA, limite=0)
    with pytest.raises(ConsultaInvalida):
        servicio.consultar(FECHA, limite=LIMITE_MAXIMO + 1)
    with pytest.raises(ConsultaInvalida):
        servicio.consultar(FECHA, desplazamiento=-1)
    assert repositorio.consultas == []


def test_metricas_con_indicadores_adicionales() -> None:
    servicio, _ = _servicio()
    indicador = Indicador("capital promedio", Funcion.PROMEDIO, "saldo_capital_pendiente")

    metricas = servicio.metricas(FECHA, indicadores=[indicador])

    assert metricas.cuentas == 3
    assert metricas.capital_total == Decimal("1000.00")
    assert metricas.cuentas_por_segmento == {"1. Preventiva": 3}
    assert metricas.adicionales == {"capital promedio": Decimal("1")}


def test_dos_indicadores_no_pueden_llamarse_igual() -> None:
    servicio, _ = _servicio()
    repetidos = [
        Indicador("total", Funcion.CONTEO),
        Indicador("total", Funcion.SUMA, "monto_cuota"),
    ]

    with pytest.raises(ConsultaInvalida):
        servicio.metricas(FECHA, indicadores=repetidos)


def test_segmentar_por_un_atributo() -> None:
    servicio, _ = _servicio()

    segmentacion = servicio.segmentar(FECHA, "region")

    assert segmentacion.campo == "region"
    assert segmentacion.grupos[0].cuentas == 2
    with pytest.raises(ConsultaInvalida):
        servicio.segmentar(FECHA, "campo_inventado")


def test_los_campos_disponibles_traen_tipo_y_operadores() -> None:
    servicio, _ = _servicio()

    catalogo = servicio.campos_disponibles()

    assert catalogo["segmento_financiero"]["tipo"] == "texto"
    assert "igual" in catalogo["segmento_financiero"]["operadores"]
