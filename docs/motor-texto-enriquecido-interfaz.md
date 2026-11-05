# Motor de texto enriquecido: reglas de interfaz

Reglas vinculantes para el frontend del motor de texto enriquecido y del constructor de columnas (T-MTE-F1). Complementan el diseño técnico de [motor-texto-enriquecido.md](motor-texto-enriquecido.md) y los requerimientos RF-42 a RF-54 de [atomics-requirements.md](atomics-requirements.md), sección 11.

Responsable: `designer`. Implementa: `dev_frontend_herramientas_implementadas`, bajo `coordinador_herramientas_implementadas`. Un cambio a estas reglas se acuerda con `designer` antes de escribirlo.

---

## 1. Principios

1. **El usuario no escribe sintaxis.** Nunca ve `[@campo | funcion(arg)]` ni corchetes, tuberías o comillas. Arma el texto con piezas, menús y campos. La sintaxis existe solo por compatibilidad con el backend (RF-42).
2. **El backend es la autoridad.** La interfaz arma el árbol de nodos y muestra lo que devuelve el backend: problemas, resultado por nodo y largo máximo. No evalúa funciones ni valida reglas de negocio; ni siquiera recalcula el largo.
3. **Prevenir antes que reportar.** Solo se ofrecen las variables del contexto y las funciones compatibles con el tipo que llega a esa posición de la cadena. Lo que el backend rechace igual se muestra en su lugar (sección 4).
4. **Todo sale del catálogo.** Variables, funciones, parámetros, tipos y nombres visibles vienen de `GET /texto-enriquecido/catalogo`. Una función nueva del backend aparece en la interfaz sin tocar el frontend, siempre que traiga su clave i18n.
5. **Controles nativos, sin `contenteditable`.** Cada pieza es un control real (`textarea` o `button`). Así el teclado, el lector de pantalla, pegar texto y los métodos de entrada funcionan sin reimplementarlos.

## 2. Editor de texto compuesto: piezas en línea

Decisión del usuario (2026-09-29): el texto se lee como la frase final, con los tramos de texto editables y cada variable como una pieza en medio.

### 2.1 Estructura

```
Texto del mensaje
┌──────────────────────────────────────────────────────┐
│ (Titular · primeros 8) Caja Cusco te informa que tu  │  ← línea de piezas
│ cuota venció el (Vencimiento · dd/mm/aaaa), acércate │
│ a pagar.                                             │
└──────────────────────────────────────────────────────┘
[+ Variable]                                            ← barra
┌ Titular ─────────────────────────────── texto ┐       ← panel de la pieza abierta
│ 1. Primeros caracteres   [ 8 ]      [↑][↓][×] │
│ [+ Agregar función ▾]                         │
│ [ ] Obligatoria: si falta, el producto se informa │
│ Resultado con el ejemplo: JUAN PER             │
└──────────────────────────────────────────────┘
Vista previa con [Registro de ejemplo ▾]
JUAN PER Caja Cusco te informa que tu cuota venció el 05/10/2026, acércate a pagar.
148 caracteres · máximo posible 156 de 160
```

- **Línea de piezas:** un contenedor con el borde de campo (`.input`), que alterna tramos de texto y piezas de variable, con `flex-wrap`.
  - **Tramo de texto:** un `textarea` sin borde propio que crece con su contenido. Uno corto queda en línea; uno largo ocupa el ancho y hace su propio ajuste de línea.
  - **Pieza de variable:** un `button` con forma de píldora (sección 6), con el nombre visible de la variable y el resumen de sus funciones: «Titular · primeros 8». Si el resumen es largo, se recorta con puntos suspensivos y el texto completo va en su nombre accesible.
- **Siempre hay un tramo al principio y otro al final,** aunque estén vacíos, para poder escribir antes y después de cualquier variable. Un tramo vacío mide 2 caracteres y muestra su borde punteado solo al tener foco o puntero encima.
- **Barra:** `+ Variable`. No hay `+ Texto`: el texto se escribe directamente en los tramos.

### 2.2 Insertar una variable

- `+ Variable` inserta en la **posición del cursor** del último tramo con foco. Si el cursor está a mitad de un tramo, lo parte en dos y pone la variable en medio. Si ningún tramo tuvo foco, la inserta al final.
- Abre un selector bajo la barra, no un diálogo modal:
  - Un buscador (`input type="search"`) y la lista de variables como botones, agrupadas por origen: **Cartera** y el contexto del módulo (por ejemplo, **MOWA MES**).
  - Cada botón muestra el nombre visible, su tipo como `.tag` (texto, número, fecha o sí/no para `booleano`, RF-43) y el nombre técnico en mono muted.
  - Buscar filtra por nombre visible y técnico, sin distinguir tildes ni mayúsculas.
  - Al elegir, la pieza queda insertada, se cierra el selector y **se abre el panel de la pieza** con el foco en `+ Agregar función`.
- Escape cierra el selector y devuelve el foco a `+ Variable`.

### 2.3 Panel de la pieza: funciones y parámetros

- Una sola pieza abierta a la vez. El panel va debajo de la línea de piezas, no flotando sobre el texto, para no tapar lo que se edita.
- **Encabezado:** nombre de la variable y su tipo.
- **Cadena de funciones:** una lista ordenada, porque el orden cambia el resultado. Cada función muestra:
  - su nombre visible (i18n del catálogo);
  - un campo por parámetro según su tipo:
    - número: `input` de texto con `inputmode="decimal"` o `"numeric"`;
    - texto: `input`;
    - enumerado, por ejemplo el patrón de fecha: `select`;
    - referencia a otra variable: `select` con las variables compatibles;
    - un parámetro que admite literal o variable: un control de dos opciones, «Valor fijo» o «Otra variable»;
  - y los botones subir, bajar y quitar, con iconos lucide y nombre accesible («Subir primeros caracteres»).
- **`+ Agregar función`:** un `select` con solo las funciones que aceptan el tipo que sale de la última función de la cadena (o el de la variable si la cadena está vacía), agrupadas por familia con `optgroup`. Al elegir una, se agrega al final y el foco va a su primer parámetro.
- **Patrón de fecha:** sin `strftime` a la vista. Un `select` con los patrones frecuentes, cada uno con su ejemplo («dd/mm/aaaa — 05/10/2026»), y la opción «Personalizado», que muestra un campo con las marcas del catálogo (`dd`, `mm`, `aaaa`, `aa`, `nombre_mes`) como botones que se insertan, igual que las variables de la plantilla de nombre de MOWA MES.
- **Obligatoria:** una casilla con el hint «Si falta este dato, el producto se informa con su motivo» (RF-45). No explica qué hace el módulo con eso: lo decide el módulo.
- **Resultado de la pieza** con el registro de la previsualización, en mono: el resultado por nodo que devuelve el backend.
- **Quitar la variable:** un botón `.btn--danger .btn--sm` al pie del panel. Al quitarla, los dos tramos vecinos se unen en uno y el foco vuelve a ese tramo, en el punto de unión.

### 2.4 Teclado

| Dónde | Tecla | Efecto |
|---|---|---|
| Línea de piezas | Tab / Mayús+Tab | Recorre tramos y piezas en el orden de lectura |
| Pieza | Enter o Espacio | Abre o cierra su panel (`aria-expanded`) |
| Pieza | Supr o Retroceso | Quita la variable (como el botón del panel) |
| Tramo | Retroceso al principio | Lleva el foco a la pieza anterior, sin borrar nada |
| Tramo | Supr al final | Lleva el foco a la pieza siguiente, sin borrar nada |
| Panel o selector | Escape | Cierra y devuelve el foco a la pieza o a `+ Variable` |

Nada depende de arrastrar. Una variable se mueve de lugar quitándola e insertándola de nuevo; no hace falta un modo de reordenar dentro de la frase.

### 2.5 Accesibilidad

- La línea de piezas es un `role="group"` con el nombre del campo («Texto del mensaje», «Speech de 9 a 30»).
- **Nombre de cada tramo:** posicional y con contexto, no «Texto 3»: «Texto al inicio», «Texto después de Titular», «Texto al final».
- **Nombre de cada pieza:** «Variable Titular, primeros 8 caracteres. Abre sus funciones». Si tiene un problema, se agrega «, con un problema».
- **El largo** se anuncia en una región `aria-live="polite"`, y solo cuando cambia el nivel (dentro del límite, cerca, excedido), no en cada tecla.
- Contraste AA en todos los estados, incluida la pieza con problema y la pieza abierta. Se prueba con axe en los estados de la sección 7.

## 3. Previsualización (RF-47)

- **Siempre visible bajo el editor,** no detrás de un botón. Se recalcula con una espera de 500 ms tras cada cambio y cancela el pedido anterior, igual que el resumen de la cartera. Mientras llega la respuesta, el resultado anterior se atenúa en su lugar.
- **Registro:** un control con dos opciones:
  - **Registro de ejemplo** (por defecto): el que trae el catálogo.
  - **Producto real:** fecha de corte y pagaré.
  - Un pagaré inexistente se informa bajo su campo, sin borrar la última vista previa.
- **Resultado:** mono, con `white-space: pre-wrap` para que se vean los saltos de línea.
  - Al enfocar o pasar el puntero sobre una pieza, **su parte del resultado se resalta** con el fondo de acento suave. Se usa el resultado por nodo del backend, para ver qué produce cada variable.
  - Una variable vacía en el registro se muestra con una marca punteada de ancho fijo, sin texto dentro y con el nombre accesible «vacío». No se copia al seleccionar el texto: marca que falta un dato, no un carácter.
- **Largo:** «148 caracteres · máximo posible 156 de 160».
  - El máximo y el límite solo aparecen si el backend los devuelve. El límite lo aporta el módulo (160 para SMS).
  - Si la expresión no se puede acotar, se dice así: «sin máximo calculable», con el motivo que devuelva el backend.
  - El nivel usa los `.tag` que ya existen: dentro del límite, `tag--vigente`; excedido, `tag--error`. El umbral de «cerca» lo decide el módulo.
- **Problemas de fila del registro,** como un teléfono inválido para `enlace_whatsapp`: se muestran bajo el resultado como `.notice--info`. Son del dato, no del texto, y no bloquean guardar.

## 4. Errores en su lugar (RF-46)

El backend devuelve cada problema con su `codigo` (catálogo `CodigoTexto`, traducido en `textoEnriquecido.codigo.*`) y su `ubicacion`: nodo, función y parámetro. La interfaz lo muestra en el lugar más preciso que la ubicación permita:

| Ubicación | Dónde se ve |
|---|---|
| Parámetro | Bajo su campo en el panel, con `.field__error`, `aria-invalid` y `aria-describedby`. La pieza lleva la marca de problema |
| Función | En la fila de la función, dentro del panel. La pieza lleva la marca de problema |
| Nodo variable | En la pieza: borde y fondo de señal (sección 6), con el detalle en su panel |
| Nodo texto | Bajo la línea de piezas, nombrando el tramo por su posición («Texto después de Titular») |
| Toda la expresión | Por ejemplo, el límite de tamaño: en el resumen |

- **Resumen:** sobre la línea de piezas, una `.notice--danger` con la cantidad de problemas y un botón por cada uno («Ir al problema») que abre la pieza y enfoca el campo.
  - Mientras se edita, el resumen se actualiza en silencio, sin `role="alert"`, para que la validación en vivo no interrumpa.
  - Al intentar guardar con problemas, no se guarda: el resumen pasa a `role="alert"` y el foco va al primer problema.
- **Pieza con problema pero cerrada:** además del color, lleva el icono `triangle-alert`, para no depender solo del color.
- **La validación en vivo** usa `POST /texto-enriquecido/validacion` con la misma espera que la previsualización. Mientras un problema siga sin resolverse, su marca se mantiene aunque el campo cambie; se quita cuando responde la validación siguiente.

## 5. Constructor de columnas (RF-49 a RF-53)

### 5.1 Encabezado de la definición

- **Nombre** (único, RF-51). Se escribe al crear la definición y **no cambia entre versiones** (B4b rechaza un nombre distinto con un problema en `campo=nombre`). Después de la primera versión se muestra de solo lectura y se cambia con «Renombrar», sin crear una versión (RF-56, sección 10.1).
- **Línea de versión:** «Versión 3» o, si se usó, «Versión 3 · usada en 2 cargas». Ninguna versión se modifica: guardar **siempre** crea una nueva. Por eso, bajo el botón de guardar va **siempre** el hint «Al guardar se crea la versión 4; la 3 no cambia», se haya usado o no. Para una definición nueva: «Al guardar se crea la versión 1». Ajuste de la revisión de B4b, 2026-10-03.
- **Versiones antiguas: solo lectura hasta que el analista decida partir de ellas.** Guardar crea siempre la vigente + 1 con el contenido en pantalla. Por eso, abrir para mirar una versión que no es la vigente nunca deja listo un guardado que la reemplace (principio «nada cambia sin confirmación explícita», PRODUCT.md):
  - Se muestra **en solo lectura:** editores deshabilitados, sin `+ Agregar columna` ni guardar. Arriba, un `.notice--info`: «Estás viendo la versión 2. La vigente es la 5».
  - En ese aviso van dos acciones: «Ir a la vigente», el botón por defecto, y «Usar como base», un botón secundario.
  - **«Usar como base»** habilita la edición y cambia el aviso a `.notice--warning`, visible hasta guardar o descartar: «Partes de la versión 2. Al guardar se crea la versión 6 con este contenido y pasa a ser la vigente; la 5 no cambia». El hint bajo el botón de guardar dice lo mismo en corto.
  - Descartar los cambios vuelve a la versión 2 en solo lectura.
  - La vigente se abre editable, como siempre.

  Decisión de `designer` del 2026-10-03, ante la propuesta del coordinador del motor.
- **Segmentación:** una sección colapsable, cerrada por defecto si la definición no tiene variantes.
  - **Criterio:** `select` con «Segmento financiero calculado por días de atraso» (por defecto, RF-50) y «Valor de un campo de la cartera». Con el segundo aparece el `select` del campo.
  - **Tabla de rangos:** solo lectura en esta pantalla, con etiqueta, desde y hasta, tal como la devuelve el backend.
  - **Sin segmento:** dos opciones de radio, «Excluir el producto e informar el motivo» (por defecto) y «Usar el contenido por defecto».
- **Protección contra fórmulas en CSV:** una casilla marcada por defecto, con el hint «Agrega un apóstrofo a los textos que empiezan con =, +, - o @, salvo los que son solo un número, como -1,234.56 o +51900000001. Desmárcala solo si la plataforma de destino no lo acepta» (RF-53).

### 5.2 Lista de columnas

Una `.table` con `.table--apilable-ancha`, porque las filas llevan editores, y una fila por columna:

| # | Nombre | Tipo | Contenido | Formato | Por defecto | Acciones |
|---|---|---|---|---|---|---|

- **#:** el orden, con botones subir y bajar. Al mover una fila, el foco sigue en el mismo botón de la fila movida.
- **Nombre:** `input`. Es la cabecera del archivo.
- **Tipo:** `select` con los tipos del contrato (`TipoSalida`): texto, número, fecha y `financiero`, que se muestra como «Importe».
- **Contenido:** resumen de solo lectura, «Variable: Saldo capital» o «Texto: JUAN PER Caja Cusco te…». Si la columna varía por segmento, lleva un `.tag` con «6 variantes».
- **Formato:** resumen del formato según el tipo; se edita en la fila expandida.
- **Por defecto:** `input` opcional (RF-45).
- **Acciones:** Editar (expande la fila), Duplicar y Quitar. Quitar pide confirmación solo si la columna tiene contenido.
- Al pie de la lista, `+ Agregar columna`, que la agrega al final y la abre expandida.

### 5.3 Fila expandida

Una sola fila expandida a la vez, debajo de la fila, con el patrón de divulgación: el botón Editar con `aria-expanded`.

- **Contenido,** dos opciones de radio:
  - **Variable directa:** un `select` de variables con su tipo. Hint: «Conserva el valor original, sin pasarlo por texto» (RF-49). Si se le agregan funciones y la columna sigue siendo una sola variable, conserva el tipo del resultado final: una fecha con días sumados sigue siendo fecha en el XLSX (precisión D11 del diseño). El resumen de la fila lo dice así: «Variable: Vencimiento · sumar 3 días (fecha)». Es el mismo `EditorTexto` montado con `soloVariable: true` (9.2): el `select` reemplaza la línea de piezas y el panel de funciones de la sección 2.3 queda siempre abierto, sin «Quitar variable». No hay una cadena de funciones aparte.
  - **Texto compuesto:** el editor de la sección 2.
- **Formato,** según el tipo:
  - fecha: el mismo selector de patrón de la sección 2.3;
  - número o importe: decimales, separador de miles y separador decimal, con un ejemplo en vivo («1,234.50»).
- **Variar por segmento:** una casilla. Al marcarla aparece el selector de variantes (5.4).

### 5.4 Variantes por segmento

- **A la izquierda,** la lista de segmentos del criterio más «Por defecto», como botones. Cada uno muestra su estado con un `.tag`:
  - completo;
  - vacío;
  - con problema;
  - largo excedido.
- **A la derecha,** el editor de la variante elegida, uno a la vez. Por debajo de 48rem, la lista pasa arriba como un `select`.
- **«Copiar de otro segmento»:** trae el contenido de otra variante para partir de ahí. Los speech de segmentos vecinos suelen diferir en pocas palabras.
- **La previsualización** usa un producto del segmento elegido si el registro es real, y el ejemplo si no.

### 5.5 Previsualización de la definición

- Bajo la lista de columnas va una tabla, con una columna por columna definida y el segmento de cada fila. Usa `POST /texto-enriquecido/previsualizacion` con la definición completa.
- **De dónde salen las filas,** acordado con el coordinador del motor (2026-09-29). Un control de dos opciones:
  - **Ejemplos por segmento** (por defecto): el registro de ejemplo del catálogo, una fila por segmento, con valores sintéticos que caen en cada rango. Es rápido, no depende de que haya una sábana cargada y muestra todas las variantes de una vez.
  - **Cartera real:** una fecha de corte y una selección guardada o filtros, con `SelectorSeleccion` en modo compacto. Muestra los primeros 5 productos de esa selección, con el mismo orden que la carga.
- Las celdas con problema de fila llevan su marca y el detalle en su nombre accesible.

### 5.6 Primer consumidor: speech de MOWA MES (fase M2)

El speech por segmento es **una columna de texto compuesto con variantes por segmento**. `/mowa-mes/configuracion` reemplaza la tabla de dos partes por:

- el selector de variantes (5.4), con los seis segmentos de MOWA MES;
- el editor (sección 2) con límite 160;
- los niveles de largo que MOWA MES ya usa (Cabe / Más de 150 / Más de 160 / Falta WhatsApp).

La versión, el nombre de la versión y el guardado conservan su forma actual. Las versiones v1 ya no existen: se convirtieron a v2 en su lugar (RF-MM-17, §10.2).

## 6. Sistema visual

- **Pieza de variable:** píldora, porque es un botón (brand guide).
  - Texto en mono `--text-sm`, fondo `--color-accent-wash` y borde hairline `--color-accent-text`.
  - Abierta: borde de 2 px `--color-text`.
  - Con problema: fondo `--color-signal-wash`, borde `--color-danger-text` e icono `triangle-alert`.
  - La pieza nunca cambia de alto entre estados, para que la línea no salte.
- **Resaltado en la previsualización:** `--color-accent-wash` con una línea inferior de 2 px `--color-accent-text`.
- **Marca de vacío en la previsualización:** 2ch de ancho con borde inferior punteado `--color-text-muted`.
- **Panel de la pieza y selector de variables:** `.panel` con radio 0.
- **Todo sale de los tokens.** Ninguna regla nueva lleva hex ni px, salvo el hairline ya definido.

## 7. Pruebas mínimas

- **Vitest,** sobre el estado del editor como funciones puras:
  - insertar en la posición del cursor (principio, medio y final de un tramo);
  - quitar una variable y unir los tramos;
  - tramos extremos siempre presentes;
  - funciones ofrecidas según el tipo de la cadena;
  - ubicar cada problema del backend en su pieza, función o parámetro;
  - ida y vuelta entre el estado del editor y el árbol del contrato.
- **Playwright:**
  - armar el speech de un segmento sin teclear sintaxis;
  - agregar, reordenar y quitar funciones;
  - un parámetro inválido con su error en su campo y el resumen que lleva a él;
  - la previsualización que resalta la parte de la pieza enfocada;
  - el largo excedido;
  - guardar con problemas no guarda y lleva el foco al primero;
  - el constructor: agregar, reordenar y quitar columnas, variar por segmento y copiar una variante.
- **axe,** en tema claro y oscuro: el editor con una pieza abierta, con un problema y con el selector de variables abierto; el constructor con una fila expandida y con variantes. También a 360 px.
- **Teclado:** la tabla de 2.4 completa, como prueba de Playwright.

## 8. Qué es compartido y quién lo hace

| Pieza | Dónde | Quién |
|---|---|---|
| Estado puro del editor (árbol, inserción, cursor, problemas) y sus ayudas (búsqueda, largo, argumentos) | `src/lib/expresion.ts`, `src/lib/editor-texto.ts` | `designer` |
| Estado puro de las variantes por segmento | `src/lib/variantes.ts` | `designer` |
| Componente del editor y su comportamiento | `src/components/EditorTexto.astro`, `src/scripts/editor-texto.ts`, `src/styles/editor-texto.css` | `designer` |
| Selector de variantes por segmento | `src/components/VariantesSegmento.astro`, `src/scripts/variantes-segmento.ts` | `designer` |
| Selector de variable y selector de patrón de fecha | `src/scripts/selector-variable.ts`, `src/scripts/selector-patron-fecha.ts` | `designer` |
| Página de prueba de los componentes compartidos, solo en el build de Playwright | `src/pruebas/editor-texto.astro`, `e2e/editor-texto.spec.ts` | `designer` |
| Cliente de catálogo, validación y previsualización | `src/lib/api-texto-enriquecido.ts` | `designer` |
| API falsa de catálogo, validación y previsualización | `e2e/api-falsa-texto-enriquecido.ts` | `designer` |
| Fila expandida de tabla y marca de vacío | `src/styles/ui.css` (`.table__detalle`, `.marca-vacio`) | `designer` |
| Textos `textoEnriquecido.*` | `src/i18n/*.json` | `designer`, con la prueba espejo del backend sobre todas sus claves |
| Etiquetas de los campos de la cartera (`campo.<nombre>`) | `src/lib/campos.ts`, `src/i18n/*.json` | `designer`, con su prueba contra el catálogo de campos del backend (`tests/nucleo/i18n-campos.test.ts`). Las usan `/cartera`, el selector de variables y el constructor. Una variable con `clave_nombre` usa esa clave; un campo de la cartera, `campo.<nombre>` |
| Cliente de `/definiciones-columnas` y su API falsa | `src/lib/api-definiciones.ts`, `e2e/api-falsa-definiciones.ts` | `dev_frontend_herramientas_implementadas` |
| Pantalla del constructor de columnas, su vista previa y sus textos `columnas.*` | `src/pages/columnas.astro`, `src/styles/columnas.css` | `dev_frontend_herramientas_implementadas` |
| Integración en el speech de MOWA MES (M2) y sus textos `mowaMes.speech.v2.*` | `src/pages/mowa-mes/configuracion.astro` | `dev_frontend_herramientas_implementadas` |
| Entrada de navegación y claves `nav.*` | `src/lib/navegacion.ts`, `src/i18n/*.json` | `designer`, cuando la página exista en el árbol |

El orden lo fija el coordinador. El editor empieza apenas el backend fije el contrato (B4a).

## 9. Contrato de montaje y decisiones de detalle

Respuestas a las dudas de `dev_frontend_herramientas_implementadas` (`docs/agents/dev_frontend_herramientas_implementadas/dudas-designer.md`), 2026-10-02. Son vinculantes como el resto del documento.

### 9.1 Variantes por segmento (D-1, D-4)

- El estado de una columna **transporta** sus `variantes` sin interpretarlas. Todo lo que las lee o las cambia vive en `src/lib/variantes.ts`:
  - el estado de cada segmento (completo, vacío, con problema);
  - copiar la variante de un segmento a otro;
  - activar o quitar la variante por defecto.
- `VariantesSegmento` contiene **un solo** `EditorTexto` y le cambia la expresión al elegir otro segmento (9.2).
- **Niveles propios de un módulo** (Cabe, Más de 150, Más de 160, Falta WhatsApp): el componente no conoce las reglas de MOWA MES. La página los calcula con su propia previsualización y se los pasa con `fijarNiveles({ [segmento]: { tono, texto } })`. El tono es uno de los de `.tag`: `vigente`, `advertencia`, `error` o `neutral`. El componente pinta ese `.tag` junto al estado genérico del segmento.

### 9.2 Montaje de `EditorTexto` (D-3)

Mismo patrón que `SelectorSeleccion`: la página renderiza el componente, escucha su evento en la raíz y **después** lo monta.

```ts
<EditorTexto id="speech-editor" etiqueta="Speech" />

const editor = await montarEditor(raiz, {
  contexto: 'mowa_mes.speech',      // del catálogo salen variables, funciones, límite y umbral
  expresion,                         // inicial; null es una expresión vacía
  controlMuestra: true,              // false: la página fija la muestra (constructor)
  resumen: 'propio',                 // 'ninguno': la pantalla muestra el resumen (9.4)
  soloLectura: false,                // true: una versión antigua abierta para mirar (5.1)
  soloVariable: false,               // true: columna de variable directa (5.3)
});

editor.fijarExpresion(otra);         // reemplaza, cierra paneles y vuelve a validar
editor.fijarMuestra({ tipo: 'producto_real', fecha_corte, pagare, cantidad: 1 }); // MuestraEntrada del contrato
editor.irAProblema(indice);          // abre la pieza y enfoca el campo
editor.expresion();                  // el árbol actual, para guardar
editor.estado();                     // lo mismo que lleva el último evento
editor.comprobarAntesDeGuardar();    // false si no se puede guardar; con resumen propio, lo vuelve alerta y lleva el foco al primero
editor.fijarSoloLectura(false);      // «Usar como base» habilita la edición
editor.fijarNotaMuestra(texto);      // nota bajo la vista previa («Ningún producto…»); null la quita
editor.destruir();                   // antes de sacarlo de la página
```

- **Desmontar:** `destruir()` quita los listeners que el componente puso en `document`, cancela la validación y la previsualización pendientes o en curso y deja de emitir. El marcado queda; lo saca la página. Una pantalla que monta y desmonta, como las filas del constructor, llama `destruir()` antes de quitar el nodo.

- **El componente llama al backend.** Pide validación y previsualización con espera de 500 ms y cancela el pedido anterior. La página no los llama para el editor.
- **El catálogo** se pide una vez por contexto y por página: varias instancias comparten la misma respuesta.
- **Varias instancias por página:** sí. Todos los `id` internos llevan el `id` de la raíz.
- **El límite y el umbral** salen del catálogo del contexto, no de atributos. La interfaz no escribe 160 en ningún lado.
- **Evento `expresioncambiada`,** con `bubbles`:

  ```ts
  {
    expresion,        // árbol del contrato
    origen,           // 'usuario' o 'externo': fijarExpresion no marca cambios sin guardar
    pendiente,        // true mientras hay una validación en curso
    valida,           // sin problemas en la última validación terminada
    problemas,        // ya ubicados en piezas (ubicarProblemas)
    largo,            // { actual, maximo, limite, sinCota } tal como lo dio el backend
  }
  ```

  Guardar solo se permite con `valida && !pendiente`.

`VariantesSegmento` sigue el mismo patrón: `montarVariantes(raiz, { contexto, segmentos, porDefecto, variantes, conPorDefecto, resumen, soloLectura, soloVariable, controlMuestra })`, con `fijarVariantes({ porDefecto, variantes })`, `fijarNiveles`, `seleccionar(segmento)`, `irAProblema(segmento, indice)`, `fijarSoloLectura`, `fijarSegmentos(segmentos)`, `estado()` y `destruir()`, que destruye también su editor. `resumen`, `soloVariable` y `controlMuestra` pasan al editor de adentro; en el constructor va `controlMuestra: false` y la pantalla fija la muestra con `editor.fijarMuestra`. `fijarSegmentos` es para cuando cambian el criterio o la tabla de rangos: conserva el segmento elegido si sigue existiendo y, si no, elige el primero; las variantes de segmentos que ya no están se conservan y las decide la pantalla (`variantesHuerfanas`); su `editor` es el controlador del `EditorTexto` de adentro, para `comprobarAntesDeGuardar` y `fijarMuestra`. `porDefecto` es la expresión propia de la columna, y `null` como segmento es «Por defecto». Emite `variantescambiadas` con `{ porDefecto, variantes, seleccionado, origen, pendiente, valida, problemas }`, donde `problemas` lleva el segmento de cada uno; el `expresioncambiada` del editor de adentro no sale de él. Al montar valida el contenido de cada segmento que no está en pantalla, para que todos muestren su estado.

Las dos piezas se prueban solas en `/pruebas/editor-texto`, una página que existe solo en el build de Playwright (`docs/testing.md`, sección 4).

**Uso en el constructor** (confirmaciones a `dev_frontend_herramientas_implementadas`, 2026-10-14):

- **Filas armadas en ejecución:** `<VariantesSegmento id="columna-editor">` dentro de un `<template>` de la página, clonado a la `.table__detalle` al expandir la fila, es el patrón esperado; no hace falta un `crearEditorTexto()`. Tres condiciones: una sola instancia a la vez (los `id` internos se fijan al compilar con el `id` de la raíz); `applyTranslations(fila)` sobre el clon antes de montar, porque el contenido de un `<template>` no recibe la pasada de idioma y sus textos estáticos están en español; y `destruir()` antes de cerrar la fila o reemplazarla.
- **Criterio «Valor de un campo»:** la lista de valores la mantiene la pantalla y la pasa con `fijarSegmentos`. `VariantesSegmento` no tiene «Agregar valor».
- **«Ir al problema» en una fila no montada:** expandir, montar y llamar `irAProblema(segmento, indice)`. Si el editor todavía no validó ese segmento, espera a su primera validación terminada y entonces enfoca. `indice` cuenta los problemas de ese segmento en el orden en que llegan en `variantescambiadas`.

### 9.3 Clientes y APIs falsas (D-2)

- **De `designer`:** `api-texto-enriquecido.ts` (catálogo, validación y previsualización) sobre `request` de `api.ts`, y `e2e/api-falsa-texto-enriquecido.ts`, tipada con el contrato.
- **De `dev_frontend_herramientas_implementadas`:** el cliente de `/definiciones-columnas` en `api-definiciones.ts`.
- **Cómo se componen las APIs falsas:** la mía exporta un manejador `manejarTextoEnriquecido(estado)` con la forma `(route, ruta, metodo, url) => Promise<boolean>`, que devuelve `true` si atendió la ruta. La suya hace lo mismo para sus rutas, y `montarApi` los encadena antes de responder 404.

### 9.4 Resumen de problemas (D-9)

**Un solo resumen por pantalla.**
- En el constructor, la pantalla muestra el resumen de toda la definición, con columna y segmento, y monta cada editor con `resumen: 'ninguno'`.
- «Ir al problema» abre la fila de la columna y el segmento, y llama a `irAProblema`.
- En el speech de MOWA MES vale lo mismo: el resumen de la pantalla nombra el segmento.
- Un editor suelto, sin pantalla que lo agregue, usa `resumen: 'propio'`.
- Nunca dos `role="alert"` a la vez.

### 9.5 Selectores compartidos (D-8)

- **`crearSelectorVariable` y `crearSelectorPatronFecha`** son míos, en `src/scripts/`, porque el editor los construye en tiempo de ejecución.
- **El constructor los reutiliza:** el selector de variable para la variable directa y el de patrón para el formato de fecha de la columna. No se arma una versión propia.
- **Opciones con valores sugeridos** (las del archivo en «Generar carga»: delimitador, codificación) usan el mismo selector de patrón: los sugeridos del backend, «Personalizado» para otro valor, y una `etiqueta` opcional por opción para un valor que no se lee solo («tabulación»; un carácter en blanco nunca se muestra).

### 9.6 Fila expandida, vacíos y esqueletos (D-6, D-10, D-12)

- **Fila expandida:** patrón compartido `.table__detalle` en `ui.css`.
  - Es una `tr` justo debajo de su fila, con una sola `td` que ocupa todas las columnas, fondo `--color-surface` y hairline.
  - El botón que la abre lleva `aria-expanded` y `aria-controls`, y su chevron rota.
  - Funciona dentro de `.table--apilable-ancha`.
- **Vista previa de la definición:** es de la pantalla. Usa `.marca-vacio`, de `ui.css`, para la marca de vacío; marca las celdas con problema con el icono `triangle-alert` y pone el detalle en su nombre accesible.
- **Vacíos y esqueletos:** se reutilizan `.empty`, `.empty__title`, `.skeleton` y `.standIn` de `ui.css`. No se copian de `console.css` ni de `mowa-mes.css`.

### 9.7 Navegación (D-5)

- **Ruta y título:** `/columnas`, con el título «Columnas de carga» y el patrón de encabezado de `/cartera`: `h1` más un párrafo de introducción. **Sin eyebrow:** el sistema no usa etiquetas sobre los títulos.
- **Una tercera sección, «Configuración»** (`nav.seccion.configuracion`), después de los canales, con el enlace «Columnas de carga» (`nav.columnas`). No va en el flujo diario porque no es un paso diario: es lo que se configura una vez y usan todas las cargas. Así queda la estructura que pidió el usuario para la navegación: `Cargas · Cartera | MOWA MES | Columnas de carga`.
- `designer` agrega la entrada **cuando la página exista en el árbol,** para no publicar un enlace que lleve a un 404.

### 9.8 Diccionarios y selección (D-7, D-11)

- **Orden de los bloques en `es.json` y `en.json`:** primero `textoEnriquecido.*`, que entra con B4a; después `columnas.*` y `mowaMes.speech.v2.*`, contiguos y al final. Nadie reformatea el bloque de otro.
- **Prueba espejo:** la del backend cubre todas las claves `textoEnriquecido.*`, no solo los códigos. Las de `columnas.*` y `mowaMes.speech.v2.*` no tienen espejo: las comprueban las pruebas de su pantalla.
- **«Cartera real»** monta `SelectorSeleccion` en modo compacto con el patrón de `campana.astro`: suscribirse a `seleccioncambiada` antes de montar. Dos diferencias:
  - el pedido de vista previa usa siempre cantidad 5, sea cual sea la cantidad de la selección;
  - recalcula con la misma espera de 500 ms y la misma cancelación que el editor.

## 10. Fase C3: decisiones del usuario del 2026-10-19

Experiencia fijada por `designer` antes de programar (T-MTE-F6 a F8), como en F3 y F5. Las decisiones están en `atomics-requirements.md` (RF-55, RF-56) y `requerimientos-mowa-mes.md` (RF-MM-17, RF-MM-27). El orden de trabajo es F7, F8 y F6.

### 10.1 Renombrar una definición guardada (F7, RF-56)

El nombre es de la definición, no de una versión: renombrar **no crea una versión** y no pasa por «Guardar». Por eso no se edita en el campo «Nombre». Si fuera editable ahí, quien lo cambia esperaría que «Guardar» lo guarde, y «Guardar» siempre crea una versión (5.1).

- **Junto al campo «Nombre»,** de solo lectura (con el estilo `.input[readonly]`), va un botón `.btn--sm` «Renombrar». Una definición nueva, todavía sin guardar, no lo tiene: su nombre se escribe en el campo, como hoy.
- **El hint del campo** pasa a «El nombre se cambia con Renombrar y no crea una versión».
- **Diálogo** (`dialog.dialog`, el patrón de confirmación de la pantalla):
  - **Título:** «Renombrar “SMS preventivo”».
  - **Campo:** «Nombre nuevo», con el nombre actual y el texto seleccionado. `maxlength` es el `largo_nombre_definicion` del catálogo.
  - **Hint:** «Las versiones y las cargas ya generadas no cambian».
  - **Acciones:** «Cancelar» (`.btn`) y «Renombrar» (`.btn--primary`, con `data-loading` mientras responde).
  - Si el nombre no cambió, después de quitar los espacios de los extremos, «Renombrar» queda inactivo: no hay nada que hacer. Es lo único que la interfaz decide sola. Un nombre vacío o demasiado largo lo rechaza el backend.
- **Nombre repetido (409, `nombre_repetido`):** el error va bajo el campo del diálogo, con `.field__error`, `aria-invalid` y `aria-describedby`. El diálogo sigue abierto, con lo escrito, y el foco vuelve al campo.
- **Al renombrar:** el diálogo se cierra y el nombre cambia en el campo y en el `select` de definiciones guardadas. El estado de la pantalla dice «Renombrada a “SMS preventivo B”» en su región `role="status"`, y el foco vuelve a «Renombrar».
- **Lo que no toca:** un borrador sin guardar sigue igual, y renombrar no pide confirmar cambios sin guardar. Una versión antigua abierta en solo lectura también se puede renombrar, porque el nombre no es de la versión.

### 10.2 Speech de MOWA MES solo v2 (F8, M3, RF-MM-17)

Pantalla de MOWA MES (`/mowa-mes/configuracion`): la revisa también `coordinador_modulo_mowa_mes`.

- **Solo v2 (RF-MM-17, decisión del usuario del 2026-10-30).** Las versiones de dos partes (v1), incluido el Speech original, se convirtieron a v2 en su lugar, con los mismos mensajes. Toda versión abre en el editor v2: ya no hay vista v1 ni «Convertir a v2» (T-MM-C11, M-F1). El Speech original lleva su propio aviso de candado; los avisos y la administración de versiones están en [mowa-mes-interfaz.md](mowa-mes-interfaz.md) §4.5.
- **El aviso del segmento con producto real** pasa a «Con un producto real de muestra, el segmento sale de sus días de atraso ajustados a hoy, como si el mensaje se enviara hoy; en la campaña se ajustan a su fecha de envío». La última parte evita que alguien crea que la campaña también usa hoy: MOWA MES conserva su regla de fecha de envío (RF-MM-15). Usa la misma idea de «hoy» que la vista previa de `/columnas` (10.3).
- **GSM-7 (RF-MM-27):** el largo y la vista previa vienen normalizados del backend.
  - **Hint fijo,** bajo el editor: «Al generar, se quitan las tildes, los signos que el SMS no admite se cambian por uno simple y los que no tienen equivalente se borran. La versión se guarda como la escribes». En inglés: «When generating, accents are removed, signs the SMS does not accept are replaced by a simple one, and those with no equivalent are deleted. The version is saved as you write it».
  - **Unidad del largo:** con la normalización, el largo se mide como lo cuenta el SMS: los signos que se cambian se cuentan ya cambiados («…» ocupa 3, como «...», y «€» también, como «EUR»). Desde el 2026-10-26, € [ ] { } \ ~ y | se transliteran y ^ se borra, así que ya no hay signos que ocupen 2. Se sigue diciendo «caracteres» en las etiquetas y los mensajes. El largo y la cota del editor en el contexto `mowa_mes.speech` usan la misma unidad, para que la pantalla no muestre dos largos distintos; en `/columnas` no cambia nada (decisión de `coordinador_modulo_mowa_mes`, 2026-10-22, dentro de T-MM-B9).
  - **Entra con la normalización, no antes:** la pantalla no promete lo que la generación todavía no hace. El hint y la línea de borrados los implementa T-MM-F7, sobre B16 y T-MM-B9, y no F8 (acuerdo de los dos coordinadores, 2026-10-20).
  - **Lo que se cambia por uno simple no se señala,** igual que las tildes. El usuario decidió transliterar (RF-MM-27, 2026-10-19): “ ” « » pasan a ", ‘ ’ a ', … a ..., – y — a -, ° y º a o, y ª a a. Se sigue leyendo igual.
  - **Lo que se borra sí se señala,** porque desaparece sin que se note en la vista previa: un emoji o un signo sin equivalente. El backend devuelve, por segmento, los caracteres que se borran, sin repetir, en el orden en que aparecen y con su punto de código (T-MM-B9).
  - **Una línea por segmento, solo cuando hay borrados:** «Al enviar se borran: 👍🏽 · ✓ · espacio de ancho cero U+200B». En inglés: «Deleted when sent: 👍🏽 · ✓ · zero-width space U+200B».
    - Cada elemento es un grafema completo de lo que se borra (un emoji con su tono de piel o una familia unida con ZWJ sale una vez, entero). Si en un grafema se conserva una parte, solo llega la que se borra (T-MM-B9).
    - Los elementos van separados por « · ». Uno visible va en mono. Uno que no se ve va por su nombre, en texto normal, seguido de su punto de código en mono.
    - Invisibles con nombre (es / en): U+200B espacio de ancho cero / zero-width space; U+200C no unión de ancho cero / zero-width non-joiner; U+200D unión de ancho cero / zero-width joiner; U+2060 unión de palabras / word joiner; U+00AD guion suave / soft hyphen; U+FEFF marca de orden de bytes / byte order mark; U+200E marca de izquierda a derecha / left-to-right mark; U+200F marca de derecha a izquierda / right-to-left mark; U+2028 separador de línea / line separator; U+2029 separador de párrafo / paragraph separator; U+000B tabulación vertical / vertical tab.
    - Cualquier otro sin parte visible (todos sus puntos de categoría Mn, Me, Cf, Cc o Zs, como «U+FE0F U+20E3» de un keycap) va como «carácter invisible U+XXXX» / «invisible character U+XXXX», con todos sus puntos.
    - No se marcan dentro del texto y la línea no bloquea guardar.
    - Lleva el icono `triangle-alert` y el color de advertencia, para no depender solo del color.
    - Es un `.notice--warning` de una línea, bajo el editor, para el segmento en pantalla.

### 10.3 Fecha de envío (F6, RF-55)

- **En `/generar-carga`,** el campo «Fecha de envío» va en el panel «Selección», justo después del selector, porque se lee junto a la fecha de corte.
  - Es un `input type="date"`.
  - **Por defecto, hoy en la hora de Lima** (`America/Lima`), nunca la fecha UTC: de noche, UTC ya es el día siguiente.
  - `min` es la fecha de corte elegida. Así el selector de fecha no ofrece una fecha imposible (principio 3: prevenir antes que reportar). La regla es del backend y está documentada en RF-55.
  - **Hint:** «Los días de atraso se cuentan hasta esta fecha para calcular el segmento. Por defecto, hoy».
  - **400 del backend** (envío anterior al corte): el error va bajo el campo y nombra las dos fechas: «La fecha de envío (18 oct. 2026) es anterior a la fecha de corte (19 oct. 2026)». Lo escrito se conserva.
  - Cambiar la fecha de envío recalcula la vista previa con la misma espera y cancelación que el resto de la pantalla.
- **Visible en la vista previa de `/generar-carga`:** sobre la tabla, una línea: «Fecha de envío: 21 oct. 2026, 2 días después del corte».
  - Con 1 día, «1 día después del corte»; con 0, «el mismo día del corte». En inglés: «Send date: Oct 21, 2026, {n} days after the cut-off», «1 day after the cut-off» y «the same day as the cut-off».
  - La página manda siempre la fecha explícita (hoy en Lima, calculado en el navegador), para que lo que se ve sea lo que se genera.
  - La línea junto al botón la suma: «Se generarán N filas en XLSX con la versión V de “SMS preventivo”, para enviar el 21 oct. 2026».
  - Las fechas se escriben con `format.ts`, como en el resto del sitio.
- **Visible en la vista previa de `/columnas`:** ahí no se elige, así que es hoy. Bajo el título de la vista previa va un `.field__hint`: «Segmentos calculados con los días de atraso a hoy, 19 oct. 2026, como si se enviara hoy».
  - Solo con «Cartera real», cuando la respuesta trae `fecha_envio`. Con ejemplos, cada fila ya es un segmento: no se calculan días y no hay hint.
- **Aviso breve en `/columnas`** cuando la versión abierta segmenta sin el ajuste a la fecha de envío. Es una red de seguridad: hoy no hay ninguna versión así.
  - Una versión guardada no se reinterpreta: la que segmenta con `dias_atraso` se genera sin ajuste, y solo las versiones nuevas usan `dias_atraso_ajustados` por defecto (D-C3-1, architec).
  - Va en el panel «Definición», bajo la línea de versión, como `.notice--info` de una sola frase, sin acciones: «Esta versión calcula los segmentos con los días de atraso de la sábana, sin ajustarlos a la fecha de envío. Para usar el ajuste, guarda una versión nueva».
  - No bloquea guardar ni generar.

### 10.4 Pruebas mínimas de C3

- **F7:** abrir el diálogo, renombrar y ver el nombre nuevo en el campo y en la lista; el 409 bajo el campo, con el diálogo abierto; «Renombrar» inactivo sin cambios; el cuerpo enviado no crea una versión; renombrar desde una versión antigua; axe con el diálogo abierto, en claro y oscuro.
- **F8:** el aviso nuevo del segmento. (La v1 en solo lectura y «Convertir a v2» se probaron hasta que M-F1 los quitó.) En T-MM-F7: el hint de GSM-7 bajo el editor, y la línea de caracteres borrados, que aparece solo con borrados, sin repetir, y no bloquea guardar.
- **F6:** la fecha por defecto, con el reloj fijado en la noche de Lima, cuando UTC ya es el día siguiente; `min` sigue a la fecha de corte; el 400 bajo el campo con las dos fechas; la fecha de envío en la vista previa y en la línea del botón; la nota de «hoy» en `/columnas`; axe en `/generar-carga` con el error de fecha.

## 11. Etiqueta, plataforma y textos guardados (T-HI-F1 y T-HI-F2, 2026-11-02)

Reglas de `designer` para las herramientas compartidas del plan WhatsMKT v2: RF-49 ampliado (etiqueta), RF-72 (definiciones con plataforma), RF-73 (celda de texto) y RF-69 (textos guardados). Las implementa `dev_frontend_herramientas_implementadas` y las aprueba `designer` con capturas a 1280 y 360 px, en es y en.

Lo propio de cada plataforma (qué columnas fija y cómo se llaman) lo declara su módulo, y llega en `GET /definiciones-columnas/plataformas`. La pantalla lo lee de ahí y no lo escribe en el código.

### 11.1 Etiqueta de la columna (RF-49)

- **En la fila expandida,** debajo de «Nombre», un `input` opcional «Etiqueta», de hasta 120 caracteres. Hint: «Un nombre para reconocer la columna, por ejemplo «Nombres del titular». No sale en el archivo».
- **En la lista de columnas,** si la columna tiene etiqueta, va debajo del nombre, en una segunda línea `.field__hint` sin `mono`. Sin etiqueta no se agrega nada. La columna «Nombre» de la tabla sigue mostrando el encabezado del archivo, que es lo que importa al leerla.
- **En los editores que ofrecen la columna,** como el editor del mensaje de WhatsMKT (RF-WM-27): «MACRO2 · Vencimiento de la cuota». Sin etiqueta, solo el nombre.
- Una versión guardada sin etiquetas se lee igual, sin aviso ni marca.

### 11.2 Definición con plataforma (RF-72)

- **Al crear,** «Nueva definición» pide, además del nombre, la **Plataforma**: un `select` con «Ninguna (archivo libre)», que es la opción por defecto, y una opción por plataforma registrada, por su etiqueta («WhatsMKT», «MOWA MES»). Hint: «Una plataforma fija algunas columnas y no se cambia después».
  - Una definición que se crea desde un canal con ir y volver (por ejemplo, desde la campaña de WhatsMKT) llega con la plataforma ya elegida, y el `select` queda inactivo con su valor.
- **Después de crear,** la plataforma se muestra en la línea de versión, como un `.tag tag--info` con su etiqueta: «Versión 3 · WhatsMKT». No se edita (supuesto de RF-72).
- **Las reglas, a la vista.** Con plataforma, bajo el encabezado de la definición, va un `.notice--info` de una sola frase, que la pantalla arma desde las reglas registradas:
  - «WhatsMKT: la 1.ª columna, «número», es fija; las siguientes se llaman por su posición, [$MARCRO1$], [$MARCRO2$]…, y son de texto». Las partes salen de `columnas_fijas`, `encabezado_por_posicion` y `tipo_resto`.
  - Si `admite_mas_columnas` es falso, se agrega «… y no se agregan más columnas».
  - No hay reglas escondidas: lo que la pantalla no deja hacer, lo dice esta frase.
- **Columna fija** (`columnas_fijas`):
  - En su fila, en lugar de «Quitar» y de las flechas de orden, va un icono `lock`, con `title` y nombre accesible: «Columna fija de WhatsMKT: no se quita ni se mueve». Esos botones no se muestran inactivos: no se ofrecen.
  - El nombre es de solo lectura (`.input[readonly]`).
  - El tipo queda fijo: el `select`, inactivo, con su valor.
  - El contenido se edita si `contenido_editable` es verdadero, y arranca en `contenido_por_defecto` (por ejemplo, `51[@telefono]`).
  - Con `celda_texto`, el resumen del formato dice «Texto de Excel» (RF-73).
  - Ninguna columna puede ponerse delante de una fija: «Subir» queda inactivo en la primera fila que no es fija.
- **Encabezado por posición** (`encabezado_por_posicion`, por ejemplo `[$MARCRO{n}$]`):
  - Una columna nueva nace con el encabezado de su posición.
  - **Al mover una columna,** las que todavía tienen su encabezado por defecto se renumeran según su nueva posición. Las que el analista renombró conservan su nombre.
  - **Si un encabezado editado ya no coincide con su posición,** un `.field__hint` en la fila lo dice: «WhatsMKT toma las columnas por su orden, no por su nombre: esta es la macro 3». La macro sale de la posición, no del nombre (RF-WM-11). Es un aviso, no un problema: el patrón es solo el valor por defecto, y la definición se guarda igual.
  - Junto al nombre, «Restaurar» (`.btn--sm .btn--quiet`) le devuelve el encabezado de su posición. Solo aparece si el nombre es distinto del de su posición.
- **Tipo del resto** (`tipo_resto`): el `select` de tipo queda inactivo con ese tipo, y el hint de la fila dice «En WhatsMKT las macros son siempre texto: el valor sale ya formateado».
- **Problemas de la plataforma:** la validación los devuelve con su columna y su regla (B2), y se muestran bajo la columna como cualquier otro problema (§4), con el texto de su código. Con un problema de plataforma no se guarda.
- **Cambiar de plataforma antes de guardar** (solo en una definición nueva): si ya hay algo escrito, un diálogo lo confirma, porque se borran **todas** las columnas, también las no fijas. Quedan las que fija la plataforma elegida o, al pasar a «Ninguna (archivo libre)», una columna vacía. El nombre, la protección de fórmulas y la segmentación se conservan. Sin nada escrito, cambia sin preguntar. El botón de confirmar es `.btn--danger`.
- **Plataforma que ya no existe:** si la definición guardada declara una plataforma que no está registrada, el tag dice «Plataforma desconocida: {clave}», en `tag--advertencia`, y el problema de la validación va arriba, en el resumen (§9.4). La definición se lee y se genera como está.
- **A 360 px** la tabla se apila (`.table--apilable-ancha`), y el candado de una columna fija ocupa el lugar de las acciones, con su texto visible: «Columna fija».

### 11.3 Textos guardados (RF-69)

Un componente reutilizable, `TextosGuardados`, para administrar los textos de un contexto. El primero en usarlo es WhatsMKT, con `whatsmkt.mensaje` ([whatsmkt-interfaz.md](whatsmkt-interfaz.md)). Sigue el patrón de la administración del speech de MOWA MES ([mowa-mes-interfaz.md](mowa-mes-interfaz.md) §4.5), que no migra a esta capacidad.

```ts
const textos = montarTextosGuardados(raiz, {
  contexto: 'whatsmkt.mensaje',
  editor,            // cómo se edita el contenido: lo pone el módulo (un textarea, un EditorTexto…)
  titulo,            // por ejemplo, «Mensajes globales»
});
textos.destruir();
```

- **Estructura,** dentro de un `.panel`:
  - Un `select` «Texto», con los habilitados por su nombre. Si el contexto agrega algo propio, como el segmento, se muestra con el nombre: «Preventivo · versión 2».
  - Al lado, «Nuevo» (`plus`) y las acciones del elegido: «Renombrar» (`pencil`), «Deshabilitar» (`power-off`) y «Eliminar» (`trash-2`, rojo). «Eliminar» solo aparece si ninguna versión se usó. Si alguna se usó, en su lugar va el motivo: «No se puede eliminar: ya se usó. Puedes deshabilitarlo». El texto es genérico: el componente no sabe qué usa el contexto.
  - La línea de versión, «Versión 3» o «Versión 3 · usada en 2 campañas», con un `select` de las versiones anteriores para verlas en solo lectura, como en §5.1.
  - El editor, que pone el módulo.
  - El pie, con «Guardar» (`save`, `.btn--primary`) y «Descartar cambios». Las versiones no tienen nombre propio. Bajo «Guardar» va el hint de siempre: «Al guardar se crea la versión 4; la 3 no cambia».
- **Nuevo:** abre el editor vacío, con un campo «Nombre» arriba. Al guardar se crea el texto con su versión 1.
- **Renombrar:** el diálogo de §10.1, con «Nombre nuevo» y el error de nombre repetido bajo el campo. No crea una versión.
- **Deshabilitados:** bajo el panel, un `<details>` cerrado, «Deshabilitados (N)», que con cero no se muestra. Cada uno lleva su nombre, un `.tag tag--neutral` «Deshabilitado» (`power-off`), «Ver» (en solo lectura), «Habilitar» (`power`) y, si se puede, «Eliminar». Es el patrón de MOWA MES §4.5.
- **Cambios sin guardar:** cambiar de texto o de versión, o salir, pide confirmar con el diálogo de siempre del selector: «Hay cambios sin guardar», «Los cambios que no guardaste se pierden» y «Descartar cambios».
- **Problemas del contenido:** los devuelve el validador del contexto y van bajo el editor, por su código, con los textos del módulo dueño del contexto.
- **Accesibilidad:**
  - El `select` y los botones llevan nombres con el texto elegido: «Renombrar «Preventivo»».
  - Cada resultado (guardado, renombrado, deshabilitado, habilitado o eliminado) se anuncia en la región `role="status"` del panel.
  - El foco vuelve al control que pidió la acción o, si desapareció, al `select`.

### 11.4 Textos (es / en)

| Clave | es | en |
|---|---|---|
| `columnas.etiqueta` | Etiqueta | Label |
| `columnas.etiqueta.hint` | Un nombre para reconocer la columna, por ejemplo «Nombres del titular». No sale en el archivo. | A name to recognise the column, for example “Holder's first names”. It does not go into the file. |
| `columnas.plataforma` | Plataforma | Platform |
| `columnas.plataforma.ninguna` | Ninguna (archivo libre) | None (free file) |
| `columnas.plataforma.hint` | Una plataforma fija algunas columnas y no se cambia después. | A platform fixes some columns and cannot be changed later. |
| `columnas.plataforma.desconocida` | Plataforma desconocida: {clave} | Unknown platform: {clave} |
| `columnas.plataforma.fija` | Columna fija de {plataforma}: no se quita ni se mueve. | Fixed {plataforma} column: it cannot be removed or moved. |
| `columnas.plataforma.fijaCorta` | Columna fija | Fixed column |
| `columnas.plataforma.reglas.fijas` | la {posicion}.ª columna, «{nombre}», es fija | column {posicion}, “{nombre}”, is fixed |
| `columnas.plataforma.reglas.posicion` | las siguientes se llaman por su posición, {ejemplo}… | the next ones are named by position, {ejemplo}… |
| `columnas.plataforma.reglas.tipo` | y son de {tipo} | and are {tipo} |
| `columnas.plataforma.reglas.sinMas` | y no se agregan más columnas | and no more columns can be added |
| `columnas.plataforma.porPosicion` | {plataforma} toma las columnas por su orden, no por su nombre: esta es la macro {n}. | {plataforma} takes the columns by order, not by name: this is macro {n}. |
| `columnas.plataforma.restaurar` | Restaurar | Restore |
| `columnas.plataforma.restaurarPara` | Restaurar el encabezado de la columna {n} | Restore the header of column {n} |
| `columnas.plataforma.cambiar.titulo` | Cambiar la plataforma | Change the platform |
| `columnas.plataforma.cambiar.cuerpo` | Se borran las columnas que escribiste y quedan solo las que fija {plataforma}. El nombre y las opciones de la definición no cambian. | The columns you wrote are deleted, and only the ones {plataforma} fixes remain. The definition's name and options do not change. |
| `columnas.plataforma.cambiar.cuerpoLibre` | Se borran las columnas que escribiste y queda una columna vacía. El nombre y las opciones de la definición no cambian. | The columns you wrote are deleted and one empty column remains. The definition's name and options do not change. |
| `columnas.plataforma.cambiar.confirmar` | Cambiar plataforma | Change platform |
| `columnas.plataforma.tipoFijo` | En {plataforma} las macros son siempre texto: el valor sale ya formateado. | In {plataforma} macros are always text: the value goes out already formatted. |
| `columnas.formato.celdaTexto` | Texto de Excel | Excel text |
| `textosGuardados.texto` | Texto | Text |
| `textosGuardados.nuevo` | Nuevo | New |
| `textosGuardados.nombre` | Nombre | Name |
| `textosGuardados.version` | Versión {n} | Version {n} |
| `textosGuardados.versionUsada` | Versión {n} · usada en {usos} campañas | Version {n} · used in {usos} campaigns |
| `textosGuardados.versionUsadaUna` | Versión {n} · usada en 1 campaña | Version {n} · used in 1 campaign |
| `textosGuardados.guardarHint` | Al guardar se crea la versión {nueva}; la {actual} no cambia. | Saving creates version {nueva}; version {actual} does not change. |
| `textosGuardados.guardarHintPrimera` | Al guardar se crea la versión 1. | Saving creates version 1. |
| `textosGuardados.renombrarPara` | Renombrar «{nombre}» | Rename “{nombre}” |
| `textosGuardados.deshabilitarPara` | Deshabilitar «{nombre}» | Disable “{nombre}” |
| `textosGuardados.habilitarPara` | Habilitar «{nombre}» | Enable “{nombre}” |
| `textosGuardados.eliminarPara` | Eliminar «{nombre}» | Delete “{nombre}” |
| `textosGuardados.noEliminable` | No se puede eliminar: ya se usó. Puedes deshabilitarlo. | It cannot be deleted: it has been used. You can disable it. |
| `textosGuardados.noEliminableDeshabilitado` | No se puede eliminar: ya se usó. | It cannot be deleted: it has been used. |
| `textosGuardados.renombrar` | Renombrar | Rename |
| `textosGuardados.deshabilitar` | Deshabilitar | Disable |
| `textosGuardados.habilitar` | Habilitar | Enable |
| `textosGuardados.eliminar` | Eliminar | Delete |
| `textosGuardados.ver` | Ver | View |
| `textosGuardados.verPara` | Ver «{nombre}» | View “{nombre}” |
| `textosGuardados.guardar` | Guardar | Save |
| `textosGuardados.descartar` | Descartar cambios | Discard changes |
| `textosGuardados.sinGuardar` | Sin guardar: texto nuevo | Unsaved: new text |
| `textosGuardados.versionVer` | Ver otra versión | View another version |
| `textosGuardados.versionOpcion` | Versión {n} | Version {n} |
| `textosGuardados.versionOpcionVigente` | Versión {n} (vigente) | Version {n} (current) |
| `textosGuardados.versionUsadaSin` | Versión {n} · usada | Version {n} · used |
| `textosGuardados.lectura` | Estás viendo la versión {vista}, solo para leer. La vigente es la {vigente}. | You are viewing version {vista}, read only. The current one is {vigente}. |
| `textosGuardados.irVigente` | Ir a la vigente | Go to the current one |
| `textosGuardados.usarBase` | Usar como base | Use as a base |
| `textosGuardados.guardarHintBase` | Al guardar se crea la versión {nueva} con el contenido de la {base}. | Saving creates version {nueva} with the content of version {base}. |
| `textosGuardados.deshabilitadoVer` | Este texto está deshabilitado: se ve solo para leer y no admite versiones nuevas. Para editarlo, habilítalo. | This text is disabled: it is read only and takes no new versions. To edit it, enable it. |
| `textosGuardados.renombrarTitulo` | Renombrar {nombreCitado} | Rename {nombreCitado} |
| `textosGuardados.renombrarCampo` | Nombre nuevo | New name |
| `textosGuardados.renombrarConfirmar` | Renombrar | Rename |
| `textosGuardados.nombreInvalido` | Escribe un nombre de 1 a {max} caracteres. | Enter a name of 1 to {max} characters. |
| `textosGuardados.eliminarTitulo` | Eliminar definitivamente {nombreCitado} | Delete {nombreCitado} permanently |
| `textosGuardados.eliminarCuerpo` | Se borran el texto y todas sus versiones. No se puede deshacer. | The text and all its versions are deleted. This cannot be undone. |
| `textosGuardados.eliminarCasilla` | Entiendo que no se puede deshacer | I understand this cannot be undone |
| `textosGuardados.eliminarBoton` | Eliminar definitivamente | Delete permanently |
| `textosGuardados.errorCarga` | No se pudieron cargar los textos guardados. | The saved texts could not be loaded. |
| `textosGuardados.deshabilitados` | Deshabilitados ({n}) | Disabled ({n}) |
| `textosGuardados.deshabilitado` | Deshabilitado | Disabled |
| `textosGuardados.guardado` | Se guardó la versión {n} de «{nombre}». | Version {n} of “{nombre}” was saved. |
| `textosGuardados.creado` | Se creó «{nombre}». | “{nombre}” was created. |
| `textosGuardados.renombrado` | Renombrado a «{nombre}». | Renamed to “{nombre}”. |
| `textosGuardados.deshabilitadoAviso` | Se deshabilitó «{nombre}». Ya no se ofrece para lo nuevo. | “{nombre}” was disabled. It is no longer offered for new items. |
| `textosGuardados.habilitado` | Se habilitó «{nombre}». | “{nombre}” was enabled. |
| `textosGuardados.eliminado` | Se eliminó «{nombre}». | “{nombre}” was deleted. |
| `textosGuardados.nombreRepetido` | Ya existe un texto con ese nombre. Elige otro. | A text with that name already exists. Choose another one. |

- Los nombres de citas usan las comillas del idioma, con `camposAdicionales.nombreCitado`: `{nombreCitado}` es ese resultado, nunca comillas escritas en la clave.
- **Se reusan, no se copian:** el diálogo de cambios sin guardar usa `selector.descartar.titulo`, `.cuerpo`, `.mantener` («Seguir editando») y `.confirmar`; el componente no crea claves `cambios.*`. La casilla de eliminar sí es propia (`eliminarCasilla`, con el texto de MOWA), para no depender de una clave `mowaMes.*` desde un componente compartido.
- `errorCarga` va con «Reintentar» (`selector.valores.reintentar`), que vuelve a pedir la lista.
- «campañas» en `versionUsada` es lo que usa WhatsMKT, el primer contexto. Si otro contexto cuenta otra cosa, el contexto pasa su propio texto.
- La confirmación de eliminar usa §4.6 de [mowa-mes-interfaz.md](mowa-mes-interfaz.md), con la casilla obligatoria. El título y el cuerpo los pone cada contexto: los de WhatsMKT están en su documento.

### 11.5 Pruebas mínimas

- **T-HI-F1:**
  - la etiqueta se guarda, se ve bajo el nombre y en el editor que ofrece la columna, y una versión sin etiquetas se lee igual;
  - la plataforma se elige al crear, aparece como tag en la línea de versión, y la frase de reglas se arma desde `GET /definiciones-columnas/plataformas`;
  - una columna fija no se quita ni se mueve, lleva su candado, y tiene el nombre de solo lectura y el tipo fijo;
  - los encabezados por posición se renumeran al mover, uno editado se conserva con su hint, y «Restaurar» lo devuelve a su posición;
  - un problema de plataforma va bajo su columna y bloquea guardar, y una plataforma desconocida se lee y se marca;
  - sin plataforma, todo igual que hoy;
  - axe en claro, oscuro y 360 px, con una definición WhatsMKT abierta.
- **T-HI-F2:**
  - crear, guardar una versión y ver una anterior en solo lectura;
  - renombrar, con el error de nombre repetido;
  - deshabilitar y habilitar;
  - eliminar con la casilla, y el motivo cuando no se puede;
  - la confirmación de cambios sin guardar;
  - axe en claro, oscuro y 360 px.

## 12. Ir y volver desde un canal (T-HI-F3, 2026-11-03)

Columnas de carga, Supervisores y Calendario laboral se abren desde un canal (MOWA MES o WhatsMKT) y devuelven al analista a donde estaba. Es la regla de «Editar en Cartera» ([mowa-mes-interfaz.md](mowa-mes-interfaz.md) §4.7), generalizada; [whatsmkt-interfaz.md](whatsmkt-interfaz.md) §2 la usa.

### 12.1 `volver`

- **Qué acepta:** la ruta de la pantalla de origen, con su consulta, validada con `volverValido` de `src/lib/volver.ts`. Los prefijos válidos pasan a ser `/mowa-mes/` y `/whatsmkt/`, y la validación sigue igual: mismo origen, ruta ya normalizada, nada que empiece con `//`. Un `volver` inválido se ignora como si no hubiera llegado: la herramienta se abre normal, sin aviso.
- **El canal sale del prefijo,** con las claves de la barra que ya existen: `/mowa-mes/` es `nav.mowaMes` («MOWA MES») y `/whatsmkt/` es `nav.whatsmkt` («WhatsMKT»). No hay una clave nueva por canal: un canal nuevo agrega su prefijo y su clave de la barra.
- **El estado de la pantalla de origen** viaja en su propio `volver` (su consulta), como hace la campaña de MOWA con Cartera. La herramienta no lo lee ni lo cambia: solo agrega lo suyo al volver.

### 12.2 El aviso

Un `.notice--info` bajo el encabezado de la página y antes de todo lo demás, con una línea y un enlace `.btn--sm` con `chevron-left`. Es el mismo marcado de `/cartera` (`data-volver`, `data-volver-enlace`).

| Herramienta | Línea | Enlace |
|---|---|---|
| Columnas de carga, definición abierta | `herramientas.volver.columnas` | `herramientas.volver.sinGuardar` |
| Columnas de carga, definición nueva con plataforma | `herramientas.volver.columnasNueva` | `herramientas.volver.sinGuardar` |
| Supervisores | `herramientas.volver.supervisores` | `herramientas.volver.volver` |
| Calendario laboral | `herramientas.volver.alMomento` | `herramientas.volver.volver` |

- **Con cambios sin guardar,** «Volver a {canal} sin guardar» pasa por la confirmación de siempre del selector (`selector.descartar.*`, con «Seguir editando»). Nada se pierde sin aviso.
- **«Volver sin guardar»** vuelve a `volver` tal como llegó, sin agregar nada.

### 12.3 Al guardar

- **Columnas de carga:** al guardar (una versión nueva o una definición nueva), vuelve sola a `volver` con `definicion=<id>&version=<n>`, que reemplazan a los que hubiera. El estado anuncia lo guardado antes de irse, como en Cartera. Renombrar no vuelve: no es el guardado de la definición.
- **Calendario laboral:** no vuelve solo. Cada cambio se guarda al hacerlo (agregar, quitar, retirar o restaurar), así que no hay un «guardado» que devolver. Se vuelve solo con el enlace, que por eso dice «Volver a {canal}», sin «sin guardar».
- **Supervisores:** tiene su «Guardar supervisores», con borrador. Al guardar **no** vuelve sola: no hay nada que devolver, y el analista puede seguir ajustando. El enlace dice «Volver a {canal}» y, si hay un borrador sin guardar, pasa antes por la confirmación de siempre (`selector.descartar.*`, con «Seguir editando»), igual que Columnas. Sin borrador vuelve directo.
- En los dos casos la pantalla de origen lee de nuevo supervisores y calendario al cargarse, así que ve lo guardado.
- **Los parámetros de Columnas** se arman con un ayudante en `volver.ts`, del estilo de `destinoConSeleccion`: `destinoConDefinicion(destino, id, version)` y `destinoSinDefinicion(destino)`. Se leen con `definicionDeLaUrl(busqueda)`, que devuelve `{id, version}` o `null` si falta alguno o no es un entero positivo.

### 12.4 En la pantalla de origen

- **Con `definicion` y `version` válidos,** el `select` de la definición queda en esa versión, y el estado lo anuncia: «Se eligió {nombre}, versión {n}».
- **Si la definición ya no es de la plataforma del canal** (se abrió una libre, por ejemplo), el `select` queda sin elegir y va el error del canal bajo él; en WhatsMKT, `definicion_no_whatsmkt`.
- **Si la definición o la versión ya no existen,** un `.notice--warning` bajo el `select`, como el de Cartera: `herramientas.volver.noExiste`. El `select` queda sin elegir y el aviso se va al elegir otra.
- Después de leerlos, la pantalla quita `definicion` y `version` de la URL (`history.replaceState`), para que recargar no vuelva a aplicarlos.

### 12.5 Columnas de carga con `?definicion=` o `?plataforma=`

- **`?definicion=<id>`:** abre esa definición en su versión vigente. Si no existe, el constructor queda en «Sin guardar: definición nueva» con un `.notice--warning`: `herramientas.volver.definicionNoExiste`. Nunca un error.
- **`?plataforma=<clave>`:** abre una definición nueva con esa plataforma ya elegida. El `select` de plataforma queda inactivo con el hint `columnas.plataforma.fijadaPor`. No sale el diálogo de cambiar de plataforma, porque no se puede cambiar. Una clave que no está registrada se ignora y el `select` queda libre.
- Si llegan los dos, gana `definicion`.
- **`?plataforma=` sin un `volver` válido** preelige la plataforma pero no la fija: el `select` queda activo y sin el hint, que necesita el canal.
- Columnas no limpia `?definicion=` ni `?plataforma=` de la URL: recargar vuelve a abrir lo mismo, y eso es lo esperable.

### 12.6 Textos (es / en)

| Clave | es | en |
|---|---|---|
| `herramientas.volver.columnas` | Estás editando una definición de columnas desde {canal}. Al guardarla, vuelves a {canal}. | You are editing a column definition from {canal}. Once you save it, you go back to {canal}. |
| `herramientas.volver.columnasNueva` | Estás creando una definición de {plataforma}. Al guardarla, vuelves a {canal}. | You are creating a {plataforma} definition. Once you save it, you go back to {canal}. |
| `herramientas.volver.alMomento` | Llegaste desde {canal}. Cada cambio se guarda al hacerlo; cuando termines, vuelve. | You came from {canal}. Each change is saved as you make it; when you are done, go back. |
| `herramientas.volver.supervisores` | Llegaste desde {canal}. Guarda los supervisores antes de volver: lo que no guardes se pierde. | You came from {canal}. Save the supervisors before going back: anything you do not save is lost. |
| `herramientas.volver.sinGuardar` | Volver a {canal} sin guardar | Back to {canal} without saving |
| `herramientas.volver.volver` | Volver a {canal} | Back to {canal} |
| `herramientas.volver.elegida` | Se eligió {nombre}, versión {n}. | {nombre}, version {n}, was chosen. |
| `herramientas.volver.noExiste` | La definición que editaste ya no existe. Elige otra. | The definition you edited no longer exists. Choose another one. |
| `herramientas.volver.definicionNoExiste` | La definición que abriste ya no existe. Arma una nueva o elige otra de la lista. | The definition you opened no longer exists. Build a new one or choose another from the list. |
| `supervisores.intro` | Los supervisores que se asignan por defecto a cada campaña, en todos los canales. | The supervisors assigned by default to each campaign, in every channel. |
| `columnas.plataforma.fijadaPor` | La fija {canal}: se abrió desde allí. | Set by {canal}: it was opened from there. |

- `{nombre}` va citado con `camposAdicionales.nombreCitado`.
- `columnasNueva` no repite «desde {canal}»: con la plataforma del mismo canal se leería «una definición de WhatsMKT desde WhatsMKT».
- `supervisores.intro` deja de nombrar solo a MOWA MES, como pide [modules.md](modules.md): WhatsMKT usa los mismos supervisores.
- **El aviso a 360 px:** el icono queda a la izquierda, y el texto con su enlace van juntos en la columna del cuerpo, como en el aviso de lectura de `TextosGuardados`. El enlace no es hermano del icono.
- **`/cartera` también recibe `volver` de los dos canales** (WhatsMKT la usa desde su campaña, T-WM-F2a1). Su aviso conserva sus claves, `cartera.volver.*`, pero el texto lleva `{canal}`, que sale del prefijo con las mismas claves de la barra que §12.1. Los textos están en [mowa-mes-interfaz.md](mowa-mes-interfaz.md) §5. El enlace sigue diciendo «Volver a la campaña sin guardar»: en los dos canales vuelve a una campaña.

### 12.7 Pruebas mínimas

- `volverValido` acepta `/whatsmkt/…` y sigue rechazando `//`, otro origen, `javascript:` y rutas que salen del prefijo al normalizarse.
- Cada herramienta con un `volver` válido muestra su aviso y su enlace, y con uno inválido no muestra nada.
- Columnas: guardar vuelve con `definicion` y `version`; «Volver sin guardar» con cambios pide confirmar; `?plataforma=` deja el `select` inactivo con su hint; `?definicion=` de una que no existe muestra su aviso.
- Calendario: un cambio no navega; el enlace vuelve.
- Supervisores: guardar no navega; el enlace con borrador pide confirmar y, sin borrador, vuelve directo.
- La pantalla de origen elige la definición que llega, avisa si ya no existe o no es del canal, y limpia la URL.
- axe en claro, oscuro y 360 px, con el aviso a la vista en las tres herramientas.

### 12.8 Capturas para `designer`

En es y claro, salvo donde se indica:

1. Columnas con `?volver=` y `?definicion=` (definición abierta, con el aviso), a 1280 y a 360.
2. Columnas con `?volver=` y `?plataforma=whatsmkt` (definición nueva, con el `select` inactivo y su hint), a 1280.
3. El diálogo de cambios sin guardar al pulsar «Volver sin guardar», a 1280.
4. Supervisores con `?volver=`, a 360.
5. Calendario laboral con `?volver=`, en inglés, a 1280.
6. La configuración de WhatsMKT recién vuelta de Columnas, con la definición elegida y su anuncio, a 1280.

## 13. Fase A: el editor común mejorado (2026-11-04)

El usuario eligió la opción 2 del diagnóstico del motor, por fases. Esta es la fase A: mejorar el editor que ya comparten Columnas de carga y el speech de MOWA MES, para que sea cómodo, y dejarlo listo para que WhatsMKT lo use. La fase B (variables con función en el mensaje de WhatsMKT, que crean o reusan columnas, el tope de 5 macros y las columnas compartidas) tiene su propia especificación.

Las reglas de §2 a §5 y §9 siguen valiendo; esta sección cambia solo lo que dice.

### 13.1 Cortes

| Corte | Qué | Dónde |
|---|---|---|
| **A1** | 13.2 a 13.5: el disparador, el buscador por tema, las funciones con su ejemplo y las píldoras | Solo el motor (`editor-texto.ts`, `selector-variable.ts` y su CSS). Columnas y MOWA lo heredan sin tocar sus páginas. Los temas son un dato nuevo de la variable en el catálogo (backend). |
| **A2** | 13.6: contador y patrón de error únicos | El motor, más las páginas de MOWA (contador GSM-7) y WhatsMKT (lista de errores del mensaje). **Toca pantallas de MOWA y WhatsMKT.** |
| **A3** | 13.7: WhatsMKT usa el editor común para su mensaje | La configuración y la campaña de WhatsMKT. **Toca pantallas de WhatsMKT.** Puede ir antes de la fase B. |

A1 no depende de nada. A2 y A3 van después de A1.

### 13.2 El disparador `[@` (A1)

- **Gesto:** en un tramo de texto, escribir `[@` abre el buscador de variables como un desplegable bajo la línea. Lo que se escribe después de `[@` filtra la lista, igual que el campo de búsqueda.
  - **Posición:** en T-HI-F8, bajo la línea y a la izquierda; en T-HI-F11, alineado al cursor. A 360 px ocupa siempre el ancho de la línea, sin desbordar: en un teléfono no se alinea al cursor.
  - **Al insertar desde `[@`,** la píldora no abre su panel: quien escribe sigue escribiendo. El panel se abre con Enter o clic sobre la píldora, como siempre.
- **Teclado:**
  - flechas arriba y abajo para moverse;
  - Enter o Tab insertan la variable resaltada **en lugar** de `[@` y lo escrito después, y el cursor queda después de la píldora;
  - Escape cierra el buscador y **deja el texto tal como se escribió** (`[@nom`), porque quien quería escribir `[@` literal no pierde nada;
  - borrar el `@` también lo cierra;
  - el foco no sale del tramo: el buscador se maneja con `aria-activedescendant` desde él.
- **Sin coincidencias:** la lista dice «Ninguna variable coincide con «{texto}»» y Enter no hace nada.
- **Lector de pantalla:**
  - el tramo pasa a `role="combobox"`, con `aria-expanded`, `aria-controls` y `aria-autocomplete="list"`, mientras el buscador está abierto;
  - al abrir, se anuncia en la región `polite` del editor: «Buscador de variables. Escribe para filtrar, Enter inserta y Escape cancela.»;
  - al insertar: «Se insertó {variable}.».
- **El botón sigue,** para quien usa el mouse: «Insertar variable» (`plus`), ahora **arriba** de la línea, al inicio de una barra propia, y no debajo. Abre la misma lista, pero **con su propio campo** de búsqueda arriba (`editorTexto.variable.buscar`, «Buscar una variable», la clave de hoy), con el foco en él. Ese campo es el combobox (`aria-controls` y `aria-activedescendant` sobre la lista). No se inserta `[@` en el texto, porque al cancelar dejaría restos en la frase.
  - Inserta en el último tramo enfocado o, si no hubo ninguno, al final, y el anuncio lo dice: «Se insertará al final del texto.».
  - Escape cierra sin insertar y el foco vuelve al botón.
  - Al insertar desde el botón, la píldora abre su panel (§2.2): quien usa el mouse suele querer aplicar una función.
  - Las opciones son `role="option"` en las dos entradas.
- **Pista visible,** bajo la línea, en `.field__hint`: «Escribe [@ para insertar una variable».
- **En una columna de variable directa** (§5.3) no hay línea ni disparador: sigue el `select`.

### 13.3 El buscador por tema, con un ejemplo (A1)

- **Agrupado por tema,** no por origen. El tema es un dato de la variable en el catálogo, `tema`, que manda el backend: una sola fuente. Las del módulo entran en el tema que les corresponde, no en un grupo aparte.
- **Temas, en este orden:**

  | Clave | es | en |
  |---|---|---|
  | `persona` | Persona y contacto | Person and contact |
  | `deuda` | Cuota y deuda | Instalment and debt |
  | `fechas` | Fechas y atraso | Dates and days overdue |
  | `credito` | Crédito | Loan |
  | `gestion` | Gestión y asignación | Collection and assignment |
  | `riesgo` | Riesgo y segmentos | Risk and segments |
  | `adicionales` | Campos adicionales | Additional fields |
  | `otros` | Otros | Other |

- **En qué tema cae cada variable:**
  - **persona:** `titular`, `documento_tipo`, `documento_numero`, `telefono` y `cliente_fallecido`; en MOWA, `titular` y `whatsapp_contacto`.
  - **deuda:** `monto_cuota`, `cuotas_aprobadas`, `cuotas_pagadas`, `cuotas_pendientes`, `saldo_capital_pendiente`, `saldo_soles_corte`, `saldo_cierre_actual` y `valor_cierre_mes_anterior`.
  - **fechas:** `fecha_vencimiento_cuota`, `vencimiento_operativo_aplica`, `vencimiento_operativo_fecha`, `dias_atraso`, `dias_atraso_entidad`, `mes_gestion`, `fecha_envio` y `dias_atraso_ajustados`; en MOWA, `vencimiento` y los días ajustados.
  - **credito:** `pagare`, `tipo_producto`, `estado_credito`, `moneda`, `tipo_reprogramacion`, `descuento_planilla`, `cantidad_paralelos` y `cartera_tag`.
  - **gestion:** `agencia`, `region`, `analista_actual`, `analista_asignacion`, `celular_analista` y `bpo`.
  - **riesgo:** `segmento_actual`, `segmento_atraso`, `segmento_financiero`, `segmento_saldo`, `tramo_actual`, `tramo_proyectado`, `tipo_basilea`, `mora_impacto_actual`, `mora_impacto_proyectada`, `provision_actual` y `provision_proyectada`.
  - **adicionales:** todo campo adicional (RF-63).
  - **otros:** un campo base nuevo sin tema asignado. Así nunca se pierde, y la prueba del catálogo avisa que le falta tema.
- **Cada fila:** el nombre visible en sans, el tipo como tag chico (texto, número, fecha, sí/no) y, a la derecha, en mono y muted, **el valor de ejemplo** del contexto (`contexto.ejemplo`), formateado como en la vista previa: «Titular · texto · TITULAR/SINTETICO,UNO». El nombre técnico ya no va en la fila: queda en `title` y se busca igual.
- **Búsqueda:** por nombre visible, nombre técnico y alias, sin tildes ni mayúsculas. Con texto, los temas vacíos se ocultan.
- **El speech de MOWA ofrecerá todos los campos de la cartera** (decisión del usuario, 2026-11-04), con los mismos temas que Columnas. Entra con la parte 2 de T-HI-B7, que espera la decisión D-CA-2. Un campo que viene vacío en un producto sigue la regla «Obligatoria» de la pieza (RF-45): si está marcada, el producto se informa con su motivo; si no, el campo queda vacío en el mensaje.
- **Lo que de verdad no está en un contexto:** solo entonces, al pie del buscador, una línea `.field__hint` con el alcance, que trae el catálogo (`clave_alcance`):
  - el speech de MOWA, **hasta la parte 2 de B7**: «El speech usa las variables de la campaña y los campos adicionales.». Con la parte 2, su `clave_alcance` se quita y la línea desaparece;
  - el mensaje de WhatsMKT, hasta la fase B (§13.7);
  - Columnas, nunca: ofrece todo.

### 13.4 Funciones, con su ejemplo antes de elegirla (A1)

- **El `select` «+ Agregar función» se reemplaza** por un botón «Agregar función» (`plus`) que abre una lista en el panel: por familia, con las compatibles con el tipo de la pieza en ese punto de la cadena (§2.3). Cada fila tiene:
  - el nombre de la función;
  - debajo, en `.field__hint`, su descripción con el ejemplo del catálogo («Deja solo los primeros N caracteres. JUAN PEREZ con 8 → JUAN PER»);
  - a la derecha, en mono, **el resultado con el valor de ejemplo de la pieza**, si la función no necesita parámetros (por ejemplo, «Mayúsculas → TITULAR/SINTETICO,UNO»). Si necesita, solo la descripción.
  La lista se filtra escribiendo, como el buscador de variables.
- **Al elegir,** la función se agrega al final de la cadena y el foco va a su primer parámetro, como hoy.
- **El error de un parámetro dice su rango,** con el mínimo y el máximo del catálogo:
  - «Escribe un número entre {min} y {max}.»;
  - solo mínimo: «Escribe un número de {min} en adelante.»;
  - solo máximo: «Escribe un número hasta {max}.»;
  - un parámetro de texto vacío que se exige: «Escribe {parametro}.».
  El texto genérico de hoy («…debe ser del tipo que se pide y estar dentro del rango») queda solo como respaldo.
- **El panel nombra su pieza** en su encabezado, con la posición cuando la misma variable está más de una vez: «Titular (2.ª vez)». La píldora abierta queda marcada (`aria-expanded="true"` y borde de acento), y el panel hace `scrollIntoView` al abrir.

### 13.5 Las píldoras y la línea (A1)

- **La píldora se lee como palabra de la frase:**
  - el nombre visible en sans, del cuerpo del texto, no en mono;
  - con **una** función, su nombre corto: «Titular · mayúsculas»;
  - con **dos o más**: «Titular · 3 funciones»;
  - la cadena completa va en `title` y en el nombre accesible («Titular, con mayúsculas, primeros caracteres 8»);
  - un ancho máximo de unas 24 letras, con puntos suspensivos; el nombre accesible no se corta.
- **La línea es un párrafo:** crece con el texto (de 3 líneas mínimo a unas 10), los tramos se parten como texto y las píldoras quedan en línea con él. Sigue siendo `input` en su borde y su foco, pero no de una sola fila.
- **El WhatsApp de contacto es una píldora** en los tres lugares, con el ícono `message-circle` y el nombre «Enlace de WhatsApp». En MOWA es la variable `whatsapp_contacto` con su función; en WhatsMKT (A3) se guarda como el marcador literal `[whatsapp]`. El usuario lo decidió así, y el editor no muestra la diferencia.
- **El resumen de una columna compuesta** en la lista de Columnas y en la campaña de WhatsMKT marca la variable entre corchetes: «Texto: 51[Teléfono]» (`textoDeContenido`). Sin las funciones, que se ven en la fila abierta.

### 13.6 Contador y errores, iguales en los tres sitios (A2)

- **Contador,** bajo la vista previa, siempre con la misma forma:
  - con tope: «{n} / {tope} caracteres»;
  - si los datos pueden alargarlo, se suma «· hasta {maximo} con los datos más largos»;
  - sin tope (Columnas): «{n} caracteres».
  - Al llegar al umbral del contexto: el tag `tag--advertencia` «Cerca del tope». Al pasarlo: el contador en `.field__error` y el tag `tag--error` «Pasa el tope».
  - Se anuncia solo al cruzar el umbral o el tope, no en cada tecla.
  - MOWA conserva la medida en GSM-7 y WhatsMKT la de [whatsapp] como 26 caracteres. Cambia la forma, no la cuenta.
- **Errores,** con un solo patrón:
  - un resumen arriba del editor (`.notice--danger`, `tabindex="-1"`): «Hay {n} problemas en el texto.», con «Ir al problema» por cada uno;
  - cada error también en su lugar: bajo el tramo, bajo el parámetro o en la píldora;
  - al guardar con errores, el foco va al resumen.
  WhatsMKT pasa a este patrón (hoy los muestra en fila bajo el textarea). La posición del emoji sigue llevando al carácter.
- **Lo que no es un error de lo escrito** (un dato vacío en la muestra) va aparte, en la vista previa, como `.field__hint`: «Con este producto, {variable} viene vacía.». No en el resumen.

### 13.7 WhatsMKT con el editor común (A3)

- El mensaje de la configuración (§5.1 de [whatsmkt-interfaz.md](whatsmkt-interfaz.md)) y su vista previa en la campaña pasan del textarea al editor común, en contexto `whatsmkt.mensaje`.
- **Hasta la fase B,** el buscador de ese contexto ofrece solo:
  - las macros de la definición por defecto, como píldoras con su etiqueta («MACRO1 · Nombres del titular»), que se guardan como `[$MACROn$]`;
  - el «Enlace de WhatsApp», que se guarda como `[whatsapp]`.
  Sin funciones: el panel dice «En WhatsMKT las funciones van en la columna, en Columnas de carga.», con el enlace de ir y volver.
- Lo demás sigue igual: el tope, los emojis, la macro que no existe y la vista previa con las filas de ejemplo.

### 13.8 Fuera de la fase A

Quedan fuera, como dijo el coordinador: pegar texto con marcadores, el producto real con fecha y pagaré, y el resaltado por píldora en la vista previa. Ninguno es imprescindible para la comodidad que pide el usuario: el disparador y el buscador resuelven lo que más cuesta. Si el usuario los pide, el primero a sumar es **pegar con marcadores**, porque hoy migrar un speech es pieza por pieza.

### 13.9 Textos (es / en)

| Clave | es | en |
|---|---|---|
| `editorTexto.variable.insertar` | Insertar variable | Insert variable |
| `editorTexto.disparador.pista` | Escribe [@ para insertar una variable | Type [@ to insert a variable |
| `editorTexto.disparador.abierto` | Buscador de variables. Escribe para filtrar, Enter inserta y Escape cancela. | Variable search. Type to filter, Enter inserts and Escape cancels. |
| `editorTexto.disparador.insertada` | Se insertó {variable}. | {variable} was inserted. |
| `editorTexto.disparador.alFinal` | Se insertará al final del texto. | It will be inserted at the end of the text. |
| `editorTexto.disparador.ninguna` | Ninguna variable coincide con {textoCitado}. | No variable matches {textoCitado}. |
| `editorTexto.tema.persona` | Persona y contacto | Person and contact |
| `editorTexto.tema.deuda` | Cuota y deuda | Instalment and debt |
| `editorTexto.tema.fechas` | Fechas y atraso | Dates and days overdue |
| `editorTexto.tema.credito` | Crédito | Loan |
| `editorTexto.tema.gestion` | Gestión y asignación | Collection and assignment |
| `editorTexto.tema.riesgo` | Riesgo y segmentos | Risk and segments |
| `editorTexto.tema.adicionales` | Campos adicionales | Additional fields |
| `editorTexto.tema.otros` | Otros | Other |
| `textoEnriquecido.alcance.mowa_mes.speech` | El speech usa las variables de la campaña y los campos adicionales. | The speech uses the campaign variables and the additional fields. |
| `textoEnriquecido.alcance.whatsmkt.mensaje` | Hasta que WhatsMKT tenga variables propias, el mensaje usa las macros de la definición por defecto y el enlace de WhatsApp. | Until WhatsMKT has its own variables, the message uses the macros of the default definition and the WhatsApp link. |
| `editorTexto.funcion.agregar` | Agregar función | Add function |
| `editorTexto.funcion.buscar` | Buscar función | Search function |
| `editorTexto.funcion.ejemploResultado` | {funcion} → {resultado} | {funcion} → {resultado} |
| `editorTexto.parametro.rango` | Escribe un número entre {min} y {max}. | Enter a number between {min} and {max}. |
| `editorTexto.parametro.minimo` | Escribe un número de {min} en adelante. | Enter a number from {min} up. |
| `editorTexto.parametro.maximo` | Escribe un número hasta {max}. | Enter a number up to {max}. |
| `editorTexto.parametro.vacio` | Escribe {parametro}. | Enter {parametro}. |
| `editorTexto.panel.vez` | {variable} ({n}.ª vez) | {variable} (occurrence {n}) |
| `editorTexto.pildora.funciones` | {variable} · {n} funciones | {variable} · {n} functions |
| `editorTexto.pildora.whatsapp` | Enlace de WhatsApp | WhatsApp link |
| `editorTexto.largo.deTope` | {n} / {tope} caracteres | {n} / {tope} characters |
| `editorTexto.largo.hasta` | · hasta {maximo} con los datos más largos | · up to {maximo} with the longest data |
| `editorTexto.largo.cerca` | Cerca del tope | Near the limit |
| `editorTexto.largo.pasa` | Pasa el tope | Over the limit |
| `editorTexto.muestra.vacia` | Con este producto, {variable} viene vacía. | With this product, {variable} is empty. |
| `editorTexto.whatsmkt.sinFunciones` | En WhatsMKT las funciones van en la columna, en Columnas de carga. | In WhatsMKT functions go in the column, in Load columns. |

- `editorTexto.variable.agregar` («Variable») se reemplaza por `editorTexto.variable.insertar`.
- `editorTexto.largo.nivel.*` y `editorTexto.largo.maximoDe` se van con A2, reemplazados por `largo.deTope`, `largo.hasta`, `largo.cerca` y `largo.pasa`.
- `{textoCitado}` y los nombres van con las comillas del idioma (`camposAdicionales.nombreCitado`).

### 13.10 Pruebas mínimas

- **A1:**
  - `[@` abre el buscador en el cursor; escribir filtra; Enter y Tab insertan en lugar de `[@…` con el cursor después; Escape deja el texto; borrar `@` cierra; sin coincidencias, Enter no inserta;
  - los atributos de combobox del tramo y los dos anuncios;
  - «Insertar variable» arriba de la línea, con el anuncio de «al final» si no hubo foco;
  - el buscador por tema en el orden de 13.3, con el ejemplo formateado, el tag de tipo y la búsqueda por el nombre técnico; un campo sin tema cae en Otros;
  - la línea de alcance en el speech de MOWA mientras no entre la parte 2 de B7, y en el mensaje de WhatsMKT (A3); ninguna en Columnas;
  - con la parte 2 de B7: el speech de MOWA con todos los campos de la cartera por tema y sin línea de alcance;
  - la lista de funciones con su descripción, el resultado de ejemplo en las sin parámetros y el filtro; los cuatro errores de parámetro con su rango;
  - el panel que nombra la pieza repetida; la píldora con una y con varias funciones, el corte de nombre largo y su nombre accesible completo;
  - la línea que crece; la píldora de WhatsApp en MOWA;
  - el resumen «Texto: 51[Teléfono]».
- **A2:** el contador con tope, con «hasta», sin tope, y sus dos tags y anuncios, en MOWA (GSM-7) y en WhatsMKT (26 por [whatsapp]); el resumen de errores con «Ir al problema» y el foco al guardar, también en WhatsMKT; el dato vacío de la muestra fuera del resumen.
- **A3:** el mensaje de WhatsMKT en el editor común con macros y WhatsApp como píldoras que se guardan como `[$MACROn$]` y `[whatsapp]`; un texto guardado antes de A3 se abre igual; sin funciones, con su enlace.
- **axe** en claro, oscuro y 360 px: el editor con el buscador abierto por `[@`, el panel de funciones abierto y el resumen de errores.
- **Capturas para `designer`:** el buscador abierto por `[@` (1280 y 360), la lista de funciones, una línea con varias píldoras y el contador con «Cerca del tope», en es y en, claro y oscuro.
