/**
 * Vanilla i18n. Both dictionaries ship in the bundle (about 4 KB each), so a
 * language switch repaints without a network round trip or a flash of keys.
 *
 * Markup declares its own strings: `data-i18n` replaces textContent,
 * `data-i18n-html` replaces innerHTML (only for copy that carries a <br>),
 * and `data-i18n-attr="placeholder:key"` writes attributes.
 */

import es from '../i18n/es.json';
import en from '../i18n/en.json';

export type Language = 'es' | 'en';

const DICTIONARIES: Record<Language, Record<string, string>> = { es, en };

export const DEFAULT_LANGUAGE: Language = 'es';
const FALLBACK_LANGUAGE: Language = 'en';

let current: Language = DEFAULT_LANGUAGE;

export function getLanguage(): Language {
  return current;
}

export function isLanguage(value: unknown): value is Language {
  return value === 'es' || value === 'en';
}

/** Resolve a key, interpolating `{name}` placeholders. */
export function t(key: string, params?: Record<string, string | number>): string {
  const template =
    DICTIONARIES[current][key] ?? DICTIONARIES[FALLBACK_LANGUAGE][key] ?? key;
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  );
}

/** Rewrite every translated node inside `root` (defaults to the document). */
export function applyTranslations(root: ParentNode = document): void {
  root.querySelectorAll<HTMLElement>('[data-i18n]').forEach((node) => {
    node.textContent = t(node.dataset.i18n!);
  });

  root.querySelectorAll<HTMLElement>('[data-i18n-html]').forEach((node) => {
    node.innerHTML = t(node.dataset.i18nHtml!);
  });

  root.querySelectorAll<HTMLElement>('[data-i18n-attr]').forEach((node) => {
    for (const pair of node.dataset.i18nAttr!.split(',')) {
      const [attribute, key] = pair.split(':').map((part) => part.trim());
      if (attribute && key) node.setAttribute(attribute, t(key));
    }
  });
}

/**
 * Switch language: updates the dictionary, the <html lang> attribute that
 * screen readers announce from, and every translated node on the page.
 */
export function setLanguage(language: Language, root: ParentNode = document): void {
  current = language;
  document.documentElement.lang = language;
  applyTranslations(root);
  document.dispatchEvent(
    new CustomEvent<Language>('languagechange', { detail: language }),
  );
}

/** Locale tag for Intl formatting — Peru is the operating country. */
export function locale(): string {
  return current === 'es' ? 'es-PE' : 'en-GB';
}
