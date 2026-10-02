"""Forma JSON de una definicion de carga y su lectura estricta (seccion 8 del diseno, C-1 a C-10).

    {"nombre": "SMS",
     "proteger_formulas": true,
     "columnas": [
        {"nombre": "mensaje", "orden": 0, "expresion": {"nodos": [...]},
         "tipo": "texto", "formato_fecha": "dd/mm/aaaa", "formato_financiero": null,
         "valor_por_defecto": null,
         "variantes": [{"segmento": "1_a_8", "expresion": {"nodos": [...]}}]}],
     "segmentacion": {"criterio": {"tipo": "calculado", "variable_dias": null, "tabla": null},
                      "politica": "excluir"}}

Es la forma que guardan las definiciones (B4b) y que usa el constructor: columnas con `orden`
explicito, contenido solo como expresion (no hay `plantilla`) y el formato de fecha con marcas
legibles (`dd/mm/aaaa`), no con strftime. Todo lo que no es obligatorio puede faltar o ser `null`.
En un criterio calculado, una tabla o una variable de dias `null` se resuelven con las del contexto:
una definicion de MOWA MES no repite su tabla.

La columna se identifica por su posicion en la lista del pedido (`columna` de cada problema, desde
0); las columnas de la definicion salen ordenadas por `orden` y `DefinicionLeida.posiciones` dice
a que posicion del pedido corresponde cada una.

Como la expresion, la lectura no revienta con lo imposible: informa cada falla como un problema con
su columna, su variante y el campo (`ProblemaDeDefinicion`). Que las variables y funciones
existan, y los limites de tamano, los comprueba despues `diagnostico.diagnosticar`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, NamedTuple

from app.core.entities.mapeo import (
    CampoSalida,
    DefinicionCarga,
    FormatoFinanciero,
    TipoSalida,
    VarianteCampo,
)
from app.core.entities.segmentacion import (
    CriterioCalculado,
    CriterioCampo,
    PoliticaSinSegmento,
    RangoDias,
    Segmentacion,
)
from app.core.entities.texto_enriquecido import (
    CodigoTexto,
    Expresion,
    ExpresionInvalida,
    Problema,
)
from app.core.services.texto_enriquecido.funciones.fecha import validar_marcas
from app.core.services.texto_enriquecido.serializacion import expresion_desde_dict


@dataclass(frozen=True)
class ProblemaDeDefinicion:
    """Un problema y donde esta.

    `columna` es la posicion de la columna en la lista del pedido (desde 0) y `segmento` la clave
    de la variante, o None si es del contenido por defecto. `campo` nombra el campo con el
    problema: de la columna (`nombre`, `orden`, `tipo`, `formato_fecha`...) o, sin columna, de la
    definicion (`definicion`, `nombre`, `columnas`, `segmentacion`, `proteger_formulas`).
    """

    problema: Problema
    columna: int | None = None
    segmento: str | None = None
    campo: str | None = None


class DefinicionLeida(NamedTuple):
    """La definicion con sus columnas ya ordenadas por `orden`.

    `posiciones[i]` es la posicion en el pedido de la columna `i` de la definicion.
    """

    definicion: DefinicionCarga
    posiciones: tuple[int, ...]


class DefinicionIlegible(Exception):
    """La definicion no tiene la forma JSON esperada. `problemas` dice donde esta cada falla."""

    def __init__(self, problemas: Sequence[ProblemaDeDefinicion]) -> None:
        super().__init__("; ".join(p.problema.detalle for p in problemas))
        self.problemas = tuple(problemas)


def definicion_desde_dict(
    dato: Any,
    tabla_por_defecto: Sequence[RangoDias],
    variable_dias_por_defecto: str,
) -> DefinicionLeida:
    """Lee la forma JSON. Si no la tiene, `DefinicionIlegible` con todos los problemas."""
    problemas: list[ProblemaDeDefinicion] = []
    lector = _Lector(problemas, tuple(tabla_por_defecto), variable_dias_por_defecto)
    leida = lector.definicion(dato)
    if problemas or leida is None:
        raise DefinicionIlegible(problemas)
    return leida


class _Lector:
    def __init__(
        self,
        problemas: list[ProblemaDeDefinicion],
        tabla: tuple[RangoDias, ...],
        variable_dias: str,
    ) -> None:
        self._problemas = problemas
        self._tabla = tabla
        self._variable_dias = variable_dias

    def _falla(
        self,
        detalle: str,
        columna: int | None = None,
        segmento: str | None = None,
        campo: str | None = None,
        codigo: CodigoTexto = CodigoTexto.DEFINICION_INVALIDA,
        parametro: str | None = None,
    ) -> None:
        problema = Problema(codigo, detalle, parametro=parametro)
        self._problemas.append(ProblemaDeDefinicion(problema, columna, segmento, campo))

    def _claves(
        self,
        dato: Mapping[str, Any],
        permitidas: set[str],
        donde: str,
        columna: int | None = None,
        segmento: str | None = None,
        campo: str | None = None,
    ) -> None:
        sobran = set(dato) - permitidas
        if sobran:
            self._falla(f"{donde} no lleva {sorted(sobran)}", columna, segmento, campo)

    # --- definicion ---

    def definicion(self, dato: Any) -> DefinicionLeida | None:
        if not isinstance(dato, Mapping):
            self._falla(
                "Una definicion es un objeto con `nombre`, `columnas` y `segmentacion`",
                campo="definicion",
            )
            return None
        self._claves(
            dato,
            {"nombre", "columnas", "segmentacion", "proteger_formulas"},
            "Una definicion",
            campo="definicion",
        )
        nombre = dato.get("nombre") or ""
        if not isinstance(nombre, str):
            self._falla("El `nombre` de la definicion es un texto", campo="nombre")
            nombre = ""
        proteger = dato.get("proteger_formulas")
        if proteger is None:
            proteger = True
        elif not isinstance(proteger, bool):
            self._falla("`proteger_formulas` es verdadero o falso", campo="proteger_formulas")
            proteger = True
        crudas = dato.get("columnas")
        columnas: list[tuple[int, int, CampoSalida]] = []  # (orden, posicion, columna)
        if not isinstance(crudas, list):
            self._falla("`columnas` es una lista de columnas", campo="columnas")
        else:
            nombres: set[str] = set()
            ordenes: set[int] = set()
            for posicion, cruda in enumerate(crudas):
                leida = self._columna(cruda, posicion, nombres, ordenes)
                if leida is not None:
                    columnas.append((leida[0], posicion, leida[1]))
        segmentacion = self._segmentacion(dato.get("segmentacion"))
        columnas.sort(key=lambda c: (c[0], c[1]))
        definicion = DefinicionCarga(nombre, tuple(c[2] for c in columnas), segmentacion, proteger)
        return DefinicionLeida(definicion, tuple(c[1] for c in columnas))

    # --- columnas ---

    def _columna(
        self, crudo: Any, indice: int, nombres: set[str], ordenes: set[int]
    ) -> tuple[int, CampoSalida] | None:
        if not isinstance(crudo, Mapping):
            self._falla(f"La columna {indice + 1} es un objeto", indice)
            return None
        antes = len(self._problemas)
        self._claves(
            crudo,
            {
                "nombre",
                "orden",
                "expresion",
                "tipo",
                "formato_fecha",
                "formato_financiero",
                "valor_por_defecto",
                "variantes",
            },
            "Una columna",
            indice,
        )
        nombre = self._nombre(crudo.get("nombre"), indice, nombres)
        orden = self._orden(crudo.get("orden"), indice, ordenes)
        por_defecto = self._texto(crudo, "valor_por_defecto", indice)
        patron_fecha = self._formato_fecha(crudo.get("formato_fecha"), indice)
        expresion = self._expresion(crudo.get("expresion"), indice, requerida=True)
        tipo = self._tipo(crudo.get("tipo"), indice)
        financiero = self._financiero(crudo.get("formato_financiero"), indice)
        variantes = self._variantes(crudo.get("variantes"), indice)
        if len(self._problemas) > antes or nombre is None or orden is None:
            return None
        return orden, CampoSalida(
            nombre=nombre,
            plantilla="",
            tipo=tipo,
            patron_fecha=patron_fecha,
            formato_financiero=financiero,
            expresion=expresion,
            valor_por_defecto=por_defecto,
            variantes=variantes,
        )

    def _nombre(self, valor: Any, indice: int, vistos: set[str]) -> str | None:
        if not isinstance(valor, str) or not valor.strip():
            self._falla("La columna necesita un `nombre` con texto", indice, campo="nombre")
            return None
        if valor in vistos:
            self._falla(f"El nombre {valor!r} esta repetido", indice, campo="nombre")
            return None
        vistos.add(valor)
        return valor

    def _orden(self, valor: Any, indice: int, vistos: set[int]) -> int | None:
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
            self._falla("El `orden` es un entero desde 0", indice, campo="orden")
            return None
        if valor in vistos:
            self._falla(f"El orden {valor} esta repetido", indice, campo="orden")
            return None
        vistos.add(valor)
        return valor

    def _texto(
        self, crudo: Mapping[str, Any], clave: str, columna: int, segmento: str | None = None
    ) -> str | None:
        valor = crudo.get(clave)
        if valor is None:
            return None
        if not isinstance(valor, str):
            self._falla(f"`{clave}` es un texto", columna, segmento, clave)
            return None
        return valor

    def _formato_fecha(self, valor: Any, columna: int) -> str | None:
        """Un patron de marcas: sin ninguna marca valida no es un formato, es un texto fijo."""
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            return None
        if not isinstance(valor, str):
            self._falla("`formato_fecha` es un texto", columna, campo="formato_fecha")
            return None
        try:
            validar_marcas(valor)
        except ValueError as error:
            self._falla(
                f"El formato de fecha {valor!r} {error}",
                columna,
                campo="formato_fecha",
                codigo=CodigoTexto.PARAMETRO_INVALIDO,
                parametro="formato_fecha",
            )
            return None
        return valor

    def _expresion(
        self, crudo: Any, columna: int, segmento: str | None = None, requerida: bool = False
    ) -> Expresion | None:
        if crudo is None:
            if requerida:
                self._falla("Falta la `expresion`", columna, segmento, "expresion")
            return None
        try:
            return expresion_desde_dict(crudo)
        except ExpresionInvalida as error:
            self._problemas.extend(
                ProblemaDeDefinicion(problema, columna, segmento) for problema in error.problemas
            )
            return None

    def _tipo(self, crudo: Any, columna: int) -> TipoSalida:
        if crudo is None:
            return TipoSalida.TEXTO
        try:
            return TipoSalida(crudo)
        except ValueError:
            admitidos = ", ".join(t.value for t in TipoSalida)
            self._falla(
                f"El `tipo` {crudo!r} no existe: es uno de {admitidos}", columna, campo="tipo"
            )
            return TipoSalida.TEXTO

    def _financiero(self, crudo: Any, columna: int) -> FormatoFinanciero:
        campo = "formato_financiero"
        if crudo is None:
            return FormatoFinanciero()
        if not isinstance(crudo, Mapping):
            self._falla("`formato_financiero` es un objeto", columna, campo=campo)
            return FormatoFinanciero()
        self._claves(
            crudo,
            {"separador_miles", "separador_decimal", "decimales"},
            "`formato_financiero`",
            columna,
            campo=campo,
        )
        base = FormatoFinanciero()
        miles = crudo.get("separador_miles", base.separador_miles)
        decimal = crudo.get("separador_decimal", base.separador_decimal)
        decimales = crudo.get("decimales", base.decimales)
        if not isinstance(miles, str) or len(miles) > 1:
            self._falla(
                "`separador_miles` es un texto de a lo mas un caracter", columna, campo=campo
            )
            miles = base.separador_miles
        if not isinstance(decimal, str) or len(decimal) != 1:
            self._falla("`separador_decimal` es un texto de un caracter", columna, campo=campo)
            decimal = base.separador_decimal
        if isinstance(decimales, bool) or not isinstance(decimales, int) or not 0 <= decimales <= 6:
            self._falla("`decimales` es un entero entre 0 y 6", columna, campo=campo)
            decimales = base.decimales
        return FormatoFinanciero(miles, decimal, decimales)

    def _variantes(self, crudo: Any, columna: int) -> tuple[VarianteCampo, ...]:
        if crudo is None:
            return ()
        if not isinstance(crudo, list):
            self._falla("`variantes` es una lista", columna, campo="variantes")
            return ()
        variantes: list[VarianteCampo] = []
        for posicion, cruda in enumerate(crudo, start=1):
            if not isinstance(cruda, Mapping):
                self._falla(f"La variante {posicion} es un objeto", columna, campo="variantes")
                continue
            segmento = cruda.get("segmento")
            if not isinstance(segmento, str) or not segmento:
                self._falla(
                    f"La variante {posicion} necesita un `segmento` de texto",
                    columna,
                    campo="variantes",
                )
                continue
            self._claves(cruda, {"segmento", "expresion"}, "Una variante", columna, segmento)
            expresion = self._expresion(cruda.get("expresion"), columna, segmento, requerida=True)
            variantes.append(VarianteCampo(segmento, None, expresion))
        return tuple(variantes)

    # --- segmentacion ---

    def _segmentacion(self, crudo: Any) -> Segmentacion | None:
        if crudo is None:
            return None
        if not isinstance(crudo, Mapping):
            self._falla(
                "`segmentacion` es un objeto con `criterio` y `politica`", campo="segmentacion"
            )
            return None
        self._claves(crudo, {"criterio", "politica"}, "La segmentacion", campo="segmentacion")
        criterio = self._criterio(crudo.get("criterio"))
        politica = PoliticaSinSegmento.EXCLUIR
        if crudo.get("politica") is not None:
            try:
                politica = PoliticaSinSegmento(crudo["politica"])
            except ValueError:
                admitidas = ", ".join(p.value for p in PoliticaSinSegmento)
                self._falla(
                    f"La `politica` {crudo['politica']!r} no existe: es {admitidas}",
                    campo="segmentacion",
                )
        if criterio is None:
            return None
        return Segmentacion(criterio, politica)

    def _criterio(self, crudo: Any) -> CriterioCalculado | CriterioCampo | None:
        if crudo is None:
            return CriterioCalculado(self._tabla, self._variable_dias)
        if not isinstance(crudo, Mapping):
            self._falla("`criterio` es un objeto con su `tipo`", campo="segmentacion")
            return None
        tipo = crudo.get("tipo")
        if tipo == "campo":
            self._claves(crudo, {"tipo", "campo"}, "Un criterio por campo", campo="segmentacion")
            campo = crudo.get("campo")
            if not isinstance(campo, str) or not campo.strip():
                self._falla(
                    "El criterio por campo necesita el nombre del `campo`", campo="segmentacion"
                )
                return None
            return CriterioCampo(campo)
        if tipo == "calculado":
            self._claves(
                crudo,
                {"tipo", "variable_dias", "tabla"},
                "Un criterio calculado",
                campo="segmentacion",
            )
            variable = crudo.get("variable_dias")
            if variable is not None and not isinstance(variable, str):
                self._falla("`variable_dias` es un texto", campo="segmentacion")
                return None
            tabla = self._tabla if crudo.get("tabla") is None else self._rangos(crudo["tabla"])
            if tabla is None:
                return None
            return CriterioCalculado(tabla, variable or self._variable_dias)
        self._falla(
            f"El tipo de criterio {tipo!r} no existe: es `calculado` o `campo`",
            campo="segmentacion",
        )
        return None

    def _rangos(self, crudo: Any) -> tuple[RangoDias, ...] | None:
        if not isinstance(crudo, list):
            self._falla("`tabla` es una lista de rangos", campo="segmentacion")
            return None
        rangos: list[RangoDias] = []
        for posicion, cruda in enumerate(crudo, start=1):
            rango = self._rango(cruda, posicion)
            if rango is not None:
                rangos.append(rango)
        return tuple(rangos) if len(rangos) == len(crudo) else None

    def _rango(self, crudo: Any, posicion: int) -> RangoDias | None:
        if not isinstance(crudo, Mapping):
            self._falla(f"El rango {posicion} es un objeto", campo="segmentacion")
            return None
        self._claves(
            crudo, {"clave", "etiqueta", "desde", "hasta"}, "Un rango", campo="segmentacion"
        )
        clave, etiqueta = crudo.get("clave"), crudo.get("etiqueta")
        desde, hasta = crudo.get("desde"), crudo.get("hasta")
        if not isinstance(clave, str) or not isinstance(etiqueta, str):
            self._falla(
                f"El rango {posicion} necesita `clave` y `etiqueta` de texto", campo="segmentacion"
            )
            return None
        for limite in (desde, hasta):
            if limite is not None and (isinstance(limite, bool) or not isinstance(limite, int)):
                self._falla(
                    f"`desde` y `hasta` del rango {clave!r} son enteros o nulos",
                    campo="segmentacion",
                )
                return None
        return RangoDias(clave, etiqueta, desde, hasta)
