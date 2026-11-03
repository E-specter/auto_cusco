/**
 * The draft of a column definition with a platform and with labels (RF-49, RF-72;
 * docs/motor-texto-enriquecido-interfaz.md §11.1 and §11.2): the fixed columns hold the top, the headers by
 * position follow the columns that still carry them, and a free file behaves exactly as before.
 */
import { describe, expect, it } from 'vitest';

import {
  aDefinicion,
  agregarColumna,
  definicionNueva,
  desdeDefinicion,
  duplicarColumna,
  fijarEtiqueta,
  fijarPlataforma,
  hayCambios,
  moverColumna,
  quitarColumna,
  renombrarColumna,
  type Borrador,
} from '../../src/lib/constructor-columnas';
import { hayContenido } from '../../src/lib/constructor-version';
import type { ReglasPlataforma } from '../../src/lib/plataformas';

const reglas = (parcial: Partial<ReglasPlataforma> = {}): ReglasPlataforma => ({
  clave: 'sintetica',
  etiqueta: 'Sintética',
  columnas_fijas: [
    { posicion: 1, nombre: 'destino', contenido_por_defecto: '51[@telefono]', tipo: 'texto', celda_texto: true, contenido_editable: true },
  ],
  encabezado_por_posicion: '[$VAR{n}$]',
  tipo_resto: 'texto',
  admite_mas_columnas: true,
  ...parcial,
});

const nombres = (b: Borrador) => b.columnas.map((c) => c.nombre);

/** destino, [$VAR1$], [$VAR2$], [$VAR3$] */
function conTresMacros(r = reglas()): Borrador {
  let b = definicionNueva(r);
  for (let i = 0; i < 3; i += 1) b = agregarColumna(b, null, r).borrador;
  return b;
}

describe('una definición nueva con plataforma', () => {
  it('arranca con las columnas fijas: su nombre, su tipo, su contenido y su celda de texto', () => {
    const b = definicionNueva(reglas());
    expect(b.plataforma).toBe('sintetica');
    expect(nombres(b)).toEqual(['destino']);
    expect(b.columnas[0].tipo).toBe('texto');
    expect(b.columnas[0].expresion.nodos).toEqual([
      { tipo: 'texto', valor: '51' },
      { tipo: 'variable', nombre: 'telefono', funciones: [] },
    ]);
    expect(b.columnas[0].celda_texto).toBe(true);
  });

  it('una fija sin celda de texto no lo declara', () => {
    const r = reglas({ columnas_fijas: [{ posicion: 1, nombre: 'canal', contenido_por_defecto: null, tipo: 'texto', celda_texto: false, contenido_editable: true }] });
    expect(definicionNueva(r).columnas[0].celda_texto).toBeUndefined();
    expect(definicionNueva(r).columnas[0].expresion.nodos).toEqual([]);
  });

  it('sin columnas fijas empieza con una columna con el encabezado de su posición y el tipo del resto', () => {
    const b = definicionNueva(reglas({ columnas_fijas: [], tipo_resto: 'numero' }));
    expect(nombres(b)).toEqual(['[$VAR1$]']);
    expect(b.columnas[0].tipo).toBe('numero');
  });

  it('sin plataforma es lo de siempre: una columna vacía y ninguna plataforma', () => {
    const b = definicionNueva();
    expect(b.plataforma).toBeNull();
    expect(nombres(b)).toEqual(['']);
    expect(aDefinicion(b)).not.toHaveProperty('plataforma');
  });

  it('cambiar la plataforma de lo no guardado vuelve a empezar desde lo que fija, y conserva el nombre', () => {
    const libre = renombrarDefinicion(definicionNueva(), 'SMS');
    const conPlataforma = fijarPlataforma(libre, reglas());
    expect(conPlataforma.nombre).toBe('SMS');
    expect(nombres(conPlataforma)).toEqual(['destino']);
    expect(nombres(fijarPlataforma(conPlataforma, null))).toEqual(['']);
    expect(fijarPlataforma(conPlataforma, null).plataforma).toBeNull();
  });
});

function renombrarDefinicion(b: Borrador, nombre: string): Borrador {
  return { ...b, nombre };
}

describe('la plataforma viaja con la definición', () => {
  it('se manda solo cuando hay una, y vuelve igual al leerla', () => {
    const b = definicionNueva(reglas());
    const guardada = aDefinicion(b);
    expect(guardada.plataforma).toBe('sintetica');
    expect(desdeDefinicion(guardada).plataforma).toBe('sintetica');
    expect(desdeDefinicion({ ...guardada, plataforma: null }).plataforma).toBeNull();
    expect(desdeDefinicion({ ...guardada, plataforma: undefined }).plataforma).toBeNull();
  });
});

describe('agregar una columna con plataforma', () => {
  it('nace con el encabezado y el tipo de su posición', () => {
    const r = reglas({ tipo_resto: 'numero' });
    const { borrador, id } = agregarColumna(definicionNueva(r), null, r);
    expect(nombres(borrador)).toEqual(['destino', '[$VAR1$]']);
    expect(borrador.columnas.find((c) => c.id === id)?.tipo).toBe('numero');
  });

  it('nunca queda por encima de una fija, ni siquiera pidiéndolo después de ninguna', () => {
    const r = reglas();
    const base = definicionNueva(r);
    const { borrador } = agregarColumna(base, base.columnas[0].id, r);
    expect(nombres(borrador)).toEqual(['destino', '[$VAR1$]']);
  });

  it('en medio, renumera las que siguen y conservan su encabezado por defecto', () => {
    const r = reglas();
    const b = conTresMacros(r);
    const { borrador } = agregarColumna(b, b.columnas[1].id, r);
    expect(nombres(borrador)).toEqual(['destino', '[$VAR1$]', '[$VAR2$]', '[$VAR3$]', '[$VAR4$]']);
  });

  it('sin plataforma sigue siendo una columna vacía', () => {
    expect(nombres(agregarColumna(definicionNueva()).borrador)).toEqual(['', '']);
  });
});

describe('mover con plataforma', () => {
  it('una fija no se mueve y nada sube por encima de ella', () => {
    const r = reglas();
    const b = conTresMacros(r);
    expect(moverColumna(b, b.columnas[0].id, 1, r)).toBe(b);
    expect(moverColumna(b, b.columnas[1].id, -1, r)).toBe(b);
  });

  it('al mover, las columnas que conservan su encabezado se renumeran por su posición nueva', () => {
    const r = reglas();
    const b = conTresMacros(r);
    const movido = moverColumna(b, b.columnas[1].id, 1, r);
    expect(nombres(movido)).toEqual(['destino', '[$VAR1$]', '[$VAR2$]', '[$VAR3$]']);
    // Misma columna de antes, ahora en la posición 2: es la que lleva el contenido de la primera.
    expect(movido.columnas[2].id).toBe(b.columnas[1].id);
  });

  it('una columna renombrada conserva su nombre al moverse', () => {
    const r = reglas();
    const b = conTresMacros(r);
    const conNombre = renombrarColumna(b, b.columnas[1].id, 'Nombres del titular');
    const movido = moverColumna(conNombre, conNombre.columnas[1].id, 1, r);
    expect(nombres(movido)).toEqual(['destino', '[$VAR1$]', 'Nombres del titular', '[$VAR3$]']);
  });

  it('sin plataforma mueve como siempre, hasta la primera posición', () => {
    const b = agregarColumna(definicionNueva()).borrador;
    expect(moverColumna(b, b.columnas[1].id, -1)).not.toBe(b);
  });
});

describe('quitar y duplicar con plataforma', () => {
  it('una fija no se quita ni se duplica', () => {
    const r = reglas();
    const b = conTresMacros(r);
    expect(quitarColumna(b, b.columnas[0].id, r)).toEqual({ borrador: b, foco: null });
    expect(duplicarColumna(b, b.columnas[0].id, 'copia', r)).toEqual({ borrador: b, id: null });
  });

  it('al quitar una columna, las de abajo se renumeran', () => {
    const r = reglas();
    const b = conTresMacros(r);
    const { borrador } = quitarColumna(b, b.columnas[1].id, r);
    expect(nombres(borrador)).toEqual(['destino', '[$VAR1$]', '[$VAR2$]']);
  });

  it('una copia toma el encabezado de su posición y no «(copia)»; las de abajo se renumeran', () => {
    const r = reglas();
    const b = conTresMacros(r);
    const { borrador, id } = duplicarColumna(b, b.columnas[1].id, 'copia', r);
    expect(nombres(borrador)).toEqual(['destino', '[$VAR1$]', '[$VAR2$]', '[$VAR3$]', '[$VAR4$]']);
    expect(borrador.columnas[2].id).toBe(id);
  });

  it('sin patrón, la copia se llama como siempre', () => {
    const r = reglas({ encabezado_por_posicion: null });
    const { borrador, id } = agregarColumna(definicionNueva(r), null, r);
    const conNombre = renombrarColumna(borrador, id, 'x');
    expect(nombres(duplicarColumna(conNombre, id, 'copia', r).borrador)).toEqual(['destino', 'x', 'x (copia)']);
  });
});

describe('la etiqueta de una columna', () => {
  it('se guarda como se escribió, y vacía o de espacios es ninguna', () => {
    const b = definicionNueva();
    const id = b.columnas[0].id;
    expect(fijarEtiqueta(b, id, 'Nombres del titular').columnas[0].etiqueta).toBe('Nombres del titular');
    expect(fijarEtiqueta(b, id, '  Con espacios ').columnas[0].etiqueta).toBe('  Con espacios ');
    expect(fijarEtiqueta(fijarEtiqueta(b, id, 'x'), id, '').columnas[0].etiqueta).toBeNull();
    expect(fijarEtiqueta(b, id, '   ').columnas[0].etiqueta).toBeNull();
  });

  it('viaja a la definición, y escribirla o borrarla cuenta como un cambio sin guardar', () => {
    const b = definicionNueva();
    const id = b.columnas[0].id;
    const guardada = aDefinicion(renombrarColumna(b, id, 'a'));
    const base = desdeDefinicion(guardada);
    const con = fijarEtiqueta(base, base.columnas[0].id, 'x');
    expect(hayCambios(guardada, con)).toBe(true);
    expect(aDefinicion(con).columnas[0].etiqueta).toBe('x');
    // Una columna guardada sin etiqueta y la misma con la etiqueta vacía son lo mismo.
    expect(hayCambios({ ...guardada, columnas: [{ ...guardada.columnas[0], etiqueta: null }] }, desdeDefinicion(guardada))).toBe(false);
  });

  it('una definición guardada sin etiquetas se lee igual', () => {
    const guardada = aDefinicion(renombrarColumna(definicionNueva(), definicionNueva().columnas[0].id, 'a'));
    expect(guardada.columnas[0].etiqueta).toBeUndefined();
    expect(desdeDefinicion(guardada).columnas[0].etiqueta).toBeUndefined();
  });
});

describe('hayContenido con plataforma', () => {
  it('las columnas con que arranca la plataforma no son algo que el analista escribió', () => {
    const r = reglas();
    expect(hayContenido(definicionNueva(r), r)).toBe(false);
  });

  it('escribir el nombre, tocar una fija, agregar una columna o ponerle etiqueta sí cuentan', () => {
    const r = reglas();
    const base = definicionNueva(r);
    expect(hayContenido({ ...base, nombre: 'SMS' }, r)).toBe(true);
    expect(hayContenido(fijarEtiqueta(base, base.columnas[0].id, 'x'), r)).toBe(true);
    expect(hayContenido(agregarColumna(base, null, r).borrador, r)).toBe(true);
    expect(hayContenido(fijarEtiqueta(fijarEtiqueta(base, base.columnas[0].id, 'x'), base.columnas[0].id, ''), r)).toBe(false);
  });

  it('sin plataforma una etiqueta es contenido, y lo demás no cambia', () => {
    const b = definicionNueva();
    expect(hayContenido(b)).toBe(false);
    expect(hayContenido(fijarEtiqueta(b, b.columnas[0].id, 'x'))).toBe(true);
  });
});
