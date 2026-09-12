/**
 * The i18n loader.
 *
 * The console repaints in place rather than reloading, so a language switch
 * has to reach three different things: text nodes, attributes, and the
 * `<html lang>` that assistive technology announces from.
 */
import { beforeEach, describe, expect, it } from 'vitest';

import { applyTranslations, getLanguage, isLanguage, setLanguage, t } from '../../src/lib/i18n';

beforeEach(() => {
  document.body.replaceChildren();
  setLanguage('es');
});

describe('resolución de claves', () => {
  it('devuelve el texto del idioma activo', () => {
    expect(t('console.upload.open')).toBe('Subir sábana');

    setLanguage('en');

    expect(t('console.upload.open')).toBe('Upload sheet');
  });

  it('interpola los parámetros entre llaves', () => {
    expect(t('console.day.version', { version: 3 })).toBe('Versión 3');
  });

  it('deja la llave intacta cuando falta el parámetro', () => {
    // Mejor un hueco visible que un texto que afirme algo falso.
    expect(t('console.day.version')).toBe('Versión {version}');
  });

  it('devuelve la clave cuando no existe, para que el fallo se vea', () => {
    expect(t('clave.que.no.existe')).toBe('clave.que.no.existe');
  });

  it('reconoce solo los idiomas que el producto habla', () => {
    expect(isLanguage('es')).toBe(true);
    expect(isLanguage('en')).toBe(true);
    expect(isLanguage('pt')).toBe(false);
    expect(isLanguage(undefined)).toBe(false);
  });
});

describe('repintado de la página', () => {
  it('traduce el contenido de los nodos marcados', () => {
    document.body.innerHTML = '<button data-i18n="console.upload.open">x</button>';

    setLanguage('en');

    expect(document.querySelector('button')!.textContent).toBe('Upload sheet');
  });

  it('traduce atributos declarados en data-i18n-attr', () => {
    document.body.innerHTML =
      '<div data-i18n-attr="aria-label:console.incidencias.filter"></div>';

    setLanguage('en');

    expect(document.querySelector('div')!.getAttribute('aria-label')).toBe('Severity');
  });

  it('permite marcado en el texto solo donde se declara explícitamente', () => {
    // welcome.headline lleva un <br>; el resto se escribe como texto para que
    // una traducción no pueda inyectar marcado por accidente.
    document.body.innerHTML = '<h1 data-i18n-html="welcome.headline"></h1>';

    applyTranslations();

    expect(document.querySelector('h1')!.querySelector('br')).not.toBeNull();
  });

  it('escribe el texto sin interpretar marcado en los nodos normales', () => {
    document.body.innerHTML = '<p data-i18n="clave.inexistente.<b>x</b>"></p>';

    applyTranslations();

    expect(document.querySelector('p')!.querySelector('b')).toBeNull();
  });

  it('actualiza el atributo lang del documento al cambiar de idioma', () => {
    setLanguage('en');
    expect(document.documentElement.lang).toBe('en');

    setLanguage('es');
    expect(document.documentElement.lang).toBe('es');
    expect(getLanguage()).toBe('es');
  });

  it('avisa del cambio para que las partes dibujadas por script se repinten', () => {
    // La consola construye la regla de fechas y la tabla desde el script; sin
    // este aviso se quedarían en el idioma anterior.
    const avisos: string[] = [];
    document.addEventListener('languagechange', (evento) => {
      avisos.push((evento as CustomEvent<string>).detail);
    });

    setLanguage('en');

    expect(avisos).toEqual(['en']);
  });
});
