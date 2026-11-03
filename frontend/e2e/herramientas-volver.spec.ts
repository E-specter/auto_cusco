/**
 * Ir y volver desde un canal (T-HI-F3, RF-74; docs/motor-texto-enriquecido-interfaz.md §12): Columnas de carga,
 * Supervisores y Calendario laboral con `?volver=` de MOWA MES o de WhatsMKT. Cada herramienta con un `volver` válido
 * muestra su aviso y su enlace, y con uno inválido no muestra nada. La pantalla de origen es del canal: aquí un destino
 * mínimo que solo deja ver adónde se fue. La plataforma es sintética. Todo es inventado.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { apiSupervisionCalendario, apiVacia, montarApi, montarApiSupervisionCalendario } from './api-falsa';
import {
  apiDefiniciones,
  contenidoSintetico,
  definicionFalsa,
  manejadorDefiniciones,
  plataformaSintetica,
  type ApiFalsaDefiniciones,
} from './api-falsa-definiciones';
import { apiTextoEnriquecidoVacia, manejarTextoEnriquecido } from './api-falsa-texto-enriquecido';

const CAMPANA_WM = '/whatsmkt/campana';

/** The channel's screen is not here: any page of it answers, so a test sees where the analyst went. */
async function canalesDeMentira(page: Page): Promise<void> {
  await page.route(/\/(whatsmkt|mowa-mes)\/campana/, (ruta) =>
    ruta.fulfill({ status: 200, contentType: 'text/html', body: '<!doctype html><title>canal</title><p>canal</p>' }),
  );
}

async function abrirColumnas(page: Page, consulta: string, api: ApiFalsaDefiniciones = apiDefiniciones()): Promise<ApiFalsaDefiniciones> {
  const base = apiVacia();
  base.manejadores = [manejarTextoEnriquecido(apiTextoEnriquecidoVacia()), manejadorDefiniciones(api)];
  await canalesDeMentira(page);
  await montarApi(page, base);
  await page.goto(`/columnas${consulta}`);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expect(page.locator('[data-contenido]')).toBeVisible();
  return api;
}

const conPlataforma = (): ApiFalsaDefiniciones => {
  const api = apiDefiniciones();
  api.plataformas = [plataformaSintetica()];
  return api;
};

const volverWm = (ruta = CAMPANA_WM) => `volver=${encodeURIComponent(ruta)}`;
const aviso = (page: Page) => page.locator('[data-volver]');
const enlace = (page: Page) => page.locator('[data-volver-enlace]');
const pedidosA = (api: ApiFalsaDefiniciones, metodo: string, ruta: string) =>
  api.pedidos.filter((p) => p.metodo === metodo && p.ruta.split('?')[0] === ruta);

test.describe('Columnas de carga con una definición abierta', () => {
  test('el aviso dice el canal por su prefijo, y «Volver … sin guardar» va a volver tal como llegó', async ({ page }) => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1, nombre: 'Envío de prueba' }));
    await abrirColumnas(page, `?definicion=1&${volverWm('/whatsmkt/campana?a=1&b=2')}`, api);

    await expect(page.getByLabel('Definición guardada')).toHaveValue('1');
    await expect(aviso(page)).toBeVisible();
    await expect(aviso(page)).toContainText('Estás editando una definición de columnas desde WhatsMKT. Al guardarla, vuelves a WhatsMKT.');
    await expect(enlace(page)).toHaveText('Volver a WhatsMKT sin guardar');
    await expect(enlace(page)).toHaveAttribute('href', '/whatsmkt/campana?a=1&b=2');
  });

  test('con volver de MOWA MES dice MOWA MES', async ({ page }) => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1 }));
    await abrirColumnas(page, `?definicion=1&${volverWm('/mowa-mes/campana')}`, api);
    await expect(aviso(page)).toContainText('desde MOWA MES. Al guardarla, vuelves a MOWA MES.');
    await expect(enlace(page)).toHaveText('Volver a MOWA MES sin guardar');
  });

  test('en inglés dice lo mismo con sus palabras', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' })));
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1 }));
    await abrirColumnas(page, `?definicion=1&${volverWm()}`, api);
    await expect(aviso(page)).toContainText('You are editing a column definition from WhatsMKT. Once you save it, you go back to WhatsMKT.');
    await expect(enlace(page)).toHaveText('Back to WhatsMKT without saving');
  });

  for (const invalido of ['//evil.com/whatsmkt/campana', 'https://evil.com/whatsmkt/campana', 'javascript:alert(1)', '/cartera', '/whatsmkt/../cartera', '']) {
    test(`un volver inválido (${invalido || 'vacío'}) no muestra nada: la pantalla queda como hoy`, async ({ page }) => {
      const api = apiDefiniciones();
      api.definiciones.push(definicionFalsa({ id: 1 }));
      await abrirColumnas(page, `?definicion=1&volver=${encodeURIComponent(invalido)}`, api);
      await expect(page.getByLabel('Definición guardada')).toHaveValue('1');
      await expect(aviso(page)).toBeHidden();
    });
  }

  test('sin volver, nada de esto aparece y guardar no navega', async ({ page }) => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1 }));
    await abrirColumnas(page, '?definicion=1', api);
    await expect(aviso(page)).toBeHidden();
    await page.getByLabel('Nombre de la columna 1').fill('telefono_2');
    await page.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByText('Guardada como versión 2.')).toBeVisible();
    await expect(page).toHaveURL(/\/columnas\?definicion=1$/);
  });
});

test.describe('guardar vuelve (§12.3)', () => {
  test('una versión nueva vuelve a volver con definicion y version, reemplazando los que hubiera', async ({ page }) => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1 }));
    await abrirColumnas(page, `?definicion=1&${volverWm('/whatsmkt/campana?definicion=9&version=9&x=1')}`, api);

    await page.getByLabel('Nombre de la columna 1').fill('telefono_2');
    await page.getByRole('button', { name: 'Guardar' }).click();

    await page.waitForURL(/\/whatsmkt\/campana\?/);
    const url = new URL(page.url());
    expect(url.pathname).toBe('/whatsmkt/campana');
    expect(url.searchParams.get('definicion')).toBe('1');
    expect(url.searchParams.get('version')).toBe('2');
    expect(url.searchParams.get('x')).toBe('1');
    expect(pedidosA(api, 'POST', '/definiciones-columnas/1/versiones')).toHaveLength(1);
  });

  test('una definición nueva con plataforma vuelve con su id y la versión 1', async ({ page }) => {
    const api = await abrirColumnas(page, `?plataforma=sintetica&${volverWm()}`, conPlataforma());
    await page.getByLabel('Nombre', { exact: true }).fill('Para WhatsMKT');
    await page.getByRole('button', { name: 'Guardar' }).click();

    await page.waitForURL(/\/whatsmkt\/campana\?/);
    const url = new URL(page.url());
    expect(url.searchParams.get('definicion')).toBe(String(api.definiciones[0].id));
    expect(url.searchParams.get('version')).toBe('1');
    expect((pedidosA(api, 'POST', '/definiciones-columnas')[0].cuerpo as { plataforma?: string }).plataforma).toBe('sintetica');
  });

  test('renombrar no vuelve: no es el guardado de la definición', async ({ page }) => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1, nombre: 'Envío de prueba' }));
    await abrirColumnas(page, `?definicion=1&${volverWm()}`, api);
    await page.getByRole('button', { name: 'Renombrar' }).click();
    const dialogo = page.getByRole('dialog', { name: /Renombrar/ });
    await dialogo.getByLabel('Nombre nuevo').fill('Otro nombre');
    await dialogo.getByRole('button', { name: 'Renombrar' }).click();
    await expect(page.getByText(/Renombrada a/)).toBeVisible();
    await expect(page).toHaveURL(/\/columnas\?/);
  });

  test('un guardado que el backend rechaza no vuelve', async ({ page }) => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1 }));
    api.respuestas.guardarVersion = [{ estado: 409, cuerpo: { detail: 'x', codigo: 'otro' } }];
    await abrirColumnas(page, `?definicion=1&${volverWm()}`, api);
    await page.getByLabel('Nombre de la columna 1').fill('telefono_2');
    await page.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page).toHaveURL(/\/columnas\?/);
  });
});

test.describe('«Volver sin guardar» (§12.2)', () => {
  test('sin cambios vuelve de una vez, a volver tal como llegó', async ({ page }) => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1 }));
    await abrirColumnas(page, `?definicion=1&${volverWm('/whatsmkt/campana?x=1')}`, api);
    await enlace(page).click();
    await page.waitForURL(/\/whatsmkt\/campana/);
    expect(new URL(page.url()).search).toBe('?x=1');
  });

  test('con cambios pide confirmar con el diálogo de siempre; «Seguir editando» se queda', async ({ page }) => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1 }));
    await abrirColumnas(page, `?definicion=1&${volverWm()}`, api);
    await page.getByLabel('Nombre de la columna 1').fill('telefono_2');

    await enlace(page).click();
    const dialogo = page.getByRole('dialog', { name: 'Hay cambios sin guardar' });
    await expect(dialogo).toBeVisible();
    await expect(dialogo.getByText('Los cambios que no guardaste se pierden.')).toBeVisible();
    await dialogo.getByRole('button', { name: 'Seguir editando' }).click();
    await expect(dialogo).toBeHidden();
    await expect(page).toHaveURL(/\/columnas\?/);
    await expect(page.getByLabel('Nombre de la columna 1')).toHaveValue('telefono_2');

    await enlace(page).click();
    await dialogo.getByRole('button', { name: 'Descartar cambios' }).click();
    await page.waitForURL(/\/whatsmkt\/campana$/);
    expect(pedidosA(api, 'POST', '/definiciones-columnas/1/versiones')).toHaveLength(0);
  });
});

test.describe('?plataforma= y ?definicion= (§12.5)', () => {
  test('?plataforma= abre una definición nueva con esa plataforma, el select inactivo con su hint y sin diálogo de cambiar', async ({ page }) => {
    await abrirColumnas(page, `?plataforma=sintetica&${volverWm()}`, conPlataforma());

    const select = page.getByLabel('Plataforma', { exact: true });
    await expect(select).toHaveValue('sintetica');
    await expect(select).toBeDisabled();
    await expect(page.getByText('La fija WhatsMKT: se abrió desde allí.')).toBeVisible();
    await expect(page.getByLabel('Nombre de la columna 1')).toHaveValue('destino');
    await expect(aviso(page)).toContainText('Estás creando una definición de Sintética. Al guardarla, vuelves a WhatsMKT.');
    await expect(page.getByLabel('Definición guardada')).toHaveValue('');
    // «Nueva definición» no la suelta: sigue siendo de la plataforma.
    await page.getByRole('button', { name: 'Nueva definición' }).click();
    await expect(page.getByLabel('Nombre de la columna 1')).toHaveValue('destino');
    await expect(page.getByRole('dialog')).toHaveCount(0);
  });

  test('una plataforma que nadie registró se ignora y el select queda libre', async ({ page }) => {
    await abrirColumnas(page, `?plataforma=otra&${volverWm()}`, conPlataforma());
    const select = page.getByLabel('Plataforma', { exact: true });
    await expect(select).toHaveValue('');
    await expect(select).toBeEnabled();
    await expect(page.getByText('Una plataforma fija algunas columnas y no se cambia después.')).toBeVisible();
  });

  test('sin volver válido la plataforma viene elegida pero no fijada por nadie', async ({ page }) => {
    await abrirColumnas(page, '?plataforma=sintetica', conPlataforma());
    const select = page.getByLabel('Plataforma', { exact: true });
    await expect(select).toHaveValue('sintetica');
    await expect(select).toBeEnabled();
    await expect(aviso(page)).toBeHidden();
  });

  test('si llegan definicion y plataforma, gana definicion', async ({ page }) => {
    const api = conPlataforma();
    api.definiciones.push(definicionFalsa({ id: 1, nombre: 'Envío de prueba' }));
    await abrirColumnas(page, `?definicion=1&plataforma=sintetica&${volverWm()}`, api);
    await expect(page.getByLabel('Definición guardada')).toHaveValue('1');
    await expect(page.getByLabel('Nombre de la columna 1')).toHaveValue('telefono');
    await expect(page.getByLabel('Plataforma', { exact: true })).toBeHidden();
  });

  test('?definicion= de una que no existe deja una definición nueva con su aviso, nunca un error', async ({ page }) => {
    await abrirColumnas(page, `?definicion=999&${volverWm()}`);
    await expect(page.getByLabel('Definición guardada')).toHaveValue('');
    await expect(page.getByText('La definición que abriste ya no existe. Arma una nueva o elige otra de la lista.')).toBeVisible();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    // El aviso de volver sigue: se puede volver.
    await expect(aviso(page)).toBeVisible();
  });

  test('el aviso de «no existe» se va al abrir otra definición', async ({ page }) => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1, nombre: 'Envío de prueba' }));
    await abrirColumnas(page, `?definicion=999&${volverWm()}`, api);
    await expect(page.locator('[data-definicion-no-existe]')).toBeVisible();
    await page.getByLabel('Definición guardada').selectOption('1');
    await expect(page.locator('[data-definicion-no-existe]')).toBeHidden();
  });

  test('un ?definicion= que no es un entero positivo se ignora', async ({ page }) => {
    await abrirColumnas(page, `?definicion=abc&${volverWm()}`);
    await expect(page.getByLabel('Definición guardada')).toHaveValue('');
    await expect(page.locator('[data-definicion-no-existe]')).toBeHidden();
  });
});

// ---- Supervisores y Calendario: la herramienta no vuelve sola, solo con su enlace ---------------------------------

async function abrirSupervision(page: Page, ruta: string, consulta: string) {
  // The same fixed clock as the calendar's own spec: the year of the page and of the fake must not depend on the runner's.
  await page.clock.setFixedTime(new Date('2026-10-15T12:00:00-05:00'));
  await canalesDeMentira(page);
  const api = apiSupervisionCalendario();
  await montarApiSupervisionCalendario(page, api);
  await page.goto(`${ruta}${consulta}`);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  return api;
}

for (const herramienta of [
  {
    ruta: '/supervisores',
    contenido: '[data-contenido]',
    linea: 'Llegaste desde WhatsMKT. Guarda los supervisores antes de volver: lo que no guardes se pierde.',
  },
  {
    ruta: '/calendario',
    contenido: '[data-anio]',
    linea: 'Llegaste desde WhatsMKT. Cada cambio se guarda al hacerlo; cuando termines, vuelve.',
  },
]) {
  test.describe(`${herramienta.ruta} con volver`, () => {
    test('muestra su aviso con el canal y el enlace «Volver a {canal}», que vuelve a volver tal como llegó', async ({ page }) => {
      await abrirSupervision(page, herramienta.ruta, `?${volverWm('/whatsmkt/campana?x=1')}`);
      await expect(page.locator(herramienta.contenido)).toBeVisible();
      await expect(aviso(page)).toBeVisible();
      await expect(aviso(page)).toContainText(herramienta.linea);
      await expect(enlace(page)).toHaveText('Volver a WhatsMKT');
      await enlace(page).click();
      await page.waitForURL(/\/whatsmkt\/campana/);
      expect(new URL(page.url()).search).toBe('?x=1');
    });

    test('con volver de MOWA MES dice MOWA MES', async ({ page }) => {
      await abrirSupervision(page, herramienta.ruta, `?${volverWm('/mowa-mes/campana')}`);
      await expect(enlace(page)).toHaveText('Volver a MOWA MES');
    });

    for (const invalido of ['//evil.com/whatsmkt/campana', 'https://evil.com/whatsmkt/', 'javascript:alert(1)', '/cartera']) {
      test(`un volver inválido (${invalido}) no muestra nada`, async ({ page }) => {
        await abrirSupervision(page, herramienta.ruta, `?volver=${encodeURIComponent(invalido)}`);
        await expect(aviso(page)).toBeHidden();
      });
    }

    test('sin volver no hay aviso', async ({ page }) => {
      await abrirSupervision(page, herramienta.ruta, '');
      await expect(aviso(page)).toBeHidden();
    });
  });
}

test('en Calendario laboral un cambio no navega', async ({ page }) => {
  const api = await abrirSupervision(page, '/calendario', `?${volverWm()}`);
  await expect(page.getByRole('button', { name: /Quitar el día no laborable/ })).toBeVisible();
  await page.getByRole('button', { name: /Quitar el día no laborable/ }).click();
  await expect(page.getByRole('row', { name: /Día no laborable sintético/ })).toHaveCount(0);
  expect(api.pedidos.some((p) => p.metodo === 'DELETE')).toBe(true);
  await expect(page).toHaveURL(/\/calendario\?/);
  await expect(aviso(page)).toBeVisible();
});

test('en Supervisores con un borrador, el enlace pide confirmar; «Seguir editando» se queda y «Descartar cambios» vuelve sin guardar nada', async ({ page }) => {
  const api = await abrirSupervision(page, '/supervisores', `?${volverWm()}`);
  await page.getByRole('button', { name: 'Agregar supervisor' }).click();
  await page.getByLabel('Número del supervisor 3').fill('900000103');

  await enlace(page).click();
  const dialogo = page.getByRole('dialog', { name: 'Hay cambios sin guardar' });
  await expect(dialogo).toBeVisible();
  await expect(dialogo.getByText('Los cambios que no guardaste se pierden.')).toBeVisible();
  await dialogo.getByRole('button', { name: 'Seguir editando' }).click();
  await expect(dialogo).toBeHidden();
  await expect(page).toHaveURL(/\/supervisores\?/);
  await expect(page.getByLabel('Número del supervisor 3')).toHaveValue('900000103');

  await enlace(page).click();
  await dialogo.getByRole('button', { name: 'Descartar cambios' }).click();
  await page.waitForURL(/\/whatsmkt\/campana$/);
  expect(api.pedidos.some((p) => p.metodo === 'PUT')).toBe(false);
});

test('en Supervisores sin borrador el enlace vuelve directo, y tras guardar también (guardar no navega, el enlace sí)', async ({ page }) => {
  await abrirSupervision(page, '/supervisores', `?${volverWm()}`);
  await page.getByRole('button', { name: 'Agregar supervisor' }).click();
  await page.getByLabel('Número del supervisor 3').fill('900000103');
  await page.getByLabel('Procedencia del supervisor 3').selectOption('Procedencia A');
  await page.getByRole('button', { name: 'Guardar supervisores' }).click();
  await expect(page.getByText('Guardado.')).toBeVisible();
  await expect(page).toHaveURL(/\/supervisores\?/);
  await enlace(page).click();
  await page.waitForURL(/\/whatsmkt\/campana$/);
});

test('en Supervisores un cambio y su guardado no navegan', async ({ page }) => {
  const api = await abrirSupervision(page, '/supervisores', `?${volverWm()}`);
  await page.getByRole('button', { name: 'Agregar supervisor' }).click();
  await page.getByLabel('Número del supervisor 3').fill('900000103');
  await page.getByLabel('Procedencia del supervisor 3').selectOption('Procedencia A');
  await page.getByRole('button', { name: 'Guardar supervisores' }).click();
  await expect(page.getByText('Guardado.')).toBeVisible();
  expect(api.pedidos.some((p) => p.metodo === 'PUT')).toBe(true);
  await expect(page).toHaveURL(/\/supervisores\?/);
});

// ---- Accesibilidad: el aviso a la vista en las tres herramientas ---------------------------------------------------

async function sinViolaciones(page: Page): Promise<void> {
  const previa = page.locator('[data-previa]');
  if ((await previa.count()) > 0) await expect(previa).toHaveAttribute('data-calculando', 'false');
  const resultado = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(resultado.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
}

async function abrirHerramienta(page: Page, cual: 'columnas' | 'supervisores' | 'calendario') {
  if (cual === 'columnas') {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1 }));
    await abrirColumnas(page, `?definicion=1&${volverWm()}`, api);
  } else {
    await abrirSupervision(page, `/${cual}`, `?${volverWm()}`);
  }
  await expect(aviso(page)).toBeVisible();
}

test.describe('accesibilidad del aviso de volver', () => {
  test.use({ reducedMotion: 'reduce' });

  for (const tema of ['light', 'dark'] as const) {
    for (const cual of ['columnas', 'supervisores', 'calendario'] as const) {
      test(`${cual}, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, async ({ page }) => {
        await page.addInitScript((elegido) => {
          localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
        }, tema);
        await abrirHerramienta(page, cual);
        await sinViolaciones(page);
      });
    }
  }

  for (const cual of ['columnas', 'supervisores', 'calendario'] as const) {
    test(`${cual} a 360 px, sin desbordar`, async ({ page }) => {
      await page.setViewportSize({ width: 360, height: 800 });
      await abrirHerramienta(page, cual);
      await sinViolaciones(page);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
    });
  }

  test('el diálogo de volver sin guardar, en claro y en oscuro', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('app:appearance', JSON.stringify({ theme: 'dark', language: 'es' })));
    await abrirHerramienta(page, 'columnas');
    await page.getByLabel('Nombre de la columna 1').fill('telefono_2');
    await enlace(page).click();
    await expect(page.getByRole('dialog', { name: 'Hay cambios sin guardar' })).toBeVisible();
    await sinViolaciones(page);
  });
});
