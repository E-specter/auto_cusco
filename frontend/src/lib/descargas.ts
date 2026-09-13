/**
 * Binary downloads from the API: a generated file whose body is the file
 * itself, whose name travels in `Content-Disposition` and whose summary
 * travels in custom `X-*` headers (see docs/generacion-cargas.md).
 *
 * Errors read exactly like any other call, because the request goes through
 * `requestRespuesta`: a refusal is an `ApiError` carrying the server's
 * `detail`, an unreachable API is a `NetworkError`.
 *
 * The API is same-origin (`/api`), so the browser exposes every header. If it
 * is ever served cross-origin, the backend has to list these headers in
 * `Access-Control-Expose-Headers` or they read as absent.
 */

import { requestRespuesta } from './api';

export interface ArchivoDescargado {
  blob: Blob;
  /** The server's file name, or null when it sent none. */
  nombre: string | null;
  /**
   * Headers that carried the prefix, keyed by what follows it in lower case:
   * with prefix `X-Carga-`, `X-Carga-Generados` arrives as `generados`.
   * Values stay as text; the caller knows which ones are numbers.
   */
  resumen: Record<string, string>;
}

/**
 * The file name from a `Content-Disposition` value. The RFC 5987 form
 * (`filename*=UTF-8''...`) wins over the plain one because it is the only one
 * that can carry accents.
 */
export function nombreDesdeDisposicion(valor: string | null): string | null {
  if (!valor) return null;

  const extendido = valor.match(/filename\*\s*=\s*([^']*)'[^']*'([^;]+)/i);
  if (extendido) {
    try {
      return decodeURIComponent(extendido[2].trim());
    } catch {
      /* A malformed escape falls through to the plain form. */
    }
  }

  const plano = valor.match(/filename\s*=\s*(?:"([^"]*)"|([^;]+))/i);
  const nombre = (plano?.[1] ?? plano?.[2])?.trim();
  return nombre ? nombre : null;
}

/** Every header starting with `prefijo`, keyed by the rest of its name. */
export function cabecerasConPrefijo(cabeceras: Headers, prefijo: string): Record<string, string> {
  const buscado = prefijo.toLowerCase();
  const resumen: Record<string, string> = {};
  cabeceras.forEach((valor, nombre) => {
    const clave = nombre.toLowerCase();
    if (clave.startsWith(buscado) && clave.length > buscado.length) {
      resumen[clave.slice(buscado.length)] = valor;
    }
  });
  return resumen;
}

/** Ask the API for a file and read its body, name and prefixed summary. */
export async function descargarArchivo(
  path: string,
  init: RequestInit = {},
  prefijoResumen = 'X-',
): Promise<ArchivoDescargado> {
  const response = await requestRespuesta(path, init);
  return {
    blob: await response.blob(),
    nombre: nombreDesdeDisposicion(response.headers.get('content-disposition')),
    resumen: cabecerasConPrefijo(response.headers, prefijoResumen),
  };
}

/**
 * Hand a downloaded file to the browser's save flow. The object URL is
 * released on the next task, once the click has started the download.
 */
export function guardarArchivo(blob: Blob, nombre: string): void {
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = nombre;
  enlace.hidden = true;
  document.body.append(enlace);
  enlace.click();
  enlace.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
