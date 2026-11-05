"""El contexto `whatsmkt.mensaje` del motor de texto enriquecido (RF-WM-45, T-WM-B9).

Es el contexto del EDITOR del mensaje (no el de los textos guardados de `contexto.py`): ofrece las
macros de la definicion por defecto, con su etiqueta (RF-WM-12), y el «Enlace de WhatsApp»
(RF-WM-51). Se arma POR PETICION con `ConstructorContextoMensaje`: si cambia la definicion por
defecto o el tope de la configuracion, cambia el contexto en el pedido siguiente.

El mensaje se guarda como texto plano con `[$MACROn$]` y `[whatsapp]` (RF-WM-17). Para que el largo
del editor coincida con `mensaje.largo_del_mensaje` sin una `medida` propia, el ejemplo de cada
macro es su marcador literal (se mide sin reemplazar, DU-WM-3) y el de `whatsapp` es un enlace de
26 caracteres. Hasta la fase B el contexto no admite funciones (§13.7 del motor).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.core.entities.contexto_texto import ContextoTexto, TemaVariable, VariableContexto
from app.core.entities.segmentacion import TABLA_RANGOS_POR_DEFECTO, VARIABLE_DIAS_AJUSTADOS
from app.core.entities.texto_enriquecido import ExpresionInvalida, TipoValor
from app.core.entities.whatsmkt import TOPE_MENSAJE_POR_DEFECTO
from app.core.ports.repositorio_definiciones_port import RepositorioDefinicionesPort
from app.core.ports.repositorio_whatsmkt_port import RepositorioWhatsmktPort
from app.core.services.mapeo_campos.serializacion import DefinicionIlegible, definicion_desde_dict
from app.core.services.plataformas.whatsmkt import mensaje

NOMBRE = "whatsmkt.mensaje"
CLAVE_NOMBRE = f"textoEnriquecido.contexto.{NOMBRE}"
VARIABLE_WHATSAPP = "whatsapp"
CLAVE_ALCANCE = "textoEnriquecido.alcance.whatsmkt.mensaje"
# Dato sintetico (rango 900000xxx): el ejemplo NO es el numero de la configuracion.
WHATSAPP_DE_EJEMPLO = "900000000"


def nombre_de_macro(numero: int) -> str:
    return f"macro{numero}"


@dataclass(frozen=True)
class _RegistroLiteral:
    """El registro de un producto: siempre los marcadores y el enlace de ejemplo, porque el mensaje
    se mide sin reemplazar. Una clase y no una funcion para que dos contextos iguales lo sean."""

    valores: tuple[tuple[str, str], ...]

    def __call__(self, producto: Mapping[str, Any]) -> dict[str, Any]:
        return dict(self.valores)


def contexto_mensaje_texto(
    etiquetas: Sequence[str | None] = (), tope: int | None = TOPE_MENSAJE_POR_DEFECTO
) -> ContextoTexto:
    """El contexto con una macro por cada etiqueta (None si la columna no la tiene) y el `tope`."""
    macros = tuple(
        VariableContexto(
            nombre_de_macro(n),
            TipoValor.TEXTO,
            None,
            NOMBRE,
            f"MACRO{n} · {etiqueta}" if etiqueta else f"MACRO{n}",
            tema=TemaVariable.ARCHIVO,
        )
        for n, etiqueta in enumerate(etiquetas, 1)
    )
    whatsapp = VariableContexto(
        VARIABLE_WHATSAPP,
        TipoValor.TEXTO,
        "textoEnriquecido.variable.whatsapp",
        NOMBRE,
        tema=TemaVariable.PERSONA,
    )
    ejemplo = {
        **{nombre_de_macro(n): f"[$MACRO{n}$]" for n in range(1, len(etiquetas) + 1)},
        VARIABLE_WHATSAPP: mensaje.enlace_whatsapp(WHATSAPP_DE_EJEMPLO),
    }
    return ContextoTexto(
        nombre=NOMBRE,
        clave_nombre=CLAVE_NOMBRE,
        variables=(*macros, whatsapp),
        ejemplo=ejemplo,
        limite_largo=tope,
        umbral_advertencia=None,  # WhatsMKT no muestra «Cerca del tope»
        variable_dias=VARIABLE_DIAS_AJUSTADOS,
        tabla_rangos=TABLA_RANGOS_POR_DEFECTO,
        registro_de_producto=_RegistroLiteral(tuple(ejemplo.items())),
        clave_alcance=CLAVE_ALCANCE,
        admite_funciones=False,
    )


class ConstructorContextoMensaje:
    """Arma el contexto con la configuracion y la definicion por defecto de AHORA."""

    def __init__(
        self, whatsmkt: RepositorioWhatsmktPort, definiciones: RepositorioDefinicionesPort
    ) -> None:
        self._whatsmkt = whatsmkt
        self._definiciones = definiciones

    def __call__(self) -> ContextoTexto:
        configuracion = self._whatsmkt.obtener_configuracion()
        return contexto_mensaje_texto(
            self._etiquetas(configuracion.definicion_defecto_id), configuracion.tope_mensaje
        )

    def _etiquetas(self, definicion_id: int | None) -> tuple[str | None, ...]:
        """La etiqueta de cada macro: las columnas despues de `numero`. Sin definicion, o con una
        que no se lee, no hay macros: el contexto sigue sirviendo con el enlace de WhatsApp."""
        if definicion_id is None:
            return ()
        guardada = self._definiciones.obtener(definicion_id)
        if guardada is None:
            return ()
        try:
            leida = definicion_desde_dict(
                {**guardada.vigente.contenido, "nombre": guardada.nombre},
                TABLA_RANGOS_POR_DEFECTO,
                VARIABLE_DIAS_AJUSTADOS,
            )
        except (DefinicionIlegible, ExpresionInvalida):
            return ()
        return tuple(campo.etiqueta for campo in leida.definicion.campos[1:])
