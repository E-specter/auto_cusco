"""Generacion de filas de salida a partir de productos y una definicion de carga.

Cada columna se evalua con el motor de texto enriquecido (RF-42): una plantilla `[@campo]` se
compila a expresion, asi sigue dando lo mismo que antes (RF-54) y admite funciones en cadena. El
tipo de la columna lo sigue aplicando `formatos.convertir`, despues del motor: no hay dos
caminos de tipado.

Una columna puede llevar un valor por defecto y un contenido por segmento; la definicion declara
como se calcula el segmento y que hacer con un producto que no cae en ninguno (RF-49, RF-50).

Un error en un campo no detiene la generacion: se registra con su fila y su
campo, y el resto de la carga se sigue construyendo. Asi el usuario ve de una
vez todo lo que hay que corregir.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.core.entities.mapeo import (
    CampoSalida,
    DefinicionCarga,
    ErrorGeneracion,
    FilaExcluida,
    PlantillaInvalida,
    ValorNoGenerable,
)
from app.core.entities.segmentacion import (
    CriterioCalculado,
    PoliticaSinSegmento,
    Segmentacion,
    SegmentacionInvalida,
)
from app.core.entities.texto_enriquecido import (
    LIMITES,
    CodigoTexto,
    Expresion,
    ExpresionInvalida,
    LimitesExpresion,
    MotivoSinCota,
    Problema,
    TipoValor,
)
from app.core.services import segmentacion as servicio_segmentacion
from app.core.services.mapeo_campos import formatos
from app.core.services.texto_enriquecido import evaluador, sintaxis
from app.core.services.texto_enriquecido.evaluador import Compilada, NodoEvaluado


@dataclass(frozen=True)
class CargaGenerada:
    cabeceras: tuple[str, ...]
    filas: tuple[dict[str, Any], ...]
    errores: tuple[ErrorGeneracion, ...]
    exclusiones: tuple[FilaExcluida, ...] = ()

    @property
    def completa(self) -> bool:
        return not self.errores


@dataclass(frozen=True)
class CeldaDetallada:
    """Una celda de una fila con el detalle que necesita la previsualizacion (RF-47).

    `texto` es lo que produjo la columna (con el valor por defecto ya aplicado); `valor` es el
    valor final tipado, el mismo que escribe la carga; `problemas` son los del motor y, si el
    texto no cabe en el tipo de la columna, `valor_no_convertible`.
    """

    campo: CampoSalida
    texto: str
    valor: Any
    nodos: tuple[NodoEvaluado, ...]
    problemas: tuple[Problema, ...]
    cota: int | None
    motivo_sin_cota: MotivoSinCota | None
    usa_variante: bool


@dataclass(frozen=True)
class FilaDetallada:
    """Una fila con su segmento y el detalle de cada celda; sin celdas si se excluye."""

    segmento: str | None
    exclusion: FilaExcluida | None
    celdas: tuple[CeldaDetallada, ...]


@dataclass(frozen=True)
class _Columna:
    campo: CampoSalida
    por_defecto: Compilada
    variantes: Mapping[str, Compilada]
    # Atajos del contenido por defecto, decididos al compilar: una columna de texto fijo o de
    # variable directa se arma sin evaluar la expresion. Dan lo mismo que evaluarla.
    texto_fijo: str | None = None
    directa: str | None = None


class GeneradorCargas:
    """Compila una definicion una vez y la aplica a muchos productos.

    `campos_disponibles` son las variables de la fila: un mapa nombre -> tipo (como
    `CAMPOS_CARTERA`, o ya `TipoValor`) o solo los nombres, que se toman como texto (una columna
    de variable directa sale igual con cualquiera de los dos).

    `constantes` son variables del catalogo con el mismo valor en toda la carga (la fecha de envio,
    RF-55): el motor las pliega al compilar (B7) y el producto no las trae.
    """

    def __init__(
        self,
        definicion: DefinicionCarga,
        campos_disponibles: Iterable[str] | Mapping[str, Any],
        constantes: Mapping[str, Any] | None = None,
    ) -> None:
        self._definicion = definicion
        self._validar_nombres(definicion.campos)
        self._variables = variables_de(campos_disponibles)
        self._constantes = constantes
        self._segmentacion = definicion.segmentacion
        self._columnas = tuple(self._compilar_columna(campo) for campo in definicion.campos)
        self._claves_con_variante = {
            clave for columna in self._columnas for clave in columna.variantes
        }
        self._validar_segmentacion()

    # --- compilacion ---

    @staticmethod
    def _validar_nombres(campos: Sequence[CampoSalida]) -> None:
        vistos: set[str] = set()
        for campo in campos:
            if not campo.nombre.strip():
                raise PlantillaInvalida("Cada campo de salida necesita un nombre")
            if campo.nombre in vistos:
                raise PlantillaInvalida(f"El campo de salida {campo.nombre!r} esta repetido")
            vistos.add(campo.nombre)
        if not campos:
            raise PlantillaInvalida("La definicion no tiene campos de salida")

    def _compilar_columna(self, campo: CampoSalida) -> _Columna:
        donde = f"La columna {campo.nombre!r}"
        por_defecto = self._compilar(campo.plantilla, campo.expresion, donde)
        if campo.variantes and self._definicion.segmentacion is None:
            raise PlantillaInvalida(
                f"{donde} declara variantes por segmento y la definicion no tiene segmentacion"
            )
        variantes: dict[str, Compilada] = {}
        for variante in campo.variantes:
            donde_variante = f"La variante {variante.segmento!r} de la columna {campo.nombre!r}"
            if variante.segmento in variantes:
                raise PlantillaInvalida(f"{donde_variante} esta repetida")
            if variante.plantilla is None and variante.expresion is None:
                raise PlantillaInvalida(f"{donde_variante} no tiene contenido")
            if variante.plantilla is not None and variante.expresion is not None:
                raise PlantillaInvalida(f"{donde_variante} trae plantilla y expresion a la vez")
            variantes[variante.segmento] = self._compilar(
                variante.plantilla or "", variante.expresion, donde_variante
            )
        return _Columna(
            campo,
            por_defecto,
            variantes,
            texto_fijo=por_defecto.texto_fijo if not variantes else None,
            directa=por_defecto.referencia_directa if not variantes else None,
        )

    def _compilar(self, plantilla: str, expresion: Expresion | None, donde: str) -> Compilada:
        texto = plantilla if expresion is None else ""
        try:
            if expresion is None:
                # Una plantilla es la ruta de compatibilidad (RF-54): lo que funcionaba sin
                # limite de tamano sigue funcionando, asi que los topes de nodos y de texto
                # fijo crecen con ella. Una expresion explicita conserva los topes (RF-48).
                limites = limites_de_plantilla(plantilla)
                expresion = sintaxis.leer(plantilla, limites)
                return evaluador.compilar(
                    expresion, self._variables, limites, constantes=self._constantes
                )
            return evaluador.compilar(expresion, self._variables, constantes=self._constantes)
        except ExpresionInvalida as error:
            raise PlantillaInvalida(_mensaje(texto, donde, error)) from error

    def _validar_segmentacion(self) -> None:
        segmentacion = self._segmentacion
        if segmentacion is None:
            return
        try:
            servicio_segmentacion.validar(segmentacion)
        except SegmentacionInvalida as error:
            raise PlantillaInvalida(str(error)) from error
        variable = _variable_del_criterio(segmentacion)
        if variable not in self._variables:
            raise PlantillaInvalida(
                f"La segmentacion usa {variable!r}, que no existe en el producto"
            )
        posibles = servicio_segmentacion.segmentos_posibles(segmentacion)
        if posibles is None:
            if not self._claves_con_variante:
                raise PlantillaInvalida(
                    "La segmentacion por campo necesita al menos una variante por segmento"
                )
            return
        for clave in sorted(self._claves_con_variante - set(posibles)):
            raise PlantillaInvalida(
                f"La variante {clave!r} no es un segmento de la tabla de rangos"
            )

    # --- consulta ---

    @property
    def cabeceras(self) -> tuple[str, ...]:
        return tuple(campo.nombre for campo in self._definicion.campos)

    def campos_de_origen(self) -> tuple[str, ...]:
        """Campos del producto que la definicion necesita, sin repetir."""
        usados: dict[str, None] = {}
        for columna in self._columnas:
            for compilada in (columna.por_defecto, *columna.variantes.values()):
                for variable in compilada.variables:
                    usados[variable] = None
        if self._segmentacion is not None:
            usados[_variable_del_criterio(self._segmentacion)] = None
        return tuple(usados)

    # --- generacion ---

    def generar_fila(
        self, producto: Mapping[str, Any], numero_fila: int
    ) -> tuple[dict[str, Any] | None, list[ErrorGeneracion]]:
        """Las celdas del producto y sus errores; la fila es None si la definicion la excluye."""
        fila, errores, _ = self._evaluar(producto, numero_fila)
        return fila, errores

    def _evaluar(
        self, producto: Mapping[str, Any], numero_fila: int
    ) -> tuple[dict[str, Any] | None, list[ErrorGeneracion], FilaExcluida | None]:
        errores: list[ErrorGeneracion] = []
        clave = None
        if self._segmentacion is not None:
            clave = servicio_segmentacion.segmento_de(self._segmentacion, producto)
            if not self._reconocido(clave):
                if self._segmentacion.politica is PoliticaSinSegmento.EXCLUIR:
                    return None, errores, self._exclusion(numero_fila, clave, producto)
                # Usar por defecto: un segmento no reconocido no tiene variante en ninguna
                # columna, asi que cada una sale con su contenido por defecto.
        fila: dict[str, Any] = {}
        for columna in self._columnas:
            if columna.texto_fijo is not None:
                texto, crudo = columna.texto_fijo, None
            elif columna.directa is not None:
                crudo = producto.get(columna.directa)
                texto = "" if crudo is None else str(crudo)
            else:
                compilada = columna.por_defecto
                if clave is not None:
                    compilada = columna.variantes.get(clave, compilada)
                self._celda(columna.campo, compilada, producto, numero_fila, fila, errores)
                continue
            self._convertir(columna.campo, texto, crudo, numero_fila, fila, errores)
        return fila, errores, None

    @staticmethod
    def _celda(
        campo: CampoSalida,
        compilada: Compilada,
        producto: Mapping[str, Any],
        numero_fila: int,
        fila: dict[str, Any],
        errores: list[ErrorGeneracion],
    ) -> None:
        resultado = compilada.evaluar(producto)
        if resultado.problemas:
            fila[campo.nombre] = None
            errores.extend(_error(numero_fila, campo.nombre, p) for p in resultado.problemas)
            return
        GeneradorCargas._convertir(
            campo, resultado.texto, resultado.valor, numero_fila, fila, errores
        )

    @staticmethod
    def _convertir(
        campo: CampoSalida,
        texto: str,
        crudo: Any,
        numero_fila: int,
        fila: dict[str, Any],
        errores: list[ErrorGeneracion],
    ) -> None:
        """El tipo de la columna, siempre con `formatos.convertir`: un solo camino de tipado."""
        if texto == "" and campo.valor_por_defecto is not None:
            texto, crudo = campo.valor_por_defecto, None
        try:
            fila[campo.nombre] = formatos.convertir(campo, texto, crudo)
        except ValorNoGenerable as exc:
            fila[campo.nombre] = None
            errores.append(ErrorGeneracion(numero_fila, campo.nombre, exc.detalle))

    def _reconocido(self, clave: str | None) -> bool:
        """El segmento existe: un rango de la tabla, o un valor que alguna columna contempla."""
        if clave is None:
            return False
        if isinstance(self._segmentacion.criterio, CriterioCalculado):  # type: ignore[union-attr]
            return True
        return clave in self._claves_con_variante

    def _exclusion(
        self, numero_fila: int, clave: str | None, producto: Mapping[str, Any]
    ) -> FilaExcluida:
        criterio = self._segmentacion.criterio  # type: ignore[union-attr]
        if isinstance(criterio, CriterioCalculado):
            dias = producto.get(criterio.variable_dias)
            if dias is None or (isinstance(dias, str) and not dias.strip()):
                detalle = (
                    f"El producto no tiene dias en {criterio.variable_dias!r} "
                    "para ubicarlo en un segmento"
                )
            else:
                detalle = (
                    f"Los dias de {criterio.variable_dias!r} ({dias!r}) no caen en ningun segmento"
                )
        elif clave is None:
            detalle = f"El producto no tiene valor en {criterio.campo!r}, que define su segmento"
        else:
            detalle = f"El valor {clave!r} de {criterio.campo!r} no tiene contenido por segmento"
        pagare = producto.get("pagare")
        return FilaExcluida(
            numero_fila,
            CodigoTexto.SIN_SEGMENTO.value,
            detalle,
            None if pagare is None else str(pagare),
        )

    def detallar_fila(self, producto: Mapping[str, Any], numero_fila: int) -> FilaDetallada:
        """Lo mismo que `generar_fila`, con el segmento, el texto de cada nodo y la cota.

        Es para la previsualizacion, no para generar cargas: las celdas coinciden con las de
        `generar_fila` (una prueba lo comprueba), pero aqui cada celda se evalua por nodo.
        """
        clave = None
        if self._segmentacion is not None:
            clave = servicio_segmentacion.segmento_de(self._segmentacion, producto)
            if not self._reconocido(clave) and (
                self._segmentacion.politica is PoliticaSinSegmento.EXCLUIR
            ):
                return FilaDetallada(clave, self._exclusion(numero_fila, clave, producto), ())
        return FilaDetallada(
            clave,
            None,
            tuple(self._detallar_celda(columna, clave, producto) for columna in self._columnas),
        )

    @staticmethod
    def _detallar_celda(
        columna: _Columna, clave: str | None, producto: Mapping[str, Any]
    ) -> CeldaDetallada:
        campo = columna.campo
        usa_variante = clave is not None and clave in columna.variantes
        compilada = columna.variantes[clave] if usa_variante else columna.por_defecto  # type: ignore[index]
        resultado = compilada.evaluar_por_nodo(producto)
        problemas = list(resultado.problemas)
        texto = resultado.texto
        if texto == "" and campo.valor_por_defecto is not None:
            texto, crudo = campo.valor_por_defecto, None
        else:
            crudo = resultado.valor
        valor = None
        if not problemas:
            fila: dict[str, Any] = {}
            errores: list[ErrorGeneracion] = []
            GeneradorCargas._convertir(campo, texto, crudo, 0, fila, errores)
            valor = fila[campo.nombre]
            problemas.extend(
                Problema(CodigoTexto.VALOR_NO_CONVERTIBLE, error.detalle) for error in errores
            )
        return CeldaDetallada(
            campo=campo,
            texto=texto,
            valor=valor,
            nodos=resultado.nodos,
            problemas=tuple(problemas),
            cota=compilada.cota,
            motivo_sin_cota=compilada.motivo_sin_cota,
            usa_variante=usa_variante,
        )

    def generar(self, productos: Iterable[Mapping[str, Any]]) -> CargaGenerada:
        filas: list[dict[str, Any]] = []
        errores: list[ErrorGeneracion] = []
        exclusiones: list[FilaExcluida] = []
        for numero_fila, producto in enumerate(productos, start=1):
            fila, errores_fila, exclusion = self._evaluar(producto, numero_fila)
            errores.extend(errores_fila)
            if exclusion is not None:
                exclusiones.append(exclusion)
                continue
            filas.append(fila)  # type: ignore[arg-type]
        return CargaGenerada(
            cabeceras=self.cabeceras,
            filas=tuple(filas),
            errores=tuple(errores),
            exclusiones=tuple(exclusiones),
        )


def limites_de_plantilla(plantilla: str) -> LimitesExpresion:
    return LimitesExpresion(
        nodos=max(LIMITES.nodos, len(plantilla)),
        largo_literal=max(LIMITES.largo_literal, len(plantilla)),
    )


def variables_de(campos: Iterable[str] | Mapping[str, Any]) -> dict[str, TipoValor]:
    if isinstance(campos, Mapping):
        return {nombre: TipoValor(getattr(tipo, "value", tipo)) for nombre, tipo in campos.items()}
    return {nombre: TipoValor.TEXTO for nombre in campos}


def _variable_del_criterio(segmentacion: Segmentacion) -> str:
    criterio = segmentacion.criterio
    return criterio.variable_dias if isinstance(criterio, CriterioCalculado) else criterio.campo


def _error(numero_fila: int, campo: str, problema: Problema) -> ErrorGeneracion:
    return ErrorGeneracion(numero_fila, campo, problema.detalle, problema.codigo.value)


def _mensaje(plantilla: str, donde: str, error: ExpresionInvalida) -> str:
    """El texto de antes para los errores de una plantilla; el del motor para el resto."""
    problema = error.problemas[0]
    if plantilla:
        if problema.codigo is CodigoTexto.REFERENCIA_VACIA:
            return f"La plantilla {plantilla!r} tiene una referencia vacia"
        if problema.codigo is CodigoTexto.SINTAXIS_INVALIDA and "sin cerrar" in problema.detalle:
            return f"La plantilla {plantilla!r} tiene un '[@' sin cerrar con ']'"
        if problema.codigo is CodigoTexto.VARIABLE_DESCONOCIDA and problema.nombre:
            return (
                f"La plantilla {plantilla!r} usa el campo {problema.nombre!r}, "
                "que no existe en el producto"
            )
    detalle = "; ".join(p.detalle for p in error.problemas)
    if plantilla:
        return f"La plantilla {plantilla!r} no es valida ({donde}): {detalle}"
    return f"{donde} no es valida: {detalle}"
