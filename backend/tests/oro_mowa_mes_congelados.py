"""Constantes de la prueba de oro de MOWA MES M1, calculadas con el codigo VIEJO.

Se calcularon en HEAD 3e567d7 (`ConstructorMensajes` sobre `GeneradorCargas`, antes de tocar
`speech.py`), en un worktree aparte y limpio. Sobreviven al retiro del camino viejo
(`plantilla_mensaje`, `contexto_fila`) en M2/B6: la prueba de oro compara siempre contra estas
constantes, y contra el camino viejo en vivo solo mientras exista.

Titulares y numeros sinteticos: titular `ZZPRUEBA SINTETICO`, WhatsApp `900000123`, vencimiento
2026-09-05.
"""

# Los 6 mensajes del Speech original, con WhatsApp, titular sintetico y vencimiento 2026-09-05.
MENSAJES_DEL_ORIGINAL = {
    "preventiva": (
        "ZZPRUEBA Caja Cusco te recuerda que tu cuota Vence el 05/09/2026. "
        "Si ya pagaste, omite este mensaje."
    ),
    "1_a_8": (
        "ZZPRUEBA Caja Cusco te informa que tu cuota venció el 05/09/2026, acércate a pagar a "
        "nuestras agencias, agentes KASNET o a través de Wayki app."
    ),
    "9_a_30": (
        "ZZPRUEBA Caja Cusco te informa que tu cuota venció el 05/09/2026, evita estar mal "
        "calificado, acércate a pagar a nuestras agencias y/o canales alternativos."
    ),
    "31_a_60": (
        "ZZPRUEBA Caja Cusco te informa que tu cuota venció el 05/09/2026, ponte al día y "
        "participa del sorteo de 06 autos. INFO por https://wa.me/+51900000123"
    ),
    "61_a_90": (
        "ZZPRUEBA cancela tu deuda CAJA CUSCO vencida el 05/09/2026, pague a tiempo y evite estar "
        "mal calificado. Más INFO por https://wa.me/+51900000123"
    ),
    "91_a_120": (
        "ZZPRUEBA cancela tu deuda CAJA CUSCO vencida el 05/09/2026, pague a tiempo y evite estar "
        "mal calificado. Más INFO por https://wa.me/+51900000123"
    ),
}

# La matriz completa (versiones x segmentos x numeros x titulares x vencimientos), en el orden y la
# serializacion de `oro_mowa_mes_datos.mensajes_de_la_matriz` / `huella_de_la_matriz`.
MATRIZ_CASOS = 4992
MATRIZ_CASOS_SIN_WHATSAPP = 928  # los que lanzan FaltaWhatsapp: su mensaje es None en la matriz
MATRIZ_HUELLA = "777ba3d83a44783436c4236fd4febbbe9d71fb0906ace31589882cbdc68ccd15"

# B16 (RF-MM-27): la MISMA matriz con `a_gsm7` aplicada a cada mensaje. Las constantes de arriba
# siguen siendo la referencia historica de 3e567d7; esta es la referencia nueva y sale de ellas:
# se calculo con la salida del camino de 3e567d7 (igual a `MATRIZ_HUELLA`, lo comprueba su prueba)
# pasada por `a_gsm7`. No se reemplazan las constantes: el cambio es solo la normalizacion.
MATRIZ_HUELLA_GSM7 = "550b0d257e1f43f83ef56c72514f83dbf21aa965c16daa67049a842aeaabffd6"
MATRIZ_FILAS_QUE_CAMBIAN_A_GSM7 = 1376  # de las 4 992: las que llevaban una tilde o un signo
# De esas, 384 cambian solo por la regla de los espacios (2026-10-20): la version sintetica
# `saltos_de_linea` lleva una TABULACION en la parte 2 de sus 6 segmentos (64 filas por segmento) y
# pasa a un espacio normal. El Speech original no tiene ningun espacio especial ni tabulacion.
MATRIZ_FILAS_CON_ESPACIO_ESPECIAL = 384
