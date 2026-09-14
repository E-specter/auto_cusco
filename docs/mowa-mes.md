# Módulo `mowa_mes` — documento técnico

Conector SMS de MOWA MES. Requerimientos en [requerimientos-mowa-mes.md](requerimientos-mowa-mes.md) (RF-MM-01 a RF-MM-22) y RF-37 a RF-41 de [atomics-requirements.md](atomics-requirements.md). Plan del coordinador en `docs/agents/coordinador_modulo_mowa_mes/plan.md`.

Este documento describe lo implementado. **Estado: primer corte (B1, B2, B3 y B6a, commit `7849ef0`) y segundo corte (B4, B5 y B6b: campaña, archivos, reporte de enviados y conciliación, secciones 9 a 14).**

## 1. Piezas

| Pieza | Ruta | Qué hace |
|---|---|---|
| Calendario laboral (transversal) | `app/core/services/calendario/` | Regla de feriados de Perú para cualquier año, siguiente día gestionable, excepciones |
| Supervisión digital (transversal) | `app/core/services/gestiones_digitales/` | Validación de supervisores (RF-02), DNIs secuenciales (RF-39), filas copiadas de la plantilla (RF-40) |
| Entidades del conector | `app/core/entities/mowa_mes.py` | Segmentos y sus rangos, catálogo de códigos, versiones de speech, configuración |
| Núcleo del conector | `app/core/services/plataformas/mowa_mes/` | `segmentos.py` (días ajustados, segmento, fecha de envío), `speech.py` (mensaje sobre el motor de mapeo, largo), `configuracion.py` (casos de uso) |
| Persistencia | `app/adapters/persistence/repositorio_{calendario,supervision,mowa_mes}_postgres.py` | Tablas de la migración `a4c8e2f6b913` |
| API | `app/api/calendario.py`, `app/api/supervisores.py`, `app/api/mowa_mes.py` | Ver sección 6 |

## 2. Calendario laboral (RF-MM-08, S-MM-4)

- **Los feriados de ley se calculan, no se guardan.** `reglas.feriados_de_ley(anio)` devuelve los 14 de fecha fija más Jueves y Viernes Santo, derivados del domingo de Pascua (algoritmo gregoriano de Meeus/Jones/Butcher).
- Fuente de la lista: artículo 6 del Decreto Legislativo 713, modificado por la Ley 31530 (6 de agosto), la Ley 31788 (7 de junio) y la Ley 31822 (23 de julio). Contrastada el 2026-09-13 con los 16 feriados de 2026 publicados en gob.pe/feriados y en la prensa. **Pendiente de revisar con el usuario (S-MM-4).**
- La regla refleja la ley vigente, no la historia: aplicada a un año anterior a 2023 incluye feriados que todavía no existían.
- **Excepciones persistidas** (`calendario_excepcion`, una por fecha): `agregado` (día no laborable decretado; no puede caer sobre un feriado de ley) y `retirado` (feriado de ley que ese año no aplica; solo sobre un feriado de ley). Un cambio de ley permanente se refleja cambiando la regla.
- **Siguiente día gestionable:** el primer día **estrictamente posterior** a la fecha de partida que cae de lunes a viernes y no es feriado vigente ni día agregado. Sin fecha, parte de hoy en `America/Lima` (zona tomada con `zoneinfo`; en Windows la aporta el paquete `tzdata`, ya presente en el entorno).

## 3. Supervisión digital (RF-37 a RF-41)

- El núcleo no conoce MOWA. `supervision.filas_supervision(supervisores, procedencias, fila_plantilla, columna_numero, columna_documento)` devuelve las filas: copia todos los campos de la primera fila válida y pone el número y el DNI del supervisor. El número sale como texto; si la plataforma lo quiere entero, lo convierte su conector.
- **DNIs:** una sola secuencia desde `00000001`, primero la primera procedencia y así, respetando el orden de la lista dentro de cada una. `documentos_por_posicion` da el DNI alineado con la lista tal como viene (la configuración lo muestra).
- Sin supervisores lanza `SinSupervisores`; sin fila plantilla, `SinProductosCargables`. La campaña (B4) no se crea en ninguno de los dos casos.
- **Configuración persistida:** `supervisor_procedencia` (nombre, posición) y `supervisor_digital` (posición, número, procedencia). Se reemplazan completas en una transacción. La migración siembra las procedencias `Caja Cusco` y `nuestra empresa`, y **ningún número** (RF-32). La base rechaza un número fuera de RF-02 con un `CHECK`.
- Validación: al menos una procedencia, sin repetir (sin distinguir mayúsculas) y de 1 a 60 caracteres; cada número con la regla N-4 de la ingesta (`normalizar_telefono`), sin corregirlo; cada procedencia de supervisor presente en la lista.

## 4. Speech (RF-MM-14 a RF-MM-19)

- **Segmentos:** `RANGOS_SEGMENTO` en las entidades, con clave estable (`preventiva`, `1_a_8`, `9_a_30`, `31_a_60`, `61_a_90`, `91_a_120`), etiqueta y rango. `dias_ajustados = dias_atraso + (fecha_envio - fecha_corte).days`. Hasta 0 es `preventiva` (S-MM-6); más de 120 o sin días, sin speech. `fecha_envio` aplica S-MM-5 (la más temprana con `diferentes_horas`).
- **Mensaje sobre el motor de mapeo, sin modificarlo:** por segmento se compila con `GeneradorCargas` la plantilla `[@titular_8]` + parte 1 + `[@vencimiento]` + parte 2, con el catálogo de campos `titular_8`, `vencimiento` y `whatsapp`. `contexto_fila` arma ese contexto desde el producto (`titular[:8]`, fecha en `dd/mm/yyyy`).
- `[whatsapp]` se reemplaza por `https://wa.me/+51<número>` antes de compilar. Una versión cuyas partes contienen `[@` no se guarda, así el texto del usuario nunca se interpreta como campo.
- **Sin WhatsApp** los segmentos que lo usan no se compilan y pedirles un mensaje lanza `FaltaWhatsapp`: nunca se genera un enlace roto. La previsualización los marca con `falta_whatsapp` y sin ejemplo.
- **Largo:** `codigo_por_largo` da `mensaje_excede_160` (exclusión) si pasa de 160 y `mensaje_excede_150` (advertencia) si pasa de 150. La previsualización calcula el largo máximo con titular de 8, fecha de 10 y el enlace (siempre de 26 caracteres). Una prueba comprueba que ese cálculo coincide con el largo del mensaje construido por el motor.
  - Con el Speech original, `9 a 30` mide **156** caracteres (RF-MM-19 dice "unos 152"); es el único que pasa de 150.
- **Versiones** (`mowa_mes_speech_version`): nombre único sin distinguir mayúsculas, partes en JSONB, `basada_en_id` para la trazabilidad y `usada_en`. La migración siembra `Speech original` con el texto exacto de RF-MM-18; `tests/test_speech_original.py` compara la semilla con la tabla del documento.
  - Una versión usada (`usada_en` no nulo) o la original **no se modifica**: `PUT` responde `409` y el cambio se guarda como versión nueva. La condición va en la misma sentencia `UPDATE`, así una campaña que la marca a la vez no queda con un speech distinto.
  - `marcar_speech_usado` lo llama la creación de campaña (B4) en su transacción.
  - Sin nombre, una versión nueva se llama `Speech N`, uno más que el mayor número usado.
  - Los espacios de los extremos de cada parte son texto y no se recortan.

## 5. Configuración del conector

`mowa_mes_configuracion`, una sola fila (`CHECK id = 1`): `limite_mensual` (2 500 000 sembrado, RF-MM-01) y `whatsapp_contacto` (nulo sembrado; si tiene valor, sigue RF-02). Se edita por la API (RF-32), no desde `.env`.

## 6. API (primer corte del contrato, B6a)

| Método y ruta | Respuesta | Errores |
|---|---|---|
| `GET /calendario/feriados?anio=` | Días no laborables del año: `ley` (con `retirado`) y `agregado`. Sin `anio`, el actual en Lima | 422 fuera de 1900–2999 |
| `GET /calendario/excepciones` | Excepciones guardadas | |
| `POST /calendario/excepciones` | `201` con la excepción | 400 sin sentido sobre la regla, 409 fecha repetida |
| `DELETE /calendario/excepciones/{fecha}` | `204` | 404 |
| `GET /calendario/siguiente-dia-gestionable?desde=` | `{desde, fecha}` | |
| `GET /supervisores` | Procedencias y supervisores, cada uno con su `documento` | |
| `PUT /supervisores` | Igual que `GET` | 400 |
| `GET /mowa-mes/configuracion` | `{limite_mensual, whatsapp_contacto, actualizado_en}` | |
| `PUT /mowa-mes/configuracion` | Igual que `GET` | 400 WhatsApp fuera de RF-02 |
| `GET /mowa-mes/speech` | Versiones, la original primero, con `usada` y `editable` y cada segmento con etiqueta, rango y `usa_whatsapp` | |
| `GET /mowa-mes/speech/{id}` | Una versión | 404 |
| `POST /mowa-mes/speech` | `201` con la versión nueva | 400 partes inválidas, 404 `basada_en_id`, 409 nombre repetido |
| `PUT /mowa-mes/speech/{id}` | La versión | 400, 404, 409 usada, original o nombre repetido |
| `POST /mowa-mes/speech/previsualizacion` | `{whatsapp, largo_advertencia, largo_maximo, problemas, segmentos}`; sin `whatsapp` usa el configurado | 400 WhatsApp fuera de RF-02 |

**Diferencia con el plan:** los feriados se exponen como `/calendario/feriados` (lectura del año) más `/calendario/excepciones` (escritura), porque la tabla guarda excepciones y no feriados.

## 7. Catálogo de códigos

`CodigoMowaMes` y `TIPO_CODIGO` en `app/core/entities/mowa_mes.py`, en el orden de evaluación del plan (§1.3), con `falta_documento` después de `telefono_invalido` (S-MM-8). En este corte solo se emiten `mensaje_excede_150` y `mensaje_excede_160` (previsualización del speech). La prueba de contrato contra el i18n del frontend (`mowaMes.*`) llega con B4, cuando se emitan las exclusiones.

## 8. Pruebas

| Archivo | Nivel |
|---|---|
| `tests/test_calendario.py` | Núcleo: Pascua, feriados de 2026 y 2027, siguiente día gestionable, excepciones |
| `tests/test_gestiones_digitales.py` | Núcleo: DNIs, filas de supervisión, validación |
| `tests/test_mowa_mes_speech.py` | Núcleo: segmentos, programación, mensaje, largo, versiones, configuración |
| `tests/test_speech_original.py` | Contrato: semilla de la migración ↔ tabla de RF-MM-18 |
| `tests/test_api_mowa_mes_configuracion.py` | API con `TestClient` y repositorios en memoria |
| `tests/test_mowa_mes_configuracion_postgres.py` | Integración y HTTP de punta a punta contra PostgreSQL (fechas 2099, prefijo propio, estado único restituido) |

## 9. Campaña (B4, RF-MM-01 a RF-MM-13)

| Pieza | Ruta |
|---|---|
| Recorrido paginado compartido (C-2) | `app/core/services/seleccion_cartera/recorrido.py` (`SeleccionPaginada`, antes privada en `generacion_cargas/servicio.py`) |
| Entidades | `app/core/entities/mowa_mes_campana.py` |
| Caso de uso | `app/core/services/plataformas/mowa_mes/campana.py` (`CampanasMowaMesService`, `evaluar_producto`, `huella_speech`, `descripcion_sugerida`) |
| División | `app/core/services/plataformas/mowa_mes/division.py` |
| Archivo `.xlsx` | `app/adapters/output/plataformas/mowa_mes/archivo_carga.py` (sobre el exportador XLSX) |
| Persistencia | `app/adapters/persistence/repositorio_campanas_mowa_mes_postgres.py`, migración `7a91278726ae` |
| API | `app/api/mowa_mes_campanas.py` |

- **Selección (RF-MM-09):** `fecha_corte`, `filtros`, `orden` y `cantidad` en la sintaxis de `/cartera`, recorridos con `SeleccionPaginada` (mismo orden y desempate que `/cartera` y el resumen). `seleccion_id` es una referencia informativa; la campaña guarda la copia de filtros, orden y cantidad.
- **Opciones deshabilitadas (RF-MM-03, 05, 06):** solo `masiva`, `numero_largo` y respuesta automática apagada; lo demás responde `400`.
- **Fecha de envío (RF-MM-15, S-MM-5):** `enviar_ahora` usa la fecha de generación en Lima y no lleva fechas; `hora_determinada` una; `diferentes_horas` la más temprana. Una fecha y hora sin zona se toma como hora de Lima.
- **Exclusiones (RF-MM-13):** `evaluar_producto` revisa en el orden del catálogo y devuelve un solo motivo: `telefono_invalido` (regla N-4), `falta_documento` (S-MM-8), `sin_speech`, `falta_titular`, `falta_vencimiento`, `mensaje_excede_160`. Un mensaje de más de 150 se carga con la advertencia `mensaje_excede_150`. Un teléfono repetido no excluye.
- **`dni` (decisión E-2):** el `documento_numero` normalizado por la ingesta, tal cual. Si no es DNI ni RUC, **se carga igual** y lleva la advertencia `documento_no_estandar` (no es exclusión). Criterio (`documento_estandar`): con el tipo de la ingesta (regla N-3) manda el tipo, así que `extranjero` es no estándar; sin tipo, es estándar solo si son dígitos de 8 u 11. Un producto puede llevar a la vez `mensaje_excede_150` y `documento_no_estandar`: cada fila guarda la lista (`mowa_mes_fila_cargada.advertencias`) y la muestra de la previsualización trae `advertencias` como lista.
- **WhatsApp:** si un producto cae en un segmento que usa `[whatsapp]` y no hay número (ni de la campaña ni configurado), no se carga ni se excluye: la campaña lleva el error `falta_whatsapp` con el conteo por segmento.
- **Supervisión (RF-37 a RF-41, RF-MM-12):** los supervisores de la campaña o, sin lista, los configurados, validados contra las procedencias configuradas. Conservan el orden de la lista, cada uno con su DNI por procedencia. La plantilla es la primera fila cargada y las filas de supervisión van al inicio de la carga, en el orden de asignación del DNI. Sin supervisores, error `sin_supervisores`; sin productos cargables, `sin_productos_cargables` y no hay supervisión.
- **Errores de campaña:** la previsualización los lista con `puede_crear: false` y responde `200`; la creación responde `400`.
- **Límite mensual (RF-MM-01, S-MM-2, S-MM-7):** `cargados_mes` suma `total_cargados` (productos y supervisión) de las campañas con el mismo `mes_imputacion`, que es el mes de la fecha de envío. Superarlo es la advertencia `limite_mensual_excedido`; crear sin `confirmar_limite` responde `409`.
- **Speech cambiado:** la previsualización devuelve `speech.huella` (SHA-256 de las partes) y la creación la exige como `speech_huella`. Si no coincide, `409`. En PostgreSQL la versión se bloquea con `FOR UPDATE`, se compara la huella y se marca `usada_en` en la misma transacción que guarda la campaña.
- **División (RF-MM-11):** primero por `registros_por_archivo` (supervisión contada en el primer archivo); después se escribe cada tramo y, si su tamaño real pasa de `bytes_por_archivo`, se parte en proporción y se vuelve a medir. Los dos límites están en `mowa_mes_configuracion` (50 000 y 2 000 000 por defecto); el `PUT` solo permite bajarlos y un `CHECK` de la base lo impone. La previsualización devuelve `archivos_previstos_por_filas`, que es una estimación solo por filas.
- **Archivos guardados (C-6):** los bytes de cada `.xlsx` van en `mowa_mes_archivo`; la descarga entrega siempre esos bytes.
- **Descripción sugerida (RF-MM-04):** `CajaCusco` más un resumen de los filtros, por ejemplo `CajaCusco 9 <= dias atraso <= 90, saldo capital pendiente > 5000`. Sin largo máximo (S-MM-3).

## 10. Reporte de enviados y conciliación (B5, RF-MM-20 a RF-MM-22)

- **Lectura:** `app/adapters/input/lector_reporte_mowa_mes.py` con `python-calamine`, primera hoja. Exige las 8 columnas (sin distinguir mayúsculas, tildes ni espacios); si falta una o no hay filas, `400` con el motivo. `celular` y `dni` guardados como número vuelven a texto (un `dni` numérico de menos de 8 dígitos recupera los ceros); una fecha real se escribe `dd/mm/yy`.
- **Importación (C-5):** `app/core/services/plataformas/mowa_mes/reportes.py`. Las filas se agrupan por `id` de MES y cada `id` se asocia a la campaña elegida (`mowa_mes_reporte`, `mes_id` único). Si algún `id` ya estaba importado, `409` salvo `reemplazar=true`, que lo reemplaza en una transacción.
- **Conciliación:** `app/core/services/plataformas/mowa_mes/conciliacion.py`. Emparejamiento multiconjunto por (`numero`, `dni`, mensaje normalizado): cada fila del reporte cuenta para una sola fila cargada. La normalización (NFD sin marcas combinantes y sin espacios en los extremos) se aplica igual a los dos lados (C-3), así la `ñ` queda `n`.
- **Cifras:** productos, supervisión y total, cada uno con cargados, enviados (decisión E-1: fila cargada emparejada con estado `enviado`, sin distinguir mayúsculas ni espacios), no enviados (las cargadas sin fila en el reporte y las emparejadas con cualquier otro estado) y conteo por `estado` de las emparejadas; filas del reporte sin correspondencia con su conteo por estado; y por `id`, sus filas y cuántas coincidieron con cualquier estado: esa cifra dice si el `id` es de la campaña, no cuánto se envió. Un `id` sin ninguna coincidencia lleva la advertencia `id_sin_correspondencia`.

## 11. API del segundo corte (B6b)

| Método y ruta | Respuesta | Errores |
|---|---|---|
| `POST /mowa-mes/campanas/previsualizacion` | Cifras, `speech` con `huella`, supervisores con DNI, muestra de 20 filas, primera página de exclusiones (100), conteos por código y segmento, `archivos_previstos_por_filas`, `limite`, `advertencias`, `errores`, `puede_crear` | 400, 404 (sin versión vigente o speech inexistente) |
| `POST /mowa-mes/campanas` | `201` con la campaña y sus archivos reales | 400 (errores de campaña, opciones o inputs), 404, 409 (límite sin confirmar o speech cambiado) |
| `GET /mowa-mes/campanas?limite=&desplazamiento=` | Las más recientes primero | |
| `GET /mowa-mes/campanas/{id}` | La campaña con la copia de sus inputs y cifras | 404 |
| `GET /mowa-mes/campanas/{id}/exclusiones?codigo=&limite=&desplazamiento=` | Página de exclusiones en el orden de la selección | 404 |
| `GET /mowa-mes/campanas/{id}/archivos/{n}` | El `.xlsx`, con `Content-Disposition` y las cabeceras `X-Mowa-Mes-Campana`, `-Archivo`, `-Archivos-Total`, `-Filas`, `-Supervision` y `-Bytes` | 404 |
| `GET /mowa-mes/limite-mensual?mes=YYYY-MM` | Consumo del mes; sin `mes`, el actual en Lima | 422 |
| `POST /mowa-mes/campanas/{id}/reportes` (multipart `archivo`, `reemplazar`) | `201` con la conciliación | 400, 404, 409, 413 (32 MB) |
| `GET /mowa-mes/campanas/{id}/conciliacion` | Reportes importados y cifras | 404 |

- Las cabeceras de la descarga salen de `CABECERAS_ARCHIVO`, la misma lista que declara el contrato y que CORS expone (`app/main.py`). Una prueba comprueba que las enviadas son exactamente las declaradas.
- `PUT /mowa-mes/configuracion` acepta además `registros_por_archivo` y `bytes_por_archivo`, opcionales (sin valor se conservan), y la respuesta los incluye.

## 12. Catálogo de códigos (completo)

`CodigoMowaMes` y `TIPO_CODIGO` en `app/core/entities/mowa_mes.py`, un código por línea (la prueba espejo del frontend lee esa clase):

| Tipo | Códigos |
|---|---|
| exclusión (en orden de evaluación) | `telefono_invalido`, `falta_documento`, `sin_speech`, `falta_titular`, `falta_vencimiento`, `mensaje_excede_160` |
| advertencia | `mensaje_excede_150`, `documento_no_estandar`, `limite_mensual_excedido`, `id_sin_correspondencia` |
| error | `falta_whatsapp`, `sin_supervisores`, `sin_productos_cargables` |

El frontend traduce cada uno con la clave plana `mowaMes.codigo.<codigo>` en `frontend/src/i18n/es.json` y `en.json`; `tests/test_codigos_mowa_mes.py` falla si falta alguna. Las agrega `dev_frontend_modulo_mowa_mes`.

## 13. Rendimiento (medido el 2026-09-14)

`scripts/medir_campana_mowa_mes.py` con una sábana sintética de 46 000 filas (`scripts/generar_sabana_sintetica.py --filas 46000`), campaña completa con el Speech original:

| Paso | Tiempo |
|---|---|
| Ingesta | 6,4 s |
| Previsualización (recorrer y evaluar 45 999 productos) | 5,5 s, memoria pico de Python 79 MB |
| Crear (armar, dividir, escribir el `.xlsx` y guardar campaña, archivo, 45 851 filas y 153 exclusiones) | 5,2 s |
| Descargar el archivo | 0,01 s |
| Guardar un reporte de 45 851 filas | 0,9 s |
| Conciliar (leer las dos tablas y emparejar) | 1,6 s |

- Resultado: 45 846 productos y 5 de supervisión en **un solo archivo de 1,53 MB**; 153 excluidos (`telefono_invalido`); 45 851 de 45 851 conciliados.
- **Filas del Speech original que entran en 2 000 000 bytes:** unas **60 000** (33 bytes por fila, porque el `.xlsx` comparte los textos repetidos del speech). Es más que el tope de 50 000 filas, así que con el Speech original la división por bytes es un caso teórico y manda el límite de filas. Puede aparecer con un speech de textos muy variados o mensajes largos, y está cubierta por pruebas.
- Las 12 677 advertencias `mensaje_excede_150` salen de la distribución de días de la sábana sintética (segmento `9 a 30`, que mide 156), no de un dato real.

## 14. Pruebas del segundo corte

| Archivo | Nivel |
|---|---|
| `tests/test_mowa_mes_campana.py` | Núcleo: exclusiones en orden, largo, segmento, supervisión, WhatsApp, límite, huella, división al crear, opciones, reporte |
| `tests/test_mowa_mes_division.py` | Núcleo de la división y adaptador `.xlsx` (releído con openpyxl) |
| `tests/test_mowa_mes_conciliacion.py` | Núcleo de la conciliación y la normalización |
| `tests/test_lector_reporte_mowa_mes.py` | Adaptador del reporte, con archivos generados en memoria |
| `tests/test_codigos_mowa_mes.py` | Contrato: catálogo ↔ i18n del frontend |
| `tests/test_api_mowa_mes_campanas.py` | API con `TestClient`: previsualización, creación, consulta, descarga y sus cabeceras, límite, reporte |
| `tests/test_mowa_mes_campanas_postgres.py` | Integración de punta a punta por HTTP contra PostgreSQL: sábana → campaña → descarga → reporte → conciliación; división real; límite; speech cambiado sin escribir nada; sin WhatsApp |
| `tests/test_generacion_cargas_postgres.py` | La prueba de paginación real ahora parchea `recorrido.LIMITE_MAXIMO` (C-2) |
