/**
 * Copying to the clipboard: the order of the attempts. Moved with the function out of the campaign's logic
 * (it has its second user now: the data to upload to MES).
 */
import { describe, expect, it } from 'vitest';

import { copiarConRespaldo } from '../../src/lib/portapapeles';

describe('copiar con respaldo: el orden de los intentos', () => {
  const sinEscribir = () => Promise.reject(new Error('negado'));

  it('con el portapapeles bien, no se llama al respaldo', async () => {
    const escritos: string[] = [];
    let respaldos = 0;
    const resultado = await copiarConRespaldo('hola', {
      escribir: async (t) => void escritos.push(t),
      seleccionarYCopiar: () => (respaldos++, true),
    });
    expect(resultado).toBe('portapapeles');
    expect(escritos).toEqual(['hola']);
    expect(respaldos).toBe(0);
  });

  it('sin portapapeles y con el respaldo en true, copia con el respaldo', async () => {
    let respaldos = 0;
    const resultado = await copiarConRespaldo('hola', { seleccionarYCopiar: () => (respaldos++, true) });
    expect(resultado).toBe('respaldo');
    expect(respaldos).toBe(1);
  });

  it('con el portapapeles rechazado y el respaldo en true, copia con el respaldo', async () => {
    let respaldos = 0;
    const resultado = await copiarConRespaldo('hola', {
      escribir: sinEscribir,
      seleccionarYCopiar: () => (respaldos++, true),
    });
    expect(resultado).toBe('respaldo');
    expect(respaldos).toBe(1);
  });

  it('con el respaldo en false, es un fallo', async () => {
    expect(await copiarConRespaldo('hola', { escribir: sinEscribir, seleccionarYCopiar: () => false })).toBe('fallo');
    expect(await copiarConRespaldo('hola', { seleccionarYCopiar: () => false })).toBe('fallo');
  });

  it('con un respaldo que lanza, es un fallo y no una excepción', async () => {
    const lanza = () => {
      throw new Error('execCommand no existe');
    };
    expect(await copiarConRespaldo('hola', { escribir: sinEscribir, seleccionarYCopiar: lanza })).toBe('fallo');
    expect(await copiarConRespaldo('hola', { seleccionarYCopiar: lanza })).toBe('fallo');
  });

  it('un portapapeles que lanza de forma síncrona también cae al respaldo', async () => {
    const resultado = await copiarConRespaldo('hola', {
      escribir: () => {
        throw new Error('sin permiso');
      },
      seleccionarYCopiar: () => true,
    });
    expect(resultado).toBe('respaldo');
  });
});
