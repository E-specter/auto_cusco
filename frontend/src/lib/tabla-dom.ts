/**
 * The pieces of a table that a page script builds by hand: a dense table in its scroll container, its
 * cells, the empty-state line and a figure. Nothing here knows a screen.
 *
 * A column header or an empty text arrives already translated: the callers say `t(...)`.
 */

/** A table cell. `columna` names the cell when the table stacks below 48rem (`.table--apilable`). */
export function celda(etiqueta: 'td' | 'th', texto: string, clase = '', columna = ''): HTMLTableCellElement {
  const nodo = document.createElement(etiqueta);
  nodo.textContent = texto;
  if (clase) nodo.className = clase;
  if (columna) nodo.dataset.etiqueta = columna;
  return nodo;
}

/** The header of a row (`th scope="row"`); a column header is `celda('th', ...)`, which sets no scope. */
export function celdaDeFila(texto: string, clase = '', columna = ''): HTMLTableCellElement {
  const nodo = celda('th', texto, clase, columna);
  nodo.scope = 'row';
  return nodo;
}

/** The line a list shows when it has nothing to list. */
export function vacio(texto: string): HTMLElement {
  const bloque = document.createElement('p');
  bloque.className = 'empty';
  bloque.textContent = texto;
  return bloque;
}

/**
 * A dense table in its scroll container. `columnas` are `[header text, numeric]`; `apilable` stacks the
 * rows below 48rem (the cells then need their `columna`).
 */
export function tabla(
  clase: string,
  columnas: Array<[string, boolean]>,
  opciones: { apilable?: boolean } = {},
): { envoltorio: HTMLElement; cuerpo: HTMLTableSectionElement } {
  const envoltorio = document.createElement('div');
  envoltorio.className = 'table-scroll';
  const nodo = document.createElement('table');
  nodo.className = ['table', opciones.apilable ? 'table--apilable' : '', clase].filter(Boolean).join(' ');
  const cabeza = document.createElement('thead');
  const fila = document.createElement('tr');
  columnas.forEach(([texto, numerica]) => {
    const th = document.createElement('th');
    th.scope = 'col';
    if (numerica) th.className = 'num';
    th.textContent = texto;
    fila.append(th);
  });
  cabeza.append(fila);
  const cuerpo = document.createElement('tbody');
  nodo.append(cabeza, cuerpo);
  envoltorio.append(nodo);
  return { envoltorio, cuerpo };
}

/** A figure: label, value and an optional hint; `apagada` reads it muted (a value that is not an amount). */
export function cifra(etiqueta: string, valor: string, pista?: string, apagada = false): HTMLElement {
  const bloque = document.createElement('div');
  bloque.className = 'stat';
  const nombre = document.createElement('dt');
  nombre.className = 'stat__label';
  nombre.textContent = etiqueta;
  const numero = document.createElement('dd');
  numero.className = apagada ? 'stat__value muted' : 'stat__value';
  numero.textContent = valor;
  bloque.append(nombre, numero);
  if (pista) {
    const detalle = document.createElement('dd');
    detalle.className = 'field__hint';
    detalle.textContent = pista;
    bloque.append(detalle);
  }
  return bloque;
}
