/**
 * The two calls the v2 speech adds to the MOWA MES client: the draft a v1 becomes (read-only, it
 * saves nothing) and the problems a refused save carries.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../src/lib/api';
import { obtenerComoV2, problemasDeErrorSpeech } from '../../src/lib/api-speech-v2';

function responderCon(estado: number, cuerpo: unknown = {}): ReturnType<typeof vi.fn> {
  const falso = vi.fn(
    async () =>
      new Response(JSON.stringify(cuerpo), { status: estado, headers: { 'content-type': 'application/json' } }),
  );
  vi.stubGlobal('fetch', falso);
  return falso;
}

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.unstubAllGlobals());

const PROBLEMA = {
  segmento: '9_a_30',
  campo: 'expresion',
  detalle: 'x',
  codigo: 'variable_desconocida',
  catalogo: 'texto',
  ubicacion: { nodo: 1, funcion: null, parametro: null },
};

describe('el borrador v2 de una v1', () => {
  it('se pide con GET a /como-v2 y no guarda nada', async () => {
    const falso = responderCon(200, { basada_en_id: 1, nombre_sugerido: 'Speech 2', expresiones: [], problemas: [] });

    const borrador = await obtenerComoV2(1);

    expect(String(falso.mock.calls[0][0])).toBe('/api/mowa-mes/speech/1/como-v2');
    expect(((falso.mock.calls[0][1] ?? {}) as RequestInit).method ?? 'GET').toBe('GET');
    expect(borrador.nombre_sugerido).toBe('Speech 2');
  });

  it('una versión que ya es v2 responde 400 con su motivo', async () => {
    responderCon(400, {
      detail: 'La version ya es v2',
      problemas: [{ ...PROBLEMA, campo: 'formato', segmento: null, codigo: null, catalogo: null, ubicacion: null }],
    });

    const fallo = await obtenerComoV2(5).catch((e: unknown) => e);

    expect(fallo).toBeInstanceOf(ApiError);
    expect((fallo as ApiError).status).toBe(400);
  });

  it('pasa la señal para cancelar el pedido', async () => {
    const falso = responderCon(200, { basada_en_id: 1, nombre_sugerido: '', expresiones: [], problemas: [] });
    const control = new AbortController();

    await obtenerComoV2(1, control.signal);

    expect(((falso.mock.calls[0][1] ?? {}) as RequestInit).signal).toBe(control.signal);
  });
});

describe('los problemas de un guardado rechazado', () => {
  it('se leen del cuerpo del 400, con su segmento, su campo y su catálogo', async () => {
    responderCon(400, { detail: 'No se guarda', problemas: [PROBLEMA] });
    const fallo = await obtenerComoV2(1).catch((e: unknown) => e);

    expect(problemasDeErrorSpeech(fallo)).toEqual([PROBLEMA]);
  });

  it('lo que no tiene forma de problema se descarta, y lo que no es una lista no se inventa', () => {
    const conCuerpo = (cuerpo: Record<string, unknown> | null) => new ApiError(400, 'x', null, cuerpo);

    expect(problemasDeErrorSpeech(conCuerpo(null))).toEqual([]);
    expect(problemasDeErrorSpeech(conCuerpo({ problemas: 'texto' }))).toEqual([]);
    expect(problemasDeErrorSpeech(conCuerpo({ problemas: [{ sin: 'forma' }, PROBLEMA] }))).toEqual([PROBLEMA]);
    expect(problemasDeErrorSpeech(new Error('otra cosa'))).toEqual([]);
    expect(problemasDeErrorSpeech(undefined)).toEqual([]);
  });
});
