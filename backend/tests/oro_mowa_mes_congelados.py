"""Constantes de la prueba de oro de MOWA MES, calculadas con el codigo VIEJO.

Los 6 mensajes del Speech original y los conteos de la matriz se calcularon en HEAD 3e567d7
(`ConstructorMensajes` sobre `GeneradorCargas`, antes de tocar `speech.py`), en un worktree aparte
y limpio. Sobreviven al retiro del camino viejo (`plantilla_mensaje`, `contexto_fila`) en M2/B6: la
prueba de oro compara siempre contra estas constantes.

T-MM-C11, M-B4 (RF-MM-17): al retirarse la v1 de la app, la comparacion "el v2 convertido da lo
mismo que el v1 EN VIVO" (M-B3) pasa a ser contra un hash congelado POR VERSION, calculado una sola
vez con el codigo v1 vivo (ver `HASHES_POR_VERSION` mas abajo). Con esa autorizacion se retiraron
`MATRIZ_HUELLA`, `MATRIZ_HUELLA_GSM7`, `MATRIZ_FILAS_QUE_CAMBIAN_A_GSM7` y
`MATRIZ_FILAS_CON_ESPACIO_ESPECIAL`: eran la huella de la matriz ENTERA de la v1 (con los productos
sin titular o sin fecha, que una v2 convertida no arma) y no se pueden reproducir sin el codigo v1.
Los hashes por version (sobre el mensaje FINAL, ya normalizado a GSM-7, que es el que sale en el
archivo) cubren las mismas versiones y las mismas filas que la campana si carga. Los dos conteos de
las filas comparables que sustituyen a `MATRIZ_FILAS_QUE_CAMBIAN_A_GSM7` (2104) y
`MATRIZ_FILAS_CON_ESPACIO_ESPECIAL` (384) estan mas abajo.

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

# --- Hashes por version, congelados en 9818e8d (T-MM-C11, M-B4) ---------------------------------
#
# Se calcularon UNA vez, con el codigo v1 todavia vivo, en un checkout de 9818e8d (la ultima
# revision con `speech.ConstructorMensajes` sobre `PartesSegmento` y `speech.convertir_a_v2`). No se
# vuelven a calcular: si cambian, es que cambio el texto de un mensaje de MOWA MES.
#
# Serializacion (la de `oro_mowa_mes_datos.huella_de_la_matriz`): las filas
# `[version, segmento, whatsapp, titular, fecha_iso, mensaje]` en el orden de
# `mensajes_de_la_matriz`, `json.dumps(filas, ensure_ascii=False, separators=(",", ":"))`,
# codificadas en UTF-8, SHA-256. El mensaje ya sale normalizado a GSM-7 (RF-MM-27).
#
# - `v1_comparable`: las filas de la matriz de la v1 viva que la campana NO excluye, es decir
#   `not (vacia(titular) or fecha is None)` (el predicado de `campana.evaluar_producto`), 216 por
#   version. El v2 convertido tiene que dar, en esas mismas filas, el mismo mensaje byte a byte.
# - `v2_completa`: las 384 filas de la matriz del v2 que da `convertir_a_v2` de entonces, con
#   `SIN_MENSAJE` donde el titular o la fecha vacios impiden armar el mensaje. Fija el v2 entero.
#
# Como regenerarlos (solo con el codigo de 9818e8d, nunca con el actual): `git worktree add` de
# 9818e8d, y desde su `backend/` correr, con `PYTHONUTF8=1`, un script que arme
# `ConstructorMensajes(version_v1, whatsapp)` y `ConstructorMensajes(DatosSpeech(.., convertir_a_v2(
# version_v1)), whatsapp)` con `oro_mowa_mes_datos.mensajes_de_la_matriz` de ese commit y aplique
# `huella_de_la_matriz` a cada lista de filas (filtrada por version y, la primera, por el
# predicado de la campana).
HASHES_POR_VERSION = {
    "original": {
        "v1_comparable": "608e2472f2ab74472d6f33c4466415810e5e8c21c9a149d9bbd9cdddffe48466",
        "v2_completa": "bd5a88d34c957c81101ca0d48dcd09ae6db50254a97b98f8ad4af0e278e46769",
    },
    "espacios_extremos": {
        "v1_comparable": "1145511b638a143ace8050f1ab569e3267c460fff388c7fc08b232b4a0d01110",
        "v2_completa": "8c74def26ea9a0ff963ad00a5209d90099124393740dac2715a2664028875410",
    },
    "tildes_y_enes": {
        "v1_comparable": "22813c083cedd9957de8e2e343b5eece7773dd73dd6cb03c8e8411517598f7aa",
        "v2_completa": "9aea0fec2b7f9577c75ac13485e33511178d5758210073cfdc2f887033c1b22f",
    },
    "corchetes_sueltos": {
        "v1_comparable": "c3c724e2e2832a3e7d8c6de81a9d252fc472c4a4b47f722e610b1482b5514090",
        "v2_completa": "67db04e38c05f1885ea43e6ad771000fe639dfc8691d246b542dcd8861548db0",
    },
    "whatsapp_repetido_y_en_ambas": {
        "v1_comparable": "bce42d3f52af1dff695a75c4c6033d90a4ce9e93c88d8881742ced9baadd5d44",
        "v2_completa": "756e27fdbf71ed76a5542c5d7b28864880645cfc8e4dacc871dbfb2827a6b214",
    },
    "whatsapp_solo_en_parte_1": {
        "v1_comparable": "ccb6e55e7b292193ec206e51eb19b841c5b509ef97df0b5a56184eef34349ccf",
        "v2_completa": "07897caff6a7118bf70d4e4ac2d1eaffa1232e803bed03251db3d4a29e69de50",
    },
    "whatsapp_solo_en_parte_2": {
        "v1_comparable": "3f4a68d4f1c00a96a99a44b29dc5a23b484dde951d99e754fa56c3f390b3ded6",
        "v2_completa": "2758146391c0f29832beafb14ea14afbfd11938fe9af831b62c64f63b0703db8",
    },
    "solo_whatsapp": {
        "v1_comparable": "9a7958a6c18f15dae3786a133e2dab38021bff2eb3aced56735c80f4acf5c7b7",
        "v2_completa": "987b4b65012542d6ecf30b379962ee13014840796ff8ce364da19f30aeaf801f",
    },
    "otra_escritura_de_whatsapp": {
        "v1_comparable": "9d5267f61be1a7c78c2f953739ee3ab2cfe50ab61269f5c3a4e57064bb1c3a04",
        "v2_completa": "5fbe5c70c248bf1a524667eea0a88637ba495354b6ae6192aeed77d1c3ce903d",
    },
    "vacias": {
        "v1_comparable": "033b9640ed6b15e5ed7a6fa4df637212d9b1a8d187d770b02bf8c9e91d9cea1e",
        "v2_completa": "9494bee6b7245622eeafd2efd8e87b9e6dbefae71712dd31dd9389b545c7f8e3",
    },
    "saltos_de_linea": {
        "v1_comparable": "ce3c08d264f57e4061903d431857b93ab84cc4903d347d7883b0383df79977cf",
        "v2_completa": "b5340f0324e02b8f07d4bd7d78b79311466057272f7a7bc0213759ff3a1f4daf",
    },
    "arrobas_sin_corchete": {
        "v1_comparable": "8377f16807da20544868bcc6542ba52e27bd013a1091ac333dd2a6e0eb6dead9",
        "v2_completa": (
            "403091aab1b78e89d9"  # partido en dos: 9 digitos seguidos parecerian un telefono
            "46622591ccc70f129187f18ee69eb767304dc180cdbc4d"  # (test_datos_sinteticos.py)
        ),
    },
    "un_texto_distinto_por_segmento": {
        "v1_comparable": "bcb63040f7807787f7c9b52863918db347886995af5bf17a66c76ca2423a6001",
        "v2_completa": "bdeed6db1b5644d282bea10c85324b064d9ed5cb78e9ae85cfd4f9f5949139ad",
    },
}
FILAS_COMPARABLES_POR_VERSION = 216
FILAS_V2_POR_VERSION = 384

# Dos conteos dentro de las filas comparables (las 2808 que la campana no excluye; 2286 con mensaje,
# las otras 522 son las que lanzan FaltaWhatsapp), congelados tambien en 9818e8d con el codigo v1
# vivo y el MENSAJE CRUDO (v1 sin el ultimo paso `a_gsm7`). Sustituyen a las dos constantes de la
# matriz entera que se retiraron. La prueba los verifica sobre el v2 convertido.
# - cambian a GSM-7: el mensaje crudo difiere de `a_gsm7(crudo)` (tildes, signos, corchetes...);
# - con espacio especial: el crudo trae algun espacio que no es el normal y que `a_gsm7` pasa a un
#   espacio normal (tabulacion, espacio duro...). Solo la version sintetica `saltos_de_linea` los
#   tiene (216 = sus 6 segmentos x 36 filas comparables con mensaje).
# Como regenerarlos: en un `git worktree add` de 9818e8d, desde su `backend/`, con PYTHONUTF8=1 y
# PYTHONPATH=., armar `mensajes_de_la_matriz` con un `ConstructorMensajes` v1 cuyo `mensaje` no
# aplique `a_gsm7`, quedarse con las filas `not (vacia(titular) or fecha is None)` y contar.
FILAS_COMPARABLES_CON_MENSAJE = 2286
FILAS_COMPARABLES_QUE_CAMBIAN_A_GSM7 = 1236
FILAS_COMPARABLES_CON_ESPACIO_ESPECIAL = 216
