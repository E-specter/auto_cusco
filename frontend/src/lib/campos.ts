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

/**
 * What names a field wherever it is shown. `etiqueta` is the literal name of an additional field
 * (RF-64), which wins over everything; `clave` is the dictionary key of a base one.
 */
export interface DatosDeCampo {
  nombre: string;
  etiqueta?: string | null;
  clave?: string | null;
}

/** The visible name of a field: its own label, the dictionary's, or its technical name with spaces. */
export function etiquetaDeCampo(campo: DatosDeCampo): string {
  if (campo.etiqueta) return campo.etiqueta;
  const clave = campo.clave ?? `campo.${campo.nombre}`;
  const texto = t(clave);
  return texto === clave ? humanizarNombre(campo.nombre) : texto;
}

/** The translated name of a portfolio field known only by its name, or its technical name with spaces. */
export function etiquetaCampo(nombre: string): string {
  return etiquetaDeCampo({ nombre });
}

/**
 * The name of a catalogue variable: the label of an additional field, the context's own key when it
 * has one (`whatsapp_contacto`), the portfolio label otherwise.
 */
export function etiquetaVariable(variable: { nombre: string; clave_nombre: string | null; etiqueta?: string | null }): string {
  if (variable.etiqueta) return variable.etiqueta;
  if (variable.clave_nombre) {
    const texto = t(variable.clave_nombre);
    if (texto !== variable.clave_nombre) return texto;
  }
  return etiquetaCampo(variable.nombre);
}

/** The part of a field of `/cartera/campos` that decides how it is listed. */
export interface CampoDelCatalogo {
  etiqueta?: string | null;
  adicional?: boolean;
  archivado?: boolean;
}

type Catalogo = Readonly<Record<string, CampoDelCatalogo>>;

/** The visible name of a field of a catalogue, by its technical name. */
export function etiquetaEnCatalogo(campos: Catalogo, nombre: string): string {
  return etiquetaDeCampo({ nombre, etiqueta: campos[nombre]?.etiqueta });
}

/** Base fields first, additional ones after, each group by label (RF-66). */
export function ordenarCampos(campos: Catalogo, nombres: readonly string[]): string[] {
  const porEtiqueta = (a: string, b: string) => etiquetaEnCatalogo(campos, a).localeCompare(etiquetaEnCatalogo(campos, b));
  const adicional = (n: string) => Boolean(campos[n]?.adicional);
  return [...nombres.filter((n) => !adicional(n)).sort(porEtiqueta), ...nombres.filter(adicional).sort(porEtiqueta)];
}

/**
 * The options of a list of fields: an archived one is not offered unless it is the one chosen, where it
 * says so; the additional ones go last, in their own group, because a native `select` reads a group out
 * loud and shows it the same in every browser.
 */
export function opcionesDeCampos(campos: Catalogo, nombres: readonly string[], actual: string | null): Array<[string, string, string?]> {
  const grupo = t('camposAdicionales.grupo');
  return ordenarCampos(campos, nombres)
    .filter((n) => !campos[n]?.archivado || n === actual)
    .map((n): [string, string, string?] => {
      const etiqueta = etiquetaEnCatalogo(campos, n);
      const texto = campos[n]?.archivado ? t('camposAdicionales.archivadoEnLista', { campo: etiqueta }) : etiqueta;
      return campos[n]?.adicional ? [n, texto, grupo] : [n, texto];
    });
}

/** The names of the archived fields among those a saved selection, column or text already uses. */
export function archivadosEnUso(campos: Catalogo, usados: Iterable<string>): string[] {
  return ordenarCampos(campos, [...new Set(usados)].filter((n) => campos[n]?.archivado)).map((n) => etiquetaEnCatalogo(campos, n));
}

/** The notice of a preview that uses an archived field: it keeps working, but is no longer offered. */
export function avisoDeArchivados(etiquetas: readonly string[]): string | null {
  if (etiquetas.length === 0) return null;
  // The quotes of a cited name are the language's: «X» in Spanish, “X” in English.
  const lista = etiquetas.map((e) => t('camposAdicionales.nombreCitado', { campo: e })).join(', ');
  return t(etiquetas.length === 1 ? 'camposAdicionales.avisoArchivado' : 'camposAdicionales.avisoArchivados', { campo: lista });
}

/** Field names in the order a person reads them, by label. */
export function ordenarPorEtiqueta(nombres: readonly string[]): string[] {
  return [...nombres].sort((a, b) => etiquetaCampo(a).localeCompare(etiquetaCampo(b)));
}
