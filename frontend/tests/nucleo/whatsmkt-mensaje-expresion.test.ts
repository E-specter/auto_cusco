/**
 * The message of WhatsMKT between the saved text and the expression of the common editor (T-WM-F4, docs/motor-texto-enriquecido-interfaz.md §13.7):
 * what each marker becomes, and the round trip, byte for byte, with the three speeches the migration seeds (RF-WM-21: their double spaces and
 * the space before a comma are on purpose, DU-WM-2), repeated macros, `[whatsapp]` at both ends, a text with no markers, the empty string and a macro
 * the definition does not have.
 */
import { describe, expect, it } from 'vitest';

import { aExpresion, desdeExpresion } from '../../src/lib/expresion';
import { expresionDeMensaje, numeroDeMacro, textoDeMensaje } from '../../src/lib/whatsmkt-mensaje-expresion';

// The three speeches of the migration `d3f7a1b9c524`, written as it seeds them (with their double spaces and their spaces before a comma).
const SEMBRADOS = [
  'Hola [$MACRO1$] Caja Cusco te informa que tu cuota vence  el [$MACRO2$] , pague puntualmente en nuestras agencias, agentes  KASNET o a través de Wayki app. Si ya pagaste, omite este mensaje. INFO por [whatsapp]',
  'Hola [$MACRO1$] Caja Cusco te informa que tu cuota venció el [$MACRO2$] , ponte al día, te invitamos a pagar en nuestras agencias, agentes KASNET o a través de Wayki app. Si ya pagaste, omite este mensaje. INFO por [whatsapp]',
  'Hola [$MACRO1$] Caja Cusco te informa que tu cuota venció el [$MACRO2$] , evita estar mal calificado en el sistema financiero, el monto de tu cuota es [$MACRO3$] , acércate a pagar a nuestras agencias , agentes KASNET y/o canales alternativos. INFO por [whatsapp]',
];

const CASOS: Array<[string, string]> = [
  ['el primer speech sembrado', SEMBRADOS[0]],
  ['el segundo speech sembrado', SEMBRADOS[1]],
  ['el tercer speech sembrado', SEMBRADOS[2]],
  ['una macro repetida', 'Hola [$MACRO1$], sí [$MACRO1$], otra vez [$MACRO1$].'],
  ['[whatsapp] al principio', '[whatsapp] es el enlace, escríbenos'],
  ['[whatsapp] al final', 'Escríbenos por [whatsapp]'],
  ['[whatsapp] al principio y al final', '[whatsapp] o [whatsapp]'],
  ['solo [whatsapp]', '[whatsapp]'],
  ['una macro sola', '[$MACRO2$]'],
  ['dos marcadores pegados', '[$MACRO1$][$MACRO2$][whatsapp]'],
  ['un texto sin marcadores', 'Pague hoy: sin macros ni enlace.'],
  ['la cadena vacía', ''],
  ['espacios al borde y dobles', '  Hola  [$MACRO1$]  '],
  ['saltos de línea', 'Hola [$MACRO1$]\n\nTu cuota vence el [$MACRO2$].\r\nINFO por [whatsapp]\n'],
  ['una macro que la definición no tiene (con 3 macros)', 'Tu saldo es [$MACRO7$] hoy'],
  ['una macro con ceros a la izquierda', 'Hola [$MACRO07$]'],
  ['marcadores que no lo son (otra caja, un espacio)', 'Hola [$macro1$] [whatsapp ] [ whatsapp] [$MACRO$] [$MACROx$] [$MACRO1$ ]'],
  ['corchetes y símbolos sueltos', 'Costo: [S/ 10] $MACRO1$ [@titular] ñandú ¿qué? ¡sí! ©'],
];

describe('del texto guardado a la expresión', () => {
  it('cada macro es la variable macroN y [whatsapp] la variable whatsapp, y el resto es texto tal cual', () => {
    expect(expresionDeMensaje('Hola [$MACRO1$], vence el [$MACRO2$]. INFO por [whatsapp]')).toEqual({
      nodos: [
        { tipo: 'texto', valor: 'Hola ' },
        { tipo: 'variable', nombre: 'macro1', funciones: [] },
        { tipo: 'texto', valor: ', vence el ' },
        { tipo: 'variable', nombre: 'macro2', funciones: [] },
        { tipo: 'texto', valor: '. INFO por ' },
        { tipo: 'variable', nombre: 'whatsapp', funciones: [] },
      ],
    });
  });

  it('un texto vacío es una expresión sin nodos, y uno sin marcadores, un solo texto', () => {
    expect(expresionDeMensaje('')).toEqual({ nodos: [] });
    expect(expresionDeMensaje('Sin marcadores')).toEqual({ nodos: [{ tipo: 'texto', valor: 'Sin marcadores' }] });
  });

  it('una macro que la definición no tiene sigue siendo una variable: el motor la marca desconocida, no se pierde ni es texto mudo', () => {
    expect(expresionDeMensaje('Saldo [$MACRO7$]').nodos[1]).toEqual({ tipo: 'variable', nombre: 'macro7', funciones: [] });
  });

  it('solo es marcador lo que lee el backend: la caja, los espacios y los dígitos de más lo vuelven texto', () => {
    const texto = '[$macro1$] [whatsapp ] [ whatsapp] [$MACRO$] [$MACROx$] [$MACRO1$ ]';
    expect(expresionDeMensaje(texto)).toEqual({ nodos: [{ tipo: 'texto', valor: texto }] });
  });

  it('los dígitos se guardan como se escribieron: [$MACRO07$] es macro07, no macro7', () => {
    expect(expresionDeMensaje('[$MACRO07$]').nodos[0]).toMatchObject({ nombre: 'macro07' });
  });
});

describe('de la expresión al texto guardado', () => {
  it('es el camino inverso: macroN a [$MACROn$] y whatsapp a [whatsapp]', () => {
    expect(
      textoDeMensaje({
        nodos: [
          { tipo: 'texto', valor: 'Hola ' },
          { tipo: 'variable', nombre: 'macro3', funciones: [] },
          { tipo: 'variable', nombre: 'whatsapp', funciones: [] },
        ],
      }),
    ).toBe('Hola [$MACRO3$][whatsapp]');
  });

  it('sin expresión, o sin nodos, es la cadena vacía', () => {
    expect(textoDeMensaje(null)).toBe('');
    expect(textoDeMensaje(undefined)).toBe('');
    expect(textoDeMensaje({ nodos: [] })).toBe('');
  });

  it('una variable que no es del mensaje no es un marcador: no escribe nada', () => {
    expect(textoDeMensaje({ nodos: [{ tipo: 'texto', valor: 'a' }, { tipo: 'variable', nombre: 'titular', funciones: [] }, { tipo: 'texto', valor: 'b' }] })).toBe('ab');
  });
});

describe('la ida y vuelta, byte a byte', () => {
  it.each(CASOS)('%s', (_nombre, texto) => {
    expect(textoDeMensaje(expresionDeMensaje(texto))).toBe(texto);
  });

  // The editor does not hand the expression back as it got it: it holds pieces (text runs between pills, two pills with an empty run
  // between them) and `aExpresion` drops the empty runs. What it saves must still be the same text.
  it.each(CASOS)('%s, pasando por las piezas del editor', (_nombre, texto) => {
    const piezas = desdeExpresion(expresionDeMensaje(texto));
    expect(textoDeMensaje(aExpresion(piezas))).toBe(texto);
  });

  it('el texto guardado no cambia si el usuario no tocó nada: una macro inexistente sigue en su sitio', () => {
    const texto = 'Hola [$MACRO1$], pagas [$MACRO7$] en [$MACRO2$]';
    expect(textoDeMensaje(aExpresion(desdeExpresion(expresionDeMensaje(texto))))).toBe(texto);
  });
});

describe('el número de una macro', () => {
  it('lo da el nombre de la variable; otra variable no tiene', () => {
    expect(numeroDeMacro('macro1')).toBe(1);
    expect(numeroDeMacro('macro12')).toBe(12);
    expect(numeroDeMacro('whatsapp')).toBeNull();
    expect(numeroDeMacro('macros')).toBeNull();
    expect(numeroDeMacro('xmacro1')).toBeNull();
  });
});
