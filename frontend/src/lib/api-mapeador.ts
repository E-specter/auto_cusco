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
