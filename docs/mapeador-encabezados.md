# Mapeador de encabezados (RF-57 a RF-63)

Diseño técnico del mapeador de encabezados: relaciona las columnas de un archivo tabular (Excel, ODS, CSV o JSON) con los campos de un catálogo, deja revisarlo y corregirlo en pantalla y recuerda lo confirmado. Es una capacidad **transversal y reutilizable** (RF-63). El primer consumidor es la carga de sábanas (RF-01, RF-02).

Decisiones del usuario del 2026-10-24:
- los parecidos llegan preseleccionados y hay que confirmarlos;
- el mapeo confirmado se recuerda;
- la hoja de Excel se elige;
- en CSV se detectan el separador y la codificación, con ajuste manual.

## 1. Estado actual y problema

- `ingesta_sabana/cabeceras.py` ya mapea por nombre y alias, no por posición (regla N-1 de `sabana-schema.md`). Usa `CATALOGO_VENCIDA` (`catalogo.py`): `ColumnaSabana(nombre, tipo, patrones, requerida)`.
- Si un encabezado no coincide con ningún alias, la columna queda «desconocida». Si era requerida (hoy solo `pagare`), la carga **falla** sin que el usuario pueda corregirla. No hay ningún paso para revisar.
- `LectorCalamine` lee `.xlsb`, `.xlsx`, `.xls` y `.ods`, siempre de una hoja fija (`VENCIDA` por defecto). No hay lectura de CSV ni de JSON.
- `POST /cargas` sube y encola el procesamiento en un solo paso.

## 2. Principios

1. **El mapeador no conoce la sábana.** Recibe un catálogo de campos y una tabla leída, y devuelve un análisis. La sábana aporta su catálogo, como `mowa_mes.speech` aporta su contexto al motor de texto.
2. **El backend decide; la pantalla muestra.** El estado de cada encabezado, la sugerencia y los problemas de validación los calcula el backend. El frontend no repite reglas.
3. **No se sube dos veces.** El archivo analizado queda en un borrador y se confirma por su identificador. Cambiar la hoja, el separador o la codificación vuelve a analizar el mismo borrador.
4. **Compatibilidad.** `POST /cargas` con `archivo` sigue funcionando como hoy: mapeo automático por alias, sin pasos. La pantalla pasa al flujo de dos pasos.

## 3. Núcleo (`backend/app/core/`, sin infraestructura)

### 3.1 Entidades (`entities/mapeador.py`)

- `CampoDestino(nombre, clave_etiqueta, tipo, obligatorio, alias)`. `alias` son expresiones regulares sobre el encabezado normalizado, como los `patrones` de hoy. `clave_etiqueta` es la clave i18n del nombre legible (`campo.<nombre>`).
- `CatalogoCampos(id, campos)`. `id` es estable, como `sabana_vencida`, y es la clave de los mapeos recordados (RF-63).
- `EstadoEncabezado`: `recordado`, `coincide`, `parecido`, `sin_coincidencia`.
- `OrigenAsignacion`: `recordado`, `coincide`, `parecido_aceptado`, `manual` (RF-62).
- `ColumnaAnalizada(indice, encabezado, normalizado, ejemplos, estado, sugerido, similitud)`. `indice` en base 0, `ejemplos` hasta 3 valores no vacíos como texto, `sugerido` un campo o `None` (`None` también significa «No cargar»).
- `Asignacion(indice, campo | None, origen)`. `campo = None` es «No cargar esta columna».
- `ProblemaMapeo(indice | None, codigo, detalle, campo | None)`. Códigos: `parecido_sin_revisar`, `obligatorio_sin_columna` (`indice = None`, con el campo), `campo_repetido` (uno por cada encabezado que repite), `campo_desconocido` e `indice_fuera_de_rango`.
- `AnalisisEncabezados(catalogo_id, columnas, campos, problemas_iniciales)`.

### 3.2 Normalización y similitud (`services/mapeador/similitud.py`)

- **Normalización:** la de hoy (`reglas.normalizar_cabecera`): sin tildes, en minúsculas, espacios recortados y colapsados. Se mueve al mapeador y la ingesta la importa de ahí, sin copiarla.
- **Coincide:** el normalizado cumple un alias del campo (`fullmatch`) o es igual a su `nombre` con `_` como espacio.
- **Similitud:** el máximo entre `difflib.SequenceMatcher.ratio` de los dos textos y la proporción de palabras en común (Jaccard de tokens). Se compara contra el nombre del campo y contra cada alias que sea un texto literal; un alias con metacaracteres de expresión regular no participa.
- **Umbral:** `UMBRAL_PARECIDO = 0.75`, una constante de configuración (RF-32) en un solo lugar.
- **Empates:** si los dos mejores candidatos difieren en menos de `0.02`, no se sugiere ninguno (RF-58).

### 3.3 Análisis (`services/mapeador/analisis.py`)

`analizar(cabeceras, filas_muestra, catalogo, recordados) -> AnalisisEncabezados`, una función pura. `recordados` es un `dict` de encabezado normalizado a campo o `None`.

Precedencia por encabezado, en este orden:
1. **Recordado:** si el normalizado está en `recordados`, el estado es `recordado` y se sugiere el campo recordado, que puede ser «No cargar».
2. **Coincide:** el primer campo del catálogo, en su orden, cuyo alias coincide y que no esté tomado. Es la regla de hoy, que mantiene `pagare` antes que `pagare_duplicado`.
3. **Parecido:** el campo de mayor similitud que no esté tomado, si supera el umbral y no hay empate.
4. **Sin coincidencia:** se sugiere «No cargar».

Un campo queda «tomado» por la primera columna que lo recibe en los pasos 1 y 2, recorriendo de izquierda a derecha. Los parecidos se resuelven después, sobre los campos que quedaron libres. Un recordado que apunta a un campo ya tomado por otro recordado pasa a `sin_coincidencia`. Los encabezados vacíos no se listan.

### 3.4 Validación (`services/mapeador/validacion.py`)

`validar(asignaciones, analisis) -> list[ProblemaMapeo]`, también pura:
- `parecido_sin_revisar`: una columna en estado `parecido` cuya asignación no trae origen `parecido_aceptado` ni `manual`;
- `obligatorio_sin_columna`: un campo obligatorio sin ninguna columna asignada;
- `campo_repetido`: dos o más columnas con el mismo campo; se informa en cada una;
- `campo_desconocido` e `indice_fuera_de_rango`: protegen la API; la pantalla no los produce.

La carga se confirma solo si la lista está vacía (RF-60). Las columnas en «No cargar» no generan problema.

**El origen lo manda la pantalla y lo ajusta el backend.**
- Aceptar un parecido sin cambiar el campo, con el botón «Aceptar» de la fila o con «Aceptar sugerencias», manda `origen = parecido_aceptado` con el mismo campo sugerido.
- Elegir otro campo, o «No cargar», es `manual`.
- El backend no confía en la etiqueta: si llega `parecido_aceptado` con un campo distinto del sugerido, lo guarda como `manual`. En una columna que no era `parecido`, el origen se recalcula desde el análisis (`recordado` o `coincide` si el campo no cambió, `manual` si cambió).

Así, elegir en el `select` el mismo campo que ya estaba no cuenta como revisión: hace falta «Aceptar».

### 3.5 Catálogo de la sábana

`ingesta_sabana/catalogo.py` expone `CATALOGO_SABANA = CatalogoCampos("sabana_vencida", ...)` derivado de `CATALOGO_VENCIDA`. `requerida` pasa a `obligatorio`, `patrones` pasa a `alias` y la etiqueta es `campo.<nombre>`. `mapear_cabeceras` de hoy se mantiene para `POST /cargas` con archivo y para el procesamiento sin borrador.

## 4. Lectores (`adapters/input/`)

Puerto nuevo `LectorTablaPort.leer(contenido, nombre_archivo, opciones) -> TablaLeida`:
- `OpcionesLectura(hoja, separador, codificacion)`: todos opcionales; sin valor, se detecta.
- `TablaLeida(formato, hojas, hoja, separador, codificacion, fila_cabecera, cabeceras, filas)`: lo detectado viaja de vuelta para mostrarlo y poder cambiarlo.

El formato se decide por la extensión del nombre, y si falta, por el contenido.

| Formato | Lectura |
|---|---|
| `xlsx`, `xlsb`, `xls`, `ods` | `LectorCalamine`, que ahora lista las hojas y lee la elegida. Por defecto, `VENCIDA` si existe y, si no, la primera (RF-57). |
| `csv` | Codificación: UTF-8 con BOM, UTF-8 y, si falla, Latin-1. Separador: `csv.Sniffer` restringido a `,` `;` y tabulación, sobre los primeros 64 KB; si no decide, `;` si aparece en la primera línea y, si no, `,`. La primera fila no vacía es la de encabezados. |
| `json` | Debe ser una lista de objetos; si no, `ArchivoIlegible` con el motivo. Los encabezados son la unión de las claves, en el orden en que aparecen por primera vez. Un valor objeto o lista se guarda como texto JSON y genera la advertencia `valor_no_escalar` en su fila. |

`LectorSabanaPort.leer_hoja` se mantiene para el procesamiento y delega en el lector nuevo. El límite de tamaño es el de hoy (`TAMANO_MAXIMO_BYTES`).

## 5. Persistencia

Una migración con dos tablas:
- **`borrador_carga_archivo`:** `id`, `catalogo_id`, `nombre_archivo`, `contenido` (bytea), `huella`, `tamano_bytes`, `opciones` (JSONB: hoja, separador y codificación elegidos) y `creado_en`. Un borrador vence a las 24 horas. Los vencidos se borran al iniciar la aplicación (junto a `recuperar_interrumpidas`) y al crear uno nuevo. Confirmar un borrador lo borra en la misma transacción que crea la carga.
- **`mapeo_recordado`:** `catalogo_id`, `encabezado_normalizado`, `campo` (nulo = «No cargar») y `actualizado_en`, con único (`catalogo_id`, `encabezado_normalizado`). Al confirmar se hace *upsert* de todas las asignaciones confirmadas (RF-61).

La versión de la sábana (`carga`) guarda en `formato.mapeo` lo que guarda hoy más el origen de cada asignación: `{"columnas": {campo: posición}, "origenes": {campo: origen}, "ignoradas": {posición: encabezado}}` (RF-62).

## 6. API

Genérica del mapeador, prefijo `/mapeador`:
- **`GET /mapeador/catalogos/{catalogo_id}`:** los campos con nombre, clave de etiqueta, tipo y obligatorio. Es la lista del desplegable.
- **`POST /mapeador/{catalogo_id}/borradores`** (multipart: `archivo`, y opcionales `hoja`, `separador` y `codificacion`): crea el borrador y devuelve el análisis:
  - lo general: `borrador_id`, `formato`, `hojas`, `hoja`, `separador`, `codificacion`, `filas` (cuántas);
  - las columnas: indice, encabezado, ejemplos, estado, sugerido y similitud;
  - `problemas` iniciales, calculados con las asignaciones sugeridas.

  Devuelve 400 si el archivo es ilegible o está vacío, y 413 si supera el tamaño.
- **`POST /mapeador/borradores/{id}/analisis`** (JSON con `hoja`, `separador` y `codificacion`): vuelve a analizar el mismo borrador con otras opciones. 404 si no existe o venció.
- **`POST /mapeador/borradores/{id}/validacion`** (JSON con `asignaciones`): devuelve los `problemas`. La pantalla lo llama al cambiar una asignación, con espera corta y cancelación, como el motor de texto.
- **`DELETE /mapeador/borradores/{id}`:** descarta el borrador (cancelar).

La confirmación es del consumidor, porque sabe qué hacer con el archivo:
- **`POST /cargas/desde-borrador`** (JSON: `borrador_id`, `fecha_corte`, `asignaciones`): vuelve a validar en el backend. Con problemas responde 422 con la lista, y sin problemas:
  1. crea la versión, como `registrar_carga`;
  2. guarda los recordados;
  3. borra el borrador;
  4. encola el procesamiento con el mapeo explícito.

  Responde 202, como `POST /cargas`.
- `procesar_carga` usa el mapeo guardado con la carga si lo tiene, y si no, `mapear_cabeceras` como hoy. Las columnas en «No cargar» van al registro crudo de cada fila (`_extras`), como las desconocidas.

Los códigos (`EstadoEncabezado`, `OrigenAsignacion` y los de `ProblemaMapeo`) se publican como enums en el contrato, como `CodigoTexto` (B9 del motor), para que el frontend no los escriba a mano. `contratos/openapi.json` se regenera en el mismo corte.

## 7. Frontend

**Componente reutilizable `MapeadorEncabezados`** (de `designer`, como `EditorTexto`), en `src/components/` y `src/scripts/mapeador-encabezados.ts`:
- se monta con `montarMapeador(raiz, { analisis, campos, validar })` y expone `estado()`, `fijarAnalisis(analisis)` y `destruir()`;
- emite `mapeocambiado` con `{ asignaciones, problemas, listo }`;
- `validar` es la función que llama a `/validacion`: el componente no conoce la sábana.

**Experiencia (la fija `designer` antes de programar; su especificación reemplaza esta lista).** Ajustes ya adelantados por `designer` (2026-10-24), y compatibles con este diseño:
- «Aceptar» por fila (§3.4);
- un `.segmented` «Por revisar (n) · Todas (n)» en lugar del resumen y el filtro;
- sin nada que revisar, la tabla se recoge en «Las N columnas coinciden…» con «Ver columnas»;
- los estados como `.tag` con texto, sin la similitud numérica (la API la sigue devolviendo para pruebas y orden);
- en el `select`, los campos en uso no se deshabilitan: se marcan «· en uso», para poder intercambiar dos, y el repetido lo señala `campo_repetido`.

Propuesta inicial:
- una tabla con `Encabezado del archivo | Ejemplos | Estado | Campo`; el estado con texto e icono, sin depender solo del color;
- el campo en un `select` con todos los campos por su nombre legible, agrupados («Obligatorios» y «Otros campos»), más «No cargar esta columna»;
- un resumen arriba: «N coinciden · N recordados · N parecidos por revisar · N sin coincidencia»;
- «Aceptar sugerencias» acepta los parecidos de una vez;
- un filtro «Solo lo que falta revisar»;
- el problema bajo su fila, y el de obligatorio sin columna arriba;
- la acción de confirmar, inactiva con el motivo a la vista mientras haya problemas.

**Pantalla de cargas** (`/cargas`, de `dev_frontend`), en dos pasos:
1. «Elegir archivo» y fecha de corte. Al elegir, se crea el borrador.
2. «Revisar columnas»: el componente, más los controles de hoja (si hay varias), separador y codificación (si es CSV), que vuelven a analizar. Después, «Confirmar y cargar».

Al cancelar se borra el borrador. El seguimiento de la versión y sus incidencias no cambia.

## 8. Cortes, agentes y orden

| Corte | Qué | Agente | Depende de |
|---|---|---|---|
| T-MAP-C1 | Plan: contrastar este diseño con el código, fijar cortes y lanzar | coordinador | — |
| T-MAP-B1 | Núcleo: entidades, normalización movida, similitud, `analizar`, `validar` y `CATALOGO_SABANA`, con pruebas sin base y propiedades | dev_backend | C1 |
| T-MAP-B2 | Lectores: `LectorTablaPort`, CSV, JSON y hojas en `LectorCalamine`, con pruebas de detección (separadores, codificaciones, BOM y JSON inválido) | dev_backend | C1 |
| T-MAP-B3 | Persistencia y API: migración, borradores con vencimiento, recordados, endpoints `/mapeador`, `POST /cargas/desde-borrador`, procesamiento con mapeo explícito y RF-62; contrato regenerado y pruebas `@postgres` | dev_backend | B1 y B2 |
| T-MAP-F1 | Experiencia y componente `MapeadorEncabezados`, con Vitest, Playwright con API falsa y axe | designer | B3 (contrato) |
| T-MAP-F2 | `/cargas` en dos pasos sobre el componente | dev_frontend | F1 |
| T-MAP-C2 | Revisión de cierre contra RF-57 a RF-63 | coordinador | todos |

Como siempre, `architec` corre `-ConBase`, el backend en Linux y Playwright completo, y mide la ingesta con 120 000 filas antes y después de B3. El análisis lee el archivo entero una vez; la muestra de ejemplos son las primeras 200 filas con datos.

## 9. Pruebas mínimas

- **Análisis:**
  - cada estado y la precedencia, incluido que un recordado gana a una coincidencia;
  - el orden de las columnas no cambia el resultado;
  - empate sin sugerencia;
  - un recordado contra un campo ya tomado;
  - `pagare` antes que `pagare_duplicado`.
- **Validación:** cada código; propiedad: si no hay problemas, toda columna asignada tiene un campo distinto y todos los obligatorios están.
- **Lectores:**
  - CSV con coma, punto y coma y tabulación;
  - UTF-8, UTF-8 con BOM y Latin-1 con tildes;
  - JSON válido, JSON que no es lista y valores no escalares;
  - Excel con varias hojas y sin `VENCIDA`.
- **API:**
  - borrador vencido (404);
  - re-análisis sin volver a subir;
  - confirmación con problemas (422);
  - confirmación que guarda los recordados y borra el borrador;
  - el siguiente análisis llega «recordado».
- **Paridad:** un archivo que hoy carga bien por alias produce la misma versión por los dos caminos, con archivo y con borrador confirmado sin cambios.
- **Datos sintéticos siempre:** ningún encabezado ni valor real en pruebas ni en documentación.
