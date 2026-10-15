/**
 * Pure helpers of the rich-text editor: finding a variable the way an analyst
 * types it, reading a parameter without deciding validity, and the length
 * level against a module's limit.
 */
import { describe, expect, it } from 'vitest';

import {
  agruparPorOrigen,
  aVariableDirecta,
  anclaDe,
  argumentosIniciales,
  cambiarVariableDirecta,
  conArgumento,
  esReferencia,
  filtrarVariables,
  leerArgumento,
  nivelDeLargo,
  nodoDePieza,
  normalizarBusqueda,
  piezaDeAncla,
  resumenFunciones,
  textoArgumento,
} from '../../src/lib/editor-texto';

const VARIABLES = [
  { nombre: 'dias_atraso', origen: 'cartera', etiqueta: 'Días de atraso' },
  { nombre: 'titular', origen: 'cartera', etiqueta: 'Titular' },
  { nombre: 'whatsapp_contacto', origen: 'mowa_mes.speech', etiqueta: 'WhatsApp de contacto' },
];
const etiqueta = (v: { etiqueta: string }) => v.etiqueta;

describe('buscar una variable', () => {
  it('no distingue tildes ni mayúsculas', () => {
    expect(normalizarBusqueda('  Días ')).toBe('dias');
    expect(filtrarVariables(VARIABLES, 'DIAS', etiqueta).map((v) => v.nombre)).toEqual(['dias_atraso']);
  });

  it('busca por la etiqueta y por el nombre técnico, con todas las palabras', () => {
    expect(filtrarVariables(VARIABLES, 'whatsapp contacto', etiqueta).map((v) => v.nombre)).toEqual(['whatsapp_contacto']);
    expect(filtrarVariables(VARIABLES, 'atraso dias', etiqueta).map((v) => v.nombre)).toEqual(['dias_atraso']);
  });

  it('una búsqueda vacía devuelve todas', () => {
    expect(filtrarVariables(VARIABLES, '   ', etiqueta)).toHaveLength(3);
  });

  it('agrupa por origen con las variables del módulo primero', () => {
    expect(agruparPorOrigen(VARIABLES).map(([origen, lista]) => [origen, lista.length])).toEqual([
      ['mowa_mes.speech', 1],
      ['cartera', 2],
    ]);
  });
});

describe('nivel del largo', () => {
  it('compara con el límite y el umbral del módulo', () => {
    expect(nivelDeLargo(140, 160, 150)).toBe('dentro');
    expect(nivelDeLargo(150, 160, 150)).toBe('dentro');
    expect(nivelDeLargo(156, 160, 150)).toBe('cerca');
    expect(nivelDeLargo(161, 160, 150)).toBe('excedido');
  });

  it('sin límite del módulo no hay nivel', () => {
    expect(nivelDeLargo(999, null, null)).toBe('sin_limite');
  });

  it('sin umbral solo distingue dentro de excedido', () => {
    expect(nivelDeLargo(159, 160, null)).toBe('dentro');
  });
});

describe('argumentos', () => {
  it('un parámetro numérico manda un número cuando el texto lo es', () => {
    expect(leerArgumento(' 8 ', 'numero')).toBe(8);
    expect(leerArgumento('-1.5', 'numero')).toBe(-1.5);
  });

  it('lo que no es número va tal cual, para que el backend marque el campo', () => {
    expect(leerArgumento('ocho', 'numero')).toBe('ocho');
    expect(leerArgumento('', 'numero')).toBe('');
  });

  it('un texto conserva sus espacios: pueden ser parte del valor', () => {
    expect(leerArgumento(' - ', 'texto')).toBe(' - ');
  });

  it('muestra un argumento guardado y reconoce una referencia a variable', () => {
    expect(textoArgumento(8)).toBe('8');
    expect(textoArgumento(undefined)).toBe('');
    expect(textoArgumento({ variable: 'dias_atraso' })).toBe('');
    expect(esReferencia({ variable: 'dias_atraso' })).toBe(true);
    expect(esReferencia('dd/mm/aaaa')).toBe(false);
  });
});

describe('resumen de una cadena', () => {
  it('lee las funciones en orden con sus argumentos', () => {
    const resumen = resumenFunciones(
      [
        { nombre: 'primeros', args: [8] },
        { nombre: 'mayusculas', args: [] },
        { nombre: 'sumar_dias', args: [{ variable: 'dias_atraso' }] },
      ],
      (n) => ({ primeros: 'Primeros caracteres', mayusculas: 'Mayúsculas', sumar_dias: 'Sumar días' })[n] ?? n,
      (n) => (n === 'dias_atraso' ? 'Días de atraso' : n),
    );

    expect(resumen).toBe('primeros caracteres 8 · mayúsculas · sumar días Días de atraso');
  });
});

describe('argumentos de una función nueva', () => {
  it('usa el valor por defecto, deja vacío el obligatorio y omite el opcional sin valor', () => {
    expect(argumentosIniciales([{ obligatorio: true, por_defecto: null }])).toEqual(['']);
    expect(argumentosIniciales([{ obligatorio: false, por_defecto: 'https://wa.me/+51' }])).toEqual(['https://wa.me/+51']);
    expect(argumentosIniciales([{ obligatorio: true, por_defecto: 2 }, { obligatorio: false, por_defecto: null }])).toEqual([2]);
    expect(argumentosIniciales([])).toEqual([]);
  });

  it('un parámetro obligatorio con opciones empieza en la primera', () => {
    const patron = { obligatorio: true, por_defecto: null, opciones: [{ valor: 'dd/mm/aaaa' }, { valor: 'dd-mm-aa' }] };
    expect(argumentosIniciales([patron])).toEqual(['dd/mm/aaaa']);
  });

  it('fija un argumento sin dejar huecos y quita los vacíos del final', () => {
    expect(conArgumento([], 1, 'x')).toEqual(['', 'x']);
    expect(conArgumento(['a', 'b'], 1, undefined)).toEqual(['a']);
    expect(conArgumento(['a', 'b'], 0, undefined)).toEqual(['', 'b']);
    expect(conArgumento([8], 0, { variable: 'dias_atraso' })).toEqual([{ variable: 'dias_atraso' }]);
  });
});

describe('un problema sigue en su pieza mientras se edita', () => {
  const piezas = [
    { tipo: 'texto' as const, valor: 'Hola ' },
    { tipo: 'variable' as const, id: 'a' },
    { tipo: 'texto' as const, valor: '' },
    { tipo: 'variable' as const, id: 'b' },
    { tipo: 'texto' as const, valor: ', paga.' },
  ];

  it('ancla una variable por su id y un tramo por la variable anterior', () => {
    expect(anclaDe(piezas, 3)).toEqual({ tipo: 'variable', id: 'b' });
    expect(anclaDe(piezas, 4)).toEqual({ tipo: 'tramo', despuesDe: 'b' });
    expect(anclaDe(piezas, 0)).toEqual({ tipo: 'tramo', despuesDe: null });
    expect(anclaDe(piezas, null)).toBeNull();
  });

  it('encuentra la pieza aunque se haya insertado otra antes', () => {
    const despues = [{ tipo: 'texto' as const, valor: '' }, { tipo: 'variable' as const, id: 'z' }, ...piezas];
    expect(piezaDeAncla(despues, { tipo: 'variable', id: 'b' })).toBe(5);
    expect(piezaDeAncla(despues, { tipo: 'tramo', despuesDe: 'b' })).toBe(6);
  });

  it('si la variable ya no está, el problema pasa a toda la expresión', () => {
    expect(piezaDeAncla(piezas, { tipo: 'variable', id: 'quitada' })).toBeNull();
  });

  it('traduce cada variable al nodo que se envía, saltando los tramos vacíos', () => {
    expect([...nodoDePieza(piezas)]).toEqual([
      ['a', 1],
      ['b', 2],
    ]);
  });
});

describe('variable directa', () => {
  const speech = {
    nodos: [
      { tipo: 'texto' as const, valor: 'Hola ' },
      { tipo: 'variable' as const, nombre: 'titular', funciones: [{ nombre: 'primeros', args: [8] }] },
      { tipo: 'variable' as const, nombre: 'telefono', funciones: [] },
    ],
  };

  it('se queda con la primera variable y su cadena, sin texto', () => {
    expect(aVariableDirecta(speech)).toEqual({ nodos: [speech.nodos[1]] });
    expect(aVariableDirecta({ nodos: [{ tipo: 'texto' as const, valor: 'solo texto' }] })).toEqual({ nodos: [] });
    expect(aVariableDirecta(null)).toEqual({ nodos: [] });
  });

  it('cambiar de variable conserva la cadena; elegir ninguna la vacía', () => {
    expect(cambiarVariableDirecta(speech, 'saldo_capital_pendiente').nodos).toEqual([
      { tipo: 'variable', nombre: 'saldo_capital_pendiente', funciones: [{ nombre: 'primeros', args: [8] }] },
    ]);
    expect(cambiarVariableDirecta({ nodos: [] }, 'titular').nodos).toEqual([{ tipo: 'variable', nombre: 'titular', funciones: [] }]);
    expect(cambiarVariableDirecta(speech, '').nodos).toEqual([]);
  });
});
