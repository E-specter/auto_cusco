# Motor de texto enriquecido: reglas de interfaz

Reglas vinculantes para el frontend del motor de texto enriquecido y del constructor de columnas (T-MTE-F1). Complementan el diseño técnico de [motor-texto-enriquecido.md](motor-texto-enriquecido.md) y los requerimientos RF-42 a RF-54 de [atomics-requirements.md](atomics-requirements.md), sección 11.

Responsable: `designer`. Implementa: `dev_frontend_motor_texto_enriquecido`, bajo `coordinador_motor_texto_enriquecido`. Un cambio a estas reglas se acuerda con `designer` antes de escribirlo.

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

- **Nombre** (único, RF-51). Se escribe al crear la definición y **no cambia entre versiones** (B4b rechaza un nombre distinto con un problema en `campo=nombre`). Después de la primera versión se muestra de solo lectura, con el hint «El nombre se fija al crear la definición». Renombrar queda como pendiente de producto.
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
- **Protección contra fórmulas en CSV:** una casilla marcada por defecto, con el hint «Agrega un apóstrofo a los textos que empiezan con =, +, - o @, salvo los que son solo un número, como -1,234.56 o +51987654321. Desmárcala solo si la plataforma de destino no lo acepta» (RF-53).

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
  - **Variable directa:** un `select` de variables con su tipo. Hint: «Conserva el valor original, sin pasarlo por texto» (RF-49). Si se le agregan funciones y la columna sigue siendo una sola variable, conserva el tipo del resultado final: una fecha con días sumados sigue siendo fecha en el XLSX (precisión D11 del diseño). El resumen de la fila lo dice así: «Variable: Vencimiento · sumar 3 días (fecha)».
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

La versión, el nombre de la versión y el guardado conservan su forma actual. Las versiones v1 se siguen mostrando en solo lectura con sus dos partes, hasta la fase M3.

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
| Estado puro del editor (árbol, inserción, cursor, problemas) | `src/lib/expresion.ts` | `designer` |
| Estado puro de las variantes por segmento | `src/lib/variantes.ts` | `designer` |
| Componente del editor y su comportamiento | `src/components/EditorTexto.astro`, `src/scripts/editor-texto.ts`, `src/styles/editor-texto.css` | `designer` |
| Selector de variantes por segmento | `src/components/VariantesSegmento.astro`, `src/scripts/variantes-segmento.ts` | `designer` |
| Selector de variable y selector de patrón de fecha | `src/scripts/selector-variable.ts`, `src/scripts/selector-patron-fecha.ts` | `designer` |
| Cliente de catálogo, validación y previsualización | `src/lib/api-texto-enriquecido.ts` | `designer` |
| API falsa de catálogo, validación y previsualización | `e2e/api-falsa-texto-enriquecido.ts` | `designer` |
| Fila expandida de tabla y marca de vacío | `src/styles/ui.css` (`.table__detalle`, `.marca-vacio`) | `designer` |
| Textos `textoEnriquecido.*` | `src/i18n/*.json` | `designer`, con la prueba espejo del backend sobre todas sus claves |
| Etiquetas de los campos de la cartera (`campo.<nombre>`) | `src/lib/campos.ts`, `src/i18n/*.json` | `designer`, con su prueba contra el catálogo de campos del backend (`tests/nucleo/i18n-campos.test.ts`). Las usan `/cartera`, el selector de variables y el constructor. Una variable con `clave_nombre` usa esa clave; un campo de la cartera, `campo.<nombre>` |
| Cliente de `/definiciones-columnas` y su API falsa | `src/lib/api-definiciones.ts`, `e2e/api-falsa-definiciones.ts` | `dev_frontend_motor_texto_enriquecido` |
| Pantalla del constructor de columnas, su vista previa y sus textos `columnas.*` | `src/pages/columnas.astro`, `src/styles/columnas.css` | `dev_frontend_motor_texto_enriquecido` |
| Integración en el speech de MOWA MES (M2) y sus textos `mowaMes.speech.v2.*` | `src/pages/mowa-mes/configuracion.astro` | `dev_frontend_motor_texto_enriquecido` |
| Entrada de navegación y claves `nav.*` | `src/lib/navegacion.ts`, `src/i18n/*.json` | `designer`, cuando la página exista en el árbol |

El orden lo fija el coordinador. El editor empieza apenas el backend fije el contrato (B4a).

## 9. Contrato de montaje y decisiones de detalle

Respuestas a las dudas de `dev_frontend_motor_texto_enriquecido` (`docs/agents/dev_frontend_motor_texto_enriquecido/dudas-designer.md`), 2026-10-02. Son vinculantes como el resto del documento.

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
});

editor.fijarExpresion(otra);         // reemplaza, cierra paneles y vuelve a validar
editor.fijarMuestra({ tipo: 'ejemplo', segmento: '9 a 30' });
editor.irAProblema(indice);          // abre la pieza y enfoca el campo
editor.expresion();                  // el árbol actual, para guardar
```

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

`VariantesSegmento` sigue el mismo patrón: `montarVariantes(raiz, { contexto, segmentos, variantes, conPorDefecto })`, con `fijarVariantes`, `fijarNiveles` e `irAProblema(segmento, indice)`. Emite `variantescambiadas` con `{ variantes, seleccionado, origen, pendiente, valida, problemas }`, donde `problemas` lleva el segmento de cada uno.

### 9.3 Clientes y APIs falsas (D-2)

- **De `designer`:** `api-texto-enriquecido.ts` (catálogo, validación y previsualización) sobre `request` de `api.ts`, y `e2e/api-falsa-texto-enriquecido.ts`, tipada con el contrato.
- **De `dev_frontend_motor_texto_enriquecido`:** el cliente de `/definiciones-columnas` en `api-definiciones.ts`.
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
