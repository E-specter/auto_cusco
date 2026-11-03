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
