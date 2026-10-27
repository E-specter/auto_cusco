/**
 * What the upload dialog says in its second step (T-MAP-F2, docs/mapeador-encabezados-interfaz.md §4 and
 * §5): why «Confirmar y cargar» is off, how a refusal of the mapper reads, and how the reading options
 * are named. Pure: no DOM, no fetch. The page draws; these tests call it directly.
 *
 * The backend decides and the component shows: nothing here validates a mapping or knows a rule of the
 * sheet. A refusal is translated by its `codigo` (`mapeador.error.*`), never by its Spanish `detail`.
 */

import { ApiError } from './api';
import type { components } from './contrato-api';
import { t } from './i18n';

type Esquemas = components['schemas'];

export type Problema = Esquemas['ProblemaMapeoRespuesta'];
export type OpcionDetectable = Esquemas['OpcionDetectable'];

/** The part of the component's state that decides the button (`mapeocambiado`). */
export interface EstadoDelMapeo {
  problemas: readonly Problema[];
  listo: boolean;
  pendiente: boolean;
}

/**
 * The reason «Confirmar y cargar» is off, in words, or `null` when confirming is allowed. A required
 * field with no column comes first (it is what blocks the load), then the columns still to review.
 * `etiquetaDeCampo` gives the visible name of a field: the screen never shows its technical name.
 */
export function motivoDeConfirmar(
  estado: EstadoDelMapeo,
  etiquetaDeCampo: (nombre: string) => string,
): string | null {
  if (estado.pendiente) return t('console.mapeo.motivo.revisando');
  if (estado.listo) return null;
  const obligatorio = estado.problemas.find((p) => p.codigo === 'obligatorio_sin_columna');
  if (obligatorio) {
    return t('console.mapeo.motivo.obligatorio', { campo: obligatorio.campo ? etiquetaDeCampo(obligatorio.campo) : '' });
  }
  const porRevisar = estado.problemas.filter((p) => p.codigo === 'parecido_sin_revisar').length;
  if (porRevisar > 0) {
    return porRevisar === 1 ? t('console.mapeo.motivo.revisarUna') : t('console.mapeo.motivo.revisar', { n: porRevisar });
  }
  // Problems of another kind, or a validation that could not finish: nothing is confirmed on a guess.
  return t(estado.problemas.length > 0 ? 'console.mapeo.motivo.corregir' : 'console.mapeo.motivo.sinValidar');
}

/** The body of a refusal of the mapper: `{detail, codigo, …datos}` (B3b). `null` if it is not one. */
function cuerpoDe(error: unknown): Readonly<Record<string, unknown>> | null {
  return error instanceof ApiError ? error.cuerpo : null;
}

/** The `codigo` of a refusal, as text, or `null` when the body carries none. */
export function codigoDeError(error: unknown): string | null {
  const codigo = cuerpoDe(error)?.codigo;
  return typeof codigo === 'string' ? codigo : null;
}

/**
 * Why a call to the mapper was refused, in the interface's words: the text of its `codigo`
 * (`mapeador.error.<codigo>`), filled with the data the body carries (`hoja`, `maximo_mb`). Without a
 * known code, a general sentence; an unreachable API is not a refusal.
 */
export function textoDeError(error: unknown, red: string, general: string): string {
  if (!(error instanceof ApiError)) return red;
  const codigo = codigoDeError(error);
  if (!codigo) return general;
  const cuerpo = cuerpoDe(error)!;
  const clave = `mapeador.error.${codigo}`;
  const texto = t(clave, {
    hoja: typeof cuerpo.hoja === 'string' ? cuerpo.hoja : '',
    maximo_mb: typeof cuerpo.maximo_mb === 'number' ? cuerpo.maximo_mb : '',
  });
  return texto === clave ? general : texto;
}

/** The sheets a `hoja_inexistente` refusal offers, if it carries them. */
export function hojasDelError(error: unknown): string[] {
  const hojas = cuerpoDe(error)?.hojas;
  return Array.isArray(hojas) ? hojas.filter((h): h is string => typeof h === 'string') : [];
}

/**
 * The problems of a 422 `mapeo_con_problemas` on confirming, to hand to the component so the screen
 * stays on the second step with what was chosen intact. `null` for any other refusal.
 */
export function problemasDeLaConfirmacion(error: unknown): Problema[] | null {
  if (!(error instanceof ApiError) || error.status !== 422 || codigoDeError(error) !== 'mapeo_con_problemas') return null;
  const problemas = cuerpoDe(error)?.problemas;
  return Array.isArray(problemas) ? (problemas as Problema[]) : null;
}

/** An expired, confirmed or missing draft: there is nothing to confirm and the flow starts over. */
export function esBorradorPerdido(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404 && codigoDeError(error) === 'borrador_no_encontrado';
}

const NOMBRES_DE_SEPARADOR: Readonly<Record<string, string>> = {
  ';': 'console.mapeo.sep.puntoycoma',
  '\t': 'console.mapeo.sep.tabulacion',
  ',': 'console.mapeo.sep.coma',
};

/** A separator by its name («Coma»); one the interface has no name for shows as itself. */
export function nombreDeSeparador(separador: string): string {
  const clave = NOMBRES_DE_SEPARADOR[separador];
  return clave ? t(clave) : separador;
}

/** An option of the reading, with «(detectado/a)» when the reader chose it by itself. */
export function conMarcaDeDetectado(texto: string, opcion: OpcionDetectable, detectados: readonly OpcionDetectable[]): string {
  if (!detectados.includes(opcion)) return texto;
  return t(opcion === 'codificacion' ? 'console.mapeo.detectada' : 'console.mapeo.detectado', { valor: texto });
}

/** The reading options a format admits: sheets for a spreadsheet, separator and encoding for a CSV. */
export function opcionesQueAplican(analisis: Pick<Esquemas['AnalisisRespuesta'], 'formato' | 'hojas'>): {
  hoja: boolean;
  separador: boolean;
  codificacion: boolean;
} {
  const esCsv = analisis.formato === 'csv';
  return { hoja: analisis.hojas.length > 1, separador: esCsv, codificacion: esCsv };
}
