/**
 * «Editar en Cartera» (RF-MM-09, T-MM-C11 M-F6), end to end across the two screens: the campaign keeps its draft,
 * sends the analyst to `/cartera?seleccion=<id>&volver=/mowa-mes/campana`, and Cartera brings them back (saving, saving
 * as a new one, or without saving) to a campaign that restores what was typed and loads the selection.
 *
 * What costs when it is wrong: a `volver` that is not ours becoming a redirect, edits lost when going back, a draft that
 * outlives its use, a campaign that breaks when the draft cannot be read, and Cartera changing for anyone who did not come
 * from a campaign. Every value is synthetic.
 *
 * The two screens use two fakes (the portfolio's and the module's): each answers the paths of its own, and a request goes
 * to the one whose paths it is (`montarAmbas`).
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { apiVacia, montarApi, seleccionGuardada, version, type ApiFalsa } from './api-falsa';
import { apiMowaMes, montarApiMowaMes, type ApiFalsaMowaMes } from './api-falsa-mowa-mes';

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const CAMPANA = '/mowa-mes/campana';
const CLAVE = 'mowaMes.campana.borrador.v1';
const PROPIA = /^\/api\/(cartera|selecciones|cargas)(\/|$)/;

/** A `page` that gives its routes only to the requests that match, so two fakes that each 404 what they do not know can share one. */
function soloRutas(page: Page, coincide: (ruta: string) => boolean): Page {
  return {
    route: (_patron: unknown, manejador: Parameters<Page['route']>[1]) => page.route((url) => coincide(url.pathname), manejador),
  } as unknown as Page;
}

interface Mundo {
  general: ApiFalsa;
  mowa: ApiFalsaMowaMes;
}

function mundo(): Mundo {
  const general = apiVacia();
  general.versiones = [version({ fecha_corte: '2026-09-13', vigente: true })];
  general.selecciones = [
    seleccionGuardada({ id: 1, nombre: 'Preventiva top 1000', cantidad: 1000 }),
    seleccionGuardada({ id: 2, nombre: 'Otra selección', cantidad: 300 }),
  ];
  return { general, mowa: apiMowaMes() };
}

async function montarAmbas(page: Page, { general, mowa }: Mundo): Promise<void> {
  await montarApi(soloRutas(page, (ruta) => PROPIA.test(ruta)), general);
  await montarApiMowaMes(soloRutas(page, (ruta) => !PROPIA.test(ruta)), mowa);
}

const seleccion = (page: Page) => page.getByLabel('Selección guardada');
const descripcion = (page: Page) => page.locator('#mm-descripcion');
const editarEnCartera = (page: Page) => page.getByRole('button', { name: 'Editar en Cartera' });
const enlaceVolver = (page: Page) => page.getByRole('link', { name: 'Volver a la campaña sin guardar' });
const avisoVolver = (page: Page) => page.locator('[data-volver]');
const avisoNoExiste = (page: Page) => page.locator('[data-seleccion-no-existe]');
const avisoBorrada = (page: Page) => page.locator('[data-seleccion-borrada]');
const dialogoCambios = (page: Page) => page.getByRole('dialog', { name: 'Hay cambios sin guardar' });
const cantidad = (page: Page) => page.getByLabel('Cantidad (primeros n)');

/** The campaign with the first saved selection chosen and a few fields filled in, to have something to lose. */
async function campanaConBorrador(page: Page): Promise<void> {
  await page.goto(CAMPANA);
  await expect(page.getByRole('heading', { name: 'Campaña de MOWA MES', level: 1 })).toBeVisible();
  await seleccion(page).selectOption({ label: 'Preventiva top 1000' });
  await expect(descripcion(page)).toBeVisible();
  await descripcion(page).fill('Mi campaña de prueba');
  // The checkbox is the style's own: the analyst clicks its label.
  await page.locator('label.choice', { has: page.locator('[data-herramienta-keyword]') }).click();
  await page.getByLabel('WhatsApp de la campaña').fill('900000999');
}

async function restaurada(page: Page): Promise<void> {
  await expect(page).toHaveURL(new RegExp(`${CAMPANA}$`));
  await expect(descripcion(page)).toHaveValue('Mi campaña de prueba');
  await expect(page.locator('[data-herramienta-keyword]')).toBeChecked();
  await expect(page.getByLabel('WhatsApp de la campaña')).toHaveValue('900000999');
}

/** From the campaign to Cartera with the selection loaded. */
async function irACartera(page: Page): Promise<void> {
  await editarEnCartera(page).click();
  await expect(page).toHaveURL(/\/cartera\?/);
  await expect(page.locator('[data-disponibles]')).toHaveText('3,200');
}

test.describe('el botón «Editar en Cartera»', () => {
  test('sin selección guardada queda inactivo y dice qué hacer en su title', async ({ page }) => {
    await montarAmbas(page, mundo());
    await page.goto(CAMPANA);

    await expect(editarEnCartera(page)).toBeVisible();
    await expect(editarEnCartera(page)).toBeDisabled();
    await expect(editarEnCartera(page)).toHaveAttribute('title', 'Elige una selección guardada para editarla.');
    await expect(editarEnCartera(page).locator('svg')).toHaveCount(1);
  });

  test('con una selección guardada se activa, y es un botón pequeño junto a la lista', async ({ page }) => {
    await montarAmbas(page, mundo());
    await page.goto(CAMPANA);

    await seleccion(page).selectOption({ label: 'Preventiva top 1000' });

    await expect(editarEnCartera(page)).toBeEnabled();
    await expect(editarEnCartera(page)).not.toHaveAttribute('title', /.+/);
    await expect(editarEnCartera(page)).toHaveClass(/btn--sm/);
    // It sits in the saved-selection field, not apart from it.
    await expect(page.locator('.field', { has: seleccion(page) }).getByRole('button', { name: 'Editar en Cartera' })).toBeVisible();
  });

  test('al pulsarlo va a Cartera con la selección y adónde volver, y deja el borrador versionado', async ({ page }) => {
    await montarAmbas(page, mundo());
    await campanaConBorrador(page);

    await editarEnCartera(page).click();

    await expect(page).toHaveURL('/cartera?seleccion=1&volver=%2Fmowa-mes%2Fcampana');
    await expect(avisoVolver(page)).toBeVisible();
    await expect(seleccion(page)).toHaveValue('1');
    const guardado = JSON.parse((await page.evaluate((clave) => sessionStorage.getItem(clave), CLAVE)) ?? 'null');
    expect(guardado).toMatchObject({ version: 1, seleccionId: 1, descripcion: 'Mi campaña de prueba', keyword: true, whatsapp: '900000999' });
  });
});

test.describe('cartera, llegando desde una campaña', () => {
  test('con volver válido muestra el aviso y el enlace, con su icono', async ({ page }) => {
    await montarAmbas(page, mundo());
    await page.goto('/cartera?seleccion=1&volver=%2Fmowa-mes%2Fcampana');

    await expect(avisoVolver(page)).toBeVisible();
    await expect(avisoVolver(page)).toHaveClass(/notice--info/);
    await expect(avisoVolver(page)).toContainText('Estás editando la selección de una campaña de MOWA MES. Al guardarla, vuelves a la campaña.');
    await expect(enlaceVolver(page)).toBeVisible();
    await expect(enlaceVolver(page).locator('svg')).toHaveCount(1);
    await expect(seleccion(page)).toHaveValue('1');
  });

  test('sin parámetros, Cartera es la de siempre: ni aviso ni selección cargada', async ({ page }) => {
    await montarAmbas(page, mundo());
    await page.goto('/cartera');

    await expect(page.locator('[data-disponibles]')).toHaveText('3,200');
    await expect(avisoVolver(page)).toBeHidden();
    await expect(avisoNoExiste(page)).toBeHidden();
    await expect(seleccion(page)).toHaveValue('');
  });

  test('guardar sin volver (no vino de una campaña) no navega a ninguna parte', async ({ page }) => {
    await montarAmbas(page, mundo());
    await page.goto('/cartera?seleccion=1');
    await expect(seleccion(page)).toHaveValue('1');

    await cantidad(page).fill('250');
    await page.getByRole('button', { name: 'Guardar cambios' }).click();
    await expect(page.getByText('«Preventiva top 1000», sin cambios.')).toBeVisible();

    await expect(page).toHaveURL(/\/cartera\?seleccion=1$/);
  });

  test('una selección que no existe deja Cartera vacía con un aviso, sin error', async ({ page }) => {
    await montarAmbas(page, mundo());
    await page.goto('/cartera?seleccion=999&volver=%2Fmowa-mes%2Fcampana');

    await expect(avisoNoExiste(page)).toBeVisible();
    await expect(avisoNoExiste(page)).toHaveClass(/notice--warning/);
    await expect(avisoNoExiste(page)).toHaveAttribute('role', 'status');
    await expect(avisoNoExiste(page)).toContainText('La selección que abriste ya no existe. Arma una nueva o elige otra de la lista.');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.locator('[data-offline]')).toBeHidden();
    // Empty, and usable: the list still loads one.
    await expect(seleccion(page)).toHaveValue('');
    await expect(page.locator('[data-disponibles]')).toHaveText('3,200');
    await seleccion(page).selectOption({ label: 'Otra selección' });
    await expect(seleccion(page)).toHaveValue('2');
  });

  test('un seleccion que no es un número tampoco rompe nada', async ({ page }) => {
    await montarAmbas(page, mundo());
    await page.goto('/cartera?seleccion=abc');

    await expect(avisoNoExiste(page)).toBeVisible();
    await expect(page.locator('[data-disponibles]')).toHaveText('3,200');
  });

  for (const invalido of ['//evil.com', 'https://evil.com/mowa-mes/', '/mowa-mes/../cartera', 'javascript:alert(1)', '/cartera', '/\\evil.com']) {
    test(`un volver inválido (${invalido}) se ignora: sin aviso y sin navegar al guardar`, async ({ page }) => {
      await montarAmbas(page, mundo());
      await page.goto(`/cartera?seleccion=1&volver=${encodeURIComponent(invalido)}`);

      await expect(page.locator('[data-disponibles]')).toHaveText('3,200');
      await expect(seleccion(page)).toHaveValue('1');
      await expect(avisoVolver(page)).toBeHidden();
      await expect(enlaceVolver(page)).toBeHidden();

      await cantidad(page).fill('250');
      await page.getByRole('button', { name: 'Guardar cambios' }).click();
      await expect(page.getByText('«Preventiva top 1000», sin cambios.')).toBeVisible();
      await expect(page).toHaveURL(/\/cartera\?/);
    });
  }
});

test.describe('ida y vuelta guardando', () => {
  test('«Guardar cambios» vuelve a la campaña, que restaura el borrador, lo borra y carga la selección', async ({ page }) => {
    const m = mundo();
    await montarAmbas(page, m);
    await campanaConBorrador(page);
    await irACartera(page);

    await cantidad(page).fill('250');
    await page.getByRole('button', { name: 'Guardar cambios' }).click();

    await restaurada(page);
    await expect(seleccion(page)).toHaveValue('1');
    await expect(editarEnCartera(page)).toBeEnabled();
    // Used once: the draft is gone, and so is the parameter of the URL.
    expect(await page.evaluate((clave) => sessionStorage.getItem(clave), CLAVE)).toBeNull();
    expect(new URL(page.url()).search).toBe('');
    expect(m.general.pedidos.filter((p) => p.metodo === 'PUT' && p.url.endsWith('/api/selecciones/1'))).toHaveLength(1);
  });

  test('«Guardar como nueva» vuelve a la campaña con la selección nueva elegida', async ({ page }) => {
    const m = mundo();
    await montarAmbas(page, m);
    await campanaConBorrador(page);
    await irACartera(page);

    await cantidad(page).fill('250');
    await page.getByRole('button', { name: 'Guardar como nueva' }).click();
    const dialogo = page.getByRole('dialog', { name: 'Guardar la selección' });
    await dialogo.getByLabel('Nombre').fill('Top nueva desde la campaña');
    await dialogo.getByRole('button', { name: 'Guardar', exact: true }).click();

    await restaurada(page);
    await expect(seleccion(page).locator('option:checked')).toHaveText('Top nueva desde la campaña');
    await expect(seleccion(page)).toHaveValue('99');
    expect(await page.evaluate((clave) => sessionStorage.getItem(clave), CLAVE)).toBeNull();
  });
});

test.describe('volver sin guardar', () => {
  test('sin cambios vuelve de una vez, con el borrador y la selección que tenía', async ({ page }) => {
    await montarAmbas(page, mundo());
    await campanaConBorrador(page);
    await irACartera(page);

    await enlaceVolver(page).click();

    await expect(page.getByRole('dialog')).toHaveCount(0);
    await restaurada(page);
    await expect(seleccion(page)).toHaveValue('1');
    expect(await page.evaluate((clave) => sessionStorage.getItem(clave), CLAVE)).toBeNull();
  });

  test('con cambios pregunta con el diálogo de siempre y su texto: «Seguir editando» no navega', async ({ page }) => {
    await montarAmbas(page, mundo());
    await campanaConBorrador(page);
    await irACartera(page);
    await cantidad(page).fill('250');

    await enlaceVolver(page).click();

    const dialogo = dialogoCambios(page);
    await expect(dialogo).toBeVisible();
    await expect(dialogo.getByText('Los cambios que no guardaste se pierden.')).toBeVisible();
    await expect(dialogo.getByRole('button', { name: 'Seguir editando' })).toBeFocused();
    await dialogo.getByRole('button', { name: 'Seguir editando' }).click();

    await expect(dialogo).toBeHidden();
    await expect(page).toHaveURL(/\/cartera\?/);
    await expect(cantidad(page)).toHaveValue('250');
    // Nothing waits behind: the same link asks again, and now it is answered.
    await enlaceVolver(page).click();
    await expect(dialogo).toBeVisible();
    await dialogo.getByRole('button', { name: 'Descartar cambios' }).click();
    await restaurada(page);
    await expect(seleccion(page)).toHaveValue('1');
  });

  test('Escape también es seguir editando', async ({ page }) => {
    await montarAmbas(page, mundo());
    await campanaConBorrador(page);
    await irACartera(page);
    await cantidad(page).fill('250');

    await enlaceVolver(page).click();
    await expect(dialogoCambios(page)).toBeVisible();
    await page.keyboard.press('Escape');

    await expect(dialogoCambios(page)).toBeHidden();
    await expect(page).toHaveURL(/\/cartera\?/);
    await expect(cantidad(page)).toHaveValue('250');
  });

  test('un doble clic con cambios no deja nada colgado: un solo diálogo, y después responde', async ({ page }) => {
    await montarAmbas(page, mundo());
    await campanaConBorrador(page);
    await irACartera(page);
    await cantidad(page).fill('250');

    await enlaceVolver(page).dblclick();

    await expect(dialogoCambios(page)).toHaveCount(1);
    await expect(dialogoCambios(page)).toBeVisible();
    await dialogoCambios(page).getByRole('button', { name: 'Seguir editando' }).click();
    await expect(page).toHaveURL(/\/cartera\?/);

    await enlaceVolver(page).click();
    await expect(dialogoCambios(page)).toBeVisible();
    await dialogoCambios(page).getByRole('button', { name: 'Descartar cambios' }).click();
    await restaurada(page);
  });

  test('un doble clic y descartar navega una sola vez, a la campaña', async ({ page }) => {
    await montarAmbas(page, mundo());
    await campanaConBorrador(page);
    await irACartera(page);
    await cantidad(page).fill('250');

    await enlaceVolver(page).dblclick();
    await dialogoCambios(page).getByRole('button', { name: 'Descartar cambios' }).click();

    await restaurada(page);
  });

  test('con la selección borrada en Cartera, la campaña no elige ninguna y lo dice', async ({ page }) => {
    const m = mundo();
    await montarAmbas(page, m);
    await campanaConBorrador(page);
    await irACartera(page);
    // Deleted from Cartera (or by someone else) while editing.
    m.general.selecciones = m.general.selecciones.filter((s) => s.id !== 1);

    await enlaceVolver(page).click();

    await restaurada(page);
    await expect(avisoBorrada(page)).toBeVisible();
    await expect(avisoBorrada(page)).toHaveClass(/notice--warning/);
    await expect(avisoBorrada(page)).toContainText('La selección que editaste en Cartera ya no existe. Elige otra selección guardada.');
    await expect(seleccion(page)).toHaveValue('');
    await expect(editarEnCartera(page)).toBeDisabled();
    // Choosing another takes the notice away.
    await seleccion(page).selectOption({ label: 'Otra selección' });
    await expect(avisoBorrada(page)).toBeHidden();
  });
});

test.describe('el selector, con la lista y los diálogos de siempre', () => {
  test('cambiar de selección con cambios, y cancelar, no navega ni deja una espera abierta', async ({ page }) => {
    await montarAmbas(page, mundo());
    await page.goto('/cartera?seleccion=1&volver=%2Fmowa-mes%2Fcampana');
    await expect(seleccion(page)).toHaveValue('1');
    await cantidad(page).fill('250');

    await seleccion(page).selectOption({ label: 'Otra selección' });
    const dialogo = dialogoCambios(page);
    await expect(dialogo).toBeVisible();
    await expect(dialogo.getByText('Los cambios que no guardaste se pierden.')).toBeVisible();
    await dialogo.getByRole('button', { name: 'Seguir editando' }).click();

    await expect(dialogo).toBeHidden();
    await expect(page).toHaveURL(/\/cartera\?seleccion=1/);
    await expect(seleccion(page)).toHaveValue('1');
    await expect(cantidad(page)).toHaveValue('250');
    // Closing it did not answer a «may I go back?» nobody asked: still here after a moment.
    await page.waitForTimeout(300);
    await expect(page).toHaveURL(/\/cartera\?seleccion=1/);
  });

  test('cambiar de selección y descartar carga la otra, sin salir de Cartera', async ({ page }) => {
    await montarAmbas(page, mundo());
    await page.goto('/cartera?seleccion=1&volver=%2Fmowa-mes%2Fcampana');
    await expect(seleccion(page)).toHaveValue('1');
    await cantidad(page).fill('250');

    await seleccion(page).selectOption({ label: 'Otra selección' });
    await dialogoCambios(page).getByRole('button', { name: 'Descartar cambios' }).click();

    await expect(seleccion(page)).toHaveValue('2');
    await expect(page).toHaveURL(/\/cartera\?/);
  });
});

test.describe('si el borrador no se puede leer', () => {
  test('un JSON roto: la campaña empieza vacía y sin errores', async ({ page }) => {
    await montarAmbas(page, mundo());
    await page.addInitScript((clave) => sessionStorage.setItem(clave, '{'), CLAVE);
    await page.goto(CAMPANA);

    await expect(page.getByRole('heading', { name: 'Campaña de MOWA MES', level: 1 })).toBeVisible();
    await expect(seleccion(page)).toHaveValue('');
    await expect(avisoBorrada(page)).toBeHidden();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(editarEnCartera(page)).toBeDisabled();
    // It was in the way, and it is gone.
    expect(await page.evaluate((clave) => sessionStorage.getItem(clave), CLAVE)).toBeNull();
  });

  test('un borrador de otra versión no se usa', async ({ page }) => {
    await montarAmbas(page, mundo());
    await page.addInitScript(() =>
      sessionStorage.setItem('mowaMes.campana.borrador.v2', JSON.stringify({ version: 2, descripcion: 'No me uses' })),
    );
    await page.goto(CAMPANA);

    await expect(seleccion(page)).toHaveValue('');
    await expect(page.getByRole('dialog')).toHaveCount(0);
  });

  test('un sessionStorage que tira error: la campaña carga y el botón igual lleva a Cartera', async ({ page }) => {
    await montarAmbas(page, mundo());
    // Only sessionStorage refuses: the rest of the page (the language, in localStorage) reads as always.
    await page.addInitScript(() => {
      for (const metodo of ['getItem', 'setItem', 'removeItem'] as const) {
        const original = Storage.prototype[metodo] as (...args: string[]) => unknown;
        Storage.prototype[metodo] = function (this: Storage, ...args: string[]) {
          if (this === window.sessionStorage) throw new DOMException('refused', 'SecurityError');
          return original.apply(this, args);
        } as never;
      }
    });
    await page.goto(CAMPANA);
    await expect(page.getByRole('heading', { name: 'Campaña de MOWA MES', level: 1 })).toBeVisible();
    await seleccion(page).selectOption({ label: 'Preventiva top 1000' });

    await editarEnCartera(page).click();

    await expect(page).toHaveURL(/\/cartera\?seleccion=1/);
  });
});

test.describe('idioma y anchos', () => {
  test('en inglés traduce el botón, su title, el aviso, el enlace y el diálogo', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    await montarAmbas(page, mundo());
    await page.goto(CAMPANA);
    const boton = page.getByRole('button', { name: 'Edit in Portfolio' });
    await expect(boton).toBeDisabled();
    await expect(boton).toHaveAttribute('title', 'Choose a saved selection to edit it.');
    await page.getByLabel('Saved selection').selectOption({ label: 'Preventiva top 1000' });
    await boton.click();

    await expect(page.locator('[data-volver]')).toContainText('You are editing the selection of a MOWA MES campaign. When you save it, you go back to the campaign.');
    await expect(page.locator('[data-disponibles]')).toHaveText('3,200');
    await page.getByLabel('Count (first n)').fill('250');
    await page.getByRole('link', { name: 'Back to the campaign without saving' }).click();
    const dialogo = page.getByRole('dialog', { name: 'There are unsaved changes' });
    await expect(dialogo.getByText('The changes you did not save will be lost.')).toBeVisible();
    await expect(dialogo.getByRole('button', { name: 'Discard changes' })).toBeVisible();
  });

  test('a 360 px el aviso no desborda y el enlace queda a la vista', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await montarAmbas(page, mundo());
    await page.goto('/cartera?seleccion=1&volver=%2Fmowa-mes%2Fcampana');
    await expect(avisoVolver(page)).toBeVisible();

    const caja = (await enlaceVolver(page).boundingBox())!;
    expect(caja.x).toBeGreaterThanOrEqual(0);
    expect(caja.x + caja.width).toBeLessThanOrEqual(361);
    const desborde = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(desborde).toBeLessThanOrEqual(0);
  });

  test('a 360 px el botón «Editar en Cartera» queda a la vista en la campaña', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await montarAmbas(page, mundo());
    await page.goto(CAMPANA);

    await editarEnCartera(page).scrollIntoViewIfNeeded();
    const caja = (await editarEnCartera(page).boundingBox())!;
    expect(caja.x).toBeGreaterThanOrEqual(0);
    expect(caja.x + caja.width).toBeLessThanOrEqual(361);
    const desborde = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(desborde).toBeLessThanOrEqual(0);
  });

  for (const tema of ['light', 'dark'] as const) {
    for (const ancho of [1280, 360]) {
      test(`sin violaciones WCAG a ${ancho} px, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, async ({ page }) => {
        await page.addInitScript((elegido) => {
          localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
        }, tema);
        await page.setViewportSize({ width: ancho, height: 900 });
        await montarAmbas(page, mundo());

        // The campaign with its button enabled.
        await page.goto(CAMPANA);
        await seleccion(page).selectOption({ label: 'Preventiva top 1000' });
        await expect(editarEnCartera(page)).toBeEnabled();
        const campana = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
        expect(campana.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);

        // Cartera with the notice and, then, the dialog open.
        await page.goto('/cartera?seleccion=1&volver=%2Fmowa-mes%2Fcampana');
        await expect(avisoVolver(page)).toBeVisible();
        await expect(page.locator('[data-disponibles]')).toHaveText('3,200');
        const cartera = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
        expect(cartera.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);

        await cantidad(page).fill('250');
        await enlaceVolver(page).click();
        await expect(dialogoCambios(page)).toBeVisible();
        const confirmando = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
        expect(confirmando.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
      });
    }
  }
});
