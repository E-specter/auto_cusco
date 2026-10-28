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
    CampoConfiguracion,
    CodigoMowaMes,
    DatosSpeech,
    ExpresionSegmento,
    FormatoSpeech,
    PartesSegmento,
    Programacion,
    Segmento,
    SpeechNoEncontrado,
    VersionSpeech,
)
from app.core.entities.mowa_mes_campana import (
    LARGO_MAXIMO_DESCRIPCION,
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
    largo_utf16,
    una_linea,
)
from app.core.entities.mowa_mes_costo import PlantillaInvalida
from app.core.ports.repositorio_campanas_mowa_mes_port import RepositorioCampanasMowaMesPort
from app.core.ports.repositorio_mowa_mes_port import RepositorioMowaMesPort
from app.core.ports.repositorio_supervision_port import RepositorioSupervisionPort
from app.core.services.calendario.servicio import ZONA, ahora_en_lima
from app.core.services.gestiones_digitales import supervision
from app.core.services.plataformas.mowa_mes import (
    costos,
    division,
    nombre_archivo,
    segmentos,
    speech,
)
from app.core.services.plataformas.mowa_mes.division import EscritorArchivo
from app.core.services.plataformas.mowa_mes.segmentos import ProgramacionInvalida
from app.core.services.seleccion_cartera import expresiones
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.core.services.seleccion_cartera.recorrido import SeleccionPaginada
from app.core.services.seleccion_cartera.servicio import CANTIDAD_MAXIMA, ConsultaCarteraService
from app.core.services.texto_enriquecido.gsm7 import largo_gsm7
from app.core.services.texto_enriquecido.serializacion import expresion_a_dict

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
    """SHA-256 del texto de las partes de una v1: con esto la creacion sabe si el speech cambio.

    No cambia nunca: las huellas de las versiones v1 ya usadas (el Speech original y las del
    usuario) son las que registraron sus campanas.
    """
    datos = [[p.segmento.value, p.parte_1, p.parte_2] for p in partes]
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def huella_expresiones(expresiones: Sequence[ExpresionSegmento]) -> str:
    """SHA-256 de la forma canonica de las expresiones de una v2, en el orden de los segmentos.

    Propia de la v2: lleva el formato por delante, asi que no puede coincidir con la de una v1
    aunque el texto de los mensajes fuera igual.
    """
    orden = {s: i for i, s in enumerate(Segmento)}
    canonica = [
        [e.segmento.value, expresion_a_dict(e.expresion)]
        for e in sorted(expresiones, key=lambda e: orden[e.segmento])
    ]
    texto = json.dumps(
        [FormatoSpeech.V2.value, canonica], ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def huella_de(datos: DatosSpeech) -> str:
    """La huella de una version, segun su formato: la creacion de campanas compara esta."""
    if datos.formato is FormatoSpeech.V2:
        return huella_expresiones(datos.expresiones)
    return huella_speech(datos.partes)


def _texto(valor: Any) -> str:
    return valor.isoformat() if isinstance(valor, date) else str(valor)


def resumen_filtro(filtro: Filtro, catalogo: CatalogoCartera) -> str:
    """El filtro en una frase. Un campo adicional sale con su nombre legible (el que el usuario
    puede cambiar); un campo base, como siempre: su nombre con espacios."""
    campos = catalogo.campos()
    adicional = campos.get(filtro.campo)
    campo = (
        adicional.etiqueta
        if adicional is not None and adicional.adicional and adicional.etiqueta
        else filtro.campo.replace("_", " ")
    )
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


def descripcion_sugerida(filtros: Sequence[Filtro], catalogo: CatalogoCartera) -> str:
    """RF-MM-04: la cartera y un resumen de los filtros, que el usuario puede editar.

    Cabe en `LARGO_MAXIMO_DESCRIPCION` (unidades UTF-16): si el resumen completo no cabe, sale el
    prefijo con los filtros ENTEROS que quepan desde el principio, cerrado con `...`; y si ni el
    primero cabe, las primeras unidades del texto completo y `...`."""
    # Un valor de filtro de texto puede traer un salto adentro: la descripcion es de una linea.
    resumenes = [una_linea(resumen_filtro(f, catalogo)) for f in filtros]
    completa = f"{PREFIJO_DESCRIPCION} {', '.join(resumenes)}" if resumenes else PREFIJO_DESCRIPCION
    if largo_utf16(completa) <= LARGO_MAXIMO_DESCRIPCION:
        return completa
    elegida = ""
    for n in range(1, len(resumenes) + 1):
        candidata = f"{PREFIJO_DESCRIPCION} {', '.join(resumenes[:n])}..."
        if largo_utf16(candidata) > LARGO_MAXIMO_DESCRIPCION:
            break
        elegida = candidata
    if elegida:
        return elegida
    corte = completa[: LARGO_MAXIMO_DESCRIPCION - 3]  # tantos puntos de codigo como unidades; sobra
    while largo_utf16(corte) > LARGO_MAXIMO_DESCRIPCION - 3:  # recorta de a un caracter entero
        corte = corte[:-1]
    return corte + "..."


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
    dias_ajustados = (
        None if dias is None else segmentos.dias_ajustados(dias, fecha_corte, fecha_envio)
    )
    rango = segmentos.rango_de(dias_ajustados)
    if rango is None:
        return Exclusion(pagare, CodigoMowaMes.SIN_SPEECH)
    # Una v1 siempre necesita el titular y la fecha; una v2, solo si la expresion del segmento usa
    # la variable (RF-MM-13). El orden de las exclusiones no cambia.
    titular = producto.get("titular")
    if constructor.usa_titular(rango.segmento) and _vacio(titular):
        return Exclusion(pagare, CodigoMowaMes.FALTA_TITULAR)
    vencimiento = producto.get("fecha_vencimiento_cuota")
    if constructor.usa_vencimiento(rango.segmento) and vencimiento is None:
        return Exclusion(pagare, CodigoMowaMes.FALTA_VENCIMIENTO)
    # D-CA-2: un campo adicional vacio que el speech lee dejaria un hueco en el SMS. Va antes del
    # WhatsApp y de los 160; uno vacio que el segmento no usa no excluye nada.
    adicionales = {n: producto.get(n) for n in constructor.adicionales_usados(rango.segmento)}
    faltan = tuple(n for n, valor in adicionales.items() if _vacio(valor))
    if faltan:
        return Exclusion(pagare, CodigoMowaMes.FALTA_CAMPO_ADICIONAL, campos=faltan)
    if constructor.requiere_whatsapp_faltante(rango.segmento):
        return rango.segmento
    # Una llamada sin adicionales es identica a la de antes: los valores solo viajan si hay.
    valores = {"adicionales": adicionales} if adicionales else {}
    mensaje = constructor.mensaje_de(
        rango.segmento, titular, vencimiento, dias_ajustados, **valores
    )
    # El mensaje ya viene normalizado a GSM-7 (RF-MM-27) y se mide en unidades GSM-7 (sin
    # extendidos, o sea `len`): se normaliza ANTES de los 150 y de los 160, no despues.
    codigo = speech.codigo_por_largo(largo_gsm7(mensaje))
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

    def etiqueta_de(self, campo: str) -> str:
        """El nombre legible de un campo adicional (el de la cartera si es base): se resuelve al
        leer, asi renombrar un campo cambia lo que se ve y no lo guardado (D-CA-2)."""
        return self._consulta.catalogo.etiqueta_de(campo)

    def armar(self, peticion: PeticionCampana) -> CampanaArmada:
        _validar_opciones(peticion)
        try:
            catalogo = self._consulta.catalogo
            filtros = [expresiones.parsear_filtro(crudo, catalogo) for crudo in peticion.filtros]
            orden = expresiones.parsear_orden(peticion.orden)
        except ConsultaInvalida as exc:
            raise PeticionCampanaInvalida(str(exc)) from exc
        fecha_generacion = fecha_en_lima(self._reloj())
        fecha_envio = self._fecha_envio(peticion, fecha_generacion)
        version = self._speech(peticion.speech_id)
        configuracion = self._mowa_mes.obtener_configuracion()
        plantilla = self._plantilla(peticion, configuracion.plantilla_nombre_archivo)
        whatsapp = self._whatsapp(peticion, configuracion.whatsapp_contacto)
        supervisores, procedencias = self._supervisores_de(peticion)
        documentos = supervision.documentos_por_posicion(supervisores, procedencias)

        constructor = speech.ConstructorMensajes(
            version.datos, whatsapp, adicionales=speech.adicionales_de(catalogo)
        )
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
        tarifa = configuracion.tarifa_sms
        costo_estimado = costos.costo(len(filas), tarifa)
        costo_del_mes = self._campanas.costo_del_mes(mes)
        consumo = ConsumoLimite(
            mes=mes,
            limite=configuracion.limite_mensual,
            cargados_mes=self._campanas.cargados_en_mes(mes),
            esta_campana=len(filas),
            costo_mes=costo_del_mes.costo,
            campanas_sin_tarifa=costo_del_mes.campanas_sin_tarifa,
            costo_esta_campana=costo_estimado,
        )
        sugerida = descripcion_sugerida(filtros, self._consulta.catalogo)
        descripcion = (peticion.descripcion or "").strip() or sugerida
        previsto = nombre_archivo.nombre_previsto(
            plantilla,
            nombre_archivo.ContextoNombre(
                nombre_archivo.MARCADOR_CAMPANA, descripcion, fecha_envio, peticion.fecha_corte
            ),
            [
                a.filas
                for a in division.previstos_por_filas(filas, configuracion.registros_por_archivo)
            ],
        )
        return CampanaArmada(
            peticion=peticion,
            descripcion=descripcion,
            descripcion_sugerida=sugerida,
            fecha_generacion=fecha_generacion,
            fecha_envio=fecha_envio,
            speech=version,
            speech_huella=huella_de(version.datos),
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
            tarifa_sms=tarifa,
            costo_estimado=costo_estimado,
            plantilla_nombre_archivo=plantilla,
            nombre_primer_archivo=None if previsto is None else previsto[0],
            nombre_estimado=False if previsto is None else previsto[1],
            # Se mira el speech entero, no solo los segmentos con productos (aviso, T-MM-B13).
            campos_archivados=catalogo.archivados_entre(constructor.adicionales_usados_en_todos()),
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

        def nombrar(campana_id: int) -> list[str]:
            contexto = nombre_archivo.ContextoNombre(
                str(campana_id), armada.descripcion, armada.fecha_envio, peticion.fecha_corte
            )
            return nombre_archivo.resolver_nombres(
                armada.plantilla_nombre_archivo, contexto, [a.filas for a in archivos]
            )

        return self._campanas.crear(armada, archivos, nombrar)

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
        costo_del_mes = self._campanas.costo_del_mes(primero)
        return ConsumoLimite(
            mes=primero,
            limite=self._mowa_mes.obtener_configuracion().limite_mensual,
            cargados_mes=self._campanas.cargados_en_mes(primero),
            costo_mes=costo_del_mes.costo,
            campanas_sin_tarifa=costo_del_mes.campanas_sin_tarifa,
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
    def _plantilla(peticion: PeticionCampana, por_defecto: str) -> str:
        try:
            return nombre_archivo.plantilla_valida(peticion.plantilla_nombre_archivo, por_defecto)
        except PlantillaInvalida as exc:
            raise PeticionCampanaInvalida(
                str(exc), CampoConfiguracion.PLANTILLA_NOMBRE_ARCHIVO
            ) from exc

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
