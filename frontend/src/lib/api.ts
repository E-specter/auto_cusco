/**
 * Typed client for the auto_cusco REST API.
 *
 * Contract: docs/versionado-sabanas.md, section 4.5. The base URL defaults to
 * a same-origin `/api` prefix (proxied in dev by astro.config.mjs, by the
 * reverse proxy in production) so the browser never needs CORS headers.
 */

export const API_BASE = import.meta.env.PUBLIC_API_URL || '/api';

export type EstadoCarga = 'en_cola' | 'procesando' | 'terminada' | 'fallida';
export type Severidad = 'error' | 'advertencia' | 'info';

export interface Version {
  id: number;
  fecha_corte: string;
  version: number;
  estado: EstadoCarga;
  vigente: boolean;
  nombre_archivo: string;
  tamano_bytes: number;
  hoja: string;
  creado_en: string;
  procesado_en: string | null;
  huella_formato: string | null;
  filas_total: number | null;
  filas_ingestadas: number | null;
  incidencias_error: number;
  incidencias_advertencia: number;
  incidencias_info: number;
  motivo_fallo: string | null;
}

export interface CargaCreada {
  id: number;
  fecha_corte: string;
  version: number;
  estado: EstadoCarga;
  versiones_identicas: number[];
  aviso: string | null;
}

export interface Incidencia {
  fila: number | null;
  columna: string | null;
  codigo: string;
  severidad: Severidad;
  detalle: string;
  valor_original: string | null;
}

export interface IncidenciasPagina {
  total: number;
  incidencias: Incidencia[];
}

export interface Health {
  api: boolean;
  database: boolean;
  ok: boolean;
}

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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
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
