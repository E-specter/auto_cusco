# Plan de ejecución del módulo `whatsmkt` (Fase 2 y 3)

Coordinador: `coordinador_modulo_whatsmkt`. Reporta a `architec`. Fecha: 2026-11-02.

Fuentes: `docs/requerimientos-whatsmkt.md` (RF-WM-01 a RF-WM-44, S-WM-1 a 9, DU-WM-1 a 11), plan WhatsMKT v2 (§3, §6.2, §6.3 y §8), `docs/atomics-requirements.md` (RF-37 a RF-41, RF-44, RF-49, RF-51, RF-53, RF-55, RF-69 a RF-74), `docs/testing.md` y `docs/contrato-api.md`.

## 1. Reglas que valen para todos los cortes

- **Sin escrituras cruzadas.** El módulo no toca el motor, el constructor, el generador, el exportador, el calendario ni la supervisión. Lo que falte se pide a `coordinador_herramientas_implementadas`. Código propio en:
  - `core/services/plataformas/whatsmkt/`;
  - `core/entities/whatsmkt*.py`;
  - `adapters/output/plataformas/whatsmkt/`;
  - `adapters/persistence/repositorio_whatsmkt*_postgres.py`;
  - `api/whatsmkt*.py`;
  - frontend `/whatsmkt/*`.
- **Dudas abiertas (DU-WM-1 a 11).** Se implementan con la regla provisional que dice cada RF. Cada una vive en un solo lugar, sea configuración o constante con comentario `DU-WM-n`, para cambiarla con una línea cuando el usuario responda.
- **Días de envío fijos.** Son de lunes a sábado y comunes a todos los canales (RF-70). `whatsmkt_configuracion` no tiene campo de días.
- **Códigos.** Un enum `CodigoWhatsmkt` en el contrato, con su prueba espejo en i18n (`whatsmkt.codigo.*`). Los nombres son los de `docs/whatsmkt-interfaz.md` §7 (designer), más `horario_invalido`: 27 códigos. El enum nace completo en B1, con todos los de B1 a B6, para que la prueba espejo nazca igual y no cambie en cada corte. Un código nuevo se acuerda primero con designer, que agrega su texto en el §7.
- **Contrato.** `contratos/openapi.json` se regenera en el mismo corte que cambia un endpoint (`exportar_openapi.py`), y en ese mismo corte se corre `npm run contrato` desde `frontend/` y `contrato:comprobar` queda en verde. Lo que faltó en B1 (8663c0c). Si dos cortes cambian el contrato a la vez, el que entra segundo lo regenera desde el código después del rebase, sin mezclar a mano.
- **Nombres.** Los modelos Pydantic llevan `Whatsmkt` en el nombre (por ejemplo, `ConfiguracionWhatsmktEntrada`): con un nombre genérico chocan con los de MOWA en OpenAPI y renombran sus esquemas. Los nombres de restricción de la base miden 63 caracteres o menos: PostgreSQL acorta los más largos con un hash (lo que falló en B1).
- **JSONB.** Toda columna JSONB nace con `none_as_null=True` y un `CHECK jsonb_typeof(...)` (lección de T-MM-B14; T-JSON-1).
- **Datos de prueba.** Siempre sintéticos, con teléfonos `900000xxx`. Los Excel de `data/whatsmkt/` no se abren en las pruebas.
- **Verificación.** El dev corre las capas sin base (pytest sin `@postgres`, `ruff format` y `ruff check`) con el turno de máquina concedido por `coordinador_herramientas_implementadas`. Las capas `-ConBase` y `@postgres`, y la ida y vuelta de las migraciones, las corre `architec`. Lo que no corrió se informa.
- **Entrega.** Sin commits: worktree propio con ruta absoluta, entrega al coordinador, que revisa y pasa a `architec`.

## 2. Dependencias con herramientas (Fase 1)

| Pieza compartida | RF | Tarea | La necesita |
|---|---|---|---|
| Funciones `nombres`/`apellidos` | RF-44 | T-HI-B1 | B2 (definición de referencia) |
| Etiqueta y plataforma en las definiciones | RF-49, RF-72 | T-HI-B2 | B2 |
| Celda de texto en XLSX | RF-73 | T-HI-B3 | B2 |
| Textos guardados | RF-69 | T-HI-B4 | B3 |
| Lunes a sábado y próximos N días | RF-70, RF-71 | T-HI-B5 | B4 |

**Decisión sobre las claves foráneas (pedido de `architec`):** B1 no se adelanta a herramientas.

- Crea solo las tablas que no dependen de piezas pendientes: configuración, segmentos y adjuntos.
- La referencia del segmento a su mensaje guardado (`texto_guardado_id`) entra en una migración de B3, cuando exista `texto_guardado` (T-HI-B4).
- La definición por defecto de la configuración apunta a `definicion_carga`, que ya existe, como FK nula. El chequeo de que sea de plataforma `whatsmkt` se agrega en B2, con RF-72.
- Las tablas de campaña (`whatsmkt_campana`, `_archivo`, `_fila_cargada`, `_exclusion`) entran en B4. Las del informe (`whatsmkt_reporte`, `_reporte_fila`) entran en B6. Así cada tabla nace con sus claves foráneas reales, sin columnas «para después».

## 3. Cortes del backend

### B1 — Configuración, segmentos y adjuntos (T-WM-B1)

**RF:** RF-WM-04, RF-WM-07 (franjas), RF-WM-20, RF-WM-33 (plantilla), RF-WM-26 (tope), RF-WM-30 y RF-WM-31 (topes, tabla). **Depende de:** T-WM-0b (hecho).

- **Entidades** (`core/entities/whatsmkt.py`):
  - `ConfiguracionWhatsmkt`:
    - `horario_1` y `horario_2`, cada uno con inicio y fin; por defecto `08:00–14:00` y `14:00–20:00`;
    - `plantilla_nombre`;
    - `definicion_defecto_id` (nula);
    - `tope_mensaje` (4096, S-WM-7);
    - `tope_video`, `tope_audio` y `tope_pdf` (16 000 000 bytes cada uno, S-WM-8).
  - `SegmentoWhatsmkt`: `clave`, `etiqueta`, `desde` (nulo = sin piso), `hasta` (nulo = sin tope) y `orden`.
  - `AdjuntoWhatsmkt`: `id`, `tipo` (`imagen_jpeg`, `imagen_png`, `video`, `audio`, `pdf`), `nombre`, `tamano`, `huella` (SHA-256 en hex), `creado_en` y `archivado_en`. El contenido va aparte, para no cargarlo al listar.
- **Reglas puras** (`core/services/plataformas/whatsmkt/configuracion.py` y `segmentos.py`):
  - Horario: inicio < fin, en formato `HH:MM`.
  - Plantilla del nombre: solo admite las variables `{fecha_corte}` y `{segmento}` (DU-WM-6). Una variable desconocida se rechaza, indicando cuál.
  - Plantilla por defecto: `CUZCO_Vencida ({segmento}) whatsapp {fecha_corte}`, con `{fecha_corte}` en `AAAA.MM.DD`. Es provisional (DU-WM-6).
  - Topes: enteros > 0, en bytes en la API. La pantalla los muestra en MB (1 MB = 1 000 000 bytes). Un tope ≤ 0 lo rechaza la validación del modelo (422 genérico), porque la pantalla no deja escribirlo.
  - Segmentos (RF-WM-20): sin superposición, sin huecos y cubriendo todos los días; el primero sin piso y el último sin tope. Los segmentos son fijos, los 3 de S-WM-1: se editan su etiqueta y sus límites, pero no se agregan ni se quitan. Un PUT con otras claves es un 422 genérico. `segmento_de(dias_ajustados)` devuelve el segmento. Los días ajustados se calculan con la función común de RF-55 (`core/services/segmentacion.py`, `dias_ajustados`), sin copiarla.
- **Migración:**
  - Tablas `whatsmkt_configuracion` (una sola fila con `id` fijo, como `mowa_mes_configuracion`), `whatsmkt_segmento` y `whatsmkt_adjunto` (`huella` UNIQUE, `contenido` LargeBinary).
  - Siembra la configuración por defecto y los 3 segmentos de S-WM-1: `preventivo` (≤ 0), `tramo_2` (1 a 8) y `mayores_2` (≥ 9).
  - `downgrade` completo.
- **Repositorio:** puerto `RepositorioWhatsmktPort` en `core/ports/` y adaptador `RepositorioWhatsmktPostgres`, con:
  - leer y guardar la configuración;
  - leer y reemplazar los segmentos en una transacción;
  - adjuntos: guardar sin repetir (si la huella existe, devuelve el existente), listar sin contenido (activos o archivados), leer el contenido, y archivar o desarchivar.
- **API** (`api/whatsmkt.py`), para que F1 pueda empezar:
  - `GET /whatsmkt/configuracion` y `PUT /whatsmkt/configuracion`. El PUT es parcial, con la regla de MOWA (B7): un campo omitido se conserva y un `null` en un campo no nulo responde 422.
  - `GET /whatsmkt/segmentos` y `PUT /whatsmkt/segmentos`. El PUT reemplaza la etiqueta y los límites de los 3 segmentos en una transacción y responde 422 con código si los segmentos se superponen o dejan huecos.
  - Los endpoints de adjuntos van en B5. B1 deja solo el repositorio.
- **Códigos:** el enum `CodigoWhatsmkt` nace con los 27 (§1). B1 emite `horario_invalido`, `variable_inexistente`, `segmentos_superpuestos` y `segmentos_con_hueco`. Los paneles de configuración de `whatsmkt-interfaz.md` §5 se guardan por separado: el PUT parcial de la configuración sirve a los paneles 3 a 6, y el PUT de segmentos, a la tabla del panel 1. Los mensajes (paneles 1 y 2) son de B3 y la biblioteca (panel 7), de B5.
- **Pruebas:**
  - Unitarias: horarios (bordes, inicio = fin); plantilla (variables válidas, desconocidas, sin variables); segmentos (cobertura con huecos y con superposición, `segmento_de` en −5, 0, 1, 8, 9 y 500, y un PUT con claves distintas de las 3).
  - API: 200 y 422 con su código, el PUT parcial (campo omitido, `null` prohibido) y el contrato contra `openapi.json`.
  - `@postgres`, las corre architec: ida y vuelta de la migración más `alembic check`, la siembra, el reemplazo de segmentos atómico y el adjunto repetido por huella.
- **Listo cuando:** contrato publicado, ruff limpio, pytest sin base en verde y la entrega con las capas corridas y las que faltan.

### B2 — Archivo de contactos (T-WM-B2)

**RF:** RF-WM-09 a RF-WM-16. **Depende de:** B1, T-HI-B1, T-HI-B2 y T-HI-B3.

- Registra las reglas de plataforma `whatsmkt` en el registro de RF-72 (RF-WM-10 y 11):
  - la 1.ª columna es `número`, fija, con `51[@telefono]` y celda de texto (RF-73);
  - las demás son `[$MARCROn$]` por posición, renumeradas al reordenar y de tipo texto.
- Chequeo de que `definicion_defecto_id` sea de plataforma `whatsmkt`, con el código `definicion_no_whatsmkt`.
- Armado con `GeneracionCargasService` sobre la selección congelada:
  - una fila por producto;
  - los supervisores primero, con las macros de la primera fila;
  - las exclusiones `sin_telefono`, `telefono_invalido` y `macro_vacia`, esta última solo si la columna no tiene valor por defecto;
  - el reparto por segmento.
- **Pruebas:**
  - Unitarias de las reglas de plataforma: número primero, renumeración, todo texto.
  - Unitarias de las exclusiones, con orden y un solo código por producto; de los supervisores en un lote (la primera fila de cada archivo); y del reparto.
  - Adaptador: el `.xlsx` leído de vuelta, con `número` en formato `@` y las macros como texto.
  - Regresión: la prueba de oro de MOWA y la de RF-54 no cambian.

### B3 — Mensaje (T-WM-B3)

**RF:** RF-WM-17 a RF-WM-27. **Depende de:** B2 y T-HI-B4.

- Registra el contexto `whatsmkt.mensaje` (texto plano) en RF-69, con sus validadores:
  - sin emojis (RF-WM-24): una lista explícita de rangos, ZWJ y selectores de variante, devolviendo la posición del primero;
  - macros contra la definición (RF-WM-25);
  - tope de largo sobre el texto con los marcadores (RF-WM-26, DU-WM-3).
- Migración:
  - `whatsmkt_segmento.texto_guardado_id`, con FK a `texto_guardado`;
  - siembra de los 3 speeches de RF-WM-21 como versión 1, textuales, con los espacios dobles (DU-WM-2).
- Vista previa: reemplaza `[$MACROn$]` con los valores de las primeras filas.
- **Pruebas:**
  - Emojis frente a tildes, `ñ`, `ü`, `¿`, `¡`, `©` y `✓` (R-4).
  - Macro inexistente; tope exacto y tope + 1.
  - Siembra byte a byte frente a RF-WM-21.
  - `@postgres` de la migración.

### B4 — Programación, campaña y ficha (T-WM-B4)

**RF:** RF-WM-05, 06, 07, 08, 22, 23 y 33 a 36. **Depende de:** B3 y T-HI-B5.

- Migración de `whatsmkt_campana` (con su lote), `whatsmkt_archivo`, `whatsmkt_fila_cargada` (las macros en JSONB) y `whatsmkt_exclusion`. Las FK van a la versión de la definición y a la versión del texto guardado.
- `GET /whatsmkt/programacion` devuelve la fecha sugerida, la mínima y las próximas, de RF-70 y RF-71.
- `POST /whatsmkt/campanas/previsualizacion`.
- `POST /whatsmkt/campanas` crea el lote completo o nada. Responde 409 si la fecha ya no vale, con la nueva sugerida.
- `GET /whatsmkt/campanas`, `GET /whatsmkt/campanas/{id}` y `GET /whatsmkt/campanas/{id}/archivo`.
- Nombre de la campaña:
  - hasta 75 caracteres;
  - si el lote tiene más de una campaña y la plantilla no usa `{segmento}`, se agrega el segmento al final (DU-WM-6);
  - el nombre del archivo es el de la campaña más `.xlsx`, sin los caracteres que Windows no admite (DU-WM-10).
- La ficha (RF-WM-36) se arma con los datos guardados.
- **Pruebas:**
  - Medianoche de Lima frente a UTC, sábado válido y domingo no, feriado.
  - El lote atómico: si falla una campaña, no queda ninguna.
  - El 409 de fecha y el nombre de 75 y 76 caracteres.
  - Descarga byte a byte después de cambiar la configuración.
  - `@postgres`.

### B5 — Adjuntos (T-WM-B5)

**RF:** RF-WM-28 a RF-WM-32. **Depende de:** B1. Puede ir en paralelo con B2 a B4.

- Tipo por firma, y tamaño controlado antes de leer.
- Foto: JPEG de 200 × 200, leído del marcador SOF, de hasta 1 MB. Es opcional en la campaña (DU-WM-5).
- Limpieza sin recodificar:
  - JPEG: se quitan APP1, APP13 y COM, y se conserva APP2;
  - PNG: se quitan los bloques de texto, `eXIf` y `tIME`.
- Rechazo de un archivo truncado.
- `POST /whatsmkt/adjuntos` (multipart), `GET /whatsmkt/adjuntos`, `GET /whatsmkt/adjuntos/{id}/contenido` y `POST /whatsmkt/adjuntos/{id}/archivar` y `/desarchivar`.
- **Pruebas:**
  - JPEG y PNG sintéticos: los datos de la imagen y el perfil de color quedan byte a byte.
  - Los límites de tamaño: tope y tope + 1.
  - Una extensión que miente, un archivo truncado y la huella repetida.

### B6 — Informe, conciliación y descartar (T-WM-B6)

**RF:** RF-WM-37 a RF-WM-42. **Depende de:** B4.

- Migración de `whatsmkt_reporte` y `whatsmkt_reporte_fila`, más `descartada_en` en la campaña si B4 no lo creó.
- Lector del «Informe» sobre el lector de tablas común:
  - encuentra las filas `FECHA` y `TOTAL DE ENVIO` y los encabezados;
  - ignora las filas vacías;
  - si el total no coincide con las filas, devuelve los dos valores sin rechazar (DU-WM-7).
- `POST /whatsmkt/campanas/{id}/reportes`: responde 201, o 409 si ya hay un informe y no se pidió `reemplazar=true`. Si la campaña está descartada, responde con `campana_descartada`.
- `GET /whatsmkt/campanas/{id}/conciliacion`: por conjuntos de número, a nivel de producto, con los supervisores aparte.
- Descartar, restaurar y eliminar, como RF-MM-31 y 32.
- **Pruebas:**
  - Lector con informes sintéticos: filas vacías, TOTAL distinto y encabezado faltante.
  - Conciliación: un número con 2 productos, números sin correspondencia, el orden distinto al de la carga y los supervisores.
  - El 409 y el reemplazo.
  - `@postgres`.

## 4. Cortes del frontend

Esperan el contrato publicado del corte de backend del que dependen y las reglas de interfaz de `designer`.

| Corte | RF | Depende de | Pruebas |
|---|---|---|---|
| F1 — Navegación y configuración | RF-WM-02 a 04, 20 y 30 (lista) | B1 y T-HI-F2 | Vitest de los formularios y los espejos i18n; Playwright del menú desplegable y la configuración, con reloj fijo y axe a 1280 y 360 px en claro y oscuro |
| F2 — Campaña | RF-WM-05 a 36 | B2 a B5 y T-HI-F1 | Vitest de los campos condicionales y del editor con etiquetas; Playwright del flujo completo con la API falsa, ir y volver al constructor y el lote por segmento; una pasada con `TZ=Pacific/Kiritimati` |
| F3 — Seguimiento | RF-WM-37 a 44 | B6 | Vitest de la conciliación; Playwright de importar, reemplazar, descartar y restaurar; tablas apilables a 360 px |

## 5. Cierre (T-WM-C1)

Revisión RF por RF contra `requerimientos-whatsmkt.md`, con las respuestas a las DU-WM incorporadas, y aceptación con los datos del 29.10 en la máquina de `architec`, según los criterios del plan v2 §8.
