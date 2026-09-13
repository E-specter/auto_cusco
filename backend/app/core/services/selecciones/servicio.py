"""Caso de uso: guardar, revisar y compartir selecciones de cartera.

Al guardar, una seleccion con partes que no aplican se rechaza. Al cargarla, se
devuelve igual pero marcando que parte dejo de aplicar, para que el analista
vea que se rompio en vez de perder la seleccion.
"""

from app.core.entities.cartera import ConsultaInvalida
from app.core.entities.selecciones import (
    LARGO_MAXIMO_NOMBRE,
    DatosSeleccion,
    ParteSeleccion,
    ProblemaSeleccion,
    SeleccionGuardada,
    SeleccionInvalida,
    SeleccionNoEncontrada,
    SeleccionRevisada,
)
from app.core.ports.repositorio_selecciones_port import RepositorioSeleccionesPort
from app.core.services.seleccion_cartera import campos, expresiones
from app.core.services.seleccion_cartera.servicio import CANTIDAD_MAXIMA


def problemas_de(datos: DatosSeleccion) -> tuple[ProblemaSeleccion, ...]:
    """Partes de la seleccion que no aplican sobre el catalogo de campos actual."""
    problemas: list[ProblemaSeleccion] = []
    if not 1 <= len(datos.nombre.strip()) <= LARGO_MAXIMO_NOMBRE:
        problemas.append(
            ProblemaSeleccion(
                ParteSeleccion.NOMBRE,
                datos.nombre,
                f"El nombre debe tener entre 1 y {LARGO_MAXIMO_NOMBRE} caracteres",
            )
        )
    for crudo in datos.filtros:
        try:
            campos.validar_filtro(expresiones.parsear_filtro(crudo))
        except ConsultaInvalida as exc:
            problemas.append(ProblemaSeleccion(ParteSeleccion.FILTRO, crudo, str(exc)))
    if datos.orden:
        try:
            campos.validar_orden(expresiones.parsear_orden(datos.orden))
        except ConsultaInvalida as exc:
            problemas.append(ProblemaSeleccion(ParteSeleccion.ORDEN, datos.orden, str(exc)))
    if datos.cantidad is not None and not 1 <= datos.cantidad <= CANTIDAD_MAXIMA:
        problemas.append(
            ProblemaSeleccion(
                ParteSeleccion.CANTIDAD,
                str(datos.cantidad),
                f"La cantidad debe estar entre 1 y {CANTIDAD_MAXIMA}",
            )
        )
    nombres: set[str] = set()
    for crudo in datos.indicadores:
        try:
            indicador = expresiones.parsear_indicador(crudo)
            campos.validar_indicador(indicador)
        except ConsultaInvalida as exc:
            problemas.append(ProblemaSeleccion(ParteSeleccion.INDICADOR, crudo, str(exc)))
            continue
        if indicador.nombre in nombres:
            problemas.append(
                ProblemaSeleccion(
                    ParteSeleccion.INDICADOR,
                    crudo,
                    f"El indicador {indicador.nombre!r} esta repetido",
                )
            )
        nombres.add(indicador.nombre)
    return tuple(problemas)


def _limpiar(datos: DatosSeleccion) -> DatosSeleccion:
    """Quita espacios sobrantes y partes vacias antes de revisar o guardar."""
    return DatosSeleccion(
        nombre=datos.nombre.strip(),
        filtros=tuple(filtro.strip() for filtro in datos.filtros if filtro.strip()),
        orden=(datos.orden or "").strip() or None,
        cantidad=datos.cantidad,
        indicadores=tuple(i.strip() for i in datos.indicadores if i.strip()),
    )


class SeleccionesService:
    def __init__(self, repositorio: RepositorioSeleccionesPort) -> None:
        self._repositorio = repositorio

    def listar(self) -> list[SeleccionRevisada]:
        return [self._revisada(seleccion) for seleccion in self._repositorio.listar()]

    def obtener(self, seleccion_id: int) -> SeleccionRevisada:
        seleccion = self._repositorio.obtener(seleccion_id)
        if seleccion is None:
            raise SeleccionNoEncontrada(seleccion_id)
        return self._revisada(seleccion)

    def revisar(self, datos: DatosSeleccion) -> tuple[ProblemaSeleccion, ...]:
        """Que partes no aplican, sin guardar nada."""
        return problemas_de(_limpiar(datos))

    def crear(self, datos: DatosSeleccion) -> SeleccionRevisada:
        return self._revisada(self._repositorio.crear(self._validos(datos)))

    def actualizar(self, seleccion_id: int, datos: DatosSeleccion) -> SeleccionRevisada:
        seleccion = self._repositorio.actualizar(seleccion_id, self._validos(datos))
        if seleccion is None:
            raise SeleccionNoEncontrada(seleccion_id)
        return self._revisada(seleccion)

    def eliminar(self, seleccion_id: int) -> None:
        if not self._repositorio.eliminar(seleccion_id):
            raise SeleccionNoEncontrada(seleccion_id)

    @staticmethod
    def _validos(datos: DatosSeleccion) -> DatosSeleccion:
        limpios = _limpiar(datos)
        problemas = problemas_de(limpios)
        if problemas:
            raise SeleccionInvalida(problemas)
        return limpios

    @staticmethod
    def _revisada(seleccion: SeleccionGuardada) -> SeleccionRevisada:
        return SeleccionRevisada(seleccion=seleccion, problemas=problemas_de(seleccion.datos))
