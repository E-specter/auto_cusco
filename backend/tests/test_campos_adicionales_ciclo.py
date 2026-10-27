"""Campos adicionales de punta a punta, sin base de datos (T-CA-B2, RF-64 a RF-66).

Crear un campo desde una columna del borrador -> asignarlo -> confirmar -> procesar, con un mismo
repositorio en memoria para el mapeador, la ingesta y el catalogo de la cartera. Lo que depende de
PostgreSQL (la migracion, el candado, las consultas) esta en `test_campos_adicionales_postgres.py`.
Archivos y valores sinteticos.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.adapters.input.lector_tabla import LectorTabla
from app.core.entities.borrador import BorradorNoEncontrado, MapeoConProblemas
from app.core.entities.campos_adicionales import (
    CampoAdicionalNoEncontrado,
    ColumnaInexistente,
    NombreDeCampoRepetido,
    TipoAdicional,
)
from app.core.entities.carga import EstadoCarga
from app.core.entities.lectura_tabla import OpcionesLectura
from app.core.entities.mapeador import Asignacion, CodigoMapeo, EstadoEncabezado, OrigenAsignacion
from app.core.services.borradores_carga.servicio import MapeadorService
from app.core.services.ingesta_sabana.mapeable import CATALOGO_SABANA_MAPEABLE
from app.core.services.ingesta_sabana.servicio import IngestaSabanaService
from app.core.services.mapeador.serializacion import analisis_desde_dict
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.core.services.seleccion_cartera.expresiones import parsear_filtro
from tests.mapeador_memoria import AdicionalesDe
from tests.test_ingesta_servicio import RepositorioEnMemoria
from tests.test_mapeador_ciclo import INICIO, Reloj, csv_de

SABANA = "sabana_vencida"
FECHA = date(2026, 9, 10)
E = EstadoEncabezado
O = OrigenAsignacion  # noqa: E741

CSV = csv_de(
    [
        ["Pagare", "Zona comercial", "Monto extra", "Fecha de visita"],
        ["000000000000000001", "SUR", "150.50", "03/08/2099"],
        ["000000000000000002", "NORTE", "7", "04/08/2099"],
        ["000000000000000003", "", "", ""],
    ]
)
CSV_CON_VALORES_MALOS = csv_de(
    [
        ["Pagare", "Monto extra", "Fecha de visita"],
        ["000000000000000001", "abc", "32/13/2099"],
        ["000000000000000002", "12,5", "no es fecha"],
        ["000000000000000003", "1E+999999", "03/08/2099"],
    ]
)


class Entorno:
    def __init__(self) -> None:
        self.reloj = Reloj()
        self.repo = RepositorioEnMemoria()
        self.adicionales = AdicionalesDe(self.repo)
        self.mapeador = MapeadorService(
            self.repo, LectorTabla(), [CATALOGO_SABANA_MAPEABLE], self.reloj
        )
        self.ingesta = IngestaSabanaService(
            self.repo, LectorTabla(), self.reloj, adicionales=self.adicionales
        )

    def catalogo(self) -> CatalogoCartera:
        """Un catalogo de cartera nuevo: lee las definiciones cuando se le piden."""
        return CatalogoCartera(self.adicionales)

    def subir(self, contenido: bytes = CSV):
        return self.mapeador.crear_borrador(SABANA, "datos.csv", contenido)

    def crear(self, analizado, indice: int, nombre: str, tipo: TipoAdicional):
        return self.mapeador.crear_campo_adicional(analizado.borrador.id, indice, nombre, tipo)

    def asignaciones(self, analizado, **campos: str) -> list[Asignacion]:
        """Lo sugerido, y `campos` (encabezado normalizado -> campo) para lo demas."""
        resultado = []
        for c in analizado.analisis.columnas:
            campo = campos.get(c.normalizado, c.sugerido)
            resultado.append(Asignacion(c.indice, campo, O.COINCIDE if campo else O.MANUAL))
        return resultado

    def procesar(self, analizado, asignaciones):
        carga = self.ingesta.registrar_desde_borrador(
            analizado.borrador.id, FECHA, asignaciones
        ).carga
        return carga, self.ingesta.procesar_carga(carga.id)


@pytest.fixture
def entorno() -> Entorno:
    return Entorno()


def crear_los_tres(entorno: Entorno, analizado) -> dict[str, str]:
    """Un adicional de cada tipo desde sus columnas; devuelve encabezado normalizado -> tecnico."""
    columnas = {c.normalizado: c.indice for c in analizado.analisis.columnas}
    tecnicos = {}
    for encabezado, nombre, tipo in (
        ("zona comercial", "Zona comercial", TipoAdicional.TEXTO),
        ("monto extra", "Monto extra", TipoAdicional.NUMERO),
        ("fecha de visita", "Fecha de visita", TipoAdicional.FECHA),
    ):
        campo, _ = entorno.crear(analizado, columnas[encabezado], nombre, tipo)
        tecnicos[encabezado] = campo.nombre
    return tecnicos


# --- Crear ----------------------------------------------------------------------------------------


def test_un_archivo_con_columnas_nuevas_las_deja_sin_coincidencia_hasta_crear_el_campo(
    entorno,
) -> None:
    analizado = entorno.subir()

    assert [(c.encabezado, c.estado) for c in analizado.analisis.columnas] == [
        ("Pagare", E.COINCIDE),
        ("Zona comercial", E.SIN_COINCIDENCIA),
        ("Monto extra", E.SIN_COINCIDENCIA),
        ("Fecha de visita", E.SIN_COINCIDENCIA),
    ]


def test_crear_el_campo_guarda_la_definicion_con_el_encabezado_de_la_columna(entorno) -> None:
    analizado = entorno.subir()

    campo, catalogo = entorno.crear(analizado, 2, "  Monto   extra ", TipoAdicional.NUMERO)

    assert (campo.nombre, campo.nombre_legible, campo.tipo) == (
        "ad_monto_extra",
        "Monto extra",
        TipoAdicional.NUMERO,
    )
    assert campo.encabezado_origen == "monto extra" and not campo.archivado
    assert entorno.repo.adicionales(SABANA) == (campo,)
    assert entorno.repo.bloqueos_de_adicionales == 1
    nuevo = next(c for c in catalogo.campos if c.nombre == "ad_monto_extra")
    assert (nuevo.adicional, nuevo.etiqueta, nuevo.obligatorio) == (True, "Monto extra", False)


def test_el_campo_creado_se_suma_al_analisis_guardado_del_borrador(entorno) -> None:
    analizado = entorno.subir()
    antes = analisis_desde_dict(entorno.repo.borradores[analizado.borrador.id].analisis)

    entorno.crear(analizado, 2, "Monto extra", TipoAdicional.NUMERO)

    despues = analisis_desde_dict(entorno.repo.borradores[analizado.borrador.id].analisis)
    assert despues.campos[: len(antes.campos)] == antes.campos  # lo de antes, igual y en su orden
    assert [c.nombre for c in despues.campos[len(antes.campos) :]] == ["ad_monto_extra"]
    assert despues.campos[-1].adicional and despues.campos[-1].etiqueta == "Monto extra"
    assert despues.columnas == antes.columnas  # las columnas no se tocan


def test_el_campo_creado_se_puede_validar_y_confirmar_enseguida(entorno) -> None:
    analizado = entorno.subir()
    entorno.crear(analizado, 2, "Monto extra", TipoAdicional.NUMERO)
    asignaciones = entorno.asignaciones(analizado, **{"monto extra": "ad_monto_extra"})

    assert entorno.mapeador.validar(analizado.borrador.id, asignaciones) == ()


def test_un_campo_que_no_se_creo_sigue_sin_validar(entorno) -> None:
    analizado = entorno.subir()
    asignaciones = entorno.asignaciones(analizado, **{"monto extra": "ad_monto_extra"})

    problemas = entorno.mapeador.validar(analizado.borrador.id, asignaciones)

    assert [p.codigo for p in problemas] == [CodigoMapeo.CAMPO_DESCONOCIDO]


def test_dos_nombres_con_el_mismo_slug_no_comparten_nombre_tecnico(entorno) -> None:
    analizado = entorno.subir()

    primero, _ = entorno.crear(analizado, 1, "Zona-comercial", TipoAdicional.TEXTO)
    segundo, _ = entorno.crear(analizado, 2, "Zona/comercial", TipoAdicional.TEXTO)

    assert (primero.nombre, segundo.nombre) == ("ad_zona_comercial", "ad_zona_comercial_2")


def test_un_nombre_tecnico_archivado_no_se_reutiliza(entorno) -> None:
    analizado = entorno.subir()
    primero, _ = entorno.crear(analizado, 1, "Zona comercial", TipoAdicional.TEXTO)
    entorno.mapeador.cambiar_campo_adicional(SABANA, primero.nombre, "Zona vieja", True)

    segundo, _ = entorno.crear(analizado, 1, "Zona/comercial", TipoAdicional.TEXTO)

    assert segundo.nombre == "ad_zona_comercial_2"


def test_un_borrador_inexistente_o_vencido_no_crea_nada(entorno) -> None:
    analizado = entorno.subir()
    entorno.reloj.avanzar(hours=25)

    with pytest.raises(BorradorNoEncontrado):
        entorno.crear(analizado, 1, "Zona comercial", TipoAdicional.TEXTO)
    with pytest.raises(BorradorNoEncontrado):
        entorno.mapeador.crear_campo_adicional(999, 1, "Zona comercial", TipoAdicional.TEXTO)

    assert entorno.repo.adicionales(SABANA) == ()


def test_una_columna_que_no_esta_en_el_analisis_no_crea_nada(entorno) -> None:
    analizado = entorno.subir()

    with pytest.raises(ColumnaInexistente):
        entorno.crear(analizado, 9, "Zona comercial", TipoAdicional.TEXTO)

    assert entorno.repo.adicionales(SABANA) == ()


# --- Nombres repetidos ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "choca_con"),
    [
        ("Región", "region"),  # un campo base, por su nombre sin tildes
        ("PAGARE", "pagare"),
        ("Dias atraso hoy", "dias_atraso"),  # por un alias del campo base
        ("tipo producto", "tipo_producto"),  # por su nombre con espacios en lugar de _
        ("Titular", "titular"),  # una variable que los contextos del motor ya usan
    ],
)
def test_un_nombre_que_coincide_con_un_campo_base_es_un_409_con_ese_campo(
    entorno, nombre, choca_con
) -> None:
    analizado = entorno.subir()

    with pytest.raises(NombreDeCampoRepetido) as error:
        entorno.crear(analizado, 1, nombre, TipoAdicional.TEXTO)

    assert error.value.campo.nombre == choca_con and not error.value.campo.adicional
    assert entorno.repo.adicionales(SABANA) == ()


@pytest.mark.parametrize("nombre", ["Zona comercial", "  ZONA   comercial ", "zóna comercial"])
def test_un_nombre_que_coincide_con_otro_adicional_es_un_409_con_ese_campo(entorno, nombre) -> None:
    analizado = entorno.subir()
    existente, _ = entorno.crear(analizado, 1, "Zona comercial", TipoAdicional.TEXTO)

    with pytest.raises(NombreDeCampoRepetido) as error:
        entorno.crear(analizado, 2, nombre, TipoAdicional.NUMERO)

    assert error.value.campo.nombre == existente.nombre and error.value.campo.adicional
    assert entorno.repo.adicionales(SABANA) == (existente,)


def test_un_adicional_archivado_sigue_ocupando_su_nombre(entorno) -> None:
    analizado = entorno.subir()
    existente, _ = entorno.crear(analizado, 1, "Zona comercial", TipoAdicional.TEXTO)
    entorno.mapeador.cambiar_campo_adicional(SABANA, existente.nombre, archivado=True)

    with pytest.raises(NombreDeCampoRepetido) as error:
        entorno.crear(analizado, 2, "Zona comercial", TipoAdicional.NUMERO)

    assert error.value.campo.nombre == existente.nombre


def test_un_nombre_que_coincide_con_el_encabezado_de_otro_adicional_tambien_choca(entorno) -> None:
    analizado = entorno.subir()
    existente, _ = entorno.crear(analizado, 1, "Zona", TipoAdicional.TEXTO)  # encabezado de origen

    with pytest.raises(NombreDeCampoRepetido) as error:
        entorno.crear(analizado, 2, "zona comercial", TipoAdicional.TEXTO)

    assert error.value.campo.nombre == existente.nombre


def test_un_409_no_deja_rastro_ni_en_la_definicion_ni_en_el_analisis(entorno) -> None:
    analizado = entorno.subir()
    antes = dict(entorno.repo.borradores[analizado.borrador.id].analisis)

    with pytest.raises(NombreDeCampoRepetido):
        entorno.crear(analizado, 1, "Región", TipoAdicional.TEXTO)

    assert entorno.repo.borradores[analizado.borrador.id].analisis == antes


# --- Procesar -------------------------------------------------------------------------------------


def test_el_ciclo_completo_guarda_cada_valor_normalizado_a_su_tipo(entorno) -> None:
    analizado = entorno.subir()
    tecnicos = crear_los_tres(entorno, analizado)
    asignaciones = entorno.asignaciones(analizado, **tecnicos)

    carga, resultado = entorno.procesar(analizado, asignaciones)

    assert resultado.estado is EstadoCarga.TERMINADA
    filas = entorno.repo.filas[carga.id]
    assert [f.adicionales for f in filas] == [
        {"ad_zona_comercial": "SUR", "ad_monto_extra": "150.5", "ad_fecha_de_visita": "2099-08-03"},
        {"ad_zona_comercial": "NORTE", "ad_monto_extra": "7", "ad_fecha_de_visita": "2099-08-04"},
        {},  # las celdas vacias no se guardan
    ]
    assert all("ad_monto_extra" not in f.valores for f in filas)  # no se mezclan con los base
    assert not [i for i in entorno.repo.incidencias[carga.id] if i.codigo == "valor_no_convertible"]


def test_un_valor_que_no_es_de_su_tipo_queda_vacio_y_avisa_sin_bloquear_la_fila(entorno) -> None:
    analizado = entorno.subir(CSV_CON_VALORES_MALOS)
    tecnicos = crear_los_tres_de_dos(entorno, analizado)
    asignaciones = entorno.asignaciones(analizado, **tecnicos)

    carga, resultado = entorno.procesar(analizado, asignaciones)

    assert resultado.estado is EstadoCarga.TERMINADA
    assert [f.adicionales for f in entorno.repo.filas[carga.id]] == [
        {},
        {},
        {"ad_fecha_de_visita": "2099-08-03"},
    ]
    avisos = [
        (i.fila, i.columna, i.codigo, i.severidad.value)
        for i in entorno.repo.incidencias[carga.id]
        if i.codigo == "valor_no_convertible"
    ]
    assert avisos == [
        (2, "ad_monto_extra", "valor_no_convertible", "advertencia"),
        (2, "ad_fecha_de_visita", "valor_no_convertible", "advertencia"),
        (3, "ad_monto_extra", "valor_no_convertible", "advertencia"),
        (3, "ad_fecha_de_visita", "valor_no_convertible", "advertencia"),
        (4, "ad_monto_extra", "valor_no_convertible", "advertencia"),
    ]
    originales = [
        i.valor_original
        for i in entorno.repo.incidencias[carga.id]
        if i.codigo == "valor_no_convertible"
    ]
    assert originales[:2] == ["abc", "32/13/2099"]


def crear_los_tres_de_dos(entorno: Entorno, analizado) -> dict[str, str]:
    columnas = {c.normalizado: c.indice for c in analizado.analisis.columnas}
    tecnicos = {}
    for encabezado, nombre, tipo in (
        ("monto extra", "Monto extra", TipoAdicional.NUMERO),
        ("fecha de visita", "Fecha de visita", TipoAdicional.FECHA),
    ):
        campo, _ = entorno.crear(analizado, columnas[encabezado], nombre, tipo)
        tecnicos[encabezado] = campo.nombre
    return tecnicos


def test_una_carga_sin_adicionales_es_igual_con_o_sin_el_puerto_de_definiciones(entorno) -> None:
    """Paridad: un archivo que no usa ningun adicional da la MISMA version que antes."""
    sin_puerto = Entorno()
    sin_puerto.ingesta = IngestaSabanaService(sin_puerto.repo, LectorTabla(), sin_puerto.reloj)
    # Con definiciones existentes que este archivo no usa.
    previo = entorno.subir()
    crear_los_tres(entorno, previo)
    archivo = csv_de([["Pagare", "Titular"], ["000000000000000001", "TITULAR FICTICIO"]])

    resultados = []
    for e in (entorno, sin_puerto):
        analizado = e.subir(archivo)
        carga, resultado = e.procesar(analizado, e.asignaciones(analizado))
        resultados.append(
            (
                resultado.estado,
                [
                    (f.numero_fila, f.valores, f.extras, f.adicionales)
                    for f in e.repo.filas[carga.id]
                ],
                [(i.fila, i.columna, i.codigo) for i in e.repo.incidencias[carga.id]],
                e.repo.cargas[carga.id].get("formato"),
            )
        )

    assert resultados[0] == resultados[1]
    assert resultados[0][1][0][3] is None  # la version no trae adicionales: NULL, no {}


def test_un_adicional_archivado_se_sigue_procesando_en_un_mapeo_ya_confirmado(entorno) -> None:
    analizado = entorno.subir()
    tecnicos = crear_los_tres(entorno, analizado)
    carga = entorno.ingesta.registrar_desde_borrador(
        analizado.borrador.id, FECHA, entorno.asignaciones(analizado, **tecnicos)
    ).carga

    entorno.mapeador.cambiar_campo_adicional(SABANA, tecnicos["monto extra"], archivado=True)
    resultado = entorno.ingesta.procesar_carga(carga.id)

    assert resultado.estado is EstadoCarga.TERMINADA
    assert entorno.repo.filas[carga.id][0].adicionales["ad_monto_extra"] == "150.5"


# --- Recordar -------------------------------------------------------------------------------------


def test_lo_asignado_a_un_adicional_se_recuerda_como_cualquier_asignacion(entorno) -> None:
    analizado = entorno.subir()
    tecnicos = crear_los_tres(entorno, analizado)
    entorno.procesar(analizado, entorno.asignaciones(analizado, **tecnicos))

    otro = entorno.subir()

    estados = {c.normalizado: (c.estado, c.sugerido) for c in otro.analisis.columnas}
    assert estados["monto extra"] == (E.RECORDADO, "ad_monto_extra")
    assert estados["zona comercial"] == (E.RECORDADO, "ad_zona_comercial")
    assert otro.analisis.problemas_iniciales == ()


def test_un_adicional_que_se_deja_sin_asignar_nunca_es_obligatorio(entorno) -> None:
    analizado = entorno.subir()
    crear_los_tres(entorno, analizado)

    # Todo en «No cargar» salvo el pagare: es valido, los adicionales no se exigen.
    solo_clave = [
        Asignacion(c.indice, c.sugerido if c.indice == 0 else None, O.MANUAL)
        for c in analizado.analisis.columnas
    ]

    assert entorno.mapeador.validar(analizado.borrador.id, solo_clave) == ()


def test_un_archivo_nuevo_ya_reconoce_el_campo_por_su_encabezado_de_origen(entorno) -> None:
    analizado = entorno.subir()
    crear_los_tres(entorno, analizado)

    otro = entorno.subir()

    assert [c.estado for c in otro.analisis.columnas][1:] == [E.COINCIDE] * 3
    assert [c.sugerido for c in otro.analisis.columnas][1:] == [
        "ad_zona_comercial",
        "ad_monto_extra",
        "ad_fecha_de_visita",
    ]


# --- Renombrar, archivar y reactivar --------------------------------------------------------------


def test_renombrar_cambia_el_nombre_legible_y_deja_el_tecnico_y_el_tipo(entorno) -> None:
    analizado = entorno.subir()
    campo, _ = entorno.crear(analizado, 2, "Monto extra", TipoAdicional.NUMERO)

    cambiado = entorno.mapeador.cambiar_campo_adicional(SABANA, campo.nombre, "Cargo adicional")

    assert (cambiado.nombre, cambiado.tipo, cambiado.encabezado_origen) == (
        "ad_monto_extra",
        TipoAdicional.NUMERO,
        "monto extra",
    )
    assert cambiado.nombre_legible == "Cargo adicional"
    assert entorno.catalogo().etiqueta_de("ad_monto_extra") == "Cargo adicional"


def test_renombrar_no_rompe_lo_que_ya_usa_el_nombre_tecnico(entorno) -> None:
    analizado = entorno.subir()
    campo, _ = entorno.crear(analizado, 2, "Monto extra", TipoAdicional.NUMERO)
    catalogo = entorno.catalogo()
    filtro = parsear_filtro(f"{campo.nombre}:mayor:10", catalogo)

    entorno.mapeador.cambiar_campo_adicional(SABANA, campo.nombre, "Cargo adicional")

    reparseado = parsear_filtro(f"{campo.nombre}:mayor:10", entorno.catalogo())
    assert reparseado == filtro and reparseado.valores == (Decimal(10),)


def test_renombrar_a_un_nombre_ocupado_es_un_409_y_no_cambia_nada(entorno) -> None:
    analizado = entorno.subir()
    zona, _ = entorno.crear(analizado, 1, "Zona comercial", TipoAdicional.TEXTO)
    monto, _ = entorno.crear(analizado, 2, "Monto extra", TipoAdicional.NUMERO)

    with pytest.raises(NombreDeCampoRepetido) as error:
        entorno.mapeador.cambiar_campo_adicional(SABANA, monto.nombre, "zona COMERCIAL")
    with pytest.raises(NombreDeCampoRepetido) as de_base:
        entorno.mapeador.cambiar_campo_adicional(SABANA, monto.nombre, "Región")

    assert error.value.campo.nombre == zona.nombre and de_base.value.campo.nombre == "region"
    assert entorno.repo.adicionales(SABANA) == (zona, monto)


def test_renombrar_a_su_propio_nombre_con_otras_mayusculas_es_valido(entorno) -> None:
    analizado = entorno.subir()
    campo, _ = entorno.crear(analizado, 2, "Monto extra", TipoAdicional.NUMERO)

    cambiado = entorno.mapeador.cambiar_campo_adicional(SABANA, campo.nombre, "MONTO EXTRA")

    assert cambiado.nombre_legible == "MONTO EXTRA"


def test_archivar_lo_saca_de_las_listas_pero_se_sigue_resolviendo(entorno) -> None:
    analizado = entorno.subir()
    campo, _ = entorno.crear(analizado, 2, "Monto extra", TipoAdicional.NUMERO)

    archivado = entorno.mapeador.cambiar_campo_adicional(SABANA, campo.nombre, archivado=True)

    assert archivado.archivado and archivado.nombre_legible == "Monto extra"
    catalogo = entorno.catalogo()
    assert campo.nombre not in catalogo.ofrecidos() and campo.nombre in catalogo.campos()
    assert catalogo.archivados_entre([campo.nombre, "region"]) == (campo.nombre,)
    assert campo.nombre not in {c.nombre for c in entorno.mapeador.catalogo(SABANA).campos}
    assert campo.nombre in {c.nombre for c in entorno.mapeador.campos_adicionales(SABANA)[0:1]}


def test_reactivar_lo_vuelve_a_ofrecer(entorno) -> None:
    analizado = entorno.subir()
    campo, _ = entorno.crear(analizado, 2, "Monto extra", TipoAdicional.NUMERO)
    entorno.mapeador.cambiar_campo_adicional(SABANA, campo.nombre, archivado=True)

    entorno.mapeador.cambiar_campo_adicional(SABANA, campo.nombre, archivado=False)

    assert campo.nombre in entorno.catalogo().ofrecidos()
    assert campo.nombre in {c.nombre for c in entorno.mapeador.catalogo(SABANA).campos}


def test_un_campo_que_no_existe_no_se_cambia(entorno) -> None:
    with pytest.raises(CampoAdicionalNoEncontrado):
        entorno.mapeador.cambiar_campo_adicional(SABANA, "ad_nada", "Otro nombre")


def test_el_catalogo_del_mapeador_trae_los_adicionales_activos_al_final(entorno) -> None:
    base = [c.nombre for c in entorno.mapeador.catalogo(SABANA).campos]
    analizado = entorno.subir()
    crear_los_tres(entorno, analizado)

    campos = entorno.mapeador.catalogo(SABANA).campos

    assert [c.nombre for c in campos][: len(base)] == base
    assert [c.nombre for c in campos][len(base) :] == [
        "ad_zona_comercial",
        "ad_monto_extra",
        "ad_fecha_de_visita",
    ]
    assert all(c.adicional and c.etiqueta and not c.obligatorio for c in campos[len(base) :])


def test_la_lectura_del_catalogo_de_la_cartera_pasa_una_sola_vez_por_instancia(entorno) -> None:
    analizado = entorno.subir()
    crear_los_tres(entorno, analizado)
    lecturas = []
    original = entorno.adicionales.listar

    def contar():
        lecturas.append(1)
        return original()

    entorno.adicionales.listar = contar
    catalogo = entorno.catalogo()

    for _ in range(5):
        catalogo.campos()
        catalogo.tipos()
        catalogo.ofrecidos()

    assert len(lecturas) == 1
    assert len(entorno.catalogo().campos()) == len(catalogo.campos())  # y uno nuevo vuelve a leer


def test_un_mapeo_con_problemas_no_crea_la_carga_aunque_el_campo_exista(entorno) -> None:
    analizado = entorno.subir()
    crear_los_tres(entorno, analizado)
    sin_clave = [Asignacion(c.indice, None, O.MANUAL) for c in analizado.analisis.columnas]

    with pytest.raises(MapeoConProblemas):
        entorno.ingesta.registrar_desde_borrador(analizado.borrador.id, FECHA, sin_clave)

    assert entorno.repo.cargas == {}
    assert INICIO == entorno.reloj.ahora


def test_la_columna_asignada_a_mano_al_campo_nuevo_se_valida_y_se_recuerda(
    entorno,
) -> None:
    analizado = entorno.subir()
    assert analizado.analisis.columnas[2].estado is E.SIN_COINCIDENCIA
    entorno.crear(analizado, 2, "Monto extra", TipoAdicional.NUMERO)
    asignaciones = [
        Asignacion(c.indice, "ad_monto_extra" if c.indice == 2 else c.sugerido, O.MANUAL)
        for c in analizado.analisis.columnas
    ]

    assert entorno.mapeador.validar(analizado.borrador.id, asignaciones) == ()
    carga = entorno.ingesta.registrar_desde_borrador(
        analizado.borrador.id, FECHA, asignaciones
    ).carga

    guardadas = {a["indice"]: a for a in entorno.repo.cargas[carga.id]["asignaciones"]}
    assert guardadas[2]["campo"] == "ad_monto_extra"
    assert guardadas[2]["origen"] == O.MANUAL.value  # una columna sin coincidencia, elegida a mano
    assert entorno.repo.recordados(SABANA)[("monto extra", 1)] == "ad_monto_extra"


def test_volver_a_analizar_arma_el_analisis_con_el_catalogo_actual(entorno) -> None:
    """Crear -> reanalizar -> la columna del campo recien creado vuelve como «coincide» por su
    alias (el encabezado de origen), y el analisis guardado trae el campo."""
    analizado = entorno.subir()
    assert analizado.analisis.columnas[2].estado is E.SIN_COINCIDENCIA
    entorno.crear(analizado, 2, "Monto extra", TipoAdicional.NUMERO)

    de_nuevo = entorno.mapeador.reanalizar(analizado.borrador.id, OpcionesLectura())

    columna = de_nuevo.analisis.columnas[2]
    assert (columna.estado, columna.sugerido) == (E.COINCIDE, "ad_monto_extra")
    guardado = analisis_desde_dict(entorno.repo.borradores[analizado.borrador.id].analisis)
    assert "ad_monto_extra" in [c.nombre for c in guardado.campos]
    asignaciones = [
        Asignacion(c.indice, c.sugerido, O.COINCIDE) for c in de_nuevo.analisis.columnas
    ]
    assert entorno.mapeador.validar(analizado.borrador.id, asignaciones) == ()


def test_un_adicional_archivado_deja_de_encontrarse_al_volver_a_analizar(entorno) -> None:
    analizado = entorno.subir()
    campo, _ = entorno.crear(analizado, 2, "Monto extra", TipoAdicional.NUMERO)
    entorno.mapeador.cambiar_campo_adicional(SABANA, campo.nombre, archivado=True)

    de_nuevo = entorno.mapeador.reanalizar(analizado.borrador.id, OpcionesLectura())

    assert de_nuevo.analisis.columnas[2].estado is E.SIN_COINCIDENCIA
    assert campo.nombre not in [c.nombre for c in de_nuevo.analisis.campos]
