/**
 * The saved-definitions calls (B4b). What is worth pinning is what the backend reads: the method,
 * the path, the JSON body — above all that a new version never sends a name, which cannot change —
 * and that a refusal reaches the screen as an ApiError whose problems are readable.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../src/lib/api';
import {
  crearDefinicion,
  guardarBorrador,
  guardarVersion,
  listarDefiniciones,
  obtenerDefinicion,
  problemasDeError,
  renombrarDefinicionGuardada,
} from '../../src/lib/api-definiciones';
import { aDefinicion, definicionNueva, fijarExpresion, renombrarDefinicion, renombrarColumna } from '../../src/lib/constructor-columnas';

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

/** A draft with a name and one column the backend could accept. */
function borrador() {
  let b = renombrarDefinicion(definicionNueva(), 'SMS preventivo');
  b = renombrarColumna(b, b.columnas[0].id, 'telefono');
  return fijarExpresion(b, b.columnas[0].id, {
    nodos: [{ tipo: 'variable', nombre: 'telefono', funciones: [] }],
  });
}

const PROBLEMA = {
  codigo: 'parametro_invalido',
  detalle: 'El patrón no tiene marcas',
  ubicacion: null,
  nombre: null,
  columna: 0,
  segmento: null,
  campo: 'formato_fecha',
};

describe('leer', () => {
  it('lista con GET', async () => {
    const falso = responderCon(200, []);

    await listarDefiniciones();

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/definiciones-columnas');
    expect(opciones.method ?? 'GET').toBe('GET');
  });

  it('pide una definición por id, vigente si no se dice la versión', async () => {
    const falso = responderCon(200, {});

    await obtenerDefinicion(7);

    expect(llamada(falso).url).toBe('/api/definiciones-columnas/7');
  });

  it('pide una versión concreta con ?version=', async () => {
    const falso = responderCon(200, {});

    await obtenerDefinicion(7, 2);

    expect(llamada(falso).url).toBe('/api/definiciones-columnas/7?version=2');
  });

  it('pasa la señal para cancelar el pedido anterior', async () => {
    const falso = responderCon(200, []);
    const control = new AbortController();

    await listarDefiniciones(control.signal);

    expect(llamada(falso).opciones.signal).toBe(control.signal);
  });
});

describe('guardar', () => {
  it('una definición nueva se crea con POST y el cuerpo es el del constructor', async () => {
    const falso = responderCon(201, {});
    const entrada = aDefinicion(borrador());

    await crearDefinicion(entrada);

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/definiciones-columnas');
    expect(opciones.method).toBe('POST');
    expect(new Headers(opciones.headers).get('content-type')).toBe('application/json');
    expect(cuerpoDe(opciones)).toMatchObject({ nombre: 'SMS preventivo', proteger_formulas: true });
    expect(cuerpoDe(opciones).columnas[0]).toMatchObject({ nombre: 'telefono', orden: 0 });
  });

  it('un cambio es una versión nueva: POST a /versiones', async () => {
    const falso = responderCon(201, {});

    await guardarVersion(7, aDefinicion(borrador()));

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/definiciones-columnas/7/versiones');
    expect(opciones.method).toBe('POST');
  });

  it('guardarBorrador sin definición guardada crea, con el nombre', async () => {
    const falso = responderCon(201, {});

    await guardarBorrador(borrador(), null);

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/definiciones-columnas');
    expect(cuerpoDe(opciones).nombre).toBe('SMS preventivo');
  });

  it('guardarBorrador con una definición guardada crea una versión y NO manda el nombre', async () => {
    const falso = responderCon(201, {});

    await guardarBorrador(borrador(), 7);

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/definiciones-columnas/7/versiones');
    expect(cuerpoDe(opciones)).not.toHaveProperty('nombre');
    expect(cuerpoDe(opciones).columnas).toHaveLength(1);
  });

  it('nunca usa PUT: ninguna versión se modifica', async () => {
    const falso = responderCon(201, {});

    await guardarBorrador(borrador(), 7);
    await guardarBorrador(borrador(), null);

    expect(falso.mock.calls.map((c) => (c[1] as RequestInit).method)).toEqual(['POST', 'POST']);
  });
});

describe('cuando el backend dice que no', () => {
  it('un 400 trae el código y los problemas ubicados', async () => {
    responderCon(400, { detail: 'La definición no es válida', codigo: 'definicion_invalida', problemas: [PROBLEMA] });

    const fallo = await crearDefinicion(aDefinicion(borrador())).catch((e: unknown) => e);

    expect(fallo).toBeInstanceOf(ApiError);
    expect((fallo as ApiError).status).toBe(400);
    expect((fallo as ApiError).codigo).toBe('definicion_invalida');
    expect(problemasDeError(fallo)).toEqual([PROBLEMA]);
  });

  it('un 409 por nombre repetido llega con su código y sin problemas', async () => {
    responderCon(409, { detail: 'Ya existe una definición con ese nombre', codigo: 'nombre_repetido' });

    const fallo = await crearDefinicion(aDefinicion(borrador())).catch((e: unknown) => e);

    expect((fallo as ApiError).status).toBe(409);
    expect((fallo as ApiError).codigo).toBe('nombre_repetido');
    expect(problemasDeError(fallo)).toEqual([]);
  });

  it('un 404 de definición o versión llega con su código', async () => {
    responderCon(404, { detail: 'No existe la versión 9', codigo: 'version_no_encontrada' });

    const fallo = await obtenerDefinicion(7, 9).catch((e: unknown) => e);

    expect((fallo as ApiError).status).toBe(404);
    expect((fallo as ApiError).codigo).toBe('version_no_encontrada');
  });

  it('lo que no es una lista de problemas ni se lee ni se inventa', () => {
    const conCuerpo = (cuerpo: Record<string, unknown> | null) => new ApiError(400, 'x', 'definicion_invalida', cuerpo);

    expect(problemasDeError(conCuerpo(null))).toEqual([]);
    expect(problemasDeError(conCuerpo({ problemas: 'texto' }))).toEqual([]);
    expect(problemasDeError(conCuerpo({ problemas: [{ sin: 'forma' }] }))).toEqual([]);
    expect(problemasDeError(new Error('otra cosa'))).toEqual([]);
    expect(problemasDeError(undefined)).toEqual([]);
  });

  it('descarta solo los problemas sin forma y conserva los demás', () => {
    const fallo = new ApiError(400, 'x', 'definicion_invalida', { problemas: [{ sin: 'forma' }, PROBLEMA] });

    expect(problemasDeError(fallo)).toEqual([PROBLEMA]);
  });
});

describe('renombrar', () => {
  it('es un PATCH a la definición con solo el nombre, sin versión', async () => {
    const falso = responderCon(200, { id: 7, nombre: 'SMS preventivo B' });

    await renombrarDefinicionGuardada(7, 'SMS preventivo B');

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/definiciones-columnas/7');
    expect(opciones.method).toBe('PATCH');
    expect(cuerpoDe(opciones)).toEqual({ nombre: 'SMS preventivo B' });
  });

  it('manda el nombre tal como se escribió: recortarlo es cosa del backend', async () => {
    const falso = responderCon(200, {});

    await renombrarDefinicionGuardada(7, '  Con espacios  ');

    expect(cuerpoDe(llamada(falso).opciones)).toEqual({ nombre: '  Con espacios  ' });
  });

  it('un rechazo llega como ApiError con su código', async () => {
    responderCon(409, { detail: 'Ya hay una definición con ese nombre', codigo: 'nombre_repetido' });

    const fallo = await renombrarDefinicionGuardada(7, 'otro').catch((e: unknown) => e);

    expect(fallo).toBeInstanceOf(ApiError);
    expect(fallo).toMatchObject({ status: 409, codigo: 'nombre_repetido' });
  });
});
