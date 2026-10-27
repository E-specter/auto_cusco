# Campos adicionales: reglas de interfaz

Reglas vinculantes para crear un campo adicional desde el mapeo y para mostrarlo en el resto de la aplicación (T-CA-F0; las construye T-CA-F1). Complementan RF-64 a RF-66 de [atomics-requirements.md](atomics-requirements.md), el plan T-CA-C1 (§28 del plan del coordinador del motor) y las reglas del mapeador, [mapeador-encabezados-interfaz.md](mapeador-encabezados-interfaz.md). El contrato es el de T-CA-B2.

Responsable: `designer`. Un cambio a estas reglas se acuerda con `designer` antes de escribirlo.

---

## 1. Principios

1. **Siempre por su nombre legible.** El nombre técnico (`ad_…`) es del sistema: la pantalla nunca lo muestra como nombre. Sale solo donde hoy ya sale el técnico de un campo base, como texto secundario en el selector de variables.
2. **Distinto con palabras, no solo con color.** Un adicional se reconoce por el texto «Adicional», en un grupo o en un `.tag`, y no por un color o un icono solos (RF-34).
3. **El mismo trato que un campo base.** Se elige, se filtra y se usa igual. Lo que cambia es dónde aparece en una lista (al final, en su grupo) y su marca.
4. **Crear es un gesto deliberado, con consecuencias a la vista.** El tipo no se cambia después, y el campo queda en el catálogo aunque se cancele la carga. El formulario dice las dos cosas antes de crear, no después.
5. **El backend decide.** La unicidad del nombre, el nombre técnico y la conversión de valores son del backend. La pantalla solo impide enviar un formulario incompleto.

## 2. Crear un campo desde el mapeo (RF-64)

Es una parte opcional del componente `MapeadorEncabezados`. Otro catálogo que use el mapeador puede no admitir campos adicionales, y entonces no la muestra.

```ts
const mapeador = montarMapeador(raiz, {
  analisis, campos, validar,
  crearCampo,   // opcional: (indice, nombre_legible, tipo, signal) => Promise<CampoAdicionalCreadoRespuesta>
});
mapeador.fijarCampos(campos);   // la lista nueva del catálogo; conserva lo elegido (no es fijarAnalisis)
```

Sin `crearCampo`, no hay referencia ni formulario. La página de `/cargas` lo pasa envuelto como `validar`: un `404 borrador_no_encontrado` la devuelve al paso 1 (§5 del mapeador).

### 2.1 La referencia, al final del mapeo

- **Bajo la tabla y sobre las advertencias de lectura,** una línea: «¿Una columna trae un dato que no está en la lista?», seguida de un botón `.btn--sm` «Crear un campo adicional».
  - El botón es de divulgación, con `aria-expanded` y `aria-controls`, y abre el formulario en el mismo lugar, en el flujo.
  - **No es un diálogo:** en `/cargas` el mapeador ya está dentro de uno, y no se apilan diálogos.
- **Solo aparece si hay alguna columna que se pueda usar:** una sin coincidencia o que esté en «No cargar esta columna».
- **Con la tabla recogida** («todo listo», §3.2 del mapeador), la referencia sigue a la vista bajo el aviso de éxito: crear un campo no obliga a abrir la tabla.

### 2.2 El formulario

Un `.panel` con tres campos, en este orden:

| Campo | Control | Regla |
|---|---|---|
| **Columna del archivo** | `select` | Solo las columnas que se pueden usar (§2.1), cada una como «C · «Monto en mora»», con la letra o el número de §3.3 del mapeador. Si hay una sola, va elegida; si hay varias, empieza en «Elige una columna». Bajo el `select`, un `.field__hint` con los ejemplos de la columna elegida, en mono, como en la tabla: «Ejemplos: 1500.50 · 82.00 · 310.75». Así se decide el tipo mirando los datos. |
| **Nombre del campo** | `input.input` | Empieza con el encabezado de la columna tal como viene, para corregirlo. `maxlength` 80, el del contrato. Hint: «Así lo verás en Cartera, en los textos y en las columnas de carga. Se puede cambiar después». |
| **Tipo de dato** | `fieldset` con tres radios | «Texto», «Número» y «Fecha». **Ninguno viene marcado:** un tipo equivocado no se corrige después, así que se elige a conciencia. Hint del grupo: «No se puede cambiar después: para otro tipo, se crea otro campo. Un valor que no sea de este tipo queda vacío y se avisa en su fila». |

- **Antes de las acciones,** un `.notice--info` de una línea: «El campo queda en el catálogo para las próximas sábanas, aunque canceles esta carga». Es una **decisión del usuario del 2026-10-27**, confirmada por `architec`: el campo se crea al pulsar «Crear campo», no al confirmar la carga, y si no se quería, se archiva (§4).
- **Acciones:** «Cancelar» (`.btn`), que cierra el formulario sin cambiar nada y devuelve el foco a «Crear un campo adicional», y «Crear campo» (`.btn--primary`, con `data-loading` mientras responde).
- **«Crear campo» queda inactivo** hasta que haya columna, nombre (después de quitar los espacios de los extremos) y tipo. Es lo único que decide la interfaz. Un nombre repetido o demasiado largo lo rechaza el backend (§2.4).
- **Al abrir,** el foco va al primer campo sin completar: la columna si hay varias, y el nombre si hay una sola.

### 2.3 Al crear

- **La columna queda asignada al campo nuevo,** con origen `manual`. El componente:
  - llama a `fijarCampos(campos)` con la lista que devuelve el backend;
  - elige el campo en esa fila, con su lista de campos;
  - valida, como cualquier cambio.

  No usa `fijarAnalisis`, porque descartaría lo elegido en las demás columnas. Al confirmar la carga, la asignación se recuerda como cualquier otra (RF-61).
- **En esa fila:**
  - el tag es `tag--info` «Campo nuevo», con la línea «Creado en esta carga», mientras la columna tenga ese campo;
  - si después se elige otro campo, el tag vuelve a las reglas de §3.4 del mapeador;
  - la marca vive en el estado del componente. Si se vuelve a leer el archivo, por cambiar la hoja, el separador o la codificación (`fijarAnalisis`), se pierde, aunque el campo siga en el catálogo: la columna vuelve a encontrarlo como «Coincide», porque su encabezado es el alias del campo. En otra hoja, se elige en la lista. Es lo esperado.
- **El formulario se cierra.** En la región `role="status"` del componente se anuncia: «Se creó el campo «Monto en mora» y se asignó a la columna C». El foco pasa a la lista de campos de esa fila.
- **La lista no se mueve bajo el cursor:**
  - en «Por revisar», la fila sigue a la vista hasta que se cambie el filtro (§3.1 del mapeador);
  - en «Todas», la fila se lleva a la vista si quedó fuera.
- **El campo nuevo aparece enseguida en todas las listas de campos del mapeo,** en su grupo (§3.1), y en las demás filas con «· en uso en C», como cualquier campo en uso.

### 2.4 Errores

Por su `codigo`, con el texto de `mapeador.error.*`. Lo escrito se conserva siempre.

| Respuesta | Dónde | Qué dice y qué ofrece |
|---|---|---|
| `409 nombre_repetido` | Bajo «Nombre del campo», con `.field__error`, `aria-invalid` y `aria-describedby`. El foco vuelve al nombre | «Ya existe el campo «Saldo de capital pendiente». Elígelo en la lista o usa otro nombre». `{campo}` es el nombre legible del `campo` que trae el 409: su `etiqueta` o, si es base, `t(clave_etiqueta)`. Si ese campo se puede elegir para la columna, porque no lo usa otra, el error lleva un botón `.btn--sm` «Usar «Saldo de capital pendiente» en la columna C»: lo asigna y cierra el formulario |
| `404 columna_inexistente` | Bajo «Columna del archivo» | El texto del código. No debería pasar, porque la lista sale del análisis |
| `404 borrador_no_encontrado` | La página, como al validar: vuelve al paso 1 | El texto del código (§5 del mapeador) |
| `422` (nombre vacío o de más de 80). Es la validación estándar, sin `codigo`, y se reconoce por el estado | Bajo «Nombre del campo» | «Escribe un nombre de hasta 80 caracteres» (`mapeador.vista.adicional.nombreInvalido`) |
| Sin red u otro fallo | Bajo las acciones, `role="alert"` | `console.upload.error.network` o `common.errorBody` |

### 2.5 Después de la carga

Un valor que no se convierte al tipo del campo queda vacío y llega como incidencia de su fila, con el código `valor_no_convertible`. Se lista en la consola de cargas como las demás incidencias, con su texto («El valor no corresponde al tipo del campo adicional; se dejó vacío»). No hace falta nada nuevo.

## 3. Cómo se distingue un adicional en las listas (RF-66)

**Un solo ayudante para el nombre:** `etiquetaDeCampo({ nombre, etiqueta, clave })`, en `lib/campos.ts`. Devuelve:
- `etiqueta`, si viene (un adicional);
- si no, `t(clave)`;
- si no hay traducción, el nombre humanizado, como hoy.

Reemplaza a `etiquetaCampo(nombre)` en todo lugar que muestre un campo de la cartera, y cuando el contrato trae `etiqueta`, ordenar por nombre usa este mismo ayudante. Hoy esos lugares son:
- Cartera (`cartera.astro`): el criterio de segmentación, las columnas a mostrar y los encabezados de la tabla;
- el selector de selección (`selector-seleccion.ts`): los filtros, el orden y los indicadores;
- el mapeador.

El editor y el constructor usan `etiquetaVariable`, que gana el mismo orden de prioridad con la `etiqueta` de `VariableRespuesta`.

| Dónde | Control | Cómo se ve un adicional |
|---|---|---|
| Filtros, orden, segmentación e indicadores de la selección | `select` nativo | Al final, en un `optgroup` «Campos adicionales», ordenado por nombre. Los campos base quedan como están. Un `optgroup` es la única marca que un `select` nativo lee en voz alta y muestra igual en todos los navegadores |
| Columnas a mostrar de Cartera | Casillas | Después del nombre, `.tag tag--neutral` «Adicional» |
| Encabezados de la tabla de Cartera | `th` | Solo el nombre legible. La marca se ve al elegir la columna; repetirla en cada encabezado es ruido |
| Selector de variables del editor y del constructor | Botones agrupados por origen (§2.2 del motor) | Dentro de su origen («Cartera»), con `.tag tag--neutral` «Adicional» junto al tag del tipo. El técnico (`ad_…`) sigue como texto secundario, como el de todos |
| Columna de variable directa del constructor | `select` con `optgroup` por origen | El texto de la opción pasa a ser «Monto en mora (número) · adicional» |
| Fichas de variable en el texto del editor | Ficha en línea | Solo el nombre legible, sin marca, igual que las demás fichas: ahí importa qué dato sale, no de dónde viene |
| Lista de campos del mapeador | Combobox (§3.5 del mapeador) | Un tercer grupo, «Campos adicionales», después de «Otros campos». La búsqueda los encuentra por su nombre y por su alias, que es el encabezado de origen |

**Un adicional archivado** no se ofrece en ninguna de esas listas. Si una selección, una definición o un speech guardados ya lo usan, sigue funcionando y no bloquea guardar ni generar. Se avisa así:

- **En Cartera, el editor y el constructor,** el aviso sale de la marca `archivado: true` que traen `/cartera/campos` y `VariableRespuesta` (T-CA-B2), con texto del frontend:
  - el filtro, la ficha o la columna que lo usa muestra su nombre y un `.tag tag--advertencia` «Archivado». En un `select` nativo, como el filtro o el orden, no cabe un `.tag`: la opción dice «Monto en mora (archivado)». El tag queda para las casillas, las fichas y el selector de variables;
  - sobre la vista previa de `/columnas` y de `/generar-carga`, y sobre el resultado de la selección en Cartera, va un `.notice--info` de una línea: «Usa el campo archivado «Monto en mora»: sigue funcionando, pero ya no se ofrece». Con varios, los nombra separados por comas.
  - Los textos van en `camposAdicionales.archivado` y `camposAdicionales.avisoArchivado`.
- **En MOWA MES,** la previsualización del speech trae su propio aviso del backend (T-MM-B12, `archivados_entre()`), y la pantalla muestra ese. Para que no haya dos textos distintos para lo mismo, el texto del backend de MOWA usa las mismas palabras que `camposAdicionales.avisoArchivado`.

## 4. Renombrar, archivar y reactivar (RF-65)

T-CA-F1 no lo incluye; propongo abrirlo como T-CA-F2. Lo dejo fijado aquí para que el contrato de B2 (el `GET` y el `PATCH` de `…/campos-adicionales`) tenga pantalla.

- **Dónde:** en `/cargas`, junto a «Subir sábana», un botón `.btn` «Campos adicionales (N)» abre un `dialog.dialog--wide`.
  - Va ahí y no en Cartera porque los campos son del catálogo de la sábana: se crean al cargarla y se relacionan con sus encabezados.
  - Con cero campos, el botón igual está, y el diálogo dice: «Todavía no hay campos adicionales. Se crean al subir una sábana, desde la revisión de columnas».
- **Una tabla:**
  - columnas: Nombre, Tipo, Encabezado de origen (mono) y Estado («Activo» o `.tag tag--advertencia` «Archivado»);
  - las acciones por fila;
  - los archivados al final.
- **«Renombrar»:**
  - el nombre de la fila pasa a ser un `input` con «Guardar» y «Cancelar» en la misma fila. No se abre un segundo diálogo;
  - hint: «Lo que ya lo usa sigue funcionando: se guarda por su nombre interno, que no cambia»;
  - el `409 nombre_repetido` va bajo el `input`, como en §2.4.
- **«Archivar»:**
  - no pide confirmar, porque se deshace con «Reactivar» en la misma fila;
  - el estado (`role="status"`) dice: «Se archivó «Monto en mora». Deja de ofrecerse; lo que ya lo usa sigue funcionando»;
  - el foco pasa a «Reactivar».
- **«Reactivar»:** el estado dice «Se reactivó «Monto en mora»», y el foco pasa a «Archivar».
- **El tipo se muestra, pero no se edita.**

## 5. Accesibilidad

- La referencia es un botón de divulgación. El formulario tiene `aria-labelledby` con su título: «Crear un campo adicional».
- Los tres radios van en un `fieldset` con `legend` «Tipo de dato», y su hint se asocia con `aria-describedby` al `fieldset`.
- Los errores siguen §2.4: bajo su campo, con `aria-invalid` y `aria-describedby`; los generales, en `role="alert"`.
- El resultado de crear, archivar o reactivar se anuncia en una región `role="status"` que ya existe, sin mover el foco a ella.
- Contraste AA en claro y oscuro, con axe en los estados de §7.

## 6. Textos

- Los del componente, en `mapeador.vista.adicional.*` (es y en). No usan los prefijos que vigila la prueba espejo del backend.
- Los de las listas y del diálogo de §4, en `camposAdicionales.*`.
- Los de error y la incidencia los publica el backend: `mapeador.error.nombre_repetido` con `{campo}`, `mapeador.error.columna_inexistente` e `incidencia.valor_no_convertible`.

## 7. Pruebas mínimas (T-CA-F1)

- **Vitest:**
  - `etiquetaDeCampo`, con etiqueta literal, con clave y sin traducción;
  - las columnas que se pueden usar para crear un campo: sin coincidencia o en «No cargar»;
  - el estado de «Crear campo», que necesita columna, nombre sin espacios y tipo.
- **Playwright:**
  - con el mapeador:
    - crear desde la referencia asigna la columna, con el tag «Campo nuevo», el anuncio y el foco en su lista; lo elegido en las demás filas no cambia;
    - el campo nuevo sale en las demás filas «en uso»;
    - el cuerpo que se manda es `{indice, nombre_legible, tipo}`;
    - el 409 nombra el campo y «Usar … en la columna C» lo asigna;
    - el 404 del borrador vuelve al paso 1;
    - sin `crearCampo` no hay referencia;
    - sin columnas que se puedan usar, tampoco;
  - en las listas:
    - un adicional sale en el `optgroup` «Campos adicionales» de los filtros, y con el tag en las columnas de Cartera y en el selector de variables;
    - uno archivado no se ofrece; donde ya se usa, muestra «Archivado», y la vista previa de `/columnas` lleva el aviso, armado con la marca `archivado` y no con un texto del backend.
- **axe,** en claro, oscuro y 360 px: el formulario abierto, el formulario con el 409 y el selector de variables con un adicional.
