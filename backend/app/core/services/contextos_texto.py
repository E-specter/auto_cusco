"""Contextos del motor de texto enriquecido (RF-43): el registro generico y el de `cartera`.

Aqui solo vive lo compartido: el registro que busca un contexto por nombre y el contexto `cartera`,
que es de todos. Cada modulo declara el suyo en su propio paquete (el speech de MOWA MES esta en
`plataformas/mowa_mes/contexto_texto.py`) y la capa de composicion de la API los registra, una
linea por contexto: sumar un canal no toca este archivo. Este modulo no importa de `plataformas/`.
"""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from app.core.entities.contexto_texto import (
    ORIGEN_CARTERA,
    ContextoDesconocido,
    ContextoTexto,
    VariableContexto,
)
from app.core.entities.segmentacion import TABLA_RANGOS_POR_DEFECTO, VARIABLE_DIAS_AJUSTADOS
from app.core.entities.texto_enriquecido import TipoValor
from app.core.services.fecha_envio import DIAS_AJUSTADOS, FECHA_ENVIO, VARIABLES_DE_ENVIO
from app.core.services.seleccion_cartera.campos import CAMPOS_CARTERA

__all__ = ["ContextoDesconocido", "RegistroContextos", "contexto_cartera"]

# Datos sinteticos: nunca de un producto real.
_EJEMPLO_POR_CAMPO: dict[str, Any] = {
    "pagare": "000000000000000001",
    "telefono": "900000001",
    "celular_analista": "900000002",
    "titular": "TITULAR/SINTETICO,UNO",
    "documento_tipo": "dni",
    "documento_numero": "12345678",
    "saldo_capital_pendiente": Decimal("1500.50"),
    "saldo_soles_corte": Decimal("1620.75"),
    "monto_cuota": Decimal("250.00"),
    "dias_atraso": 12,
    "dias_atraso_entidad": 12,
    "fecha_vencimiento_cuota": date(2026, 10, 5),
    "vencimiento_operativo_fecha": date(2026, 10, 5),
    "moneda": "PEN",
    "region": "CUSCO",
    "agencia": "AGENCIA SINTETICA",
    FECHA_ENVIO: date(2026, 10, 5),
    DIAS_AJUSTADOS: 12,
}
# Las variables de la fecha de envio (RF-55) se nombran en la interfaz con su clave propia: no son
# columnas de la sabana. `dias_atraso_ajustados` comparte clave con la de MOWA MES (es la misma).
_CLAVES_DE_ENVIO = {
    FECHA_ENVIO: "textoEnriquecido.variable.fecha_envio",
    DIAS_AJUSTADOS: "textoEnriquecido.variable.dias_atraso_ajustados",
}
_EJEMPLO_POR_TIPO: dict[TipoValor, Any] = {
    TipoValor.TEXTO: "EJEMPLO",
    TipoValor.NUMERO: 100,
    TipoValor.FECHA: date(2026, 10, 5),
    TipoValor.BOOLEANO: True,
}


def _tipo(valor: Any) -> TipoValor:
    return TipoValor(getattr(valor, "value", valor))


def contexto_cartera() -> ContextoTexto:
    variables = tuple(
        VariableContexto(nombre, _tipo(tipo), None, ORIGEN_CARTERA)
        for nombre, tipo in CAMPOS_CARTERA.items()
    ) + tuple(
        VariableContexto(nombre, tipo, _CLAVES_DE_ENVIO[nombre], ORIGEN_CARTERA)
        for nombre, tipo in VARIABLES_DE_ENVIO.items()
    )
    ejemplo = {
        v.nombre: _EJEMPLO_POR_CAMPO.get(v.nombre, _EJEMPLO_POR_TIPO[v.tipo]) for v in variables
    }
    return ContextoTexto(
        nombre="cartera",
        clave_nombre="textoEnriquecido.contexto.cartera",
        variables=variables,
        ejemplo=ejemplo,
        limite_largo=None,
        umbral_advertencia=None,
        # Una definicion NUEVA segmenta por los dias ajustados a la fecha de envio (RF-55); una
        # version ya guardada conserva la variable que guardo y no se reinterpreta.
        variable_dias=VARIABLE_DIAS_AJUSTADOS,
        tabla_rangos=TABLA_RANGOS_POR_DEFECTO,
        registro_de_producto=dict,
    )


class RegistroContextos:
    """Los contextos que la aplicacion ofrece, por nombre y en el orden en que se registraron."""

    def __init__(self, contextos: Iterable[ContextoTexto]) -> None:
        self._contextos: dict[str, ContextoTexto] = {}
        for contexto in contextos:
            if contexto.nombre in self._contextos:
                raise ValueError(f"El contexto {contexto.nombre!r} esta registrado dos veces")
            self._contextos[contexto.nombre] = contexto

    def disponibles(self) -> tuple[ContextoTexto, ...]:
        return tuple(self._contextos.values())

    def obtener(self, nombre: str) -> ContextoTexto:
        try:
            return self._contextos[nombre]
        except KeyError:
            raise ContextoDesconocido(nombre) from None
