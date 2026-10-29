/**
 * What the mapper client sends: method, JSON header and body of each write. Pinned when `conJson`
 * moved to `api.ts` (T-MM-L-F2): the bodies must stay exactly what the API expects.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  cambiarCampoAdicional,
  confirmarCarga,
  crearCampoAdicional,
  reanalizarBorrador,
  validarMapeo,
} from '../../src/lib/api-mapeador';

function responderCon(cuerpo: unknown): ReturnType<typeof vi.fn> {
  const falso = vi.fn(
    async () => new Response(JSON.stringify(cuerpo), { status: 200, headers: { 'content-type': 'application/json' } }),
  );
  vi.stubGlobal('fetch', falso);
  return falso;
}

afterEach(() => vi.unstubAllGlobals());

function peticion(falso: ReturnType<typeof vi.fn>): { url: string; init: RequestInit } {
  const [url, init] = falso.mock.calls[0] as [string, RequestInit];
  return { url, init };
}

describe('las escrituras del mapeador mandan JSON con su método', () => {
  it('validarMapeo: POST con { asignaciones }', async () => {
    const falso = responderCon({ problemas: [] });
    const controlador = new AbortController();

    await validarMapeo(7, [{ columna: 'A' } as never], controlador.signal);

    const { url, init } = peticion(falso);
    expect(url).toBe('/api/mapeador/borradores/7/validacion');
    expect(init.method).toBe('POST');
    expect(init.headers).toEqual({ 'content-type': 'application/json' });
    expect(init.body).toBe(JSON.stringify({ asignaciones: [{ columna: 'A' }] }));
    expect(init.signal).toBe(controlador.signal);
  });

  it('reanalizarBorrador: POST con las opciones', async () => {
    const falso = responderCon({});

    await reanalizarBorrador(3, { hoja: 'VENCIDA' } as never);

    const { url, init } = peticion(falso);
    expect(url).toBe('/api/mapeador/borradores/3/analisis');
    expect(init.method).toBe('POST');
    expect(init.headers).toEqual({ 'content-type': 'application/json' });
    expect(init.body).toBe(JSON.stringify({ hoja: 'VENCIDA' }));
  });

  it('confirmarCarga: POST con la confirmación', async () => {
    const falso = responderCon({});

    await confirmarCarga({ borrador_id: 3 } as never);

    const { url, init } = peticion(falso);
    expect(url).toBe('/api/cargas/desde-borrador');
    expect(init.method).toBe('POST');
    expect(init.headers).toEqual({ 'content-type': 'application/json' });
    expect(init.body).toBe(JSON.stringify({ borrador_id: 3 }));
  });

  it('crearCampoAdicional: POST con el campo nuevo', async () => {
    const falso = responderCon({});

    await crearCampoAdicional(3, { etiqueta: 'Región' } as never);

    const { url, init } = peticion(falso);
    expect(url).toBe('/api/mapeador/borradores/3/campos-adicionales');
    expect(init.method).toBe('POST');
    expect(init.headers).toEqual({ 'content-type': 'application/json' });
    expect(init.body).toBe(JSON.stringify({ etiqueta: 'Región' }));
  });

  it('cambiarCampoAdicional: PATCH con el cambio y el nombre codificado', async () => {
    const falso = responderCon({});

    await cambiarCampoAdicional('ad_región', { archivado: true } as never);

    const { url, init } = peticion(falso);
    expect(url).toBe('/api/mapeador/sabana_vencida/campos-adicionales/ad_regi%C3%B3n');
    expect(init.method).toBe('PATCH');
    expect(init.headers).toEqual({ 'content-type': 'application/json' });
    expect(init.body).toBe(JSON.stringify({ archivado: true }));
  });
});
