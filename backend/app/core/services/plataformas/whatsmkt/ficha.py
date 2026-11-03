"""La ficha «Para subir a WhatsMKT» de una campana (RF-WM-36): cada dato del formulario de
WhatsMKT con su valor, listo para copiar, armado con lo que la campana tiene congelado."""

from dataclasses import dataclass
from datetime import date

from app.core.entities.whatsmkt import CodigoWhatsmkt, TipoEnvio
from app.core.entities.whatsmkt_campana import CampanaWhatsmkt, HorarioElegido
from app.core.services.plataformas.whatsmkt import mensaje

PAIS = "Perú"  # P-9: solo Peru


@dataclass(frozen=True)
class FichaCampana:
    nombre: str
    fecha_envio: date
    horarios: tuple[HorarioElegido, ...]
    lo_antes_posible: bool
    pais: str
    foto_id: int | None
    cantidad: int
    tipo_envio: TipoEnvio
    adjunto_id: int | None
    etiqueta_vcard: str | None
    # El mensaje para copiar en WhatsMKT: [whatsapp] ya es el enlace; las `[$MACROn$]` quedan
    # tal cual, porque WhatsMKT las reemplaza (RF-WM-17).
    mensaje: str
    # `sin_whatsapp`: el mensaje usa [whatsapp] y no hay numero vigente; queda el marcador.
    avisos: tuple[CodigoWhatsmkt, ...] = ()


def ficha_de(campana: CampanaWhatsmkt, whatsapp_vigente: str | None) -> FichaCampana:
    """La ficha con lo congelado, salvo [whatsapp]: ese lo reemplaza el numero VIGENTE al leer,
    porque el texto se copia ahora en WhatsMKT. El numero que tenia al crear queda en la campana."""
    usa_whatsapp = mensaje.marcadores_del_texto(campana.mensaje_texto).usa_whatsapp
    return FichaCampana(
        nombre=campana.nombre,
        fecha_envio=campana.fecha_envio,
        horarios=campana.horarios,
        lo_antes_posible=campana.lo_antes_posible,
        pais=PAIS,
        foto_id=campana.foto_id,
        cantidad=campana.cantidad,
        tipo_envio=campana.tipo_envio,
        adjunto_id=campana.adjunto_id,
        etiqueta_vcard=campana.etiqueta_vcard,
        mensaje=mensaje.vista(campana.mensaje_texto, [], whatsapp_vigente),
        avisos=(CodigoWhatsmkt.SIN_WHATSAPP,) if usa_whatsapp and not whatsapp_vigente else (),
    )
