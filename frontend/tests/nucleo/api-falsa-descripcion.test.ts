/**
 * The suggested description the fake API builds (RF-MM-04, T-MM-B10): the specs trust it to shorten like
 * the backend does, so it is checked on its own. Every text is synthetic.
 */
import { describe, expect, it } from 'vitest';

import { acortarDescripcion } from '../../e2e/api-falsa-mowa-mes';

describe('la descripción sugerida de la API falsa se acorta como la del backend', () => {
  it('si cabe en 100, va completa', () => {
    expect(acortarDescripcion('CajaCusco', ['9 <= dias atraso <= 30'])).toBe('CajaCusco 9 <= dias atraso <= 30');
  });

  it('exactamente 100 cabe', () => {
    const filtro = 'f'.repeat(100 - 'CajaCusco '.length);
    const texto = acortarDescripcion('CajaCusco', [filtro]);
    expect(texto).toHaveLength(100);
    expect(texto.endsWith('...')).toBe(false);
  });

  it('si pasa, quita filtros enteros desde el final y cierra con «...», sin pasar de 100', () => {
    const filtros = ['filtro uno de prueba', 'filtro dos de prueba', 'filtro tres de prueba', 'filtro cuatro de prueba', 'filtro cinco de prueba'];
    const texto = acortarDescripcion('CajaCusco', filtros);
    expect(texto).toBe('CajaCusco filtro uno de prueba, filtro dos de prueba, filtro tres de prueba...');
    // Con el cuarto filtro serían 103: no cabe, y no se corta a la mitad.
    expect(texto.length).toBeLessThanOrEqual(100);
    // Cada filtro que queda está entero.
    expect(texto.replace(/^CajaCusco /, '').replace(/\.\.\.$/, '').split(', ').every((f) => filtros.includes(f))).toBe(true);
  });

  it('si ni el primero cabe, 97 caracteres y «...»', () => {
    const texto = acortarDescripcion('CajaCusco', ['x'.repeat(200), 'otro']);
    expect(texto).toHaveLength(100);
    expect(texto.endsWith('...')).toBe(true);
    expect(texto.startsWith('CajaCusco xxxx')).toBe(true);
  });

  it('un emoji cuenta 2 al medir', () => {
    // 'CajaCusco ' (10) + 88 letras + 😀 (2) = 100: cabe; con una letra más pasa.
    expect(acortarDescripcion('CajaCusco', [`${'a'.repeat(88)}😀`])).toHaveLength(100);
    expect(acortarDescripcion('CajaCusco', [`${'a'.repeat(89)}😀`]).endsWith('...')).toBe(true);
  });
});
