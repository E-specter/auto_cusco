"""Los valores de los campos adicionales (RF-64), normalizados a su tipo, para `adicionales`.

Un valor sale siempre como texto: el decimal en su forma canonica (sin ceros de mas ni notacion
cientifica) y la fecha en ISO, que es lo que el repositorio de la cartera convierte con `CAST`. Lo
que no se puede convertir queda vacio y avisa con `valor_no_convertible`: nunca bloquea la fila.
"""

from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.entities.sabana import Aviso, Severidad, TipoCampo
from app.core.services.ingesta_sabana import reglas
from app.core.services.ingesta_sabana.reglas import Resultado

# Mas digitos o mas exponente que esto no es un dato de cobranza: se rechaza antes de escribir un
# texto enorme (`1E+999999` es un decimal valido).
_DIGITOS_MAXIMOS = 30
_EXPONENTE_MAXIMO = 30


def _no_convertible(tipo: str) -> Resultado[str]:
    return Resultado(
        None,
        Aviso(
            "valor_no_convertible",
            Severidad.ADVERTENCIA,
            f"El valor no se pudo convertir a {tipo}; se dejo vacio",
        ),
    )


def normalizar_adicional_texto(valor: Any) -> Resultado[str]:
    return reglas.normalizar_texto(valor)


def normalizar_adicional_numero(valor: Any) -> Resultado[str]:
    if reglas.es_vacio(valor):
        return Resultado(None)
    try:
        numero = Decimal(str(valor).strip())
    except InvalidOperation:
        return _no_convertible("numero")
    if not numero.is_finite() or len(numero.as_tuple().digits) > _DIGITOS_MAXIMOS:
        return _no_convertible("numero")
    if numero == 0:
        return Resultado("0")
    if abs(numero.adjusted()) > _EXPONENTE_MAXIMO:
        return _no_convertible("numero")
    return Resultado(format(numero.normalize(), "f"))


def normalizar_adicional_fecha(valor: Any) -> Resultado[str]:
    resultado = reglas.normalizar_fecha(valor)
    if resultado.aviso is not None:
        return _no_convertible("fecha")
    return Resultado(None if resultado.valor is None else resultado.valor.isoformat())


CONVERSORES_ADICIONALES = {
    TipoCampo.ADICIONAL_TEXTO: normalizar_adicional_texto,
    TipoCampo.ADICIONAL_NUMERO: normalizar_adicional_numero,
    TipoCampo.ADICIONAL_FECHA: normalizar_adicional_fecha,
}
