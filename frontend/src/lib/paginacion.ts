/**
 * Paging: `paginar` slices rows the page already holds (asking for another page never calls the API),
 * and `pintarPaginador` paints the pager under any paged table. Generic: it knows nothing about a screen.
 */

import { formatNumber } from './format';
import { t } from './i18n';

/** Rows per page of the campaign preview's tables (RF-MM-26). */
export const FILAS_POR_PAGINA = 10;

export interface PaginaLocal<T> {
  filas: T[];
  /** 1-based, clamped into 1..paginas. */
  pagina: number;
  paginas: number;
  /** 1-based range shown, both 0 when there are no rows. */
  desde: number;
  hasta: number;
  total: number;
  /** The pager only exists when the rows do not fit one page. */
  hayPaginador: boolean;
}

/** One page of rows the client already holds; asking for another never calls the API. */
export function paginar<T>(
  filas: readonly T[],
  pagina: number,
  porPagina: number = FILAS_POR_PAGINA,
): PaginaLocal<T> {
  const total = filas.length;
  const paginas = Math.max(1, Math.ceil(total / porPagina));
  const actual = Math.min(Math.max(1, Math.trunc(pagina) || 1), paginas);
  const inicio = (actual - 1) * porPagina;
  const fin = Math.min(inicio + porPagina, total);
  return {
    filas: filas.slice(inicio, fin),
    pagina: actual,
    paginas,
    desde: total === 0 ? 0 : inicio + 1,
    hasta: fin,
    total,
    hayPaginador: total > porPagina,
  };
}

/** The 1-based range a page shows, out of `total` rows. */
export interface RangoPagina {
  desde: number;
  hasta: number;
  total: number;
}

/**
 * Paint a pager (`.pager`: `[data-page-prev]`, `[data-page-range]`, `[data-page-next]`): the range, and
 * each button off at its edge. It only exists when the rows do not fit one page; with no range (an empty
 * page) it is hidden too. Whoever pages (the screen) moves the page on a click.
 */
export function pintarPaginador(raiz: HTMLElement, rango: RangoPagina | null): void {
  const unaSola = rango === null || (rango.desde <= 1 && rango.hasta >= rango.total);
  raiz.hidden = unaSola;
  if (unaSola) return;
  raiz.querySelector<HTMLElement>('[data-page-range]')!.textContent = t('console.incidencias.range', {
    desde: formatNumber(rango.desde),
    hasta: formatNumber(rango.hasta),
    total: formatNumber(rango.total),
  });
  raiz.querySelector<HTMLButtonElement>('[data-page-prev]')!.disabled = rango.desde <= 1;
  raiz.querySelector<HTMLButtonElement>('[data-page-next]')!.disabled = rango.hasta >= rango.total;
}
