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

- `CampoDestino(nombre, clave_etiqueta, tipo, obligatorio, alias)`. `alias` son expresiones regulares sobre el encabezado normalizado, como los `patrones` de hoy. `clave_etiqueta` es la clave i18n del nombre legible (`campo.<nombre>`). `tipo` es un texto descriptivo (en la sábana, el nombre de su `TipoCampo`): el mapeador no convierte valores ni importa `entities/sabana.py`, y una prueba de arquitectura lo fija.
- `CatalogoCampos(id, campos)`. `id` es estable, como `sabana_vencida`, y es la clave de los mapeos recordados (RF-63).
- `EstadoEncabezado`: `recordado`, `coincide`, `parecido`, `sin_coincidencia`.
- `OrigenAsignacion`: `recordado`, `coincide`, `parecido_aceptado`, `manual` (RF-62).
- `ColumnaAnalizada(indice, encabezado, normalizado, ocurrencia, ejemplos, estado, sugerido, similitud)`. `indice` en base 0 (en la API también; en `formato.mapeo` las posiciones siguen en base 1, como hoy). `ocurrencia` cuenta desde 1 entre los encabezados con el mismo normalizado, de izquierda a derecha: los dos «Pagare» de la sábana son las ocurrencias 1 y 2. `ejemplos` hasta 3 valores no vacíos como texto, `sugerido` un campo o `None` (`None` también significa «No cargar»).
- `Asignacion(indice, campo | None, origen)`. `campo = None` es «No cargar esta columna».
- `ProblemaMapeo(indice | None, codigo, detalle, campo | None)`. Códigos: `parecido_sin_revisar`, `obligatorio_sin_columna` (`indice = None`, con el campo), `campo_repetido` (uno por cada encabezado que repite), `campo_desconocido`, `indice_fuera_de_rango`, `asignacion_faltante` e `indice_repetido`.
- `AnalisisEncabezados(catalogo_id, columnas, campos, problemas_iniciales)`.

### 3.2 Normalización y similitud (`services/mapeador/similitud.py`)

- **Normalización:** la de hoy (`reglas.normalizar_cabecera`): sin tildes, en minúsculas, espacios recortados y colapsados. Se mueve al mapeador y la ingesta la importa de ahí, sin copiarla.
- **Coincide:** el normalizado cumple un alias del campo (`fullmatch`) o es igual a su `nombre` con `_` como espacio. Hay **una sola función `coincide(normalizado, campo)`**, que usan `analizar` y también `mapear_cabeceras`, el camino viejo de `POST /cargas`. Así, un encabezado que es igual al nombre de un campo coincide en los dos caminos: por ejemplo, «DIAS ATRASO» ahora coincide con `dias_atraso` (decisión de architec del 2026-10-24, M-6 (a); ver `sabana-schema.md` N-1).
- **Similitud:** el máximo entre `difflib.SequenceMatcher.ratio` de los dos textos y la proporción de palabras en común (Jaccard de tokens). Se compara contra el nombre del campo y contra cada alias que sea un texto literal; un alias con metacaracteres de expresión regular no participa.
  - **Límite conocido:** un campo cuyos alias tienen todos metacaracteres (`documento`, `pagare_duplicado`, `cod_tipo_basilea`…) se compara solo contra su nombre. Si hace falta, más adelante se agrega a `CampoDestino` una lista de nombres literales para la similitud, sin tocar `alias`.
- **Umbral:** `UMBRAL_PARECIDO = 0.75`, una constante de configuración (RF-32) en un solo lugar.
- **Empates:** si los dos mejores candidatos difieren en menos de `0.02`, no se sugiere ninguno (RF-58).

### 3.3 Análisis (`services/mapeador/analisis.py`)

`analizar(cabeceras, filas_muestra, catalogo, recordados) -> AnalisisEncabezados`, una función pura. `recordados` es un `dict` de (encabezado normalizado, ocurrencia) a campo o `None`. La ocurrencia evita que dos encabezados iguales compartan un recordado: si fuera solo por el normalizado, confirmar los dos «Pagare» dejaría «pagare» → `pagare_duplicado`, y en la carga siguiente faltaría el pagaré (M-1).

Precedencia por encabezado, en este orden:
1. **Recordado:** si (normalizado, ocurrencia) está en `recordados`, el estado es `recordado` y se sugiere el campo recordado, que puede ser «No cargar».
2. **Coincide:** el primer campo del catálogo, en su orden, cuyo alias coincide y que no esté tomado. Es la regla de hoy, que mantiene `pagare` antes que `pagare_duplicado`.
3. **Parecido:** el campo de mayor similitud que no esté tomado, si alcanza el umbral y no hay empate.
4. **Sin coincidencia:** se sugiere «No cargar».

Son **tres pasadas sobre todas las columnas**, de izquierda a derecha en cada una: primero todos los recordados, después las coincidencias sobre los campos libres y por último los parecidos sobre los que quedan. Así un recordado gana siempre a una coincidencia, aunque esta esté más a la izquierda (M-3). Un recordado que apunta a un campo ya tomado por otro recordado pasa a `sin_coincidencia`. Los encabezados vacíos no se listan.

Decisiones de B1 sobre lo que el diseño no decía:
- **Parecidos, «mejor primero» (no de izquierda a derecha).** Se arman todos los pares (columna sin decidir, campo libre) con similitud ≥ umbral, se ordenan de mayor a menor similitud (a igual similitud, por índice de columna y después por orden del catálogo) y se recorren saltando las columnas ya decididas y los campos ya tomados. Así la columna 9 con 0,95 a `monto_cuota` le gana a la 2 con 0,76, y la sugerencia no depende de cuántas columnas la precedan. Permutar las columnas no cambia qué campo recibe cada encabezado, salvo los empates exactos de similitud entre columnas, que desempata el índice.
- **Empate y umbral.** El umbral es inclusivo (`similitud >= 0,75`). El empate es por columna y se mide en el momento de asignarla: si sus dos mejores campos **libres** (el segundo puede estar bajo el umbral) difieren en menos de 0,02, la columna queda sin sugerencia y no toma ningún campo.
- **Un recordado hacia un campo que ya no está en el catálogo se ignora:** la columna sigue con la coincidencia o el parecido que le toque. Solo el «tomado por otro recordado» pasa a `sin_coincidencia`.
- **Qué es vacío.** Por defecto, `None` o un texto en blanco (`es_vacio` del mapeador); `analizar` acepta un `vacio` opcional y la sábana le pasa el suyo (`ingesta_sabana.reglas.es_vacio`, que además toma el literal `NULL` por vacío), así que con ese criterio los dos caminos listan las mismas columnas. Sin él, el mapeador lista un encabezado «NULL» (como `sin_coincidencia`, «No cargar») que el camino viejo salta; con mapeo explícito esa columna va a `_extras` y en el camino viejo no está: diferencia conocida y menor que desaparece al pasar el criterio de la sábana.

### 3.4 Validación (`services/mapeador/validacion.py`)

`validar(asignaciones, analisis) -> list[ProblemaMapeo]`, también pura:
- `parecido_sin_revisar`: una columna en estado `parecido` cuya asignación no trae origen `parecido_aceptado` ni `manual`;
- `obligatorio_sin_columna`: un campo obligatorio sin ninguna columna asignada;
- `campo_repetido`: dos o más columnas con el mismo campo; se informa en cada una;
- `campo_desconocido`, `indice_fuera_de_rango`, `asignacion_faltante` (una columna listada sin asignación) e `indice_repetido` (dos asignaciones para la misma columna): protegen la API; la pantalla no los produce. Se exige una asignación por cada columna listada (M-5).

`analisis` es el que se mostró al usuario, guardado con el borrador (§5), no uno nuevo: si otro usuario recordó algo en el medio, un análisis nuevo daría otros estados (M-4). Re-analizar con otras opciones lo reemplaza.

La carga se confirma solo si la lista está vacía (RF-60). Las columnas en «No cargar» no generan problema.

**El origen lo manda la pantalla y lo ajusta el backend.**
- Aceptar un parecido sin cambiar el campo, con el botón «Aceptar» de la fila o con «Aceptar sugerencias», manda `origen = parecido_aceptado` con el mismo campo sugerido.
- Elegir otro campo, o «No cargar», es `manual`.
- El backend no confía en la etiqueta: si llega `parecido_aceptado` con un campo distinto del sugerido, lo guarda como `manual`. En una columna que no era `parecido`, el origen se recalcula desde el análisis (`recordado` o `coincide` si el campo no cambió, `manual` si cambió).

Así, elegir en el `select` el mismo campo que ya estaba no cuenta como revisión: hace falta «Aceptar».

Decisiones de B1 sobre lo que el diseño no decía:
- **El origen de una `sin_coincidencia` que se confirma sin cambio («No cargar») es `manual`:** no tiene origen automático y la confirmó el usuario. Un `parecido` con otro campo (o «No cargar») es `manual` diga lo que diga la etiqueta; con el sugerido conserva su etiqueta, y solo `parecido_aceptado` o `manual` lo dan por revisado.
- **`validar` devuelve solo los problemas;** el origen recalculado sale de `resolver_asignaciones`, que `validar` aplica por dentro y que el backend usa para guardar los orígenes (RF-62). Es idempotente.
- **Orden de los problemas:** primero los de protección de la API (`indice_repetido`, `indice_fuera_de_rango`), después los de cada columna en el orden de las columnas y al final los `obligatorio_sin_columna`, en el orden del catálogo. Con dos asignaciones para una misma columna se valida la primera; un índice fuera de rango es el de una columna que no se listó (incluidos los encabezados vacíos).

### 3.5 Catálogo de la sábana

`ingesta_sabana/catalogo.py` expone `CATALOGO_SABANA = CatalogoCampos("sabana_vencida", ...)` derivado de `CATALOGO_VENCIDA`. `requerida` pasa a `obligatorio`, `patrones` pasa a `alias` y la etiqueta es `campo.<nombre>`. `mapear_cabeceras` de hoy se mantiene para `POST /cargas` con archivo y para el procesamiento sin borrador, y usa la misma `coincide` (§3.2).

## 4. Lectores (`adapters/input/`)

Puerto nuevo `LectorTablaPort.leer(contenido, nombre_archivo, opciones) -> TablaLeida`:
- `OpcionesLectura(hoja, separador, codificacion)`: todos opcionales; sin valor, se detecta.
- `TablaLeida(formato, hojas, hoja, separador, codificacion, fila_cabecera, cabeceras, filas)`: lo detectado viaja de vuelta para mostrarlo y poder cambiarlo.

El formato se decide por la extensión del nombre, y si falta, por el contenido.

| Formato | Lectura |
|---|---|
| `xlsx`, `xlsb`, `xls`, `ods` | `LectorCalamine`, que ahora lista las hojas y lee la elegida. Por defecto, `VENCIDA` si existe y, si no, la primera (RF-57). |
| `csv` | Codificación (RF-57): UTF-8, con o sin BOM; Windows-1252, la del Excel en español; o Latin-1 si Windows-1252 no la decodifica. Separador: el primero de `;`, tabulación y `,` que da el mismo número de campos (más de uno) en todos los registros de la muestra (los primeros 50 de los primeros 64 KB); si ninguno es consistente, `csv.Sniffer` restringido a esos tres y, si no decide, `;` si aparece en la primera línea y, si no, `,`. La primera fila no vacía es la de encabezados. |
| `json` | Debe ser una lista de objetos; si no, `ArchivoIlegible` con el motivo. Los encabezados son la unión de las claves, en el orden en que aparecen por primera vez. Un valor objeto o lista se guarda como texto JSON y genera la advertencia `valor_no_escalar` en su fila. |

`LectorSabanaPort.leer_hoja` se mantiene para el procesamiento y delega en el lector nuevo. El límite de tamaño es el de hoy (`TAMANO_MAXIMO_BYTES`).

Decisiones de B2 sobre lo que el diseño no decía:
- **Dónde vive.** `entities/lectura_tabla.py` (`FormatoTabla`, `OpcionesLectura`, `TablaLeida`, `AdvertenciaLectura`), `ports/lector_tabla_port.py`, `services/lectura_tabla.py` (la detección del formato, pura) y, en `adapters/input/`, `lector_tabla.py` (despacha), `lector_csv.py`, `lector_json.py` y `lector_calamine.py` (`leer_tabla`). Se reusan `FilaCruda` y los errores `ArchivoIlegible`, `HojaNoEncontrada` y `HojaVacia` de `entities/sabana.py`; el núcleo de la lectura no importa el mapeador ni la ingesta.
- **Formato.** Por extensión (`xlsx`/`xlsm`, `xlsb`, `xls`, `ods`, `csv`/`tsv`/`txt`, `json`) y, si falta o no se conoce, por el contenido: firma ZIP (`PK`) o OLE para las hojas de cálculo (dentro del ZIP: `mimetype` de ODS, `xl/workbook.bin` de XLSB, si no XLSX), `[` o `{` (tras un BOM y espacios) para JSON y, si no, CSV. En las hojas de cálculo el formato que se informa sale del contenido, no de la extension. Una extensión que no coincide con el contenido (una hoja de cálculo con texto, un `.csv` o `.json` que es una hoja de cálculo, un `.json` que no empieza con `[` o `{`) es `ArchivoIlegible` con el motivo; un `.csv` manda sobre el texto aunque parezca JSON. Sin extensión, un archivo vacío es `ArchivoIlegible`; un `.csv` vacío o sin datos es `HojaVacia`.
- **Hojas de cálculo.** `TablaLeida.hojas` lista las hojas y `hoja` es la leída: la pedida o, sin ella, `VENCIDA` si existe y, si no, la primera. `LectorCalamine.leer_hoja` (el camino de la ingesta) sigue pidiendo una hoja por nombre, sin caer a la primera, y sigue exigiendo una hoja de cálculo.
- **CSV, codificación.** Se prueban en este orden: UTF-8 con BOM (el BOM se quita, también si la codificación elegida es `utf-8`), UTF-8, Windows-1252 y, solo si Windows-1252 no decodifica (los bytes 0x81, 0x8D, 0x8F, 0x90 y 0x9D no están definidos), Latin-1. `codificacion` es el nombre del codec usado: `utf-8-sig`, `utf-8`, `windows-1252` o `latin-1`; esa lista, en ese orden, es la constante `CODIFICACIONES` (`lector_csv.py`) que ofrece la pantalla, y la elegida a mano gana. Windows-1252 importa porque el «CSV» del Excel de Windows en español guarda ahí las comillas tipográficas, la raya y el euro (0x80–0x9F), que en Latin-1 serían controles invisibles. Unos bytes de una codificación de un byte que también son UTF-8 válido se leen como UTF-8: no hay forma de distinguirlos sin que el usuario elija.
- **CSV, separador.** No lo decide el desempate de `csv.Sniffer`, que prefiere la coma: el Excel en español exporta con `;` y coma decimal (`agencia;saldo,total` / `Norte;1500,25`), y el Sniffer elegiría la coma y partiría los montos. Por cada candidato, en el orden `;`, tabulación, `,` (que también desempata), se cuentan los campos de cada uno de los primeros 50 registros de la muestra de 64 KB (sin los vacíos; si la muestra se cortó, sin el último, que puede estar partido): gana el primero que da el mismo número, mayor que uno, en todos. Si ninguno lo es, se recurre al Sniffer y, si no decide, a la regla de `;` en la primera línea. Un archivo de una sola columna cae en `,`. `separador` es un solo carácter. Un separador o una codificación elegidos que no sirven son `ArchivoIlegible`. Una celda es texto y no se recorta (los espacios se conservan). Los números de fila son los del registro (una celda entrecomillada con saltos de línea es una sola fila) y cuentan también las filas vacías. Un CSV sin cabecera ni datos es `HojaVacia`.
- **JSON.** La fila 1 es la de encabezados y los objetos son las filas 2 en adelante; una clave ausente o un `null` es una celda vacía (`""`), como en una hoja de cálculo; un objeto vacío no es una fila pero cuenta en la numeración. **Cómo viaja la advertencia:** `TablaLeida.advertencias` es una tupla de `AdvertenciaLectura(numero_fila, columna, codigo)` con `codigo = valor_no_escalar` (`CodigoAdvertenciaLectura`, un enum que B3 publica en el contrato), una por cada valor objeto o lista, con el encabezado de la columna. Vacía en los demás formatos.

## 5. Persistencia

Una migración con dos tablas y una columna:
- **`borrador_carga_archivo`:** `id`, `catalogo_id`, `nombre_archivo`, `contenido` (bytea), `huella`, `tamano_bytes`, `opciones` (JSONB: hoja, separador y codificación elegidos), `analisis` (JSONB: el análisis que se mostró, contra el que se valida al confirmar, M-4) y `creado_en`. Un borrador vence a las 24 horas. Los vencidos se borran al iniciar la aplicación (junto a `recuperar_interrumpidas`) y al crear uno nuevo. Confirmar un borrador lo borra en la misma transacción que crea la carga.
- **`mapeo_recordado`:** `catalogo_id`, `encabezado_normalizado`, `ocurrencia`, `campo` (nulo = «No cargar») y `actualizado_en`, con único (`catalogo_id`, `encabezado_normalizado`, `ocurrencia`) (M-1). Al confirmar se hace *upsert* de todas las asignaciones confirmadas (RF-61).
- **`carga.opciones_lectura`** (JSONB: formato, hoja, separador y codificación): `procesar_carga` relee el archivo con esto, porque un CSV necesita el separador y la codificación elegidos (M-2). Las versiones existentes quedan con `{hoja}`, y `carga.hoja` se mantiene por compatibilidad.

La versión de la sábana (`carga`) guarda en `formato.mapeo` lo de hoy, **sin cambios** (`columnas`, `desconocidas` y `faltantes`, con posiciones en base 1), **más** `origenes` (`{campo: origen}`) e `ignoradas` (`{posición: encabezado}`) (RF-62). El cambio es aditivo: el camino viejo y las versiones viejas se leen igual (M-7).

**Concurrencia:** confirmar bloquea el borrador (`SELECT … FOR UPDATE`); un segundo confirmar del mismo borrador responde 404.

## 6. API

Genérica del mapeador, prefijo `/mapeador`:
- **`GET /mapeador/catalogos/{catalogo_id}`:** los campos con nombre, clave de etiqueta, tipo y obligatorio. Es la lista del desplegable.
- **`POST /mapeador/{catalogo_id}/borradores`** (multipart: `archivo`, y opcionales `hoja`, `separador` y `codificacion`): crea el borrador y devuelve el análisis:
  - lo general: `borrador_id`, `formato`, `hojas`, `hoja`, `separador`, `codificacion`, `filas` (cuántas);
  - las columnas: indice, encabezado, ejemplos, estado, sugerido y similitud;
  - `problemas` iniciales, calculados con las asignaciones sugeridas.

  Devuelve 400 si el archivo es ilegible o está vacío, y 413 si supera el tamaño.
- **`POST /mapeador/borradores/{id}/analisis`** (JSON con `hoja`, `separador` y `codificacion`): vuelve a analizar el mismo borrador con otras opciones. 404 si no existe o venció.
- **`POST /mapeador/borradores/{id}/validacion`** (JSON con `asignaciones`, una por columna): devuelve los `problemas`, validados contra el análisis guardado en el borrador. La pantalla lo llama al cambiar una asignación, con espera corta y cancelación, como el motor de texto.
- **`DELETE /mapeador/borradores/{id}`:** descarta el borrador (cancelar).

La confirmación es del consumidor, porque sabe qué hacer con el archivo:
- **`POST /cargas/desde-borrador`** (JSON: `borrador_id`, `fecha_corte`, `asignaciones`): vuelve a validar en el backend. Con problemas responde 422 con la lista, y sin problemas:
  1. crea la versión, como `registrar_carga`;
  2. guarda los recordados;
  3. borra el borrador;
  4. encola el procesamiento con el mapeo explícito.

  Responde 202, como `POST /cargas`.
- `procesar_carga` lee el archivo con `carga.opciones_lectura` y usa el mapeo guardado con la carga si lo tiene; si no, `mapear_cabeceras` como hoy. Las columnas en «No cargar» van al registro crudo de cada fila (`_extras`), como las desconocidas.

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
  - `pagare` antes que `pagare_duplicado`;
  - dos «Pagare»: confirmar y volver a analizar da `pagare` y `pagare_duplicado` como recordados, y se puede confirmar (M-1);
  - un recordado a la derecha gana el campo a una coincidencia a la izquierda (M-3).
- **Validación:** cada código, incluidos `asignacion_faltante` e `indice_repetido`; validar contra el análisis guardado aunque los recordados hayan cambiado (M-4); propiedad: si no hay problemas, toda columna asignada tiene un campo distinto y todos los obligatorios están.
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
  - el siguiente análisis llega «recordado»;
  - un CSV confirmado se procesa con su separador y su codificación (`opciones_lectura`, M-2);
  - dos confirmaciones del mismo borrador: la segunda da 404 (`@postgres` y su doble sin base).
- **Paridad:** un archivo cuyas cabeceras ya coincidían por alias produce la misma versión por los dos caminos, con archivo y con borrador confirmado sin cambios. Caso nuevo del camino viejo: «DIAS ATRASO» ahora coincide con `dias_atraso` (M-6). `formato.mapeo` conserva sus claves de hoy (M-7).
- **Datos sintéticos siempre:** ningún encabezado ni valor real en pruebas ni en documentación.
