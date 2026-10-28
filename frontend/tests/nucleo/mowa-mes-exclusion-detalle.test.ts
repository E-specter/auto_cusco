/**
 * What the Detail of an exclusion says when a product was left out for an additional field that was empty
 * (RF-MM-04 / RF-65, T-MM-F11): the readable names, each in the quotes of the language, in singular or plural.
 * What costs when it is wrong: the technical name on screen (`ad_monto_mora`), a plural sentence for one
 * field (or the other way round), or the wrong quotes in a language. Every name is synthetic.
 */
import { afterEach, describe, expect, it } from 'vitest';

import { detalleDeExclusion, listaDeCampos } from '../../src/lib/mowa-mes-seguimiento';
import { t } from '../../src/lib/i18n';
import { setLanguageForTests } from './idioma';

const ZONA = { nombre: 'ad_zona', etiqueta: 'Zona' };
const MORA = { nombre: 'ad_monto_mora', etiqueta: 'Monto en mora' };

afterEach(() => setLanguageForTests('es'));

describe('la lista de nombres', () => {
  it('sin campos no hay lista', () => {
    expect(listaDeCampos([])).toBeNull();
    expect(listaDeCampos(undefined)).toBeNull();
  });

  it('cada nombre va entre las comillas del idioma, separado por comas, en el orden que llegan', () => {
    setLanguageForTests('es');
    expect(listaDeCampos([MORA, ZONA])).toBe('«Monto en mora», «Zona»');
    setLanguageForTests('en');
    expect(listaDeCampos([MORA, ZONA])).toBe('“Monto en mora”, “Zona”');
  });

  it('lee la etiqueta, y solo si falta usa el nombre técnico', () => {
    expect(listaDeCampos([ZONA])).toBe('«Zona»');
    expect(listaDeCampos([{ nombre: 'ad_zona', etiqueta: '' }])).toBe('«ad_zona»');
  });
});

describe('el detalle de una exclusión', () => {
  it('con un campo, la frase en singular con su nombre', () => {
    expect(detalleDeExclusion({ codigo: 'falta_campo_adicional', campos: [ZONA] })).toBe(
      'Falta el campo adicional «Zona», que el mensaje necesita.',
    );
  });

  it('con varios campos, la frase en plural con todos los nombres', () => {
    expect(detalleDeExclusion({ codigo: 'falta_campo_adicional', campos: [MORA, ZONA] })).toBe(
      'Faltan los campos adicionales «Monto en mora», «Zona», que el mensaje necesita.',
    );
  });

  it('en inglés, singular y plural con sus comillas', () => {
    setLanguageForTests('en');
    expect(detalleDeExclusion({ codigo: 'falta_campo_adicional', campos: [ZONA] })).toBe(
      'The additional field “Zona” is missing, and the message needs it.',
    );
    expect(detalleDeExclusion({ codigo: 'falta_campo_adicional', campos: [MORA, ZONA] })).toBe(
      'The additional fields “Monto en mora”, “Zona” are missing, and the message needs them.',
    );
  });

  it('un código que no es falta_campo_adicional sigue diciendo el texto del código, aunque traiga campos', () => {
    expect(detalleDeExclusion({ codigo: 'telefono_invalido', campos: [ZONA] })).toBe(t('mowaMes.codigo.telefono_invalido'));
    expect(detalleDeExclusion({ codigo: 'falta_documento', campos: [] })).toBe(t('mowaMes.codigo.falta_documento'));
  });

  it('falta_campo_adicional sin campos (una campaña vieja) dice el texto del código, sin nombres', () => {
    expect(detalleDeExclusion({ codigo: 'falta_campo_adicional', campos: [] })).toBe(t('mowaMes.codigo.falta_campo_adicional'));
    expect(detalleDeExclusion({ codigo: 'falta_campo_adicional', campos: [] })).toBe(
      'Falta un campo adicional que el mensaje necesita.',
    );
  });

  it('el nombre técnico no aparece cuando hay etiqueta', () => {
    const texto = detalleDeExclusion({ codigo: 'falta_campo_adicional', campos: [MORA, ZONA] });
    expect(texto).not.toContain('ad_');
  });
});
