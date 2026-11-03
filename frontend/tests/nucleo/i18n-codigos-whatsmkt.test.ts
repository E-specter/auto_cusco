/**
 * Contract between the WhatsMKT code catalogue and the interface dictionaries.
 *
 * A 422 of the module carries a `codigo` (`CodigoWhatsmkt`), which the screens translate under
 * `whatsmkt.codigo.<codigo>`. The backend has its own test that every code has a key; this one reads
 * the backend's enum and adds the other direction: keys left behind for codes that no longer exist.
 * It also keeps every WhatsMKT key present in both languages with the same placeholders, so a
 * sentence never loses a `{parameter}` in one of them.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import es from '../../src/i18n/es.json';
import en from '../../src/i18n/en.json';

// fileURLToPath, not URL.pathname: the repo path contains a space.
const ENTIDADES = fileURLToPath(new URL('../../../backend/app/core/entities/whatsmkt.py', import.meta.url));

const PREFIJO = 'whatsmkt.codigo.';

function codigosDelCatalogo(): string[] {
  const fuente = readFileSync(ENTIDADES, 'utf8');
  const clase = fuente.match(/class CodigoWhatsmkt\(StrEnum\):([\s\S]*?)(?=\n\S)/);

  if (!clase) {
    throw new Error(
      `No se encontró la clase CodigoWhatsmkt en ${ENTIDADES}. Si el backend la movió o la renombró, ` +
        'esta prueba debe seguirla: dejarla pasar en verde sería peor que fallar.',
    );
  }

  return [...clase[1].matchAll(/^\s+[A-Z][A-Z0-9_]*\s*=\s*"([a-z][a-z0-9_]*)"/gm)]
    .map(([, codigo]) => codigo)
    .sort();
}

const claves = (diccionario: Record<string, string>, prefijo: string) =>
  Object.keys(diccionario).filter((clave) => clave.startsWith(prefijo));

const marcadores = (texto: string) => [...texto.matchAll(/\{(\w+)\}/g)].map(([, nombre]) => nombre).sort();

describe('traducción de los códigos de WhatsMKT', () => {
  const codigos = codigosDelCatalogo();

  it('lee el catálogo canónico del backend', () => {
    // Un catálogo que dejara de leerse haría pasar en verde todo lo de abajo.
    expect(codigos.length).toBeGreaterThanOrEqual(27);
    expect(codigos).toContain('horario_invalido');
  });

  it.each([
    ['español', es],
    ['inglés', en],
  ])('cada código tiene su texto en %s, y no sobra ninguno', (_idioma, diccionario) => {
    const traducidos = claves(diccionario, PREFIJO).map((clave) => clave.slice(PREFIJO.length)).sort();

    expect(traducidos).toEqual(codigos);
    for (const codigo of codigos) expect((diccionario as Record<string, string>)[`${PREFIJO}${codigo}`].trim()).not.toBe('');
  });

  it('cada código lleva los mismos {parámetros} en los dos idiomas', () => {
    const distintos = codigos.filter((codigo) => {
      const clave = `${PREFIJO}${codigo}`;
      return marcadores((es as Record<string, string>)[clave]).join() !== marcadores((en as Record<string, string>)[clave]).join();
    });

    expect(distintos).toEqual([]);
  });
});

describe('claves de WhatsMKT', () => {
  const prefijos = ['whatsmkt.', 'nav.whatsmkt'];
  const deWhatsmkt = (diccionario: Record<string, string>) =>
    Object.keys(diccionario).filter((clave) => prefijos.some((prefijo) => clave.startsWith(prefijo))).sort();

  it('existen en los dos idiomas', () => {
    expect(deWhatsmkt(en)).toEqual(deWhatsmkt(es));
  });

  it('llevan los mismos {parámetros} en los dos idiomas', () => {
    const distintas = deWhatsmkt(es).filter(
      (clave) => marcadores((es as Record<string, string>)[clave]).join() !== marcadores((en as Record<string, string>)[clave]).join(),
    );

    expect(distintas).toEqual([]);
  });
});
