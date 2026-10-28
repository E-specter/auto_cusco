/**
 * Every exclusion reason the filter offers needs its text in both languages: the filter of tracking
 * (`seguimiento.astro`) and the tags of tracking and of the campaign preview build the key from the code.
 * A reason the backend adds without its text shows the raw key on screen (it happened with
 * `falta_campo_adicional`, T-MM-B12). Same keys as the pages: `mowaMes.seguimiento.exclusiones.motivo.<code>`.
 */
import { describe, expect, it } from 'vitest';

import en from '../../src/i18n/en.json';
import es from '../../src/i18n/es.json';
import { CODIGOS_EXCLUSION } from '../../src/lib/mowa-mes-seguimiento';

describe('cada motivo de exclusión tiene su texto en español y en inglés', () => {
  for (const codigo of CODIGOS_EXCLUSION) {
    it(codigo, () => {
      const clave = `mowaMes.seguimiento.exclusiones.motivo.${codigo}`;
      const textos = { es, en } as Record<string, Record<string, string>>;
      for (const idioma of ['es', 'en']) {
        expect(textos[idioma][clave], `${idioma}: falta ${clave}`).toBeTruthy();
        // A text that is the key itself is the same hole with another name.
        expect(textos[idioma][clave]).not.toBe(clave);
      }
    });
  }
});
