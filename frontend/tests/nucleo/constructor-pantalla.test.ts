/**
 * What the `/columnas` screen decides from the draft and the backend's answers, kept out of the
 * page so it can be tested without a browser: where each located problem belongs, and how a
 * column's content reads in the list.
 */
import { describe, expect, it } from 'vitest';

import type { ProblemaDefinicion } from '../../src/lib/api-definiciones';
import {
  agregarColumna,
  definicionNueva,
  fijarExpresion,
  renombrarColumna,
  type Borrador,
  type Expresion,
} from '../../src/lib/constructor-columnas';
import {
  agruparProblemas,
  destinoDeProblema,
  ejemploFinanciero,
  resumenDeContenido,
} from '../../src/lib/constructor-pantalla';

const problema = (parcial: Partial<ProblemaDefinicion> = {}): ProblemaDefinicion => ({
  codigo: 'definicion_invalida',
  detalle: 'x',
  ubicacion: null,
  nombre: null,
  columna: null,
  segmento: null,
  campo: null,
  ...parcial,
});

/** A draft with three columns, so a problem's `columna` index has something to point at. */
function borrador(): Borrador {
  let b = definicionNueva();
  b = renombrarColumna(b, b.columnas[0].id, 'telefono');
  b = agregarColumna(b).borrador;
  b = agregarColumna(b).borrador;
  return b;
}

describe('a dónde va cada problema', () => {
  it('un problema de la columna 1 va a la segunda columna del borrador, por su id', () => {
    const b = borrador();

    const destino = destinoDeProblema(problema({ columna: 1, campo: 'nombre' }), b);

    expect(destino).toEqual({ tipo: 'columna', id: b.columnas[1].id, campo: 'nombre', segmento: null });
  });

  it('sin `campo` es del contenido de la columna, y con segmento es de su variante', () => {
    const b = borrador();

    expect(destinoDeProblema(problema({ columna: 0 }), b)).toMatchObject({ campo: 'expresion', segmento: null });
    expect(destinoDeProblema(problema({ columna: 2, segmento: '1_a_8' }), b)).toMatchObject({
      id: b.columnas[2].id,
      campo: 'expresion',
      segmento: '1_a_8',
    });
  });

  it('un formato de fecha mal escrito se queda en su campo de la columna', () => {
    const b = borrador();

    expect(destinoDeProblema(problema({ columna: 0, campo: 'formato_fecha' }), b)).toMatchObject({
      tipo: 'columna',
      campo: 'formato_fecha',
    });
  });

  it('el nombre de la definición, las columnas y la segmentación son de la definición', () => {
    const b = borrador();

    expect(destinoDeProblema(problema({ campo: 'nombre' }), b)).toEqual({ tipo: 'definicion', campo: 'nombre' });
    expect(destinoDeProblema(problema({ campo: 'columnas' }), b)).toEqual({ tipo: 'definicion', campo: 'columnas' });
    expect(destinoDeProblema(problema({ campo: 'segmentacion' }), b)).toEqual({
      tipo: 'definicion',
      campo: 'segmentacion',
    });
  });

  it('un problema sin ningún campo ni columna es de toda la definición', () => {
    expect(destinoDeProblema(problema(), borrador())).toEqual({ tipo: 'definicion', campo: null });
  });

  it('una columna que ya no existe (se quitó mientras se editaba) no se pega a otra: va a la definición', () => {
    const b = borrador();

    expect(destinoDeProblema(problema({ columna: 7, campo: 'nombre' }), b)).toEqual({
      tipo: 'definicion',
      campo: null,
    });
  });
});

describe('agrupar para mostrarlos', () => {
  it('junta los de cada columna por su id y deja aparte los de la definición', () => {
    const b = borrador();
    const nombre = problema({ columna: 1, campo: 'nombre', detalle: 'sin nombre' });
    const contenido = problema({ columna: 1, detalle: 'variable desconocida' });
    const defNombre = problema({ campo: 'nombre', detalle: 'nombre repetido' });

    const grupos = agruparProblemas([nombre, contenido, defNombre], b);

    expect(grupos.definicion).toEqual([defNombre]);
    expect(grupos.porColumna.get(b.columnas[1].id)).toEqual([nombre, contenido]);
    expect(grupos.porColumna.has(b.columnas[0].id)).toBe(false);
    expect(grupos.total).toBe(3);
  });

  it('el orden es el del backend, y sin problemas no hay grupos', () => {
    const grupos = agruparProblemas([], borrador());

    expect(grupos.total).toBe(0);
    expect(grupos.definicion).toEqual([]);
    expect(grupos.porColumna.size).toBe(0);
  });
});

describe('cómo se lee el contenido de una columna en la lista', () => {
  const etiqueta = (nombre: string) =>
    ({ titular: 'Titular', fecha_vencimiento_cuota: 'Vencimiento', telefono: 'Teléfono' })[nombre] ?? nombre;

  it('una columna vacía lo dice', () => {
    expect(resumenDeContenido({ nodos: [] }, etiqueta)).toEqual({ modo: 'vacio' });
  });

  it('una variable directa sin funciones nombra la variable', () => {
    const e: Expresion = { nodos: [{ tipo: 'variable', nombre: 'telefono', funciones: [] }] };

    expect(resumenDeContenido(e, etiqueta)).toEqual({ modo: 'variable', variable: 'Teléfono', funciones: 0 });
  });

  it('con funciones cuenta cuántas, sin leerlas ni evaluarlas', () => {
    const e: Expresion = {
      nodos: [
        {
          tipo: 'variable',
          nombre: 'fecha_vencimiento_cuota',
          funciones: [
            { nombre: 'sumar_dias', args: [3] },
            { nombre: 'formato_fecha', args: ['dd/mm/aaaa'] },
          ],
        },
      ],
    };

    expect(resumenDeContenido(e, etiqueta)).toEqual({ modo: 'variable', variable: 'Vencimiento', funciones: 2 });
  });

  it('un texto compuesto muestra el principio, con el nombre visible de cada variable y sin sintaxis', () => {
    const e: Expresion = {
      nodos: [
        { tipo: 'variable', nombre: 'titular', funciones: [] },
        { tipo: 'texto', valor: ' te recuerda que tu cuota vence el ' },
        { tipo: 'variable', nombre: 'fecha_vencimiento_cuota', funciones: [] },
      ],
    };

    const resumen = resumenDeContenido(e, etiqueta, 30);

    expect(resumen).toMatchObject({ modo: 'texto', variables: 2, recortado: true });
    expect((resumen as { fragmento: string }).fragmento.startsWith('Titular te recuerda')).toBe(true);
    expect((resumen as { fragmento: string }).fragmento).not.toMatch(/[{}\[\]@|]/);
    expect((resumen as { fragmento: string }).fragmento.length).toBeLessThanOrEqual(30);
  });

  it('un texto corto no se recorta', () => {
    const e: Expresion = { nodos: [{ tipo: 'texto', valor: 'Hola' }] };

    expect(resumenDeContenido(e, etiqueta)).toEqual({ modo: 'texto', fragmento: 'Hola', variables: 0, recortado: false });
  });

  it('un salto de línea se ve como un espacio en la lista', () => {
    const e: Expresion = { nodos: [{ tipo: 'texto', valor: 'uno\ndos' }] };

    expect(resumenDeContenido(e, etiqueta)).toMatchObject({ fragmento: 'uno dos' });
  });

  it('una expresión de solo un texto vacío cuenta como vacía', () => {
    const e: Expresion = { nodos: [{ tipo: 'texto', valor: '' }] };

    expect(resumenDeContenido(e, etiqueta)).toEqual({ modo: 'vacio' });
  });
});

describe('ejemplo del formato de un importe', () => {
  it('con los separadores por defecto', () => {
    expect(ejemploFinanciero({ separador_miles: ',', separador_decimal: '.', decimales: 2 })).toBe('1,234.50');
  });

  it('con otros separadores y sin decimales', () => {
    expect(ejemploFinanciero({ separador_miles: '.', separador_decimal: ',', decimales: 0 })).toBe('1.235');
  });

  it('con coma decimal y punto de miles, con decimales', () => {
    expect(ejemploFinanciero({ separador_miles: '.', separador_decimal: ',', decimales: 2 })).toBe('1.234,50');
  });

  it('sin separador de miles', () => {
    expect(ejemploFinanciero({ separador_miles: '', separador_decimal: '.', decimales: 3 })).toBe('1234.500');
  });
});

describe('el borrador no se modifica', () => {
  it('agrupar y ubicar no tocan el borrador', () => {
    const b = fijarExpresion(borrador(), borrador().columnas[0].id, { nodos: [] });
    const antes = JSON.stringify(b);

    agruparProblemas([problema({ columna: 0 })], b);
    destinoDeProblema(problema({ columna: 0 }), b);

    expect(JSON.stringify(b)).toBe(antes);
  });
});
