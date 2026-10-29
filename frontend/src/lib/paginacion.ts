/**
 * Client-side paging of rows the page already holds: asking for another page never calls the API.
 * Generic: it knows nothing about MOWA MES.
 */

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
