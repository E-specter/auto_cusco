/**
 * Switch the interface language inside a `node` test. `setLanguage` also
 * touches the document, which does not exist here, so the stub gives it just
 * enough of one.
 */
import { setLanguage, type Language } from '../../src/lib/i18n';

export function setLanguageForTests(language: Language): void {
  const global = globalThis as { document?: unknown };
  const teniaDocumento = 'document' in global;
  if (!teniaDocumento) {
    global.document = {
      documentElement: {},
      querySelectorAll: () => [],
      dispatchEvent: () => true,
    };
  }
  setLanguage(language, { querySelectorAll: () => [] } as unknown as ParentNode);
  if (!teniaDocumento) delete global.document;
}
