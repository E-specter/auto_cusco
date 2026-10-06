/**
 * The rich-text engine client. What matters: a text with problems is an
 * answer, not an error; the catalogue is fetched once per context; and a
 * failed catalogue request is not cached, so the screen can recover.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../src/lib/api';
import {
  obtenerCatalogo,
  olvidarCatalogos,
  previsualizarTexto,
  validarTexto,
} from '../../src/lib/api-texto-enriquecido';

function responderCon(...respuestas: Array<{ estado: number; cuerpo: unknown }>): ReturnType<typeof vi.fn> {
  const cola = [...respuestas];
  const falso = vi.fn(async () => {
    const { estado, cuerpo } = cola.length > 1 ? cola.shift()! : cola[0];
    return new Response(JSON.stringify(cuerpo), { status: estado, headers: { 'content-type': 'application/json' } });
  });
  vi.stubGlobal('fetch', falso);
  return falso;
}

beforeEach(() => {
  vi.unstubAllGlobals();
  olvidarCatalogos();
});
afterEach(() => vi.unstubAllGlobals());

describe('catálogo', () => {
  it('se pide por contexto y una sola vez aunque lo pidan varios editores', async () => {
    const falso = responderCon({ estado: 200, cuerpo: { contexto: { nombre: 'mowa_mes.speech' } } });

    const [a, b] = await Promise.all([obtenerCatalogo('mowa_mes.speech'), obtenerCatalogo('mowa_mes.speech')]);

    expect(falso).toHaveBeenCalledTimes(1);
    expect(a).toBe(b);
    expect(String(falso.mock.calls[0][0])).toBe('/api/texto-enriquecido/catalogo?contexto=mowa_mes.speech');
  });

  it('otro contexto es otro pedido', async () => {
    const falso = responderCon({ estado: 200, cuerpo: {} });

    await obtenerCatalogo('cartera');
    await obtenerCatalogo('mowa_mes.speech');

    expect(falso).toHaveBeenCalledTimes(2);
  });

  it('un pedido fallido no queda guardado: el siguiente vuelve a intentar', async () => {
    const falso = responderCon(
      { estado: 404, cuerpo: { detail: 'No existe el contexto', codigo: 'contexto_desconocido' } },
      { estado: 200, cuerpo: { contexto: { nombre: 'cartera' } } },
    );

    const fallo = await obtenerCatalogo('cartera').catch((e: unknown) => e);
    const segundo = await obtenerCatalogo('cartera');

    expect((fallo as ApiError).codigo).toBe('contexto_desconocido');
    expect(segundo).toEqual({ contexto: { nombre: 'cartera' } });
    expect(falso).toHaveBeenCalledTimes(2);
  });
});

describe('validación y previsualización', () => {
  it('una expresión con problemas es una respuesta normal, no un error', async () => {
    responderCon({
      estado: 200,
      cuerpo: { problemas: [{ codigo: 'variable_desconocida', detalle: 'x', ubicacion: { nodo: 0 } }], tipo: null, cota: null, sin_cota: null, variables: [] },
    });

    const respuesta = await validarTexto('cartera', { nodos: [{ tipo: 'variable', nombre: 'no_existe', funciones: [] }] });

    expect(respuesta.problemas[0].codigo).toBe('variable_desconocida');
  });

  it('valida con POST y cuerpo JSON, y pasa la señal de cancelación', async () => {
    const falso = responderCon({ estado: 200, cuerpo: { problemas: [] } });
    const control = new AbortController();

    await validarTexto('mowa_mes.speech', { nodos: [] }, control.signal);

    const opciones = falso.mock.calls[0][1] as RequestInit;
    expect(String(falso.mock.calls[0][0])).toBe('/api/texto-enriquecido/validacion');
    expect(opciones.method).toBe('POST');
    expect(JSON.parse(String(opciones.body))).toEqual({ contexto: 'mowa_mes.speech', expresion: { nodos: [] } });
    expect(opciones.signal).toBe(control.signal);
  });

  it('un pagaré inexistente llega como 404 con su código, para ponerlo bajo su campo', async () => {
    responderCon({ estado: 404, cuerpo: { detail: 'No hay producto', codigo: 'producto_no_encontrado' } });

    const fallo = await previsualizarTexto({
      contexto: 'cartera',
      expresion: { nodos: [] },
      muestra: { tipo: 'producto_real', fecha_corte: '2026-09-10', pagare: '000000000000000100', cantidad: 1 },
    }).catch((e: unknown) => e);

    expect(fallo).toBeInstanceOf(ApiError);
    expect((fallo as ApiError).codigo).toBe('producto_no_encontrado');
  });
});
