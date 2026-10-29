/**
 * The default supervisors (`/supervisores`): shared by every connector, so it is not under `/mowa-mes`.
 * Shapes come from the generated contract; the transport is the shared `request` of `api.ts`.
 */

import { conJson, request } from './api';
import type { components } from './contrato-api';

type Esquemas = components['schemas'];

export type ConfiguracionSupervision = Esquemas['ConfiguracionSupervisionRespuesta'];
export type ConfiguracionSupervisionEntrada = Esquemas['ConfiguracionSupervisionEntrada'];

export function obtenerSupervision(): Promise<ConfiguracionSupervision> {
  return request<ConfiguracionSupervision>('/supervisores');
}

export function guardarSupervision(
  entrada: ConfiguracionSupervisionEntrada,
): Promise<ConfiguracionSupervision> {
  return request<ConfiguracionSupervision>('/supervisores', conJson('PUT', entrada));
}
