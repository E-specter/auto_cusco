"""Registros de supervision de las campanas digitales (RF-37 a RF-41).

Transversal a toda plataforma digital: no sabe nada de MOWA MES ni de otra
plataforma. Donde van los registros dentro del archivo lo decide cada conector.
Los numeros de los supervisores son configuracion (RF-32): nunca se fijan en
el codigo.
"""

from dataclasses import dataclass

LARGO_MAXIMO_PROCEDENCIA = 60
LARGO_DOCUMENTO_SUPERVISION = 8  # DNI no real, secuencial desde 00000001 (RF-39)


@dataclass(frozen=True)
class Supervisor:
    numero: str
    procedencia: str


@dataclass(frozen=True)
class ConfiguracionSupervision:
    """Lista por defecto de supervisores y orden de las procedencias (RF-38, RF-39).

    El orden de `procedencias` es el orden en que se asignan los documentos.
    """

    procedencias: tuple[str, ...]
    supervisores: tuple[Supervisor, ...]


@dataclass(frozen=True)
class ProblemaSupervision:
    """Algo que impide guardar la configuracion. `posicion` cuenta desde 0."""

    campo: str  # "procedencias" o "supervisores"
    posicion: int | None
    detalle: str


class SupervisionInvalida(Exception):
    def __init__(self, problemas: tuple[ProblemaSupervision, ...]) -> None:
        resumen = "; ".join(
            p.detalle if p.posicion is None else f"{p.campo} {p.posicion + 1}: {p.detalle}"
            for p in problemas
        )
        super().__init__(f"La configuracion de supervision no es valida. {resumen}")
        self.problemas = problemas


class SinSupervisores(Exception):
    """La campana no tiene supervisores: no se genera la carga (RF-37)."""

    def __init__(self) -> None:
        super().__init__("La campana no tiene supervisores configurados")


class SinProductosCargables(Exception):
    """No hay primera fila valida: no hay supervision ni carga (RF-37)."""

    def __init__(self) -> None:
        super().__init__("La seleccion no tiene productos que se puedan cargar")
