/**
 * Contract between the MOWA MES speech error codes and the interface dictionaries.
 *
 * A 409 on a speech `DELETE` carries a `codigo` (`CodigoErrorSpeech`), translated under
 * `mowaMes.errorSpeech.<codigo>`. The backend test checks that every code has a key; this one
 * reads the backend's enum and adds the other direction: keys left behind for codes that no
 * longer exist, and both languages having the same keys.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import es from '../../src/i18n/es.json';
import en from '../../src/i18n/en.json';

// fileURLToPath, not URL.pathname: the repo path contains a space.
const ENTIDADES = fileURLToPath(
  new URL('../../../backend/app/core/entities/mowa_mes.py', import.meta.url),
);

const PREFIJO = 'mowaMes.errorSpeech.';

function codigosDelCatalogo(): string[] {
  const fuente = readFileSync(ENTIDADES, 'utf8');
  const clase = fuente.match(/class CodigoErrorSpeech\(StrEnum\):([\s\S]*?)(?=\n\S)/);

  if (!clase) {
    throw new Error(
      `No se encontró la clase CodigoErrorSpeech en ${ENTIDADES}. Si el backend la movió o la ` +
        'renombró, esta prueba debe seguirla: dejarla pasar en verde sería peor que fallar.',
    );
  }

  return [...clase[1].matchAll(/^\s+[A-Z][A-Z0-9_]*\s*=\s*"([a-z][a-z0-9_]*)"/gm)]
    .map(([, codigo]) => codigo)
    .sort();
}

const clavesCon = (diccionario: Record<string, string>) =>
  Object.keys(diccionario)
    .filter((clave) => clave.startsWith(PREFIJO))
    .map((clave) => clave.slice(PREFIJO.length))
    .sort();

describe('traducción de los códigos de error de las versiones de speech', () => {
  const codigos = codigosDelCatalogo();

  it('lee el catálogo canónico del backend', () => {
    expect(codigos).toContain('speech_original');
    expect(codigos).toContain('speech_no_deshabilitado');
    expect(codigos).toEqual([...new Set(codigos)]);
  });

  it.each(codigosDelCatalogo())('traduce %s al español y al inglés', (codigo) => {
    expect(es).toHaveProperty([`${PREFIJO}${codigo}`]);
    expect(en).toHaveProperty([`${PREFIJO}${codigo}`]);
  });

  it('no conserva traducciones de códigos que el catálogo ya no incluye', () => {
    expect(clavesCon(es).filter((codigo) => !codigos.includes(codigo))).toEqual([]);
  });

  it('tiene las mismas claves en los dos idiomas', () => {
    expect(clavesCon(en)).toEqual(clavesCon(es));
  });
});
