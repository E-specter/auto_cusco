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

export type Campo = Esquemas['CampoRespuesta'];
/** Every queryable field, keyed by name (`GET /cartera/campos`). */
export type Campos = Record<string, Campo>;
export type Resumen = Esquemas['ResumenRespuesta'];
export type Bloque = Esquemas['BloqueRespuesta'];
export type Metricas = Esquemas['MetricasRespuesta'];
export type Segmentacion = Esquemas['SegmentacionRespuesta'];
export type Grupo = Esquemas['GrupoRespuesta'];
export type PaginaCartera = Esquemas['PaginaRespuesta'];
export type SeleccionGuardada = Esquemas['SeleccionRespuesta'];
export type SeleccionEntrada = Esquemas['SeleccionEntrada'];
export type Revision = Esquemas['RevisionRespuesta'];
export type Problema = Esquemas['ProblemaRespuesta'];

/** Filters, order, top n and indicators, already in the API's text syntax. */
export interface ConsultaCartera {
  filtros: string[];
  orden: string | null;
  cantidad?: number | null;
  indicadores?: string[];
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

// ---- Portfolio (docs/consulta-cartera.md) ---------------------------------------

export function listarCampos(): Promise<Campos> {
  return request<Campos>('/cartera/campos');
}

/** Repeated parameters, the way FastAPI reads `list[str]` from a query. */
function parametrosConsulta(fechaCorte: string, consulta: ConsultaCartera): URLSearchParams {
  const query = new URLSearchParams({ fecha_corte: fechaCorte });
  consulta.filtros.forEach((filtro) => query.append('filtro', filtro));
  if (consulta.orden) query.set('orden', consulta.orden);
  return query;
}

/**
 * The universe that meets the filters and its first n, side by side, in one
 * call (RF-28). A 404 means the date has no current version: there is no
 * portfolio to read, which is not the same as an empty one.
 */
export function resumirCartera(
  fechaCorte: string,
  consulta: ConsultaCartera,
  segmento: string | null,
  signal?: AbortSignal,
): Promise<Resumen> {
  const query = parametrosConsulta(fechaCorte, consulta);
  if (consulta.cantidad) query.set('cantidad', String(consulta.cantidad));
  (consulta.indicadores ?? []).forEach((indicador) => query.append('indicador', indicador));
  if (segmento) query.set('segmento', segmento);
  return request<Resumen>(`/cartera/resumen?${query}`, { signal });
}

export function consultarCartera(
  fechaCorte: string,
  consulta: ConsultaCartera,
  pagina: { limite: number; desplazamiento: number },
  signal?: AbortSignal,
): Promise<PaginaCartera> {
  const query = parametrosConsulta(fechaCorte, consulta);
  query.set('limite', String(pagina.limite));
  query.set('desplazamiento', String(pagina.desplazamiento));
  return request<PaginaCartera>(`/cartera?${query}`, { signal });
}

// ---- Saved selections (docs/selecciones-guardadas.md) ---------------------------

const json = (method: string, cuerpo: unknown, signal?: AbortSignal): RequestInit => ({
  method,
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(cuerpo),
  signal,
});

export function listarSelecciones(): Promise<SeleccionGuardada[]> {
  return request<SeleccionGuardada[]>('/selecciones');
}

/** 201 with the saved selection; 400 if a part does not apply, 409 on a taken name. */
export function crearSeleccion(entrada: SeleccionEntrada): Promise<SeleccionGuardada> {
  return request<SeleccionGuardada>('/selecciones', json('POST', entrada));
}

export function actualizarSeleccion(
  id: number,
  entrada: SeleccionEntrada,
): Promise<SeleccionGuardada> {
  return request<SeleccionGuardada>(`/selecciones/${id}`, json('PUT', entrada));
}

/** Which parts would not apply, without saving anything. */
export function revisarSeleccion(entrada: SeleccionEntrada, signal?: AbortSignal): Promise<Revision> {
  return request<Revision>('/selecciones/revision', json('POST', entrada, signal));
}

export function eliminarSeleccion(id: number): Promise<void> {
  return request<void>(`/selecciones/${id}`, { method: 'DELETE' });
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
