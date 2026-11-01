/**
 * What the v2 speech adds to the MOWA MES client (backend B6). The rest of the speech calls
 * (`listarSpeech`, `crearSpeech`, `editarSpeech`, `previsualizarSpeech`) are `api-mowa-mes.ts`'s and
 * already carry `expresiones`: this file only has the reading of a refused save.
 */

import { ApiError } from './api';
import type { ProblemaSpeech } from './mowa-mes-speech-v2';

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
