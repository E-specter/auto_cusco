/**
 * Calls for the load files that leave for a platform (`/archivos-carga`, docs/generacion-cargas.md).
 *
 * Not to be mixed up with `/cargas`, which are the daily sheets that come in. Shapes come from the
 * generated contract only; the transport, errors included, is the shared `request` of `api.ts`, and
 * the download goes through `descargarArchivo`, so a refusal is an `ApiError` carrying the server's
 * reason and an unreachable API is a `NetworkError`.
 *
 * Both POSTs take the same body (`PeticionGeneracion`): the preview shows what the download will
 * produce. The summary of a download travels in `X-Carga-*` headers because the body is the file.
 */

import { request } from './api';
import { descargarArchivo, type ArchivoDescargado } from './descargas';
import type { FormatoDisponible, PeticionGeneracion, PrevisualizacionCarga } from './generar-carga';

const RUTA = '/archivos-carga';

/** Prefix of the headers that carry the summary of a generated file. */
export const PREFIJO_RESUMEN_CARGA = 'X-Carga-';

function conJson(cuerpo: PeticionGeneracion, signal?: AbortSignal): RequestInit {
  return {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(cuerpo),
    signal,
  };
}

/** The formats that can be generated and what each admits: extension and options with their limits. */
export function listarFormatos(signal?: AbortSignal): Promise<FormatoDisponible[]> {
  return request<FormatoDisponible[]>(`${RUTA}/formatos`, { signal });
}

/** The first rows, the totals and what is left out, without writing the file or marking anything used. */
export function previsualizarCarga(
  peticion: PeticionGeneracion,
  signal?: AbortSignal,
): Promise<PrevisualizacionCarga> {
  return request<PrevisualizacionCarga>(`${RUTA}/previsualizacion`, conJson(peticion, signal));
}

/**
 * The whole file. The server keeps working after the connection is cut (it runs to the end), so
 * aborting the signal only frees the screen; the saved version may be marked used all the same.
 */
export function generarCarga(peticion: PeticionGeneracion, signal?: AbortSignal): Promise<ArchivoDescargado> {
  return descargarArchivo(RUTA, conJson(peticion, signal), PREFIJO_RESUMEN_CARGA);
}
