"""Caso de uso: generar la tabla de carga de una seleccion de cartera (RF-09, RF-15).

La seleccion se lee por paginas y las filas de salida se van construyendo sobre
la marcha, asi una carga de decenas de miles de productos no obliga a tener en
memoria la cartera entera: solo la pagina en curso y las columnas que la
definicion pide.

El resultado se entrega como `Tabla`, lista para que un exportador la escriba
en XLSX, CSV o JSON (RF-13). Este servicio no elige el formato.

La carga tiene una fecha de envio (RF-55): la pedida o, sin ella, hoy en Lima, nunca anterior a la
fecha de corte. Con ella la cartera ofrece `fecha_envio` (una constante de la carga) y
`dias_atraso_ajustados` (por producto), y una segmentacion calculada puede usarlos.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.core.entities.cartera import ConsultaInvalida, Filtro, Orden
from app.core.entities.exportacion import Tabla
from app.core.entities.mapeo import DefinicionCarga, ErrorGeneracion, FilaExcluida
from app.core.services.fecha_envio import (
    DIAS_AJUSTADOS,
    VARIABLES_DE_ENVIO,
    EnvioDeCarga,
    Reloj,
    hoy_en_lima,
)
from app.core.services.mapeo_campos.generador import GeneradorCargas
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.core.services.seleccion_cartera.recorrido import SeleccionPaginada
from app.core.services.seleccion_cartera.servicio import (
    CANTIDAD_MAXIMA,
    ConsultaCarteraService,
)

CANTIDAD_POR_DEFECTO = 1_000


@dataclass(frozen=True)
class ResultadoGeneracion:
    """La tabla generada y lo que el usuario necesita saber sobre ella.

    Los numeros cierran asi: de los `solicitados` se evaluan `min(disponibles, solicitados)`
    productos y cada uno o sale en la tabla o se excluye con su motivo (RF-50), es decir
    `generados + excluidos == min(disponibles, solicitados)`. `suficiente` habla de la seleccion
    (habia productos para lo pedido), no de la tabla: con exclusiones puede ser verdadero y haber
    menos `generados` que `solicitados`.
    """

    tabla: Tabla
    disponibles: int
    solicitados: int
    errores: tuple[ErrorGeneracion, ...]
    fecha_envio: date  # la que se uso: la pedida o, sin ella, hoy en Lima (RF-55)
    exclusiones: tuple[FilaExcluida, ...] = ()

    @property
    def generados(self) -> int:
        return self.tabla.cantidad

    @property
    def excluidos(self) -> int:
        return len(self.exclusiones)

    @property
    def suficiente(self) -> bool:
        """Habia al menos tantos productos como se pidieron (RF-08)."""
        return self.disponibles >= self.solicitados

    @property
    def completa(self) -> bool:
        return not self.errores


class GeneracionCargasService:
    def __init__(self, consulta: ConsultaCarteraService, hoy: Reloj = hoy_en_lima) -> None:
        self._consulta = consulta
        self._hoy = hoy

    @property
    def catalogo(self) -> CatalogoCartera:
        """El catalogo de campos con el que se arman filtros y columnas."""
        return self._consulta.catalogo

    def generar(
        self,
        fecha_corte: date,
        definicion: DefinicionCarga,
        filtros: Sequence[Filtro] = (),
        orden: Orden | None = None,
        cantidad: int = CANTIDAD_POR_DEFECTO,
        fecha_envio: date | None = None,
    ) -> ResultadoGeneracion:
        """Aplica la definicion a los primeros `cantidad` productos de la seleccion.

        `fecha_envio` por defecto es hoy en Lima; si es anterior a `fecha_corte` lanza
        `FechaEnvioAnterior` (con las dos fechas) antes de tocar la base de datos.
        """
        if not 1 <= cantidad <= CANTIDAD_MAXIMA:
            raise ConsultaInvalida(f"La cantidad debe estar entre 1 y {CANTIDAD_MAXIMA}")
        envio = EnvioDeCarga.de(fecha_corte, fecha_envio, self._hoy)
        # Compilar antes de consultar: una plantilla mal escrita se rechaza sin
        # haber tocado la base de datos.
        variables = {**self._consulta.catalogo.tipos(), **VARIABLES_DE_ENVIO}
        generador = GeneradorCargas(definicion, variables, envio.constantes(variables))
        seleccion = SeleccionPaginada(self._consulta, fecha_corte, filtros, orden, cantidad)
        # Los dias ajustados se calculan por producto, y solo si la definicion los usa.
        usa_dias = DIAS_AJUSTADOS in generador.campos_de_origen()
        carga = generador.generar(envio.ajustar_todos(seleccion) if usa_dias else seleccion)
        return ResultadoGeneracion(
            tabla=Tabla(nombre=definicion.nombre, cabeceras=carga.cabeceras, filas=carga.filas),
            disponibles=seleccion.disponibles,
            solicitados=cantidad,
            errores=carga.errores,
            fecha_envio=envio.fecha_envio,
            exclusiones=carga.exclusiones,
        )
