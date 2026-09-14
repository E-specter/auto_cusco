/**
 * Calls for the MOWA MES connector: its configuration, the default
 * supervisors, the speech versions and the working-day calendar.
 *
 * Shapes come from the generated contract only (`contrato-api.d.ts`); the
 * transport, errors included, is the shared `request` of `api.ts`.
 */

import { request } from './api';
import type { components } from './contrato-api';

type Esquemas = components['schemas'];

export type ConfiguracionMowaMes = Esquemas['ConfiguracionRespuesta'];
export type ConfiguracionMowaMesEntrada = Esquemas['ConfiguracionEntrada'];
export type ConfiguracionSupervision = Esquemas['ConfiguracionSupervisionRespuesta'];
export type ConfiguracionSupervisionEntrada = Esquemas['ConfiguracionSupervisionEntrada'];
export type Supervisor = Esquemas['SupervisorRespuesta'];
export type VersionSpeech = Esquemas['VersionSpeechRespuesta'];
export type PartesSpeech = Esquemas['PartesRespuesta'];
export type PartesEntrada = Esquemas['PartesEntrada'];
export type SpeechNuevoEntrada = Esquemas['SpeechNuevoEntrada'];
export type SpeechEdicionEntrada = Esquemas['SpeechEdicionEntrada'];
export type PrevisualizacionSpeechEntrada = Esquemas['PrevisualizacionEntrada'];
export type PrevisualizacionSpeech = Esquemas['app__api__mowa_mes__PrevisualizacionRespuesta'];
export type LargoSegmento = Esquemas['LargoSegmentoRespuesta'];
export type Segmento = Esquemas['Segmento'];
export type CodigoMowaMes = Esquemas['CodigoMowaMes'];
export type Feriados = Esquemas['FeriadosRespuesta'];
export type DiaNoLaborable = Esquemas['DiaNoLaborableRespuesta'];
export type TipoExcepcion = Esquemas['TipoExcepcion'];
export type Excepcion = Esquemas['ExcepcionRespuesta'];
export type ExcepcionEntrada = Esquemas['ExcepcionEntrada'];
export type SiguienteDia = Esquemas['SiguienteDiaRespuesta'];

function conJson(method: string, cuerpo: unknown, signal?: AbortSignal): RequestInit {
  return {
    method,
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(cuerpo),
    signal,
  };
}

// ---- Connector configuration ------------------------------------------------

export function obtenerConfiguracion(): Promise<ConfiguracionMowaMes> {
  return request<ConfiguracionMowaMes>('/mowa-mes/configuracion');
}

export function guardarConfiguracion(
  entrada: ConfiguracionMowaMesEntrada,
): Promise<ConfiguracionMowaMes> {
  return request<ConfiguracionMowaMes>('/mowa-mes/configuracion', conJson('PUT', entrada));
}

// ---- Default supervisors (transversal) ----------------------------------------

export function obtenerSupervision(): Promise<ConfiguracionSupervision> {
  return request<ConfiguracionSupervision>('/supervisores');
}

export function guardarSupervision(
  entrada: ConfiguracionSupervisionEntrada,
): Promise<ConfiguracionSupervision> {
  return request<ConfiguracionSupervision>('/supervisores', conJson('PUT', entrada));
}

// ---- Speech versions ---------------------------------------------------------

export function listarSpeech(): Promise<VersionSpeech[]> {
  return request<VersionSpeech[]>('/mowa-mes/speech');
}

export function crearSpeech(entrada: SpeechNuevoEntrada): Promise<VersionSpeech> {
  return request<VersionSpeech>('/mowa-mes/speech', conJson('POST', entrada));
}

/** Only for a version nobody used; the original and used ones answer 409. */
export function editarSpeech(id: number, entrada: SpeechEdicionEntrada): Promise<VersionSpeech> {
  return request<VersionSpeech>(`/mowa-mes/speech/${id}`, conJson('PUT', entrada));
}

export function previsualizarSpeech(
  entrada: PrevisualizacionSpeechEntrada,
  signal?: AbortSignal,
): Promise<PrevisualizacionSpeech> {
  return request<PrevisualizacionSpeech>(
    '/mowa-mes/speech/previsualizacion',
    conJson('POST', entrada, signal),
  );
}

// ---- Working-day calendar (transversal) --------------------------------------

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
