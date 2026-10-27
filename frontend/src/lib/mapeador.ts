/**
 * Pure state of the header mapper (docs/mapeador-encabezados-interfaz.md §3).
 *
 * The backend decides each header's state, suggestion and problems; this file
 * only keeps the analyst's choices and turns them into the assignments the
 * backend expects, with the origin each gesture sends (§3.5). No DOM, no fetch.
 */

import type { components } from './contrato-api';

type Esquemas = components['schemas'];
export type Analisis = Esquemas['AnalisisRespuesta'];
export type Columna = Esquemas['ColumnaAnalizadaRespuesta'];
export type Asignacion = Esquemas['AsignacionEntrada'];
export type Problema = Esquemas['ProblemaMapeoRespuesta'];
type Origen = Esquemas['OrigenAsignacion'];

const HOJAS_DE_CALCULO = new Set<Esquemas['FormatoTabla']>(['xlsx', 'xlsb', 'xls', 'ods']);

/** The column as the analyst sees it in the file: A, B… AA in a spreadsheet; 1, 2… in CSV and JSON. */
export function etiquetaColumna(indice: number, formato: Esquemas['FormatoTabla']): string {
  if (!HOJAS_DE_CALCULO.has(formato)) return String(indice + 1);
  let letras = '';
  for (let n = indice + 1; n > 0; n = Math.floor((n - 1) / 26)) {
    letras = String.fromCharCode(65 + ((n - 1) % 26)) + letras;
  }
  return letras;
}

/**
 * The origin a column has while nobody touched it. A similar header keeps the
 * unreviewed origin (`coincide`): `manual` would count as a review in the
 * backend. A column left as «No cargar» without a match is `manual` (B1).
 */
function origenInicial(columna: Columna): Origen {
  if (columna.estado === 'recordado') return 'recordado';
  if (columna.estado === 'sin_coincidencia') return 'manual';
  return 'coincide';
}

export function asignacionesIniciales(analisis: Analisis): Asignacion[] {
  return analisis.columnas.map((c) => ({ indice: c.indice, campo: c.sugerido, origen: origenInicial(c) }));
}

const columnaDe = (analisis: Analisis, indice: number) => analisis.columnas.find((c) => c.indice === indice)!;

function reemplazar(asignaciones: readonly Asignacion[], nueva: Asignacion): Asignacion[] {
  return asignaciones.map((a) => (a.indice === nueva.indice ? nueva : a));
}

/** A choice in the select. Choosing the suggested field again keeps the origin it had: it is not a review. */
export function elegir(asignaciones: readonly Asignacion[], analisis: Analisis, indice: number, campo: string | null): Asignacion[] {
  const columna = columnaDe(analisis, indice);
  const origen = campo === columna.sugerido ? origenInicial(columna) : 'manual';
  return reemplazar(asignaciones, { indice, campo, origen });
}

/** «Aceptar»: the suggested field, reviewed. */
export function aceptar(asignaciones: readonly Asignacion[], analisis: Analisis, indice: number): Asignacion[] {
  return reemplazar(asignaciones, { indice, campo: columnaDe(analisis, indice).sugerido, origen: 'parecido_aceptado' });
}

/** A similar header still waiting for «Aceptar»: the suggested field, without review. */
export function pendiente(columna: Columna, asignacion: Asignacion): boolean {
  return columna.estado === 'parecido' && asignacion.campo === columna.sugerido && asignacion.origen !== 'parecido_aceptado';
}

/** «Aceptar sugerencias»: every pending similar header at once. */
export function aceptarTodas(asignaciones: readonly Asignacion[], analisis: Analisis): Asignacion[] {
  return asignaciones.map((a) => {
    const columna = columnaDe(analisis, a.indice);
    return pendiente(columna, a) ? { ...a, origen: 'parecido_aceptado' } : a;
  });
}

export type Insignia = 'recordado' | 'coincide' | 'por_revisar' | 'aceptado' | 'sin_coincidencia' | 'manual';

/** What the tag says now: the analysis state while the column has its field, «Elegido a mano» otherwise (§3.4). */
export function insignia(columna: Columna, asignacion: Asignacion): Insignia {
  if (asignacion.campo !== columna.sugerido) return 'manual';
  if (columna.estado === 'parecido') return asignacion.origen === 'parecido_aceptado' ? 'aceptado' : 'por_revisar';
  return columna.estado;
}

/** Which columns use each field, for «· en uso en C» and the disabled options. */
export function usos(asignaciones: readonly Asignacion[]): Map<string, number[]> {
  const mapa = new Map<string, number[]>();
  for (const a of asignaciones) {
    if (a.campo !== null) mapa.set(a.campo, [...(mapa.get(a.campo) ?? []), a.indice]);
  }
  return mapa;
}

/** Whether the analyst chose or accepted anything: changing the sheet would discard it (§4). */
export function modificado(asignaciones: readonly Asignacion[], analisis: Analisis): boolean {
  const iniciales = asignacionesIniciales(analisis);
  return asignaciones.some((a, i) => a.campo !== iniciales[i].campo || a.origen !== iniciales[i].origen);
}

/** Columns to review: a pending similar header, or a problem on that column. */
export function porRevisar(analisis: Analisis, asignaciones: readonly Asignacion[], problemas: readonly Problema[]): Set<number> {
  const indices = new Set(problemas.flatMap((p) => (p.indice === null ? [] : [p.indice])));
  for (const a of asignaciones) if (pendiente(columnaDe(analisis, a.indice), a)) indices.add(a.indice);
  return indices;
}
