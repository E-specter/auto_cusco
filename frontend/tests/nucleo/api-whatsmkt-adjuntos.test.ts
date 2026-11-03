/**
 * The attachment library calls (T-WM-F1b1) and the two partial PUTs of the new panels. What is worth pinning is what the
 * backend reads: the method, the path, the query, the multipart body of an upload (no hand-written `content-type`: the
 * browser puts the boundary), and that a refusal reaches the screen as an ApiError with its code.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../src/lib/api';
import {
  archivarAdjunto,
  desarchivarAdjunto,
  descargarAdjunto,
  guardarConfiguracion,
  listarAdjuntos,
  subirAdjunto,
} from '../../src/lib/api-whatsmkt';
import { errorDeModulo } from '../../src/lib/whatsmkt';

function responderCon(estado: number, cuerpo: unknown = {}, cabeceras: Record<string, string> = {}): ReturnType<typeof vi.fn> {
  const falso = vi.fn(
    async () =>
      new Response(typeof cuerpo === 'string' ? cuerpo : JSON.stringify(cuerpo), {
        status: estado,
        headers: { 'content-type': 'application/json', ...cabeceras },
      }),
  );
  vi.stubGlobal('fetch', falso);
  return falso;
}

const llamada = (falso: ReturnType<typeof vi.fn>) => ({
  url: String(falso.mock.calls[0][0]),
  opciones: (falso.mock.calls[0][1] ?? {}) as RequestInit,
});

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.unstubAllGlobals());

describe('la biblioteca', () => {
  it('lista los activos con GET, y los archivados con ?archivados=true', async () => {
    const activos = responderCon(200, []);
    await listarAdjuntos();
    expect(llamada(activos).url).toBe('/api/whatsmkt/adjuntos');
    expect(llamada(activos).opciones.method).toBeUndefined();

    const archivados = responderCon(200, []);
    await listarAdjuntos(true);
    expect(llamada(archivados).url).toBe('/api/whatsmkt/adjuntos?archivados=true');
  });

  it('sube con POST multipart: el archivo y el propósito «adjunto», sin content-type escrito a mano', async () => {
    const falso = responderCon(201, { id: 5, ya_existia: false });
    const archivo = new File(['bytes sinteticos'], 'afiche.jpg', { type: 'image/jpeg' });

    await subirAdjunto(archivo);

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/whatsmkt/adjuntos');
    expect(opciones.method).toBe('POST');
    expect(opciones.headers).toBeUndefined();
    const cuerpo = opciones.body as FormData;
    expect(cuerpo).toBeInstanceOf(FormData);
    expect((cuerpo.get('archivo') as File).name).toBe('afiche.jpg');
    expect(cuerpo.get('proposito')).toBe('adjunto');
  });

  it('el rechazo de un tipo llega como ApiError con su código', async () => {
    responderCon(422, { detail: 'x', codigo: 'adjunto_tipo', horarios: null, variable: null, segmento: null, fila: null, desde: null, hasta: null, peso: null, maximo: null, tipo: null, ancho: null, alto: null });

    const error = await subirAdjunto(new File(['x'], 'datos.txt')).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(errorDeModulo(error)).toMatchObject({ codigo: 'adjunto_tipo' });
  });

  it('el rechazo por peso trae el peso, el máximo y el tipo para su texto', async () => {
    responderCon(422, { detail: 'x', codigo: 'adjunto_peso', peso: 20_000_000, maximo: 16_000_000, tipo: 'video' });

    const error = await subirAdjunto(new File(['x'], 'largo.mp4')).catch((e: unknown) => e);

    expect(errorDeModulo(error)).toMatchObject({ codigo: 'adjunto_peso', peso: 20_000_000, maximo: 16_000_000, tipo: 'video' });
  });

  it('archiva y restaura con POST sobre el id', async () => {
    const archivar = responderCon(200, { id: 7 });
    await archivarAdjunto(7);
    expect(llamada(archivar).url).toBe('/api/whatsmkt/adjuntos/7/archivar');
    expect(llamada(archivar).opciones.method).toBe('POST');

    const restaurar = responderCon(200, { id: 7 });
    await desarchivarAdjunto(7);
    expect(llamada(restaurar).url).toBe('/api/whatsmkt/adjuntos/7/desarchivar');
    expect(llamada(restaurar).opciones.method).toBe('POST');
  });

  it('un adjunto que no existe (404) llega como ApiError con el motivo de la API', async () => {
    responderCon(404, { detail: 'No existe el adjunto' });

    const error = await archivarAdjunto(99).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).detail).toBe('No existe el adjunto');
  });

  it('descarga el contenido con el nombre de la cabecera', async () => {
    const falso = responderCon(200, 'contenido sintetico', {
      'content-type': 'application/octet-stream',
      'content-disposition': 'attachment; filename="afiche.jpg"',
    });

    const archivo = await descargarAdjunto(3);

    expect(llamada(falso).url).toBe('/api/whatsmkt/adjuntos/3/contenido');
    expect(archivo.nombre).toBe('afiche.jpg');
    expect(await archivo.blob.text()).toBe('contenido sintetico');
  });
});

describe('los PUT parciales de los paneles nuevos', () => {
  it('el WhatsApp manda solo su campo, y un campo vacío manda null (borra el número)', async () => {
    const poner = responderCon(200, {});
    await guardarConfiguracion({ whatsapp_contacto: '900000123' });
    expect(JSON.parse(String(llamada(poner).opciones.body))).toEqual({ whatsapp_contacto: '900000123' });

    const borrar = responderCon(200, {});
    await guardarConfiguracion({ whatsapp_contacto: null });
    expect(JSON.parse(String(llamada(borrar).opciones.body))).toEqual({ whatsapp_contacto: null });
  });

  it('la definición por defecto manda solo su campo, y «sin definición» manda null (la quita)', async () => {
    const elegir = responderCon(200, {});
    await guardarConfiguracion({ definicion_defecto_id: 12 });
    expect(JSON.parse(String(llamada(elegir).opciones.body))).toEqual({ definicion_defecto_id: 12 });
    expect(llamada(elegir).opciones.method).toBe('PUT');

    const quitar = responderCon(200, {});
    await guardarConfiguracion({ definicion_defecto_id: null });
    expect(JSON.parse(String(llamada(quitar).opciones.body))).toEqual({ definicion_defecto_id: null });
  });
});
