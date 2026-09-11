# Esquema de la sábana diaria (RF-02)

Especificación formal de la sábana que llega cada día, levantada a partir de las muestras reales de `data/sabanas/`. Es el insumo de la Fase 1 (ingesta y cartera, RF-01 – RF-03) y de la clasificación de campos de RF-21.

> **Privacidad:** este documento solo contiene estructura, categorías de negocio y conteos agregados. No incluye nombres, documentos ni teléfonos reales. Las muestras nunca se versionan (ver `/AGENTS.md`).

## 1. Muestras analizadas

| Archivo | Filas de datos | Tamaño |
|---|---|---|
| `DATOS A GESTIONAR ASIGNACION IMPULSE - 09.09.2026.xlsb` | 46,334 | ~11.2 MB |
| `DATOS A GESTIONAR ASIGNACION IMPULSE - 10.09.2026.xlsb` | 45,989 | ~11.7 MB |

- El análisis cubre **dos días consecutivos**. Las clasificaciones de "variable/invariable" (sección 5) son provisionales hasta contrastarlas con más cortes.
- Las muestras de agosto usaban otro nombre de archivo (`SABANA DE ASIGNACION IMPULSE - DD.MM.YYYY.xlsb`) y ya no están en la carpeta, así que no se pudo comparar su estructura. **El nombre del archivo no es estable**: la fecha del corte debe confirmarla el usuario al subir la sábana (con un valor sugerido extraído del nombre, patrón `DD.MM.YYYY`).
- Volumen de referencia para RNF-3: ~46 mil productos por sábana diaria.

## 2. Estructura del libro

| Hoja | Contenido | Tratamiento en la ingesta |
|---|---|---|
| `VENCIDA` | Datos: una fila por producto (pagaré). Cabecera en la **fila 1**, 45 columnas. | Se ingesta. |
| `Td` | Dos tablas dinámicas de resumen: (a) `SEGMENTO DIA` × `CUENTAS` / `SALDOS`, (b) conteo de `Pagare` por segmento × `TAG`. | No se ingesta como datos. Puede usarse como **control de totales** (conteo por segmento debe cuadrar con `VENCIDA`). |

- Las hojas reportan un rango usado mucho mayor que el real (miles de columnas vacías); el lector debe recortar filas/columnas vacías al final.
- Formato binario `.xlsb`: requiere un lector específico (p. ej. `pyxlsb` o `python-calamine`). La elección de librería queda para la implementación de la Fase 1.

## 3. Claves

- **Clave de producto: `Pagare`.** Única en ambos cortes (45,989 valores distintos en 45,989 filas). Texto de 18 caracteres con dos formas: 18 dígitos (33,928) o 3 dígitos + 1 letra + 14 dígitos (12,061). **Debe tratarse siempre como texto.** Si un archivo trae un pagaré repetido, se guarda la primera aparición y las siguientes se reportan como error (regla V-10 de `docs/versionado-sabanas.md`).
- **Clave de cliente: `DniRuc`.** Un documento puede tener varios productos en la sábana (1 producto: 40,686 documentos; 2: 2,602; 3: 33). `Cant.Paralelos` llega hasta 8, así que cuenta créditos del cliente en toda la entidad, no solo los presentes en la sábana.

## 4. Columnas de la hoja `VENCIDA`

Cabecera original tal como llega (entre comillas si trae espacios sobrantes). Nombre normalizado propuesto en `snake_case`. Llenado y valores medidos sobre el corte 10.09.

| # | Cabecera original | Nombre normalizado | Tipo lógico | Notas |
|---|---|---|---|---|
| 0 | `Región` | `region` | texto (catálogo, 20 valores) | Siempre lleno. |
| 1 | `Agencia` | `agencia` | texto (catálogo, 153 valores) | Siempre lleno. |
| 2 | `Analista` | `analista_asignacion` | texto | Formato `APELLIDO/APELLIDO,NOMBRES`. Analista al momento de la asignación. |
| 3 | `Titular` | `titular` | texto | Mismo formato `APELLIDO/APELLIDO,NOMBRES`; 185 filas sin ese formato. Dato personal. |
| 4 | `DniRuc` | `documento_numero` (+ `documento_tipo` inferido) | texto | Puede contener DNI, RUC o documento extranjero. Llega mayormente como **número** (pierde ceros a la izquierda). Ver regla N-3. Dato personal. |
| 5 | `Teléfono` | `telefono` | texto | Llega mayormente como número. 36 vacíos. Ver regla N-4. Dato personal. |
| 6 | `Pagare` | `pagare` | texto (18) | **Clave de producto.** |
| 7 | `SaldoSoles 03/09` | `saldo_soles_corte` | financiero | **La cabecera incluye una fecha** (`dd/mm`). Idéntico en ambos cortes: foto del saldo a esa fecha. Mapear por prefijo `SaldoSoles`. |
| 8 | `TIPO DE REPROGRAMACIÓN` | `tipo_reprogramacion` | texto (catálogo) | Valor literal `NULL` = sin reprogramación (45,954). Otros: `Conflictos Sociales`, `COVID 19`, y un valor libre con número. **Vacía por completo el 09.09.** |
| 9 | `Vencimientos Operativo` | `vencimiento_operativo_aplica` + `vencimiento_operativo_fecha` | booleano + fecha | Columna mixta: texto `NO` (36,501) o fecha como serial de Excel (9,488; rango 10.09 – 25.09). |
| 10 | `Dias Atraso Hoy` | `dias_atraso` | entero | Rango −8 a 71. **Negativo = días que faltan para vencer** (28,569 filas); 0 en 4,036. Aumenta en 1 por día salvo pagos. |
| 11 | `Analista Actual` | `analista_actual` | texto | Mismo formato que `Analista`. Puede cambiar día a día. |
| 12 | `Saldo Capital Pendiente` | `saldo_capital_pendiente` | financiero | Rango 50.74 – 2,521,280.36. |
| 13 | `Monto Cuota` | `monto_cuota` | financiero | Rango 0 – 96,216.15; 2 filas en 0. Cambia a diario en ~31% de productos (mediana +0.15), consistente con intereses acumulados. |
| 14 | `Estado del Crédito` | `estado_credito` | texto (catálogo) | `VIGENTE NORMAL`, `VIGENTE VENCIDO`, `VIGENTE MOROSO`, `REFINANCIADO NORMAL`, `REFINANCIADO VENCIDO`, `REFINANCIADO MOROSO`. |
| 15 | `Vencimiento Cuota` | `fecha_vencimiento_cuota` | fecha | Serial de Excel (rango 01.07.2026 – 18.09.2026). |
| 16 | `Cliente Fallecido` | `cliente_fallecido` | booleano | Valores en minúscula `si` / `no` (56 `si`). |
| 17 | `DÍAS SICMAC-C` | `dias_atraso_entidad` | entero | Coincide con `Dias Atraso Hoy` en 45,986 de 45,989 filas. **Redundante**; conservar por las 3 diferencias. |
| 18 | `Cuotas Apro` | `cuotas_aprobadas` | entero | 1 – 240. |
| 19 | `Cuotas pagadas` | `cuotas_pagadas` | entero | 0 – 107. |
| 20 | `Cuotas Pendientes` | `cuotas_pendientes` | entero | 1 – 226. `pagadas + pendientes = aprobadas` en el 100% de filas (sirve como regla de consistencia). |
| 21 | `TipoBasilea` | `tipo_basilea` | texto (catálogo) | `CREDITO MICRO EMPRESA`, `CREDITO PEQUEÑA EMPRESA`, `CREDITO CONSUMO NO REVOLVENTE`, `CREDITO HIPOTECARIO DE VIVIENDA`. **Vacía por completo el 09.09.** |
| 22 | `TipoProducto` | `tipo_producto` | texto (catálogo, 23 valores) | Variantes sucias del mismo valor: `CREDICASA A CONSTRUIR.` vs `CREDICASA A CONSTRUIR..`; doble espacio en `PERSONAL  DIRECTO`. |
| 23 | `PAGARE` (09.09: `PAGARE2`) | — | texto | **Duplicado exacto de `Pagare`** en el 100% de filas. **La cabecera cambió entre días.** Descartar tras verificar igualdad. |
| 24 | `VALIDADOR` | — | booleano | Siempre `TRUE`. Columna auxiliar de la entidad; sin valor informativo. |
| 25 | `Segmento Saldo` | `segmento_saldo` | texto (catálogo) | `1. Menos de 20 mil`, `2. Entre 20 y 50 mil`, `3. Entre 50 y 100 mil`, `4. Mayor a 100 mil`. Calculado al asignar (no cambia aunque cambie el saldo). |
| 26 | `Moneda` | `moneda` | texto (catálogo) | `Soles` (45,988), `Dolares` (1). Se almacena como dato informativo; todos los montos se tratan como PEN (supuesto S-1). |
| 27 | `" Días Cierre Mes Anterior"` | `valor_cierre_mes_anterior` (nombre neutral provisional) | financiero | **Nombre engañoso:** contiene montos (50.82 – 2,552,490.05), no días. Espacio inicial en la cabecera. Significado pendiente (P-2). |
| 28 | `Saldo CIERRE actual` | `saldo_cierre_actual` | financiero | Sin cambios entre ambos cortes. |
| 29 | `Cod.Tipo Basilea` | — | — | **Vacía** en todas las filas. |
| 30 | `"BPO  "` | `bpo` | texto | Constante `IMPULSE`. Metadato del lote, no del producto. |
| 31 | `"TAG "` | `cartera_tag` | texto (catálogo) | `CARTERA ANTIGUA`, `CARTERA WAYKI`, `CARTERA NUEVA`, `CARTERA SCORE SETIEMBRE -CUENTAS NUEVAS ` (con espacio final), `CARTERA WAYKI - CARTERA SCORE`, `CARTERA SCORE SEG.AGOSTO`. |
| 32 | `"MES DE GESTIÓN "` | `mes_gestion` | texto | Constante `GESTION SETIEMBRE ` (con espacio final). Metadato del lote. |
| 33 | `"SEGMENTO ACTUAL "` | `segmento_actual` | texto (catálogo, 8 valores) | `1. Preventiva`, `2. 1 a 4`, `3. 5 a 8`, `4. 9 a 11`, `4. 12 a 15`, `5. 16 a 24`, `5. 25 a 30`, `6. 31 a 90`. **Prefijos numéricos repetidos.** |
| 34 | `SEGMENTO FINACIERO` | `segmento_financiero` | texto (catálogo, 6 valores) | `1. Preventiva`, `2. 1 a 8`, `3. 9 a 15`, `4. 16 a 30`, `4. 31 a 60`, `5. 61 a 90`. **Prefijo `4.` repetido.** Error ortográfico en la cabecera. Base de RF-26. |
| 35 | `validacion descuento planilla` | `descuento_planilla` | booleano | `SI` / `NO` (190 `SI`). |
| 36 | `Segmento` | `segmento_atraso` | texto (catálogo) | `Menor a 0` / `De 0 a más`. Derivado del signo de `Dias Atraso Hoy`. |
| 37 | `Tramo Actual` | `tramo_actual` | texto (catálogo, 6 valores) | `0. Mora Preventiva` … `5. Mora Tramo 61 a 90`. **Misma partición que `SEGMENTO FINACIERO`** (conteos y cambios idénticos) pero con prefijos únicos. |
| 38 | `Provisión Actual` | `provision_actual` | texto (catálogo) | `1. Provisión Normal`, `2. Provisión CPP`, `3. Provisión Deficiente`, `4. Provisión Dudoso`. |
| 39 | `Mora Impacto Actual` | `mora_impacto_actual` | booleano | `SI` / `NO`. |
| 40 | `Tramo Proyectado` | `tramo_proyectado` | texto (catálogo) | 5 valores, de `2. Mora Tramo 9 a 15` a `6. Mora Tramo 91 a 120`. |
| 41 | `Provisión Proyectada` | `provision_proyectada` | texto (catálogo) | `2. Provisión CPP`, `3. Provisión Deficiente`, `4. Provisión Dudoso`. |
| 42 | `Mora Impacto Proyectada` | `mora_impacto_proyectada` | booleano | `SI` / `NO`. |
| 43 | `Cant.Paralelos` | `cantidad_paralelos` | entero | 1 – 8. Créditos del cliente en la entidad. |
| 44 | `Celular Analista` | `celular_analista` | texto | **Teléfono del analista, no del cliente.** No debe usarse como contacto del titular. 350 valores fuera del formato de celular. |

## 5. Clasificación para RF-21 (provisional)

Basada en la comparación 09.09 → 10.09 sobre los 42,767 pagarés presentes en ambos cortes.

| Clase | Columnas | Criterio |
|---|---|---|
| **Variable** (cambia a diario) | `dias_atraso`, `dias_atraso_entidad`, `monto_cuota` | Cambian en casi todos o en una fracción grande de productos. |
| **Variable** (cambia ocasionalmente) | `telefono`, `vencimiento_operativo_aplica`/`vencimiento_operativo_fecha`, `analista_actual`, `saldo_capital_pendiente`, `estado_credito`, `fecha_vencimiento_cuota`, `cuotas_aprobadas`, `cuotas_pagadas`, `cuotas_pendientes`, `segmento_actual`, `segmento_financiero`, `segmento_atraso`, `tramo_actual`, `provision_actual`, `mora_impacto_actual`, `tramo_proyectado`, `provision_proyectada`, `mora_impacto_proyectada` | Cambian en menos del 11% de productos entre días. |
| **Invariable** (observado) | `region`, `agencia`, `analista_asignacion`, `titular`, `documento_numero`, `pagare`, `saldo_soles_corte`, `cliente_fallecido`, `tipo_producto`, `segmento_saldo`, `moneda`, `valor_cierre_mes_anterior`, `saldo_cierre_actual`, `cartera_tag`, `descuento_planilla`, `cantidad_paralelos`, `celular_analista` | 0 cambios en dos días. Confirmar con más cortes (p. ej. `cliente_fallecido` o `cantidad_paralelos` podrían cambiar dentro del mes). |
| **Llenado intermitente** | `tipo_reprogramacion`, `tipo_basilea` | Vacías el 09.09 y llenas el 10.09. Un vacío **no debe registrarse como cambio de valor** en el historial (RF-22). |
| **Metadato del lote** | `bpo`, `mes_gestion` | Constantes por archivo: guardar una vez por carga, no por producto. |
| **Sin valor informativo** | `VALIDADOR`, `Cod.Tipo Basilea`, `PAGARE`/`PAGARE2` | Constante, vacía o duplicada. Se almacenan en el registro crudo (RF-21 exige guardar todo) pero no se modelan como columnas. |

**Candidatos a "campos de interés interno de la entidad"** (RF-21): `tramo_actual`, `tramo_proyectado`, `provision_actual`, `provision_proyectada`, `mora_impacto_actual`, `mora_impacto_proyectada`. Parecen ser el seguimiento propio de la entidad (provisiones y mora proyectada), pero **debe confirmarlo el usuario** (P-5).

## 6. Reglas de normalización

**Implementación:** las reglas N-1 a N-6 y N-8 están implementadas en `backend/app/core/services/ingesta_sabana/` (catálogo de columnas en `catalogo.py`), con tests sobre datos sintéticos. Validadas contra ambos cortes reales: los conteos de documentos, teléfonos y consistencia coinciden con las tablas de este documento. N-7 corresponde al módulo de métricas y N-9 al adaptador de persistencia (pendientes).

**Severidades de las incidencias:** `error` (la clave `pagare` falta o es inválida, o el documento es inválido), `advertencia` (dato inválido que no impide registrar el producto, p. ej. teléfono) e `info` (corrección prevista por las reglas, p. ej. DNI completado con ceros).

- **N-1 — Mapeo por nombre, no por posición.** Normalizar cabeceras (recortar espacios, mayúsculas/minúsculas, tildes) y mapear contra una lista de alias. Alias ya observados: `PAGARE` / `PAGARE2`; `SaldoSoles dd/mm` (prefijo). Una cabecera desconocida o faltante debe reportarse, no romper la carga. **Solo la columna `Pagare` es requerida:** si falta, el archivo se rechaza; cualquier otra columna faltante genera una advertencia.
- **N-2 — Texto.** Recortar espacios iniciales/finales y colapsar espacios dobles en catálogos (`TAG`, `TipoProducto`, `MES DE GESTIÓN`). El literal `NULL` se convierte en nulo. Unificar variantes con puntos finales de `TipoProducto` solo mediante una tabla de equivalencias configurable (RF-32), no con reglas fijas en código.
- **N-3 — Documento de identidad** (confirmado, decisión D-1). La columna `DniRuc` puede contener DNI, RUC o documentos de identidad extranjeros. La sábana no trae el tipo; se infiere en este orden:

  1. **RUC:** 11 dígitos, prefijo `10`, `15`, `16`, `17` o `20`, y dígito verificador válido (módulo 11 de SUNAT: pesos `5,4,3,2,7,6,5,4,3,2` sobre los 10 primeros dígitos; `r = 11 − (suma mod 11)`, con `10 → 0` y `11 → 1`; `r` debe igualar al dígito 11). Un valor de 11 dígitos que falle el prefijo o el verificador es **inválido**.
  2. **DNI:** solo dígitos y hasta 8 de largo. Si tiene menos de 8, **se completa con ceros a la izquierda** hasta 8. El DNI es siempre una cadena de 8 dígitos.
  3. **Documento extranjero:** cualquier otro valor no vacío (9, 10, 12 caracteres, o alfanumérico). Se conserva tal cual, recortando espacios.
  4. **Vacío o solo ceros:** inválido, se reporta.

  | Forma recibida | 09.09 | 10.09 | Resultado |
  |---|---|---|---|
  | 8 dígitos | 42,811 | 42,472 | DNI |
  | 7 dígitos | 2,576 | 2,569 | DNI, se completa a 8 |
  | 6 dígitos | 506 | 498 | DNI, se completa a 8 |
  | 5 dígitos | 14 | 13 | DNI, se completa a 8 |
  | 11 dígitos, prefijo y verificador válidos | 426 | 436 | RUC |
  | 9 dígitos | 1 | 1 | Documento extranjero |
  | Inválidos o vacíos | 0 | 0 | — |

- **N-4 — Teléfono del cliente** (regla de RF-02, confirmada por el usuario el 2026-09-11). Válido solo si es numérico, tiene 9 dígitos y empieza con 9 (celular). Puede llegar como número o como texto de solo dígitos; se guarda como texto sin decimales. Los inválidos no se corrigen automáticamente: se reportan como advertencia y el producto se ingesta igual, con teléfono nulo. La misma regla se aplica a `Celular Analista`.
  - **Posible implementación futura: teléfonos fijos.** Hoy no se usan en la gestión, así que un número fijo cuenta como teléfono inválido. Si más adelante se necesitan, habrá que definir su formato (código de área y longitud por provincia) y clasificarlos aparte de los números mal escritos.

  | Resultado (10.09) | Filas |
  |---|---|
  | Válido | 45,935 |
  | Vacío | 36 |
  | 10 dígitos empezando en 9 | 15 |
  | Otros inválidos (6 o 12 dígitos) | 3 |

- **N-5 — Fechas.** Las fechas llegan como serial de Excel (días desde 1899-12-30). `Vencimientos Operativo` se separa en booleano (`NO` → falso) y fecha.
- **N-6 — Booleanos.** `si`/`no`, `SI`/`NO` → booleano, sin importar mayúsculas.
- **N-7 — Segmentos.** Para conteos por segmento (RF-26) usar la **etiqueta completa** o `tramo_actual`, nunca el prefijo numérico: `SEGMENTO FINACIERO` repite `4.` y `SEGMENTO ACTUAL` repite `4.` y `5.`.
- **N-8 — Reglas de consistencia (reportar, no bloquear).** `cuotas_pagadas + cuotas_pendientes = cuotas_aprobadas`; `dias_atraso` ≈ `dias_atraso_entidad`; `pagare` = columna duplicada; totales por segmento cuadran con la hoja `Td`.
- **N-9 — Registro crudo.** Guardar la fila original completa (p. ej. JSONB) además de las columnas tipadas, para cumplir RF-21 ("almacenar la información completa") aunque cambie la estructura.

## 7. Presencia y rotación entre cortes (RF-03, RF-23)

La sábana es una **foto completa** de los productos asignados ese día, no un incremental:

| Movimiento 09.09 → 10.09 | Pagarés | Detalle |
|---|---|---|
| Presentes en ambos | 42,767 | — |
| Salen (solo en 09.09) | 3,567 | 1,860 en mora preventiva y 1,574 en tramo 1 a 8 el día anterior. |
| Entran (solo en 10.09) | 3,222 | 3,212 en mora preventiva; mayormente `CARTERA ANTIGUA` y `CARTERA WAYKI`. |

Implicancia para la ingesta: la **ausencia** de un pagaré en un corte es un evento (omisión/salida, RF-03) que debe registrarse, no inferirse después. El motivo de salida (pago, reasignación, otro) no viene en la sábana (P-6).

## 8. Decisiones y preguntas abiertas

### Confirmado por el usuario (2026-09-11)

- **D-1 — Documentos de identidad** (resuelve P-3). El DNI es por definición una cadena de 8 dígitos; si llega con menos, se completa con ceros a la izquierda. En la misma columna pueden llegar RUC (formato nacional) y documentos de identidad extranjeros. Aplicado en la regla N-3.
- **S-1 — Moneda: supuesto de trabajo** (resuelve P-1 de forma provisional). Todos los montos se tratan como **PEN, soles (`S/`)**, incluido el producto marcado como `Dolares`. La columna `moneda` se conserva como dato informativo. Si más adelante se trabaja con otra moneda, este supuesto se revisa.

### Pendiente de definir

Por la regla de `/AGENTS.md`, estas reglas de negocio no se asumen hasta confirmarlas:

- **P-2 — `" Días Cierre Mes Anterior"`.** Contiene montos, no días. Su significado queda por definir; mientras tanto se almacena con el nombre neutral `valor_cierre_mes_anterior` y no se usa en métricas.
- **P-4 — Fecha en `SaldoSoles 03/09`.** ¿Qué representa el 03/09 (fecha de asignación del mes)? ¿Cambia en cada corte o solo al inicio del mes?
- **P-5 — Campos de interés interno.** ¿Cuáles son los campos que la entidad marca como relevantes para su seguimiento? (candidatos en la sección 5)
- **P-6 — Salidas.** ¿Por qué un pagaré deja de aparecer: pago, cambio de tramo, reasignación a otro BPO? ¿Hay otra fuente que lo indique?
- **P-7 — Otras hojas.** ¿La hoja de datos siempre se llama `VENCIDA`? ¿Pueden llegar sábanas con otras hojas (p. ej. preventiva) o de otros BPO además de IMPULSE?
- **P-8 — Nombre del archivo.** El patrón cambió entre agosto y septiembre. ¿Hay un nombre oficial o siempre depende de quién lo exporta?
- **P-9 — `Celular Analista`.** ¿Se usa para algo en las cargas (p. ej. WhatsApp al analista) o solo es referencia?
