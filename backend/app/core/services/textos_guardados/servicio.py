"""Caso de uso: guardar, versionar, renombrar, deshabilitar y eliminar textos (RF-69).

Como las definiciones de columnas (RF-51, RF-56): ninguna version se modifica, un cambio es una
version nueva y la vigente es la ultima; renombrar cambia solo el nombre. El contenido de cada
version lo valida el validador del contexto del texto (`contextos.py`) y todos los problemas se
informan juntos, cada uno con su campo (`nombre` o `contenido`).

Un contexto que no esta registrado se rechaza al listar, crear o versionar; leer un texto ya
guardado, renombrarlo, deshabilitarlo y eliminarlo no necesitan su validador.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.core.entities.texto_enriquecido import CodigoTexto, Problema
from app.core.entities.textos_guardados import (
    LARGO_MAXIMO_NOMBRE,
    ResumenTexto,
    TextoDeshabilitado,
    TextoGuardado,
    TextoNoEncontrado,
    VersionDeTextoNoEncontrada,
    VersionTexto,
)
from app.core.ports.repositorio_textos_guardados_port import RepositorioTextosGuardadosPort
from app.core.services.mapeo_campos.serializacion import ProblemaDeDefinicion
from app.core.services.textos_guardados.contextos import (
    ContextoGuardado,
    RegistroContextosGuardados,
)


class TextoInvalido(Exception):
    """El texto no se puede guardar. `problemas` dice en que campo esta cada falla."""

    def __init__(self, problemas: tuple[ProblemaDeDefinicion, ...]) -> None:
        resumen = "; ".join(p.problema.detalle for p in problemas)
        super().__init__(f"El texto no se puede guardar. {resumen}")
        self.problemas = problemas


@dataclass(frozen=True)
class VistaTexto:
    """El texto y la version que se pidio (la vigente si no se pidio una)."""

    texto: TextoGuardado
    version: VersionTexto


def _problema(detalle: str, campo: str) -> ProblemaDeDefinicion:
    return ProblemaDeDefinicion(
        Problema(CodigoTexto.TEXTO_GUARDADO_INVALIDO, detalle), None, None, campo
    )


class TextosGuardadosService:
    def __init__(
        self, repositorio: RepositorioTextosGuardadosPort, contextos: RegistroContextosGuardados
    ) -> None:
        self._repositorio = repositorio
        self._contextos = contextos

    # --- consulta ---

    def contextos(self) -> tuple[ContextoGuardado, ...]:
        return self._contextos.disponibles()

    def listar(self, contexto: str, incluir_deshabilitados: bool = False) -> list[ResumenTexto]:
        """Los textos del contexto por nombre; los deshabilitados solo si se piden."""
        self._contextos.obtener(contexto)
        return self._repositorio.listar(contexto, incluir_deshabilitados)

    def obtener(self, texto_id: int, numero: int | None = None) -> VistaTexto:
        texto = self._texto(texto_id)
        return VistaTexto(texto, self._version(texto, numero))

    # --- escritura ---

    def crear(self, contexto: str, nombre: Any, contenido: Any) -> VistaTexto:
        """Guarda un texto nuevo (version 1) en el contexto."""
        reglas = self._contextos.obtener(contexto)
        limpio = self._validar(reglas, nombre, contenido)
        texto = self._repositorio.crear(contexto, limpio, dict(contenido))
        return VistaTexto(texto, texto.vigente)

    def agregar_version(self, texto_id: int, contenido: Any) -> VistaTexto:
        """Guarda el contenido como una version nueva, que pasa a ser la vigente."""
        existente = self._texto(texto_id)
        reglas = self._contextos.obtener(existente.contexto)
        if existente.deshabilitado:
            raise TextoDeshabilitado(texto_id)
        self._validar(reglas, None, contenido, con_nombre=False)
        version = self._repositorio.agregar_version(texto_id, dict(contenido))
        if version is None:
            raise TextoNoEncontrado(texto_id)
        return VistaTexto(self._texto(texto_id), version)

    def renombrar(self, texto_id: int, nombre: Any) -> TextoGuardado:
        """Cambia el nombre (RF-56), sin version nueva. Mismo nombre: sin error ni cambios."""
        actual = self._texto(texto_id)
        limpio = self._nombre(nombre)
        if limpio == actual.nombre:
            return actual
        renombrado = self._repositorio.renombrar(texto_id, limpio)
        if renombrado is None:
            raise TextoNoEncontrado(texto_id)
        return renombrado

    def deshabilitar(self, texto_id: int) -> TextoGuardado:
        """Deja de ofrecerlo para lo nuevo; lo que ya lo uso lo sigue leyendo. Es idempotente."""
        texto = self._repositorio.deshabilitar(texto_id)
        if texto is None:
            raise TextoNoEncontrado(texto_id)
        return texto

    def habilitar(self, texto_id: int) -> TextoGuardado:
        """Vuelve a ofrecerlo y admite versiones nuevas otra vez. Es idempotente."""
        texto = self._repositorio.habilitar(texto_id)
        if texto is None:
            raise TextoNoEncontrado(texto_id)
        return texto

    def eliminar(self, texto_id: int) -> None:
        """Lo borra con sus versiones; `TextoConVersionesUsadas` si alguna ya se uso."""
        if not self._repositorio.eliminar(texto_id):
            raise TextoNoEncontrado(texto_id)

    def marcar_usada(self, texto_id: int, numero: int) -> None:
        """Marca la version como usada (la primera vez; despues no cambia)."""
        if not self._repositorio.marcar_version_usada(texto_id, numero):
            raise VersionDeTextoNoEncontrada(texto_id, numero)

    # --- internos ---

    def _texto(self, texto_id: int) -> TextoGuardado:
        texto = self._repositorio.obtener(texto_id)
        if texto is None:
            raise TextoNoEncontrado(texto_id)
        return texto

    @staticmethod
    def _version(texto: TextoGuardado, numero: int | None) -> VersionTexto:
        version = texto.version(numero)
        if version is None:
            raise VersionDeTextoNoEncontrada(texto.id, numero)  # type: ignore[arg-type]
        return version

    @staticmethod
    def _nombre(nombre: Any) -> str:
        limpio = nombre.strip() if isinstance(nombre, str) else ""
        if not 1 <= len(limpio) <= LARGO_MAXIMO_NOMBRE:
            raise TextoInvalido(
                (
                    _problema(
                        f"El nombre debe tener entre 1 y {LARGO_MAXIMO_NOMBRE} caracteres",
                        "nombre",
                    ),
                )
            )
        return limpio

    def _validar(
        self, contexto: ContextoGuardado, nombre: Any, contenido: Any, con_nombre: bool = True
    ) -> str:
        """El nombre limpio (si se pidio) o `TextoInvalido` con todos los problemas juntos."""
        problemas: list[ProblemaDeDefinicion] = []
        limpio = ""
        if con_nombre:
            try:
                limpio = self._nombre(nombre)
            except TextoInvalido as error:
                problemas += error.problemas
        if not isinstance(contenido, Mapping):
            problemas.append(_problema("El contenido es un objeto", "contenido"))
        else:
            problemas += [
                ProblemaDeDefinicion(p, None, None, "contenido")
                for p in contexto.validar(contenido)
            ]
        if problemas:
            raise TextoInvalido(tuple(problemas))
        return limpio
