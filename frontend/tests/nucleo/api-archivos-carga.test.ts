/**
 * The load-file calls. What is worth pinning is what the backend reads (method, path, the JSON body
 * as given) and what the screen reads back: the download's name and `X-Carga-*` summary, and a
 * refusal as an ApiError. Aborting must reach `fetch`, because the screen's Cancel depends on it.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, NetworkError } from '../../src/lib/api';
import { PREFIJO_RESUMEN_CARGA, generarCarga, listarFormatos, previsualizarCarga } from '../../src/lib/api-archivos-carga';
import type { PeticionGeneracion } from '../../src/lib/generar-carga';

const PETICION: PeticionGeneracion = {
  fecha_corte: '2026-09-10',
  definicion_guardada: { id: 7, version: 2 },
  formato: 'csv',
  filtros: ['telefono:no_vacio'],
  orden: '-saldo_capital_pendiente',
  cantidad: 500,
};

function responder(respuesta: Response): ReturnType<typeof vi.fn> {
  const falso = vi.fn(async () => respuesta);
  vi.stubGlobal('fetch', falso);
  return falso;
}

const json = (estado: number, cuerpo: unknown) =>
  new Response(JSON.stringify(cuerpo), { status: estado, headers: { 'content-type': 'application/json' } });

const llamada = (falso: ReturnType<typeof vi.fn>) => ({
  url: String(falso.mock.calls[0][0]),
  opciones: (falso.mock.calls[0][1] ?? {}) as RequestInit,
});

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.unstubAllGlobals());

describe('listarFormatos', () => {
  it('pide los formatos con GET', async () => {
    const falso = responder(json(200, []));
    await expect(listarFormatos()).resolves.toEqual([]);
    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/archivos-carga/formatos');
    expect(opciones.method ?? 'GET').toBe('GET');
  });
});

describe('previsualizarCarga', () => {
  it('envía la petición tal cual, por POST y como JSON', async () => {
    const falso = responder(json(200, { filas: [] }));
    await previsualizarCarga(PETICION);
    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/archivos-carga/previsualizacion');
    expect(opciones.method).toBe('POST');
    expect((opciones.headers as Record<string, string>)['content-type']).toBe('application/json');
    expect(JSON.parse(String(opciones.body))).toEqual(PETICION);
  });

  it('un rechazo llega como ApiError con el motivo y el código del servidor', async () => {
    responder(json(404, { detail: 'No hay versión vigente', codigo: 'sin_version_vigente' }));
    const error = await previsualizarCarga(PETICION).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, detail: 'No hay versión vigente', codigo: 'sin_version_vigente' });
  });

  it('sin red es un NetworkError', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('failed'))));
    await expect(previsualizarCarga(PETICION)).rejects.toBeInstanceOf(NetworkError);
  });

  it('pasa la señal para poder cancelar y el aborto no se confunde con una red caída', async () => {
    const controlador = new AbortController();
    const falso = vi.fn(async (_url: string, _init?: RequestInit) => {
      controlador.abort();
      throw new DOMException('abortada', 'AbortError');
    });
    vi.stubGlobal('fetch', falso);
    const error = await previsualizarCarga(PETICION, controlador.signal).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(DOMException);
    expect((error as DOMException).name).toBe('AbortError');
    expect(falso.mock.calls[0][1]?.signal).toBe(controlador.signal);
  });
});

describe('generarCarga', () => {
  const archivo = () =>
    new Response('a,b\r\n1,2\r\n', {
      status: 200,
      headers: {
        'content-type': 'text/csv',
        'content-disposition': 'attachment; filename="sms_preventivo.csv"',
        'x-carga-generados': '500',
        'x-carga-disponibles': '3200',
        'x-carga-solicitados': '500',
        'x-carga-suficiente': '1',
        'x-carga-errores': '0',
        'x-carga-excluidos': '3',
        'x-otra': 'no',
      },
    });

  it('envía la misma petición a /archivos-carga', async () => {
    const falso = responder(archivo());
    await generarCarga(PETICION);
    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/archivos-carga');
    expect(opciones.method).toBe('POST');
    expect(JSON.parse(String(opciones.body))).toEqual(PETICION);
  });

  it('devuelve el archivo, su nombre y el resumen sin el prefijo, solo con las cabeceras de la carga', async () => {
    responder(archivo());
    const descargado = await generarCarga(PETICION);
    expect(await descargado.blob.text()).toBe('a,b\r\n1,2\r\n');
    expect(descargado.nombre).toBe('sms_preventivo.csv');
    expect(descargado.resumen).toEqual({
      generados: '500',
      disponibles: '3200',
      solicitados: '500',
      suficiente: '1',
      errores: '0',
      excluidos: '3',
    });
    expect(PREFIJO_RESUMEN_CARGA).toBe('X-Carga-');
  });

  it('un rechazo no deja archivo: llega como ApiError', async () => {
    responder(json(400, { detail: 'El filtro está mal escrito' }));
    const error = await generarCarga(PETICION).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 400, detail: 'El filtro está mal escrito' });
  });

  it('pasa la señal para que Cancelar corte la espera', async () => {
    const controlador = new AbortController();
    const falso = responder(archivo());
    await generarCarga(PETICION, controlador.signal);
    expect(falso.mock.calls[0][1]?.signal).toBe(controlador.signal);
  });
});
