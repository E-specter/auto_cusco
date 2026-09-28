"""Tarifa por SMS y costo de las campanas de MOWA MES (RF-MM-23, RF-MM-24).

Piezas puras. Todo monto es `Decimal`: el costo se guarda exacto (cargados por
tarifa) y el costo del mes suma valores exactos; el redondeo a dos decimales, a
la mitad hacia arriba, es solo de presentacion y lo hace quien muestra el monto.
"""

import re
from decimal import Decimal

from app.core.entities.mowa_mes import DECIMALES_TARIFA
from app.core.entities.mowa_mes_costo import CostoReal, EstadoCosto, TarifaInvalida

_ENTEROS_MAXIMOS = 8  # NUMERIC(12, 4)
_CUATRO_DECIMALES = Decimal(1).scaleb(-DECIMALES_TARIFA)
_TARIFA_EN_TEXTO = re.compile(rf"\d{{1,{_ENTEROS_MAXIMOS}}}(\.\d{{1,{DECIMALES_TARIFA}}})?")

MENSAJE_TARIFA = (
    f"La tarifa debe ser un numero decimal mayor o igual a 0, con hasta {DECIMALES_TARIFA} "
    "decimales (por ejemplo 0.02)"
)


def validar_tarifa(tarifa: Decimal) -> Decimal:
    """La tarifa tal cual, o TarifaInvalida si no es finita, negativa o pasa de 4 decimales."""
    if not isinstance(tarifa, Decimal) or not tarifa.is_finite() or tarifa < 0:
        raise TarifaInvalida(MENSAJE_TARIFA)
    if tarifa != tarifa.quantize(_CUATRO_DECIMALES) or tarifa >= Decimal(10) ** _ENTEROS_MAXIMOS:
        raise TarifaInvalida(MENSAJE_TARIFA)
    return tarifa


def tarifa_desde_texto(texto: str) -> Decimal:
    """Lee la tarifa que envia el cliente: texto decimal plano, sin exponente ni signo."""
    if not _TARIFA_EN_TEXTO.fullmatch(texto.strip()):
        raise TarifaInvalida(MENSAJE_TARIFA)
    return validar_tarifa(Decimal(texto.strip()))


def costo(cantidad: int, tarifa: Decimal) -> Decimal:
    """SMS por tarifa, exacto: un entero por una tarifa de hasta 4 decimales no se redondea."""
    return Decimal(cantidad) * tarifa


def costo_real(tarifa: Decimal | None, hay_reporte: bool, enviados: int) -> CostoReal:
    """Enviados (E-1) por la tarifa congelada de la campana (RF-MM-24, D-3).

    Sin tarifa guardada no hay costo, con o sin reporte; con tarifa y sin reporte
    importado esta pendiente. Ninguno de los dos es cero: el frontend los distingue.
    """
    if tarifa is None:
        return CostoReal(EstadoCosto.NO_DISPONIBLE, None)
    if not hay_reporte:
        return CostoReal(EstadoCosto.PENDIENTE, None)
    return CostoReal(EstadoCosto.CALCULADO, costo(enviados, tarifa))


def texto_decimal(valor: Decimal) -> str:
    """Notacion plana, nunca exponente, con al menos 4 decimales: asi viaja en el contrato."""
    if valor.as_tuple().exponent > -DECIMALES_TARIFA:
        valor = valor.quantize(_CUATRO_DECIMALES)
    return format(valor, "f")
