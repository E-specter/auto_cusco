/**
 * Contract between the portfolio's field catalogue and the field labels.
 *
 * The backend lists the queryable fields by their technical name
 * (`/cartera/campos`, and the rich-text catalogue with `clave_nombre: null`);
 * the label each screen shows lives in `campo.<nombre>`. Nothing ties the two:
 * a field added to the sheet would reach the interface as
 * `valor cierre mes anterior`, in Spanish, inside an English screen. This test
 * is what complains.
 *
 * It reads the backend's canonical source, `CATALOGO_VENCIDA`, and applies the
 * same rules `seleccion_cartera/campos.py` applies to turn sheet columns into
 * queryable fields. If those rules change, this test needs the same change:
 * it fails loudly in the meantime rather than passing on a stale list.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import en from '../../src/i18n/en.json';
import es from '../../src/i18n/es.json';

const desdeAqui = (ruta: string) => fileURLToPath(new URL(ruta, import.meta.url));
const CATALOGO = desdeAqui('../../../backend/app/core/services/ingesta_sabana/catalogo.py');
const CAMPOS = desdeAqui('../../../backend/app/core/services/seleccion_cartera/campos.py');

const PREFIJO = 'campo.';

/**
 * The queryable fields, derived like `_construir_campos`: columns without a
 * value and the discarded duplicate key are left out; a document splits into
 * type and number; an operational maturity into "applies" and date.
 */
function columnasDelCatalogo(): Array<{ nombre: string; tipo: string }> {
  const fuente = readFileSync(CATALOGO, 'utf8');
  const columnas = [...fuente.matchAll(/^\s*_col\("([a-z_]+)",\s*T\.([A-Z_]+)/gm)].map(([, nombre, tipo]) => ({ nombre, tipo }));
  if (columnas.length < 20) {
    throw new Error(`Solo se leyeron ${columnas.length} columnas de ${CATALOGO}: ¿cambió su forma?`);
  }
  return columnas;
}

function camposDelCatalogo(): string[] {
  const columnas = columnasDelCatalogo();

  // The rules live in campos.py; if they stop matching what is applied here,
  // the test must be updated rather than silently trusted.
  const reglas = readFileSync(CAMPOS, 'utf8');
  for (const pista of ['_FUERA_DE_CONSULTA = frozenset({"pagare_duplicado"})', 'TipoCampo.SIN_VALOR', '_tipo"', '_numero"', '_aplica"', '_fecha"']) {
    if (!reglas.includes(pista)) {
      throw new Error(`campos.py ya no contiene ${pista}: revisa cómo se derivan los campos y actualiza esta prueba`);
    }
  }

  return columnas.flatMap(({ nombre, tipo }) => {
    if (tipo === 'SIN_VALOR' || nombre === 'pagare_duplicado') return [];
    if (tipo === 'DOCUMENTO') return [`${nombre}_tipo`, `${nombre}_numero`];
    if (tipo === 'VENCIMIENTO_OPERATIVO') return [`${nombre}_aplica`, `${nombre}_fecha`];
    return [nombre];
  });
}

const etiquetasDe = (diccionario: Record<string, string>) =>
  Object.keys(diccionario).filter((clave) => clave.startsWith(PREFIJO)).map((clave) => clave.slice(PREFIJO.length));

describe('etiquetas de los campos de la cartera', () => {
  const campos = camposDelCatalogo();
  // The header mapper lists every sheet column as it comes (CATALOGO_SABANA), split or not (M-9).
  const columnas = columnasDelCatalogo().map((c) => c.nombre);

  it.each([
    ['español', es],
    ['inglés', en],
  ])('cada columna de la sábana, la que lista el mapeador, tiene su etiqueta en %s', (_idioma, diccionario) => {
    const faltan = columnas.filter((columna) => !(`${PREFIJO}${columna}` in diccionario));

    expect(faltan).toEqual([]);
  });

  it.each([
    ['español', es],
    ['inglés', en],
  ])('cada campo consultable tiene su etiqueta en %s', (_idioma, diccionario) => {
    const faltan = campos.filter((campo) => !(`${PREFIJO}${campo}` in diccionario));

    expect(faltan).toEqual([]);
  });

  it.each([
    ['español', es],
    ['inglés', en],
  ])('no sobran etiquetas de campos que ya no existen en %s', (_idioma, diccionario) => {
    const sobran = etiquetasDe(diccionario).filter((campo) => !campos.includes(campo) && !columnas.includes(campo));

    expect(sobran).toEqual([]);
  });

  it('ninguna etiqueta está vacía ni repite el nombre técnico', () => {
    const malas = [...etiquetasDe(es).map((c) => es[`${PREFIJO}${c}` as keyof typeof es]), ...etiquetasDe(en).map((c) => en[`${PREFIJO}${c}` as keyof typeof en])]
      .filter((texto) => !texto || /_/.test(texto));

    expect(malas).toEqual([]);
  });
});
