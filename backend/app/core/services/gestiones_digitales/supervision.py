"""Reglas de los registros de supervision (RF-37 a RF-41), sin plataforma concreta.

El conector de cada plataforma entrega los supervisores de la campana, el orden
de las procedencias, la primera fila valida de sus productos y el nombre de sus
columnas de numero y documento; recibe las filas de supervision listas para
anexar donde su formato lo pida.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from app.core.entities.gestiones_digitales import (
    LARGO_DOCUMENTO_SUPERVISION,
    LARGO_MAXIMO_PROCEDENCIA,
    ConfiguracionSupervision,
    ProblemaSupervision,
    SinProductosCargables,
    SinSupervisores,
    SupervisionInvalida,
    Supervisor,
)
from app.core.services.ingesta_sabana.reglas import normalizar_telefono


def numero_valido(numero: str) -> bool:
    """El mismo criterio de telefono que la ingesta (RF-02, regla N-4), sin corregir nada."""
    return normalizar_telefono(numero).valor == numero


def limpiar(configuracion: ConfiguracionSupervision) -> ConfiguracionSupervision:
    return ConfiguracionSupervision(
        procedencias=tuple(p.strip() for p in configuracion.procedencias),
        supervisores=tuple(
            Supervisor(numero=s.numero.strip(), procedencia=s.procedencia.strip())
            for s in configuracion.supervisores
        ),
    )


def problemas_de(configuracion: ConfiguracionSupervision) -> tuple[ProblemaSupervision, ...]:
    problemas: list[ProblemaSupervision] = []
    if not configuracion.procedencias:
        problemas.append(
            ProblemaSupervision("procedencias", None, "Debe haber al menos una procedencia")
        )
    vistas: set[str] = set()
    for posicion, procedencia in enumerate(configuracion.procedencias):
        if not 1 <= len(procedencia) <= LARGO_MAXIMO_PROCEDENCIA:
            problemas.append(
                ProblemaSupervision(
                    "procedencias",
                    posicion,
                    f"La procedencia debe tener entre 1 y {LARGO_MAXIMO_PROCEDENCIA} caracteres",
                )
            )
        elif procedencia.casefold() in vistas:
            problemas.append(
                ProblemaSupervision(
                    "procedencias", posicion, f"La procedencia {procedencia!r} esta repetida"
                )
            )
        vistas.add(procedencia.casefold())
    conocidas = set(configuracion.procedencias)
    for posicion, supervisor in enumerate(configuracion.supervisores):
        if not numero_valido(supervisor.numero):
            problemas.append(
                ProblemaSupervision(
                    "supervisores",
                    posicion,
                    "El numero debe tener 9 digitos y empezar con 9",
                )
            )
        if supervisor.procedencia not in conocidas:
            problemas.append(
                ProblemaSupervision(
                    "supervisores",
                    posicion,
                    f"La procedencia {supervisor.procedencia!r} no esta en la lista",
                )
            )
    return tuple(problemas)


def validar(configuracion: ConfiguracionSupervision) -> ConfiguracionSupervision:
    """Devuelve la configuracion limpia o lanza SupervisionInvalida."""
    limpia = limpiar(configuracion)
    problemas = problemas_de(limpia)
    if problemas:
        raise SupervisionInvalida(problemas)
    return limpia


def _posiciones_en_orden(
    supervisores: Sequence[Supervisor], procedencias: Sequence[str]
) -> list[int]:
    orden = {procedencia: indice for indice, procedencia in enumerate(procedencias)}
    desconocidas = [s.procedencia for s in supervisores if s.procedencia not in orden]
    if desconocidas:
        raise SupervisionInvalida(
            (
                ProblemaSupervision(
                    "supervisores", None, f"Procedencias sin orden: {sorted(set(desconocidas))}"
                ),
            )
        )
    # sorted es estable: dentro de una procedencia se respeta el orden de la lista.
    return sorted(range(len(supervisores)), key=lambda i: orden[supervisores[i].procedencia])


def _documento(numero: int) -> str:
    return str(numero).zfill(LARGO_DOCUMENTO_SUPERVISION)


def documentos_asignados(
    supervisores: Sequence[Supervisor], procedencias: Sequence[str]
) -> list[tuple[Supervisor, str]]:
    """Cada supervisor con su DNI no real (RF-39), en el orden de asignacion.

    Primero los de la primera procedencia, luego los de la segunda, y asi; dentro
    de cada procedencia, en el orden de la lista. La secuencia es una sola para
    toda la campana: 00000001, 00000002...
    """
    return [
        (supervisores[posicion], _documento(numero))
        for numero, posicion in enumerate(_posiciones_en_orden(supervisores, procedencias), 1)
    ]


def documentos_por_posicion(
    supervisores: Sequence[Supervisor], procedencias: Sequence[str]
) -> list[str]:
    """El DNI que le toca a cada supervisor, alineado con la lista tal como viene."""
    documentos = [""] * len(supervisores)
    for numero, posicion in enumerate(_posiciones_en_orden(supervisores, procedencias), 1):
        documentos[posicion] = _documento(numero)
    return documentos


def filas_supervision(
    supervisores: Sequence[Supervisor],
    procedencias: Sequence[str],
    fila_plantilla: Mapping[str, Any] | None,
    columna_numero: str,
    columna_documento: str,
) -> list[dict[str, Any]]:
    """Filas de supervision de la campana (RF-39, RF-40).

    `fila_plantilla` es la primera fila valida de los productos, ya con las
    exclusiones de la plataforma aplicadas. Todos sus campos se copian salvo el
    numero y el documento, que son los del supervisor. El numero va como texto:
    si la plataforma lo quiere de otro tipo, lo convierte su conector.
    """
    if not supervisores:
        raise SinSupervisores()
    if fila_plantilla is None:
        raise SinProductosCargables()
    return [
        {**fila_plantilla, columna_numero: supervisor.numero, columna_documento: documento}
        for supervisor, documento in documentos_asignados(supervisores, procedencias)
    ]
