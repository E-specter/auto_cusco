/**
 * The line «Al enviar se borran: …» of the speech (RF-MM-27; docs/motor-texto-enriquecido-interfaz.md
 * §10.2). The backend says what the GSM-7 normalisation DELETES, per grapheme; this is only how each
 * one reads. What costs when it is wrong: a deleted character that reads as nothing (an invisible
 * one drawn as a blank), a composite emoji split in pieces, or a line for a segment with nothing
 * deleted.
 */
import { afterEach, describe, expect, it } from 'vitest';

import en from '../../src/i18n/en.json';
import es from '../../src/i18n/es.json';
import {
  SEPARADOR_BORRADOS,
  elementoBorrado,
  elementosBorrados,
  esInvisible,
  puntosDeCodigo,
  textoDeBorrados,
  type CaracterQuitado,
} from '../../src/lib/mowa-mes-gsm7';
import { setLanguageForTests } from './idioma';

const quitado = (caracter: string, punto_de_codigo: string): CaracterQuitado => ({ caracter, punto_de_codigo });

afterEach(() => setLanguageForTests('es'));

describe('puntosDeCodigo', () => {
  it('lee uno o varios puntos separados por un espacio', () => {
    expect(puntosDeCodigo('U+1F600')).toEqual([0x1f600]);
    expect(puntosDeCodigo('U+1F44D U+1F3FD')).toEqual([0x1f44d, 0x1f3fd]);
    expect(puntosDeCodigo('U+0419')).toEqual([0x419]);
  });

  it('rechaza lo que no es un punto de código', () => {
    expect(puntosDeCodigo('')).toBeNull();
    expect(puntosDeCodigo('1F600')).toBeNull();
    expect(puntosDeCodigo('U+1F600 x')).toBeNull();
    expect(puntosDeCodigo('U+110000')).toBeNull();
    expect(puntosDeCodigo('U+1f600')).toBeNull();
  });
});

describe('elementoBorrado', () => {
  it('un carácter visible va tal cual', () => {
    expect(elementoBorrado(quitado('👍', 'U+1F44D'))).toEqual({
      tipo: 'visible',
      caracter: '👍',
      codigo: 'U+1F44D',
      nombre: null,
    });
    expect(elementoBorrado(quitado('✓', 'U+2713')).tipo).toBe('visible');
    // Una letra que el alfabeto no tiene: se borra y se ve.
    expect(elementoBorrado(quitado('Й', 'U+0419')).tipo).toBe('visible');
  });

  it('un invisible con nombre va por su nombre y su punto de código', () => {
    expect(elementoBorrado(quitado('\u200b', 'U+200B'))).toEqual({
      tipo: 'con_nombre',
      caracter: '\u200b',
      codigo: 'U+200B',
      nombre: 'espacio de ancho cero',
    });
  });

  it('los once nombres existen en español y en inglés, y ninguno cae en el genérico', () => {
    const puntos = ['200B', '200C', '200D', '2060', '00AD', 'FEFF', '200E', '200F', '2028', '2029', '000B'];
    for (const punto of puntos) {
      const claveNombre = `mowaMes.speech.borrados.nombre.u${punto.toLowerCase()}`;
      expect(es, claveNombre).toHaveProperty([claveNombre]);
      expect(en, claveNombre).toHaveProperty([claveNombre]);
      const elemento = elementoBorrado(quitado(String.fromCodePoint(Number.parseInt(punto, 16)), `U+${punto}`));
      expect(elemento.tipo, punto).toBe('con_nombre');
      expect(elemento.nombre).toBe((es as Record<string, string>)[claveNombre]);
    }
  });

  it('el nombre sigue al idioma de la pantalla', () => {
    setLanguageForTests('en');
    expect(elementoBorrado(quitado('\u200b', 'U+200B')).nombre).toBe('zero-width space');
    expect(elementoBorrado(quitado('️⃣', 'U+FE0F U+20E3')).nombre).toBe('invisible character');
  });

  it('un invisible sin nombre va como «carácter invisible» con todos sus puntos', () => {
    expect(elementoBorrado(quitado('️⃣', 'U+FE0F U+20E3'))).toEqual({
      tipo: 'invisible',
      caracter: '️⃣',
      codigo: 'U+FE0F U+20E3',
      nombre: 'carácter invisible',
    });
    // Un control (Cc) que no tiene nombre.
    expect(elementoBorrado(quitado('\u0007', 'U+0007')).tipo).toBe('invisible');
  });

  it('un grafema compuesto es un solo elemento, entero', () => {
    const tono = elementoBorrado(quitado('👍🏽', 'U+1F44D U+1F3FD'));
    expect(tono).toMatchObject({ tipo: 'visible', caracter: '👍🏽', codigo: 'U+1F44D U+1F3FD' });
    const familia = elementoBorrado(quitado('👨‍👩‍👧', 'U+1F468 U+200D U+1F469 U+200D U+1F467'));
    expect(familia).toMatchObject({ tipo: 'visible', caracter: '👨‍👩‍👧' });
    const bandera = elementoBorrado(quitado('🇵🇪', 'U+1F1F5 U+1F1EA'));
    expect(bandera).toMatchObject({ tipo: 'visible', caracter: '🇵🇪' });
  });

  it('un punto que no se puede leer no se esconde: se muestra el carácter', () => {
    expect(elementoBorrado(quitado('?', 'raro'))).toMatchObject({ tipo: 'visible', caracter: '?' });
  });
});

describe('esInvisible: todos los puntos sin forma propia', () => {
  it('Mn, Me, Cf, Cc y Zs lo son', () => {
    expect(esInvisible('U+0301')).toBe(true); // Mn: acento combinante
    expect(esInvisible('U+20E3')).toBe(true); // Me: recuadro combinante
    expect(esInvisible('U+2066')).toBe(true); // Cf: aislamiento de izquierda a derecha
    expect(esInvisible('U+0007')).toBe(true); // Cc
    expect(esInvisible('U+3000')).toBe(true); // Zs
  });

  it('basta un punto con forma para que se vea', () => {
    expect(esInvisible('U+0031 U+FE0F U+20E3')).toBe(false); // el «1» de un keycap
    expect(esInvisible('U+1F44D U+1F3FD')).toBe(false);
    expect(esInvisible('U+E000')).toBe(false); // uso privado: no entra en el criterio
  });

  it('todos los puntos de un keycap sin su dígito lo son', () => {
    expect(esInvisible('U+FE0F U+20E3')).toBe(true);
  });
});

describe('elementosBorrados y la línea', () => {
  it('una lista vacía no deja ningún elemento: no hay línea', () => {
    expect(elementosBorrados([])).toEqual([]);
    expect(textoDeBorrados([])).toBe('');
  });

  it('conserva el orden del backend y separa con « · »', () => {
    const elementos = elementosBorrados([
      quitado('👍🏽', 'U+1F44D U+1F3FD'),
      quitado('✓', 'U+2713'),
      quitado('\u200b', 'U+200B'),
    ]);
    expect(elementos.map((e) => e.tipo)).toEqual(['visible', 'visible', 'con_nombre']);
    expect(SEPARADOR_BORRADOS).toBe(' · ');
    expect(textoDeBorrados(elementos)).toBe('👍🏽 · ✓ · espacio de ancho cero U+200B');
  });

  it('el invisible genérico se lee con todos sus puntos', () => {
    expect(textoDeBorrados(elementosBorrados([quitado('️⃣', 'U+FE0F U+20E3')]))).toBe(
      'carácter invisible U+FE0F U+20E3',
    );
  });

  it('un repetido no debería llegar, pero si llega no rompe ni se quita aquí', () => {
    const elementos = elementosBorrados([quitado('✓', 'U+2713'), quitado('✓', 'U+2713')]);
    expect(elementos).toHaveLength(2);
    expect(textoDeBorrados(elementos)).toBe('✓ · ✓');
  });
});
