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

import { request } from './api';
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

/** Drop every cached catalogue. Tests use it; a page never needs it. */
export function olvidarCatalogos(): void {
  catalogos.clear();
}

const json = (cuerpo: unknown, signal?: AbortSignal): RequestInit => ({
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(cuerpo),
  signal,
});

export function validarTexto(
  contexto: string,
  expresion: ExpresionEntrada,
  signal?: AbortSignal,
): Promise<ValidacionTexto> {
  return request<ValidacionTexto>('/texto-enriquecido/validacion', json({ contexto, expresion }, signal));
}

export function previsualizarTexto(
  peticion: PeticionPrevisualizacion,
  signal?: AbortSignal,
): Promise<PrevisualizacionTexto> {
  return request<PrevisualizacionTexto>('/texto-enriquecido/previsualizacion', json(peticion, signal));
}
