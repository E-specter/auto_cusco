# Plan de F5: pantalla «Generar carga» (`/generar-carga`)

Propuesta del 2026-10-16 de `dev_frontend_motor_texto_enriquecido` para `designer` (aprobación) y `coordinador_motor_texto_enriquecido`. Hecha sobre `ba9de60`, **sin código de producto**: nada se programa hasta que `designer` apruebe este plan. Fuentes: `docs/generacion-cargas.md`, `backend/app/api/archivos_carga.py` (HEAD y el worktree de B12, solo lectura), `src/scripts/selector-seleccion.ts`, `src/lib/seleccion.ts`, `src/lib/descargas.ts`, `src/lib/api-definiciones.ts`, `plan.md` del coordinador §22.

## 0. Reglas de trabajo (sin cambios)

- Worktree propio (`auto_cusco_mte_f5`, rama `mte-f5`), sin commit; entrego lista de archivos y capas corridas/no corridas al coordinador. Playwright completo lo corre architec.
- No toco `ui.css`, `navegacion.ts`, `nav.*`, `Shell` ni componentes compartidos: lo pido a `designer`. Estilos propios en `src/styles/generar.css`; i18n en un bloque contiguo `generar.*` al final de `es.json`/`en.json`.
- El frontend no valida ni evalúa nada: filas, errores, exclusiones y totales salen del backend.
- Datos sintéticos siempre.

## 1. Verificación del contrato (lo que me pidió el coordinador)

| Pregunta | Resultado |
|---|---|
| ¿Los filtros y el orden de `SelectorSeleccion` encajan con `PeticionGeneracion.filtros: list[str]` y `orden: str`? | **Sí, tal cual.** `EstadoSeleccion.consulta.filtros` son `campo:operador:valor` y `orden` es `campo`/`-campo` (`escribirFiltro`/`escribirOrden`), la misma sintaxis que `/cartera` (`generacion-cargas.md` §2). Se envían sin transformar. `consulta.indicadores` no se envía (no aplica a una carga) |
| ¿`/archivos-carga` acepta una selección guardada? | **No acepta `seleccion_id` y no hace falta.** El selector ya resuelve la guardada a `filtros`/`orden`/`cantidad` en `estado().consulta`; esa consulta viaja en el cuerpo. Una selección guardada borrada o editada después no cambia lo ya pedido. **Sin cambio de contrato** |
| `consulta.cantidad` vs `PeticionGeneracion.cantidad` | **Desajuste de semántica, sin cambio de contrato.** En la selección `cantidad` es el «top n» y puede ser `null` (todo el universo); en la petición es obligatoria (`1..120 000`, por defecto 1 000). La pantalla tiene **su propio campo «Cantidad a generar»**, precargado con `consulta.cantidad` si existe y, si no, con 1 000; se vuelve a precargar solo si el usuario no lo tocó y cambia la selección. Tope 120 000 (`CANTIDAD_MAXIMA` de `seleccion.ts`). No se envía nada más que lo que el usuario ve |
| Definición | Siempre `definicion_guardada: {id, version?}` (de `/definiciones-columnas`). La definición en línea no se usa en la pantalla. `proteger_formulas` lo toma el backend de la definición: la pantalla solo lo **muestra** (solo lectura) y no lo envía |
| Opciones del archivo | Solo las que dice `GET /archivos-carga/formatos` para el formato elegido (`opciones: ["delimitador", ...]`). Ver faltante G-2 |
| Errores de la petición | `400` (filtro/orden/plantilla), `404` (`definicion_no_encontrada`, `version_no_encontrada`, `sin_version_vigente`, fecha sin versión vigente) con `codigo` y `detail`; `422` no debería ocurrir porque el formulario limita rangos. Se muestran con el catálogo de códigos ya existente (`mensajeDeProblema`) |

### Faltantes para B12 (para que el coordinador los sume o los descarte)

- **G-1 (B12 ya lo cubre; decisión del coordinador 2026-10-16):** `excluidos` y `exclusiones` en `/previsualizacion` y `X-Carga-Excluidos` en la descarga están en el worktree de B12. Con ellos la pantalla puede mostrar «N productos salen / M no salen (sin segmento)». Necesito que el **`openapi.json` de B12 esté en main antes de F5**, porque mis tipos se generan de ahí. **Sin tipos locales:** programo primero lo que no depende de B12 (estado puro, cliente, formulario, descarga) y la parte de exclusiones espera a B12 en main.
- **G-2 (sumado a B12 por el coordinador):** `GET /archivos-carga/formatos` solo da los **nombres** de las opciones, no sus valores permitidos ni sus valores por defecto. Para `codificacion` (utf-8, utf-8-sig, latin-1…) y el `delimitador` el frontend tendría que fijar una lista a mano, y eso es una regla de plataforma que el backend ya conoce. Propongo que `FormatoRespuesta.opciones` pase a objetos `{nombre, defecto, valores?}`. El backend dará por opción el tipo, el valor por defecto y los valores permitidos donde la lista es cerrada. **El frontend no fija listas propias** de codificaciones ni delimitadores: arma los controles desde `/formatos`. Hasta que B12 esté en main, el formulario de opciones espera.
- **G-3 (pregunta):** la descarga tarda hasta ~40 s con 120 000 filas y 45 columnas en XLSX (`generacion-cargas.md` §4). `api.ts` no tiene tiempo de espera, así que la pantalla muestra «Generando…» sin tope y con botón de cancelar (`AbortController`). Pregunto si el backend cancela el trabajo cuando se corta la conexión; si no, lo documento como límite conocido (el servidor termina igual y marca la versión como `usada_en`).
- **G-4 (pregunta):** la descarga marca la versión de la definición como usada (`marcar_usada`). Si el usuario cancela a medias, ¿puede quedar marcada sin que haya recibido el archivo? Lo trato como límite conocido igual que G-3.

## 2. Ruta y estructura

Ruta `/generar-carga` (archivo `src/pages/generar-carga.astro`). Entrada de navegación «Generar carga» en «Flujo diario» (Cargas · Cartera · **Generar carga**): la agrega `designer`, yo no toco `nav.*` ni `navegacion.ts`.

```
Shell
 └ <h1> Generar carga
   <p class="lead">  «Cargas» es lo que entra (las sábanas diarias); «Generar carga» es el archivo que sale hacia una plataforma.
   .notice (offline / sin definiciones)
   1. Selección                 SelectorSeleccion modo="compacto" id="seleccion"
   2. Definición                .panel: select de definiciones guardadas · select de versión (vigente por defecto) ·
                                 resumen de solo lectura (n.º de columnas, segmentada sí/no, proteger fórmulas sí/no) ·
                                 enlace «Editar en Columnas» a /columnas
   3. Archivo                   .panel: formato (radio) · cantidad a generar · opciones del formato
   4. Resumen y vista previa    .panel: totales (disponibles / pedidos / saldrán / excluidos) · .notice de suficiencia ·
                                 .table con la muestra (hasta 20 filas) · lista única de problemas (§9.4)
   5. Generar                   botón primario «Generar y descargar» · estado de la última descarga
```

Es una **sola columna** que baja en el orden del recorrido; a 360 px no cambia. La vista previa se calcula sola (con espera de 600 ms como el selector) cuando los cuatro insumos están completos y válidos; el botón de generar depende de la misma condición.

### 2.1 Qué es mío y qué es de designer

| Mío | De designer |
|---|---|
| `generar.astro`, `generar.css`, `src/lib/generar-carga.ts` (estado puro), `src/lib/api-archivos-carga.ts`, `e2e/api-falsa-archivos-carga.ts`, `e2e/generar.spec.ts`, bloque `generar.*` de i18n | `SelectorSeleccion`, `ui.css` (`.panel`, `.notice`, `.table`, `.table__detalle`, `.btn`), `Shell`, `nav.*`, `descargas.ts` (lo uso, no lo cambio) |

## 3. Estado puro (`src/lib/generar-carga.ts`)

Sin DOM, sin red. Un `Borrador` (`seleccion`, `definicionId`, `version`, `formato`, `cantidad`, `cantidadTocada`, `opciones`) y funciones:

- `peticionDe(borrador): PeticionGeneracion | null` — `null` mientras falte fecha, definición o algo no sea válido. `filtros`/`orden` van directos de la consulta, `cantidad` es la del campo, `definicion_guardada` con `version` solo si el usuario eligió una que no es la vigente.
- `cantidadInicial(consulta)` y `cantidadValida(texto)` — entero `1..120 000`.
- `opcionesDeFormato(formato, formatos)` y `opcionesAEntrada(...)` (con el contrato de B12) — solo las opciones que el formato admite, con tipo, defecto y valores permitidos tal como los dé `/formatos` (B12). Sin reglas de plataforma propias: ni `hoja` ni `sangria` se validan en el frontend (ver §13).
- `resumenDeCarga(prev | cabeceras)` — `{disponibles, solicitados, generados, excluidos, suficiente}` desde la previsualización o desde las cabeceras `X-Carga-*`. **Un solo lector** para las dos fuentes (`cabecerasConPrefijo(..., 'X-Carga-')` ya entrega las claves en minúscula).
- `mensajeSuficiencia(resumen)` — qué `.notice` toca: «Hay 3 200 productos; se pidieron 5 000, saldrán 3 200» (`suficiente=false`), o «salen N, no salen M» (`excluidos > 0`).
- `problemasUnicos(prev)` — fusiona `errores` y `exclusiones` en **una** lista de problemas con su fila, pagaré y motivo (§9.4 del diseño); agrupa por `codigo` cuando hay más de 5 del mismo.
- `nombreDeArchivoLocal(...)` solo como respaldo si el servidor no envía `Content-Disposition`.

## 4. Estados de la pantalla

| Estado | Qué se ve |
|---|---|
| Cargando | Esqueleto de los paneles; el selector se monta después de suscribirse a `seleccioncambiada` |
| Offline / API caída | `.notice` con «Reintentar»; contenido oculto (igual que `/cartera`) |
| Sin definiciones guardadas | `.notice` con enlace a `/columnas`; el botón de generar queda inactivo |
| Sin fecha o selección no aplicable (`aplicable=false`) | Aviso en el panel 4; sin llamadas |
| Incompleto | Botón inactivo con la razón en texto (no solo desactivado) |
| Calculando vista previa | `aria-busy` en el panel 4; cifras atenuadas |
| Vista previa lista | Totales, aviso de suficiencia, tabla de 20 filas, problemas |
| Vista previa con errores | Tabla igual; lista de problemas expandida. **No bloquea** descargar (el backend entrega lo que pudo y `completa` lo dice) |
| Generando | Botón con `data-loading`, texto «Generando…», botón «Cancelar»; el resto del formulario bloqueado |
| Generado | `.notice` de éxito con nombre del archivo, filas generadas/excluidas y un recordatorio «la versión N de la definición queda marcada como usada» |
| Error de generación | `.notice` de error con el código del catálogo; lo escrito se conserva |

## 5. Interacción y accesibilidad

- Un solo `h1`; cada panel con `aria-labelledby`; el estado de la vista previa en `aria-live="polite"` (una sola región, texto corto).
- Orden de tabulación = orden visual. El foco, tras un error de generación, va al `.notice` (con `tabindex="-1"`); tras generar, se queda en el botón.
- La tabla de la vista previa usa `.table` con `<caption>` visible; a 360 px, desplazamiento horizontal dentro de su contenedor (sin scroll de página). Las filas excluidas/erróneas llevan icono **y** texto.
- Radio de formato con `fieldset/legend`; las opciones que no aplican se **ocultan** (no solo se desactivan).
- Cambios de definición/versión/formato no pierden lo escrito en los demás campos.

## 6. Escenarios de Playwright (API falsa `e2e/api-falsa-archivos-carga.ts`)

La API falsa responde `/archivos-carga/formatos`, `/archivos-carga/previsualizacion` (según el cuerpo recibido, para poder afirmar lo que se envió), `/archivos-carga` (blob + cabeceras `X-Carga-*`) y reutiliza `manejadorDefiniciones` y la base de `api-falsa.ts` (campos, versiones, selecciones). Guardo los cuerpos recibidos para comparar.

1. Carga inicial: título, párrafo «Cargas vs Generar carga», selector compacto montado una sola vez, sin llamadas de previsualización hasta tener definición.
2. Sin definiciones guardadas: aviso con enlace a `/columnas`, botón inactivo con razón.
3. Elegir definición: resumen de solo lectura (columnas, segmentada, proteger fórmulas); la versión vigente viene elegida.
4. Elegir una versión no vigente: el cuerpo lleva `definicion_guardada.version`; con la vigente, no la lleva.
5. Selección guardada con filtros y orden: el cuerpo de la previsualización lleva `filtros`/`orden` exactos del selector (sin indicadores).
6. Cantidad: se precarga con la de la selección; sin cantidad en la selección, 1 000; editarla la marca como «tocada» y un cambio de selección ya no la pisa; 0, 120 001 y texto → error visible y botón inactivo; 120 000 pasa.
7. Formato CSV: aparecen delimitador, codificación y cabeceras; XLSX: hoja y cabeceras; JSON: codificación y sangría. Cambiar de formato oculta las otras. El cuerpo lleva solo las opciones del formato.
8. Vista previa: 20 filas, totales y aviso de `suficiente=false` («se pidieron N, hay M»); con `suficiente=true` sin exclusiones, sin aviso.
9. Exclusiones (B12): `excluidos > 0` → «salen X, no salen Y»; la lista muestra pagaré, fila y motivo con el texto del catálogo; con > 5 del mismo código, agrupa.
10. Errores de campos: una sola lista de problemas (errores + exclusiones), orden por fila; descargar sigue habilitado.
11. Generar: se hace `POST /archivos-carga`, se dispara una descarga con el nombre del `Content-Disposition` (`page.waitForEvent('download')`), el resumen sale de las cabeceras y coincide con la previsualización; se muestra el aviso de versión usada.
12. Cancelar mientras se genera: la llamada se aborta, el formulario vuelve a quedar editable, sin aviso de éxito.
13. Error 404 `sin_version_vigente`, `definicion_no_encontrada`, `version_no_encontrada` y 400 de filtro mal escrito → mensaje del catálogo; lo escrito se conserva.
14. API caída al arrancar → offline + reintentar recupera; caída durante la previsualización → aviso sin perder el formulario.
15. Respuestas fuera de orden: dos previsualizaciones seguidas, la lenta no pisa a la rápida (último cambio gana).
16. Selección con `aplicable=false` → sin llamadas y con aviso.
17. Cambiar la fecha de corte recalcula una sola vez (sin ráfaga).
18. Teclado: recorrido completo hasta «Generar» sin ratón.

Estimación: 22–26 pruebas.

## 7. Vitest (`tests/nucleo/generar-carga.test.ts`, `api-archivos-carga.test.ts`)

`peticionDe` (todas las ramas: sin fecha, sin definición, versión vigente vs explícita, cantidad inválida), `cantidadInicial`/`cantidadValida` (bordes 0, 1, 120 000, 120 001, decimales, texto), `opcionesDeFormato` por formato, `resumenDeCarga` desde cuerpo y desde cabeceras (mismos números), `mensajeSuficiencia`, `problemasUnicos` (orden, agrupación, vacío), y el cliente: cuerpo exacto, `AbortSignal`, errores `ApiError`/`NetworkError`. Una prueba de lectura de fuente para que el módulo no declare `interface` donde use el contrato (índice `extra="allow"`).

## 8. axe

`generar` en tema claro y oscuro y a 360 px, en tres estados: inicial con definición, con vista previa con problemas y generado. Se agrega a `e2e/accesibilidad.spec.ts` (archivo de designer: aviso antes de tocarlo).

## 9. Verificación y mutaciones

`npm run tipos`, Vitest (`nucleo`), `astro check` y el spec de la pantalla; Playwright completo lo corre architec. Mutaciones a mano, en el worktree: enviar `indicadores`, omitir `version` explícita, no limitar cantidad, enviar opciones de otro formato, leer el resumen solo de la previsualización, bloquear la descarga por errores, no abortar al cancelar, no ignorar la respuesta vieja, perder la cantidad tocada al cambiar la selección.

## 10. Riesgos

| Riesgo | Mitigación |
|---|---|
| B12 aún no está en main (tipos de `excluidos`/`exclusiones` y opciones de `/formatos`) | G-1/G-2: sin tipos locales; programo antes lo que no depende de B12 y dejo exclusiones y opciones para después |
| Descargas largas sin tope | G-3 + cancelar + estado visible |
| Doble clic en «Generar» | Botón bloqueado y `AbortController` único por generación |
| Dos vistas previas en vuelo | Se descarta la respuesta si ya no es la última petición |
| Selector compacto no expone `cantidad` editable | Campo propio (§1); se confirma con designer que no se quiere editor completo aquí |

## 11. Lo que pido a designer (aprobación y dudas)

- **D-1:** ¿La ruta es `/generar-carga` y el rótulo «Generar carga»? ¿Entrada de nav al final de «Flujo diario»?
- **D-2:** ¿Aprueba la **sola columna** con cinco paneles y el botón de generar al final (sin barra pegajosa)?
- **D-3:** ¿Aprueba el campo propio «Cantidad a generar» en lugar de exigir que la selección traiga `cantidad` (como hace la campaña de MOWA MES)? Mi recomendación: campo propio.
- **D-4:** ¿Hay patrón de `.notice` de éxito con acción (no existe uno en `ui.css`)? Si no, uso `.notice` informativo.
- **D-5:** ¿Qué patrón se usa para «Cancelar» durante una operación larga (botón secundario junto al principal)? Propongo botón secundario `.btn--ghost` al lado.
- **D-6:** Texto del párrafo introductorio: «Cargas» (sábanas que entran) vs «Generar carga» (archivo que sale). ¿Lo redacta usted o lo propongo en `generar.intro`?

## 12. Orden de trabajo una vez aprobado

1. F5-a: `generar-carga.ts` + Vitest (sin pantalla), lo que no depende de B12.
2. F5-b: cliente `api-archivos-carga.ts` y API falsa; exclusiones y opciones de `/formatos` cuando B12 esté en main.
3. F5-c: pantalla, i18n, estilos y escenarios; axe.
4. Entrega al coordinador con lista de archivos y capas corridas/no corridas.

## 13. Ajustes aprobados por `designer` (2026-10-16): el plan queda aprobado con esto

Manda sobre lo anterior si hay conflicto.

- **Ruta `/generar-carga`** (no `/generar`). La entrada de nav la agrega designer cuando la página exista. Todo texto visible va en i18n; el rótulo «Cargas»/«Generar carga» puede cambiar por decisión del usuario.
- **Resumen junto al botón**, en texto: «Se generarán N filas en XLSX con la versión 4 de "SMS preventivo"». Si el botón está inactivo, su motivo va en texto.
- **Cantidad:** hint «Toma la cantidad de la selección hasta que la cambies»; tras editarla, «Ya no sigue a la selección». El tope de 120 000 se dice en el hint.
- **Éxito:** `.notice--success` (existe), sin acción: nombre del archivo, filas generadas y excluidas, y que la versión N queda marcada como usada.
- **Cancelar:** botón `.btn` (no existe `.btn--ghost`) junto al primario; el primario con `data-loading` y `btn__spinner`. **Foco:** al empezar la generación va a «Cancelar»; al terminar o cancelar vuelve a «Generar y descargar» (se suma al escenario 12). Aviso de cancelación en `.notice--info`, sin prometer: «Se canceló la descarga. Si el servidor alcanzó a generarla, la versión N puede figurar como usada».
- **Intro (`generar.intro`):** una frase; h1 y párrafo con una clase propia de `generar.css` (`.generar__intro`), sin eyebrow y sin `.lead`.
- **Hoja de XLSX y demás reglas de plataforma:** el frontend **no** valida `hoja` (≤ 31, `[]:*?/\`); si el backend la rechaza con campo y código, se muestra bajo su campo. Se quita de `opcionesDeFormato` y de Vitest. Codificaciones/delimitadores solo desde `/formatos` de B12; si no llega a tiempo, la lista provisoria la aprueba el usuario vía el coordinador.
- **Formato:** `.segmented` con `aria-pressed` (como «Muestra» en F3), no fieldset de radios.
- **Enlace del panel de definición:** «Editar en Columnas de carga».
- **Tabla de vista previa:** en `.table-scroll` y `observarDesplazables` (`desplazables.ts`) para `scrollable-region-focusable` a 360 px.
- **Grupos de más de 5 problemas del mismo código:** el grupo dice cuántos son y se despliega con botón `aria-expanded`.
- **axe:** casos propios en un `describe` al final de `accesibilidad.spec.ts`, sin tocar los existentes; aviso a designer al hacerlo.
- Revisión de experiencia de designer, con capturas, antes del commit.

## 14. Límites conocidos de la generación (respuesta del dev backend, comprobada con servidor real, 2026-10-16)

- **G-3: Cancelar no detiene al servidor.** `POST /archivos-carga` corre entero en un hilo; cerrar la conexión no lo corta y sigue hasta terminar (unos 40 s en el peor caso). **Cancelar solo libera la pantalla.** Varias cancelaciones y reintentos seguidos acumulan trabajo en el servidor.
- **G-4: `usada_en` puede quedar marcada sin que el usuario reciba el archivo.** Se marca después de generar y exportar bien, pero antes de enviar el cuerpo. Si la generación falla (400/404) no se marca. La previsualización nunca marca.
- **Mitigación en la interfaz, sin lógica de negocio:**
  - Mientras haya una generación en curso desde la pantalla no se puede lanzar otra (el primario queda inactivo; ya lo exige el `AbortController` único).
  - Tras Cancelar, un `.notice--info` breve: «Se canceló la descarga. La generación cancelada puede seguir procesándose unos segundos en el servidor y, si alcanzó a terminar, la versión N puede figurar como usada». Sin prometer nada más. El texto lo revisa designer.
  - El frontend **no deduce** si la versión quedó marcada ni vuelve a consultarlo.
- **Pregunta abierta para designer/coordinador:** tras Cancelar el servidor sigue trabajando, pero la pantalla no tiene forma de saber cuándo termina. Dejo el botón primario habilitado tras cancelar (el aviso advierte del trabajo pendiente) y no invento un enfriamiento; si se quiere uno, que lo fije el coordinador.

## 15. Opciones del formato (indicación de designer vía coordinador, 2026-10-16; manda sobre lo anterior)

- Los controles de texto con `sugeridos` usan `crearSelectorPatronFecha` (`src/scripts/selector-patron-fecha.ts`) con `opciones` = sugeridos, `cerradas: false` y `marcas: []`: un select con los sugeridos más «Personalizado», que abre un campo. **No** se arma un selector propio y **no** se usa `datalist`.
- `defecto` viene elegido; un valor que no está entre los sugeridos abre «Personalizado» con ese valor.
- `minimo`/`maximo` van en el hint («Un solo carácter», «De 0 a 8 espacios») y como atributo nativo del campo propio cuando corresponde (`maxlength` en el delimitador, `inputmode="numeric"` en la sangría). **No se valida en el frontend**: si el backend rechaza el valor, el error va bajo su campo (los 400 de exportación sin campo van en un aviso del panel «Archivo»).
- Delimitador con nombres visibles («coma», «punto y coma», «tabulación», «barra vertical») y el carácter al lado cuando se ve: designer agrega una `etiqueta` opcional por opción en su selector; las claves van en mi bloque `generar.delimitador.*`. Avisar a designer al llegar a F5-c.
- La codificación se muestra tal cual (`utf-8`, `latin-1`…), más «Personalizado».
