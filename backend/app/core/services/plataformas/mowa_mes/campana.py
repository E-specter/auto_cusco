"""Caso de uso: armar, previsualizar y crear una campana de MOWA MES (RF-MM-01 a RF-MM-13).

La seleccion se recorre por paginas con el mismo orden y desempate que
`/cartera` (RF-MM-09). Cada producto queda cargado o excluido con un solo
motivo, en el orden del catalogo. La supervision se arma con la primera fila
cargada como plantilla y va al inicio del primer archivo (RF-MM-12, RF-40).

La previsualizacion no escribe ni guarda nada; la creacion divide la carga en
archivos por filas y por bytes reales y la guarda entera en una transaccion.
"""

import hashlib
import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime
from typing import Any

from app.core.entities.cartera import ConsultaInvalida, Filtro, Operador
from app.core.entities.gestiones_digitales import ConfiguracionSupervision, SupervisionInvalida
from app.core.entities.mowa_mes import (
    CodigoMowaMes,
    PartesSegmento,
    Programacion,
    Segmento,
    SpeechNoEncontrado,
    VersionSpeech,
)
from app.core.entities.mowa_mes_campana import (
    PREFIJO_DESCRIPCION,
    ArchivoCarga,
    ArchivoNoEncontrado,
    CampanaArmada,
    CampanaInvalida,
    CampanaNoEncontrada,
    CampanaRegistrada,
    ConsumoLimite,
    ErrorCampana,
    Exclusion,
    FilaCarga,
    LimiteMensualExcedido,
    PeticionCampana,
    PeticionCampanaInvalida,
    Salida,
    SpeechCambiado,
    SupervisorAsignado,
    TipoCarga,
)
from app.core.ports.repositorio_campanas_mowa_mes_port import RepositorioCampanasMowaMesPort
from app.core.ports.repositorio_mowa_mes_port import RepositorioMowaMesPort
from app.core.ports.repositorio_supervision_port import RepositorioSupervisionPort
from app.core.services.calendario.servicio import ZONA, ahora_en_lima
from app.core.services.gestiones_digitales import supervision
from app.core.services.plataformas.mowa_mes import division, segmentos, speech
from app.core.services.plataformas.mowa_mes.division import EscritorArchivo
from app.core.services.plataformas.mowa_mes.segmentos import ProgramacionInvalida
from app.core.services.seleccion_cartera import expresiones
from app.core.services.seleccion_cartera.recorrido import SeleccionPaginada
from app.core.services.seleccion_cartera.servicio import CANTIDAD_MAXIMA, ConsultaCarteraService

COLUMNA_NUMERO = "numero"
COLUMNA_DOCUMENTO = "dni"

_SIMBOLOS = {
    Operador.IGUAL: "=",
    Operador.DISTINTO: "<>",
    Operador.MAYOR: ">",
    Operador.MAYOR_IGUAL: ">=",
    Operador.MENOR: "<",
    Operador.MENOR_IGUAL: "<=",
}


# --- Piezas puras ---------------------------------------------------------


def huella_speech(partes: Sequence[PartesSegmento]) -> str:
    """SHA-256 del texto de las partes: con esto la creacion sabe si el speech cambio."""
    datos = [[p.segmento.value, p.parte_1, p.parte_2] for p in partes]
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _texto(valor: Any) -> str:
    return valor.isoformat() if isinstance(valor, date) else str(valor)


def resumen_filtro(filtro: Filtro) -> str:
    campo = filtro.campo.replace("_", " ")
    valores = [_texto(v) for v in filtro.valores]
    if filtro.operador in _SIMBOLOS:
        return f"{campo} {_SIMBOLOS[filtro.operador]} {valores[0]}"
    if filtro.operador is Operador.ENTRE:
        return f"{valores[0]} <= {campo} <= {valores[1]}"
    if filtro.operador is Operador.EN:
        return f"{campo} en {'/'.join(valores)}"
    if filtro.operador is Operador.CONTIENE:
        return f"{campo} contiene {valores[0]}"
    if filtro.operador is Operador.EMPIEZA_CON:
        return f"{campo} empieza con {valores[0]}"
    if filtro.operador is Operador.VACIO:
        return f"sin {campo}"
    return f"con {campo}"


def descripcion_sugerida(filtros: Sequence[Filtro]) -> str:
    """RF-MM-04: la cartera y un resumen de los filtros, que el usuario puede editar."""
    if not filtros:
        return PREFIJO_DESCRIPCION
    return f"{PREFIJO_DESCRIPCION} {', '.join(resumen_filtro(f) for f in filtros)}"


def fecha_en_lima(momento: datetime) -> date:
    """Una fecha y hora sin zona se toma como hora de Lima."""
    return momento.date() if momento.tzinfo is None else momento.astimezone(ZONA).date()


def _vacio(valor: Any) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


LARGOS_DOCUMENTO_ESTANDAR = (8, 11)  # RF-MM-10: DNI de 8 o RUC de 11
_TIPOS_DOCUMENTO_ESTANDAR = ("dni", "ruc")


def documento_estandar(tipo: str | None, numero: str) -> bool:
    """DNI o RUC segun RF-MM-10 (decision E-2).

    Con el tipo que asigno la ingesta (regla N-3), manda el tipo: `extranjero` no es
    estandar. Sin tipo, el mismo criterio de forma: solo digitos, de 8 u 11.
    """
    if tipo:
        return tipo in _TIPOS_DOCUMENTO_ESTANDAR
    return numero.isdigit() and len(numero) in LARGOS_DOCUMENTO_ESTANDAR


def evaluar_producto(
    producto: Mapping[str, Any],
    fecha_corte: date,
    fecha_envio: date,
    constructor: speech.ConstructorMensajes,
) -> FilaCarga | Exclusion | Segmento:
    """La fila cargada, la exclusion con su motivo o, si falta el WhatsApp, el segmento.

    Los motivos se revisan en el orden del catalogo: el primero que falla es el
    unico que se reporta.
    """
    pagare = str(producto["pagare"])
    telefono = producto.get("telefono")
    if _vacio(telefono) or not supervision.numero_valido(str(telefono)):
        return Exclusion(pagare, CodigoMowaMes.TELEFONO_INVALIDO)
    documento = producto.get("documento_numero")
    if _vacio(documento):
        return Exclusion(pagare, CodigoMowaMes.FALTA_DOCUMENTO)
    dias = producto.get("dias_atraso")
    rango = segmentos.rango_de(
        None if dias is None else segmentos.dias_ajustados(dias, fecha_corte, fecha_envio)
    )
    if rango is None:
        return Exclusion(pagare, CodigoMowaMes.SIN_SPEECH)
    titular = producto.get("titular")
    if _vacio(titular):
        return Exclusion(pagare, CodigoMowaMes.FALTA_TITULAR)
    vencimiento = producto.get("fecha_vencimiento_cuota")
    if vencimiento is None:
        return Exclusion(pagare, CodigoMowaMes.FALTA_VENCIMIENTO)
    if constructor.requiere_whatsapp_faltante(rango.segmento):
        return rango.segmento
    mensaje = constructor.mensaje_de(rango.segmento, titular, vencimiento)
    codigo = speech.codigo_por_largo(len(mensaje))
    if codigo is CodigoMowaMes.MENSAJE_EXCEDE_160:
        return Exclusion(pagare, codigo)
    dni = str(documento).strip()
    advertencias = () if codigo is None else (codigo,)
    if not documento_estandar(producto.get("documento_tipo"), dni):
        # E-2: se carga igual y se advierte; no es motivo de exclusion.
        advertencias = (*advertencias, CodigoMowaMes.DOCUMENTO_NO_ESTANDAR)
    return FilaCarga(
        numero=str(telefono),
        mensaje=mensaje,
        dni=dni,
        pagare=pagare,
        segmento=rango.segmento,
        advertencias=advertencias,
    )


# --- Caso de uso ----------------------------------------------------------


class CampanasMowaMesService:
    def __init__(
        self,
        consulta: ConsultaCarteraService,
        mowa_mes: RepositorioMowaMesPort,
        supervisores: RepositorioSupervisionPort,
        campanas: RepositorioCampanasMowaMesPort,
        escritor: EscritorArchivo,
        reloj: Callable[[], datetime] = ahora_en_lima,
    ) -> None:
        self._consulta = consulta
        self._mowa_mes = mowa_mes
        self._supervisores = supervisores
        self._campanas = campanas
        self._escritor = escritor
        self._reloj = reloj

    def previsualizar(self, peticion: PeticionCampana) -> CampanaArmada:
        return self.armar(peticion)

    def armar(self, peticion: PeticionCampana) -> CampanaArmada:
        _validar_opciones(peticion)
        try:
            filtros = [expresiones.parsear_filtro(crudo) for crudo in peticion.filtros]
            orden = expresiones.parsear_orden(peticion.orden)
        except ConsultaInvalida as exc:
            raise PeticionCampanaInvalida(str(exc)) from exc
        fecha_generacion = fecha_en_lima(self._reloj())
        fecha_envio = self._fecha_envio(peticion, fecha_generacion)
        version = self._speech(peticion.speech_id)
        configuracion = self._mowa_mes.obtener_configuracion()
        whatsapp = self._whatsapp(peticion, configuracion.whatsapp_contacto)
        supervisores, procedencias = self._supervisores_de(peticion)
        documentos = supervision.documentos_por_posicion(supervisores, procedencias)

        constructor = speech.ConstructorMensajes(version.datos.partes, whatsapp)
        seleccion = SeleccionPaginada(
            self._consulta, peticion.fecha_corte, filtros, orden, peticion.cantidad
        )
        productos: list[FilaCarga] = []
        exclusiones: list[Exclusion] = []
        sin_whatsapp: Counter[Segmento] = Counter()
        evaluados = 0
        for producto in seleccion:
            evaluados += 1
            resultado = evaluar_producto(producto, peticion.fecha_corte, fecha_envio, constructor)
            if isinstance(resultado, FilaCarga):
                productos.append(resultado)
            elif isinstance(resultado, Exclusion):
                exclusiones.append(resultado)
            else:
                sin_whatsapp[resultado] += 1

        errores = _errores(productos, supervisores, sin_whatsapp)
        filas_supervision = _filas_supervision(productos, supervisores, procedencias)
        filas = (*filas_supervision, *productos)
        mes = fecha_envio.replace(day=1)
        consumo = ConsumoLimite(
            mes=mes,
            limite=configuracion.limite_mensual,
            cargados_mes=self._campanas.cargados_en_mes(mes),
            esta_campana=len(filas),
        )
        sugerida = descripcion_sugerida(filtros)
        return CampanaArmada(
            peticion=peticion,
            descripcion=(peticion.descripcion or "").strip() or sugerida,
            descripcion_sugerida=sugerida,
            fecha_generacion=fecha_generacion,
            fecha_envio=fecha_envio,
            speech=version,
            speech_huella=huella_speech(version.datos.partes),
            whatsapp=whatsapp,
            supervisores=tuple(
                SupervisorAsignado(s.numero, s.procedencia, documento)
                for s, documento in zip(supervisores, documentos, strict=True)
            ),
            registros_por_archivo=configuracion.registros_por_archivo,
            bytes_por_archivo=configuracion.bytes_por_archivo,
            disponibles=seleccion.disponibles,
            evaluados=evaluados,
            filas=filas,
            exclusiones=tuple(exclusiones),
            errores=errores,
            consumo=consumo,
        )

    def crear(self, peticion: PeticionCampana) -> CampanaRegistrada:
        if not peticion.speech_huella:
            raise PeticionCampanaInvalida(
                "Falta speech_huella: la creacion debe traer la huella que devolvio la "
                "previsualizacion"
            )
        armada = self.armar(peticion)
        if armada.errores:
            raise CampanaInvalida(armada.errores)
        if peticion.speech_huella != armada.speech_huella:
            raise SpeechCambiado(armada.speech.id)
        if armada.consumo.excedido and not peticion.confirmar_limite:
            raise LimiteMensualExcedido(armada.consumo)
        archivos = division.dividir(
            armada.filas, armada.registros_por_archivo, armada.bytes_por_archivo, self._escritor
        )
        return self._campanas.crear(armada, archivos)

    def listar(self, limite: int, desplazamiento: int) -> tuple[int, list[CampanaRegistrada]]:
        return self._campanas.listar(limite, desplazamiento)

    def obtener(self, campana_id: int) -> CampanaRegistrada:
        campana = self._campanas.obtener(campana_id)
        if campana is None:
            raise CampanaNoEncontrada(campana_id)
        return campana

    def exclusiones(
        self, campana_id: int, codigo: CodigoMowaMes | None, limite: int, desplazamiento: int
    ) -> tuple[int, list[Exclusion]]:
        self.obtener(campana_id)
        return self._campanas.exclusiones(campana_id, codigo, limite, desplazamiento)

    def archivo(self, campana_id: int, numero: int) -> tuple[CampanaRegistrada, ArchivoCarga]:
        campana = self.obtener(campana_id)
        archivo = self._campanas.archivo(campana_id, numero)
        if archivo is None:
            raise ArchivoNoEncontrado(campana_id, numero)
        return campana, archivo

    def limite_mensual(self, mes: date | None = None) -> ConsumoLimite:
        """Consumo del mes (por defecto el actual en Lima), sin campana nueva."""
        primero = (mes or fecha_en_lima(self._reloj())).replace(day=1)
        return ConsumoLimite(
            mes=primero,
            limite=self._mowa_mes.obtener_configuracion().limite_mensual,
            cargados_mes=self._campanas.cargados_en_mes(primero),
        )

    # --- Detalles ------------------------------------------------------

    @staticmethod
    def _fecha_envio(peticion: PeticionCampana, fecha_generacion: date) -> date:
        if peticion.programacion is Programacion.ENVIAR_AHORA and peticion.envios:
            raise PeticionCampanaInvalida("Enviar ahora no lleva fechas de envio")
        try:
            return segmentos.fecha_envio(
                peticion.programacion,
                fecha_generacion,
                [fecha_en_lima(momento) for momento in peticion.envios],
            )
        except ProgramacionInvalida as exc:
            raise PeticionCampanaInvalida(str(exc)) from exc

    def _speech(self, speech_id: int | None) -> VersionSpeech:
        if speech_id is not None:
            version = self._mowa_mes.obtener_speech(speech_id)
            if version is None:
                raise SpeechNoEncontrado(speech_id)
            return version
        original = next((v for v in self._mowa_mes.listar_speech() if v.original), None)
        if original is None:
            raise RuntimeError("Falta el Speech original: aplica las migraciones")
        return original

    @staticmethod
    def _whatsapp(peticion: PeticionCampana, por_defecto: str | None) -> str | None:
        propio = (peticion.whatsapp or "").strip()
        if propio and not speech.whatsapp_valido(propio):
            raise PeticionCampanaInvalida("El WhatsApp debe tener 9 digitos y empezar con 9")
        return propio or por_defecto

    def _supervisores_de(self, peticion: PeticionCampana) -> tuple[tuple, tuple[str, ...]]:
        defecto = self._supervisores.obtener()
        propios = defecto.supervisores if peticion.supervisores is None else peticion.supervisores
        try:
            validos = supervision.validar(ConfiguracionSupervision(defecto.procedencias, propios))
        except SupervisionInvalida as exc:
            raise PeticionCampanaInvalida(str(exc)) from exc
        return validos.supervisores, validos.procedencias


def _validar_opciones(peticion: PeticionCampana) -> None:
    if peticion.tipo_carga is not TipoCarga.MASIVA:
        raise PeticionCampanaInvalida("El tipo de carga Personalizada todavia no esta habilitado")
    if peticion.salida is not Salida.NUMERO_LARGO:
        raise PeticionCampanaInvalida("Solo la salida Numero largo esta habilitada")
    if peticion.herramientas.respuesta_automatica:
        raise PeticionCampanaInvalida("La respuesta automatica todavia no esta habilitada")
    if not 1 <= peticion.cantidad <= CANTIDAD_MAXIMA:
        raise PeticionCampanaInvalida(f"La cantidad debe estar entre 1 y {CANTIDAD_MAXIMA}")


def _errores(
    productos: Sequence[FilaCarga], supervisores: Sequence, sin_whatsapp: Counter[Segmento]
) -> tuple[ErrorCampana, ...]:
    errores: list[ErrorCampana] = []
    if sin_whatsapp:
        detalle = ", ".join(f"{seg.value} ({n})" for seg, n in sorted(sin_whatsapp.items()))
        errores.append(
            ErrorCampana(
                CodigoMowaMes.FALTA_WHATSAPP,
                f"Hay productos en segmentos que usan [whatsapp] y no hay numero: {detalle}",
            )
        )
    if not supervisores:
        errores.append(
            ErrorCampana(CodigoMowaMes.SIN_SUPERVISORES, "La campana no tiene supervisores")
        )
    if not productos:
        errores.append(
            ErrorCampana(
                CodigoMowaMes.SIN_PRODUCTOS_CARGABLES,
                "Ningun producto de la seleccion quedo dentro de la carga",
            )
        )
    return tuple(errores)


def _filas_supervision(
    productos: Sequence[FilaCarga], supervisores: Sequence, procedencias: Sequence[str]
) -> tuple[FilaCarga, ...]:
    if not productos or not supervisores:
        return ()
    plantilla = productos[0]
    filas = supervision.filas_supervision(
        supervisores,
        procedencias,
        {
            COLUMNA_NUMERO: plantilla.numero,
            "mensaje": plantilla.mensaje,
            COLUMNA_DOCUMENTO: plantilla.dni,
        },
        COLUMNA_NUMERO,
        COLUMNA_DOCUMENTO,
    )
    return tuple(
        FilaCarga(
            numero=fila[COLUMNA_NUMERO],
            mensaje=fila["mensaje"],
            dni=fila[COLUMNA_DOCUMENTO],
            supervision=True,
        )
        for fila in filas
    )
