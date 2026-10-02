/**
 * Contract between the rich-text engine's code catalogue and the interface dictionaries.
 *
 * Problems from the engine (validation, preview, 404s) arrive as a `codigo`, which the screens
 * translate under `textoEnriquecido.codigo.<codigo>`. The backend has its own test that every
 * key it can send exists (`test_i18n_texto_enriquecido.py`, which also covers functions,
 * parameters, families and contexts); this one reads the backend's enum and covers the part
 * that lives in the frontend: no key left behind for a code that no longer exists, and both
 * languages in step.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import es from '../../src/i18n/es.json';
import en from '../../src/i18n/en.json';

// fileURLToPath, not URL.pathname: the repo path contains a space.
const CATALOGO = fileURLToPath(
  new URL('../../../backend/app/core/entities/texto_enriquecido.py', import.meta.url),
);

const PREFIJO = 'textoEnriquecido.codigo.';

/** The values of `class CodigoTexto(StrEnum)`, one `NOMBRE = "codigo"` per line (a trailing `# comment` is allowed). */
function codigosDelCatalogo(): string[] {
  const fuente = readFileSync(CATALOGO, 'utf8');
  const clase = fuente.match(/class CodigoTexto\(StrEnum\):([\s\S]*?)(?=\n\S)/);

  if (!clase) {
    throw new Error(
      `No se encontró la clase CodigoTexto en ${CATALOGO}. Si el backend la movió o la renombró, ` +
        'esta prueba debe seguirla: dejarla pasar en verde sería peor que fallar.',
    );
  }

  return [...clase[1].matchAll(/^\s+[A-Z][A-Z0-9_]*\s*=\s*"([a-z][a-z0-9_]*)"/gm)]
    .map(([, codigo]) => codigo)
    .sort();
}

const clavesCon = (diccionario: Record<string, string>, prefijo: string) =>
  Object.keys(diccionario).filter((clave) => clave.startsWith(prefijo));

describe('traducción de códigos del motor de texto enriquecido', () => {
  const codigos = codigosDelCatalogo();

  it('lee el catálogo canónico del backend', () => {
    // Un catálogo que dejara de leerse haría pasar en verde todo lo de abajo.
    expect(codigos.length).toBeGreaterThanOrEqual(24);
    expect(codigos).toContain('expresion_invalida');
    expect(codigos).toContain('variable_desconocida');
    expect(codigos).toContain('sin_version_vigente');
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

  it('cada clave del motor existe en los dos idiomas', () => {
    const soloEs = clavesCon(es, 'textoEnriquecido.').filter((clave) => !(clave in en));
    const soloEn = clavesCon(en, 'textoEnriquecido.').filter((clave) => !(clave in es));
    expect({ soloEs, soloEn }).toEqual({ soloEs: [], soloEn: [] });
  });
});
