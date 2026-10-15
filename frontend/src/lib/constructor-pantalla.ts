/**
 * What the column-builder screen decides from the draft and from the backend's answers
 * (docs/motor-texto-enriquecido-interfaz.md §5 and §9.4), kept out of the page so it can be
 * tested without a browser. Pure: no DOM, no fetch, never mutates its arguments.
 *
 * Nothing here evaluates or validates: a problem is the backend's, and this only says where on
 * screen it belongs; a content summary only reads the tree it is given.
 */

import type { ProblemaDefinicion } from './api-definiciones';
import type { Borrador, Expresion, FormatoFinanciero } from './constructor-columnas';
import { estaVacia } from './variantes';

// ---- Where a problem belongs --------------------------------------------------------------

/** A field of a column a problem can be about; `expresion` is its content (or its variant). */
export type CampoDeColumna =
  | 'nombre'
  | 'tipo'
  | 'formato_fecha'
  | 'formato_financiero'
  | 'valor_por_defecto'
  | 'variantes'
  | 'expresion';

export type Destino =
  | { tipo: 'definicion'; campo: string | null }
  | { tipo: 'columna'; id: string; campo: CampoDeColumna; segmento: string | null };

/**
 * The column the backend names by its position in the request, as the draft's own id; the field
 * it is about; and the segment when it is a variant's. A column that no longer exists (it was
 * removed while the answer was on its way) is not pinned to whichever one took its place: the
 * problem becomes the definition's.
 */
export function destinoDeProblema(problema: ProblemaDefinicion, borrador: Borrador): Destino {
  if (problema.columna === null) return { tipo: 'definicion', campo: problema.campo };
  const columna = borrador.columnas[problema.columna];
  if (!columna) return { tipo: 'definicion', campo: null };
  return {
    tipo: 'columna',
    id: columna.id,
    campo: (problema.campo ?? 'expresion') as CampoDeColumna,
    segmento: problema.segmento,
  };
}

export type ProblemasAgrupados = {
  /** Of the definition itself: its name, its columns, its segmentation. */
  definicion: ProblemaDefinicion[];
  /** Of each column, by the draft's id, in the backend's order. */
  porColumna: Map<string, ProblemaDefinicion[]>;
  total: number;
};

export function agruparProblemas(problemas: readonly ProblemaDefinicion[], borrador: Borrador): ProblemasAgrupados {
  const definicion: ProblemaDefinicion[] = [];
  const porColumna = new Map<string, ProblemaDefinicion[]>();
  for (const problema of problemas) {
    const destino = destinoDeProblema(problema, borrador);
    if (destino.tipo === 'definicion') {
      definicion.push(problema);
    } else {
      porColumna.set(destino.id, [...(porColumna.get(destino.id) ?? []), problema]);
    }
  }
  return { definicion, porColumna, total: problemas.length };
}

// ---- How a column's content reads in the list -----------------------------------------------

export type ResumenContenido =
  | { modo: 'vacio' }
  | { modo: 'variable'; variable: string; funciones: number }
  | { modo: 'texto'; fragmento: string; variables: number; recortado: boolean };

/**
 * A short reading of a column's content for its row: a single variable (with how many functions
 * it carries) or the start of a composed text, each variable by its visible name and with no
 * syntax (the user never sees it, §1.1). The result of evaluating it is the preview's, never this.
 */
export function resumenDeContenido(
  expresion: Expresion,
  etiquetaVariable: (nombre: string) => string,
  maximo = 60,
): ResumenContenido {
  if (estaVacia(expresion)) return { modo: 'vacio' };
  const [unico] = expresion.nodos;
  if (expresion.nodos.length === 1 && unico.tipo === 'variable') {
    return { modo: 'variable', variable: etiquetaVariable(unico.nombre), funciones: unico.funciones.length };
  }
  let texto = '';
  let variables = 0;
  for (const nodo of expresion.nodos) {
    if (nodo.tipo === 'texto') {
      texto += nodo.valor;
    } else {
      variables += 1;
      texto += etiquetaVariable(nodo.nombre);
    }
  }
  texto = texto.replace(/\s+/g, ' ');
  const recortado = texto.length > maximo;
  return { modo: 'texto', fragmento: recortado ? texto.slice(0, maximo) : texto, variables, recortado };
}

// ---- Format example ---------------------------------------------------------------------------

/** 1234.5 written with the column's separators and decimals: the live example under the format. */
export function ejemploFinanciero(formato: FormatoFinanciero): string {
  const unidades = Math.round(1234.5 * 10 ** formato.decimales);
  const texto = String(unidades).padStart(formato.decimales + 1, '0');
  const entero = texto.slice(0, texto.length - formato.decimales);
  const fraccion = formato.decimales > 0 ? texto.slice(-formato.decimales) : '';
  const conMiles = entero.replace(/\B(?=(\d{3})+(?!\d))/g, formato.separador_miles);
  return fraccion ? `${conMiles}${formato.separador_decimal}${fraccion}` : conMiles;
}
