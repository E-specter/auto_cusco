"""Caso de uso: generar la tabla de carga de una seleccion de cartera (RF-09, RF-15).

La seleccion se lee por paginas y las filas de salida se van construyendo sobre
la marcha, asi una carga de decenas de miles de productos no obliga a tener en
memoria la cartera entera: solo la pagina en curso y las columnas que la
definicion pide.

El resultado se entrega como `Tabla`, lista para que un exportador la escriba
en XLSX, CSV o JSON (RF-13). Este servicio no elige el formato.
"""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.core.entities.cartera import ConsultaInvalida, Filtro, Orden
from app.core.entities.exportacion import Tabla
from app.core.entities.mapeo import DefinicionCarga, ErrorGeneracion
from app.core.services.mapeo_campos.generador import GeneradorCargas
from app.core.services.seleccion_cartera.campos import CAMPOS_CARTERA
from app.core.services.seleccion_cartera.servicio import LIMITE_MAXIMO, ConsultaCarteraService

CANTIDAD_POR_DEFECTO = 1_000
# Tope de productos por archivo, medido y no estimado: ha habido sabanas de mas
# de 55 000 filas, y con 120 000 la generacion sigue siendo lineal en tiempo y
# razonable en memoria (docs/generacion-cargas.md, seccion 4). Volver a medir
# con scripts/medir_generacion.py antes de subirlo.
CANTIDAD_MAXIMA = 120_000


@dataclass(frozen=True)
class ResultadoGeneracion:
    """La tabla generada y lo que el usuario necesita saber sobre ella."""

    tabla: Tabla
    disponibles: int
    solicitados: int
    errores: tuple[ErrorGeneracion, ...]

    @property
    def generados(self) -> int:
        return self.tabla.cantidad

    @property
    def suficiente(self) -> bool:
        """Habia al menos tantos productos como se pidieron (RF-08)."""
        return self.disponibles >= self.solicitados

    @property
    def completa(self) -> bool:
        return not self.errores


class GeneracionCargasService:
    def __init__(self, consulta: ConsultaCarteraService) -> None:
        self._consulta = consulta

    def generar(
        self,
        fecha_corte: date,
        definicion: DefinicionCarga,
        filtros: Sequence[Filtro] = (),
        orden: Orden | None = None,
        cantidad: int = CANTIDAD_POR_DEFECTO,
    ) -> ResultadoGeneracion:
        """Aplica la definicion a los primeros `cantidad` productos de la seleccion."""
        if not 1 <= cantidad <= CANTIDAD_MAXIMA:
            raise ConsultaInvalida(f"La cantidad debe estar entre 1 y {CANTIDAD_MAXIMA}")
        # Compilar antes de consultar: una plantilla mal escrita se rechaza sin
        # haber tocado la base de datos.
        generador = GeneradorCargas(definicion, CAMPOS_CARTERA)
        seleccion = _SeleccionPaginada(self._consulta, fecha_corte, filtros, orden, cantidad)
        carga = generador.generar(seleccion)
        return ResultadoGeneracion(
            tabla=Tabla(nombre=definicion.nombre, cabeceras=carga.cabeceras, filas=carga.filas),
            disponibles=seleccion.disponibles,
            solicitados=cantidad,
            errores=carga.errores,
        )


class _SeleccionPaginada:
    """Recorre la seleccion en paginas del tamano que admite la consulta.

    La consulta ya ordena con un desempate estable por pagare, asi que paginar
    no repite ni salta productos.
    """

    def __init__(
        self,
        consulta: ConsultaCarteraService,
        fecha_corte: date,
        filtros: Sequence[Filtro],
        orden: Orden | None,
        cantidad: int,
    ) -> None:
        self._consulta = consulta
        self._fecha_corte = fecha_corte
        self._filtros = tuple(filtros)
        self._orden = orden
        self._cantidad = cantidad
        # Primera pagina por adelantado: valida la consulta y deja el total
        # disponible a la vista antes de generar nada.
        self._primera = self._pagina(desplazamiento=0)
        self.disponibles: int = self._primera.total

    def __iter__(self) -> Iterator[Mapping[str, Any]]:
        entregados = 0
        pagina = self._primera
        while pagina.filas:
            for fila in pagina.filas:
                yield fila
                entregados += 1
            if entregados >= min(self._cantidad, self.disponibles):
                return
            pagina = self._pagina(desplazamiento=entregados)

    def _pagina(self, desplazamiento: int):
        limite = min(self._cantidad - desplazamiento, LIMITE_MAXIMO)
        return self._consulta.consultar(
            self._fecha_corte,
            self._filtros,
            self._orden,
            limite=max(limite, 1),
            desplazamiento=desplazamiento,
        )
