/**
 * Screen logic of the working-day calendar, shared by every connector. Nothing here decides a date:
 * the API computes the holidays and the next manageable day; this only says what a day offers.
 */

import type { DiaNoLaborable } from './api-calendario';

export type AccionDia = 'retirar' | 'restaurar' | 'quitar';

/**
 * What a non-working day offers. Law holidays are computed by rule, so they
 * are never deleted: a year that does not observe one records a `retirado`
 * exception, and undoing that deletes the exception. An added day is itself an
 * exception, so removing it deletes it.
 */
export function accionDia(dia: DiaNoLaborable): AccionDia {
  if (dia.origen === 'agregado') return 'quitar';
  return dia.retirado ? 'restaurar' : 'retirar';
}
