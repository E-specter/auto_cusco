/**
 * Calls for the saved texts of a context (RF-69; `docs/textos-guardados.md`).
 *
 * Shapes come from the generated contract only (`contrato-api.d.ts`); the transport, errors included, is the
 * shared `request` of `api.ts`. As with the column definitions, no version is ever modified: a save is a POST of
 * the version after the latest, a rename creates none, and a text that was used can only be disabled.
 */

import { ApiError, conJson, request } from './api';
import type { components } from './contrato-api';

type Esquemas = components['schemas'];

export type ContextoGuardado = Esquemas['ContextoGuardadoRespuesta'];
export type ResumenTexto = Esquemas['ResumenTextoRespuesta'];
export type TextoRespuesta = Esquemas['TextoRespuesta'];
export type VersionTextoResumen = Esquemas['VersionTextoResumenRespuesta'];
export type ProblemaTexto = Esquemas['ProblemaTextoRespuesta'];

/** What a context stores in a version: an object whose shape the context decides (`{expresion}`, `{texto}`). */
export type ContenidoTexto = { [clave: string]: unknown };

const RUTA = '/textos-guardados';

/** The contexts a module registered, with the shape of their content (`expresion` or `texto_plano`). */
export function listarContextos(signal?: AbortSignal): Promise<ContextoGuardado[]> {
  return request<ContextoGuardado[]>(`${RUTA}/contextos`, { signal });
}

/** The texts of a context by name, with their latest version. Disabled ones only when asked for. */
export function listarTextos(contexto: string, deshabilitados = false, signal?: AbortSignal): Promise<ResumenTexto[]> {
  const consulta = new URLSearchParams({ contexto, ...(deshabilitados ? { deshabilitados: 'true' } : {}) });
  return request<ResumenTexto[]>(`${RUTA}?${consulta}`, { signal });
}

/** A text with its latest version, or with `version` when it is given; also when it is disabled. */
export function obtenerTexto(id: number, version?: number, signal?: AbortSignal): Promise<TextoRespuesta> {
  const consulta = version === undefined ? '' : `?${new URLSearchParams({ version: String(version) })}`;
  return request<TextoRespuesta>(`${RUTA}/${id}${consulta}`, { signal });
}

/** A text that has never been saved: its first version. */
export function crearTexto(contexto: string, nombre: string, contenido: ContenidoTexto): Promise<TextoRespuesta> {
  return request<TextoRespuesta>(RUTA, conJson('POST', { contexto, nombre, contenido }));
}

/** The version after the latest. A disabled text answers 409 `texto_guardado_deshabilitado`. */
export function agregarVersion(id: number, contenido: ContenidoTexto): Promise<TextoRespuesta> {
  return request<TextoRespuesta>(`${RUTA}/${id}/versiones`, conJson('POST', { contenido }));
}

/** RF-56: only the name; no version is created. 409 `nombre_repetido`. */
export function renombrarTexto(id: number, nombre: string): Promise<TextoRespuesta> {
  return request<TextoRespuesta>(`${RUTA}/${id}`, conJson('PATCH', { nombre }));
}

/** Stops offering it for what is new. Idempotent. */
export function deshabilitarTexto(id: number): Promise<TextoRespuesta> {
  return request<TextoRespuesta>(`${RUTA}/${id}/deshabilitar`, { method: 'POST' });
}

/** Offers it again and admits versions again. Idempotent. */
export function habilitarTexto(id: number): Promise<TextoRespuesta> {
  return request<TextoRespuesta>(`${RUTA}/${id}/habilitar`, { method: 'POST' });
}

/** Deletes it with its versions. 409 `texto_guardado_usado` when any of them was used. */
export function eliminarTexto(id: number): Promise<void> {
  return request<void>(`${RUTA}/${id}`, { method: 'DELETE' });
}

function esProblema(valor: unknown): valor is ProblemaTexto {
  if (typeof valor !== 'object' || valor === null) return false;
  const candidato = valor as Record<string, unknown>;
  return typeof candidato.codigo === 'string' && typeof candidato.detalle === 'string';
}

/**
 * The located problems of a refused save (400 `texto_guardado_invalido`): each says whether it is about the
 * `nombre` or the `contenido`. Anything that is not such a list reads as none.
 */
export function problemasDeError(error: unknown): ProblemaTexto[] {
  if (!(error instanceof ApiError)) return [];
  const problemas = error.cuerpo?.problemas;
  return Array.isArray(problemas) ? problemas.filter(esProblema) : [];
}
