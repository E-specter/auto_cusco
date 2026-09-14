# Requerimientos del módulo `mowa_mes` — conector SMS de MOWA MES

Primer conector de plataforma SMS del sistema. Aplica los requerimientos generales de gestiones digitales (RF-37 a RF-41, sección 10 de [atomics-requirements.md](atomics-requirements.md)) y los de generación de cargas digitales (RF-09 a RF-15), y agrega las reglas propias de la plataforma.

Los requerimientos de este documento se numeran `RF-MM-XX` dentro del módulo, para no mezclar su secuencia con la global.

## 1. Plataforma

| Dato | Valor |
|---|---|
| Empresa | MOWA |
| Plataforma | MES — *Messaging Enterprise Service* |
| URL | https://app.contactahabilidad.com/MES/ |
| Límite mensual | 2 500 000 SMS |
| Usuario emisor observado | `mgi_kontactus` (único) |

**Supuesto S-MM-1 — sin integración por API.** El módulo no envía mensajes a MES: genera los archivos de carga y registra la campaña. Un operador sube los archivos en la web de MES con los inputs registrados, y después descarga el reporte de enviados y lo importa en el sistema. Si MES ofreciera una API más adelante, se incorporaría como otro adaptador (RF-14).

* **RF-MM-01 — Control del límite mensual:** Mostrar cuántos SMS se cargaron en el mes calendario y cuánto queda respecto del límite mensual de la plataforma.
  * Límite por defecto: 2 500 000 SMS por mes, configurable (RF-32).
  * El consumo de una campaña se imputa al mes calendario de su fecha de envío, la misma que usa RF-MM-15, no al de la fecha de generación (decisión del usuario, sección 6).
  * Si una campaña superaría el límite del mes, entonces el sistema lo advierte antes de generar la carga y pide confirmación explícita (supuesto S-MM-2: advertir, no bloquear).
* **RF-MM-02 — SMS cargados y SMS enviados:** Distinguir en cada campaña los **SMS cargados** (los que el sistema generó y exportó) de los **SMS enviados** (los que MES reporta como despachados), porque pueden diferir por causas propias de la plataforma.
  * Los cargados se conocen al generar la carga; los enviados, al importar el reporte de enviados (sección 5).
  * Un SMS cargado cuenta como **enviado** solo si su fila del reporte trae `estado` = `enviado`. Si la fila del reporte trae otro estado, el SMS cuenta como cargado no enviado y aparece en el conteo por `estado` (RF-MM-22).

## 2. Inputs de la campaña

* **RF-MM-03 — Tipo de carga:** Registrar el tipo de carga de la campaña: `Masiva` (por defecto) o `Personalizada`.
  * `Personalizada` (carga individual) se muestra pero queda deshabilitada mientras no se use.
* **RF-MM-04 — Descripción de campaña:** Registrar una descripción corta que identifica la campaña en el listado de reportes de MES.
  * El sistema la sugiere a partir de la cartera y un resumen de los filtros de la selección, y el usuario puede editarla. Ejemplo de la forma: `CajaCusco` + segmento financiero, rango de días de atraso (`9 < x < 90`), saldo capital (`> 5000`), cuota (`> 1000`), sin gestiones SMS, sin llamadas progresivas, sin llamadas progresivas de supervisión (lista no exhaustiva, según los filtros aplicados).
  * Largo máximo que acepta MES: por confirmar (supuesto S-MM-3: sin límite hasta que se confirme).
* **RF-MM-05 — Salida:** Registrar el tipo de número de salida: `Número largo` (por defecto y única opción habilitada), `Número corto` y `Número corto flash` (visibles y deshabilitadas).
* **RF-MM-06 — Herramientas:** Registrar las herramientas elegidas para la campaña:
  * `Keyword` (casilla).
  * `Respuesta automática` (casilla, deshabilitada mientras no se use).
  * `Blacklist Indecopi` (casilla; se marca o no según la regulación peruana vigente para la campaña).
  * `Speech optimizado` (se activa internamente; baja prioridad).
* **RF-MM-07 — Programación:** Registrar la programación del envío con una de estas modalidades:
  * `Enviar ahora`.
  * `Enviar en hora determinada` (**por defecto**): una fecha y hora; la fecha sugerida es el siguiente día gestionable (RF-MM-08).
  * `Enviar en diferentes horas` (uso ocasional): varias fechas y horas.
* **RF-MM-08 — Día gestionable:** Calcular el siguiente día gestionable a partir de la fecha de generación: de lunes a viernes, excluyendo los feriados nacionales de Perú.
  * Los feriados nacionales se calculan para cualquier año: los de fecha fija por su día y mes, y Jueves y Viernes Santo a partir de la fecha de Pascua. Así el cálculo no depende de cargar las fechas de cada año.
  * La configuración permite agregar días no laborables decretados y retirar un feriado cuando cambie la ley (RF-32, RF-33).
  * Supuesto S-MM-4: la regla inicial es la lista de feriados nacionales de Perú vigente al 2026. Debe revisarse con el usuario.
* **RF-MM-09 — Base de datos de la campaña:** Tomar como base de la campaña una selección de cartera de una fecha de corte (filtros, orden y cantidad, o una selección guardada), con el mismo orden y desempate que la lista de `/cartera` y que el resumen del top n (RF-08).

## 3. Archivo de carga

Formato confirmado con el ejemplo de carga (sección 7).

* **RF-MM-10 — Formato del archivo de carga:** Generar la carga en Excel `.xlsx` (2007 en adelante) con una hoja `Hoja1` y exactamente estas columnas, en este orden y con estos nombres de cabecera:

  | Columna | Contenido | Tipo en la celda |
  |---|---|---|
  | `numero` | Teléfono del destinatario, 9 dígitos que empiezan con 9 (RF-02) | número entero |
  | `mensaje` | Texto del SMS (sección 4) | texto |
  | `dni` | Documento del destinatario: DNI de 8 dígitos con ceros a la izquierda, o RUC de 11 | texto |

  * Si el documento del producto no es DNI ni RUC (por ejemplo, carné de extranjería o pasaporte), entonces se carga igual en `dni`, con su número normalizado, y la previsualización de la campaña advierte cuántos registros lo llevan. No se sabe si MES acepta esos documentos: la advertencia deja decidir antes de subir el archivo.

* **RF-MM-11 — Límites por archivo y división:** Limitar cada archivo de carga a **50 000 registros y 2 MB**; si la carga supera cualquiera de los dos límites, entonces dividirla en dos o más archivos que respeten ambos.
  * Los registros de supervisión van en el primer archivo (RF-41).
  * Cada archivo conserva el orden de la selección.
  * El límite de 2 MB se mide sobre el tamaño real del `.xlsx` generado, no sobre una estimación.
  * Los archivos generados se conservan con la campaña: una descarga posterior entrega exactamente los mismos archivos, aunque la cartera o el speech hayan cambiado.
* **RF-MM-12 — Registros de supervisión en MOWA MES:** Ubicar los registros de supervisión (RF-37 a RF-40) **al inicio del primer archivo**, antes de los productos de la cartera, como en el formato observado.
  * `numero`: el número del supervisor; `dni`: el asignado según RF-39; `mensaje`: el de la primera fila válida de productos (RF-40).
* **RF-MM-13 — Productos excluidos de la carga:** Excluir de la carga, y reportar con su motivo, cada producto que cumpla alguna de estas condiciones:
  * No tiene teléfono válido según RF-02.
  * No tiene documento de identidad para la columna `dni`; no se carga con `dni` vacío.
  * No tiene speech: sus días de atraso ajustados quedan fuera de los segmentos de RF-MM-15.
  * Le falta un dato que el speech necesita (titular o fecha de vencimiento de cuota).
  * Su mensaje supera los 160 caracteres (RF-MM-19).
  * Un mismo teléfono puede recibir más de un mensaje si tiene varios productos en la selección: no es motivo de exclusión (así ocurre en el ejemplo).
  * Un documento que no es DNI ni RUC tampoco es motivo de exclusión: se carga y se advierte (RF-MM-10).

## 4. Construcción del campo `mensaje` (speech)

* **RF-MM-14 — Estructura del mensaje:** Construir `mensaje` con esta estructura por defecto:

  ```
  mensaje = [titular 8] + [parte 1 del speech] + [fecha] + [parte 2 del speech]
  ```

  * `[titular 8]`: los primeros 8 caracteres del titular del producto, tal como vienen en la sábana.
  * `[fecha]`: la fecha de vencimiento de cuota en formato `dd/mm/yyyy`, **en todos los segmentos**.
* **RF-MM-15 — Segmento del speech por días de atraso ajustados:** Elegir el speech de cada producto según sus **días de atraso ajustados al día de envío**, no según la etiqueta del segmento financiero de la sábana:

  ```
  dias_ajustados = dias_atraso (de la sábana) + días calendario entre la fecha de corte y la fecha de envío
  ```

  | Segmento | Días de atraso ajustados |
  |---|---|
  | 1. Preventiva | `dias_ajustados <= 0` |
  | 2. 1 a 8 | `1 <= dias_ajustados <= 8` |
  | 3. 9 a 30 | `9 <= dias_ajustados <= 30` |
  | 4. 31 a 60 | `31 <= dias_ajustados <= 60` |
  | 5. 61 a 90 | `61 <= dias_ajustados <= 90` |
  | 6. 91 a 120 | `91 <= dias_ajustados <= 120` |

  * Ejemplo: `dias_atraso = 4` y el envío es a 3 días de la fecha de corte → `dias_ajustados = 7` → segmento `1 a 8`.
  * Si `dias_ajustados > 120`, entonces el producto no tiene speech y se excluye (RF-MM-13).
  * Fecha de envío para el cálculo: la de `Enviar en hora determinada`; con `Enviar ahora`, la fecha de generación; con `Enviar en diferentes horas`, la más temprana (supuesto S-MM-5).
  * Supuesto S-MM-6: `dias_ajustados = 0` (la cuota vence el mismo día del envío) es `Preventiva`.
* **RF-MM-16 — Variable de WhatsApp en el speech:** Reemplazar la variable de WhatsApp del speech por `https://wa.me/+51` seguido del número de WhatsApp de contacto de la campaña.
  * El número de contacto se configura por campaña, con un valor por defecto en la configuración (RF-32); no se fija en el código.
* **RF-MM-17 — Speech versionado y trazable:** Permitir ajustar y personalizar las partes del speech de cada segmento, guardando cada cambio como una **versión nueva y trazable** (`Speech original`, `Speech 2`, …).
  * Cada campaña registra la versión de speech con la que se generó.
  * Si una versión ya se usó en alguna campaña, entonces no se modifica: el cambio crea una versión nueva.
  * La versión `Speech original` (RF-MM-18) es la referencia del módulo y **no se modifica nunca**, aunque no se haya usado: personalizarla siempre crea una versión nueva.
  * La estructura de RF-MM-14 es la de la versión por defecto; una versión nueva puede cambiar el texto de las partes.
* **RF-MM-18 — Speech original:** Mantener como versión por defecto el speech vigente, con la fecha incluida en todos los segmentos:

  | Segmento | Parte 1 | Parte 2 |
  |---|---|---|
  | Preventiva | ` Caja Cusco te recuerda que tu cuota Vence el ` | `. Si ya pagaste, omite este mensaje.` |
  | 1 a 8 | ` Caja Cusco te informa que tu cuota venció el ` | `, acércate a pagar a nuestras agencias, agentes KASNET o a través de Wayki app.` |
  | 9 a 30 | ` Caja Cusco te informa que tu cuota venció el ` | `, evita estar mal calificado, acércate a pagar a nuestras agencias y/o canales alternativos.` |
  | 31 a 60 | ` Caja Cusco te informa que tu cuota venció el ` | `, ponte al día y participa del sorteo de 06 autos. INFO por [whatsapp]` |
  | 61 a 90 | ` cancela tu deuda CAJA CUSCO vencida el ` | `, pague a tiempo y evite estar mal calificado. Más INFO por [whatsapp]` |
  | 91 a 120 | ` cancela tu deuda CAJA CUSCO vencida el ` | `, pague a tiempo y evite estar mal calificado. Más INFO por [whatsapp]` |

  `[whatsapp]` es el enlace de RF-MM-16.
* **RF-MM-19 — Largo del mensaje:** Controlar el largo de cada `mensaje`:
  * Si supera **160 caracteres** (límite de un SMS), entonces el producto se excluye (RF-MM-13).
  * Si supera **150 caracteres**, entonces se carga pero se advierte, porque el speech se ajusta para no pasar de ~150.
  * La previsualización de una versión de speech muestra el largo máximo que puede alcanzar cada segmento. Con el speech original, `9 a 30` llega a 156 caracteres: se advierte.

## 5. Reporte de enviados (descargado de MES)

Estructura confirmada con el ejemplo de reporte (sección 7).

* **RF-MM-20 — Importar el reporte de enviados:** Permitir importar el reporte "Campañas de enviados" descargado de MES, en `.xlsx`, validando que traiga estas columnas:

  | Columna | Contenido |
  |---|---|
  | `id` | identificador de la campaña en MES (número) |
  | `celular` | teléfono, 9 dígitos (texto) |
  | `mensaje` | mensaje enviado |
  | `fecha de envio` | texto `dd/mm/yy` |
  | `dni` | documento, igual que en la carga |
  | `estado` | estado del envío (observado: `enviado`) |
  | `salida` | tipo de número (observado: `Nro. LARGO`) |
  | `usuario` | usuario emisor (observado: `mgi_kontactus`) |

  * Si falta una columna o la hoja no tiene filas, entonces se rechaza con el motivo.
* **RF-MM-21 — Asociar el reporte a la campaña:** Asociar cada reporte importado a una campaña del sistema, identificada en MES por su `id`.
  * Una campaña del sistema puede tener varios `id` de MES si su carga se dividió en varios archivos.
  * Si un mismo archivo de reporte trae varios `id` de MES, entonces cada `id` se asocia a la campaña elegida y se muestra su conteo por separado; si un `id` no coincide con ninguna fila cargada de la campaña, se advierte, porque probablemente es de otra campaña.
  * Si el mismo `id` de MES ya estaba importado, entonces se advierte y se reemplaza solo con confirmación.
* **RF-MM-22 — Conciliación de cargados y enviados:** Conciliar las filas cargadas con las filas del reporte y mostrar, por campaña: cargados, enviados, cargados no enviados y filas del reporte sin correspondencia, además del conteo por `estado`.
  * La correspondencia usa `numero`/`celular`, `dni` y `mensaje` normalizado.
  * Enviados son las filas cargadas que tienen correspondencia con `estado` = `enviado` (RF-MM-02). Las que tienen correspondencia con otro estado suman a cargados no enviados.
  * **Normalización del mensaje:** se quitan los signos diacríticos (tildes, diéresis y la virgulilla de la `ñ`, que queda `n`) y los espacios en los extremos, **por igual en el mensaje cargado y en el enviado**. MES quita las tildes y recorta espacios al enviar (sección 7); normalizar los dos lados hace que la conciliación funcione aunque MES conserve o no la `ñ`.
  * Los registros de supervisión se concilian y se muestran aparte de los productos (RF-41).

## 6. Decisiones tomadas sobre los puntos abiertos del pedido

| Punto | Decisión | Fuente |
|---|---|---|
| La fórmula no concatena la fecha en `9 a 30` y `31 a 60` | Error de la fórmula: **todos los segmentos llevan la fecha** | Usuario (2026-09-13); en el ejemplo de carga, `31 a 60` ya la lleva |
| Productos cuyo speech queda vacío | **Se excluyen y se reportan**; no se carga un mensaje con solo el titular | Usuario (2026-09-13); en el ejemplo, 2 740 de 10 333 mensajes llevan solo el titular |
| Etiqueta `Preventivo` o `Preventiva` | `Preventiva`, que es la etiqueta de los datos (`1. Preventiva`); el speech se elige por días de atraso ajustados, no por la etiqueta | `docs/sabana-schema.md`; usuario |
| Cierre de paréntesis del `LET` | La fórmula está balanceada: un `)` cierra `SI.CONJUNTO` y el siguiente cierra `LET` | Revisión de la fórmula |
| Split 3/2 y DNIs `00000001`–`00000005` | Configurables por campaña, con 3/2 por defecto y DNIs secuenciales (RF-38, RF-39) | Usuario (2026-09-13) |
| Formato de fecha | `dd/mm/yyyy` es la fecha de vencimiento dentro del speech; `dd/mm/yy` es la fecha de envío del reporte. Son campos distintos | Ejemplos de carga y de reporte |
| Formato de la carga | Se replica el del ejemplo de carga: `Hoja1`, `numero` (entero), `mensaje`, `dni` (texto) | Usuario (2026-09-13); ejemplo de carga |
| Qué cuenta como SMS enviado | Solo la fila con correspondencia y `estado` = `enviado`; otro estado cuenta como cargado no enviado (RF-MM-02, RF-MM-22) | Usuario (2026-09-14); el ejemplo de reporte solo trae `enviado` |
| Documento que no es DNI ni RUC en `dni` | Se carga y la previsualización advierte cuántos lo llevan; no se excluye (RF-MM-10, RF-MM-13) | Usuario (2026-09-14) |
| Mes al que se imputa el límite mensual (antes S-MM-7) | El de la fecha de envío, no el de generación (RF-MM-01) | Usuario (2026-09-14) |
| Producto sin documento de identidad (antes S-MM-8) | Se excluye con su motivo; no se carga con `dni` vacío (RF-MM-13) | Usuario (2026-09-14) |

## 7. Evidencia de los ejemplos

Los ejemplos están en `archivos_anexo_chat/`, con prefijo `MOWA_MES_Ejemplo_`: `MOWA_MES_Ejemplo_CargaGestiones.xlsx` y `MOWA_MES_Ejemplo_ReporteMensajesEnviados.xlsx`. La carpeta **no se versiona** (`.gitignore`) porque contiene datos de cobranza. Lo que sigue son solo agregados y formas, sin ningún valor personal.

**Ejemplo de carga:**

- Hoja `Hoja1`, cabecera `numero`, `mensaje`, `dni`; 10 333 filas.
- `numero`: entero de 9 dígitos. `dni`: texto de 8 caracteres (10 202 filas) u 11 (131 filas).
- Registros de supervisión: DNIs `00000001` a `00000005` en las filas 2 a 6, al inicio del archivo.
- `mensaje`: entre 8 y 150 caracteres; ninguno pasa de 150. Prefijo del titular de 8 caracteres.
- Plantillas presentes: `1 a 8` (5 472), `31 a 60` con fecha (1 516), `61 a 90`/`91 a 120` (605). No hay mensajes de `Preventiva` ni de `9 a 30` en esta muestra.
- **2 740 mensajes (26,5 %) llevan solo los 8 caracteres del titular**, sin speech.

**Ejemplo de reporte de enviados:**

- Hoja `Hoja1`, cabecera `id`, `celular`, `mensaje`, `fecha de envio`, `dni`, `estado`, `salida`, `usuario`; 10 333 filas, una por cada fila cargada, incluida la supervisión en las filas 2 a 6.
- `id`: un único valor numérico para toda la campaña. `celular`: texto de 9 dígitos (en la carga era entero).
- `fecha de envio`: texto `dd/mm/yy`, un único valor. `estado`: `enviado`. `salida`: `Nro. LARGO`. `usuario`: `mgi_kontactus`.
- **MES altera el mensaje al enviarlo:** quita las tildes (`vencio`, `acercate`, `a traves`, `dia`, `Mas`) y recorta espacios en los extremos (10 mensajes pasan de 8 a 7 caracteres de prefijo). Por eso la conciliación normaliza el mensaje (RF-MM-22).

## 8. Supuestos por confirmar con el usuario

| Supuesto | Qué se asumió | Dónde aplica |
|---|---|---|
| S-MM-1 | Sin integración por API: se generan archivos y se importa el reporte a mano | Todo el módulo |
| S-MM-2 | Superar el límite mensual se advierte y se confirma, no se bloquea | RF-MM-01 |
| S-MM-3 | La descripción de campaña no tiene largo máximo mientras no se confirme el de MES | RF-MM-04 |
| S-MM-4 | Feriados nacionales de Perú vigentes al 2026, calculados por regla para cualquier año; decretos y cambios de ley por configuración | RF-MM-08 |
| S-MM-5 | Con `Enviar en diferentes horas`, el segmento se calcula con la fecha más temprana | RF-MM-15 |
| S-MM-6 | `dias_ajustados = 0` es `Preventiva` | RF-MM-15 |

S-MM-7 y S-MM-8 se confirmaron el 2026-09-14 y pasaron a la sección 6.
