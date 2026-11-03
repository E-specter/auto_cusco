/**
 * What the saved-texts component decides on its own (docs/motor-texto-enriquecido-interfaz.md §11.3, RF-69): which
 * mode a text is in, what saving does, when deleting is offered, how a refusal is read. All data is invented.
 */
import { describe, expect, it } from 'vitest';

import { ApiError } from '../../src/lib/api';
import type { ResumenTexto, TextoRespuesta } from '../../src/lib/api-textos-guardados';
import {
  clasificarError,
  descartar,
  esEditable,
  hayNombreNuevo,
  iguales,
  listaConNombre,
  modoInicial,
  problemasPorCampo,
  puedeEliminar,
  puedeGuardar,
  repartir,
  usarComoBase,
  vecinoDe,
  versionAlGuardar,
} from '../../src/lib/textos-guardados';

function texto(mostrada: number, vigente: number, parcial: Partial<TextoRespuesta> = {}, usadas: number[] = []): TextoRespuesta {
  const versiones = Array.from({ length: vigente }, (_, i) => ({
    numero: i + 1,
    creado_en: '2026-10-01T09:00:00-05:00',
    usada_en: usadas.includes(i + 1) ? '2026-10-03T10:00:00-05:00' : null,
    usada: usadas.includes(i + 1),
  }));
  return {
    id: 1,
    contexto: 'c',
    nombre: 'Preventivo',
    creado_en: '2026-10-01T09:00:00-05:00',
    actualizado_en: '2026-10-01T09:00:00-05:00',
    deshabilitado_en: null,
    version_vigente: vigente,
    versiones,
    version: { ...versiones[mostrada - 1], contenido: { texto: 'x' } },
    ...parcial,
  };
}

const resumen = (id: number, nombre: string, deshabilitado = false): ResumenTexto => ({
  id,
  contexto: 'c',
  nombre,
  version_vigente: 1,
  cantidad_versiones: 1,
  actualizado_en: '2026-10-01T09:00:00-05:00',
  vigente_usada: false,
  deshabilitado_en: deshabilitado ? '2026-10-05T10:00:00-05:00' : null,
  eliminable: true,
});

describe('el modo de un texto', () => {
  it('uno que no se guardó es nuevo, la versión vigente se edita y una anterior se lee', () => {
    expect(modoInicial(null)).toBe('nuevo');
    expect(modoInicial(texto(3, 3))).toBe('editable');
    expect(modoInicial(texto(1, 3))).toBe('lectura');
  });

  it('un texto deshabilitado se ve solo para leer, sea cual sea la versión', () => {
    expect(modoInicial(texto(3, 3, { deshabilitado_en: '2026-10-05T10:00:00-05:00' }))).toBe('deshabilitado');
    expect(modoInicial(texto(1, 3, { deshabilitado_en: '2026-10-05T10:00:00-05:00' }))).toBe('deshabilitado');
  });

  it('se edita en nuevo, editable y base; nada más', () => {
    expect(esEditable('nuevo')).toBe(true);
    expect(esEditable('editable')).toBe(true);
    expect(esEditable('base')).toBe(true);
    expect(esEditable('lectura')).toBe(false);
    expect(esEditable('deshabilitado')).toBe(false);
  });

  it('«Usar como base» solo cambia una versión anterior, y «Descartar» la devuelve a lectura', () => {
    expect(usarComoBase('lectura')).toBe('base');
    expect(usarComoBase('editable')).toBe('editable');
    expect(usarComoBase('deshabilitado')).toBe('deshabilitado');
    expect(descartar('base')).toBe('lectura');
    expect(descartar('nuevo')).toBe('nuevo');
    expect(descartar('editable')).toBe('editable');
  });
});

describe('guardar', () => {
  it('crea la versión siguiente a la vigente, aunque se esté viendo una anterior', () => {
    expect(versionAlGuardar(null)).toEqual({ nueva: 1, actual: null });
    expect(versionAlGuardar(texto(3, 3))).toEqual({ nueva: 4, actual: 3 });
    expect(versionAlGuardar(texto(1, 3))).toEqual({ nueva: 4, actual: 3 });
  });

  it('se ofrece con cambios; sobre una versión antigua tomada como base, también sin ellos; nunca en lectura ni guardando', () => {
    expect(puedeGuardar('editable', true)).toBe(true);
    expect(puedeGuardar('editable', false)).toBe(false);
    expect(puedeGuardar('nuevo', false)).toBe(false);
    expect(puedeGuardar('base', false)).toBe(true);
    expect(puedeGuardar('lectura', true)).toBe(false);
    expect(puedeGuardar('deshabilitado', true)).toBe(false);
    expect(puedeGuardar('editable', true, true)).toBe(false);
    expect(puedeGuardar('base', true, true)).toBe(false);
  });
});

describe('eliminar', () => {
  it('se ofrece solo si ninguna versión se usó, aunque la que se usó no sea la vigente', () => {
    expect(puedeEliminar(texto(2, 2))).toBe(true);
    expect(puedeEliminar(texto(2, 2, {}, [2]))).toBe(false);
    expect(puedeEliminar(texto(2, 2, {}, [1]))).toBe(false);
  });
});

describe('comparar contenidos', () => {
  it('es igual sin importar el orden de las claves, y distingue lo que cambió', () => {
    expect(iguales({ a: 1, b: { c: [1, 2], d: 'x' } }, { b: { d: 'x', c: [1, 2] }, a: 1 })).toBe(true);
    expect(iguales({ texto: 'a' }, { texto: 'b' })).toBe(false);
    expect(iguales({ a: [1, 2] }, { a: [2, 1] })).toBe(false);
    expect(iguales({}, {})).toBe(true);
  });
});

describe('las listas', () => {
  it('reparte lo que trae el listado completo en habilitados y deshabilitados, en su orden', () => {
    const { habilitados, deshabilitados } = repartir([resumen(1, 'A'), resumen(2, 'B', true), resumen(3, 'C'), resumen(4, 'D', true)]);
    expect(habilitados.map((t) => t.id)).toEqual([1, 3]);
    expect(deshabilitados.map((t) => t.id)).toEqual([2, 4]);
    expect(repartir([])).toEqual({ habilitados: [], deshabilitados: [] });
  });

  it('renombra uno y deja los demás como están', () => {
    const lista = [resumen(1, 'A'), resumen(2, 'B')];
    const nueva = listaConNombre(lista, 2, 'Z');
    expect(nueva.map((t) => t.nombre)).toEqual(['A', 'Z']);
    expect(nueva[0]).toBe(lista[0]);
  });

  it('el que toma la selección al irse uno es el siguiente, y si era el último, el anterior', () => {
    const lista = [resumen(1, 'A'), resumen(2, 'B'), resumen(3, 'C')];
    expect(vecinoDe(lista, 2)?.id).toBe(3);
    expect(vecinoDe(lista, 3)?.id).toBe(2);
    expect(vecinoDe(lista, 1)?.id).toBe(2);
    expect(vecinoDe([resumen(1, 'A')], 1)).toBeNull();
    expect(vecinoDe(lista, 99)?.id).toBe(1);
    expect(vecinoDe([], 1)).toBeNull();
  });

  it('«Renombrar» solo tiene algo que hacer si el nombre cambió, sin contar los espacios de los extremos', () => {
    expect(hayNombreNuevo('Preventivo', ' Preventivo ')).toBe(false);
    expect(hayNombreNuevo('Preventivo', 'preventivo')).toBe(true);
    expect(hayNombreNuevo('Preventivo', '')).toBe(true);
  });
});

describe('leer un rechazo por su código', () => {
  const rechazo = (estado: number, codigo: string | null, cuerpo: Record<string, unknown> | null = null) =>
    new ApiError(estado, 'detalle', codigo, cuerpo);

  it('distingue los casos que la pantalla cuenta con sus palabras', () => {
    expect(clasificarError(rechazo(409, 'nombre_repetido')).tipo).toBe('repetido');
    expect(clasificarError(rechazo(409, 'texto_guardado_deshabilitado')).tipo).toBe('deshabilitado');
    expect(clasificarError(rechazo(409, 'texto_guardado_usado')).tipo).toBe('usado');
    expect(clasificarError(rechazo(400, 'contexto_guardado_desconocido')).tipo).toBe('contexto');
    expect(clasificarError(rechazo(400, 'texto_guardado_invalido')).tipo).toBe('invalido');
    expect(clasificarError(rechazo(404, 'texto_guardado_no_encontrado')).tipo).toBe('no_existe');
  });

  it('un 409 con otro código, o un error que no es del API, es «otro»', () => {
    expect(clasificarError(rechazo(409, 'otra_cosa')).tipo).toBe('otro');
    expect(clasificarError(rechazo(500, null)).tipo).toBe('otro');
    expect(clasificarError(new Error('red')).tipo).toBe('otro');
  });

  it('reparte los problemas de un 400 entre el nombre y el contenido', () => {
    const base = { detalle: 'x', ubicacion: null, nombre: null, columna: null, segmento: null };
    const error = rechazo(400, 'texto_guardado_invalido', {
      problemas: [
        { ...base, codigo: 'texto_guardado_invalido', campo: 'nombre' },
        { ...base, codigo: 'expresion_invalida', campo: 'contenido' },
        { ...base, codigo: 'limite_excedido', campo: null },
      ],
    });
    const { nombre, contenido } = problemasPorCampo(error);
    expect(nombre.map((p) => p.codigo)).toEqual(['texto_guardado_invalido']);
    expect(contenido.map((p) => p.codigo)).toEqual(['expresion_invalida', 'limite_excedido']);
  });
});
