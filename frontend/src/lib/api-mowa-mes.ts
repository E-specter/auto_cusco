/**
 * Calls for the MOWA MES connector: its configuration, the default
 * supervisors, the speech versions and the working-day calendar.
 *
 * Shapes come from the generated contract only (`contrato-api.d.ts`); the
 * transport, errors included, is the shared `request` of `api.ts`.
 */

import { request } from './api';
import type { components } from './contrato-api';
import { descargarArchivo, type ArchivoDescargado } from './descargas';

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
export type Campana = Esquemas['CampanaRespuesta'];
export type ListaCampanas = Esquemas['ListaCampanasRespuesta'];
export type ArchivoCampana = Esquemas['ArchivoRespuesta'];
export type PaginaExclusiones = Esquemas['PaginaExclusionesRespuesta'];
export type Exclusion = Esquemas['ExclusionRespuesta'];
export type ConsumoLimite = Esquemas['ConsumoLimiteRespuesta'];
export type Conciliacion = Esquemas['ConciliacionRespuesta'];
export type CifrasGrupo = Esquemas['CifrasGrupoRespuesta'];
export type EstadoConteo = Esquemas['EstadoConteoRespuesta'];
export type CifrasId = Esquemas['CifrasIdRespuesta'];
export type AdvertenciaReporte = Esquemas['AdvertenciaReporteRespuesta'];
export type ReporteImportado = Esquemas['ReporteImportadoRespuesta'];
export type PeticionCampanaEntrada = Esquemas['PeticionCampanaEntrada'];
export type CreacionCampanaEntrada = Esquemas['CreacionCampanaEntrada'];
export type PrevisualizacionCampana = Esquemas['PrevisualizacionCampanaRespuesta'];
export type AvisoCampana = Esquemas['AvisoCampanaRespuesta'];
export type ArchivoPrevisto = Esquemas['ArchivoPrevistoRespuesta'];
export type CodigoConteo = Esquemas['CodigoConteoRespuesta'];
export type FilaMuestra = Esquemas['FilaMuestraRespuesta'];
export type SegmentoConteo = Esquemas['SegmentoConteoRespuesta'];
export type SupervisorAsignado = Esquemas['SupervisorAsignadoRespuesta'];
export type SpeechCampana = Esquemas['SpeechCampanaRespuesta'];
export type HerramientasEntrada = Esquemas['HerramientasModelo'];
export type ProgramacionCampana = Esquemas['Programacion'];
export type TipoCarga = Esquemas['TipoCarga'];
export type Salida = Esquemas['Salida'];
export type SupervisorCampanaEntrada = Esquemas['SupervisorCampanaEntrada'];

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

// ---- Campaigns, files, sent reports and reconciliation (B6b) --------------------

/** Most recent first. */
export function listarCampanas(
  params: { limite?: number; desplazamiento?: number } = {},
): Promise<ListaCampanas> {
  const query = new URLSearchParams({
    limite: String(params.limite ?? 20),
    desplazamiento: String(params.desplazamiento ?? 0),
  });
  return request<ListaCampanas>(`/mowa-mes/campanas?${query}`);
}

export function obtenerCampana(id: number): Promise<Campana> {
  return request<Campana>(`/mowa-mes/campanas/${id}`);
}

/** In the selection's order; without `codigo`, every reason. */
export function listarExclusiones(
  id: number,
  params: { codigo?: CodigoMowaMes; limite?: number; desplazamiento?: number } = {},
): Promise<PaginaExclusiones> {
  const query = new URLSearchParams();
  if (params.codigo) query.set('codigo', params.codigo);
  query.set('limite', String(params.limite ?? 50));
  query.set('desplazamiento', String(params.desplazamiento ?? 0));
  return request<PaginaExclusiones>(`/mowa-mes/campanas/${id}/exclusiones?${query}`);
}

/** Prefix of the summary headers a load file carries (docs/mowa-mes.md §11). */
export const PREFIJO_RESUMEN_ARCHIVO = 'X-Mowa-Mes-';

/** The stored `.xlsx`: body, name from `Content-Disposition`, summary from `X-Mowa-Mes-*`. */
export function descargarArchivoCampana(id: number, numero: number): Promise<ArchivoDescargado> {
  return descargarArchivo(`/mowa-mes/campanas/${id}/archivos/${numero}`, {}, PREFIJO_RESUMEN_ARCHIVO);
}

/** Consumption of a month (`YYYY-MM`); without it, the current month in Lima. */
export function consumoLimite(mes?: string): Promise<ConsumoLimite> {
  const query = mes ? `?${new URLSearchParams({ mes })}` : '';
  return request<ConsumoLimite>(`/mowa-mes/limite-mensual${query}`);
}

/**
 * Upload MES's sent report for a campaign. A MES id already imported answers
 * 409 unless `reemplazar` is true, which replaces it.
 */
export function importarReporte(id: number, archivo: File, reemplazar = false): Promise<Conciliacion> {
  const body = new FormData();
  body.set('archivo', archivo);
  body.set('reemplazar', String(reemplazar));
  return request<Conciliacion>(`/mowa-mes/campanas/${id}/reportes`, { method: 'POST', body });
}

export function obtenerConciliacion(id: number): Promise<Conciliacion> {
  return request<Conciliacion>(`/mowa-mes/campanas/${id}/conciliacion`);
}

/** Without `desde`, the API starts from today in America/Lima. */
export function siguienteDiaGestionable(desde?: string): Promise<SiguienteDia> {
  const query = desde ? `?${new URLSearchParams({ desde })}` : '';
  return request<SiguienteDia>(`/calendario/siguiente-dia-gestionable${query}`);
}

/**
 * Preview a campaign without persisting it. Answers 200 even when it cannot be
 * created (`puede_crear: false`, with `errores`); 400 for disabled options or
 * an out-of-range quantity; 404 without a current sheet version or an unknown
 * speech id.
 */
export function previsualizarCampana(
  entrada: PeticionCampanaEntrada,
  signal?: AbortSignal,
): Promise<PrevisualizacionCampana> {
  return request<PrevisualizacionCampana>(
    '/mowa-mes/campanas/previsualizacion',
    conJson('POST', entrada, signal),
  );
}

/**
 * Create a campaign. `speech_huella` must be the one the last preview
 * returned; a 409 means either the speech changed since (huella mismatch) or
 * the month's limit is exceeded and `confirmar_limite` was not sent.
 */
export function crearCampana(entrada: CreacionCampanaEntrada): Promise<Campana> {
  return request<Campana>('/mowa-mes/campanas', conJson('POST', entrada));
}
