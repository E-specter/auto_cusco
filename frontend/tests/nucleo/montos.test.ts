/**
 * Amounts. The API sends capital and instalments as text so JSON cannot round
 * them; these tests pin that the interface keeps that promise all the way to
 * the screen.
 */
import { afterEach, describe, expect, it } from 'vitest';

import { formatMonto, formatParticipacion, formatSoles, formatTarifa } from '../../src/lib/format';
import { setLanguageForTests } from './idioma';

afterEach(() => setLanguageForTests('es'));

describe('montos como texto', () => {
  it('agrupa miles y fija dos decimales', () => {
    expect(formatMonto('1234567.5')).toBe('1,234,567.50');
  });

  it('no pierde precisión donde un float sí la pierde', () => {
    // 9007199254740993 no existe como número de JavaScript.
    expect(formatMonto('9007199254740993.01')).toBe('9,007,199,254,740,993.01');
  });

  it('redondea sobre las cifras, con acarreo', () => {
    expect(formatMonto('0.005')).toBe('0.01');
    expect(formatMonto('1.004')).toBe('1.00');
    expect(formatMonto('999.995')).toBe('1,000.00');
  });

  it('los negativos conservan el signo y el cero no lleva signo', () => {
    expect(formatMonto('-1500.2')).toBe('-1,500.20');
    expect(formatMonto('-0.001')).toBe('0.00');
  });

  it('entiende la notación con exponente que puede imprimir Decimal', () => {
    expect(formatMonto('0E-8')).toBe('0.00');
    expect(formatMonto('1.2E+3')).toBe('1,200.00');
  });

  it('un monto ausente se muestra como raya', () => {
    expect(formatMonto(null)).toBe('—');
    expect(formatMonto('')).toBe('—');
  });

  it('un texto que no es monto se muestra tal cual en vez de inventar una cifra', () => {
    expect(formatMonto('n/d')).toBe('n/d');
  });

  it('usa los separadores del idioma de la interfaz', () => {
    setLanguageForTests('en');

    expect(formatMonto('1234.5')).toBe('1,234.50');
  });
});

describe('soles (RF-MM-24)', () => {
  it('un monto en soles lleva el símbolo y siempre dos decimales', () => {
    expect(formatSoles('24691.3')).toBe('S/ 24,691.30');
    expect(formatSoles('0')).toBe('S/ 0.00');
  });

  it('redondea el costo sin pasar por un float', () => {
    expect(formatSoles('9007199254740993.005')).toBe('S/ 9,007,199,254,740,993.01');
  });

  it('un costo ausente es una raya, y un texto que no es monto no gana símbolo', () => {
    expect(formatSoles(null)).toBe('—');
    expect(formatSoles('pendiente')).toBe('pendiente');
  });
});

describe('tarifa (RF-MM-23)', () => {
  it('muestra los decimales que tiene, con un mínimo de dos', () => {
    expect(formatTarifa('0.02')).toBe('S/ 0.02');
    expect(formatTarifa('0.0215')).toBe('S/ 0.0215');
    expect(formatTarifa('0.1')).toBe('S/ 0.10');
  });

  it('no cuenta los ceros que agrega la escala guardada', () => {
    expect(formatTarifa('0.0200')).toBe('S/ 0.02');
    expect(formatTarifa('0.0210')).toBe('S/ 0.021');
  });

  it('nunca muestra más de cuatro decimales', () => {
    expect(formatTarifa('0.021549')).toBe('S/ 0.0215');
  });

  it('una tarifa ausente es una raya', () => {
    expect(formatTarifa(null)).toBe('—');
  });
});

describe('participación', () => {
  it('muestra la parte sobre el total con un decimal', () => {
    expect(formatParticipacion(500, 3200)).toBe('15.6 %');
    expect(formatParticipacion('382.00', '1000.00')).toBe('38.2 %');
  });

  it('sin total no hay participación', () => {
    expect(formatParticipacion(0, 0)).toBe('—');
  });
});
