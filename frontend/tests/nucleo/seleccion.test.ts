/**
 * The selection syntax. The same strings go to `/cartera/resumen`, to saved
 * selections and to the load file, so a filter written wrong here selects the
 * wrong debtors everywhere at once.
 */
import { describe, expect, it } from 'vitest';

import type { Campos } from '../../src/lib/api';
import {
  CANTIDAD_MAXIMA,
  borradorDe,
  consultaDe,
  escribirFiltro,
  escribirIndicador,
  escribirOrden,
  filtroCompleto,
  funcionAdmiteCampo,
  indicadorCompleto,
  leerCantidad,
  leerFiltro,
  leerIndicador,
  leerOrden,
  operadoresPara,
  partesIncompletas,
  ubicarProblemas,
  valoresQuePide,
} from '../../src/lib/seleccion';

const CAMPOS: Campos = {
  dias_atraso: {
    tipo: 'numero',
    operadores: ['vacio', 'entre', 'igual', 'mayor', 'no_vacio', 'en'],
  },
  segmento_financiero: { tipo: 'texto', operadores: ['contiene', 'igual', 'en'] },
};

describe('escribir filtros en la sintaxis de la API', () => {
  it('une varios valores con barra vertical', () => {
    expect(
      escribirFiltro({ campo: 'region', operador: 'en', valores: ['CUSCO SUR', 'TACNA'] }),
    ).toBe('region:en:CUSCO SUR|TACNA');
  });

  it('escribe un rango de dos valores', () => {
    expect(escribirFiltro({ campo: 'dias_atraso', operador: 'entre', valores: ['0', '30'] })).toBe(
      'dias_atraso:entre:0|30',
    );
  });

  it('omite el valor en los operadores que no lo llevan', () => {
    expect(escribirFiltro({ campo: 'telefono', operador: 'no_vacio', valores: ['x'] })).toBe(
      'telefono:no_vacio',
    );
  });

  it('quita espacios sobrantes y valores vacíos', () => {
    expect(
      escribirFiltro({ campo: 'region', operador: 'en', valores: [' TACNA ', '', 'PUNO'] }),
    ).toBe('region:en:TACNA|PUNO');
  });
});

describe('leer filtros guardados', () => {
  it('es la inversa de escribir', () => {
    const texto = 'segmento_financiero:igual:1. Preventiva';

    expect(escribirFiltro(leerFiltro(texto))).toBe(texto);
  });

  it('conserva los dos puntos dentro del valor, como el backend', () => {
    expect(leerFiltro('observacion:contiene:hora 10:30')).toEqual({
      campo: 'observacion',
      operador: 'contiene',
      valores: ['hora 10:30'],
    });
  });

  it('lee un operador sin valor', () => {
    expect(leerFiltro('telefono:vacio')).toEqual({
      campo: 'telefono',
      operador: 'vacio',
      valores: [],
    });
  });
});

describe('cuándo un filtro está completo', () => {
  it('pide la cantidad de valores de cada operador', () => {
    expect(valoresQuePide('vacio')).toBe(0);
    expect(valoresQuePide('igual')).toBe(1);
    expect(valoresQuePide('entre')).toBe(2);
    expect(valoresQuePide('en')).toBeNull();
  });

  it('un rango con un solo extremo no está completo', () => {
    expect(filtroCompleto({ campo: 'dias_atraso', operador: 'entre', valores: ['0', ''] })).toBe(
      false,
    );
  });

  it('un filtro sin campo u operador no está completo', () => {
    expect(filtroCompleto({ campo: '', operador: 'igual', valores: ['1'] })).toBe(false);
    expect(filtroCompleto({ campo: 'dias_atraso', operador: '', valores: ['1'] })).toBe(false);
  });

  it('en necesita al menos un valor no vacío', () => {
    expect(filtroCompleto({ campo: 'region', operador: 'en', valores: [' '] })).toBe(false);
    expect(filtroCompleto({ campo: 'region', operador: 'en', valores: ['PUNO'] })).toBe(true);
  });

  it('la consulta deja fuera lo incompleto y lo marca por posición', () => {
    const borrador = {
      filtros: [
        { campo: 'dias_atraso', operador: 'mayor', valores: ['30'] },
        { campo: 'region', operador: 'igual', valores: [''] },
      ],
      orden: null,
      cantidad: null,
      indicadores: [{ nombre: '', funcion: 'conteo' as const, campo: null }],
    };

    expect(consultaDe(borrador).filtros).toEqual(['dias_atraso:mayor:30']);
    expect(consultaDe(borrador).indicadores).toEqual([]);
    expect(partesIncompletas(borrador)).toEqual({ filtros: [1], indicadores: [0] });
  });
});

describe('orden', () => {
  it('descendente se escribe con guion', () => {
    expect(escribirOrden({ campo: 'saldo_capital_pendiente', descendente: true })).toBe(
      '-saldo_capital_pendiente',
    );
    expect(leerOrden('-saldo_capital_pendiente')).toEqual({
      campo: 'saldo_capital_pendiente',
      descendente: true,
    });
  });

  it('sin campo no hay orden', () => {
    expect(escribirOrden({ campo: '', descendente: false })).toBeNull();
    expect(leerOrden(null)).toBeNull();
    expect(leerOrden('-')).toBeNull();
  });
});

describe('indicadores (RF-27)', () => {
  it('conteo puede ir sin campo', () => {
    const conteo = { nombre: 'productos', funcion: 'conteo' as const, campo: null };

    expect(indicadorCompleto(conteo)).toBe(true);
    expect(escribirIndicador(conteo)).toBe('productos:conteo');
    expect(leerIndicador('productos:conteo')).toEqual(conteo);
  });

  it('las demás funciones necesitan campo', () => {
    expect(indicadorCompleto({ nombre: 'cuota', funcion: 'promedio', campo: null })).toBe(false);
  });

  it('suma y promedio solo aplican a números', () => {
    expect(funcionAdmiteCampo('suma', 'texto')).toBe(false);
    expect(funcionAdmiteCampo('promedio', 'numero')).toBe(true);
    expect(funcionAdmiteCampo('maximo', 'fecha')).toBe(true);
  });

  it('una selección guardada vuelve al editor tal como se escribió', () => {
    const guardada = {
      filtros: ['dias_atraso:entre:0|30'],
      orden: '-saldo_capital_pendiente',
      cantidad: 500,
      indicadores: ['cuota promedio:promedio:monto_cuota'],
    };

    expect(consultaDe(borradorDe(guardada))).toEqual(guardada);
  });
});

describe('catálogo', () => {
  it('ordena los operadores para leer, sin inventar los que el campo no admite', () => {
    expect(operadoresPara(CAMPOS, 'dias_atraso')).toEqual([
      'igual',
      'en',
      'mayor',
      'entre',
      'vacio',
      'no_vacio',
    ]);
    expect(operadoresPara(CAMPOS, 'no_existe')).toEqual([]);
  });

  it('la cantidad acepta enteros dentro del tope de la API', () => {
    expect(leerCantidad('500')).toBe(500);
    expect(leerCantidad(String(CANTIDAD_MAXIMA))).toBe(CANTIDAD_MAXIMA);
    expect(leerCantidad(String(CANTIDAD_MAXIMA + 1))).toBeNull();
    expect(leerCantidad('0')).toBeNull();
    expect(leerCantidad('12.5')).toBeNull();
    expect(leerCantidad('')).toBeNull();
  });
});

describe('problemas que informa la API', () => {
  it('ubica cada problema en la fila que lo causó', () => {
    const borrador = borradorDe({
      filtros: ['dias_atraso:mayor:30', 'campo_viejo:igual:x'],
      orden: null,
      cantidad: null,
      indicadores: ['cuota:suma:region'],
    });

    const ubicados = ubicarProblemas(
      [
        { parte: 'filtro', expresion: 'campo_viejo:igual:x', detalle: 'El campo no existe' },
        { parte: 'indicador', expresion: 'cuota:suma:region', detalle: 'Solo numéricos' },
        { parte: 'cantidad', expresion: '999999', detalle: 'Fuera de rango' },
      ],
      borrador,
    );

    expect(ubicados.map((problema) => [problema.parte, problema.indice])).toEqual([
      ['filtro', 1],
      ['indicador', 0],
      ['cantidad', null],
    ]);
  });
});
