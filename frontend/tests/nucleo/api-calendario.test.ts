/**
 * The working-day calendar's calls: the method, the path and the JSON body the backend reads.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { crearExcepcion, eliminarExcepcion, listarFeriados, siguienteDiaGestionable } from '../../src/lib/api-calendario';

function responderCon(estado: number, cuerpo: unknown = {}): ReturnType<typeof vi.fn> {
  const falso = vi.fn(async () =>
    estado === 204
      ? new Response(null, { status: 204 })
      : new Response(JSON.stringify(cuerpo), {
          status: estado,
          headers: { 'content-type': 'application/json' },
        }),
  );
  vi.stubGlobal('fetch', falso);
  return falso;
}

const llamada = (falso: ReturnType<typeof vi.fn>) => ({
  url: String(falso.mock.calls[0][0]),
  opciones: (falso.mock.calls[0][1] ?? {}) as RequestInit,
});

const cuerpoDe = (opciones: RequestInit) => JSON.parse(String(opciones.body));

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.unstubAllGlobals());

describe('calendario', () => {
  it('pide los feriados del año indicado', async () => {
    const falso = responderCon(200, { anio: 2099, dias: [] });

    await listarFeriados(2099);

    const url = new URL(llamada(falso).url, 'http://x');
    expect(url.pathname).toBe('/api/calendario/feriados');
    expect(url.searchParams.get('anio')).toBe('2099');
  });

  it('registra una excepción con POST', async () => {
    const falso = responderCon(201, {});
    const entrada = { fecha: '2099-12-24', tipo: 'agregado' as const, descripcion: 'Dia sintetico' };

    await crearExcepcion(entrada);

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/calendario/excepciones');
    expect(opciones.method).toBe('POST');
    expect(cuerpoDe(opciones)).toEqual(entrada);
  });

  it('borra una excepción por su fecha, sin leer cuerpo', async () => {
    const falso = responderCon(204);

    await expect(eliminarExcepcion('2099-07-28')).resolves.toBeUndefined();

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/calendario/excepciones/2099-07-28');
    expect(opciones.method).toBe('DELETE');
  });

  it('el siguiente día gestionable manda `desde` solo si se indica', async () => {
    const sinFecha = responderCon(200, {});
    await siguienteDiaGestionable();
    expect(llamada(sinFecha).url).toBe('/api/calendario/siguiente-dia-gestionable');

    const conFecha = responderCon(200, {});
    await siguienteDiaGestionable('2099-01-02');
    const url = new URL(llamada(conFecha).url, 'http://x');
    expect(url.searchParams.get('desde')).toBe('2099-01-02');
  });
});
