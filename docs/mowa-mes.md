# Módulo `mowa_mes` — documento técnico

Conector SMS de MOWA MES. Requerimientos en [requerimientos-mowa-mes.md](requerimientos-mowa-mes.md) (RF-MM-01 a RF-MM-22) y RF-37 a RF-41 de [atomics-requirements.md](atomics-requirements.md). Plan del coordinador en `docs/agents/coordinador_modulo_mowa_mes/plan.md`.

Este documento describe lo implementado. **Estado: primer corte (B1, B2, B3 y B6a) — configuración.** Campaña, archivos, reporte de enviados y conciliación (B4, B5, B6b) se agregan aquí cuando se entreguen.

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
