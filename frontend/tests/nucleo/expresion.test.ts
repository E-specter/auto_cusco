/**
 * The editor state of a rich-text expression. What matters: the analyst can
 * always type before, between and after variables; nothing the editor adds
 * for itself reaches the backend; and a problem the backend reports lands on
 * the piece that caused it, not one next to it.
 */
import { describe, expect, it } from 'vitest';

import {
  aExpresion,
  agregarFuncion,
  cambiarArgumento,
  fijarArgumentos,
  desdeExpresion,
  editarTramo,
  funcionesCompatibles,
  insertarVariable,
  marcarObligatoria,
  moverFuncion,
  nodosAPiezas,
  normalizar,
  posicionTramo,
  quitarFuncion,
  quitarVariable,
  tipoEnPosicion,
  ubicarProblemas,
  type Catalogo,
  type Expresion,
  type Pieza,
  type PiezaVariable,
} from '../../src/lib/expresion';

const CATALOGO: Catalogo = {
  variables: [
    { nombre: 'titular', tipo: 'texto' },
    { nombre: 'fecha_vencimiento_cuota', tipo: 'fecha' },
    { nombre: 'saldo_capital_pendiente', tipo: 'numero' },
  ],
  funciones: [
    { nombre: 'primeros', recibe: ['texto'], devuelve: 'texto' },
    { nombre: 'mayusculas', recibe: ['texto'], devuelve: 'texto' },
    { nombre: 'sumar_dias', recibe: ['fecha'], devuelve: 'fecha' },
    { nombre: 'formato_fecha', recibe: ['fecha'], devuelve: 'texto' },
    { nombre: 'redondear', recibe: ['numero'], devuelve: 'numero' },
    { nombre: 'si_vacio', recibe: ['texto', 'numero', 'fecha'], devuelve: 'entrada' },
  ],
};

/** The speech example of the design (§4.1). */
const SPEECH: Expresion = {
  nodos: [
    { tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'primeros', args: [8] }] },
    { tipo: 'texto', valor: ' Caja Cusco te informa que tu cuota venció el ' },
    {
      tipo: 'variable',
      nombre: 'fecha_vencimiento_cuota',
      funciones: [{ nombre: 'formato_fecha', args: ['dd/mm/aaaa'] }],
    },
    { tipo: 'texto', valor: ', acércate a pagar.' },
  ],
};

const forma = (piezas: Pieza[]) => piezas.map((p) => (p.tipo === 'texto' ? `T:${p.valor}` : `V:${p.nombre}`));

describe('invariante de piezas', () => {
  it('siempre hay un tramo de texto al principio y al final', () => {
    expect(forma(desdeExpresion(SPEECH))).toEqual([
      'T:',
      'V:titular',
      'T: Caja Cusco te informa que tu cuota venció el ',
      'V:fecha_vencimiento_cuota',
      'T:, acércate a pagar.',
    ]);
  });

  it('una expresión vacía es un único tramo vacío', () => {
    expect(forma(desdeExpresion({ nodos: [] }))).toEqual(['T:']);
    expect(forma(desdeExpresion(null))).toEqual(['T:']);
  });

  it('une tramos seguidos y separa variables seguidas con un tramo vacío', () => {
    const v = (nombre: string): PiezaVariable => ({ tipo: 'variable', id: nombre, nombre, funciones: [], obligatoria: false });

    const piezas = normalizar([{ tipo: 'texto', valor: 'a' }, { tipo: 'texto', valor: 'b' }, v('x'), v('y')]);

    expect(forma(piezas)).toEqual(['T:ab', 'V:x', 'T:', 'V:y', 'T:']);
  });
});

describe('ida y vuelta con el contrato', () => {
  it('lo que llega del backend vuelve igual', () => {
    expect(aExpresion(desdeExpresion(SPEECH))).toEqual(SPEECH);
  });

  it('los tramos vacíos del editor no se envían', () => {
    const expresion = aExpresion(desdeExpresion({ nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [] }] }));

    expect(expresion.nodos).toEqual([{ tipo: 'variable', nombre: 'titular', funciones: [] }]);
  });

  it('obligatoria solo viaja cuando está marcada', () => {
    const piezas = marcarObligatoria(desdeExpresion(SPEECH), 1, true);

    const nodos = aExpresion(piezas).nodos;

    expect(nodos[0]).toMatchObject({ obligatoria: true });
    expect(nodos[2]).not.toHaveProperty('obligatoria');
  });
});

describe('insertar una variable en el cursor', () => {
  it('en medio de un tramo lo parte en dos', () => {
    const base = desdeExpresion({ nodos: [{ tipo: 'texto', valor: 'Hola mundo' }] });

    const { piezas, indiceVariable } = insertarVariable(base, 0, 5, 'titular');

    expect(forma(piezas)).toEqual(['T:Hola ', 'V:titular', 'T:mundo']);
    expect(indiceVariable).toBe(1);
  });

  it('al principio y al final deja un tramo vacío para seguir escribiendo', () => {
    const base = desdeExpresion({ nodos: [{ tipo: 'texto', valor: 'Hola' }] });

    expect(forma(insertarVariable(base, 0, 0, 'titular').piezas)).toEqual(['T:', 'V:titular', 'T:Hola']);
    expect(forma(insertarVariable(base, 0, 4, 'titular').piezas)).toEqual(['T:Hola', 'V:titular', 'T:']);
  });

  it('sin un tramo válido inserta al final', () => {
    const base = desdeExpresion(SPEECH);

    const { piezas } = insertarVariable(base, 1, 0, 'saldo_capital_pendiente');

    expect(forma(piezas).at(-2)).toBe('V:saldo_capital_pendiente');
  });

  it('un cursor fuera de rango se ajusta al tramo', () => {
    const base = desdeExpresion({ nodos: [{ tipo: 'texto', valor: 'ab' }] });

    expect(forma(insertarVariable(base, 0, 99, 'titular').piezas)).toEqual(['T:ab', 'V:titular', 'T:']);
  });
});

describe('quitar una variable', () => {
  it('une los tramos vecinos y deja el cursor en el punto de unión', () => {
    const base = desdeExpresion({
      nodos: [
        { tipo: 'texto', valor: 'Hola ' },
        { tipo: 'variable', nombre: 'titular', funciones: [] },
        { tipo: 'texto', valor: ', bienvenido' },
      ],
    });

    const { piezas, indiceTramo, cursor } = quitarVariable(base, 1);

    expect(forma(piezas)).toEqual(['T:Hola , bienvenido']);
    expect(indiceTramo).toBe(0);
    expect(cursor).toBe(5);
  });

  it('pedir quitar un tramo no cambia nada', () => {
    const base = desdeExpresion(SPEECH);

    expect(quitarVariable(base, 0).piezas).toBe(base);
  });
});

describe('cadena de funciones', () => {
  it('agrega, reordena y quita funciones sin tocar otras piezas', () => {
    let piezas = desdeExpresion(SPEECH);
    piezas = agregarFuncion(piezas, 1, { nombre: 'mayusculas', args: [] });
    piezas = moverFuncion(piezas, 1, 1, -1);

    expect((piezas[1] as PiezaVariable).funciones.map((f) => f.nombre)).toEqual(['mayusculas', 'primeros']);

    piezas = quitarFuncion(piezas, 1, 0);
    expect((piezas[1] as PiezaVariable).funciones.map((f) => f.nombre)).toEqual(['primeros']);
    // The other variable in the sentence is untouched.
    expect((piezas[3] as PiezaVariable).funciones).toEqual([{ nombre: 'formato_fecha', args: ['dd/mm/aaaa'] }]);
  });

  it('mover fuera del rango no hace nada', () => {
    const piezas = desdeExpresion(SPEECH);

    expect(moverFuncion(piezas, 1, 0, -1)[1]).toEqual(piezas[1]);
  });

  it('cambia un argumento, también a una referencia a otra variable', () => {
    let piezas = desdeExpresion(SPEECH);
    piezas = cambiarArgumento(piezas, 1, 0, 0, 12);
    piezas = cambiarArgumento(piezas, 3, 0, 0, { variable: 'fecha_envio' });

    expect((piezas[1] as PiezaVariable).funciones[0].args).toEqual([12]);
    expect((piezas[3] as PiezaVariable).funciones[0].args).toEqual([{ variable: 'fecha_envio' }]);
  });

  it('reemplaza la lista de argumentos de una sola función', () => {
    const piezas = fijarArgumentos(desdeExpresion(SPEECH), 3, 0, ['dd-mm-aa']);

    expect((piezas[3] as PiezaVariable).funciones[0].args).toEqual(['dd-mm-aa']);
    expect(fijarArgumentos(piezas, 0, 0, [1])).toBe(piezas);
  });

  it('editar un tramo no altera las variables', () => {
    const piezas = editarTramo(desdeExpresion(SPEECH), 2, 'otro texto');

    expect(forma(piezas)[2]).toBe('T:otro texto');
    expect(editarTramo(piezas, 1, 'x')).toBe(piezas);
  });
});

describe('tipos a lo largo de la cadena', () => {
  it('sigue el tipo por cada función', () => {
    const fecha = { nombre: 'fecha_vencimiento_cuota', funciones: [{ nombre: 'sumar_dias', args: [3] }, { nombre: 'formato_fecha', args: ['dd/mm/aaaa'] }] };

    expect(tipoEnPosicion(CATALOGO, fecha, 0)).toBe('fecha');
    expect(tipoEnPosicion(CATALOGO, fecha, 1)).toBe('fecha');
    expect(tipoEnPosicion(CATALOGO, fecha)).toBe('texto');
  });

  it('una función que devuelve su entrada conserva el tipo', () => {
    expect(tipoEnPosicion(CATALOGO, { nombre: 'saldo_capital_pendiente', funciones: [{ nombre: 'si_vacio', args: [0] }] })).toBe('numero');
  });

  it('una función incompatible corta la cadena', () => {
    expect(tipoEnPosicion(CATALOGO, { nombre: 'titular', funciones: [{ nombre: 'formato_fecha', args: [] }] })).toBeNull();
    expect(tipoEnPosicion(CATALOGO, { nombre: 'no_existe', funciones: [] })).toBeNull();
  });

  it('solo ofrece funciones que aceptan el tipo que llega', () => {
    expect(funcionesCompatibles(CATALOGO, 'fecha').map((f) => f.nombre)).toEqual(['sumar_dias', 'formato_fecha', 'si_vacio']);
    expect(funcionesCompatibles(CATALOGO, null)).toEqual([]);
  });
});

describe('problemas del backend', () => {
  it('traduce el índice de nodo a la pieza, saltando los tramos vacíos del editor', () => {
    const piezas = desdeExpresion(SPEECH);

    expect(nodosAPiezas(piezas)).toEqual([1, 2, 3, 4]);
    const [problema] = ubicarProblemas(
      [{ codigo: 'parametro_invalido', detalle: 'x', ubicacion: { nodo: 2, funcion: 0, parametro: 'patron' } }],
      piezas,
    );
    expect(problema.pieza).toBe(3);
  });

  it('un problema de toda la expresión no se clava en ninguna pieza', () => {
    const [problema] = ubicarProblemas([{ codigo: 'expresion_muy_larga', detalle: 'x', ubicacion: null }], desdeExpresion(SPEECH));

    expect(problema.pieza).toBeNull();
  });

  it('un nodo que ya no existe no apunta a otra pieza por error', () => {
    const [problema] = ubicarProblemas([{ codigo: 'x', detalle: 'x', ubicacion: { nodo: 9 } }], desdeExpresion(SPEECH));

    expect(problema.pieza).toBeNull();
  });
});

describe('nombre de cada tramo', () => {
  it('dice dónde está el tramo respecto de las variables', () => {
    const piezas = desdeExpresion(SPEECH);

    expect(posicionTramo(piezas, 0)).toEqual({ caso: 'inicio' });
    expect(posicionTramo(piezas, 2)).toEqual({ caso: 'despues', variable: 'titular' });
    expect(posicionTramo(piezas, 4)).toEqual({ caso: 'final' });
    expect(posicionTramo(desdeExpresion({ nodos: [] }), 0)).toEqual({ caso: 'unico' });
  });
});
