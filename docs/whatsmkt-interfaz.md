# WhatsMKT: reglas de interfaz

Reglas vinculantes para las tres pantallas de WhatsMKT: `/whatsmkt/campana`, `/whatsmkt/seguimiento` y `/whatsmkt/configuracion`. Las construyen T-WM-F1, F2 y F3, y `designer` las aprueba con capturas.

Complementan [requerimientos-whatsmkt.md](requerimientos-whatsmkt.md) (RF-WM-01 a RF-WM-44) y la sección 5 del plan WhatsMKT v2. Reutilizan las reglas ya escritas, sin repetirlas:

- el constructor con plataforma, la etiqueta y los textos guardados: [motor-texto-enriquecido-interfaz.md](motor-texto-enriquecido-interfaz.md) §11;
- el criterio de iconos, los estados, las confirmaciones, «Para subir a MES», descartadas, pendientes y «Editar en Cartera»: [mowa-mes-interfaz.md](mowa-mes-interfaz.md);
- la estructura de página (`.page`), el paginador y las tablas apilables: `ui.css`.

Donde una regla depende de una duda abierta (DU-WM-1 a DU-WM-11), se aplica la regla provisional del documento de requerimientos y se dice en su lugar (§12).

Responsable: `designer`. Un cambio a estas reglas se acuerda con `designer` antes de escribirlo.

---

## 1. Principios

1. **Igual que MOWA MES donde el flujo es igual.** Campaña, Seguimiento y Configuración se leen como en MOWA: mismas secciones, mismos estados, mismos iconos, mismas confirmaciones. Lo distinto de WhatsMKT (macros por posición, lote por segmento, adjuntos y horarios) se nota por lo que dice, no por un estilo propio.
2. **El sistema prepara, el operador sube.** Todo termina en una ficha con los datos listos para copiar en el formulario de WhatsMKT. Cada dato se copia con un botón, en el orden del formulario.
3. **Un lote se ve como un lote.** Si el modo es por segmento, la previsualización y las fichas muestran cuántas campañas resultan y cada una por separado, sin mezclar sus cifras.
4. **Las reglas de WhatsMKT, a la vista.** Lo que no se puede hacer (un emoji, una macro que no existe, un nombre de más de 75) se dice en su campo, al salir de él, antes de llegar a crear.
5. **Nada propio donde ya hay una herramienta.** Supervisores, Calendario laboral y Columnas de carga se usan desde Herramientas, con ir y volver.

## 2. Navegación (RF-WM-02 y RF-WM-03)

- **En Canales,** «WhatsMKT ▾», con el mismo desplegable que MOWA MES: Campaña, Seguimiento y Configuración. Va después de MOWA MES.
- **Herramientas** (Columnas de carga, Supervisores y Calendario laboral) no se repiten en WhatsMKT. La campaña y la configuración enlazan a ellas con ir y volver, como «Editar en Cartera» ([mowa-mes-interfaz.md](mowa-mes-interfaz.md) §4.7):
  - al llegar, la herramienta muestra un `.notice--info` con «Volver a WhatsMKT sin guardar»;
  - al guardar, vuelve a la pantalla de WhatsMKT con lo guardado elegido.
- Cada pantalla usa `.page`, con la etiqueta «CANALES · WHATSMKT» sobre el título, como MOWA.

## 3. Campaña (`/whatsmkt/campana`)

### 3.1 Orden de las secciones

Un `.panel` por sección, en el orden del flujo:

1. **Base** (§3.2)
2. **Archivo de carga** (§3.3)
3. **Mensaje** (§3.4)
4. **Programación** (§3.5)
5. **Envío** (§3.6)
6. **Nombre de la campaña** (§3.7)
7. **Previsualización** (§3.8), con «Crear» al pie (§3.9)

Al crear, la página reemplaza la previsualización por las fichas «Para subir a WhatsMKT» (§3.10), como hace la campaña de MOWA.

### 3.2 Base (RF-WM-05)

- `SelectorSeleccion` en modo compacto (fecha de corte y selección guardada), con «Editar en Cartera» (`square-pen`) y su vuelta, igual que MOWA ([mowa-mes-interfaz.md](mowa-mes-interfaz.md) §4.7).
- Debajo, el resumen de siempre: «Preventiva top 1000, sin cambios».

### 3.3 Archivo de carga (RF-WM-09 a RF-WM-12)

- **«Definición de columnas»:** un `select` con las definiciones de plataforma WhatsMKT, por su nombre. Por defecto, la de la configuración. La línea de versión va debajo: «Versión 3 · WhatsMKT».
- **Las columnas de un vistazo,** en una tabla de solo lectura, apilable (`.table--apilable`):

  | Macro | Encabezado | Etiqueta | Contenido |
  |---|---|---|---|
  | — | `número` | Número con prefijo | `51[@telefono]` |
  | 1 | `[$MARCRO1$]` | Nombres del titular | Variable: Titular · nombres |

  - La columna «Macro» es la posición: es lo que el mensaje usa como `[$MACROn$]` (RF-WM-11).
  - «Contenido» es el mismo resumen de la lista del constructor.
- **«Editar en Columnas de carga»** (`square-pen`, `.btn--sm`): abre la definición elegida en el constructor, en modo WhatsMKT, con ir y volver. Al volver, el `select` queda en la versión guardada.
- **Sin ninguna definición de WhatsMKT:** el `select` queda inactivo con «No hay definiciones de WhatsMKT», y un `.notice--warning`: «Crea una definición de WhatsMKT en Columnas de carga para armar el archivo», con «Crear en Columnas de carga» (ir y volver, con la plataforma ya elegida).
- **DU-WM-1, provisional:** con más de 5 macros, un `.field__hint` bajo la tabla: «WhatsMKT publica hasta 5 variables por mensaje; esta definición tiene {n}». Avisa y no bloquea (regla provisional: libre).

### 3.4 Mensaje (RF-WM-17 a RF-WM-27)

- **Modo:** un `.segmented` con «Por segmento» (por defecto) y «Global». El texto de ayuda cambia con el modo:
  - Por segmento: «Un mensaje por segmento: se crea una campaña de WhatsMKT por cada segmento con productos».
  - Global: «Un solo mensaje para toda la selección: se crea una sola campaña».
- **Por segmento:** una fila por segmento de WhatsMKT, en una tabla apilable:

  | Segmento | Días de atraso | Mensaje |
  |---|---|---|
  | Preventivo | hasta 0 | `select` de mensajes guardados, con el del segmento por defecto |

  Debajo de cada `select`, el texto del mensaje elegido en un bloque de solo lectura (`.mono`, con el largo «312 / 4096»). Los marcadores `[$MACROn$]` van resaltados con su etiqueta en `title`.
- **Global:** un solo `select`, con los mensajes globales y luego los de los segmentos, en dos `optgroup` («Mensajes globales» y «Mensajes por segmento»), y el mismo bloque de solo lectura debajo.
- **Los mensajes se escriben en la configuración,** no en la campaña: la campaña elige. Junto al `select`, «Editar en la configuración» (`square-pen`, `.btn--sm .btn--quiet`), con ir y volver.
- **Mensajes deshabilitados:** no se ofrecen (RF-WM-22). Si la campaña venía con uno que se deshabilitó mientras tanto, el `select` queda sin elegir y un `.field__error` lo dice con su código (§7).
- **Problemas del mensaje** (emoji, macro que no existe en la definición, largo): van bajo su `select`, por su código, y también en el resumen de la previsualización (§3.8).

### 3.5 Programación (RF-WM-06 a RF-WM-08)

- **«Fecha de envío»:** `input type="date"`, con `min` en mañana y, por defecto, el día gestionable sugerido. Hint: «Se sugiere el siguiente día gestionable: de lunes a sábado, sin feriados». Si el analista elige un día no gestionable, el error va al salir del campo, con la fecha sugerida y el botón «Usar el {fecha}».
- **«Horarios de envío»:** un `fieldset` con dos casillas, «Horario 1 · 08:00 – 14:00» y «Horario 2 · 14:00 – 20:00». Las franjas salen de la configuración. Hint del `fieldset`: «Marca al menos uno». Sin ninguno, el error va en el `fieldset`.
- **«Deseo que salga mi envío lo antes posible»:** una casilla, con el texto exacto del formulario de WhatsMKT. Hint: «Se copia en la ficha; no cambia la fecha ni los horarios».

### 3.6 Envío (RF-WM-28 a RF-WM-31)

- **«Tipo de envío»:** un `fieldset` con tres radios: «Solo texto» (por defecto), «Texto + archivo» y «Texto + vCard».
- **Campos condicionales:** van justo debajo del radio que los muestra, con `hidden` en los otros. Cambiar de tipo conserva lo elegido en los demás, pero solo se manda lo del tipo elegido.
  - **Texto + archivo:** un `select` «Archivo», con los adjuntos activos de la biblioteca (imagen, video, audio o PDF), cada uno con su tipo y su tamaño: «Afiche octubre.jpg · imagen · 240 KB». Al lado, «Subir un archivo» (`upload`), que lo agrega a la biblioteca y lo deja elegido.
  - **Texto + vCard:** un `input` «Etiqueta del contacto» (DU-WM-4, provisional: solo la etiqueta).
- **«Foto de perfil»:** un `select` con las fotos de la biblioteca y «Sin foto» (DU-WM-5, provisional: opcional), más «Subir una foto». Hint: «JPEG de 200 × 200 píxeles, hasta 1 MB».
- **Subir:** el selector de archivo propio del sitio, con el tipo y el tope del hint. El archivo se valida al elegirlo, y el error va bajo el campo, por su código. Mientras sube, el botón queda con `data-loading`.
- **Archivo repetido:** si el archivo ya estaba en la biblioteca (misma huella), se elige el existente y el estado dice «Ya estaba en la biblioteca: se usa el mismo archivo».

### 3.7 Nombre de la campaña (RF-WM-33)

- Igual que el nombre de los archivos de MOWA (RF-MM-25): un `input` con la plantilla de la configuración y, debajo, las variables como fichas que se insertan con un clic: `{fecha_corte}` y `{segmento}`.
- Un contador «62 / 75» que pasa a `.field__error` al superar el tope. El `input` no deja escribir más de 75 caracteres de plantilla.
- **El nombre resultante,** por campaña: «Nombre de la campaña Preventivo: CUSCO_Vencida whatsapp 2026.10.29 Preventivo». Si alguno pasa de 75, va su error y no se deja crear (RF-WM-33).
- **DU-WM-6, provisional:** en un lote, si la plantilla no usa `{segmento}`, el hint lo dice: «Se agrega el segmento al final para que los nombres no se repitan».

### 3.8 Previsualización (RF-WM-35)

Se recalcula sola, con la misma espera y cancelación que la campaña de MOWA, cada vez que cambia algo de las secciones de arriba.

- **Resumen,** arriba:
  - «Se crearán 3 campañas · 1 205 filas en total», o «Se creará 1 campaña · 400 filas».
  - Si hay problemas, un `.notice--danger` con la lista, cada uno con el texto de su código y un enlace «Ir al campo» que lleva el foco a su sección.
- **Un `.segmented` por campaña del lote:** «Preventivo (520) · Tramo 2 (480) · Mayores al 2 (205)», con el número de filas. En modo global no hay `.segmented`: hay una sola campaña.
- **Por campaña:**
  - **Cifras** (`.stat`), con los iconos del catálogo de MOWA: filas del archivo (`file-up`), supervisión (`user-check`) y excluidos (`ban`).
  - **Nombre:** el resultante (§3.7), en mono.
  - **Mensaje de ejemplo:** el texto con las macros reemplazadas con la primera fila de productos, en un bloque de lectura, con el título «Así lo verá el cliente». Es lo que hará WhatsMKT (RF-WM-27).
  - **Muestra:** las primeras filas del archivo, en una tabla apilable. Los encabezados son los del archivo, con la etiqueta debajo: «[$MARCRO1$]», y en la segunda línea «Nombres del titular». Las filas de supervisión llevan el tag «Supervisión».
  - **Exclusiones:** una tabla apilable con Pagaré, Motivo (tag con su texto corto) y Detalle, paginada con el paginador compartido. Sin exclusiones: «Ningún producto queda fuera».
- **Un segmento sin productos no aparece** en el `.segmented` (RF-WM-23). Si ninguno tiene productos, en lugar de la previsualización va un `.notice--warning` con el motivo, y «Crear» queda inactivo.

### 3.9 Crear (RF-WM-23)

- **Botón:** «Crear campaña» o «Crear 3 campañas», `.btn--primary`. Mientras haya problemas, queda inactivo con el motivo en texto al lado, como en la carga de sábanas (por ejemplo, «Corrige 2 problemas para crear»).
- **El lote se crea entero o no se crea.** Si falla, nada se crea, y el error va arriba, en `role="alert"`.
- **Fecha que dejó de ser válida (409):** un `.notice--warning` en Programación, «El {fecha} ya no es un día gestionable. El siguiente es el {nueva}», con «Usar el {nueva}». Lo escrito se conserva.

### 3.10 «Para subir a WhatsMKT» (RF-WM-36)

Es el patrón de «Para subir a MES» ([mowa-mes-interfaz.md](mowa-mes-interfaz.md) §4.4), con el ajuste de las filas de C11: una sola línea por fila.

- **`.notice--success`:** «Se crearon 3 campañas (lote 12). Ahora súbelas a WhatsMKT con estos datos», o «Se creó la campaña 37…» si es una sola.
- **Un `.segmented` por campaña,** como en la previsualización, cuando hay más de una.
- **Por campaña, tres pasos numerados:**
  1. **«Descarga los archivos»:** la lista de contactos (`.xlsx`), la foto de perfil y el adjunto, si los hay, cada uno con «Descargar» (`download`) y su nombre en mono.
  2. **«Completa el formulario de WhatsMKT»:** un `dl` en rejilla (dato | valor | Copiar), en el orden del formulario:
     - Nombre de campaña;
     - Fecha y horarios: «29/10/2026 · Horario 1 (08:00 – 14:00)»;
     - Lo antes posible: «Sí» o «No»;
     - País: «Perú»;
     - ¿Cuántos teléfonos tiene en su Lista de contactos?: el número, sin separador de miles, porque así se escribe en el campo;
     - Tipo de envío: «Texto + imagen» o «Texto + vCard · Caja Cusco»;
     - Texto del mensaje: el mensaje con los marcadores, en un bloque de varias líneas, con su «Copiar».

     Cada «Copiar» anuncia «Copiado: {dato}», como en MOWA.
  3. **«Después del envío, importa el informe»:** «Ir al seguimiento de la campaña».
- **A 360 px,** el `dl` se apila: el dato arriba, y el valor con su botón debajo.

## 4. Seguimiento (`/whatsmkt/seguimiento`)

Es el seguimiento de MOWA ([mowa-mes-interfaz.md](mowa-mes-interfaz.md) §4.2 y §4.3) sin el límite mensual ni el costo, que WhatsMKT no tiene en esta entrega (DU-WM-9).

### 4.1 Lista de campañas (RF-WM-40 a RF-WM-42)

- **`.segmented`** «Activas (N) · Descartadas (M)», con la vista en la URL.
- **Filtros,** en una fila: «Mes de envío» (`calendar`, con `formatMesGestion`), «Lote» y «Segmento».
- **Línea de pendientes,** con `hourglass`, si hay alguna sin informe: «2 campañas pendientes del informe».
- **Tabla apilable,** paginada:

  | # | Creada | Nombre | Lote | Segmento | Envío | Filas | Estado | Acción |
  |---|---|---|---|---|---|---|---|---|

  - Estado: el tag «Pendiente del informe» (`tag--advertencia`, `hourglass`) o nada si ya está conciliada. Una descartada lleva «Descartada» (`archive`).
  - Acción: «Ver» (`eye`), «Descargar» (`download`) y «Descartar» (`archive`). En Descartadas: «Ver», «Restaurar» (`archive-restore`) y «Eliminar definitivamente» (`trash-2`, rojo).
  - Lote: el número del lote en mono, con el filtro al tocarlo. Las campañas de un mismo lote quedan juntas.

### 4.2 Detalle de la campaña

- **Encabezado del panel:** «Campaña 37 · Preventivo · lote 12», y a la derecha, en mono: «Corte 13 set. 2026 · envío 15 set. 2026 · Horario 1».
- **Pendiente del informe:** un `.notice--warning` con «Falta importar el informe de WhatsMKT. Cuando la campaña se haya enviado, descárgalo de WhatsMKT e impórtalo aquí», y «Importar el informe» (`upload`).
- **Cifras,** con los iconos del catálogo: productos cargados, supervisión (`user-check`), total cargados (`file-up`), excluidos (`ban`) y, con informe, enviados (`send`) y no enviados (`circle-x`).
- **Archivos:** la lista de contactos, la foto y el adjunto, con «Descargar».
- **Informe de WhatsMKT (RF-WM-37 y RF-WM-38):**
  - El selector de archivo propio, con el hint «El informe que descargas de WhatsMKT al terminar el envío (hoja «Informe»), en Excel, CSV o JSON, hasta 32 MB».
  - «Importar informe» (`upload`, `.btn--primary`).
  - En una descartada, el formulario se oculta y va el hint «Esta campaña está descartada: restáurala para importar su informe».
  - Si ya tiene informe, la confirmación «Este informe ya estaba importado», como en MOWA.
- **Conciliación (RF-WM-39),** con informe:
  - La línea del informe: «Informe del 30/10/2026 · total informado 101 · 101 filas».
  - **DU-WM-7, provisional:** si el total informado no coincide con las filas, un `.notice--warning`: «El informe dice 101 enviados y trae 99 filas. La conciliación usa las filas». No bloquea.
  - Tabla **Productos**, apilable: cargados, enviados y no enviados.
  - Tabla **Supervisión**, aparte (RF-41), apilable, con las mismas columnas.
  - **Números sin correspondencia:** «Números del informe que no están en la carga: 2», con la lista en mono. Si no hay, la línea no se muestra.
  - El nombre que trae el informe, solo para leer: «Nombre en el informe: CUZCO_Vencida…». No se compara.
  - Nota bajo la tabla: «Un producto cuenta como enviado si su número aparece en el informe. Si dos productos comparten número, el envío cuenta para los dos».
- **Descartar, restaurar y eliminar:** las confirmaciones de [mowa-mes-interfaz.md](mowa-mes-interfaz.md) §4.6, con los textos de WhatsMKT (§8). Eliminar dice además que la biblioteca y los mensajes no cambian (RF-WM-42).

## 5. Configuración (`/whatsmkt/configuracion`)

Arriba, un `.notice--info`: «Columnas de carga, Supervisores y Calendario laboral tienen su propia pantalla:», con los tres enlaces. No nombra la sección «Herramientas»: en la barra ese nombre no se ve (es el `aria-label` de la lista), y un texto no manda a un lugar que no se lee.

Cada bloque se guarda por separado, como en MOWA. Los paneles van en este orden:

1. **Segmentos y mensajes** (RF-WM-20 y RF-WM-21):
   - La tabla de segmentos, apilable, con Segmento, «Desde (días)» y «Hasta (días)» (días de atraso ajustados), editables. Un límite vacío se lee como par: el «Desde» del preventivo dice «sin mínimo», y el «Hasta» de «Tramos mayores al 2» dice «sin máximo». Una tabla que deja huecos o se superpone se rechaza con su código, bajo la fila.
   - Debajo, el mensaje de cada segmento con `TextosGuardados` (§11.3 del motor), un `.segmented` por segmento para elegir cuál se edita.
2. **Mensajes globales** (RF-WM-19): `TextosGuardados`, con el título «Mensajes globales» y el hint «Para las campañas especiales, con un solo mensaje para toda la selección».
3. **Horarios de envío** (RF-WM-07): las dos franjas, cada una con dos `input type="time"` (desde y hasta). Una franja cuyo inicio no es anterior a su fin (14:00 a 08:00, o la misma hora) se rechaza con `horario_invalido`, bajo esa franja; `{horario}` es su nombre, «Horario 1» o «Horario 2».
4. **Nombre de la campaña** (RF-WM-33): la plantilla, con sus fichas de variables, el contador «/ 75» y un ejemplo resultante.
5. **Archivo de carga** (RF-WM-09): el `select` de la definición por defecto, con las de plataforma WhatsMKT, y «Editar en Columnas de carga».
6. **Topes** (RF-WM-26 y RF-WM-31): largo máximo del mensaje (caracteres) y tamaño máximo de video, audio y PDF (MB). La API los guarda en bytes; el panel los muestra y los recibe en MB, en base decimal (1 MB son un millón de bytes). Los `input` llevan `min="1"`, así que un tope de cero o negativo no llega a validarse. Cada uno con su hint del supuesto: «Valor inicial: el largo de un mensaje de WhatsApp (4096). No es un dato verificado de WhatsMKT».
7. **Biblioteca de adjuntos** (RF-WM-30 a RF-WM-32):
   - Una tabla apilable con Nombre, Tipo, Tamaño, Subido y Acción («Descargar» y «Archivar»), y «Subir un archivo».
   - Los archivados van en un `<details>` «Archivados (N)», con «Descargar» y «Restaurar». Un adjunto no se borra: se archiva.
   - Al subir una imagen, el estado dice «Se guardó sin metadatos (EXIF, ubicación)», porque el usuario lo pidió explícitamente (P-8).

### 5.1 Editor del mensaje (RF-WM-24 a RF-WM-27)

Es el editor que `TextosGuardados` recibe en el contexto `whatsmkt.mensaje`:

- **Barra «Insertar macro»,** sobre el campo: un botón `.btn--sm` por macro de la definición por defecto, «MACRO1 · Nombres del titular», que inserta `[$MACRO1$]` donde está el cursor y devuelve el foco al campo. Si la columna no tiene etiqueta, solo «MACRO1».
- **El campo:** un `textarea`, en texto plano, con `spellcheck`. Crece con el texto hasta unas 12 líneas.
- **Contador:** «312 / 4096 caracteres», con los marcadores sin reemplazar (DU-WM-3, provisional). Pasa a `.field__error` al superar el tope. Se anuncia solo al cruzar el tope, no en cada tecla.
- **Emojis (RF-WM-24):** al salir del campo, o al guardar, el error dice el primero y su posición: «No se admiten emojis: el primero es «😀», en la posición 42». Al enfocar el error, el cursor queda sobre ese carácter (`setSelectionRange`).
- **Macro que no existe (RF-WM-25):** «[$MACRO4$] no existe en la definición elegida: tiene 3 macros».
- **Vista previa,** bajo el campo: «Así lo verá el cliente», con las macros reemplazadas con la fila 1 de la muestra y un `select` «Fila de ejemplo» (1 a 3). Es la misma vista previa de la campaña.
- **DU-WM-2 y DU-WM-11, provisionales:** el texto sembrado se muestra tal cual, con sus espacios dobles y el enlace de WhatsApp dentro del mensaje.

## 6. Iconos

Se usa el catálogo de [mowa-mes-interfaz.md](mowa-mes-interfaz.md) §3, con las mismas reglas de tamaño, alineación y cuándo no va un icono. WhatsMKT suma solo estos conceptos:

| Concepto | Icono | Dónde |
|---|---|---|
| Horario de envío | `clock` | Etiqueta del `fieldset` «Horarios de envío» y el dato de la ficha |
| Foto de perfil | `image` | Etiqueta del campo y el dato de la ficha |
| Adjunto (texto + archivo) | `paperclip` | Etiqueta del campo y el dato de la ficha |
| vCard | `contact` | Etiqueta del campo y el dato de la ficha |
| Lote | `layers` | Encabezado «Lote» del detalle y su filtro |
| Número sin correspondencia | `circle-help` | Etiqueta de la línea |

Los estados, las acciones y las cifras son los de MOWA: no se inventan otros para lo mismo.

## 7. Errores por código

Los códigos los define el backend en su enum (`whatsmkt.codigo.*`, RF-WM-43) y llegan con la frase del servidor como respaldo. Esta tabla fija dónde va cada uno y su texto. Los nombres de código son una propuesta: si el backend usa otros, se cambia el nombre y se conserva el texto.

| Código | Dónde | es | en |
|---|---|---|---|
| `sin_telefono` | Exclusiones | Sin teléfono | No phone |
| `telefono_invalido` | Exclusiones | Teléfono inválido | Invalid phone |
| `macro_vacia` | Exclusiones | Macro vacía | Empty macro |
| `mensaje_con_emoji` | Bajo el mensaje | No se admiten emojis: el primero es «{caracter}», en la posición {posicion}. | Emojis are not allowed: the first one is “{caracter}”, at position {posicion}. |
| `macro_inexistente` | Bajo el mensaje | {macro} no existe en la definición elegida: tiene {n} macros. | {macro} does not exist in the chosen definition: it has {n} macros. |
| `mensaje_largo` | Bajo el mensaje | El mensaje tiene {largo} caracteres: el máximo es {maximo}. | The message has {largo} characters: the maximum is {maximo}. |
| `mensaje_deshabilitado` | Bajo el `select` del mensaje | El mensaje elegido está deshabilitado. Elige otro o habilítalo en la configuración. | The chosen message is disabled. Choose another one or enable it in the settings. |
| `nombre_largo` | Bajo el nombre | El nombre tiene {largo} caracteres: el máximo es 75. | The name has {largo} characters: the maximum is 75. |
| `variable_inexistente` | Bajo la plantilla | La variable {variable} no existe. Usa las de la lista. | The variable {variable} does not exist. Use the ones in the list. |
| `fecha_no_gestionable` | Bajo la fecha | El {fecha} no es un día gestionable. El siguiente es el {sugerida}. | {fecha} is not a working day. The next one is {sugerida}. |
| `sin_horario` | En los horarios | Marca al menos un horario. | Check at least one time slot. |
| `horario_invalido` | Configuración, bajo la franja | {horario} termina antes de empezar: la hora de inicio tiene que ser anterior a la de fin. | {horario} ends before it starts: the start time must be earlier than the end time. |
| `sin_productos` | En la previsualización | Ningún segmento tiene productos después de las exclusiones: no se crea ninguna campaña. | No segment has products after the exclusions: no campaign is created. |
| `definicion_no_whatsmkt` | Bajo la definición | La definición elegida no es de WhatsMKT. | The chosen definition is not a WhatsMKT one. |
| `foto_formato` | Bajo la foto | La foto tiene que ser JPEG. | The photo must be a JPEG. |
| `foto_medidas` | Bajo la foto | La foto mide {ancho} × {alto} píxeles: tiene que medir 200 × 200. | The photo is {ancho} × {alto} pixels: it must be 200 × 200. |
| `foto_peso` | Bajo la foto | La foto pesa {peso}: el máximo es 1 MB. | The photo weighs {peso}: the maximum is 1 MB. |
| `adjunto_tipo` | Bajo el archivo | WhatsMKT no admite este tipo de archivo. Sube una imagen, un video, un audio o un PDF. | WhatsMKT does not accept this type of file. Upload an image, a video, an audio or a PDF. |
| `adjunto_peso` | Bajo el archivo | El archivo pesa {peso}: el máximo para {tipo} es {maximo}. | The file weighs {peso}: the maximum for {tipo} is {maximo}. |
| `adjunto_danado` | Bajo el archivo | El archivo está incompleto o dañado. Vuelve a descargarlo y súbelo de nuevo. | The file is incomplete or damaged. Download it again and upload it again. |
| `segmentos_superpuestos` | Bajo la fila del segmento | Los rangos de días se superponen con {segmento}. | The day ranges overlap with {segmento}. |
| `segmentos_con_hueco` | Bajo la tabla de segmentos | Quedan días de atraso sin segmento: {desde} a {hasta}. | Some days overdue have no segment: {desde} to {hasta}. |
| `informe_sin_encabezados` | Bajo el informe | El informe no tiene los encabezados CAMPAÑA, TIPO DE ENVIO y NUMERO en la fila 4. ¿Es el informe de WhatsMKT? | The report does not have the headers CAMPAÑA, TIPO DE ENVIO and NUMERO in row 4. Is it the WhatsMKT report? |
| `informe_sin_filas` | Bajo el informe | El informe no trae números enviados. | The report has no sent numbers. |
| `informe_ya_importado` | Diálogo de reemplazo | Esta campaña ya tiene un informe; confirma para reemplazarlo. | This campaign already has a report; confirm to replace it. |
| `campana_descartada` | Bajo el informe | La campaña está descartada. Restáurala primero. | The campaign is discarded. Restore it first. |
| `campana_no_descartada` | (respaldo) | Solo se puede eliminar una campaña descartada. Descártala primero. | Only a discarded campaign can be deleted. Discard it first. |

Las tres primeras son motivos de exclusión: además del texto corto, llevan un detalle para la columna Detalle, con su clave `whatsmkt.exclusiones.*`, como en MOWA:
- `macro_vacia`: es «La macro {n} ({etiqueta}) queda vacía y su columna no tiene valor por defecto.» / en «Macro {n} ({etiqueta}) is empty and its column has no default value.»

## 8. Textos de la interfaz (es / en)

Los de las confirmaciones, estados y acciones repiten los de MOWA con «WhatsMKT»: no se copian, se reusan las claves comunes donde ya existen (`mowaMes.accion.*`, `mowaMes.estado.*`) o se crean sus pares `whatsmkt.*` si el texto cambia. Los nuevos de WhatsMKT:

| Clave | es | en |
|---|---|---|
| `nav.whatsmkt` | WhatsMKT | WhatsMKT |
| `nav.whatsmkt.campana` | Campaña | Campaign |
| `nav.whatsmkt.seguimiento` | Seguimiento | Tracking |
| `nav.whatsmkt.configuracion` | Configuración | Settings |
| `whatsmkt.campana.titulo` | Campaña de WhatsMKT | WhatsMKT campaign |
| `whatsmkt.campana.intro` | Arma la lista de contactos sobre una selección de cartera, revisa la previsualización y crea la campaña. | Build the contact list from a portfolio selection, check the preview and create the campaign. |
| `whatsmkt.seccion.base` | Base | Base |
| `whatsmkt.seccion.archivo` | Archivo de carga | Load file |
| `whatsmkt.seccion.mensaje` | Mensaje | Message |
| `whatsmkt.seccion.programacion` | Programación | Scheduling |
| `whatsmkt.seccion.envio` | Envío | Sending |
| `whatsmkt.seccion.nombre` | Nombre de la campaña | Campaign name |
| `whatsmkt.seccion.previsualizacion` | Previsualización | Preview |
| `whatsmkt.archivo.definicion` | Definición de columnas | Column definition |
| `whatsmkt.archivo.sinDefiniciones` | No hay definiciones de WhatsMKT | There are no WhatsMKT definitions |
| `whatsmkt.archivo.crearAviso` | Crea una definición de WhatsMKT en Columnas de carga para armar el archivo. | Create a WhatsMKT definition in Load columns to build the file. |
| `whatsmkt.archivo.crear` | Crear en Columnas de carga | Create in Load columns |
| `whatsmkt.archivo.editar` | Editar en Columnas de carga | Edit in Load columns |
| `whatsmkt.archivo.col.macro` | Macro | Macro |
| `whatsmkt.archivo.col.encabezado` | Encabezado | Header |
| `whatsmkt.archivo.col.etiqueta` | Etiqueta | Label |
| `whatsmkt.archivo.col.contenido` | Contenido | Content |
| `whatsmkt.archivo.cincoMacros` | WhatsMKT publica hasta 5 variables por mensaje; esta definición tiene {n}. | WhatsMKT states up to 5 variables per message; this definition has {n}. |
| `whatsmkt.mensaje.modo.segmento` | Por segmento | By segment |
| `whatsmkt.mensaje.modo.global` | Global | Global |
| `whatsmkt.mensaje.modo.segmentoHint` | Un mensaje por segmento: se crea una campaña de WhatsMKT por cada segmento con productos. | One message per segment: a WhatsMKT campaign is created for each segment with products. |
| `whatsmkt.mensaje.modo.globalHint` | Un solo mensaje para toda la selección: se crea una sola campaña. | A single message for the whole selection: a single campaign is created. |
| `whatsmkt.mensaje.globales` | Mensajes globales | Global messages |
| `whatsmkt.mensaje.porSegmento` | Mensajes por segmento | Messages by segment |
| `whatsmkt.mensaje.editarEnConfiguracion` | Editar en la configuración | Edit in the settings |
| `whatsmkt.mensaje.largo` | {largo} / {maximo} caracteres | {largo} / {maximo} characters |
| `whatsmkt.mensaje.insertarMacro` | Insertar macro | Insert macro |
| `whatsmkt.mensaje.macro` | MACRO{n} · {etiqueta} | MACRO{n} · {etiqueta} |
| `whatsmkt.mensaje.vistaPrevia` | Así lo verá el cliente | This is how the customer will see it |
| `whatsmkt.mensaje.filaEjemplo` | Fila de ejemplo | Sample row |
| `whatsmkt.programacion.fecha` | Fecha de envío | Send date |
| `whatsmkt.programacion.fechaHint` | Se sugiere el siguiente día gestionable: de lunes a sábado, sin feriados. | The next working day is suggested: Monday to Saturday, without holidays. |
| `whatsmkt.programacion.usar` | Usar el {fecha} | Use {fecha} |
| `whatsmkt.programacion.horarios` | Horarios de envío | Send time slots |
| `whatsmkt.programacion.horariosHint` | Marca al menos uno. | Check at least one. |
| `whatsmkt.programacion.horario` | Horario {n} · {desde} – {hasta} | Time slot {n} · {desde} – {hasta} |
| `whatsmkt.programacion.antes` | Deseo que salga mi envío lo antes posible | Deseo que salga mi envío lo antes posible |
| `whatsmkt.programacion.antesHint` | Se copia en la ficha; no cambia la fecha ni los horarios. | It is copied into the sheet; it does not change the date or the time slots. |
| `whatsmkt.envio.tipo` | Tipo de envío | Sending type |
| `whatsmkt.envio.texto` | Solo texto | Text only |
| `whatsmkt.envio.archivo` | Texto + archivo | Text + file |
| `whatsmkt.envio.vcard` | Texto + vCard | Text + vCard |
| `whatsmkt.envio.adjunto` | Archivo | File |
| `whatsmkt.envio.subir` | Subir un archivo | Upload a file |
| `whatsmkt.envio.etiquetaContacto` | Etiqueta del contacto | Contact label |
| `whatsmkt.envio.foto` | Foto de perfil | Profile photo |
| `whatsmkt.envio.sinFoto` | Sin foto | No photo |
| `whatsmkt.envio.subirFoto` | Subir una foto | Upload a photo |
| `whatsmkt.envio.fotoHint` | JPEG de 200 × 200 píxeles, hasta 1 MB. | JPEG of 200 × 200 pixels, up to 1 MB. |
| `whatsmkt.envio.repetido` | Ya estaba en la biblioteca: se usa el mismo archivo. | It was already in the library: the same file is used. |
| `whatsmkt.nombre.segmentoAlFinal` | Se agrega el segmento al final para que los nombres no se repitan. | The segment is added at the end so the names do not repeat. |
| `whatsmkt.nombre.resultante` | Nombre de la campaña {segmento}: | Campaign name {segmento}: |
| `whatsmkt.previa.resumenVarias` | Se crearán {n} campañas · {filas} filas en total | {n} campaigns will be created · {filas} rows in total |
| `whatsmkt.previa.resumenUna` | Se creará 1 campaña · {filas} filas | 1 campaign will be created · {filas} rows |
| `whatsmkt.previa.irAlCampo` | Ir al campo | Go to the field |
| `whatsmkt.previa.sinExclusiones` | Ningún producto queda fuera. | No product is left out. |
| `whatsmkt.crear.una` | Crear campaña | Create campaign |
| `whatsmkt.crear.varias` | Crear {n} campañas | Create {n} campaigns |
| `whatsmkt.crear.problemas` | Corrige {n} problemas para crear. | Fix {n} problems to create. |
| `whatsmkt.crear.problemasUno` | Corrige 1 problema para crear. | Fix 1 problem to create. |
| `whatsmkt.subir.titulo` | Para subir a WhatsMKT | To upload to WhatsMKT |
| `whatsmkt.subir.creadas` | Se crearon {n} campañas (lote {lote}). Ahora súbelas a WhatsMKT con estos datos. | {n} campaigns were created (batch {lote}). Now upload them to WhatsMKT with this data. |
| `whatsmkt.subir.creada` | Se creó la campaña {id}. Ahora súbela a WhatsMKT con estos datos. | Campaign {id} was created. Now upload it to WhatsMKT with this data. |
| `whatsmkt.subir.paso1` | Descarga los archivos | Download the files |
| `whatsmkt.subir.paso2` | Completa el formulario de WhatsMKT | Fill in the WhatsMKT form |
| `whatsmkt.subir.paso3` | Después del envío, importa el informe | After sending, import the report |
| `whatsmkt.subir.dato.nombre` | Nombre de campaña | Campaign name |
| `whatsmkt.subir.dato.fecha` | Fecha y horarios | Date and time slots |
| `whatsmkt.subir.dato.antes` | Lo antes posible | As soon as possible |
| `whatsmkt.subir.dato.pais` | País | Country |
| `whatsmkt.subir.dato.cantidad` | ¿Cuántos teléfonos tiene en su Lista de contactos? | ¿Cuántos teléfonos tiene en su Lista de contactos? |
| `whatsmkt.subir.dato.tipo` | Tipo de envío | Sending type |
| `whatsmkt.subir.dato.mensaje` | Texto del mensaje | Message text |
| `whatsmkt.subir.irSeguimiento` | Ir al seguimiento de la campaña | Go to the campaign's tracking |
| `whatsmkt.seguimiento.titulo` | Seguimiento de WhatsMKT | WhatsMKT tracking |
| `whatsmkt.seguimiento.pendientes` | {n} campañas pendientes del informe | {n} campaigns with the report pending |
| `whatsmkt.seguimiento.pendientesUna` | 1 campaña pendiente del informe | 1 campaign with the report pending |
| `whatsmkt.estado.pendienteInforme` | Pendiente del informe | Report pending |
| `whatsmkt.seguimiento.pendiente.aviso` | Falta importar el informe de WhatsMKT. Cuando la campaña se haya enviado, descárgalo de WhatsMKT e impórtalo aquí. | The WhatsMKT report has not been imported yet. Once the campaign is sent, download it from WhatsMKT and import it here. |
| `whatsmkt.seguimiento.importar` | Importar el informe | Import the report |
| `whatsmkt.informe.hint` | El informe que descargas de WhatsMKT al terminar el envío (hoja «Informe»), en Excel, CSV o JSON, hasta 32 MB. | The report you download from WhatsMKT when the sending ends (“Informe” sheet), in Excel, CSV or JSON, up to 32 MB. |
| `whatsmkt.informe.descartada` | Esta campaña está descartada: restáurala para importar su informe. | This campaign is discarded: restore it to import its report. |
| `whatsmkt.informe.linea` | Informe del {fecha} · total informado {total} · {filas} filas | Report of {fecha} · reported total {total} · {filas} rows |
| `whatsmkt.informe.totalDistinto` | El informe dice {total} enviados y trae {filas} filas. La conciliación usa las filas. | The report says {total} sent and has {filas} rows. The reconciliation uses the rows. |
| `whatsmkt.conciliacion.productos` | Productos | Products |
| `whatsmkt.conciliacion.supervision` | Supervisión | Supervision |
| `whatsmkt.conciliacion.sinCorrespondencia` | Números del informe que no están en la carga: {n} | Report numbers that are not in the load: {n} |
| `whatsmkt.conciliacion.nombreInforme` | Nombre en el informe: {nombre} | Name in the report: {nombre} |
| `whatsmkt.conciliacion.nota` | Un producto cuenta como enviado si su número aparece en el informe. Si dos productos comparten número, el envío cuenta para los dos. | A product counts as sent if its number appears in the report. If two products share a number, the sending counts for both. |
| `whatsmkt.confirmar.eliminar.cuerpo` | Se borran la campaña, su lista de contactos, sus filas, exclusiones e informe. La biblioteca de adjuntos y los mensajes no cambian. No se puede deshacer. | The campaign, its contact list, rows, exclusions and report are deleted. The attachment library and the messages do not change. This cannot be undone. |
| `whatsmkt.configuracion.titulo` | Configuración de WhatsMKT | WhatsMKT settings |
| `whatsmkt.configuracion.herramientas` | Columnas de carga, Supervisores y Calendario laboral tienen su propia pantalla: | Load columns, Supervisors and Working calendar have their own screens: |
| `whatsmkt.configuracion.segmentos` | Segmentos y mensajes | Segments and messages |
| `whatsmkt.configuracion.sinPiso` | sin mínimo | no minimum |
| `whatsmkt.configuracion.sinTope` | sin máximo | no maximum |
| `whatsmkt.configuracion.col.segmento` | Segmento | Segment |
| `whatsmkt.configuracion.col.desde` | Desde (días) | From (days) |
| `whatsmkt.configuracion.col.hasta` | Hasta (días) | To (days) |
| `whatsmkt.configuracion.horario.desde` | Desde | From |
| `whatsmkt.configuracion.horario.hasta` | Hasta | To |
| `whatsmkt.configuracion.pronto` | Disponible pronto. | Available soon. |
| `whatsmkt.configuracion.globalesHint` | Para las campañas especiales, con un solo mensaje para toda la selección. | For special campaigns, with a single message for the whole selection. |
| `whatsmkt.configuracion.horarios` | Horarios de envío | Send time slots |
| `whatsmkt.configuracion.definicionDefecto` | Definición por defecto | Default definition |
| `whatsmkt.configuracion.topes` | Topes | Limits |
| `whatsmkt.configuracion.tope.mensaje` | Largo máximo del mensaje | Maximum message length |
| `whatsmkt.configuracion.tope.mensajeHint` | Valor inicial: el largo de un mensaje de WhatsApp (4096). No es un dato verificado de WhatsMKT. | Initial value: the length of a WhatsApp message (4096). It is not a verified WhatsMKT figure. |
| `whatsmkt.configuracion.tope.adjuntos` | Tamaño máximo de video, audio y PDF | Maximum size of video, audio and PDF |
| `whatsmkt.configuracion.tope.adjuntosHint` | Valor inicial: el límite general de WhatsApp para multimedia (16 MB). No es un dato verificado de WhatsMKT. | Initial value: WhatsApp's general limit for media (16 MB). It is not a verified WhatsMKT figure. |
| `whatsmkt.biblioteca.titulo` | Biblioteca de adjuntos | Attachment library |
| `whatsmkt.biblioteca.archivar` | Archivar | Archive |
| `whatsmkt.biblioteca.restaurar` | Restaurar | Restore |
| `whatsmkt.biblioteca.archivados` | Archivados ({n}) | Archived ({n}) |
| `whatsmkt.biblioteca.sinMetadatos` | Se guardó sin metadatos (EXIF, ubicación). | It was saved without metadata (EXIF, location). |

- «Deseo que salga mi envío lo antes posible» y «¿Cuántos teléfonos tiene en su Lista de contactos?» quedan en español también en inglés: son el texto exacto del formulario de WhatsMKT, y el operador los busca así.
- Las citas de nombres usan las comillas del idioma (`camposAdicionales.nombreCitado`).
- Un rango en inglés es "From … To", no "Until": en los encabezados, en las etiquetas accesibles de cada campo y en sus errores.
- Las fechas van con `format.ts`, y los meses sueltos con `formatMesGestion`.

## 9. A 360 px

- Todas las tablas son apilables desde el inicio (`.table--apilable`): columnas del archivo, mensajes por segmento, muestra, exclusiones, campañas, conciliación, segmentos y biblioteca. Ninguna se desplaza de lado (RF-WM-44).
- Los `.segmented` del lote se desplazan de lado dentro de su caja si no caben, con el elegido siempre a la vista.
- El `dl` de la ficha se apila: el dato arriba, y el valor con su «Copiar» debajo.
- La barra «Insertar macro» se parte en varias líneas; ningún botón se corta.
- La página nunca desborda: lo comprueba una prueba de geometría en las tres pantallas.

## 10. Accesibilidad

- Controles nativos, con las ayudas asociadas por `aria-describedby` y los grupos en `fieldset` con `legend`.
- Los campos condicionales ocultos van con `hidden`: no se leen ni reciben foco.
- Al fallar la validación al crear, el foco va al primer error (RF-WM-43), y el resumen de la previsualización enlaza cada problema con su campo.
- Los resultados (guardado, copiado, subido, importado, descartado) se anuncian en `role="status"`. Los errores que bloquean van en `role="alert"`.
- Contraste AA en claro y oscuro, sin opacidad en el texto que se puede leer u operar.

## 11. Pruebas mínimas

- **T-WM-F1 (navegación y configuración):**
  - el desplegable de WhatsMKT y los enlaces a Herramientas con su vuelta;
  - segmentos con hueco y superpuestos, por su código;
  - mensajes con `TextosGuardados`: insertar macro, el contador, el emoji en su posición, la macro inexistente y la vista previa;
  - horarios, plantilla con su tope, definición por defecto y topes;
  - la biblioteca: subir, archivo repetido, archivar y restaurar.
- **T-WM-F2 (campaña):**
  - las secciones en orden, con «Editar en Cartera» y «Editar en Columnas de carga» y sus vueltas;
  - el modo por segmento y el global, con el `select` de mensajes y sus `optgroup`;
  - la fecha sugerida, el `min`, y un día no gestionable con «Usar el …»;
  - sin horarios, el error en el `fieldset`;
  - los tipos de envío con sus campos condicionales, que conservan lo escrito y mandan solo lo del elegido;
  - la foto con sus tres errores;
  - el nombre con su contador y el nombre resultante por campaña;
  - la previsualización del lote, con el `.segmented`, las cifras, el mensaje de ejemplo, la muestra con etiquetas, y las exclusiones paginadas con su detalle;
  - sin productos; «Crear» inactivo con el motivo; el 409 de la fecha;
  - las fichas del lote, con cada «Copiar» y su anuncio.
- **T-WM-F3 (seguimiento):**
  - Activas y Descartadas, filtros y pendientes;
  - importar, reemplazar, y el total distinto;
  - la conciliación con supervisión aparte y los números sin correspondencia;
  - descartar, restaurar y eliminar.
- **axe,** en claro, oscuro y 360 px, en las tres pantallas, con la previsualización de un lote, una ficha, la conciliación y la biblioteca.
- **Capturas para `designer`,** antes del commit de cada corte: las mismas, en claro y oscuro, a 1280 y a 360 px, en es y en.

## 12. Dudas que cambian el diseño

Se aplica la regla provisional de [requerimientos-whatsmkt.md](requerimientos-whatsmkt.md) §11. Si el usuario responde otra cosa, cambia esto:

| Duda | Qué hace la pantalla hoy | Si la respuesta es otra |
|---|---|---|
| DU-WM-1 (5 macros) | Avisa con más de 5 y no bloquea (§3.3) | Con un límite, el constructor no deja agregar la sexta, y el aviso pasa a ser una regla de la plataforma (§11.2 del motor) |
| DU-WM-3 (largo) | Cuenta con los marcadores (§5.1) | Con los valores reemplazados, el contador va en la previsualización, por campaña, con la fila más larga |
| DU-WM-4 (vCard) | Solo la etiqueta del contacto (§3.6) | Más campos debajo del radio, con su origen |
| DU-WM-5 (foto) | Opcional, con «Sin foto» (§3.6) | Obligatoria: sin «Sin foto», con su error al crear |
| DU-WM-6 (nombre) | Variables `{fecha_corte}` y `{segmento}`; el segmento al final en un lote (§3.7) | Más fichas de variables (filtros, fecha de envío) |
| DU-WM-7 (total) | Avisa y no bloquea (§4.2) | Un error que rechaza el informe |
| DU-WM-9 (costo y límite) | Sin costo ni límite | Un panel de límite como el de MOWA, con su barra de uso |
| DU-WM-2, 8, 10 y 11 | No cambian el diseño: son contenido o formato | — |
