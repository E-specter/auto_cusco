"""Pruebas del caso de uso de campanas de MOWA MES (RF-MM-01 a RF-MM-13) y del reporte.

Repositorios en memoria: lo que importa aqui son las reglas (exclusiones,
supervision, WhatsApp, limite, huella del speech, division), no PostgreSQL.
Titulares, documentos y telefonos sinteticos; supervisores del rango 900000xxx.
"""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from app.core.entities.gestiones_digitales import ConfiguracionSupervision, Supervisor
from app.core.entities.mowa_mes import (
    CodigoMowaMes,
    PartesSegmento,
    Programacion,
    Segmento,
    SpeechNoEncontrado,
)
from app.core.entities.mowa_mes_campana import (
    ArchivoResumen,
    CampanaInvalida,
    CampanaRegistrada,
    Exclusion,
    FilaCarga,
    Herramientas,
    LimiteMensualExcedido,
    PeticionCampana,
    PeticionCampanaInvalida,
    Salida,
    SpeechCambiado,
    TipoCarga,
)
from app.core.entities.mowa_mes_reporte import FilaReporte, ReporteImportado, ReporteYaImportado
from app.core.services.plataformas.mowa_mes import speech
from app.core.services.plataformas.mowa_mes.campana import (
    CampanasMowaMesService,
    descripcion_sugerida,
    documento_estandar,
    evaluar_producto,
    huella_speech,
)
from app.core.services.plataformas.mowa_mes.reportes import ReportesMowaMesService
from app.core.services.seleccion_cartera import expresiones
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService
from tests.test_gestiones_digitales import PROCEDENCIAS, SUPERVISORES, RepositorioSupervisionFalso
from tests.test_mowa_mes_speech import ORIGINAL, WHATSAPP, RepositorioMowaMesFalso

MOMENTO = datetime(2026, 9, 13, 15, 0, tzinfo=UTC)  # domingo 13, 10:00 en Lima
FECHA_CORTE = date(2026, 9, 10)
ENVIO = datetime(2026, 9, 14, 9, 0)  # sin zona: hora de Lima
VENCIMIENTO = date(2026, 9, 6)
HUELLA_ORIGINAL = huella_speech(ORIGINAL)


def producto(i: int, **cambios) -> dict:
    datos = {
        "pagare": f"{i:018d}",
        "telefono": f"9000001{i:02d}",
        "documento_numero": f"{i:08d}",
        "titular": f"ZZPRU{i:03d} SINTETICO",
        "dias_atraso": 4,  # + 4 dias hasta el envio = 8: segmento 1 a 8
        "fecha_vencimiento_cuota": VENCIMIENTO,
    }
    datos.update(cambios)
    return datos


class RepositorioCarteraFalso:
    def __init__(self, productos: list[dict], vigente: bool = True) -> None:
        self.productos = productos
        self.vigente = vigente

    def hay_version_vigente(self, fecha_corte):
        return self.vigente

    def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento):
        return len(self.productos), self.productos[desplazamiento : desplazamiento + limite]


class RepositorioCampanasMemoria:
    def __init__(self, cargados_mes: int = 0) -> None:
        self.cargados_mes = cargados_mes
        self.meses_consultados: list[date] = []
        self.campanas: dict[int, CampanaRegistrada] = {}
        self.guardadas: dict[int, tuple] = {}
        self.informes: dict[int, tuple[int, str, list[FilaReporte]]] = {}

    def cargados_en_mes(self, mes):
        self.meses_consultados.append(mes)
        propias = sum(c.total_cargados for c in self.campanas.values() if c.mes_imputacion == mes)
        return self.cargados_mes + propias

    def crear(self, armada, archivos):
        p = armada.peticion
        campana_id = len(self.campanas) + 1
        campana = CampanaRegistrada(
            id=campana_id,
            creado_en=MOMENTO,
            fecha_corte=p.fecha_corte,
            filtros=p.filtros,
            orden=p.orden,
            cantidad=p.cantidad,
            seleccion_id=p.seleccion_id,
            tipo_carga=p.tipo_carga,
            descripcion=armada.descripcion,
            salida=p.salida,
            herramientas=p.herramientas,
            programacion=p.programacion,
            envios=p.envios,
            fecha_envio=armada.fecha_envio,
            speech_id=armada.speech.id,
            speech_nombre=armada.speech.datos.nombre,
            whatsapp=armada.whatsapp,
            supervisores=armada.supervisores,
            disponibles=armada.disponibles,
            evaluados=armada.evaluados,
            productos_cargados=armada.productos_cargados,
            supervision_cargados=armada.supervision_cargados,
            excluidos=len(armada.exclusiones),
            advertencias=sum(armada.advertencias_por_codigo().values()),
            confirmo_limite=p.confirmar_limite,
            archivos=tuple(
                ArchivoResumen(a.numero, a.filas, a.supervision, a.bytes) for a in archivos
            ),
        )
        self.campanas[campana_id] = campana
        self.guardadas[campana_id] = (armada, list(archivos))
        return campana

    def listar(self, limite, desplazamiento):
        todas = sorted(self.campanas.values(), key=lambda c: -c.id)
        return len(todas), todas[desplazamiento : desplazamiento + limite]

    def obtener(self, campana_id):
        return self.campanas.get(campana_id)

    def exclusiones(self, campana_id, codigo, limite, desplazamiento):
        todas = [
            e
            for e in self.guardadas[campana_id][0].exclusiones
            if codigo is None or e.codigo is codigo
        ]
        return len(todas), todas[desplazamiento : desplazamiento + limite]

    def archivo(self, campana_id, numero):
        return next((a for a in self.guardadas[campana_id][1] if a.numero == numero), None)

    def filas_cargadas(self, campana_id):
        return list(self.guardadas[campana_id][0].filas)

    def reportes_ya_importados(self, mes_ids):
        return tuple(sorted(i for i in mes_ids if i in self.informes))

    def guardar_reportes(self, campana_id, nombre_archivo, filas_por_id):
        for mes_id, filas in filas_por_id.items():
            self.informes[mes_id] = (campana_id, nombre_archivo, list(filas))

    def reportes(self, campana_id):
        return [
            ReporteImportado(mes_id, nombre, len(filas), MOMENTO)
            for mes_id, (cid, nombre, filas) in sorted(self.informes.items())
            if cid == campana_id
        ]

    def filas_reporte(self, campana_id):
        return [
            fila
            for _, (cid, _, filas) in sorted(self.informes.items())
            if cid == campana_id
            for fila in filas
        ]


def _escritor(filas) -> bytes:
    return b"x" * len(filas)


def armar_servicio(
    productos: list[dict],
    supervisores=SUPERVISORES,
    whatsapp: str | None = WHATSAPP,
    cargados_mes: int = 0,
    vigente: bool = True,
):
    mowa_mes = RepositorioMowaMesFalso(whatsapp)
    supervision = RepositorioSupervisionFalso()
    supervision.configuracion = ConfiguracionSupervision(PROCEDENCIAS, tuple(supervisores))
    campanas = RepositorioCampanasMemoria(cargados_mes)
    servicio = CampanasMowaMesService(
        ConsultaCarteraService(RepositorioCarteraFalso(productos, vigente)),
        mowa_mes,
        supervision,
        campanas,
        _escritor,
        reloj=lambda: MOMENTO,
    )
    return servicio, campanas, mowa_mes


def peticion(**cambios) -> PeticionCampana:
    datos = {
        "fecha_corte": FECHA_CORTE,
        "cantidad": 100,
        "programacion": Programacion.HORA_DETERMINADA,
        "envios": (ENVIO,),
        "speech_huella": HUELLA_ORIGINAL,
    }
    datos.update(cambios)
    return PeticionCampana(**datos)


# --- Exclusiones (RF-MM-13) ---------------------------------------------


def test_cada_producto_excluido_lleva_un_solo_motivo_el_primero_que_falla() -> None:
    productos = [
        producto(1),
        producto(2, telefono=None, documento_numero=None),
        producto(3, telefono="800000003"),
        producto(4, documento_numero="  ", dias_atraso=None),
        producto(5, dias_atraso=200, titular=None),
        producto(6, dias_atraso=None),
        producto(7, titular=" ", fecha_vencimiento_cuota=None),
        producto(8, fecha_vencimiento_cuota=None),
        producto(9),
    ]
    servicio, _, _ = armar_servicio(productos)

    armada = servicio.previsualizar(peticion())

    assert [(e.pagare[-1], e.codigo) for e in armada.exclusiones] == [
        ("2", CodigoMowaMes.TELEFONO_INVALIDO),
        ("3", CodigoMowaMes.TELEFONO_INVALIDO),
        ("4", CodigoMowaMes.FALTA_DOCUMENTO),
        ("5", CodigoMowaMes.SIN_SPEECH),
        ("6", CodigoMowaMes.SIN_SPEECH),
        ("7", CodigoMowaMes.FALTA_TITULAR),
        ("8", CodigoMowaMes.FALTA_VENCIMIENTO),
    ]
    assert [f.pagare[-1] for f in armada.filas if not f.supervision] == ["1", "9"]
    assert armada.errores == ()


def test_un_telefono_repetido_no_es_motivo_de_exclusion() -> None:
    servicio, _, _ = armar_servicio([producto(1), producto(2, telefono="900000101")])

    armada = servicio.previsualizar(peticion())

    assert armada.productos_cargados == 2 and armada.exclusiones == ()


def _con_parte_2(largo_total: int) -> list[PartesSegmento]:
    # mensaje = titular 8 + parte 1 (46) + fecha 10 + parte 2
    relleno = "x" * (largo_total - 8 - len(ORIGINAL[1].parte_1) - 10)
    return [replace(p, parte_2=relleno) if p.segmento is Segmento.DE_1_A_8 else p for p in ORIGINAL]


@pytest.mark.parametrize(
    ("largo", "resultado"),
    [
        (150, None),
        (151, CodigoMowaMes.MENSAJE_EXCEDE_150),
        (160, CodigoMowaMes.MENSAJE_EXCEDE_150),
        (161, CodigoMowaMes.MENSAJE_EXCEDE_160),
    ],
)
def test_largo_del_mensaje(largo, resultado) -> None:
    constructor = speech.ConstructorMensajes(_con_parte_2(largo), WHATSAPP)

    evaluado = evaluar_producto(producto(1), FECHA_CORTE, date(2026, 9, 14), constructor)

    if resultado is CodigoMowaMes.MENSAJE_EXCEDE_160:
        assert evaluado == Exclusion(producto(1)["pagare"], resultado)
    else:
        assert isinstance(evaluado, FilaCarga)
        assert len(evaluado.mensaje) == largo
        assert evaluado.advertencias == (() if resultado is None else (resultado,))


def test_el_segmento_sale_de_los_dias_ajustados_al_envio() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, WHATSAPP)

    # 4 de atraso al corte y el envio 21 dias despues: 25, segmento 9 a 30.
    fila = evaluar_producto(producto(1), FECHA_CORTE, date(2026, 10, 1), constructor)

    assert fila.segmento is Segmento.DE_9_A_30
    assert fila.mensaje.startswith(
        "ZZPRU001 Caja Cusco te informa que tu cuota venció el 06/09/2026"
    )


# --- Supervision (RF-MM-12, RF-40) --------------------------------------


def test_la_supervision_va_primero_con_el_mensaje_de_la_primera_fila_cargada() -> None:
    servicio, _, _ = armar_servicio([producto(1, telefono=None), producto(2), producto(3)])

    armada = servicio.previsualizar(peticion())

    supervision, productos = armada.filas[:5], armada.filas[5:]
    assert all(f.supervision for f in supervision)
    assert [(f.numero, f.dni) for f in supervision] == [
        ("900000001", "00000001"),
        ("900000002", "00000002"),
        ("900000003", "00000003"),
        ("900000004", "00000004"),
        ("900000005", "00000005"),
    ]
    assert {f.mensaje for f in supervision} == {productos[0].mensaje}
    assert productos[0].pagare.endswith("2")
    assert (armada.supervision_cargados, armada.productos_cargados, armada.total_cargados) == (
        5,
        2,
        7,
    )


def test_la_campana_puede_traer_sus_propios_supervisores() -> None:
    propios = (Supervisor("900000009", "nuestra empresa"),)
    servicio, _, _ = armar_servicio([producto(1)])

    armada = servicio.previsualizar(peticion(supervisores=propios))

    assert [(s.numero, s.documento) for s in armada.supervisores] == [("900000009", "00000001")]


def test_supervisores_de_la_campana_invalidos() -> None:
    servicio, _, _ = armar_servicio([producto(1)])

    with pytest.raises(PeticionCampanaInvalida, match="9 digitos"):
        servicio.previsualizar(peticion(supervisores=(Supervisor("12345", "Caja Cusco"),)))


def test_sin_supervisores_la_campana_no_se_crea() -> None:
    servicio, campanas, _ = armar_servicio([producto(1)], supervisores=())

    armada = servicio.previsualizar(peticion())

    assert [e.codigo for e in armada.errores] == [CodigoMowaMes.SIN_SUPERVISORES]
    with pytest.raises(CampanaInvalida):
        servicio.crear(peticion())
    assert campanas.campanas == {}


def test_sin_productos_cargables_no_hay_supervision_ni_campana() -> None:
    servicio, _, _ = armar_servicio([producto(1, telefono=None)])

    armada = servicio.previsualizar(peticion())

    assert [e.codigo for e in armada.errores] == [CodigoMowaMes.SIN_PRODUCTOS_CARGABLES]
    assert armada.filas == ()
    with pytest.raises(CampanaInvalida):
        servicio.crear(peticion())


# --- WhatsApp (RF-MM-16) ------------------------------------------------


def test_sin_whatsapp_y_con_productos_en_un_segmento_que_lo_usa_es_error() -> None:
    productos = [producto(1), producto(2, dias_atraso=40)]  # 44 dias: 31 a 60 usa [whatsapp]
    servicio, _, _ = armar_servicio(productos, whatsapp=None)

    armada = servicio.previsualizar(peticion())

    assert [e.codigo for e in armada.errores] == [CodigoMowaMes.FALTA_WHATSAPP]
    assert "31_a_60 (1)" in armada.errores[0].detalle
    assert armada.productos_cargados == 1 and armada.exclusiones == ()
    with pytest.raises(CampanaInvalida):
        servicio.crear(peticion())


def test_sin_whatsapp_pero_sin_productos_en_esos_segmentos_se_crea() -> None:
    servicio, campanas, _ = armar_servicio([producto(1)], whatsapp=None)

    servicio.crear(peticion())

    assert len(campanas.campanas) == 1


def test_el_whatsapp_de_la_campana_reemplaza_al_configurado() -> None:
    servicio, _, _ = armar_servicio([producto(1, dias_atraso=40)])

    armada = servicio.previsualizar(peticion(whatsapp="900000456"))

    assert armada.filas[-1].mensaje.endswith("https://wa.me/+51900000456")
    with pytest.raises(PeticionCampanaInvalida):
        servicio.previsualizar(peticion(whatsapp="51900000456"))


# --- Limite mensual (RF-MM-01, S-MM-2, S-MM-7) --------------------------


def test_el_limite_se_imputa_al_mes_de_la_fecha_de_envio() -> None:
    servicio, campanas, _ = armar_servicio([producto(1)])

    armada = servicio.previsualizar(peticion(envios=(datetime(2026, 10, 1, 9, 0),)))

    assert campanas.meses_consultados == [date(2026, 10, 1)]
    assert (armada.consumo.mes, armada.consumo.esta_campana) == (date(2026, 10, 1), 6)


def test_superar_el_limite_se_advierte_y_crear_exige_confirmacion() -> None:
    servicio, campanas, _ = armar_servicio([producto(1)], cargados_mes=2_499_995)

    armada = servicio.previsualizar(peticion())

    assert armada.consumo.excedido and armada.errores == ()
    with pytest.raises(LimiteMensualExcedido):
        servicio.crear(peticion())
    creada = servicio.crear(peticion(confirmar_limite=True))
    assert creada.confirmo_limite is True
    assert servicio.limite_mensual(date(2026, 9, 20)).cargados_mes == 2_499_995 + 6


def test_justo_en_el_limite_no_se_excede() -> None:
    servicio, _, _ = armar_servicio([producto(1)], cargados_mes=2_499_994)

    assert not servicio.previsualizar(peticion()).consumo.excedido


# --- Speech y huella ----------------------------------------------------


def test_crear_exige_la_huella_del_speech_que_se_previsualizo() -> None:
    servicio, campanas, _ = armar_servicio([producto(1)])

    with pytest.raises(PeticionCampanaInvalida, match="speech_huella"):
        servicio.crear(peticion(speech_huella=None))
    with pytest.raises(SpeechCambiado):
        servicio.crear(peticion(speech_huella="0" * 64))
    assert campanas.campanas == {}


def test_la_huella_cambia_si_cambia_cualquier_parte() -> None:
    cambiado = [replace(ORIGINAL[0], parte_2=ORIGINAL[0].parte_2 + " ")] + list(ORIGINAL[1:])

    assert huella_speech(cambiado) != HUELLA_ORIGINAL
    assert huella_speech(list(ORIGINAL)) == HUELLA_ORIGINAL


def test_una_version_de_speech_elegida_que_no_existe() -> None:
    servicio, _, _ = armar_servicio([producto(1)])

    with pytest.raises(SpeechNoEncontrado):
        servicio.previsualizar(peticion(speech_id=99))


# --- Creacion y division ------------------------------------------------


def test_crear_divide_con_los_limites_de_la_configuracion() -> None:
    servicio, campanas, mowa_mes = armar_servicio([producto(i) for i in range(1, 4)])
    mowa_mes.configuracion = replace(mowa_mes.configuracion, registros_por_archivo=6)

    creada = servicio.crear(peticion())

    assert [(a.numero, a.filas, a.supervision) for a in creada.archivos] == [(1, 6, 5), (2, 2, 0)]
    assert creada.total_cargados == 8


def test_opciones_deshabilitadas_se_rechazan() -> None:
    servicio, _, _ = armar_servicio([producto(1)])

    for cambio in (
        {"tipo_carga": TipoCarga.PERSONALIZADA},
        {"salida": Salida.NUMERO_CORTO},
        {"herramientas": Herramientas(respuesta_automatica=True)},
    ):
        with pytest.raises(PeticionCampanaInvalida):
            servicio.previsualizar(peticion(**cambio))


def test_enviar_ahora_usa_la_fecha_de_generacion_en_lima_y_no_lleva_fechas() -> None:
    servicio, _, _ = armar_servicio([producto(1)])

    armada = servicio.previsualizar(peticion(programacion=Programacion.ENVIAR_AHORA, envios=()))

    assert armada.fecha_envio == date(2026, 9, 13)
    with pytest.raises(PeticionCampanaInvalida):
        servicio.previsualizar(peticion(programacion=Programacion.ENVIAR_AHORA))


def test_la_cantidad_recorta_la_seleccion() -> None:
    servicio, _, _ = armar_servicio([producto(i) for i in range(1, 6)])

    armada = servicio.previsualizar(peticion(cantidad=3))

    assert (armada.disponibles, armada.evaluados, armada.productos_cargados) == (5, 3, 3)


def test_descripcion_sugerida_y_propia() -> None:
    filtros = [
        expresiones.parsear_filtro("dias_atraso:entre:9|90"),
        expresiones.parsear_filtro("saldo_capital_pendiente:mayor:5000"),
    ]
    servicio, _, _ = armar_servicio([producto(1)])

    sugerida = descripcion_sugerida(filtros)
    propia = servicio.previsualizar(peticion(descripcion="  Campana sintetica "))

    assert sugerida == "CajaCusco 9 <= dias atraso <= 90, saldo capital pendiente > 5000"
    assert descripcion_sugerida([]) == "CajaCusco"
    assert propia.descripcion == "Campana sintetica"


def test_un_filtro_mal_escrito_se_rechaza() -> None:
    servicio, _, _ = armar_servicio([producto(1)])

    with pytest.raises(PeticionCampanaInvalida):
        servicio.previsualizar(peticion(filtros=("campo_inventado:igual:x",)))


# --- Reporte de enviados (RF-MM-20 a RF-MM-22) --------------------------


class LectorFalso:
    def __init__(self, filas):
        self.filas = filas

    def leer(self, contenido):
        return tuple(self.filas)


def _reporte_de(filas: list[FilaCarga], mes_id: int) -> list[FilaReporte]:
    return [
        FilaReporte(i, mes_id, f.numero, f.mensaje, "14/09/26", f.dni, "enviado", "Nro. LARGO", "u")
        for i, f in enumerate(filas, start=2)
    ]


def test_importar_asocia_cada_id_y_un_id_repetido_exige_confirmar() -> None:
    servicio, campanas, _ = armar_servicio([producto(1), producto(2)])
    creada = servicio.crear(peticion())
    filas = campanas.filas_cargadas(creada.id)
    reporte = _reporte_de(filas[:4], 70001) + _reporte_de(filas[4:], 70002)
    reportes = ReportesMowaMesService(campanas, LectorFalso(reporte))

    estado = reportes.importar(creada.id, "reporte.xlsx", b"")

    assert [(r.mes_id, r.filas) for r in estado.reportes] == [(70001, 4), (70002, 3)]
    assert (estado.conciliacion.total.cargados, estado.conciliacion.total.enviados) == (7, 7)
    with pytest.raises(ReporteYaImportado):
        reportes.importar(creada.id, "reporte.xlsx", b"")
    reemplazado = reportes.importar(creada.id, "otro.xlsx", b"", reemplazar=True)
    assert {r.nombre_archivo for r in reemplazado.reportes} == {"otro.xlsx"}


# --- Documentos que no son DNI ni RUC (E-2) -----------------------------


@pytest.mark.parametrize(
    ("tipo", "numero", "estandar"),
    [
        ("dni", "01234567", True),
        ("ruc", "20123456789", True),
        ("extranjero", "ZZCE123456", False),
        ("extranjero", "123456789", False),  # la ingesta lo tipo como extranjero
        # Con tipo, manda el tipo aunque la forma parezca DNI o RUC.
        ("extranjero", "12345678", False),
        ("extranjero", "20123456789", False),
        (None, "01234567", True),
        (None, "20123456789", True),
        (None, "123456789", False),
        (None, "ZZ123456", False),
    ],
)
def test_documento_estandar(tipo, numero, estandar) -> None:
    assert documento_estandar(tipo, numero) is estandar


def test_un_carne_sintetico_se_carga_y_se_advierte_sin_excluirse() -> None:
    carne = producto(2, documento_numero="ZZCE123456", documento_tipo="extranjero")
    servicio, _, _ = armar_servicio([producto(1, documento_tipo="dni"), carne])

    armada = servicio.previsualizar(peticion())

    productos = [f for f in armada.filas if not f.supervision]
    assert armada.exclusiones == ()
    assert [(f.dni, f.advertencias) for f in productos] == [
        ("00000001", ()),
        ("ZZCE123456", (CodigoMowaMes.DOCUMENTO_NO_ESTANDAR,)),
    ]
    assert armada.advertencias_por_codigo() == {CodigoMowaMes.DOCUMENTO_NO_ESTANDAR: 1}


def test_un_producto_puede_llevar_las_dos_advertencias() -> None:
    constructor = speech.ConstructorMensajes(_con_parte_2(155), WHATSAPP)
    carne = producto(1, documento_numero="ZZCE123456", documento_tipo="extranjero")

    fila = evaluar_producto(carne, FECHA_CORTE, date(2026, 9, 14), constructor)

    assert fila.advertencias == (
        CodigoMowaMes.MENSAJE_EXCEDE_150,
        CodigoMowaMes.DOCUMENTO_NO_ESTANDAR,
    )
