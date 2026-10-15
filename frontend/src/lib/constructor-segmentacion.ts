/**
 * The segmentation of a column definition (docs/motor-texto-enriquecido-interfaz.md §5.1, §5.4).
 *
 * A definition has none until it is switched on. Then its criterion is either calculated (the days
 * of delay against the context's table of ranges, the default because the sheet's own segment
 * field arrives badly loaded) or the value of a field, and a policy says what happens to a product
 * that falls in no segment. The columns' variants hang from it: they are keyed by the segment.
 *
 * Pure: no DOM, no fetch, never mutates its arguments. Changing the criterion does not touch the
 * variants (their keys may stop existing): telling the analyst and choosing is the screen's, with
 * `columnasConVariantes` and `quitarTodasLasVariantes`.
 */

import type { Borrador, PoliticaSinSegmento, RangoDias, Segmentacion } from './constructor-columnas';
import type { Segmento } from './variantes';

/** What the catalogue says about a context's segments (`ContextoRespuesta`). */
export type ContextoSegmentos = {
  tabla: readonly RangoDias[];
  variable_dias: string;
};

const copiaTabla = (tabla: readonly RangoDias[]): RangoDias[] => tabla.map((r) => ({ ...r }));

const calculado = (contexto: ContextoSegmentos): Segmentacion['criterio'] => ({
  tipo: 'calculado',
  variable_dias: contexto.variable_dias,
  tabla: copiaTabla(contexto.tabla),
});

/** Switch segmentation on with the calculated criterion; one that is already on is left as it is. */
export function activarSegmentacion(borrador: Borrador, contexto: ContextoSegmentos): Borrador {
  if (borrador.segmentacion) return borrador;
  return { ...borrador, segmentacion: { criterio: calculado(contexto), politica: 'excluir' } };
}

/** Switch it off. Without a segmentation no column keeps variants: the backend would refuse them. */
export function desactivarSegmentacion(borrador: Borrador): Borrador {
  return { ...quitarTodasLasVariantes(borrador), segmentacion: null };
}

export function fijarCriterioCalculado(borrador: Borrador, contexto: ContextoSegmentos): Borrador {
  if (!borrador.segmentacion) return borrador;
  return { ...borrador, segmentacion: { ...borrador.segmentacion, criterio: calculado(contexto) } };
}

export function fijarCriterioCampo(borrador: Borrador, campo: string): Borrador {
  if (!borrador.segmentacion) return borrador;
  return {
    ...borrador,
    segmentacion: { ...borrador.segmentacion, criterio: { tipo: 'campo', campo } },
  };
}

export function fijarPolitica(borrador: Borrador, politica: PoliticaSinSegmento): Borrador {
  if (!borrador.segmentacion) return borrador;
  return { ...borrador, segmentacion: { ...borrador.segmentacion, politica } };
}

/**
 * The segments the selector of variants offers: the table's ranges in order, or the values the
 * analyst has given for a field (no repeats, no blanks). No segmentation, no segments.
 */
export function segmentosDe(segmentacion: Segmentacion | null, valores: readonly string[]): Segmento[] {
  if (!segmentacion) return [];
  const { criterio } = segmentacion;
  if (criterio.tipo === 'calculado') return criterio.tabla.map((r) => ({ ...r }));
  const vistos = new Set<string>();
  const segmentos: Segmento[] = [];
  for (const valor of valores) {
    if (valor.trim() === '' || vistos.has(valor)) continue;
    vistos.add(valor);
    segmentos.push({ clave: valor, etiqueta: valor, desde: null, hasta: null });
  }
  return segmentos;
}

/** How many columns carry at least one variant. */
export function columnasConVariantes(borrador: Borrador): number {
  return borrador.columnas.filter((c) => c.variantes.length > 0).length;
}

/** The keys the variants of every column use, in order of appearance, without repeats. */
export function valoresEnUso(borrador: Borrador): string[] {
  const claves = new Set<string>();
  for (const columna of borrador.columnas) {
    for (const variante of columna.variantes) claves.add(variante.segmento);
  }
  return [...claves];
}

/** Every column back to its own content only; the default content is not touched. */
export function quitarTodasLasVariantes(borrador: Borrador): Borrador {
  return { ...borrador, columnas: borrador.columnas.map((c) => ({ ...c, variantes: [] })) };
}
