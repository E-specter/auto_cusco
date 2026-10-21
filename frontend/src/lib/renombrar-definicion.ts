/**
 * Renaming a saved definition (T-MTE-F7, RF-56; docs/motor-texto-enriquecido-interfaz.md §10.1).
 *
 * The name belongs to the definition, not to a version: renaming creates no version and does not
 * go through «Guardar». Pure on purpose (no DOM, no fetch): the page reads these and draws.
 *
 * What the screen decides on its own is one thing: whether there is anything to do. Everything else
 * is the backend's: an empty or too long name, a name already taken. The screen shows the reason
 * where the field is, with texts of its own for the case (the backend's `detail` is Spanish prose
 * that no dictionary translates).
 */

import { ApiError } from './api';
import { problemasDeError, type DefinicionGuardadaRespuesta, type ResumenDefinicion } from './api-definiciones';

/**
 * Whether «Renombrar» has something to do. The name is compared exactly after trimming the edge
 * spaces (which the backend trims too): ignoring case would block «SMS preventivo» → «Sms preventivo»,
 * a change the backend accepts and keeps.
 */
export function hayNombreNuevo(actual: string, escrito: string): boolean {
  return escrito.trim() !== actual;
}

/** Why a rename was refused, as far as the screen needs to tell the cases apart. */
export type ErrorDeRenombrar =
  | { tipo: 'repetido' }
  | { tipo: 'invalido' }
  | { tipo: 'no_existe' }
  | { tipo: 'otro'; error: unknown };

/**
 * Reads a refusal of `PATCH /definiciones-columnas/{id}`: 409 `nombre_repetido`; 400 whose located
 * problem is the field `nombre` (empty or too long); 404 (deleted by someone else, or never there).
 * Anything else, a failed network included, is `otro` and the screen says it in general words.
 */
export function clasificarErrorDeRenombrar(error: unknown): ErrorDeRenombrar {
  if (error instanceof ApiError) {
    if (error.status === 409 && error.codigo === 'nombre_repetido') return { tipo: 'repetido' };
    if (error.status === 400 && problemasDeError(error).some((p) => p.campo === 'nombre')) return { tipo: 'invalido' };
    if (error.status === 404) return { tipo: 'no_existe' };
  }
  return { tipo: 'otro', error };
}

/**
 * What the screen already shows of a definition, with the new name. The response of the rename carries
 * the *latest* version, which is not necessarily the one on screen (an old one may be open, read-only):
 * only the name and the date of the change are taken from it, never its content or its versions.
 */
export function conNombreRenombrado(
  mostrada: DefinicionGuardadaRespuesta,
  renombrada: Pick<DefinicionGuardadaRespuesta, 'nombre' | 'actualizado_en'>,
): DefinicionGuardadaRespuesta {
  return { ...mostrada, nombre: renombrada.nombre, actualizado_en: renombrada.actualizado_en };
}

/** The list of saved definitions with one renamed; the others are the same objects. */
export function listaConNombre(
  lista: readonly ResumenDefinicion[],
  id: number,
  renombrada: Pick<DefinicionGuardadaRespuesta, 'nombre' | 'actualizado_en'>,
): ResumenDefinicion[] {
  return lista.map((d) => (d.id === id ? { ...d, nombre: renombrada.nombre, actualizado_en: renombrada.actualizado_en } : d));
}
