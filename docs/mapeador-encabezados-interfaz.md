# Mapeador de encabezados: reglas de interfaz

Reglas vinculantes para el componente compartido `MapeadorEncabezados` (T-MAP-F1, de `designer`) y para la pantalla que lo usa en la carga de sábanas (T-MAP-F2, de `dev_frontend_motor_texto_enriquecido`). Complementan el diseño técnico de [mapeador-encabezados.md](mapeador-encabezados.md) y RF-57 a RF-63 de [atomics-requirements.md](atomics-requirements.md). Reemplazan la lista de experiencia de §7 de ese diseño.

Responsable: `designer`. Un cambio a estas reglas se acuerda con `designer` antes de escribirlo.

---

## 1. Principios

1. **Claro y sencillo, por pedido del usuario.** El caso de todos los días, en el que todo coincide, se resuelve con un clic: ver el resumen y confirmar. La tabla completa aparece solo cuando hay algo que revisar o cuando se la pide.
2. **El backend decide; la pantalla muestra.** El estado de cada encabezado, la sugerencia y los problemas vienen del análisis y de `/validacion`. La pantalla no calcula similitudes ni repite reglas de validación.
3. **Nada se acepta sin un gesto.** Un parecido llega preseleccionado, pero hasta que alguien lo acepte sigue «por revisar». Elegir otra vez el mismo campo en la lista no cuenta como revisión (§3.4 del diseño).
4. **Todo en palabras.** Ni porcentajes de similitud ni nombres técnicos de campo: cada campo se muestra con su etiqueta (`campo.<nombre>`) y cada estado con su texto, además del icono o el color.
5. **El componente no conoce la sábana.** Recibe un catálogo y un análisis. Con otro catálogo sirve para otra carga sin cambios (RF-63).

## 2. Montaje

Mismo patrón que `EditorTexto`: la página renderiza el componente, escucha su evento en la raíz y después lo monta.

```ts
<MapeadorEncabezados id="mapeador" />

const mapeador = montarMapeador(raiz, {
  analisis,        // AnalisisRespuesta del borrador
  campos,          // CatalogoMapeadorRespuesta.campos
  validar,         // (asignaciones, signal) => Promise<ProblemaMapeoRespuesta[]>, llama a /validacion
});

mapeador.estado();             // { asignaciones, problemas, listo, pendiente, modificado }
mapeador.fijarAnalisis(nuevo); // tras cambiar hoja, separador o codificación
mapeador.fijarProblemas(p);    // el 422 de confirmar: los muestra sin tocar lo elegido
mapeador.destruir();
```

- **Evento `mapeocambiado`,** con `bubbles`: `{ asignaciones, problemas, listo, pendiente }`. `asignaciones` va con una por columna listada, con su `origen`; `listo` es «sin problemas en la última validación terminada»; `pendiente`, que hay una validación en curso. Confirmar solo se permite con `listo && !pendiente`.
- **Validación en vivo:** cada cambio llama a `validar` con 300 ms de espera y cancela el pedido anterior, como el editor de texto. Los problemas iniciales del análisis se muestran desde el primer momento, sin esperar.
- **`modificado`:** el analista eligió o aceptó algo, así que cambiar una opción de lectura lo descartaría (§4).
- **`fijarProblemas(problemas)`:** toma los problemas como una validación terminada, los muestra en su lugar (los de fila bajo su fila, los sin columna arriba, y la tabla vuelve si estaba recogida) y emite, sin tocar las asignaciones. F2 lo usa con el 422 de confirmar (§5).
- **`destruir()`:** quita los listeners de `document`, aborta la validación en curso y deja de emitir.

## 3. Estructura

```
┌ Resumen ──────────────────────────────────────────────────────────┐
│ 45 columnas · 3 200 filas · hoja «VENCIDA»                         │
│ [ Por revisar (3) | Todas (45) ]            [Aceptar sugerencias (2)]│
└────────────────────────────────────────────────────────────────────┘
┌ Problemas (solo si hay alguno sin fila) ────────────────────────────┐
│ ⚠ Falta asignar una columna al campo obligatorio Pagaré. [Elegir…] │
└────────────────────────────────────────────────────────────────────┘
 Col. │ Encabezado del archivo │ Ejemplos        │ Estado        │ Campo de carga
  C   │ Saldo Capital          │ 1500.50 · 82.00 │ POR REVISAR   │ [Saldo de capital pendiente ▾] [Aceptar]
      │                        │                 │ Parecido a «Saldo de capital pendiente»
```

### 3.1 Resumen y filtro

- **Una línea de contexto,** en mono: «45 columnas · 3 200 filas», más «· hoja «VENCIDA»» en una hoja de cálculo.
- **El filtro es un `.segmented`:** «Por revisar (N) · Todas (M)».
  - «Por revisar» lista las columnas con un parecido sin aceptar o con un problema. Si hay alguna, abre ahí; si no, en «Todas».
  - **La lista no se mueve bajo el cursor:** una fila que se revisa estando en «Por revisar» sigue a la vista hasta que se cambia el filtro. Solo cambia el contador.
- **«Aceptar sugerencias (N)»** (`.btn`) acepta de una vez todos los parecidos pendientes. Solo aparece si hay alguno.

### 3.2 Todo listo: la tabla se recoge

Si el análisis no deja nada por revisar ni ningún problema, el componente muestra un `.notice--success`: «Las 45 columnas se relacionaron con los campos de carga». Debajo va «Ver columnas», un botón de divulgación con `aria-expanded` que abre la tabla completa. Es el caso de todos los días, y se confirma sin abrir nada.

### 3.3 La tabla

Una `.table` dentro de `.table-scroll`, con `<caption>` «Columnas del archivo», y `.table--apilable` a menos de 48rem. Una fila por columna del archivo:

| Columna | Qué muestra |
|---|---|
| **Col.** | La posición en el archivo: letra en una hoja de cálculo (A, B… AA), como la ve el analista en Excel; número en CSV y JSON. Distingue dos encabezados iguales, como las dos «Pagare» de la sábana (M-1) |
| **Encabezado del archivo** | El texto tal como viene |
| **Ejemplos** | Hasta 3, en mono, separados por « · », cada uno recortado con puntos suspensivos y completo en `title`. Sin ejemplos, «—» |
| **Estado** | Un `.tag`, y debajo una línea corta cuando hace falta (§3.4) |
| **Campo de carga** | El `select` y, en un parecido pendiente, el botón «Aceptar» (§3.5) |

### 3.4 Estados

El `.tag` muestra lo que vale **ahora** para esa columna. Mientras tenga el campo que trae el análisis, muestra su estado del análisis. «Elegido a mano» aparece solo si el campo es distinto del sugerido; si el analista vuelve al campo original, el tag vuelve a su estado del análisis.

| Situación | `.tag` | Línea debajo |
|---|---|---|
| Recordado | `tag--info` «Recordado» | «De una carga anterior» |
| Coincide | `tag--vigente` «Coincide» | — |
| Parecido sin aceptar | `tag--advertencia` «Por revisar» | «Parecido a «Saldo de capital pendiente»» |
| Parecido aceptado | `tag--vigente` «Aceptado» | — |
| Sin coincidencia | `tag--neutral` «Sin coincidencia» | — |
| Cambiado a mano | `tag--neutral` «Elegido a mano» | — |

### 3.5 El campo de carga

- **El `select`** tiene, en este orden:
  - «No cargar esta columna»;
  - el grupo «Obligatorios»;
  - el grupo «Otros campos», ordenado por etiqueta (`ordenarPorEtiqueta`).
- **Un campo que ya usa otra columna sale deshabilitado** en el `select` de las demás filas (decisión del usuario, 2026-10-27).
  - La opción sigue diciendo dónde está en uso, «Saldo de capital pendiente · en uso en C», para que se entienda por qué no se puede elegir. Los lectores de pantalla la anuncian como no disponible.
  - La fila que tiene el campo lo conserva habilitado en su propio `select`.
  - Para intercambiar dos columnas, primero se pasa una a «No cargar». Un hint sobre la tabla lo dice una sola vez: «Un campo se usa en una sola columna. Para pasarlo a otra, primero deja la suya en «No cargar»».
  - **Si el análisis llega con un repetido** (por ejemplo, un recordado y una coincidencia en el mismo campo): las dos filas lo tienen elegido y habilitado en su `select`, cada una con el problema `campo_repetido` bajo el `select` y contada en «Por revisar». En las demás filas el campo sale deshabilitado, con «· en uso en C y F». El problema se va cuando una de las dos elige otro campo o «No cargar».
- **«Aceptar»** (`.btn--sm`) aparece solo en un parecido sin aceptar. Manda `parecido_aceptado` con el mismo campo sugerido. Al aceptar, el botón desaparece y el foco pasa al `select` de esa fila.
- **Qué origen manda cada gesto** (para que el backend y la pantalla digan lo mismo, §3.4 del diseño y `resolver_asignaciones`):
  - **En una columna parecida:** con el campo sugerido elegido en el `select`, manda el origen inicial no revisado que trae el análisis (`coincide`), nunca `manual`, porque en el backend `manual` contaría como revisión. Así, volver a elegir el sugerido en la lista no lo acepta; para eso está «Aceptar», que manda `parecido_aceptado`. Un campo distinto del sugerido, o «No cargar», manda `manual`.
  - **En una columna no parecida:** con el campo del análisis, `recordado` o `coincide`, como venía; con otro, `manual`. El backend recalcula el origen si no cuadra.
  - Una columna `sin_coincidencia` que se queda en «No cargar» se guarda como `manual` (decisión de B1). No cambia lo que muestra la pantalla.

### 3.6 Problemas

- **Problema de una columna** (`parecido_sin_revisar`, y `campo_repetido` cuando lo trae el análisis): bajo su `select`, con `.field__error`, `aria-invalid` y `aria-describedby`. La fila cuenta en «Por revisar». Con el campo en uso deshabilitado, ningún gesto de la pantalla produce un `campo_repetido` nuevo.
- **Problema sin columna** (`obligatorio_sin_columna`, que llega sin índice): en un `.notice--danger` arriba de la tabla, uno por campo. Lleva el botón «Elegir la columna», que pasa a «Todas» y lleva el foco al `select` de la primera columna en «No cargar». Es el único resumen de la pantalla (§9.4 del motor).
- **`{campo}` en los textos de problema** se llena con la etiqueta visible del campo, nunca con su nombre técnico.
- Los códigos de protección (`campo_desconocido`, `indice_fuera_de_rango`, `asignacion_faltante`, `indice_repetido`, y `campo_repetido` fuera del análisis inicial) no los produce la pantalla. Si alguno llegara, va al resumen con su texto.

### 3.7 Advertencias de lectura

`advertencias` (por ahora, `valor_no_escalar`) van bajo la tabla en un `.notice--info` plegable: «Hay 12 valores que se guardaron como texto JSON. [Ver dónde]». Cada línea dice «Fila 14, columna «Datos»: …». No bloquean confirmar.

## 4. Opciones de lectura (en la pantalla, F2)

Hoja, separador y codificación son de la pantalla de carga, sobre el componente, porque vuelven a analizar el borrador:
- **«Hoja»:** un `select` con `hojas`, solo si hay más de una.
- **«Separador»** (CSV): un `select` con los separadores del catálogo, por su nombre («Coma», «Punto y coma», «Tabulación»). El detectado lleva «(detectado)».
- **«Codificación»** (CSV): un `select` con `codificaciones` tal cual (`utf-8`, `windows-1252`…), y «(detectada)» en la detectada.
- **Cambiar una opción** vuelve a analizar y llama a `fijarAnalisis`. Si el analista ya eligió algo a mano o aceptó sugerencias, primero confirma: «Cambiar la hoja vuelve a leer el archivo y descarta lo que elegiste en las columnas». Un 400 se dice bajo la opción, con su código.

## 5. Pantalla de cargas (F2, de `dev_frontend`)

- Dos pasos a la vista, «1. Elegir archivo» y «2. Revisar columnas», con el paso actual marcado con `aria-current="step"`.
- **«Confirmar y cargar»** (`.btn--primary`) queda inactivo mientras el componente no esté `listo`, con el motivo en texto: «Revisa 3 columnas para poder cargar» o «Falta asignar el campo obligatorio Pagaré».
- **«Cancelar»** (`.btn`) borra el borrador (`DELETE`) y vuelve al paso 1.
- **Errores al subir o reanalizar:** por su `codigo`, con el texto de `mapeador.error.*` (§7). Si la hoja no existe, se ofrecen las `hojas` del error en el `select` de hoja. Descartar un borrador ya vencido responde 204: «Cancelar» siempre vuelve al paso 1 sin error.
- **Un 422 al confirmar con `problemas`** se pasa al componente y la pantalla vuelve al paso 2 con el resumen.

## 6. Accesibilidad

- Cada `select` se llama «Campo de carga para la columna C, «Saldo Capital»». Cada «Aceptar» se llama «Aceptar Saldo de capital pendiente para la columna C».
- El contador de «Por revisar» se anuncia en una región `aria-live="polite"`, solo cuando cambia.
- El orden de tabulación es el de lectura: filtro, «Aceptar sugerencias», y después cada fila.
- Contraste AA en claro y oscuro, con axe en los estados de §8.

## 7. Textos

Los textos del componente van en `mapeador.*` (es y en). Los de estado, origen, problema y advertencia los publica el backend en el enum, con los ajustes de `designer` del 2026-10-24. Las cinco etiquetas `campo.*` que faltan (`documento`, `vencimiento_operativo`, `pagare_duplicado`, `validador`, `cod_tipo_basilea`, M-9) entran en F1, con su prueba contra el catálogo.

**Lo que publica B3b para la pantalla** (pedido por `designer`):
- los errores de `/mapeador` llevan `codigo` (enum `CodigoErrorMapeador`), con sus datos (`maximo_mb`, `hoja` y `hojas`) y su texto `mapeador.error.*`;
- el catálogo trae `separadores`, en el orden de la detección, y el `select` los muestra en ese orden;
- el análisis trae `detectados` (enum `OpcionDetectable`), que dice qué opciones se detectaron, para el «(detectado)».

## 8. Pruebas mínimas

- **Vitest:** el estado puro. Asignaciones iniciales desde el análisis, aceptar uno y aceptar todos, una elección manual, «en uso», los contadores del filtro y la etiqueta de la columna (letra o número). Además, el origen que manda cada gesto: en una columna parecida, volver al sugerido en el `select` no manda `manual`; y el tag vuelve a su estado del análisis cuando el campo vuelve a ser el original.
- **Playwright:**
  - todo coincide: el aviso de éxito, la tabla recogida y confirmar habilitado;
  - un parecido se acepta con su botón, y elegir el mismo campo en la lista no lo acepta;
  - «Aceptar sugerencias»;
  - dos «Pagare» se distinguen por su columna;
  - un campo en uso sale deshabilitado en las demás filas, se anuncia como no disponible y dice en qué columna está; su fila lo conserva habilitado;
  - un repetido que trae el análisis marca las dos filas, y se resuelve pasando una a «No cargar»;
  - obligatorio sin columna, con «Elegir la columna»;
  - la fila revisada sigue en «Por revisar» hasta cambiar el filtro;
  - `destruir()`.
- **axe,** en claro, oscuro y 360 px: con parecidos por revisar, con un obligatorio sin columna y con la tabla recogida.
