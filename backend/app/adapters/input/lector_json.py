"""Lector de archivos JSON (RF-57, ver docs/mapeador-encabezados.md, seccion 4).

Debe ser una lista de objetos. Los encabezados son la union de las claves, en el orden en que
aparecen por primera vez; los objetos son las filas 2 en adelante (la fila 1 es la de encabezados).
Los numeros y los booleanos conservan su tipo; un valor objeto o lista se guarda como texto JSON y
avisa con `valor_no_escalar` en su fila. Un valor `null` o una clave ausente es una celda vacia
(""), como en las hojas de calculo.
"""

import json
from typing import Any

from app.adapters.input.celdas import recortar
from app.core.entities.lectura_tabla import (
    AdvertenciaLectura,
    CodigoAdvertenciaLectura,
    FormatoTabla,
    OpcionesLectura,
    TablaLeida,
)
from app.core.entities.sabana import ArchivoIlegible, FilaCruda, HojaVacia

FILA_DE_CABECERA = 1


def _texto(valor: Any) -> Any:
    """El valor de la celda: escalar tal cual, `null` como vacio y un objeto o lista como texto."""
    if valor is None:
        return ""
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False)
    return valor


def leer_json(contenido: bytes, opciones: OpcionesLectura = OpcionesLectura()) -> TablaLeida:  # noqa: B008
    try:
        datos = json.loads(contenido.decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise ArchivoIlegible("El JSON no está en UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ArchivoIlegible(
            f"El JSON no es válido: {exc.msg} (línea {exc.lineno}, columna {exc.colno})"
        ) from exc
    if not isinstance(datos, list):
        raise ArchivoIlegible("El JSON debe ser una lista de objetos")
    for posicion, objeto in enumerate(datos, 1):
        if not isinstance(objeto, dict):
            raise ArchivoIlegible(f"El elemento {posicion} del JSON no es un objeto")
    cabeceras = list(dict.fromkeys(clave for objeto in datos for clave in objeto))
    if not cabeceras:
        raise HojaVacia("El archivo no tiene cabecera ni datos")

    filas: list[FilaCruda] = []
    advertencias: list[AdvertenciaLectura] = []
    for posicion, objeto in enumerate(datos):
        numero_fila = FILA_DE_CABECERA + 1 + posicion
        for clave, valor in objeto.items():
            if isinstance(valor, (dict, list)):
                advertencias.append(
                    AdvertenciaLectura(
                        numero_fila, clave, CodigoAdvertenciaLectura.VALOR_NO_ESCALAR
                    )
                )
        celdas = recortar([_texto(objeto.get(clave)) for clave in cabeceras])
        if celdas:
            filas.append(FilaCruda(numero_fila=numero_fila, celdas=celdas))
    return TablaLeida(
        formato=FormatoTabla.JSON,
        hojas=(),
        hoja=None,
        separador=None,
        codificacion=None,
        fila_cabecera=FILA_DE_CABECERA,
        cabeceras=cabeceras,
        filas=filas,
        advertencias=tuple(advertencias),
    )
