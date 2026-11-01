/**
 * Administering speech versions (T-MM-C11, M-F2; RF-MM-28 to RF-MM-30): which versions each place lists,
 * what stands where «Eliminar definitivamente» would, which option a campaign keeps chosen and how a
 * refused rename reads. What the API says (`eliminable`, `motivo_no_eliminable`) is believed: the screen
 * does not work it out from the rest of the version.
 */
import { describe, expect, it } from 'vitest';

import { ApiError } from '../../src/lib/api';
import type { VersionSpeech } from '../../src/lib/api-mowa-mes';
import {
  accionDeEliminar,
  clasificarErrorDeRenombrarSpeech,
  conVersion,
  deshabilitadas,
  habilitadas,
  opcionesDeCampana,
  preseleccionDeCampana,
  sinVersion,
  versionesDelSelector,
} from '../../src/lib/mowa-mes-speech-administracion';

const DESHABILITADA = '2026-10-31T09:00:00-05:00';

function version(parcial: Partial<VersionSpeech> = {}): VersionSpeech {
  return {
    id: 2,
    nombre: 'Speech 2',
    original: false,
    basada_en_id: 1,
    usada: false,
    editable: true,
    creado_en: '2026-10-10T08:00:00-05:00',
    deshabilitada_en: null,
    eliminable: false,
    motivo_no_eliminable: null,
    expresiones: [],
    ...parcial,
  };
}

const original = version({ id: 1, nombre: 'Speech original', original: true, motivo_no_eliminable: 'original' });
const activa = version({ id: 2, nombre: 'Activa' });
const usadaDeshabilitada = version({ id: 3, nombre: 'Usada', usada: true, deshabilitada_en: DESHABILITADA, motivo_no_eliminable: 'usada' });
const borrable = version({ id: 4, nombre: 'Borrable', deshabilitada_en: DESHABILITADA, eliminable: true });
const todas = [original, activa, usadaDeshabilitada, borrable];

describe('las habilitadas y las deshabilitadas', () => {
  it('se separan por deshabilitada_en, en el orden de la API', () => {
    expect(habilitadas(todas).map((v) => v.id)).toEqual([1, 2]);
    expect(deshabilitadas(todas).map((v) => v.id)).toEqual([3, 4]);
  });

  it('la cuenta del panel es la de las deshabilitadas', () => {
    expect(deshabilitadas(todas)).toHaveLength(2);
    expect(deshabilitadas([original, activa])).toHaveLength(0);
  });
});

describe('el selector de la configuración', () => {
  it('lista las habilitadas', () => {
    expect(versionesDelSelector(todas, 1).map((v) => v.id)).toEqual([1, 2]);
    expect(versionesDelSelector(todas, null).map((v) => v.id)).toEqual([1, 2]);
  });

  it('suma la deshabilitada que está abierta, para que diga lo que muestra el editor', () => {
    expect(versionesDelSelector(todas, 3).map((v) => v.id)).toEqual([1, 2, 3]);
  });
});

describe('en vez del botón «Eliminar definitivamente»', () => {
  it('con eliminable verdadero va el botón', () => {
    expect(accionDeEliminar(borrable)).toEqual({ tipo: 'boton' });
  });

  it('una usada dice por qué no, con la clave de errorSpeech', () => {
    expect(accionDeEliminar(usadaDeshabilitada)).toEqual({ tipo: 'motivo', clave: 'speech_usado' });
  });

  it('el Speech original dice que es el original, aunque esté deshabilitado', () => {
    expect(accionDeEliminar(version({ original: true, deshabilitada_en: DESHABILITADA, motivo_no_eliminable: 'original' }))).toEqual({
      tipo: 'motivo',
      clave: 'speech_original',
    });
  });

  it('se cree lo que dice la API: eliminable falso no lleva botón, aunque la versión parezca borrable', () => {
    // Disabled and unused, but the API says no (a campaign used it a moment ago): no button, no reason made up.
    expect(accionDeEliminar(version({ deshabilitada_en: DESHABILITADA, eliminable: false, motivo_no_eliminable: null }))).toEqual({
      tipo: 'nada',
    });
  });

  it('con eliminable verdadero, un motivo no le quita el botón', () => {
    expect(accionDeEliminar(version({ eliminable: true, motivo_no_eliminable: 'usada' }))).toEqual({ tipo: 'boton' });
  });
});

describe('el selector de la campaña', () => {
  it('ofrece solo las habilitadas, con el original primero y vacío (el valor por defecto de la API)', () => {
    const opciones = opcionesDeCampana([activa, original, usadaDeshabilitada, borrable]);
    expect(opciones.map((o) => o.valor)).toEqual(['', '2']);
    expect(opciones.map((o) => o.version.id)).toEqual([1, 2]);
  });

  it('si el original está deshabilitado, no se ofrece', () => {
    const opciones = opcionesDeCampana([{ ...original, deshabilitada_en: DESHABILITADA }, activa]);
    expect(opciones.map((o) => o.valor)).toEqual(['2']);
  });

  it('sin ninguna habilitada no hay opciones', () => {
    expect(opcionesDeCampana([usadaDeshabilitada, borrable])).toEqual([]);
    expect(opcionesDeCampana([])).toEqual([]);
  });

  it('conserva la elegida mientras se ofrezca', () => {
    const opciones = opcionesDeCampana([original, activa]);
    expect(preseleccionDeCampana(opciones, '2')).toBe('2');
    expect(preseleccionDeCampana(opciones, '')).toBe('');
  });

  it('si la elegida quedó deshabilitada, preselecciona la primera habilitada', () => {
    // The chosen version 3 was disabled: the first one offered takes its place.
    expect(preseleccionDeCampana(opcionesDeCampana([original, activa]), '3')).toBe('');
    // And with the original disabled too, the first enabled non-original one.
    expect(preseleccionDeCampana(opcionesDeCampana([{ ...original, deshabilitada_en: DESHABILITADA }, activa]), '')).toBe('2');
  });

  it('sin opciones, no hay nada que elegir', () => {
    expect(preseleccionDeCampana([], '2')).toBe('');
  });
});

describe('un renombrar rechazado', () => {
  it('409 es un nombre repetido (el PATCH no tiene otro 409)', () => {
    expect(clasificarErrorDeRenombrarSpeech(new ApiError(409, 'Ya existe'))).toEqual({ tipo: 'repetido' });
  });

  it('400 es un nombre en blanco o demasiado largo', () => {
    expect(clasificarErrorDeRenombrarSpeech(new ApiError(400, 'En blanco'))).toEqual({ tipo: 'invalido' });
  });

  it('lo demás (un 404, la red) es otro y se dice con palabras generales', () => {
    const caido = new ApiError(404, 'No existe');
    expect(clasificarErrorDeRenombrarSpeech(caido)).toEqual({ tipo: 'otro', error: caido });
    const red = new Error('red');
    expect(clasificarErrorDeRenombrarSpeech(red)).toEqual({ tipo: 'otro', error: red });
  });
});

describe('la lista tras renombrar o eliminar', () => {
  it('conVersion cambia solo la que respondió la API', () => {
    const renombrada = { ...activa, nombre: 'Nueva' };
    const lista = conVersion(todas, renombrada);
    expect(lista.map((v) => v.nombre)).toEqual(['Speech original', 'Nueva', 'Usada', 'Borrable']);
    expect(lista[0]).toBe(original);
    expect(lista[3]).toBe(borrable);
  });

  it('sinVersion quita la eliminada y deja las demás', () => {
    expect(sinVersion(todas, 4).map((v) => v.id)).toEqual([1, 2, 3]);
    expect(sinVersion(todas, 99)).toHaveLength(4);
  });
});
