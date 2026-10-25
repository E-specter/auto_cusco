"""El analisis y las asignaciones del mapeador como JSON (se guardan con el borrador y la carga).

El borrador guarda el analisis que se le mostro al usuario (M-4): se valida contra ese, no contra
uno nuevo. La carga guarda la lista de asignaciones ya resuelta, con el encabezado normalizado de
cada columna, para comprobar al procesar que la columna sigue siendo la misma.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from app.core.entities.mapeador import (
    AnalisisEncabezados,
    Asignacion,
    CampoDestino,
    ColumnaAnalizada,
    EstadoEncabezado,
    OrigenAsignacion,
)


def _campo_a_dict(campo: CampoDestino) -> dict[str, Any]:
    return {
        "nombre": campo.nombre,
        "clave_etiqueta": campo.clave_etiqueta,
        "tipo": campo.tipo,
        "obligatorio": campo.obligatorio,
        "alias": list(campo.alias),
    }


def _campo_desde_dict(datos: Mapping[str, Any]) -> CampoDestino:
    return CampoDestino(
        nombre=datos["nombre"],
        clave_etiqueta=datos["clave_etiqueta"],
        tipo=datos["tipo"],
        obligatorio=datos["obligatorio"],
        alias=tuple(datos["alias"]),
    )


def _columna_a_dict(columna: ColumnaAnalizada) -> dict[str, Any]:
    return {
        "indice": columna.indice,
        "encabezado": columna.encabezado,
        "normalizado": columna.normalizado,
        "ocurrencia": columna.ocurrencia,
        "ejemplos": list(columna.ejemplos),
        "estado": columna.estado.value,
        "sugerido": columna.sugerido,
        "similitud": columna.similitud,
    }


def _columna_desde_dict(datos: Mapping[str, Any]) -> ColumnaAnalizada:
    return ColumnaAnalizada(
        indice=datos["indice"],
        encabezado=datos["encabezado"],
        normalizado=datos["normalizado"],
        ocurrencia=datos["ocurrencia"],
        ejemplos=tuple(datos["ejemplos"]),
        estado=EstadoEncabezado(datos["estado"]),
        sugerido=datos["sugerido"],
        similitud=datos["similitud"],
    )


def analisis_a_dict(analisis: AnalisisEncabezados) -> dict[str, Any]:
    """El analisis sin sus problemas iniciales: se recalculan al leerlo (son derivados)."""
    return {
        "catalogo_id": analisis.catalogo_id,
        "columnas": [_columna_a_dict(c) for c in analisis.columnas],
        "campos": [_campo_a_dict(c) for c in analisis.campos],
    }


def analisis_desde_dict(datos: Mapping[str, Any]) -> AnalisisEncabezados:
    """El analisis guardado. Sus `problemas_iniciales` quedan vacios: no se guardan."""
    return AnalisisEncabezados(
        catalogo_id=datos["catalogo_id"],
        columnas=tuple(_columna_desde_dict(c) for c in datos["columnas"]),
        campos=tuple(_campo_desde_dict(c) for c in datos["campos"]),
        problemas_iniciales=(),
    )


def asignaciones_a_dict(
    asignaciones: Sequence[Asignacion], analisis: AnalisisEncabezados
) -> list[dict[str, Any]]:
    """Las asignaciones como se guardan con la carga: `{indice, encabezado_normalizado, campo,
    origen}`, en el orden de las columnas. `indice` va en base 0 (como en la API)."""
    por_indice = {a.indice: a for a in asignaciones}
    return [
        {
            "indice": columna.indice,
            "encabezado_normalizado": columna.normalizado,
            "campo": por_indice[columna.indice].campo,
            "origen": por_indice[columna.indice].origen.value,
        }
        for columna in analisis.columnas
    ]


def asignaciones_desde_dict(datos: Sequence[Mapping[str, Any]]) -> tuple[Asignacion, ...]:
    return tuple(Asignacion(a["indice"], a["campo"], OrigenAsignacion(a["origen"])) for a in datos)


def recordados_de(
    asignaciones: Sequence[Asignacion], analisis: AnalisisEncabezados
) -> dict[tuple[str, int], str | None]:
    """Lo que se recuerda al confirmar: (encabezado normalizado, ocurrencia) -> campo (RF-61)."""
    por_indice = {a.indice: a for a in asignaciones}
    return {
        (columna.normalizado, columna.ocurrencia): por_indice[columna.indice].campo
        for columna in analisis.columnas
    }
