"""Previsualizacion de los archivos de la campana de WhatsMKT, sin guardar nada (RF-WM-35, B4a).

Usa `ArchivoContactosService` (B2) sin rearmar nada y le suma lo que la pantalla necesita para
decidir si deja «Crear»:

- el reparto de las exclusiones por campana (por el segmento del producto);
- `sin_dias_atraso` (RF-WM-20): en un lote por segmento, un producto sin dias de atraso no cae en
  ningun segmento y es una exclusion mas; en modo global no aplica;
- los problemas, que NO son errores 4xx sino una lista: `definicion_no_whatsmkt`,
  `sin_supervisores` y `sin_productos`. La interfaz deja «Crear» inactivo mientras haya alguno.

Con el mensaje (B4b1, parte 1): cada campana puede traer su mensaje elegido, con el ejemplo ya
armado con la primera fila de productos y los problemas del mensaje (`macro_inexistente`,
`mensaje_largo`, `mensaje_con_emoji`, `mensaje_deshabilitado`, `sin_whatsapp`), cada uno con el
segmento al que se refiere. Todavia no valida la fecha de envio ni guarda nada.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

from app.core.entities.textos_guardados import (
    TextoGuardado,
    TextoNoEncontrado,
    VersionDeTextoNoEncontrada,
    VersionTexto,
)
from app.core.entities.whatsmkt import (
    CodigoWhatsmkt,
    ConfiguracionWhatsmkt,
    ErrorWhatsmkt,
    ExclusionContacto,
    ModoCampana,
    SegmentoWhatsmkt,
)
from app.core.ports.repositorio_textos_guardados_port import RepositorioTextosGuardadosPort
from app.core.ports.repositorio_whatsmkt_port import RepositorioWhatsmktPort
from app.core.services.definiciones_columnas.servicio import DefinicionesColumnasService
from app.core.services.gestiones_digitales.servicio import SupervisionService
from app.core.services.plataformas.whatsmkt import mensaje
from app.core.services.plataformas.whatsmkt.archivo_contactos import (
    ArchivoContactos,
    ArchivoContactosService,
    SeleccionCampana,
)
from app.core.services.plataformas.whatsmkt.contexto import CLAVE_CONTEXTO_MENSAJE
from app.core.services.plataformas.whatsmkt.plataforma import CLAVE
from app.core.services.plataformas.whatsmkt.programacion import (
    FechaNoGestionable,
    ProgramacionWhatsmktService,
)


@dataclass(frozen=True)
class MensajePedido:
    """El mensaje elegido: un texto guardado del contexto `whatsmkt.mensaje` y, si se pide una,
    su version (sin ella, la vigente)."""

    texto_id: int
    version: int | None = None


@dataclass(frozen=True)
class PeticionPrevia:
    seleccion: SeleccionCampana
    definicion_id: int
    version: int | None  # sin version, la vigente
    modo: ModoCampana = ModoCampana.GLOBAL
    # En modo global, el mensaje de la unica campana. Sin el, la campana va sin mensaje.
    mensaje: MensajePedido | None = None
    # En modo por segmento, el mensaje de cada segmento por su clave; el que no se nombre usa el
    # de la configuracion del segmento (RF-WM-22), y sin ese tampoco, va sin mensaje.
    mensajes_por_segmento: Mapping[str, MensajePedido] = field(default_factory=dict)


@dataclass(frozen=True)
class ProblemaCampana:
    """Algo que impide crear la campana; la interfaz lo muestra con el texto de su `codigo`.

    `segmento` es la clave del segmento al que se refiere (los del mensaje en un lote por
    segmento); `parametros`, los valores que el texto del codigo nombra (`{macro}`, `{largo}`...).
    """

    codigo: CodigoWhatsmkt
    detalle: str
    segmento: str | None = None
    parametros: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CabeceraPrevia:
    """El encabezado del archivo y, debajo, la etiqueta de la columna (RF-WM-12)."""

    nombre: str
    etiqueta: str | None


@dataclass(frozen=True)
class MensajeDeCampana:
    """El mensaje resuelto de una campana: el texto guardado y la version que se usaran, su texto
    y el ejemplo con la primera fila de productos y el WhatsApp de contacto (RF-WM-27)."""

    texto_id: int
    nombre: str
    version: int
    texto: str
    ejemplo: str
    deshabilitado: bool


@dataclass(frozen=True)
class CampanaPrevista:
    """Una campana que resultara: su segmento (None si es global), su archivo y sus exclusiones."""

    segmento: SegmentoWhatsmkt | None
    archivo: ArchivoContactos
    cabeceras: tuple[CabeceraPrevia, ...]
    exclusiones: tuple[ExclusionContacto, ...]
    mensaje: MensajeDeCampana | None = None


@dataclass(frozen=True)
class PreviaCampanas:
    campanas: tuple[CampanaPrevista, ...]
    # Exclusiones que no pertenecen a ninguna campana: las de un producto sin dias de atraso y las
    # de un segmento que se quedo sin productos.
    exclusiones_sin_campana: tuple[ExclusionContacto, ...]
    problemas: tuple[ProblemaCampana, ...]
    disponibles: int
    solicitados: int
    fecha_envio: date | None
    # Lo que la creacion congela de la definicion y de la configuracion (B4b1, parte 2).
    definicion_id: int = 0
    definicion_nombre: str = ""
    definicion_version: int = 0
    whatsapp_contacto: str | None = None
    # La fecha de envio no es un dia gestionable (RF-70): tambien viaja en `problemas`, y la
    # creacion la usa para responder 409 en vez de 422.
    fecha_no_gestionable: FechaNoGestionable | None = None

    @property
    def total_exclusiones(self) -> int:
        return sum(len(c.exclusiones) for c in self.campanas) + len(self.exclusiones_sin_campana)


def _problema_de_fecha(error: FechaNoGestionable) -> ProblemaCampana:
    return ProblemaCampana(
        CodigoWhatsmkt.FECHA_NO_GESTIONABLE,
        str(error),
        None,
        {"fecha": error.fecha.isoformat(), "sugerida": error.sugerida.isoformat()},
    )


class PrevisualizacionWhatsmktService:
    def __init__(
        self,
        archivos: ArchivoContactosService,
        repositorio: RepositorioWhatsmktPort,
        definiciones: DefinicionesColumnasService,
        supervision: SupervisionService,
        textos: RepositorioTextosGuardadosPort,
        programacion: ProgramacionWhatsmktService,
    ) -> None:
        self._archivos = archivos
        self._repositorio = repositorio
        self._definiciones = definiciones
        self._supervision = supervision
        self._textos = textos
        self._programacion = programacion

    def previsualizar(self, peticion: PeticionPrevia) -> PreviaCampanas:
        """Lanza `DefinicionNoEncontrada` o `VersionNoEncontrada` si la definicion no existe, y
        `TextoNoEncontrado` o `VersionDeTextoNoEncontrada` si un mensaje elegido no existe (o no es
        un mensaje de WhatsMKT)."""
        vista = self._definiciones.obtener(peticion.definicion_id, peticion.version)
        if vista.definicion.plataforma != CLAVE:
            return PreviaCampanas(
                campanas=(),
                exclusiones_sin_campana=(),
                problemas=(
                    ProblemaCampana(
                        CodigoWhatsmkt.DEFINICION_NO_WHATSMKT,
                        f"La definicion {vista.definicion.nombre!r} no es de la plataforma "
                        "WhatsMKT",
                    ),
                ),
                disponibles=0,
                solicitados=peticion.seleccion.cantidad,
                fecha_envio=peticion.seleccion.fecha_envio,
            )
        cargada = self._definiciones.cargar(peticion.definicion_id, vista.version.numero)
        supervision = self._supervision.obtener()
        segmentos = self._repositorio.listar_segmentos()
        por_segmento = peticion.modo is ModoCampana.POR_SEGMENTO
        seleccion = peticion.seleccion
        if seleccion.fecha_envio is None:
            # Sin fecha se sugiere la siguiente gestionable: hoy nunca es un dia de envio.
            seleccion = replace(seleccion, fecha_envio=self._programacion.sugerida())
        armado = self._archivos.armar(
            seleccion,
            cargada.definicion,
            segmentos,
            supervision.supervisores,
            supervision.procedencias,
            por_segmento,
        )
        # RF-WM-20: solo en un lote por segmento un producto sin dias de atraso se excluye.
        exclusiones = sorted(
            [
                *armado.exclusiones,
                *(
                    ExclusionContacto(
                        s.fila,
                        s.pagare,
                        CodigoWhatsmkt.SIN_DIAS_ATRASO,
                        "No tiene dias de atraso, asi que no cae en ningun segmento",
                    )
                    for s in armado.sin_segmento
                ),
            ],
            key=lambda e: e.fila,
        )
        por_clave = {s.clave: s for s in segmentos}
        cabeceras = tuple(CabeceraPrevia(c.nombre, c.etiqueta) for c in cargada.definicion.campos)
        configuracion = self._repositorio.obtener_configuracion()
        campanas = []
        problemas_del_mensaje: list[ProblemaCampana] = []
        for a in armado.archivos:
            segmento = None if a.segmento is None else por_clave[a.segmento]
            resuelto, problemas = self._mensaje(
                self._pedido(peticion, segmento), a, len(cabeceras) - 1, configuracion
            )
            problemas_del_mensaje += problemas
            campanas.append(
                CampanaPrevista(
                    segmento=segmento,
                    archivo=a,
                    cabeceras=cabeceras,
                    exclusiones=tuple(e for e in exclusiones if e.segmento == a.segmento),
                    mensaje=resuelto,
                )
            )
        con_campana = {a.segmento for a in armado.archivos}
        fecha_no_gestionable = self._fecha_no_gestionable(armado.fecha_envio)
        return PreviaCampanas(
            campanas=tuple(campanas),
            exclusiones_sin_campana=tuple(e for e in exclusiones if e.segmento not in con_campana),
            problemas=(
                *self._problemas(bool(supervision.supervisores), bool(campanas)),
                *(
                    ()
                    if fecha_no_gestionable is None
                    else (_problema_de_fecha(fecha_no_gestionable),)
                ),
                *problemas_del_mensaje,
            ),
            disponibles=armado.disponibles,
            solicitados=armado.solicitados,
            fecha_envio=armado.fecha_envio,
            definicion_id=cargada.id,
            definicion_nombre=cargada.nombre,
            definicion_version=cargada.numero,
            whatsapp_contacto=configuracion.whatsapp_contacto,
            fecha_no_gestionable=fecha_no_gestionable,
        )

    def _fecha_no_gestionable(self, fecha_envio: date | None) -> FechaNoGestionable | None:
        if fecha_envio is None:
            return None
        try:
            self._programacion.validar(fecha_envio)
        except FechaNoGestionable as error:
            return error
        return None

    @staticmethod
    def _pedido(
        peticion: PeticionPrevia, segmento: SegmentoWhatsmkt | None
    ) -> MensajePedido | None:
        """El mensaje de la campana: el global, o el pedido para el segmento y, si no, el de su
        configuracion (RF-WM-22)."""
        if segmento is None:
            return peticion.mensaje
        pedido = peticion.mensajes_por_segmento.get(segmento.clave)
        if pedido is None and segmento.texto_guardado_id is not None:
            return MensajePedido(segmento.texto_guardado_id)
        return pedido

    def _mensaje(
        self,
        pedido: MensajePedido | None,
        archivo: ArchivoContactos,
        macros_de_la_definicion: int,
        configuracion: ConfiguracionWhatsmkt,
    ) -> tuple[MensajeDeCampana | None, list[ProblemaCampana]]:
        if pedido is None:
            # WhatsMKT exige el texto: una campana sin mensaje no se crea, y ningun otro
            # problema del mensaje se emite para ella.
            return None, [
                ProblemaCampana(
                    CodigoWhatsmkt.SIN_MENSAJE,
                    "La campana no tiene mensaje: elige uno o configura el del segmento",
                    archivo.segmento,
                )
            ]
        texto, version = self._texto(pedido)
        contenido = version.contenido.get("texto")
        contenido = contenido if isinstance(contenido, str) else ""
        # Las macros del ejemplo son las de la primera fila de PRODUCTOS (despues de los
        # supervisores): la que WhatsMKT mostraria primero.
        primera = archivo.tabla.filas[archivo.supervisores]
        macros = [None if v is None else str(v) for v in list(primera.values())[1:]]
        resuelto = MensajeDeCampana(
            texto_id=texto.id,
            nombre=texto.nombre,
            version=version.numero,
            texto=contenido,
            ejemplo=mensaje.vista(contenido, macros, configuracion.whatsapp_contacto),
            deshabilitado=texto.deshabilitado,
        )
        segmento = archivo.segmento
        problemas = []
        if texto.deshabilitado:
            problemas.append(
                ProblemaCampana(
                    CodigoWhatsmkt.MENSAJE_DESHABILITADO,
                    f"El mensaje {texto.nombre!r} esta deshabilitado",
                    segmento,
                )
            )
        for regla in (
            lambda: mensaje.validar_macros(contenido, macros_de_la_definicion),
            lambda: mensaje.validar_sin_emojis(contenido),
            lambda: mensaje.validar_largo(contenido, configuracion.tope_mensaje),
        ):
            try:
                regla()
            except ErrorWhatsmkt as error:
                problemas.append(
                    ProblemaCampana(error.codigo, str(error), segmento, dict(error.parametros))
                )
        usa_whatsapp = mensaje.marcadores_del_texto(contenido).usa_whatsapp
        if usa_whatsapp and not configuracion.whatsapp_contacto:
            problemas.append(
                ProblemaCampana(
                    CodigoWhatsmkt.SIN_WHATSAPP,
                    "El mensaje usa [whatsapp] y no hay WhatsApp de contacto configurado",
                    segmento,
                )
            )
        return resuelto, problemas

    def _texto(self, pedido: MensajePedido) -> tuple[TextoGuardado, VersionTexto]:
        """El texto y la version pedida (la vigente si no se pidio una). Un texto de otro contexto
        es, para WhatsMKT, un texto que no existe."""
        texto = self._textos.obtener(pedido.texto_id)
        if texto is None or texto.contexto != CLAVE_CONTEXTO_MENSAJE:
            raise TextoNoEncontrado(pedido.texto_id)
        if pedido.version is None:
            return texto, max(texto.versiones, key=lambda v: v.numero)
        version = next((v for v in texto.versiones if v.numero == pedido.version), None)
        if version is None:
            raise VersionDeTextoNoEncontrada(texto.id, pedido.version)
        return texto, version

    @staticmethod
    def _problemas(hay_supervisores: bool, hay_campanas: bool) -> tuple[ProblemaCampana, ...]:
        problemas = []
        if not hay_supervisores:
            problemas.append(
                ProblemaCampana(
                    CodigoWhatsmkt.SIN_SUPERVISORES,
                    "No hay supervisores configurados: sin ellos no se crea la campana",
                )
            )
        if not hay_campanas:
            problemas.append(
                ProblemaCampana(
                    CodigoWhatsmkt.SIN_PRODUCTOS,
                    "Ningun segmento tiene productos despues de las exclusiones: "
                    "no se crea ninguna campana",
                )
            )
        return tuple(problemas)
