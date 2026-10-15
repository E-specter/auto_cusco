/**
 * What the v2 speech adds to the MOWA MES client (backend B6). The rest of the speech calls
 * (`listarSpeech`, `crearSpeech`, `editarSpeech`, `previsualizarSpeech`) are `api-mowa-mes.ts`'s and
 * already carry `expresiones`: this file only has the draft a v1 becomes and the reading of a
 * refused save.
 */

import { ApiError, request } from './api';
import type { BorradorV2, ProblemaSpeech } from './mowa-mes-speech-v2';

/**
 * The v2 draft of a v1: the same structure written with the engine, which gives the same messages
 * and lengths. It saves nothing; the analyst reviews it and saves it as a new version with
 * `crearSpeech({ basada_en_id, expresiones })`. A version that is already v2 answers 400.
 */
export function obtenerComoV2(id: number, signal?: AbortSignal): Promise<BorradorV2> {
  return request<BorradorV2>(`/mowa-mes/speech/${id}/como-v2`, { signal });
}

function esProblema(valor: unknown): valor is ProblemaSpeech {
  if (typeof valor !== 'object' || valor === null) return false;
  const candidato = valor as Record<string, unknown>;
  return typeof candidato.detalle === 'string' && typeof candidato.campo === 'string';
}

/**
 * The located problems of a refused speech save (400): each says its segment, its field and the
 * catalogue its code belongs to. Anything that is not such a list reads as none, and the screen
 * falls back to `detail`.
 */
export function problemasDeErrorSpeech(error: unknown): ProblemaSpeech[] {
  if (!(error instanceof ApiError)) return [];
  const problemas = error.cuerpo?.problemas;
  return Array.isArray(problemas) ? problemas.filter(esProblema) : [];
}
