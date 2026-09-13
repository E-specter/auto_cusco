/**
 * Typed client for the auto_cusco REST API.
 *
 * The base URL defaults to a same-origin `/api` prefix (proxied in dev by
 * astro.config.mjs, by the reverse proxy in production) so the browser never
 * needs CORS headers.
 *
 * Every response shape comes from the backend's contract, never from here:
 * `contrato-api.d.ts` is generated from contratos/openapi.json by
 * `npm run contrato`, and CI fails if it drifts. See docs/contrato-api.md.
 */

import type { components } from './contrato-api';

export const API_BASE = import.meta.env.PUBLIC_API_URL || '/api';

type Esquemas = components['schemas'];

export type EstadoCarga = Esquemas['EstadoCarga'];
export type Severidad = Esquemas['Severidad'];
export type Version = Esquemas['VersionRespuesta'];
export type CargaCreada = Esquemas['CargaCreadaRespuesta'];
export type Incidencia = Esquemas['IncidenciaRespuesta'];
export type IncidenciasPagina = Esquemas['IncidenciasRespuesta'];
export type Health = Esquemas['HealthRespuesta'];

/** An API response that arrived but said no. `detail` is the server's reason. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail || `HTTP ${status}`);
    this.name = 'ApiError';
  }
}

/** The API could not be reached at all — a different problem to the user. */
export class NetworkError extends Error {
  constructor() {
    super('network');
    this.name = 'NetworkError';
  }
}

/**
 * Reach the API and hand back a response that said yes, whatever its body.
 * Binary downloads start here too (see `descargas.ts`), so every caller shares
 * one reading of "the server said no" versus "the server never answered".
 *
 * A request the caller aborted rethrows its `AbortError` untouched: a newer
 * request replacing it is not the API being down.
 */
export async function requestRespuesta(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new NetworkError();
  }

  if (!response.ok) {
    let detail = '';
    try {
      const body = await response.json();
      detail = typeof body?.detail === 'string' ? body.detail : '';
    } catch {
      /* A non-JSON error body leaves `detail` empty; the status still speaks. */
    }
    throw new ApiError(response.status, detail);
  }

  return response;
}

/** A JSON call. Feature clients (`api-<module>.ts`) build on this one. */
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await requestRespuesta(path, init);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function health(): Promise<Health> {
  return request<Health>('/health');
}

export function listarVersiones(params: {
  fechaCorte?: string;
  limite?: number;
  desplazamiento?: number;
} = {}): Promise<Version[]> {
  const query = new URLSearchParams();
  if (params.fechaCorte) query.set('fecha_corte', params.fechaCorte);
  query.set('limite', String(params.limite ?? 200));
  query.set('desplazamiento', String(params.desplazamiento ?? 0));
  return request<Version[]>(`/cargas?${query}`);
}

export function obtenerVersion(id: number): Promise<Version> {
  return request<Version>(`/cargas/${id}`);
}

export function listarIncidencias(
  id: number,
  params: { severidad?: Severidad; limite?: number; desplazamiento?: number } = {},
): Promise<IncidenciasPagina> {
  const query = new URLSearchParams();
  if (params.severidad) query.set('severidad', params.severidad);
  query.set('limite', String(params.limite ?? 50));
  query.set('desplazamiento', String(params.desplazamiento ?? 0));
  return request<IncidenciasPagina>(`/cargas/${id}/incidencias?${query}`);
}

export function subirSabana(input: {
  archivo: File;
  fechaCorte: string;
  hoja?: string;
}): Promise<CargaCreada> {
  const body = new FormData();
  body.set('archivo', input.archivo);
  body.set('fecha_corte', input.fechaCorte);
  if (input.hoja) body.set('hoja', input.hoja);
  return request<CargaCreada>('/cargas', { method: 'POST', body });
}

export function asignarVigente(id: number): Promise<Version> {
  return request<Version>(`/cargas/${id}/vigente`, { method: 'POST' });
}

export function eliminarVersion(
  id: number,
  dejarFechaSinVigente: boolean,
): Promise<void> {
  const query = new URLSearchParams({
    dejar_fecha_sin_vigente: String(dejarFechaSinVigente),
  });
  return request<void>(`/cargas/${id}?${query}`, { method: 'DELETE' });
}
