/**
 * The WhatsMKT configuration calls. What is worth pinning is what the backend reads: the method, the
 * path, JSON bodies (a partial PUT sends only what the panel owns), and that a refusal reaches the screen
 * as an ApiError carrying the code and the parameters the text needs.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../src/lib/api';
import {
  guardarConfiguracion,
  guardarSegmentos,
  listarSegmentos,
  obtenerConfiguracion,
} from '../../src/lib/api-whatsmkt';
import { errorDeModulo } from '../../src/lib/whatsmkt';

function responderCon(estado: number, cuerpo: unknown = {}): ReturnType<typeof vi.fn> {
  const falso = vi.fn(
    async () =>
      new Response(JSON.stringify(cuerpo), { status: estado, headers: { 'content-type': 'application/json' } }),
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

describe('configuración', () => {
  it('lee con GET', async () => {
    const falso = responderCon(200, { tope_mensaje: 4096 });

    await expect(obtenerConfiguracion()).resolves.toEqual({ tope_mensaje: 4096 });

    expect(llamada(falso).url).toBe('/api/whatsmkt/configuracion');
    expect(llamada(falso).opciones.method).toBeUndefined();
  });

  it('guarda con PUT y manda solo lo del panel: lo omitido se conserva', async () => {
    const falso = responderCon(200, {});

    await guardarConfiguracion({ tope_video: 20_000_000, tope_audio: 20_000_000, tope_pdf: 20_000_000, tope_mensaje: 4096 });

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/whatsmkt/configuracion');
    expect(opciones.method).toBe('PUT');
    expect(cuerpoDe(opciones)).toEqual({ tope_video: 20_000_000, tope_audio: 20_000_000, tope_pdf: 20_000_000, tope_mensaje: 4096 });
  });

  it('un horario inválido llega como ApiError con su código y las franjas que fallan', async () => {
    responderCon(422, { detail: 'x', codigo: 'horario_invalido', horarios: ['horario_2'], variable: null, segmento: null, fila: null, desde: null, hasta: null });

    const error = await guardarConfiguracion({ horario_2: { inicio: '20:00', fin: '14:00' } }).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(errorDeModulo(error)).toMatchObject({ codigo: 'horario_invalido', horarios: ['horario_2'] });
  });
});

describe('segmentos', () => {
  it('lista con GET', async () => {
    const falso = responderCon(200, []);

    await listarSegmentos();

    expect(llamada(falso).url).toBe('/api/whatsmkt/segmentos');
  });

  it('reemplaza con PUT y el cuerpo es la lista de los tres', async () => {
    const falso = responderCon(200, []);
    const entrada = [
      { clave: 'preventivo', etiqueta: 'Preventivo', desde: null, hasta: 0 },
      { clave: 'tramo_2', etiqueta: 'Tramo 2', desde: 1, hasta: 8 },
      { clave: 'mayores_2', etiqueta: 'Tramos mayores al 2', desde: 9, hasta: null },
    ];

    await guardarSegmentos(entrada);

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/whatsmkt/segmentos');
    expect(opciones.method).toBe('PUT');
    expect(cuerpoDe(opciones)).toEqual(entrada);
  });

  it('un hueco llega como ApiError con los días que quedan sin segmento', async () => {
    responderCon(422, { detail: 'x', codigo: 'segmentos_con_hueco', horarios: null, variable: null, segmento: null, fila: null, desde: 3, hasta: 5 });

    const error = await guardarSegmentos([]).catch((e: unknown) => e);

    expect(errorDeModulo(error)).toMatchObject({ codigo: 'segmentos_con_hueco', desde: 3, hasta: 5 });
  });
});
