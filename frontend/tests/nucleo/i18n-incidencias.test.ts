/**
 * Contract between the ingestion catalogue and the interface's dictionaries.
 *
 * The API writes each issue's `detalle` in Spanish, so the console translates
 * by `codigo` instead. That coupling is invisible from either side: adding a
 * code in the backend leaves a Spanish sentence sitting inside an English
 * table, and nothing complains. This test is the thing that complains.
 *
 * It reads the backend's canonical catalogue rather than a copy kept here, so
 * it fails when the catalogue grows a code the dictionaries do not know.
 *
 * The other half of the chain lives in the backend: its own test fails if the
 * ingestion emits a code the catalogue does not list, or if the catalogue
 * lists one nobody emits any more. Between the two, neither side has to read
 * the other's source — only this one shared list.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import es from '../../src/i18n/es.json';
import en from '../../src/i18n/en.json';

// fileURLToPath, not URL.pathname: the repo path contains a space, and
// pathname would hand back a percent-encoded string that fs cannot open.
const CATALOGO = fileURLToPath(
  new URL('../../../backend/app/core/entities/incidencias.py', import.meta.url),
);

const PREFIJO = 'incidencia.';

/**
 * The codes listed in `CODIGOS_INCIDENCIA`.
 *
 * Only the literals inside that constant are read, so a docstring mentioning
 * a code in prose cannot smuggle one in.
 */
function codigosDelCatalogo(): string[] {
  const fuente = readFileSync(CATALOGO, 'utf8');
  const constante = fuente.match(/CODIGOS_INCIDENCIA[^=]*=\s*frozenset\(\s*\{([\s\S]*?)\}\s*\)/);

  if (!constante) {
    throw new Error(
      `No se encontró CODIGOS_INCIDENCIA en ${CATALOGO}. Si el backend la movió o la renombró, ` +
        'esta prueba debe seguirla: dejarla pasar en verde sería peor que fallar.',
    );
  }

  return [...constante[1].matchAll(/"([a-z][a-z0-9_]*)"/g)].map(([, codigo]) => codigo).sort();
}

describe('traducción de incidencias por código', () => {
  const codigos = codigosDelCatalogo();

  it('lee el catálogo canónico del backend', () => {
    // Sin esta comprobación, un catálogo que dejara de leerse haría pasar en
    // verde las pruebas de abajo sin comprobar nada.
    expect(codigos.length).toBeGreaterThanOrEqual(20);
    expect(codigos).toContain('pagare_repetido');
    expect(codigos).toContain('cabecera_duplicada');
    expect(codigos).toContain('dni_completado_con_ceros');
  });

  it('no lista el mismo código dos veces', () => {
    expect(codigos).toEqual([...new Set(codigos)]);
  });

  it.each(codigosDelCatalogo())('traduce %s al español', (codigo) => {
    expect(es).toHaveProperty(`${PREFIJO}${codigo}`);
  });

  it.each(codigosDelCatalogo())('traduce %s al inglés', (codigo) => {
    expect(en).toHaveProperty(`${PREFIJO}${codigo}`);
  });

  it('no conserva traducciones de códigos que el catálogo ya no incluye', () => {
    // Esta es la dirección que la prueba del backend no cubre: allí se
    // comprueba lo que se emite contra el catálogo, aquí el diccionario.
    const traducidos = Object.keys(es)
      .filter((clave) => clave.startsWith(PREFIJO))
      .map((clave) => clave.slice(PREFIJO.length));

    expect(traducidos.filter((codigo) => !codigos.includes(codigo))).toEqual([]);
  });

  it('traduce cada código en los dos idiomas o en ninguno', () => {
    const soloEs = Object.keys(es).filter((c) => c.startsWith(PREFIJO) && !(c in en));
    const soloEn = Object.keys(en).filter((c) => c.startsWith(PREFIJO) && !(c in es));

    expect({ soloEs, soloEn }).toEqual({ soloEs: [], soloEn: [] });
  });
});
