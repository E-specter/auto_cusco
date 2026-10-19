# Plan de F3 y F4 (frontend del motor de texto enriquecido)

Propuesta del 2026-10-01 de `dev_frontend_motor_texto_enriquecido` para `coordinador_motor_texto_enriquecido`. Hecha sobre HEAD `2f0b3b3`, **sin código de producto**: nada de esto se implementa hasta que B4a, B4b, B6 y F2 estén entregados. Fuentes: `motor-texto-enriquecido-interfaz.md` (§2, §3, §4, §5, §5.6, §7, §8), `motor-texto-enriquecido.md` (§4 a §10, §20), `plan.md` del coordinador (§6, §7, §12, §13), `frontend/src/lib/expresion.ts` (designer, `5ffeddf`), las entidades `CampoSalida`, `DefinicionCarga` y `Segmentacion` del backend, y el código actual de `/mowa-mes/configuracion`.

Las dudas para `designer` están aparte, en [dudas-designer.md](dudas-designer.md). Las preguntas de contrato para el coordinador y el backend están en la sección 6 de este documento.

## 0. Lo que no cambia (reglas de trabajo)

- No se commitea. Se entrega al coordinador la lista de archivos tocados y las capas corridas y no corridas.
- Verificación en worktree desde HEAD con `$env:PLAYWRIGHT_PUERTO` propio: `npm run verificar` (contrato, `astro check`, build, Vitest, Playwright). Playwright corre contra una API falsa; **no hay backend ni base** en el frontend.
- Claves i18n nuevas en bloques contiguos al final de `es.json` y `en.json`, sin reformatear lo ajeno: `textoEnriquecido.*` es de `designer` (F2); lo mío va aparte, en `columnas.*` (F3) y `mowaMes.speech.v2.*` (F4). Ver duda D-7.
- Lo que toque archivos compartidos (`ui.css`, `format.ts`, `api.ts`, `navegacion.ts`, `Navegacion.astro`, `Shell.astro`, componentes compartidos) se le pide a `designer`. Estilos propios en `src/styles/columnas.css` y, para F4, en `mowa-mes.css`.
- El frontend no evalúa funciones ni valida reglas de negocio ni recalcula el largo (interfaz §1.2). Todo lo que muestre sale del catálogo, la validación y la previsualización del backend.
- F4 toca MOWA MES: pasa **con su worktree** por la revisión de `coordinador_modulo_mowa_mes` antes de ir a architec (`plan.md` §13).
- Datos sintéticos siempre (`900000xxx`, titulares `ZZPRUEBA…`). Nada de datos reales en pruebas ni ejemplos.

## 1. Dependencias y orden

| Corte | Espera | Qué necesito para empezar |
|---|---|---|
| F3-a, estado puro (`src/lib/constructor-columnas.ts`) | nada | Tipos provisionales tomados de `entities/mapeo.py` y `entities/segmentacion.py`. **Puede empezar ya** |
| F3-b, cliente y tipos de definiciones | B4b | Forma exacta de `/definiciones-columnas` en `openapi.json` |
| F3-c, pantalla | B4b y F2 | `EditorTexto`, `VariantesSegmento`, `api-texto-enriquecido.ts` y las claves `textoEnriquecido.*` de designer |
| F4 | B6 y F2 | Contrato de versiones v2 en `/mowa-mes/speech`, el cliente del motor y el editor |

Hasta que lleguen B4a y F2 no hay API falsa del motor. La del constructor se arma en F3 sobre la que escriba `designer` (duda D-2).

## 2. F3: pantalla del constructor de columnas

### 2.1 Ruta y estructura

- Ruta propuesta por el coordinador: `/columnas`, título visible «Columnas de carga». Archivo: `src/pages/columnas.astro`. La entrada de navegación (`navegacion.ts`, `Navegacion.astro`, claves `nav.*`) la pide yo a `designer`, con copia al coordinador (duda D-5).
- Es una pantalla operativa que **scrollea** (como `/mowa-mes/*`): no se bloquea a `100dvh`. Usa los tokens, `.panel`, `.table--apilable-ancha`, `.notice`, `.tag`, `.field`, `.btn`, sin radios ni hex nuevos. El markup que arma el script va en una hoja global propia (`columnas.css`), como `mowa-mes.css` (DESIGN.md, «Why console.css is global»).

```
Eyebrow · Cargas                      (provisional)
H1  Columnas de carga
Intro                                  
[ aviso sin conexión ]  (data-offline)

Panel «Definición»
  [Definición ▾]  [+ Nueva definición]            ← lista de guardadas
  Nombre  [..............]   Versión 3 · usada en 2 cargas
  ▸ Segmentación (colapsable, cerrada si no hay variantes)
        Criterio ▾ · tabla de rangos (solo lectura) · sin segmento (radio)
  [x] Proteger fórmulas en CSV  (hint largo de interfaz §5.1)

Panel «Columnas»
  .notice--danger  resumen de problemas   (cuando hay)
  .table  # | Nombre | Tipo | Contenido | Formato | Por defecto | Acciones
        fila expandida (una a la vez, aria-expanded en Editar)
          Contenido: ( ) Variable directa  ( ) Texto compuesto → EditorTexto
          Formato según tipo
          [x] Variar por segmento → VariantesSegmento
  [+ Agregar columna]

Panel «Vista previa»
  Muestra: (•) Ejemplos por segmento  ( ) Cartera real  [SelectorSeleccion compacto]
  tabla: una columna por columna definida + segmento

Pie: hint de versión · [Guardar] [Descartar cambios] · estado (role=status)
```

### 2.2 Qué es mío y qué es de designer

| Pieza | Responsable |
|---|---|
| `columnas.astro`, `columnas.css`, `constructor-columnas.ts`, `api-definiciones.ts` (cliente de `/definiciones-columnas`, si no lo cubre `api-texto-enriquecido.ts`: duda D-2), claves `columnas.*` | yo |
| `EditorTexto`, `VariantesSegmento`, cliente del motor, `expresion.ts`, claves `textoEnriquecido.*`, patrón de fecha compartido (D-8) | `designer` |
| Nav (`navegacion.ts`, `Navegacion.astro`, `nav.*`) | `designer`, a mi pedido |

### 2.3 Estados de la pantalla

| Estado | Qué se ve | Notas |
|---|---|---|
| Cargando | Esqueleto del panel de definición y de la lista (`.skeleton`); controles deshabilitados; sin saltos de diseño | `aria-busy` en el contenedor |
| Sin conexión | `standIn` «Sin conexión con la API» con Reintentar, igual que `/mowa-mes/*` | `data-offline` |
| Vacío (sin definiciones guardadas) | Bloque vacío con título, una frase y `+ Nueva definición` | La definición nueva arranca con una columna vacía |
| Definición cargada, sin cambios | Guardar deshabilitado (sin la opacidad de un primario: DESIGN.md), Descartar deshabilitado | |
| Con cambios sin guardar | Guardar y Descartar habilitados; al cambiar de definición o salir, un diálogo con `openWhenFree` | `beforeunload` solo si hay cambios |
| Versión usada | Hint bajo Guardar: «Al guardar se crea la versión N+1; la N no cambia». Guarda con `POST …/versiones` | Mismo patrón que el speech |
| Guardando | `data-loading="true"` en Guardar, controles de la definición deshabilitados | El borrador no se pierde si falla |
| Con problemas de validación | `.notice--danger` sobre la lista con el conteo y un botón «Ir al problema» por cada uno; filas y variantes con marca y `triangle-alert`. En vivo sin `role="alert"`; al intentar guardar, `role="alert"` y foco al primero (interfaz §4) | Ver 2.5 |
| 400 al guardar | Con `codigo` y `ubicacion`: se ubica bajo su campo (nombre repetido bajo el nombre; columna y segmento bajo su fila) | Los 400 de B4b |
| 409 al guardar | La versión se usó mientras se editaba: se conserva lo escrito, se recarga la lista y se ofrece guardar como versión nueva | Mismo manejo que el speech |
| Definición inexistente (404) | Aviso `.notice--warning` y se vuelve a la lista | |
| Previsualización cargando | El resultado anterior se atenúa en su lugar, sin saltos | Espera de 500 ms y cancelación del pedido anterior |
| Previsualización con problemas de fila | Celda con marca y el detalle en su nombre accesible (§5.5) | Los problemas de fila son del dato y no bloquean guardar |

### 2.4 Estado del constructor (F3-a, hoy)

`src/lib/constructor-columnas.ts`, puro (sin DOM ni `fetch`), como `expresion.ts`. Es la base de la pantalla y lo único que se puede escribir ya:

- **Tipos provisionales** que después pasan a ser alias de los generados desde el contrato de B4b: `TipoSalida`, `FormatoFinanciero`, `VarianteColumna`, `Columna`, `Segmentacion` (criterio calculado o por campo, política), `Definicion`. Se toman de `entities/mapeo.py` y `entities/segmentacion.py`; la forma de la API la fija B4b.
- **Borrador de la columna** con un `id` estable (identidad de DOM y foco, nunca viaja al backend), `nombre`, `tipo`, formato, `valor_por_defecto`, `expresion` y `variantes`.
- **Funciones puras:** crear definición y columna; agregar, quitar y duplicar (con nombre único); mover una posición con límites; renombrar; cambiar el tipo (al cambiar, el formato que no aplica se descarta); fijar el formato de fecha, el financiero y el valor por defecto; fijar la protección y la segmentación; `hayCambios` contra la copia guardada; `desdeDefinicion` y `aDefinicion` (ida y vuelta con el contrato, sin lo que añade el editor); resumen del contenido de una columna («Variable: …», «Texto: …») y modo (`variable` o `texto`) derivado de la expresión.
- **Fuera de este archivo:** el estado de las variantes por segmento (cuáles hay, copiar, la variante por defecto) puede ser de `VariantesSegmento`. Mover, duplicar y quitar columnas conservan las variantes sin tocarlas. La frontera se le pregunta a `designer` (D-1).
- **Lo que no hace:** no valida reglas de negocio ni el nombre. Marca el nombre repetido como **pista preventiva** local (sin tildes ni mayúsculas) para no ofrecer un guardado inútil, pero el backend es la autoridad y su 400 manda.

Vitest (`tests/nucleo/constructor-columnas.test.ts`): agregar al final y en medio; quitar la única columna (queda una vacía o ninguna: definir); duplicar con nombre único repetido varias veces; mover en los extremos (no-op) y el orden resultante; el `id` no cambia al mover ni al duplicar produce un `id` nuevo; cambio de tipo y formato; valor por defecto vacío es `null`; `hayCambios` ante cada campo; `desdeDefinicion`/`aDefinicion` ida y vuelta sin perder variantes ni la segmentación; el borrador no comparte referencias con lo guardado.

### 2.5 Ubicación de problemas por columna

El backend ubicará un problema por columna y, en una variante, por segmento. Hoy `Problema.ubicacion` solo tiene `nodo`, `funcion` y `parametro` (expresión). Falta saber cómo B4b indica la columna y el segmento (pregunta C-2, sección 6). Cuando se sepa, `ubicarProblemasColumnas` traduce cada problema a la fila y a la variante, igual que `ubicarProblemas` de `expresion.ts` hace con las piezas, y un problema cuyo destino ya no existe se conserva para toda la definición.

### 2.6 Escenarios de Playwright (API falsa del constructor)

API falsa: `e2e/api-falsa-definiciones.ts`, tipada contra el contrato generado, con una función `montarApiDefiniciones(page, estado)` y la lista de `pedidos`, como `api-falsa-mowa-mes.ts`. Reutiliza la falsa del motor de `designer` para catálogo, validación y previsualización (D-2). Datos sintéticos.

Archivos: `e2e/columnas.spec.ts` (flujo) y casos nuevos en `e2e/accesibilidad.spec.ts` (axe).

| ID | Escenario | Qué comprueba |
|---|---|---|
| K1 | Carga inicial con definiciones | Lista, una definición abierta, línea «Versión N · usada en M cargas» |
| K2 | Sin definiciones | Estado vacío y `+ Nueva definición` |
| K3 | Sin conexión | Aviso y contenido oculto, Reintentar vuelve a pedir |
| K4 | Definición nueva de punta a punta | Nombre, dos columnas, tipos; el POST lleva la forma del contrato y **ningún texto con sintaxis**; mensaje de éxito |
| K5 | Reordenar columnas | Subir y bajar; el foco sigue en el mismo botón de la fila movida; orden en el POST |
| K6 | Duplicar | Nombre único; no comparte contenido con la original |
| K7 | Quitar | Con contenido pide confirmación (diálogo); sin contenido no |
| K8 | Variable directa conserva el tipo | Resumen «Variable: Vencimiento · sumar 3 días (fecha)» desde el catálogo; el POST lleva un solo nodo |
| K9 | Texto compuesto | Monta el editor; el cambio llega a la pantalla por `expresioncambiada` y guarda |
| K10 | Variar por segmento | Marca, seis variantes, estados por segmento, copiar de otro segmento |
| K11 | Segmentación | Criterio calculado por defecto, tabla de rangos de solo lectura, política sin segmento (radio), criterio por campo con su `select` |
| K12 | Protección de fórmulas | Casilla marcada por defecto y el valor viaja en el POST |
| K13 | Guardar siempre crea una versión | El hint «Al guardar se crea la versión N+1; la N no cambia» se ve siempre (en una definición nueva, «se crea la versión 1»); se guarda con `POST …/versiones`, nunca `PUT`; el nombre es editable solo al crear y de solo lectura después, con su hint (§5.1, 2026-10-03) |
| K14 | Guardar con problemas | No guarda; resumen con `role="alert"`; foco al primer problema; «Ir al problema» abre la fila |
| K15 | 400 con `codigo` y `ubicacion` | Nombre repetido bajo su campo; columna bajo su fila |
| K16 | 409 `nombre_repetido` al crear | Se ubica bajo el nombre y se conserva lo escrito. (Ya no hay 409 por versión usada: ninguna versión se modifica) |
| K17 | Cambios sin guardar | Cambiar de definición pide confirmar; descartar restaura |
| K18 | Previsualización | Ejemplos por segmento (una fila por segmento); cartera real con el selector compacto; atenuado mientras llega; problemas de fila marcados |
| K19 | Idioma | Pantalla en inglés sin claves sin traducir |
| K20 | Ancho 360 | Tabla apilada, sin scroll horizontal de página |
| K21 | Teclado | Editar abre y cierra con Enter/Espacio (`aria-expanded`); Escape devuelve el foco a Editar; orden de Tab lógico |
| K22 | Una versión antigua se abre en solo lectura | Editores deshabilitados, sin «+ Agregar columna» ni Guardar; `.notice--info` «Estás viendo la versión 2. La vigente es la 5» con «Ir a la vigente» como botón por defecto y «Usar como base» como secundario |
| K23 | «Usar como base» | Habilita la edición, cambia el aviso a `.notice--warning` («Partes de la versión 2. Al guardar se crea la versión 6 con este contenido y pasa a ser la vigente; la 5 no cambia») y muestra Guardar, también sin cambios |
| K24 | Guardar desde la base y descartar | Guardar crea la versión 6 con el contenido de la 2 y la vigente pasa a ser la 6 (el POST va a `/versiones` sin nombre); Descartar vuelve a la versión 2 en solo lectura; la vigente siempre se abre editable |

### 2.7 axe (en tema claro y oscuro, y a 360 px)

Lista con una fila expandida; variantes por segmento con estados; resumen de problemas con marcas; la vista previa con un problema de fila; diálogo de confirmación de cambios sin guardar; diálogo de quitar columna; segmentación desplegada; estado vacío y sin conexión.

### 2.8 Lo que no cubre F3

NVDA real, zoom real al 200 % (se aproxima con viewport de 640 px), regresión visual, cobertura y análisis estático. Se declaran al entregar.

## 3. F4: speech v2 en `/mowa-mes/configuracion`

### 3.1 Qué cambia y qué no

La tabla de dos partes se reemplaza, **para versiones v2**, por el selector de variantes con los seis segmentos y el editor de texto enriquecido con límite 160 (interfaz §5.6). Las v1 se siguen viendo en solo lectura con sus dos partes hasta M3. No cambian: la versión, el nombre, el guardado (`modoGuardado`), la inmutabilidad (original y usada), la marca «usada», el aviso de falta de WhatsApp, el resumen de niveles ni el resto de la pantalla (plataforma, supervisores, calendario, costos).

### 3.2 Cambios por bloque de `configuracion.astro`

| Bloque (hoy) | Cambio |
|---|---|
| Selector de versión (`pintarVersiones`) | Cada opción lleva su formato (v1 o v2) como marca, además de «original» y «usada» |
| `elegirVersion` / `borradorDesdeVersion` | El borrador pasa a ser una unión: partes (v1) o expresiones por segmento (v2). La v1 queda de solo lectura: se muestra sin cajas editables |
| `pintarSpeech` | Rama v1: texto solo lectura con las dos partes por segmento. Rama v2: `VariantesSegmento` + `EditorTexto` (límite del contexto `mowa_mes.speech`, que viene del catálogo, no escrito a mano) |
| `pintarPrevisualizacion` | La rama v2 usa la previsualización del motor para el contexto `mowa_mes.speech` con **ejemplos por segmento**. Los niveles (Cabe / Más de 150 / Más de 160 / Falta WhatsApp) salen de los límites del backend; no se recalcula el largo en el cliente |
| `hayCambiosSpeech`, `modoGuardado` | Se extienden a v2 (comparación por expresión, no por texto) |
| Guardar | Una versión v2 guarda con `POST /mowa-mes/speech` con las expresiones; el 409 de versión usada mientras se editaba conserva lo escrito, como ya hace el speech v1 |
| Aviso de falta de WhatsApp | Sin cambios: sale del backend |

Funciones puras nuevas, para probarlas sin navegador, en `src/lib/mowa-mes.ts` o un archivo nuevo `src/lib/mowa-mes-speech-v2.ts` (sin tocar lo que ya prueba `tests/nucleo/mowa-mes.test.ts`): borrador v2 desde una versión; `hayCambios` v2; `modoGuardado` para v2; resumen de niveles por segmento.

### 3.3 Estados

Sin versión v2 (solo la original y las v1); versión v2 vigente; segmento sin contenido; con problemas de validación por segmento (resumen y marca en la variante); largo excedido y cerca; falta de WhatsApp; versión usada (solo lectura con la opción de «guardar como versión nueva»); guardando; 409; sin conexión (el aviso de siempre).

### 3.4 Escenarios de Playwright

API falsa: se extiende `e2e/api-falsa-mowa-mes.ts` con versiones v2 (campo de formato y expresiones por segmento) y se mantiene tal cual lo que usan los 43 escenarios actuales de `mowa-mes-configuracion.spec.ts`. Esos 43 **no deben cambiar** ni salir rojos: son la regresión de v1.

| ID | Escenario | Qué comprueba |
|---|---|---|
| M1 | v1 en solo lectura | El Speech original se ve con sus dos partes, sin cajas editables, con el aviso de inmutable |
| M2 | v1 y v2 conviven en el selector | Cada una con su marca; elegir una cambia la vista sin perder la otra |
| M3 | Armar el speech de un segmento sin teclear sintaxis | Texto, variable y función con los menús; el POST lleva la expresión y no `[@…]` |
| M4 | Largo con niveles | Cabe, más de 150, más de 160 con los límites de la API; el resumen es `role=status` y solo se escribe al cambiar de nivel |
| M5 | Falta WhatsApp | Segmento con `[whatsapp]` y sin número: nivel y aviso, sin ejemplo |
| M6 | Problemas de validación por segmento | Resumen, marca y «Ir al problema»; guardar no guarda y el foco va al primero |
| M7 | Crear versión v2 | Según la respuesta a la pregunta C-5 (basada en una v1 o desde cero) |
| M8 | 409 de versión usada | Se conserva lo escrito |
| M9 | Inglés | Sin claves sin traducir |
| M10 | Sin conexión | Igual que hoy |

### 3.5 axe

Configuración con el speech v2 abierto: en claro y oscuro, con una pieza abierta, con un problema, con el selector de variables abierto y a 360 px.

### 3.6 Revisión

Con su worktree, antes de architec, por `coordinador_modulo_mowa_mes` (plan.md §13). Debe quedar en verde `mowa-mes-configuracion.spec.ts` y `mowa-mes.test.ts` de siempre.

## 4. Verificación de cada corte (criterio de listo)

- Worktree desde HEAD y `$env:PLAYWRIGHT_PUERTO` propio. `npm run verificar` completo (contrato, `astro check`, build, Vitest, Playwright con axe).
- Vitest de cada pieza pura, con el caso normal, los bordes y las entradas inválidas.
- Mutación a mano en el worktree (nunca en el árbol compartido): al cerrar cada corte, una por regla importante. Para F3: mover con arranque desplazado, duplicar sin nombre único, el foco al mover, guardar con problemas, versión usada con `PUT`, cambios sin guardar sin confirmar, el hint de la versión siguiente, el campo `proteger_formulas` ignorado. Para F4: la rama v1 editable, niveles con límites escritos a mano, comparar partes en vez de expresiones, no conservar lo escrito tras un 409.
- Lo que se declara fuera, con su motivo: NVDA, zoom real, regresión visual, cobertura, análisis estático, y las capas con base de datos (solo las corre architec).
- Se informa por escrito: archivos, capas corridas y no corridas, y las claves i18n nuevas.

## 5. Riesgos

| Riesgo | Mitigación |
|---|---|
| `es.json` y `en.json` los tocan varios agentes a la vez (designer, yo) | Bloque contiguo propio al final; el coordinador fija el orden (duda D-7) |
| La forma de la definición cambia cuando B4b la fije | Tipos provisionales y un solo módulo (`constructor-columnas.ts`) que los reexporta; el resto de la pantalla importa de ahí |
| El estado de variantes se duplica entre mi pantalla y `VariantesSegmento` | Pregunta D-1 antes de tocar variantes |
| F4 rompe los 43 escenarios de configuración | La rama v1 queda sin cambios y los 43 son la red de seguridad |
| Un editor por columna y por variante (muchas instancias) | Una instancia a la vez (una fila expandida, una variante elegida). Se confirma con `designer` que el componente lo admite (D-3) |

## 6. Preguntas de contrato para el coordinador y el backend

| # | Pregunta | Para qué |
|---|---|---|
| C-1 | ¿La definición guardada trae el `orden` de cada columna como entero explícito o por posición en la lista? ¿Y un identificador de columna, o se identifica por nombre? | Es la clave del estado del constructor y de los problemas por columna |
| C-2 | ¿Cómo ubica B4b un problema de una definición: `columna` (índice o nombre), `segmento` y la ubicación de la expresión dentro? | `ubicarProblemasColumnas` y los 400 con `ubicacion` |
| C-3 | ¿La API devuelve `formato_fecha` como marcas (`dd/mm/aaaa`) o como `strftime`? Hoy `CampoSalida.formato_fecha` es `strftime` | El selector de patrón de fecha del constructor y del editor |
| C-4 | ¿Una columna que viene de una plantilla `[@…]` (formato viejo) la devuelve la API ya convertida a expresión? | El constructor solo edita expresiones |
| C-5 | ¿B6 ofrece crear una versión v2 **a partir de una v1** (convertida con `expresion_de`), o parte desde cero? ¿Cómo marca la API el formato de una versión (campo `formato`)? ¿Qué devuelve para la v1 cuando se pide como v2? | Es lo más importante de F4: que la analista no tenga que reescribir el Speech original |
| C-6 | ¿La previsualización del speech v2 sale de `POST /texto-enriquecido/previsualizacion` con `contexto=mowa_mes.speech`, o de `/mowa-mes/speech/previsualizacion` ampliado? ¿Quién devuelve los niveles (cabe, 150, 160, falta WhatsApp)? | La rama v2 de `pintarPrevisualizacion` |
| C-7 | ¿Qué trae `GET /definiciones-columnas` en el listado (nombre, versión vigente, usada en N cargas)? ¿Hay paginación? | La lista y la línea de versión |
| C-8 | ¿El número de cargas en que se usó una versión viene en la definición? | «Versión 3 · usada en 2 cargas» |
| C-9 | ¿Hay un límite de columnas por definición y de variantes? | Para no ofrecer lo que el backend rechaza |
| C-10 | ¿`proteger_formulas` y la segmentación viajan en la definición o en las opciones del archivo? | Encabezado de la definición |

## 7. Qué necesito para empezar cada corte

- **F3-a (ya):** nada. Empiezo con los tipos provisionales y Vitest, sin tocar `expresion.ts` ni nada de designer.
- **F3-b y F3-c:** contrato de B4b y F2 entregado.
- **F4:** contrato de B6 y F2 entregado, y la respuesta a C-5 y C-6.

## 8. Límite de F3 resuelto: la muestra del editor es el producto del segmento elegido (2026-10-19)

Antes el editor de la fila usaba el primer producto de la selección. Con B11 (`pagare` y `fecha_corte` por fila de la previsualización) y `controlMuestra` en `montarVariantes` (ya en main) el límite se cerró en el corte chico de `/columnas`: con «Cartera real» y un segmento a la vista, `muestraDelEditor()` toma el pagaré y la fecha de la primera fila de la vista previa que cae en ese segmento (`producto_real`); si ninguna cae, usa el primer producto de la selección y lo dice en una línea (`columnas.muestra.sinSegmento`); con el contenido por defecto a la vista no hay segmento y vale el primer producto. Con ejemplos, el registro de ejemplo. La regla CSS de `controlMuestra` se quitó, y la vista previa expone `data-calculando` y `aria-busy` para que axe espere a que esté al día.
