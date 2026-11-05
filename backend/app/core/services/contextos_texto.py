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
    TemaVariable,
    VariableContexto,
)
from app.core.entities.segmentacion import TABLA_RANGOS_POR_DEFECTO, VARIABLE_DIAS_AJUSTADOS
from app.core.entities.texto_enriquecido import TipoValor
from app.core.services.fecha_envio import DIAS_AJUSTADOS, FECHA_ENVIO, VARIABLES_DE_ENVIO
from app.core.services.seleccion_cartera.campos import CatalogoCartera

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
# El tema de cada campo base en el buscador (§13.3 del motor). Una sola fuente: la manda el backend.
# Un campo base que no este aqui cae en `OTROS`, y una prueba del catalogo lo avisa.
_TEMAS: dict[TemaVariable, tuple[str, ...]] = {
    TemaVariable.PERSONA: (
        "titular",
        "documento_tipo",
        "documento_numero",
        "telefono",
        "cliente_fallecido",
        "whatsapp_contacto",  # la variable de MOWA MES, no un campo de la cartera
    ),
    TemaVariable.DEUDA: (
        "monto_cuota",
        "cuotas_aprobadas",
        "cuotas_pagadas",
        "cuotas_pendientes",
        "saldo_capital_pendiente",
        "saldo_soles_corte",
        "saldo_cierre_actual",
        "valor_cierre_mes_anterior",
    ),
    TemaVariable.FECHAS: (
        "fecha_vencimiento_cuota",
        "vencimiento_operativo_aplica",
        "vencimiento_operativo_fecha",
        "dias_atraso",
        "dias_atraso_entidad",
        "mes_gestion",
        FECHA_ENVIO,
        DIAS_AJUSTADOS,
    ),
    TemaVariable.CREDITO: (
        "pagare",
        "tipo_producto",
        "estado_credito",
        "moneda",
        "tipo_reprogramacion",
        "descuento_planilla",
        "cantidad_paralelos",
        "cartera_tag",
    ),
    TemaVariable.GESTION: (
        "agencia",
        "region",
        "analista_actual",
        "analista_asignacion",
        "celular_analista",
        "bpo",
    ),
    TemaVariable.RIESGO: (
        "segmento_actual",
        "segmento_atraso",
        "segmento_financiero",
        "segmento_saldo",
        "tramo_actual",
        "tramo_proyectado",
        "tipo_basilea",
        "mora_impacto_actual",
        "mora_impacto_proyectada",
        "provision_actual",
        "provision_proyectada",
    ),
}
_TEMA_POR_CAMPO = {nombre: tema for tema, nombres in _TEMAS.items() for nombre in nombres}


def tema_de(nombre: str, adicional: bool = False) -> TemaVariable:
    """El tema de un campo: `ADICIONALES` si lo creo el usuario, el de la tabla si es base, y
    `OTROS` si es un campo base sin tema asignado."""
    if adicional:
        return TemaVariable.ADICIONALES
    return _TEMA_POR_CAMPO.get(nombre, TemaVariable.OTROS)


_EJEMPLO_POR_TIPO: dict[TipoValor, Any] = {
    TipoValor.TEXTO: "EJEMPLO",
    TipoValor.NUMERO: 100,
    TipoValor.FECHA: date(2026, 10, 5),
    TipoValor.BOOLEANO: True,
}


def _tipo(valor: Any) -> TipoValor:
    return TipoValor(getattr(valor, "value", valor))


def contexto_cartera(catalogo: CatalogoCartera) -> ContextoTexto:
    # Los archivados tambien: lo que ya los usa tiene que seguir compilando (RF-65).
    variables = tuple(
        VariableContexto(
            nombre,
            _tipo(campo.tipo),
            None,
            ORIGEN_CARTERA,
            campo.etiqueta,
            campo.adicional,
            campo.archivado,
            tema_de(nombre, campo.adicional),
        )
        for nombre, campo in catalogo.campos().items()
    ) + tuple(
        VariableContexto(
            nombre, tipo, _CLAVES_DE_ENVIO[nombre], ORIGEN_CARTERA, tema=tema_de(nombre)
        )
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
