/**
 * What a non-working day offers (the screen logic of `/calendario`).
 */
import { describe, expect, it } from 'vitest';

import { accionDia } from '../../src/lib/calendario';

describe('acciones del calendario', () => {
  const dia = { fecha: '2099-07-28', descripcion: 'Feriado sintetico' };

  it('un feriado de ley se retira, nunca se borra', () => {
    expect(accionDia({ ...dia, origen: 'ley', retirado: false })).toBe('retirar');
  });

  it('un feriado de ley retirado se restaura', () => {
    expect(accionDia({ ...dia, origen: 'ley', retirado: true })).toBe('restaurar');
  });

  it('un día agregado se quita', () => {
    expect(accionDia({ ...dia, origen: 'agregado', retirado: false })).toBe('quitar');
  });
});
