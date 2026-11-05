/**
 * Client of the rich-text engine (docs/motor-texto-enriquecido.md §10, interface
 * rules §9.3): catalogue, validation and preview.
 *
 * Two things a caller should know:
 * - A text with problems is a normal answer, 200 with `problemas`: only a 4xx
 *   (an unknown context, product or cut-off date, with `codigo`) or an
 *   unreachable API rejects.
 * - The catalogue is asked for once per context and page. Several editors on
 *   one screen share the answer, and a failed request is forgotten so the
 *   next call tries again instead of repeating the failure.
 */

import { conJson, request } from './api';
import type { components } from './contrato-api';

type Esquemas = components['schemas'];

export type CatalogoTexto = Esquemas['CatalogoRespuesta'];
export type ValidacionTexto = Esquemas['ValidacionRespuesta'];
export type PrevisualizacionTexto = Esquemas['PrevisualizacionTextoRespuesta'];
export type PeticionPrevisualizacion = Esquemas['PeticionPrevisualizacion'];
export type MuestraTexto = Esquemas['MuestraEntrada'];
export type ExpresionEntrada = Esquemas['ExpresionEntrada'];
export type CodigoTexto = Esquemas['CodigoTexto'];

const catalogos = new Map<string, Promise<CatalogoTexto>>();

export function obtenerCatalogo(contexto: string): Promise<CatalogoTexto> {
  const guardado = catalogos.get(contexto);
  if (guardado) return guardado;
  const pedido = request<CatalogoTexto>(
    `/texto-enriquecido/catalogo?${new URLSearchParams({ contexto })}`,
  );
  catalogos.set(contexto, pedido);
  pedido.catch(() => catalogos.delete(contexto));
  return pedido;
}

/**
 * Drop every cached catalogue. Tests use it; a page rarely needs it: use `olvidarCatalogo` when only one context changed.
 */
export function olvidarCatalogos(): void {
  catalogos.clear();
}

/**
 * Drop the cached catalogue of one context, so the next editor mounted on it asks again. For a context whose catalogue follows
 * something the page can change (the message of a channel takes its macros and its limit from the configuration): the page
 * calls this before mounting the editor again. The other contexts keep theirs.
 */
export function olvidarCatalogo(contexto: string): void {
  catalogos.delete(contexto);
}

export function validarTexto(
  contexto: string,
  expresion: ExpresionEntrada,
  signal?: AbortSignal,
): Promise<ValidacionTexto> {
  return request<ValidacionTexto>('/texto-enriquecido/validacion', conJson('POST', { contexto, expresion }, signal));
}

export function previsualizarTexto(
  peticion: PeticionPrevisualizacion,
  signal?: AbortSignal,
): Promise<PrevisualizacionTexto> {
  return request<PrevisualizacionTexto>('/texto-enriquecido/previsualizacion', conJson('POST', peticion, signal));
}
