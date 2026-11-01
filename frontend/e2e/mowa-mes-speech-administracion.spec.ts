/**
 * Administering speech versions (RF-MM-28 to RF-MM-30, T-MM-C11 M-F2): rename any version, disable and enable
 * it, the folded panel of the disabled ones with Ver, Habilitar and Eliminar definitivamente (or, in its place,
 * why it cannot be), and the campaign that offers only enabled versions. What can be deleted is what the API
 * says (`eliminable`, `motivo_no_eliminable`): the screen never works it out. Every value is synthetic.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { seleccionGuardada } from './api-falsa';
import {
  DESHABILITADA_EN,
  apiMowaMes,
  conEliminable,
  montarApiMowaMes,
  speechOriginal,
  versionAdministrable,
  type ApiFalsaMowaMes,
} from './api-falsa-mowa-mes';
import { montarConfiguracion, versionV2Sintetica } from './api-falsa-speech-v2';
import { montarSeleccion, seleccionFalsa } from './apoyo-seleccion';

// No animations: axe reads the contrast of what is painted, and a dialog still fading in is not what the analyst sees.
test.use({ reducedMotion: 'reduce' });

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const RUTA = '/mowa-mes/configuracion';

/**
 * 1 is the Speech original and 2 «Activa» (both enabled); 3 is disabled and used by a campaign (it can never be
 * deleted), 4 and 5 are disabled and unused (they can).
 */
function conVersiones(): ApiFalsaMowaMes {
  const api = apiMowaMes();
  api.versiones = [
    speechOriginal(),
    versionAdministrable({ id: 2, nombre: 'Activa' }),
    versionAdministrable({ id: 3, nombre: 'Usada deshabilitada', usada: true, deshabilitada_en: DESHABILITADA_EN }),
    versionAdministrable({ id: 4, nombre: 'Borrable uno', deshabilitada_en: DESHABILITADA_EN }),
    versionAdministrable({ id: 5, nombre: 'Borrable dos', deshabilitada_en: DESHABILITADA_EN }),
  ];
  return api;
}

async function abrir(page: Page, api: ApiFalsaMowaMes): Promise<void> {
  // Every version is a v2: the screen always mounts the editor, so it gets the whole API.
  await montarConfiguracion(page, api);
  await page.goto(RUTA);
  await expect(page.getByRole('heading', { name: 'Configuración de MOWA MES' })).toBeVisible();
  await expect(page.locator('#mm-version option').first()).toBeAttached();
}

const version = (page: Page) => page.locator('#mm-version');
const estado = (page: Page) => page.locator('[data-speech-estado]');
const panel = (page: Page) => page.locator('[data-deshabilitadas]');
const resumen = (page: Page) => panel(page).locator('summary');
const fila = (page: Page, id: number) => page.locator(`[data-deshab-lista] [data-version="${id}"]`);
const candado = (page: Page) => page.locator('[data-speech-inmutable]');
const renombrar = (page: Page) => page.getByRole('button', { name: 'Renombrar' }).first();
const deshabilitar = (page: Page) => page.getByRole('button', { name: 'Deshabilitar' });
const pedidos = (api: ApiFalsaMowaMes, metodo: string, ruta: string) =>
  api.pedidos.filter((p) => p.metodo === metodo && p.ruta === ruta);

/** Open the folded panel to reach its rows. */
async function abrirPanel(page: Page): Promise<void> {
  await resumen(page).click();
  await expect(fila(page, 4)).toBeVisible();
}

test.describe('las versiones habilitadas', () => {
  test('el selector lista solo las habilitadas', async ({ page }) => {
    await abrir(page, conVersiones());

    await expect(version(page).locator('option')).toHaveText(['Speech original (original)', 'Activa']);
  });

  test('una habilitada, hasta el Speech original, lleva «Renombrar» y «Deshabilitar»', async ({ page }) => {
    await abrir(page, conVersiones());

    await expect(renombrar(page)).toBeVisible();
    await expect(deshabilitar(page)).toBeVisible();
    await version(page).selectOption('2');
    await expect(renombrar(page)).toBeVisible();
    await expect(deshabilitar(page)).toBeVisible();
  });
});

test.describe('renombrar', () => {
  test('abre el diálogo con el nombre actual seleccionado, y «Renombrar» inactivo mientras no cambie', async ({ page }) => {
    await abrir(page, conVersiones());
    await version(page).selectOption('2');

    await renombrar(page).click();

    const dialogo = page.getByRole('dialog', { name: 'Renombrar la versión «Activa»' });
    await expect(dialogo).toBeVisible();
    const campo = dialogo.getByLabel('Nombre nuevo');
    await expect(campo).toHaveValue('Activa');
    await expect(campo).toBeFocused();
    await expect(dialogo.getByText('Las campañas siguen apuntando a esta versión: registran la versión, no su nombre.')).toBeVisible();
    const confirmar = dialogo.getByRole('button', { name: 'Renombrar' });
    // The same name, and the same with spaces at the edges, is nothing to do.
    await expect(confirmar).toBeDisabled();
    await campo.fill('  Activa  ');
    await expect(confirmar).toBeDisabled();
    await campo.fill('Activa B');
    await expect(confirmar).toBeEnabled();
    await campo.fill('Activa');
    await expect(confirmar).toBeDisabled();
  });

  test('renombra: el diálogo se cierra, el selector y la región de estado lo dicen y el foco vuelve a «Renombrar»', async ({ page }) => {
    const api = conVersiones();
    await abrir(page, api);
    await version(page).selectOption('2');

    await renombrar(page).click();
    const dialogo = page.getByRole('dialog', { name: 'Renombrar la versión «Activa»' });
    await dialogo.getByLabel('Nombre nuevo').fill('Activa B');
    await dialogo.getByRole('button', { name: 'Renombrar' }).click();

    await expect(dialogo).toBeHidden();
    await expect(version(page).locator('option')).toHaveText(['Speech original (original)', 'Activa B']);
    await expect(estado(page)).toHaveText('Renombrada a «Activa B».');
    await expect(renombrar(page)).toBeFocused();
    const envios = pedidos(api, 'PATCH', '/mowa-mes/speech/2');
    expect(envios).toHaveLength(1);
    expect(envios[0].cuerpo).toEqual({ nombre: 'Activa B' });
  });

  test('se puede renombrar el Speech original', async ({ page }) => {
    const api = conVersiones();
    await abrir(page, api);

    await renombrar(page).click();
    const dialogo = page.getByRole('dialog', { name: 'Renombrar la versión «Speech original»' });
    await dialogo.getByLabel('Nombre nuevo').fill('Original de 2026');
    await dialogo.getByRole('button', { name: 'Renombrar' }).click();

    await expect(estado(page)).toHaveText('Renombrada a «Original de 2026».');
    expect(pedidos(api, 'PATCH', '/mowa-mes/speech/1')).toHaveLength(1);
  });

  test('un nombre repetido (409) va bajo el campo, con el diálogo abierto y lo escrito intacto', async ({ page }) => {
    await abrir(page, conVersiones());

    await renombrar(page).click();
    const dialogo = page.getByRole('dialog', { name: 'Renombrar la versión «Speech original»' });
    const campo = dialogo.getByLabel('Nombre nuevo');
    // The check ignores case and the spaces at the edges, as the backend does.
    await campo.fill(' activa ');
    await dialogo.getByRole('button', { name: 'Renombrar' }).click();

    await expect(dialogo.getByRole('alert')).toHaveText('Ya existe una versión con ese nombre. Elige otro.');
    await expect(dialogo).toBeVisible();
    await expect(campo).toHaveValue(' activa ');
    await expect(campo).toHaveAttribute('aria-invalid', 'true');
    await expect(campo).toBeFocused();
    // Writing again takes the error away.
    await campo.fill('Otro nombre');
    // An empty alert is not in the accessibility tree: the node itself is what has to be empty.
    await expect(dialogo.locator('#mm-renombrar-error')).toBeEmpty();
  });

  test('Escape o «Cancelar» no renombran', async ({ page }) => {
    const api = conVersiones();
    await abrir(page, api);

    await renombrar(page).click();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(renombrar(page)).toBeFocused();
    expect(pedidos(api, 'PATCH', '/mowa-mes/speech/1')).toHaveLength(0);
  });
});

test.describe('deshabilitar', () => {
  test('la versión sigue a la vista, en solo lectura y con el candado; sale del selector al cambiar de versión', async ({ page }) => {
    const api = conVersiones();
    await abrir(page, api);
    await version(page).selectOption('2');

    await deshabilitar(page).click();

    await expect(estado(page)).toHaveText('Se deshabilitó «Activa». Ya no aparece en la campaña.');
    expect(pedidos(api, 'PATCH', '/mowa-mes/speech/2')[0].cuerpo).toEqual({ habilitada: false });
    await expect(candado(page)).toBeVisible();
    await expect(candado(page)).toContainText(
      'Esta versión está deshabilitada: no aparece en la campaña y se ve en solo lectura. Para usarla o editarla, habilítala.',
    );
    await expect(candado(page).locator('svg')).toHaveCount(1);
    // No actions, no footer: it is read.
    await expect(renombrar(page)).toBeHidden();
    await expect(deshabilitar(page)).toBeHidden();
    await expect(page.locator('[data-speech-pie]')).toBeHidden();
    await expect(version(page)).toBeFocused();
    // The selector still says what is on screen, with its mark; leaving it, it goes.
    await expect(version(page).locator('option')).toHaveText(['Speech original (original)', 'Activa (deshabilitada)']);
    await version(page).selectOption('1');
    await expect(version(page).locator('option')).toHaveText(['Speech original (original)']);
  });

  test('entra en «Versiones deshabilitadas (N)», que sigue cerrado', async ({ page }) => {
    await abrir(page, conVersiones());
    await expect(resumen(page)).toHaveText('Versiones deshabilitadas (3)');
    await version(page).selectOption('2');

    await deshabilitar(page).click();

    await expect(resumen(page)).toHaveText('Versiones deshabilitadas (4)');
    await expect(panel(page).locator('details')).not.toHaveAttribute('open', '');
    await expect(fila(page, 2)).toBeHidden();
  });

  test('con cambios sin guardar no deshabilita: lo dice y no manda nada', async ({ page }) => {
    const api = conVersiones();
    await abrir(page, api);
    // Typing in a segment of the original: a change nobody has saved.
    await page.locator('#mm-speech-v2 [data-segmento-botones] button').nth(2).click();
    await page.locator('#mm-speech-v2').getByRole('textbox').last().fill(', pague ya y evite el cobro.');

    await deshabilitar(page).click();

    await expect(page.locator('[data-speech-error]')).toHaveText(
      'Tienes cambios sin guardar en esta versión. Guárdalos o descártalos antes de cambiar de versión.',
    );
    expect(pedidos(api, 'PATCH', '/mowa-mes/speech/1')).toHaveLength(0);
  });
});

test.describe('versiones deshabilitadas', () => {
  test('en el resumen, el título va junto a la flecha, a la izquierda', async ({ page }) => {
    await abrir(page, conVersiones());

    const resumenCaja = (await resumen(page).boundingBox())!;
    const flecha = (await resumen(page).locator('svg').boundingBox())!;
    const titulo = (await resumen(page).locator('h2').boundingBox())!;
    // The arrow first, the title right after it, both at the left edge of the summary (not the title pushed to the right).
    expect(flecha.x + flecha.width).toBeLessThanOrEqual(titulo.x + 1);
    expect(titulo.x - (flecha.x + flecha.width)).toBeLessThan(24);
    expect(titulo.x - resumenCaja.x).toBeLessThan(resumenCaja.width / 3);
  });

  test('el panel abre cerrado y no se muestra con cero', async ({ page }) => {
    await abrir(page, conVersiones());

    await expect(panel(page)).toBeVisible();
    await expect(resumen(page)).toHaveText('Versiones deshabilitadas (3)');
    await expect(panel(page).locator('details')).not.toHaveAttribute('open', '');
    await expect(fila(page, 4)).toBeHidden();

    const sin = apiMowaMes();
    const otra = await page.context().newPage();
    await montarConfiguracion(otra, sin);
    await otra.goto(RUTA);
    await expect(otra.getByRole('heading', { name: 'Configuración de MOWA MES' })).toBeVisible();
    await expect(otra.locator('[data-deshabilitadas]')).toBeHidden();
    await otra.close();
  });

  test('cada fila: nombre, tag «Deshabilitada» con su icono y «Original» si lo es', async ({ page }) => {
    const api = conVersiones();
    api.versiones.push(
      versionAdministrable({ id: 6, nombre: 'Original archivado', original: true, deshabilitada_en: DESHABILITADA_EN }),
    );
    await abrir(page, api);
    await abrirPanel(page);

    await expect(fila(page, 4).locator('.tag')).toHaveText(['Deshabilitada']);
    await expect(fila(page, 4).locator('.tag svg')).toHaveCount(1);
    await expect(fila(page, 6).locator('.tag')).toHaveText(['Deshabilitada', 'Original']);
    await expect(fila(page, 6).locator('.tag svg')).toHaveCount(2);
    expect(await fila(page, 4).evaluate((el) => getComputedStyle(el).opacity)).toBe('1');
  });

  test('«Eliminar definitivamente» solo si eliminable; si no, el motivo en su lugar', async ({ page }) => {
    const api = conVersiones();
    api.versiones.push(
      versionAdministrable({ id: 6, nombre: 'Original archivado', original: true, deshabilitada_en: DESHABILITADA_EN }),
    );
    await abrir(page, api);
    await abrirPanel(page);

    await expect(fila(page, 4).getByRole('button', { name: 'Eliminar definitivamente' })).toBeVisible();
    await expect(fila(page, 4).getByRole('button', { name: 'Eliminar definitivamente' })).toHaveClass(/btn--danger/);
    // Used by a campaign: the reason, no button.
    await expect(fila(page, 3).getByRole('button', { name: 'Eliminar definitivamente' })).toHaveCount(0);
    await expect(fila(page, 3).locator('.field__hint')).toHaveText('No se puede eliminar: la usaron campañas.');
    // The Speech original: its own reason.
    await expect(fila(page, 6).getByRole('button', { name: 'Eliminar definitivamente' })).toHaveCount(0);
    await expect(fila(page, 6).locator('.field__hint')).toHaveText('No se puede eliminar: es el Speech original.');
  });

  test('el nombre accesible de cada botón de fila lleva el nombre de la versión, empezando por su texto', async ({ page }) => {
    await abrir(page, conVersiones());
    await abrirPanel(page);

    await expect(fila(page, 4).getByRole('button', { name: 'Ver' })).toHaveAccessibleName('Ver Borrable uno');
    await expect(fila(page, 4).getByRole('button', { name: 'Habilitar' })).toHaveAccessibleName('Habilitar Borrable uno');
    await expect(fila(page, 4).getByRole('button', { name: 'Eliminar definitivamente' })).toHaveAccessibleName(
      'Eliminar definitivamente Borrable uno',
    );
    // The same words in another row say another name: a list of buttons tells them apart.
    await expect(fila(page, 5).getByRole('button', { name: 'Ver' })).toHaveAccessibleName('Ver Borrable dos');
    await expect(fila(page, 3).getByRole('button', { name: 'Ver' })).toHaveAccessibleName('Ver Usada deshabilitada');
  });

  test('«Ver» abre la versión en el editor, en solo lectura y con el candado', async ({ page }) => {
    await abrir(page, conVersiones());
    await abrirPanel(page);

    await fila(page, 4).getByRole('button', { name: 'Ver' }).click();

    await expect(version(page)).toHaveValue('4');
    await expect(version(page).locator('option')).toHaveText(['Speech original (original)', 'Activa', 'Borrable uno (deshabilitada)']);
    await expect(candado(page)).toContainText('Esta versión está deshabilitada');
    await expect(page.locator('[data-speech-pie]')).toBeHidden();
    await expect(renombrar(page)).toBeHidden();
  });

  test('una v2 deshabilitada se abre en el modo de solo lectura del editor; al habilitarla, vuelve a poder editarse', async ({ page }) => {
    const api = conVersiones();
    api.versiones = [
      speechOriginal(),
      conEliminable(versionV2Sintetica(speechOriginal(), { id: 20, nombre: 'Speech v2 archivado', deshabilitada_en: DESHABILITADA_EN })),
    ];
    await abrir(page, api);

    await resumen(page).click();
    await fila(page, 20).getByRole('button', { name: 'Ver' }).click();

    const editor = page.locator('#mm-speech-v2');
    await expect(editor).toBeVisible();
    await expect(editor.locator('.editor-texto--soloLectura')).toHaveCount(1);
    await expect(candado(page)).toBeVisible();
    await expect(page.locator('[data-speech-pie]')).toBeHidden();

    await fila(page, 20).getByRole('button', { name: 'Habilitar' }).click();

    await expect(estado(page)).toHaveText('Se habilitó «Speech v2 archivado».');
    await expect(editor.locator('.editor-texto--soloLectura')).toHaveCount(0);
    await expect(candado(page)).toBeHidden();
    await expect(page.locator('[data-speech-pie]')).toBeVisible();
  });

  test('«Habilitar» devuelve la versión al selector y a la campaña: la fila sale, el conteo baja y se anuncia', async ({ page }) => {
    const api = conVersiones();
    await abrir(page, api);
    await abrirPanel(page);

    await fila(page, 4).getByRole('button', { name: 'Habilitar' }).click();

    await expect(fila(page, 4)).toHaveCount(0);
    await expect(resumen(page)).toHaveText('Versiones deshabilitadas (2)');
    await expect(estado(page)).toHaveText('Se habilitó «Borrable uno».');
    await expect(version(page).locator('option')).toHaveText(['Speech original (original)', 'Activa', 'Borrable uno']);
    expect(pedidos(api, 'PATCH', '/mowa-mes/speech/4')[0].cuerpo).toEqual({ habilitada: true });
    // The focus passes to the row that follows.
    await expect(fila(page, 5).getByRole('button').first()).toBeFocused();
  });

  test('habilitar la última cierra el panel y deja el foco en el selector', async ({ page }) => {
    const api = conVersiones();
    api.versiones = [speechOriginal(), versionAdministrable({ id: 4, nombre: 'Única', deshabilitada_en: DESHABILITADA_EN })];
    await abrir(page, api);
    await abrirPanel(page);

    await fila(page, 4).getByRole('button', { name: 'Habilitar' }).click();

    await expect(panel(page)).toBeHidden();
    await expect(version(page)).toBeFocused();
  });
});

test.describe('eliminar definitivamente', () => {
  test('exige la casilla, con el foco en «Cancelar» y el aviso en rojo', async ({ page }) => {
    await abrir(page, conVersiones());
    await abrirPanel(page);

    await fila(page, 4).getByRole('button', { name: 'Eliminar definitivamente' }).click();

    const dialogo = page.getByRole('dialog', { name: 'Eliminar definitivamente la versión «Borrable uno»' });
    await expect(dialogo).toBeVisible();
    await expect(dialogo.locator('.notice--danger')).toContainText('Se borra la versión y su texto. No se puede deshacer.');
    await expect(dialogo.getByRole('button', { name: 'Cancelar' })).toBeFocused();
    const eliminar = dialogo.getByRole('button', { name: 'Eliminar definitivamente' });
    await expect(eliminar).toHaveClass(/btn--danger/);
    await expect(eliminar).toBeDisabled();
    await dialogo.getByLabel('Entiendo que no se puede deshacer').check();
    await expect(eliminar).toBeEnabled();
    await dialogo.getByLabel('Entiendo que no se puede deshacer').uncheck();
    await expect(eliminar).toBeDisabled();
  });

  test('con la casilla borra la versión: sale de la lista, baja el conteo, se anuncia y el foco pasa a la fila siguiente', async ({ page }) => {
    const api = conVersiones();
    await abrir(page, api);
    await abrirPanel(page);

    await fila(page, 4).getByRole('button', { name: 'Eliminar definitivamente' }).click();
    const dialogo = page.getByRole('dialog', { name: 'Eliminar definitivamente la versión «Borrable uno»' });
    await dialogo.getByLabel('Entiendo que no se puede deshacer').check();
    await dialogo.getByRole('button', { name: 'Eliminar definitivamente' }).click();

    await expect(dialogo).toBeHidden();
    await expect(fila(page, 4)).toHaveCount(0);
    await expect(resumen(page)).toHaveText('Versiones deshabilitadas (2)');
    await expect(estado(page)).toHaveText('Se eliminó «Borrable uno».');
    await expect(fila(page, 5).getByRole('button').first()).toBeFocused();
    expect(pedidos(api, 'DELETE', '/mowa-mes/speech/4')).toHaveLength(1);
    expect(api.versiones.map((v) => v.id)).not.toContain(4);
  });

  test('sin marcar la casilla no se manda ninguna petición', async ({ page }) => {
    const api = conVersiones();
    await abrir(page, api);
    await abrirPanel(page);

    await fila(page, 4).getByRole('button', { name: 'Eliminar definitivamente' }).click();
    const dialogo = page.getByRole('dialog', { name: 'Eliminar definitivamente la versión «Borrable uno»' });
    await dialogo.getByRole('button', { name: 'Eliminar definitivamente' }).click({ force: true });

    await expect(dialogo).toBeVisible();
    expect(pedidos(api, 'DELETE', '/mowa-mes/speech/4')).toHaveLength(0);
  });

  test('un 409 con código (la usó una campaña mientras tanto) se dice dentro del diálogo, que sigue abierto', async ({ page }) => {
    const api = conVersiones();
    await abrir(page, api);
    await abrirPanel(page);

    // A campaign used it after the list was read.
    api.versiones = api.versiones.map((v) => (v.id === 4 ? conEliminable({ ...v, usada: true }) : v));
    await fila(page, 4).getByRole('button', { name: 'Eliminar definitivamente' }).click();
    const dialogo = page.getByRole('dialog', { name: 'Eliminar definitivamente la versión «Borrable uno»' });
    await dialogo.getByLabel('Entiendo que no se puede deshacer').check();
    await dialogo.getByRole('button', { name: 'Eliminar definitivamente' }).click();

    await expect(dialogo.getByRole('alert')).toHaveText('No se puede eliminar: la usaron campañas.');
    await expect(dialogo).toBeVisible();
    // The list is read again: the row now says why instead of offering the button.
    await dialogo.getByRole('button', { name: 'Cancelar' }).click();
    await expect(fila(page, 4).getByRole('button', { name: 'Eliminar definitivamente' })).toHaveCount(0);
    await expect(fila(page, 4).locator('.field__hint')).toHaveText('No se puede eliminar: la usaron campañas.');
  });

  test('borrar la versión que está a la vista devuelve la pantalla a la primera habilitada', async ({ page }) => {
    const api = conVersiones();
    await abrir(page, api);
    await abrirPanel(page);
    await fila(page, 4).getByRole('button', { name: 'Ver' }).click();
    await expect(version(page)).toHaveValue('4');

    await fila(page, 4).getByRole('button', { name: 'Eliminar definitivamente' }).click();
    const dialogo = page.getByRole('dialog', { name: 'Eliminar definitivamente la versión «Borrable uno»' });
    await dialogo.getByLabel('Entiendo que no se puede deshacer').check();
    await dialogo.getByRole('button', { name: 'Eliminar definitivamente' }).click();

    await expect(version(page)).toHaveValue('1');
    await expect(version(page).locator('option')).toHaveText(['Speech original (original)', 'Activa']);
  });
});

test.describe('la campaña', () => {
  async function abrirCampana(page: Page, api: ApiFalsaMowaMes): Promise<void> {
    await montarApiMowaMes(page, api);
    await montarSeleccion(page, seleccionFalsa({ selecciones: [seleccionGuardada({ id: 1, nombre: 'Preventiva top 1000' })] }));
    await page.goto('/mowa-mes/campana');
    await expect(page.getByRole('heading', { name: 'Campaña de MOWA MES', level: 1 })).toBeVisible();
    await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
  }
  const selector = (page: Page) => page.locator('#mm-speech');

  test('el selector muestra solo las habilitadas, con el original primero', async ({ page }) => {
    await abrirCampana(page, conVersiones());

    await expect(selector(page).locator('option')).toHaveText(['Speech original (automático)', 'Activa']);
    await expect(page.locator('[data-speech-ninguna]')).toBeHidden();
  });

  test('con el original deshabilitado, preselecciona la primera habilitada', async ({ page }) => {
    const api = conVersiones();
    api.versiones[0] = conEliminable({ ...speechOriginal(), deshabilitada_en: DESHABILITADA_EN });
    await abrirCampana(page, api);

    await expect(selector(page).locator('option')).toHaveText(['Activa']);
    await expect(selector(page)).toHaveValue('2');
  });

  test('sin ninguna habilitada: el select queda inactivo, el aviso con su enlace y «Crear campaña» inactivo', async ({ page }) => {
    const api = conVersiones();
    api.versiones = api.versiones.map((v) => conEliminable({ ...v, deshabilitada_en: DESHABILITADA_EN }));
    await abrirCampana(page, api);

    await expect(selector(page)).toBeDisabled();
    await expect(selector(page).locator('option')).toHaveText(['No hay versiones habilitadas']);
    const aviso = page.locator('[data-speech-ninguna]');
    await expect(aviso).toBeVisible();
    await expect(aviso).toHaveClass(/notice--warning/);
    await expect(aviso).toContainText('No hay ninguna versión de speech habilitada. Habilita una en la configuración para crear la campaña.');
    await expect(aviso.getByRole('link', { name: 'Ir a la configuración' })).toHaveAttribute('href', '/mowa-mes/configuracion');
    await expect(page.getByRole('button', { name: 'Crear campaña' })).toBeDisabled();
  });
});

test.describe('idioma y anchos', () => {
  test('en inglés traduce las acciones, el panel, el candado y el diálogo', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    await montarConfiguracion(page, conVersiones());
    await page.goto(RUTA);
    await expect(page.getByRole('button', { name: 'Rename' }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Disable' })).toBeVisible();
    await expect(page.locator('[data-deshabilitadas] summary')).toHaveText('Disabled versions (3)');

    await page.locator('[data-deshabilitadas] summary').click();
    await expect(fila(page, 4).locator('.tag')).toHaveText(['Disabled']);
    await expect(fila(page, 3).locator('.field__hint')).toHaveText('It cannot be deleted: campaigns used it.');
    await fila(page, 4).getByRole('button', { name: 'View' }).click();
    await expect(page.locator('[data-speech-inmutable]')).toContainText('This version is disabled');

    await fila(page, 5).getByRole('button', { name: 'Delete permanently' }).click();
    const dialogo = page.getByRole('dialog', { name: 'Permanently delete the “Borrable dos” version' });
    await expect(dialogo.getByLabel('I understand this cannot be undone')).toBeVisible();
  });

  test('a 360 px no desborda y los botones de cada fila quedan a la vista', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await abrir(page, conVersiones());
    await abrirPanel(page);

    const desborde = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(desborde).toBeLessThanOrEqual(0);
    for (const nombre of ['Ver', 'Habilitar', 'Eliminar definitivamente']) {
      const caja = (await fila(page, 4).getByRole('button', { name: nombre }).boundingBox())!;
      expect(caja.x).toBeGreaterThanOrEqual(0);
      expect(caja.x + caja.width).toBeLessThanOrEqual(361);
    }
  });

  for (const tema of ['light', 'dark'] as const) {
    for (const ancho of [1280, 360]) {
      test(`sin violaciones WCAG a ${ancho} px, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, async ({ page }) => {
        await page.addInitScript((elegido) => {
          localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
        }, tema);
        await page.setViewportSize({ width: ancho, height: 900 });
        await abrir(page, conVersiones());
        await abrirPanel(page);
        await fila(page, 4).getByRole('button', { name: 'Ver' }).click();
        await expect(candado(page)).toBeVisible();
        // The preview of the version just opened is being calculated, and its lengths are dimmed meanwhile: axe reads
        // the contrast of what is painted, so it waits for the calculation to end (as accesibilidad.spec does).
        await expect(page.locator('#mm-speech-v2 [data-segmento-botones] button')).toHaveCount(6);
        await expect(page.locator('[data-form-speech]')).not.toHaveAttribute('data-calculando', 'true');

        const lista = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
        expect(lista.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);

        // And with each dialog open.
        await fila(page, 5).getByRole('button', { name: 'Eliminar definitivamente' }).click();
        const dialogo = page.getByRole('dialog', { name: 'Eliminar definitivamente la versión «Borrable dos»' });
        await expect(dialogo).toBeVisible();
        const confirmando = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
        expect(confirmando.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
      });
    }
  }
});
