/**
 * Renaming a saved definition (RF-56, §10.1). What costs a team when it is wrong: the button blocking
 * a change the backend accepts (a case-only rename), the screen taking the *latest* version's content
 * when the rename answers (an old version is open, read-only), or one refusal read as another.
 */
import { describe, expect, it } from 'vitest';

import { ApiError, NetworkError } from '../../src/lib/api';
import type { DefinicionGuardadaRespuesta, ResumenDefinicion } from '../../src/lib/api-definiciones';
import {
  clasificarErrorDeRenombrar,
  conNombreRenombrado,
  hayNombreNuevo,
  listaConNombre,
} from '../../src/lib/renombrar-definicion';

describe('hayNombreNuevo', () => {
  it('el mismo nombre no tiene nada que hacer, con o sin espacios en los extremos', () => {
    expect(hayNombreNuevo('SMS preventivo', 'SMS preventivo')).toBe(false);
    expect(hayNombreNuevo('SMS preventivo', '  SMS preventivo  ')).toBe(false);
  });

  it('cambiar solo las mayúsculas es un cambio: el backend lo acepta y lo guarda', () => {
    expect(hayNombreNuevo('SMS preventivo', 'Sms preventivo')).toBe(true);
  });

  it('cambiar solo una tilde o un espacio interior también cuenta', () => {
    expect(hayNombreNuevo('Cobranza', 'Cobranzá')).toBe(true);
    expect(hayNombreNuevo('SMS preventivo', 'SMS  preventivo')).toBe(true);
  });

  it('un nombre vacío es un cambio: lo rechaza el backend, no la interfaz', () => {
    expect(hayNombreNuevo('SMS preventivo', '')).toBe(true);
    expect(hayNombreNuevo('SMS preventivo', '   ')).toBe(true);
  });
});

describe('clasificarErrorDeRenombrar', () => {
  const problemaDeNombre = {
    codigo: 'definicion_invalida',
    detalle: 'El nombre debe tener entre 1 y 120 caracteres',
    ubicacion: null,
    nombre: null,
    columna: null,
    segmento: null,
    campo: 'nombre',
  };

  it('409 nombre_repetido es «repetido»', () => {
    expect(clasificarErrorDeRenombrar(new ApiError(409, 'Ya hay una definición', 'nombre_repetido'))).toEqual({
      tipo: 'repetido',
    });
  });

  it('un 409 que no es de nombre repetido no se toma por tal', () => {
    expect(clasificarErrorDeRenombrar(new ApiError(409, 'otra cosa', 'otro_codigo')).tipo).toBe('otro');
  });

  it('400 con el problema ubicado en el campo nombre es «invalido»', () => {
    const error = new ApiError(400, 'x', 'definicion_invalida', { problemas: [problemaDeNombre] });
    expect(clasificarErrorDeRenombrar(error)).toEqual({ tipo: 'invalido' });
  });

  it('un 400 cuyos problemas son de otro campo (o ninguno) no es de nombre', () => {
    const deOtroCampo = new ApiError(400, 'x', 'definicion_invalida', {
      problemas: [{ ...problemaDeNombre, campo: 'formato_fecha' }],
    });
    expect(clasificarErrorDeRenombrar(deOtroCampo).tipo).toBe('otro');
    expect(clasificarErrorDeRenombrar(new ApiError(400, 'x', 'definicion_invalida', { problemas: [] })).tipo).toBe('otro');
    expect(clasificarErrorDeRenombrar(new ApiError(400, 'x')).tipo).toBe('otro');
  });

  it('404 es «no_existe»', () => {
    expect(clasificarErrorDeRenombrar(new ApiError(404, 'x', 'definicion_no_encontrada'))).toEqual({ tipo: 'no_existe' });
  });

  it('una red caída u otro fallo es «otro» y conserva el error', () => {
    const red = new NetworkError();
    expect(clasificarErrorDeRenombrar(red)).toEqual({ tipo: 'otro', error: red });
    expect(clasificarErrorDeRenombrar(new ApiError(500, 'x')).tipo).toBe('otro');
  });
});

describe('lo que queda en pantalla al renombrar', () => {
  const mostrada = {
    id: 7,
    nombre: 'SMS preventivo',
    creado_en: '2026-10-01T09:00:00-05:00',
    actualizado_en: '2026-10-03T09:00:00-05:00',
    version_vigente: 3,
    versiones: [{ numero: 1 }, { numero: 2 }, { numero: 3 }],
    version: { numero: 2, contenido: { columnas: ['de la versión 2'] } },
  } as unknown as DefinicionGuardadaRespuesta;
  // What the API really answers: the whole definition with its LATEST version, not just the name.
  const renombrada = {
    id: 7,
    nombre: 'SMS preventivo B',
    creado_en: '2026-10-01T09:00:00-05:00',
    actualizado_en: '2026-10-19T10:00:00-05:00',
    version_vigente: 3,
    versiones: [{ numero: 1 }, { numero: 2 }, { numero: 3 }, { numero: 4 }],
    version: { numero: 3, contenido: { columnas: ['de la vigente'] } },
  } as unknown as DefinicionGuardadaRespuesta;

  it('toma el nombre y la fecha, y deja la versión que se estaba mirando', () => {
    const nueva = conNombreRenombrado(mostrada, renombrada);
    expect(nueva.nombre).toBe('SMS preventivo B');
    expect(nueva.actualizado_en).toBe('2026-10-19T10:00:00-05:00');
    expect(nueva.version).toBe(mostrada.version);
    expect(nueva.versiones).toBe(mostrada.versiones);
    expect(nueva.version_vigente).toBe(3);
    expect(nueva.version.numero).toBe(2);
  });

  it('no modifica lo que recibe', () => {
    conNombreRenombrado(mostrada, renombrada);
    expect(mostrada.nombre).toBe('SMS preventivo');
  });

  it('en la lista cambia solo la definición renombrada', () => {
    const lista = [
      { id: 7, nombre: 'SMS preventivo', version_vigente: 3, cantidad_versiones: 3, actualizado_en: 'a', vigente_usada: false },
      { id: 9, nombre: 'WhatsApp', version_vigente: 1, cantidad_versiones: 1, actualizado_en: 'b', vigente_usada: true },
    ] as ResumenDefinicion[];
    const nueva = listaConNombre(lista, 7, renombrada);
    expect(nueva.map((d) => d.nombre)).toEqual(['SMS preventivo B', 'WhatsApp']);
    expect(nueva[0]).toMatchObject({ id: 7, version_vigente: 3, cantidad_versiones: 3, actualizado_en: '2026-10-19T10:00:00-05:00' });
    expect(nueva[1]).toBe(lista[1]);
    expect(lista[0].nombre).toBe('SMS preventivo');
  });

  it('una definición que no está en la lista la deja como está', () => {
    expect(listaConNombre([], 7, renombrada)).toEqual([]);
  });
});
