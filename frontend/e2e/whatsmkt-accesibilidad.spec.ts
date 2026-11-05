/**
 * Automated accessibility (WCAG 2.1 A and AA rules of axe-core) on the WhatsMKT screens of T-WM-F1a, in the
 * light and dark themes, at 1280 and 360 px (RF-WM-44), including the states where problems hide: the
 * dropdown open and the errors under a row, a time slot, the name template and a limit.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { apiWhatsmkt, errorWhatsmkt, montarApiWhatsmkt } from './api-falsa-whatsmkt';
import { mensajesFalsos, montarMensajesWhatsmkt } from './api-falsa-whatsmkt-mensajes';
import { campanaFalsa, montarCampanaWhatsmkt } from './api-falsa-whatsmkt-campana';
import { informeFalso, montarSeguimientoWhatsmkt, seguimientoFalso } from './api-falsa-whatsmkt-seguimiento';
import { montarSeleccion } from './apoyo-seleccion';

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

// Contrast measured mid-entrance reads a half-faded paragraph as a failure: with reduced motion every screen
// lands in its final state at once, which is also a real mode the product supports.
test.use({ reducedMotion: 'reduce' });

async function sinViolaciones(page: Page): Promise<void> {
  const resultado = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
  const resumen = resultado.violations.map(
    (v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => `${n.target.join(' ')} ${n.html.slice(0, 160)} → ${(n.failureSummary ?? '').replace(/\s+/g, ' ')}`).join(' | ')}`,
  );
  expect(resumen).toEqual([]);
}

const anchos = [
  ['1280 px', { width: 1280, height: 900 }],
  ['360 px', { width: 360, height: 900 }],
] as const;

for (const tema of ['light', 'dark'] as const) {
  for (const [nombreAncho, tamano] of anchos) {
    test.describe(`WhatsMKT, tema ${tema === 'light' ? 'claro' : 'oscuro'}, ${nombreAncho}`, () => {
      test.beforeEach(async ({ page }) => {
        await page.setViewportSize(tamano);
        await page.addInitScript((elegido) => {
          localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
        }, tema);
        await montarApiWhatsmkt(page, apiWhatsmkt());
        // The settings read the saved messages and the default definition; what a spec registers after this one answers first.
        await montarMensajesWhatsmkt(page, mensajesFalsos());
      });

      test('campaña, sin selección elegida', async ({ page }) => {
        await montarCampanaWhatsmkt(page, campanaFalsa());
        await montarSeleccion(page);
        await page.goto('/whatsmkt/campana');
        await expect(page.getByRole('heading', { name: 'Campaña de WhatsMKT', level: 1 })).toBeVisible();
        await expect(page.locator('[data-guardia]')).toBeVisible();
        await sinViolaciones(page);
      });

      test('campaña, con la previsualización del lote, sus problemas y los productos fuera de las campañas', async ({ page }) => {
        await montarCampanaWhatsmkt(
          page,
          campanaFalsa({
            problemasExtra: [
              { codigo: 'sin_supervisores', detalle: 'Sin supervisores', segmento: null, parametros: {} },
              { codigo: 'sin_whatsapp', detalle: 'Sin WhatsApp', segmento: 'tramo_2', parametros: {} },
            ],
          }),
        );
        await montarSeleccion(page);
        await page.goto('/whatsmkt/campana');
        await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
        // The fixture has no default definition: choosing one is what lets the preview be asked for.
        await page.locator('#wm-definicion').selectOption({ label: 'Contactos WhatsMKT' });
        await page.locator('[data-franja="horario_1"]').check();
        await expect(page.locator('[data-campana]')).toBeVisible();
        await expect(page.locator('[data-fuera]')).toBeVisible();
        await expect(page.locator('[data-previa]')).toHaveAttribute('data-calculando', 'false');
        await sinViolaciones(page);
      });

      test('campaña, con la ficha del lote creado, con su aviso y la subida de un archivo archivado', async ({ page }) => {
        await montarCampanaWhatsmkt(page, campanaFalsa({ avisosFicha: ['sin_whatsapp'] }));
        await montarSeleccion(page);
        await page.goto('/whatsmkt/campana');
        await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
        await page.locator('#wm-definicion').selectOption({ label: 'Contactos WhatsMKT' });
        await page.locator('[data-franja="horario_1"]').check();
        // The fixture's segments own no message: each one that will make a campaign needs its own, or nothing can be created.
        await page.locator('#wm-mensaje-preventivo').selectOption({ label: 'Preventivo' });
        await page.locator('#wm-mensaje-tramo_2').selectOption({ label: 'Tramo 2' });
        // An archived file found again: its status and «Restaurar y usar» are on screen next to the select.
        await page.getByLabel('Texto + archivo').check();
        await page.locator('[data-subir-entrada="adjunto"]').setInputFiles({ name: 'spot-anterior.mp4', mimeType: 'video/mp4', buffer: Buffer.from('sintetico') });
        await expect(page.getByRole('button', { name: 'Restaurar y usar' }).first()).toBeVisible();
        await sinViolaciones(page);
        await page.getByLabel('Solo texto').check();
        await expect(page.locator('[data-crear]')).toBeEnabled();
        await page.locator('[data-crear]').click();
        await expect(page.locator('#wm-sec-ficha')).toBeVisible();
        await expect(page.locator('[data-ficha-avisos]')).toBeVisible();
        await sinViolaciones(page);
      });

      // Back from Columnas de carga (T-WM-F2b): the announcement of the definition chosen, the notice of one that is gone, the error of one that is not WhatsMKT's.
      test('campaña, de vuelta de Columnas con la definición elegida y su anuncio', async ({ page }) => {
        await montarCampanaWhatsmkt(page, campanaFalsa());
        await montarSeleccion(page);
        await page.goto('/whatsmkt/campana?definicion=12&version=1');
        await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
        await expect(page.locator('[data-definicion-anuncio]')).toHaveText('Se eligió «Contactos WhatsMKT con apellido», versión 1.');
        await sinViolaciones(page);
      });

      test('campaña, de vuelta con una definición que ya no existe, con su aviso', async ({ page }) => {
        await montarCampanaWhatsmkt(page, campanaFalsa());
        await montarSeleccion(page);
        await page.goto('/whatsmkt/campana?definicion=99&version=1');
        await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
        await expect(page.locator('[data-definicion-noexiste]')).toBeVisible();
        await sinViolaciones(page);
      });

      test('configuración, recién vuelta de Columnas con la definición elegida y su anuncio', async ({ page }) => {
        await page.goto('/whatsmkt/configuracion?definicion=12&version=1');
        await expect(page.locator('[data-definicion-anuncio]')).toHaveText(
          'Se eligió «Contactos WhatsMKT con apellido», versión 1. Falta guardarla como definición por defecto.',
        );
        await sinViolaciones(page);
      });

      test('configuración, de vuelta con una definición que no es de WhatsMKT, con su error', async ({ page }) => {
        await page.goto('/whatsmkt/configuracion?definicion=13&version=1');
        await expect(page.locator('[data-definicion-error]')).toHaveText('La definición elegida no es de WhatsMKT.');
        await sinViolaciones(page);
      });

      // The report (T-WM-F3b): the reconciliation with a total that differs, the refusal under the field, and the confirmation to replace one.
      test('seguimiento, con la conciliación y el aviso de que el total del informe no coincide', async ({ page }) => {
        const estado = seguimientoFalso();
        estado.campanas.find((c) => c.resumen.id === 36)!.informe = informeFalso(36, { total_informado: 101, filas: 99, coincide_total: false });
        await montarSeguimientoWhatsmkt(page, estado);
        await page.goto('/whatsmkt/seguimiento?campana=36');
        await expect(page.locator('[data-conciliacion-total]')).toBeVisible();
        await expect(page.locator('[data-conciliacion-tablas] table')).toHaveCount(2);
        await sinViolaciones(page);
      });

      test('seguimiento, con el error del informe bajo su campo y el aviso de pendiente', async ({ page }) => {
        const estado = seguimientoFalso();
        estado.respuestas.informe = [{ estado: 422, cuerpo: errorWhatsmkt('informe_sin_encabezados') }];
        await montarSeguimientoWhatsmkt(page, estado);
        await page.goto('/whatsmkt/seguimiento?campana=37');
        // The detail resets the form when it opens: the file is chosen once it is there.
        await expect(page.locator('[data-detalle]')).toBeVisible();
        await page.locator('#wm-informe').setInputFiles({ name: 'informe.xlsx', mimeType: 'application/octet-stream', buffer: Buffer.from('sintetico') });
        await page.getByRole('button', { name: 'Importar informe', exact: true }).click();
        await expect(page.locator('[data-informe-error]')).not.toBeEmpty();
        await expect(page.locator('[data-detalle-pendiente]')).toBeVisible();
        await sinViolaciones(page);
      });

      test('seguimiento, con la confirmación de reemplazar un informe', async ({ page }) => {
        await montarSeguimientoWhatsmkt(page, seguimientoFalso());
        await page.goto('/whatsmkt/seguimiento?campana=36');
        // The detail resets the form when it opens: the file is chosen once it is there.
        await expect(page.locator('[data-detalle]')).toBeVisible();
        await page.locator('#wm-informe').setInputFiles({ name: 'informe.xlsx', mimeType: 'application/octet-stream', buffer: Buffer.from('sintetico') });
        await page.getByRole('button', { name: 'Importar informe', exact: true }).click();
        await expect(page.locator('[data-dialog="confirmar"]')).toBeVisible();
        await sinViolaciones(page);
      });

      test('seguimiento, con la lista que no se pudo actualizar y su aviso para reintentar', async ({ page }) => {
        const estado = seguimientoFalso();
        estado.fallos.lista = [null, { estado: 500, cuerpo: { detail: 'No responde' } }, { estado: 500, cuerpo: { detail: 'No responde' } }];
        await montarSeguimientoWhatsmkt(page, estado);
        await page.goto('/whatsmkt/seguimiento');
        await page.locator('tr[data-campana="37"]').getByRole('button', { name: /^Descartar/ }).click();
        await page.locator('[data-dialog="confirmar"]').getByRole('button', { name: 'Descartar', exact: true }).click();
        await page.locator('[data-dialog="error"]').getByRole('button', { name: 'Cerrar' }).click();
        await expect(page.locator('[data-lista-vieja]')).toBeVisible();
        await sinViolaciones(page);
      });

      test('seguimiento, con la lista y el detalle abierto con sus productos fuera del lote', async ({ page }) => {
        await montarSeguimientoWhatsmkt(page, seguimientoFalso());
        await page.goto('/whatsmkt/seguimiento?campana=37');
        await expect(page.getByRole('heading', { name: 'Seguimiento de WhatsMKT', level: 1 })).toBeVisible();
        await expect(page.locator('[data-detalle]')).toBeVisible();
        await sinViolaciones(page);
        // The folded list open: its table and its pager are on screen too.
        await page.locator('[data-detalle-fuera-titulo]').click();
        await expect(page.locator('[data-detalle-fuera-tabla] tbody tr').first()).toBeVisible();
        await sinViolaciones(page);
      });

      test('seguimiento, con las descartadas y la confirmación de eliminar', async ({ page }) => {
        await montarSeguimientoWhatsmkt(page, seguimientoFalso());
        await page.goto('/whatsmkt/seguimiento?vista=descartadas');
        await expect(page.locator('tr[data-campana="30"]')).toBeVisible();
        await sinViolaciones(page);
        await page.locator('tr[data-campana="30"]').getByRole('button', { name: /^Eliminar definitivamente/ }).click();
        await expect(page.locator('[data-dialog="confirmar"]')).toBeVisible();
        await sinViolaciones(page);
      });

      test('configuración, con todos sus paneles', async ({ page }) => {
        await page.goto('/whatsmkt/configuracion');
        await expect(page.getByLabel('Nombre del segmento Preventivo')).toBeVisible();
        await sinViolaciones(page);
      });

      test('configuración, con los archivados abiertos y los errores del WhatsApp y de la subida', async ({ page }) => {
        await page.goto('/whatsmkt/configuracion');
        await expect(page.getByLabel('Nombre del segmento Preventivo')).toBeVisible();
        // The library fold open, with its table of archived attachments.
        await page.locator('[data-biblioteca-archivados] summary').click();
        await expect(page.getByRole('table', { name: 'Adjuntos archivados' })).toBeVisible();

        await page.locator('#wm-whatsapp').fill('812345678');
        await page.locator('#wm-whatsapp').blur();
        await expect(page.locator('[data-whatsapp-error]')).not.toBeEmpty();

        await page.locator('#wm-adjunto').setInputFiles({ name: 'datos.txt', mimeType: 'text/plain', buffer: Buffer.from('sintetico') });
        await page.getByRole('button', { name: 'Subir un archivo' }).click();
        await expect(page.locator('[data-adjunto-error]')).not.toBeEmpty();

        await sinViolaciones(page);
      });

      test('configuración, con el error de una fila, el de una franja, el del nombre y el de un tope', async ({ page }) => {
        await page.goto('/whatsmkt/configuracion');
        await expect(page.getByLabel('Nombre del segmento Preventivo')).toBeVisible();

        await page.getByLabel('Desde, segmento Tramo 2').fill('0');
        await page.getByRole('button', { name: 'Guardar segmentos' }).click();
        await expect(page.locator('[data-error-fila="tramo_2"]')).toBeVisible();

        await page.locator('#wm-h1-fin').fill('08:00');
        await page.locator('#wm-h1-fin').blur();
        await expect(page.locator('[data-franja="horario_1"] [data-franja-error]')).not.toBeEmpty();

        await page.locator('#wm-plantilla').fill(`${'a'.repeat(64)}{segmento}`);
        await expect(page.locator('[data-plantilla-error]')).not.toBeEmpty();

        // A limit says its error on leaving the field.
        await page.locator('#wm-tope-mensaje').fill('0');
        await page.locator('#wm-tope-mensaje').blur();
        await expect(page.locator('[data-tope-error="tope_mensaje"]')).not.toBeEmpty();

        await sinViolaciones(page);
      });

      test('configuración, con los mensajes: el emoji, la macro que no existe, el tope pasado y la vista previa', async ({ page }) => {
        const api = apiWhatsmkt();
        api.configuracion.definicion_defecto_id = 11;
        api.configuracion.tope_mensaje = 30;
        api.configuracion.whatsapp_contacto = '900000123';
        api.segmentos[0].texto_guardado_id = 101;
        api.segmentos[1].texto_guardado_id = 102;
        await montarApiWhatsmkt(page, api);
        await montarMensajesWhatsmkt(page, mensajesFalsos());
        await page.goto('/whatsmkt/configuracion');
        await expect(page.locator('#wm-mensajes-segmento')).toHaveAttribute('data-montado', 'true');
        await expect(page.getByRole('button', { name: 'MACRO1 · Nombres del titular' }).first()).toBeVisible();
        await expect(page.locator('#wm-msg-segmento-texto')).toHaveValue(/tu cuota vence el/);
        await page.locator('#wm-msg-segmento-texto').fill('Hola 😀 INFO por [whatsapp] y [$MACRO4$]');
        // Leaving the field says the error, and the counter is over the limit.
        await page.locator('#wm-whatsapp').focus();
        await expect(page.locator('#wm-msg-segmento-error')).not.toBeEmpty();
        await expect(page.locator('#wm-msg-segmento-contador')).toHaveAttribute('data-excede', 'true');
        await expect(page.locator('#wm-mensajes-segmento .wm-vista__texto')).toContainText('https://wa.me/+51900000123');
        await sinViolaciones(page);
      });
    });
  }

  test(`el desplegable de WhatsMKT abierto, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, async ({ page }) => {
    await page.addInitScript((elegido) => {
      localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
    }, tema);
    await montarApiWhatsmkt(page, apiWhatsmkt());
    // The settings read the saved messages and the default definition; what a spec registers after this one answers first.
    await montarMensajesWhatsmkt(page, mensajesFalsos());
    // The campaign screen reads the selection, the saved texts and a definition: without them it opens its error dialog.
    await montarCampanaWhatsmkt(page, campanaFalsa());
    await montarSeleccion(page);
    await page.goto('/whatsmkt/campana');

    await page.getByRole('button', { name: 'WhatsMKT' }).click();
    await expect(page.getByRole('link', { name: 'WhatsMKT: campaña' })).toBeVisible();

    await sinViolaciones(page);
  });
}
