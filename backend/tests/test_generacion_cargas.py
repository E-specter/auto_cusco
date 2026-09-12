"""Pruebas del caso de uso que genera la tabla de carga (RF-09, RF-15).

Usan un repositorio en memoria: lo que importa aqui es como se recorre la
seleccion, no como se consulta PostgreSQL.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.core.entities.cartera import ConsultaInvalida, Filtro, Operador, SinVersionVigente
from app.core.entities.mapeo import (
    CampoSalida,
    DefinicionCarga,
    PlantillaInvalida,
    TipoSalida,
)
from app.core.services.generacion_cargas.servicio import (
    CANTIDAD_MAXIMA,
    GeneracionCargasService,
)
from app.core.services.seleccion_cartera.servicio import LIMITE_MAXIMO, ConsultaCarteraService

FECHA = date(2026, 9, 10)

DEFINICION = DefinicionCarga(
    nombre="SMS preventiva",
    campos=(
        CampoSalida(nombre="anexo", plantilla="1010", tipo=TipoSalida.NUMERO),
        CampoSalida(nombre="numero", plantilla="51[@telefono]"),
        CampoSalida(
            nombre="deuda", plantilla="[@saldo_capital_pendiente]", tipo=TipoSalida.FINANCIERO
        ),
    ),
)


class RepositorioFalso:
    """Devuelve `total` productos sinteticos, respetando limite y desplazamiento."""

    def __init__(self, total: int = 3, vigente: bool = True) -> None:
        self.total = total
        self.vigente = vigente
        self.paginas: list[tuple[int, int]] = []

    def hay_version_vigente(self, fecha_corte):
        return self.vigente

    def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento):
        self.paginas.append((limite, desplazamiento))
        indices = range(desplazamiento, min(desplazamiento + limite, self.total))
        filas = [
            {
                "pagare": f"{i:018d}",
                "telefono": f"9{i:08d}",
                "saldo_capital_pendiente": Decimal("1500.5"),
            }
            for i in indices
        ]
        return self.total, filas

    def metricas(self, fecha_corte, filtros, indicadores):  # pragma: no cover
        raise AssertionError("la generacion no pide metricas")

    def segmentar(self, fecha_corte, campo, filtros):  # pragma: no cover
        raise AssertionError("la generacion no segmenta")


def _servicio(**kwargs):
    repositorio = RepositorioFalso(**kwargs)
    return GeneracionCargasService(ConsultaCarteraService(repositorio)), repositorio


def test_aplica_la_definicion_a_los_productos_seleccionados() -> None:
    servicio, _ = _servicio(total=2)

    resultado = servicio.generar(FECHA, DEFINICION, cantidad=2)

    assert resultado.tabla.nombre == "SMS preventiva"
    assert resultado.tabla.cabeceras == ("anexo", "numero", "deuda")
    assert resultado.tabla.filas[0] == {
        "anexo": 1010,
        "numero": "51900000000",
        "deuda": "1,500.50",
    }
    assert (resultado.generados, resultado.disponibles) == (2, 2)
    assert resultado.completa and resultado.suficiente


def test_los_filtros_llegan_a_la_consulta() -> None:
    servicio, repositorio = _servicio()
    filtro = Filtro(campo="telefono", operador=Operador.NO_VACIO)

    servicio.generar(FECHA, DEFINICION, [filtro], cantidad=1)

    assert repositorio.paginas == [(1, 0)]


def test_una_seleccion_mas_grande_que_una_pagina_se_recorre_por_partes() -> None:
    cantidad = LIMITE_MAXIMO + 10
    servicio, repositorio = _servicio(total=cantidad)

    resultado = servicio.generar(FECHA, DEFINICION, cantidad=cantidad)

    assert resultado.generados == cantidad
    assert repositorio.paginas == [(LIMITE_MAXIMO, 0), (10, LIMITE_MAXIMO)]
    # Sin repetidos: el desempate estable de la consulta lo garantiza.
    assert len({fila["numero"] for fila in resultado.tabla.filas}) == cantidad


def test_si_no_alcanzan_los_productos_se_genera_lo_que_hay_y_se_avisa() -> None:
    servicio, _ = _servicio(total=3)

    resultado = servicio.generar(FECHA, DEFINICION, cantidad=100)

    assert resultado.generados == 3
    assert resultado.disponibles == 3
    assert resultado.solicitados == 100
    assert not resultado.suficiente  # RF-08


def test_una_seleccion_vacia_no_es_un_error() -> None:
    servicio, _ = _servicio(total=0)

    resultado = servicio.generar(FECHA, DEFINICION, cantidad=10)

    assert resultado.tabla.filas == ()
    assert resultado.tabla.cabeceras == ("anexo", "numero", "deuda")
    assert not resultado.suficiente


def test_los_errores_de_un_campo_no_detienen_la_generacion() -> None:
    definicion = DefinicionCarga(
        nombre="con error",
        campos=(
            CampoSalida(nombre="pagare", plantilla="[@pagare]"),
            CampoSalida(nombre="roto", plantilla="x[@telefono]", tipo=TipoSalida.NUMERO),
        ),
    )
    servicio, _ = _servicio(total=2)

    resultado = servicio.generar(FECHA, definicion, cantidad=2)

    assert not resultado.completa
    assert [(e.fila, e.campo) for e in resultado.errores] == [(1, "roto"), (2, "roto")]
    assert resultado.generados == 2


def test_una_plantilla_invalida_se_rechaza_sin_consultar_la_base() -> None:
    definicion = DefinicionCarga(
        nombre="mala", campos=(CampoSalida(nombre="x", plantilla="[@no_existe]"),)
    )
    servicio, repositorio = _servicio()

    with pytest.raises(PlantillaInvalida):
        servicio.generar(FECHA, definicion)

    assert repositorio.paginas == []


@pytest.mark.parametrize("cantidad", [0, -1, CANTIDAD_MAXIMA + 1])
def test_la_cantidad_tiene_limites(cantidad) -> None:
    servicio, _ = _servicio()

    with pytest.raises(ConsultaInvalida, match="cantidad"):
        servicio.generar(FECHA, DEFINICION, cantidad=cantidad)


def test_sin_version_vigente_para_la_fecha() -> None:
    servicio, _ = _servicio(vigente=False)

    with pytest.raises(SinVersionVigente):
        servicio.generar(FECHA, DEFINICION, cantidad=1)
