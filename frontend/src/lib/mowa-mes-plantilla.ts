/**
 * The file-name template editor of MOWA MES (RF-MM-25), shared by the
 * configuration and the campaign screens: one row of buttons that put a
 * `{variable}` where the cursor is, and the live note for a variable the API
 * did not list. The name a template gives is never worked out here — the API
 * answers it (see `previsualizarPlantillaNombre`).
 */

import type { VariablePlantilla } from './api-mowa-mes';
import { t } from './i18n';
import { insertarVariable, variablesDesconocidas } from './mowa-mes';

/**
 * Fill `host` with one quiet button per variable. Pressing one inserts it at the
 * input's cursor (replacing a selection), puts the focus and the cursor back in
 * the input and fires `input`, so whatever listens to typing also hears it.
 */
export function pintarBotonesDeVariables(
  host: HTMLElement,
  campo: HTMLInputElement,
  variables: readonly VariablePlantilla[],
): void {
  host.replaceChildren(
    ...variables.map((variable) => {
      const boton = document.createElement('button');
      boton.type = 'button';
      boton.className = 'btn btn--sm btn--quiet mono';
      boton.textContent = `{${variable.nombre}}`;
      // The API's own sentence for the variable, as a hover hint.
      boton.title = variable.descripcion;
      boton.addEventListener('click', () => {
        const inicio = campo.selectionStart ?? campo.value.length;
        const fin = campo.selectionEnd ?? inicio;
        const { texto, cursor } = insertarVariable(campo.value, inicio, fin, variable.nombre);
        campo.value = texto;
        campo.focus();
        campo.setSelectionRange(cursor, cursor);
        campo.dispatchEvent(new Event('input', { bubbles: true }));
      });
      return boton;
    }),
  );
}

/** The note for the unknown `{names}` of a template, or `''` when there are none. */
export function notaVariablesDesconocidas(plantilla: string, variables: readonly VariablePlantilla[]): string {
  const desconocidas = variablesDesconocidas(plantilla, variables);
  if (desconocidas.length === 0) return '';
  return t('mowaMes.plantilla.desconocidas', { nombres: desconocidas.map((nombre) => `{${nombre}}`).join(', ') });
}
