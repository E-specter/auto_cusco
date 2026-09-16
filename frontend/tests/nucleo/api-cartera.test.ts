/**
 * The portfolio and saved-selection calls. What is worth pinning is the shape
 * FastAPI expects: repeated `filtro` and `indicador` parameters, and JSON
 * bodies for selections. A comma-joined list would read as one bad filter.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  ApiError,
  actualizarSeleccion,
  consultarCartera,
  crearSeleccion,
  eliminarSeleccion,
  resumirCartera,
  revisarSeleccion,
} from '../../src/lib/api';

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

const urlDe = (falso: ReturnType<typeof vi.fn>) => new URL(String(falso.mock.calls[0][0]), 'http://x');

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.unstubAllGlobals());

describe('resumen de cartera', () => {
  it('repite filtro e indicador en vez de juntarlos', async () => {
    const falso = responderCon(200, {});

    await resumirCartera(
      '2026-09-10',
      {
        filtros: ['dias_atraso:entre:0|30', 'telefono:no_vacio'],
        orden: '-saldo_capital_pendiente',
        cantidad: 500,
        indicadores: ['productos:conteo', 'cuota promedio:promedio:monto_cuota'],
      },
      'segmento_financiero',
    );

    const url = urlDe(falso);
    expect(url.pathname).toBe('/api/cartera/resumen');
    expect(url.searchParams.get('fecha_corte')).toBe('2026-09-10');
    expect(url.searchParams.getAll('filtro')).toEqual(['dias_atraso:entre:0|30', 'telefono:no_vacio']);
    expect(url.searchParams.getAll('indicador')).toEqual([
      'productos:conteo',
      'cuota promedio:promedio:monto_cuota',
    ]);
    expect(url.searchParams.get('orden')).toBe('-saldo_capital_pendiente');
    expect(url.searchParams.get('cantidad')).toBe('500');
    expect(url.searchParams.get('segmento')).toBe('segmento_financiero');
  });

  it('sin cantidad ni segmento no los envía', async () => {
    const falso = responderCon(200, {});

    await resumirCartera('2026-09-10', { filtros: [], orden: null }, null);

    const url = urlDe(falso);
    expect(url.searchParams.has('cantidad')).toBe(false);
    expect(url.searchParams.has('segmento')).toBe(false);
    expect(url.searchParams.has('orden')).toBe(false);
  });

  it('una fecha sin vigente llega como 404, distinto de una cartera vacía', async () => {
    responderCon(404, { detail: 'La fecha 2026-09-11 no tiene una version vigente de sabana' });

    const fallo = await resumirCartera('2026-09-11', { filtros: [], orden: null }, null).catch(
      (error: unknown) => error,
    );

    expect(fallo).toBeInstanceOf(ApiError);
    expect((fallo as ApiError).status).toBe(404);
  });

  it('pasa la señal de cancelación al pedido', async () => {
    const falso = responderCon(200, {});
    const control = new AbortController();

    await resumirCartera('2026-09-10', { filtros: [], orden: null }, null, control.signal);

    expect((falso.mock.calls[0][1] as RequestInit).signal).toBe(control.signal);
  });
});

describe('lista de productos', () => {
  it('pagina con límite y desplazamiento', async () => {
    const falso = responderCon(200, {});

    await consultarCartera(
      '2026-09-10',
      { filtros: ['region:igual:TACNA'], orden: 'dias_atraso' },
      { limite: 50, desplazamiento: 100 },
    );

    const url = urlDe(falso);
    expect(url.pathname).toBe('/api/cartera');
    expect(url.searchParams.get('limite')).toBe('50');
    expect(url.searchParams.get('desplazamiento')).toBe('100');
    expect(url.searchParams.getAll('filtro')).toEqual(['region:igual:TACNA']);
  });
});

describe('selecciones guardadas', () => {
  const entrada = {
    nombre: 'Preventiva top 500',
    filtros: ['dias_atraso:entre:0|30'],
    orden: '-saldo_capital_pendiente',
    cantidad: 500,
    indicadores: [],
  };

  it('guarda con POST y cuerpo JSON', async () => {
    const falso = responderCon(201, { id: 1 });

    await crearSeleccion(entrada);

    const opciones = falso.mock.calls[0][1] as RequestInit;
    expect(String(falso.mock.calls[0][0])).toBe('/api/selecciones');
    expect(opciones.method).toBe('POST');
    expect(new Headers(opciones.headers).get('content-type')).toBe('application/json');
    expect(JSON.parse(String(opciones.body))).toEqual(entrada);
  });

  it('un nombre repetido llega como 409 con el motivo', async () => {
    responderCon(409, { detail: 'Ya existe una seleccion con ese nombre' });

    const fallo = await crearSeleccion(entrada).catch((error: unknown) => error);

    expect((fallo as ApiError).status).toBe(409);
    expect((fallo as ApiError).detail).toBe('Ya existe una seleccion con ese nombre');
  });

  it('reemplaza con PUT sobre su id', async () => {
    const falso = responderCon(200, { id: 4 });

    await actualizarSeleccion(4, entrada);

    expect(String(falso.mock.calls[0][0])).toBe('/api/selecciones/4');
    expect((falso.mock.calls[0][1] as RequestInit).method).toBe('PUT');
  });

  it('revisa sin guardar en su propia ruta', async () => {
    const falso = responderCon(200, { aplicable: true, problemas: [] });

    await revisarSeleccion(entrada);

    expect(String(falso.mock.calls[0][0])).toBe('/api/selecciones/revision');
  });

  it('borra con DELETE y no lee cuerpo', async () => {
    const falso = responderCon(204);

    await expect(eliminarSeleccion(4)).resolves.toBeUndefined();
    expect((falso.mock.calls[0][1] as RequestInit).method).toBe('DELETE');
  });
});
