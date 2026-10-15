/**
 * The segmentation of a definition (docs/motor-texto-enriquecido-interfaz.md §5.1): off by
 * default, calculated from the days of delay against the context's table, or by the value of a
 * field. The variants of the columns depend on it: without a segmentation there are none, and
 * changing the criterion leaves the old keys without a segment.
 */
import { describe, expect, it } from 'vitest';

import {
  agregarColumna,
  definicionNueva,
  desdeDefinicion,
  fijarExpresion,
  fijarVariantes,
  type Borrador,
  type DefinicionGuardada,
  type Expresion,
} from '../../src/lib/constructor-columnas';
import {
  activarSegmentacion,
  columnasConVariantes,
  desactivarSegmentacion,
  fijarCriterioCalculado,
  fijarCriterioCampo,
  fijarPolitica,
  quitarTodasLasVariantes,
  segmentosDe,
  valoresEnUso,
  type ContextoSegmentos,
} from '../../src/lib/constructor-segmentacion';

const HOLA: Expresion = { nodos: [{ tipo: 'texto', valor: 'Hola' }] };

const CONTEXTO: ContextoSegmentos = {
  variable_dias: 'dias_atraso',
  tabla: [
    { clave: 'preventiva', etiqueta: 'Preventiva', desde: null, hasta: 0 },
    { clave: '1_a_8', etiqueta: '1 a 8', desde: 1, hasta: 8 },
    { clave: '9_a_30', etiqueta: '9 a 30', desde: 9, hasta: 30 },
  ],
};

/** A draft with two columns; the first carries variants for two segments. */
function conVariantes(): Borrador {
  let b = agregarColumna(definicionNueva()).borrador;
  b = activarSegmentacion(b, CONTEXTO);
  b = fijarExpresion(b, b.columnas[0].id, HOLA);
  b = fijarExpresion(b, b.columnas[1].id, HOLA);
  return fijarVariantes(b, b.columnas[0].id, [
    { segmento: 'preventiva', expresion: HOLA },
    { segmento: '1_a_8', expresion: HOLA },
  ]);
}

describe('activar y desactivar', () => {
  it('activar pone el criterio calculado con la tabla del contexto y excluye lo que no cae en un rango', () => {
    const b = activarSegmentacion(definicionNueva(), CONTEXTO);

    expect(b.segmentacion).toEqual({
      criterio: { tipo: 'calculado', variable_dias: 'dias_atraso', tabla: CONTEXTO.tabla },
      politica: 'excluir',
    });
  });

  it('la tabla del borrador es una copia: no se comparte con el contexto', () => {
    const b = activarSegmentacion(definicionNueva(), CONTEXTO);

    if (b.segmentacion?.criterio.tipo === 'calculado') b.segmentacion.criterio.tabla[0].etiqueta = 'otra';

    expect(CONTEXTO.tabla[0].etiqueta).toBe('Preventiva');
  });

  it('activar una definición que ya la tiene no la pisa', () => {
    let b = activarSegmentacion(definicionNueva(), CONTEXTO);
    b = fijarPolitica(b, 'usar_por_defecto');

    expect(activarSegmentacion(b, CONTEXTO).segmentacion?.politica).toBe('usar_por_defecto');
  });

  it('desactivar la quita y, sin ella, ninguna columna conserva variantes', () => {
    const b = desactivarSegmentacion(conVariantes());

    expect(b.segmentacion).toBeNull();
    expect(columnasConVariantes(b)).toBe(0);
  });
});

describe('el criterio', () => {
  it('por campo guarda el campo y conserva la política', () => {
    let b = activarSegmentacion(definicionNueva(), CONTEXTO);
    b = fijarPolitica(b, 'usar_por_defecto');

    b = fijarCriterioCampo(b, 'segmento_financiero');

    expect(b.segmentacion).toEqual({
      criterio: { tipo: 'campo', campo: 'segmento_financiero' },
      politica: 'usar_por_defecto',
    });
  });

  it('volver a calculado trae la tabla del contexto otra vez', () => {
    let b = fijarCriterioCampo(activarSegmentacion(definicionNueva(), CONTEXTO), 'segmento_financiero');

    b = fijarCriterioCalculado(b, CONTEXTO);

    expect(b.segmentacion?.criterio).toEqual({ tipo: 'calculado', variable_dias: 'dias_atraso', tabla: CONTEXTO.tabla });
  });

  it('volver a calculado conserva la política que se había elegido', () => {
    let b = activarSegmentacion(definicionNueva(), CONTEXTO);
    b = fijarPolitica(b, 'usar_por_defecto');
    b = fijarCriterioCampo(b, 'segmento_financiero');

    b = fijarCriterioCalculado(b, CONTEXTO);

    expect(b.segmentacion?.politica).toBe('usar_por_defecto');
  });

  it('cambiar el criterio no toca las variantes: el aviso y la decisión son de la pantalla', () => {
    const b = fijarCriterioCampo(conVariantes(), 'segmento_financiero');

    expect(columnasConVariantes(b)).toBe(1);
  });

  it('sin segmentación, cambiar el criterio no la inventa', () => {
    expect(fijarCriterioCampo(definicionNueva(), 'x').segmentacion).toBeNull();
    expect(fijarPolitica(definicionNueva(), 'excluir').segmentacion).toBeNull();
  });
});

describe('qué segmentos ofrece', () => {
  it('el criterio calculado ofrece los rangos de su tabla, en orden', () => {
    const b = activarSegmentacion(definicionNueva(), CONTEXTO);

    expect(segmentosDe(b.segmentacion, [])).toEqual(CONTEXTO.tabla);
  });

  it('el criterio por campo ofrece los valores que se le dieron, sin repetir y sin vacíos', () => {
    const b = fijarCriterioCampo(activarSegmentacion(definicionNueva(), CONTEXTO), 'segmento_financiero');

    const segmentos = segmentosDe(b.segmentacion, ['Vigente', 'Vigente', ' ', 'Vencido']);

    expect(segmentos.map((s) => s.clave)).toEqual(['Vigente', 'Vencido']);
    expect(segmentos[0]).toEqual({ clave: 'Vigente', etiqueta: 'Vigente', desde: null, hasta: null });
  });

  it('sin segmentación no ofrece ninguno', () => {
    expect(segmentosDe(null, ['x'])).toEqual([]);
  });
});

describe('variantes en uso', () => {
  it('cuenta las columnas con variantes', () => {
    expect(columnasConVariantes(conVariantes())).toBe(1);
    expect(columnasConVariantes(definicionNueva())).toBe(0);
  });

  it('los valores en uso son las claves de las variantes de todas las columnas, sin repetir', () => {
    let b = conVariantes();
    b = fijarVariantes(b, b.columnas[1].id, [
      { segmento: '1_a_8', expresion: HOLA },
      { segmento: '9_a_30', expresion: HOLA },
    ]);

    expect(valoresEnUso(b)).toEqual(['preventiva', '1_a_8', '9_a_30']);
  });

  it('quitar todas las variantes las deja sin variantes y no toca el contenido por defecto', () => {
    const b = quitarTodasLasVariantes(conVariantes());

    expect(columnasConVariantes(b)).toBe(0);
    expect(b.columnas.map((c) => c.expresion)).toEqual(conVariantes().columnas.map((c) => c.expresion));
  });

  it('una definición guardada con variantes se lee igual', () => {
    const guardada: DefinicionGuardada = {
      nombre: 'x',
      proteger_formulas: true,
      segmentacion: { criterio: { tipo: 'campo', campo: 'segmento_financiero' }, politica: 'excluir' },
      columnas: [
        {
          orden: 0,
          nombre: 'a',
          tipo: 'texto',
          formato_fecha: null,
          formato_financiero: { separador_miles: ',', separador_decimal: '.', decimales: 2 },
          expresion: HOLA,
          valor_por_defecto: null,
          variantes: [{ segmento: 'Vigente', expresion: HOLA }],
        },
      ],
    };

    expect(valoresEnUso(desdeDefinicion(guardada))).toEqual(['Vigente']);
  });
});
