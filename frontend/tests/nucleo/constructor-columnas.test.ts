/**
 * The draft of a column definition (docs/motor-texto-enriquecido-interfaz.md §5).
 * What matters: moving, duplicating and removing columns never loses or
 * shares content; the draft knows when it differs from what is saved; and
 * nothing the editor adds for itself (ids) reaches the backend.
 */
import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

import type { components } from '../../src/lib/contrato-api';

import {
  agregarColumna,
  aDefinicion,
  cambiarTipo,
  desdeDefinicion,
  definicionNueva,
  duplicarColumna,
  fijarExpresion,
  fijarFormatoFecha,
  fijarFormatoFinanciero,
  fijarProteccion,
  fijarSegmentacion,
  fijarValorPorDefecto,
  fijarVariantes,
  guardadaDesdeRespuesta,
  hayCambios,
  modoContenido,
  moverColumna,
  nombresRepetidos,
  normalizarNombre,
  quitarColumna,
  renombrarColumna,
  renombrarDefinicion,
  versionAlGuardar,
  type Borrador,
  type DefinicionGuardada,
  type Expresion,
} from '../../src/lib/constructor-columnas';

const TELEFONO: Expresion = { nodos: [{ tipo: 'variable', nombre: 'telefono', funciones: [] }] };
const VENCIMIENTO: Expresion = {
  nodos: [{ tipo: 'variable', nombre: 'fecha_vencimiento_cuota', funciones: [{ nombre: 'sumar_dias', args: [3] }] }],
};
const MENSAJE: Expresion = {
  nodos: [
    { tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'primeros', args: [8] }] },
    { tipo: 'texto', valor: ' te recuerda tu cuota' },
  ],
};

const GUARDADA: DefinicionGuardada = {
  nombre: 'SMS preventivo',
  proteger_formulas: true,
  segmentacion: {
    criterio: {
      tipo: 'calculado',
      variable_dias: 'dias_atraso',
      tabla: [
        { clave: 'preventiva', etiqueta: 'Preventiva', desde: null, hasta: 0 },
        { clave: '1_a_8', etiqueta: '1 a 8', desde: 1, hasta: 8 },
      ],
    },
    politica: 'excluir',
  },
  columnas: [
    {
      orden: 0,
      nombre: 'telefono',
      tipo: 'texto',
      formato_fecha: null,
      formato_financiero: { separador_miles: ',', separador_decimal: '.', decimales: 2 },
      expresion: TELEFONO,
      valor_por_defecto: null,
      variantes: [],
    },
    {
      orden: 1,
      nombre: 'mensaje',
      tipo: 'texto',
      formato_fecha: null,
      formato_financiero: { separador_miles: ',', separador_decimal: '.', decimales: 2 },
      expresion: MENSAJE,
      valor_por_defecto: 'sin mensaje',
      variantes: [{ segmento: 'preventiva', expresion: TELEFONO }],
    },
    {
      orden: 2,
      nombre: 'vence',
      tipo: 'fecha',
      formato_fecha: 'dd/mm/aaaa',
      formato_financiero: { separador_miles: ',', separador_decimal: '.', decimales: 2 },
      expresion: VENCIMIENTO,
      valor_por_defecto: null,
      variantes: [],
    },
  ],
};

const base = (): Borrador => desdeDefinicion(GUARDADA);
const nombres = (b: Borrador) => b.columnas.map((c) => c.nombre);

describe('ida y vuelta con el contrato', () => {
  it('lo que llega del backend vuelve igual, sin ids', () => {
    expect(aDefinicion(base())).toEqual(GUARDADA);
  });

  it('cada columna del borrador tiene un id propio y estable', () => {
    const ids = base().columnas.map((c) => c.id);

    expect(new Set(ids).size).toBe(3);
    expect(ids.every((id) => id !== '')).toBe(true);
  });

  it('el borrador no comparte referencias con lo guardado', () => {
    const borrador = base();

    borrador.columnas[1].variantes[0].expresion.nodos.push({ tipo: 'texto', valor: 'x' });
    borrador.columnas[1].formato_financiero.decimales = 9;

    expect(GUARDADA.columnas[1].variantes[0].expresion.nodos).toHaveLength(1);
    expect(GUARDADA.columnas[1].formato_financiero.decimales).toBe(2);
  });

  it('lo que sale hacia el backend tampoco comparte referencias con el borrador', () => {
    const borrador = base();

    const salida = aDefinicion(borrador);
    salida.columnas[0].expresion.nodos.push({ tipo: 'texto', valor: 'x' });

    expect(borrador.columnas[0].expresion.nodos).toHaveLength(1);
  });

  it('el orden explícito del contrato manda sobre la posición en la lista', () => {
    const desordenada: DefinicionGuardada = {
      ...GUARDADA,
      columnas: [GUARDADA.columnas[2], GUARDADA.columnas[0], GUARDADA.columnas[1]],
    };

    expect(nombres(desdeDefinicion(desordenada))).toEqual(['telefono', 'mensaje', 'vence']);
  });

  it('al salir, el orden es un entero explícito que sigue la posición', () => {
    const inicial = base();

    const salida = aDefinicion(moverColumna(inicial, inicial.columnas[2].id, -1));

    expect(salida.columnas.map((c) => [c.orden, c.nombre])).toEqual([
      [0, 'telefono'],
      [1, 'vence'],
      [2, 'mensaje'],
    ]);
  });

  it('una definición sin segmentación sigue sin segmentación', () => {
    const sin = { ...GUARDADA, segmentacion: null };

    expect(aDefinicion(desdeDefinicion(sin)).segmentacion).toBeNull();
  });
});

describe('definición nueva', () => {
  it('arranca con una columna vacía y la protección de fórmulas puesta', () => {
    const nueva = definicionNueva();

    expect(nueva.nombre).toBe('');
    expect(nueva.columnas).toHaveLength(1);
    expect(nueva.columnas[0]).toMatchObject({ nombre: '', tipo: 'texto', valor_por_defecto: null, variantes: [] });
    expect(nueva.columnas[0].expresion.nodos).toEqual([]);
    expect(nueva.proteger_formulas).toBe(true);
    expect(nueva.segmentacion).toBeNull();
  });
});

describe('agregar una columna', () => {
  it('va al final por defecto y devuelve su id para abrirla', () => {
    const { borrador, id } = agregarColumna(base());

    expect(borrador.columnas).toHaveLength(4);
    expect(borrador.columnas.at(-1)?.id).toBe(id);
    expect(borrador.columnas.at(-1)).toMatchObject({ nombre: '', tipo: 'texto' });
  });

  it('puede ir justo después de otra', () => {
    const inicial = base();

    const { borrador, id } = agregarColumna(inicial, inicial.columnas[0].id);

    expect(borrador.columnas[1].id).toBe(id);
    expect(nombres(borrador)).toEqual(['telefono', '', 'mensaje', 'vence']);
  });

  it('una referencia que ya no existe la agrega al final', () => {
    const { borrador } = agregarColumna(base(), 'no-existe');

    expect(borrador.columnas).toHaveLength(4);
    expect(borrador.columnas.at(-1)?.nombre).toBe('');
  });

  it('no modifica el borrador de partida', () => {
    const inicial = base();

    agregarColumna(inicial);

    expect(inicial.columnas).toHaveLength(3);
  });
});

describe('quitar una columna', () => {
  it('la saca y lleva el foco a la siguiente', () => {
    const inicial = base();

    const { borrador, foco } = quitarColumna(inicial, inicial.columnas[1].id);

    expect(nombres(borrador)).toEqual(['telefono', 'vence']);
    expect(foco).toBe(inicial.columnas[2].id);
  });

  it('si era la última, el foco va a la anterior', () => {
    const inicial = base();

    const { borrador, foco } = quitarColumna(inicial, inicial.columnas[2].id);

    expect(nombres(borrador)).toEqual(['telefono', 'mensaje']);
    expect(foco).toBe(inicial.columnas[1].id);
  });

  it('la única columna se puede quitar y no deja foco', () => {
    const solo = definicionNueva();

    const { borrador, foco } = quitarColumna(solo, solo.columnas[0].id);

    expect(borrador.columnas).toEqual([]);
    expect(foco).toBeNull();
  });

  it('un id desconocido no cambia nada', () => {
    const inicial = base();

    const { borrador, foco } = quitarColumna(inicial, 'no-existe');

    expect(borrador).toBe(inicial);
    expect(foco).toBeNull();
  });
});

describe('mover una columna', () => {
  it('sube y baja una posición', () => {
    const inicial = base();

    expect(nombres(moverColumna(inicial, inicial.columnas[1].id, -1))).toEqual(['mensaje', 'telefono', 'vence']);
    expect(nombres(moverColumna(inicial, inicial.columnas[1].id, 1))).toEqual(['telefono', 'vence', 'mensaje']);
  });

  it('en los extremos no hace nada y devuelve el mismo borrador', () => {
    const inicial = base();

    expect(moverColumna(inicial, inicial.columnas[0].id, -1)).toBe(inicial);
    expect(moverColumna(inicial, inicial.columnas[2].id, 1)).toBe(inicial);
  });

  it('la columna movida conserva su id, su contenido y sus variantes', () => {
    const inicial = base();
    const original = inicial.columnas[1];

    const movida = moverColumna(inicial, original.id, -1).columnas[0];

    expect(movida).toEqual(original);
  });

  it('un id desconocido no cambia nada', () => {
    const inicial = base();

    expect(moverColumna(inicial, 'no-existe', 1)).toBe(inicial);
  });

  it('el orden resultante es el que viaja al backend', () => {
    const inicial = base();

    const salida = aDefinicion(moverColumna(inicial, inicial.columnas[2].id, -1));

    expect(salida.columnas.map((c) => c.nombre)).toEqual(['telefono', 'vence', 'mensaje']);
  });
});

describe('duplicar una columna', () => {
  it('queda justo después con un id nuevo y el mismo contenido', () => {
    const inicial = base();
    const original = inicial.columnas[1];

    const { borrador, id } = duplicarColumna(inicial, original.id);

    expect(borrador.columnas[2].id).toBe(id);
    expect(id).not.toBe(original.id);
    expect(borrador.columnas[2].expresion).toEqual(original.expresion);
    expect(borrador.columnas[2].variantes).toEqual(original.variantes);
    expect(borrador.columnas[2].valor_por_defecto).toBe('sin mensaje');
  });

  it('no comparte contenido con la original', () => {
    const inicial = base();

    const { borrador } = duplicarColumna(inicial, inicial.columnas[1].id);
    borrador.columnas[2].expresion.nodos.push({ tipo: 'texto', valor: 'x' });
    borrador.columnas[2].variantes[0].expresion.nodos.push({ tipo: 'texto', valor: 'x' });

    expect(borrador.columnas[1].expresion.nodos).toHaveLength(2);
    expect(borrador.columnas[1].variantes[0].expresion.nodos).toHaveLength(1);
  });

  it('el nombre de la copia es único aunque se duplique varias veces', () => {
    let borrador = base();
    const id = borrador.columnas[1].id;

    borrador = duplicarColumna(borrador, id, 'copia').borrador;
    borrador = duplicarColumna(borrador, id, 'copia').borrador;
    borrador = duplicarColumna(borrador, id, 'copia').borrador;

    expect(nombres(borrador)).toEqual([
      'telefono',
      'mensaje',
      'mensaje (copia 3)',
      'mensaje (copia 2)',
      'mensaje (copia)',
      'vence',
    ]);
  });

  it('un nombre ya ocupado, aunque difiera en tildes o mayúsculas, no se repite', () => {
    let borrador = base();
    borrador = renombrarColumna(borrador, borrador.columnas[2].id, 'Mensáje (COPIA)');

    const copia = duplicarColumna(borrador, borrador.columnas[1].id, 'copia').borrador;

    expect(copia.columnas[2].nombre).toBe('mensaje (copia 2)');
  });

  it('una columna sin nombre se copia sin nombre', () => {
    const solo = definicionNueva();

    const { borrador } = duplicarColumna(solo, solo.columnas[0].id);

    expect(nombres(borrador)).toEqual(['', '']);
  });

  it('un id desconocido no cambia nada', () => {
    const inicial = base();

    const { borrador, id } = duplicarColumna(inicial, 'no-existe');

    expect(borrador).toBe(inicial);
    expect(id).toBeNull();
  });
});

describe('nombres repetidos (pista preventiva; el backend manda)', () => {
  it('normaliza sin tildes, sin mayúsculas y sin espacios de los extremos', () => {
    expect(normalizarNombre('  Número  ')).toBe(normalizarNombre('numero'));
    expect(normalizarNombre('Saldo Capital')).not.toBe(normalizarNombre('saldo_capital'));
  });

  it('marca todas las columnas que comparten nombre', () => {
    let borrador = base();
    borrador = renombrarColumna(borrador, borrador.columnas[2].id, ' TELEFONO ');

    const repetidos = nombresRepetidos(borrador);

    expect([...repetidos].sort()).toEqual([borrador.columnas[0].id, borrador.columnas[2].id].sort());
  });

  it('los nombres vacíos no cuentan como repetidos', () => {
    const { borrador } = agregarColumna(agregarColumna(definicionNueva()).borrador);

    expect(nombresRepetidos(borrador).size).toBe(0);
  });
});

describe('editar una columna', () => {
  it('renombra solo esa columna y no recorta lo que escribe el analista', () => {
    const inicial = base();

    const borrador = renombrarColumna(inicial, inicial.columnas[0].id, 'nuevo ');

    expect(nombres(borrador)).toEqual(['nuevo ', 'mensaje', 'vence']);
    expect(nombres(inicial)).toEqual(['telefono', 'mensaje', 'vence']);
  });

  it('fija la expresión de la columna', () => {
    const inicial = base();

    const borrador = fijarExpresion(inicial, inicial.columnas[0].id, MENSAJE);

    expect(borrador.columnas[0].expresion).toEqual(MENSAJE);
  });

  it('fija las variantes sin tocar el contenido por defecto', () => {
    const inicial = base();
    const variantes = [{ segmento: '1_a_8', expresion: VENCIMIENTO }];

    const borrador = fijarVariantes(inicial, inicial.columnas[0].id, variantes);

    expect(borrador.columnas[0].variantes).toEqual(variantes);
    expect(borrador.columnas[0].expresion).toEqual(TELEFONO);
  });

  it('un id desconocido no cambia nada', () => {
    const inicial = base();

    expect(renombrarColumna(inicial, 'no-existe', 'x')).toBe(inicial);
    expect(fijarExpresion(inicial, 'no-existe', MENSAJE)).toBe(inicial);
  });
});

describe('tipo y formato', () => {
  it('pasar a otro tipo descarta el formato que ya no aplica', () => {
    let borrador = base();
    const idFecha = borrador.columnas[2].id;

    borrador = cambiarTipo(borrador, idFecha, 'financiero');

    expect(borrador.columnas[2].tipo).toBe('financiero');
    expect(borrador.columnas[2].formato_fecha).toBeNull();
  });

  it('pasar de financiero a otro tipo vuelve el formato financiero al de por defecto', () => {
    let borrador = base();
    const id = borrador.columnas[0].id;
    borrador = cambiarTipo(borrador, id, 'financiero');
    borrador = fijarFormatoFinanciero(borrador, id, { decimales: 4, separador_miles: ' ' });

    borrador = cambiarTipo(borrador, id, 'numero');

    expect(borrador.columnas[0].formato_financiero).toEqual({
      separador_miles: ',',
      separador_decimal: '.',
      decimales: 2,
    });
  });

  it('mantener el mismo tipo conserva el formato', () => {
    const inicial = base();

    const borrador = cambiarTipo(inicial, inicial.columnas[2].id, 'fecha');

    expect(borrador.columnas[2].formato_fecha).toBe('dd/mm/aaaa');
  });

  it('fija el patrón de fecha', () => {
    const inicial = base();

    const borrador = fijarFormatoFecha(inicial, inicial.columnas[2].id, 'aaaa-mm-dd');

    expect(borrador.columnas[2].formato_fecha).toBe('aaaa-mm-dd');
  });

  it('sucesivos ajustes del formato financiero se acumulan', () => {
    const id = base().columnas[0].id;
    let borrador = desdeDefinicion(GUARDADA);
    borrador = fijarFormatoFinanciero(borrador, borrador.columnas[0].id, { separador_miles: ' ' });
    borrador = fijarFormatoFinanciero(borrador, borrador.columnas[0].id, { decimales: 0 });

    expect(borrador.columnas[0].formato_financiero).toEqual({ separador_miles: ' ', separador_decimal: '.', decimales: 0 });
    expect(id).not.toBe(borrador.columnas[0].id);
  });

  it('fija solo lo que se le pasa del formato financiero', () => {
    const inicial = base();

    const borrador = fijarFormatoFinanciero(inicial, inicial.columnas[0].id, { decimales: 3 });

    expect(borrador.columnas[0].formato_financiero).toEqual({
      separador_miles: ',',
      separador_decimal: '.',
      decimales: 3,
    });
  });
});

describe('valor por defecto', () => {
  it('un valor vacío es ninguno (null), no un texto vacío', () => {
    const inicial = base();

    const borrador = fijarValorPorDefecto(inicial, inicial.columnas[1].id, '');

    expect(borrador.columnas[1].valor_por_defecto).toBeNull();
  });

  it('conserva lo escrito, espacios incluidos', () => {
    const inicial = base();

    const borrador = fijarValorPorDefecto(inicial, inicial.columnas[0].id, ' — ');

    expect(borrador.columnas[0].valor_por_defecto).toBe(' — ');
  });
});

describe('la definición', () => {
  it('renombra, fija la protección de fórmulas y la segmentación', () => {
    let borrador = base();

    borrador = renombrarDefinicion(borrador, 'Otra');
    borrador = fijarProteccion(borrador, false);
    borrador = fijarSegmentacion(borrador, null);

    expect(borrador.nombre).toBe('Otra');
    expect(borrador.proteger_formulas).toBe(false);
    expect(borrador.segmentacion).toBeNull();
  });
});

describe('modo del contenido de una columna', () => {
  it('sin nodos es vacío', () => {
    expect(modoContenido({ nodos: [] })).toBe('vacio');
  });

  it('un solo nodo variable, con o sin funciones, es variable directa', () => {
    expect(modoContenido(TELEFONO)).toBe('variable');
    expect(modoContenido(VENCIMIENTO)).toBe('variable');
  });

  it('un solo texto o varios nodos es texto compuesto', () => {
    expect(modoContenido({ nodos: [{ tipo: 'texto', valor: 'fijo' }] })).toBe('texto');
    expect(modoContenido(MENSAJE)).toBe('texto');
  });
});

describe('¿hay cambios sin guardar?', () => {
  it('un borrador recién cargado no los tiene', () => {
    expect(hayCambios(GUARDADA, base())).toBe(false);
  });

  it.each<[string, (b: Borrador) => Borrador]>([
    ['el nombre de la definición', (b) => renombrarDefinicion(b, 'otra')],
    ['la protección', (b) => fijarProteccion(b, false)],
    ['la segmentación', (b) => fijarSegmentacion(b, null)],
    ['el nombre de una columna', (b) => renombrarColumna(b, b.columnas[0].id, 'otra')],
    ['el orden', (b) => moverColumna(b, b.columnas[0].id, 1)],
    ['una columna agregada', (b) => agregarColumna(b).borrador],
    ['una columna quitada', (b) => quitarColumna(b, b.columnas[0].id).borrador],
    ['una columna duplicada', (b) => duplicarColumna(b, b.columnas[0].id).borrador],
    ['el tipo', (b) => cambiarTipo(b, b.columnas[0].id, 'numero')],
    ['el patrón de fecha', (b) => fijarFormatoFecha(b, b.columnas[2].id, 'aaaa')],
    ['el formato financiero', (b) => fijarFormatoFinanciero(b, b.columnas[0].id, { decimales: 0 })],
    ['el valor por defecto', (b) => fijarValorPorDefecto(b, b.columnas[0].id, 'x')],
    ['la expresión', (b) => fijarExpresion(b, b.columnas[0].id, MENSAJE)],
    ['las variantes', (b) => fijarVariantes(b, b.columnas[1].id, [])],
  ])('detecta un cambio en %s', (_nombre, cambio) => {
    expect(hayCambios(GUARDADA, cambio(base()))).toBe(true);
  });

  it('volver a dejarlo como estaba ya no cuenta como cambio', () => {
    let borrador = base();
    borrador = renombrarColumna(borrador, borrador.columnas[0].id, 'otra');
    borrador = renombrarColumna(borrador, borrador.columnas[0].id, 'telefono');

    expect(hayCambios(GUARDADA, borrador)).toBe(false);
  });

  it('mover y devolver la columna a su sitio tampoco', () => {
    let borrador = base();
    borrador = moverColumna(borrador, borrador.columnas[0].id, 1);
    borrador = moverColumna(borrador, borrador.columnas[1].id, -1);

    expect(hayCambios(GUARDADA, borrador)).toBe(false);
  });

  it('la marca obligatoria ausente es lo mismo que false: el editor la omite y el backend la devuelve siempre', () => {
    const conMarca: Expresion = {
      nodos: [{ tipo: 'variable', nombre: 'telefono', funciones: [], obligatoria: false }],
    };
    const guardada: DefinicionGuardada = {
      ...GUARDADA,
      columnas: GUARDADA.columnas.map((c, i) => (i === 0 ? { ...c, expresion: conMarca } : c)),
    };
    let borrador = desdeDefinicion(guardada);

    borrador = fijarExpresion(borrador, borrador.columnas[0].id, TELEFONO);

    expect(hayCambios(guardada, borrador)).toBe(false);
  });

  it('el orden de las variantes no es un cambio: se quita una y se vuelve a poner', () => {
    const dos = [
      { segmento: 'preventiva', expresion: TELEFONO },
      { segmento: '1_a_8', expresion: VENCIMIENTO },
    ];
    const guardada: DefinicionGuardada = {
      ...GUARDADA,
      columnas: GUARDADA.columnas.map((c, i) => (i === 1 ? { ...c, variantes: dos } : c)),
    };
    let borrador = desdeDefinicion(guardada);

    // The selector appends a variant that is set again, so it ends up last.
    borrador = fijarVariantes(borrador, borrador.columnas[1].id, [dos[1], dos[0]]);

    expect(hayCambios(guardada, borrador)).toBe(false);
  });

  it('cambiar el contenido de una variante sí es un cambio, esté donde esté', () => {
    const dos = [
      { segmento: 'preventiva', expresion: TELEFONO },
      { segmento: '1_a_8', expresion: VENCIMIENTO },
    ];
    const guardada: DefinicionGuardada = {
      ...GUARDADA,
      columnas: GUARDADA.columnas.map((c, i) => (i === 1 ? { ...c, variantes: dos } : c)),
    };
    let borrador = desdeDefinicion(guardada);

    borrador = fijarVariantes(borrador, borrador.columnas[1].id, [dos[1], { segmento: 'preventiva', expresion: MENSAJE }]);

    expect(hayCambios(guardada, borrador)).toBe(true);
  });

  it('lo mismo dentro de una variante', () => {
    const conMarca: Expresion = {
      nodos: [{ tipo: 'variable', nombre: 'telefono', funciones: [], obligatoria: false }],
    };
    const guardada: DefinicionGuardada = {
      ...GUARDADA,
      columnas: GUARDADA.columnas.map((c, i) =>
        i === 1 ? { ...c, variantes: [{ segmento: 'preventiva', expresion: conMarca }] } : c,
      ),
    };
    let borrador = desdeDefinicion(guardada);

    borrador = fijarVariantes(borrador, borrador.columnas[1].id, [{ segmento: 'preventiva', expresion: TELEFONO }]);

    expect(hayCambios(guardada, borrador)).toBe(false);
  });

  it('obligatoria en true sí es un cambio, también dentro de una variante', () => {
    const inicial = base();
    const obligatoria: Expresion = {
      nodos: [{ tipo: 'variable', nombre: 'telefono', funciones: [], obligatoria: true }],
    };

    expect(hayCambios(GUARDADA, fijarExpresion(inicial, inicial.columnas[0].id, obligatoria))).toBe(true);
    expect(
      hayCambios(GUARDADA, fijarVariantes(inicial, inicial.columnas[1].id, [{ segmento: 'preventiva', expresion: obligatoria }])),
    ).toBe(true);
  });

  it('los espacios de los extremos de un nombre son un cambio', () => {
    const inicial = base();

    const borrador = renombrarColumna(inicial, inicial.columnas[0].id, 'telefono ');

    expect(hayCambios(GUARDADA, borrador)).toBe(true);
  });
});

/**
 * Compile-time contract with the generated types (`astro check` runs this file). The backend's
 * input models accept extra keys, so the generated types carry an index signature, and only a
 * `type` alias (never an `interface`) is assignable to one: if someone turns a shape of the
 * constructor, or of `expresion.ts`, back into an interface, this stops compiling.
 */
describe('compatibilidad con el contrato generado (B4a)', () => {
  it('lo que sale hacia el backend es asignable a la entrada de la previsualización', () => {
    const entrada: components['schemas']['DefinicionColumnasEntrada'] = aDefinicion(base());

    expect(entrada.columnas).toHaveLength(3);
    expect(entrada.columnas[0]).toHaveProperty('orden', 0);
  });

  it('una definición nueva también, con la expresión vacía y el orden siempre presentes', () => {
    const entrada: components['schemas']['DefinicionColumnasEntrada'] = aDefinicion(definicionNueva());

    expect(entrada.columnas[0]).toMatchObject({ nombre: '', orden: 0, expresion: { nodos: [] } });
  });

  // `astro check` catches a top-level interface (`DefinicionGuardada`) but let a nested one through in
  // a mutation run, while `tsc --noEmit` caught it. This reads this module's own source so the
  // ordinary suite fails whichever way the compiler is run. (`expresion.ts` is `designer`'s: its own
  // guard belongs in his tests, not in a list of names kept here.)
  it('constructor-columnas.ts no declara ninguna interface: sus formas viajan al backend', () => {
    const fuente = readFileSync(new URL('../../src/lib/constructor-columnas.ts', import.meta.url), 'utf-8');

    expect(fuente.match(/export interface \w+/)?.[0]).toBeUndefined();
  });
});

/** A saved definition as `GET /definiciones-columnas/{id}` answers it (B4b). Synthetic data only. */
function respuesta(parcial: Partial<components['schemas']['DefinicionRespuesta']> = {}) {
  const completa: components['schemas']['DefinicionRespuesta'] = {
    id: 7,
    nombre: 'SMS preventivo',
    creado_en: '2026-10-01T09:00:00-05:00',
    actualizado_en: '2026-10-03T09:00:00-05:00',
    version_vigente: 3,
    versiones: [
      { numero: 1, creado_en: '2026-10-01T09:00:00-05:00', usada_en: '2026-10-02T10:00:00-05:00', usada: true },
      { numero: 2, creado_en: '2026-10-02T09:00:00-05:00', usada_en: null, usada: false },
      { numero: 3, creado_en: '2026-10-03T09:00:00-05:00', usada_en: null, usada: false },
    ],
    version: {
      numero: 3,
      creado_en: '2026-10-03T09:00:00-05:00',
      usada_en: null,
      usada: false,
      contenido: {
        proteger_formulas: true,
        segmentacion: {
          criterio: {
            tipo: 'calculado',
            variable_dias: 'dias_atraso',
            tabla: [
              { clave: 'preventiva', etiqueta: 'Preventiva', desde: null, hasta: 0 },
              { clave: '1_a_8', etiqueta: '1 a 8', desde: 1, hasta: 8 },
            ],
          },
          politica: 'excluir',
        },
        columnas: [
          {
            nombre: 'telefono',
            orden: 0,
            tipo: 'texto',
            formato_fecha: null,
            formato_financiero: { separador_miles: ',', separador_decimal: '.', decimales: 2 },
            expresion: { nodos: [{ tipo: 'variable', nombre: 'telefono', funciones: [], obligatoria: false }] },
            valor_por_defecto: null,
            variantes: [],
          },
          {
            nombre: 'mensaje',
            orden: 1,
            tipo: 'texto',
            formato_fecha: null,
            formato_financiero: { separador_miles: ',', separador_decimal: '.', decimales: 2 },
            expresion: {
              nodos: [
                { tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'primeros', args: [8] }], obligatoria: true },
                { tipo: 'texto', valor: ' te recuerda tu cuota' },
              ],
            },
            valor_por_defecto: 'sin mensaje',
            variantes: [
              { segmento: 'preventiva', expresion: { nodos: [{ tipo: 'texto', valor: 'Hola' }] } },
            ],
          },
        ],
      },
    },
  };
  return { ...completa, ...parcial };
}

describe('leer una definición guardada (B4b)', () => {
  it('la respuesta del backend se lee sin casts: nombre, protección, segmentación y columnas', () => {
    const guardada: DefinicionGuardada = guardadaDesdeRespuesta(respuesta());

    expect(guardada.nombre).toBe('SMS preventivo');
    expect(guardada.proteger_formulas).toBe(true);
    expect(guardada.segmentacion?.criterio).toMatchObject({ tipo: 'calculado', variable_dias: 'dias_atraso' });
    expect(guardada.segmentacion?.politica).toBe('excluir');
    expect(guardada.columnas.map((c) => [c.orden, c.nombre])).toEqual([
      [0, 'telefono'],
      [1, 'mensaje'],
    ]);
    expect(guardada.columnas[1].variantes[0]).toEqual({
      segmento: 'preventiva',
      expresion: { nodos: [{ tipo: 'texto', valor: 'Hola' }] },
    });
    expect(guardada.columnas[1].valor_por_defecto).toBe('sin mensaje');
  });

  it('una definición sin segmentación llega sin segmentación', () => {
    const base = respuesta();

    const guardada = guardadaDesdeRespuesta({
      ...base,
      version: { ...base.version, contenido: { ...base.version.contenido, segmentacion: null } },
    });

    expect(guardada.segmentacion).toBeNull();
  });

  it('lo leído no comparte referencias con la respuesta', () => {
    const r = respuesta();

    const guardada = guardadaDesdeRespuesta(r);
    guardada.columnas[1].variantes[0].expresion.nodos.push({ tipo: 'texto', valor: 'x' });

    expect(r.version.contenido.columnas[1].variantes[0].expresion.nodos).toHaveLength(1);
  });

  it('un borrador recién leído de la respuesta no tiene cambios', () => {
    const guardada = guardadaDesdeRespuesta(respuesta());

    expect(hayCambios(guardada, desdeDefinicion(guardada))).toBe(false);
  });
});

describe('qué versión crea el guardado y qué se muestra', () => {
  it('una definición nueva crea la versión 1 y su nombre se escribe', () => {
    expect(versionAlGuardar(null)).toEqual({ nueva: 1, mostrada: null, usada: false, nombreEditable: true });
  });

  it('una guardada crea la siguiente a la vigente, aunque se esté viendo una más antigua', () => {
    const vistaAntigua = respuesta({
      version: { ...respuesta().version, numero: 1, usada: true, usada_en: '2026-10-02T10:00:00-05:00' },
    });

    expect(versionAlGuardar(vistaAntigua)).toEqual({ nueva: 4, mostrada: 1, usada: true, nombreEditable: false });
  });

  it('la vigente sin usar también crea una versión nueva: ninguna se modifica', () => {
    expect(versionAlGuardar(respuesta())).toEqual({ nueva: 4, mostrada: 3, usada: false, nombreEditable: false });
  });
});
