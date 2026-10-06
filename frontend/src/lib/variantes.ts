/**
 * Per-segment variants of a column (RF-50; interface rules §5.4 and §9.1).
 *
 * A column has its own expression — the default content — and may carry one
 * variant per segment that replaces it for that segment
 * (docs/motor-texto-enriquecido.md, ColumnaEntrada and VarianteEntrada). There
 * is no "default" variant key: a problem the backend reports with
 * `segmento: null` belongs to the column's own expression.
 *
 * The column's state only transports its `variantes`; everything that reads
 * or changes them lives here, so the column builder and the MOWA MES speech
 * share one set of rules. Pure: no DOM, no fetch, never mutates its arguments.
 */

import type { Expresion, Problema } from './expresion';

export type Variante = {
  segmento: string;
  expresion: Expresion;
};

/** A segment as the catalogue lists it (`RangoRespuesta`). */
export type Segmento = {
  clave: string;
  etiqueta: string;
  desde: number | null;
  hasta: number | null;
};

export type EstadoVariante = 'propia' | 'por_defecto' | 'vacia' | 'con_problema';

export type ResumenSegmento = Segmento & {
  /**
   * `propia`: the segment has its own content; `por_defecto`: it uses the
   * column's; `vacia`: neither has anything, so the segment would produce an
   * empty value; `con_problema`: the backend reported a problem in it.
   */
  estado: EstadoVariante;
  problemas: number;
};

/** A problem as the backend ties it to a segment (`ProblemaTextoRespuesta`). */
export type ProblemaDeSegmento = Problema & {
  segmento?: string | null;
  campo?: string | null;
};

/** An expression with nothing that would produce text. */
export function estaVacia(expresion: Expresion | null | undefined): boolean {
  return !expresion || expresion.nodos.every((nodo) => nodo.tipo === 'texto' && nodo.valor === '');
}

export function varianteDe(variantes: readonly Variante[], segmento: string): Variante | undefined {
  return variantes.find((variante) => variante.segmento === segmento);
}

/** The expression a segment actually uses: its own, or the column's. */
export function expresionDeSegmento(
  porDefecto: Expresion,
  variantes: readonly Variante[],
  segmento: string,
): Expresion {
  return varianteDe(variantes, segmento)?.expresion ?? porDefecto;
}

function copiaExpresion(expresion: Expresion): Expresion {
  return {
    nodos: expresion.nodos.map((nodo) =>
      nodo.tipo === 'texto'
        ? { ...nodo }
        : {
            ...nodo,
            funciones: nodo.funciones.map((f) => ({
              nombre: f.nombre,
              args: f.args.map((a) => (typeof a === 'object' ? { ...a } : a)),
            })),
          },
    ),
  };
}

/**
 * Set a segment's own content. An empty expression removes the variant, so
 * the segment falls back to the column's content instead of producing an
 * empty value nobody asked for.
 */
export function fijarVariante(
  variantes: readonly Variante[],
  segmento: string,
  expresion: Expresion,
): Variante[] {
  const indice = variantes.findIndex((v) => v.segmento === segmento);
  if (estaVacia(expresion)) return variantes.filter((v) => v.segmento !== segmento);
  const nueva = { segmento, expresion: copiaExpresion(expresion) };
  if (indice < 0) return [...variantes, nueva];
  return [...variantes.slice(0, indice), nueva, ...variantes.slice(indice + 1)];
}

/** Drop a segment's own content: it goes back to the column's. */
export function quitarVariante(variantes: readonly Variante[], segmento: string): Variante[] {
  return variantes.filter((v) => v.segmento !== segmento);
}

/**
 * "Copiar de otro segmento": the target gets an independent copy of what the
 * source uses, its own content or the column's. Editing it later never
 * changes the source.
 */
export function copiarVariante(
  porDefecto: Expresion,
  variantes: readonly Variante[],
  desde: string,
  hacia: string,
): Variante[] {
  if (desde === hacia) return [...variantes];
  return fijarVariante(variantes, hacia, expresionDeSegmento(porDefecto, variantes, desde));
}

const esDelContenidoPropio = (p: ProblemaDeSegmento) =>
  (p.segmento ?? null) === null && (p.campo ?? 'expresion') === 'expresion';

/** Problems of the column's own content (`segmento: null`). */
export function problemasPorDefecto(problemas: readonly ProblemaDeSegmento[]): number {
  return problemas.filter(esDelContenidoPropio).length;
}

/** Each segment, in the catalogue's order, with what the selector shows. */
export function resumirSegmentos(
  segmentos: readonly Segmento[],
  porDefecto: Expresion,
  variantes: readonly Variante[],
  problemas: readonly ProblemaDeSegmento[],
): ResumenSegmento[] {
  const defectoVacio = estaVacia(porDefecto);
  return segmentos.map((segmento) => {
    const propios = problemas.filter((p) => p.segmento === segmento.clave).length;
    const variante = varianteDe(variantes, segmento.clave);
    let estado: EstadoVariante;
    if (propios > 0) estado = 'con_problema';
    else if (variante && !estaVacia(variante.expresion)) estado = 'propia';
    else estado = defectoVacio ? 'vacia' : 'por_defecto';
    return { ...segmento, estado, problemas: propios };
  });
}

/** Segments that would produce an empty value: no content of their own and an empty default. */
export function segmentosVacios(
  segmentos: readonly Segmento[],
  porDefecto: Expresion,
  variantes: readonly Variante[],
): Segmento[] {
  return segmentos.filter((s) => estaVacia(expresionDeSegmento(porDefecto, variantes, s.clave)));
}

/** Variants of segments the criterion no longer has (after changing the table of ranges). */
export function variantesHuerfanas(segmentos: readonly Segmento[], variantes: readonly Variante[]): Variante[] {
  const claves = new Set(segmentos.map((s) => s.clave));
  return variantes.filter((v) => !claves.has(v.segmento));
}
