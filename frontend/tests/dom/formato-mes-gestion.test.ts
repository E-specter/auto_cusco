/**
 * The management month as the analyst reads it (`formatMesGestion`): the one label of the limit's panel, the
 * discarded filter and the detail. Capital first letter in both languages; January and December are the
 * edges of the year.
 */
import { afterEach, describe, expect, it } from 'vitest';

import { formatMes, formatMesGestion } from '../../src/lib/format';
import { setLanguage } from '../../src/lib/i18n';

afterEach(() => setLanguage('es'));

describe('formatMesGestion', () => {
  it('en español: «Octubre de 2026», con mayúscula', () => {
    setLanguage('es');
    expect(formatMesGestion('2026-10')).toBe('Octubre de 2026');
    expect(formatMesGestion('2026-01')).toBe('Enero de 2026');
    expect(formatMesGestion('2025-12')).toBe('Diciembre de 2025');
  });

  it('en inglés: «October 2026», sin cambios', () => {
    setLanguage('en');
    expect(formatMesGestion('2026-10')).toBe('October 2026');
    expect(formatMesGestion('2026-01')).toBe('January 2026');
    expect(formatMesGestion('2025-12')).toBe('December 2025');
  });

  it('a mitad de frase («cuenta en»), en español el mes va en minúscula; en inglés, como lo da Intl', () => {
    setLanguage('es');
    expect(formatMes('2026-10')).toBe('octubre de 2026');
    expect(formatMes('2026-01')).toBe('enero de 2026');
    setLanguage('en');
    expect(formatMes('2026-10')).toBe('October 2026');
    expect(formatMes('2025-12')).toBe('December 2025');
  });

  it('el rótulo es el mes de a mitad de frase con la primera letra en mayúscula, nada más', () => {
    setLanguage('es');
    for (let mes = 1; mes <= 12; mes++) {
      const clave = `2026-${String(mes).padStart(2, '0')}`;
      expect(formatMesGestion(clave)).toBe(formatMes(clave).charAt(0).toLocaleUpperCase('es-PE') + formatMes(clave).slice(1));
    }
  });

  it('el mes de cada estación del año empieza con mayúscula', () => {
    setLanguage('es');
    for (let mes = 1; mes <= 12; mes++) {
      const texto = formatMesGestion(`2026-${String(mes).padStart(2, '0')}`);
      expect(texto.charAt(0), texto).toBe(texto.charAt(0).toLocaleUpperCase('es-PE'));
      expect(texto).toMatch(/ de 2026$/);
    }
  });
});
