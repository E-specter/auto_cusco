"""Generacion de filas de salida a partir de productos y una definicion de carga.

Un error en un campo no detiene la generacion: se registra con su fila y su
campo, y el resto de la carga se sigue construyendo. Asi el usuario ve de una
vez todo lo que hay que corregir.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.core.entities.mapeo import (
    CampoSalida,
    DefinicionCarga,
    ErrorGeneracion,
    PlantillaInvalida,
    ValorNoGenerable,
)
from app.core.services.mapeo_campos import formatos, plantillas


@dataclass(frozen=True)
class CargaGenerada:
    cabeceras: tuple[str, ...]
    filas: tuple[dict[str, Any], ...]
    errores: tuple[ErrorGeneracion, ...]

    @property
    def completa(self) -> bool:
        return not self.errores


class GeneradorCargas:
    """Compila una definicion una vez y la aplica a muchos productos."""

    def __init__(self, definicion: DefinicionCarga, campos_disponibles: Iterable[str]) -> None:
        disponibles = tuple(campos_disponibles)
        self._definicion = definicion
        self._validar_nombres(definicion.campos)
        self._compiladas = {
            campo.nombre: plantillas.compilar(campo.plantilla, disponibles)
            for campo in definicion.campos
        }

    @staticmethod
    def _validar_nombres(campos: Sequence[CampoSalida]) -> None:
        vistos: set[str] = set()
        for campo in campos:
            if not campo.nombre.strip():
                raise PlantillaInvalida("Cada campo de salida necesita un nombre")
            if campo.nombre in vistos:
                raise PlantillaInvalida(f"El campo de salida {campo.nombre!r} esta repetido")
            vistos.add(campo.nombre)
        if not campos:
            raise PlantillaInvalida("La definicion no tiene campos de salida")

    @property
    def cabeceras(self) -> tuple[str, ...]:
        return tuple(campo.nombre for campo in self._definicion.campos)

    def campos_de_origen(self) -> tuple[str, ...]:
        """Campos del producto que la definicion necesita, sin repetir."""
        usados: list[str] = []
        for compilada in self._compiladas.values():
            for campo in compilada.campos:
                if campo not in usados:
                    usados.append(campo)
        return tuple(usados)

    def generar_fila(
        self, producto: Mapping[str, Any], numero_fila: int
    ) -> tuple[dict[str, Any], list[ErrorGeneracion]]:
        fila: dict[str, Any] = {}
        errores: list[ErrorGeneracion] = []
        for campo in self._definicion.campos:
            compilada = self._compiladas[campo.nombre]
            texto = plantillas.aplicar(compilada, producto)
            crudo = plantillas.valor_crudo(compilada, producto)
            try:
                fila[campo.nombre] = formatos.convertir(campo, texto, crudo)
            except ValorNoGenerable as exc:
                fila[campo.nombre] = None
                errores.append(
                    ErrorGeneracion(fila=numero_fila, campo=campo.nombre, detalle=exc.detalle)
                )
        return fila, errores

    def generar(self, productos: Iterable[Mapping[str, Any]]) -> CargaGenerada:
        filas: list[dict[str, Any]] = []
        errores: list[ErrorGeneracion] = []
        for numero_fila, producto in enumerate(productos, start=1):
            fila, errores_fila = self.generar_fila(producto, numero_fila)
            filas.append(fila)
            errores.extend(errores_fila)
        return CargaGenerada(cabeceras=self.cabeceras, filas=tuple(filas), errores=tuple(errores))
