/**
 * The working-day calendar (`/calendario/*`): shared by every connector, so it is not under `/mowa-mes`.
 * Shapes come from the generated contract; the transport is the shared `request` of `api.ts`.
 */

import { conJson, request } from './api';
import type { components } from './contrato-api';

type Esquemas = components['schemas'];

export type Feriados = Esquemas['FeriadosRespuesta'];
export type DiaNoLaborable = Esquemas['DiaNoLaborableRespuesta'];
export type TipoExcepcion = Esquemas['TipoExcepcion'];
export type Excepcion = Esquemas['ExcepcionRespuesta'];
export type ExcepcionEntrada = Esquemas['ExcepcionEntrada'];
export type SiguienteDia = Esquemas['SiguienteDiaRespuesta'];

export function listarFeriados(anio: number): Promise<Feriados> {
  return request<Feriados>(`/calendario/feriados?${new URLSearchParams({ anio: String(anio) })}`);
}

export function crearExcepcion(entrada: ExcepcionEntrada): Promise<Excepcion> {
  return request<Excepcion>('/calendario/excepciones', conJson('POST', entrada));
}

export function eliminarExcepcion(fecha: string): Promise<void> {
  return request<void>(`/calendario/excepciones/${encodeURIComponent(fecha)}`, {
    method: 'DELETE',
  });
}

/** Without `desde`, the API starts from today in America/Lima. */
export function siguienteDiaGestionable(desde?: string): Promise<SiguienteDia> {
  const query = desde ? `?${new URLSearchParams({ desde })}` : '';
  return request<SiguienteDia>(`/calendario/siguiente-dia-gestionable${query}`);
}
