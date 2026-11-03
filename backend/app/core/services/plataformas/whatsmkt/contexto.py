"""El contexto de textos guardados `whatsmkt.mensaje` (RF-WM-19, RF-69).

Cada mensaje de WhatsMKT es un texto guardado y versionado de este contexto: texto plano, un solo
bloque. Por ahora el validador solo exige un largo de 1 a `TOPE_MENSAJE_POR_DEFECTO`; las reglas
del mensaje (sin emojis y el largo de la configuracion, `mensaje.py`) se enganchan cuando el
nucleo de textos guardados acepte reglas con codigo de modulo (T-HI-B6). Las macros contra la
definicion NO van aqui: al guardar no se sabe que definicion se usara (van en la previsualizacion
y al crear).
"""

from app.core.entities.whatsmkt import TOPE_MENSAJE_POR_DEFECTO
from app.core.services.textos_guardados.contextos import (
    ContextoGuardado,
    TipoContenido,
    validador_de_texto_plano,
)

CLAVE_CONTEXTO_MENSAJE = "whatsmkt.mensaje"

CONTEXTO_MENSAJE = ContextoGuardado(
    clave=CLAVE_CONTEXTO_MENSAJE,
    etiqueta="Mensaje de WhatsMKT",
    tipo=TipoContenido.TEXTO_PLANO,
    # shortcut: tope fijo y sin rechazar emojis al guardar; T-WM-B3 paso 2 (con T-HI-B6) lee el
    # tope de la configuracion y aplica mensaje.py
    validar=validador_de_texto_plano(TOPE_MENSAJE_POR_DEFECTO),
)
