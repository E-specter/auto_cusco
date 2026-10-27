"""El catalogo de campos de la cartera: la base de la sabana mas los campos adicionales.

Los campos base se derivan de CATALOGO_VENCIDA para que no puedan desalinearse con lo que produce
la normalizacion ni con las columnas donde se guardan. Los campos adicionales (RF-64 a RF-66) los
crea el usuario y se leen de un puerto: `CatalogoCartera` es la UNICA fuente de los campos de la
cartera, y filtros, segmentacion, indicadores, variables del motor y columnas de carga la reciben
en lugar de importar una constante. Una capacidad nueva que use el catalogo ve los adicionales sin
codigo propio (RF-66). `CAMPOS_BASE` es solo la base: nadie fuera de este modulo la importa.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.entities.campos_adicionales import CampoAdicional, TipoAdicional
from app.core.entities.cartera import (
    OPERADORES_POR_TIPO,
    VALORES_POR_OPERADOR,
    ConsultaInvalida,
    Filtro,
    Funcion,
    Indicador,
    Orden,
    TipoDato,
)
from app.core.entities.sabana import TipoCampo
from app.core.ports.repositorio_campos_adicionales_port import RepositorioCamposAdicionalesPort
from app.core.services.ingesta_sabana.catalogo import CATALOGO_VENCIDA

_TIPOS = {
    TipoCampo.CLAVE: TipoDato.TEXTO,
    TipoCampo.TEXTO: TipoDato.TEXTO,
    TipoCampo.CATALOGO: TipoDato.TEXTO,
    TipoCampo.TELEFONO: TipoDato.TEXTO,
    TipoCampo.FINANCIERO: TipoDato.NUMERO,
    TipoCampo.ENTERO: TipoDato.NUMERO,
    TipoCampo.FECHA: TipoDato.FECHA,
    TipoCampo.BOOLEANO: TipoDato.BOOLEANO,
}
_TIPOS_ADICIONALES = {
    TipoAdicional.TEXTO: TipoDato.TEXTO,
    TipoAdicional.NUMERO: TipoDato.NUMERO,
    TipoAdicional.FECHA: TipoDato.FECHA,
}
# La columna duplicada del pagare se descarta al ingestar (regla N-8).
_FUERA_DE_CONSULTA = frozenset({"pagare_duplicado"})

_VERDADEROS = frozenset({"true", "si", "1", "verdadero"})
_FALSOS = frozenset({"false", "no", "0", "falso"})

# Con un campo base, la suma y el promedio solo aplican a un numero. Un campo adicional es mas
# estricto (RF-27): suma, promedio, minimo y maximo, solo si es un numero.
_FUNCIONES_NUMERICAS = frozenset({Funcion.SUMA, Funcion.PROMEDIO})
_FUNCIONES_NUMERICAS_ADICIONALES = _FUNCIONES_NUMERICAS | {Funcion.MINIMO, Funcion.MAXIMO}


@dataclass(frozen=True)
class CampoCartera:
    """Un campo de la cartera. Un campo base se muestra con `clave_etiqueta` (i18n, `campo.<n>`);
    uno adicional, con `etiqueta`, el nombre legible que escribio el usuario."""

    nombre: str
    tipo: TipoDato
    clave_etiqueta: str | None = None
    etiqueta: str | None = None
    adicional: bool = False
    archivado: bool = False


def _construir_campos() -> dict[str, TipoDato]:
    campos: dict[str, TipoDato] = {}
    for columna in CATALOGO_VENCIDA:
        if columna.tipo is TipoCampo.SIN_VALOR or columna.nombre in _FUERA_DE_CONSULTA:
            continue
        if columna.tipo is TipoCampo.DOCUMENTO:
            campos[f"{columna.nombre}_tipo"] = TipoDato.TEXTO
            campos[f"{columna.nombre}_numero"] = TipoDato.TEXTO
        elif columna.tipo is TipoCampo.VENCIMIENTO_OPERATIVO:
            campos[f"{columna.nombre}_aplica"] = TipoDato.BOOLEANO
            campos[f"{columna.nombre}_fecha"] = TipoDato.FECHA
        else:
            campos[columna.nombre] = _TIPOS[columna.tipo]
    return campos


CAMPOS_BASE: dict[str, TipoDato] = _construir_campos()


def _de_adicional(campo: CampoAdicional) -> CampoCartera:
    return CampoCartera(
        nombre=campo.nombre,
        tipo=_TIPOS_ADICIONALES[campo.tipo],
        clave_etiqueta=f"campo.{campo.nombre}",
        etiqueta=campo.nombre_legible,
        adicional=True,
        archivado=campo.archivado,
    )


class CatalogoCartera:
    """Los campos de la cartera: la base y los adicionales que da el puerto (si lo hay).

    `campos()` trae TODOS, archivados incluidos, para que lo que ya los usa siga resolviendo (una
    seleccion, una definicion guardada, un speech); `ofrecidos()` no los trae y `catalogo_publico()`
    los trae marcados. Sin puerto, es solo la base. El puerto se lee UNA vez por instancia, la
    primera vez que se pide un campo: la API crea un catalogo por peticion.
    """

    def __init__(self, adicionales: RepositorioCamposAdicionalesPort | None = None) -> None:
        self._adicionales = adicionales
        self._leidos: tuple[CampoAdicional, ...] | None = None

    def campos(self) -> dict[str, CampoCartera]:
        campos = {
            nombre: CampoCartera(nombre, tipo, clave_etiqueta=f"campo.{nombre}")
            for nombre, tipo in CAMPOS_BASE.items()
        }
        for adicional in self._definiciones():
            campos[adicional.nombre] = _de_adicional(adicional)
        return campos

    def _definiciones(self) -> tuple[CampoAdicional, ...]:
        """Las definiciones, leidas del puerto UNA vez por catalogo: el catalogo vive lo que dura la
        peticion (o la generacion), y `armar()` pide los campos por cada filtro."""
        if self._leidos is None:
            self._leidos = () if self._adicionales is None else tuple(self._adicionales.listar())
        return self._leidos

    def ofrecidos(self) -> dict[str, CampoCartera]:
        return {n: c for n, c in self.campos().items() if not c.archivado}

    def tipos(self) -> dict[str, TipoDato]:
        """Nombre -> tipo de TODOS los campos (los archivados resuelven): lo que reciben los
        contextos del motor y las columnas de carga."""
        return {nombre: campo.tipo for nombre, campo in self.campos().items()}

    def etiqueta_de(self, nombre: str) -> str:
        """El nombre legible de un campo adicional; el nombre de un campo base (o desconocido)."""
        campo = self.campos().get(nombre)
        return campo.etiqueta if campo is not None and campo.etiqueta else nombre

    def archivados_entre(self, nombres: Sequence[str]) -> tuple[str, ...]:
        """De los campos que usa algo, cuales estan archivados: para avisarlo, sin romper nada."""
        campos = self.campos()
        return tuple(n for n in dict.fromkeys(nombres) if n in campos and campos[n].archivado)

    def tipo_de(self, campo: str) -> TipoDato:
        return self._campo(campo).tipo

    def _campo(self, nombre: str) -> CampoCartera:
        campo = self.campos().get(nombre)
        if campo is None:
            raise ConsultaInvalida(f"El campo {nombre!r} no existe en la cartera")
        return campo

    def convertir(self, campo: str, texto: str) -> Any:
        """Convierte al tipo del campo un valor que llego como texto."""
        tipo = self.tipo_de(campo)
        crudo = texto.strip()
        if tipo is TipoDato.TEXTO:
            return crudo
        try:
            if tipo is TipoDato.NUMERO:
                return Decimal(crudo)
            if tipo is TipoDato.FECHA:
                return date.fromisoformat(crudo)
            if crudo.casefold() in _VERDADEROS:
                return True
            if crudo.casefold() in _FALSOS:
                return False
            raise ValueError(crudo)
        except (InvalidOperation, ValueError) as exc:
            raise ConsultaInvalida(
                f"El valor {texto!r} no es un {tipo.value} valido para el campo {campo!r}"
            ) from exc

    def validar_filtro(self, filtro: Filtro) -> None:
        tipo = self.tipo_de(filtro.campo)
        if filtro.operador not in OPERADORES_POR_TIPO[tipo]:
            permitidos = ", ".join(sorted(o.value for o in OPERADORES_POR_TIPO[tipo]))
            raise ConsultaInvalida(
                f"El operador {filtro.operador.value!r} no aplica a un campo {tipo.value}; "
                f"permitidos: {permitidos}"
            )
        esperados = VALORES_POR_OPERADOR[filtro.operador]
        if esperados is None and not filtro.valores:
            raise ConsultaInvalida(
                f"El operador {filtro.operador.value!r} necesita al menos un valor"
            )
        if esperados is not None and len(filtro.valores) != esperados:
            raise ConsultaInvalida(
                f"El operador {filtro.operador.value!r} necesita {esperados} valor(es); "
                f"se recibieron {len(filtro.valores)}"
            )
        for valor in filtro.valores:
            if isinstance(valor, datetime):
                raise ConsultaInvalida("Las fechas de cartera no llevan hora")
            if isinstance(valor, str) and tipo is not TipoDato.TEXTO:
                raise ConsultaInvalida(
                    f"El valor {valor!r} llego como texto y el campo {filtro.campo!r} "
                    f"es {tipo.value}"
                )

    def validar_orden(self, orden: Orden) -> None:
        self.tipo_de(orden.campo)

    def validar_indicador(self, indicador: Indicador) -> None:
        if not indicador.nombre.strip():
            raise ConsultaInvalida("Cada indicador necesita un nombre")
        if indicador.campo is None:
            if indicador.funcion is Funcion.CONTEO:
                return
            raise ConsultaInvalida(f"La funcion {indicador.funcion.value!r} necesita un campo")
        campo = self._campo(indicador.campo)
        numericas = _FUNCIONES_NUMERICAS_ADICIONALES if campo.adicional else _FUNCIONES_NUMERICAS
        if indicador.funcion in numericas and campo.tipo is not TipoDato.NUMERO:
            raise ConsultaInvalida(
                f"La funcion {indicador.funcion.value!r} solo aplica a campos numericos, "
                f"y {indicador.campo!r} es {campo.tipo.value}"
            )

    def catalogo_publico(self) -> dict[str, dict[str, Any]]:
        """Los campos con su tipo y operadores, para que la interfaz arme los filtros. Un campo
        adicional trae ademas `adicional`, su `etiqueta` y si esta `archivado`. Los archivados
        vienen tambien: no se ofrecen para filtros nuevos, pero una seleccion guardada que filtra
        por uno necesita su etiqueta y su tipo."""
        publico: dict[str, dict[str, Any]] = {}
        for nombre, campo in self.campos().items():
            datos: dict[str, Any] = {
                "tipo": campo.tipo.value,
                "operadores": sorted(o.value for o in OPERADORES_POR_TIPO[campo.tipo]),
            }
            if campo.adicional:
                datos |= {
                    "adicional": True,
                    "etiqueta": campo.etiqueta,
                    "archivado": campo.archivado,
                }
            publico[nombre] = datos
        return publico
