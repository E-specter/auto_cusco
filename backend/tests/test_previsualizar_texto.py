"""El servicio de previsualizacion, sin HTTP: las muestras y el aislamiento del contexto (B4a)."""

from datetime import date

from app.core.entities.cartera import PaginaCartera
from app.core.services.contextos_texto import RegistroContextos, contexto_cartera
from app.core.services.plataformas.mowa_mes.contexto_texto import contexto_speech
from app.core.services.previsualizar_texto import (
    MuestraEjemplo,
    MuestraEjemplosPorSegmento,
    MuestraPrimerosDeSeleccion,
    MuestraProductoReal,
    PrevisualizacionTextoService,
)

CARTERA = contexto_cartera()
SPEECH = contexto_speech()
SERVICIO = PrevisualizacionTextoService(RegistroContextos([CARTERA, SPEECH]))


def _variable(nombre: str) -> dict:
    return {"tipo": "variable", "nombre": nombre}


def _texto(valor: str) -> dict:
    return {"tipo": "texto", "valor": valor}


def _columna(nombre: str, orden: int, *nodos: dict, **extra) -> dict:
    return {"nombre": nombre, "orden": orden, "expresion": {"nodos": list(nodos)}, **extra}


def _definicion(**segmentacion) -> dict:
    return {
        "columnas": [_columna("a", 0, _variable("titular"), _texto(" "), _variable("dias_atraso"))],
        "segmentacion": segmentacion,
    }


def test_los_ejemplos_por_segmento_no_modifican_el_registro_de_ejemplo_del_contexto() -> None:
    antes = dict(SPEECH.ejemplo)

    SERVICIO.previsualizar(
        "mowa_mes.speech",
        MuestraEjemplosPorSegmento(),
        expresion={"nodos": [{"tipo": "variable", "nombre": "dias_atraso_ajustados"}]},
    )

    assert dict(SPEECH.ejemplo) == antes
    assert SPEECH.ejemplo["dias_atraso_ajustados"] == 12


def test_si_la_variable_de_dias_no_es_numerica_no_se_inventan_dias() -> None:
    definicion = _definicion(
        criterio={"tipo": "calculado", "variable_dias": "titular"}, politica="usar_por_defecto"
    )

    previa = SERVICIO.previsualizar("cartera", MuestraEjemplosPorSegmento(), definicion=definicion)

    assert [f.columnas[0].texto for f in previa.filas] == [f"{CARTERA.ejemplo['titular']} 12"] * 6


def test_una_tabla_propia_de_la_definicion_marca_las_filas_de_ejemplo() -> None:
    definicion = _definicion(
        criterio={
            "tipo": "calculado",
            "tabla": [
                {"clave": "al_dia", "etiqueta": "Al dia", "desde": None, "hasta": 0},
                {"clave": "tarde", "etiqueta": "Tarde", "desde": 20, "hasta": None},
            ],
        }
    )

    previa = SERVICIO.previsualizar("cartera", MuestraEjemplosPorSegmento(), definicion=definicion)

    assert [(f.etiqueta, f.segmento, f.columnas[0].texto.split()[-1]) for f in previa.filas] == [
        ("Al dia", "al_dia", "0"),
        ("Tarde", "tarde", "20"),
    ]


def test_la_muestra_de_ejemplo_es_el_registro_tal_cual() -> None:
    previa = SERVICIO.previsualizar("cartera", MuestraEjemplo(), definicion=_definicion())

    [fila] = previa.filas
    assert fila.columnas[0].texto == f"{CARTERA.ejemplo['titular']} 12"
    assert fila.numero == 1


def test_el_producto_real_pasa_por_el_registro_del_contexto() -> None:
    class Cartera:
        def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento=0):
            fila = {
                "titular": "UNO",
                "dias_atraso": 33,
                "fecha_vencimiento_cuota": date(2026, 9, 1),
            }
            return PaginaCartera(total=1, filas=(fila,), limite=limite)

    # Con la fecha de envio igual a la de corte los dias no se mueven (RF-55).
    servicio = PrevisualizacionTextoService(
        RegistroContextos([SPEECH]), Cartera(), hoy=lambda: date(2026, 9, 10)
    )

    previa = servicio.previsualizar(
        "mowa_mes.speech",
        MuestraProductoReal(date(2026, 9, 10), "x"),
        expresion={
            "nodos": [
                {"tipo": "variable", "nombre": "titular"},
                {"tipo": "texto", "valor": " "},
                {"tipo": "variable", "nombre": "dias_atraso_ajustados"},
            ]
        },
    )

    assert previa.filas[0].columnas[0].texto == "UNO 33"


def test_un_criterio_por_campo_da_una_fila_por_valor_aunque_varias_columnas_lo_contemplen() -> None:
    def variante(segmento: str, texto: str) -> dict:
        return {"segmento": segmento, "expresion": {"nodos": [_texto(texto)]}}

    variantes = [variante("CUSCO", "c"), variante("LIMA", "l")]
    definicion = {
        "columnas": [
            _columna("a", 0, _texto("x"), variantes=variantes),
            _columna("b", 1, _texto("y"), variantes=variantes[:1]),
        ],
        "segmentacion": {"criterio": {"tipo": "campo", "campo": "region"}},
    }

    previa = SERVICIO.previsualizar("cartera", MuestraEjemplosPorSegmento(), definicion=definicion)

    assert [f.segmento for f in previa.filas] == ["CUSCO", "LIMA"]
    assert [[c.texto for c in f.columnas] for f in previa.filas] == [["c", "c"], ["l", "y"]]


def _con_producto(producto: dict) -> PrevisualizacionTextoService:
    class Cartera:
        def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento=0):
            return PaginaCartera(total=1, filas=(producto,), limite=limite)

    return PrevisualizacionTextoService(RegistroContextos([SPEECH]), Cartera())


def _real(servicio: PrevisualizacionTextoService, politica: str):
    return servicio.previsualizar(
        "mowa_mes.speech",
        MuestraProductoReal(date(2026, 9, 10), "x"),
        definicion={
            "columnas": [_columna("m", 0, _variable("titular"))],
            "segmentacion": {"politica": politica},
        },
    )


def test_un_producto_real_sin_dias_de_atraso_se_previsualiza_sin_segmento_y_no_falla() -> None:
    servicio = _con_producto({"titular": "UNO", "fecha_vencimiento_cuota": date(2026, 9, 1)})

    usando_defecto = _real(servicio, "usar_por_defecto")
    excluyendo = _real(servicio, "excluir")

    [fila] = usando_defecto.filas
    assert (fila.segmento, fila.excluida, fila.columnas[0].texto) == (None, None, "UNO")
    [fila] = excluyendo.filas
    assert (fila.segmento, fila.columnas) == (None, ())
    assert fila.excluida.codigo == "sin_segmento"  # type: ignore[union-attr]


def test_un_producto_real_con_mas_de_120_dias_tampoco_cae_en_un_segmento() -> None:
    previa = _real(_con_producto({"titular": "UNO", "dias_atraso": 500}), "excluir")

    assert [(f.segmento, f.excluida.codigo) for f in previa.filas] == [(None, "sin_segmento")]  # type: ignore[union-attr]


def test_los_primeros_de_una_seleccion_se_acotan_a_cinco_aunque_se_pidan_mas() -> None:
    pedidas = []

    class Cartera:
        def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento=0):
            pedidas.append(limite)
            filas = tuple({"titular": f"T{i}"} for i in range(min(limite, 40)))
            return PaginaCartera(total=40, filas=filas, limite=limite)

    servicio = PrevisualizacionTextoService(RegistroContextos([CARTERA]), Cartera())

    previa = servicio.previsualizar(
        "cartera",
        MuestraPrimerosDeSeleccion(date(2026, 9, 10), cantidad=50),
        expresion={"nodos": [_variable("titular")]},
    )

    assert pedidas == [5]
    assert len(previa.filas) == 5
    assert previa.disponibles == 40
    # un producto sin pagare no se ofrece como muestra: ni pagare ni fecha de corte
    assert [(f.pagare, f.fecha_corte) for f in previa.filas] == [(None, None)] * 5
