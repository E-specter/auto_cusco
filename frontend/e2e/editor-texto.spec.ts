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
  variablesAdicionalesSinteticas,
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
const botonFuncion = (page: Page) => editor(page).getByRole('button', { name: 'Agregar función', exact: true });
const listaFunciones = (page: Page) => editor(page).getByRole('listbox', { name: 'Agregar función' });

/** Opens the list of functions of the open piece and chooses one by its name. */
async function agregarFuncion(page: Page, nombre: RegExp): Promise<void> {
  await botonFuncion(page).click();
  await editor(page).getByRole('option', { name: nombre }).click();
}

function ultimaValidacion(motor: ApiFalsaTextoEnriquecido) {
  const pedidos = motor.pedidos.filter((p) => p.ruta === '/texto-enriquecido/validacion');
  return (pedidos.at(-1)?.cuerpo as { expresion: unknown } | undefined)?.expresion;
}

test.describe('armar un texto', () => {
  test('arma un speech sin teclear sintaxis', async ({ page }) => {
    const { motor } = await abrir(page);
    const linea = editor(page).getByRole('group', { name: 'Texto del mensaje' });

    await linea.getByRole('textbox', { name: 'Texto' }).fill('Hola ');
    await editor(page).getByRole('button', { name: 'Insertar variable', exact: true }).click();
    await page.keyboard.type('titu');
    await editor(page).getByRole('option', { name: /^Titular/ }).click();

    // The piece opens with the focus on «Agregar función».
    await expect(botonFuncion(page)).toBeFocused();
    await agregarFuncion(page, /^Primeros caracteres/);
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
    await expect(pieza(page, /^Variable Titular/)).toHaveText('Titular · primeros caracteres');
    // No syntax anywhere on screen.
    await expect(linea).not.toContainText('[@');
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
    await editor(page).getByRole('button', { name: 'Insertar variable', exact: true }).click();
    await editor(page).getByRole('option', { name: /^Titular/ }).click();

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
    await agregarFuncion(page, /^Mayúsculas/);

    await editor(page).getByRole('button', { name: 'Bajar Primeros caracteres' }).click();
    // The moved function is now the last one: the focus stays on its row.
    await expect(editor(page).getByRole('button', { name: 'Subir Primeros caracteres' })).toBeFocused();
    await expect.poll(() => ultimaValidacion(motor)).toEqual({
      nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'mayusculas', args: [] }, { nombre: 'primeros', args: [8] }] }],
    });

    await editor(page).getByRole('button', { name: 'Quitar Mayúsculas' }).click();
    await expect(pieza(page, /^Variable Titular/)).toHaveText('Titular · primeros caracteres');
    await expect.poll(() => ultimaValidacion(motor)).toEqual({
      nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'primeros', args: [8] }] }],
    });
  });

  test('solo ofrece las funciones que aceptan el tipo que llega', async ({ page }) => {
    await abrir(page, {
      expresion: { nodos: [{ tipo: 'variable', nombre: 'fecha_vencimiento_cuota', funciones: [] }] },
    });
    await pieza(page, /^Variable Vencimiento/).click();
    await botonFuncion(page).click();
    await expect(listaFunciones(page).getByRole('option', { name: /^Formato de fecha/ })).toHaveCount(1);
    await expect(listaFunciones(page).getByRole('option', { name: /^Mayúsculas/ })).toHaveCount(0);
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
    // El mensaje dice el rango del catálogo (primeros: entero, mínimo 1), no el genérico.
    await expect(campo).toHaveAccessibleDescription('Escribe un número de 1 en adelante.');
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

  test('el contador tiene una sola forma: con tope «n / tope», con «hasta» si los datos lo alargan, sin tag mientras no hay nada que decir', async ({ page }) => {
    await abrir(page, {
      expresion: SPEECH,
      ajustar: (motor) => {
        motor.validacion = () => ({ problemas: [], tipo: 'texto', cota: 120, sin_cota: null, variables: [] });
      },
    });
    const largo = editor(page).locator('.editor-texto__largo');
    // El largo del texto de ejemplo, contra el tope de 160, y lo que puede llegar a medir con los datos más largos.
    await expect(largo.locator('[data-largo-texto]')).toHaveText(/^\d+ \/ 160 caracteres · hasta 120 con los datos más largos$/);
    // Dentro del tope y por debajo del umbral (150): ningún tag.
    await expect(largo.locator('.tag')).toBeHidden();
    await expect(largo.locator('[data-largo-texto]')).not.toHaveClass(/editor-texto__largo--error/);
    await expect(editor(page).locator('[data-largo-anuncio]')).toBeEmpty();
  });

  test('sin «hasta» cuando el máximo no supera lo escrito, y sin tope (Columnas) solo «n caracteres»', async ({ page }) => {
    await abrir(page, {
      expresion: SPEECH,
      ajustar: (motor) => {
        motor.validacion = () => ({ problemas: [], tipo: 'texto', cota: 1, sin_cota: null, variables: [] });
      },
    });
    await expect(editor(page).locator('[data-largo-texto]')).toHaveText(/^\d+ \/ 160 caracteres$/);

    await abrir(page, { extra: '&contexto=cartera', expresion: SPEECH });
    await expect(editor(page).locator('[data-largo-texto]')).toHaveText(/^\d+ caracteres$/);
    await expect(editor(page).locator('.editor-texto__largo .tag')).toBeHidden();
  });

  test('«Cerca del tope» al llegar al umbral y «Pasa el tope» al pasarlo, cada uno en su tag y anunciado una sola vez', async ({ page }) => {
    let cota = 120;
    await abrir(page, {
      expresion: SPEECH,
      ajustar: (motor) => {
        motor.validacion = () => ({ problemas: [], tipo: 'texto', cota, sin_cota: null, variables: [] });
      },
    });
    const largo = editor(page).locator('.editor-texto__largo');
    const anuncio = editor(page).locator('[data-largo-anuncio]');
    await expect(largo.locator('[data-largo-texto]')).toContainText('· hasta 120');

    // Pasa el umbral del contexto (150) sin pasar el tope (160).
    cota = 155;
    await editor(page).getByRole('textbox', { name: 'Texto al final' }).fill('. Gracias.');
    await expect(largo.locator('.tag')).toHaveText('Cerca del tope');
    await expect(largo.locator('.tag')).toHaveClass(/tag--advertencia/);
    await expect(largo.locator('[data-largo-texto]')).not.toHaveClass(/editor-texto__largo--error/);
    await expect(anuncio).toHaveText('Cerca del tope');

    // Pasa el tope: el contador se marca como error y el tag cambia.
    cota = 170;
    await editor(page).getByRole('textbox', { name: 'Texto al final' }).fill('. Gracias de nuevo.');
    await expect(largo.locator('[data-largo-texto]')).toContainText('· hasta 170');
    await expect(largo.locator('.tag')).toHaveText('Pasa el tope');
    await expect(largo.locator('.tag')).toHaveClass(/tag--error/);
    await expect(largo.locator('[data-largo-texto]')).toHaveClass(/editor-texto__largo--error/);
    // En el color de error y sin caja: ni borde ni fondo propios.
    await expect(largo.locator('[data-largo-texto]')).toHaveCSS('border-top-width', '0px');
    await expect(largo.locator('[data-largo-texto]')).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
    const colorError = await page.evaluate(() => {
      const prueba = document.createElement('span');
      prueba.style.color = 'var(--color-danger-text)';
      document.body.append(prueba);
      const color = getComputedStyle(prueba).color;
      prueba.remove();
      return color;
    });
    await expect(largo.locator('[data-largo-texto]')).toHaveCSS('color', colorError);
    await expect(anuncio).toHaveText('Pasa el tope');

    // Vuelve por debajo del umbral: el tag y el error se van, y no se anuncia nada nuevo.
    cota = 120;
    await editor(page).getByRole('textbox', { name: 'Texto al final' }).fill('.');
    await expect(largo.locator('.tag')).toBeHidden();
    await expect(largo.locator('[data-largo-texto]')).not.toHaveClass(/editor-texto__largo--error/);
    await expect(anuncio).toHaveText('Pasa el tope');
  });

  test('«Ir al problema» se ve como un enlace y lleva a su lugar: el tramo, el parámetro y la píldora', async ({ page }) => {
    const conProblemaEn = (ubicacion: Problema['ubicacion']) => (motor: ApiFalsaTextoEnriquecido) => {
      motor.validacion = () => ({
        problemas: [problema('parametro_invalido', ubicacion)],
        tipo: 'texto', cota: 170, sin_cota: null, variables: [],
      });
    };
    const ir = (p: Page) => editor(p).locator('[data-resumen]').getByRole('button', { name: 'Ir al problema' });

    // Un enlace: subrayado, del color del aviso (el de los enlaces de los otros avisos) y sin la caja de un botón.
    await abrir(page, { expresion: SPEECH, ajustar: conProblemaEn({ nodo: 0, funcion: null, parametro: null }) });
    await expect(ir(page)).toHaveCSS('text-decoration-line', 'underline');
    await expect(ir(page)).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
    await expect(ir(page)).toHaveCSS('border-top-width', '0px');
    const colorDelAviso = await editor(page).locator('[data-resumen]').evaluate((aviso) => getComputedStyle(aviso.querySelector('[data-resumen-lista]')!).color);
    await expect(ir(page)).toHaveCSS('color', colorDelAviso);

    // El tramo (nodo 0 es el texto «Hola »).
    await ir(page).click();
    await expect(editor(page).locator('[data-tramo="0"]')).toBeFocused();

    // La píldora (nodo 1 es la variable, sin función).
    await abrir(page, { expresion: SPEECH, ajustar: conProblemaEn({ nodo: 1, funcion: null, parametro: null }) });
    await ir(page).click();
    await expect(pieza(page, /^Variable Titular/)).toBeFocused();

    // El parámetro (nodo 1, función 0, parámetro n).
    await abrir(page, { expresion: SPEECH, ajustar: conProblemaEn({ nodo: 1, funcion: 0, parametro: 'n' }) });
    await ir(page).click();
    await expect(editor(page).getByRole('textbox', { name: 'Cantidad de caracteres' })).toBeFocused();
  });

  test('un dato vacío de la muestra es un hint bajo la vista previa, «Con este producto, falta el dato de …», y no entra al resumen', async ({ page }) => {
    await abrir(page, {
      expresion: SPEECH,
      ajustar: (motor) => {
        delete motor.catalogos['mowa_mes.speech'].contexto.ejemplo.fecha_vencimiento_cuota;
      },
    });
    const hint = editor(page).locator('.editor-texto__datos .field__hint');
    await expect(hint).toHaveText('Con este producto, falta el dato de Vencimiento de la cuota.');
    // Es un hint, no un aviso, y no cuenta como problema del texto.
    await expect(editor(page).locator('.editor-texto__datos .notice')).toHaveCount(0);
    await expect(editor(page).locator('[data-resumen]')).toBeHidden();
    // Está en la vista previa, después del resultado y del contador.
    const abajo = await page.evaluate(() => {
      const hint = document.querySelector('#editor-prueba .editor-texto__datos')!.getBoundingClientRect();
      const resultado = document.querySelector('#editor-prueba [data-resultado]')!.getBoundingClientRect();
      return hint.top >= resultado.bottom;
    });
    expect(abajo).toBe(true);
  });

  test('sin datos vacíos no hay hints, y la lista es una región viva que no se esconde', async ({ page }) => {
    await abrir(page, { expresion: SPEECH });
    await expect(editor(page).locator('.editor-texto__datos')).toBeEmpty();
    await expect(editor(page).locator('.editor-texto__datos')).toHaveAttribute('aria-live', 'polite');
    await expect(editor(page).locator('.editor-texto__datos')).not.toHaveAttribute('hidden');
  });

  test('los hints de la muestra se anuncian: están en una región viva, y se reescriben solo si cambia lo que dicen', async ({ page }) => {
    await abrir(page, {
      expresion: SPEECH,
      ajustar: (motor) => {
        delete motor.catalogos['mowa_mes.speech'].contexto.ejemplo.fecha_vencimiento_cuota;
      },
    });
    const region = editor(page).locator('.editor-texto__datos');
    await expect(region.locator('.field__hint')).toHaveText('Con este producto, falta el dato de Vencimiento de la cuota.');
    await expect(region).toHaveAttribute('aria-live', 'polite');
    // Se marca el nodo del hint y se escribe en el texto sin tocar lo vacío: la vista se repinta, el hint es el mismo nodo.
    await region.locator('.field__hint').evaluate((nodo) => ((nodo as HTMLElement).dataset.visto = 'si'));
    await editor(page).getByRole('textbox', { name: 'Texto al final' }).fill('. Gracias.');
    await expect(resultado(page)).toContainText('Gracias');
    await expect(region.locator('.field__hint')).toHaveAttribute('data-visto', 'si');
  });

  test('en el speech de MOWA, un adicional obligatorio que viene vacío da primero «falta el dato» y después el motivo de exclusión de la fila', async ({ page }) => {
    await abrir(page, {
      expresion: { nodos: [{ tipo: 'texto', valor: 'Zona: ' }, { tipo: 'variable', nombre: 'ad_zona', funciones: [], obligatoria: true }] },
      ajustar: (motor) => {
        motor.catalogos['mowa_mes.speech'].contexto.variables.push(...variablesAdicionalesSinteticas());
        const original = motor.previsualizacion;
        motor.previsualizacion = (cuerpo, catalogo) => {
          const respuesta = original(cuerpo, catalogo);
          if ('estado' in respuesta) return respuesta;
          // La fila de la muestra queda excluida por el dato obligatorio vacío, como lo hace el backend.
          respuesta.filas[0].excluida = { codigo: 'variable_obligatoria_vacia', detalle: 'Falta un dato obligatorio.' };
          return respuesta;
        };
      },
    });
    const hints = editor(page).locator('.editor-texto__datos .field__hint');
    await expect(hints).toHaveText([
      'Con este producto, falta el dato de Zona.',
      'Falta en este producto un dato marcado como obligatorio.',
    ]);
    // Ninguno de los dos es un error de lo escrito: el resumen no aparece.
    await expect(editor(page).locator('[data-resumen]')).toBeHidden();
  });

  test('un error de verdad sigue en el resumen: el dato vacío no lo infla', async ({ page }) => {
    await abrir(page, {
      expresion: SPEECH,
      ajustar: (motor) => {
        delete motor.catalogos['mowa_mes.speech'].contexto.ejemplo.fecha_vencimiento_cuota;
        motor.validacion = () => ({
          problemas: [problema('parametro_invalido', { nodo: 1, funcion: 0, parametro: 'n' })],
          tipo: 'texto', cota: 170, sin_cota: null, variables: [],
        });
      },
    });
    await expect(editor(page).locator('[data-resumen]')).toContainText('Hay 1 problema en el texto.');
    await expect(editor(page).locator('.editor-texto__datos .field__hint')).toHaveCount(1);
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

  test('Escape en el buscador del botón lo cierra sin insertar y devuelve el foco al botón', async ({ page }) => {
    await abrir(page);
    const agregar = editor(page).getByRole('button', { name: 'Insertar variable', exact: true });
    await agregar.click();
    await expect(editor(page).getByRole('combobox', { name: 'Buscar una variable' })).toBeFocused();
    await expect(editor(page).getByRole('listbox', { name: 'Elegir una variable' })).toBeVisible();
    await expect(agregar).toHaveAttribute('aria-expanded', 'true');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Escape');
    await expect(editor(page).getByRole('listbox')).toHaveCount(0);
    await expect(agregar).toBeFocused();
    await expect(agregar).toHaveAttribute('aria-expanded', 'false');
    await expect(editor(page).locator('[data-pieza]')).toHaveCount(0);
  });
});

test('una versión de solo lectura no se puede editar', async ({ page }) => {
  await abrir(page, { expresion: SPEECH, extra: '&soloLectura=1' });
  await expect(editor(page).getByRole('textbox', { name: 'Texto al inicio' })).not.toBeEditable();
  await expect(editor(page).getByRole('button', { name: 'Insertar variable', exact: true })).toBeDisabled();
  await expect(editor(page).locator('[data-pista-disparador]')).toBeHidden();
  await pieza(page, /^Variable Titular/).click();
  await expect(editor(page).getByRole('button', { name: 'Quitar variable' })).toBeDisabled();
});

test.describe('el disparador [@ (§13.2)', () => {
  const tramo = (page: Page, indice: number) => editor(page).locator(`[data-tramo="${indice}"]`);
  const buscador = (page: Page) => editor(page).getByRole('listbox', { name: 'Elegir una variable' });
  const anuncio = (page: Page) => editor(page).locator('[data-disparador-anuncio]');

  test('escribir [@ abre el buscador en el texto sin sacar el foco, con los atributos de combobox y el anuncio', async ({ page }) => {
    await abrir(page);
    await tramo(page, 0).click();
    await expect(tramo(page, 0)).not.toHaveAttribute('role', 'combobox');

    await page.keyboard.type('Hola [@');

    await expect(buscador(page)).toBeVisible();
    await expect(tramo(page, 0)).toBeFocused();
    await expect(tramo(page, 0)).toHaveAttribute('role', 'combobox');
    await expect(tramo(page, 0)).toHaveAttribute('aria-expanded', 'true');
    await expect(tramo(page, 0)).toHaveAttribute('aria-autocomplete', 'list');
    await expect(tramo(page, 0)).toHaveAttribute('aria-controls', (await buscador(page).getAttribute('id')) ?? '');
    const primera = (await buscador(page).getByRole('option').first().getAttribute('id')) ?? '';
    await expect(tramo(page, 0)).toHaveAttribute('aria-activedescendant', primera);
    await expect(anuncio(page)).toHaveText('Buscador de variables. Escribe para filtrar, Enter inserta y Escape cancela.');
  });

  test('lo que se escribe filtra; Enter inserta en lugar de [@… y el cursor queda después de la pieza', async ({ page }) => {
    const { motor } = await abrir(page);
    await tramo(page, 0).click();
    await page.keyboard.type('Hola [@titu');

    await expect(buscador(page).getByRole('option')).toHaveCount(1);
    await expect(buscador(page).getByRole('option', { name: /^Titular/ })).toBeVisible();
    await page.keyboard.press('Enter');

    await expect(buscador(page)).toHaveCount(0);
    await expect(tramo(page, 0)).toHaveValue('Hola ');
    await expect(pieza(page, /^Variable Titular/)).toHaveAttribute('aria-expanded', 'false');
    await expect(tramo(page, 2)).toBeFocused();
    await expect(tramo(page, 0)).not.toHaveAttribute('role', 'combobox');
    await expect(anuncio(page)).toHaveText('Se insertó Titular.');

    await page.keyboard.type(' paga');
    await expect(tramo(page, 2)).toHaveValue(' paga');
    await expect.poll(() => ultimaValidacion(motor)).toEqual({
      nodos: [
        { tipo: 'texto', valor: 'Hola ' },
        { tipo: 'variable', nombre: 'titular', funciones: [] },
        { tipo: 'texto', valor: ' paga' },
      ],
    });
  });

  test('en medio de un texto lo parte en dos y borra solo [@ y lo escrito para buscar', async ({ page }) => {
    const { motor } = await abrir(page, { expresion: { nodos: [{ tipo: 'texto', valor: 'Hola mundo' }] } });
    await tramo(page, 0).click();
    await tramo(page, 0).evaluate((area: HTMLTextAreaElement) => area.setSelectionRange(4, 4));
    await page.keyboard.type('[@sal');
    await page.keyboard.press('Enter');

    await expect.poll(() => ultimaValidacion(motor)).toEqual({
      nodos: [
        { tipo: 'texto', valor: 'Hola' },
        { tipo: 'variable', nombre: 'saldo_capital_pendiente', funciones: [] },
        { tipo: 'texto', valor: ' mundo' },
      ],
    });
  });

  test('las flechas mueven la opción resaltada y Tab inserta la resaltada', async ({ page }) => {
    const { motor } = await abrir(page);
    await tramo(page, 0).click();
    await page.keyboard.type('[@');
    const primera = (await buscador(page).getByRole('option').first().getAttribute('id')) ?? '';

    await page.keyboard.press('ArrowDown');
    const segunda = (await buscador(page).getByRole('option').nth(1).getAttribute('id')) ?? '';
    await expect(tramo(page, 0)).toHaveAttribute('aria-activedescendant', segunda);
    await expect(page.locator(`#${segunda}`)).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator(`#${primera}`)).toHaveAttribute('aria-selected', 'false');
    await page.keyboard.press('ArrowUp');
    await expect(tramo(page, 0)).toHaveAttribute('aria-activedescendant', primera);

    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Tab');
    const nombre = segunda.split('-opcion-')[1];
    await expect.poll(() => ultimaValidacion(motor)).toMatchObject({ nodos: [{ tipo: 'variable', nombre }] });
    await expect(tramo(page, 2)).toBeFocused();
  });

  test('Escape deja el texto tal como se escribió, y quien quería [@ literal no pierde nada', async ({ page }) => {
    await abrir(page);
    await tramo(page, 0).click();
    await page.keyboard.type('a [@tit');
    await expect(buscador(page)).toBeVisible();

    await page.keyboard.press('Escape');

    await expect(buscador(page)).toHaveCount(0);
    await expect(tramo(page, 0)).toHaveValue('a [@tit');
    await expect(tramo(page, 0)).toBeFocused();
    await expect(tramo(page, 0)).not.toHaveAttribute('role', 'combobox');
    // Seguir escribiendo no lo reabre.
    await page.keyboard.type('x');
    await expect(buscador(page)).toHaveCount(0);
  });

  test('borrar la @ cierra el buscador', async ({ page }) => {
    await abrir(page);
    await tramo(page, 0).click();
    await page.keyboard.type('[@');
    await expect(buscador(page)).toBeVisible();

    await page.keyboard.press('Backspace');

    await expect(buscador(page)).toHaveCount(0);
    await expect(tramo(page, 0)).toHaveValue('[');
    // Volver a escribir la @ lo abre de nuevo.
    await page.keyboard.type('@');
    await expect(buscador(page)).toBeVisible();
  });

  test('sin coincidencias lo dice con lo escrito, y Enter no inserta nada', async ({ page }) => {
    const { motor } = await abrir(page);
    await tramo(page, 0).click();
    await page.keyboard.type('[@zzzz');

    await expect(editor(page).getByText('Ninguna variable coincide con «zzzz».')).toBeVisible();
    await expect(buscador(page).getByRole('option')).toHaveCount(0);
    await expect(tramo(page, 0)).not.toHaveAttribute('aria-activedescendant', /.+/);
    await page.keyboard.press('Enter');

    await expect(tramo(page, 0)).toHaveValue('[@zzzz');
    // La lista vacía no tiene alto: sigue abierta si su mensaje sigue ahí.
    await expect(editor(page).getByText('Ninguna variable coincide con «zzzz».')).toBeVisible();
    await expect.poll(() => ultimaValidacion(motor)).toEqual({ nodos: [{ tipo: 'texto', valor: '[@zzzz' }] });
  });

  test('un clic en una opción inserta igual, sin que el texto pierda el foco antes', async ({ page }) => {
    const { motor } = await abrir(page);
    await tramo(page, 0).click();
    await page.keyboard.type('[@tele');
    await buscador(page).getByRole('option', { name: /^Teléfono/ }).click();

    await expect.poll(() => ultimaValidacion(motor)).toMatchObject({ nodos: [{ tipo: 'variable', nombre: 'telefono' }] });
    await expect(tramo(page, 2)).toBeFocused();
  });

  test('«Insertar variable» va arriba de la línea, con la pista debajo', async ({ page }) => {
    await abrir(page);
    const boton = editor(page).getByRole('button', { name: 'Insertar variable', exact: true });
    const linea = editor(page).getByRole('group', { name: 'Texto del mensaje' });
    const pista = editor(page).locator('[data-pista-disparador]');
    await expect(pista).toHaveText('Escribe [@ para insertar una variable');
    await expect(linea).toHaveAccessibleDescription('Escribe [@ para insertar una variable');

    const cajas = await Promise.all([boton, linea, pista].map((l) => l.boundingBox()));
    const [cajaBoton, cajaLinea, cajaPista] = cajas as NonNullable<(typeof cajas)[number]>[];
    expect(cajaBoton.y + cajaBoton.height).toBeLessThanOrEqual(cajaLinea.y);
    expect(cajaPista.y).toBeGreaterThanOrEqual(cajaLinea.y + cajaLinea.height);
  });

  test('el botón abre el buscador con su campo y el foco ahí; sin foco previo avisa «al final», con foco no', async ({ page }) => {
    await abrir(page);
    const agregar = editor(page).getByRole('button', { name: 'Insertar variable', exact: true });
    await agregar.click();
    const campo = editor(page).getByRole('combobox', { name: 'Buscar una variable' });
    await expect(buscador(page)).toBeVisible();
    await expect(campo).toBeFocused();
    await expect(campo).toHaveAttribute('aria-expanded', 'true');
    await expect(campo).toHaveAttribute('aria-autocomplete', 'list');
    await expect(campo).toHaveAttribute('aria-controls', (await buscador(page).getAttribute('id')) ?? '');
    const primera = (await buscador(page).getByRole('option').first().getAttribute('id')) ?? '';
    await expect(campo).toHaveAttribute('aria-activedescendant', primera);
    // El texto no es el combobox: el campo lo es.
    await expect(tramo(page, 0)).not.toHaveAttribute('role', 'combobox');
    await expect(anuncio(page)).toContainText('Se insertará al final del texto.');
    await page.keyboard.press('Escape');

    await tramo(page, 0).click();
    await page.keyboard.type('ab');
    await agregar.click();
    await expect(campo).toBeFocused();
    await expect(anuncio(page)).not.toContainText('al final');
  });

  test('escribir en el campo del botón filtra la lista y no toca el texto; Enter inserta donde estaba el cursor', async ({ page }) => {
    const { motor } = await abrir(page, { expresion: { nodos: [{ tipo: 'texto', valor: 'Hola mundo' }] } });
    await tramo(page, 0).click();
    await tramo(page, 0).evaluate((area: HTMLTextAreaElement) => {
      area.setSelectionRange(4, 4);
      area.dispatchEvent(new Event('select'));
    });
    await editor(page).getByRole('button', { name: 'Insertar variable', exact: true }).click();
    await page.keyboard.type('sal');

    await expect(buscador(page).getByRole('option')).toHaveCount(1);
    await expect(tramo(page, 0)).toHaveValue('Hola mundo');
    await page.keyboard.press('Enter');

    await expect.poll(() => ultimaValidacion(motor)).toEqual({
      nodos: [
        { tipo: 'texto', valor: 'Hola' },
        { tipo: 'variable', nombre: 'saldo_capital_pendiente', funciones: [] },
        { tipo: 'texto', valor: ' mundo' },
      ],
    });
  });

  test('el campo del botón sin coincidencias lo dice, y Enter no inserta', async ({ page }) => {
    await abrir(page);
    await editor(page).getByRole('button', { name: 'Insertar variable', exact: true }).click();
    await page.keyboard.type('zzzz');
    await expect(editor(page).getByText('Ninguna variable coincide con «zzzz».')).toBeVisible();
    await page.keyboard.press('Enter');
    await expect(editor(page).getByText('Ninguna variable coincide con «zzzz».')).toBeVisible();
    await expect(editor(page).locator('[data-pieza]')).toHaveCount(0);
  });

  test('Tab desde el campo del buscador de variables sale directo y lo cierra, sin pasar por la lista', async ({ page }) => {
    await abrir(page);
    await editor(page).getByRole('button', { name: 'Insertar variable', exact: true }).click();
    await expect(editor(page).getByRole('combobox', { name: 'Buscar una variable' })).toBeFocused();
    await expect(buscador(page)).toHaveAttribute('tabindex', '-1');
    await page.keyboard.press('Tab');
    await expect(buscador(page)).toHaveCount(0);
    await expect(editor(page).getByRole('button', { name: 'Insertar variable', exact: true })).not.toBeFocused();
    expect(await page.evaluate(() => document.activeElement?.getAttribute('role'))).not.toBe('listbox');
  });

  test('desde el botón la pieza abre su panel, como siempre', async ({ page }) => {
    await abrir(page);
    await editor(page).getByRole('button', { name: 'Insertar variable', exact: true }).click();
    await page.keyboard.type('titu');
    await page.keyboard.press('Enter');
    await expect(botonFuncion(page)).toBeFocused();
  });

  test('a 360 px el buscador ocupa el ancho de la línea, abierto por [@ o por el botón, y la página no desborda', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 780 });
    await abrir(page, { expresion: SPEECH });

    const medir = () =>
      page.evaluate(() => {
        const linea = document.querySelector('#editor-prueba [data-linea]')!.getBoundingClientRect();
        const lista = document.querySelector('#editor-prueba [role="listbox"]')!.closest('.selector-variable')!.getBoundingClientRect();
        return {
          izquierda: lista.left - linea.left,
          derecha: linea.right - lista.right,
          pagina: document.documentElement.scrollWidth,
          vista: window.innerWidth,
        };
      });

    await tramo(page, 4).click();
    await page.keyboard.type('[@');
    await expect(buscador(page)).toBeVisible();
    const porDisparador = await medir();
    expect(Math.abs(porDisparador.izquierda)).toBeLessThanOrEqual(1);
    expect(Math.abs(porDisparador.derecha)).toBeLessThanOrEqual(1);
    expect(porDisparador.pagina).toBeLessThanOrEqual(porDisparador.vista);
    await page.keyboard.press('Escape');

    await editor(page).getByRole('button', { name: 'Insertar variable', exact: true }).click();
    await expect(buscador(page)).toBeVisible();
    const porBoton = await medir();
    expect(Math.abs(porBoton.izquierda)).toBeLessThanOrEqual(1);
    expect(Math.abs(porBoton.derecha)).toBeLessThanOrEqual(1);
    expect(porBoton.pagina).toBeLessThanOrEqual(porBoton.vista);
  });
});

test.describe('las píldoras (§13.5)', () => {
  const dePieza = (funciones: unknown[] = [], nombre = 'titular') => ({
    expresion: { nodos: [{ tipo: 'variable', nombre, funciones }] },
  });

  test('con una función dice su nombre corto, con dos o más cuántas, y la cadena completa va en el title y en el nombre accesible', async ({ page }) => {
    await abrir(page, dePieza([{ nombre: 'mayusculas', args: [] }]));
    const una = pieza(page, /^Variable Titular/);
    await expect(una).toHaveText('Titular · mayúsculas');
    await expect(una).toHaveAttribute('title', 'Titular · mayúsculas');

    await abrir(page, dePieza([{ nombre: 'primeros', args: [8] }, { nombre: 'mayusculas', args: [] }, { nombre: 'sin_tildes', args: [] }]));
    const varias = pieza(page, /^Variable Titular/);
    await expect(varias).toHaveText('Titular · 3 funciones');
    // La cadena completa, sin cortar, en el title y en el nombre accesible.
    await expect(varias).toHaveAttribute('title', 'Titular · primeros caracteres 8 · mayúsculas · quitar tildes');
    await expect(varias).toHaveAccessibleName(/primeros caracteres 8 · mayúsculas · quitar tildes/);
  });

  test('sin funciones dice solo el nombre; con dos, «2 funciones»', async ({ page }) => {
    await abrir(page, dePieza());
    await expect(pieza(page, /^Variable Titular/)).toHaveText('Titular');
    await abrir(page, dePieza([{ nombre: 'mayusculas', args: [] }, { nombre: 'sin_tildes', args: [] }]));
    await expect(pieza(page, /^Variable Titular/)).toHaveText('Titular · 2 funciones');
  });

  test('se lee como una palabra de la frase: en la sans del cuerpo, no en mono, y con un ancho máximo de unas 24 letras', async ({ page }) => {
    await abrir(page, dePieza([], 'dias_atraso_ajustados'));
    const p = pieza(page, /^Variable Días de atraso ajustados/);
    const medidas = await p.evaluate((boton) => {
      const texto = boton.querySelector('.editor-texto__piezaTexto') as HTMLElement;
      return {
        fuente: getComputedStyle(boton).fontFamily,
        cortado: texto.scrollWidth > texto.clientWidth,
        ancho: texto.clientWidth,
        tamanoLetra: parseFloat(getComputedStyle(texto).fontSize),
      };
    });
    expect(medidas.fuente).toMatch(/Inter/);
    expect(medidas.fuente).not.toMatch(/JetBrains|monospace/);
    // «Días de atraso ajustados al envío» (33 letras) se corta con puntos suspensivos; su nombre accesible, completo.
    expect(medidas.cortado).toBe(true);
    expect(medidas.ancho).toBeLessThanOrEqual(medidas.tamanoLetra * 24);
    await expect(p).toHaveAccessibleName(/^Variable Días de atraso ajustados al envío/);
    await expect(p).toHaveAttribute('title', 'Días de atraso ajustados al envío');
  });

  test('el WhatsApp de contacto lleva el ícono message-circle y las demás píldoras no', async ({ page }) => {
    await abrir(page, {
      expresion: {
        nodos: [
          { tipo: 'variable', nombre: 'whatsapp_contacto', funciones: [] },
          { tipo: 'texto', valor: ' ' },
          { tipo: 'variable', nombre: 'titular', funciones: [] },
        ],
      },
    });
    const whatsapp = pieza(page, /^Variable WhatsApp de contacto/);
    await expect(whatsapp.locator('svg')).toHaveCount(1);
    await expect(whatsapp.locator('svg path[d^="M2.992 16.342"]')).toHaveCount(1);
    await expect(pieza(page, /^Variable Titular/).locator('svg')).toHaveCount(0);
  });

  test('la variable «whatsapp» de WhatsMKT también lleva el ícono message-circle', async ({ page }) => {
    await abrir(page, {
      expresion: { nodos: [{ tipo: 'variable', nombre: 'whatsapp', funciones: [] }, { tipo: 'texto', valor: ' ' }, { tipo: 'variable', nombre: 'titular', funciones: [] }] },
      ajustar: (motor) => {
        motor.catalogos['mowa_mes.speech'].contexto.variables.push({
          nombre: 'whatsapp', tipo: 'texto', clave_nombre: null, origen: 'cartera', etiqueta: 'Enlace de WhatsApp', adicional: false, archivado: false, tema: 'persona',
        });
      },
    });
    const pildoras = editor(page).locator('[data-pieza]');
    await expect(pildoras.nth(0)).toHaveAccessibleName(/^Variable Enlace de WhatsApp/);
    await expect(pildoras.nth(0).locator('svg path[d^="M2.992 16.342"]')).toHaveCount(1);
    await expect(pildoras.nth(1).locator('svg')).toHaveCount(0);
  });

  test('con un problema, el ícono es el del problema y no el de WhatsApp', async ({ page }) => {
    await abrir(page, {
      expresion: { nodos: [{ tipo: 'variable', nombre: 'whatsapp_contacto', funciones: [{ nombre: 'primeros', args: [0] }] }] },
      ajustar: (motor) => {
        motor.validacion = () => ({
          problemas: [problema('parametro_invalido', { nodo: 0, funcion: 0, parametro: 'n' })],
          tipo: 'texto', cota: 170, sin_cota: null, variables: [],
        });
      },
    });
    const whatsapp = pieza(page, /^Variable WhatsApp de contacto/);
    await expect(whatsapp).toHaveAccessibleName(/con un problema/);
    await expect(whatsapp.locator('svg')).toHaveCount(1);
    await expect(whatsapp.locator('svg path[d^="M2.992 16.342"]')).toHaveCount(0);
  });
});

test.describe('la línea compacta (§13.5)', () => {
  const FRASE = {
    nodos: [
      { tipo: 'texto', valor: 'Hola ' },
      { tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'mayusculas', args: [] }] },
      { tipo: 'texto', valor: ', vence el ' },
      { tipo: 'variable', nombre: 'fecha_vencimiento_cuota', funciones: [] },
      { tipo: 'texto', valor: '.' },
    ],
  };
  const linea = (page: Page) => editor(page).locator('[data-linea]');

  /** Rows of the line: the top of each piece with something to show, grouped; and what each row holds. */
  const renglones = (page: Page) =>
    linea(page).evaluate((contenedor) => {
      const piezas = [...contenedor.querySelectorAll<HTMLElement>('[data-pieza], textarea')]
        .filter((e) => !(e instanceof HTMLTextAreaElement) || e.value !== '')
        .map((e) => {
          const caja = e.getBoundingClientRect();
          return { medio: caja.top + caja.height / 2, texto: e instanceof HTMLTextAreaElement ? e.value : '[pieza]' };
        })
        .sort((a, b) => a.medio - b.medio);
      // Pills and runs differ in height, so their tops differ: a new row starts when the middle drops by more than half a row.
      const filas: string[][] = [];
      let ultimo = -Infinity;
      for (const p of piezas) {
        if (p.medio - ultimo > 12) filas.push([]);
        filas[filas.length - 1].push(p.texto);
        ultimo = p.medio;
      }
      return filas;
    });

  test('a 1280 px «Hola [Titular · mayúsculas], vence el [Vencimiento de la cuota].» cabe en un renglón', async ({ page }) => {
    await abrir(page, { expresion: FRASE });
    const filas = await renglones(page);
    expect(filas).toHaveLength(1);
  });

  test('a 360 px cabe en tres renglones como máximo, y ningún renglón queda con solo un signo', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await abrir(page, { expresion: FRASE });
    const filas = await renglones(page);
    expect(filas.length).toBeLessThanOrEqual(3);
    for (const fila of filas) expect(fila.every((t) => /^\s*[.,;:]\s*$/.test(t))).toBe(false);
    // El punto final va en el mismo renglón que la píldora de antes.
    expect([...filas.at(-1)!].sort()).toEqual(['.', '[pieza]']);
    const pagina = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(pagina).toBeLessThanOrEqual(360);
  });

  test('un tramo vacío conserva un blanco de 24 px donde hacer clic para poner el cursor', async ({ page }) => {
    await abrir(page, {
      expresion: { nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [] }, { tipo: 'variable', nombre: 'telefono', funciones: [] }] },
    });
    for (const indice of [0, 2, 4]) {
      const caja = (await editor(page).locator(`[data-tramo="${indice}"]`).boundingBox())!;
      expect(caja.width, `tramo ${indice}`).toBeGreaterThanOrEqual(24);
      expect(caja.height, `tramo ${indice}`).toBeGreaterThanOrEqual(20);
    }
    await editor(page).locator('[data-tramo="2"]').click();
    await expect(editor(page).locator('[data-tramo="2"]')).toBeFocused();
    await page.keyboard.type('y');
    await expect(editor(page).locator('[data-tramo="2"]')).toHaveValue('y');
  });

  test('un tramo largo ocupa su renglón y se parte; uno corto sigue pegado a su píldora al escribir', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await abrir(page, { expresion: { nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [] }, { tipo: 'texto', valor: '.' }] } });
    const par = editor(page).locator('.editor-texto__par');
    await expect(par).toHaveClass(/editor-texto__par--junto/);

    await editor(page).locator('[data-tramo="2"]').click();
    await page.keyboard.press('End');
    await page.keyboard.type(' y un texto bastante largo que no cabe junto a la píldora en un teléfono');
    await expect(par).not.toHaveClass(/editor-texto__par--junto/);
    const g = await linea(page).evaluate((contenedor) => {
      const area = contenedor.querySelector<HTMLElement>('[data-tramo="2"]')!.getBoundingClientRect();
      const caja = contenedor.getBoundingClientRect();
      return { derecha: area.right, limite: caja.right, pagina: document.documentElement.scrollWidth };
    });
    expect(g.derecha).toBeLessThanOrEqual(g.limite + 1);
    expect(g.pagina).toBeLessThanOrEqual(360);

    // Y vuelve a pegarse al borrar hasta dejar un signo.
    await page.keyboard.press('Control+A');
    await page.keyboard.type(',');
    await expect(par).toHaveClass(/editor-texto__par--junto/);
  });

  test('la línea mide al menos tres renglones aunque esté vacía, y desde unos diez hace scroll en vez de crecer', async ({ page }) => {
    await abrir(page);
    const vacia = await linea(page).evaluate((c) => ({ alto: c.getBoundingClientRect().height, renglon: parseFloat(getComputedStyle(c).lineHeight) }));
    expect(vacia.alto).toBeGreaterThanOrEqual(vacia.renglon * 3);

    await editor(page).locator('[data-tramo="0"]').fill(Array.from({ length: 40 }, (_, i) => `renglón ${i + 1}`).join('\n'));
    const llena = await linea(page).evaluate((c) => ({
      alto: c.getBoundingClientRect().height,
      renglon: parseFloat(getComputedStyle(c).lineHeight),
      scroll: c.scrollHeight > c.clientHeight,
    }));
    expect(llena.alto).toBeLessThanOrEqual(llena.renglon * 10 + 40);
    expect(llena.scroll).toBe(true);
  });

  test('quitar una variable une los tramos y la línea sigue en orden', async ({ page }) => {
    const { motor } = await abrir(page, { expresion: FRASE });
    await pieza(page, /^Variable Titular/).click();
    await editor(page).getByRole('button', { name: 'Quitar variable' }).click();
    await expect.poll(() => ultimaValidacion(motor)).toEqual({
      nodos: [
        { tipo: 'texto', valor: 'Hola , vence el ' },
        { tipo: 'variable', nombre: 'fecha_vencimiento_cuota', funciones: [] },
        { tipo: 'texto', valor: '.' },
      ],
    });
    await expect(editor(page).locator('[data-pieza]')).toHaveCount(1);
  });
});

test.describe('un navegador sin field-sizing: content (Firefox)', () => {
  test('el ancho del tramo lo pone el script, por caracteres, y sigue al texto mientras se escribe', async ({ page }) => {
    // El navegador de la prueba sí tiene field-sizing: se le dice que no, antes de que monte el editor.
    await page.addInitScript(() => {
      const original = CSS.supports.bind(CSS);
      CSS.supports = ((propiedad: string, valor?: string) =>
        propiedad.includes('field-sizing') ? false : valor === undefined ? original(propiedad) : original(propiedad, valor)) as typeof CSS.supports;
    });
    await abrir(page, { expresion: { nodos: [{ tipo: 'texto', valor: 'Hola' }, { tipo: 'variable', nombre: 'titular', funciones: [] }, { tipo: 'texto', valor: '' }] } });
    const ancho = (indice: number) => editor(page).locator(`[data-tramo="${indice}"]`).evaluate((a) => (a as HTMLElement).style.inlineSize);

    await expect.poll(() => ancho(0)).toBe('5ch');
    await expect.poll(() => ancho(2)).toBe('2ch');

    await editor(page).locator('[data-tramo="2"]').click();
    await page.keyboard.type('uno dos');
    await expect.poll(() => ancho(2)).toBe('8ch');
    await page.keyboard.press('Enter');
    await page.keyboard.type('tres cuatro');
    // La línea más larga manda: «tres cuatro» (11) más uno.
    await expect.poll(() => ancho(2)).toBe('12ch');
    await page.keyboard.press('Control+A');
    await page.keyboard.press('Backspace');
    await expect.poll(() => ancho(2)).toBe('2ch');
  });

  test('con field-sizing el script no toca el ancho: lo deja al CSS', async ({ page }) => {
    await abrir(page, { expresion: { nodos: [{ tipo: 'texto', valor: 'Hola' }] } });
    const ancho = await editor(page).locator('[data-tramo="0"]').evaluate((a) => (a as HTMLElement).style.inlineSize);
    expect(ancho).toBe('');
  });
});

test.describe('el buscador alineado al cursor (§13.2)', () => {
  const tramo = (page: Page, indice: number) => editor(page).locator(`[data-tramo="${indice}"]`);
  const panel = (page: Page) => editor(page).getByRole('listbox', { name: 'Elegir una variable' }).locator('xpath=..');

  test('a 1280 px abre bajo la línea, a la altura del cursor, sin pasar el borde de la línea', async ({ page }) => {
    await abrir(page, { expresion: { nodos: [{ tipo: 'texto', valor: 'Estimado cliente, le escribimos para recordarle ' }] } });
    await tramo(page, 0).click();
    await page.keyboard.press('End');
    await page.keyboard.type('[@');
    await expect(panel(page)).toBeVisible();
    // Con movimiento reducido el navegador anima cada propiedad en 0,01 ms: se espera a que el margen se asiente.
    await expect.poll(() => panel(page).evaluate((e) => getComputedStyle(e).marginInlineStart)).not.toBe('0px');

    const g = await page.evaluate(() => {
      const linea = document.querySelector('#editor-prueba [data-linea]')!.getBoundingClientRect();
      const area = document.querySelector('#editor-prueba [data-tramo="0"]')!.getBoundingClientRect();
      const panel = document.querySelector('#editor-prueba .selector-variable')!.getBoundingClientRect();
      return { lineaIzq: linea.left, lineaDer: linea.right, areaDer: area.right, panelIzq: panel.left, panelDer: panel.right, panelAncho: panel.width, lineaAncho: linea.width };
    });
    // Empieza donde empieza el «[@» (junto al final del texto), no en el borde izquierdo.
    expect(g.panelIzq).toBeGreaterThan(g.lineaIzq + 100);
    expect(Math.abs(g.panelIzq - (g.areaDer - 14))).toBeLessThanOrEqual(24);
    expect(g.panelDer).toBeLessThanOrEqual(g.lineaDer + 1);
    expect(g.panelAncho).toBeLessThan(g.lineaAncho);
  });

  test('con el cursor cerca del borde derecho, el buscador se recorre para no salirse', async ({ page }) => {
    await abrir(page, { expresion: { nodos: [{ tipo: 'texto', valor: 'x'.repeat(10) }] } });
    await tramo(page, 0).click();
    await page.keyboard.press('End');
    // Un texto largo en un renglón: el cursor queda lejos, a la derecha.
    await tramo(page, 0).fill('Estimado cliente, le escribimos de parte de la caja para recordarle que su cuota de este mes vence muy pronto, ');
    await page.keyboard.press('End');
    await page.keyboard.type('[@');
    await expect(panel(page)).toBeVisible();
    await expect.poll(() => panel(page).evaluate((e) => getComputedStyle(e).marginInlineStart)).not.toBe('0px');
    const g = await page.evaluate(() => {
      const linea = document.querySelector('#editor-prueba [data-linea]')!.getBoundingClientRect();
      const panel = document.querySelector('#editor-prueba .selector-variable')!.getBoundingClientRect();
      return { dentro: panel.left >= linea.left - 1 && panel.right <= linea.right + 1, pagina: document.documentElement.scrollWidth, vista: window.innerWidth };
    });
    expect(g.dentro).toBe(true);
    expect(g.pagina).toBeLessThanOrEqual(g.vista);
  });

  test('el buscador del botón no sigue al cursor: queda a la izquierda, del ancho de la línea', async ({ page }) => {
    await abrir(page, { expresion: { nodos: [{ tipo: 'texto', valor: 'Estimado cliente, le escribimos para recordarle ' }] } });
    await editor(page).getByRole('button', { name: 'Insertar variable', exact: true }).click();
    const g = await page.evaluate(() => {
      const linea = document.querySelector('#editor-prueba [data-linea]')!.getBoundingClientRect();
      const panel = document.querySelector('#editor-prueba .selector-variable')!.getBoundingClientRect();
      return { izquierda: panel.left - linea.left, ancho: panel.width, lineaAncho: linea.width };
    });
    expect(Math.abs(g.izquierda)).toBeLessThanOrEqual(1);
    expect(g.ancho).toBeGreaterThan(g.lineaAncho - 2);
  });
});

test.describe('un contexto que no admite funciones (admite_funciones=false)', () => {
  const sinFunciones = (motor: ApiFalsaTextoEnriquecido) => {
    motor.catalogos['mowa_mes.speech'].contexto.admite_funciones = false;
  };
  const conTitular = (funciones: unknown[] = []) => ({ nodos: [{ tipo: 'variable', nombre: 'titular', funciones }] });

  test('el panel de la pieza no ofrece «Agregar función» y dice lo que la página le pasó, con su enlace', async ({ page }) => {
    await abrir(page, { expresion: conTitular(), ajustar: sinFunciones, extra: '&sinFunciones=1' });
    await pieza(page, /^Variable Titular/).click();

    await expect(editor(page).getByRole('button', { name: 'Agregar función', exact: true })).toHaveCount(0);
    await expect(editor(page).getByRole('combobox', { name: 'Buscar función' })).toHaveCount(0);
    const nota = editor(page).locator('[data-sin-funciones]');
    await expect(nota).toContainText('Aquí las funciones se arman en otra pantalla.');
    const enlace = nota.getByRole('link', { name: 'Abrir Columnas de carga' });
    await expect(enlace).toBeVisible();
    await expect(enlace).toHaveAttribute('href', '/columnas?volver=%2Fpruebas%2Feditor-texto');
    // El panel queda con el aviso, su enlace y quitar la variable: sin «Obligatoria» ni «Resultado con el registro».
    await expect(editor(page).getByRole('checkbox', { name: 'Obligatoria' })).toHaveCount(0);
    await expect(editor(page).getByText('Resultado con el registro')).toHaveCount(0);
    await expect(editor(page).locator('[data-resultado-pieza]')).toHaveCount(0);
    await expect(editor(page).getByRole('button', { name: 'Quitar variable' })).toBeVisible();
  });

  test('con solo el texto, sin enlace, no hay enlace; sin la opción, solo se oculta «Agregar función»', async ({ page }) => {
    await abrir(page, { expresion: conTitular(), ajustar: sinFunciones, extra: '&sinFunciones=texto' });
    await pieza(page, /^Variable Titular/).click();
    await expect(editor(page).locator('[data-sin-funciones]')).toContainText('Aquí las funciones se arman en otra pantalla.');
    await expect(editor(page).locator('[data-sin-funciones] a')).toHaveCount(0);

    await abrir(page, { expresion: conTitular(), ajustar: sinFunciones });
    await pieza(page, /^Variable Titular/).click();
    await expect(editor(page).getByRole('button', { name: 'Agregar función', exact: true })).toHaveCount(0);
    await expect(editor(page).locator('[data-sin-funciones]')).toHaveCount(0);
    await expect(editor(page).getByRole('button', { name: 'Quitar variable' })).toBeVisible();
  });

  test('las funciones que ya tuviera la expresión se siguen viendo y se pueden quitar, para corregir lo que el backend rechace', async ({ page }) => {
    await abrir(page, { expresion: conTitular([{ nombre: 'mayusculas', args: [] }]), ajustar: sinFunciones, extra: '&sinFunciones=1' });
    await pieza(page, /^Variable Titular/).click();
    await expect(editor(page).getByRole('button', { name: 'Quitar Mayúsculas' })).toBeVisible();
    await expect(editor(page).getByRole('button', { name: 'Agregar función', exact: true })).toHaveCount(0);
  });

  test('«Insertar variable» no abre el panel de una pieza que no admite funciones: el cursor queda después de ella', async ({ page }) => {
    const { motor } = await abrir(page, { ajustar: sinFunciones, extra: '&sinFunciones=1' });
    await editor(page).getByRole('button', { name: 'Insertar variable', exact: true }).click();
    await page.keyboard.type('titu');
    await page.keyboard.press('Enter');

    await expect(pieza(page, /^Variable Titular/)).toHaveAttribute('aria-expanded', 'false');
    await expect(editor(page).locator('[data-tramo="2"]')).toBeFocused();
    await expect.poll(() => ultimaValidacion(motor)).toEqual({ nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [] }] });
  });

  test('un contexto que sí admite funciones queda igual: «Agregar función» y sin la nota', async ({ page }) => {
    await abrir(page, { expresion: conTitular(), extra: '&sinFunciones=1' });
    await pieza(page, /^Variable Titular/).click();
    await expect(botonFuncion(page)).toBeVisible();
    await expect(editor(page).locator('[data-sin-funciones]')).toHaveCount(0);
    // Y «Insertar variable» sigue abriendo el panel de la pieza, con el foco en «Agregar función».
    await abrir(page);
    await editor(page).getByRole('button', { name: 'Insertar variable', exact: true }).click();
    await page.keyboard.type('titu');
    await page.keyboard.press('Enter');
    await expect(botonFuncion(page)).toBeFocused();
  });
});

test.describe('un contexto sin funciones: la vista previa y el panel (T-HI-F15)', () => {
  const sinFunciones = (motor: ApiFalsaTextoEnriquecido) => {
    motor.catalogos['mowa_mes.speech'].contexto.admite_funciones = false;
  };

  test('la vista previa no informa el dato vacío de una variable en ese contexto', async ({ page }) => {
    await abrir(page, {
      expresion: { nodos: [{ tipo: 'texto', valor: 'Hola ' }, { tipo: 'variable', nombre: 'fecha_vencimiento_cuota', funciones: [] }] },
      extra: '&sinFunciones=1',
      ajustar: (motor) => {
        sinFunciones(motor);
        delete motor.catalogos['mowa_mes.speech'].contexto.ejemplo.fecha_vencimiento_cuota;
      },
    });
    await expect(resultado(page)).toContainText('Hola');
    await expect(editor(page).locator('.editor-texto__datos .field__hint')).toHaveCount(0);

    // En un contexto que sí admite funciones, el mismo dato vacío sí se informa.
    await abrir(page, {
      expresion: { nodos: [{ tipo: 'texto', valor: 'Hola ' }, { tipo: 'variable', nombre: 'fecha_vencimiento_cuota', funciones: [] }] },
      ajustar: (motor) => {
        delete motor.catalogos['mowa_mes.speech'].contexto.ejemplo.fecha_vencimiento_cuota;
      },
    });
    await expect(editor(page).locator('.editor-texto__datos .field__hint')).toHaveCount(1);
  });

  test('en un contexto que admite funciones el panel conserva «Obligatoria» y el resultado de la pieza', async ({ page }) => {
    await abrir(page, { expresion: { nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [] }] } });
    await pieza(page, /^Variable Titular/).click();
    await expect(editor(page).getByRole('checkbox', { name: 'Obligatoria' })).toBeVisible();
    await expect(editor(page).getByText('Resultado con el registro')).toBeVisible();
  });
});

test.describe('una variable que el contexto no conoce (T-HI-F15)', () => {
  const DESCONOCIDA = {
    nodos: [{ tipo: 'texto', valor: 'Hola ' }, { tipo: 'variable', nombre: 'macro1', funciones: [] }, { tipo: 'texto', valor: '.' }],
  };
  const conProblema = (motor: ApiFalsaTextoEnriquecido) => {
    motor.validacion = () => ({
      problemas: [problema('variable_desconocida', { nodo: 1, funcion: null, parametro: null })],
      tipo: 'texto', cota: 170, sin_cota: null, variables: [],
    });
  };

  test('su píldora dice el nombre técnico tal cual, en sans, con el ícono y el estado de error, y su nombre accesible lo dice', async ({ page }) => {
    await abrir(page, { expresion: DESCONOCIDA, ajustar: conProblema });
    const p = editor(page).locator('[data-pieza]');
    await expect(p).toHaveText('macro1');
    await expect(p).toHaveAccessibleName(/^macro1, no existe en este contexto\. Abre sus funciones/);
    await expect(p).toHaveClass(/editor-texto__pieza--problema/);
    await expect(p.locator('svg')).toHaveCount(1);
    // La misma letra que las demás píldoras: sans, no mono.
    const fuente = await p.evaluate((boton) => getComputedStyle(boton).fontFamily);
    expect(fuente).toMatch(/Inter/);
    expect(fuente).not.toMatch(/JetBrains|monospace/);
  });

  test('está en error aunque el backend todavía no haya dicho nada', async ({ page }) => {
    await abrir(page, { expresion: DESCONOCIDA });
    await expect(editor(page).locator('[data-pieza]')).toHaveClass(/editor-texto__pieza--problema/);
    await expect(editor(page).locator('[data-pieza]')).toHaveAccessibleName(/no existe en este contexto/);
  });

  test('una variable que sí existe no cambia: su nombre visible y su nombre accesible de siempre', async ({ page }) => {
    await abrir(page, { expresion: { nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [] }] } });
    await expect(pieza(page, /^Variable Titular\. Abre sus funciones/)).toHaveText('Titular');
    await expect(pieza(page, /no existe/)).toHaveCount(0);
  });

  test('con nombreDesconocida, la píldora y su panel dicen lo que la página devuelve', async ({ page }) => {
    await abrir(page, { expresion: DESCONOCIDA, ajustar: conProblema, extra: '&nombreDesconocida=1' });
    const p = editor(page).locator('[data-pieza]');
    await expect(p).toHaveText('macro MACRO1');
    await expect(p).toHaveAccessibleName(/^macro MACRO1, no existe en este contexto/);
    await p.click();
    await expect(editor(page).getByRole('heading', { name: 'macro MACRO1' })).toBeVisible();
  });

  test('sale solo como su problema en el resumen, con el texto del código, y no como «falta el dato de…»', async ({ page }) => {
    await abrir(page, { expresion: DESCONOCIDA, ajustar: conProblema });
    await expect(editor(page).locator('[data-resumen]')).toContainText('Hay 1 problema en el texto.');
    await expect(editor(page).locator('[data-resumen-lista]')).toContainText('Esta variable no existe en este contexto. Elige otra de la lista.');
    // El nodo viene vacío (la variable no existe en el registro de ejemplo), y aun así no hay hint de dato vacío.
    await expect(editor(page).locator('.editor-texto__datos .field__hint')).toHaveCount(0);
  });

  test('«Ir al problema» lleva a su píldora', async ({ page }) => {
    await abrir(page, { expresion: DESCONOCIDA, ajustar: conProblema });
    await editor(page).locator('[data-resumen]').getByRole('button', { name: 'Ir al problema' }).click();
    await expect(editor(page).locator('[data-pieza]')).toBeFocused();
  });
});

test.describe('el editor sin vista previa (T-HI-F15)', () => {
  test('con vistaPrevia en false oculta el título, el control de muestra, el resultado y los hints, y deja el contador', async ({ page }) => {
    await abrir(page, {
      expresion: SPEECH,
      extra: '&vistaPrevia=0',
      ajustar: (motor) => {
        delete motor.catalogos['mowa_mes.speech'].contexto.ejemplo.fecha_vencimiento_cuota;
      },
    });
    await expect(editor(page).locator('[data-largo-texto]')).toHaveText(/^\d+ \/ 160 caracteres/);
    await expect(editor(page).getByRole('heading', { name: 'Vista previa' })).toBeHidden();
    await expect(editor(page).getByRole('button', { name: 'Registro de ejemplo' })).toBeHidden();
    await expect(resultado(page)).toBeHidden();
    await expect(editor(page).locator('.editor-texto__datos')).toBeHidden();
  });

  test('el contador sigue su camino: avisa «Pasa el tope» sin que se vea la vista', async ({ page }) => {
    await abrir(page, {
      expresion: SPEECH,
      extra: '&vistaPrevia=0',
      ajustar: (motor) => {
        motor.validacion = () => ({ problemas: [], tipo: 'texto', cota: 170, sin_cota: null, variables: [] });
      },
    });
    await expect(editor(page).locator('.editor-texto__largo .tag')).toHaveText('Pasa el tope');
    await expect(resultado(page)).toBeHidden();
  });

  test('sin la opción, la vista previa se ve como siempre', async ({ page }) => {
    await abrir(page, { expresion: SPEECH });
    await expect(editor(page).getByRole('heading', { name: 'Vista previa' })).toBeVisible();
    await expect(resultado(page)).toBeVisible();
  });
});

test.describe('las funciones (§13.4)', () => {
  const unaPieza = (funciones: unknown[] = []) => ({
    expresion: { nodos: [{ tipo: 'variable', nombre: 'titular', funciones }] },
  });
  const campoFuncion = (page: Page) => editor(page).getByRole('combobox', { name: 'Buscar función' });

  test('«Agregar función» es un botón que abre una lista con su campo, agrupada por familia y con la descripción', async ({ page }) => {
    await abrir(page, unaPieza());
    await pieza(page, /^Variable Titular/).click();
    await expect(botonFuncion(page)).toHaveAttribute('aria-expanded', 'false');
    await botonFuncion(page).click();

    await expect(botonFuncion(page)).toHaveAttribute('aria-expanded', 'true');
    await expect(campoFuncion(page)).toBeFocused();
    await expect(campoFuncion(page)).toHaveAttribute('aria-controls', (await listaFunciones(page).getAttribute('id')) ?? '');
    const primera = (await listaFunciones(page).getByRole('option').first().getAttribute('id')) ?? '';
    await expect(campoFuncion(page)).toHaveAttribute('aria-activedescendant', primera);
    // Texto (tipo de titular): sus tres funciones, por familia; las de fecha o número no se ofrecen.
    await expect(editor(page).locator('.selector-funcion .selector-variable__tema')).toHaveText(['Texto', 'Valores vacíos', 'Enlaces']);
    const mayusculas = listaFunciones(page).getByRole('option', { name: /^Mayúsculas/ });
    await expect(mayusculas.locator('.selector-funcion__descripcion')).toHaveText('Pasa el texto a mayúsculas. ana ruiz → ANA RUIZ.');
    await expect(listaFunciones(page).getByRole('option', { name: /^Redondear/ })).toHaveCount(0);
  });

  test('las funciones sin parámetro muestran su resultado con el ejemplo de la pieza, antes de elegirla; las que piden uno, no', async ({ page }) => {
    await abrir(page, unaPieza([{ nombre: 'primeros', args: [8] }]));
    await pieza(page, /^Variable Titular/).click();
    await botonFuncion(page).click();

    // El resultado parte de la cadena de la pieza: primeros 8, y la función que se vería.
    await expect(listaFunciones(page).getByRole('option', { name: /^Mayúsculas/ }).locator('.selector-variable__ejemplo')).toHaveText('Mayúsculas → NOMBRE S');
    await expect(listaFunciones(page).getByRole('option', { name: /^Quitar tildes/ }).locator('.selector-variable__ejemplo')).toHaveText('Quitar tildes → NOMBRE S');
    await expect(listaFunciones(page).getByRole('option', { name: /^Primeros caracteres/ }).locator('.selector-variable__ejemplo')).toHaveCount(0);
  });

  test('escribir filtra, las flechas mueven y Enter agrega al final de la cadena con el foco en su primer parámetro', async ({ page }) => {
    const { motor } = await abrir(page, unaPieza());
    await pieza(page, /^Variable Titular/).click();
    await botonFuncion(page).click();
    await page.keyboard.type('prim');

    await expect(listaFunciones(page).getByRole('option')).toHaveCount(1);
    await expect(editor(page).locator('.selector-funcion .selector-variable__tema')).toHaveText(['Texto']);
    await page.keyboard.press('Enter');

    await expect(editor(page).getByRole('textbox', { name: 'Cantidad de caracteres' })).toBeFocused();
    await expect(listaFunciones(page)).toHaveCount(0);
    await expect.poll(() => ultimaValidacion(motor)).toMatchObject({
      nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'primeros' }] }],
    });
  });

  test('las flechas recorren la lista y Enter elige la resaltada', async ({ page }) => {
    const { motor } = await abrir(page, unaPieza());
    await pieza(page, /^Variable Titular/).click();
    await botonFuncion(page).click();
    const segunda = (await listaFunciones(page).getByRole('option').nth(1).getAttribute('id')) ?? '';
    await page.keyboard.press('ArrowDown');
    await expect(campoFuncion(page)).toHaveAttribute('aria-activedescendant', segunda);
    await expect(page.locator(`#${segunda}`)).toHaveAttribute('aria-selected', 'true');
    await page.keyboard.press('Enter');
    await expect
      .poll(() => (ultimaValidacion(motor) as { nodos: Array<{ funciones: Array<{ nombre: string }> }> } | undefined)?.nodos[0]?.funciones[0]?.nombre)
      .toBe(segunda.split('-opcion-')[1]);
  });

  test('sin coincidencias lo dice y Enter no agrega nada; Escape cierra y devuelve el foco al botón sin agregar', async ({ page }) => {
    const { motor } = await abrir(page, unaPieza());
    await pieza(page, /^Variable Titular/).click();
    await botonFuncion(page).click();
    await page.keyboard.type('zzzz');
    await expect(editor(page).getByText('Ninguna variable coincide con «zzzz».')).toBeVisible();
    await page.keyboard.press('Enter');
    await expect(campoFuncion(page)).toBeFocused();

    await page.keyboard.press('Escape');
    await expect(campoFuncion(page)).toHaveCount(0);
    await expect(botonFuncion(page)).toBeFocused();
    await expect(botonFuncion(page)).toHaveAttribute('aria-expanded', 'false');
    // Escape no cerró el panel de la pieza.
    await expect(editor(page).getByRole('button', { name: 'Quitar variable' })).toBeVisible();
    await expect.poll(() => ultimaValidacion(motor)).toEqual({ nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [] }] });
  });

  test('a 360 px los botones de una función mantienen su tamaño y pasan a una fila propia bajo el título, a la derecha', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await abrir(page, unaPieza([{ nombre: 'primeros', args: [8] }]));
    await pieza(page, /^Variable Titular/).click();

    const g = await page.evaluate(() => {
      const caja = (e: Element) => e.getBoundingClientRect();
      const cabeza = document.querySelector('.editor-texto__funcionCabeza')!;
      const titulo = caja(cabeza.querySelector('.editor-texto__funcionNombre')!);
      const botones = [...cabeza.querySelectorAll('.editor-texto__funcionAcciones .btn')].map(caja);
      return {
        cabeza: caja(cabeza),
        // El título cabe en una línea: su alto es el de una línea de texto, no de dos.
        tituloLineas: Math.round(titulo.height / parseFloat(getComputedStyle(cabeza.querySelector('.editor-texto__funcionNombre')!).lineHeight)),
        titulo,
        botones: botones.map((b) => ({ ancho: Math.round(b.width), alto: Math.round(b.height), arriba: b.top, derecha: b.right })),
        pagina: document.documentElement.scrollWidth,
      };
    });
    expect(g.tituloLineas).toBe(1);
    // Los tres botones conservan su tamaño de botón (2,5 rem = 40 px) y quedan en una fila bajo el título.
    expect(g.botones).toHaveLength(3);
    for (const b of g.botones) {
      expect(b.ancho).toBe(40);
      expect(b.alto).toBe(40);
      expect(b.arriba).toBeGreaterThanOrEqual(g.titulo.bottom - 1);
    }
    // Alineados a la derecha de la fila, sin salirse de ella.
    expect(Math.abs(Math.max(...g.botones.map((b) => b.derecha)) - g.cabeza.right)).toBeLessThanOrEqual(1);
    expect(g.pagina).toBeLessThanOrEqual(360);
  });

  test('a 1280 px los botones siguen en la misma fila que el título', async ({ page }) => {
    await abrir(page, unaPieza([{ nombre: 'primeros', args: [8] }]));
    await pieza(page, /^Variable Titular/).click();
    const g = await page.evaluate(() => {
      const cabeza = document.querySelector('.editor-texto__funcionCabeza')!;
      const titulo = cabeza.querySelector('.editor-texto__funcionNombre')!.getBoundingClientRect();
      const boton = cabeza.querySelector('.editor-texto__funcionAcciones .btn')!.getBoundingClientRect();
      return { tituloArriba: titulo.top, botonArriba: boton.top, botonAbajo: boton.bottom, tituloAbajo: titulo.bottom };
    });
    expect(g.botonArriba).toBeLessThan(g.tituloAbajo);
  });

  test('un clic en una función la agrega, y salir de la lista con Tab la cierra', async ({ page }) => {
    await abrir(page, unaPieza());
    await pieza(page, /^Variable Titular/).click();
    await botonFuncion(page).click();
    // La lista no es un destino del teclado: un Tab desde el campo sale de la búsqueda y la cierra.
    await page.keyboard.press('Tab');
    await expect(listaFunciones(page)).toHaveCount(0);
    await expect(editor(page).getByRole('checkbox', { name: 'Obligatoria' })).toBeFocused();

    await agregarFuncion(page, /^Mayúsculas/);
    await expect(pieza(page, /^Variable Titular/)).toHaveText('Titular · mayúsculas');
  });

  test('los resultados salen de UNA sola petición, con un nodo por función sin parámetro', async ({ page }) => {
    const { motor } = await abrir(page, unaPieza([{ nombre: 'primeros', args: [8] }]));
    await pieza(page, /^Variable Titular/).click();
    const vistas = () => motor.pedidos.filter((p) => p.ruta === '/texto-enriquecido/previsualizacion').length;
    await expect.poll(vistas).toBeGreaterThan(0);
    await page.waitForTimeout(700);
    const antes = vistas();

    await botonFuncion(page).click();
    await expect(listaFunciones(page).getByRole('option', { name: /^Mayúsculas/ }).locator('.selector-variable__ejemplo')).toBeVisible();
    expect(vistas()).toBe(antes + 1);
    const lote = motor.pedidos.filter((p) => p.ruta === '/texto-enriquecido/previsualizacion').at(-1)?.cuerpo as {
      expresion: { nodos: Array<{ nombre: string; funciones: Array<{ nombre: string }> }> };
    };
    // Una variable con la cadena de la pieza más la función de cada fila que no pide parámetro (no «Primeros caracteres»).
    expect(lote.expresion.nodos.every((n) => n.nombre === 'titular' && n.funciones[0].nombre === 'primeros')).toBe(true);
    expect(lote.expresion.nodos.map((n) => n.funciones.at(-1)!.nombre).sort()).toEqual(['enlace_whatsapp', 'mayusculas', 'sin_tildes']);
  });

  test('si un nodo falla, solo su fila queda sin resultado y la lista sigue sirviendo', async ({ page }) => {
    await abrir(page, {
      ...unaPieza(),
      ajustar: (motor) => {
        const original = motor.previsualizacion;
        motor.previsualizacion = (cuerpo, catalogo) => {
          const respuesta = original(cuerpo, catalogo);
          if ('estado' in respuesta) return respuesta;
          const nodos = (cuerpo.expresion?.nodos ?? []) as Array<{ funciones?: Array<{ nombre: string }> }>;
          const indice = nodos.findIndex((n) => n.funciones?.some((f) => f.nombre === 'mayusculas'));
          if (indice >= 0) respuesta.filas[0].columnas[0].problemas.push(problema('parametro_invalido', { nodo: indice, funcion: 0, parametro: null }));
          return respuesta;
        };
      },
    });
    await pieza(page, /^Variable Titular/).click();
    await botonFuncion(page).click();
    await expect(listaFunciones(page).getByRole('option', { name: /^Quitar tildes/ }).locator('.selector-variable__ejemplo')).toHaveCount(1);
    await expect(listaFunciones(page).getByRole('option', { name: /^Mayúsculas/ }).locator('.selector-variable__ejemplo')).toHaveCount(0);
    await listaFunciones(page).getByRole('option', { name: /^Mayúsculas/ }).click();
    await expect(pieza(page, /^Variable Titular/)).toHaveText('Titular · mayúsculas');
  });

  test('si toda la petición falla, ninguna fila lleva resultado y la lista sigue sirviendo', async ({ page }) => {
    await abrir(page, {
      ...unaPieza(),
      ajustar: (motor) => {
        const original = motor.previsualizacion;
        motor.previsualizacion = (cuerpo, catalogo) =>
          (cuerpo.expresion?.nodos ?? []).length > 1 ? { estado: 500, cuerpo: { detail: 'falla' } } : original(cuerpo, catalogo);
      },
    });
    await pieza(page, /^Variable Titular/).click();
    await botonFuncion(page).click();
    await expect(listaFunciones(page).getByRole('option').first()).toBeVisible();
    await expect(listaFunciones(page).locator('.selector-variable__ejemplo')).toHaveCount(0);
    await listaFunciones(page).getByRole('option', { name: /^Quitar tildes/ }).click();
    await expect(pieza(page, /^Variable Titular/)).toHaveText('Titular · quitar tildes');
  });

  const conProblemaEn = (funcion: string, parametro: string, args: unknown[]) => ({
    expresion: { nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [{ nombre: funcion, args }] }] },
    ajustar: (motor: ApiFalsaTextoEnriquecido) => {
      motor.validacion = () => ({
        problemas: [problema('parametro_invalido', { nodo: 0, funcion: 0, parametro })],
        tipo: 'texto', cota: 170, sin_cota: null, variables: [],
      });
    },
  });
  const parametroDe = (motor: ApiFalsaTextoEnriquecido, funcion: string) =>
    motor.catalogos['mowa_mes.speech'].funciones.find((f) => f.nombre === funcion)!.parametros[0];

  for (const [nombre, minimo, maximo, mensaje] of [
    ['con mínimo y máximo', 0, 6, 'Escribe un número entre 0 y 6.'],
    ['solo con mínimo', 1, null, 'Escribe un número de 1 en adelante.'],
    ['solo con máximo', null, 100, 'Escribe un número hasta 100.'],
  ] as const) {
    test(`el error de un parámetro numérico ${nombre} dice su rango, en su lugar y en el resumen`, async ({ page }) => {
      const caso = conProblemaEn('primeros', 'n', [-5]);
      await abrir(page, {
        ...caso,
        ajustar: (motor) => {
          caso.ajustar(motor);
          Object.assign(parametroDe(motor, 'primeros'), { minimo, maximo });
        },
      });
      await pieza(page, /^Variable Titular/).click();
      await expect(editor(page).locator('[data-error-parametro="0:n"]')).toHaveText(mensaje);
      await expect(editor(page).locator('[data-resumen-lista]')).toContainText(mensaje);
      await expect(editor(page).getByRole('textbox', { name: 'Cantidad de caracteres' })).toHaveAttribute('aria-invalid', 'true');
    });
  }

  test('un texto exigido y vacío dice «Escribe Inicio del enlace.»', async ({ page }) => {
    const caso = conProblemaEn('enlace_whatsapp', 'prefijo', ['']);
    await abrir(page, {
      ...caso,
      ajustar: (motor) => {
        caso.ajustar(motor);
        Object.assign(parametroDe(motor, 'enlace_whatsapp'), { obligatorio: true, por_defecto: null });
      },
    });
    await pieza(page, /^Variable Titular/).click();
    await expect(editor(page).locator('[data-error-parametro="0:prefijo"]')).toHaveText('Escribe Inicio del enlace.');
  });

  test('un parámetro sin rango en el catálogo deja el mensaje genérico', async ({ page }) => {
    const caso = conProblemaEn('primeros', 'n', ['x']);
    await abrir(page, {
      ...caso,
      ajustar: (motor) => {
        caso.ajustar(motor);
        Object.assign(parametroDe(motor, 'primeros'), { minimo: null, maximo: null });
      },
    });
    await pieza(page, /^Variable Titular/).click();
    await expect(editor(page).locator('[data-error-parametro="0:n"]')).toContainText('debe ser del tipo que se pide');
  });

  test('el panel nombra su pieza, con la posición si la variable está más de una vez, y la píldora abierta se marca', async ({ page }) => {
    await abrir(page, {
      expresion: {
        nodos: [
          { tipo: 'variable', nombre: 'titular', funciones: [] },
          { tipo: 'texto', valor: ' y ' },
          { tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'mayusculas', args: [] }] },
          { tipo: 'texto', valor: ' y ' },
          { tipo: 'variable', nombre: 'telefono', funciones: [] },
        ],
      },
    });
    const pildoras = editor(page).locator('[data-pieza]');
    await pildoras.nth(1).click();
    await expect(editor(page).getByRole('heading', { name: 'Titular (2.ª vez)' })).toBeVisible();
    await expect(pildoras.nth(1)).toHaveAttribute('aria-expanded', 'true');
    await expect(pildoras.nth(0)).toHaveAttribute('aria-expanded', 'false');

    await pildoras.nth(0).click();
    await expect(editor(page).getByRole('heading', { name: 'Titular (1.ª vez)' })).toBeVisible();
    // Una variable que aparece una sola vez no lleva posición.
    await pildoras.nth(2).click();
    await expect(editor(page).getByRole('heading', { name: 'Teléfono', exact: true })).toBeVisible();
  });
});

test.describe('el buscador por tema (§13.3)', () => {
  const tramo = (page: Page, indice: number) => editor(page).locator(`[data-tramo="${indice}"]`);
  const buscador = (page: Page) => editor(page).getByRole('listbox', { name: 'Elegir una variable' });
  const temas = (page: Page) => editor(page).locator('.selector-variable__tema');
  const abrirPorBoton = (page: Page) => editor(page).getByRole('button', { name: 'Insertar variable', exact: true }).click();
  const abrirPorDisparador = async (page: Page) => {
    await tramo(page, 0).click();
    await page.keyboard.type('[@');
  };
  type Variable = Esquemas['VariableRespuesta'];
  const variable = (nombre: string, tema: string, cambios: Partial<Variable> = {}): Variable =>
    ({ nombre, tipo: 'texto', clave_nombre: null, origen: 'cartera', etiqueta: null, adicional: false, archivado: false, tema, ...cambios }) as Variable;

  for (const [como, abrirBuscador] of [
    ['desde el botón', abrirPorBoton],
    ['por [@', abrirPorDisparador],
  ] as const) {
    test(`${como}: la lista se agrupa por tema, no por origen, y cada fila trae el ejemplo`, async ({ page }) => {
      await abrir(page);
      await abrirBuscador(page);

      // Las variables del módulo (WhatsApp, días ajustados) entran en su tema, no en un grupo aparte.
      await expect(temas(page)).toHaveText(['Persona y contacto', 'Cuota y deuda', 'Fechas y atraso']);
      const persona = buscador(page).getByRole('group', { name: 'Persona y contacto' });
      await expect(persona.getByRole('option')).toHaveCount(4);
      await expect(persona.getByRole('option', { name: /^WhatsApp de contacto/ })).toHaveCount(1);
    });
  }

  test('los ocho temas salen en el orden de §13.3 y un campo con un tema desconocido cae en Otros', async ({ page }) => {
    await abrir(page, {
      ajustar: (motor) => {
        motor.catalogos['mowa_mes.speech'].contexto.variables.unshift(
          variable('campo_nuevo', 'inventado'),
          variable('segmento_actual', 'riesgo'),
          variable('agencia', 'gestion'),
          variable('pagare', 'credito'),
          ...variablesAdicionalesSinteticas(),
        );
      },
    });
    await abrirPorBoton(page);

    await expect(temas(page)).toHaveText([
      'Persona y contacto',
      'Cuota y deuda',
      'Fechas y atraso',
      'Crédito',
      'Gestión y asignación',
      'Riesgo y segmentos',
      'Campos adicionales',
      'Otros',
    ]);
    await expect(buscador(page).getByRole('group', { name: 'Otros' }).getByRole('option')).toHaveCount(1);
    // El archivado no se ofrece.
    await expect(buscador(page).getByRole('option', { name: /^Región/ })).toHaveCount(0);
  });

  test('cada fila trae el tag de tipo y el valor de ejemplo, formateado; el nombre técnico queda en el title', async ({ page }) => {
    await abrir(page);
    await abrirPorBoton(page);
    const fila = (nombre: RegExp) => buscador(page).getByRole('option', { name: nombre });

    await expect(fila(/^Titular/).locator('.tag')).toHaveText('texto');
    await expect(fila(/^Titular/).locator('.selector-variable__ejemplo')).toHaveText('NOMBRE SINTETICO DE PRUEBA');
    await expect(fila(/^Titular/)).toHaveAttribute('title', 'titular');
    await expect(fila(/^Vencimiento/).locator('.tag')).toHaveText('fecha');
    await expect(fila(/^Vencimiento/).locator('.selector-variable__ejemplo')).toHaveText('05/10/2026');
    await expect(fila(/^Saldo de capital pendiente/).locator('.selector-variable__ejemplo')).toHaveText('1500.50');
    await expect(fila(/^Cliente fallecido/).locator('.tag')).toHaveText('sí/no');
    await expect(fila(/^Cliente fallecido/).locator('.selector-variable__ejemplo')).toHaveText('No');
    // El nombre técnico ya no está escrito en la fila.
    await expect(fila(/^Titular/)).not.toContainText('titular');
  });

  test('una variable sin ejemplo en el contexto no lleva el valor', async ({ page }) => {
    await abrir(page, {
      ajustar: (motor) => {
        motor.catalogos['mowa_mes.speech'].contexto.variables.push(...variablesAdicionalesSinteticas());
      },
    });
    await abrirPorBoton(page);
    await expect(buscador(page).getByRole('option', { name: /^Zona/ }).locator('.selector-variable__ejemplo')).toHaveCount(0);
  });

  test('se busca por el nombre técnico, aunque no se vea, y con texto los temas vacíos se ocultan', async ({ page }) => {
    await abrir(page);
    await abrirPorBoton(page);
    await page.keyboard.type('fecha_venc');

    await expect(buscador(page).getByRole('option')).toHaveCount(1);
    await expect(buscador(page).getByRole('option', { name: /^Vencimiento/ })).toBeVisible();
    await expect(temas(page)).toHaveText(['Fechas y atraso']);
  });

  test('las flechas recorren la lista en el orden en que se lee, tema por tema', async ({ page }) => {
    const { motor } = await abrir(page);
    await abrirPorDisparador(page);
    // Persona (4): la primera ya está resaltada; la quinta es la de «Cuota y deuda».
    for (let i = 0; i < 4; i += 1) await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');
    await expect.poll(() => ultimaValidacion(motor)).toMatchObject({ nodos: [{ tipo: 'variable', nombre: 'saldo_capital_pendiente' }] });
  });

  test('la línea de alcance sale al pie cuando el contexto la trae, y no cuando no', async ({ page }) => {
    await abrir(page, {
      ajustar: (motor) => {
        motor.catalogos['mowa_mes.speech'].contexto.clave_alcance = 'pruebas.alcance';
      },
    });
    await abrirPorBoton(page);
    const alcance = buscador(page).locator('xpath=..').locator('.selector-variable__alcance');
    await expect(alcance).toHaveText('Alcance de prueba: este contexto no ofrece todo.');
    await expect(alcance).toHaveClass(/field__hint/);
    await page.keyboard.press('Escape');

    // Sin alcance (Columnas ofrece todo; MOWA, con la parte 2 de B7): ninguna línea, en los dos modos.
    await abrir(page, {
      ajustar: (motor) => {
        motor.catalogos['mowa_mes.speech'].contexto.clave_alcance = null;
      },
    });
    await abrirPorBoton(page);
    await expect(buscador(page)).toBeVisible();
    await expect(editor(page).locator('.selector-variable__alcance')).toHaveCount(0);
    await page.keyboard.press('Escape');
    await abrirPorDisparador(page);
    await expect(buscador(page)).toBeVisible();
    await expect(editor(page).locator('.selector-variable__alcance')).toHaveCount(0);
  });

  test('en Columnas (contexto cartera) no hay línea de alcance', async ({ page }) => {
    await abrir(page, { extra: '&contexto=cartera' });
    await abrirPorBoton(page);
    await expect(buscador(page)).toBeVisible();
    await expect(editor(page).locator('.selector-variable__alcance')).toHaveCount(0);
  });

  test('en inglés los temas salen en inglés', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ theme: 'light', language: 'en' }));
    });
    await abrir(page);
    await editor(page).getByRole('button', { name: 'Insert variable', exact: true }).click();
    await expect(temas(page)).toHaveText(['Person and contact', 'Instalment and debt', 'Dates and days overdue']);
    await expect(
      editor(page).getByRole('listbox', { name: 'Choose a variable' }).getByRole('option', { name: /^Deceased client/ }).locator('.selector-variable__ejemplo'),
    ).toHaveText('No');
  });
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
    await expect(editor(page).getByRole('button', { name: 'Insertar variable', exact: true })).toBeHidden();
    await expect(editor(page).locator('[data-pista-disparador]')).toBeHidden();

    const variable = editor(page).getByRole('combobox', { name: 'Texto del mensaje' });
    await expect(variable).toHaveAccessibleDescription('Conserva el valor original, sin pasarlo por texto.');
    await variable.selectOption({ label: 'Vencimiento de la cuota (fecha)' });
    await agregarFuncion(page, /^Sumar días/);
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

    test('editor con el buscador de variables abierto por [@', async ({ page }) => {
      await abrir(page, { expresion: SPEECH });
      await editor(page).getByRole('textbox', { name: 'Texto al final' }).pressSequentially('[@');
      await expect(editor(page).getByRole('listbox', { name: 'Elegir una variable' })).toBeVisible();
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

    test('panel de una pieza en un contexto sin funciones, con su texto y su enlace', async ({ page }) => {
      await abrir(page, {
        expresion: { nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [] }] },
        extra: '&sinFunciones=1',
        ajustar: (motor) => {
          motor.catalogos['mowa_mes.speech'].contexto.admite_funciones = false;
        },
      });
      await pieza(page, /^Variable Titular/).click();
      await expect(editor(page).locator('[data-sin-funciones] a')).toBeVisible();
      await sinViolaciones(page);
    });

    for (const ancho of [1280, 360] as const) {
      test(`editor con la lista de funciones abierta, a ${ancho} px`, async ({ page }) => {
        await page.setViewportSize({ width: ancho, height: 800 });
        await abrir(page, { expresion: SPEECH });
        await pieza(page, /^Variable Titular/).click();
        await botonFuncion(page).click();
        await expect(listaFunciones(page)).toBeVisible();
        // Con los resultados ya pintados: la fila final es la que se mide.
        await expect(listaFunciones(page).locator('.selector-variable__ejemplo').first()).toContainText('→');
        await sinViolaciones(page);
        const pagina = await page.evaluate(() => document.documentElement.scrollWidth);
        expect(pagina).toBeLessThanOrEqual(ancho);
      });
    }

    test('editor con la vista previa pendiente: la respuesta no llega y el texto conserva su contraste', async ({ page }) => {
      const { motor } = await abrir(page, { expresion: SPEECH });
      await expect(resultado(page)).toContainText('Hola NOMBRE S');
      // Desde aquí la previsualización no responde: la petición queda abierta y la vista, en espera.
      await page.route('**/texto-enriquecido/previsualizacion', () => undefined);
      await editor(page).getByRole('textbox', { name: 'Texto al final' }).fill('. Gracias.');
      await expect(resultado(page)).toHaveClass(/editor-texto__resultado--pendiente/);
      await expect.poll(() => motor.pedidos.filter((p) => p.ruta === '/texto-enriquecido/validacion').length).toBeGreaterThan(1);
      await page.waitForTimeout(600);
      await expect(resultado(page)).toHaveClass(/editor-texto__resultado--pendiente/);
      await sinViolaciones(page);
    });

    test('editor con una variable que el contexto no conoce, con su panel abierto', async ({ page }) => {
      await abrir(page, {
        expresion: { nodos: [{ tipo: 'texto', valor: 'Hola ' }, { tipo: 'variable', nombre: 'macro1', funciones: [] }, { tipo: 'texto', valor: '.' }] },
        ajustar: (motor) => {
          motor.validacion = () => ({
            problemas: [problema('variable_desconocida', { nodo: 1, funcion: null, parametro: null })],
            tipo: 'texto', cota: 170, sin_cota: null, variables: [],
          });
        },
      });
      await expect(editor(page).locator('[data-resumen]')).toBeVisible();
      await editor(page).locator('[data-pieza]').click();
      await sinViolaciones(page);
    });

    test('panel de una pieza en un contexto sin funciones, solo con su aviso, su enlace y quitar', async ({ page }) => {
      await abrir(page, {
        expresion: { nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [] }] },
        extra: '&sinFunciones=1&vistaPrevia=0',
        ajustar: (motor) => {
          motor.catalogos['mowa_mes.speech'].contexto.admite_funciones = false;
        },
      });
      await pieza(page, /^Variable Titular/).click();
      await expect(editor(page).getByRole('checkbox', { name: 'Obligatoria' })).toHaveCount(0);
      await sinViolaciones(page);
    });

    test('editor con un error de rango en un parámetro', async ({ page }) => {
      await abrir(page, {
        expresion: SPEECH,
        ajustar: (motor) => {
          motor.validacion = () => ({
            problemas: [problema('parametro_invalido', { nodo: 1, funcion: 0, parametro: 'n' })],
            tipo: 'texto', cota: 170, sin_cota: null, variables: [],
          });
          Object.assign(motor.catalogos['mowa_mes.speech'].funciones.find((f) => f.nombre === 'primeros')!.parametros[0], { minimo: 1, maximo: 50 });
        },
      });
      await pieza(page, /^Variable Titular/).click();
      await expect(editor(page).locator('[data-error-parametro="0:n"]')).toHaveText('Escribe un número entre 1 y 50.');
      await sinViolaciones(page);
    });

    test('editor con el buscador de variables abierto desde el botón, con su campo y la línea de alcance', async ({ page }) => {
      await abrir(page, {
        expresion: SPEECH,
        ajustar: (motor) => {
          motor.catalogos['mowa_mes.speech'].contexto.clave_alcance = 'pruebas.alcance';
        },
      });
      await editor(page).getByRole('button', { name: 'Insertar variable', exact: true }).click();
      await expect(editor(page).getByRole('combobox', { name: 'Buscar una variable' })).toBeFocused();
      await expect(editor(page).getByRole('listbox', { name: 'Elegir una variable' })).toBeVisible();
      await pieza(page, /^Variable Vencimiento/).hover();
      await sinViolaciones(page);
    });

    for (const [nombre, abrirBuscador] of [
      ['por [@', async (page: Page) => { await editor(page).locator('[data-tramo="4"]').pressSequentially('[@'); }],
      ['desde el botón', async (page: Page) => { await editor(page).getByRole('button', { name: 'Insertar variable', exact: true }).click(); }],
    ] as const) {
      test(`editor a 360 px con el buscador abierto ${nombre}`, async ({ page }) => {
        await page.setViewportSize({ width: 360, height: 740 });
        await abrir(page, { expresion: SPEECH });
        await abrirBuscador(page);
        await expect(editor(page).getByRole('listbox', { name: 'Elegir una variable' })).toBeVisible();
        await sinViolaciones(page);
        const ancho = await page.evaluate(() => document.documentElement.scrollWidth);
        expect(ancho).toBeLessThanOrEqual(360);
      });
    }
  });
}
