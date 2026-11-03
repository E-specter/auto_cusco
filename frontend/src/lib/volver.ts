/**
 * Where a tool (`/cartera`, `/columnas`, `/supervisores`, `/calendario`) may send the analyst back to with
 * `?volver=`: the screens of a channel (T-MM-C11, M-F6; docs/mowa-mes-interfaz.md §4.7; T-HI-F3, RF-74,
 * docs/whatsmkt-interfaz.md §2).
 *
 * `volver` arrives in a link, so it is untrusted input that the page would turn into a navigation: left
 * unchecked it is an open redirect (`//evil.com`, `https://evil.com/whatsmkt/`) or a script
 * (`javascript:…`). Pure on purpose (no `location`, no DOM): the page hands in its origin and these decide.
 */

/** The channels a tool may go back to. A new channel is one more prefix here, and nothing else. */
const PREFIJOS = ['/mowa-mes/', '/whatsmkt/'] as const;

/**
 * The path `volver` names, or `null` when it is not one the app may go back to, in which case it is
 * ignored as if it had not come. Accepted only if, once the browser's own URL parser has resolved it
 * against `origen`:
 *  - it is the same origin (so no other host, no other scheme, no `javascript:`);
 *  - its path, ALREADY normalised (`/whatsmkt/../cartera` is `/cartera`), starts with `/mowa-mes/` or `/whatsmkt/`;
 *  - the text does not start with `//` (a protocol-relative address) in the first place.
 * What comes back is that normalised path with its query, never the text that arrived.
 */
export function volverValido(volver: string | null | undefined, origen: string): string | null {
  if (typeof volver !== 'string' || volver === '' || volver.startsWith('//')) return null;
  let url: URL;
  try {
    url = new URL(volver, origen);
  } catch {
    return null;
  }
  if (url.origin !== new URL(origen).origin) return null;
  if (!PREFIJOS.some((prefijo) => url.pathname.startsWith(prefijo)) || url.pathname.startsWith('//')) return null;
  return `${url.pathname}${url.search}`;
}

/**
 * The channel a `volver` that `volverValido` accepted belongs to: the screen says «Volver a WhatsMKT» or «Volver a MOWA MES» from it.
 * It reads the prefix and nothing else, so anything that is not a path of a channel (what did not pass `volverValido`, an empty text)
 * is `null`: it never guesses.
 */
export function origenDeVolver(volver: string): 'mowa-mes' | 'whatsmkt' | null {
  if (volver.startsWith('/whatsmkt/')) return 'whatsmkt';
  if (volver.startsWith('/mowa-mes/')) return 'mowa-mes';
  return null;
}

/** `destino` with `seleccion=<id>`: where the campaign picks the selection that was just saved. */
export function destinoConSeleccion(destino: string, id: number): string {
  const url = new URL(destino, 'http://destino.invalid');
  url.searchParams.set('seleccion', String(id));
  return `${url.pathname}${url.search}`;
}

/** `destino` without `seleccion`: going back without saving brings back nothing to load. */
export function destinoSinSeleccion(destino: string): string {
  const url = new URL(destino, 'http://destino.invalid');
  url.searchParams.delete('seleccion');
  return `${url.pathname}${url.search}`;
}

/** The whole, positive number a query parameter holds, or `null` if it is missing or anything else. */
function enteroPositivo(busqueda: string, nombre: string): number | null {
  const valor = new URLSearchParams(busqueda).get(nombre);
  if (valor === null || !/^[0-9]+$/.test(valor)) return null;
  const id = Number(valor);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

/** The id `?seleccion=` asks for, or `null` if it is missing or not a whole, positive number. */
export const seleccionDeLaUrl = (busqueda: string): number | null => enteroPositivo(busqueda, 'seleccion');

/**
 * The id `?definicion=` asks Columnas de carga to open (a saved definition, in its latest version), or `null` if it is
 * missing or not a whole, positive number.
 */
export const definicionPedidaDeLaUrl = (busqueda: string): number | null => enteroPositivo(busqueda, 'definicion');

/**
 * What a channel finds in its own URL when Columnas de carga sends it back after saving: `{ id, version }` from
 * `?definicion=<id>&version=<n>`, or `null` if either is missing or not a whole, positive number. The screen of origin
 * reads it once and then takes both out of the URL (`history.replaceState`).
 */
export function definicionDeLaUrl(busqueda: string): { id: number; version: number } | null {
  const id = enteroPositivo(busqueda, 'definicion');
  const version = enteroPositivo(busqueda, 'version');
  return id === null || version === null ? null : { id, version };
}

/**
 * The platform `?plataforma=` asks to create a definition for, or `null` when it is missing or no registered platform
 * has that key: an unknown key is ignored, as if it had not come (RF-72).
 */
export function plataformaDeLaUrl(busqueda: string, plataformas: ReadonlyArray<{ clave: string }>): string | null {
  const clave = new URLSearchParams(busqueda).get('plataforma');
  return clave !== null && plataformas.some((p) => p.clave === clave) ? clave : null;
}

/** `destino` with `definicion=<id>&version=<n>`: where a channel picks the definition that was just saved, and its version. */
export function destinoConDefinicion(destino: string, id: number, version: number): string {
  const url = new URL(destino, 'http://destino.invalid');
  url.searchParams.set('definicion', String(id));
  url.searchParams.set('version', String(version));
  return `${url.pathname}${url.search}`;
}

/** `destino` without `definicion` and `version`: going back without saving brings back nothing to pick. */
export function destinoSinDefinicion(destino: string): string {
  const url = new URL(destino, 'http://destino.invalid');
  url.searchParams.delete('definicion');
  url.searchParams.delete('version');
  return `${url.pathname}${url.search}`;
}

/** The link that sends the analyst to Cartera to edit selection `id`, coming back to `volver` (`/mowa-mes/campana`). */
export function enlaceEditarEnCartera(id: number, volver: string): string {
  return `/cartera?${new URLSearchParams({ seleccion: String(id), volver }).toString()}`;
}

/**
 * The link that sends the analyst to Columnas de carga to edit the saved definition `id`, coming back to `volver`
 * (`/whatsmkt/campana`). Final form, for the channels to use as it is:
 *
 *     /columnas?definicion=<id>&volver=<ruta codificada>
 *
 * Saving there goes back to `volver` with `definicion=<id>&version=<n>` added (`destinoConDefinicion`); the link of the
 * notice that says «Volver … sin guardar» goes back without them (`destinoSinDefinicion`).
 */
export function enlaceEditarDefinicion(id: number, volver: string): string {
  return `/columnas?${new URLSearchParams({ definicion: String(id), volver }).toString()}`;
}

/**
 * The link that sends the analyst to Columnas de carga to create a definition for platform `plataforma` (the `clave` of
 * `GET /definiciones-columnas/plataformas`, e.g. `whatsmkt`), coming back to `volver`. Final form:
 *
 *     /columnas?plataforma=<clave>&volver=<ruta codificada>
 *
 * The platform comes chosen and cannot be changed there; saving goes back to `volver` as for `enlaceEditarDefinicion`.
 */
export function enlaceCrearDefinicion(plataforma: string, volver: string): string {
  return `/columnas?${new URLSearchParams({ plataforma, volver }).toString()}`;
}
