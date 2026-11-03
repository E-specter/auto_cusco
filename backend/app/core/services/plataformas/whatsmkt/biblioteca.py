"""Casos de uso de la biblioteca de adjuntos de WhatsMKT (RF-WM-30 a 32)."""

import hashlib

from app.core.entities.whatsmkt import AdjuntoNoEncontrado, AdjuntoWhatsmkt, TipoAdjunto
from app.core.ports.repositorio_whatsmkt_port import RepositorioWhatsmktPort
from app.core.services.plataformas.whatsmkt import adjuntos

LARGO_MAXIMO_NOMBRE = 255


def nombre_de_archivo(nombre: str | None) -> str:
    """El nombre que el navegador mando, sin la ruta que algunos clientes antiguos incluyen."""
    limpio = (nombre or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    return limpio[:LARGO_MAXIMO_NOMBRE] or "adjunto"


class BibliotecaWhatsmktService:
    def __init__(self, repositorio: RepositorioWhatsmktPort) -> None:
        self._repositorio = repositorio

    def admitir(self, cabecera: bytes, tamano: int, como_foto: bool = False) -> TipoAdjunto | None:
        """El tipo del archivo, comprobado con su cabecera y su tamano ANTES de leerlo entero.

        Como foto (RF-WM-29): JPEG y hasta 1 MB. Si no, el tipo ha de ser conocido y caber en su
        tope (RF-WM-31). Las medidas de la foto se ven despues, con el archivo en la mano.
        """
        tipo = adjuntos.reconocer(cabecera, como_foto)
        if como_foto:
            adjuntos.validar_foto(tipo, tamano)
        else:
            assert tipo is not None  # `reconocer` ya rechazo el desconocido
            adjuntos.revisar_tamano(tipo, tamano, self._repositorio.obtener_configuracion())
        return tipo

    def guardar(
        self, nombre: str | None, contenido: bytes, como_foto: bool = False
    ) -> tuple[AdjuntoWhatsmkt, bool]:
        """Valida, limpia y guarda. Devuelve el adjunto y si ya estaba en la biblioteca.

        La huella se calcula sobre el archivo YA limpio: dos fotos iguales con distinto EXIF son un
        solo adjunto. Vuelve a comprobar tipo y tamano con los bytes reales, por si no coinciden
        con lo declarado.
        """
        tipo = self.admitir(contenido[: adjuntos.LARGO_CABECERA], len(contenido), como_foto)
        assert tipo is not None
        limpio = adjuntos.limpiar(tipo, contenido)
        if como_foto:
            adjuntos.validar_foto(tipo, len(contenido), limpio)
        existente = self._repositorio.buscar_adjunto_por_huella(hashlib.sha256(limpio).hexdigest())
        if existente is not None:
            return existente, True
        guardado = self._repositorio.guardar_adjunto(tipo, nombre_de_archivo(nombre), limpio)
        return guardado, False

    def listar(self, archivados: bool = False) -> list[AdjuntoWhatsmkt]:
        return self._repositorio.listar_adjuntos(archivados)

    def obtener(self, adjunto_id: int) -> AdjuntoWhatsmkt:
        adjunto = self._repositorio.obtener_adjunto(adjunto_id)
        if adjunto is None:
            raise AdjuntoNoEncontrado(adjunto_id)
        return adjunto

    def contenido(self, adjunto_id: int) -> tuple[AdjuntoWhatsmkt, bytes]:
        adjunto = self.obtener(adjunto_id)
        contenido = self._repositorio.leer_contenido_adjunto(adjunto_id)
        if contenido is None:  # lo borraron entre las dos lecturas
            raise AdjuntoNoEncontrado(adjunto_id)
        return adjunto, contenido

    def validar_como_foto(self, adjunto_id: int) -> AdjuntoWhatsmkt:
        """Comprueba que un adjunto ya guardado sirve de foto de perfil (RF-WM-29): JPEG, 200 x 200
        y hasta 1 MB. Lanza `foto_formato`, `foto_peso` o `foto_medidas`; si no existe,
        `AdjuntoNoEncontrado`."""
        adjunto, contenido = self.contenido(adjunto_id)
        adjuntos.validar_foto_de(contenido)
        return adjunto

    def archivar(self, adjunto_id: int) -> AdjuntoWhatsmkt:
        adjunto = self._repositorio.archivar_adjunto(adjunto_id)
        if adjunto is None:
            raise AdjuntoNoEncontrado(adjunto_id)
        return adjunto

    def desarchivar(self, adjunto_id: int) -> AdjuntoWhatsmkt:
        adjunto = self._repositorio.desarchivar_adjunto(adjunto_id)
        if adjunto is None:
            raise AdjuntoNoEncontrado(adjunto_id)
        return adjunto
