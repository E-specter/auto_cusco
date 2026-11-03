/**
 * The rules of a WhatsMKT message that the settings editor says at once (T-WM-F1b2): emojis with their position, the length with
 * `[whatsapp]` as the link it becomes, the macros against the definition, and the view with its placeholder. They mirror
 * `backend/app/core/services/plataformas/whatsmkt/mensaje.py`; the backend stays the judge.
 */
import { beforeAll, describe, expect, it } from 'vitest';

import {
  LARGO_ENLACE_WHATSAPP,
  indiceDePosicion,
  largoDelMensaje,
  macrosDeLaDefinicion,
  partesDeLaVista,
  primerEmoji,
  primeraMacroInexistente,
  textoDeMacro,
  textoDeProblemaDelMensaje,
} from '../../src/lib/whatsmkt-mensaje';
import { setLanguageForTests } from './idioma';

beforeAll(() => setLanguageForTests('es'));

describe('los emojis', () => {
  it('el primero se dice con su posición en caracteres, no en unidades UTF-16, y su índice para el cursor', () => {
    // «Hola » is 5 characters; the emoji is the 6th and takes two UTF-16 units; «€» after it is not an emoji.
    const encontrado = primerEmoji('Hola 😀 y 😀 €');

    expect(encontrado).toEqual({ caracter: '😀', posicion: 6, indice: 5 });
  });

  it('la posición de un carácter después de un emoji cuenta el emoji como uno', () => {
    expect(primerEmoji('😀😀x😊')?.posicion).toBe(1);
    expect(primerEmoji('ab😊')).toEqual({ caracter: '😊', posicion: 3, indice: 2 });
    expect(indiceDePosicion('😀😀x', 3)).toBe(4);
    expect(indiceDePosicion('ab', 3)).toBeNull();
  });

  it('pasan las tildes, la ñ, los signos de apertura y los símbolos que son texto; no el selector de variante', () => {
    expect(primerEmoji('Año ¿qué? ¡Sí! © ® ™ ✓ ← → ♥ ☎ ✈')).toBeNull();
    expect(primerEmoji('✈️')?.caracter).toBe('️');
    expect(primerEmoji('listo ✅')?.caracter).toBe('✅');
    expect(primerEmoji('')).toBeNull();
  });
});

describe('el largo', () => {
  it('cuenta [whatsapp] como el enlace de 26 caracteres y las macros como están escritas', () => {
    expect(LARGO_ENLACE_WHATSAPP).toBe(26);
    expect(largoDelMensaje('abc')).toBe(3);
    expect(largoDelMensaje('[$MACRO1$]')).toBe(10);
    expect(largoDelMensaje('INFO por [whatsapp]')).toBe('INFO por '.length + 26);
    expect(largoDelMensaje('[whatsapp] y [whatsapp]')).toBe(' y '.length + 52);
  });

  it('cuenta un emoji de dos unidades como un carácter, como el backend', () => {
    expect(largoDelMensaje('a😀b')).toBe(3);
  });
});

describe('las macros', () => {
  it('la primera que no existe, en el orden del texto', () => {
    expect(primeraMacroInexistente('Hola [$MACRO1$] y [$MACRO4$] y [$MACRO9$]', 3)).toBe('[$MACRO4$]');
    expect(primeraMacroInexistente('[$MACRO0$]', 3)).toBe('[$MACRO0$]');
    expect(primeraMacroInexistente('[$MACRO1$] [$MACRO3$]', 3)).toBeNull();
    expect(primeraMacroInexistente('sin macros', 0)).toBeNull();
  });

  it('las de una definición son sus columnas menos la primera, numeradas por posición, con su etiqueta si la tienen', () => {
    const macros = macrosDeLaDefinicion([{ etiqueta: 'Número' }, { etiqueta: 'Nombres del titular' }, { etiqueta: null }, { etiqueta: '  ' }]);

    expect(macros).toEqual([
      { n: 1, etiqueta: 'Nombres del titular' },
      { n: 2, etiqueta: null },
      { n: 3, etiqueta: null },
    ]);
    expect(textoDeMacro(macros[0])).toBe('MACRO1 · Nombres del titular');
    expect(textoDeMacro(macros[1])).toBe('MACRO2');
    expect(macrosDeLaDefinicion([])).toEqual([]);
  });
});

describe('la vista previa', () => {
  const sinWhatsapp = '(sin WhatsApp configurado)';

  it('reemplaza las macros con los valores de la fila y [whatsapp] con el enlace', () => {
    const partes = partesDeLaVista('Hola [$MACRO1$], vence el [$MACRO2$]. INFO por [whatsapp]', ['Maria', '05/10/2026'], '900000123', sinWhatsapp);

    expect(partes.map((p) => p.texto).join('')).toBe('Hola Maria, vence el 05/10/2026. INFO por https://wa.me/+51900000123');
    expect(partes.some((p) => p.apagado)).toBe(false);
  });

  it('sin número de WhatsApp pone el texto apagado en su lugar', () => {
    const partes = partesDeLaVista('INFO por [whatsapp]', [], null, sinWhatsapp);

    expect(partes).toEqual([
      { texto: 'INFO por ', apagado: false },
      { texto: sinWhatsapp, apagado: true },
    ]);
  });

  it('una macro vacía se reemplaza por nada y una que la fila no tiene se deja como está, para que se vea el error', () => {
    expect(partesDeLaVista('a[$MACRO1$]b[$MACRO5$]', [null], null, sinWhatsapp).map((p) => p.texto).join('')).toBe('ab[$MACRO5$]');
  });

  it('un valor que parece un marcador no se vuelve a leer como marcador', () => {
    expect(partesDeLaVista('[$MACRO1$]', ['[whatsapp]'], '900000123', sinWhatsapp).map((p) => p.texto).join('')).toBe('[whatsapp]');
  });
});

describe('los problemas que el backend dice al guardar', () => {
  it('se leen por el código del módulo y con sus parámetros', () => {
    expect(textoDeProblemaDelMensaje({ codigo_contexto: 'mensaje_con_emoji', parametros: { caracter: '😀', posicion: 42 } })).toBe(
      'No se admiten emojis: el primero es «😀», en la posición 42.',
    );
    expect(textoDeProblemaDelMensaje({ codigo_contexto: 'mensaje_largo', parametros: { largo: 5000, maximo: 4096 } })).toBe(
      'El mensaje tiene 5000 caracteres: el máximo es 4096.',
    );
  });

  it('sin código del módulo, o con uno que esta versión no traduce, deja la frase al componente', () => {
    expect(textoDeProblemaDelMensaje({ codigo_contexto: null })).toBeNull();
    expect(textoDeProblemaDelMensaje({})).toBeNull();
    expect(textoDeProblemaDelMensaje({ codigo_contexto: 'codigo_nuevo' })).toBeNull();
  });
});
