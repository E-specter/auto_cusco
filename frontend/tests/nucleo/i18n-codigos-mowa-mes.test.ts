/**
 * Contract between the MOWA MES code catalogue and the interface dictionaries.
 *
 * Exclusions, warnings and preview problems arrive as a `codigo`, which the
 * screens translate under `mowaMes.codigo.<codigo>`. The backend has its own
 * test that every code has a key; this one reads the backend's enum and adds
 * the direction that test does not cover: keys left behind for codes that no
 * longer exist. It also keeps every `mowaMes.*` key present in both languages.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import es from '../../src/i18n/es.json';
import en from '../../src/i18n/en.json';

// fileURLToPath, not URL.pathname: the repo path contains a space.
const CATALOGO = fileURLToPath(
  new URL('../../../backend/app/core/entities/mowa_mes.py', import.meta.url),
);

const PREFIJO = 'mowaMes.codigo.';

/** The values of `class CodigoMowaMes(StrEnum)`, one `NOMBRE = "codigo"` per line. */
function codigosDelCatalogo(): string[] {
  const fuente = readFileSync(CATALOGO, 'utf8');
  const clase = fuente.match(/class CodigoMowaMes\(StrEnum\):([\s\S]*?)(?=\n\S)/);

  if (!clase) {
    throw new Error(
      `No se encontró la clase CodigoMowaMes en ${CATALOGO}. Si el backend la movió o la renombró, ` +
        'esta prueba debe seguirla: dejarla pasar en verde sería peor que fallar.',
    );
  }

  return [...clase[1].matchAll(/^\s+[A-Z][A-Z0-9_]*\s*=\s*"([a-z][a-z0-9_]*)"/gm)]
    .map(([, codigo]) => codigo)
    .sort();
}

const clavesCon = (diccionario: Record<string, string>, prefijo: string) =>
  Object.keys(diccionario).filter((clave) => clave.startsWith(prefijo));

describe('traducción de códigos de MOWA MES', () => {
  const codigos = codigosDelCatalogo();

  it('lee el catálogo canónico del backend', () => {
    // Un catálogo que dejara de leerse haría pasar en verde todo lo de abajo.
    expect(codigos.length).toBeGreaterThanOrEqual(8);
    expect(codigos).toContain('telefono_invalido');
    expect(codigos).toContain('mensaje_excede_160');
    expect(codigos).toContain('limite_mensual_excedido');
  });

  it('no lista el mismo código dos veces', () => {
    expect(codigos).toEqual([...new Set(codigos)]);
  });

  it.each(codigosDelCatalogo())('traduce %s al español', (codigo) => {
    expect(es).toHaveProperty([`${PREFIJO}${codigo}`]);
  });

  it.each(codigosDelCatalogo())('traduce %s al inglés', (codigo) => {
    expect(en).toHaveProperty([`${PREFIJO}${codigo}`]);
  });

  it('no conserva traducciones de códigos que el catálogo ya no incluye', () => {
    const sobrantes = clavesCon(es, PREFIJO)
      .map((clave) => clave.slice(PREFIJO.length))
      .filter((codigo) => !codigos.includes(codigo));
    expect(sobrantes).toEqual([]);
  });

  it('cada clave del módulo existe en los dos idiomas', () => {
    const soloEs = clavesCon(es, 'mowaMes.').filter((clave) => !(clave in en));
    const soloEn = clavesCon(en, 'mowaMes.').filter((clave) => !(clave in es));
    expect({ soloEs, soloEn }).toEqual({ soloEs: [], soloEn: [] });
  });
});
