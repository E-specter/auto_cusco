/**
 * The header mapper's validation (`POST /mapeador/borradores/{id}/validacion`),
 * the `validar` that `montarMapeador` receives. A mapping with problems is a
 * normal answer: only an unreachable API, or a draft that expired (404), rejects.
 */

import { request } from './api';
import type { components } from './contrato-api';

type Esquemas = components['schemas'];

export function validarMapeo(
  borradorId: number,
  asignaciones: Esquemas['AsignacionEntrada'][],
  signal?: AbortSignal,
): Promise<Esquemas['ProblemaMapeoRespuesta'][]> {
  const cuerpo: Esquemas['ValidacionEntrada'] = { asignaciones };
  return request<Esquemas['ValidacionMapeoRespuesta']>(`/mapeador/borradores/${borradorId}/validacion`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(cuerpo),
    signal,
  }).then((respuesta) => respuesta.problemas);
}

// ---- The upload flow in two steps (T-MAP-F2) -----------------------------------------------

/** The catalogue of the daily sheet: the key of its remembered mappings (docs/mapeador-encabezados.md §3.1). */
export const CATALOGO_SABANA = 'sabana_vencida';

export type CatalogoMapeador = Esquemas['CatalogoMapeadorRespuesta'];
export type AnalisisBorrador = Esquemas['AnalisisRespuesta'];
export type OpcionesLectura = Esquemas['OpcionesLecturaEntrada'];

const conJson = (method: string, cuerpo: unknown, signal?: AbortSignal): RequestInit => ({
  method,
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(cuerpo),
  signal,
});

/** The fields of the catalogue (the dropdown), the encodings and the separators a CSV accepts. */
export function obtenerCatalogoMapeador(signal?: AbortSignal): Promise<CatalogoMapeador> {
  return request<CatalogoMapeador>(`/mapeador/catalogos/${CATALOGO_SABANA}`, { signal });
}

/**
 * Step 1: the file is read and analysed once and kept as a draft (24 hours). An option left out is
 * detected; the analysis says which ones were.
 */
export function crearBorrador(archivo: File, opciones: OpcionesLectura = {}): Promise<AnalisisBorrador> {
  const cuerpo = new FormData();
  cuerpo.set('archivo', archivo);
  for (const [clave, valor] of Object.entries(opciones)) if (valor) cuerpo.set(clave, valor);
  return request<AnalisisBorrador>(`/mapeador/${CATALOGO_SABANA}/borradores`, { method: 'POST', body: cuerpo });
}

/** The same draft read with other options, without uploading the file again. */
export function reanalizarBorrador(id: number, opciones: OpcionesLectura): Promise<AnalisisBorrador> {
  return request<AnalisisBorrador>(`/mapeador/borradores/${id}/analisis`, conJson('POST', opciones));
}

/** Cancel: 204, also for a draft that expired. */
export function descartarBorrador(id: number): Promise<void> {
  return request<void>(`/mapeador/borradores/${id}`, { method: 'DELETE' });
}

/**
 * Step 2: confirm. The assignments are the component's, as they are. 202 like `POST /cargas`;
 * 422 `mapeo_con_problemas` with the problems; 404 `borrador_no_encontrado`.
 */
export function confirmarCarga(entrada: Esquemas['ConfirmacionEntrada']): Promise<Esquemas['CargaCreadaRespuesta']> {
  return request<Esquemas['CargaCreadaRespuesta']>('/cargas/desde-borrador', conJson('POST', entrada));
}
