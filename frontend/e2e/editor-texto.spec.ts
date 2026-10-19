/**
 * EditorTexto and VariantesSegmento on their own, through the test-only page
 * `/pruebas/editor-texto` (it exists only in Playwright's build, see
 * astro.config.mjs). Covers the minimum of docs/motor-texto-enriquecido-interfaz.md
 * §7 for the shared components, the keyboard table of §2.4 and axe in the
 * states where problems hide.
 *
 * The engine is the synthetic fake: every value is invented.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import type { components } from '../src/lib/contrato-api';
import { apiVacia, montarApi } from './api-falsa';
import {
  apiTextoEnriquecidoVacia,
  catalogoSintetico,
  manejarTextoEnriquecido,
  type ApiFalsaTextoEnriquecido,
} from './api-falsa-texto-enriquecido';

type Esquemas = components['schemas'];
type Problema = Esquemas['ProblemaTextoRespuesta'];

test.use({ reducedMotion: 'reduce' });

const SPEECH = {
  nodos: [
    { tipo: 'texto', valor: 'Hola ' },
    { tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'primeros', args: [8] }] },
    { tipo: 'texto', valor: ', vence el ' },
    { tipo: 'variable', nombre: 'fecha_vencimiento_cuota', funciones: [{ nombre: 'formato_fecha', args: ['dd/mm/aaaa'] }] },
    { tipo: 'texto', valor: '.' },
  ],
};

function problema(codigo: Problema['codigo'], ubicacion: Problema['ubicacion'], cambios: Partial<Problema> = {}): Problema {
  return { codigo, detalle: codigo, ubicacion, nombre: null, columna: null, segmento: null, campo: null, ...cambios };
}

interface Caso {
  componente?: 'editor' | 'variantes';
  expresion?: unknown;
  variantes?: unknown;
  extra?: string;
  ajustar?: (motor: ApiFalsaTextoEnriquecido) => void;
}

async function abrir(page: Page, caso: Caso = {}) {
  const motor = apiTextoEnriquecidoVacia();
  caso.ajustar?.(motor);
  const api = apiVacia();
  api.manejadores = [manejarTextoEnriquecido(motor)];
  await montarApi(page, api);
  const query = new URLSearchParams({ componente: caso.componente ?? 'editor' });
  if (caso.expresion) query.set('expresion', JSON.stringify(caso.expresion));
  if (caso.variantes) query.set('variantes', JSON.stringify(caso.variantes));
  await page.goto(`/pruebas/editor-texto?${query}${caso.extra ?? ''}`);
  await expect(page.locator('body')).toHaveAttribute('data-montado', 'true');
  return { motor, api };
}

const editor = (page: Page) => page.locator('#editor-prueba');
const resultado = (page: Page) => editor(page).locator('[data-resultado]');
const pieza = (page: Page, nombre: RegExp) => editor(page).getByRole('button', { name: nombre });

function ultimaValidacion(motor: ApiFalsaTextoEnriquecido) {
  const pedidos = motor.pedidos.filter((p) => p.ruta === '/texto-enriquecido/validacion');
  return (pedidos.at(-1)?.cuerpo as { expresion: unknown } | undefined)?.expresion;
}

test.describe('armar un texto', () => {
  test('arma un speech sin teclear sintaxis', async ({ page }) => {
    const { motor } = await abrir(page);
    const linea = editor(page).getByRole('group', { name: 'Texto del mensaje' });

    await linea.getByRole('textbox', { name: 'Texto' }).fill('Hola ');
    await editor(page).getByRole('button', { name: 'Variable', exact: true }).click();
    await editor(page).getByRole('searchbox', { name: 'Buscar una variable' }).fill('titu');
    await editor(page).getByRole('button', { name: /^Titular/ }).click();

    // The piece opens with the focus on «Agregar función».
    const agregar = editor(page).getByRole('combobox', { name: 'Agregar función' });
    await expect(agregar).toBeFocused();
    await agregar.selectOption({ label: 'Primeros caracteres' });
    const cantidad = editor(page).getByRole('textbox', { name: 'Cantidad de caracteres' });
    await expect(cantidad).toBeFocused();
    await cantidad.fill('8');

    await linea.getByRole('textbox', { name: 'Texto al final' }).fill(', paga.');

    await expect(resultado(page)).toHaveText('Hola NOMBRE S, paga.');
    await expect.poll(() => ultimaValidacion(motor)).toEqual({
      nodos: [
        { tipo: 'texto', valor: 'Hola ' },
        { tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'primeros', args: [8] }] },
        { tipo: 'texto', valor: ', paga.' },
      ],
    });
    await expect(pieza(page, /^Variable Titular/)).toHaveText('Titular · primeros caracteres 8');
    // No syntax anywhere on screen.
    await expect(editor(page)).not.toContainText('[@');
    await expect(editor(page)).not.toContainText('|');
  });

  test('inserta la variable en la posición del cursor', async ({ page }) => {
    const { motor } = await abrir(page, { expresion: { nodos: [{ tipo: 'texto', valor: 'Hola, paga.' }] } });
    const tramo = editor(page).getByRole('textbox', { name: 'Texto' });
    await tramo.click();
    await tramo.evaluate((area: HTMLTextAreaElement) => {
      area.setSelectionRange(4, 4);
      area.dispatchEvent(new Event('select'));
    });
    await editor(page).getByRole('button', { name: 'Variable', exact: true }).click();
    await editor(page).getByRole('button', { name: /^Titular/ }).click();

    await expect.poll(() => ultimaValidacion(motor)).toEqual({
      nodos: [
        { tipo: 'texto', valor: 'Hola' },
        { tipo: 'variable', nombre: 'titular', funciones: [] },
        { tipo: 'texto', valor: ', paga.' },
      ],
    });
  });

  test('agrega, reordena y quita funciones', async ({ page }) => {
    const { motor } = await abrir(page, {
      expresion: { nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'primeros', args: [8] }] }] },
    });
    await pieza(page, /^Variable Titular/).click();
    await editor(page).getByRole('combobox', { name: 'Agregar función' }).selectOption({ label: 'Mayúsculas' });

    await editor(page).getByRole('button', { name: 'Bajar Primeros caracteres' }).click();
    // The moved function is now the last one: the focus stays on its row.
    await expect(editor(page).getByRole('button', { name: 'Subir Primeros caracteres' })).toBeFocused();
    await expect.poll(() => ultimaValidacion(motor)).toEqual({
      nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'mayusculas', args: [] }, { nombre: 'primeros', args: [8] }] }],
    });

    await editor(page).getByRole('button', { name: 'Quitar Mayúsculas' }).click();
    await expect(pieza(page, /^Variable Titular/)).toHaveText('Titular · primeros caracteres 8');
    await expect.poll(() => ultimaValidacion(motor)).toEqual({
      nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'primeros', args: [8] }] }],
    });
  });

  test('solo ofrece las funciones que aceptan el tipo que llega', async ({ page }) => {
    await abrir(page, {
      expresion: { nodos: [{ tipo: 'variable', nombre: 'fecha_vencimiento_cuota', funciones: [] }] },
    });
    await pieza(page, /^Variable Vencimiento/).click();
    const agregar = editor(page).getByRole('combobox', { name: 'Agregar función' });
    const opciones = await agregar.locator('option').allTextContents();
    expect(opciones).toContain('Formato de fecha');
    expect(opciones).not.toContain('Mayúsculas');
  });

  test('el patrón de fecha se elige con ejemplos y uno propio se arma con marcas', async ({ page }) => {
    const { motor } = await abrir(page, { expresion: SPEECH });
    await pieza(page, /^Variable Vencimiento/).click();
    const formato = editor(page).getByRole('combobox', { name: 'Formato', exact: true });
    await expect(formato.locator('option:checked')).toHaveText('dd/mm/aaaa — 05/10/2026');

    await formato.selectOption({ label: 'Personalizado' });
    const propio = editor(page).getByRole('textbox', { name: 'Formato personalizado' });
    await expect(propio).toBeFocused();
    await editor(page).getByRole('button', { name: /^Día \(dd\)/ }).click();
    await propio.press('End');
    await propio.pressSequentially(' de ');
    await editor(page).getByRole('button', { name: /^Nombre del mes/ }).click();

    await expect.poll(() => JSON.stringify(ultimaValidacion(motor))).toContain('"args":["dd de nombre_mes"]');
  });
});

test.describe('errores en su lugar', () => {
  const conProblema = (motor: ApiFalsaTextoEnriquecido) => {
    motor.validacion = () => ({
      problemas: [problema('parametro_invalido', { nodo: 1, funcion: 0, parametro: 'n' })],
      tipo: 'texto',
      cota: null,
      sin_cota: null,
      variables: ['titular'],
    });
  };

  test('un parámetro inválido se marca en su campo y el resumen lleva a él', async ({ page }) => {
    await abrir(page, { expresion: SPEECH, ajustar: conProblema });
    const resumen = editor(page).locator('[data-resumen]');
    await expect(resumen).toBeVisible();
    await expect(resumen).toContainText('Hay 1 problema en el texto.');
    await expect(resumen).not.toHaveAttribute('role', 'alert');
    await expect(pieza(page, /^Variable Titular/)).toHaveAccessibleName(/con un problema/);

    await resumen.getByRole('button', { name: 'Ir al problema' }).click();
    const campo = editor(page).getByRole('textbox', { name: 'Cantidad de caracteres' });
    await expect(campo).toBeFocused();
    await expect(campo).toHaveAttribute('aria-invalid', 'true');
    await expect(campo).toHaveAccessibleDescription(/Un valor de la función no es válido/);
  });

  test('guardar con problemas no guarda y lleva el foco al primero', async ({ page }) => {
    await abrir(page, { expresion: SPEECH, ajustar: conProblema });
    await expect(editor(page).locator('[data-resumen]')).toBeVisible();

    await page.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.locator('[data-guardado]')).toHaveText('no guardado');
    await expect(editor(page).locator('[data-resumen]')).toHaveAttribute('role', 'alert');
    await expect(editor(page).getByRole('textbox', { name: 'Cantidad de caracteres' })).toBeFocused();
  });

  test('sin problemas, guardar se permite', async ({ page }) => {
    await abrir(page, { expresion: SPEECH });
    await expect(resultado(page)).toContainText('Hola NOMBRE S');
    await page.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.locator('[data-guardado]')).toHaveText('guardado');
  });

  test('un problema de un tramo se nombra por su posición', async ({ page }) => {
    await abrir(page, {
      expresion: SPEECH,
      ajustar: (motor) => {
        motor.validacion = () => ({
          problemas: [problema('limite_excedido', { nodo: 2, funcion: null, parametro: null })],
          tipo: 'texto', cota: null, sin_cota: null, variables: [],
        });
      },
    });
    const tramo = editor(page).getByRole('textbox', { name: 'Texto después de Titular' });
    await expect(tramo).toHaveAttribute('aria-invalid', 'true');
    await expect(tramo).toHaveAccessibleDescription(/Texto después de Titular: El texto es demasiado grande/);
  });
});

test.describe('vista previa', () => {
  test('resalta la parte de la pieza enfocada y marca el dato vacío', async ({ page }) => {
    await abrir(page, {
      expresion: SPEECH,
      ajustar: (motor) => {
        delete motor.catalogos['mowa_mes.speech'].contexto.ejemplo.fecha_vencimiento_cuota;
      },
    });
    await expect(resultado(page)).toContainText('Hola NOMBRE S');
    await pieza(page, /^Variable Titular/).focus();
    await expect(resultado(page).locator('.editor-texto__parte--resaltada')).toHaveText('NOMBRE S');
    await expect(resultado(page).getByRole('img', { name: 'vacío' })).toBeVisible();
  });

  test('el largo excedido se dice con su nivel y se anuncia una vez', async ({ page }) => {
    let cota = 120;
    await abrir(page, {
      expresion: SPEECH,
      ajustar: (motor) => {
        motor.validacion = () => ({ problemas: [], tipo: 'texto', cota, sin_cota: null, variables: [] });
      },
    });
    const largo = editor(page).locator('.editor-texto__largo');
    await expect(largo).toContainText('máximo posible 120 de 160');
    await expect(largo.locator('.tag')).toHaveText('Dentro del límite');

    cota = 170;
    await editor(page).getByRole('textbox', { name: 'Texto al final' }).fill('. Gracias.');
    await expect(largo).toContainText('máximo posible 170 de 160');
    await expect(largo.locator('.tag')).toHaveText('Excede el límite');
    await expect(largo.locator('.tag')).toHaveClass(/tag--error/);
    await expect(editor(page).locator('[data-largo-anuncio]')).toHaveText('Excede el límite');
  });

  test('un pagaré que no existe se dice bajo su campo y la vista anterior se queda', async ({ page }) => {
    await abrir(page, { expresion: SPEECH });
    await expect(resultado(page)).toContainText('Hola NOMBRE S');
    await editor(page).getByRole('button', { name: 'Producto real' }).click();
    await editor(page).getByLabel('Fecha de corte').fill('2026-10-05');
    await editor(page).getByLabel('Pagaré').fill('000000000');

    const pagare = editor(page).getByLabel('Pagaré');
    await expect(pagare).toHaveAttribute('aria-invalid', 'true');
    await expect(pagare).toHaveAccessibleDescription(/No hay un producto con ese pagaré/);
    await expect(resultado(page)).toContainText('Hola NOMBRE S');
  });
});

test.describe('teclado (§2.4)', () => {
  test('Tab recorre tramos y piezas en el orden de lectura', async ({ page }) => {
    await abrir(page, { expresion: SPEECH });
    await editor(page).getByRole('textbox', { name: 'Texto al inicio' }).focus();
    const orden = [/^Variable Titular/, 'Texto después de Titular', /^Variable Vencimiento/, 'Texto al final'];
    for (const nombre of orden) {
      await page.keyboard.press('Tab');
      await expect(page.locator(':focus')).toHaveAccessibleName(nombre);
    }
  });

  test('Enter abre y cierra el panel; Escape lo cierra y devuelve el foco', async ({ page }) => {
    await abrir(page, { expresion: SPEECH });
    const titular = pieza(page, /^Variable Titular/);
    await titular.focus();
    await page.keyboard.press('Enter');
    await expect(titular).toHaveAttribute('aria-expanded', 'true');
    await page.keyboard.press('Space');
    await expect(titular).toHaveAttribute('aria-expanded', 'false');

    await page.keyboard.press('Enter');
    await editor(page).getByRole('textbox', { name: 'Cantidad de caracteres' }).focus();
    await page.keyboard.press('Escape');
    await expect(titular).toHaveAttribute('aria-expanded', 'false');
    await expect(titular).toBeFocused();
  });

  test('Supr o Retroceso en una pieza la quita y el foco queda en la unión', async ({ page }) => {
    const { motor } = await abrir(page, { expresion: SPEECH });
    await pieza(page, /^Variable Titular/).focus();
    await page.keyboard.press('Delete');
    const unido = editor(page).getByRole('textbox', { name: 'Texto al inicio' });
    await expect(unido).toBeFocused();
    await expect(unido).toHaveValue('Hola , vence el ');
    expect(await unido.evaluate((a: HTMLTextAreaElement) => a.selectionStart)).toBe(5);

    await pieza(page, /^Variable Vencimiento/).focus();
    await page.keyboard.press('Backspace');
    await expect.poll(() => ultimaValidacion(motor)).toEqual({ nodos: [{ tipo: 'texto', valor: 'Hola , vence el .' }] });
  });

  test('Retroceso al inicio y Supr al final de un tramo mueven el foco sin borrar', async ({ page }) => {
    await abrir(page, { expresion: SPEECH });
    const medio = editor(page).getByRole('textbox', { name: 'Texto después de Titular' });
    await medio.focus();
    await medio.evaluate((a: HTMLTextAreaElement) => a.setSelectionRange(0, 0));
    await page.keyboard.press('Backspace');
    await expect(pieza(page, /^Variable Titular/)).toBeFocused();
    await expect(medio).toHaveValue(', vence el ');

    await medio.focus();
    await medio.evaluate((a: HTMLTextAreaElement) => a.setSelectionRange(a.value.length, a.value.length));
    await page.keyboard.press('Delete');
    await expect(pieza(page, /^Variable Vencimiento/)).toBeFocused();
    await expect(medio).toHaveValue(', vence el ');
  });

  test('Escape en el selector de variables lo cierra y vuelve a + Variable', async ({ page }) => {
    await abrir(page);
    const agregar = editor(page).getByRole('button', { name: 'Variable', exact: true });
    await agregar.click();
    await expect(editor(page).getByRole('searchbox', { name: 'Buscar una variable' })).toBeFocused();
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Escape');
    await expect(editor(page).getByRole('searchbox')).toHaveCount(0);
    await expect(agregar).toBeFocused();
    await expect(agregar).toHaveAttribute('aria-expanded', 'false');
  });
});

test('una versión de solo lectura no se puede editar', async ({ page }) => {
  await abrir(page, { expresion: SPEECH, extra: '&soloLectura=1' });
  await expect(editor(page).getByRole('textbox', { name: 'Texto al inicio' })).not.toBeEditable();
  await expect(editor(page).getByRole('button', { name: 'Variable', exact: true })).toBeDisabled();
  await pieza(page, /^Variable Titular/).click();
  await expect(editor(page).getByRole('button', { name: 'Quitar variable' })).toBeDisabled();
});

test.describe('variantes por segmento', () => {
  const variantes = [
    { segmento: '1_a_8', expresion: { nodos: [{ tipo: 'texto', valor: 'Recuerda tu cuota.' }] } },
  ];
  const variantesRaiz = (page: Page) => page.locator('#variantes-prueba');

  test('cada segmento muestra su estado y copiar trae el contenido de otro', async ({ page }) => {
    await abrir(page, {
      componente: 'variantes',
      expresion: { nodos: [{ tipo: 'texto', valor: 'Texto general.' }] },
      variantes,
      extra: '&defecto=1',
    });
    const raiz = variantesRaiz(page);
    const lista = raiz.locator('[data-segmento-botones]');
    await expect(lista.getByRole('button', { name: /^1 a 8/ })).toContainText('Propio');
    await expect(lista.getByRole('button', { name: /^9 a 30/ })).toContainText('Usa el por defecto');

    // The first segment is on screen, with its own content.
    await expect(raiz.getByRole('group', { name: 'Speech de Preventiva' })).toBeVisible();
    await lista.getByRole('button', { name: /^9 a 30/ }).click();
    await expect(raiz.getByRole('group', { name: 'Speech de 9 a 30' })).toBeVisible();
    await expect(raiz.getByRole('textbox', { name: 'Texto' })).toHaveValue('Texto general.');

    await raiz.getByLabel('Copiar de otro segmento').selectOption({ label: '1 a 8' });
    await raiz.getByRole('button', { name: 'Copiar' }).click();
    await expect(raiz.getByRole('textbox', { name: 'Texto' })).toHaveValue('Recuerda tu cuota.');
    await expect(lista.getByRole('button', { name: /^9 a 30/ })).toContainText('Propio');

    const evento = JSON.parse((await page.locator('[data-ultimo-evento]').textContent()) ?? '{}');
    expect(evento.variantes.map((v: { segmento: string }) => v.segmento).sort()).toEqual(['1_a_8', '9_a_30']);
    expect(evento.origen).toBe('usuario');
  });

  test('editar un segmento que usa el por defecto le da contenido propio', async ({ page }) => {
    await abrir(page, { componente: 'variantes', expresion: { nodos: [{ tipo: 'texto', valor: 'General.' }] }, extra: '&defecto=1' });
    const raiz = variantesRaiz(page);
    await raiz.locator('[data-segmento-botones]').getByRole('button', { name: /^1 a 8/ }).click();
    await raiz.getByRole('textbox', { name: 'Texto' }).fill('Solo para 1 a 8.');
    await expect(raiz.locator('[data-segmento-botones]').getByRole('button', { name: /^1 a 8/ })).toContainText('Propio');

    await raiz.getByRole('button', { name: 'Usar el contenido por defecto' }).click();
    await expect(raiz.getByRole('textbox', { name: 'Texto' })).toHaveValue('General.');
    await expect(raiz.locator('[data-segmento-botones]').getByRole('button', { name: /^1 a 8/ })).toContainText('Usa el por defecto');
  });

  test('con controlMuestra: false el editor de adentro no muestra su control y la página fija la muestra', async ({ page }) => {
    const { motor } = await abrir(page, { componente: 'variantes', variantes, extra: '&muestra=0' });
    await expect(variantesRaiz(page).getByRole('button', { name: 'Registro de ejemplo' })).toBeHidden();
    await expect(variantesRaiz(page).locator('[data-resultado]')).not.toHaveClass(/pendiente/);

    await llamarEditor(page, 'fijarMuestra', { tipo: 'producto_real', fecha_corte: '2026-10-05', pagare: '000000001', cantidad: 1 });
    await expect
      .poll(() => motor.pedidos.filter((p) => p.ruta === '/texto-enriquecido/previsualizacion').at(-1)?.cuerpo)
      .toMatchObject({ muestra: { tipo: 'producto_real', pagare: '000000001' } });
  });

  test('a 360 px la lista pasa a un select', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 740 });
    await abrir(page, { componente: 'variantes', variantes });
    const raiz = variantesRaiz(page);
    await expect(raiz.locator('[data-segmento-botones]')).toBeHidden();
    await raiz.getByRole('combobox', { name: 'Segmento', exact: true }).selectOption({ label: '1 a 8 — Propio' });
    await expect(raiz.getByRole('textbox', { name: 'Texto' })).toHaveValue('Recuerda tu cuota.');
  });
});

// ---- Mounting and unmounting (rows of the column builder, §9.2) ------------------------------

/** Calls a method of the controller the test page leaves on `window`. */
async function llamar(page: Page, metodo: string, ...args: unknown[]): Promise<void> {
  await page.evaluate(
    ([m, a]) => {
      const controlador = (window as unknown as { controladorPrueba: Record<string, (...x: unknown[]) => void> })
        .controladorPrueba;
      controlador[m as string](...(a as unknown[]));
    },
    [metodo, args] as const,
  );
}

/** The same, on the editor inside VariantesSegmento (`controlador.editor`). */
async function llamarEditor(page: Page, metodo: string, ...args: unknown[]): Promise<void> {
  await page.evaluate(
    ([m, a]) => {
      const controlador = (window as unknown as { controladorPrueba: { editor: Record<string, (...x: unknown[]) => void> } })
        .controladorPrueba;
      controlador.editor[m as string](...(a as unknown[]));
    },
    [metodo, args] as const,
  );
}

const validaciones = (motor: ApiFalsaTextoEnriquecido) =>
  motor.pedidos.filter((p) => p.ruta === '/texto-enriquecido/validacion').length;

test.describe('nota sobre la muestra', () => {
  test('la página la fija bajo la vista previa, se anuncia una vez y se quita con null', async ({ page }) => {
    await abrir(page, { expresion: SPEECH });
    await expect(resultado(page)).toContainText('Hola NOMBRE S');
    const nota = editor(page).locator('[data-resultado] + [data-nota-muestra]');
    await expect(nota).toBeHidden();

    await llamar(page, 'fijarNotaMuestra', 'Nota sintética sobre la muestra.');
    await expect(nota).toBeVisible();
    await expect(nota).toHaveText('Nota sintética sobre la muestra.');
    await expect(editor(page).locator('[data-nota-anuncio]')).toHaveText('Nota sintética sobre la muestra.');

    // The same note again is not said again.
    await editor(page).locator('[data-nota-anuncio]').evaluate((e) => (e.textContent = ''));
    await llamar(page, 'fijarNotaMuestra', 'Nota sintética sobre la muestra.');
    await expect(editor(page).locator('[data-nota-anuncio]')).toHaveText('');

    await llamar(page, 'fijarNotaMuestra', null);
    await expect(nota).toBeHidden();
  });

  test('en las variantes se llega por su editor y queda junto a su vista previa', async ({ page }) => {
    await abrir(page, {
      componente: 'variantes',
      variantes: [{ segmento: '1_a_8', expresion: { nodos: [{ tipo: 'texto', valor: 'Recuerda tu cuota.' }] } }],
      extra: '&muestra=0',
    });
    await llamarEditor(page, 'fijarNotaMuestra', 'Ningún producto sintético cae en «1 a 8».');
    await expect(page.locator('#variantes-prueba [data-resultado] + [data-nota-muestra]')).toHaveText(
      'Ningún producto sintético cae en «1 a 8».',
    );
  });
});

test.describe('montar y desmontar', () => {
  test('el cambio de idioma repinta un editor montado', async ({ page }) => {
    await abrir(page, { expresion: SPEECH });
    await expect(resultado(page)).toContainText('Hola NOMBRE S');
    await page.locator('[data-lang="en"]').click();
    await expect(editor(page).getByRole('button', { name: /^Variable Account holder/ })).toHaveAccessibleName(/Opens its functions/);
  });

  test('destruir: ni el idioma, ni teclear, ni la espera pendiente hacen nada', async ({ page }) => {
    const errores: string[] = [];
    page.on('pageerror', (error) => errores.push(error.message));
    const { motor } = await abrir(page, { expresion: SPEECH });
    await expect(resultado(page)).toContainText('Hola NOMBRE S');

    // A change whose validation is still waiting its 500 ms, then unmount.
    await editor(page).getByRole('textbox', { name: 'Texto al final' }).fill('. Pendiente.');
    const eventos = await page.locator('body').getAttribute('data-eventos');
    const antes = validaciones(motor);
    await llamar(page, 'destruir');
    await page.locator('[data-lang="en"]').click();
    await editor(page).getByRole('textbox', { name: 'Texto al final' }).fill('. Después.');
    await page.waitForTimeout(800);

    expect(validaciones(motor)).toBe(antes);
    await expect(page.locator('body')).toHaveAttribute('data-eventos', eventos!);
    // The pill was not repainted in English: no listener was left behind.
    await expect(pieza(page, /^Variable Titular/)).toHaveAccessibleName(/Abre sus funciones/);
    expect(errores).toEqual([]);
  });

  test('destruir las variantes destruye también su editor', async ({ page }) => {
    const errores: string[] = [];
    page.on('pageerror', (error) => errores.push(error.message));
    const { motor } = await abrir(page, {
      componente: 'variantes',
      variantes: [{ segmento: '1_a_8', expresion: { nodos: [{ tipo: 'texto', valor: 'Recuerda tu cuota.' }] } }],
    });
    const lista = page.locator('#variantes-prueba [data-segmento-botones]');
    await expect(lista.getByRole('button', { name: /^1 a 8/ })).toContainText('Propio');
    await expect(page.locator('#variantes-prueba [data-resultado]')).not.toHaveClass(/pendiente/);
    const eventos = await page.locator('body').getAttribute('data-eventos');
    const antes = validaciones(motor);

    await llamar(page, 'destruir');
    await page.locator('[data-lang="en"]').click();
    await page.locator('#variantes-prueba').getByRole('textbox', { name: 'Texto' }).fill('Otro.');
    await page.waitForTimeout(800);

    expect(validaciones(motor)).toBe(antes);
    await expect(page.locator('body')).toHaveAttribute('data-eventos', eventos!);
    await expect(lista.getByRole('button', { name: /^1 a 8/ })).toContainText('Propio');
    expect(errores).toEqual([]);
  });
});

test.describe('variantes sin remontar', () => {
  const variantes = [{ segmento: '1_a_8', expresion: { nodos: [{ tipo: 'texto', valor: 'Recuerda tu cuota.' }] } }];
  const raiz = (page: Page) => page.locator('#variantes-prueba');
  const lista = (page: Page) => raiz(page).locator('[data-segmento-botones]');
  const dosSegmentos = catalogoSintetico().contexto.segmentos.slice(0, 2);

  test('fijarSegmentos conserva el segmento elegido si sigue existiendo', async ({ page }) => {
    await abrir(page, { componente: 'variantes', variantes });
    await lista(page).getByRole('button', { name: /^1 a 8/ }).click();
    await raiz(page).getByRole('textbox', { name: 'Texto' }).focus();

    await llamar(page, 'fijarSegmentos', dosSegmentos);
    await expect(lista(page).getByRole('button')).toHaveCount(2);
    await expect(lista(page).getByRole('button', { name: /^1 a 8/ })).toHaveAttribute('aria-pressed', 'true');
    await expect(raiz(page).getByRole('textbox', { name: 'Texto' })).toHaveValue('Recuerda tu cuota.');
    await expect(raiz(page).getByRole('textbox', { name: 'Texto' })).toBeFocused();
  });

  test('fijarSegmentos elige el primero si el elegido ya no existe', async ({ page }) => {
    await abrir(page, { componente: 'variantes', variantes });
    await lista(page).getByRole('button', { name: /^9 a 30/ }).click();
    await llamar(page, 'fijarSegmentos', dosSegmentos);
    await expect(lista(page).getByRole('button', { name: /^Preventiva/ })).toHaveAttribute('aria-pressed', 'true');
    await expect(raiz(page).getByRole('group', { name: 'Speech de Preventiva' })).toBeVisible();
  });

  test('el foco sigue en su segmento mientras llegan las validaciones de todos', async ({ page }) => {
    const { motor } = await abrir(page, {
      componente: 'variantes',
      variantes: [
        ...variantes,
        { segmento: '9_a_30', expresion: { nodos: [{ tipo: 'texto', valor: 'Otro texto.' }] } },
      ],
    });
    const boton = lista(page).getByRole('button', { name: /^1 a 8/ });
    await expect(boton).toContainText('Propio');
    await boton.focus();
    await boton.evaluate((b) => b.setAttribute('data-mismo-nodo', ''));
    const antes = validaciones(motor);

    // New content for every segment: each one is validated again, and each answer repaints the list.
    await llamar(page, 'fijarVariantes', {
      porDefecto: null,
      variantes: [
        { segmento: '1_a_8', expresion: { nodos: [{ tipo: 'texto', valor: 'Cambiado.' }] } },
        { segmento: '9_a_30', expresion: { nodos: [{ tipo: 'texto', valor: 'Cambiado también.' }] } },
      ],
    });
    await expect.poll(() => validaciones(motor)).toBeGreaterThanOrEqual(antes + 2);
    await expect(raiz(page).locator('[data-resultado]')).not.toHaveClass(/pendiente/);

    await expect(lista(page).locator('[data-mismo-nodo]')).toBeFocused();
    await expect(boton).toBeFocused();
  });

  test('si cambian los segmentos, el foco vuelve al mismo segmento', async ({ page }) => {
    await abrir(page, { componente: 'variantes', variantes });
    const boton = lista(page).getByRole('button', { name: /^1 a 8/ });
    await boton.focus();
    await llamar(page, 'fijarSegmentos', dosSegmentos);
    await expect(lista(page).getByRole('button')).toHaveCount(2);
    await expect(lista(page).getByRole('button', { name: /^1 a 8/ })).toBeFocused();
  });

  test('fijarSoloLectura(false) habilita la edición sin perder el segmento («Usar como base»)', async ({ page }) => {
    await abrir(page, { componente: 'variantes', variantes, extra: '&soloLectura=1' });
    await lista(page).getByRole('button', { name: /^9 a 30/ }).click();
    const texto = raiz(page).getByRole('textbox', { name: 'Texto' });
    await expect(texto).not.toBeEditable();
    await expect(raiz(page).getByRole('button', { name: 'Copiar' })).toBeDisabled();

    await llamar(page, 'fijarSoloLectura', false);
    await expect(texto).toBeEditable();
    await expect(lista(page).getByRole('button', { name: /^9 a 30/ })).toHaveAttribute('aria-pressed', 'true');
    await texto.fill('Solo para 9 a 30.');
    await expect(lista(page).getByRole('button', { name: /^9 a 30/ })).toContainText('Propio');
  });
});

test.describe('variable directa (§5.3)', () => {
  test('se elige de un select y su cadena se arma en el mismo panel', async ({ page }) => {
    const { motor } = await abrir(page, { extra: '&soloVariable=1' });
    await expect(editor(page).getByRole('group', { name: 'Texto del mensaje' })).toBeHidden();
    await expect(editor(page).getByRole('button', { name: 'Variable', exact: true })).toBeHidden();

    const variable = editor(page).getByRole('combobox', { name: 'Texto del mensaje' });
    await expect(variable).toHaveAccessibleDescription('Conserva el valor original, sin pasarlo por texto.');
    await variable.selectOption({ label: 'Vencimiento de la cuota (fecha)' });
    await editor(page).getByRole('combobox', { name: 'Agregar función' }).selectOption({ label: 'Sumar días' });
    await editor(page).getByRole('textbox', { name: 'Cantidad de días' }).fill('3');
    await expect.poll(() => ultimaValidacion(motor)).toEqual({
      nodos: [{ tipo: 'variable', nombre: 'fecha_vencimiento_cuota', funciones: [{ nombre: 'sumar_dias', args: [3] }] }],
    });

    // Another variable keeps the chain (the backend judges whether it still fits).
    await variable.selectOption({ label: 'Titular (texto)' });
    await expect.poll(() => ultimaValidacion(motor)).toEqual({
      nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'sumar_dias', args: [3] }] }],
    });
    // The panel never closes and has no «Quitar variable».
    await editor(page).getByRole('textbox', { name: 'Cantidad de días' }).press('Escape');
    await expect(editor(page).getByRole('textbox', { name: 'Cantidad de días' })).toBeVisible();
    await expect(editor(page).getByRole('button', { name: 'Quitar variable' })).toHaveCount(0);

    await variable.selectOption({ label: 'Elige una variable' });
    await expect.poll(() => ultimaValidacion(motor)).toEqual({ nodos: [] });
  });

  test('un texto con variables se reduce a la primera, con su cadena', async ({ page }) => {
    const { motor } = await abrir(page, { expresion: SPEECH, extra: '&soloVariable=1' });
    await expect(editor(page).getByRole('combobox', { name: 'Texto del mensaje' })).toHaveValue('titular');
    await expect(editor(page).getByRole('heading', { name: 'Titular' })).toBeVisible();
    await expect.poll(() => ultimaValidacion(motor)).toEqual({
      nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'primeros', args: [8] }] }],
    });
  });
});

// ---- axe ----------------------------------------------------------------------------------

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

async function sinViolaciones(page: Page): Promise<void> {
  const resultadoAxe = await new AxeBuilder({ page }).include('[data-ruta-prueba]').withTags(REGLAS).analyze();
  expect(resultadoAxe.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
}

for (const tema of ['light', 'dark'] as const) {
  test.describe(`axe, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((elegido) => {
        localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
      }, tema);
    });

    test('editor con una pieza abierta y un problema', async ({ page }) => {
      await abrir(page, {
        expresion: SPEECH,
        ajustar: (motor) => {
          motor.validacion = () => ({
            problemas: [problema('parametro_invalido', { nodo: 1, funcion: 0, parametro: 'n' })],
            tipo: 'texto', cota: 170, sin_cota: null, variables: [],
          });
        },
      });
      await expect(editor(page).locator('[data-resumen]')).toBeVisible();
      await pieza(page, /^Variable Titular/).click();
      await expect(editor(page).getByRole('textbox', { name: 'Cantidad de caracteres' })).toHaveAttribute('aria-invalid', 'true');
      await sinViolaciones(page);
    });

    test('editor con el selector de variables abierto', async ({ page }) => {
      await abrir(page, { expresion: SPEECH });
      await editor(page).getByRole('button', { name: 'Variable', exact: true }).click();
      await expect(editor(page).getByRole('searchbox')).toBeVisible();
      await pieza(page, /^Variable Vencimiento/).hover();
      await sinViolaciones(page);
    });

    // The chosen segment with a problem: its washed tag on the chosen row's
    // fill is where contrast broke once.
    test('variantes por segmento, la elegida con un problema', async ({ page }) => {
      await abrir(page, {
        componente: 'variantes',
        expresion: { nodos: [{ tipo: 'texto', valor: 'General.' }] },
        variantes: [{ segmento: '1_a_8', expresion: { nodos: [{ tipo: 'texto', valor: 'Propio.' }] } }],
        extra: '&defecto=1',
        ajustar: (motor) => {
          motor.validacion = () => ({
            problemas: [problema('limite_excedido', null)],
            tipo: 'texto', cota: null, sin_cota: null, variables: [],
          });
        },
      });
      const elegido = page.locator('[data-segmento-botones] [aria-pressed="true"]');
      await expect(elegido).toContainText('Con problema');
      await sinViolaciones(page);
    });

    test('variable directa con su panel', async ({ page }) => {
      await abrir(page, { expresion: SPEECH, extra: '&soloVariable=1' });
      await expect(editor(page).getByRole('heading', { name: 'Titular' })).toBeVisible();
      await expect(resultado(page)).toContainText('NOMBRE S');
      await sinViolaciones(page);
    });

    test('editor a 360 px con una pieza abierta', async ({ page }) => {
      await page.setViewportSize({ width: 360, height: 740 });
      await abrir(page, { expresion: SPEECH });
      await pieza(page, /^Variable Vencimiento/).click();
      await editor(page).getByRole('combobox', { name: 'Formato', exact: true }).selectOption({ label: 'Personalizado' });
      await sinViolaciones(page);
      const ancho = await page.evaluate(() => document.documentElement.scrollWidth);
      expect(ancho).toBeLessThanOrEqual(360);
    });
  });
}
