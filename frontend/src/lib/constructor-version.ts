/**
 * How the constructor opens a definition and what it lets the analyst do
 * (docs/motor-texto-enriquecido-interfaz.md §5.1, decided 2026-10-03).
 *
 * The rule: looking at the history must never leave a save armed that would replace the current
 * version. No version is ever modified, so every save creates the one after the latest; saving
 * while looking at an old version would put its content on top of the current one. So an old
 * version opens read-only, and "Usar como base" is the explicit step that makes it editable.
 *
 * Pure: no DOM, no fetch. The screen reads the mode and draws; the tests call it directly. Wording
 * is the screen's (i18n): this only says which case applies and with which numbers.
 */

import type { Borrador, DefinicionRespuesta } from './constructor-columnas';
import { estaVacia } from './variantes';

/**
 * - `nueva`: never saved; its first save creates version 1.
 * - `editable`: the latest version, editable as always.
 * - `lectura`: an older version, read-only.
 * - `base`: an older version the analyst chose to build on; editable until saved or discarded.
 */
export type ModoVista = 'nueva' | 'editable' | 'lectura' | 'base';

/** `null` is a definition that has not been saved yet. */
export function modoInicial(respuesta: DefinicionRespuesta | null): ModoVista {
  if (respuesta === null) return 'nueva';
  return respuesta.version.numero === respuesta.version_vigente ? 'editable' : 'lectura';
}

export const esEditable = (modo: ModoVista): boolean => modo !== 'lectura';

/** "Usar como base": only an old version in read-only mode changes. */
export const usarComoBase = (modo: ModoVista): ModoVista => (modo === 'lectura' ? 'base' : modo);

/**
 * "Descartar": what was built on an old version goes back to read-only. The latest version and a
 * new definition keep their mode; the screen only restores the draft.
 */
export const descartar = (modo: ModoVista): ModoVista => (modo === 'base' ? 'lectura' : modo);

/**
 * Whether Guardar is on. `cambios` is whether the draft differs from what is saved (for a new
 * definition: whether anything is written, see `hayContenido`). Building on an old version saves
 * even without changes: copying its content forward is the point.
 */
export function puedeGuardar(modo: ModoVista, cambios: boolean, guardando = false): boolean {
  if (guardando || modo === 'lectura') return false;
  return modo === 'base' ? true : cambios;
}

export type Aviso =
  | { tipo: 'ninguno' }
  | { tipo: 'lectura'; vista: number; vigente: number }
  | { tipo: 'base'; base: number; nueva: number; vigente: number };

/** The notice over the editor: `.notice--info` in read-only, `.notice--warning` when building on it. */
export function aviso(modo: ModoVista, respuesta: DefinicionRespuesta | null): Aviso {
  if (respuesta === null || (modo !== 'lectura' && modo !== 'base')) return { tipo: 'ninguno' };
  const vista = respuesta.version.numero;
  const vigente = respuesta.version_vigente;
  return modo === 'lectura'
    ? { tipo: 'lectura', vista, vigente }
    : { tipo: 'base', base: vista, nueva: vigente + 1, vigente };
}

/**
 * What saving does when the version on screen is not the latest: a new version with the old
 * content, which becomes the latest. `null` when it is the latest (nothing special).
 */
export function guardadoDeUnaVersionAntigua(
  respuesta: DefinicionRespuesta,
): { base: number; nueva: number; vigenteAntes: number } | null {
  if (respuesta.version.numero === respuesta.version_vigente) return null;
  return { base: respuesta.version.numero, nueva: respuesta.version_vigente + 1, vigenteAntes: respuesta.version_vigente };
}

/**
 * Whether a definition that has never been saved has anything written, so Guardar is not offered on
 * a blank form. A name of spaces does not count, and neither does the single empty column it opens with.
 */
export function hayContenido(borrador: Borrador): boolean {
  const columnaConContenido = borrador.columnas.some(
    (c) =>
      c.nombre.trim() !== '' ||
      !estaVacia(c.expresion) ||
      c.valor_por_defecto !== null ||
      c.variantes.length > 0,
  );
  return borrador.nombre.trim() !== '' || columnaConContenido || borrador.columnas.length > 1;
}
