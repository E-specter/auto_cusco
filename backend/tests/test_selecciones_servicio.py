"""Pruebas del caso de uso de selecciones guardadas, con un repositorio en memoria."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.core.entities.selecciones import (
    DatosSeleccion,
    NombreDeSeleccionRepetido,
    ParteSeleccion,
    SeleccionGuardada,
    SeleccionInvalida,
    SeleccionNoEncontrada,
)
from app.core.services.seleccion_cartera.servicio import CANTIDAD_MAXIMA
from app.core.services.selecciones.servicio import SeleccionesService, problemas_de

MOMENTO = datetime(2026, 9, 12, 10, 0, tzinfo=UTC)

VALIDA = DatosSeleccion(
    nombre="Preventiva con telefono",
    filtros=("segmento_financiero:igual:1. Preventiva", "telefono:no_vacio"),
    orden="-saldo_capital_pendiente",
    cantidad=500,
    indicadores=("cuota promedio:promedio:monto_cuota",),
)


class RepositorioFalso:
    def __init__(self) -> None:
        self.selecciones: dict[int, SeleccionGuardada] = {}
        self.escrituras = 0

    def _repetido(self, nombre: str, excepto: int | None = None) -> bool:
        return any(
            s.datos.nombre.casefold() == nombre.casefold() and s.id != excepto
            for s in self.selecciones.values()
        )

    def listar(self):
        return sorted(self.selecciones.values(), key=lambda s: s.datos.nombre.casefold())

    def obtener(self, seleccion_id):
        return self.selecciones.get(seleccion_id)

    def crear(self, datos):
        self.escrituras += 1
        if self._repetido(datos.nombre):
            raise NombreDeSeleccionRepetido(datos.nombre)
        nueva = SeleccionGuardada(
            id=len(self.selecciones) + 1, datos=datos, creado_en=MOMENTO, actualizado_en=MOMENTO
        )
        self.selecciones[nueva.id] = nueva
        return nueva

    def actualizar(self, seleccion_id, datos):
        self.escrituras += 1
        actual = self.selecciones.get(seleccion_id)
        if actual is None:
            return None
        if self._repetido(datos.nombre, excepto=seleccion_id):
            raise NombreDeSeleccionRepetido(datos.nombre)
        self.selecciones[seleccion_id] = replace(actual, datos=datos)
        return self.selecciones[seleccion_id]

    def eliminar(self, seleccion_id):
        return self.selecciones.pop(seleccion_id, None) is not None


def _servicio():
    repositorio = RepositorioFalso()
    return SeleccionesService(repositorio), repositorio


def test_una_seleccion_bien_armada_no_tiene_problemas() -> None:
    assert problemas_de(VALIDA) == ()


@pytest.mark.parametrize(
    ("cambio", "parte"),
    [
        ({"nombre": "   "}, ParteSeleccion.NOMBRE),
        ({"filtros": ("campo_inventado:igual:x",)}, ParteSeleccion.FILTRO),
        ({"filtros": ("dias_atraso:igual:mucho",)}, ParteSeleccion.FILTRO),
        ({"filtros": ("region:parecido:x",)}, ParteSeleccion.FILTRO),
        ({"orden": "-campo_inventado"}, ParteSeleccion.ORDEN),
        ({"cantidad": 0}, ParteSeleccion.CANTIDAD),
        ({"cantidad": CANTIDAD_MAXIMA + 1}, ParteSeleccion.CANTIDAD),
        ({"indicadores": ("capital:suma:region",)}, ParteSeleccion.INDICADOR),
        ({"indicadores": ("productos:conteo", "productos:conteo")}, ParteSeleccion.INDICADOR),
    ],
)
def test_cada_parte_que_no_aplica_se_marca(cambio, parte) -> None:
    problemas = problemas_de(replace(VALIDA, **cambio))

    assert [problema.parte for problema in problemas] == [parte]


def test_guardar_quita_espacios_y_partes_vacias() -> None:
    servicio, _ = _servicio()
    sucia = replace(
        VALIDA, nombre="  Mi seleccion  ", filtros=(" telefono:no_vacio ", "  "), orden=" "
    )

    guardada = servicio.crear(sucia)

    assert guardada.seleccion.datos.nombre == "Mi seleccion"
    assert guardada.seleccion.datos.filtros == ("telefono:no_vacio",)
    assert guardada.seleccion.datos.orden is None
    assert guardada.aplicable


def test_una_seleccion_que_no_aplica_no_se_guarda() -> None:
    servicio, repositorio = _servicio()

    with pytest.raises(SeleccionInvalida) as error:
        servicio.crear(replace(VALIDA, filtros=("campo_inventado:igual:x",)))

    assert error.value.problemas[0].expresion == "campo_inventado:igual:x"
    assert repositorio.escrituras == 0


def test_al_cargar_una_seleccion_que_perdio_validez_se_marca_sin_perderla() -> None:
    servicio, repositorio = _servicio()
    # Guardada cuando el catalogo tenia un campo que despues se retiro.
    rota = replace(VALIDA, filtros=("campo_retirado:igual:x", "telefono:no_vacio"))
    repositorio.selecciones[1] = SeleccionGuardada(1, rota, MOMENTO, MOMENTO)

    revisada = servicio.obtener(1)
    listada = servicio.listar()[0]

    assert not revisada.aplicable
    assert [(p.parte, p.expresion) for p in revisada.problemas] == [
        (ParteSeleccion.FILTRO, "campo_retirado:igual:x")
    ]
    assert revisada.seleccion.datos.filtros == rota.filtros  # nada se pierde
    assert not listada.aplicable


def test_el_nombre_repetido_no_distingue_mayusculas() -> None:
    servicio, _ = _servicio()
    servicio.crear(VALIDA)

    with pytest.raises(NombreDeSeleccionRepetido):
        servicio.crear(replace(VALIDA, nombre=VALIDA.nombre.upper()))


def test_actualizar_y_eliminar() -> None:
    servicio, _ = _servicio()
    creada = servicio.crear(VALIDA)

    actualizada = servicio.actualizar(creada.seleccion.id, replace(VALIDA, cantidad=100))
    servicio.eliminar(creada.seleccion.id)

    assert actualizada.seleccion.datos.cantidad == 100
    with pytest.raises(SeleccionNoEncontrada):
        servicio.obtener(creada.seleccion.id)


def test_actualizar_o_eliminar_una_que_no_existe() -> None:
    servicio, _ = _servicio()

    with pytest.raises(SeleccionNoEncontrada):
        servicio.actualizar(99, VALIDA)
    with pytest.raises(SeleccionNoEncontrada):
        servicio.eliminar(99)


def test_revisar_no_guarda_nada() -> None:
    servicio, repositorio = _servicio()

    problemas = servicio.revisar(replace(VALIDA, orden="-inventado"))

    assert [problema.parte for problema in problemas] == [ParteSeleccion.ORDEN]
    assert repositorio.escrituras == 0
