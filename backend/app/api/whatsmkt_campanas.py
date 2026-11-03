"""Campanas de WhatsMKT por HTTP (docs/requerimientos-whatsmkt.md; T-WM-B4a).

Primer corte, la previsualizacion (RF-WM-35):

    POST /whatsmkt/campanas/previsualizacion   los archivos que resultarian, sin guardar nada

Devuelve una campana por archivo (una, o una por segmento con productos), con su cantidad, las
primeras 20 filas, las primeras 100 exclusiones y el total exacto de ellas: la pantalla pagina esas
listas sin volver a calcular (como RF-MM-26). Lo que impide crear (`definicion_no_whatsmkt`,
`sin_supervisores`, `sin_productos`) viaja en `problemas` con un 200, no como error 4xx.

Con el mensaje (B4b1, parte 1): el pedido elige el mensaje y cada campana trae su ejemplo y
los problemas del mensaje. Todavia sin la validacion de la fecha de envio ni las tablas.
"""

from datetime import date, datetime
from typing import Any, Literal, Self

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator, model_validator

from app.adapters.output.exportadores.comunes import disposicion_de_descarga
from app.adapters.output.plataformas.whatsmkt.exportador_contactos import exportar_contactos
from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_campanas_whatsmkt_postgres import (
    RepositorioCampanasWhatsmktPostgres,
)
from app.adapters.persistence.repositorio_textos_guardados_postgres import (
    RepositorioTextosGuardadosPostgres,
)
from app.adapters.persistence.repositorio_whatsmkt_postgres import RepositorioWhatsmktPostgres
from app.api.archivos_carga import RESPUESTAS_ERROR, obtener_servicio_generacion
from app.api.cartera import obtener_catalogo_cartera
from app.api.consultas import parsear_filtro, parsear_orden
from app.api.definiciones_columnas import obtener_servicio_definiciones
from app.api.errores import (
    ErrorConCodigo,
    respuestas_de_error,
    respuestas_de_error_con_codigo,
)
from app.api.fecha_envio import error_de_fecha_envio
from app.api.respuestas import ModeloRespuesta
from app.api.supervisores import obtener_servicio_supervision
from app.api.whatsmkt import PARAMETROS, ErrorWhatsmktRespuesta
from app.core.entities.cartera import ConsultaInvalida, SinVersionVigente
from app.core.entities.definiciones_columnas import DefinicionNoEncontrada, VersionNoEncontrada
from app.core.entities.exportacion import TIPOS_MIME, FormatoArchivo
from app.core.entities.mapeo import PlantillaInvalida
from app.core.entities.texto_enriquecido import CodigoTexto
from app.core.entities.textos_guardados import TextoNoEncontrado, VersionDeTextoNoEncontrada
from app.core.entities.whatsmkt import (
    CLAVES_SEGMENTOS,
    AdjuntoNoEncontrado,
    CodigoWhatsmkt,
    ModoCampana,
    TipoEnvio,
)
from app.core.entities.whatsmkt_campana import (
    CampanaNoEncontrada,
    CampanaWhatsmkt,
    EstadoCampana,
    PaginaExclusiones,
)
from app.core.services.definiciones_columnas.servicio import DefinicionesColumnasService
from app.core.services.fecha_envio import FechaEnvioAnterior
from app.core.services.generacion_cargas.servicio import (
    CANTIDAD_MAXIMA,
    GeneracionCargasService,
)
from app.core.services.gestiones_digitales.servicio import SupervisionService
from app.core.services.plataformas.whatsmkt.archivo_contactos import (
    ArchivoContactosService,
    ExclusionContacto,
    SeleccionCampana,
)
from app.core.services.plataformas.whatsmkt.biblioteca import BibliotecaWhatsmktService
from app.core.services.plataformas.whatsmkt.consulta import (
    ConsultaCampanasWhatsmktService,
    DetalleCampana,
    Paginacion,
)
from app.core.services.plataformas.whatsmkt.crear import (
    CreacionCampanasWhatsmktService,
    CreacionInvalida,
    PeticionCreacion,
)
from app.core.services.plataformas.whatsmkt.ficha import FichaCampana, ficha_de
from app.core.services.plataformas.whatsmkt.previa import (
    CampanaPrevista,
    MensajePedido,
    PeticionPrevia,
    PreviaCampanas,
    PrevisualizacionWhatsmktService,
)
from app.core.services.seleccion_cartera.campos import CatalogoCartera

router = APIRouter(prefix="/whatsmkt/campanas", tags=["whatsmkt"])

FILAS_DE_MUESTRA = 20
EXCLUSIONES_EN_PREVIA = 100


def obtener_servicio_previa_whatsmkt(
    generacion: GeneracionCargasService = Depends(obtener_servicio_generacion),
    definiciones: DefinicionesColumnasService = Depends(obtener_servicio_definiciones),
    supervision: SupervisionService = Depends(obtener_servicio_supervision),
) -> PrevisualizacionWhatsmktService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return PrevisualizacionWhatsmktService(
        ArchivoContactosService(generacion),
        RepositorioWhatsmktPostgres(get_engine()),
        definiciones,
        supervision,
        RepositorioTextosGuardadosPostgres(get_engine()),
    )


class DefinicionWhatsmktEntrada(BaseModel):
    """Una definicion de `/definiciones-columnas`: la version pedida o, sin ella, la vigente."""

    id: int
    version: int | None = Field(default=None, ge=1)


class MensajeWhatsmktEntrada(BaseModel):
    """Un mensaje: un texto guardado del contexto `whatsmkt.mensaje` y, sin version, la vigente."""

    texto_guardado_id: int
    version: int | None = Field(default=None, ge=1)

    def pedido(self) -> MensajePedido:
        return MensajePedido(self.texto_guardado_id, self.version)


class PrevisualizacionCampanasWhatsmktEntrada(BaseModel):
    fecha_corte: date
    filtros: list[str] = []
    orden: str | None = None
    cantidad: int = Field(ge=1, le=CANTIDAD_MAXIMA)
    seleccion_id: int | None = Field(
        default=None, description="Referencia informativa a la seleccion guardada de origen"
    )
    definicion: DefinicionWhatsmktEntrada
    modo: ModoCampana = ModoCampana.GLOBAL
    fecha_envio: date | None = Field(
        default=None,
        description=(
            "Fecha de envio, solo para los dias de atraso ajustados (RF-55); sin ella, hoy en "
            "America/Lima. Todavia SIN validar contra los dias de envio (RF-70): eso llega con "
            "el mensaje"
        ),
    )

    mensaje: MensajeWhatsmktEntrada | None = Field(
        default=None,
        description=(
            "El mensaje de la unica campana en modo `global`. Sin el, la campana va sin mensaje; "
            "en modo `por_segmento` no se usa"
        ),
    )
    mensajes: dict[str, MensajeWhatsmktEntrada] | None = Field(
        default=None,
        description=(
            "En modo `por_segmento`, el mensaje de cada segmento por su clave. El segmento que no "
            "se nombra usa el de la configuracion (RF-WM-22); sin ese tampoco, va sin mensaje"
        ),
    )

    @field_validator("mensajes")
    @classmethod
    def _claves_de_segmento(cls, mensajes):
        desconocidas = sorted(set(mensajes or {}) - CLAVES_SEGMENTOS)
        if desconocidas:
            raise ValueError(f"Segmentos desconocidos: {', '.join(desconocidas)}")
        return mensajes

    def a_peticion_previa(self, catalogo: CatalogoCartera) -> PeticionPrevia:
        return PeticionPrevia(
            seleccion=self.seleccion(catalogo),
            definicion_id=self.definicion.id,
            version=self.definicion.version,
            modo=self.modo,
            mensaje=None if self.mensaje is None else self.mensaje.pedido(),
            mensajes_por_segmento={clave: m.pedido() for clave, m in (self.mensajes or {}).items()},
        )

    def seleccion(self, catalogo: CatalogoCartera) -> SeleccionCampana:
        return SeleccionCampana(
            fecha_corte=self.fecha_corte,
            # shortcut: fecha_envio llega sin validar; B4b la valida con RF-70 cuando entre T-HI-B5
            fecha_envio=self.fecha_envio,
            filtros=[parsear_filtro(crudo, catalogo) for crudo in self.filtros],
            orden=parsear_orden(self.orden),
            cantidad=self.cantidad,
        )


class CabeceraWhatsmktRespuesta(ModeloRespuesta):
    nombre: str = Field(description="El encabezado del archivo")
    etiqueta: str | None = Field(description="La etiqueta de la columna; no sale en el archivo")


class FilaMuestraWhatsmktRespuesta(ModeloRespuesta):
    supervision: bool = Field(description="Una fila de supervision (van antes de los productos)")
    celdas: list[str | None] = Field(description="Un valor por cabecera, en el mismo orden")


class ExclusionWhatsmktRespuesta(ModeloRespuesta):
    codigo: CodigoWhatsmkt
    fila: int = Field(description="Posicion del producto entre los que genero la seleccion")
    pagare: str | None
    detalle: str
    macro: int | None = Field(description="macro_vacia: el numero de la macro (1 es la segunda)")
    etiqueta: str | None = Field(description="macro_vacia: la etiqueta de la columna")


class MensajeCampanaWhatsmktRespuesta(ModeloRespuesta):
    texto_guardado_id: int
    nombre: str
    version: int = Field(description="La version que se usara: la pedida o la vigente")
    deshabilitado: bool


class CampanaPrevistaWhatsmktRespuesta(ModeloRespuesta):
    segmento: str | None = Field(description="La clave del segmento; null en una campana global")
    etiqueta_segmento: str | None
    cantidad: int = Field(description="Filas del archivo, supervisores incluidos (S-WM-4)")
    productos: int
    supervisores: int
    cabeceras: list[CabeceraWhatsmktRespuesta]
    total_exclusiones: int
    exclusiones: list[ExclusionWhatsmktRespuesta] = Field(
        description=f"Las primeras {EXCLUSIONES_EN_PREVIA}; el total esta en `total_exclusiones`"
    )
    muestra: list[FilaMuestraWhatsmktRespuesta] = Field(
        description=f"Las primeras {FILAS_DE_MUESTRA} filas del archivo"
    )
    mensaje: MensajeCampanaWhatsmktRespuesta | None = Field(
        description="El mensaje elegido para esta campana; null si no se eligio ninguno"
    )
    mensaje_ejemplo: str | None = Field(
        description=(
            "El mensaje con las macros de la primera fila de productos y el WhatsApp de "
            "contacto (RF-WM-27); null sin mensaje"
        )
    )


class ProblemaWhatsmktRespuesta(ModeloRespuesta):
    codigo: CodigoWhatsmkt
    detalle: str
    segmento: str | None = Field(
        description="La clave del segmento al que se refiere (los del mensaje en un lote)"
    )
    parametros: dict[str, str | int] = Field(
        description="Los valores que el texto del codigo nombra: macro, n, largo, maximo..."
    )


class PrevisualizacionCampanasWhatsmktRespuesta(ModeloRespuesta):
    campanas: list[CampanaPrevistaWhatsmktRespuesta]
    problemas: list[ProblemaWhatsmktRespuesta] = Field(
        description="Lo que impide crear; con alguno, la pantalla deja «Crear» inactivo"
    )
    disponibles: int = Field(description="Productos de la seleccion completa (RF-08)")
    solicitados: int
    total_exclusiones: int = Field(description="Todas, incluidas las que no son de una campana")
    total_exclusiones_sin_campana: int
    exclusiones_sin_campana: list[ExclusionWhatsmktRespuesta] = Field(
        description=(
            "Exclusiones que no son de ninguna campana: un producto sin dias de atraso, o de un "
            f"segmento que se quedo sin productos. Las primeras {EXCLUSIONES_EN_PREVIA}"
        )
    )


def _texto(valor: Any) -> str | None:
    return None if valor is None else str(valor)


def _exclusion(e: ExclusionContacto) -> ExclusionWhatsmktRespuesta:
    return ExclusionWhatsmktRespuesta(
        codigo=e.codigo,
        fila=e.fila,
        pagare=e.pagare,
        detalle=e.detalle,
        macro=e.macro,
        etiqueta=e.etiqueta,
    )


def _campana(c: CampanaPrevista) -> CampanaPrevistaWhatsmktRespuesta:
    archivo = c.archivo
    cabeceras = archivo.tabla.cabeceras
    return CampanaPrevistaWhatsmktRespuesta(
        segmento=None if c.segmento is None else c.segmento.clave,
        etiqueta_segmento=None if c.segmento is None else c.segmento.etiqueta,
        cantidad=archivo.cantidad,
        productos=archivo.productos,
        supervisores=archivo.supervisores,
        cabeceras=[
            CabeceraWhatsmktRespuesta(nombre=h.nombre, etiqueta=h.etiqueta) for h in c.cabeceras
        ],
        total_exclusiones=len(c.exclusiones),
        exclusiones=[_exclusion(e) for e in c.exclusiones[:EXCLUSIONES_EN_PREVIA]],
        muestra=[
            FilaMuestraWhatsmktRespuesta(
                supervision=indice < archivo.supervisores,
                celdas=[_texto(fila[h]) for h in cabeceras],
            )
            for indice, fila in enumerate(archivo.tabla.filas[:FILAS_DE_MUESTRA])
        ],
        mensaje=None
        if c.mensaje is None
        else MensajeCampanaWhatsmktRespuesta(
            texto_guardado_id=c.mensaje.texto_id,
            nombre=c.mensaje.nombre,
            version=c.mensaje.version,
            deshabilitado=c.mensaje.deshabilitado,
        ),
        mensaje_ejemplo=None if c.mensaje is None else c.mensaje.ejemplo,
    )


def _respuesta(previa: PreviaCampanas) -> PrevisualizacionCampanasWhatsmktRespuesta:
    return PrevisualizacionCampanasWhatsmktRespuesta(
        campanas=[_campana(c) for c in previa.campanas],
        problemas=[
            ProblemaWhatsmktRespuesta(
                codigo=p.codigo,
                detalle=p.detalle,
                segmento=p.segmento,
                parametros=dict(p.parametros),
            )
            for p in previa.problemas
        ],
        disponibles=previa.disponibles,
        solicitados=previa.solicitados,
        total_exclusiones=previa.total_exclusiones,
        total_exclusiones_sin_campana=len(previa.exclusiones_sin_campana),
        exclusiones_sin_campana=[
            _exclusion(e) for e in previa.exclusiones_sin_campana[:EXCLUSIONES_EN_PREVIA]
        ],
    )


def _error(exc: Exception) -> ErrorConCodigo:
    if isinstance(exc, DefinicionNoEncontrada):
        return ErrorConCodigo(404, str(exc), CodigoTexto.DEFINICION_NO_ENCONTRADA)
    if isinstance(exc, VersionNoEncontrada):
        return ErrorConCodigo(404, str(exc), CodigoTexto.VERSION_NO_ENCONTRADA)
    if isinstance(exc, TextoNoEncontrado):
        return ErrorConCodigo(404, str(exc), CodigoTexto.TEXTO_GUARDADO_NO_ENCONTRADO)
    if isinstance(exc, VersionDeTextoNoEncontrada):
        return ErrorConCodigo(404, str(exc), CodigoTexto.VERSION_NO_ENCONTRADA)
    if isinstance(exc, AdjuntoNoEncontrado):
        return ErrorConCodigo(404, str(exc), None)
    if isinstance(exc, SinVersionVigente):
        return ErrorConCodigo(404, str(exc), CodigoTexto.SIN_VERSION_VIGENTE)
    if isinstance(exc, FechaEnvioAnterior):
        return error_de_fecha_envio(exc)
    return ErrorConCodigo(400, str(exc), None)


@router.post(
    "/previsualizacion",
    summary="Previsualizar los archivos de la campana",
    response_model=PrevisualizacionCampanasWhatsmktRespuesta,
    responses=RESPUESTAS_ERROR,
)
def previsualizar_campanas(
    entrada: PrevisualizacionCampanasWhatsmktEntrada,
    servicio: PrevisualizacionWhatsmktService = Depends(obtener_servicio_previa_whatsmkt),
    catalogo: CatalogoCartera = Depends(obtener_catalogo_cartera),
) -> PrevisualizacionCampanasWhatsmktRespuesta:
    """Los archivos que resultarian de la seleccion, sin guardar nada (RF-WM-35).

    En modo `por_segmento` sale una campana por cada segmento con productos (RF-WM-23); en
    `global`, una. Los problemas (`definicion_no_whatsmkt`, `sin_supervisores`, `sin_productos`
    y los del mensaje: `macro_inexistente`, `mensaje_largo`, `mensaje_con_emoji`,
    `mensaje_deshabilitado`, `sin_whatsapp`) se listan con un 200: no impiden previsualizar,
    impiden crear. Un mensaje elegido que no existe, o no es de WhatsMKT, responde 404.
    """
    try:
        previa = servicio.previsualizar(entrada.a_peticion_previa(catalogo))
    except (
        ConsultaInvalida,
        PlantillaInvalida,
        SinVersionVigente,
        DefinicionNoEncontrada,
        VersionNoEncontrada,
        TextoNoEncontrado,
        VersionDeTextoNoEncontrada,
        FechaEnvioAnterior,
    ) as exc:
        raise _error(exc) from exc
    return _respuesta(previa)


# --- Crear el lote (B4b1, parte 2) ------------------------------------------------------------


class CreacionCampanasWhatsmktEntrada(PrevisualizacionCampanasWhatsmktEntrada):
    """La previsualizacion mas lo que se agrega para crear. `fecha_envio` llega SIN validar contra
    los dias de envio (RF-70); la validacion llega con B4c."""

    horarios: list[Literal["horario_1", "horario_2"]] = Field(
        default=[],
        description=(
            "Los horarios de envio elegidos (RF-WM-07). Vacio responde 422 con `sin_horario`"
        ),
    )
    lo_antes_posible: bool = Field(
        default=False, description="Solo se guarda y se copia en la ficha (RF-WM-08)"
    )
    tipo_envio: TipoEnvio = TipoEnvio.SOLO_TEXTO
    foto_id: int | None = Field(
        default=None,
        description="Un adjunto de la biblioteca que sirva de foto de perfil (RF-WM-29); opcional",
    )
    adjunto_id: int | None = Field(
        default=None, description="Con `tipo_envio=archivo`: el adjunto de la biblioteca"
    )
    etiqueta_vcard: str | None = Field(
        default=None, max_length=100, description="Con `tipo_envio=vcard`: la etiqueta del contacto"
    )
    nombre: str | None = Field(
        default=None,
        max_length=500,
        description="El nombre de la campana global; sin el, sale de la plantilla (RF-WM-33)",
    )
    nombres: dict[str, str] | None = Field(
        default=None,
        description="El nombre de cada campana por clave de segmento; sin el, sale de la plantilla",
    )

    @model_validator(mode="after")
    def _los_campos_del_tipo(self) -> Self:
        if self.tipo_envio is TipoEnvio.ARCHIVO and self.adjunto_id is None:
            raise ValueError("`adjunto_id` es obligatorio con `tipo_envio=archivo`")
        if self.tipo_envio is TipoEnvio.VCARD and not (self.etiqueta_vcard or "").strip():
            raise ValueError("`etiqueta_vcard` es obligatoria con `tipo_envio=vcard`")
        return self

    def a_peticion_de_creacion(self, catalogo: CatalogoCartera) -> PeticionCreacion:
        # Solo se manda lo del tipo elegido: lo escrito en los otros se descarta.
        archivo = self.tipo_envio is TipoEnvio.ARCHIVO
        vcard = self.tipo_envio is TipoEnvio.VCARD
        return PeticionCreacion(
            previa=self.a_peticion_previa(catalogo),
            filtros=tuple(self.filtros),
            orden=self.orden,
            horarios=tuple(self.horarios),
            lo_antes_posible=self.lo_antes_posible,
            tipo_envio=self.tipo_envio,
            foto_id=self.foto_id,
            adjunto_id=self.adjunto_id if archivo else None,
            etiqueta_vcard=(self.etiqueta_vcard or "").strip() if vcard else None,
            nombres={
                **({None: self.nombre.strip()} if self.nombre and self.nombre.strip() else {}),
                **{k: v.strip() for k, v in (self.nombres or {}).items() if v.strip()},
            },
        )


class HorarioCampanaWhatsmktRespuesta(ModeloRespuesta):
    nombre: str = Field(description="horario_1 u horario_2")
    inicio: str = Field(description="HH:MM")
    fin: str = Field(description="HH:MM")


class ArchivoCampanaWhatsmktRespuesta(ModeloRespuesta):
    nombre: str = Field(description="El nombre de la campana mas .xlsx")
    tamano: int = Field(description="Bytes")
    filas: int = Field(description="Filas del archivo, supervisores incluidos (S-WM-4)")


class FichaWhatsmktRespuesta(ModeloRespuesta):
    """Cada dato del formulario de WhatsMKT, listo para copiar (RF-WM-36)."""

    nombre: str
    fecha_envio: date
    horarios: list[HorarioCampanaWhatsmktRespuesta]
    lo_antes_posible: bool
    pais: str
    foto_id: int | None = Field(description="La foto de perfil, para descargar de la biblioteca")
    cantidad: int = Field(description="¿Cuantos telefonos tiene su Lista de contactos?")
    tipo_envio: TipoEnvio
    adjunto_id: int | None
    etiqueta_vcard: str | None
    mensaje: str = Field(
        description=(
            "Texto para copiar: [whatsapp] ya es el enlace (con el numero VIGENTE al leer) y las "
            "[$MACROn$] quedan tal cual"
        )
    )
    avisos: list[CodigoWhatsmkt] = Field(
        description=(
            "`sin_whatsapp`: el mensaje usa [whatsapp] y no hay WhatsApp de contacto configurado; "
            "el marcador queda sin reemplazar"
        )
    )


class CampanaCreadaWhatsmktRespuesta(ModeloRespuesta):
    id: int
    lote_id: int
    nombre: str
    segmento: str | None
    archivo: ArchivoCampanaWhatsmktRespuesta
    ficha: FichaWhatsmktRespuesta


class ErrorCreacionWhatsmktRespuesta(ErrorWhatsmktRespuesta):
    """422 al crear: `codigo` y sus parametros son los del PRIMER problema; `problemas` los trae
    todos (la campana no se crea mientras haya alguno)."""

    problemas: list[ProblemaWhatsmktRespuesta]


def _horarios(horarios) -> list[HorarioCampanaWhatsmktRespuesta]:
    return [
        HorarioCampanaWhatsmktRespuesta(
            nombre=h.nombre, inicio=h.inicio.strftime("%H:%M"), fin=h.fin.strftime("%H:%M")
        )
        for h in horarios
    ]


def _ficha(c: CampanaWhatsmkt, whatsapp_vigente: str | None) -> FichaWhatsmktRespuesta:
    return _respuesta_de_ficha(ficha_de(c, whatsapp_vigente))


def _respuesta_de_ficha(f: FichaCampana) -> FichaWhatsmktRespuesta:
    return FichaWhatsmktRespuesta(
        nombre=f.nombre,
        fecha_envio=f.fecha_envio,
        horarios=_horarios(f.horarios),
        lo_antes_posible=f.lo_antes_posible,
        pais=f.pais,
        foto_id=f.foto_id,
        cantidad=f.cantidad,
        tipo_envio=f.tipo_envio,
        adjunto_id=f.adjunto_id,
        etiqueta_vcard=f.etiqueta_vcard,
        mensaje=f.mensaje,
        avisos=list(f.avisos),
    )


def _campana_creada(c: CampanaWhatsmkt) -> CampanaCreadaWhatsmktRespuesta:
    return CampanaCreadaWhatsmktRespuesta(
        id=c.id,
        lote_id=c.lote_id,
        nombre=c.nombre,
        segmento=c.segmento,
        archivo=ArchivoCampanaWhatsmktRespuesta(
            nombre=c.archivo_nombre, tamano=c.archivo_tamano, filas=c.cantidad
        ),
        ficha=_ficha(c, c.whatsapp_contacto),  # al crear, el vigente es el que se congelo
    )


def _creacion_invalida(exc: CreacionInvalida) -> ErrorConCodigo:
    primero = exc.problemas[0]
    parametros = {campo: None for campo in PARAMETROS} | dict(primero.parametros)
    return ErrorConCodigo(
        422,
        str(exc),
        primero.codigo,
        {
            **parametros,
            "problemas": [
                {
                    "codigo": p.codigo.value,
                    "detalle": p.detalle,
                    "segmento": p.segmento,
                    "parametros": dict(p.parametros),
                }
                for p in exc.problemas
            ],
        },
    )


def obtener_servicio_creacion_whatsmkt(
    previa: PrevisualizacionWhatsmktService = Depends(obtener_servicio_previa_whatsmkt),
) -> CreacionCampanasWhatsmktService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    repositorio = RepositorioWhatsmktPostgres(get_engine())
    return CreacionCampanasWhatsmktService(
        previa,
        repositorio,
        RepositorioCampanasWhatsmktPostgres(get_engine()),
        BibliotecaWhatsmktService(repositorio),
        exportar_contactos,
    )


def obtener_repositorio_campanas_whatsmkt() -> RepositorioCampanasWhatsmktPostgres:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return RepositorioCampanasWhatsmktPostgres(get_engine())


@router.post(
    "",
    status_code=201,
    summary="Crear el lote de campanas",
    response_model=list[CampanaCreadaWhatsmktRespuesta],
    responses={
        **RESPUESTAS_ERROR,
        422: {
            "model": ErrorCreacionWhatsmktRespuesta,
            "description": (
                "Algo impide crear (nada se guarda): `codigo` es el del primero y `problemas` los "
                "trae todos"
            ),
        },
    },
)
def crear_campanas(
    entrada: CreacionCampanasWhatsmktEntrada,
    servicio: CreacionCampanasWhatsmktService = Depends(obtener_servicio_creacion_whatsmkt),
    catalogo: CatalogoCartera = Depends(obtener_catalogo_cartera),
) -> list[CampanaCreadaWhatsmktRespuesta]:
    """Crea el LOTE completo o nada, en una sola transaccion (RF-WM-23): una campana en modo
    `global`, o una por segmento con productos. Cada una congela la version exacta del mensaje y de
    la definicion (la pedida o, sin ella, la vigente), el archivo, los horarios y los supervisores.

    Responde 201 con cada campana (id, nombre, archivo y la ficha de RF-WM-36). Si algo impide
    crear (sin horario, sin supervisores, sin mensaje, un problema del mensaje, la foto, un nombre
    de mas de 75 caracteres...) responde 422 con todos los problemas y no guarda nada.
    """
    try:
        lote = servicio.crear(entrada.a_peticion_de_creacion(catalogo))
    except CreacionInvalida as exc:
        raise _creacion_invalida(exc) from exc
    except AdjuntoNoEncontrado as exc:
        raise ErrorConCodigo(404, str(exc), None) from exc
    except (
        ConsultaInvalida,
        PlantillaInvalida,
        SinVersionVigente,
        DefinicionNoEncontrada,
        VersionNoEncontrada,
        TextoNoEncontrado,
        VersionDeTextoNoEncontrada,
        FechaEnvioAnterior,
    ) as exc:
        raise _error(exc) from exc
    return [_campana_creada(c) for c in lote.campanas]


@router.get(
    "/{campana_id}/archivo",
    summary="Descargar el archivo de contactos de la campana",
    response_class=Response,
    responses={
        200: {
            "description": "Los bytes guardados al crear la campana, siempre los mismos",
            "content": {
                TIPOS_MIME[FormatoArchivo.XLSX]: {"schema": {"type": "string", "format": "binary"}}
            },
            "headers": {
                "Content-Disposition": {
                    "description": (
                        'attachment; filename="<nombre en ASCII>"; '
                        "filename*=UTF-8''<nombre exacto> (RFC 5987)"
                    ),
                    "schema": {"type": "string"},
                }
            },
        },
        **respuestas_de_error(404),
    },
)
def descargar_archivo_de_la_campana(
    campana_id: int,
    repositorio: RepositorioCampanasWhatsmktPostgres = Depends(
        obtener_repositorio_campanas_whatsmkt
    ),
) -> Response:
    archivo = repositorio.obtener_archivo(campana_id)
    if archivo is None:
        raise HTTPException(404, str(CampanaNoEncontrada(campana_id)))
    return Response(
        content=archivo.contenido,
        media_type=TIPOS_MIME[FormatoArchivo.XLSX],
        headers={"Content-Disposition": disposicion_de_descarga(archivo.nombre)},
    )


# --- Leer: la lista y el detalle (T-WM-B4b1, parte 3; RF-WM-36 y RF-WM-40) --------------------

EXCLUSIONES_POR_PAGINA = 100  # como la previsualizacion
_MES = r"^\d{4}-(0[1-9]|1[0-2])$"


class ResumenCampanaWhatsmktRespuesta(ModeloRespuesta):
    id: int
    nombre: str
    lote_id: int
    segmento: str | None = Field(description="La clave del segmento; nula en el modo global")
    segmento_etiqueta: str | None
    fecha_envio: date
    horarios: list[HorarioCampanaWhatsmktRespuesta]
    cantidad: int = Field(description="Filas del archivo, supervisores incluidos")
    creada_en: datetime
    descartada_en: datetime | None = Field(
        description="Cuando se descarto; nula en una activa (RF-WM-41)"
    )
    con_informe: bool = Field(
        description="Si tiene el informe de WhatsMKT importado; las activas sin el estan pendientes"
    )


class ListaCampanasWhatsmktRespuesta(ModeloRespuesta):
    total: int = Field(description="De todas las que cumplen los filtros, no solo de esta pagina")
    limite: int
    desplazamiento: int
    campanas: list[ResumenCampanaWhatsmktRespuesta]
    total_activas: int = Field(description="De todas las campanas, sin los filtros")
    total_descartadas: int = Field(description="De todas las campanas, sin los filtros")
    total_pendientes: int = Field(
        description="De todas las activas, sin los filtros: las que no tienen informe (RF-WM-40)"
    )


class LoteWhatsmktRespuesta(ModeloRespuesta):
    id: int = Field(description="El numero del lote")
    modo: ModoCampana


class PaginaExclusionesWhatsmktRespuesta(ModeloRespuesta):
    total: int
    limite: int
    desplazamiento: int
    exclusiones: list[ExclusionWhatsmktRespuesta]


class DetalleCampanaWhatsmktRespuesta(ResumenCampanaWhatsmktRespuesta):
    lote: LoteWhatsmktRespuesta
    fecha_corte: date
    productos: int = Field(description="Productos cargados, sin la supervision")
    supervisores: int = Field(description="Cuantos supervisores van en el archivo")
    definicion_nombre: str
    definicion_version: int
    texto_version: int
    archivo: ArchivoCampanaWhatsmktRespuesta
    ficha: FichaWhatsmktRespuesta
    exclusiones: PaginaExclusionesWhatsmktRespuesta = Field(
        description="Las exclusiones de ESTA campana, paginadas"
    )
    exclusiones_fuera_del_lote: PaginaExclusionesWhatsmktRespuesta = Field(
        description=(
            "Los productos del lote que no cayeron en ninguna campana: se ven desde cualquiera "
            "del lote. Su `total` es el total de exclusiones fuera del lote; en un lote global "
            "es cero y la lista, vacia"
        )
    )


def obtener_servicio_consulta_whatsmkt() -> ConsultaCampanasWhatsmktService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return ConsultaCampanasWhatsmktService(
        RepositorioCampanasWhatsmktPostgres(get_engine()),
        RepositorioWhatsmktPostgres(get_engine()),
    )


def _resumen(c: CampanaWhatsmkt) -> dict[str, Any]:
    return {
        "id": c.id,
        "nombre": c.nombre,
        "lote_id": c.lote_id,
        "segmento": c.segmento,
        "segmento_etiqueta": c.segmento_etiqueta,
        "fecha_envio": c.fecha_envio,
        "horarios": _horarios(c.horarios),
        "cantidad": c.cantidad,
        "creada_en": c.creado_en,
        "descartada_en": c.descartada_en,
        "con_informe": c.con_informe,
    }


def respuesta_resumen(c: CampanaWhatsmkt) -> ResumenCampanaWhatsmktRespuesta:
    return ResumenCampanaWhatsmktRespuesta(**_resumen(c))


def _pagina_de_exclusiones(
    pagina: PaginaExclusiones, paginacion: Paginacion
) -> PaginaExclusionesWhatsmktRespuesta:
    return PaginaExclusionesWhatsmktRespuesta(
        total=pagina.total,
        limite=paginacion.limite,
        desplazamiento=paginacion.desplazamiento,
        exclusiones=[
            ExclusionWhatsmktRespuesta(
                codigo=e.codigo,
                fila=e.fila,
                pagare=e.pagare,
                detalle=e.detalle,
                macro=e.macro,
                etiqueta=e.etiqueta,
            )
            for e in pagina.exclusiones
        ],
    )


@router.get("", summary="Lista de campanas", response_model=ListaCampanasWhatsmktRespuesta)
def listar_campanas(
    limite: int = Query(default=50, ge=1, le=500),
    desplazamiento: int = Query(default=0, ge=0),
    lote_id: int | None = Query(default=None, ge=1, description="Solo las de este lote"),
    mes: str | None = Query(
        default=None, pattern=_MES, description="YYYY-MM: el mes de la fecha de envio"
    ),
    estado: EstadoCampana = Query(
        default=EstadoCampana.ACTIVAS, description="Las activas (por defecto) o las descartadas"
    ),
    servicio: ConsultaCampanasWhatsmktService = Depends(obtener_servicio_consulta_whatsmkt),
) -> ListaCampanasWhatsmktRespuesta:
    """Las campanas, las mas recientes primero (las de un mismo lote quedan juntas), paginadas."""
    primero = None if mes is None else date(int(mes[:4]), int(mes[5:]), 1)
    pagina = servicio.listar(Paginacion(limite, desplazamiento), lote_id, primero, estado)
    return ListaCampanasWhatsmktRespuesta(
        total=pagina.total,
        limite=limite,
        desplazamiento=desplazamiento,
        campanas=[respuesta_resumen(c) for c in pagina.campanas],
        total_activas=pagina.total_activas,
        total_descartadas=pagina.total_descartadas,
        total_pendientes=pagina.total_pendientes,
    )


@router.get(
    "/{campana_id}",
    summary="Detalle de la campana",
    response_model=DetalleCampanaWhatsmktRespuesta,
    responses=respuestas_de_error_con_codigo(404),
)
def obtener_campana(
    campana_id: int,
    exclusiones_limite: int = Query(default=EXCLUSIONES_POR_PAGINA, ge=1, le=1000),
    exclusiones_desplazamiento: int = Query(default=0, ge=0),
    fuera_del_lote_limite: int = Query(default=EXCLUSIONES_POR_PAGINA, ge=1, le=1000),
    fuera_del_lote_desplazamiento: int = Query(default=0, ge=0),
    servicio: ConsultaCampanasWhatsmktService = Depends(obtener_servicio_consulta_whatsmkt),
) -> DetalleCampanaWhatsmktRespuesta:
    """La campana con su ficha (RF-WM-36), su lote y sus exclusiones, las suyas y las que quedaron
    fuera de todas las campanas del lote, cada lista con su propia paginacion.

    La ficha sale de lo congelado al crear, salvo [whatsapp]: se reemplaza con el WhatsApp de
    contacto VIGENTE, porque el texto se copia ahora en WhatsMKT. Sin numero queda el marcador y
    la ficha trae el aviso `sin_whatsapp`.
    """
    propias = Paginacion(exclusiones_limite, exclusiones_desplazamiento)
    fuera = Paginacion(fuera_del_lote_limite, fuera_del_lote_desplazamiento)
    try:
        d: DetalleCampana = servicio.detalle(campana_id, propias, fuera)
    except CampanaNoEncontrada as exc:
        raise ErrorConCodigo(404, str(exc), None) from exc
    c = d.campana
    return DetalleCampanaWhatsmktRespuesta(
        **_resumen(c),
        lote=LoteWhatsmktRespuesta(id=c.lote_id, modo=d.modo),
        fecha_corte=c.fecha_corte,
        productos=c.productos,
        supervisores=len(c.supervisores),
        definicion_nombre=c.definicion_nombre,
        definicion_version=c.definicion_version,
        texto_version=c.texto_version,
        archivo=ArchivoCampanaWhatsmktRespuesta(
            nombre=c.archivo_nombre, tamano=c.archivo_tamano, filas=c.cantidad
        ),
        ficha=_respuesta_de_ficha(d.ficha),
        exclusiones=_pagina_de_exclusiones(d.exclusiones, propias),
        exclusiones_fuera_del_lote=_pagina_de_exclusiones(d.exclusiones_fuera_del_lote, fuera),
    )
