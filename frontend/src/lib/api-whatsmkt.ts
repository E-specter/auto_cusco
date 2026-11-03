/**
 * Calls for the WhatsMKT connector: its configuration and its segment table.
 * The default supervisors, the working-day calendar and the load columns are shared by every connector
 * (`api-supervision.ts`, `api-calendario.ts`, `api-definiciones.ts`).
 *
 * Shapes come from the generated contract only (`contrato-api.d.ts`); the transport, errors included,
 * is the shared `request` of `api.ts`.
 */

import { conJson, request } from './api';
import type { components } from './contrato-api';
import { descargarArchivo, type ArchivoDescargado } from './descargas';

type Esquemas = components['schemas'];

export type ConfiguracionWhatsmkt = Esquemas['ConfiguracionWhatsmktRespuesta'];
export type ConfiguracionWhatsmktEntrada = Esquemas['ConfiguracionWhatsmktEntrada'];
export type HorarioWhatsmkt = Esquemas['HorarioWhatsmktRespuesta'];
export type SegmentoWhatsmkt = Esquemas['SegmentoWhatsmktRespuesta'];
export type SegmentoWhatsmktEntrada = Esquemas['SegmentoWhatsmktEntrada'];
export type CodigoWhatsmkt = Esquemas['CodigoWhatsmkt'];
/** The 422 of a module rule: the code the screen translates and the data its text names. */
export type ErrorWhatsmkt = Esquemas['ErrorWhatsmktRespuesta'];

export function obtenerConfiguracion(): Promise<ConfiguracionWhatsmkt> {
  return request<ConfiguracionWhatsmkt>('/whatsmkt/configuracion');
}

/** A partial PUT: a field left out keeps what is saved, so each panel sends only its own. */
export function guardarConfiguracion(entrada: ConfiguracionWhatsmktEntrada): Promise<ConfiguracionWhatsmkt> {
  return request<ConfiguracionWhatsmkt>('/whatsmkt/configuracion', conJson('PUT', entrada));
}

export function listarSegmentos(): Promise<SegmentoWhatsmkt[]> {
  return request<SegmentoWhatsmkt[]>('/whatsmkt/segmentos');
}

/** Replaces the label and the limits of the 3 fixed segments in one transaction. */
export function guardarSegmentos(entrada: SegmentoWhatsmktEntrada[]): Promise<SegmentoWhatsmkt[]> {
  return request<SegmentoWhatsmkt[]>('/whatsmkt/segmentos', conJson('PUT', entrada));
}

// ---- Attachment library (RF-WM-30 to RF-WM-32) -----------------------------------------------------

export type AdjuntoWhatsmkt = Esquemas['AdjuntoWhatsmktRespuesta'];
/** What an upload answers: the attachment and whether the library already had it (same fingerprint). */
export type AdjuntoSubido = Esquemas['AdjuntoSubidoRespuesta'];
export type TipoAdjunto = Esquemas['TipoAdjunto'];

const ADJUNTOS = '/whatsmkt/adjuntos';

/** The library: the active attachments, or with `archivados` the archived ones. The content is not listed. */
export function listarAdjuntos(archivados = false): Promise<AdjuntoWhatsmkt[]> {
  return request<AdjuntoWhatsmkt[]>(archivados ? `${ADJUNTOS}?archivados=true` : ADJUNTOS);
}

/**
 * Validates, cleans and stores a file (201). A file with the same fingerprint answers the one that was there,
 * with `ya_existia`: an archived one that is uploaded again stays archived. The module's refusals are 422.
 */
export function subirAdjunto(archivo: File): Promise<AdjuntoSubido> {
  const cuerpo = new FormData();
  cuerpo.set('archivo', archivo);
  cuerpo.set('proposito', 'adjunto');
  return request<AdjuntoSubido>(ADJUNTOS, { method: 'POST', body: cuerpo });
}

/** It stops being offered in new campaigns; the ones that used it keep it. 404 if it does not exist. */
export function archivarAdjunto(id: number): Promise<AdjuntoWhatsmkt> {
  return request<AdjuntoWhatsmkt>(`${ADJUNTOS}/${id}/archivar`, { method: 'POST' });
}

export function desarchivarAdjunto(id: number): Promise<AdjuntoWhatsmkt> {
  return request<AdjuntoWhatsmkt>(`${ADJUNTOS}/${id}/desarchivar`, { method: 'POST' });
}

/** The file as it was stored (images without metadata), with the name the server gives it. */
export function descargarAdjunto(id: number): Promise<ArchivoDescargado> {
  return descargarArchivo(`${ADJUNTOS}/${id}/contenido`);
}
