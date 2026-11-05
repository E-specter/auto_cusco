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
/** The next working day and the first date that can be picked (RF-70 and RF-71). */
export type ProgramacionWhatsmkt = Esquemas['ProgramacionWhatsmktRespuesta'];
/** The 422 of a module rule: the code the screen translates and the data its text names. */
export type ErrorWhatsmkt = Esquemas['ErrorWhatsmktRespuesta'];

/** The suggested send date (`sugerida`) and the earliest one allowed (`minima`), both in the Lima calendar. */
export function obtenerProgramacion(): Promise<ProgramacionWhatsmkt> {
  return request<ProgramacionWhatsmkt>('/whatsmkt/programacion');
}

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
export function subirAdjunto(archivo: File, proposito: 'adjunto' | 'foto' = 'adjunto'): Promise<AdjuntoSubido> {
  const cuerpo = new FormData();
  cuerpo.set('archivo', archivo);
  // `foto` also checks that it serves as a profile photo: JPEG, 200 x 200, up to 1 MB.
  cuerpo.set('proposito', proposito);
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

// ---- Campaigns (RF-WM-23, RF-WM-35) ----------------------------------------------------------------

export type PeticionPrevisualizacion = Esquemas['PrevisualizacionCampanasWhatsmktEntrada'];
export type PrevisualizacionCampanas = Esquemas['PrevisualizacionCampanasWhatsmktRespuesta'];
export type CampanaPrevista = Esquemas['CampanaPrevistaWhatsmktRespuesta'];
export type ProblemaCampana = Esquemas['ProblemaWhatsmktRespuesta'];
export type ExclusionCampana = Esquemas['ExclusionWhatsmktRespuesta'];
export type MensajeEntrada = Esquemas['MensajeWhatsmktEntrada'];
export type ModoCampana = Esquemas['ModoCampana'];
export type TipoEnvio = Esquemas['TipoEnvio'];
export type PeticionCreacion = Esquemas['CreacionCampanasWhatsmktEntrada'];
/** A campaign of the lot just created, with the data of its form already written (RF-WM-36). */
export type CampanaCreada = Esquemas['CampanaCreadaWhatsmktRespuesta'];
export type FichaCampana = Esquemas['FichaWhatsmktRespuesta'];
/** The 409 of creating: the send date stopped being a working day; `sugerida` is the next one. */
export type ErrorFechaNoGestionable = Esquemas['ErrorFechaNoGestionableWhatsmktRespuesta'];

/**
 * What the lot would be, without creating anything: the campaigns, their sample and exclusions, the message of each and
 * the problems that stop creating. It recalculates on every change of the form, so a newer call cancels the older.
 */
export function previsualizarCampanas(
  entrada: PeticionPrevisualizacion,
  signal?: AbortSignal,
): Promise<PrevisualizacionCampanas> {
  return request<PrevisualizacionCampanas>('/whatsmkt/campanas/previsualizacion', conJson('POST', entrada, signal));
}

/**
 * Creates the whole lot or none (201 with the campaigns of the lot). A date that stopped being a working day is a 409 with the next one
 * (`ErrorFechaNoGestionable`); what keeps it from being created is a 422 with every problem; the rest are 400 and 404.
 */
export function crearCampanas(entrada: PeticionCreacion): Promise<CampanaCreada[]> {
  return request<CampanaCreada[]>('/whatsmkt/campanas', conJson('POST', entrada));
}

/** The `.xlsx` of a campaign, with the name the server gives it. */
export function descargarArchivoCampana(id: number): Promise<ArchivoDescargado> {
  return descargarArchivo(`/whatsmkt/campanas/${id}/archivo`);
}

// ---- Tracking (RF-WM-40 to RF-WM-42) ------------------------------------------------------------------

export type ListaCampanas = Esquemas['ListaCampanasWhatsmktRespuesta'];
export type ResumenCampana = Esquemas['ResumenCampanaWhatsmktRespuesta'];
export type DetalleCampana = Esquemas['DetalleCampanaWhatsmktRespuesta'];
export type PaginaExclusiones = Esquemas['PaginaExclusionesWhatsmktRespuesta'];
export type EstadoCampana = Esquemas['EstadoCampana'];

export interface FiltroCampanas {
  estado: EstadoCampana;
  /** `YYYY-MM`: the month of the send date. */
  mes?: string;
  loteId?: number;
  limite: number;
  desplazamiento: number;
}

/** The campaigns, the latest first (a lot stays together), one page, with the counts of the whole: active, discarded and pending the report. */
export function listarCampanas(filtro: FiltroCampanas, signal?: AbortSignal): Promise<ListaCampanas> {
  const consulta = new URLSearchParams({
    estado: filtro.estado,
    limite: String(filtro.limite),
    desplazamiento: String(filtro.desplazamiento),
  });
  if (filtro.mes) consulta.set('mes', filtro.mes);
  if (filtro.loteId) consulta.set('lote_id', String(filtro.loteId));
  return request<ListaCampanas>(`/whatsmkt/campanas?${consulta}`, { signal });
}

/** One campaign with its card, its lot and its exclusions, its own and those left out of every campaign of the lot, each list with its page. */
export function obtenerCampana(
  id: number,
  paginas: { exclusiones?: number; fuera?: number; limite: number },
  signal?: AbortSignal,
): Promise<DetalleCampana> {
  const consulta = new URLSearchParams({
    exclusiones_limite: String(paginas.limite),
    exclusiones_desplazamiento: String(paginas.exclusiones ?? 0),
    fuera_del_lote_limite: String(paginas.limite),
    fuera_del_lote_desplazamiento: String(paginas.fuera ?? 0),
  });
  return request<DetalleCampana>(`/whatsmkt/campanas/${id}?${consulta}`, { signal });
}

/** Sets it aside without deleting anything: discarding one that is already discarded changes nothing. */
export function descartarCampana(id: number): Promise<ResumenCampana> {
  return request<ResumenCampana>(`/whatsmkt/campanas/${id}/descartar`, { method: 'POST' });
}

export function restaurarCampana(id: number): Promise<ResumenCampana> {
  return request<ResumenCampana>(`/whatsmkt/campanas/${id}/restaurar`, { method: 'POST' });
}

/** Deletes a DISCARDED campaign for good (an active one answers 409 `campana_no_descartada`); the library and the messages stay. */
export function eliminarCampana(id: number): Promise<void> {
  return request<void>(`/whatsmkt/campanas/${id}`, { method: 'DELETE' });
}
