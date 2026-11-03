/**
 * What the saved-texts component decides from the texts and from the backend's answers
 * (docs/motor-texto-enriquecido-interfaz.md §11.3, RF-69), kept out of the script so it can be tested without a
 * browser. Pure: no DOM, no fetch, never mutates its arguments.
 *
 * Nothing here validates a name or a content: that is the backend's. This only says which case applies.
 */

import { ApiError } from './api';
import { problemasDeError, type ProblemaTexto, type ResumenTexto, type TextoRespuesta } from './api-textos-guardados';

export { hayNombreNuevo } from './renombrar-definicion';

/**
 * - `nuevo`: never saved; its first save creates version 1.
 * - `editable`: the latest version of an enabled text.
 * - `lectura`: an older version, read-only.
 * - `base`: an older version the analyst chose to build on; editable until saved or discarded.
 * - `deshabilitado`: a disabled text, seen read-only: it admits no new version.
 */
export type ModoTexto = 'nuevo' | 'editable' | 'lectura' | 'base' | 'deshabilitado';

/** `null` is a text that has not been saved yet. */
export function modoInicial(texto: TextoRespuesta | null): ModoTexto {
  if (texto === null) return 'nuevo';
  if (texto.deshabilitado_en !== null) return 'deshabilitado';
  return texto.version.numero === texto.version_vigente ? 'editable' : 'lectura';
}

export const esEditable = (modo: ModoTexto): boolean => modo === 'nuevo' || modo === 'editable' || modo === 'base';

/** «Usar como base»: only an old version in read-only mode changes. */
export const usarComoBase = (modo: ModoTexto): ModoTexto => (modo === 'lectura' ? 'base' : modo);

/** «Descartar»: what was built on an old version goes back to read-only. */
export const descartar = (modo: ModoTexto): ModoTexto => (modo === 'base' ? 'lectura' : modo);

/**
 * What saving does: the version after the latest, even when an old one is on screen (no version is ever
 * modified). `nueva` is `1` for a text that has not been saved.
 */
export function versionAlGuardar(texto: TextoRespuesta | null): { nueva: number; actual: number | null } {
  return texto === null ? { nueva: 1, actual: null } : { nueva: texto.version_vigente + 1, actual: texto.version_vigente };
}

/** Deleting is offered only when no version was ever used; otherwise the reason takes its place. */
export const puedeEliminar = (texto: Pick<TextoRespuesta, 'versiones'>): boolean => !texto.versiones.some((v) => v.usada);

/** Whether the version on screen was used. */
export const versionUsada = (texto: TextoRespuesta): boolean => texto.version.usada;

/**
 * Whether «Guardar» is on. `cambios` is whether the editor differs from what is saved (for a new text: whether a
 * name or a content is written). Building on an old version saves even without changes: copying it forward is
 * the point.
 */
export function puedeGuardar(modo: ModoTexto, cambios: boolean, guardando = false): boolean {
  if (guardando || !esEditable(modo)) return false;
  return modo === 'base' ? true : cambios;
}

/** Same content, whatever the order of the keys. */
export function iguales(a: unknown, b: unknown): boolean {
  const canonico = (valor: unknown): unknown => {
    if (Array.isArray(valor)) return valor.map(canonico);
    if (typeof valor !== 'object' || valor === null) return valor;
    return Object.fromEntries(
      Object.entries(valor as Record<string, unknown>)
        .sort(([x], [y]) => x.localeCompare(y))
        .map(([clave, hijo]) => [clave, canonico(hijo)]),
    );
  };
  return JSON.stringify(canonico(a)) === JSON.stringify(canonico(b));
}

/** The enabled texts and the disabled ones of a listing that asked for both. */
export function repartir(lista: readonly ResumenTexto[]): { habilitados: ResumenTexto[]; deshabilitados: ResumenTexto[] } {
  return {
    habilitados: lista.filter((t) => t.deshabilitado_en === null),
    deshabilitados: lista.filter((t) => t.deshabilitado_en !== null),
  };
}

/**
 * The texts the panel offers: all of them with no filter (the same list), or the ones that pass `filtrar`. The filter is
 * the module's (e.g. «only the texts not linked to a segment») and is asked every time the panel is drawn, so a link that
 * changed since it was mounted is reflected. Nothing is mutated.
 */
export function visibles(lista: readonly ResumenTexto[], filtrar?: (texto: ResumenTexto) => boolean): readonly ResumenTexto[] {
  return filtrar ? lista.filter((texto) => filtrar(texto)) : lista;
}

/** The list with one text renamed; the others are the same objects. */
export function listaConNombre(lista: readonly ResumenTexto[], id: number, nombre: string): ResumenTexto[] {
  return lista.map((t) => (t.id === id ? { ...t, nombre } : t));
}

/** The text that takes the selection when the selected one leaves the list: the next one, else the previous. */
export function vecinoDe(lista: readonly ResumenTexto[], id: number): ResumenTexto | null {
  const indice = lista.findIndex((t) => t.id === id);
  if (indice < 0) return lista[0] ?? null;
  return lista[indice + 1] ?? lista[indice - 1] ?? null;
}

/** Why a request was refused, as far as the screen needs to tell the cases apart. */
export type ErrorDeTexto =
  | { tipo: 'repetido' }
  | { tipo: 'invalido' }
  | { tipo: 'no_existe' }
  | { tipo: 'deshabilitado' }
  | { tipo: 'usado' }
  | { tipo: 'contexto' }
  | { tipo: 'otro'; error: unknown };

/** Reads a refusal by its `codigo`, never by its text. */
export function clasificarError(error: unknown): ErrorDeTexto {
  if (error instanceof ApiError) {
    if (error.status === 409 && error.codigo === 'nombre_repetido') return { tipo: 'repetido' };
    if (error.status === 409 && error.codigo === 'texto_guardado_deshabilitado') return { tipo: 'deshabilitado' };
    if (error.status === 409 && error.codigo === 'texto_guardado_usado') return { tipo: 'usado' };
    if (error.status === 400 && error.codigo === 'contexto_guardado_desconocido') return { tipo: 'contexto' };
    if (error.status === 400) return { tipo: 'invalido' };
    if (error.status === 404) return { tipo: 'no_existe' };
  }
  return { tipo: 'otro', error };
}

/** Where a located problem belongs: the name field or the editor. */
export function problemasPorCampo(error: unknown): { nombre: ProblemaTexto[]; contenido: ProblemaTexto[] } {
  const problemas = problemasDeError(error);
  return {
    nombre: problemas.filter((p) => p.campo === 'nombre'),
    contenido: problemas.filter((p) => p.campo !== 'nombre'),
  };
}
