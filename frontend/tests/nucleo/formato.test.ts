/**
 * Formatting and the cut-off date guessed from a file name.
 *
 * The guess is the one place the interface puts a value in front of the
 * analyst that nobody typed, so it has to be right or visibly absent — never
 * confidently wrong.
 */
import { describe, expect, it } from 'vitest';

import {
  formatDateCompact,
  formatDateTime,
  guessDateFromFilename,
  parseApiDate,
  toApiDate,
} from '../../src/lib/format';

describe('fecha de corte sugerida desde el nombre del archivo', () => {
  it('la toma del patrón DD.MM.YYYY que usa la entidad', () => {
    expect(guessDateFromFilename('SABANA_10.09.2026.xlsx')).toBe('2026-09-10');
  });

  it('la encuentra en un nombre con espacios y un guion separador', () => {
    // Caso real del archivo sintético de prueba: el guion que separa el
    // rótulo de la fecha no debe confundirse con un separador de la fecha.
    expect(guessDateFromFilename('SINTETICA DE PRUEBA - 26.09.2026.xlsb')).toBe('2026-09-26');
  });

  it('acepta guion, guion bajo y barra como separadores', () => {
    expect(guessDateFromFilename('corte 01-02-2026.xlsb')).toBe('2026-02-01');
    expect(guessDateFromFilename('corte 01_02_2026.xlsb')).toBe('2026-02-01');
    expect(guessDateFromFilename('corte 01/02/2026.xlsb')).toBe('2026-02-01');
  });

  it('interpreta un año de dos dígitos como del siglo actual', () => {
    expect(guessDateFromFilename('corte 05.03.26.xlsx')).toBe('2026-03-05');
  });

  it('no sugiere nada cuando el nombre no lleva fecha', () => {
    expect(guessDateFromFilename('asignacion_impulse.xlsb')).toBeNull();
  });

  it('rechaza un día que no existe en ese mes en vez de correrlo al siguiente', () => {
    // El constructor Date acepta 31.02 y devuelve el 3 de marzo. Sugerir una
    // fecha que el usuario no escribió y que no está en el nombre sería peor
    // que no sugerir nada.
    expect(guessDateFromFilename('corte 31.02.2026.xlsx')).toBeNull();
  });

  it('rechaza un mes fuera de rango', () => {
    expect(guessDateFromFilename('corte 10.13.2026.xlsx')).toBeNull();
  });
});

describe('fechas de la API', () => {
  it('lee YYYY-MM-DD como fecha local y no como medianoche UTC', () => {
    // Interpretarla en UTC adelanta o atrasa el día según la zona horaria, y
    // en Lima (UTC-5) mostraría siempre el día anterior.
    const fecha = parseApiDate('2026-09-10');

    expect(fecha.getFullYear()).toBe(2026);
    expect(fecha.getMonth()).toBe(8);
    expect(fecha.getDate()).toBe(10);
  });

  it('vuelve a texto sin perder el día', () => {
    expect(toApiDate(parseApiDate('2026-01-05'))).toBe('2026-01-05');
  });

  it('escribe el sello compacto con día, mes y año', () => {
    expect(formatDateCompact('2026-09-08')).toBe('08.09.2026');
  });

  it('escribe la marca de tiempo como sello y no como frase', () => {
    // Intl en es-PE devuelve "10-set.," para el mes corto, que en una columna
    // monoespaciada se lee como un defecto.
    const marca = formatDateTime('2026-09-10T14:32:07');

    expect(marca).toBe('10.09 · 14:32');
  });
});
