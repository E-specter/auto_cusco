/**
 * The API client.
 *
 * What matters here is the distinction the interface is built on: a server
 * that answered "no" (`ApiError`, with the server's own reason) is a
 * different situation for the analyst than a server that never answered
 * (`NetworkError`). Collapsing them would make "the file is too big" and "the
 * backend is down" read the same.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  ApiError,
  NetworkError,
  asignarVigente,
  eliminarVersion,
  listarIncidencias,
  listarVersiones,
  subirSabana,
} from '../../src/lib/api';

/** Stand in for `fetch` with a fixed answer, and record how it was called. */
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

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.unstubAllGlobals());

describe('respuestas que el servidor rechaza', () => {
  it('convierte un 409 en ApiError conservando el motivo del servidor', async () => {
    responderCon(409, { detail: 'Solo una version terminada puede ser vigente' });

    const fallo = await asignarVigente(7).catch((error: unknown) => error);

    expect(fallo).toBeInstanceOf(ApiError);
    expect((fallo as ApiError).status).toBe(409);
    expect((fallo as ApiError).detail).toBe('Solo una version terminada puede ser vigente');
  });

  it('convierte un 404 en ApiError', async () => {
    responderCon(404, { detail: 'No existe la carga 999' });

    const fallo = await listarIncidencias(999).catch((error: unknown) => error);

    expect(fallo).toBeInstanceOf(ApiError);
    expect((fallo as ApiError).status).toBe(404);
  });

  it('convierte un 413 en ApiError para que la consola hable del tamaño', async () => {
    responderCon(413, { detail: 'El archivo supera el maximo de 64 MB' });

    const fallo = await subirSabana({
      archivo: new File(['x'], 'SABANA_10.09.2026.xlsx'),
      fechaCorte: '2026-09-10',
    }).catch((error: unknown) => error);

    expect(fallo).toBeInstanceOf(ApiError);
    expect((fallo as ApiError).status).toBe(413);
  });

  it('sobrevive a un cuerpo de error que no es JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('<html>502</html>', { status: 502 })),
    );

    const fallo = await listarVersiones().catch((error: unknown) => error);

    expect(fallo).toBeInstanceOf(ApiError);
    expect((fallo as ApiError).status).toBe(502);
    expect((fallo as ApiError).detail).toBe('');
  });
});

describe('API inalcanzable', () => {
  it('distingue no poder contactar del servidor respondiendo que no', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch');
      }),
    );

    const fallo = await listarVersiones().catch((error: unknown) => error);

    expect(fallo).toBeInstanceOf(NetworkError);
    expect(fallo).not.toBeInstanceOf(ApiError);
  });
});

describe('forma de las peticiones', () => {
  it('pide las versiones al prefijo del mismo origen', async () => {
    const falso = responderCon(200, []);

    await listarVersiones({ fechaCorte: '2026-09-10', limite: 50 });

    const url = String(falso.mock.calls[0][0]);
    expect(url).toContain('/api/cargas?');
    expect(url).toContain('fecha_corte=2026-09-10');
    expect(url).toContain('limite=50');
  });

  it('filtra incidencias por severidad y desplazamiento', async () => {
    const falso = responderCon(200, { total: 0, incidencias: [] });

    await listarIncidencias(3, { severidad: 'advertencia', limite: 50, desplazamiento: 100 });

    const url = String(falso.mock.calls[0][0]);
    expect(url).toContain('/api/cargas/3/incidencias?');
    expect(url).toContain('severidad=advertencia');
    expect(url).toContain('desplazamiento=100');
  });

  it('sube la sábana como multipart con su fecha de corte', async () => {
    const falso = responderCon(202, { id: 1, versiones_identicas: [] });

    await subirSabana({
      archivo: new File(['contenido'], 'SABANA_10.09.2026.xlsx'),
      fechaCorte: '2026-09-10',
      hoja: 'VENCIDA',
    });

    const opciones = falso.mock.calls[0][1] as RequestInit;
    const cuerpo = opciones.body as FormData;

    expect(opciones.method).toBe('POST');
    expect(cuerpo.get('fecha_corte')).toBe('2026-09-10');
    expect(cuerpo.get('hoja')).toBe('VENCIDA');
    expect((cuerpo.get('archivo') as File).name).toBe('SABANA_10.09.2026.xlsx');
  });

  it('pide la eliminación diciendo explícitamente si la fecha queda sin vigente', async () => {
    const falso = responderCon(204);

    await eliminarVersion(4, true);

    const url = String(falso.mock.calls[0][0]);
    expect(url).toContain('/api/cargas/4?');
    expect(url).toContain('dejar_fecha_sin_vigente=true');
    expect((falso.mock.calls[0][1] as RequestInit).method).toBe('DELETE');
  });

  it('no intenta leer un cuerpo en el 204 de una eliminación', async () => {
    responderCon(204);

    await expect(eliminarVersion(4, false)).resolves.toBeUndefined();
  });
});
