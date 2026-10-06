/**
 * The rich-text engine's fake, chained into `montarApi`. Screens that use the
 * engine (the column builder, the MOWA MES speech) build their tests on it,
 * so it has to answer like the backend does: a context it does not know is a
 * 404 with its code, a text with problems is a 200, and a preview by segment
 * brings one row per segment with the segment's key.
 */
import { expect, test, type Page } from '@playwright/test';

import { apiVacia, montarApi } from './api-falsa';
import { apiTextoEnriquecidoVacia, manejarTextoEnriquecido } from './api-falsa-texto-enriquecido';

async function pedir(page: Page, ruta: string, cuerpo?: unknown) {
  return page.evaluate(
    async ([r, c]) => {
      const respuesta = await fetch(`/api${r}`, c === undefined
        ? undefined
        : { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(c) });
      return { estado: respuesta.status, cuerpo: await respuesta.json() };
    },
    [ruta, cuerpo] as const,
  );
}

async function preparar(page: Page) {
  const motor = apiTextoEnriquecidoVacia();
  const api = apiVacia();
  api.manejadores = [manejarTextoEnriquecido(motor)];
  await montarApi(page, api);
  await page.goto('/cargas');
  return { api, motor };
}

test('el catálogo responde por contexto y un contexto desconocido es 404 con su código', async ({ page }) => {
  await preparar(page);

  const speech = await pedir(page, '/texto-enriquecido/catalogo?contexto=mowa_mes.speech');
  const desconocido = await pedir(page, '/texto-enriquecido/catalogo?contexto=no_existe');

  expect(speech.estado).toBe(200);
  expect(speech.cuerpo.contexto.limite_largo).toBe(160);
  expect(desconocido.estado).toBe(404);
  expect(desconocido.cuerpo.codigo).toBe('contexto_desconocido');
});

test('una expresión con problemas responde 200 con la lista, como el backend', async ({ page }) => {
  const { motor } = await preparar(page);
  motor.validacion = () => ({
    problemas: [{ codigo: 'variable_desconocida', detalle: 'x', ubicacion: { nodo: 0, funcion: null, parametro: null }, nombre: null, columna: null, segmento: null, campo: null }],
    tipo: null,
    cota: null,
    sin_cota: null,
    variables: [],
  });

  const respuesta = await pedir(page, '/texto-enriquecido/validacion', { contexto: 'cartera', expresion: { nodos: [] } });

  expect(respuesta.estado).toBe(200);
  expect(respuesta.cuerpo.problemas[0].codigo).toBe('variable_desconocida');
});

test('la previsualización por segmento trae una fila por segmento, con su clave', async ({ page }) => {
  await preparar(page);

  const respuesta = await pedir(page, '/texto-enriquecido/previsualizacion', {
    contexto: 'mowa_mes.speech',
    expresion: {
      nodos: [
        { tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'primeros', args: [8] }] },
        { tipo: 'texto', valor: ', tu cuota vence el ' },
        { tipo: 'variable', nombre: 'fecha_vencimiento_cuota', funciones: [{ nombre: 'formato_fecha', args: ['dd/mm/aaaa'] }] },
      ],
    },
    muestra: { tipo: 'ejemplos_por_segmento', cantidad: 5 },
  });

  expect(respuesta.estado).toBe(200);
  expect(respuesta.cuerpo.filas.map((f: { segmento: string }) => f.segmento)).toEqual(['preventiva', '1_a_8', '9_a_30']);
  expect(respuesta.cuerpo.filas[0].columnas[0].texto).toBe('NOMBRE S, tu cuota vence el 05/10/2026');
});

test('un pagaré que no está en la muestra responde 404 con su código', async ({ page }) => {
  await preparar(page);

  const respuesta = await pedir(page, '/texto-enriquecido/previsualizacion', {
    contexto: 'cartera',
    expresion: { nodos: [] },
    muestra: { tipo: 'producto_real', fecha_corte: '2026-09-10', pagare: '000000000000000999', cantidad: 1 },
  });

  expect(respuesta.estado).toBe(404);
  expect(respuesta.cuerpo.codigo).toBe('producto_no_encontrado');
});

test('lo que el manejador no atiende sigue llegando al 404 de montarApi', async ({ page }) => {
  await preparar(page);

  const respuesta = await pedir(page, '/ruta/que/no/existe');

  expect(respuesta.estado).toBe(404);
  expect(respuesta.cuerpo.detail).toContain('sin ruta falsa');
});
