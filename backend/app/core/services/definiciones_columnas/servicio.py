"""Caso de uso: guardar, versionar y cargar definiciones de columnas (RF-51, RF-46).

Al guardar, la definicion se lee con el mismo lector estricto que usa la previsualizacion y se
valida contra el contexto `cartera` (las definiciones guardadas alimentan `/archivos-carga`): que
las variables y funciones existan, los tipos, los limites de tamano. Todos los problemas se
informan juntos, cada uno con su columna, su variante y su campo (C-2). Lo que se guarda es la
forma canonica, con expresiones (una `plantilla` que llega se convierte) y con la tabla de rangos
resuelta.

Ninguna version se modifica: un cambio es una version nueva (la vigente es la ultima). Renombrar
una definicion (RF-56) cambia solo su nombre: no crea ni toca ninguna version.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.core.entities.contexto_texto import ContextoTexto
from app.core.entities.definiciones_columnas import (
    LARGO_MAXIMO_NOMBRE,
    MAXIMO_COLUMNAS,
    MAXIMO_VARIANTES,
    DefinicionGuardada,
    DefinicionNoEncontrada,
    ResumenDefinicion,
    VersionDefinicion,
    VersionNoEncontrada,
    normalizar_nombre,
)
from app.core.entities.mapeo import DefinicionCarga
from app.core.entities.texto_enriquecido import CodigoTexto, Problema
from app.core.ports.repositorio_definiciones_port import RepositorioDefinicionesPort
from app.core.services.mapeo_campos.diagnostico import diagnosticar_leida
from app.core.services.mapeo_campos.serializacion import (
    DefinicionIlegible,
    DefinicionLeida,
    ProblemaDeDefinicion,
    definicion_a_dict,
    definicion_desde_dict,
)


class DefinicionInvalida(Exception):
    """La definicion no se puede guardar. `problemas` dice donde esta cada falla."""

    def __init__(self, problemas: tuple[ProblemaDeDefinicion, ...]) -> None:
        resumen = "; ".join(p.problema.detalle for p in problemas)
        super().__init__(f"La definicion no se puede guardar. {resumen}")
        self.problemas = problemas


@dataclass(frozen=True)
class VistaDefinicion:
    """La definicion y la version que se pidio (la vigente si no se pidio una)."""

    definicion: DefinicionGuardada
    version: VersionDefinicion


@dataclass(frozen=True)
class DefinicionCargada:
    """Lista para generar una carga: la definicion de columnas y de que version salio."""

    id: int
    numero: int
    nombre: str
    definicion: DefinicionCarga


class DefinicionesColumnasService:
    def __init__(self, repositorio: RepositorioDefinicionesPort, contexto: ContextoTexto) -> None:
        self._repositorio = repositorio
        self._contexto = contexto

    # --- consulta ---

    def listar(self) -> list[ResumenDefinicion]:
        return self._repositorio.listar()

    def obtener(self, definicion_id: int, numero: int | None = None) -> VistaDefinicion:
        guardada = self._guardada(definicion_id)
        return VistaDefinicion(guardada, self._version(guardada, numero))

    def cargar(self, definicion_id: int, numero: int | None = None) -> DefinicionCargada:
        """La definicion lista para `GeneradorCargas`: la version pedida o la vigente."""
        guardada = self._guardada(definicion_id)
        version = self._version(guardada, numero)
        leida = definicion_desde_dict(
            {**version.contenido, "nombre": guardada.nombre},
            self._contexto.tabla_rangos,
            self._contexto.variable_dias,
        )
        return DefinicionCargada(guardada.id, version.numero, guardada.nombre, leida.definicion)

    # --- escritura ---

    def crear(self, dato: Any) -> VistaDefinicion:
        """Guarda una definicion nueva (version 1)."""
        nombre, leida = self._validar(dato, None)
        guardada = self._repositorio.crear(nombre, self._contenido(leida))
        return VistaDefinicion(guardada, guardada.vigente)

    def agregar_version(self, definicion_id: int, dato: Any) -> VistaDefinicion:
        """Guarda la definicion como una version nueva, que pasa a ser la vigente."""
        existente = self._guardada(definicion_id)
        _, leida = self._validar(dato, existente.nombre)
        version = self._repositorio.agregar_version(definicion_id, self._contenido(leida))
        if version is None:
            raise DefinicionNoEncontrada(definicion_id)
        return VistaDefinicion(self._guardada(definicion_id), version)

    def renombrar(self, definicion_id: int, nombre: Any) -> DefinicionGuardada:
        """Cambia el nombre de la definicion (RF-56), sin version nueva.

        El nombre sigue las reglas de siempre: entre 1 y `LARGO_MAXIMO_NOMBRE` caracteres, sin los
        espacios de los extremos, unico sin distinguir mayusculas ni espacios. Dejar el mismo
        nombre no es un error ni cambia nada (tampoco `actualizado_en`: no hubo cambio); cambiar
        solo las mayusculas si es un cambio y lo guarda.
        """
        actual = self._guardada(definicion_id)
        limpio = nombre.strip() if isinstance(nombre, str) else ""
        if not 1 <= len(limpio) <= LARGO_MAXIMO_NOMBRE:
            raise DefinicionInvalida(
                (
                    _problema(
                        CodigoTexto.DEFINICION_INVALIDA,
                        f"El nombre debe tener entre 1 y {LARGO_MAXIMO_NOMBRE} caracteres",
                        campo="nombre",
                    ),
                )
            )
        if limpio == actual.nombre:
            return actual
        renombrada = self._repositorio.renombrar(definicion_id, limpio)
        if renombrada is None:
            raise DefinicionNoEncontrada(definicion_id)
        return renombrada

    def marcar_usada(self, definicion_id: int, numero: int) -> None:
        """Marca la version como usada en una carga (la primera vez; despues no cambia)."""
        if not self._repositorio.marcar_version_usada(definicion_id, numero):
            raise VersionNoEncontrada(definicion_id, numero)

    # --- internos ---

    def _guardada(self, definicion_id: int) -> DefinicionGuardada:
        guardada = self._repositorio.obtener(definicion_id)
        if guardada is None:
            raise DefinicionNoEncontrada(definicion_id)
        return guardada

    @staticmethod
    def _version(guardada: DefinicionGuardada, numero: int | None) -> VersionDefinicion:
        version = guardada.version(numero)
        if version is None:
            raise VersionNoEncontrada(guardada.id, numero)  # type: ignore[arg-type]
        return version

    @staticmethod
    def _contenido(leida: DefinicionLeida) -> Mapping[str, Any]:
        return definicion_a_dict(leida, con_nombre=False)

    def _validar(self, dato: Any, nombre_existente: str | None) -> tuple[str, DefinicionLeida]:
        """El nombre y la definicion leida, o `DefinicionInvalida` con todos los problemas."""
        problemas: list[ProblemaDeDefinicion] = list(_problemas_de_nombre(dato, nombre_existente))
        try:
            leida = definicion_desde_dict(
                dato,
                self._contexto.tabla_rangos,
                self._contexto.variable_dias,
                admitir_plantillas=True,
            )
        except DefinicionIlegible as error:
            raise DefinicionInvalida((*problemas, *error.problemas)) from error
        problemas += _problemas_de_limites(leida)
        problemas += diagnosticar_leida(leida, self._contexto.tipos)
        if problemas:
            raise DefinicionInvalida(tuple(problemas))
        nombre = nombre_existente if nombre_existente is not None else dato["nombre"].strip()
        return nombre, leida


def _problema(
    codigo: CodigoTexto, detalle: str, columna: int | None = None, campo: str | None = None
) -> ProblemaDeDefinicion:
    return ProblemaDeDefinicion(Problema(codigo, detalle), columna, None, campo)


def _problemas_de_nombre(dato: Any, existente: str | None) -> list[ProblemaDeDefinicion]:
    """El nombre de una definicion nueva es obligatorio; el de una version nueva no cambia."""
    nombre = dato.get("nombre") if isinstance(dato, Mapping) else None
    if existente is not None:
        if isinstance(nombre, str) and nombre.strip():
            if normalizar_nombre(nombre) != normalizar_nombre(existente):
                return [
                    _problema(
                        CodigoTexto.DEFINICION_INVALIDA,
                        "El nombre de una definicion no cambia con una version nueva",
                        campo="nombre",
                    )
                ]
        return []
    # Un nombre que no es texto lo informa el lector; aqui, el que falta o no cabe.
    if nombre is None or (
        isinstance(nombre, str) and not 1 <= len(nombre.strip()) <= LARGO_MAXIMO_NOMBRE
    ):
        return [
            _problema(
                CodigoTexto.DEFINICION_INVALIDA,
                f"El nombre debe tener entre 1 y {LARGO_MAXIMO_NOMBRE} caracteres",
                campo="nombre",
            )
        ]
    return []


def _problemas_de_limites(leida: DefinicionLeida) -> list[ProblemaDeDefinicion]:
    campos = leida.definicion.campos
    problemas: list[ProblemaDeDefinicion] = []
    if not campos:
        problemas.append(
            _problema(
                CodigoTexto.DEFINICION_INVALIDA,
                "La definicion necesita al menos una columna",
                campo="columnas",
            )
        )
    if len(campos) > MAXIMO_COLUMNAS:
        problemas.append(
            _problema(
                CodigoTexto.LIMITE_EXCEDIDO,
                f"Una definicion admite hasta {MAXIMO_COLUMNAS} columnas",
                campo="columnas",
            )
        )
    for indice, campo in enumerate(campos):
        if len(campo.variantes) > MAXIMO_VARIANTES:
            problemas.append(
                _problema(
                    CodigoTexto.LIMITE_EXCEDIDO,
                    f"Una columna admite hasta {MAXIMO_VARIANTES} variantes",
                    columna=leida.posiciones[indice],
                    campo="variantes",
                )
            )
    return problemas
