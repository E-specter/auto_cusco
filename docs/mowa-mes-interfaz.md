# MOWA MES: reglas de interfaz

Reglas vinculantes para la iconografía de `/mowa-mes` (RF-MM-36) y para las secciones nuevas de T-MM-C11: campañas descartadas (RF-MM-31 y RF-MM-32), pendientes de reporte (RF-MM-33), versiones de speech deshabilitadas (RF-MM-28 a RF-MM-30) y el panel para subir la campaña a MES (RF-MM-35). Es T-MM-D11.

Complementan [requerimientos-mowa-mes.md](requerimientos-mowa-mes.md) y el brief de diseño ([design_ui/brand_guide.json](design_ui/brand_guide.json), «iconography»). Los cortes los implementa `dev_frontend_modulo_mowa_mes` con el plan T-MM-C11 de `coordinador_modulo_mowa_mes`, y `designer` los aprueba con capturas.

Responsable: `designer`. Un cambio a estas reglas se acuerda con `designer` antes de escribirlo.

---

## 1. Principios

1. **Un concepto, un icono, en todo el módulo.** El mismo dato o la misma acción llevan el mismo icono en la campaña, el seguimiento y la configuración. Nada se elige por gusto: sale del catálogo de §3.
2. **El icono acompaña, nunca reemplaza.** Todo icono va junto a su texto, salvo los botones de solo icono que ya existen (subir, bajar, quitar, paginar), que tienen nombre accesible.
3. **Menos es más.** Un icono entra si ayuda a encontrar o a distinguir algo de un vistazo. Si repite lo que ya dice el lugar, o si todos los elementos vecinos llevarían el mismo, no va.
4. **El estado no depende solo del color.** Activa, descartada, deshabilitada y pendiente se distinguen por texto, icono y lugar, y nunca con opacidad (RF-34; misma razón que §2.5 de [filtro-valores-interfaz.md](filtro-valores-interfaz.md)).
5. **Lo irreversible se ve irreversible.** Eliminar definitivamente es la única acción en rojo, y siempre pide una confirmación explícita.

## 2. Reglas de los iconos

### 2.1 Set, trazo y color

- **El set es lucide,** con `Icon.astro` (trazo 1,75 y `currentColor`), como pide el brief. No se agrega otra librería ni se dibujan SVG propios.
- **El color siempre se hereda** (`currentColor`), así que sale del texto o del componente donde va el icono. Un icono nunca lleva un color propio. Los tonos son los tokens semánticos que ya usa ese componente: `tag--*`, `notice--*`, `btn--danger` o `--color-text-muted`.
- **Un icono que hace falta en tiempo de ejecución,** como el de una fila que arma el script, se clona de un `<template data-icono-…>` de la página. Es el patrón que ya usan `campana.astro` y `configuracion.astro`, porque `Icon.astro` solo existe al compilar.

### 2.2 Tamaño por contexto

| Contexto | Tamaño | Nota |
|---|---|---|
| Aviso (`.notice`) | 20 | Como hoy |
| Botón con texto (`.btn`, `.btn--sm`) | 16 | Antes del texto; después solo en «Siguientes» y en las flechas de avance |
| Botón de solo icono (`.btn--icon`) | 16 | Como hoy |
| Etiqueta de una cifra (`.stat__label`) | 16 | Antes del texto, en `--color-text-muted` |
| Título de un panel con medidor (§4.1) | 20 | Antes del título |
| Tag de estado (`.tag`) | 1,2 em del texto del tag | Con CSS, `.tag svg { inline-size: 1.2em; block-size: 1.2em; }`. 16 px sería más alto que el tag |

### 2.3 Alineación

- El icono y su texto van en `display: inline-flex; align-items: center; gap: var(--space-1)`. En un botón ya es así; en `.stat__label` y en `.tag` se agrega.
- Si el texto se parte en dos líneas, el icono queda alineado con la primera (`align-items: flex-start` y un margen de 0,1 em). Pasa a 360 px en las etiquetas largas.
- Nunca se centra un icono sobre su texto ni se lo pone en una columna aparte.

### 2.4 Cuándo NO va un icono

- **En los títulos de panel,** salvo el del medidor del límite (§4.1). Un título ya es un título, y un icono en cada panel es decoración.
- **En los encabezados de tabla** (`th`). La tabla ya ordena.
- **En las cifras de un medidor** (cargados del mes, límite, disponible, uso). Las explica el medidor, y el panel lleva el icono.
- **Cuando todos los vecinos llevarían el mismo:** en la lista de campañas activas, cada fila no lleva el tag «Activa», porque la lista ya lo dice (§4.3).
- **Dos veces seguidas el mismo:** si un botón y su aviso dicen lo mismo, el icono va en uno.

### 2.5 Accesibilidad

- **Con texto al lado,** el icono es `aria-hidden="true"` (`Icon.astro` ya lo pone).
- **Solo,** va dentro de un botón con `aria-label` y `title`. El texto es el de la acción con su objeto: «Descartar la campaña 1234».
- **Un tag de estado** se lee por su texto. El icono no agrega nada al lector de pantalla.

## 3. Catálogo

### 3.1 Datos, cifras y medidores

| Concepto | Icono | Dónde |
|---|---|---|
| Límite mensual (el medidor) | `gauge` | Título del panel «Límite mensual» del seguimiento (§4.1) |
| Cargados (filas que salieron hacia MES) | `file-up` | Etiqueta de la cifra en la campaña y en el detalle del seguimiento |
| Enviados (según el reporte de MES) | `send` | Etiqueta de la cifra |
| No enviados | `circle-x` | Etiqueta de la cifra |
| Excluidos | `ban` | Etiqueta de la cifra y de la sección de exclusiones |
| Advertencias | `triangle-alert` | Etiqueta de la cifra; es el mismo icono de los avisos de advertencia |
| Costo | `coins` | Etiqueta de la cifra «Costo» y «Costo del mes» |
| Archivos | `files` | Etiqueta de la cifra y de la lista de archivos |
| Supervisión | `user-check` | Etiqueta de la cifra de filas de supervisión |
| Mes de gestión | `calendar` | El filtro por mes de las descartadas (§4.2) |

### 3.2 Estados

| Estado | Tag | Icono | Texto |
|---|---|---|---|
| Activa | — | — | No lleva tag: es lo normal y su lista lo dice (§2.4) |
| Descartada | `tag--neutral` | `archive` | «Descartada» |
| Pendiente del reporte | `tag--advertencia` | `hourglass` | «Pendiente del reporte» |
| Deshabilitada (versión de speech) | `tag--neutral` | `power-off` | «Deshabilitada» |
| Original (el Speech original) | `tag--info` | `lock` | «Original». Es el mismo candado del aviso de solo lectura |

Un costo que todavía no es un monto («Pendiente del reporte», «No disponible») sigue como hoy: texto en `muted` en el lugar de la cifra (`.stat__value.muted`), sin tag ni icono.

### 3.3 Acciones

| Acción | Icono | Botón |
|---|---|---|
| Ver | `eye` | `.btn--sm` |
| Descartar | `archive` | `.btn--sm`. No es rojo: se deshace con Restaurar |
| Restaurar | `archive-restore` | `.btn--sm` |
| Eliminar definitivamente | `trash-2` | `.btn--sm .btn--danger`. Es el único botón rojo del módulo |
| Renombrar | `pencil` | `.btn--sm` |
| Deshabilitar | `power-off` | `.btn--sm` |
| Habilitar | `power` | `.btn--sm` |
| Editar (incluido «Editar en Cartera») | `square-pen` | `.btn--sm` |
| Copiar | `copy` | `.btn--sm`, o `.btn--icon` junto a un valor (§4.4) |
| Descargar | `download` | `.btn--sm` |
| Importar (el reporte de MES) | `upload` | `.btn--sm` |

Las acciones que ya existen sin icono (por ejemplo «Guardar», «Convertir a v2») no ganan uno: el catálogo cubre las de la lista. «Guardar» sigue con `save` donde ya lo tiene.

### 3.4 Avisos

Siguen como en el resto del sitio: `info` en `.notice--info`, `triangle-alert` en `.notice--warning`, `circle-alert` en `.notice--danger`, `circle-check` en `.notice--success` y `lock` en el aviso de solo lectura.

## 4. Las secciones nuevas

### 4.1 El límite mensual (atención especial)

- **El título del panel lleva `gauge`,** a 20 px. Es el único título de panel con icono (§2.4), porque nombra un medidor.
- **Bajo las cifras va una barra de uso,** un `div` con `aria-hidden="true"`: el porcentaje ya está escrito en la cifra «Uso del límite» y lo lee el lector de pantalla.
  - Alto `var(--space-2)`, fondo `--color-surface-sunken` y relleno con el porcentaje (`inline-size: X%`, con tope en 100%).
  - **Color del relleno:**
    - hasta el 90%, `--color-accent`;
    - del 90% al 100%, `--color-signal`, porque se acerca;
    - más del 100%, `--color-danger`, y aparece el aviso de exceso que ya existe.

  La marca del 90% no lleva texto propio: el color basta como refuerzo, y el número manda.
- **Las cifras** (cargados en el mes, límite, disponible y uso) no llevan icono (§2.4).
- **A 360 px,** la barra ocupa el ancho del panel, bajo las cifras apiladas.

### 4.2 Campañas descartadas (RF-MM-31 y RF-MM-32)

- **Arriba de la lista de campañas del seguimiento,** un `.segmented`: «Activas (N) · Descartadas (M)». Es el mismo patrón del filtro del mapeador. Una sola lista que cambia de vista, en lugar de un segundo bloque al pie que nadie ve.
  - «Descartadas (0)» se muestra igual, y su vista dice «No hay campañas descartadas».
  - Lo que se elige se guarda en la URL (`?vista=descartadas`), así que volver atrás vuelve a la misma vista.
- **En la vista Descartadas:**
  - **Filtro por mes:** un `select` «Mes de gestión», con el icono `calendar` en su etiqueta. Ofrece solo los meses que tienen descartadas, del más reciente al más antiguo, escritos como «Octubre de 2026», y abre en el más reciente.
  - **Cada fila:** la campaña como en la lista activa, más el tag «Descartada» (`archive`) y, debajo, «Descartada el 30 oct. 2026», con `format.ts`. Acciones: «Ver», «Restaurar» y «Eliminar definitivamente».
  - **Sus cifras no suman** en ningún total de la pantalla (RF-MM-31). La vista lo dice una vez, como hint bajo el filtro: «Las campañas descartadas no cuentan en el límite, el costo ni las cifras del mes».
- **En la lista Activas,** cada campaña lleva «Descartar» (`archive`) junto a sus otras acciones.
- **Al descartar o restaurar:** la fila sale de su vista, el contador de las dos pestañas se actualiza y la región `role="status"` dice «Se descartó la campaña 1234» o «Se restauró la campaña 1234». El foco pasa a la fila siguiente; si no hay, al control de vistas.

### 4.3 Activa, descartada, deshabilitada y pendiente

- **Activa:** la lista normal, sin tag.
- **Descartada:** vive solo en su vista (§4.2), con su tag. Nunca aparece mezclada con las activas.
- **Deshabilitada:** vive solo en su sección de la configuración (§4.5), con su tag. No aparece en el selector de la campaña (RF-MM-29).
- **Pendiente del reporte** (RF-MM-33): es una activa sin reporte importado.
  - Lleva el tag «Pendiente del reporte» (`hourglass`) en su fila y, en su detalle, un `.notice--warning` con el paso siguiente: «Falta importar el reporte de enviados de MES. Cuando la campaña se haya enviado, descárgalo de MES e impórtalo aquí», con el botón «Importar el reporte» (`upload`) que lleva al campo de importación.
  - Arriba de la lista Activas, si hay alguna pendiente, una línea: «{n} campañas pendientes del reporte».
- **Ninguno usa opacidad.** El texto de una fila descartada o deshabilitada conserva su contraste.

### 4.4 «Para subir a MES» (RF-MM-35)

Al crear la campaña, el resultado deja de ser solo «creada» y pasa a ser el paso siguiente:

- **Un `.notice--success`:** «Se creó la campaña {id}. Ahora súbela a MES con estos datos».
- **Un panel titulado «Para subir a MES»,** con tres pasos numerados (`ol`):
  1. **«Descarga los archivos de carga»:** un botón «Descargar» (`download`) por archivo, con su nombre en mono, en el orden de `{archivo}`.
  2. **«Completa el formulario de MES»:** una lista de definición (`dl`) con cada dato en el orden del formulario de MES (tipo de carga, descripción, salida, herramientas y programación).
     - Cada valor va en mono, con un botón de solo icono «Copiar» (`copy`, `aria-label` «Copiar {dato}»).
     - Al copiar, la región de estado dice «Copiado: {dato}», y el icono pasa a `check` por 2 s. Es el patrón que ya existe en la campaña (`campana.astro:143`).
  3. **«Después del envío, importa el reporte»:** un enlace «Ir al seguimiento de la campaña» al seguimiento de esa campaña (RF-MM-33).
- **A 360 px,** el `dl` se apila: el nombre del dato encima y el valor con su botón debajo.

### 4.5 Versiones de speech deshabilitadas (RF-MM-28 a RF-MM-30)

- **En la configuración, bajo el panel del speech,** un panel propio, «Versiones deshabilitadas (N)», que se pliega con `<details>` y abre cerrado: se usa poco. Con cero no se muestra.
- **Cada versión:** su nombre, el tag «Deshabilitada» (`power-off`) y «Original» (`lock`) si es el Speech original. Acciones:
  - «Ver» (`eye`): abre la versión en el editor en solo lectura, con el aviso de candado que ya existe;
  - «Habilitar» (`power`);
  - «Eliminar definitivamente» (`trash-2`, rojo).
- **Si no se puede eliminar** (la usó una campaña, o es el Speech original), «Eliminar definitivamente» no se muestra, y en su lugar va el motivo en `.field__hint`: «No se puede eliminar: la usaron campañas» o «No se puede eliminar: es el Speech original». **Para el backend:** la lista de deshabilitadas trae `eliminable` y `motivo`, así la pantalla no lo descubre con un 409.
- **En las versiones activas** se suman «Renombrar» (`pencil`) y «Deshabilitar» (`power-off`). Renombrar usa el diálogo de §10.1 de [motor-texto-enriquecido-interfaz.md](motor-texto-enriquecido-interfaz.md), el mismo que el de las definiciones.

### 4.6 Confirmaciones

Las tres usan `dialog.dialog`, con el foco inicial en «Cancelar» y Escape para cancelar.

| | Descartar | Restaurar | Eliminar definitivamente |
|---|---|---|---|
| Título | «Descartar la campaña {id}» | «Restaurar la campaña {id}» | «Eliminar definitivamente la campaña {id}» (o «…la versión «{nombre}»») |
| Cuerpo | «Deja de mostrarse entre las activas y sale del límite, el costo y las cifras del mes. No se borra nada: se puede restaurar.» | «Vuelve a las activas y a todos los cálculos del mes.» | `.notice--danger`: «Se borran la campaña, sus archivos, filas, exclusiones y reportes. No se puede deshacer.» (Para una versión: «Se borra la versión y su texto. No se puede deshacer.») |
| Extra | Si tiene reporte importado, un `.notice--warning`: «Esta campaña ya tiene reporte de enviados. Si se envió, su consumo deja de contar en el límite del mes.» | — | Una casilla obligatoria: «Entiendo que no se puede deshacer». El botón queda inactivo hasta marcarla. Es el patrón de eliminar una versión en `/cargas` |
| Botón | «Descartar» (`.btn--primary`, `archive`) | «Restaurar» (`.btn--primary`, `archive-restore`) | «Eliminar definitivamente» (`.btn--danger`, `trash-2`) |

### 4.7 «Editar en Cartera» (RF-MM-09, M-F6)

- **En la campaña,** junto al `select` «Selección guardada», va un botón `.btn--sm` «Editar en Cartera» (`square-pen`). Abre `/cartera` con esa selección y `?volver=`.
  - Sin una selección elegida, queda inactivo, con el `title` «Elige una selección guardada para editarla».
- **En `/cartera`, cuando llega con `?volver=`,** un `.notice--info` bajo el encabezado de la página y antes de todo lo demás, con una línea y un enlace:
  - el texto: «Estás editando la selección de una campaña de MOWA MES. Al guardarla, vuelves a la campaña»;
  - el enlace «Volver a la campaña sin guardar», con el icono `chevron-left`. Si hay cambios sin guardar, pasa por la misma confirmación que ya tiene Cartera («Hay cambios sin guardar»), y no se pierde nada sin aviso.
- **Si al volver la selección ya no existe** (se borró en Cartera), la campaña muestra un `.notice--warning` bajo el `select`: «La selección que editaste en Cartera ya no existe. Elige otra selección guardada». El `select` queda sin elegir. El aviso se va al elegir otra.
- **Si `/cartera` llega con un `seleccion` que no existe,** queda vacía y usable, con un `.notice--warning` (`role="status"`): «La selección que abriste ya no existe. Arma una nueva o elige otra de la lista». Nunca un error.
- **La confirmación de volver con cambios** es «la de siempre del selector» (`dialog.dialog` con el título «Hay cambios sin guardar» y «Seguir editando»), no una propia. Para que sirva a los dos usos, el texto de siempre cambia en todas las pantallas que lo tienen: el cuerpo pasa a «Los cambios que no guardaste se pierden» y el botón, a «Descartar cambios» (antes «Si cargas otra selección, los cambios de ahora se pierden» y «Descartar y cargar»).

## 5. Textos nuevos

Prefijo `mowaMes.*` (es y en). No usan el prefijo `mowaMes.codigo.*`, que vigila la prueba espejo del backend.

| Clave | es | en |
|---|---|---|
| `mowaMes.seguimiento.vista.activas` | Activas ({n}) | Active ({n}) |
| `mowaMes.seguimiento.vista.descartadas` | Descartadas ({n}) | Discarded ({n}) |
| `mowaMes.seguimiento.vista.etiqueta` | Mostrar | Show |
| `mowaMes.seguimiento.descartadas.mes` | Mes de gestión | Management month |
| `mowaMes.seguimiento.descartadas.hint` | Las campañas descartadas no cuentan en el límite, el costo ni las cifras del mes. | Discarded campaigns do not count toward the month's limit, cost or figures. |
| `mowaMes.seguimiento.descartadas.vacio` | No hay campañas descartadas. | There are no discarded campaigns. |
| `mowaMes.seguimiento.descartadas.el` | Descartada el {fecha} | Discarded on {fecha} |
| `mowaMes.estado.descartada` | Descartada | Discarded |
| `mowaMes.estado.pendienteReporte` | Pendiente del reporte | Report pending |
| `mowaMes.estado.deshabilitada` | Deshabilitada | Disabled |
| `mowaMes.estado.original` | Original | Original |
| `mowaMes.seguimiento.pendientes` | {n} campañas pendientes del reporte | {n} campaigns with the report pending |
| `mowaMes.seguimiento.pendientesUna` | 1 campaña pendiente del reporte | 1 campaign with the report pending |
| `mowaMes.seguimiento.pendiente.aviso` | Falta importar el reporte de enviados de MES. Cuando la campaña se haya enviado, descárgalo de MES e impórtalo aquí. | The MES sent report has not been imported yet. Once the campaign is sent, download it from MES and import it here. |
| `mowaMes.seguimiento.pendiente.importar` | Importar el reporte | Import the report |
| `mowaMes.accion.ver` | Ver | View |
| `mowaMes.accion.descartar` | Descartar | Discard |
| `mowaMes.accion.restaurar` | Restaurar | Restore |
| `mowaMes.accion.eliminar` | Eliminar definitivamente | Delete permanently |
| `mowaMes.accion.renombrar` | Renombrar | Rename |
| `mowaMes.accion.deshabilitar` | Deshabilitar | Disable |
| `mowaMes.accion.habilitar` | Habilitar | Enable |
| `mowaMes.accion.editarEnCartera` | Editar en Cartera | Edit in Portfolio |
| `mowaMes.accion.copiar` | Copiar {dato} | Copy {dato} |
| `mowaMes.estado.copiado` | Copiado: {dato} | Copied: {dato} |
| `mowaMes.seguimiento.descartada` | Se descartó la campaña {id}. | Campaign {id} was discarded. |
| `mowaMes.seguimiento.restaurada` | Se restauró la campaña {id}. | Campaign {id} was restored. |
| `mowaMes.seguimiento.eliminada` | Se eliminó la campaña {id}. | Campaign {id} was deleted. |
| `mowaMes.confirmar.descartar.titulo` | Descartar la campaña {id} | Discard campaign {id} |
| `mowaMes.confirmar.descartar.cuerpo` | Deja de mostrarse entre las activas y sale del límite, el costo y las cifras del mes. No se borra nada: se puede restaurar. | It stops showing among the active ones and leaves the month's limit, cost and figures. Nothing is deleted: it can be restored. |
| `mowaMes.confirmar.descartar.conReporte` | Esta campaña ya tiene reporte de enviados. Si se envió, su consumo deja de contar en el límite del mes. | This campaign already has a sent report. If it was sent, its usage stops counting toward the month's limit. |
| `mowaMes.confirmar.restaurar.titulo` | Restaurar la campaña {id} | Restore campaign {id} |
| `mowaMes.confirmar.restaurar.cuerpo` | Vuelve a las activas y a todos los cálculos del mes. | It returns to the active ones and to all of the month's calculations. |
| `mowaMes.confirmar.eliminar.tituloCampana` | Eliminar definitivamente la campaña {id} | Permanently delete campaign {id} |
| `mowaMes.confirmar.eliminar.tituloVersion` | Eliminar definitivamente la versión «{nombre}» | Permanently delete the “{nombre}” version |
| `mowaMes.confirmar.eliminar.cuerpoCampana` | Se borran la campaña, sus archivos, filas, exclusiones y reportes. No se puede deshacer. | The campaign, its files, rows, exclusions and reports are deleted. This cannot be undone. |
| `mowaMes.confirmar.eliminar.cuerpoVersion` | Se borra la versión y su texto. No se puede deshacer. | The version and its text are deleted. This cannot be undone. |
| `mowaMes.confirmar.eliminar.casilla` | Entiendo que no se puede deshacer | I understand this cannot be undone |
| `mowaMes.confirmar.cancelar` | Cancelar | Cancel |
| `mowaMes.configuracion.deshabilitadas.titulo` | Versiones deshabilitadas ({n}) | Disabled versions ({n}) |
| `mowaMes.configuracion.habilitada` | Se habilitó «{nombre}». | “{nombre}” was enabled. |
| `mowaMes.configuracion.deshabilitada` | Se deshabilitó «{nombre}». Ya no aparece en la campaña. | “{nombre}” was disabled. It no longer shows in the campaign. |
| `mowaMes.speech.renombrar.titulo` | Renombrar la versión «{nombre}» | Rename the “{nombre}” version |
| `mowaMes.speech.renombrar.campo` | Nombre nuevo | New name |
| `mowaMes.speech.renombrar.hint` | Las campañas siguen apuntando a esta versión: registran la versión, no su nombre. | Campaigns keep pointing to this version: they record the version, not its name. |
| `mowaMes.speech.renombrar.confirmar` | Renombrar | Rename |
| `mowaMes.speech.renombrar.repetido` | Ya existe una versión con ese nombre. Elige otro. | A version with that name already exists. Choose another one. |
| `mowaMes.speech.renombrar.hecho` | Renombrada a «{nombre}». | Renamed to “{nombre}”. |
| `mowaMes.speech.inmutable.deshabilitada` | Esta versión está deshabilitada: no aparece en la campaña y se ve en solo lectura. Para usarla o editarla, habilítala. | This version is disabled: it does not show in the campaign and is read-only. To use or edit it, enable it. |
| `mowaMes.speech.inmutable.original` | Este es el Speech original: no se modifica. Tus cambios se guardan como una versión nueva basada en él. | This is the original speech: it is not modified. Your changes are saved as a new version based on it. |
| `mowaMes.campana.speech.ninguna` | No hay versiones habilitadas | No enabled versions |
| `mowaMes.campana.speech.ningunaAviso` | No hay ninguna versión de speech habilitada. Habilita una en la configuración para crear la campaña. | There is no enabled speech version. Enable one in the settings to create the campaign. |
| `mowaMes.campana.speech.irConfiguracion` | Ir a la configuración | Go to the settings |
| `mowaMes.speech.renombrar.invalido` | Escribe un nombre de 1 a {max} caracteres. | Enter a name of 1 to {max} characters. |
| `mowaMes.speech.marca.deshabilitada` | deshabilitada | disabled |
| `mowaMes.configuracion.eliminada` | Se eliminó «{nombre}». | “{nombre}” was deleted. |
| `mowaMes.campana.subir.creada` | Se creó la campaña {id}. Ahora súbela a MES con estos datos. | Campaign {id} was created. Now upload it to MES with this data. |
| `mowaMes.campana.subir.titulo` | Para subir a MES | To upload to MES |
| `mowaMes.campana.subir.paso1` | Descarga los archivos de carga | Download the load files |
| `mowaMes.campana.subir.paso2` | Completa el formulario de MES | Fill in the MES form |
| `mowaMes.campana.subir.paso3` | Después del envío, importa el reporte | After sending, import the report |
| `mowaMes.campana.subir.irSeguimiento` | Ir al seguimiento de la campaña | Go to the campaign's tracking |
| `mowaMes.campana.editarEnCartera.inactivo` | Elige una selección guardada para editarla. | Choose a saved selection to edit it. |
| `mowaMes.campana.seleccionBorrada` | La selección que editaste en Cartera ya no existe. Elige otra selección guardada. | The selection you edited in Portfolio no longer exists. Choose another saved selection. |
| `cartera.volver.aviso` | Estás editando la selección de una campaña de MOWA MES. Al guardarla, vuelves a la campaña. | You are editing the selection of a MOWA MES campaign. When you save it, you go back to the campaign. |
| `cartera.volver.sinGuardar` | Volver a la campaña sin guardar | Back to the campaign without saving |
| `cartera.volver.noExiste` | La selección que abriste ya no existe. Arma una nueva o elige otra de la lista. | The selection you opened no longer exists. Build a new one or choose another from the list. |
| `selector.descartar.cuerpo` (cambia el texto) | Los cambios que no guardaste se pierden. | The changes you did not save will be lost. |
| `selector.descartar.confirmar` (cambia el texto) | Descartar cambios | Discard changes |

Las cifras que ya tienen texto (cargados, enviados, costo…) conservan sus claves: solo ganan el icono.

## 6. Pruebas mínimas

- **Vitest:** el color de la barra del límite por tramo (hasta 90%, de 90% a 100% y más de 100%), con el relleno topado en 100%; y el texto de la fecha de descarte.
- **Playwright:**
  - el límite con la barra en los tres tramos y su aviso de exceso;
  - Activas y Descartadas, con los contadores, el filtro por mes y la vista en la URL;
  - descartar con y sin reporte importado (el aviso extra);
  - restaurar;
  - eliminar, con «Eliminar definitivamente» inactivo hasta marcar la casilla;
  - pendiente del reporte, con su tag, su aviso y el enlace;
  - «Para subir a MES», con descargar, copiar cada dato con su anuncio, y el enlace al seguimiento;
  - versiones deshabilitadas: habilitar, ver en solo lectura y eliminar, y el motivo cuando no se puede;
  - renombrar y deshabilitar una activa.
- **axe,** en claro, oscuro y 360 px: el límite, la vista Descartadas, la confirmación de eliminar, el panel «Para subir a MES» y las versiones deshabilitadas.
- **Capturas para `designer`,** antes del commit de cada corte: las mismas pantallas, en claro y oscuro, a 1280 y a 360 px.
