/**
 * Field and variable names on screen. A portfolio field shows its label; a
 * context variable shows the context's own key; anything without a label
 * falls back to its technical name with spaces instead of a raw key.
 */
import { afterEach, describe, expect, it } from 'vitest';

import { etiquetaCampo, etiquetaVariable, humanizarNombre, ordenarPorEtiqueta } from '../../src/lib/campos';
import { setLanguageForTests } from './idioma';

afterEach(() => setLanguageForTests('es'));

describe('etiqueta de un campo', () => {
  it('usa la etiqueta del diccionario en el idioma de la interfaz', () => {
    expect(etiquetaCampo('saldo_capital_pendiente')).toBe('Saldo de capital pendiente');

    setLanguageForTests('en');

    expect(etiquetaCampo('saldo_capital_pendiente')).toBe('Outstanding principal');
  });

  it('un campo sin etiqueta muestra su nombre técnico con espacios, nunca la clave', () => {
    expect(etiquetaCampo('campo_nuevo_sin_etiqueta')).toBe('campo nuevo sin etiqueta');
    expect(humanizarNombre('a_b')).toBe('a b');
  });
});

describe('etiqueta de una variable del catálogo', () => {
  it('una variable de contexto usa su propia clave', () => {
    expect(etiquetaVariable({ nombre: 'whatsapp_contacto', clave_nombre: 'textoEnriquecido.variable.whatsapp_contacto' })).toBe(
      'WhatsApp de contacto',
    );
  });

  it('un campo de la cartera, sin clave propia, usa la etiqueta del campo', () => {
    expect(etiquetaVariable({ nombre: 'titular', clave_nombre: null })).toBe('Titular');
  });

  it('una clave que el diccionario no conoce cae a la etiqueta del campo', () => {
    expect(etiquetaVariable({ nombre: 'titular', clave_nombre: 'textoEnriquecido.variable.inexistente' })).toBe('Titular');
  });
});

describe('orden de lectura', () => {
  it('ordena por la etiqueta visible, no por el nombre técnico', () => {
    expect(ordenarPorEtiqueta(['pagare', 'dias_atraso', 'agencia'])).toEqual(['agencia', 'dias_atraso', 'pagare']);
    expect(ordenarPorEtiqueta(['titular', 'saldo_capital_pendiente'])).toEqual(['saldo_capital_pendiente', 'titular']);
  });
});
