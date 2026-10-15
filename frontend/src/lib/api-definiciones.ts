/**
 * Calls for the saved column definitions (RF-46, RF-51; `docs/motor-texto-enriquecido.md` §22).
 *
 * Shapes come from the generated contract only (`contrato-api.d.ts`); the transport, errors
 * included, is the shared `request` of `api.ts`. No version is ever modified, so there is no PUT:
 * a new definition is a POST, and every later save is a POST of a new version.
 */

import { ApiError, request } from './api';
import { aDefinicion, type Borrador } from './constructor-columnas';
import type { components } from './contrato-api';

type Esquemas = components['schemas'];

export type ResumenDefinicion = Esquemas['ResumenDefinicionRespuesta'];
export type DefinicionGuardadaRespuesta = Esquemas['DefinicionRespuesta'];
export type VersionDefinicionResumen = Esquemas['VersionDefinicionResumenRespuesta'];
export type DefinicionColumnasEntrada = Esquemas['DefinicionColumnasEntrada'];
export type ProblemaDefinicion = Esquemas['ProblemaTextoRespuesta'];

const RUTA = '/definiciones-columnas';

function conJson(method: string, cuerpo: unknown, signal?: AbortSignal): RequestInit {
  return {
    method,
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(cuerpo),
    signal,
  };
}

/** Every saved definition with its latest version, newest activity first as the API sorts them. */
export function listarDefiniciones(signal?: AbortSignal): Promise<ResumenDefinicion[]> {
  return request<ResumenDefinicion[]>(RUTA, { signal });
}

/** A definition with its latest version, or with `version` when it is given. */
export function obtenerDefinicion(
  id: number,
  version?: number,
  signal?: AbortSignal,
): Promise<DefinicionGuardadaRespuesta> {
  const consulta = version === undefined ? '' : `?${new URLSearchParams({ version: String(version) })}`;
  return request<DefinicionGuardadaRespuesta>(`${RUTA}/${id}${consulta}`, { signal });
}

/** A definition that has never been saved: its first version. The name is required here. */
export function crearDefinicion(entrada: DefinicionColumnasEntrada): Promise<DefinicionGuardadaRespuesta> {
  return request<DefinicionGuardadaRespuesta>(RUTA, conJson('POST', entrada));
}

/** A change to a saved definition: the version after the latest. */
export function guardarVersion(
  id: number,
  entrada: DefinicionColumnasEntrada,
): Promise<DefinicionGuardadaRespuesta> {
  return request<DefinicionGuardadaRespuesta>(`${RUTA}/${id}/versiones`, conJson('POST', entrada));
}

/**
 * Saves a draft. With no saved definition (`id` is `null`) it creates one and sends the name; with
 * one it saves a new version and sends **no name**: it cannot change between versions, and the
 * backend would answer with a problem on `nombre` if it differed.
 */
export function guardarBorrador(borrador: Borrador, id: number | null): Promise<DefinicionGuardadaRespuesta> {
  const definicion = aDefinicion(borrador);
  if (id === null) return crearDefinicion(definicion);
  const { nombre: _nombre, ...sinNombre } = definicion;
  return guardarVersion(id, sinNombre);
}

function esProblema(valor: unknown): valor is ProblemaDefinicion {
  if (typeof valor !== 'object' || valor === null) return false;
  const candidato = valor as Record<string, unknown>;
  return typeof candidato.codigo === 'string' && typeof candidato.detalle === 'string';
}

/**
 * The located problems of a refused save (400 `definicion_invalida`): each says which column,
 * which segment and which field it is about. Anything that is not such a list reads as none:
 * the screen falls back to `detail`.
 */
export function problemasDeError(error: unknown): ProblemaDefinicion[] {
  if (!(error instanceof ApiError)) return [];
  const problemas = error.cuerpo?.problemas;
  return Array.isArray(problemas) ? problemas.filter(esProblema) : [];
}
