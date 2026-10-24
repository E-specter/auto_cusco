"""La fecha de envio de una carga y los dias de atraso ajustados a ella (RF-55).

Los dias de atraso de la sabana son los de la fecha de corte. Una carga se envia despues, y el
cliente ya acumulo los dias que pasaron: `dias_atraso_ajustados = dias_atraso + dias calendario
entre la fecha de corte y la de envio` (la formula de RF-MM-15: `segmentacion.dias_ajustados`).

Aqui vive lo que comparten la generacion de cargas y la previsualizacion del motor de texto:

- «hoy» en America/Lima, en un solo lugar y reemplazable en las pruebas;
- la eleccion de la fecha (la pedida o hoy) y su validacion contra la fecha de corte;
- las dos variables de contexto que la fecha de envio aporta a la cartera: `fecha_envio`, una
  constante de la carga (el motor la pliega al compilar, B7), y `dias_atraso_ajustados`, una por
  producto (una suma por fila, y solo si la definicion la usa).

El nucleo de segmentacion no conoce la fecha de envio: recibe los dias ya ajustados, como variable.
"""

from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.core.entities.segmentacion import VARIABLE_DIAS_AJUSTADOS, VARIABLE_DIAS_POR_DEFECTO
from app.core.entities.texto_enriquecido import TipoValor
from app.core.services.calendario.servicio import ZONA, ahora_en_lima
from app.core.services.segmentacion import dias_ajustados

FECHA_ENVIO = "fecha_envio"
DIAS_ATRASO = VARIABLE_DIAS_POR_DEFECTO  # los dias de la sabana, a la fecha de corte
DIAS_AJUSTADOS = VARIABLE_DIAS_AJUSTADOS

# Las variables que la fecha de envio suma al contexto `cartera` (no son columnas de la sabana).
VARIABLES_DE_ENVIO: dict[str, TipoValor] = {
    FECHA_ENVIO: TipoValor.FECHA,
    DIAS_AJUSTADOS: TipoValor.NUMERO,
}

Reloj = Callable[[], date]


def hoy_en_lima() -> date:
    """La fecha de hoy en America/Lima, aunque el servidor corra en otra zona (o en UTC, donde ya
    puede ser «manana»). Es la unica forma de preguntar «hoy» en una carga: nada de `date.today()`.
    """
    return ahora_en_lima().astimezone(ZONA).date()


class FechaEnvioAnterior(Exception):
    """La fecha de envio es anterior a la fecha de corte de la sabana: no hay dias que sumar."""

    def __init__(self, fecha_envio: date, fecha_corte: date) -> None:
        super().__init__(
            f"La fecha de envio ({fecha_envio}) es anterior a la fecha de corte ({fecha_corte})"
        )
        self.fecha_envio = fecha_envio
        self.fecha_corte = fecha_corte


def resolver_fecha_envio(
    fecha_corte: date, fecha_envio: date | None = None, hoy: Reloj = hoy_en_lima
) -> date:
    """La fecha de envio pedida o, sin ella, hoy en Lima; nunca anterior a la fecha de corte."""
    elegida = hoy() if fecha_envio is None else fecha_envio
    if elegida < fecha_corte:
        raise FechaEnvioAnterior(elegida, fecha_corte)
    return elegida


def _dias(valor: Any) -> int | Decimal | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, Decimal)):
        return None
    return valor


@dataclass(frozen=True)
class EnvioDeCarga:
    """La fecha de corte de la sabana y la de envio de la carga, ya validadas."""

    fecha_corte: date
    fecha_envio: date

    @classmethod
    def de(
        cls, fecha_corte: date, fecha_envio: date | None = None, hoy: Reloj = hoy_en_lima
    ) -> "EnvioDeCarga":
        return cls(fecha_corte, resolver_fecha_envio(fecha_corte, fecha_envio, hoy))

    @property
    def dias_extra(self) -> int:
        """Los dias calendario entre la fecha de corte y la de envio (0 si son la misma)."""
        return (self.fecha_envio - self.fecha_corte).days

    def constantes(self, variables: Mapping[str, Any]) -> dict[str, date]:
        """Las constantes de la carga que el contexto declara: solo `fecha_envio`."""
        return {FECHA_ENVIO: self.fecha_envio} if FECHA_ENVIO in variables else {}

    def ajustar(self, producto: Mapping[str, Any]) -> dict[str, Any]:
        """El producto con `dias_atraso_ajustados`; vacio si el producto no tiene `dias_atraso`."""
        dias = _dias(producto.get(DIAS_ATRASO))
        if dias is not None:
            dias = dias_ajustados(dias, self.fecha_corte, self.fecha_envio)
        return {**producto, DIAS_AJUSTADOS: dias}

    def ajustar_todos(self, productos: Iterable[Mapping[str, Any]]) -> Iterator[dict[str, Any]]:
        for producto in productos:
            yield self.ajustar(producto)
