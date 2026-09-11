# Versionado de sábanas por fecha de corte

Evaluación de viabilidad y costo, y diseño propuesto para permitir **varias versiones de sábana por día**, elegir cuál se considera y eliminar las que no sirven. Base para el modelo de persistencia de la Fase 1 (RF-01 – RF-03, RF-21 – RF-23).

## 1. Necesidad (definida por el usuario, 2026-09-11)

- Cada fecha de corte es una fotografía de la sábana de ese día.
- A veces la entidad envía sábanas con datos incorrectos, o cambia el formato de cabecera. Caso real: Caja Cusco reasignó cartera entre sus empresas colaboradoras y la cabecera cambió (`PAGARE2` → `PAGARE`).
- Por eso se necesita:
  - poder **cargar varias sábanas para un mismo día**;
  - poder **corregir la sábana de un día anterior** (se permiten cargas de fechas pasadas);
  - que el sistema **pregunte si la nueva versión se considera o no**, con **una sola versión seleccionada por día**;
  - poder **elegir qué versión tomar y cuál eliminar**;
  - conservar la **trazabilidad, incluso de los formatos** de cada archivo.
- La fecha de corte la especifica el usuario al subir el archivo.

## 2. Veredicto

**Viable y rentable**, con el diseño de la sección 4:

- **Costo de almacenamiento bajo:** ~27 MB por versión en la base más ~11 MB del archivo original. Las correcciones son la excepción, así que el versionado agrega poco sobre lo que ya cuesta guardar un corte por día.
- **Operaciones de versionado instantáneas:** cambiar la versión vigente toma menos de 1 ms y eliminar una versión completa, ~0.3 s.
- **Sin recálculos:** cartera, presencia entre días, historial y métricas se consultan siempre sobre las versiones vigentes. Cambiar la vigente o cargar un día pasado actualiza todo automáticamente, sin reprocesar nada.
- **Garantía en la base de datos:** la regla "una sola versión vigente por día" la impone PostgreSQL con un índice único parcial; no depende de que el código lo recuerde.

La condición para que sea rentable es **no guardar cada fila como JSON crudo** (diseño B de la sección 3): cuesta 3.5 veces más espacio sin aportar trazabilidad adicional, porque el archivo original ya la da completa.

## 3. Mediciones (2026-09-11)

Hechas en el PostgreSQL 18 local del proyecto, con los dos cortes reales leídos con `python-calamine` y normalizados con el núcleo de la app. **Antes de tocar la base, nombres, documentos y teléfonos se reemplazaron por valores inventados de la misma longitud.** Todo se hizo en un esquema temporal que se eliminó al terminar.

### 3.1 Espacio por versión

| Diseño | Qué guarda por fila | Tamaño por versión, con índices | Tiempo de carga (`COPY`) |
|---|---|---|---|
| **A (propuesto)** | Columnas tipadas normalizadas + `extras` JSONB para columnas no catalogadas | **~27 MB** | ~1 s |
| B (descartado) | Fila cruda en JSONB + fila normalizada en JSONB | ~94 MB | ~4 s |
| Archivo original `.xlsb` | Un solo bloque binario por versión | ~11 MB | — |

### 3.2 Un mes simulado

36 versiones en 30 días (un 20% de días con una corrección), 1.66 millones de filas, diseño A: **~1 GB en total**. Tiempos, mediana de 5 ejecuciones:

| Operación | Tiempo |
|---|---|
| Historial de un pagaré en todos los días vigentes (RF-22) | 0.2 ms |
| Métricas de un día: capital, cuentas por segmento, cuota mínima y máxima (RF-26) | 37 ms |
| Comparar dos versiones del mismo día (qué filas cambiaron) | 41 ms |
| Entradas y salidas entre dos días vigentes consecutivos (RF-23) | 291 ms |
| Cambiar la versión vigente de un día | 0.4 ms |
| Eliminar una versión no vigente completa (~46 mil filas) | 280 ms |
| Intentar dejar dos versiones vigentes el mismo día | Rechazado por la base |

### 3.3 Proyección de espacio

Supuesto: ~22 sábanas por mes (días hábiles, como en las muestras de agosto) y un 20% de correcciones, es decir ~26 versiones por mes.

| Escenario | Por mes | Por año |
|---|---|---|
| Diseño A + archivo original, con versionado | ~1.0 GB | ~12 GB |
| Diseño A + archivo original, sin versionado (1 carga por día) | ~0.8 GB | ~10 GB |
| Diseño B + archivo original, con versionado | ~2.7 GB | ~33 GB |

El versionado agrega ~2 GB por año con ese nivel de correcciones, y eliminar versiones descartadas libera ese espacio.

## 4. Diseño propuesto

### 4.1 Conceptos

- **Fecha de corte:** el día que representa la sábana. La elige el usuario al subir; el sistema la sugiere desde el nombre del archivo.
- **Versión:** cada archivo subido. Tiene número correlativo por fecha (v1, v2, …).
- **Versión vigente:** la versión que se considera para esa fecha. **Como máximo una por fecha.**
- **Estado de procesamiento:** en cola, procesando, terminada o fallida (la ingesta corre en segundo plano).

### 4.2 Reglas

- **V-1 — Toda carga crea una versión nueva.** Nunca se sobrescribe una versión existente.
- **V-2 — Fechas pasadas permitidas.** Se puede cargar o corregir cualquier fecha, anterior o posterior a la última.
- **V-3 — Primera versión de una fecha:** queda vigente automáticamente al terminar de procesarse sin errores bloqueantes.
- **V-4 — Fecha que ya tiene vigente:** al terminar el procesamiento, el sistema **pregunta si la nueva versión pasa a ser la vigente**. Para decidir muestra: filas, incidencias por severidad, si el formato cambió y cuántos productos difieren respecto a la vigente actual. Opción preseleccionada: **mantener la vigente actual** (nada cambia sin confirmación). Ver punto a confirmar C-1.
- **V-5 — Versiones fallidas o en proceso nunca son vigentes.** Una versión fallida (p. ej. falta la columna `Pagare`) queda registrada con su motivo y puede eliminarse.
- **V-6 — Archivo repetido.** Si el archivo es idéntico (misma huella SHA-256) a una versión existente de la misma fecha, se avisa antes de procesarlo y el usuario decide si continuar.
- **V-7 — Cambiar la vigente en cualquier momento** desde la lista de versiones de la fecha. Todo lo derivado (cartera, presencia, historial, métricas) se calcula sobre versiones vigentes, así que refleja el cambio de inmediato.
- **V-8 — Eliminar versiones.** Una versión no vigente se elimina por completo: filas, incidencias y archivo original. Para eliminar la vigente hay que elegir otra antes, o confirmar explícitamente que la fecha queda sin versión vigente. Se conserva un **registro de auditoría mínimo** (fecha de corte, número de versión, nombre y huella del archivo, cantidad de filas, fechas de carga y de eliminación), sin ningún dato de la sábana.
- **V-9 — Trazabilidad de formato.** Cada versión guarda sus cabeceras originales, el mapeo aplicado, las incidencias de cabecera y una **huella de formato** (calculada sobre las cabeceras normalizadas). El sistema marca "formato distinto" cuando cambia respecto a la versión vigente del día anterior o a otra versión del mismo día, con el detalle de cabeceras agregadas, quitadas o renombradas.
- **V-10 — Pagaré repetido dentro de un archivo** (confirmado 2026-09-11). Se guarda la primera aparición. Cada repetición posterior se registra como incidencia de error `pagare_repetido`, con su número de fila, y no se guarda.

### 4.3 Modelo de datos (diseño A)

| Tabla | Una fila por | Contenido principal |
|---|---|---|
| `carga` | Versión | `fecha_corte`, `version`, `vigente`, `estado`, `nombre_archivo`, `huella_archivo`, `huella_formato`, `cabeceras_originales` (JSONB), `mapeo` (JSONB), `filas_total`, conteo de incidencias por severidad, fechas de creación y fin de proceso |
| `carga_archivo` | Versión | El `.xlsb` original (binario). Separado de `carga` para que listar versiones no lea archivos de 11 MB |
| `carga_fila` | Fila de la sábana | `carga_id`, `numero_fila`, las columnas normalizadas tipadas de `docs/sabana-schema.md` y `extras` (JSONB, solo columnas no catalogadas; normalmente vacío) |
| `carga_incidencia` | Incidencia | `carga_id`, `fila`, `columna`, `codigo`, `severidad`, `detalle`, `valor_original` |
| `carga_auditoria` | Evento | Alta, cambio de vigente y eliminación de versiones, sin datos de la sábana |

Restricciones e índices clave (implementados en `backend/app/adapters/persistence/modelos.py`, migración inicial en `backend/migrations/versions/`):

- Índice único parcial `(fecha_corte) WHERE vigente`: impide dos vigentes el mismo día.
- Restricción `NOT vigente OR estado = 'terminada'`: una versión en cola, en proceso o fallida nunca es vigente (V-5).
- Único `(fecha_corte, version)` y `version >= 1`.
- `carga_fila`: clave primaria `(carga_id, pagare)`, que además impide pagarés repetidos dentro de una misma versión, e índice `(pagare, carga_id)` para historial y comparación entre días. `numero_fila` se guarda como columna para ubicar cada producto en el archivo original.
- Estados, severidades, tipos de documento y eventos de auditoría restringidos a los valores definidos en el dominio (`app/core/entities/`).
- Borrado en cascada de filas, incidencias y archivo al eliminar una versión. `carga_auditoria` no tiene clave foránea para sobrevivir a la eliminación.
- El archivo original se guarda sin recompresión (`STORAGE EXTERNAL`), porque el `.xlsb` ya viene comprimido.

**Por qué no JSON crudo por fila (diseño B):** RF-21 exige conservar la información completa. El archivo original la conserva de forma exacta, incluso con formatos que el catálogo todavía no conoce, y releerlo con `python-calamine` toma menos de 1 s si hubiera que reprocesar con reglas nuevas (RF-33). Guardar además cada fila cruda en JSONB multiplica el espacio por 3.5 sin aportar información nueva.

### 4.4 Flujo de carga

1. El usuario sube el archivo e indica la fecha de corte (sugerida desde el nombre).
2. Si el archivo es idéntico a otra versión de esa fecha, se avisa (V-6).
3. Se crea la versión en estado "en cola" y se procesa en segundo plano: lectura, normalización, guardado de filas e incidencias.
4. Al terminar:
   - si la fecha no tenía vigente, la nueva queda vigente (V-3);
   - si ya tenía, se muestra el resumen y la pregunta de V-4.
5. Desde la lista de versiones de cada fecha se puede cambiar la vigente, comparar versiones o eliminarlas (V-7, V-8).

### 4.5 Implementación del guardado

- **Caso de uso:** `backend/app/core/services/ingesta_sabana/servicio.py`, con tres operaciones: registrar la versión, procesarla y asignar la vigente. Solo depende de puertos, así que se prueba con un repositorio en memoria.
- **Adaptador PostgreSQL:** `backend/app/adapters/persistence/repositorio_cargas_postgres.py`. Filas e incidencias se escriben con `COPY` dentro de la misma transacción. El número de versión y la vigencia se serializan por fecha con un bloqueo consultivo de PostgreSQL (`pg_advisory_xact_lock`), así dos cargas simultáneas de la misma fecha no chocan.
- **Todo o nada:** si falla cualquier paso del guardado, la transacción se revierte completa y la versión queda `fallida` con un motivo que no incluye datos de la sábana.
- **Medición con volumen real (2026-09-11):** corte 10.09 con nombres, documentos y teléfonos reemplazados en memoria. Registrar la versión con un archivo de 11.7 MB tomó 0.26 s. Procesarla, es decir normalizar 45,989 filas, guardarlas junto a sus 3,495 incidencias y cerrar la versión, tomó 3.88 s. Los conteos guardados coinciden con `docs/sabana-schema.md`.
- **API:** `backend/app/api/cargas.py`. Subir responde de inmediato y el procesamiento sigue en segundo plano dentro del mismo proceso.

  | Endpoint | Para qué |
  |---|---|
  | `POST /cargas` | Sube el archivo con su fecha de corte, crea la versión y lanza el procesamiento. Avisa si el archivo es idéntico a otra versión de la fecha (V-6) |
  | `GET /cargas` | Lista versiones, con filtro por fecha de corte |
  | `GET /cargas/{id}` | Estado, resumen de filas e incidencias de una versión |
  | `GET /cargas/{id}/incidencias` | Incidencias con filtro por severidad y paginación |
  | `POST /cargas/{id}/vigente` | Elige la versión vigente de su fecha (V-7) |
  | `DELETE /cargas/{id}` | Elimina una versión. Para eliminar la vigente hay que confirmarlo (V-8) |

- **Recuperación de interrupciones:** al arrancar la aplicación, las versiones que quedaron en `procesando` vuelven a la cola. Es seguro porque el guardado es una sola transacción y una versión interrumpida no dejó filas a medias. Asume un solo proceso de la aplicación; con varios haría falta un sistema de colas.
- **Pendiente:** las pantallas del frontend.

## 5. Costos y riesgos

- **Desarrollo:** moderado. Además de la ingesta básica, suma la gestión de versiones (lista por fecha, cambio de vigente, eliminación, comparación y aviso de formato) y la pregunta al terminar de procesar. No requiere procesos de recálculo.
- **Riesgo: consultas de rotación sobre rangos largos.** Entradas y salidas cuestan ~0.3 s por par de días; un reporte de todo un año (~250 pares) tardaría ~75 s. Mitigación, solo si hace falta: tabla resumen de presencia por fecha recalculada al cambiar la vigente de esa fecha y de la siguiente.
- **Riesgo: crecimiento de la base.** ~12 GB por año. Mitigación: eliminar versiones descartadas y, a partir de varios años de datos, particionar `carga_fila` por mes.
- **Datos personales multiplicados por versión.** Cada versión es otra copia de nombres, documentos y teléfonos. Eliminar las versiones descartadas también reduce esa exposición.

## 6. Decisiones confirmadas (2026-09-11)

- **C-1 — Opción preseleccionada en la pregunta de V-4:** **mantener la vigente actual.** Nada cambia sin confirmación explícita del usuario.
- **C-2 — Retención de versiones no vigentes:** **se conservan hasta que el usuario las elimine.** El sistema no sugiere ni hace borrados automáticos.
- **C-3 — Quién hizo cada acción:** **por ahora no se registra.** La aplicación no tiene usuarios ni inicio de sesión; la auditoría guarda qué pasó y cuándo. Cuando exista autenticación se agregará el usuario a `carga_auditoria`.
