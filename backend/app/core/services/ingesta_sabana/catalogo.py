"""Catalogo por defecto de columnas de la hoja VENCIDA.

Refleja docs/sabana-schema.md, seccion 4. Es configuracion (RF-32): otro
formato de sabana puede usar su propio catalogo sin tocar las reglas.

Los patrones se evaluan en orden sobre la cabecera normalizada (sin tildes,
minusculas, espacios colapsados); una columna ya asignada no vuelve a
asignarse. Por eso `pagare` va antes que `pagare_duplicado`: la primera
cabecera "Pagare" toma la clave y la segunda ("PAGARE" o "PAGARE2") el
duplicado.
"""

from collections.abc import Iterable

from app.core.entities.campos_adicionales import CampoAdicional
from app.core.entities.mapeador import CampoDestino, CatalogoCampos
from app.core.entities.sabana import ColumnaSabana, TipoCampo

T = TipoCampo


def _col(nombre: str, tipo: TipoCampo, *patrones: str, requerida: bool = False) -> ColumnaSabana:
    return ColumnaSabana(nombre=nombre, tipo=tipo, patrones=patrones, requerida=requerida)


CATALOGO_VENCIDA: tuple[ColumnaSabana, ...] = (
    _col("region", T.CATALOGO, r"region"),
    _col("agencia", T.CATALOGO, r"agencia"),
    _col("analista_asignacion", T.TEXTO, r"analista"),
    _col("titular", T.TEXTO, r"titular"),
    _col("documento", T.DOCUMENTO, r"dniruc", r"dni ?/ ?ruc"),
    _col("telefono", T.TELEFONO, r"telefono"),
    _col("pagare", T.CLAVE, r"pagare", requerida=True),
    _col("saldo_soles_corte", T.FINANCIERO, r"saldosoles( [0-9]{1,2}/[0-9]{1,2})?"),
    _col("tipo_reprogramacion", T.CATALOGO, r"tipo de reprogramacion"),
    _col("vencimiento_operativo", T.VENCIMIENTO_OPERATIVO, r"vencimientos? operativos?"),
    _col("dias_atraso", T.ENTERO, r"dias atraso hoy"),
    _col("analista_actual", T.TEXTO, r"analista actual"),
    _col("saldo_capital_pendiente", T.FINANCIERO, r"saldo capital pendiente"),
    _col("monto_cuota", T.FINANCIERO, r"monto cuota"),
    _col("estado_credito", T.CATALOGO, r"estado del credito"),
    _col("fecha_vencimiento_cuota", T.FECHA, r"vencimiento cuota"),
    _col("cliente_fallecido", T.BOOLEANO, r"cliente fallecido"),
    _col("dias_atraso_entidad", T.ENTERO, r"dias sicmac-c"),
    _col("cuotas_aprobadas", T.ENTERO, r"cuotas apro(badas)?"),
    _col("cuotas_pagadas", T.ENTERO, r"cuotas pagadas"),
    _col("cuotas_pendientes", T.ENTERO, r"cuotas pendientes"),
    _col("tipo_basilea", T.CATALOGO, r"tipo ?basilea"),
    _col("tipo_producto", T.CATALOGO, r"tipo ?producto"),
    _col("pagare_duplicado", T.CLAVE, r"pagare2?"),
    _col("validador", T.SIN_VALOR, r"validador"),
    _col("segmento_saldo", T.CATALOGO, r"segmento saldo"),
    _col("moneda", T.CATALOGO, r"moneda"),
    # Nombre enganoso en origen: contiene montos, no dias (pregunta abierta P-2).
    _col("valor_cierre_mes_anterior", T.FINANCIERO, r"dias cierre mes anterior"),
    _col("saldo_cierre_actual", T.FINANCIERO, r"saldo cierre actual"),
    _col("cod_tipo_basilea", T.SIN_VALOR, r"cod\.? ?tipo basilea"),
    _col("bpo", T.CATALOGO, r"bpo"),
    _col("cartera_tag", T.CATALOGO, r"tag"),
    _col("mes_gestion", T.CATALOGO, r"mes de gestion"),
    _col("segmento_actual", T.CATALOGO, r"segmento actual"),
    # En origen la cabecera trae el error "FINACIERO"; se aceptan ambas formas.
    _col("segmento_financiero", T.CATALOGO, r"segmento fina?n?ciero"),
    _col("descuento_planilla", T.BOOLEANO, r"validacion descuento planilla"),
    _col("segmento_atraso", T.CATALOGO, r"segmento"),
    _col("tramo_actual", T.CATALOGO, r"tramo actual"),
    _col("provision_actual", T.CATALOGO, r"provision actual"),
    _col("mora_impacto_actual", T.BOOLEANO, r"mora impacto actual"),
    _col("tramo_proyectado", T.CATALOGO, r"tramo proyectado"),
    _col("provision_proyectada", T.CATALOGO, r"provision proyectada"),
    _col("mora_impacto_proyectada", T.BOOLEANO, r"mora impacto proyectada"),
    _col("cantidad_paralelos", T.ENTERO, r"cant\.? ?paralelos"),
    _col("celular_analista", T.TELEFONO, r"celular analista"),
)


def campo_destino(columna: ColumnaSabana) -> CampoDestino:
    """La columna de la sabana como campo del mapeador: `requerida` pasa a `obligatorio`, `patrones`
    a `alias`, el tipo a su nombre (el mapeador no conoce `TipoCampo`) y la etiqueta es
    `campo.<nombre>`."""
    return CampoDestino(
        nombre=columna.nombre,
        clave_etiqueta=f"campo.{columna.nombre}",
        tipo=columna.tipo.value,
        obligatorio=columna.requerida,
        alias=columna.patrones,
    )


def campo_destino_adicional(campo: CampoAdicional) -> CampoDestino:
    """Un campo adicional (RF-64) como campo del mapeador: nunca obligatorio, su alias es el
    encabezado de origen (un texto) y su nombre legible es una etiqueta literal."""
    return CampoDestino(
        nombre=campo.nombre,
        clave_etiqueta=f"campo.{campo.nombre}",
        tipo=campo.tipo.value,
        obligatorio=False,
        alias=(campo.encabezado_origen,),
        etiqueta=campo.nombre_legible,
        adicional=True,
    )


def armar_catalogo_sabana(adicionales: Iterable[CampoAdicional] = ()) -> CatalogoCampos:
    """Los campos base y, despues, los adicionales ACTIVOS (un archivado no se ofrece, RF-65)."""
    return CatalogoCampos(
        "sabana_vencida",
        (
            *(campo_destino(c) for c in CATALOGO_VENCIDA),
            *(campo_destino_adicional(c) for c in adicionales if not c.archivado),
        ),
    )


# El catalogo base de la sabana para el mapeador de encabezados (RF-63). Su `id` es la clave de los
# mapeos recordados: no se cambia. Con campos adicionales, `armar_catalogo_sabana`.
CATALOGO_SABANA = armar_catalogo_sabana()
