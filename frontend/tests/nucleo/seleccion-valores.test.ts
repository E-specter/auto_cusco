/**
 * The syntax of a list filter (T-FV-F1, RF-67, docs/consulta-cartera.md §3): the operator `no_en`, «(vacío)» as an
 * empty element of the list, and the escape of `|` and `\`. It has to agree with the backend, so the tables of
 * `partirValores` and `escaparValor` below are what the backend's own `partir_valores` and `escapar_valor`
 * answered on the same inputs (B1, `seleccion_cartera/expresiones.py`).
 */
import { describe, expect, it } from 'vitest';

import type { Campos } from '../../src/lib/api';
import {
  borradorDe,
  consultaDe,
  escaparValor,
  escribirFiltro,
  filtroCompleto,
  leerFiltro,
  operadoresPara,
  partirValores,
  ubicarProblemas,
  valoresQuePide,
  type FiltroBorrador,
} from '../../src/lib/seleccion';

/** Input → what `partir_valores` answered. */
const PARTIR: Array<[string, string[]]> = [
  ['', ['']],
  ['|', ['', '']],
  ['a|b', ['a', 'b']],
  ['a\\|b', ['a|b']],
  ['a\\\\|b', ['a\\', 'b']],
  ['\\', ['\\']],
  ['a\\', ['a\\']],
  ['a\\b', ['a\\b']],
  ['\\\\', ['\\']],
  ['\\\\\\|', ['\\|']],
  ['x|', ['x', '']],
  ['|x', ['', 'x']],
  ['a||b', ['a', '', 'b']],
  ['10:30|b', ['10:30', 'b']],
  ['uno\\|dos|tres', ['uno|dos', 'tres']],
];

/** Input → what `escapar_valor` answered. */
const ESCAPAR: Array<[string, string]> = [
  ['a|b', 'a\\|b'],
  ['a\\b', 'a\\\\b'],
  ['\\', '\\\\'],
  ['|', '\\|'],
  ['a\\|b', 'a\\\\\\|b'],
  ['x y', 'x y'],
  ['10:30', '10:30'],
  ['a\\\\b', 'a\\\\\\\\b'],
];

const filtro = (operador: string, valores: string[], vacio?: boolean, campo = 'tipo_asignacion'): FiltroBorrador =>
  vacio === undefined ? { campo, operador, valores } : { campo, operador, valores, vacio };

describe('el escape, igual al del backend', () => {
  it.each(PARTIR)('partir %j da lo mismo que el backend', (texto, esperado) => {
    expect(partirValores(texto)).toEqual(esperado);
  });

  it.each(ESCAPAR)('escapar %j da lo mismo que el backend', (valor, esperado) => {
    expect(escaparValor(valor)).toBe(esperado);
  });

  it('escapar y partir son inversas para cualquier valor', () => {
    for (const [valor] of ESCAPAR) expect(partirValores(escaparValor(valor))).toEqual([valor]);
  });

  it('una barra suelta queda literal: no da error ni cambia el valor', () => {
    expect(leerFiltro('observacion:contiene:ruta a\\b').valores).toEqual(['ruta a\\b']);
    expect(leerFiltro('observacion:contiene:termina en \\').valores).toEqual(['termina en \\']);
  });
});

describe('no_en, el operador de excluir', () => {
  it('pide uno o más valores, igual que en', () => {
    expect(valoresQuePide('no_en')).toBeNull();
    expect(valoresQuePide('en')).toBeNull();
  });

  it('en un campo de texto, «es uno de» y «no es ninguno de» van primeros del menú; en otro, después de en', () => {
    const operadores = ['no_vacio', 'contiene', 'no_en', 'igual', 'en', 'vacio', 'mayor'];
    const campos = {
      region: { tipo: 'texto', operadores, adicional: false, etiqueta: null, archivado: false },
      dias_atraso: { tipo: 'numero', operadores, adicional: false, etiqueta: null, archivado: false },
    } as Campos;

    expect(operadoresPara(campos, 'region')).toEqual(['en', 'no_en', 'igual', 'contiene', 'mayor', 'vacio', 'no_vacio']);
    expect(operadoresPara(campos, 'dias_atraso')).toEqual(['igual', 'en', 'no_en', 'contiene', 'mayor', 'vacio', 'no_vacio']);
  });

  it('se escribe y se lee como en', () => {
    const texto = 'region:no_en:CUSCO SUR|TACNA';

    expect(leerFiltro(texto)).toEqual({ campo: 'region', operador: 'no_en', valores: ['CUSCO SUR', 'TACNA'] });
    expect(escribirFiltro(leerFiltro(texto))).toBe(texto);
  });

  it('sin un valor no está completo, con uno sí', () => {
    expect(filtroCompleto(filtro('no_en', []))).toBe(false);
    expect(filtroCompleto(filtro('no_en', ['TACNA']))).toBe(true);
  });
});

describe('«(vacío)» es un elemento vacío de la lista', () => {
  it('marcado, cierra la lista con un elemento vacío: en y no_en', () => {
    expect(escribirFiltro(filtro('en', ['Primera asignación'], true))).toBe('tipo_asignacion:en:Primera asignación|');
    expect(escribirFiltro(filtro('no_en', ['CUSCO SUR', 'TACNA'], true))).toBe('tipo_asignacion:no_en:CUSCO SUR|TACNA|');
  });

  it('sin marcar no escribe nada de más, también cuando la marca es false', () => {
    expect(escribirFiltro(filtro('en', ['A', 'B']))).toBe('tipo_asignacion:en:A|B');
    expect(escribirFiltro(filtro('en', ['A', 'B'], false))).toBe('tipo_asignacion:en:A|B');
  });

  it('solo el vacío es una lista válida: un elemento vacío', () => {
    expect(escribirFiltro(filtro('en', [], true))).toBe('tipo_asignacion:en:');
    expect(escribirFiltro(filtro('no_en', [], true))).toBe('tipo_asignacion:no_en:');
    expect(filtroCompleto(filtro('en', [], true))).toBe(true);
    expect(filtroCompleto(filtro('no_en', [], true))).toBe(true);
    expect(filtroCompleto(filtro('en', [], false))).toBe(false);
  });

  it('al leer, el elemento vacío pasa a ser la marca y no queda entre los valores', () => {
    expect(leerFiltro('tipo_asignacion:en:Primera asignación|')).toEqual({
      campo: 'tipo_asignacion',
      operador: 'en',
      valores: ['Primera asignación'],
      vacio: true,
    });
    expect(leerFiltro('tipo_asignacion:en:|Segunda')).toEqual({
      campo: 'tipo_asignacion',
      operador: 'en',
      valores: ['Segunda'],
      vacio: true,
    });
  });

  it('solo el vacío se lee, venga como un elemento o como los dos de «|»', () => {
    expect(leerFiltro('tipo_asignacion:en:')).toEqual({ campo: 'tipo_asignacion', operador: 'en', valores: [], vacio: true });
    expect(leerFiltro('tipo_asignacion:no_en:|')).toEqual({ campo: 'tipo_asignacion', operador: 'no_en', valores: [], vacio: true });
  });

  it('varios elementos vacíos o con solo espacios son una sola marca', () => {
    const leido = leerFiltro('tipo_asignacion:en:A||  |B');

    expect(leido.valores).toEqual(['A', 'B']);
    expect(leido.vacio).toBe(true);
    expect(escribirFiltro(leido)).toBe('tipo_asignacion:en:A|B|');
  });

  it('una línea en blanco escrita en el textarea no se convierte en vacío', () => {
    expect(escribirFiltro(filtro('en', ['A', '', '   ', 'B']))).toBe('tipo_asignacion:en:A|B');
    expect(escribirFiltro(filtro('no_en', ['', 'A', '']))).toBe('tipo_asignacion:no_en:A');
    expect(filtroCompleto(filtro('en', ['', '  ']))).toBe(false);
  });

  it('la consulta lo manda y lo deja pasar como completo', () => {
    const borrador = { filtros: [filtro('no_en', [], true)], orden: null, cantidad: null, indicadores: [] };

    expect(consultaDe(borrador).filtros).toEqual(['tipo_asignacion:no_en:']);
  });

  it('en un operador de un solo valor la marca no se escribe', () => {
    expect(escribirFiltro(filtro('igual', ['A'], true))).toBe('tipo_asignacion:igual:A');
    expect(escribirFiltro(filtro('contiene', ['A'], true))).toBe('tipo_asignacion:contiene:A');
  });

  it('en un operador de un solo valor un elemento vacío sigue siendo un valor vacío, como hoy', () => {
    expect(leerFiltro('dias_atraso:entre:|5')).toEqual({ campo: 'dias_atraso', operador: 'entre', valores: ['', '5'] });
  });
});

describe('ida y vuelta, escribir ↔ leer', () => {
  const VALORES = ['plana', 'con | barra', 'con \\ invertida', 'con \\| ambas', 'hora 10:30', 'dos  espacios', '\\', '|', 'termina en \\', 'a\\\\b', 'campo:op:valor'];

  it.each(['en', 'no_en'])('%s: cada valor vuelve igual, solo y todos juntos', (operador) => {
    for (const valor of VALORES) {
      const volvio = leerFiltro(escribirFiltro(filtro(operador, [valor])));
      expect(volvio.valores).toEqual([valor]);
      expect(volvio.vacio).toBeUndefined();
    }
    const todos = leerFiltro(escribirFiltro(filtro(operador, VALORES)));
    expect(todos.valores).toEqual(VALORES);
  });

  it.each(['en', 'no_en'])('%s: con y sin el vacío, cada combinación vuelve igual', (operador) => {
    for (const vacio of [false, true]) {
      for (const valores of [[], ['A'], VALORES]) {
        if (valores.length === 0 && !vacio) continue;
        const escrito = escribirFiltro(filtro(operador, valores, vacio));
        const volvio = leerFiltro(escrito);
        expect(volvio.valores).toEqual(valores);
        expect(volvio.vacio === true).toBe(vacio);
        expect(escribirFiltro(volvio)).toBe(escrito);
      }
    }
  });

  it('un valor de un operador de uno solo, con barra o invertida, también vuelve igual', () => {
    for (const operador of ['igual', 'distinto', 'contiene', 'empieza_con']) {
      for (const valor of VALORES) {
        expect(leerFiltro(escribirFiltro(filtro(operador, [valor]))).valores).toEqual([valor]);
      }
    }
  });

  it('un rango con barra en sus extremos tampoco se parte', () => {
    expect(leerFiltro(escribirFiltro(filtro('entre', ['a|b', 'c\\d']))).valores).toEqual(['a|b', 'c\\d']);
  });

  it('una selección guardada con vacío se abre y se vuelve a guardar sin perder nada', () => {
    const guardada = {
      filtros: ['tipo_asignacion:en:Primera asignación|', 'region:no_en:CUSCO SUR|TACNA|'],
      orden: null,
      cantidad: null,
      indicadores: [],
    };

    expect(consultaDe(borradorDe(guardada)).filtros).toEqual(guardada.filtros);
  });

  it('el problema que la API cita con el escape se ubica en su fila', () => {
    const borrador = borradorDe({ filtros: ['tipo_asignacion:en:con \\| barra|otro'], orden: null, cantidad: null, indicadores: [] });
    const [ubicado] = ubicarProblemas(
      [{ parte: 'filtro', expresion: 'tipo_asignacion:en:con \\| barra|otro', detalle: 'x' } as never],
      borrador,
    );

    expect(ubicado.indice).toBe(0);
  });
});

describe('los filtros guardados antes se leen igual que hoy', () => {
  it.each([
    ['segmento_financiero:igual:1. Preventiva', { campo: 'segmento_financiero', operador: 'igual', valores: ['1. Preventiva'] }],
    ['region:en:CUSCO SUR|TACNA', { campo: 'region', operador: 'en', valores: ['CUSCO SUR', 'TACNA'] }],
    ['dias_atraso:entre:0|30', { campo: 'dias_atraso', operador: 'entre', valores: ['0', '30'] }],
    ['telefono:vacio', { campo: 'telefono', operador: 'vacio', valores: [] }],
    ['observacion:contiene:hora 10:30', { campo: 'observacion', operador: 'contiene', valores: ['hora 10:30'] }],
    ['region:en:PUNO', { campo: 'region', operador: 'en', valores: ['PUNO'] }],
  ])('%s', (texto, esperado) => {
    expect(leerFiltro(texto)).toEqual(esperado);
    // And without any mark: an old filter does not grow a `vacio` it never had.
    expect('vacio' in leerFiltro(texto)).toBe(false);
  });

  it('y se escriben como se escribían', () => {
    for (const texto of ['segmento_financiero:igual:1. Preventiva', 'region:en:CUSCO SUR|TACNA', 'dias_atraso:entre:0|30', 'telefono:vacio']) {
      expect(escribirFiltro(leerFiltro(texto))).toBe(texto);
    }
  });
});
