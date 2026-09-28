"""Nombre de los archivos de carga de MOWA MES a partir de una plantilla (RF-MM-25).

Una sola resolucion para todo: la creacion de la campana, la previsualizacion y
el ejemplo de la configuracion llaman a estas mismas funciones, asi el nombre
que se muestra es el que se guarda.

Resolucion de un archivo, en este orden:

1. Sustituir las variables `{...}`.
2. Reemplazar por `_` los caracteres que Windows no admite (`\\ / : * ? " < > |` y
   los de control).
3. Recortar los espacios y los puntos de los extremos.
4. Con mas de un archivo y sin `{archivo}` en la plantilla, reservar el sufijo
   `_{archivo}de{total}`.
5. Limitar el nombre, sin la extension, a 120 caracteres recortando la parte de
   la plantilla y nunca el sufijo.
6. Agregar `.xlsx`.

Si tras los pasos 1 a 3 no queda nada, se usa la plantilla por defecto (antes
del sufijo: un sufijo solo no es un nombre). Si al resolver los archivos de una
campana dos nombres coinciden (por ejemplo `{archivo}{cantidad}` da `123` para
el archivo 1 con 23 filas y para el 12 con 3), se reserva el sufijo en todos: con
el sufijo el nombre es unico.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.core.entities.mowa_mes import PLANTILLA_NOMBRE_POR_DEFECTO
from app.core.entities.mowa_mes_costo import (
    EXTENSION_ARCHIVO,
    LARGO_MAXIMO_NOMBRE_ARCHIVO,
    VARIABLES_PLANTILLA,
    PlantillaInvalida,
)

LARGO_MAXIMO_PLANTILLA = 300
MARCADOR_CAMPANA = "[campana]"  # la campana todavia no existe al previsualizar (D-1)

_NOMBRES = tuple(v.nombre for v in VARIABLES_PLANTILLA)
_VARIABLE = re.compile(r"\{([^{}]*)\}")
_PROHIBIDOS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_VALIDAS = ", ".join("{" + nombre + "}" for nombre in _NOMBRES)
# Variables cuyo valor sale de como se divida la carga: el nombre previsto es una estimacion.
_DEPENDEN_DE_LA_DIVISION = frozenset({"archivo", "total", "cantidad"})


@dataclass(frozen=True)
class ContextoNombre:
    """Lo que la campana aporta a la plantilla; lo de cada archivo se pasa aparte."""

    campana: str  # el id, o `MARCADOR_CAMPANA` antes de crearla
    descripcion: str
    fecha_envio: date
    fecha_corte: date


# Datos de muestra del ejemplo de la configuracion: dos archivos, para que se vea el
# nombre con varios (RF-MM-25 da este mismo ejemplo, con fecha de envio 2026-10-01).
CONTEXTO_EJEMPLO = ContextoNombre("1234", "CajaCusco", date(2026, 10, 1), date(2026, 9, 30))
CANTIDADES_EJEMPLO = (50_000, 1_200)


def variables_usadas(plantilla: str) -> tuple[str, ...]:
    """Las variables de la plantilla, en orden. PlantillaInvalida si hay una que no existe
    (la nombra) o una llave sin cerrar o sin abrir."""
    resto = _VARIABLE.sub("", plantilla)
    if "{" in resto:
        raise PlantillaInvalida("La plantilla tiene una llave { sin cerrar")
    if "}" in resto:
        raise PlantillaInvalida("La plantilla tiene una llave } sin abrir")
    nombres = tuple(coincidencia.group(1) for coincidencia in _VARIABLE.finditer(plantilla))
    for nombre in nombres:
        if nombre not in _NOMBRES:
            raise PlantillaInvalida(
                f"{{{nombre}}} no es una variable de la plantilla. Variables validas: {_VALIDAS}"
            )
    return nombres


def plantilla_valida(texto: str | None, por_defecto: str = PLANTILLA_NOMBRE_POR_DEFECTO) -> str:
    """La plantilla lista para guardar o usar: sin espacios en los extremos, la de por
    defecto si viene vacia, y validada."""
    plantilla = (texto or "").strip() or por_defecto
    if len(plantilla) > LARGO_MAXIMO_PLANTILLA:
        raise PlantillaInvalida(
            f"La plantilla no puede pasar de {LARGO_MAXIMO_PLANTILLA} caracteres"
        )
    variables_usadas(plantilla)
    return plantilla


def _cuerpo(
    plantilla: str, contexto: ContextoNombre, archivo: int, total: int, cantidad: int
) -> str:
    valores = {
        "campana": contexto.campana,
        "descripcion": contexto.descripcion,
        "fecha_envio": contexto.fecha_envio.isoformat(),
        "fecha_corte": contexto.fecha_corte.isoformat(),
        "archivo": str(archivo),
        "total": str(total),
        "cantidad": str(cantidad),
    }
    sustituido = _VARIABLE.sub(lambda coincidencia: valores[coincidencia.group(1)], plantilla)
    return _PROHIBIDOS.sub("_", sustituido).strip(" .")


def resolver_nombre(
    plantilla: str,
    contexto: ContextoNombre,
    archivo: int,
    total: int,
    cantidad: int,
    forzar_sufijo: bool = False,
) -> str:
    """El nombre, con la extension, de un archivo. La plantilla debe estar validada."""
    efectiva = plantilla
    cuerpo = _cuerpo(efectiva, contexto, archivo, total, cantidad)
    if not cuerpo:
        efectiva = PLANTILLA_NOMBRE_POR_DEFECTO
        cuerpo = _cuerpo(efectiva, contexto, archivo, total, cantidad)
    necesita_sufijo = forzar_sufijo or (total > 1 and "archivo" not in variables_usadas(efectiva))
    sufijo = f"_{archivo}de{total}" if necesita_sufijo else ""
    cuerpo = cuerpo[: LARGO_MAXIMO_NOMBRE_ARCHIVO - len(sufijo)].rstrip(" .")
    return f"{cuerpo}{sufijo}{EXTENSION_ARCHIVO}"


def resolver_nombres(
    plantilla: str, contexto: ContextoNombre, cantidades: Sequence[int]
) -> list[str]:
    """Los nombres de todos los archivos de una campana, uno por cantidad de filas.

    Nunca dos iguales (sin distinguir mayusculas, como el sistema de archivos de Windows).
    """
    total = len(cantidades)
    nombres = [
        resolver_nombre(plantilla, contexto, numero, total, filas)
        for numero, filas in enumerate(cantidades, start=1)
    ]
    if len({nombre.casefold() for nombre in nombres}) < total:
        nombres = [
            resolver_nombre(plantilla, contexto, numero, total, filas, forzar_sufijo=True)
            for numero, filas in enumerate(cantidades, start=1)
        ]
    return nombres


def nombre_previsto(
    plantilla: str, contexto: ContextoNombre, cantidades: Sequence[int]
) -> tuple[str, bool] | None:
    """Nombre del primer archivo antes de crear la campana y si es una estimacion (D-1).

    Es estimado si depende de como se divida la carga: usa `{archivo}`, `{total}` o
    `{cantidad}`, o el sufijo automatico entra porque hay mas de un archivo. Sin
    archivos previstos (la campana no se puede crear) no hay nombre.
    """
    if not cantidades:
        return None
    usadas = set(variables_usadas(plantilla))
    nombres = resolver_nombres(plantilla, contexto, cantidades)
    estimado = bool(usadas & _DEPENDEN_DE_LA_DIVISION) or (
        len(cantidades) > 1 and "archivo" not in usadas
    )
    return nombres[0], estimado
