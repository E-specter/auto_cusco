/**
 * Where `/cartera?volver=` may send the analyst back to (T-MM-C11, M-F6; docs/mowa-mes-interfaz.md §4.7).
 *
 * `volver` arrives in a link, so it is untrusted input that the page would turn into a navigation: left
 * unchecked it is an open redirect (`//evil.com`, `https://evil.com/mowa-mes/`) or a script
 * (`javascript:…`). Pure on purpose (no `location`, no DOM): the page hands in its origin and these decide.
 */

const PREFIJO = '/mowa-mes/';

/**
 * The path `volver` names, or `null` when it is not one the app may go back to, in which case it is
 * ignored as if it had not come. Accepted only if, once the browser's own URL parser has resolved it
 * against `origen`:
 *  - it is the same origin (so no other host, no other scheme, no `javascript:`);
 *  - its path, ALREADY normalised (`/mowa-mes/../cartera` is `/cartera`), starts with `/mowa-mes/`;
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
  if (!url.pathname.startsWith(PREFIJO) || url.pathname.startsWith('//')) return null;
  return `${url.pathname}${url.search}`;
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

/** The id `?seleccion=` asks for, or `null` if it is missing or not a whole, positive number. */
export function seleccionDeLaUrl(busqueda: string): number | null {
  const valor = new URLSearchParams(busqueda).get('seleccion');
  if (valor === null || !/^[0-9]+$/.test(valor)) return null;
  const id = Number(valor);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

/** The link that sends the analyst to Cartera to edit selection `id`, coming back to `volver` (`/mowa-mes/campana`). */
export function enlaceEditarEnCartera(id: number, volver: string): string {
  return `/cartera?${new URLSearchParams({ seleccion: String(id), volver }).toString()}`;
}
