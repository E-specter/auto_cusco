"""El contexto del speech de MOWA MES para el motor de texto enriquecido (RF-43).

MOWA MES declara aqui sus variables, sus limites de largo y su tabla de rangos a partir de lo que
ya tiene (`speech`, `entities/mowa_mes`). El motor y el registro generico no lo conocen: la capa de
composicion de la API lo registra con una linea (`app/api/texto_enriquecido.py`).
"""

from collections.abc import Mapping
from datetime import date
from typing import Any

from app.core.entities.contexto_texto import ORIGEN_CARTERA, ContextoTexto, VariableContexto
from app.core.entities.mowa_mes import LARGO_ADVERTENCIA, LARGO_MAXIMO, RANGOS_SEGMENTO
from app.core.entities.segmentacion import RangoDias
from app.core.services.plataformas.mowa_mes import speech

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


def _registro_de_producto(producto: Mapping[str, Any]) -> dict[str, Any]:
    """Titular y vencimiento salen del producto y el contacto es el de ejemplo.

    Los dias ajustados parten de `dias_atraso` de la sabana, SIN el ajuste a la fecha de envio (lo
    aporta la campana): el segmento sale de los dias de atraso a la fecha de corte, y en una
    campana el mismo producto puede caer en otro segmento."""
    return {
        speech.VARIABLE_TITULAR: producto.get("titular"),
        speech.VARIABLE_VENCIMIENTO: producto.get("fecha_vencimiento_cuota"),
        speech.VARIABLE_CONTACTO: WHATSAPP_DE_EJEMPLO,
        VARIABLE_DIAS: producto.get("dias_atraso"),
    }


def contexto_speech() -> ContextoTexto:
    tipos = speech.VARIABLES_V2
    return ContextoTexto(
        nombre=NOMBRE,
        clave_nombre=f"textoEnriquecido.contexto.{NOMBRE}",
        variables=tuple(
            VariableContexto(
                nombre, tipo, _CLAVES.get(nombre), NOMBRE if nombre in _CLAVES else ORIGEN_CARTERA
            )
            for nombre, tipo in tipos.items()
        ),
        ejemplo=dict(_EJEMPLO),
        limite_largo=LARGO_MAXIMO,
        umbral_advertencia=LARGO_ADVERTENCIA,
        variable_dias=VARIABLE_DIAS,
        tabla_rangos=tuple(
            RangoDias(r.segmento.value, r.etiqueta, r.desde, r.hasta) for r in RANGOS_SEGMENTO
        ),
        registro_de_producto=_registro_de_producto,
    )
