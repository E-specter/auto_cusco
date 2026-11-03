"""Entidades del informe de WhatsMKT y de su conciliacion (RF-WM-37 y RF-WM-39, T-WM-B6a)."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class InformeWhatsmkt:
    """Lo que se lee del informe que genera WhatsMKT al terminar una campana.

    - `fecha_informada` y `total_informado`: los de las filas `FECHA` y `TOTAL DE ENVIO`; nulos si
      la fila falta o no se entiende (no se rechaza por eso).
    - `campana` y `tipo_envio`: el texto de la primera fila de detalle. El nombre de campana se
      escribe a mano en WhatsMKT: solo se muestra, nunca sirve de clave.
    - `numeros`: uno por fila de detalle, como texto de digitos y en el orden del informe. Un
      numero repetido se conserva repetido: el total se compara con las filas.
    """

    fecha_informada: date | None
    total_informado: int | None
    campana: str | None
    tipo_envio: str | None
    numeros: tuple[str, ...]

    @property
    def coincide_total(self) -> bool | None:
        """Si el total informado es la cantidad de filas de detalle; None si no se informo (DU-WM-7:
        la diferencia se muestra, no rechaza el informe)."""
        return None if self.total_informado is None else self.total_informado == len(self.numeros)


@dataclass(frozen=True)
class FilaCargadaWhatsmkt:
    """Una fila del archivo cargado: su numero (digitos), su pagare (nulo en un supervisor) y si
    es un registro de supervision (RF-WM-14)."""

    numero: str
    pagare: str | None
    supervision: bool = False


@dataclass(frozen=True)
class CifrasWhatsmkt:
    cargados: int
    enviados: int
    no_enviados: int


@dataclass(frozen=True)
class ConciliacionWhatsmkt:
    """El resultado de comparar lo cargado con el informe, por conjuntos de numeros.

    Los productos y los registros de supervision van aparte (RF-41). `sin_correspondencia` son los
    numeros del informe que no estan en la carga, sin repetir y en el orden del informe.
    """

    productos: CifrasWhatsmkt
    supervision: CifrasWhatsmkt
    total: CifrasWhatsmkt
    productos_enviados: tuple[FilaCargadaWhatsmkt, ...]
    productos_no_enviados: tuple[FilaCargadaWhatsmkt, ...]
    supervision_enviados: tuple[FilaCargadaWhatsmkt, ...]
    supervision_no_enviados: tuple[FilaCargadaWhatsmkt, ...]
    sin_correspondencia: tuple[str, ...]

    @property
    def total_sin_correspondencia(self) -> int:
        return len(self.sin_correspondencia)
