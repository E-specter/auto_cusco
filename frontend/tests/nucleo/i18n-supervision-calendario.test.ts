/**
 * The default supervisors and the working-day calendar are shared by every connector, so their texts
 * live under `supervisores.*` and `calendario.*`, not under the MOWA MES prefix (T-MM-C10, L-F7).
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const desdeAqui = (ruta: string) => fileURLToPath(new URL(ruta, import.meta.url));
const idiomas = {
  es: JSON.parse(readFileSync(desdeAqui('../../src/i18n/es.json'), 'utf8')) as Record<string, string>,
  en: JSON.parse(readFileSync(desdeAqui('../../src/i18n/en.json'), 'utf8')) as Record<string, string>,
};

describe.each(['es', 'en'] as const)('claves de supervisores y calendario (%s)', (idioma) => {
  const claves = Object.keys(idiomas[idioma]);

  it('no queda ninguna clave mowaMes.supervisores ni mowaMes.calendario', () => {
    expect(claves.filter((k) => /^mowaMes\.(supervisores|calendario)(\.|$)/.test(k))).toEqual([]);
  });

  it('las dos familias existen y las dos entradas del menú están traducidas', () => {
    expect(claves.filter((k) => k.startsWith('supervisores.')).length).toBeGreaterThan(20);
    expect(claves.filter((k) => k.startsWith('calendario.')).length).toBeGreaterThan(20);
    for (const clave of ['nav.supervisores', 'nav.calendario', 'supervisores.intro', 'calendario.intro']) {
      expect(idiomas[idioma][clave], clave).toBeTruthy();
    }
  });
});

describe('paridad entre idiomas', () => {
  it.each(['supervisores.', 'calendario.'])('las claves %s* son las mismas en español y en inglés', (prefijo) => {
    const de = (idioma: 'es' | 'en') => Object.keys(idiomas[idioma]).filter((k) => k.startsWith(prefijo)).sort();
    expect(de('en')).toEqual(de('es'));
  });
});
