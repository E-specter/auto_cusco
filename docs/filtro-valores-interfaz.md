# Filtro de valores y orden de los filtros: reglas de interfaz

Reglas vinculantes para elegir valores de una lista en un filtro de texto (RF-67) y para reordenar los filtros de la selección (RF-68). Es T-FV-F0. Se construyen en T-FV-F2 (la lista) y T-FV-F3 (el orden).

Complementan RF-67 y RF-68 de [atomics-requirements.md](atomics-requirements.md) y el plan T-FV-C1 (§29 del plan del coordinador del motor). El contrato es el de T-FV-B1 (`no_en` y el elemento vacío) y T-FV-B2 (`GET /cartera/valores`).

El selector es uno solo, `SelectorSeleccion`, y se usa en Cartera, en Columnas y en la campaña de MOWA MES. Lo que cambia en la campaña está marcado con **[MOWA]** y lo revisa `coordinador_modulo_mowa_mes`.

Responsable: `designer`. Un cambio a estas reglas se acuerda con `designer` antes de escribirlo.

---

## 1. Principios

1. **Elegir en vez de escribir, cuando se puede.** Si un campo de texto tiene pocos valores, se ofrecen los reales, con cuántos productos tiene cada uno, y el analista no adivina cómo está escrito un valor.
2. **El backend decide si hay lista.** El umbral, los valores y sus cantidades llegan en la respuesta. La pantalla no cuenta valores ni repite el umbral.
3. **Nada se desmarca solo.** Lo que el analista marcó sigue marcado aunque los filtros de arriba lo dejen sin productos. La pantalla lo muestra aparte y lo dice.
4. **El orden se ve, pero no asusta.** El número de cada filtro hace visible la cascada, y una línea dice que el orden no cambia el resultado.
5. **El arrastre es un atajo, no la única forma.** Todo se puede hacer con el teclado y con un toque, con botones a la vista (RF-34).

## 2. La lista de valores (RF-67)

### 2.1 Cuándo aparece

- **El campo es de texto,** base o adicional, archivados incluidos, y el operador es «es uno de» (`en`) o «no es ninguno de» (`no_en`, nuevo).
- **Al elegir un campo de texto,** en una fila nueva o al cambiar de campo, el operador por defecto pasa a ser «es uno de». **Al abrir una selección guardada,** cada filtro conserva su operador guardado: el valor por defecto nunca lo pisa. Los dos operadores van primeros en la lista de operadores de un campo de texto, y los demás siguen como hoy («contiene», «empieza con», «está vacío»…).
- **La pantalla pide `GET /cartera/valores`** para ese campo, con los filtros completos que están encima (§2.6).
  - **Con `ofrece_lista: true`,** en lugar del `textarea` «Un valor por línea» va la lista de §2.2.
  - **Con `ofrece_lista: false`,** el filtro sigue como hoy: el `textarea` «Un valor por línea», con un hint, «Este campo tiene más de {umbral} valores distintos en esta fecha: escribe los valores, uno por línea». `{umbral}` es el `umbral` de la respuesta, con `formatNumber`.
- **El control se decide sobre la fecha entera, no sobre lo filtrado** (P-4). Por eso un campo no pasa de lista a `textarea` porque cambie un filtro de arriba: solo cambia al cambiar la fecha de corte.

### 2.2 Cómo se ve

Es un `fieldset` dentro de la fila del filtro, debajo del campo y del operador:

```
[Tipo de asignación ▾] [es uno de ▾]                     [↑][↓][×]
  Incluye los productos que tienen alguno de los valores marcados.
  [Buscar un valor            ]          (solo con más de 10 valores)
  ☑ Primera asignación                                       1 820
  ☑ Segunda asignación                                       1 204
  ☐ Asignación especial                                        96
  ☐ (vacío)                                                     12
  2 de 4 marcados · [Desmarcar todos]
```

- **Leyenda** (`legend`, `visually-hidden`): «Valores de {campo}». El nombre del campo ya está a la vista en su `select`.
- **Una línea, que cambia con el operador,** dice qué hace el filtro. Es la ayuda de incluir y excluir, dicha en palabras:
  - «es uno de»: «Incluye los productos que tienen alguno de los valores marcados».
  - «no es ninguno de»: «Excluye los productos que tienen alguno de los valores marcados. Los que no tienen valor quedan, salvo que marques «(vacío)»».
- **Cada valor** es una casilla con su texto **tal como viene** (D-FV-1) y, a la derecha, su cantidad en mono, alineada y con `formatNumber`.
  - El nombre accesible de la casilla es el texto y la cantidad: «Primera asignación, 1 820 productos».
  - Un valor largo se corta con «…» y se lee entero en `title`.
- **El orden es el de la respuesta** (D-FV-2): por cantidad, de mayor a menor, con desempate alfabético. **«(vacío)» va siempre al final,** en cursiva para que no se confunda con un valor que diga «(vacío)». Se muestra solo si hay productos sin valor, o si está marcado (§2.4).
- **La lista mide hasta unas 8 casillas de alto** y desplaza adentro; la fila no crece sin fin.
- **La búsqueda** aparece solo con más de 10 valores (el máximo es el umbral, 100). Es un `input type="search"` con «Buscar un valor».
  - Filtra lo que se ve, sin distinguir mayúsculas ni tildes, con la búsqueda de siempre (`normalizarBusqueda`), aunque los valores se comparen tal cual. Buscar no es filtrar la cartera.
  - Lo marcado sigue marcado aunque la búsqueda lo oculte, y el resumen («2 de 40 marcados») lo cuenta.
  - Sin resultados: «Ningún valor contiene «{texto}»».
  - «(vacío)» no se busca: queda siempre al final, a la vista.
- **El resumen bajo la lista:** «{n} de {total} marcados», y «Desmarcar todos» (`.btn--sm .btn--quiet`) cuando hay alguno marcado. No hay «Marcar todos»: incluir todos es no filtrar, y excluir todos se dice mejor con «está vacío».
- **Sin nada marcado,** la fila queda «incompleta», con la marca que ya existe (`selector.fila.incompleta`), y no filtra.

### 2.3 Incluir o excluir

- El control por filtro es el **operador**: «es uno de» incluye y «no es ninguno de» excluye. No hay un segundo control: dos controles para lo mismo podrían contradecirse. La línea de §2.2 lo dice en palabras.
- **Cambiar de uno a otro conserva lo marcado.** Solo cambian la línea de ayuda y el resultado.
- **Excluir y los vacíos** (P-1 y P-2): un producto sin valor queda en la selección al excluir, salvo que se marque «(vacío)». La línea de ayuda lo dice; así nadie se lleva la sorpresa de ver productos «sin tipo» en una exclusión.

### 2.4 Un valor marcado que se queda sin productos

Si un filtro de arriba cambia y un valor marcado ya no está en `valores` (P-7):

- **Sigue marcado.** Pasa a un grupo aparte, bajo la lista y antes del resumen, con el título «Marcados sin productos con los filtros de arriba».
- **Cada uno** muestra su casilla marcada, su texto, la cantidad «0» y un `.tag tag--advertencia` «Sin productos».
- **Sobre el grupo,** un `.field__hint`: «Ningún producto tiene estos valores con los filtros de arriba. Siguen marcados: desmárcalos si ya no los necesitas».
- **Si vuelven a tener productos** (porque cambió otra vez un filtro de arriba), regresan a su lugar en la lista, sin aviso.
- **Al desmarcar uno de ese grupo,** desaparece: ya no está ni en la lista ni marcado.
- **Una selección guardada** que trae un valor que no existe en esta fecha se muestra igual.
- **El filtro se manda igual** con ese valor; `en` con un valor sin productos no rompe nada.

### 2.5 Errores y estados

- **Primera carga:** en el lugar de la lista, «Cargando valores…» (`aria-busy="true"` en el `fieldset`).
- **Recalcular (§2.6):**
  - la lista anterior queda a la vista y operable, atenuada, con `aria-busy="true"` y la línea «Actualizando valores…»;
  - al llegar la respuesta, se reemplazan las cantidades y el orden, y lo marcado se conserva;
  - no se vacía la lista mientras espera: así no salta y el foco no se pierde.
- **Error** (red o 5xx):
  - la fila vuelve al `textarea` de siempre, con lo marcado escrito, uno por línea, para que se pueda seguir trabajando;
  - **«(vacío)» no va en el `textarea`:** sería una línea en blanco, que `escribirFiltro` descarta, y `en A|` pasaría a `en A` sin aviso. Si estaba marcado, debajo del `textarea` queda una casilla «(vacío)» marcada, y el filtro lo sigue mandando. Al volver la lista, vuelve a su lugar;
  - bajo el operador, «No se pudieron cargar los valores», con «Reintentar» (`.btn--sm`), que vuelve a pedir la lista y, si llega, vuelve a las casillas con lo que diga el `textarea`;
  - lo marcado se sigue mandando, y la selección se calcula igual.
- **`404`, sin versión vigente para la fecha:** lo dice la pantalla como hoy, para toda la selección. La fila no repite el error.
- **`400`, el campo no es de texto:** no pasa, porque la pantalla solo pide la lista de campos de texto. Si llegara, la fila vuelve al `textarea`.

### 2.6 Cuándo se recalcula la lista (la cascada)

- **La lista del filtro N depende solo de la fecha de corte y de los filtros 1 a N−1 completos.**
  - Un filtro incompleto o con problema no cuenta para la cascada: no filtra, igual que en el resultado.
  - Los filtros de abajo no afectan a la lista de arriba.
- **Se recalcula cuando:**
  - cambia la fecha de corte (todas las listas);
  - cambia, se completa, se quita o se mueve un filtro de arriba (las listas de los filtros de abajo);
  - se abre una selección guardada (todas, de arriba hacia abajo).
- **Con la misma espera y cancelación que la revisión de la selección:** 300 ms después del último cambio, y una respuesta vieja se descarta (`AbortController`).
- **Marcar o desmarcar un valor de un filtro** recalcula solo las listas de los filtros que tiene debajo.
- **Se pide una lista por filtro de texto que la muestre,** y nunca la de un campo que no la ofrece.

## 3. El orden de los filtros (RF-68)

### 3.1 Cómo se ve

- **Con dos filtros o más,** cada fila lleva a la izquierda su número de orden, en mono («1», «2»…), y tres controles al final, junto a «Quitar filtro»:
  - un **asa de arrastre** (icono `grip-vertical`);
  - «**Subir**» (`chevron-up`);
  - «**Bajar**» (`chevron-down`).

  Todos son `.btn--quiet .btn--icon`. Con un solo filtro, no hay número ni controles de orden.
- **Bajo el título «Filtros»,** con dos o más, un `.field__hint`: «El orden no cambia el resultado: cada filtro muestra los valores que quedan con los de arriba». Es lo único que hace falta saber, y se dice una vez, no en cada fila.

### 3.2 Arrastrar

- **Se arrastra desde el asa,** con el puntero o el dedo (eventos de puntero, que sirven igual en táctil). La fila sigue al puntero con una sombra y una línea marca dónde caerá.
- **Al soltar,** la fila queda en su nuevo lugar, los números se actualizan y se anuncia (§3.4).
- **Escape, mientras se arrastra,** cancela y la fila vuelve a su lugar.
- **El asa no recibe el foco** (`tabindex="-1"`, `aria-hidden="true"`), y su texto, «Arrastrar el filtro «Tipo de asignación»», va en `title` para el puntero. Su equivalente de teclado son «Subir» y «Bajar», que están a la vista. Así hay un solo camino de teclado, sin un modo especial de «tomar y mover» que un lector de pantalla podría no anunciar.

### 3.3 Con el teclado y con un toque (RF-34)

- **«Subir» y «Bajar»** mueven el filtro una posición, al instante.
  - Su nombre accesible incluye el filtro: «Subir el filtro «Tipo de asignación»».
  - Quedan inactivos en el primer y el último lugar, respectivamente.
- **El foco sigue al filtro movido:** queda en el mismo botón de su nueva fila. Si ese botón quedó inactivo, porque llegó al borde, pasa al otro («Bajar» o «Subir»).
- A 360 px los botones son el camino natural, porque arrastrar en una lista que desplaza es incómodo.

### 3.4 El anuncio para el lector de pantalla

En la región `role="status"` del selector:
- **al mover:** «Movido «Tipo de asignación» a la posición 2 de 4»;
- **al cancelar un arrastre:** «Movimiento cancelado».

No dice nada de las listas: se recalculan solas (§2.6), y el hint de §3.1 ya explica el efecto.

### 3.5 Qué cambia al mover

- **Cambian el número de cada filtro y las listas de los que quedaron debajo de otro.**
- **No cambian** el resultado, los totales ni las cifras.
- **Mover emite `seleccioncambiada` con el orden nuevo,** como cualquier cambio de filtros, y cuenta como cambio sin guardar, porque el orden se guarda con la selección. El selector siempre avisa. Qué hace la pantalla con ese aviso lo decide ella: en Cartera, recalcular da los mismos totales.
- **[MOWA]** La campaña solo se entera del orden por ese evento (`campana.astro`). Mover vuelve a previsualizar: los totales salen iguales y la descripción sugerida cambia. Si no se emitiera, la sugerida y la creación quedarían con el orden viejo.
- **[MOWA]** En la campaña de MOWA MES, mover un filtro cambia la `descripcion_sugerida` de una campaña nueva, porque resume los filtros en su orden. Es lo esperado (§29 del plan): es una sugerencia que el usuario edita, y una campaña ya creada guarda su descripción. Si el usuario ya editó la descripción, el orden no la toca, como cualquier otro cambio de filtros.

## 4. La campaña de MOWA MES **[MOWA]**

- El selector es el mismo, con las mismas reglas de §2 y §3.
- **`resumen_filtro`** (T-FV-B1, backend) escribe:
  - `en`, igual que hoy: «tipo de asignación en Primera asignación/Segunda asignación». De eso dependen las pruebas de oro;
  - `en` con el vacío: «… en Primera asignación/(vacío)»;
  - `no_en`: «tipo de asignación no es Primera asignación/Segunda asignación»;
  - solo el vacío: «… en (vacío)» o «… no es (vacío)»;
  - siempre con `una_linea` y el límite de 100 UTF-16.
- **«(vacío)» en la descripción lo escribe el backend, siempre en español,** porque es el texto que va a MES. No se traduce, aunque en pantalla `selector.valores.vacio` diga «(empty)» en inglés.
- Ninguna otra pantalla de MOWA cambia.

## 5. Accesibilidad

- La lista es un `fieldset` con `legend` «Valores de {campo}». Sus casillas son nativas, con el nombre de §2.2.
- La línea de incluir o excluir se asocia al `fieldset` con `aria-describedby`.
- `aria-busy` mientras carga o recalcula. El error es un `role="alert"` bajo el operador.
- El grupo «Marcados sin productos» es otro `fieldset`, con su `legend`.
- El orden se hace con botones nativos, con nombre y estado inactivo; el arrastre es solo un atajo. El anuncio va en `role="status"`.
- Contraste AA en claro y oscuro, con axe en los estados de §7.

## 6. Textos

En `selector.valores.*` y `selector.mover.*` (es y en). `op.no_en` se suma a los operadores.

| Clave | es | en |
|---|---|---|
| `op.no_en` | no es ninguno de | is none of |
| `selector.valores.leyenda` | Valores de {campo} | Values of {campo} |
| `selector.valores.incluye` | Incluye los productos que tienen alguno de los valores marcados. | Includes the products that have any of the checked values. |
| `selector.valores.excluye` | Excluye los productos que tienen alguno de los valores marcados. Los que no tienen valor quedan, salvo que marques «(vacío)». | Excludes the products that have any of the checked values. Those with no value stay, unless you check “(empty)”. |
| `selector.valores.vacio` | (vacío) | (empty) |
| `selector.valores.cantidad` | {valor}, {n} productos | {valor}, {n} products |
| `selector.valores.cantidadUno` | {valor}, 1 producto | {valor}, 1 product |
| `selector.valores.buscar` | Buscar un valor | Search a value |
| `selector.valores.sinResultados` | Ningún valor contiene «{texto}». | No value contains “{texto}”. |
| `selector.valores.marcados` | {n} de {total} marcados | {n} of {total} checked |
| `selector.valores.desmarcar` | Desmarcar todos | Uncheck all |
| `selector.valores.sinProductos.titulo` | Marcados sin productos con los filtros de arriba | Checked, with no products under the filters above |
| `selector.valores.sinProductos.aviso` | Ningún producto tiene estos valores con los filtros de arriba. Siguen marcados: desmárcalos si ya no los necesitas. | No product has these values under the filters above. They stay checked: uncheck them if you no longer need them. |
| `selector.valores.sinProductos.tag` | Sin productos | No products |
| `selector.valores.cargando` | Cargando valores… | Loading values… |
| `selector.valores.actualizando` | Actualizando valores… | Updating values… |
| `selector.valores.error` | No se pudieron cargar los valores. | The values could not be loaded. |
| `selector.valores.reintentar` | Reintentar | Try again |
| `selector.valores.sobreUmbral` | Este campo tiene más de {umbral} valores distintos en esta fecha: escribe los valores, uno por línea. | This field has more than {umbral} different values on this date: type the values, one per line. |
| `selector.mover.hint` | El orden no cambia el resultado: cada filtro muestra los valores que quedan con los de arriba. | The order does not change the result: each filter shows the values left by the ones above. |
| `selector.mover.subir` | Subir el filtro «{campo}» | Move the “{campo}” filter up |
| `selector.mover.bajar` | Bajar el filtro «{campo}» | Move the “{campo}” filter down |
| `selector.mover.arrastrar` | Arrastrar el filtro «{campo}» | Drag the “{campo}” filter |
| `selector.mover.movido` | Movido «{campo}» a la posición {posicion} de {total}. | Moved “{campo}” to position {posicion} of {total}. |
| `selector.mover.cancelado` | Movimiento cancelado. | Move cancelled. |

- `{campo}` es siempre el nombre legible del campo (`etiquetaEnCatalogo`), y en las citas va con las comillas del idioma (`camposAdicionales.nombreCitado`).
- Un filtro sin campo elegido usa «Filtro {n}» en los nombres de «Subir» y «Bajar»: `selector.mover.sinCampo`, es «Filtro {n}», en «Filter {n}».

## 7. Pruebas mínimas

- **Vitest:**
  - qué filtros cuentan para la cascada de cada fila (completos y de arriba);
  - la partición de la lista en «en la lista» y «marcados sin productos»;
  - el resumen «n de total»;
  - la búsqueda sin mayúsculas ni tildes, que no toca lo marcado;
  - la posición y el estado inactivo de «Subir» y «Bajar».
- **Playwright:**
  - un campo de texto con lista: marcar dos, incluir, y que se mande `en` con esos valores;
  - pasar a «no es ninguno de» conserva lo marcado y cambia la línea de ayuda;
  - marcar «(vacío)» manda el elemento vacío;
  - el orden de la lista y «(vacío)» al final;
  - con más de 10 valores, la búsqueda filtra sin desmarcar;
  - un campo sobre el umbral muestra el `textarea` con el hint y el umbral de la respuesta;
  - cambiar un filtro de arriba recalcula solo las listas de abajo, conserva lo marcado y deja aparte el valor que se quedó sin productos, con el aviso;
  - el error con «Reintentar»;
  - fallar la lista con «(vacío)» marcado no cambia el filtro que se manda;
  - «Subir» y «Bajar» mueven, el foco sigue al filtro, el anuncio y los botones inactivos en los bordes;
  - arrastrar mueve, y Escape cancela;
  - mover no cambia los totales, pero sí las listas de abajo;
  - el orden se guarda con la selección y vuelve igual;
  - **[MOWA]** en la campaña:
    - el mismo selector;
    - mover con la descripción sin editar cambia la sugerida, y con la descripción editada (`estado.descripcionEditada`) no la toca;
    - la petición de previsualización y la de creación llevan los filtros en el orden de la pantalla;
    - `api-falsa-mowa-mes.ts` responde `GET /cartera/valores`; si no, el selector cae al `textarea` porque la llamada falla (§2.5), sin que los specs se rompan ni esperen de más;
    - F2 y F3 corren además `mowa-mes-campana`, `mowa-mes-campana-descripcion` y `mowa-mes-adicionales`.
- **axe,** en claro, oscuro y 360 px: la lista con marcados, la lista con marcados sin productos, el error y la fila con los controles de orden.
