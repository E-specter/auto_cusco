/**
 * TextosGuardados on its own, through the test-only page /pruebas/textos-guardados (T-HI-F2b, RF-69;
 * docs/motor-texto-enriquecido-interfaz.md §11.3 and §11.5). The editor is a textarea; the texts come from the
 * fake of `/textos-guardados` and its synthetic contexts. Every name and text is invented.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { apiVacia, montarApi } from './api-falsa';
import {
  apiTextosGuardados,
  CONTEXTO_EXPRESION,
  manejadorTextosGuardados,
  textoFalso,
  type ApiFalsaTextosGuardados,
} from './api-falsa-textos-guardados';

test.use({ reducedMotion: 'reduce' });

async function abrir(page: Page, api: ApiFalsaTextosGuardados, consulta = ''): Promise<ApiFalsaTextosGuardados> {
  const base = apiVacia();
  base.manejadores = [manejadorTextosGuardados(api)];
  await montarApi(page, base);
  await page.goto(`/pruebas/textos-guardados${consulta}`);
  await expect(page.locator('body')).toHaveAttribute('data-montado', 'true');
  return api;
}

/** Two enabled texts, «Cobranza» first by name. */
function conDosTextos(): ApiFalsaTextosGuardados {
  const api = apiTextosGuardados();
  api.textos.push(textoFalso({ id: 1, nombre: 'Preventivo', versiones: 2 }), textoFalso({ id: 2, nombre: 'Cobranza' }));
  return api;
}

const raiz = (page: Page) => page.locator('#textos-prueba');
const selectorDeTexto = (page: Page) => page.getByLabel('Texto', { exact: true });
const contenido = (page: Page) => page.getByLabel('Contenido', { exact: true });
const guardar = (page: Page) => page.getByRole('button', { name: 'Guardar', exact: true });
const anuncio = (page: Page) => raiz(page).locator('[data-textos-anuncio]');
const pedidosA = (api: ApiFalsaTextosGuardados, metodo: string, ruta: string) =>
  api.pedidos.filter((p) => p.metodo === metodo && p.ruta.split('?')[0] === ruta);

/** Chooses a text by its option and waits for its content. */
async function elegir(page: Page, nombre: string, esperado: string): Promise<void> {
  await selectorDeTexto(page).selectOption({ label: nombre });
  await expect(contenido(page)).toHaveValue(esperado);
}

test.describe('carga inicial', () => {
  test('lista los textos habilitados por nombre y abre el primero con su versión vigente', async ({ page }) => {
    await abrir(page, conDosTextos());

    await expect(raiz(page).getByRole('heading', { name: 'Mensajes de prueba', level: 2 })).toBeVisible();
    await expect(selectorDeTexto(page).locator('option')).toHaveText(['Cobranza', 'Preventivo']);
    await expect(selectorDeTexto(page)).toHaveValue('2');
    await expect(contenido(page)).toHaveValue('Hola Cobranza, v1');
    await expect(raiz(page).locator('[data-textos-version]')).toHaveText('Versión 1');
    await expect(page.getByText('Al guardar se crea la versión 2; la 1 no cambia.')).toBeVisible();
    await expect(guardar(page)).toBeDisabled();
    // Los deshabilitados no se ofrecen, y sin ninguno no hay panel plegado.
    await expect(raiz(page).locator('[data-textos-deshab]')).toBeHidden();
  });

  test('sin textos guardados abre uno nuevo, con el nombre a escribir', async ({ page }) => {
    await abrir(page, apiTextosGuardados());

    await expect(selectorDeTexto(page).locator('option')).toHaveText(['Sin guardar: texto nuevo']);
    await expect(page.getByLabel('Nombre', { exact: true })).toBeVisible();
    await expect(page.getByText('Al guardar se crea la versión 1.')).toBeVisible();
    await expect(guardar(page)).toBeDisabled();
    await expect(page.getByRole('button', { name: /^(Renombrar|Deshabilitar|Eliminar)/ })).toHaveCount(0);
  });

  test('un contexto que nadie registró se dice, y no se ofrece nada', async ({ page }) => {
    await abrir(page, conDosTextos(), '?contexto=desconocido');
    await expect(raiz(page).locator('[data-textos-error]')).toHaveText('Ese tipo de texto guardado no está disponible.');
    await expect(selectorDeTexto(page)).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Nuevo' })).toBeDisabled();
  });

  test('un contexto de expresión recibe su tipo y guarda lo que su editor arma', async ({ page }) => {
    const api = apiTextosGuardados();
    await abrir(page, api, `?contexto=${CONTEXTO_EXPRESION}`);
    await page.getByLabel('Nombre', { exact: true }).fill('Con expresión');
    await contenido(page).fill('Hola');
    await guardar(page).click();
    await expect(anuncio(page)).toHaveText('Se creó «Con expresión».');
    const cuerpo = pedidosA(api, 'POST', '/textos-guardados')[0].cuerpo as { contexto: string; contenido: unknown };
    expect(cuerpo.contexto).toBe(CONTEXTO_EXPRESION);
    expect(cuerpo.contenido).toEqual({ expresion: { nodos: [{ tipo: 'texto', valor: 'Hola' }] } });
  });

  test('lo que el módulo agrega a la opción y a la línea de versión se muestra', async ({ page }) => {
    const api = apiTextosGuardados();
    api.textos.push(textoFalso({ id: 1, nombre: 'Preventivo', versiones: 2, usadasHasta: 1 }));
    await abrir(page, api, '?etiqueta=1&usos=1');
    await expect(selectorDeTexto(page).locator('option')).toHaveText(['Preventivo · versión 2']);
    // La versión vigente (la 2) no se usó; la 1 sí, y el módulo dice cuántas veces.
    await expect(raiz(page).locator('[data-textos-version]')).toHaveText('Versión 2');
    await page.getByLabel('Ver otra versión').selectOption('1');
    await expect(raiz(page).locator('[data-textos-version]')).toHaveText('Versión 1 · usada en 3 campañas');
  });

  test('sin conteo del módulo, una versión usada dice solo que se usó', async ({ page }) => {
    const api = apiTextosGuardados();
    api.textos.push(textoFalso({ id: 1, usadasHasta: 1 }));
    await abrir(page, api);
    await expect(raiz(page).locator('[data-textos-version]')).toHaveText('Versión 1 · usada');
  });
});

test.describe('crear, guardar una versión y ver una anterior', () => {
  test('un texto nuevo se crea con su versión 1 y queda abierto, con su nombre fijo', async ({ page }) => {
    const api = await abrir(page, conDosTextos());
    await page.getByRole('button', { name: 'Nuevo' }).click();
    await expect(selectorDeTexto(page)).toHaveValue('');
    await expect(page.getByLabel('Nombre', { exact: true })).toBeFocused();

    await page.getByLabel('Nombre', { exact: true }).fill('  Recordatorio ');
    await contenido(page).fill('Hola, te recordamos tu cuota');
    await expect(guardar(page)).toBeEnabled();
    await guardar(page).click();

    await expect(anuncio(page)).toHaveText('Se creó «Recordatorio».');
    expect(pedidosA(api, 'POST', '/textos-guardados')[0].cuerpo).toEqual({
      contexto: 'sintetico.texto',
      nombre: '  Recordatorio ',
      contenido: { texto: 'Hola, te recordamos tu cuota' },
    });
    await expect(selectorDeTexto(page).locator('option')).toHaveText(['Cobranza', 'Preventivo', 'Recordatorio']);
    await expect(page.getByRole('combobox', { name: 'Texto', exact: true })).toHaveValue('3');
    await expect(page.getByLabel('Nombre', { exact: true })).toBeHidden();
    await expect(raiz(page).locator('[data-textos-version]')).toHaveText('Versión 1');
  });

  test('guardar crea la versión siguiente, y las anteriores se ven en solo lectura', async ({ page }) => {
    const api = await abrir(page, conDosTextos());
    await elegir(page, 'Preventivo', 'Hola Preventivo, v2');
    await expect(page.getByLabel('Ver otra versión').locator('option')).toHaveText(['Versión 2 (vigente)', 'Versión 1']);

    await contenido(page).fill('Hola Preventivo, v3');
    await expect(guardar(page)).toBeEnabled();
    await guardar(page).click();
    await expect(anuncio(page)).toHaveText('Se guardó la versión 3 de «Preventivo».');
    expect(pedidosA(api, 'POST', '/textos-guardados/1/versiones')[0].cuerpo).toEqual({ contenido: { texto: 'Hola Preventivo, v3' } });
    await expect(raiz(page).locator('[data-textos-version]')).toHaveText('Versión 3');
    // Las anteriores no cambiaron.
    expect(api.textos[0].versiones.map((v) => (v.contenido as { texto: string }).texto)).toEqual([
      'Hola Preventivo, v1',
      'Hola Preventivo, v2',
      'Hola Preventivo, v3',
    ]);

    await page.getByLabel('Ver otra versión').selectOption('1');
    await expect(contenido(page)).toHaveValue('Hola Preventivo, v1');
    await expect(contenido(page)).toHaveJSProperty('readOnly', true);
    await expect(page.getByText('Estás viendo la versión 1, solo para leer. La vigente es la 3.')).toBeVisible();
    await expect(guardar(page)).toBeHidden();

    await page.getByRole('button', { name: 'Ir a la vigente' }).click();
    await expect(contenido(page)).toHaveValue('Hola Preventivo, v3');
    await expect(contenido(page)).toHaveJSProperty('readOnly', false);
  });

  test('«Usar como base» arranca una versión nueva con el contenido de la antigua', async ({ page }) => {
    const api = await abrir(page, conDosTextos());
    await elegir(page, 'Preventivo', 'Hola Preventivo, v2');
    await page.getByLabel('Ver otra versión').selectOption('1');
    await page.getByRole('button', { name: 'Usar como base' }).click();

    await expect(contenido(page)).toHaveJSProperty('readOnly', false);
    await expect(page.getByText('Al guardar se crea la versión 3 con el contenido de la 1.')).toBeVisible();
    // Guardar se ofrece sin cambios: copiar lo antiguo hacia adelante es el punto.
    await expect(guardar(page)).toBeEnabled();
    await guardar(page).click();
    await expect(anuncio(page)).toHaveText('Se guardó la versión 3 de «Preventivo».');
    expect(pedidosA(api, 'POST', '/textos-guardados/1/versiones')[0].cuerpo).toEqual({ contenido: { texto: 'Hola Preventivo, v1' } });
  });

  test('lo que el backend rechaza se muestra bajo el editor y lo escrito se conserva', async ({ page }) => {
    const api = await abrir(page, conDosTextos());
    await contenido(page).fill('   ');
    await guardar(page).click();
    await expect(raiz(page).locator('[data-textos-problemas]')).toContainText('El texto no tiene una forma válida');
    await expect(contenido(page)).toHaveValue('   ');
    expect(api.textos[1].versiones).toHaveLength(1);
  });

  test('un nombre repetido al crear se explica bajo el campo, sin cerrar nada', async ({ page }) => {
    await abrir(page, conDosTextos());
    await page.getByRole('button', { name: 'Nuevo' }).click();
    await page.getByLabel('Nombre', { exact: true }).fill('cobranza');
    await contenido(page).fill('algo');
    await guardar(page).click();
    await expect(raiz(page).locator('[data-textos-nombre-error]')).toHaveText('Ya existe un texto con ese nombre. Elige otro.');
    await expect(page.getByLabel('Nombre', { exact: true })).toHaveAttribute('aria-invalid', 'true');
    await expect(page.getByLabel('Nombre', { exact: true })).toBeFocused();
    await expect(contenido(page)).toHaveValue('algo');
  });
});

test.describe('renombrar', () => {
  test('el diálogo no crea versión: con el error de nombre repetido y luego el nombre nuevo', async ({ page }) => {
    const api = await abrir(page, conDosTextos());
    await elegir(page, 'Preventivo', 'Hola Preventivo, v2');
    await page.getByRole('button', { name: 'Renombrar «Preventivo»' }).click();

    const dialogo = page.getByRole('dialog', { name: 'Renombrar «Preventivo»' });
    await expect(dialogo).toBeVisible();
    const campo = dialogo.getByLabel('Nombre nuevo');
    await expect(campo).toHaveValue('Preventivo');
    await expect(campo).toBeFocused();
    // Sin cambios, no hay nada que hacer.
    await expect(dialogo.getByRole('button', { name: 'Renombrar' })).toBeDisabled();

    await campo.fill('COBRANZA');
    await dialogo.getByRole('button', { name: 'Renombrar' }).click();
    await expect(dialogo.getByText('Ya existe un texto con ese nombre. Elige otro.')).toBeVisible();
    await expect(campo).toHaveAttribute('aria-invalid', 'true');
    await expect(campo).toHaveValue('COBRANZA');
    await expect(dialogo).toBeVisible();

    await campo.fill('Preventivo B');
    await dialogo.getByRole('button', { name: 'Renombrar' }).click();
    await expect(dialogo).toBeHidden();
    await expect(anuncio(page)).toHaveText('Renombrado a «Preventivo B».');
    await expect(selectorDeTexto(page).locator('option')).toHaveText(['Cobranza', 'Preventivo B']);
    await expect(page.getByRole('button', { name: 'Renombrar «Preventivo B»' })).toBeFocused();
    // Ninguna versión nueva, y lo que se leía sigue ahí.
    expect(api.textos[0].versiones).toHaveLength(2);
    expect(pedidosA(api, 'POST', '/textos-guardados/1/versiones')).toHaveLength(0);
    await expect(contenido(page)).toHaveValue('Hola Preventivo, v2');
  });

  test('renombrar no toca lo escrito y no pide confirmar cambios', async ({ page }) => {
    await abrir(page, conDosTextos());
    await contenido(page).fill('Sin guardar todavía');
    await page.getByRole('button', { name: 'Renombrar «Cobranza»' }).click();
    const dialogo = page.getByRole('dialog', { name: 'Renombrar «Cobranza»' });
    await dialogo.getByLabel('Nombre nuevo').fill('Cobranza 2');
    await dialogo.getByRole('button', { name: 'Renombrar' }).click();
    await expect(dialogo).toBeHidden();
    await expect(contenido(page)).toHaveValue('Sin guardar todavía');
    await expect(page.getByRole('dialog')).toHaveCount(0);
  });
});

test.describe('deshabilitar y habilitar', () => {
  test('un texto deshabilitado sale del select y va al panel plegado, desde donde se ve y se vuelve a habilitar', async ({ page }) => {
    const api = await abrir(page, conDosTextos());
    await elegir(page, 'Preventivo', 'Hola Preventivo, v2');
    await page.getByRole('button', { name: 'Deshabilitar «Preventivo»' }).click();

    await expect(anuncio(page)).toHaveText('Se deshabilitó «Preventivo». Ya no se ofrece para lo nuevo.');
    await expect(selectorDeTexto(page).locator('option')).toHaveText(['Cobranza']);
    // El foco no se pierde con el botón que se fue: va al select.
    await expect(selectorDeTexto(page)).toBeFocused();
    expect(api.textos[0].deshabilitado_en).not.toBeNull();

    const panel = raiz(page).locator('[data-textos-deshab]');
    await expect(panel).toBeVisible();
    await expect(panel).not.toHaveAttribute('open', '');
    await expect(panel.locator('summary')).toHaveText('Deshabilitados (1)');
    await panel.locator('summary').click();
    const fila = panel.locator('li[data-texto="1"]');
    await expect(fila).toContainText('Preventivo');
    await expect(fila.getByText('Deshabilitado', { exact: true })).toBeVisible();

    // «Ver»: solo lectura, con su estado y sin versiones nuevas.
    await fila.getByRole('button', { name: 'Ver «Preventivo»' }).click();
    await expect(contenido(page)).toHaveValue('Hola Preventivo, v2');
    await expect(contenido(page)).toHaveJSProperty('readOnly', true);
    await expect(raiz(page).locator('[data-textos-aviso]')).toContainText('Este texto está deshabilitado');
    await expect(raiz(page).locator('[data-textos-tag-deshabilitado]')).toBeVisible();
    await expect(guardar(page)).toBeHidden();
    await expect(page.getByRole('button', { name: /^Renombrar|^Deshabilitar/ })).toHaveCount(0);

    await fila.getByRole('button', { name: 'Habilitar «Preventivo»' }).click();
    await expect(anuncio(page)).toHaveText('Se habilitó «Preventivo».');
    await expect(selectorDeTexto(page).locator('option')).toHaveText(['Cobranza', 'Preventivo']);
    await expect(panel).toBeHidden();
    await expect(selectorDeTexto(page)).toBeFocused();
    expect(api.textos[0].deshabilitado_en).toBeNull();
  });

  test('deshabilitar el único texto deja uno nuevo abierto', async ({ page }) => {
    const api = apiTextosGuardados();
    api.textos.push(textoFalso({ id: 1, nombre: 'Único' }));
    await abrir(page, api);
    await page.getByRole('button', { name: 'Deshabilitar «Único»' }).click();
    await expect(selectorDeTexto(page).locator('option')).toHaveText(['Sin guardar: texto nuevo']);
    await expect(page.getByLabel('Nombre', { exact: true })).toBeVisible();
    await expect(raiz(page).locator('[data-textos-deshab] summary')).toHaveText('Deshabilitados (1)');
  });
});

test.describe('eliminar', () => {
  test('con la casilla obligatoria, y solo si ninguna versión se usó', async ({ page }) => {
    const api = await abrir(page, conDosTextos());
    await page.getByRole('button', { name: 'Eliminar «Cobranza»' }).click();
    const dialogo = page.getByRole('dialog', { name: 'Eliminar definitivamente «Cobranza»' });
    await expect(dialogo).toBeVisible();
    await expect(dialogo.getByRole('button', { name: 'Cancelar' })).toBeFocused();
    await expect(dialogo.getByRole('button', { name: 'Eliminar definitivamente' })).toBeDisabled();

    await dialogo.getByRole('button', { name: 'Cancelar' }).click();
    expect(api.textos).toHaveLength(2);

    await page.getByRole('button', { name: 'Eliminar «Cobranza»' }).click();
    await dialogo.getByLabel('Entiendo que no se puede deshacer').check();
    await dialogo.getByRole('button', { name: 'Eliminar definitivamente' }).click();
    await expect(dialogo).toBeHidden();
    await expect(anuncio(page)).toHaveText('Se eliminó «Cobranza».');
    expect(api.textos.map((t) => t.nombre)).toEqual(['Preventivo']);
    await expect(selectorDeTexto(page).locator('option')).toHaveText(['Preventivo']);
    await expect(selectorDeTexto(page)).toBeFocused();
  });

  test('si alguna versión se usó, no se ofrece y el motivo ocupa su lugar', async ({ page }) => {
    const api = apiTextosGuardados();
    api.textos.push(textoFalso({ id: 1, nombre: 'Usado', versiones: 2, usadasHasta: 1 }));
    await abrir(page, api);
    // Se usó la versión 1, no la vigente: el texto lo sabe por sus versiones.
    await expect(page.getByRole('button', { name: /^Eliminar/ })).toHaveCount(0);
    await expect(page.getByText('No se puede eliminar: ya se usó. Puedes deshabilitarlo.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Deshabilitar «Usado»' })).toBeVisible();
  });

  test('un deshabilitado con una versión vieja usada no ofrece eliminar: el listado lo dice (eliminable)', async ({ page }) => {
    const api = apiTextosGuardados();
    api.textos.push(
      textoFalso({ id: 1, nombre: 'Activo' }),
      textoFalso({ id: 2, nombre: 'Viejo', versiones: 2, usadasHasta: 1, deshabilitado_en: '2026-10-05T10:00:00-05:00' }),
      textoFalso({ id: 3, nombre: 'Limpio', deshabilitado_en: '2026-10-05T10:00:00-05:00' }),
    );
    await abrir(page, api);
    const panel = raiz(page).locator('[data-textos-deshab]');
    await panel.locator('summary').click();
    await expect(panel.getByRole('button', { name: 'Eliminar «Viejo»' })).toHaveCount(0);
    await expect(panel.locator('li[data-texto="2"]').getByText('No se puede eliminar: ya se usó.')).toBeVisible();
    // Sin ningún uso, sí.
    await expect(panel.getByRole('button', { name: 'Eliminar «Limpio»' })).toBeVisible();
  });

  test('si el backend lo rechaza después de todo (409), el botón se va y el motivo ocupa su lugar', async ({ page }) => {
    const api = apiTextosGuardados();
    api.textos.push(
      textoFalso({ id: 1, nombre: 'Activo' }),
      textoFalso({ id: 2, nombre: 'Viejo', deshabilitado_en: '2026-10-05T10:00:00-05:00' }),
    );
    // Alguien lo usó entre la lectura de la lista y este clic.
    api.respuestas.eliminar.push({ estado: 409, cuerpo: { detail: 'usado', codigo: 'texto_guardado_usado' } });
    await abrir(page, api);
    const panel = raiz(page).locator('[data-textos-deshab]');
    await panel.locator('summary').click();
    await panel.getByRole('button', { name: 'Eliminar «Viejo»' }).click();
    const dialogo = page.getByRole('dialog', { name: 'Eliminar definitivamente «Viejo»' });
    await dialogo.getByLabel('Entiendo que no se puede deshacer').check();
    await dialogo.getByRole('button', { name: 'Eliminar definitivamente' }).click();
    await expect(dialogo.getByText('Este texto ya se usó en una versión y no se puede eliminar.')).toBeVisible();
    await dialogo.getByRole('button', { name: 'Cancelar' }).click();
    expect(api.textos).toHaveLength(2);
    await expect(panel.getByRole('button', { name: 'Eliminar «Viejo»' })).toHaveCount(0);
    await expect(panel.getByText('No se puede eliminar: ya se usó.')).toBeVisible();
  });
});

test.describe('cambios sin guardar', () => {
  test('cambiar de texto con algo escrito pide confirmar, y «Seguir editando» deja todo como estaba', async ({ page }) => {
    await abrir(page, conDosTextos());
    await contenido(page).fill('Escrito sin guardar');
    await selectorDeTexto(page).selectOption({ label: 'Preventivo' });

    const dialogo = page.getByRole('dialog', { name: 'Hay cambios sin guardar' });
    await expect(dialogo).toBeVisible();
    await expect(dialogo.getByText('Los cambios que no guardaste se pierden.')).toBeVisible();
    await dialogo.getByRole('button', { name: 'Seguir editando' }).click();
    await expect(dialogo).toBeHidden();
    await expect(selectorDeTexto(page)).toHaveValue('2');
    await expect(contenido(page)).toHaveValue('Escrito sin guardar');

    await selectorDeTexto(page).selectOption({ label: 'Preventivo' });
    await dialogo.getByRole('button', { name: 'Descartar cambios' }).click();
    await expect(contenido(page)).toHaveValue('Hola Preventivo, v2');
    await expect(selectorDeTexto(page)).toHaveValue('1');
  });

  test('«Nuevo», cambiar de versión y «Deshabilitar» también preguntan; y «Descartar cambios» vuelve a lo guardado', async ({ page }) => {
    await abrir(page, conDosTextos());
    await elegir(page, 'Preventivo', 'Hola Preventivo, v2');
    await contenido(page).fill('Cambiado');
    const dialogo = page.getByRole('dialog', { name: 'Hay cambios sin guardar' });

    await page.getByRole('button', { name: 'Nuevo' }).click();
    await expect(dialogo).toBeVisible();
    await dialogo.getByRole('button', { name: 'Seguir editando' }).click();
    await expect(dialogo).toBeHidden();

    await page.getByLabel('Ver otra versión').selectOption('1');
    await expect(dialogo).toBeVisible();
    await dialogo.getByRole('button', { name: 'Seguir editando' }).click();
    await expect(dialogo).toBeHidden();
    await expect(page.getByLabel('Ver otra versión')).toHaveValue('2');

    await page.getByRole('button', { name: 'Deshabilitar «Preventivo»' }).click();
    await expect(dialogo).toBeVisible();
    await dialogo.getByRole('button', { name: 'Seguir editando' }).click();

    await page.getByRole('button', { name: 'Descartar cambios', exact: true }).click();
    await expect(contenido(page)).toHaveValue('Hola Preventivo, v2');
    await expect(page.getByRole('dialog')).toHaveCount(0);
  });

  test('el módulo puede preguntar antes de irse, y lo escrito cuenta como un cambio', async ({ page }) => {
    await abrir(page, conDosTextos());
    const hay = () => page.evaluate(() => (window as unknown as { controladorPrueba: { hayCambios(): boolean } }).controladorPrueba.hayCambios());
    expect(await hay()).toBe(false);
    await contenido(page).fill('algo');
    expect(await hay()).toBe(true);
    await contenido(page).fill('Hola Cobranza, v1');
    expect(await hay()).toBe(false);
  });
});

test('si la lista no carga, lo dice con «Reintentar», que la pide otra vez', async ({ page }) => {
  const api = conDosTextos();
  api.sinRed = true;
  await abrir(page, api);
  await expect(raiz(page).locator('[data-textos-error]')).toHaveText('No se pudieron cargar los textos guardados.');
  await expect(selectorDeTexto(page)).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Nuevo' })).toBeDisabled();

  api.sinRed = false;
  await page.getByRole('button', { name: 'Reintentar' }).click();
  await expect(selectorDeTexto(page).locator('option')).toHaveText(['Cobranza', 'Preventivo']);
  await expect(raiz(page).locator('[data-textos-error]')).toBeEmpty();
  await expect(page.getByRole('button', { name: 'Reintentar' })).toBeHidden();
  await expect(contenido(page)).toHaveValue('Hola Cobranza, v1');
  await expect(guardar(page)).toBeDisabled();
});

test('un nombre que el backend rechaza dice su límite en la frase', async ({ page }) => {
  await abrir(page, conDosTextos());
  await page.getByRole('button', { name: 'Renombrar «Cobranza»' }).click();
  const dialogo = page.getByRole('dialog', { name: 'Renombrar «Cobranza»' });
  await dialogo.getByLabel('Nombre nuevo').fill('x'.repeat(121));
  await dialogo.getByRole('button', { name: 'Renombrar' }).click();
  await expect(dialogo.getByText('Escribe un nombre de 1 a 120 caracteres.')).toBeVisible();
});

test.describe('la opción filtrar del módulo', () => {
  const ocultar = (page: Page, ...nombres: string[]) =>
    page.evaluate((cuales) => {
      const conjunto = (window as unknown as { ocultosPrueba: Set<string> }).ocultosPrueba;
      conjunto.clear();
      cuales.forEach((n) => conjunto.add(n));
    }, nombres);
  const repintar = (page: Page) =>
    page.evaluate(() => (window as unknown as { controladorPrueba: { repintar(): void } }).controladorPrueba.repintar());

  test('sin la opción no cambia nada: se ofrecen todos', async ({ page }) => {
    await abrir(page, conDosTextos(), '?ocultos=Cobranza');
    await expect(selectorDeTexto(page).locator('option')).toHaveText(['Cobranza', 'Preventivo']);
  });

  test('con la opción, los que no la pasan no se ofrecen en el select ni en los deshabilitados, y el primero es el primero ofrecido', async ({ page }) => {
    const api = conDosTextos();
    api.textos.push(
      textoFalso({ id: 3, nombre: 'Viejo', deshabilitado_en: '2026-10-05T10:00:00-05:00' }),
      textoFalso({ id: 4, nombre: 'Otro', deshabilitado_en: '2026-10-06T10:00:00-05:00' }),
    );
    await abrir(page, api, '?filtrar=1&ocultos=Cobranza,Viejo');

    await expect(selectorDeTexto(page).locator('option')).toHaveText(['Preventivo']);
    // El primero que se abre es el primero que se ofrece, no el primero del API.
    await expect(contenido(page)).toHaveValue('Hola Preventivo, v2');
    const panel = raiz(page).locator('[data-textos-deshab]');
    await expect(panel.locator('summary')).toHaveText('Deshabilitados (1)');
    await panel.locator('summary').click();
    await expect(panel.locator('li')).toHaveCount(1);
    await expect(panel.locator('li[data-texto="4"]')).toContainText('Otro');
  });

  test('si todos los deshabilitados quedan fuera, el panel plegado no se muestra', async ({ page }) => {
    const api = conDosTextos();
    api.textos.push(textoFalso({ id: 3, nombre: 'Viejo', deshabilitado_en: '2026-10-05T10:00:00-05:00' }));
    await abrir(page, api, '?filtrar=1&ocultos=Viejo');
    await expect(raiz(page).locator('[data-textos-deshab]')).toBeHidden();
  });

  test('se pregunta en cada repintado: un vínculo que cambió se refleja sin volver a montar', async ({ page }) => {
    await abrir(page, conDosTextos(), '?filtrar=1');
    await expect(selectorDeTexto(page).locator('option')).toHaveText(['Cobranza', 'Preventivo']);

    await ocultar(page, 'Preventivo');
    await repintar(page);
    await expect(selectorDeTexto(page).locator('option')).toHaveText(['Cobranza']);

    await ocultar(page);
    await repintar(page);
    await expect(selectorDeTexto(page).locator('option')).toHaveText(['Cobranza', 'Preventivo']);
  });

  test('un texto abierto que deja de pasar el filtro sigue abierto, sale del select y se cambia eligiendo otro', async ({ page }) => {
    await abrir(page, conDosTextos(), '?filtrar=1');
    await elegir(page, 'Preventivo', 'Hola Preventivo, v2');
    await contenido(page).fill('Lo que escribí');

    await ocultar(page, 'Preventivo');
    await repintar(page);

    await expect(selectorDeTexto(page).locator('option')).toHaveText(['Cobranza']);
    // Sigue abierto: su contenido, lo escrito y sus gestos no se tocan.
    await expect(contenido(page)).toHaveValue('Lo que escribí');
    await expect(page.getByRole('button', { name: 'Renombrar «Preventivo»' })).toBeVisible();
    await expect(page.getByRole('dialog')).toHaveCount(0);

    // Hasta que se elige otro, y lo escrito pide confirmar como siempre.
    await selectorDeTexto(page).selectOption({ label: 'Cobranza' });
    await expect(page.getByRole('dialog', { name: 'Hay cambios sin guardar' })).toBeVisible();
    await page.getByRole('dialog').getByRole('button', { name: 'Descartar cambios' }).click();
    await expect(contenido(page)).toHaveValue('Hola Cobranza, v1');
  });

  test('deshabilitar con el filtro puesto abre el siguiente que se ofrece, no uno oculto', async ({ page }) => {
    const api = apiTextosGuardados();
    api.textos.push(
      textoFalso({ id: 1, nombre: 'Alfa' }),
      textoFalso({ id: 2, nombre: 'Beta' }),
      textoFalso({ id: 3, nombre: 'Gamma' }),
    );
    await abrir(page, api, '?filtrar=1&ocultos=Beta');
    await expect(selectorDeTexto(page).locator('option')).toHaveText(['Alfa', 'Gamma']);
    await page.getByRole('button', { name: 'Deshabilitar «Alfa»' }).click();
    await expect(anuncio(page)).toContainText('Se deshabilitó «Alfa»');
    await expect(selectorDeTexto(page).locator('option')).toHaveText(['Gamma']);
    await expect(contenido(page)).toHaveValue('Hola Gamma, v1');
  });
});

test('en inglés dice lo mismo con sus palabras', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' })));
  await abrir(page, conDosTextos());
  await expect(page.getByLabel('Text', { exact: true })).toBeVisible();
  await expect(page.getByText('Saving creates version 2; version 1 does not change.')).toBeVisible();
  await page.getByRole('button', { name: 'Disable “Cobranza”' }).click();
  await expect(anuncio(page)).toHaveText('“Cobranza” was disabled. It is no longer offered for new items.');
  await expect(raiz(page).locator('[data-textos-deshab] summary')).toHaveText('Disabled (1)');
});

// ---- Accessibility: the panel, the folded list and the dialogs ----------------------------------------------------

async function sinViolaciones(page: Page): Promise<void> {
  const resultado = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(resultado.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
}

function conTodo(): ApiFalsaTextosGuardados {
  const api = conDosTextos();
  api.textos.push(textoFalso({ id: 3, nombre: 'Viejo', deshabilitado_en: '2026-10-05T10:00:00-05:00' }));
  return api;
}

for (const tema of ['light', 'dark'] as const) {
  test.describe(`accesibilidad, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((elegido) => {
        localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
      }, tema);
    });

    test('el panel con una versión anterior y la lista de deshabilitados abierta', async ({ page }) => {
      await abrir(page, conTodo());
      await elegir(page, 'Preventivo', 'Hola Preventivo, v2');
      await page.getByLabel('Ver otra versión').selectOption('1');
      await raiz(page).locator('[data-textos-deshab] summary').click();
      await sinViolaciones(page);
    });

    test('un texto nuevo con su error de nombre repetido', async ({ page }) => {
      await abrir(page, conDosTextos());
      await page.getByRole('button', { name: 'Nuevo' }).click();
      await page.getByLabel('Nombre', { exact: true }).fill('Cobranza');
      await contenido(page).fill('algo');
      await guardar(page).click();
      await expect(raiz(page).locator('[data-textos-nombre-error]')).not.toBeEmpty();
      await sinViolaciones(page);
    });

    test('los diálogos de renombrar, eliminar y cambios sin guardar', async ({ page }) => {
      await abrir(page, conDosTextos());
      await page.getByRole('button', { name: 'Renombrar «Cobranza»' }).click();
      await expect(page.getByRole('dialog', { name: /^Renombrar/ })).toBeVisible();
      await sinViolaciones(page);
      await page.keyboard.press('Escape');

      await page.getByRole('button', { name: 'Eliminar «Cobranza»' }).click();
      await expect(page.getByRole('dialog', { name: /^Eliminar/ })).toBeVisible();
      await sinViolaciones(page);
      await page.keyboard.press('Escape');

      await contenido(page).fill('Escrito');
      await selectorDeTexto(page).selectOption({ label: 'Preventivo' });
      await expect(page.getByRole('dialog', { name: 'Hay cambios sin guardar' })).toBeVisible();
      await sinViolaciones(page);
    });
  });
}

test('a 360 px el panel, los gestos y la lista de deshabilitados caben sin desbordar', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 640 });
  await abrir(page, conTodo());
  await raiz(page).locator('[data-textos-deshab] summary').click();
  await sinViolaciones(page);
  const ancho = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(ancho).toBeLessThanOrEqual(360);
});
