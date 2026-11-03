/**
 * The saved-texts calls (T-HI-B4, RF-69). What is worth pinning is what the backend reads: the method, the path, the
 * query and the JSON body, and that a refusal reaches the screen as an ApiError whose problems are readable.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../src/lib/api';
import {
  agregarVersion,
  crearTexto,
  deshabilitarTexto,
  eliminarTexto,
  habilitarTexto,
  listarContextos,
  listarTextos,
  obtenerTexto,
  problemasDeError,
  renombrarTexto,
} from '../../src/lib/api-textos-guardados';

function responderCon(estado: number, cuerpo: unknown = {}): ReturnType<typeof vi.fn> {
  const falso = vi.fn(async () =>
    estado === 204
      ? new Response(null, { status: 204 })
      : new Response(JSON.stringify(cuerpo), { status: estado, headers: { 'content-type': 'application/json' } }),
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

describe('leer', () => {
  it('los contextos, el listado de un contexto con y sin deshabilitados, y un texto con o sin versión', async () => {
    let falso = responderCon(200, []);
    await listarContextos();
    expect(llamada(falso).url).toMatch(/\/textos-guardados\/contextos$/);

    falso = responderCon(200, []);
    await listarTextos('whatsmkt.mensaje');
    expect(llamada(falso).url).toMatch(/\/textos-guardados\?contexto=whatsmkt\.mensaje$/);

    falso = responderCon(200, []);
    await listarTextos('whatsmkt.mensaje', true);
    expect(llamada(falso).url).toMatch(/\/textos-guardados\?contexto=whatsmkt\.mensaje&deshabilitados=true$/);

    falso = responderCon(200, {});
    await obtenerTexto(4);
    expect(llamada(falso).url).toMatch(/\/textos-guardados\/4$/);

    falso = responderCon(200, {});
    await obtenerTexto(4, 2);
    expect(llamada(falso).url).toMatch(/\/textos-guardados\/4\?version=2$/);
  });

  it('un nombre de contexto con caracteres especiales viaja codificado', async () => {
    const falso = responderCon(200, []);
    await listarTextos('a b&c');
    expect(llamada(falso).url).toMatch(/contexto=a\+b%26c$/);
  });
});

describe('escribir', () => {
  it('crear manda el contexto, el nombre y el contenido; una versión nueva solo el contenido', async () => {
    let falso = responderCon(201, {});
    await crearTexto('c', 'Preventivo', { texto: 'Hola' });
    let { url, opciones } = llamada(falso);
    expect(url).toMatch(/\/textos-guardados$/);
    expect(opciones.method).toBe('POST');
    expect(JSON.parse(String(opciones.body))).toEqual({ contexto: 'c', nombre: 'Preventivo', contenido: { texto: 'Hola' } });

    falso = responderCon(201, {});
    await agregarVersion(7, { texto: 'Hola otra vez' });
    ({ url, opciones } = llamada(falso));
    expect(url).toMatch(/\/textos-guardados\/7\/versiones$/);
    expect(opciones.method).toBe('POST');
    expect(JSON.parse(String(opciones.body))).toEqual({ contenido: { texto: 'Hola otra vez' } });
  });

  it('renombrar es un PATCH con solo el nombre', async () => {
    const falso = responderCon(200, {});
    await renombrarTexto(7, 'Nuevo nombre');
    const { url, opciones } = llamada(falso);
    expect(url).toMatch(/\/textos-guardados\/7$/);
    expect(opciones.method).toBe('PATCH');
    expect(JSON.parse(String(opciones.body))).toEqual({ nombre: 'Nuevo nombre' });
  });

  it('deshabilitar y habilitar son POST sin cuerpo; eliminar es un DELETE que no devuelve nada', async () => {
    let falso = responderCon(200, {});
    await deshabilitarTexto(7);
    expect(llamada(falso).url).toMatch(/\/textos-guardados\/7\/deshabilitar$/);
    expect(llamada(falso).opciones.method).toBe('POST');
    expect(llamada(falso).opciones.body).toBeUndefined();

    falso = responderCon(200, {});
    await habilitarTexto(7);
    expect(llamada(falso).url).toMatch(/\/textos-guardados\/7\/habilitar$/);
    expect(llamada(falso).opciones.method).toBe('POST');

    falso = responderCon(204);
    await expect(eliminarTexto(7)).resolves.toBeUndefined();
    expect(llamada(falso).url).toMatch(/\/textos-guardados\/7$/);
    expect(llamada(falso).opciones.method).toBe('DELETE');
  });
});

describe('un rechazo llega como ApiError', () => {
  it('con su estado y su código', async () => {
    responderCon(409, { detail: 'Ya existe', codigo: 'nombre_repetido' });
    const error = await renombrarTexto(1, 'x').catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(409);
    expect((error as ApiError).codigo).toBe('nombre_repetido');
  });

  it('con los problemas de un 400 bien formados, y ninguno si no lo son', async () => {
    const problema = { codigo: 'expresion_invalida', detalle: 'x', campo: 'contenido', ubicacion: null, nombre: null, columna: null, segmento: null };
    responderCon(400, { detail: 'No se puede guardar', codigo: 'texto_guardado_invalido', problemas: [problema, { roto: true }] });
    const error = await crearTexto('c', 'n', {}).catch((e: unknown) => e);
    expect(problemasDeError(error)).toEqual([problema]);
    expect(problemasDeError(new Error('otra cosa'))).toEqual([]);
    expect(problemasDeError(new ApiError(400, 'sin cuerpo'))).toEqual([]);
  });
});
