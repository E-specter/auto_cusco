/**
 * Going to Columnas de carga and coming back, from the WhatsMKT campaign and from the settings (T-WM-F2b, docs/motor-texto-enriquecido-interfaz.md §12),
 * end to end against an intercepted API: the link that goes (to the definition chosen, to create one, or only with its way back), what each screen does
 * with `?definicion=&version=` when Columnas sends the analyst back (chooses it and says so, says it is gone, says it is not WhatsMKT's), the URL left
 * clean, and the links of the other tools with their way back. The clock is fixed from the first spec, in `montarApiWhatsmkt`. Every text is invented.
 */
import { expect, test, type Page } from '@playwright/test';

import { apiVacia, montarApi } from './api-falsa';
import { apiDefiniciones, definicionFalsa, manejadorDefiniciones, plataformaSintetica, type ApiFalsaDefiniciones } from './api-falsa-definiciones';
import { apiTextoEnriquecidoVacia, manejarTextoEnriquecido } from './api-falsa-texto-enriquecido';
import { apiWhatsmkt, definicionSintetica, montarApiWhatsmkt, type ApiFalsaWhatsmkt } from './api-falsa-whatsmkt';
import { campanaFalsa, montarCampanaWhatsmkt } from './api-falsa-whatsmkt-campana';
import { mensajesFalsos, montarMensajesWhatsmkt } from './api-falsa-whatsmkt-mensajes';
import { montarSeleccion } from './apoyo-seleccion';

const CAMPANA = '/whatsmkt/campana';
const CONFIGURACION = '/whatsmkt/configuracion';

/** The definition 12 has three versions; 14 is a free one (of no platform), 13 is another channel's. */
function api(): ApiFalsaWhatsmkt {
  const a = apiWhatsmkt();
  a.configuracion.definicion_defecto_id = 11;
  a.definiciones = a.definiciones.map((d) => (d.id === 12 ? { ...d, version_vigente: 3, cantidad_versiones: 3 } : d));
  a.definiciones.push(definicionSintetica(14, 'Carga libre', null));
  return a;
}

const pedidosA = (a: ApiFalsaWhatsmkt, metodo: string, ruta: string) => a.pedidos.filter((p) => p.metodo === metodo && p.ruta.split('?')[0] === ruta);

async function abrirCampana(page: Page, busqueda = '', a = api()): Promise<ApiFalsaWhatsmkt> {
  await montarApiWhatsmkt(page, a);
  await montarCampanaWhatsmkt(page, campanaFalsa());
  await montarSeleccion(page);
  await page.goto(`${CAMPANA}${busqueda}`);
  // By its attribute, not by its label, so it also works in English.
  await page.locator('[data-selector-guardada]').selectOption({ label: 'Preventiva top 1000' });
  await expect(page.locator('[data-formulario]')).toBeVisible();
  return a;
}

async function abrirConfiguracion(page: Page, busqueda = '', a = api()): Promise<ApiFalsaWhatsmkt> {
  await montarApiWhatsmkt(page, a);
  await montarMensajesWhatsmkt(page, mensajesFalsos());
  await page.goto(`${CONFIGURACION}${busqueda}`);
  await expect(page.getByRole('heading', { name: 'Configuración de WhatsMKT', level: 1 })).toBeVisible();
  await expect(page.locator('#wm-definicion')).toBeEnabled();
  return a;
}

const select = (page: Page) => page.locator('#wm-definicion');
const anuncio = (page: Page) => page.locator('[data-definicion-anuncio]');
const noExiste = (page: Page) => page.locator('[data-definicion-noexiste]');
const errorDefinicion = (page: Page) => page.locator('[data-definicion-error]');
const columnas = (page: Page) => page.locator('[data-columnas]');

test.describe('desde la campaña, el enlace a Columnas de carga', () => {
  test('edita la definición elegida y vuelve a la campaña', async ({ page }) => {
    await abrirCampana(page);

    await expect(columnas(page)).toHaveText('Editar en Columnas de carga');
    // The saved selection travels in the way back: the campaign comes back with it chosen.
    await expect(columnas(page)).toHaveAttribute('href', /^\/columnas\?definicion=11&volver=%2Fwhatsmkt%2Fcampana%3Fseleccion%3D\d+$/);
  });

  test('al elegir otra definición, el enlace pasa a editar esa', async ({ page }) => {
    await abrirCampana(page);

    await select(page).selectOption({ label: 'Contactos WhatsMKT con apellido' });

    await expect(columnas(page)).toHaveAttribute('href', /^\/columnas\?definicion=12&volver=/);
  });

  test('con definiciones y ninguna elegida abre Columnas con solo el camino de vuelta, y sigue diciendo «Editar»', async ({ page }) => {
    const a = api();
    a.configuracion.definicion_defecto_id = null;
    await abrirCampana(page, '', a);
    await expect(columnas(page)).toHaveText('Editar en Columnas de carga');
    await expect(columnas(page)).toHaveAttribute('href', /^\/columnas\?volver=%2Fwhatsmkt%2Fcampana/);
  });

  test('sin definiciones de WhatsMKT crea una de la plataforma, y vuelve a la campaña', async ({ page }) => {
    const a = api();
    a.configuracion.definicion_defecto_id = null;
    a.definiciones = a.definiciones.filter((d) => d.plataforma !== 'whatsmkt');
    await abrirCampana(page, '', a);

    await expect(columnas(page)).toHaveText('Crear en Columnas de carga');
    await expect(columnas(page)).toHaveAttribute('href', /^\/columnas\?plataforma=whatsmkt&volver=%2Fwhatsmkt%2Fcampana%3Fseleccion%3D\d+$/);
  });
});

test.describe('la campaña, de vuelta de Columnas de carga', () => {
  test('elige la definición y la versión que vuelven, lo anuncia y deja la URL limpia', async ({ page }) => {
    await abrirCampana(page, '?definicion=12&version=3');

    await expect(select(page)).toHaveValue('12');
    await expect(anuncio(page)).toHaveText('Se eligió «Contactos WhatsMKT con apellido», versión 3.');
    await expect(noExiste(page)).toBeHidden();
    await expect(page).toHaveURL(/\/whatsmkt\/campana$/);
    await expect(columnas(page)).toHaveAttribute('href', /^\/columnas\?definicion=12&volver=/);
  });

  test('con una versión vieja, anuncia la que queda elegida (la vigente), no la de la URL', async ({ page }) => {
    await abrirCampana(page, '?definicion=12&version=1');

    await expect(select(page)).toHaveValue('12');
    await expect(anuncio(page)).toHaveText('Se eligió «Contactos WhatsMKT con apellido», versión 3.');
    await expect(page.locator('[data-version-linea]')).toHaveText('Versión 3 · WhatsMKT');
  });

  test('recargar no la vuelve a aplicar', async ({ page }) => {
    await abrirCampana(page, '?definicion=12&version=3');
    await expect(select(page)).toHaveValue('12');

    await page.reload();
    await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });

    await expect(select(page)).toHaveValue('11');
    await expect(anuncio(page)).toHaveText('');
  });

  test('conserva la selección que viajó en el camino de vuelta, y quita solo definición y versión', async ({ page }) => {
    await montarApiWhatsmkt(page, api());
    await montarCampanaWhatsmkt(page, campanaFalsa());
    await montarSeleccion(page);
    await page.goto(`${CAMPANA}?seleccion=1&definicion=12&version=1`);

    await expect(page.getByLabel('Selección guardada')).toHaveValue('1');
    await expect(select(page)).toHaveValue('12');
    await expect(page).toHaveURL(/\/whatsmkt\/campana$/);
  });

  test('una definición que ya no existe dice que ya no existe y deja el campo sin elegir', async ({ page }) => {
    await abrirCampana(page, '?definicion=99&version=1');

    await expect(noExiste(page)).toBeVisible();
    await expect(noExiste(page)).toHaveClass(/notice--warning/);
    await expect(noExiste(page)).toContainText('La definición que editaste ya no existe. Elige otra.');
    await expect(select(page)).toHaveValue('');
    await expect(anuncio(page)).toHaveText('');
    await expect(page).toHaveURL(/\/whatsmkt\/campana$/);
  });

  test('una versión que no existe tampoco existe', async ({ page }) => {
    await abrirCampana(page, '?definicion=12&version=4');

    await expect(noExiste(page)).toBeVisible();
    await expect(select(page)).toHaveValue('');
  });

  test('aviso y campo se limpian al elegir otra definición', async ({ page }) => {
    await abrirCampana(page, '?definicion=99&version=1');
    await expect(noExiste(page)).toBeVisible();

    await select(page).selectOption({ label: 'Contactos WhatsMKT' });

    await expect(noExiste(page)).toBeHidden();
    await expect(columnas(page)).toHaveAttribute('href', /^\/columnas\?definicion=11&volver=/);
  });

  test('una definición que no es de WhatsMKT dice definicion_no_whatsmkt bajo el campo y lo deja sin elegir', async ({ page }) => {
    await abrirCampana(page, '?definicion=14&version=1');

    await expect(errorDefinicion(page)).toHaveText('La definición elegida no es de WhatsMKT.');
    await expect(select(page)).toHaveValue('');
    await expect(select(page)).toHaveAttribute('aria-invalid', 'true');
    await expect(anuncio(page)).toHaveText('');

    await select(page).selectOption({ label: 'Contactos WhatsMKT' });
    await expect(errorDefinicion(page)).toHaveText('');
  });

  test('la de otro canal tampoco es de WhatsMKT', async ({ page }) => {
    await abrirCampana(page, '?definicion=13&version=1');

    await expect(errorDefinicion(page)).toHaveText('La definición elegida no es de WhatsMKT.');
  });

  test('en inglés lo anuncia en inglés', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' })));
    await abrirCampana(page, '?definicion=12&version=3');

    await expect(anuncio(page)).toHaveText('“Contactos WhatsMKT con apellido”, version 3, was chosen.');
  });
});

test.describe('desde la configuración, el panel «Definición por defecto»', () => {
  test('el enlace edita la definición del campo y vuelve a la configuración; sigue al campo', async ({ page }) => {
    await abrirConfiguracion(page);

    await expect(columnas(page)).toHaveAttribute('href', '/columnas?definicion=11&volver=%2Fwhatsmkt%2Fconfiguracion');

    await select(page).selectOption({ label: 'Contactos WhatsMKT con apellido' });
    await expect(columnas(page)).toHaveAttribute('href', '/columnas?definicion=12&volver=%2Fwhatsmkt%2Fconfiguracion');
  });

  test('de vuelta, la definición queda elegida en el campo para guardar, y no se guarda sola', async ({ page }) => {
    const a = await abrirConfiguracion(page, '?definicion=12&version=3');

    await expect(select(page)).toHaveValue('12');
    await expect(anuncio(page)).toHaveText('Se eligió «Contactos WhatsMKT con apellido», versión 3. Falta guardarla como definición por defecto.');
    await expect(page).toHaveURL(/\/whatsmkt\/configuracion$/);
    expect(pedidosA(a, 'PUT', CONFIGURACION)).toHaveLength(0);

    await page.getByRole('button', { name: 'Guardar definición' }).click();

    await expect(page.locator('[data-definicion-estado]')).toContainText('Guardado');
    expect(pedidosA(a, 'PUT', CONFIGURACION).at(-1)?.cuerpo).toEqual({ definicion_defecto_id: 12 });
  });

  test('una definición que ya no existe lo dice y deja el campo sin elegir', async ({ page }) => {
    await abrirConfiguracion(page, '?definicion=99&version=1');

    await expect(noExiste(page)).toBeVisible();
    await expect(select(page)).toHaveValue('');
    await expect(page).toHaveURL(/\/whatsmkt\/configuracion$/);

    await select(page).selectOption({ label: 'Contactos WhatsMKT' });
    await expect(noExiste(page)).toBeHidden();
  });

  test('una que no es de WhatsMKT dice definicion_no_whatsmkt bajo el campo', async ({ page }) => {
    await abrirConfiguracion(page, '?definicion=14&version=1');

    await expect(errorDefinicion(page)).toHaveText('La definición elegida no es de WhatsMKT.');
    await expect(select(page)).toHaveValue('');
  });

  test('recargar no la vuelve a aplicar', async ({ page }) => {
    await abrirConfiguracion(page, '?definicion=12&version=3');
    await expect(select(page)).toHaveValue('12');

    await page.reload();

    await expect(select(page)).toHaveValue('11');
    await expect(anuncio(page)).toHaveText('');
  });
});

test.describe('los enlaces de la configuración a las otras herramientas', () => {
  test('Columnas, Supervisores y Calendario llevan el camino de vuelta', async ({ page }) => {
    await abrirConfiguracion(page);
    const aviso = page.locator('[data-herramientas]');

    await expect(aviso.getByRole('link', { name: 'Columnas de carga' })).toHaveAttribute('href', '/columnas?volver=%2Fwhatsmkt%2Fconfiguracion');
    await expect(aviso.getByRole('link', { name: 'Supervisores' })).toHaveAttribute('href', '/supervisores?volver=%2Fwhatsmkt%2Fconfiguracion');
    await expect(aviso.getByRole('link', { name: 'Calendario laboral' })).toHaveAttribute('href', '/calendario?volver=%2Fwhatsmkt%2Fconfiguracion');
  });
});

/**
 * The whole trip, with no page invented: the real WhatsMKT screens and the real Columnas de carga against ONE fake of the definitions, so that what
 * Columnas saves is what the screen of origin finds when it is back. It is where the two sides meet: the names `definicion` and `version` and the
 * encoding of `volver` have to be the same on both.
 */
async function montarViaje(page: Page, whatsmkt: ApiFalsaWhatsmkt, definiciones: ApiFalsaDefiniciones): Promise<void> {
  // Columnas reads the portfolio and the texts; whatever nobody else answers ends here.
  const base = apiVacia();
  base.manejadores = [manejarTextoEnriquecido(apiTextoEnriquecidoVacia())];
  await montarApi(page, base);
  await montarApiWhatsmkt(page, whatsmkt);
  await montarMensajesWhatsmkt(page, mensajesFalsos());
  await montarCampanaWhatsmkt(page, campanaFalsa());
  await montarSeleccion(page);
  // One list of definitions for both sides: this route is registered last, so it answers before the WhatsMKT fake's own.
  const manejar = manejadorDefiniciones(definiciones);
  await page.route('**/api/definiciones-columnas**', async (route) => {
    const url = new URL(route.request().url());
    const ruta = url.pathname.replace(/^\/api/, '');
    if (!(await manejar(route, ruta, route.request().method(), url))) await route.fallback();
  });
}

/**
 * One saved definition of the platform, with its first version, that the settings also have as the default. Columnas knows the platform (without it
 * it refuses to save: «Plataforma desconocida»), with a fixed first column named as the definition's, so that the second one is free to edit.
 */
function viaje(): { whatsmkt: ApiFalsaWhatsmkt; definiciones: ApiFalsaDefiniciones } {
  const whatsmkt = api();
  whatsmkt.configuracion.definicion_defecto_id = 1;
  const definiciones = apiDefiniciones();
  definiciones.plataformas = [
    plataformaSintetica({
      clave: 'whatsmkt',
      etiqueta: 'WhatsMKT',
      columnas_fijas: [{ posicion: 1, nombre: 'telefono', contenido_por_defecto: '[@telefono]', tipo: 'texto', celda_texto: false, contenido_editable: true }],
    }),
  ];
  definiciones.definiciones.push(definicionFalsa({ id: 1, nombre: 'Contactos WhatsMKT', plataforma: 'whatsmkt' }));
  return { whatsmkt, definiciones };
}

const versionesGuardadas = (definiciones: ApiFalsaDefiniciones) =>
  definiciones.pedidos.filter((p) => p.metodo === 'POST' && p.ruta.split('?')[0] === '/definiciones-columnas/1/versiones');

test.describe('el viaje entero con Columnas de carga', () => {
  test('desde la campaña: Editar, guardar una versión nueva en Columnas y volver con ella elegida y la URL limpia', async ({ page }) => {
    const { whatsmkt, definiciones } = viaje();
    await montarViaje(page, whatsmkt, definiciones);
    await page.goto(CAMPANA);
    await page.locator('[data-selector-guardada]').selectOption({ label: 'Preventiva top 1000' });
    await expect(select(page)).toHaveValue('1');
    await expect(page.locator('[data-version-linea]')).toHaveText('Versión 1 · WhatsMKT');

    await columnas(page).click();

    // The real Columnas, opened on that definition, knowing where it came from.
    await page.waitForURL(/\/columnas\?/);
    await expect(page.getByLabel('Definición guardada')).toHaveValue('1');
    await expect(page.locator('[data-volver]')).toContainText('Estás editando una definición de columnas desde WhatsMKT.');
    await page.getByLabel('Nombre de la columna 2').fill('mensaje_2');
    await page.getByRole('button', { name: 'Guardar' }).click();

    // It comes back by itself, with the new version: the campaign has it chosen, says so and leaves the URL clean.
    await page.waitForURL(/\/whatsmkt\/campana/);
    await expect(select(page)).toHaveValue('1');
    await expect(anuncio(page)).toHaveText('Se eligió «Contactos WhatsMKT», versión 2.');
    await expect(page.locator('[data-version-linea]')).toHaveText('Versión 2 · WhatsMKT');
    await expect(page.locator('[data-selector-guardada]')).toHaveValue('1');
    await expect(page).toHaveURL(/\/whatsmkt\/campana$/);
    expect(versionesGuardadas(definiciones)).toHaveLength(1);
  });

  test('desde la configuración: Editar, guardar en Columnas y volver con la definición elegida en el campo, sin guardarla', async ({ page }) => {
    const { whatsmkt, definiciones } = viaje();
    await montarViaje(page, whatsmkt, definiciones);
    await page.goto(CONFIGURACION);
    await expect(select(page)).toHaveValue('1');

    await columnas(page).click();

    await page.waitForURL(/\/columnas\?/);
    await expect(page.getByLabel('Definición guardada')).toHaveValue('1');
    await expect(page.locator('[data-volver]')).toContainText('desde WhatsMKT');
    await page.getByLabel('Nombre de la columna 2').fill('mensaje_2');
    await page.getByRole('button', { name: 'Guardar' }).click();

    await page.waitForURL(/\/whatsmkt\/configuracion/);
    await expect(select(page)).toHaveValue('1');
    await expect(anuncio(page)).toHaveText('Se eligió «Contactos WhatsMKT», versión 2. Falta guardarla como definición por defecto.');
    await expect(page).toHaveURL(/\/whatsmkt\/configuracion$/);
    expect(versionesGuardadas(definiciones)).toHaveLength(1);
    // Nothing was saved as the default by the trip itself.
    expect(pedidosA(whatsmkt, 'PUT', CONFIGURACION)).toHaveLength(0);
  });

  test('sin definiciones de la plataforma: Crear, guardar una nueva en Columnas y volver con ella elegida', async ({ page }) => {
    const { whatsmkt, definiciones } = viaje();
    whatsmkt.configuracion.definicion_defecto_id = null;
    definiciones.definiciones = [];
    definiciones.plataformas = [plataformaSintetica({ clave: 'whatsmkt', etiqueta: 'WhatsMKT' })];
    await montarViaje(page, whatsmkt, definiciones);
    await page.goto(CAMPANA);
    await page.locator('[data-selector-guardada]').selectOption({ label: 'Preventiva top 1000' });
    await expect(columnas(page)).toHaveText('Crear en Columnas de carga');

    await columnas(page).click();

    await page.waitForURL(/\/columnas\?/);
    await expect(page.locator('[data-volver]')).toContainText('Estás creando una definición de');
    await page.getByLabel('Nombre', { exact: true }).fill('Para WhatsMKT');
    await page.getByRole('button', { name: 'Guardar' }).click();

    await page.waitForURL(/\/whatsmkt\/campana/);
    await expect(select(page)).toHaveValue(String(definiciones.definiciones[0].id));
    await expect(anuncio(page)).toHaveText('Se eligió «Para WhatsMKT», versión 1.');
    await expect(page).toHaveURL(/\/whatsmkt\/campana$/);
  });
});
