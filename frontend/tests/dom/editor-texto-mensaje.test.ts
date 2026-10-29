/**
 * The editor's problem message: the engine's text for a code it knows, and the backend's own sentence
 * for one this build lacks (the fallback `traducirPorPrefijo` must keep).
 */
import { describe, expect, it } from 'vitest';

import { t } from '../../src/lib/i18n';
import { mensajeProblema } from '../../src/scripts/editor-texto';

describe('mensajeProblema', () => {
  it('un código conocido: el texto del diccionario', () => {
    expect(mensajeProblema({ codigo: 'sintaxis_invalida', detalle: 'respaldo' })).toBe(
      t('textoEnriquecido.codigo.sintaxis_invalida'),
    );
  });

  it('un código desconocido: el detalle del servidor, no la clave', () => {
    expect(mensajeProblema({ codigo: 'codigo_inventado', detalle: 'La frase del servidor' })).toBe(
      'La frase del servidor',
    );
  });
});
