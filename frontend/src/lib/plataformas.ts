/**
 * What a platform fixes in a column definition (RF-72, docs/motor-texto-enriquecido-interfaz.md §11.2).
 *
 * The rules come from `GET /definiciones-columnas/plataformas`; the screen never writes a platform
 * into the code. Pure: no DOM, no fetch, no wording (that is `plataformas-texto.ts`).
 *
 * A column is *fixed* when it sits in the position the platform gives it and carries its name: the
 * backend finds the fixed columns by name too (`problemas_de_plataforma`). A fixed column that is
 * missing, moved or renamed is not fixed on screen: it is an ordinary column with a problem under
 * it, so the analyst can put it back.
 */

import type { components } from './contrato-api';
import type { Expresion, Nodo } from './expresion';

export type ReglasPlataforma = components['schemas']['ReglasPlataformaRespuesta'];
export type ColumnaFija = components['schemas']['ColumnaFijaRespuesta'];

/** The rules of `clave`, or `null` for a free file and for a platform nobody registered. */
export function reglasDe(plataformas: readonly ReglasPlataforma[], clave: string | null): ReglasPlataforma | null {
  return clave === null ? null : (plataformas.find((r) => r.clave === clave) ?? null);
}

/** The number of the column after the fixed ones (the `n` of `[$MARCRO{n}$]`), from 1; 0 for a fixed position. */
export function numeroPorPosicion(reglas: ReglasPlataforma, indice: number): number {
  return Math.max(0, indice - reglas.columnas_fijas.length + 1);
}

/** The header the column at `indice` (from 0) gets by position; `null` when the platform sets none or the position is a fixed one. */
export function encabezadoPorPosicion(reglas: ReglasPlataforma, indice: number): string | null {
  const patron = reglas.encabezado_por_posicion;
  const n = numeroPorPosicion(reglas, indice);
  return patron === null || n < 1 ? null : patron.replaceAll('{n}', String(n));
}

/**
 * How many rows from the top are fixed: the ones that carry the platform's name in the platform's
 * position, one after another. Everything below is ordinary, and nothing can go above them.
 */
export function cantidadDeFijas(columnas: ReadonlyArray<{ nombre: string }>, reglas: ReglasPlataforma | null): number {
  if (reglas === null) return 0;
  let n = 0;
  while (n < reglas.columnas_fijas.length && columnas[n]?.nombre === reglas.columnas_fijas[n].nombre) n += 1;
  return n;
}

/** Whether the header was not left as its position gives it: the case the screen warns about. */
export function encabezadoEditado(reglas: ReglasPlataforma, indice: number, nombre: string): boolean {
  const porDefecto = encabezadoPorPosicion(reglas, indice);
  return porDefecto !== null && nombre !== porDefecto;
}

/**
 * A fixed column's starting content: the platform's text in the `[@campo]` syntax, as an expression.
 *
 * shortcut: only plain references and literals. A reference with functions (`[@campo | f()]`) stays
 * literal text, because the real parser lives in the backend; upgrade when a platform needs one.
 */
export function expresionDeTexto(texto: string): Expresion {
  const nodos: Nodo[] = [];
  const agregarTexto = (valor: string) => {
    if (valor === '') return;
    const ultimo = nodos[nodos.length - 1];
    if (ultimo?.tipo === 'texto') ultimo.valor += valor;
    else nodos.push({ tipo: 'texto', valor });
  };
  const referencia = /\[@(@|[^\]|@[]+)\]/g;
  let desde = 0;
  for (const coincidencia of texto.matchAll(referencia)) {
    agregarTexto(texto.slice(desde, coincidencia.index));
    if (coincidencia[1] === '@') agregarTexto('[@');
    else nodos.push({ tipo: 'variable', nombre: coincidencia[1].trim(), funciones: [] });
    desde = coincidencia.index + coincidencia[0].length;
  }
  agregarTexto(texto.slice(desde));
  return { nodos };
}
