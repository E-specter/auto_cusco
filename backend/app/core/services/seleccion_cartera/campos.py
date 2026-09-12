"""Campos consultables de la cartera, derivados del catalogo de la sabana.

Se construyen desde CATALOGO_VENCIDA para que no puedan desalinearse con lo que
produce la normalizacion ni con las columnas donde se guarda.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.entities.cartera import (
    OPERADORES_POR_TIPO,
    VALORES_POR_OPERADOR,
    ConsultaInvalida,
    Filtro,
    Funcion,
    Indicador,
    Orden,
    TipoDato,
)
from app.core.entities.sabana import TipoCampo
from app.core.services.ingesta_sabana.catalogo import CATALOGO_VENCIDA

_TIPOS = {
    TipoCampo.CLAVE: TipoDato.TEXTO,
    TipoCampo.TEXTO: TipoDato.TEXTO,
    TipoCampo.CATALOGO: TipoDato.TEXTO,
    TipoCampo.TELEFONO: TipoDato.TEXTO,
    TipoCampo.FINANCIERO: TipoDato.NUMERO,
    TipoCampo.ENTERO: TipoDato.NUMERO,
    TipoCampo.FECHA: TipoDato.FECHA,
    TipoCampo.BOOLEANO: TipoDato.BOOLEANO,
}
# La columna duplicada del pagare se descarta al ingestar (regla N-8).
_FUERA_DE_CONSULTA = frozenset({"pagare_duplicado"})

_VERDADEROS = frozenset({"true", "si", "1", "verdadero"})
_FALSOS = frozenset({"false", "no", "0", "falso"})

# Funciones que solo tienen sentido sobre un campo numerico.
_FUNCIONES_NUMERICAS = frozenset({Funcion.SUMA, Funcion.PROMEDIO})


def _construir_campos() -> dict[str, TipoDato]:
    campos: dict[str, TipoDato] = {}
    for columna in CATALOGO_VENCIDA:
        if columna.tipo is TipoCampo.SIN_VALOR or columna.nombre in _FUERA_DE_CONSULTA:
            continue
        if columna.tipo is TipoCampo.DOCUMENTO:
            campos[f"{columna.nombre}_tipo"] = TipoDato.TEXTO
            campos[f"{columna.nombre}_numero"] = TipoDato.TEXTO
        elif columna.tipo is TipoCampo.VENCIMIENTO_OPERATIVO:
            campos[f"{columna.nombre}_aplica"] = TipoDato.BOOLEANO
            campos[f"{columna.nombre}_fecha"] = TipoDato.FECHA
        else:
            campos[columna.nombre] = _TIPOS[columna.tipo]
    return campos


CAMPOS_CARTERA: dict[str, TipoDato] = _construir_campos()


def tipo_de(campo: str) -> TipoDato:
    if campo not in CAMPOS_CARTERA:
        raise ConsultaInvalida(f"El campo {campo!r} no existe en la cartera")
    return CAMPOS_CARTERA[campo]


def convertir(campo: str, texto: str) -> Any:
    """Convierte al tipo del campo un valor que llego como texto."""
    tipo = tipo_de(campo)
    crudo = texto.strip()
    if tipo is TipoDato.TEXTO:
        return crudo
    try:
        if tipo is TipoDato.NUMERO:
            return Decimal(crudo)
        if tipo is TipoDato.FECHA:
            return date.fromisoformat(crudo)
        if crudo.casefold() in _VERDADEROS:
            return True
        if crudo.casefold() in _FALSOS:
            return False
        raise ValueError(crudo)
    except (InvalidOperation, ValueError) as exc:
        raise ConsultaInvalida(
            f"El valor {texto!r} no es un {tipo.value} valido para el campo {campo!r}"
        ) from exc


def validar_filtro(filtro: Filtro) -> None:
    tipo = tipo_de(filtro.campo)
    if filtro.operador not in OPERADORES_POR_TIPO[tipo]:
        permitidos = ", ".join(sorted(o.value for o in OPERADORES_POR_TIPO[tipo]))
        raise ConsultaInvalida(
            f"El operador {filtro.operador.value!r} no aplica a un campo {tipo.value}; "
            f"permitidos: {permitidos}"
        )
    esperados = VALORES_POR_OPERADOR[filtro.operador]
    if esperados is None and not filtro.valores:
        raise ConsultaInvalida(f"El operador {filtro.operador.value!r} necesita al menos un valor")
    if esperados is not None and len(filtro.valores) != esperados:
        raise ConsultaInvalida(
            f"El operador {filtro.operador.value!r} necesita {esperados} valor(es); "
            f"se recibieron {len(filtro.valores)}"
        )
    for valor in filtro.valores:
        if isinstance(valor, datetime):
            raise ConsultaInvalida("Las fechas de cartera no llevan hora")
        if isinstance(valor, str) and tipo is not TipoDato.TEXTO:
            raise ConsultaInvalida(
                f"El valor {valor!r} llego como texto y el campo {filtro.campo!r} es {tipo.value}"
            )


def validar_orden(orden: Orden) -> None:
    tipo_de(orden.campo)


def validar_indicador(indicador: Indicador) -> None:
    if not indicador.nombre.strip():
        raise ConsultaInvalida("Cada indicador necesita un nombre")
    if indicador.campo is None:
        if indicador.funcion is Funcion.CONTEO:
            return
        raise ConsultaInvalida(f"La funcion {indicador.funcion.value!r} necesita un campo")
    tipo = tipo_de(indicador.campo)
    if indicador.funcion in _FUNCIONES_NUMERICAS and tipo is not TipoDato.NUMERO:
        raise ConsultaInvalida(
            f"La funcion {indicador.funcion.value!r} solo aplica a campos numericos, "
            f"y {indicador.campo!r} es {tipo.value}"
        )


def catalogo_publico() -> dict[str, dict[str, Any]]:
    """Campos con su tipo y operadores, para que la interfaz arme los filtros."""
    return {
        nombre: {
            "tipo": tipo.value,
            "operadores": sorted(o.value for o in OPERADORES_POR_TIPO[tipo]),
        }
        for nombre, tipo in CAMPOS_CARTERA.items()
    }
