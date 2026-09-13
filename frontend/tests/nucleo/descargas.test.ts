/**
 * Binary downloads. A generated file brings its name and its summary in the
 * headers, because the body is the file; losing either one means the analyst
 * saves "download" with no idea how many rows it holds.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, NetworkError, request } from '../../src/lib/api';
import {
  cabecerasConPrefijo,
  descargarArchivo,
  nombreDesdeDisposicion,
} from '../../src/lib/descargas';

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.unstubAllGlobals());

describe('nombre del archivo desde Content-Disposition', () => {
  it('lee la forma entre comillas', () => {
    expect(nombreDesdeDisposicion('attachment; filename="carga_sms.xlsx"')).toBe('carga_sms.xlsx');
  });

  it('lee la forma sin comillas', () => {
    expect(nombreDesdeDisposicion('attachment; filename=carga.csv')).toBe('carga.csv');
  });

  it('prefiere la forma extendida, que conserva las tildes', () => {
    const valor = "attachment; filename=\"campana.xlsx\"; filename*=UTF-8''campa%C3%B1a.xlsx";

    expect(nombreDesdeDisposicion(valor)).toBe('campaña.xlsx');
  });

  it('devuelve null si no hay cabecera o no trae nombre', () => {
    expect(nombreDesdeDisposicion(null)).toBeNull();
    expect(nombreDesdeDisposicion('attachment')).toBeNull();
  });
});

describe('resumen en cabeceras con prefijo', () => {
  it('toma solo las cabeceras del prefijo, con la clave en minúsculas', () => {
    const cabeceras = new Headers({
      'X-Carga-Generados': '500',
      'X-Carga-Suficiente': 'false',
      'Content-Type': 'text/csv',
    });

    expect(cabecerasConPrefijo(cabeceras, 'X-Carga-')).toEqual({
      generados: '500',
      suficiente: 'false',
    });
  });
});

describe('descargar un archivo', () => {
  it('devuelve el cuerpo, el nombre y el resumen', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response('pagare;monto\n', {
            status: 200,
            headers: {
              'content-type': 'text/csv',
              'content-disposition': 'attachment; filename="carga.csv"',
              'x-carga-generados': '1',
            },
          }),
      ),
    );

    const archivo = await descargarArchivo('/archivos-carga', { method: 'POST' }, 'X-Carga-');

    expect(await archivo.blob.text()).toBe('pagare;monto\n');
    expect(archivo.nombre).toBe('carga.csv');
    expect(archivo.resumen).toEqual({ generados: '1' });
  });

  it('un rechazo llega como ApiError con el motivo, no como un archivo', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: 'La fecha no tiene version vigente' }), {
            status: 404,
            headers: { 'content-type': 'application/json' },
          }),
      ),
    );

    const fallo = await descargarArchivo('/archivos-carga').catch((error: unknown) => error);

    expect(fallo).toBeInstanceOf(ApiError);
    expect((fallo as ApiError).detail).toBe('La fecha no tiene version vigente');
  });
});

describe('pedidos cancelados', () => {
  it('no confunde un pedido cancelado con la API caída', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new DOMException('The operation was aborted.', 'AbortError');
      }),
    );

    const fallo = await request('/cartera/resumen').catch((error: unknown) => error);

    expect(fallo).not.toBeInstanceOf(NetworkError);
    expect((fallo as DOMException).name).toBe('AbortError');
  });
});
