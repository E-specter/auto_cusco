/**
 * Logic of the MOWA MES follow-up screen (T-MM-F3), kept out of the page so it
 * can be tested without a browser. Every figure comes from the API as counted
 * there; this module only orders, pages and reads what arrived.
 */

import type {
  CifrasGrupo,
  CodigoMowaMes,
  Conciliacion,
  ConsumoLimite,
  EstadoConteo,
} from './api-mowa-mes';

/** Exclusion reasons in evaluation order (docs/mowa-mes.md §12): the filter's options. */
export const CODIGOS_EXCLUSION = [
  'telefono_invalido',
  'falta_documento',
  'sin_speech',
  'falta_titular',
  'falta_vencimiento',
  'mensaje_excede_160',
] as const satisfies readonly CodigoMowaMes[];

// ---- Months --------------------------------------------------------------------

const dosDigitos = (n: number) => String(n).padStart(2, '0');

/** `YYYY-MM` of a local date. */
export function mesDe(fecha: Date): string {
  return `${fecha.getFullYear()}-${dosDigitos(fecha.getMonth() + 1)}`;
}

/** Move a `YYYY-MM` month by whole months, across years. */
export function moverMes(mes: string, delta: number): string {
  const [anio, numero] = mes.split('-').map(Number);
  const indice = anio * 12 + (numero - 1) + delta;
  return `${Math.floor(indice / 12)}-${dosDigitos((indice % 12) + 1)}`;
}

/** Share of the monthly limit already loaded; 0 for a limit that is not positive. */
export function usoDelLimite(consumo: Pick<ConsumoLimite, 'cargados_mes' | 'limite'>): number {
  return consumo.limite > 0 ? consumo.cargados_mes / consumo.limite : 0;
}

// ---- Downloads -------------------------------------------------------------------

export interface ResumenDescarga {
  campana: number | null;
  archivo: number | null;
  total: number | null;
  filas: number | null;
  supervision: number | null;
  bytes: number | null;
}

/**
 * The `X-Mowa-Mes-*` summary as numbers. A header that is missing or not a
 * whole number reads as null rather than as a guess.
 */
export function leerResumenDescarga(resumen: Record<string, string>): ResumenDescarga {
  const entero = (clave: string) => {
    const valor = resumen[clave]?.trim();
    return valor && /^\d+$/.test(valor) ? Number(valor) : null;
  };
  return {
    campana: entero('campana'),
    archivo: entero('archivo'),
    total: entero('archivos-total'),
    filas: entero('filas'),
    supervision: entero('supervision'),
    bytes: entero('bytes'),
  };
}

/** The server's file name, or a stable one when it sent none. */
export function nombreArchivo(nombre: string | null, campanaId: number, numero: number): string {
  return nombre && nombre.trim() ? nombre.trim() : `mowa_mes_campana_${campanaId}_archivo_${numero}.xlsx`;
}

// ---- Reconciliation ------------------------------------------------------------

export type GrupoConciliacion = 'productos' | 'supervision' | 'total';

/** Products, supervision and total, always in that order and always apart (RF-41). */
export function filasConciliacion(
  conciliacion: Conciliacion,
): Array<{ grupo: GrupoConciliacion; cifras: CifrasGrupo }> {
  return (['productos', 'supervision', 'total'] as const).map((grupo) => ({
    grupo,
    cifras: conciliacion[grupo],
  }));
}

/** States as MES wrote them, most frequent first, ties by name. */
export function ordenarEstados(estados: readonly EstadoConteo[]): EstadoConteo[] {
  return [...estados].sort((a, b) => b.cantidad - a.cantidad || a.estado.localeCompare(b.estado));
}

// ---- Paging ----------------------------------------------------------------------

/** The 1-based range a page shows, or null when the page is empty. */
export function rangoPagina(
  desplazamiento: number,
  enPagina: number,
  total: number,
): { desde: number; hasta: number } | null {
  if (enPagina <= 0 || total <= 0) return null;
  return { desde: desplazamiento + 1, hasta: Math.min(desplazamiento + enPagina, total) };
}
