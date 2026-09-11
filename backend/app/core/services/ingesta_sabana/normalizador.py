"""Normalizacion de filas y chequeos de consistencia (reglas N-2 a N-8)."""

from collections.abc import Callable, Sequence
from typing import Any

from app.core.entities.sabana import (
    Aviso,
    ColumnaSabana,
    FilaNormalizada,
    Incidencia,
    MapeoCabeceras,
    Severidad,
    TipoCampo,
)
from app.core.services.ingesta_sabana import reglas
from app.core.services.ingesta_sabana.reglas import Resultado

_CONVERSORES: dict[TipoCampo, Callable[[Any], Resultado[Any]]] = {
    TipoCampo.TEXTO: reglas.normalizar_texto,
    TipoCampo.CATALOGO: lambda v: reglas.normalizar_texto(v, colapsar_espacios=True),
    TipoCampo.TELEFONO: reglas.normalizar_telefono,
    TipoCampo.FINANCIERO: reglas.normalizar_financiero,
    TipoCampo.ENTERO: reglas.normalizar_entero,
    TipoCampo.FECHA: reglas.normalizar_fecha,
    TipoCampo.BOOLEANO: reglas.normalizar_booleano,
}


def _normalizar_clave(valor: Any) -> Resultado[str]:
    """El pagare debe llegar como texto: como numero pierde precision (18 digitos)."""
    if reglas.es_vacio(valor):
        return Resultado(None, Aviso("clave_vacia", Severidad.ERROR, "Pagare vacio"))
    if not isinstance(valor, str):
        return Resultado(
            None,
            Aviso(
                "clave_no_texto",
                Severidad.ERROR,
                "El pagare llego como numero; puede haber perdido digitos",
            ),
        )
    return Resultado(valor.strip())


def _asignar(columna: ColumnaSabana, crudo: Any, valores: dict[str, Any]) -> Aviso | None:
    """Convierte un valor y lo escribe en `valores` con el/los nombres de salida."""
    nombre = columna.nombre
    if columna.tipo is TipoCampo.DOCUMENTO:
        resultado = reglas.normalizar_documento(crudo)
        documento = resultado.valor
        valores[f"{nombre}_tipo"] = documento.tipo if documento else None
        valores[f"{nombre}_numero"] = documento.numero if documento else None
        return resultado.aviso
    if columna.tipo is TipoCampo.VENCIMIENTO_OPERATIVO:
        resultado = reglas.normalizar_vencimiento_operativo(crudo)
        aplica, fecha = resultado.valor if resultado.valor else (None, None)
        valores[f"{nombre}_aplica"] = aplica
        valores[f"{nombre}_fecha"] = fecha
        return resultado.aviso
    if columna.tipo is TipoCampo.CLAVE:
        resultado = _normalizar_clave(crudo)
        if resultado.aviso and columna.nombre != "pagare":
            # El duplicado no es la clave: su ausencia o formato no bloquea la fila.
            resultado = Resultado(
                resultado.valor,
                Aviso(resultado.aviso.codigo, Severidad.ADVERTENCIA, resultado.aviso.detalle),
            )
    else:
        resultado = _CONVERSORES[columna.tipo](crudo)
    valores[nombre] = resultado.valor
    return resultado.aviso


def _consistencia(valores: dict[str, Any]) -> list[Aviso]:
    """Reglas de consistencia N-8: se reportan, no bloquean."""
    avisos: list[Aviso] = []
    aprobadas = valores.get("cuotas_aprobadas")
    pagadas = valores.get("cuotas_pagadas")
    pendientes = valores.get("cuotas_pendientes")
    if None not in (aprobadas, pagadas, pendientes) and pagadas + pendientes != aprobadas:
        avisos.append(
            Aviso(
                "cuotas_inconsistentes",
                Severidad.ADVERTENCIA,
                "cuotas_pagadas + cuotas_pendientes no coincide con cuotas_aprobadas",
            )
        )
    dias, dias_entidad = valores.get("dias_atraso"), valores.get("dias_atraso_entidad")
    if dias is not None and dias_entidad is not None and dias != dias_entidad:
        avisos.append(
            Aviso(
                "dias_atraso_difiere_entidad",
                Severidad.INFO,
                "dias_atraso difiere de dias_atraso_entidad",
            )
        )
    if "pagare_duplicado" in valores:
        duplicado = valores.pop("pagare_duplicado")
        clave = valores.get("pagare")
        if duplicado is not None and clave is not None and duplicado != clave:
            avisos.append(
                Aviso(
                    "pagare_duplicado_distinto",
                    Severidad.ADVERTENCIA,
                    "La columna duplicada del pagare no coincide con la clave",
                )
            )
    return avisos


def normalizar_fila(
    celdas: Sequence[Any], mapeo: MapeoCabeceras, numero_fila: int
) -> FilaNormalizada:
    """Normaliza una fila de datos segun el mapeo de cabeceras del archivo.

    `numero_fila` es el numero de fila en la hoja (base 1), para ubicar las
    incidencias. Las columnas `SIN_VALOR` y desconocidas no se incluyen en
    `valores`; deben conservarse en el registro crudo (N-9) por el adaptador.
    """
    valores: dict[str, Any] = {}
    incidencias: list[Incidencia] = []

    for indice, columna in mapeo.columnas.items():
        if columna.tipo is TipoCampo.SIN_VALOR:
            continue
        crudo = celdas[indice] if indice < len(celdas) else None
        aviso = _asignar(columna, crudo, valores)
        if aviso is not None:
            incidencias.append(
                Incidencia(
                    numero_fila, columna.nombre, aviso.codigo, aviso.severidad, aviso.detalle, crudo
                )
            )

    for aviso in _consistencia(valores):
        incidencias.append(
            Incidencia(numero_fila, None, aviso.codigo, aviso.severidad, aviso.detalle)
        )

    return FilaNormalizada(numero_fila=numero_fila, valores=valores, incidencias=incidencias)
