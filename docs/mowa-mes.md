# Módulo `mowa_mes` — documento técnico

Conector SMS de MOWA MES. Requerimientos en [requerimientos-mowa-mes.md](requerimientos-mowa-mes.md) (RF-MM-01 a RF-MM-22) y RF-37 a RF-41 de [atomics-requirements.md](atomics-requirements.md). Plan del coordinador en `docs/agents/coordinador_modulo_mowa_mes/plan.md`.

Este documento describe lo implementado. **Estado: primer corte (B1, B2, B3 y B6a, commit `7849ef0`), segundo corte (B4, B5 y B6b: campaña, archivos, reporte de enviados y conciliación, secciones 9 a 14), el `409` con código (sección 15) B8: tarifa, costos y nombre de los archivos (sección 16) y B9: mensaje en GSM-7 (sección 17).**

## 1. Piezas

| Pieza | Ruta | Qué hace |
|---|---|---|
| Calendario laboral (transversal) | `app/core/services/calendario/` | Regla de feriados de Perú para cualquier año, siguiente día gestionable, excepciones |
| Supervisión digital (transversal) | `app/core/services/gestiones_digitales/` | Validación de supervisores (RF-02), DNIs secuenciales (RF-39), filas copiadas de la plantilla (RF-40) |
| Entidades del conector | `app/core/entities/mowa_mes.py` | Segmentos y sus rangos, catálogo de códigos, versiones de speech, configuración |
| Núcleo del conector | `app/core/services/plataformas/mowa_mes/` | `segmentos.py` (días ajustados, segmento, fecha de envío), `speech.py` (mensaje sobre el motor de texto enriquecido, largo), `configuracion.py` (casos de uso) |
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

- **Segmentos:** `RANGOS_SEGMENTO` en las entidades (desde B2 se arma desde la tabla del núcleo `TABLA_RANGOS_POR_DEFECTO`: hay una sola, y `segmentos.dias_ajustados` es la función del núcleo. **Cuidado:** esa tabla por defecto ES la regla RF-MM-15 de MOWA MES; editarla —un rango «121 o más», otra etiqueta o clave— cambia el negocio del módulo sin tocar un archivo suyo, y una clave nueva tumbaría la aplicación al importar. Otro canal define su propia tabla en su criterio; no edita el default), con clave estable (`preventiva`, `1_a_8`, `9_a_30`, `31_a_60`, `61_a_90`, `91_a_120`), etiqueta y rango. `dias_ajustados = dias_atraso + (fecha_envio - fecha_corte).days`. Hasta 0 es `preventiva` (S-MM-6); más de 120 o sin días, sin speech. `fecha_envio` aplica S-MM-5 (la más temprana con `diferentes_horas`).
- **Mensaje sobre el motor de texto enriquecido (M1, B5):** por segmento se convierte la versión v1 a una expresión y se compila una vez: `titular | primeros(8)`, parte 1, `fecha_vencimiento_cuota | formato_fecha("dd/mm/aaaa")` y parte 2. La fila aporta las variables `titular`, `fecha_vencimiento_cuota` y `whatsapp_contacto`. Ver [motor-texto-enriquecido.md](motor-texto-enriquecido.md), sección 17. El resultado es idéntico byte a byte al de antes (prueba de oro).
- `[whatsapp]` pasa a ser la variable `whatsapp_contacto | enlace_whatsapp`, que arma `https://wa.me/+51<número>`. La expresión se arma con nodos, no por la sintaxis de texto: el texto de las partes (corchetes sueltos, `[whatsapp` sin cerrar) nunca se interpreta. Una versión cuyas partes contienen `[@` sigue sin guardarse (`problemas_de`).
- **`MensajeNoGenerable` (inalcanzable por diseño):** si el motor informa un problema al armar un mensaje (un WhatsApp fuera de RF-02, una fecha que no es fecha), `ConstructorMensajes.mensaje` lanza `MensajeNoGenerable` (en `entities/mowa_mes.py`, con el segmento y los `CodigoTexto`) en lugar de dejar salir un SMS sin enlace o con un hueco. No se alcanza porque la configuración y la campaña validan el número (RF-02) y `evaluar_producto` excluye un titular o un vencimiento vacíos antes de pedir el mensaje. **Si alguna de esas validaciones cambia, este error pasa a ser un 500.** Desde B7 el número es una constante que se pliega al compilar, así que un número inválido se detecta **al construir** el constructor (no en cada fila) y queda solo en los segmentos que usan `[whatsapp]`; los demás siguen generando mensajes (ver [motor-texto-enriquecido.md](motor-texto-enriquecido.md), sección 19). Una prueba fija con un constructor espía que un titular vacío, en blanco o un vencimiento vacío nunca llegan a pedir el mensaje.
- **Sin WhatsApp** los segmentos que lo usan no se compilan y pedirles un mensaje lanza `FaltaWhatsapp`: nunca se genera un enlace roto. La previsualización los marca con `falta_whatsapp` y sin ejemplo.
- **Largo:** `codigo_por_largo` da `mensaje_excede_160` (exclusión) si pasa de 160 y `mensaje_excede_150` (advertencia) si pasa de 150. La previsualización toma el largo máximo de la cota de la expresión (`Compilada.cota`): titular de 8, fecha de 10 y el enlace (siempre de 26 caracteres). Una prueba comprueba que coincide con el largo del mensaje construido y con la aritmética de antes. El `ejemplo` sigue armándose con marcadores (`XXXXXXXX`, `dd/mm/yyyy`).
  - Con el Speech original, `9 a 30` mide **156** caracteres (RF-MM-19 dice "unos 152"); es el único que pasa de 150.
- **Versiones** (`mowa_mes_speech_version`): nombre único sin distinguir mayúsculas, partes en JSONB, `basada_en_id` para la trazabilidad y `usada_en`. La migración siembra `Speech original` con el texto exacto de RF-MM-18; `tests/test_speech_original.py` compara la semilla con la tabla del documento.
  - Una versión usada (`usada_en` no nulo) o la original **no se modifica**: `PUT` responde `409` y el cambio se guarda como versión nueva. La condición va en la misma sentencia `UPDATE`, así una campaña que la marca a la vez no queda con un speech distinto.
  - `marcar_speech_usado` lo llama la creación de campaña (B4) en su transacción.
  - Sin nombre, una versión nueva se llama `Speech N`, uno más que el mayor número usado.
  - Los espacios de los extremos de cada parte son texto y no se recortan.
- **Speech v2 (M2, B6):** una versión puede ser v2, con una expresión del motor por segmento (`formato`, `expresiones`). Conviven con las v1, que conservan su huella. En una v2, `falta_titular` y `falta_vencimiento` excluyen solo si la expresión del segmento usa la variable. Ver [motor-texto-enriquecido.md](motor-texto-enriquecido.md), sección 23.
- **Retiro del editor de dos partes (M3, B15, RF-MM-17):** ya no se crean ni se editan versiones de dos partes. `POST /mowa-mes/speech` y `PUT /mowa-mes/speech/{id}` con `partes` responden `400` con el código `version_v1_retirada` (tipo `error`, clave `mowaMes.codigo.version_v1_retirada`), antes de mirar el resto del pedido: ni un `basada_en_id` inexistente (que daría `404`) ni la versión original (que daría `409`) lo cambian. Crear y editar una v2 sigue igual. Las v1 que ya existen, incluido el Speech original, se siguen leyendo, usando en campañas y convirtiendo con `GET /{id}/como-v2`, y sus huellas no cambian; la previsualización sigue aceptando `partes` para medir su largo. La regla vive en `ConfiguracionMowaMesService` (`crear_speech` siempre la lanza y `actualizar_speech` la lanza con datos v1); el repositorio puede seguir guardando una v1, que es como las pruebas siembran una versión heredada.

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
| `POST /mowa-mes/speech` | `201` con la versión nueva, siempre v2 (`expresiones`); desde M3 con `partes` es `400` `version_v1_retirada` | 400 contenido inválido o `version_v1_retirada`, 404 `basada_en_id`, 409 nombre repetido |
| `GET /mowa-mes/speech/{id}/como-v2` | Borrador v2 de una v1, sin guardar (M2) | 400 si ya es v2, 404 |
| `PUT /mowa-mes/speech/{id}` | La versión v2 | 400 (con `partes`: `version_v1_retirada`), 404, 409 usada, original o nombre repetido |
| `POST /mowa-mes/speech/previsualizacion` | `{whatsapp, largo_advertencia, largo_maximo, problemas, segmentos}`; acepta `partes` (para medir una v1 guardada) o `expresiones`; sin `whatsapp` usa el configurado | 400 WhatsApp fuera de RF-02 o contenido inválido |

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
| `tests/test_mowa_mes_speech_oro.py` | Oro de M1: mensaje byte a byte en el Speech original y 12 versiones sintéticas contra constantes congeladas en HEAD 3e567d7 (6 mensajes literales y un SHA-256 de 4 992 casos) y, mientras exista, contra el camino de antes en vivo; `previsualizar` entero, bordes de 150 y 160, orden de exclusiones con constructor espía, huellas fijadas y un solo dueño del prefijo de WhatsApp |
| `tests/test_api_mowa_mes_configuracion.py` | API con `TestClient` y repositorios en memoria |
| `tests/test_api_mowa_mes_conciliacion_v2.py` | API con repositorios en memoria: una campana con speech v2 (una por `como-v2` desde el Speech original y otra que no usa el titular) hasta el reporte de enviados y la conciliacion; un producto sin titular (RF-MM-13), estados distintos de «enviado» (E-1), mensajes con tildes y espacios en los extremos |
| `tests/test_mowa_mes_conciliacion_v2_postgres.py` | Los mismos dos escenarios contra PostgreSQL (B8, escritos y no corridos en su entrega): el reporte se arma desde `mowa_mes_fila_cargada`, se importa por HTTP y se compara con las tablas por SQL crudo |
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
- **Descripción sugerida (RF-MM-04):** `CajaCusco` más un resumen de los filtros, por ejemplo `CajaCusco 9 <= dias atraso <= 90, saldo capital pendiente > 5000`. Cabe en 100 unidades (ver §18): si el resumen completo no cabe, sale el prefijo con los filtros enteros que quepan, cerrada con `...`.

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
- `PUT /mowa-mes/configuracion` acepta además `registros_por_archivo` y `bytes_por_archivo`, y la respuesta los incluye. **Es una actualización parcial sobre PUT, no un reemplazo completo** (decisión del coordinador y de architec, 2026-09-14): un campo omitido conserva su valor, así un cliente que olvida el campo no borra el número sin avisar. `whatsapp_contacto: null` explícito borra el número. `registros_por_archivo` y `bytes_por_archivo` no admiten null: un null explícito responde 422 y no se trata como omitido. `limite_mensual` es obligatorio (`{}` responde 422). La regla está también en la descripción del endpoint en el contrato y es propia de este endpoint: `PUT /supervisores` sigue reemplazando la lista completa.

## 12. Catálogo de códigos (completo)

`CodigoMowaMes` y `TIPO_CODIGO` en `app/core/entities/mowa_mes.py`, un código por línea (la prueba espejo del frontend lee esa clase):

| Tipo | Códigos |
|---|---|
| exclusión (en orden de evaluación) | `telefono_invalido`, `falta_documento`, `sin_speech`, `falta_titular`, `falta_vencimiento`, `mensaje_excede_160` |
| advertencia | `mensaje_excede_150`, `documento_no_estandar`, `limite_mensual_excedido`, `id_sin_correspondencia` |
| error | `falta_whatsapp`, `sin_supervisores`, `sin_productos_cargables`, `version_v1_retirada` |

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

**Medición de B8 (2026-09-28, contra `auto_cusco_test`, misma sábana de 46 000 filas).** Desde B8 guardar un reporte recalcula `enviados_conciliados` dentro de la misma transacción (relee las filas cargadas y las del reporte de cada campaña afectada y las concilia), con un `pg_advisory_xact_lock` que serializa las importaciones.

| Paso | Tiempo |
|---|---|
| Previsualización | 5,3 s |
| Crear | 4,8 s |
| Guardar un reporte de 45 851 filas, con el recálculo | 2,4 s (antes 0,9 s) |
| Conciliar | 1,6 s |
| Reemplazar el reporte (1 campaña) | 2,5 s |
| Mover el id a otra campaña que se queda sin reportes (concilia solo la de destino) | 2,3 s |

El costo de la importación pasó de unos 0,9 s a unos 2,4 s, que sigue siendo del orden de unos pocos segundos, así que no se optimizó. El peor caso, mover un id que deja a la campaña de origen con otro id (con lo que se concilian las dos, una con la mitad de sus filas y otra con todas), tarda 3,6 s. Con esto se cumplen las condiciones de architec para aceptarlo sin optimizar: importar menos de unos 3 s (2,4 s) y crear sin empeorar respecto de lo medido antes (4,6 s contra 5,2 s). El escenario completo está en `scripts/medir_campana_mowa_mes.py` (necesita `DB_NAME` terminado en `_test`).

## 14. Pruebas del segundo corte

| Archivo | Nivel |
|---|---|
| `tests/test_mowa_mes_campana.py` | Núcleo: exclusiones en orden, largo, segmento, supervisión, WhatsApp, límite, huella, división al crear, opciones, reporte |
| `tests/test_mowa_mes_division.py` | Núcleo de la división y adaptador `.xlsx` (releído con openpyxl) |
| `tests/test_mowa_mes_conciliacion.py` | Núcleo de la conciliación y la normalización |
| `tests/test_lector_reporte_mowa_mes.py` | Adaptador del reporte, con archivos generados en memoria |
| `tests/test_codigos_mowa_mes.py` | Contrato: catálogo ↔ i18n del frontend |
| `tests/test_api_mowa_mes_campanas.py` | API con `TestClient`: previsualización, creación, consulta, descarga y sus cabeceras, límite, reporte |
| `tests/test_mowa_mes_campanas_postgres.py` | Integración de punta a punta por HTTP contra PostgreSQL: sábana → campaña → descarga → reporte → conciliación; división real; límite; speech cambiado sin escribir nada; sin WhatsApp; documento no estándar; estados distintos de "enviado". 2026-09-16 (revisión B7 contra P1–P9 de F2): `muestra` de la previsualización con la supervisión primero (no solo el archivo ya escrito); `sin_supervisores` y `sin_productos_cargables` como error de previsualización (200) y 400 al crear; fecha de corte sin versión vigente, 404 contra el repositorio real |
| `tests/test_generacion_cargas_postgres.py` | La prueba de paginación real ahora parchea `recorrido.LIMITE_MAXIMO` (C-2) |

## 15. 409 estructurado de `POST /mowa-mes/campanas`

El `409` de creación tenía un solo motivo de texto en `detail`; el frontend no podía distinguir "huella cambiada" de "límite excedido" sin repetir la lógica del backend (eso causó un bug real en `campana.astro`, corregido en B7 — ver la fila de tareas). Desde este corte el `409` trae, además de `detail`, un `codigo`:

| `codigo` | Motivo |
|---|---|
| `huella_cambiada` | `speech_huella` no coincide con la versión vigente al crear |
| `limite_excedido` | La campaña supera el límite mensual y no trae `confirmar_limite` |

- **Modelo:** `CodigoErrorCampana` (`app/core/entities/mowa_mes_campana.py`) y `ErrorCreacionCampanaRespuesta` (`detail` + `codigo`, en `app/api/mowa_mes_campanas.py`), declarado en `responses` del `POST` solo para el `409` — el `400`/`404` del mismo endpoint y el `409` de los demás endpoints (por ejemplo `ReporteYaImportado`) siguen con `DetalleError`, sin cambios.
- **Catálogo separado de `CodigoMowaMes` (decisión de architec):** `limite_excedido` no es lo mismo que la advertencia `limite_mensual_excedido` de la previsualización (mismo hecho, dos endpoints distintos: uno lo previene, el otro lo impide). Ponerlos en el mismo catálogo haría que un nombre significara "advertencia" en un endpoint y "error" en otro. Por eso `CodigoErrorCampana` no entra en `CodigoMowaMes` y no le aplican las claves `mowaMes.codigo.*` ni `tests/test_codigos_mowa_mes.py`.
- **El orden de los chequeos no cambia:** `CampanasMowaMesService.crear()` revisa la huella antes que el límite (`app/core/services/plataformas/mowa_mes/campana.py`), igual que antes de este corte. Con `confirmar_limite=True`, un `409` solo puede ser `huella_cambiada` (el chequeo del límite queda salteado); con `confirmar_limite=False`, puede ser cualquiera de los dos según cuál se dispare primero.
- **En el frontend**, un `409` sin `codigo` reconocido se trata como `huella_cambiada` (decisión de architec, implementación de `dev_frontend_modulo_mowa_mes`).
- **Prueba de contrato:** `tests/test_contrato_openapi.py::test_los_errores_declarados_traen_detail_obligatorio` recorre cada respuesta `4xx` salvo `422`, resuelve `$ref` y aplana `allOf`, y exige `detail` string obligatorio. No hay excepciones por nombre de endpoint: este `409` pasa porque conserva `detail`, no porque esté en una lista. La regla completa está en `docs/contrato-api.md`, sección 3 (decisión de architec).

## 16. Tarifa, costos y nombre de los archivos (B8, RF-MM-23 a RF-MM-25)

| Pieza | Ruta |
|---|---|
| Entidades y catálogo de variables | `app/core/entities/mowa_mes_costo.py` |
| Tarifa y costos | `app/core/services/plataformas/mowa_mes/costos.py` |
| Plantilla del nombre | `app/core/services/plataformas/mowa_mes/nombre_archivo.py` |
| `Content-Disposition` | `disposicion_de_descarga` en `app/adapters/output/exportadores/comunes.py` |
| Migración | `c3d9f5a17e28` (una sola; ida y vuelta y `alembic check` limpios) |

### 16.1 Decisiones técnicas (aprobadas por architec el 2026-09-28)

1. **Montos en el contrato: texto decimal con 4 decimales fijos**, plano y sin exponente (`"0.0200"`, `"917.0200"`, `"0.0000"`). Todo es `Decimal` en el backend, nunca `float` (`costos.costo` es `Decimal(cantidad) * tarifa`, exacto). La entrada de `tarifa_sms` también es texto: un número de JSON responde `422`; un texto que no es decimal ≥ 0 con hasta 4 decimales (y hasta 8 enteros) responde `400` con el motivo; `null` responde `422`. Columnas: `NUMERIC(12,4)` la tarifa y `NUMERIC(18,4)` el costo (el peor caso, 120 100 filas a la tarifa máxima, cabe en 14 enteros).
2. **Redondeo solo al mostrar.** Se guarda el valor exacto (cargados × tarifa) y el costo del mes suma valores exactos; el redondeo a 2 decimales, a la mitad hacia arriba, lo hace quien muestra el monto.
3. **Tarifa congelada.** La campaña guarda `tarifa_sms` y `costo_estimado` al crearse; un cambio posterior en la configuración no los toca. Las campañas anteriores quedan con `NULL` y su costo es `no_disponible` (`costo_estimado_estado`, `costo_real_estado`); no se les asigna la tarifa actual. El costo del mes (`ConsumoLimite.costo_mes`) suma los `costo_estimado` guardados con la regla de imputación del límite, omite las campañas sin tarifa y dice cuántas fueron (`campanas_sin_tarifa`, D-2). `costo_esta_campana` y `costo_total` los calcula el backend: el frontend no suma ni multiplica.
4. **Costo real (D-3).** No se guarda el costo: sale de `enviados_conciliados × tarifa` de la campaña. `enviados_conciliados` es un valor **derivado** de la conciliación vigente (E-1, supervisión incluida) que actualiza `guardar_reportes` en la misma transacción que importa o reemplaza un reporte, con la misma función del núcleo que arma la conciliación (`reportes.enviados_de`): una sola definición de "enviado". Recalcula la campaña elegida y también cualquier campaña a la que el reemplazo le quita un id de MES (C-5 permite moverlo). Un `pg_advisory_xact_lock` (clave `CLAVE_BLOQUEO_IMPORTACION_REPORTES`, en el repositorio) serializa las importaciones. **Es global y no por campaña a propósito:** un id de MES es único entre campañas (`mowa_mes_reporte.mes_id`), así que dos importaciones de campañas distintas pueden reclamar el mismo id a la vez; con un lock por campaña se pisarían el reemplazo y el conteo de la campaña de la que se lo quitan. El costo es que dos importaciones se turnan (cada una tarda unos 2,4 s con 46 000 filas) y, como son manuales y poco frecuentes, no se nota. Una prueba postgres (`test_una_segunda_importacion_espera_al_lock_global_y_no_falla`) retiene el lock desde otra conexión y comprueba que la importación espera y, al soltarlo, termina con 201. `NULL` = sin reporte (`pendiente`); `0` = se importó y no se envió nada. Sin backfill (las campañas anteriores no tienen tarifa, así que su costo real es `no_disponible` con o sin reportes) y el campo **no se expone** en ninguna respuesta: las cifras de enviados que se muestran salen siempre de la conciliación en vivo. Un `CHECK` lo mantiene entre 0 y `total_cargados`. La conciliación (`GET .../conciliacion`, `POST .../reportes`) calcula además su propio `costo_real` en vivo; una prueba postgres comprueba que coincide con el del listado.
5. **Nombre y límite de 120.** El recorte se aplica a la parte de la plantilla y nunca al sufijo `_{archivo}de{total}`. El nombre resuelto se guarda con cada archivo (`mowa_mes_archivo.nombre`, con extensión, único por campaña): una descarga posterior entrega el mismo nombre aunque la plantilla de la configuración cambie. La migración completó las campañas existentes con `mowa_mes_campana_<id>_<n>_de_<total>.xlsx`, así que sus descargas no cambian.
6. **`Content-Disposition`** lleva `filename` en ASCII (sin tildes, `_` en lo que no es seguro, como `nombre_de_archivo`) y `filename*=UTF-8''…` (RFC 5987) con el nombre exacto.

### 16.2 Precisiones del nombre de archivo (revisadas por el coordinador)

- **Orden de resolución:** sustituir variables → reemplazar por `_` los caracteres de Windows (`\ / : * ? " < > |`) → recortar espacios y puntos de los extremos → reservar el sufijo → limitar a 120 → `.xlsx`. Es la misma función para la creación, la previsualización y el ejemplo de la configuración.
- **(1) `nombre_estimado`** es `true` no solo si la plantilla usa `{archivo}` o `{total}` (D-1), también si usa `{cantidad}` o si el sufijo automático entró por haber más de un archivo: los dos dependen de cómo se divida la carga.
- **(2) Vacío antes del sufijo:** si tras sustituir y sanear no queda nada, se usa la plantilla por defecto **antes** de agregar el sufijo; con el orden literal, un `_1de3` solo habría contado como nombre. `{descripcion}` con solo espacios y puntos cae en este caso; una plantilla de solo caracteres prohibidos no queda vacía (quedan guiones bajos).
- **(3) Unicidad:** si dos nombres de una campaña coinciden (por ejemplo `{archivo}{cantidad}` da `123` para el archivo 1 con 23 filas y para el 12 con 3), se reserva el sufijo en todos; con el sufijo el nombre es único y nunca se recorta. La comparación no distingue mayúsculas, como el sistema de archivos de Windows.
- **(4) Caracteres de control** (0x00–0x1F) también se reemplazan por `_`, además de los 9 prohibidos.
- **Plantilla vacía** (en la configuración o en la campaña) = la de por defecto; en la campaña, la de la configuración. Máximo 300 caracteres. Variable desconocida (`{x}`), llave `{` sin cerrar o `}` sin abrir responden `400` con el motivo, en la configuración, en la previsualización y en la creación de campañas. Las variables distinguen mayúsculas.
- **Previsualización de la campaña:** `nombre_primer_archivo` con `[campana]` en el lugar del número de campaña (todavía no existe) y `null` si no hay archivos previstos.
- **Ejemplo de la configuración:** `POST /mowa-mes/plantilla-nombre-archivo/previsualizacion` resuelve la plantilla con datos de muestra fijos (campaña 1234, descripción `CajaCusco`, envío 2026-10-01, corte 2026-09-30) para dos archivos de 50 000 y 1 200 filas, sin guardar nada. La respuesta de configuración trae `variables_plantilla` para que el frontend no copie la lista.

### 16.2.1 El `400` trae el campo (pedido de architec)

Antes el frontend ubicaba el error bajo su campo adivinando por el texto del `detail`, y eso se rompe en cuanto cambia una frase. Ahora el `400` de estos endpoints trae, además de `detail`, el campo al que pertenece, en un modelo de error propio que extiende `detail` (regla de `docs/contrato-api.md`, sección 3; mismo patrón que el `409` de la sección 15):

| Endpoint | Modelo | `campo` |
|---|---|---|
| `PUT /mowa-mes/configuracion` | `ErrorConfiguracionRespuesta` | `CampoConfiguracion`, siempre presente: `limite_mensual`, `whatsapp_contacto`, `registros_por_archivo`, `bytes_por_archivo`, `tarifa_sms`, `plantilla_nombre_archivo` |
| `POST /mowa-mes/plantilla-nombre-archivo/previsualizacion` | `ErrorConfiguracionRespuesta` | siempre `plantilla_nombre_archivo` |
| `POST /mowa-mes/campanas/previsualizacion` y `POST /mowa-mes/campanas` | `ErrorPeticionCampanaRespuesta` | `plantilla_nombre_archivo` si el error es de la plantilla; `null` en cualquier otro `400` (filtro mal escrito, opción deshabilitada, sin supervisores…) |

- El enum `CampoConfiguracion` vive en `app/core/entities/mowa_mes.py`. `ConfiguracionInvalida` y `PeticionCampanaInvalida` llevan `campo`; los sitios que las lanzan lo fijan. Si un `400` de la configuración no trajera campo, la respuesta falla al construirse (500) en vez de salir sin él.
- Si un `PUT` de configuración trae dos errores, el `400` habla de uno solo: la tarifa se lee antes que la plantilla, y el núcleo revisa límite, WhatsApp, filas, bytes, tarifa y plantilla en ese orden.
- El `404` de la previsualización y de la creación (sin versión vigente, speech inexistente) sigue siendo `DetalleError`, sin `campo`.
- `null` en `tarifa_sms` o en `plantilla_nombre_archivo` sigue siendo `422` (lo ataja Pydantic antes del servicio), y por eso no trae `campo`.

### 16.3 Pruebas

| Archivo | Qué cubre |
|---|---|
| `tests/test_mowa_mes_costos.py` | Tarifa (bordes, texto inválido, float rechazado), costo exacto, costo real con sus tres estados, texto decimal |
| `tests/test_mowa_mes_nombre_archivo.py` | Variables, saneamiento, bordes (vacío, solo prohibidos, solo espacios y puntos, 120 exacto), sufijo, unicidad y **propiedades a mano** con semilla fija sobre miles de plantillas: sin caracteres prohibidos, nunca más de 120, sufijo que sobrevive al recorte y nombres distintos por campaña |
| `tests/test_mowa_mes_campana.py` | Costo estimado con supervisión, tarifa congelada, costo del mes, campañas sin tarifa, nombres guardados, plantilla por campaña, costo real y `enviados_conciliados` (importar, reemplazar, segundo id, mover un id) |
| `tests/test_api_mowa_mes_campanas.py`, `test_api_mowa_mes_configuracion.py`, `test_exportadores.py` | Formas del contrato, montos como texto, 400/422, `Content-Disposition` con `ñ` |
| `tests/test_mowa_mes_campanas_postgres.py` | Defectos de la base, tarifa exacta, congelado y costo del mes contra la base real, campañas sin tarifa, consistencia de `enviados_conciliados` con la conciliación tras cada paso, atomicidad de la importación, restricciones (`CHECK` y `UNIQUE`) y nombres guardados |

**Mutaciones (en un worktree pinneado, 24 en total, todas detectadas; las 7 últimas son del `campo` del `400` —campo equivocado en la tarifa, el WhatsApp, la plantilla de la configuración y del `PUT`, plantilla de campaña sin campo, `campo` descartado en el `400` de campañas— y el lock global retirado):** tarifa actual en lugar de la congelada (costo real del núcleo, del listado y costo del mes en SQL), `float` en lugar de `Decimal` (costo y lectura de la tarifa), costo real con cualquier estado (núcleo y postgres), sufijo recortado por el límite de 120, variable desconocida aceptada, reemplazo que no recalcula el conteo, campaña de origen de un id movido sin recalcular, `0` en lugar de `NULL` sin reporte, conteo fuera de la transacción, descarga sin `filename*`, campañas sin tarifa sin contarse, costo estimado sin la supervisión y descarga con el nombre de la plantilla actual en lugar del guardado.

## 17. Mensaje en GSM-7 (B9, RF-MM-27 y RF-MM-19 ampliado)

Un SMS con un carácter fuera de GSM-7 pasa a UCS-2 y su límite baja de 160 a 70. Decisión del usuario (2026-10-19): el `mensaje` se normaliza a GSM-7 al generar la carga, de modo que el límite de 160 sea siempre el real. La tabla y las funciones son del motor (`app/core/services/texto_enriquecido/gsm7.py`, §24 de `motor-texto-enriquecido.md`); MOWA MES las usa.

### 17.1 Qué hace el conector

| Dónde | Qué |
|---|---|
| `ConstructorMensajes.mensaje` (`plataformas/mowa_mes/speech.py`) | Evalúa la expresión del segmento y aplica `a_gsm7` al **texto ya evaluado**, como último paso fijo, tanto en una v1 como en una v2. El archivo `.xlsx`, la fila guardada, la supervisión (que copia el mensaje de la primera fila) y la conciliación ven todos el mismo texto |
| `_compilar` (mismo archivo) | Compila con `medida=largo_gsm7_normalizado`: el texto fijo de la cota se mide ya transliterado (`…` y `€` miden 3) |
| `evaluar_producto` (`campana.py`) | `codigo_por_largo(largo_gsm7(mensaje))` sobre el mensaje ya normalizado: se normaliza **antes** de los 150 y de los 160 |
| `POST /mowa-mes/campanas/previsualizacion` | `muestra[].largo` en unidades GSM-7 y `mensaje` ya normalizado |
| `POST /mowa-mes/speech/previsualizacion` | `ejemplo` normalizado, `largo_maximo` en unidades GSM-7 y `caracteres_quitados` (17.3) |

- **`a_gsm7` NO se cuelga de las variables.** La función `a_gsm7` del motor tiene como cota el triple de la de su entrada: aplicada al titular subiría la cota de «9 a 30» de 156 a 172 y rompería la advertencia de RF-MM-19. Se normaliza el texto final, no el dato. Además `primeros(8)` corta antes de normalizar, así que un titular con `ñ` cuenta la `ñ` como un carácter y después pierde la virgulilla (`  Peña R` sale `  Pena R`).
- **La versión se guarda como se escribió.** Las huellas del Speech original y de las versiones guardadas no cambian; lo que cambia es el mensaje que sale (`venció` → `vencio`), un cambio decidido y registrado en RF-54. La prueba de oro compara con `a_gsm7(constante congelada)` y no reemplaza las constantes de 3e567d7.
- **Cota en unidades GSM-7.** Exacta para el texto fijo; las variables cuentan 1 por carácter (el titular de 8 y la fecha de 10 son ASCII). Es un supuesto documentado: un dato con `…` o `€` (pasan a 3) puede pasarla, y el control exacto sigue siendo el de cada fila, sobre el mensaje real. Una propiedad con semilla fija comprueba que, con un titular de 8 y una fecha de 10, el largo del mensaje real es exactamente la cota.
- **Extendidos (T-MTE-B19, RF-MM-27; cierra S-MM-9).** Ya no se conservan: el mensaje queda solo en el alfabeto básico y no depende de cómo los cobre MES. `€` → `EUR`, `[` y `{` → `(`, `]` y `}` → `)`, `\` y `|` → `/`, `~` → `-` y el salto de página → un espacio; el `^` se borra y se avisa. El mensaje mide `len`. El marcador `[whatsapp]` de una v1 se reemplaza por el enlace antes de compilar (`expresion_de` parte el texto por él), así que `a_gsm7` nunca lo toca; un `[...]` que no sea exactamente ese marcador es texto fijo y sale con paréntesis. Las campañas guardadas antes de B19 conservan sus extendidos.

### 17.2 La conciliación no cambia de código

Los mensajes nuevos se guardan ya normalizados y `normalizar_mensaje` (NFD sin marcas y sin espacios en los extremos) es idempotente sobre ellos; una campaña anterior, guardada con tildes, concilia como siempre contra el reporte de MES, que ya viene sin tildes. Las pruebas de `test_mowa_mes_conciliacion.py` lo fijan: una campaña nueva (emoji borrado, comillas angulares transliteradas, espacio duro, tildes y el euro, que sale `EUR`) concilia contra un reporte con el mismo texto, y una anterior y una nueva concilian igual.

**Campañas anteriores a B19.** `normalizar_mensaje` **no** usa `a_gsm7` ni se cuelga de él: una fila cargada con `€` o `[` concilia contra un reporte de MES con ese mismo texto crudo. Si la conciliación transliterara, la clave del reporte (`EUR10`) dejaría de coincidir con la de lo cargado antes (`€10`). Queda una incógnita que solo MES resuelve: si para esas campañas viejas devolvió el `€` tal cual, concilian; si lo cambió por otra cosa, no habría correspondencia (no se puede saber sin un reporte real).

### 17.3 `caracteres_quitados` en la previsualización del speech

`segmentos[].caracteres_quitados: [{ caracter, punto_de_codigo }]`, siempre presente, vacía si no se borra nada. Forma cerrada con `dev_frontend_modulo_mowa_mes` y `designer` (el texto visible y el nombre de los invisibles son del frontend):

- **Por grafema, no por punto de código:** un emoji compuesto (👍🏽, una familia con ZWJ, una bandera) es **un** elemento. `caracter` es el grafema de lo borrado y `punto_de_codigo` trae sus puntos como «U+XXXX» (mayúsculas, mínimo 4 dígitos) separados por un espacio: `U+1F44D U+1F3FD`.
- **Sin repetir** el grafema entero y **en orden de aparición**.
- **De un grafema mixto, solo la parte borrada:** una letra que se conserva seguida de un ZWJ suelto da `U+200D`; un `1` con su selector y su keycap da `U+FE0F U+20E3`.
- **Nunca aparece lo que no se pierde:** ni los diacríticos que se quitan, ni lo transliterado (`«` → `"`, `…` → `...`, `°` → `o`), ni los espacios especiales que pasan a un espacio normal.
- **Qué texto:** el del segmento **antes** de normalizar. Una v1 y una v2 que se puede evaluar: el texto evaluado con el ejemplo (titular de 8, fecha de ejemplo y WhatsApp si hay), o sea el texto fijo, porque los datos de ejemplo son ASCII. Si el segmento usa `[whatsapp]` y no hay número, o una v2 no se puede evaluar, se calcula sobre el texto fijo: el aviso sale aunque `ejemplo` sea nulo. No incluye datos de filas reales; ese control es por fila en la campaña.
- **Cada trozo fijo se agrupa por su lado:** en una v1 las dos partes (y lo que separa el marcador `[whatsapp]`) van separadas en el mensaje por la fecha o el enlace; en una v2 sin ejemplo, cada texto fijo es un nodo aparte. Se calcula `grafemas_borrados` por trozo y se unen sin repetir y en orden; si no, un trozo que termina en una mitad de bandera y el siguiente que la completa formarían una bandera que nadie escribió (lo mismo con un emoji y un tono de piel).
- **Dónde vive:** la agrupación es `grafemas_borrados` en `gsm7.py` del motor, junto a `caracteres_borrados` (única fuente de qué se borra). Agrupa con las reglas de emoji de UAX #29 y no con la `\X` de la librería `regex`, que el proyecto no usa; su alcance está declarado en su docstring y en §24.

### 17.4 Pruebas

| Archivo | Qué cubre |
|---|---|
| `tests/test_mowa_mes_speech_gsm7.py` | Mensaje normalizado de una v1 y de una v2, normalizar después de evaluar (titular recortado antes), extendidos transliterados, supervisión, huellas intactas, los bordes de 150 y 160 en unidades GSM-7 con euro y con elipsis, cota de una v2, «9 a 30» en 156, propiedad cota == largo real, ejemplo y borrados de la previsualización (v1 y v2, con y sin WhatsApp), y que dos trozos fijos separados en el mensaje no formen un grafema (bandera partida entre las dos partes o por el enlace, emoji y tono de piel, nodos de texto de una v2) |
| `tests/test_texto_enriquecido_gsm7_grafemas.py` | `grafemas_borrados`: tono de piel, familia con ZWJ, bandera y dos banderas seguidas, keycap, corazón con selector, bandera de subdivisión con etiquetas, repetidos, ZWJ suelto, invisibles, VS16 suelto, indicador regional impar, emoji junto a letra con tilde; propiedades con semilla fija (la unión es exactamente lo que borra `a_gsm7`; sin repetir; orden de primera aparición); corridas de 20 000 indicadores regionales; cadena larga de ZWJ seguida de una bandera |
| `tests/test_mowa_mes_speech_oro.py` | Oro: los seis mensajes, la matriz completa y el texto conocido contra `a_gsm7(constante)`; la matriz cruda se recupera con un constructor de prueba sin normalizar |
| `tests/test_mowa_mes_conciliacion.py` | Regresión de la conciliación (17.2) |
| `tests/test_api_mowa_mes_speech_v2.py`, `test_api_mowa_mes_configuracion.py`, `test_api_mowa_mes_campanas.py` | Contrato de `caracteres_quitados`, ejemplo normalizado, largo de la muestra de la campaña en unidades GSM-7 |

**Mutaciones (en un worktree, 20, todas detectadas; la G19 por tiempo):** no normalizar (v1 y v2; solo la v2; solo la v1), colgar `a_gsm7` de las variables, medir el control de 150/160 en caracteres, medir la cota en caracteres, sacar los borrados del texto ya normalizado (v1 y v2), ejemplo sin normalizar (v1 y v2), largo de la muestra en caracteres, punto de código en minúscula, y las del agrupador (no agrupar, el ZWJ no une, dos banderas se funden, grafema repetido dos veces, informar también lo que se conserva), pegar los trozos fijos antes de agrupar, recontar los indicadores regionales con `sum` en cada carácter (no termina en 180 s con el grupo largo de ZWJ) y no reiniciar la cuenta al abrir un grupo.
### 17.5 El editor de `/texto-enriquecido` mide y muestra lo mismo (medida y salida del contexto)

El editor del motor y la tabla de MOWA MES tienen que dar el mismo número para el mismo texto. Por eso el contexto `mowa_mes.speech` declara dos comportamientos que el motor genérico no conoce:

- **`ContextoTexto.medida`** (por defecto `len`): la unidad del largo y de la cota. El speech declara `largo_gsm7_normalizado`. La usan `/validacion` (la cota), `/previsualizacion` (`largo` de cada columna y la cota que trae) y el `GeneradorCargas` que la previsualización arma para el contexto.
- **`ContextoTexto.salida`** (por defecto, el texto tal cual): lo que se le hace al texto antes de enviarlo. El speech declara `a_gsm7`. La previsualización la aplica al texto de cada celda y al de cada nodo, en todas las muestras (ejemplo, ejemplos por segmento, producto real, primeros de una selección), en una expresión y en una definición, con variantes por segmento o sin ellas. El `largo` se mide sobre lo que devuelve la salida.
- **No cambia el contrato.** Son campos de comportamiento (`repr=False`, `compare=False`), el catálogo no los trae y `contratos/openapi.json` no cambia (una prueba lo fija). Los problemas y las ubicaciones siguen refiriéndose a la expresión escrita, sin corrimientos.
- **Solo la previsualización la usa.** La generación de cargas (`generar`) no aplica la salida: lo que se envía a MOWA MES lo normaliza el constructor del mensaje (§17.1), no el motor. Si la salida cambia el texto de una celda, el valor tipado se vuelve a obtener del texto de salida.
- **La cartera y cualquier otro contexto no cambian:** miden en caracteres y no tienen salida (una prueba los recorre todos).
- **Los caracteres borrados NO van en la previsualización del motor**: son del conector (§17.3).
- **Qué se prueba** (`tests/test_texto_enriquecido_medida_salida.py`, 21): la cota del speech en unidades GSM-7 y que sea el `largo_maximo` de la tabla para la misma expresión; la cartera sigue en caracteres; los problemas no se corren; texto normalizado y largo en cada muestra, en una definición y en una variante; el editor y la tabla coinciden en 150, 151, 160 y 161 (con la elipsis); la medida y la salida no están en el catálogo ni en el contrato; la generación de cargas no aplica la salida; y el orden de la celda: se evalúa, si el texto CRUDO está vacío se usa el valor por defecto y después se aplica la salida a lo que quede (un dato que es solo un emoji se muestra vacío, sin el valor por defecto; un valor por defecto con tilde se muestra normalizado; ambos iguales a la carga normalizada). La columna del speech no admite valor por defecto hoy, así que esto se prueba con un generador de prueba con salida y valor por defecto.
- **Mutaciones (en un worktree, 14, todas detectadas):** invertir el orden del valor por defecto y la salida, volver a decidir el valor por defecto al tipar el texto de salida, la salida no se aplica al texto de la celda, a los nodos ni a las celdas con variante; la validación, el generador o la columna miden en caracteres; el contexto del speech no declara la medida o la salida; la previsualización ignora la salida o la medida del contexto; la cartera con una salida o con otra medida.

## 18. Largo de la descripción de campaña (B10, RF-MM-04, cierra S-MM-3)

El usuario confirmó el 2026-10-27 que el campo «Descripción de Campaña» de MES admite **100 caracteres**.

- **La API rechaza más de 100** (`422`, de validación sobre `descripcion`, como el de los 1000 de antes): `PeticionCampanaEntrada` (y con ella la previsualización y `CreacionCampanaEntrada`, que la heredan) valida la descripción con `LARGO_MAXIMO_DESCRIPCION = 100` (`entities/mowa_mes_campana.py`; no es la constante homónima del calendario). Es el único camino de entrada: la campaña no se edita después y `PeticionCampana.descripcion` solo la arma esa petición.
- **Se mide lo que se registra:** sobre `descripcion.strip()`, porque la campaña guarda la descripción sin los espacios de los extremos. Una descripción de 100 con espacios alrededor se acepta.
- **La unidad son unidades UTF-16** (`largo_utf16`: `len(texto.encode("utf-16-le", "surrogatepass")) // 2`), las que cuentan el `.length` del navegador y el `maxlength` del campo: un emoji mide 2, y la pantalla y la API no discrepan. Con tildes da lo mismo que `len`. El contrato dice el tope y la unidad en la descripción del campo (no hay `maxLength`: ese cuenta puntos de código).
- **Una sola línea (B11):** el campo de MES no admite saltos (confirmado por el usuario), así que la API los cambia por **un espacio** antes de medir los 100 y registra el valor ya cambiado: `una_linea` (`entities/mowa_mes_campana.py`) toma `\r\n` como UNO y después `\r`, `\n`, U+2028 y U+2029 sueltos; los espacios seguidos no se juntan (`a\n\nb` queda `a  b`) y `\v`, `\f` y U+0085 no se tocan (nadie los decidió). Los saltos de los extremos desaparecen con el `strip`. La descripción guardada nunca lleva saltos.
- **Vacía o en blanco** sigue cayendo en la sugerida.
- **La sugerida (`descripcion_sugerida`) también cabe en 100.** Si ``"CajaCusco " + ", ".join(filtros)`` mide 100 o menos, sale igual que antes. Si no: el prefijo y los filtros **enteros** que quepan desde el principio, cerrada con `...` (sin coma antes), de 100 o menos en total, y se corta en el primer filtro que no cabe (no salta a uno posterior más corto); si ni el primero cabe, las primeras 97 unidades del texto completo y `...`, sin partir un par sustituto. **Un valor de filtro de texto puede traer un salto adentro** (`titular:contiene:a\nb`: `convertir` solo recorta los extremos), y como la sugerida es lo que se guarda cuando la descripción va vacía, `descripcion_sugerida` también pasa cada resumen por `una_linea` antes de unirlos y medirlos. El filtro sigue siendo válido para seleccionar.
- **Sin migración:** la columna es `Text`.
- **Pruebas:** `tests/test_mowa_mes_descripcion_una_linea.py` (los cinco saltos, CRLF como uno, los bordes de 99/100/101 medidos después del cambio, VT y U+0085 intactos, lo guardado, la sugerida con un salto en un valor, también con `en`) y `tests/test_mowa_mes_descripcion.py` (los bordes de 100/101, los espacios, tildes, emoji, la sugerida en cada borde del corte y una propiedad con semilla fija) y las del contrato.


## 19. Campos adicionales en el speech v2 (B12, D-CA-0 a D-CA-2, RF-64 a RF-66)

Una v2 puede leer los campos adicionales de la cartera (los que el usuario crea desde el mapeo) como una variable más. Especificación: `docs/agents/coordinador_modulo_mowa_mes/plan.md` §7.

- **Qué ve una v2 (D-CA-0).** `VARIABLES_V2` no cambia. `speech.adicionales_de(catalogo)` lee `campos()` una sola vez y devuelve nombre → tipo de los adicionales, **archivados incluidos** (lo que ya los usa tiene que seguir resolviendo). `problemas_de`, `compilar_expresion`, `previsualizar_v2`, `ConstructorMensajes` y `mensaje_de` los reciben como argumento de palabra clave `adicionales`, **vacío por defecto**: una v1 y cada llamada de hoy compilan igual. `ConfiguracionMowaMesService` recibe el catálogo (`crear_catalogo_cartera()` en la API) y lo pasa al guardar, al convertir (`como_v2`) y al previsualizar; la campaña usa `self._consulta.catalogo`; `contexto_speech(catalogo)` ofrece los adicionales al editor con su etiqueta y su marca de archivado.
- **Valores.** La fila trae cada adicional ya tipado (`producto["ad_x"]`). El ejemplo de la previsualización y el del contexto usan un valor sintético por tipo (`speech.EJEMPLO_ADICIONAL`): texto `ZONA SINTETICA`, número `1250.50`, fecha `2026-10-05`. El producto de una muestra trae el suyo.
- **Tope obligatorio (D-CA-1).** Al validar una v2 (guardar y previsualizar), cada nodo que lee un adicional de **texto o de número**, como base o como argumento, se compila solo; si el motor no le calcula cota sale `sin_cota_variable` ubicado en ese nodo, con el nombre del campo. Se usa la cota del motor, no la palabra `primeros`: sirve `ad | primeros(12)` y `ad | a_texto | primeros(6)`. No aplica a una fecha (con `formato_fecha` ya tiene cota) ni al titular, el vencimiento y los días. Guardar con el problema es un `400` (`SpeechInvalido`, con sus problemas) y no se guarda.
- **Exclusión (D-CA-2).** `CodigoMowaMes.FALTA_CAMPO_ADICIONAL` (`falta_campo_adicional`, de tipo exclusión) va justo después de `FALTA_VENCIMIENTO` y antes del WhatsApp y de los 160. `ConstructorMensajes.adicionales_usados(segmento)` da los adicionales que lee el segmento, en el orden de sus nodos. Un producto con alguno vacío (`None` o texto en blanco, el `_vacio` del titular; un `0` no lo es) sale con `Exclusion(pagare, FALTA_CAMPO_ADICIONAL, campos=...)`. Un adicional vacío que el segmento no usa no excluye nada; uno archivado vacío excluye igual. `evaluar_producto` solo manda los valores a `mensaje_de` si el speech lee alguno (una llamada sin adicionales es idéntica a la de antes).
- **Persistencia y API.** Migración `e9b3d2a7c561`: `mowa_mes_exclusion.campos text[] NULL` (nombres técnicos; una fila anterior da `()`). `ExclusionRespuesta.campos` es `[{nombre, etiqueta}]`, **siempre presente** (vacía en los demás códigos): el nombre legible se resuelve al leer con el catálogo, así que renombrar un campo cambia lo que se ve y no lo guardado.
- **Aviso de campo archivado.** `POST /mowa-mes/speech/previsualizacion` devuelve `campos_archivados: [{nombre, etiqueta}]` con los archivados que usan las expresiones de una v2 (`catalogo.archivados_entre`); vacía en una v1. Es un aviso: nunca bloquea y guardar una versión que usa un archivado se permite.
- **Frontend.** Solo se agregó el texto `mowaMes.codigo.falta_campo_adicional` (es y en, sin marcador `{campos}` porque el código también sale en los conteos por motivo); el detalle con los nombres, el aviso y la lista de variables son de T-MM-F11.
- **Pruebas.** `tests/test_mowa_mes_adicionales.py` (núcleo, en memoria), `tests/test_api_mowa_mes_adicionales.py` (HTTP), `tests/test_mowa_mes_exclusion_campos_migracion.py` (el SQL de la migración sin base y lo que se inserta) y `tests/test_mowa_mes_exclusion_campos_postgres.py` (`@postgres`, de ida y vuelta y la fila anterior; la corre `architec`). Cambian a propósito `test_codigos_mowa_mes.py` (el orden) y una línea de `test_api_mowa_mes_campanas.py` (`"campos": []` en la exclusión esperada).
