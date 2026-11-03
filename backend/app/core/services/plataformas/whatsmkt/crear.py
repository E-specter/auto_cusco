"""Crear el lote de campanas de WhatsMKT (RF-WM-05 a 08, 16, 22, 23, 33 a 36; T-WM-B4b1, parte 2).

Se crea el lote COMPLETO o nada. Primero se previsualiza (el mismo calculo, sin rearmar nada) y se
exige que no tenga problemas; luego se validan el horario, la foto, el adjunto y los nombres, y
recien entonces se guarda todo en UNA transaccion. Cada campana congela lo que uso: la version
exacta de la definicion y del texto guardado (la pedida o, sin ella, la vigente al crear), una
copia del texto, la fecha de envio, los horarios con sus horas, el tipo de envio, la foto, el
adjunto, los supervisores y el archivo, que se descarga siempre igual (RF-WM-16).

`fecha_envio` llega SIN validar contra los dias de envio (RF-70): solo sirve para los dias de
atraso ajustados. B4c la valida cuando entre T-HI-B5.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.core.entities.exportacion import ArchivoGenerado
from app.core.entities.whatsmkt import (
    AdjuntoNoEncontrado,
    CodigoWhatsmkt,
    ErrorWhatsmkt,
    Horario,
    TipoEnvio,
)
from app.core.entities.whatsmkt_campana import (
    CampanaNueva,
    FilaNueva,
    HorarioElegido,
    LoteCreado,
    LoteNuevo,
)
from app.core.ports.repositorio_campanas_whatsmkt_port import RepositorioCampanasWhatsmktPort
from app.core.ports.repositorio_whatsmkt_port import RepositorioWhatsmktPort
from app.core.services.plataformas.whatsmkt import nombres
from app.core.services.plataformas.whatsmkt.archivo_contactos import ArchivoContactos
from app.core.services.plataformas.whatsmkt.biblioteca import BibliotecaWhatsmktService
from app.core.services.plataformas.whatsmkt.previa import (
    CampanaPrevista,
    PeticionPrevia,
    PreviaCampanas,
    PrevisualizacionWhatsmktService,
    ProblemaCampana,
)

HORARIOS = ("horario_1", "horario_2")

Exportador = Callable[[ArchivoContactos], ArchivoGenerado]


@dataclass(frozen=True)
class PeticionCreacion:
    """La previsualizacion y lo que se agrega para crear. `filtros` y `orden` son los TEXTOS tal
    como llegaron: es lo que se congela. `nombres` va por clave de segmento (None: la global)."""

    previa: PeticionPrevia
    filtros: tuple[str, ...]
    orden: str | None
    horarios: tuple[str, ...]
    lo_antes_posible: bool = False
    tipo_envio: TipoEnvio = TipoEnvio.SOLO_TEXTO
    foto_id: int | None = None
    adjunto_id: int | None = None
    etiqueta_vcard: str | None = None
    nombres: Mapping[str | None, str] = field(default_factory=dict)


class CreacionInvalida(Exception):
    """El lote no se puede crear: `problemas` los dice todos, cada uno con su codigo."""

    def __init__(self, problemas: tuple[ProblemaCampana, ...]) -> None:
        super().__init__("; ".join(p.detalle for p in problemas))
        self.problemas = problemas


def _problema(error: ErrorWhatsmkt, segmento: str | None = None) -> ProblemaCampana:
    return ProblemaCampana(error.codigo, str(error), segmento, dict(error.parametros))


class CreacionCampanasWhatsmktService:
    def __init__(
        self,
        previa: PrevisualizacionWhatsmktService,
        repositorio: RepositorioWhatsmktPort,
        campanas: RepositorioCampanasWhatsmktPort,
        biblioteca: BibliotecaWhatsmktService,
        exportar: Exportador,
    ) -> None:
        self._previa = previa
        self._repositorio = repositorio
        self._campanas = campanas
        self._biblioteca = biblioteca
        self._exportar = exportar

    def crear(self, peticion: PeticionCreacion) -> LoteCreado:
        """Lanza `CreacionInvalida` si algo impide crear (nada se guarda), `AdjuntoNoEncontrado` si
        la foto o el adjunto no existen, y los errores de la previsualizacion (definicion o texto
        que no existe)."""
        problemas: list[ProblemaCampana] = []
        if not peticion.horarios:
            problemas.append(
                _problema(
                    ErrorWhatsmkt(CodigoWhatsmkt.SIN_HORARIO, "Marca al menos un horario de envio")
                )
            )
        previa = self._previa.previsualizar(peticion.previa)
        problemas += previa.problemas
        problemas += self._problemas_de_la_foto_y_el_adjunto(peticion)
        configuracion = self._repositorio.obtener_configuracion()
        varias = len(previa.campanas) > 1
        nombres_de_campana, problemas_de_nombre = self._nombres(
            peticion, previa, configuracion.plantilla_nombre, varias
        )
        problemas += problemas_de_nombre
        if problemas:
            raise CreacionInvalida(tuple(problemas))

        horarios = tuple(
            HorarioElegido(nombre, *self._horas(configuracion, nombre))
            for nombre in HORARIOS
            if nombre in peticion.horarios
        )
        lote = LoteNuevo(
            modo=peticion.previa.modo,
            campanas=tuple(
                self._nueva(peticion, previa, c, nombre, horarios)
                for c, nombre in zip(previa.campanas, nombres_de_campana, strict=True)
            ),
            exclusiones_sin_campana=previa.exclusiones_sin_campana,
        )
        return self._campanas.crear_lote(lote)

    # --- Validaciones --------------------------------------------------------------------

    def _problemas_de_la_foto_y_el_adjunto(
        self, peticion: PeticionCreacion
    ) -> list[ProblemaCampana]:
        problemas = []
        if peticion.foto_id is not None:
            try:
                self._biblioteca.validar_como_foto(peticion.foto_id)
            except ErrorWhatsmkt as error:
                problemas.append(_problema(error))
        if peticion.tipo_envio is TipoEnvio.ARCHIVO and peticion.adjunto_id is not None:
            adjunto = self._biblioteca.obtener(peticion.adjunto_id)
            if adjunto.archivado_en is not None:
                # Un adjunto archivado ya no se ofrece para campanas nuevas (RF-WM-30).
                raise AdjuntoNoEncontrado(peticion.adjunto_id)
        return problemas

    @staticmethod
    def _nombres(
        peticion: PeticionCreacion, previa: PreviaCampanas, plantilla: str, varias: bool
    ) -> tuple[list[str], list[ProblemaCampana]]:
        validos, problemas = [], []
        fecha_corte = peticion.previa.seleccion.fecha_corte
        for c in previa.campanas:
            clave = None if c.segmento is None else c.segmento.clave
            etiqueta = None if c.segmento is None else c.segmento.etiqueta
            pedido = peticion.nombres.get(clave)
            nombre = pedido or nombres.nombre_de_campana(plantilla, fecha_corte, etiqueta, varias)
            try:
                validos.append(nombres.validar_nombre(nombre))
            except ErrorWhatsmkt as error:
                validos.append(nombre)
                problemas.append(_problema(error, clave))
        return validos, problemas

    @staticmethod
    def _horas(configuracion: Any, nombre: str) -> tuple[Any, Any]:
        horario: Horario = getattr(configuracion, nombre)
        return horario.inicio, horario.fin

    # --- La campana nueva ----------------------------------------------------------------

    def _nueva(
        self,
        peticion: PeticionCreacion,
        previa: PreviaCampanas,
        campana: CampanaPrevista,
        nombre: str,
        horarios: tuple[HorarioElegido, ...],
    ) -> CampanaNueva:
        archivo = campana.archivo
        mensaje = campana.mensaje
        assert mensaje is not None and previa.fecha_envio is not None  # lo exigen los problemas
        cabeceras = archivo.tabla.cabeceras
        return CampanaNueva(
            nombre=nombre,
            segmento=None if campana.segmento is None else campana.segmento.clave,
            segmento_etiqueta=None if campana.segmento is None else campana.segmento.etiqueta,
            definicion_id=previa.definicion_id,
            definicion_nombre=previa.definicion_nombre,
            definicion_version=previa.definicion_version,
            texto_guardado_id=mensaje.texto_id,
            texto_version=mensaje.version,
            mensaje_texto=mensaje.texto,
            whatsapp_contacto=previa.whatsapp_contacto,
            fecha_corte=peticion.previa.seleccion.fecha_corte,
            filtros=peticion.filtros,
            orden=peticion.orden,
            cantidad_pedida=previa.solicitados,
            # shortcut: fecha_envio llega sin validar; B4c la valida con RF-70 cuando entre T-HI-B5
            fecha_envio=previa.fecha_envio,
            horarios=horarios,
            lo_antes_posible=peticion.lo_antes_posible,
            tipo_envio=peticion.tipo_envio,
            foto_id=peticion.foto_id,
            adjunto_id=peticion.adjunto_id,
            etiqueta_vcard=peticion.etiqueta_vcard,
            cantidad=archivo.cantidad,
            productos=archivo.productos,
            supervisores=tuple(
                str(f[cabeceras[0]]) for f in archivo.tabla.filas[: archivo.supervisores]
            ),
            archivo_nombre=nombres.nombre_del_archivo(nombre),
            archivo_contenido=self._exportar(archivo).contenido,
            filas=self._filas(archivo),
            exclusiones=campana.exclusiones,
        )

    @staticmethod
    def _filas(archivo: ArchivoContactos) -> tuple[FilaNueva, ...]:
        """Las filas del archivo en su orden. Los supervisores no tienen pagare."""
        cabeceras = archivo.tabla.cabeceras
        filas = []
        for posicion, fila in enumerate(archivo.tabla.filas, 1):
            supervision = posicion <= archivo.supervisores
            filas.append(
                FilaNueva(
                    posicion=posicion,
                    numero=str(fila[cabeceras[0]]),
                    pagare=None
                    if supervision
                    else archivo.pagares[posicion - archivo.supervisores - 1],
                    supervision=supervision,
                    macros=tuple(None if fila[h] is None else str(fila[h]) for h in cabeceras[1:]),
                )
            )
        return tuple(filas)
