"""El contexto del speech de MOWA MES para el motor de texto enriquecido (RF-43).

MOWA MES declara aqui sus variables, sus limites de largo y su tabla de rangos a partir de lo que
ya tiene (`speech`, `entities/mowa_mes`). El motor y el registro generico no lo conocen: la capa de
composicion de la API lo registra con una linea (`app/api/texto_enriquecido.py`).
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.core.entities.contexto_texto import ORIGEN_CARTERA, ContextoTexto, VariableContexto
from app.core.entities.mowa_mes import LARGO_ADVERTENCIA, LARGO_MAXIMO, RANGOS_SEGMENTO
from app.core.entities.segmentacion import RangoDias
from app.core.services.plataformas.mowa_mes import speech
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.core.services.texto_enriquecido.gsm7 import a_gsm7, largo_gsm7_normalizado

NOMBRE = "mowa_mes.speech"
VARIABLE_DIAS = speech.VARIABLE_DIAS

# Datos sinteticos: nunca de un producto real. El telefono es del rango 900000xxx.
WHATSAPP_DE_EJEMPLO = "900000123"
_EJEMPLO = {
    speech.VARIABLE_TITULAR: "TITULAR/SINTETICO,UNO",
    speech.VARIABLE_VENCIMIENTO: date(2026, 10, 5),
    speech.VARIABLE_CONTACTO: WHATSAPP_DE_EJEMPLO,
    VARIABLE_DIAS: 12,
}
# Solo las variables que aporta el modulo llevan nombre propio y lo declaran como su origen; el
# titular y el vencimiento son campos de la cartera.
_CLAVES = {
    speech.VARIABLE_CONTACTO: "textoEnriquecido.variable.whatsapp_contacto",
    VARIABLE_DIAS: "textoEnriquecido.variable.dias_atraso_ajustados",
}


@dataclass(frozen=True)
class _RegistroDeProducto:
    """Titular y vencimiento salen del producto y el contacto es el de ejemplo.

    Los dias ajustados los trae el producto: la previsualizacion los calcula con la fecha de envio
    de la muestra (hoy en Lima, RF-55) antes de pedir el registro, con la misma formula que la
    campana (RF-MM-15). Esto no ajusta nada: la campana sigue aportando los suyos. Cada campo
    adicional toma el valor que trae el producto de la muestra (D-CA-0). Es una clase y no una
    funcion para que dos contextos con los mismos adicionales sean iguales."""

    adicionales: Collection[str] = ()

    def __call__(self, producto: Mapping[str, Any]) -> dict[str, Any]:
        return {
            speech.VARIABLE_TITULAR: producto.get("titular"),
            speech.VARIABLE_VENCIMIENTO: producto.get("fecha_vencimiento_cuota"),
            speech.VARIABLE_CONTACTO: WHATSAPP_DE_EJEMPLO,
            VARIABLE_DIAS: producto.get(VARIABLE_DIAS),
            **{nombre: producto.get(nombre) for nombre in self.adicionales},
        }


def contexto_speech(catalogo: CatalogoCartera | None = None) -> ContextoTexto:
    """Las variables v2 y, con el catalogo, los campos adicionales de la cartera (archivados
    incluidos: lo que ya los usa sigue compilando), con su etiqueta y su marca de archivado."""
    adicionales = speech.adicionales_de(catalogo)
    campos = catalogo.campos() if catalogo is not None else {}
    propias = tuple(
        VariableContexto(
            nombre, tipo, _CLAVES.get(nombre), NOMBRE if nombre in _CLAVES else ORIGEN_CARTERA
        )
        for nombre, tipo in speech.VARIABLES_V2.items()
    )
    de_la_cartera = tuple(
        VariableContexto(
            nombre,
            tipo,
            origen=ORIGEN_CARTERA,
            etiqueta=campos[nombre].etiqueta,
            adicional=True,
            archivado=campos[nombre].archivado,
        )
        for nombre, tipo in adicionales.items()
    )
    return ContextoTexto(
        nombre=NOMBRE,
        clave_nombre=f"textoEnriquecido.contexto.{NOMBRE}",
        variables=propias + de_la_cartera,
        ejemplo={**_EJEMPLO, **{n: speech.EJEMPLO_ADICIONAL[t] for n, t in adicionales.items()}},
        limite_largo=LARGO_MAXIMO,
        umbral_advertencia=LARGO_ADVERTENCIA,
        variable_dias=VARIABLE_DIAS,
        tabla_rangos=tuple(
            RangoDias(r.segmento.value, r.etiqueta, r.desde, r.hasta) for r in RANGOS_SEGMENTO
        ),
        registro_de_producto=_RegistroDeProducto(tuple(adicionales)),
        # Como el mensaje que se envia (RF-MM-27): se mide en unidades GSM-7 lo que SALDRIA de
        # normalizar, y la previsualizacion muestra el texto ya normalizado.
        medida=largo_gsm7_normalizado,
        salida=a_gsm7,
    )
