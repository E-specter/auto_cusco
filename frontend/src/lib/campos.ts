/**
 * Visible names of the portfolio fields (`campo.<nombre>` in the
 * dictionaries), shared by every screen that lists them: the portfolio
 * filters and product columns, the rich-text editor's variable picker and the
 * column builder.
 *
 * The backend's catalogue gives fields by their technical name and leaves
 * `clave_nombre` empty for the portfolio ones; the label lives here, on the
 * frontend. `tests/nucleo/i18n-campos.test.ts` reads the backend catalogue and
 * fails if a field has no label in either language, or if a label is left
 * over from a field that no longer exists.
 */

import { t } from './i18n';

/** `saldo_capital_pendiente` → `saldo capital pendiente`: the last resort. */
export function humanizarNombre(nombre: string): string {
  return nombre.replace(/_/g, ' ');
}

/** The translated name of a portfolio field, or its technical name with spaces. */
export function etiquetaCampo(nombre: string): string {
  const clave = `campo.${nombre}`;
  const texto = t(clave);
  return texto === clave ? humanizarNombre(nombre) : texto;
}

/**
 * The name of a catalogue variable: the context's own key when it has one
 * (`whatsapp_contacto`), the portfolio label otherwise.
 */
export function etiquetaVariable(variable: { nombre: string; clave_nombre: string | null }): string {
  if (variable.clave_nombre) {
    const texto = t(variable.clave_nombre);
    if (texto !== variable.clave_nombre) return texto;
  }
  return etiquetaCampo(variable.nombre);
}

/** Field names in the order a person reads them, by label. */
export function ordenarPorEtiqueta(nombres: readonly string[]): string[] {
  return [...nombres].sort((a, b) => etiquetaCampo(a).localeCompare(etiquetaCampo(b)));
}
