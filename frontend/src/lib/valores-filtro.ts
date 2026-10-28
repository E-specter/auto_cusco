/**
 * The list of values of a list filter (RF-67, docs/filtro-valores-interfaz.md §2): when a filter offers one,
 * which filters above it make up its cascade, how its answer splits into «in the list» and «checked, no products»,
 * and the counts under it. Pure: no DOM, no fetch.
 */

import type { Campos } from './api';
import { normalizarBusqueda } from './editor-texto';
import { escribirFiltro, filtroCompleto, tipoDe, type FiltroBorrador } from './seleccion';

export interface ValorConCantidad {
  /** `null` is «(vacío)»: the products with no value. */
  valor: string | null;
  cantidad: number;
}

/** A search box appears with more values than this (§2.2). */
export const MAS_DE_PARA_BUSCAR = 10;

/** A text field with «es uno de» or «no es ninguno de» picks from a list when the backend offers one (§2.1). */
export function pideLista(campos: Campos, filtro: FiltroBorrador): boolean {
  return (
    Boolean(filtro.campo) &&
    tipoDe(campos, filtro.campo) === 'texto' &&
    (filtro.operador === 'en' || filtro.operador === 'no_en')
  );
}

/**
 * The filters that make up the cascade of the filter at `indice`: the complete ones above it, written as the API
 * reads them (§2.6). An incomplete one does not filter in the result, so it does not here.
 */
export function filtrosDeArriba(filtros: readonly FiltroBorrador[], indice: number): string[] {
  return filtros.slice(0, indice).filter(filtroCompleto).map(escribirFiltro);
}

/** What a list depends on: the date, the field and the filters above. A change of any asks for it again. */
export function claveDeLista(fecha: string, campo: string, arriba: readonly string[]): string {
  return JSON.stringify([fecha, campo, arriba]);
}

/** What decides whether a field offers a list at all: only the date and the field, never the filters (§2.1). */
export function claveDeDecision(fecha: string, campo: string): string {
  return JSON.stringify([fecha, campo]);
}

/** The values checked, without blank lines and without repeats. */
export function marcados(filtro: FiltroBorrador): string[] {
  return [...new Set(filtro.valores.map((valor) => valor.trim()).filter(Boolean))];
}

export interface Reparto {
  /** The values of the answer that have a value, in the answer's order (D-FV-2). */
  enLista: ValorConCantidad[];
  /** «(vacío)» shows when there are products without a value, or when it is checked (§2.2). */
  mostrarVacio: boolean;
  cantidadVacio: number;
  /** Checked values the answer no longer has: they stay checked, apart (§2.4). */
  sinProductos: string[];
}

export function repartir(respuesta: readonly ValorConCantidad[], filtro: FiltroBorrador): Reparto {
  const enLista = respuesta.filter((item): item is ValorConCantidad & { valor: string } => item.valor !== null);
  const vacio = respuesta.find((item) => item.valor === null);
  const presentes = new Set(enLista.map((item) => item.valor.trim()));
  return {
    enLista,
    mostrarVacio: vacio !== undefined || filtro.vacio === true,
    cantidadVacio: vacio?.cantidad ?? 0,
    sinProductos: marcados(filtro).filter((valor) => !presentes.has(valor)),
  };
}

/** Checks or unchecks one value, keeping the others where they were. */
export function conValor(valores: readonly string[], valor: string, marcado: boolean): string[] {
  const limpios = valores.map((v) => v.trim()).filter(Boolean);
  const sin = limpios.filter((v) => v !== valor.trim());
  return marcado ? [...sin, valor.trim()] : sin;
}

/** The values the search leaves on screen: it hides, it never unchecks (§2.2). «(vacío)» is not searched. */
export function buscar(valores: readonly ValorConCantidad[], texto: string): ValorConCantidad[] {
  const consulta = normalizarBusqueda(texto);
  if (!consulta) return [...valores];
  return valores.filter((item) => normalizarBusqueda(item.valor ?? '').includes(consulta));
}

/** «{n} de {total} marcados»: every checked value counts, the ones with no products and «(vacío)» too. */
export function resumen(filtro: FiltroBorrador, reparto: Reparto): { n: number; total: number } {
  return {
    n: marcados(filtro).length + (filtro.vacio ? 1 : 0),
    total: reparto.enLista.length + (reparto.mostrarVacio ? 1 : 0) + reparto.sinProductos.length,
  };
}
