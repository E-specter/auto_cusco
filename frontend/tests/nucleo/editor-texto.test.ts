/**
 * Pure helpers of the rich-text editor: finding a variable the way an analyst
 * types it, reading a parameter without deciding validity, and the length
 * level against a module's limit.
 */
import { describe, expect, it } from 'vitest';

import {
  agruparPorOrigen,
  agruparPorTema,
  aVariableDirecta,
  anclaDe,
  argumentosIniciales,
  cambiarVariableDirecta,
  conArgumento,
  consultaDelBuscador,
  disparadorEn,
  ejemploDeVariable,
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

  it('el nombre técnico se encuentra tal como se escribe, con guion bajo, y con espacios', () => {
    expect(filtrarVariables(VARIABLES, 'whatsapp_contacto', etiqueta).map((v) => v.nombre)).toEqual(['whatsapp_contacto']);
    expect(filtrarVariables(VARIABLES, 'dias_atr', etiqueta).map((v) => v.nombre)).toEqual(['dias_atraso']);
    expect(filtrarVariables(VARIABLES, 'dias atr', etiqueta).map((v) => v.nombre)).toEqual(['dias_atraso']);
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

describe('el disparador [@ (§13.2)', () => {
  it('se detecta cuando el cursor queda justo después de [@, y dice dónde empieza', () => {
    expect(disparadorEn('Hola [@', 7)).toBe(5);
    expect(disparadorEn('[@', 2)).toBe(0);
    expect(disparadorEn('Hola [@ mundo', 7)).toBe(5);
  });

  it('no se detecta con solo uno de los dos caracteres, ni con el cursor en otro lado', () => {
    expect(disparadorEn('Hola [', 6)).toBeNull();
    expect(disparadorEn('Hola @', 6)).toBeNull();
    expect(disparadorEn('[@', 1)).toBeNull();
    expect(disparadorEn('Hola [@', 3)).toBeNull();
    expect(disparadorEn('', 0)).toBeNull();
  });

  it('lo escrito después del disparador es la consulta', () => {
    expect(consultaDelBuscador('Hola [@', 5, 7)).toBe('');
    expect(consultaDelBuscador('Hola [@titu', 5, 11)).toBe('titu');
    // El cursor a media consulta filtra solo con lo que queda a su izquierda.
    expect(consultaDelBuscador('Hola [@titular', 5, 9)).toBe('ti');
    // Una consulta con espacios es válida: las variables se buscan por varias palabras.
    expect(consultaDelBuscador('[@monto cuo', 0, 11)).toBe('monto cuo');
  });

  it('se cierra (null) al borrar la @ o el [, o al llevar el cursor antes del final del disparador', () => {
    expect(consultaDelBuscador('Hola [', 5, 6)).toBeNull();
    expect(consultaDelBuscador('Hola x@titu', 5, 11)).toBeNull();
    expect(consultaDelBuscador('Hola [@titu', 5, 6)).toBeNull();
    expect(consultaDelBuscador('Hola [@titu', 5, 3)).toBeNull();
  });

  it('se cierra con un salto de línea en la consulta', () => {
    expect(consultaDelBuscador('[@ti\ntu', 0, 7)).toBeNull();
  });
});

describe('el buscador por tema (§13.3)', () => {
  const v = (nombre: string, tema: string) => ({ nombre, tema });

  it('agrupa por tema en el orden fijo de los ocho, sea cual sea el orden en que llegan', () => {
    const grupos = agruparPorTema([
      v('segmento_actual', 'riesgo'),
      v('ad_zona', 'adicionales'),
      v('agencia', 'gestion'),
      v('pagare', 'credito'),
      v('dias_atraso', 'fechas'),
      v('monto_cuota', 'deuda'),
      v('titular', 'persona'),
      v('campo_nuevo', 'otros'),
    ]);
    expect(grupos.map(([tema]) => tema)).toEqual(['persona', 'deuda', 'fechas', 'credito', 'gestion', 'riesgo', 'adicionales', 'otros']);
  });

  it('dentro de un tema deja las variables en el orden en que llegaron', () => {
    const grupos = agruparPorTema([v('telefono', 'persona'), v('saldo', 'deuda'), v('titular', 'persona')]);
    expect(grupos[0][1].map((x) => x.nombre)).toEqual(['telefono', 'titular']);
  });

  it('deja fuera el tema sin variables', () => {
    expect(agruparPorTema([v('titular', 'persona')]).map(([tema]) => tema)).toEqual(['persona']);
    expect(agruparPorTema([])).toEqual([]);
  });

  it('una variable con un tema que no se conoce cae en «otros», no se pierde', () => {
    const grupos = agruparPorTema([v('titular', 'persona'), v('raro', 'inventado'), v('sin', '')]);
    expect(grupos.map(([tema]) => tema)).toEqual(['persona', 'otros']);
    expect(grupos[1][1].map((x) => x.nombre)).toEqual(['raro', 'sin']);
  });

  const siNo = (si: boolean) => (si ? 'Sí' : 'No');

  it('el ejemplo de una fecha se lee dd/mm/aaaa; el de un sí/no, con la palabra; lo demás, como llega', () => {
    expect(ejemploDeVariable('fecha', '2026-10-05', siNo)).toBe('05/10/2026');
    expect(ejemploDeVariable('booleano', false, siNo)).toBe('No');
    expect(ejemploDeVariable('booleano', true, siNo)).toBe('Sí');
    expect(ejemploDeVariable('numero', '1500.50', siNo)).toBe('1500.50');
    expect(ejemploDeVariable('numero', 12, siNo)).toBe('12');
    expect(ejemploDeVariable('texto', 'NOMBRE SINTETICO', siNo)).toBe('NOMBRE SINTETICO');
  });

  it('una fecha que no viene en ISO se deja como llega; sin valor no hay ejemplo', () => {
    expect(ejemploDeVariable('fecha', '05/10/2026', siNo)).toBe('05/10/2026');
    expect(ejemploDeVariable('texto', undefined, siNo)).toBeNull();
    expect(ejemploDeVariable('texto', null, siNo)).toBeNull();
    expect(ejemploDeVariable('texto', '', siNo)).toBeNull();
  });
});
