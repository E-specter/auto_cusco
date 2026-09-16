/**
 * Formatting helpers. Every value the analyst reads is data, so everything
 * here lands in tabular numerals set in the secondary face.
 */

import { locale, t } from './i18n';

/** Parse an API date (`YYYY-MM-DD`) as a local date, not UTC midnight. */
export function parseApiDate(value: string): Date {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
}

export function toApiDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

/** "10 sep 2026" — long enough to be unambiguous, short enough for a node. */
export function formatDate(value: string): string {
  return new Intl.DateTimeFormat(locale(), {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(parseApiDate(value));
}

/** "10.09" — the compact stamp the ruler nodes carry. */
export function formatDateShort(value: string): string {
  const date = parseApiDate(value);
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${day}.${month}`;
}

/** "10.09.2026" — the compact stamp, for columns too narrow for the long form. */
export function formatDateCompact(value: string): string {
  const date = parseApiDate(value);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()}`;
}

/**
 * "10.09 · 14:32" — a stamp, not a sentence. Built by hand rather than with
 * Intl because the locale's short-month form lands as "10-set.," here, which
 * reads like a defect in a column of monospaced data.
 */
export function formatDateTime(value: string): string {
  const date = new Date(value);
  const pad = (n: number) => String(n).padStart(2, '0');
  return (
    `${pad(date.getDate())}.${pad(date.getMonth() + 1)}` +
    ` · ${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat(locale()).format(value);
}

/** The locale's grouping and decimal marks, read from Intl rather than assumed. */
function separadores(): { grupo: string; decimal: string } {
  const partes = new Intl.NumberFormat(locale()).formatToParts(12345.6);
  return {
    grupo: partes.find((parte) => parte.type === 'group')?.value ?? ',',
    decimal: partes.find((parte) => parte.type === 'decimal')?.value ?? '.',
  };
}

/**
 * A decimal written out in plain digits. Python's Decimal can print a zero
 * with scale as `0E-8` or a round figure as `1.2E+3`; both are the same
 * number and must not reach the analyst in that form.
 */
function aPlano(texto: string): string | null {
  const match = texto.trim().match(/^([+-]?)(\d+)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/);
  if (!match) return null;
  const [, signo, entero, fraccion = '', exponenteTexto] = match;
  const exponente = exponenteTexto ? Number(exponenteTexto) : 0;

  let digitos = entero + fraccion;
  let coma = entero.length + exponente;
  if (coma < 0) {
    digitos = '0'.repeat(-coma) + digitos;
    coma = 0;
  }
  if (coma > digitos.length) {
    digitos += '0'.repeat(coma - digitos.length);
  }
  const parteEntera = digitos.slice(0, coma).replace(/^0+(?=\d)/, '') || '0';
  const parteDecimal = digitos.slice(coma);
  return `${signo === '-' ? '-' : ''}${parteEntera}${parteDecimal ? `.${parteDecimal}` : ''}`;
}

/**
 * An amount that arrived as text, formatted without ever becoming a float.
 * Amounts travel as strings precisely so JSON cannot round them
 * (docs/consulta-cartera.md §6); `Number()` here would undo that. Rounding is
 * half away from zero on the digits themselves, with BigInt for the carry.
 */
export function formatMonto(valor: string | null | undefined, decimales = 2): string {
  if (valor === null || valor === undefined || valor.trim() === '') return '—';
  const plano = aPlano(valor);
  if (plano === null) return valor;

  const negativo = plano.startsWith('-');
  const [entero, fraccion = ''] = plano.replace(/^-/, '').split('.');
  const relleno = fraccion.padEnd(decimales + 1, '0');

  let escalado = BigInt(entero + relleno.slice(0, decimales));
  if (Number(relleno[decimales]) >= 5) escalado += 1n;

  const cifras = escalado.toString().padStart(decimales + 1, '0');
  const parteEntera = decimales ? cifras.slice(0, -decimales) : cifras;
  const parteDecimal = decimales ? cifras.slice(-decimales) : '';

  const { grupo, decimal } = separadores();
  const agrupada = parteEntera.replace(/\B(?=(\d{3})+(?!\d))/g, grupo);
  const esCero = escalado === 0n;
  return `${negativo && !esCero ? '-' : ''}${agrupada}${parteDecimal ? `${decimal}${parteDecimal}` : ''}`;
}

/**
 * A share as a percentage with one decimal, for reading only. Two amounts
 * divided to get "38.2 %" lose nothing the analyst reads; the amounts
 * themselves are still shown exactly with `formatMonto`.
 */
export function formatParticipacion(parte: string | number, total: string | number): string {
  const a = Number(parte);
  const b = Number(total);
  if (!Number.isFinite(a) || !Number.isFinite(b) || b === 0) return '—';
  return `${new Intl.NumberFormat(locale(), {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format((a / b) * 100)} %`;
}

export function formatBytes(bytes: number): string {
  const megabytes = bytes / 1024 / 1024;
  const digits = megabytes < 10 ? 1 : 0;
  return t('common.bytes', {
    n: new Intl.NumberFormat(locale(), {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(megabytes),
  });
}

/**
 * The entity names its sheets with the cut-off date in `DD.MM.YYYY`, so the
 * upload form can suggest it. Separators vary (dot, dash, underscore), and a
 * two-digit year is read as 20xx. The user always confirms the suggestion.
 */
export function guessDateFromFilename(filename: string): string | null {
  const match = filename.match(/(\d{2})[.\-_/](\d{2})[.\-_/](\d{2,4})/);
  if (!match) return null;

  const day = Number(match[1]);
  const month = Number(match[2]);
  const year = match[3].length === 2 ? 2000 + Number(match[3]) : Number(match[3]);

  if (month < 1 || month > 12 || day < 1 || day > 31) return null;

  const date = new Date(year, month - 1, day);
  // Rejects 31.02: the Date constructor rolls over instead of failing.
  if (date.getMonth() !== month - 1 || date.getDate() !== day) return null;

  return toApiDate(date);
}
