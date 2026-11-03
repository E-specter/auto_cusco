/**
 * What the WhatsMKT configuration screen decides on its own for the contact WhatsApp, the default definition and the
 * attachment library (T-WM-F1b1): the number's rule, which definitions are offered, how a size and a type are
 * written, and the text of an attachment refusal. The API stays the judge; these are the checks a field makes.
 */
import { afterEach, beforeAll, describe, expect, it } from 'vitest';

import type { CodigoWhatsmkt, ErrorWhatsmkt } from '../../src/lib/api-whatsmkt';
import {
  definicionesDeWhatsmkt,
  esImagen,
  nombreDeTipo,
  tamanoLegible,
  textoDeCodigo,
  textoDeErrorAdjunto,
  tipoEnFrase,
  whatsappAEnviar,
  whatsappValido,
} from '../../src/lib/whatsmkt';
import { setLanguageForTests } from './idioma';

beforeAll(() => setLanguageForTests('es'));
afterEach(() => setLanguageForTests('es'));

function cuerpo(codigo: CodigoWhatsmkt, parcial: Partial<ErrorWhatsmkt> = {}): ErrorWhatsmkt {
  return { detail: 'motivo del servidor', codigo, horarios: null, variable: null, segmento: null, fila: null, desde: null, hasta: null, peso: null, maximo: null, tipo: null, ancho: null, alto: null, ...parcial };
}

describe('WhatsApp de contacto', () => {
  it('vale vacío (el número es opcional) y vale de 9 dígitos que empiezan con 9', () => {
    for (const texto of ['', '   ', '900000123', ' 900000123 ', '900000100']) {
      expect(whatsappValido(texto), texto).toBe(true);
    }
  });

  it('no vale si no empieza con 9, si no mide 9 o si trae algo que no es un dígito', () => {
    for (const texto of ['812345678', '90000012', '9000001234', '90000012a', '9 0000012', '+51900000123']) {
      expect(whatsappValido(texto), texto).toBe(false);
    }
  });

  it('manda el número sin espacios, y null para un campo vacío (que borra el guardado)', () => {
    expect(whatsappAEnviar(' 900000123 ')).toBe('900000123');
    expect(whatsappAEnviar('')).toBeNull();
    expect(whatsappAEnviar('   ')).toBeNull();
  });

  it('el texto de su error es el del código', () => {
    expect(textoDeCodigo(cuerpo('whatsapp_invalido'))).toBe('El WhatsApp debe tener 9 dígitos y empezar con 9.');
    setLanguageForTests('en');
    expect(textoDeCodigo(cuerpo('whatsapp_invalido'))).toBe('WhatsApp must have 9 digits and start with 9.');
  });
});

describe('definición por defecto', () => {
  const lista = [
    { id: 1, nombre: 'Carga SMS', plataforma: 'mowa_mes' },
    { id: 2, nombre: 'Contactos', plataforma: 'whatsmkt' },
    { id: 3, nombre: 'Sin plataforma', plataforma: null },
    { id: 4, nombre: 'Contactos 2', plataforma: 'whatsmkt' },
  ];

  it('ofrece solo las de plataforma WhatsMKT, en el orden de la API', () => {
    expect(definicionesDeWhatsmkt(lista).map((d) => d.id)).toEqual([2, 4]);
  });

  it('una definición sin plataforma no es de WhatsMKT, y una lista vacía da vacía', () => {
    expect(definicionesDeWhatsmkt([lista[2]])).toEqual([]);
    expect(definicionesDeWhatsmkt([])).toEqual([]);
  });
});

describe('biblioteca: tamaños y tipos', () => {
  it('escribe el tamaño en base decimal, como los topes (1 MB = 1 000 000 bytes)', () => {
    expect(tamanoLegible(0)).toBe('0 B');
    expect(tamanoLegible(999)).toBe('999 B');
    expect(tamanoLegible(1_000)).toBe('1 KB');
    expect(tamanoLegible(240_000)).toBe('240 KB');
    expect(tamanoLegible(16_000_000)).toBe('16 MB');
    expect(tamanoLegible(1_500_000)).toMatch(/^1[.,]5 MB$/);
  });

  it('999 999 bytes ya son 1 MB, no «1 000 KB»', () => {
    expect(tamanoLegible(999_999)).toBe('1 MB');
    expect(tamanoLegible(999_499)).toBe('999 KB');
  });

  it('las imágenes son las dos de imagen, y nada más', () => {
    expect(esImagen('imagen_jpeg')).toBe(true);
    expect(esImagen('imagen_png')).toBe(true);
    for (const tipo of ['video', 'audio', 'pdf', '']) expect(esImagen(tipo), tipo).toBe(false);
  });

  it('el tipo de la tabla y el de una frase, en cada idioma; uno desconocido se muestra como lo escribió la API', () => {
    expect(nombreDeTipo('imagen_jpeg')).toBe('Imagen JPEG');
    expect(nombreDeTipo('pdf')).toBe('PDF');
    expect(tipoEnFrase('video')).toBe('video');
    expect(tipoEnFrase('imagen_png')).toBe('imágenes PNG');
    expect(nombreDeTipo('hoja_de_calculo')).toBe('hoja_de_calculo');
    expect(tipoEnFrase('hoja_de_calculo')).toBe('hoja_de_calculo');
    setLanguageForTests('en');
    expect(nombreDeTipo('imagen_jpeg')).toBe('JPEG image');
    expect(tipoEnFrase('imagen_png')).toBe('PNG images');
  });
});

describe('biblioteca: el texto de un rechazo', () => {
  it('adjunto_peso dice cuánto pesa y cuánto admite ese tipo, con el tipo en palabras y los tamaños legibles', () => {
    expect(textoDeErrorAdjunto(cuerpo('adjunto_peso', { peso: 20_000_000, maximo: 16_000_000, tipo: 'video' }))).toBe(
      'El archivo pesa 20 MB: el máximo para video es 16 MB.',
    );
    expect(textoDeErrorAdjunto(cuerpo('adjunto_peso', { peso: 300_000, maximo: 240_000, tipo: 'imagen_jpeg' }))).toBe(
      'El archivo pesa 300 KB: el máximo para imágenes JPEG es 240 KB.',
    );
  });

  it('adjunto_tipo y adjunto_danado no llevan parámetros', () => {
    expect(textoDeErrorAdjunto(cuerpo('adjunto_tipo'))).toBe(
      'WhatsMKT no admite este tipo de archivo. Sube una imagen, un video, un audio o un PDF.',
    );
    expect(textoDeErrorAdjunto(cuerpo('adjunto_danado'))).toBe(
      'El archivo está incompleto o dañado. Vuelve a descargarlo y súbelo de nuevo.',
    );
  });

  it('en inglés', () => {
    setLanguageForTests('en');
    expect(textoDeErrorAdjunto(cuerpo('adjunto_peso', { peso: 20_000_000, maximo: 16_000_000, tipo: 'pdf' }))).toBe(
      'The file weighs 20 MB: the maximum for PDF is 16 MB.',
    );
  });
});
