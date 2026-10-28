/**
 * The order of the filters of a selection (RF-68, docs/filtro-valores-interfaz.md §3): moving one, where the
 * focus goes after it, and where a drag would drop it. The order does not change the result (the query is an AND),
 * but it decides each filter's list of values (the cascade) and it is saved with the selection. Pure: no DOM.
 */

export type BotonDeOrden = 'subir' | 'bajar';

/** The list with the item at `desde` moved to `hacia`, the others keeping their order. A new array always. */
export function moverFiltro<T>(lista: readonly T[], desde: number, hacia: number): T[] {
  const copia = [...lista];
  if (desde < 0 || desde >= copia.length) return copia;
  const destino = Math.min(copia.length - 1, Math.max(0, hacia));
  const [movido] = copia.splice(desde, 1);
  copia.splice(destino, 0, movido);
  return copia;
}

/** The first filter cannot go up and the last cannot go down: their buttons are off (§3.3). */
export function puedeMover(boton: BotonDeOrden, indice: number, total: number): boolean {
  return boton === 'subir' ? indice > 0 : indice < total - 1;
}

/**
 * The button that keeps the focus after a move: the same one, in the filter's new row; or the other one when that
 * one is off because the filter reached an edge (§3.3).
 */
export function botonConFoco(boton: BotonDeOrden, nuevoIndice: number, total: number): BotonDeOrden {
  if (puedeMover(boton, nuevoIndice, total)) return boton;
  return boton === 'subir' ? 'bajar' : 'subir';
}

/**
 * Where a filter dragged from `origen` lands if dropped with the pointer at `y`, given the vertical centre of every
 * row: before the first row whose centre is below the pointer, or at the end. `antes` is the row the drop line is
 * drawn above (`total` means below the last one); `destino` is the final position of the filter.
 */
export function destinoDeArrastre(centros: readonly number[], y: number, origen: number): { antes: number; destino: number } {
  const hallada = centros.findIndex((centro) => y < centro);
  const antes = hallada < 0 ? centros.length : hallada;
  const destino = antes > origen ? antes - 1 : antes;
  return { antes, destino: Math.min(centros.length - 1, Math.max(0, destino)) };
}

/** The 1-based position, as it is said and shown. */
export const posicion = (indice: number): number => indice + 1;
