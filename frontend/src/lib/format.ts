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
