/**
 * Logic of the MOWA MES follow-up screen (T-MM-F3), kept out of the page so it
 * can be tested without a browser. Every figure comes from the API as counted
 * there; this module only orders, pages and reads what arrived.
 */

import type {
  Campana,
  CifrasGrupo,
  CodigoMowaMes,
  Conciliacion,
  ConsumoLimite,
  EstadoConteo,
  Exclusion,
} from './api-mowa-mes';
import { formatDate, formatMesGestion, toApiDate } from './format';
import { t } from './i18n';
import { traducirCodigo } from './mowa-mes';

/** Exclusion reasons in evaluation order (docs/mowa-mes.md §12): the filter's options. */
export const CODIGOS_EXCLUSION = [
  'telefono_invalido',
  'falta_documento',
  'sin_speech',
  'falta_titular',
  'falta_vencimiento',
  'falta_campo_adicional',
  'mensaje_excede_160',
] as const satisfies readonly CodigoMowaMes[];

/**
 * The names of the additional fields that left a product out, by their readable label, each in the quotes
 * of the language (they live in the template, `mowaMes.exclusiones.campo`) and separated by commas.
 * `null` when there are none. The label is what a person reads; the technical name is only a fallback.
 */
export function listaDeCampos(campos: Exclusion['campos'] | undefined): string | null {
  if (!campos || campos.length === 0) return null;
  return campos.map((c) => t('mowaMes.exclusiones.campo', { campo: c.etiqueta || c.nombre })).join(', ');
}

/**
 * The notice of the archived additional fields the speech still reads (RF-65): in the campaign preview, where
 * it explains products left out, or in the speech editor. Own texts of MOWA MES, not the engine's
 * `avisoDeArchivados` («sigue funcionando»), which would mislead here: sheets loaded after archiving no longer
 * bring the field. `null` when there are none. Singular or plural, with the readable names.
 */
export function avisoDeCamposArchivados(campos: Parameters<typeof listaDeCampos>[0], donde: 'campana' | 'editor'): string | null {
  const lista = listaDeCampos(campos);
  if (lista === null || !campos) return null;
  // The four keys written out, so a search for one of them finds where it is used.
  const [uno, varios] =
    donde === 'campana'
      ? (['mowaMes.campana.avisoArchivado', 'mowaMes.campana.avisoArchivados'] as const)
      : (['mowaMes.speech.v2.avisoArchivado', 'mowaMes.speech.v2.avisoArchivados'] as const);
  return t(campos.length === 1 ? uno : varios, { campos: lista });
}

/**
 * What the Detail column says about an exclusion. For `falta_campo_adicional` with fields, a sentence with
 * their names, in singular or plural; for any other code, or with no fields, the text of the code as before.
 */
export function detalleDeExclusion(exclusion: Pick<Exclusion, 'codigo' | 'campos'>): string {
  const lista = exclusion.codigo === 'falta_campo_adicional' ? listaDeCampos(exclusion.campos) : null;
  if (lista === null) return traducirCodigo(exclusion.codigo, exclusion.codigo);
  return t(exclusion.campos.length === 1 ? 'mowaMes.exclusiones.faltaCampoAdicional' : 'mowaMes.exclusiones.faltanCamposAdicionales', {
    campos: lista,
  });
}

// ---- Months --------------------------------------------------------------------

const dosDigitos = (n: number) => String(n).padStart(2, '0');

/** `YYYY-MM` of a local date. */
export function mesDe(fecha: Date): string {
  return `${fecha.getFullYear()}-${dosDigitos(fecha.getMonth() + 1)}`;
}

/** Move a `YYYY-MM` month by whole months, across years. */
export function moverMes(mes: string, delta: number): string {
  const [anio, numero] = mes.split('-').map(Number);
  const indice = anio * 12 + (numero - 1) + delta;
  return `${Math.floor(indice / 12)}-${dosDigitos((indice % 12) + 1)}`;
}

/** Share of the monthly limit already loaded; 0 for a limit that is not positive. */
export function usoDelLimite(consumo: Pick<ConsumoLimite, 'cargados_mes' | 'limite'>): number {
  return consumo.limite > 0 ? consumo.cargados_mes / consumo.limite : 0;
}

/** How close the month is to its limit: the colour of the usage bar (docs/mowa-mes-interfaz.md §4.1). */
export type TonoDeUso = 'normal' | 'cerca' | 'excedido';

/**
 * The tone of the bar: `normal` (accent) up to 90%, `cerca` (signal) from 90% to 100%, both included, and
 * `excedido` (danger) above 100%. Whole numbers, never a share: 90% is `cargados * 10 >= limite * 9`, so the
 * edge is not at the mercy of a division. A limit that is not positive has no share to speak of: with
 * something loaded it is exceeded (nothing fits), with nothing it is not.
 */
export function tonoDelUso(consumo: Pick<ConsumoLimite, 'cargados_mes' | 'limite'>): TonoDeUso {
  const { cargados_mes: cargados, limite } = consumo;
  if (cargados > limite) return 'excedido';
  if (limite > 0 && cargados * 10 >= limite * 9) return 'cerca';
  return 'normal';
}

/** The fill of the bar, as a percentage of its width: from 0 to 100, never more, whatever the usage. */
export function anchoDeLaBarra(consumo: Pick<ConsumoLimite, 'cargados_mes' | 'limite'>): number {
  const { cargados_mes: cargados, limite } = consumo;
  if (limite <= 0) return cargados > 0 ? 100 : 0;
  return Math.min(100, Math.max(0, (cargados / limite) * 100));
}

// ---- Downloads -------------------------------------------------------------------

export interface ResumenDescarga {
  campana: number | null;
  archivo: number | null;
  total: number | null;
  filas: number | null;
  supervision: number | null;
  bytes: number | null;
}

/**
 * The `X-Mowa-Mes-*` summary as numbers. A header that is missing or not a
 * whole number reads as null rather than as a guess.
 */
export function leerResumenDescarga(resumen: Record<string, string>): ResumenDescarga {
  const entero = (clave: string) => {
    const valor = resumen[clave]?.trim();
    return valor && /^\d+$/.test(valor) ? Number(valor) : null;
  };
  return {
    campana: entero('campana'),
    archivo: entero('archivo'),
    total: entero('archivos-total'),
    filas: entero('filas'),
    supervision: entero('supervision'),
    bytes: entero('bytes'),
  };
}

/** The server's file name, or a stable one when it sent none. */
export function nombreArchivo(nombre: string | null, campanaId: number, numero: number): string {
  return nombre && nombre.trim() ? nombre.trim() : `mowa_mes_campana_${campanaId}_archivo_${numero}.xlsx`;
}

// ---- Reconciliation ------------------------------------------------------------

export type GrupoConciliacion = 'productos' | 'supervision' | 'total';

/** Products, supervision and total, always in that order and always apart (RF-41). */
export function filasConciliacion(
  conciliacion: Conciliacion,
): Array<{ grupo: GrupoConciliacion; cifras: CifrasGrupo }> {
  return (['productos', 'supervision', 'total'] as const).map((grupo) => ({
    grupo,
    cifras: conciliacion[grupo],
  }));
}

/** States as MES wrote them, most frequent first, ties by name. */
export function ordenarEstados(estados: readonly EstadoConteo[]): EstadoConteo[] {
  return [...estados].sort((a, b) => b.cantidad - a.cantidad || a.estado.localeCompare(b.estado));
}

// ---- Paging ----------------------------------------------------------------------

/** The 1-based range a page shows, or null when the page is empty. */
export function rangoPagina(
  desplazamiento: number,
  enPagina: number,
  total: number,
): { desde: number; hasta: number } | null {
  if (enPagina <= 0 || total <= 0) return null;
  return { desde: desplazamiento + 1, hasta: Math.min(desplazamiento + enPagina, total) };
}

/**
 * The campaign a link asks the follow-up to open: `?campana=<id>` (the one «Para subir a MES» points at).
 * `null` when the parameter is missing or is not a whole, positive number: the screen then starts from the
 * latest campaign, as always.
 */
export function campanaDeLaUrl(busqueda: string): number | null {
  const valor = new URLSearchParams(busqueda).get('campana');
  if (valor === null || !/^[0-9]+$/.test(valor)) return null;
  const id = Number(valor);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

// ---- Active and discarded campaigns (RF-MM-31, RF-MM-32) ----------------------------------

/** Which list the screen shows: the live campaigns, or the ones set aside. */
export type VistaCampanas = 'activas' | 'descartadas';

/** The view the URL asks for (`?vista=descartadas`); anything else is the active list. */
export function vistaDeLaUrl(busqueda: string): VistaCampanas {
  return new URLSearchParams(busqueda).get('vista') === 'descartadas' ? 'descartadas' : 'activas';
}

/**
 * The query string for a view, keeping the other parameters. The active list is the default, so it carries no
 * `vista`: going back to it leaves the URL as it was before any switch.
 */
export function busquedaConVista(busqueda: string, vista: VistaCampanas): string {
  const parametros = new URLSearchParams(busqueda);
  if (vista === 'descartadas') parametros.set('vista', 'descartadas');
  else parametros.delete('vista');
  const texto = parametros.toString();
  return texto === '' ? '' : `?${texto}`;
}

/** The months with discarded campaigns, newest first, each once and only if it is a `YYYY-MM`. */
export function ordenarMeses(meses: readonly string[]): string[] {
  return [...new Set(meses.filter((mes) => /^\d{4}-(0[1-9]|1[0-2])$/.test(mes)))].sort().reverse();
}

/**
 * The month the discarded view shows: the one chosen while it still has campaigns, otherwise the most recent
 * (so the view opens on it), and `''` when no month has any.
 */
export function elegirMesDescartadas(meses: readonly string[], elegido: string): string {
  const ordenados = ordenarMeses(meses);
  return ordenados.includes(elegido) ? elegido : (ordenados[0] ?? '');
}

/** The day a campaign was discarded, in the analyst's zone, as the site writes dates (`format.ts`). */
export function fechaDeDescarte(descartadaEn: string): string {
  return formatDate(toApiDate(new Date(descartadaEn)));
}

/**
 * Whether discarding warns that a report was imported. `pendiente_reporte` is the only sign the API gives of
 * «has a report»: false means one is in. The warning says its consumption stops counting toward the limit.
 */
export function advertirAlDescartar(campana: Pick<Campana, 'pendiente_reporte'>): boolean {
  return campana.pendiente_reporte === false;
}

/**
 * Whether a campaign shows as «pending the report». `pendiente_reporte` does not look at whether it was
 * discarded, so a discarded one never shows it, nor the notice or the way to import.
 */
export function pendienteVisible(campana: Pick<Campana, 'pendiente_reporte' | 'descartada_en'>): boolean {
  return campana.pendiente_reporte && campana.descartada_en === null;
}

/** The text of a month in a select, for each month the API lists. */
export function opcionesDeMeses(meses: readonly string[]): Array<{ valor: string; texto: string }> {
  return ordenarMeses(meses).map((mes) => ({ valor: mes, texto: formatMesGestion(mes) }));
}
