/**
 * Administering speech versions (T-MM-C11, M-F2; RF-MM-28 to RF-MM-30; docs/mowa-mes-interfaz.md §4.5):
 * rename, disable, enable and delete for good. Pure on purpose (no DOM, no fetch): the pages read these
 * and draw. What the screen never works out itself: whether a version can be deleted, and why not. The
 * API says it (`eliminable`, `motivo_no_eliminable`), so no refusal is discovered with a 409.
 */

import { ApiError } from './api';
import type { VersionSpeech } from './api-mowa-mes';

/** The longest name the API accepts (a longer or blank one is its 400). */
export const LARGO_NOMBRE_SPEECH = 120;

export const estaHabilitada = (version: Pick<VersionSpeech, 'deshabilitada_en'>): boolean =>
  version.deshabilitada_en === null;

export const habilitadas = (versiones: readonly VersionSpeech[]): VersionSpeech[] =>
  versiones.filter(estaHabilitada);

export const deshabilitadas = (versiones: readonly VersionSpeech[]): VersionSpeech[] =>
  versiones.filter((version) => !estaHabilitada(version));

/**
 * What the configuration's version selector lists: the enabled versions, in the API's order, plus the
 * disabled one the analyst has open to read (so the selector still says what the editor shows).
 */
export function versionesDelSelector(versiones: readonly VersionSpeech[], abierta: number | null): VersionSpeech[] {
  return versiones.filter((version) => estaHabilitada(version) || version.id === abierta);
}

/** What goes where «Eliminar definitivamente» would: the button, the reason it is not there, or nothing. */
export type AccionDeEliminar =
  | { tipo: 'boton' }
  | { tipo: 'motivo'; clave: 'speech_original' | 'speech_usado' }
  | { tipo: 'nada' };

/**
 * Only an `eliminable` version has the button. The others say why, in the API's own words
 * (`motivo_no_eliminable`: the Speech original, or one campaigns used). A disabled version with no
 * reason and not deletable cannot happen; it shows neither, rather than a button that would answer 409.
 */
export function accionDeEliminar(
  version: Pick<VersionSpeech, 'eliminable' | 'motivo_no_eliminable'>,
): AccionDeEliminar {
  if (version.eliminable) return { tipo: 'boton' };
  if (version.motivo_no_eliminable === 'original') return { tipo: 'motivo', clave: 'speech_original' };
  if (version.motivo_no_eliminable === 'usada') return { tipo: 'motivo', clave: 'speech_usado' };
  return { tipo: 'nada' };
}

/** An option of the campaign's speech selector: `''` is the Speech original (the API's default). */
export interface OpcionDeCampana {
  valor: string;
  version: VersionSpeech;
}

/**
 * The versions a campaign can pick: only the enabled ones, the Speech original first (as `''`). If the
 * original is disabled it is not offered, and a campaign sent without a choice would be refused.
 */
export function opcionesDeCampana(versiones: readonly VersionSpeech[]): OpcionDeCampana[] {
  const todas = habilitadas(versiones).map((version) => ({ valor: version.original ? '' : String(version.id), version }));
  return [...todas.filter((o) => o.version.original), ...todas.filter((o) => !o.version.original)];
}

/**
 * The option that stays chosen: the one the analyst had while it is still offered; otherwise the first
 * enabled one. `''` with nothing to choose.
 */
export function preseleccionDeCampana(opciones: readonly OpcionDeCampana[], previa: string): string {
  return opciones.some((o) => o.valor === previa) ? previa : (opciones[0]?.valor ?? '');
}

/** Why a rename was refused, as far as the screen needs to tell the cases apart. */
export type ErrorDeRenombrarSpeech = { tipo: 'repetido' } | { tipo: 'invalido' } | { tipo: 'otro'; error: unknown };

/**
 * Reads a refusal of `PATCH /mowa-mes/speech/{id}` with a name: 409 is the name already taken (it carries no
 * `codigo`; the PATCH has no other 409), 400 is a blank or too long one. Anything else, a 404 or a failed
 * network included, is `otro` and the screen says it in general words.
 */
export function clasificarErrorDeRenombrarSpeech(error: unknown): ErrorDeRenombrarSpeech {
  if (error instanceof ApiError) {
    if (error.status === 409) return { tipo: 'repetido' };
    if (error.status === 400) return { tipo: 'invalido' };
  }
  return { tipo: 'otro', error };
}

/** The list with one version replaced by what the API answered; the others are the same objects. */
export function conVersion(versiones: readonly VersionSpeech[], nueva: VersionSpeech): VersionSpeech[] {
  return versiones.map((version) => (version.id === nueva.id ? nueva : version));
}

/** The list without a version that was deleted. */
export function sinVersion(versiones: readonly VersionSpeech[], id: number): VersionSpeech[] {
  return versiones.filter((version) => version.id !== id);
}
