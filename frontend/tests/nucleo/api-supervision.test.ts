/**
 * The default supervisors' calls: the method, the path and the JSON body the backend reads.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { guardarSupervision } from '../../src/lib/api-supervision';

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

describe('supervisores', () => {
  it('reemplaza la lista completa con PUT', async () => {
    const falso = responderCon(200, { procedencias: [], supervisores: [] });
    const entrada = {
      procedencias: ['Procedencia A'],
      supervisores: [{ numero: '900000101', procedencia: 'Procedencia A' }],
    };

    await guardarSupervision(entrada);

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/supervisores');
    expect(opciones.method).toBe('PUT');
    expect(cuerpoDe(opciones)).toEqual(entrada);
  });
});
