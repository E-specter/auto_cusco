/**
 * The rules of the list of values of a list filter (T-FV-F2, RF-67, docs/filtro-valores-interfaz.md §2 and §7): when
 * a filter picks from a list, which filters above it make up its cascade, how an answer splits into «in the list»
 * and «checked, no products», the search and the count under the list.
 */
import { describe, expect, it } from 'vitest';

import type { Campos } from '../../src/lib/api';
import type { FiltroBorrador } from '../../src/lib/seleccion';
import {
  MAS_DE_PARA_BUSCAR,
  buscar,
  claveDeDecision,
  claveDeLista,
  conValor,
  filtrosDeArriba,
  marcados,
  pideLista,
  repartir,
  resumen,
  type ValorConCantidad,
} from '../../src/lib/valores-filtro';

const campo = (tipo: string) => ({ tipo, operadores: ['igual', 'en', 'no_en'], adicional: false, etiqueta: null, archivado: false });
const CAMPOS = { region: campo('texto'), dias_atraso: campo('numero'), vence: campo('fecha'), activo: campo('booleano') } as unknown as Campos;

const filtro = (campoNombre: string, operador: string, valores: string[], vacio?: boolean): FiltroBorrador =>
  vacio === undefined ? { campo: campoNombre, operador, valores } : { campo: campoNombre, operador, valores, vacio };

const RESPUESTA: ValorConCantidad[] = [
  { valor: 'CUSCO SUR', cantidad: 1820 },
  { valor: 'TACNA', cantidad: 96 },
  { valor: 'Ñuñoa', cantidad: 40 },
  { valor: null, cantidad: 12 },
];

describe('cuándo un filtro elige de una lista', () => {
  it('un campo de texto con «es uno de» o «no es ninguno de»', () => {
    expect(pideLista(CAMPOS, filtro('region', 'en', []))).toBe(true);
    expect(pideLista(CAMPOS, filtro('region', 'no_en', []))).toBe(true);
  });

  it('con los demás operadores de texto no', () => {
    for (const operador of ['igual', 'distinto', 'contiene', 'empieza_con', 'vacio', 'no_vacio', '']) {
      expect(pideLista(CAMPOS, filtro('region', operador, []))).toBe(false);
    }
  });

  it('un campo de número, de fecha o de sí/no tampoco, aunque use en', () => {
    for (const nombre of ['dias_atraso', 'vence', 'activo']) {
      expect(pideLista(CAMPOS, filtro(nombre, 'en', []))).toBe(false);
    }
  });

  it('sin campo, o con un campo que el catálogo no conoce, no hay lista', () => {
    expect(pideLista(CAMPOS, filtro('', 'en', []))).toBe(false);
    expect(pideLista(CAMPOS, filtro('inexistente', 'en', []))).toBe(false);
  });
});

describe('la cascada: qué filtros de arriba cuentan', () => {
  const filtros = [
    filtro('region', 'en', ['CUSCO SUR', 'TACNA']),
    filtro('dias_atraso', 'mayor', ['30']),
    filtro('region', 'igual', ['']),
    filtro('region', 'no_en', []),
    filtro('region', 'en', [], true),
    filtro('region', 'en', ['PUNO']),
  ];

  it('el primero no tiene nada encima', () => {
    expect(filtrosDeArriba(filtros, 0)).toEqual([]);
  });

  it('solo los completos de arriba, escritos como los lee la API', () => {
    expect(filtrosDeArriba(filtros, 2)).toEqual(['region:en:CUSCO SUR|TACNA', 'dias_atraso:mayor:30']);
  });

  it('un filtro incompleto no filtra el resultado y por eso no cuenta aquí', () => {
    expect(filtrosDeArriba(filtros, 4)).toEqual(['region:en:CUSCO SUR|TACNA', 'dias_atraso:mayor:30']);
  });

  it('un filtro que es solo «(vacío)» sí es completo', () => {
    expect(filtrosDeArriba(filtros, 5)).toEqual(['region:en:CUSCO SUR|TACNA', 'dias_atraso:mayor:30', 'region:en:']);
  });

  it('los de abajo no afectan a los de arriba', () => {
    expect(filtrosDeArriba(filtros, 1)).toEqual(['region:en:CUSCO SUR|TACNA']);
  });

  it('un valor con barra o invertida viaja escapado', () => {
    expect(filtrosDeArriba([filtro('region', 'en', ['A|B']), filtro('region', 'en', [])], 1)).toEqual(['region:en:A\\|B']);
  });
});

describe('qué pide cada lista de nuevo', () => {
  it('la clave cambia con la fecha, el campo o un filtro de arriba, no con otra cosa', () => {
    const base = claveDeLista('2026-09-10', 'region', ['a:en:x']);

    expect(claveDeLista('2026-09-10', 'region', ['a:en:x'])).toBe(base);
    expect(claveDeLista('2026-09-11', 'region', ['a:en:x'])).not.toBe(base);
    expect(claveDeLista('2026-09-10', 'agencia', ['a:en:x'])).not.toBe(base);
    expect(claveDeLista('2026-09-10', 'region', ['a:en:y'])).not.toBe(base);
    expect(claveDeLista('2026-09-10', 'region', [])).not.toBe(base);
  });

  it('que haya lista o no depende solo de la fecha y el campo', () => {
    expect(claveDeDecision('2026-09-10', 'region')).toBe(claveDeDecision('2026-09-10', 'region'));
    expect(claveDeDecision('2026-09-10', 'region')).not.toBe(claveDeDecision('2026-09-11', 'region'));
    expect(claveDeDecision('2026-09-10', 'region')).not.toBe(claveDeDecision('2026-09-10', 'agencia'));
  });
});

describe('lo marcado', () => {
  it('sin líneas en blanco, sin espacios en los bordes y sin repetidos', () => {
    expect(marcados(filtro('region', 'en', [' TACNA ', '', '  ', 'PUNO', 'TACNA']))).toEqual(['TACNA', 'PUNO']);
  });

  it('marcar suma al final y desmarcar quita, sin mover los demás', () => {
    expect(conValor(['A', 'B'], 'C', true)).toEqual(['A', 'B', 'C']);
    expect(conValor(['A', 'B', 'C'], 'B', false)).toEqual(['A', 'C']);
    expect(conValor(['A', 'B'], 'A', true)).toEqual(['B', 'A']);
  });

  it('marcar y desmarcar el mismo valor deja la lista como estaba', () => {
    expect(conValor(conValor(['A', 'B'], 'C', true), 'C', false)).toEqual(['A', 'B']);
  });

  it('las líneas en blanco del textarea se van al primer cambio', () => {
    expect(conValor(['', 'A', ' '], 'B', true)).toEqual(['A', 'B']);
  });
});

describe('«en la lista» y «marcados sin productos»', () => {
  it('lo que la respuesta trae va a la lista y «(vacío)» aparte', () => {
    const reparto = repartir(RESPUESTA, filtro('region', 'en', []));

    expect(reparto.enLista.map((item) => item.valor)).toEqual(['CUSCO SUR', 'TACNA', 'Ñuñoa']);
    expect(reparto.mostrarVacio).toBe(true);
    expect(reparto.cantidadVacio).toBe(12);
    expect(reparto.sinProductos).toEqual([]);
  });

  it('un valor marcado que la respuesta ya no trae queda aparte, y sigue marcado', () => {
    const f = filtro('region', 'en', ['TACNA', 'PUNO']);
    const reparto = repartir(RESPUESTA, f);

    expect(reparto.sinProductos).toEqual(['PUNO']);
    expect(marcados(f)).toEqual(['TACNA', 'PUNO']);
  });

  it('si el valor vuelve a tener productos, regresa a la lista sin aviso', () => {
    expect(repartir(RESPUESTA, filtro('region', 'en', ['TACNA'])).sinProductos).toEqual([]);
  });

  it('«(vacío)» no se ofrece si nadie lo tiene, salvo que esté marcado, y entonces dice 0', () => {
    const sinVacios = RESPUESTA.filter((item) => item.valor !== null);

    expect(repartir(sinVacios, filtro('region', 'en', [])).mostrarVacio).toBe(false);
    const marcado = repartir(sinVacios, filtro('region', 'en', [], true));
    expect(marcado.mostrarVacio).toBe(true);
    expect(marcado.cantidadVacio).toBe(0);
  });

  it('los espacios de los bordes no hacen que un valor con productos parezca no tenerlos', () => {
    expect(repartir([{ valor: 'TACNA ', cantidad: 3 }], filtro('region', 'en', ['TACNA'])).sinProductos).toEqual([]);
  });
});

describe('la búsqueda', () => {
  it('sin mayúsculas ni tildes', () => {
    expect(buscar(RESPUESTA, 'nunoa').map((item) => item.valor)).toEqual(['Ñuñoa']);
    expect(buscar(RESPUESTA, 'cusco').map((item) => item.valor)).toEqual(['CUSCO SUR']);
    expect(buscar(RESPUESTA, 'TACNA').map((item) => item.valor)).toEqual(['TACNA']);
  });

  it('un texto vacío o de espacios deja todo', () => {
    expect(buscar(RESPUESTA, '').length).toBe(RESPUESTA.length);
    expect(buscar(RESPUESTA, '   ').length).toBe(RESPUESTA.length);
  });

  it('«(vacío)» no se busca: ni aparece ni desaparece por lo que se escriba', () => {
    expect(buscar(RESPUESTA, 'vacio').some((item) => item.valor === null)).toBe(false);
    expect(buscar([{ valor: null, cantidad: 1 }], '')).toHaveLength(1);
  });

  it('sin resultados da una lista vacía', () => {
    expect(buscar(RESPUESTA, 'zzz')).toEqual([]);
  });

  it('con más de 10 valores se ofrece buscar', () => {
    expect(MAS_DE_PARA_BUSCAR).toBe(10);
  });
});

describe('el resumen «n de total marcados»', () => {
  it('cuenta lo marcado de la lista, lo marcado sin productos y el vacío', () => {
    const f = filtro('region', 'en', ['TACNA', 'PUNO'], true);

    expect(resumen(f, repartir(RESPUESTA, f))).toEqual({ n: 3, total: 3 + 1 + 1 });
  });

  it('sin nada marcado, cero de todo lo que hay', () => {
    const f = filtro('region', 'en', []);

    expect(resumen(f, repartir(RESPUESTA, f))).toEqual({ n: 0, total: 4 });
  });

  it('un marcado oculto por la búsqueda sigue contando (la búsqueda no desmarca)', () => {
    const f = filtro('region', 'en', ['TACNA']);

    expect(buscar(RESPUESTA, 'cusco')).toHaveLength(1);
    expect(resumen(f, repartir(RESPUESTA, f)).n).toBe(1);
  });
});
