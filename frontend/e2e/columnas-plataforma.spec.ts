/**
 * The column builder with labels and with a platform (T-HI-F1, RF-49, RF-72;
 * docs/motor-texto-enriquecido-interfaz.md §11): the label under the name, the platform chosen when the
 * definition is created, the fixed columns with their lock, the headers by position with «Restaurar», and the
 * problems of the platform's rules under their column. The platform is synthetic: the rules come from the
 * fake's `GET /definiciones-columnas/plataformas`, as the screen reads them from the backend. Every name is invented.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { apiVacia, montarApi } from './api-falsa';
import {
  apiDefiniciones,
  contenidoSintetico,
  definicionFalsa,
  manejadorDefiniciones,
  plataformaSintetica,
  type ApiFalsaDefiniciones,
  type DefinicionFalsa,
} from './api-falsa-definiciones';
import { apiTextoEnriquecidoVacia, manejarTextoEnriquecido } from './api-falsa-texto-enriquecido';

const RUTA = '/columnas';
const FIJA = 'Columna fija de Sintética: no se quita ni se mueve.';
const FRASE =
  'Sintética: la 1.ª columna, «destino», es fija; las siguientes se llaman por su posición, [$VAR1$], [$VAR2$]…, y son de texto.';

const pedidosA = (api: ApiFalsaDefiniciones, metodo: string, ruta: string) =>
  api.pedidos.filter((p) => p.metodo === metodo && p.ruta.split('?')[0] === ruta);

async function abrir(page: Page, api: ApiFalsaDefiniciones): Promise<void> {
  const base = apiVacia();
  base.manejadores = [manejarTextoEnriquecido(apiTextoEnriquecidoVacia()), manejadorDefiniciones(api)];
  await montarApi(page, base);
  await page.goto(RUTA);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

/** An API that knows the synthetic platform. */
const conPlataforma = (): ApiFalsaDefiniciones => {
  const api = apiDefiniciones();
  api.plataformas = [plataformaSintetica()];
  return api;
};

const nombreDeColumna = (page: Page, numero: number) => page.getByLabel(`Nombre de la columna ${numero}`);
const selectorDePlataforma = (page: Page) => page.getByLabel('Plataforma', { exact: true });
const filaDe = (page: Page, numero: number) => page.locator('[data-filas] > tr[data-columna]').nth(numero - 1);

/** A new definition for the synthetic platform: its fixed column and the two columns after it. */
async function nuevaConPlataforma(page: Page, api = conPlataforma()): Promise<ApiFalsaDefiniciones> {
  await abrir(page, api);
  await selectorDePlataforma(page).selectOption('sintetica');
  await expect(nombreDeColumna(page, 1)).toHaveValue('destino');
  await page.getByRole('button', { name: 'Agregar columna' }).click();
  await page.getByRole('button', { name: 'Agregar columna' }).click();
  await expect(nombreDeColumna(page, 3)).toHaveValue('[$VAR2$]');
  return api;
}

/** A saved definition of the synthetic platform with these column names, in this order. */
function definicionDeLaPlataforma(nombres: string[], parcial: Partial<Omit<DefinicionFalsa, 'versiones'>> = {}): DefinicionFalsa {
  const d = definicionFalsa({ plataforma: 'sintetica', ...parcial });
  const [modelo] = contenidoSintetico().columnas;
  d.versiones[0].contenido.columnas = nombres.map((nombre, orden) => ({ ...modelo, nombre, orden }));
  return d;
}

test.describe('la etiqueta de la columna (RF-49)', () => {
  test('se escribe en la fila abierta, se ve bajo el nombre y viaja al guardar', async ({ page }) => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa());
    await abrir(page, api);
    await page.getByLabel('Definición guardada').selectOption('1');
    await expect(nombreDeColumna(page, 1)).toHaveValue('telefono');

    // Una versión guardada sin etiquetas se lee igual: ninguna línea bajo el nombre y nada por guardar.
    await expect(page.locator('[data-linea-etiqueta]:visible')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Guardar' })).toBeDisabled();

    await page.getByRole('button', { name: 'Editar telefono' }).click();
    const campo = page.getByLabel('Etiqueta', { exact: true });
    await expect(campo).toHaveAttribute('maxlength', '120');
    await expect(page.getByText(/No sale en el archivo/)).toBeVisible();
    await campo.fill('Teléfono del titular');
    await expect(filaDe(page, 1).locator('[data-linea-etiqueta]')).toHaveText('Teléfono del titular');
    await expect(filaDe(page, 2).locator('[data-linea-etiqueta]')).toBeHidden();

    await page.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByText('Guardada como versión 2.')).toBeVisible();
    const cuerpo = pedidosA(api, 'POST', '/definiciones-columnas/1/versiones')[0].cuerpo as {
      columnas: Array<{ etiqueta?: string | null }>;
    };
    expect(cuerpo.columnas[0].etiqueta).toBe('Teléfono del titular');
    expect(cuerpo.columnas[1].etiqueta ?? null).toBeNull();
    // La etiqueta no es el encabezado: el nombre sigue siendo el del archivo.
    await expect(nombreDeColumna(page, 1)).toHaveValue('telefono');
    await expect(filaDe(page, 1).locator('[data-linea-etiqueta]')).toHaveText('Teléfono del titular');
  });

  test('borrarla la quita de la línea y de lo que se manda', async ({ page }) => {
    const api = apiDefiniciones();
    const d = definicionFalsa();
    d.versiones[0].contenido.columnas[0].etiqueta = 'Teléfono del titular';
    api.definiciones.push(d);
    await abrir(page, api);
    await page.getByLabel('Definición guardada').selectOption('1');
    await expect(filaDe(page, 1).locator('[data-linea-etiqueta]')).toHaveText('Teléfono del titular');

    await page.getByRole('button', { name: 'Editar telefono' }).click();
    await page.getByLabel('Etiqueta', { exact: true }).fill('   ');
    await expect(filaDe(page, 1).locator('[data-linea-etiqueta]')).toBeHidden();
    await page.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByText('Guardada como versión 2.')).toBeVisible();
    const cuerpo = pedidosA(api, 'POST', '/definiciones-columnas/1/versiones')[0].cuerpo as {
      columnas: Array<{ etiqueta?: string | null }>;
    };
    expect(cuerpo.columnas[0].etiqueta ?? null).toBeNull();
  });
});

test.describe('elegir la plataforma al crear (RF-72)', () => {
  test('sin plataformas registradas no hay nada que elegir, y todo es como siempre', async ({ page }) => {
    await abrir(page, apiDefiniciones());
    await expect(selectorDePlataforma(page)).toBeHidden();
    await expect(page.locator('[data-reglas]')).toBeHidden();
    await expect(nombreDeColumna(page, 1)).toBeEditable();
  });

  test('se elige con un select, la frase de las reglas sale de las reglas registradas, y queda como tag al guardar', async ({ page }) => {
    const api = conPlataforma();
    await abrir(page, api);

    const select = selectorDePlataforma(page);
    await expect(select.locator('option')).toHaveText(['Ninguna (archivo libre)', 'Sintética']);
    await expect(select).toHaveValue('');
    await expect(page.getByText('Una plataforma fija algunas columnas y no se cambia después.')).toBeVisible();
    await expect(page.locator('[data-reglas]')).toBeHidden();

    await select.selectOption('sintetica');
    await expect(page.locator('[data-reglas]')).toContainText(FRASE);
    await expect(nombreDeColumna(page, 1)).toHaveValue('destino');
    // Lo que la plataforma pone no es algo que el analista escribió: no hay nada que guardar todavía.
    await expect(page.getByRole('button', { name: 'Guardar' })).toBeDisabled();

    await page.getByLabel('Nombre', { exact: true }).fill('Envío de prueba');
    await page.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByText('Guardada como versión 1.')).toBeVisible();

    const cuerpo = pedidosA(api, 'POST', '/definiciones-columnas')[0].cuerpo as {
      plataforma?: string;
      columnas: Array<{ nombre: string; celda_texto?: boolean; expresion: { nodos: unknown[] } }>;
    };
    expect(cuerpo.plataforma).toBe('sintetica');
    expect(cuerpo.columnas[0]).toMatchObject({ nombre: 'destino', celda_texto: true });
    expect(cuerpo.columnas[0].expresion.nodos).toHaveLength(2);

    // Después de crear, la plataforma no se elige ni se cambia: queda en la línea de versión.
    await expect(selectorDePlataforma(page)).toBeHidden();
    await expect(page.locator('[data-version-linea]')).toContainText('Versión 1');
    await expect(page.locator('[data-plataforma-tag="sintetica"]')).toHaveText('Sintética');
    await expect(page.locator('[data-reglas]')).toContainText(FRASE);
  });

  test('una definición sin plataforma no manda ninguna', async ({ page }) => {
    const api = conPlataforma();
    await abrir(page, api);
    await page.getByLabel('Nombre', { exact: true }).fill('Libre');
    await nombreDeColumna(page, 1).fill('telefono');
    await page.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByText('Guardada como versión 1.')).toBeVisible();
    expect(pedidosA(api, 'POST', '/definiciones-columnas')[0].cuerpo).not.toHaveProperty('plataforma');
    await expect(page.locator('[data-plataforma-tag]')).toHaveCount(0);
  });

  test('cambiar de plataforma con columnas ya escritas pide confirmar, y no pregunta si no hay nada escrito', async ({ page }) => {
    await nuevaConPlataforma(page);
    await selectorDePlataforma(page).selectOption('');
    await expect(page.getByRole('dialog', { name: 'Cambiar la plataforma' })).toBeVisible();
    // A free file keeps one empty column; the yes of a destructive change is the red button.
    await expect(page.getByRole('dialog')).toContainText(
      'Se borran las columnas que escribiste y queda una columna vacía. El nombre y las opciones de la definición no cambian.',
    );
    await expect(page.getByRole('dialog').getByRole('button', { name: 'Cambiar plataforma' })).toHaveClass(/btn--danger/);
    await page.getByRole('dialog').getByRole('button', { name: 'Cancelar' }).click();
    await expect(selectorDePlataforma(page)).toHaveValue('sintetica');
    await expect(nombreDeColumna(page, 3)).toHaveValue('[$VAR2$]');

    await selectorDePlataforma(page).selectOption('');
    await page.getByRole('dialog').getByRole('button', { name: 'Cambiar plataforma' }).click();
    await expect(nombreDeColumna(page, 1)).toHaveValue('');
    await expect(nombreDeColumna(page, 2)).toHaveCount(0);

    // Sin nada escrito, el cambio no pregunta.
    await selectorDePlataforma(page).selectOption('sintetica');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(nombreDeColumna(page, 1)).toHaveValue('destino');
  });

  test('de un archivo libre con columnas escritas a una plataforma, el diálogo dice qué queda', async ({ page }) => {
    await abrir(page, conPlataforma());
    await nombreDeColumna(page, 1).fill('telefono');
    await selectorDePlataforma(page).selectOption('sintetica');
    await expect(page.getByRole('dialog')).toContainText(
      'Se borran las columnas que escribiste y quedan solo las que fija Sintética. El nombre y las opciones de la definición no cambian.',
    );
    await expect(page.getByRole('dialog').getByRole('button', { name: 'Cambiar plataforma' })).toHaveClass(/btn--danger/);
    // «Volver a la definición» no: el diálogo del constructor dice «Cancelar».
    await page.getByRole('dialog').getByRole('button', { name: 'Cancelar' }).click();
    await expect(selectorDePlataforma(page)).toHaveValue('');
    await expect(nombreDeColumna(page, 1)).toHaveValue('telefono');
  });

  test('en inglés dice lo mismo con sus palabras', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' })));
    await abrir(page, conPlataforma());
    await expect(page.getByLabel('Platform', { exact: true }).locator('option')).toHaveText(['None (free file)', 'Sintética']);
    await page.getByLabel('Platform', { exact: true }).selectOption('sintetica');
    await expect(page.locator('[data-reglas]')).toContainText(
      'Sintética: column 1, “destino”, is fixed; the next ones are named by position, [$VAR1$], [$VAR2$]…, and are text.',
    );
    const candado = page.getByRole('img', { name: 'Fixed column', exact: true });
    await expect(candado).toBeVisible();
    await expect(candado).toHaveAccessibleDescription('Fixed Sintética column: it cannot be removed or moved.');
  });
});

test.describe('las columnas fijas (RF-72)', () => {
  test('llevan candado en lugar de quitar y de las flechas, con el nombre y el tipo fijos', async ({ page }) => {
    await nuevaConPlataforma(page);

    await expect(page.getByRole('img', { name: 'Columna fija', exact: true })).toBeVisible();
    for (const accion of ['Quitar', 'Subir', 'Bajar', 'Duplicar']) {
      await expect(page.getByRole('button', { name: `${accion} destino` })).toHaveCount(0);
    }
    await expect(nombreDeColumna(page, 1)).toHaveJSProperty('readOnly', true);
    await expect(page.getByLabel('Tipo de destino')).toBeDisabled();
    await expect(page.getByLabel('Tipo de destino')).toHaveValue('texto');
    await expect(filaDe(page, 1).locator('[data-celda="formato"]')).toHaveText('Texto de Excel');
    // Las demás siguen con todo.
    await expect(page.getByRole('button', { name: 'Quitar [$VAR1$]' })).toBeEnabled();
  });

  test('el candado se llama «Columna fija» aunque a 1280 no tenga texto visible, y su descripción dice la regla', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await nuevaConPlataforma(page);
    const candado = page.getByRole('img', { name: 'Columna fija', exact: true });
    await expect(candado).toBeVisible();
    await expect(candado).toHaveAccessibleDescription(FIJA);
    await expect(candado).toHaveAttribute('title', FIJA);
    // A 1280 el texto no se ve: lo que lo nombra es el candado, no una palabra suelta.
    await expect(filaDe(page, 1).locator('.cl-candado__texto')).toBeHidden();
  });

  test('a 1280 todos los botones de acción miden lo mismo, con su icono entero, en la fila fija y en las demás', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    const api = conPlataforma();
    api.definiciones.push(definicionDeLaPlataforma(['destino', '[$VAR1$]', 'Nombres del titular', '[$VAR3$]']));
    await abrir(page, api);
    await page.getByLabel('Definición guardada').selectOption('1');
    await expect(nombreDeColumna(page, 4)).toBeVisible();
    const medidas = await page.evaluate(() =>
      [...document.querySelectorAll<HTMLElement>('[data-filas] .cl-acciones button')].map((b) => {
        const caja = b.getBoundingClientRect();
        const icono = b.querySelector('svg')?.getBoundingClientRect();
        return [Math.round(caja.width), Math.round(caja.height), Math.round(icono?.width ?? 0)];
      }),
    );
    expect(medidas.length).toBe(1 + 5 * 3);
    expect(new Set(medidas.map((m) => m.join('x')))).toEqual(new Set(['40x40x16']));
    // Y ninguno queda recortado por el desplazamiento de la tabla.
    const sobra = await page.evaluate(() => {
      const c = document.querySelector<HTMLElement>('[data-tabla-contenedor]')!;
      return c.scrollWidth - c.clientWidth;
    });
    expect(sobra).toBeLessThanOrEqual(0);
  });

  test('el contenido se edita si la plataforma lo permite, y si no queda en solo lectura', async ({ page }) => {
    await nuevaConPlataforma(page);
    await page.getByRole('button', { name: 'Editar destino' }).click();
    await expect(page.getByRole('radio', { name: 'Variable directa' })).toBeEnabled();
    await expect(page.locator('#columna-editor')).toBeVisible();
  });

  test('un contenido que no es editable bloquea los modos y el valor por defecto', async ({ page }) => {
    const api = apiDefiniciones();
    const base = plataformaSintetica();
    api.plataformas = [
      plataformaSintetica({ columnas_fijas: [{ ...base.columnas_fijas[0], contenido_editable: false }] }),
    ];
    await abrir(page, api);
    await selectorDePlataforma(page).selectOption('sintetica');
    await page.getByRole('button', { name: 'Editar destino' }).click();
    await expect(page.getByRole('radio', { name: 'Variable directa' })).toBeDisabled();
    await expect(page.getByLabel('Valor por defecto de destino')).toHaveJSProperty('readOnly', true);
    // La etiqueta sí se puede escribir: no es contenido.
    await expect(page.getByLabel('Etiqueta', { exact: true })).toBeEditable();
  });

  test('con una plataforma que no admite más columnas, «Agregar columna» no se ofrece', async ({ page }) => {
    const api = apiDefiniciones();
    api.plataformas = [plataformaSintetica({ admite_mas_columnas: false })];
    await abrir(page, api);
    await selectorDePlataforma(page).selectOption('sintetica');
    await expect(page.getByRole('button', { name: 'Agregar columna' })).toBeDisabled();
    await expect(page.locator('[data-reglas]')).toContainText('y no se agregan más columnas');
  });
});

test.describe('los encabezados por posición (RF-72)', () => {
  test('una columna nueva nace con el de su posición y con el tipo del resto, que no se cambia', async ({ page }) => {
    await nuevaConPlataforma(page);
    await expect(nombreDeColumna(page, 2)).toHaveValue('[$VAR1$]');
    await expect(page.getByLabel('Tipo de [$VAR1$]')).toBeDisabled();
    await expect(page.getByLabel('Tipo de [$VAR1$]')).toHaveValue('texto');
    await expect(filaDe(page, 2).getByText('En Sintética las macros son siempre texto: el valor sale ya formateado.')).toBeVisible();
  });

  test('«Subir» está inactivo en la primera fila que no es fija', async ({ page }) => {
    await nuevaConPlataforma(page);
    await expect(page.getByRole('button', { name: 'Subir [$VAR1$]' })).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Bajar [$VAR1$]' })).toBeEnabled();
    await expect(page.getByRole('button', { name: 'Bajar [$VAR2$]' })).toBeDisabled();
  });

  test('al mover, los que conservan su encabezado se renumeran, y uno editado se conserva con su aviso y «Restaurar»', async ({ page }) => {
    await nuevaConPlataforma(page);
    await nombreDeColumna(page, 2).fill('Nombres del titular');

    // Un encabezado editado es un aviso, no un problema: la definición se guarda igual.
    const aviso = 'Sintética toma las columnas por su orden, no por su nombre: esta es la macro 1.';
    await expect(filaDe(page, 2).getByText(aviso)).toBeVisible();
    await expect(page.locator('[data-resumen]')).toBeHidden();
    await expect(filaDe(page, 3).getByText(/toma las columnas por su orden/)).toBeHidden();
    await expect(page.getByRole('button', { name: 'Restaurar el encabezado de la columna 2' })).toBeVisible();

    await filaDe(page, 2).getByRole('button', { name: /^Bajar/ }).click();
    await expect(nombreDeColumna(page, 2)).toHaveValue('[$VAR1$]');
    await expect(nombreDeColumna(page, 3)).toHaveValue('Nombres del titular');
    await expect(filaDe(page, 3).getByText('esta es la macro 2.')).toBeVisible();

    await page.getByRole('button', { name: 'Restaurar el encabezado de la columna 3' }).click();
    await expect(nombreDeColumna(page, 3)).toHaveValue('[$VAR2$]');
    await expect(page.locator('[data-aviso-posicion]:visible')).toHaveCount(0);
    await expect(page.getByRole('button', { name: /^Restaurar/ })).toBeHidden();
  });

  test('al abrir una definición guardada, «Restaurar» y el aviso solo salen en el encabezado editado', async ({ page }) => {
    const api = conPlataforma();
    api.definiciones.push(definicionDeLaPlataforma(['destino', '[$VAR1$]', 'Nombres del titular', '[$VAR3$]']));
    await abrir(page, api);
    await page.getByLabel('Definición guardada').selectOption('1');
    await expect(nombreDeColumna(page, 3)).toHaveValue('Nombres del titular');

    // Sin teclear nada: el encabezado por defecto (filas 2 y 4) no lleva ni botón ni aviso; el editado (fila 3), sí.
    await expect(page.locator('[data-restaurar]:visible')).toHaveCount(1);
    await expect(filaDe(page, 3).getByRole('button', { name: /^Restaurar/ })).toBeVisible();
    await expect(page.locator('[data-aviso-posicion]:visible')).toHaveCount(1);
    await expect(filaDe(page, 3).getByText('esta es la macro 2.')).toBeVisible();
    await expect(filaDe(page, 2).getByText(/toma las columnas por su orden/)).toBeHidden();
    await expect(filaDe(page, 4).getByRole('button', { name: /^Restaurar/ })).toBeHidden();
  });

  for (const ancho of [1280, 360]) {
    test(`bajo el nombre va, en orden, el campo, la etiqueta, «Restaurar» y su aviso, a ${ancho} px`, async ({ page }) => {
      await page.setViewportSize({ width: ancho, height: 900 });
      const api = conPlataforma();
      const d = definicionDeLaPlataforma(['destino', '[$VAR1$]', 'Nombres del titular']);
      d.versiones[0].contenido.columnas[2].etiqueta = 'Nombres';
      api.definiciones.push(d);
      await abrir(page, api);
      await page.getByLabel('Definición guardada').selectOption('1');
      await expect(nombreDeColumna(page, 3)).toHaveValue('Nombres del titular');

      const orden = await filaDe(page, 3)
        .locator('td[data-etiqueta]')
        .nth(1)
        .evaluate((celda) =>
          [...celda.children]
            .filter((hijo) => (hijo as HTMLElement).offsetParent !== null && (hijo.matches('input') || (hijo.textContent ?? '').trim() !== ''))
            .map((hijo) =>
              hijo.matches('input')
                ? 'campo'
                : hijo.matches('[data-linea-etiqueta]')
                  ? 'etiqueta'
                  : hijo.matches('[data-restaurar]')
                    ? 'restaurar'
                    : hijo.matches('[data-aviso-posicion]')
                      ? 'aviso'
                      : 'otro',
            ),
        );
      expect(orden).toEqual(['campo', 'etiqueta', 'restaurar', 'aviso']);
    });
  }

  test('quitar una columna renumera las de abajo', async ({ page }) => {
    await nuevaConPlataforma(page);
    await page.getByRole('button', { name: 'Quitar [$VAR1$]' }).click();
    await expect(nombreDeColumna(page, 2)).toHaveValue('[$VAR1$]');
    await expect(nombreDeColumna(page, 3)).toHaveCount(0);
  });

  test('guardar manda las columnas en su orden con sus encabezados', async ({ page }) => {
    const api = await nuevaConPlataforma(page);
    await page.getByLabel('Nombre', { exact: true }).fill('Con macros');
    await page.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByText('Guardada como versión 1.')).toBeVisible();
    const cuerpo = pedidosA(api, 'POST', '/definiciones-columnas')[0].cuerpo as { columnas: Array<{ nombre: string; orden: number }> };
    expect(cuerpo.columnas.map((c) => [c.orden, c.nombre])).toEqual([
      [0, 'destino'],
      [1, '[$VAR1$]'],
      [2, '[$VAR2$]'],
    ]);
  });
});

test.describe('los problemas de la plataforma', () => {
  test('van bajo su columna y en el resumen, con el texto de su código, y no dejan guardar', async ({ page }) => {
    const api = conPlataforma();
    // Le falta la columna fija «destino».
    api.definiciones.push(definicionDeLaPlataforma(['telefono', 'mensaje']));
    await abrir(page, api);
    await page.getByLabel('Definición guardada').selectOption('1');
    await expect(nombreDeColumna(page, 1)).toHaveValue('telefono');

    const texto = 'Falta la columna fija «destino» de la plataforma. Agrégala en su posición.';
    await expect(page.locator('[data-resumen]')).toContainText(texto);
    await expect(filaDe(page, 1).getByText(texto)).toBeVisible();
    // Sin su fija, ninguna fila es fija: la definición se puede arreglar.
    await expect(page.getByRole('img', { name: 'Columna fija', exact: true })).toHaveCount(0);

    await nombreDeColumna(page, 2).fill('mensaje 2');
    await page.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.locator('[data-resumen]')).toContainText(texto);
    await expect(page.locator('[data-resumen]')).toHaveAttribute('role', 'alert');
    expect(api.definiciones[0].versiones).toHaveLength(1);
  });

  test('una fija con otro tipo se marca bajo ella', async ({ page }) => {
    const api = conPlataforma();
    const d = definicionDeLaPlataforma(['destino', '[$VAR1$]']);
    d.versiones[0].contenido.columnas[0].tipo = 'numero';
    api.definiciones.push(d);
    await abrir(page, api);
    await page.getByLabel('Definición guardada').selectOption('1');
    await expect(filaDe(page, 1).getByText('La columna fija «destino» debe ser del tipo que fija la plataforma. Cámbiale el tipo.')).toBeVisible();
    // Una fija de otro tipo sigue siendo fija en pantalla: el tipo no se cambia desde ahí.
    await expect(page.getByLabel('Tipo de destino')).toBeDisabled();
  });

  test('una plataforma que ya no existe se lee y se marca arriba, sin tapar las columnas', async ({ page }) => {
    const api = conPlataforma();
    api.definiciones.push(definicionDeLaPlataforma(['telefono', 'mensaje'], { plataforma: 'borrada' }));
    await abrir(page, api);
    await page.getByLabel('Definición guardada').selectOption('1');

    await expect(nombreDeColumna(page, 1)).toHaveValue('telefono');
    await expect(page.locator('[data-plataforma-tag="borrada"]')).toHaveText('Plataforma desconocida: borrada');
    await expect(page.locator('[data-resumen]')).toContainText('La plataforma «borrada» ya no está disponible o nunca lo estuvo.');
    await expect(page.locator('[data-reglas]')).toBeHidden();
  });

  test('una definición válida de la plataforma no trae problemas y no pide nada por guardar', async ({ page }) => {
    const api = conPlataforma();
    api.definiciones.push(definicionDeLaPlataforma(['destino', '[$VAR1$]']));
    await abrir(page, api);
    await page.getByLabel('Definición guardada').selectOption('1');
    await expect(page.locator('[data-resumen]')).toBeHidden();
    await expect(page.getByRole('img', { name: 'Columna fija', exact: true })).toBeVisible();
    await expect(page.locator('[data-plataforma-tag="sintetica"]')).toHaveText('Sintética');
    await expect(page.getByRole('button', { name: 'Guardar' })).toBeDisabled();
  });
});

// ---- Accessibility: a platform definition with its lock, an edited header and the label field open ---------------

async function sinViolaciones(page: Page): Promise<void> {
  await expect(page.locator('[data-previa]')).toHaveAttribute('data-calculando', 'false');
  const resultado = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(resultado.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
}

test.describe('accesibilidad de una definición con plataforma', () => {
  test.use({ reducedMotion: 'reduce' });

  for (const tema of ['light', 'dark'] as const) {
    test(`tema ${tema === 'light' ? 'claro' : 'oscuro'}: el candado, el encabezado editado y la fila abierta`, async ({ page }) => {
      await page.addInitScript((elegido) => {
        localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
      }, tema);
      await nuevaConPlataforma(page);
      await nombreDeColumna(page, 2).fill('Nombres del titular');
      await page.getByRole('button', { name: 'Editar destino' }).click();
      await expect(page.getByLabel('Etiqueta', { exact: true })).toBeVisible();
      await sinViolaciones(page);
    });
  }

  test('a 360 px el candado dice «Columna fija» y la tabla se apila', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 640 });
    await nuevaConPlataforma(page);
    await nombreDeColumna(page, 2).fill('Nombres del titular');
    await expect(filaDe(page, 1).getByText('Columna fija', { exact: true })).toBeVisible();
    await sinViolaciones(page);
  });

  test('con problemas de la plataforma a la vista', async ({ page }) => {
    const api = conPlataforma();
    api.definiciones.push(definicionDeLaPlataforma(['telefono', 'mensaje']));
    await abrir(page, api);
    await page.getByLabel('Definición guardada').selectOption('1');
    await expect(page.locator('[data-resumen]')).toBeVisible();
    await sinViolaciones(page);
  });
});
