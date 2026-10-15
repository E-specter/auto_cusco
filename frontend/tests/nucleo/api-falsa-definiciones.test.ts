/**
 * The fake of `/definiciones-columnas` that the Playwright specs of the constructor use. It is
 * tested here, without a browser, because a fake that does not behave like the backend makes a
 * green spec mean nothing: it must refuse what B4b refuses (a repeated name, a name that changes
 * between versions, a blank column name) and never modify a version.
 */
import { describe, expect, it } from 'vitest';

import {
  apiDefiniciones,
  definicionFalsa,
  manejadorDefiniciones,
  type ApiFalsaDefiniciones,
} from '../../e2e/api-falsa-definiciones';
import type { DefinicionColumnasEntrada } from '../../src/lib/api-definiciones';

/** A Playwright `Route` reduced to what the handler uses: it records how it was answered. */
function rutaFalsa(cuerpo: unknown) {
  const respuesta: { estado: number | null; cuerpo: any; abortado: boolean } = {
    estado: null,
    cuerpo: null,
    abortado: false,
  };
  const route = {
    request: () => ({ postData: () => (cuerpo === null ? null : JSON.stringify(cuerpo)) }),
    fulfill: async (o: { status: number; body?: string }) => {
      respuesta.estado = o.status;
      respuesta.cuerpo = o.body ? JSON.parse(o.body) : null;
    },
    abort: async () => {
      respuesta.abortado = true;
    },
  };
  return { route: route as any, respuesta };
}

async function llamar(api: ApiFalsaDefiniciones, metodo: string, ruta: string, cuerpo: unknown = null) {
  const { route, respuesta } = rutaFalsa(cuerpo);
  const url = new URL(`http://localhost/api${ruta}`);
  const manejar = manejadorDefiniciones(api);
  const atendido = await manejar(route, url.pathname.replace(/^\/api/, ''), metodo, url);
  return { atendido, ...respuesta };
}

const COLUMNA = (nombre: string, orden = 0) => ({
  nombre,
  orden,
  expresion: { nodos: [{ tipo: 'variable', nombre: 'telefono', funciones: [] }] },
});

const entrada = (nombre: string | null, columnas = [COLUMNA('telefono')]): DefinicionColumnasEntrada =>
  ({ nombre, columnas, proteger_formulas: true }) as DefinicionColumnasEntrada;

describe('lo que no es suyo', () => {
  it('no atiende otra ruta y lo dice para que la cadena siga', async () => {
    const api = apiDefiniciones();

    expect((await llamar(api, 'GET', '/cargas')).atendido).toBe(false);
    expect((await llamar(api, 'GET', '/texto-enriquecido/catalogo')).atendido).toBe(false);
  });

  it('sin red aborta la llamada', async () => {
    const api = apiDefiniciones();
    api.sinRed = true;

    const r = await llamar(api, 'GET', '/definiciones-columnas');

    expect(r.atendido).toBe(true);
    expect(r.abortado).toBe(true);
  });
});

describe('listar y leer', () => {
  it('lista con el resumen que da el backend, por nombre', async () => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 2, nombre: 'Zeta' }), definicionFalsa({ id: 1, nombre: 'alfa', versiones: 3 }));

    const r = await llamar(api, 'GET', '/definiciones-columnas');

    expect(r.estado).toBe(200);
    expect(r.cuerpo.map((d: any) => d.nombre)).toEqual(['alfa', 'Zeta']);
    expect(r.cuerpo[0]).toMatchObject({ id: 1, version_vigente: 3, cantidad_versiones: 3, vigente_usada: false });
  });

  it('una definición trae su versión vigente con todas las versiones', async () => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1, versiones: 3 }));

    const r = await llamar(api, 'GET', '/definiciones-columnas/1');

    expect(r.estado).toBe(200);
    expect(r.cuerpo).toMatchObject({ id: 1, version_vigente: 3, version: { numero: 3 } });
    expect(r.cuerpo.versiones.map((v: any) => v.numero)).toEqual([1, 2, 3]);
  });

  it('?version= trae esa versión, con su contenido', async () => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1, versiones: 3, usadasHasta: 1 }));

    const r = await llamar(api, 'GET', '/definiciones-columnas/1?version=1');

    expect(r.cuerpo.version).toMatchObject({ numero: 1, usada: true });
    expect(r.cuerpo.version_vigente).toBe(3);
    expect(r.cuerpo.version.contenido.columnas.length).toBeGreaterThan(0);
  });

  it('una definición o una versión que no existen dan 404 con su código', async () => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1 }));

    const sinDefinicion = await llamar(api, 'GET', '/definiciones-columnas/9');
    const sinVersion = await llamar(api, 'GET', '/definiciones-columnas/1?version=9');

    expect(sinDefinicion.estado).toBe(404);
    expect(sinDefinicion.cuerpo.codigo).toBe('definicion_no_encontrada');
    expect(sinVersion.estado).toBe(404);
    expect(sinVersion.cuerpo.codigo).toBe('version_no_encontrada');
  });
});

describe('crear', () => {
  it('guarda la versión 1 con el contenido completado como lo completa el backend', async () => {
    const api = apiDefiniciones();

    const r = await llamar(api, 'POST', '/definiciones-columnas', entrada('SMS preventivo'));

    expect(r.estado).toBe(201);
    expect(r.cuerpo).toMatchObject({ nombre: 'SMS preventivo', version_vigente: 1, version: { numero: 1, usada: false } });
    const contenido = r.cuerpo.version.contenido;
    expect(contenido.proteger_formulas).toBe(true);
    expect(contenido.segmentacion).toBeNull();
    expect(contenido.columnas[0]).toMatchObject({
      nombre: 'telefono',
      tipo: 'texto',
      formato_fecha: null,
      formato_financiero: { separador_miles: ',', separador_decimal: '.', decimales: 2 },
      variantes: [],
    });
    expect(contenido.columnas[0].expresion.nodos[0]).toEqual({
      tipo: 'variable',
      nombre: 'telefono',
      funciones: [],
      obligatoria: false,
    });
    expect(api.definiciones).toHaveLength(1);
  });

  it('un nombre repetido, aunque cambien las mayúsculas o las tildes, es 409 nombre_repetido', async () => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1, nombre: 'Mensajería' }));

    const r = await llamar(api, 'POST', '/definiciones-columnas', entrada('  MENSAJERIA '));

    expect(r.estado).toBe(409);
    expect(r.cuerpo.codigo).toBe('nombre_repetido');
    expect(api.definiciones).toHaveLength(1);
  });

  it('sin nombre, o con uno que no cabe, es un 400 con el problema en `nombre`', async () => {
    const api = apiDefiniciones();

    const sin = await llamar(api, 'POST', '/definiciones-columnas', entrada(null));
    const largo = await llamar(api, 'POST', '/definiciones-columnas', entrada('x'.repeat(121)));

    for (const r of [sin, largo]) {
      expect(r.estado).toBe(400);
      expect(r.cuerpo.codigo).toBe('definicion_invalida');
      expect(r.cuerpo.problemas[0]).toMatchObject({ campo: 'nombre', columna: null });
    }
  });

  it('una columna sin nombre es un 400 ubicado en su columna', async () => {
    const api = apiDefiniciones();

    const r = await llamar(api, 'POST', '/definiciones-columnas', entrada('SMS', [COLUMNA('ok', 0), COLUMNA('  ', 1)]));

    expect(r.estado).toBe(400);
    expect(r.cuerpo.problemas).toHaveLength(1);
    expect(r.cuerpo.problemas[0]).toMatchObject({ columna: 1, campo: 'nombre', codigo: 'definicion_invalida' });
    expect(api.definiciones).toHaveLength(0);
  });

  it('sin columnas es un 400 en `columnas`', async () => {
    const api = apiDefiniciones();

    const r = await llamar(api, 'POST', '/definiciones-columnas', entrada('SMS', []));

    expect(r.estado).toBe(400);
    expect(r.cuerpo.problemas[0]).toMatchObject({ campo: 'columnas', columna: null });
  });

  it('un 400 junta todos los problemas, no el primero', async () => {
    const api = apiDefiniciones();

    const r = await llamar(api, 'POST', '/definiciones-columnas', entrada(null, [COLUMNA(''), COLUMNA('', 1)]));

    expect(r.cuerpo.problemas).toHaveLength(3);
  });
});

describe('guardar una versión', () => {
  it('crea la versión siguiente a la vigente y deja intactas las anteriores', async () => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1, nombre: 'SMS', versiones: 2 }));
    const antes = JSON.stringify(api.definiciones[0].versiones);

    const r = await llamar(api, 'POST', '/definiciones-columnas/1/versiones', entrada(null, [COLUMNA('nuevo')]));

    expect(r.estado).toBe(201);
    expect(r.cuerpo).toMatchObject({ version_vigente: 3, version: { numero: 3, usada: false } });
    expect(r.cuerpo.version.contenido.columnas[0].nombre).toBe('nuevo');
    expect(JSON.stringify(api.definiciones[0].versiones.slice(0, 2))).toBe(antes);
    expect(api.definiciones[0].versiones).toHaveLength(3);
  });

  it('el nombre puede faltar o ser el mismo, pero no otro', async () => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1, nombre: 'SMS' }));

    const mismo = await llamar(api, 'POST', '/definiciones-columnas/1/versiones', entrada(' sms '));
    const otro = await llamar(api, 'POST', '/definiciones-columnas/1/versiones', entrada('Otro nombre'));

    expect(mismo.estado).toBe(201);
    expect(otro.estado).toBe(400);
    expect(otro.cuerpo.problemas[0]).toMatchObject({ campo: 'nombre' });
    expect(api.definiciones[0].versiones).toHaveLength(2);
  });

  it('una definición que no existe da 404', async () => {
    const api = apiDefiniciones();

    const r = await llamar(api, 'POST', '/definiciones-columnas/9/versiones', entrada(null));

    expect(r.estado).toBe(404);
    expect(r.cuerpo.codigo).toBe('definicion_no_encontrada');
  });
});

describe('respuestas guionadas y registro', () => {
  it('una respuesta guionada gana sobre el comportamiento y se repite la última', async () => {
    const api = apiDefiniciones();
    api.respuestas.crear = [{ estado: 500, cuerpo: { detail: 'boom' } }];

    const a = await llamar(api, 'POST', '/definiciones-columnas', entrada('SMS'));
    const b = await llamar(api, 'POST', '/definiciones-columnas', entrada('SMS'));

    expect(a.estado).toBe(500);
    expect(b.estado).toBe(500);
    expect(api.definiciones).toHaveLength(0);
  });

  it('registra cada pedido con su método, su ruta y su cuerpo', async () => {
    const api = apiDefiniciones();

    await llamar(api, 'GET', '/definiciones-columnas');
    await llamar(api, 'POST', '/definiciones-columnas', entrada('SMS'));

    expect(api.pedidos.map((p) => [p.metodo, p.ruta])).toEqual([
      ['GET', '/definiciones-columnas'],
      ['POST', '/definiciones-columnas'],
    ]);
    expect((api.pedidos[1].cuerpo as { nombre: string }).nombre).toBe('SMS');
  });
});
