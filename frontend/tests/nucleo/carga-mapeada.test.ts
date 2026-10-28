/**
 * What the upload's second step says (T-MAP-F2): why «Confirmar y cargar» is off, how a refusal of the
 * mapper reads by its `codigo`, how the reading options are named and which of them a format admits.
 */
import { beforeEach, describe, expect, it } from 'vitest';

import { ApiError, NetworkError } from '../../src/lib/api';
import {
  campoDelError,
  codigoDeError,
  conMarcaDeDetectado,
  esBorradorPerdido,
  hojasDelError,
  motivoDeConfirmar,
  nombreDeSeparador,
  opcionesQueAplican,
  problemasDeLaConfirmacion,
  textoDeError,
  type Problema,
} from '../../src/lib/carga-mapeada';
import { setLanguageForTests } from './idioma';

beforeEach(() => setLanguageForTests('es'));

const rechazo = (status: number, codigo: string | null, datos: Record<string, unknown> = {}) =>
  new ApiError(status, 'detalle en el idioma del servidor', codigo, { detail: 'x', ...(codigo ? { codigo } : {}), ...datos });
const problema = (codigo: string, campo: string | null = null): Problema => ({ indice: null, codigo, detalle: 'x', campo }) as Problema;
const etiqueta = (nombre: string) => (nombre === 'pagare' ? 'Pagaré' : nombre);
const estado = (parcial: Partial<{ problemas: Problema[]; listo: boolean; pendiente: boolean }>) => ({
  problemas: [],
  listo: false,
  pendiente: false,
  ...parcial,
});

describe('el motivo por el que «Confirmar y cargar» está apagado', () => {
  it('con el mapeo listo no hay motivo: se puede confirmar', () => {
    expect(motivoDeConfirmar(estado({ listo: true }), etiqueta)).toBeNull();
  });

  it('mientras se revisa, lo dice, aunque el mapeo parezca listo', () => {
    expect(motivoDeConfirmar(estado({ listo: true, pendiente: true }), etiqueta)).toBe('Revisando las columnas…');
  });

  it('un obligatorio sin columna va primero y se nombra por su etiqueta visible', () => {
    const problemas = [problema('parecido_sin_revisar', 'titular'), problema('obligatorio_sin_columna', 'pagare')];
    expect(motivoDeConfirmar(estado({ problemas }), etiqueta)).toBe('Falta asignar el campo obligatorio Pagaré.');
  });

  it('cuenta las columnas por revisar, en singular y en plural', () => {
    expect(motivoDeConfirmar(estado({ problemas: [problema('parecido_sin_revisar')] }), etiqueta)).toBe('Revisa 1 columna para poder cargar.');
    expect(
      motivoDeConfirmar(estado({ problemas: [problema('parecido_sin_revisar'), problema('parecido_sin_revisar')] }), etiqueta),
    ).toBe('Revisa 2 columnas para poder cargar.');
  });

  it('otros problemas piden corregir lo marcado; sin problemas ni listo, que no se pudo revisar', () => {
    expect(motivoDeConfirmar(estado({ problemas: [problema('campo_repetido', 'titular')] }), etiqueta)).toBe(
      'Corrige las columnas marcadas para poder cargar.',
    );
    expect(motivoDeConfirmar(estado({}), etiqueta)).toBe('No se pudieron revisar las columnas. Vuelve a intentarlo.');
  });

  it('nunca confirma por defecto: todo lo no listo tiene un motivo', () => {
    for (const parcial of [{}, { pendiente: true }, { problemas: [problema('x')] }]) {
      expect(motivoDeConfirmar(estado(parcial), etiqueta)).not.toBeNull();
    }
  });
});

describe('el texto de un rechazo del lector, por su código', () => {
  const red = 'sin red';
  const general = 'algo falló';

  it('toma el texto de la interfaz, no el detalle del servidor', () => {
    expect(textoDeError(rechazo(400, 'archivo_vacio'), red, general)).toBe('El archivo está vacío.');
  });

  it('rellena lo que el cuerpo trae: el máximo y la hoja', () => {
    expect(textoDeError(rechazo(413, 'archivo_demasiado_grande', { maximo_mb: 64 }), red, general)).toBe('El archivo supera el máximo de 64 MB.');
    expect(textoDeError(rechazo(400, 'hoja_inexistente', { hoja: 'ANTIGUA', hojas: ['A'] }), red, general)).toBe(
      'La hoja «ANTIGUA» no está en el archivo. Elige una de la lista.',
    );
  });

  it('cambia con el idioma', () => {
    setLanguageForTests('en');
    expect(textoDeError(rechazo(400, 'archivo_vacio'), red, general)).not.toBe('El archivo está vacío.');
  });

  it('sin código, o con uno que la interfaz no conoce, dice la frase general', () => {
    expect(textoDeError(rechazo(500, null), red, general)).toBe(general);
    expect(textoDeError(rechazo(400, 'codigo_inventado'), red, general)).toBe(general);
  });

  it('una API inalcanzable no es un rechazo: dice lo de la red', () => {
    expect(textoDeError(new NetworkError(), red, general)).toBe(red);
    expect(textoDeError(new Error('otra cosa'), red, general)).toBe(red);
  });

  it('el código se lee del cuerpo, y solo si es texto', () => {
    expect(codigoDeError(rechazo(400, 'archivo_vacio'))).toBe('archivo_vacio');
    expect(codigoDeError(new ApiError(400, 'x', null, { codigo: 3 }))).toBeNull();
    expect(codigoDeError(new Error('x'))).toBeNull();
  });
});

describe('las hojas que ofrece una hoja inexistente', () => {
  it('son las del cuerpo, solo las que son texto', () => {
    expect(hojasDelError(rechazo(400, 'hoja_inexistente', { hojas: ['VENCIDA', 'MORA', 3] }))).toEqual(['VENCIDA', 'MORA']);
  });

  it('sin ellas, ninguna', () => {
    expect(hojasDelError(rechazo(400, 'hoja_inexistente'))).toEqual([]);
    expect(hojasDelError(new Error('x'))).toEqual([]);
  });
});

describe('qué se hace con un rechazo al confirmar', () => {
  const problemas = [problema('campo_repetido', 'titular')];

  it('un 422 con mapeo_con_problemas entrega los problemas para ponerlos sobre sus filas', () => {
    expect(problemasDeLaConfirmacion(rechazo(422, 'mapeo_con_problemas', { problemas }))).toEqual(problemas);
  });

  it('el mismo código con otro estado, u otro código con 422, no son de este caso', () => {
    expect(problemasDeLaConfirmacion(rechazo(400, 'mapeo_con_problemas', { problemas }))).toBeNull();
    expect(problemasDeLaConfirmacion(rechazo(422, 'otro', { problemas }))).toBeNull();
    expect(problemasDeLaConfirmacion(rechazo(422, 'mapeo_con_problemas'))).toBeNull();
    expect(problemasDeLaConfirmacion(new NetworkError())).toBeNull();
  });

  it('solo un 404 borrador_no_encontrado es un borrador perdido', () => {
    expect(esBorradorPerdido(rechazo(404, 'borrador_no_encontrado'))).toBe(true);
    expect(esBorradorPerdido(rechazo(404, 'catalogo_desconocido'))).toBe(false);
    expect(esBorradorPerdido(rechazo(404, null))).toBe(false);
    expect(esBorradorPerdido(rechazo(410, 'borrador_no_encontrado'))).toBe(false);
    expect(esBorradorPerdido(new NetworkError())).toBe(false);
  });
});

describe('las opciones de lectura', () => {
  it('los separadores se nombran; uno desconocido se muestra tal cual', () => {
    expect(nombreDeSeparador(';')).toBe('Punto y coma');
    expect(nombreDeSeparador('\t')).toBe('Tabulación');
    expect(nombreDeSeparador(',')).toBe('Coma');
    expect(nombreDeSeparador('|')).toBe('|');
  });

  it('«(detectado)» o «(detectada)» solo si el lector eligió esa opción', () => {
    expect(conMarcaDeDetectado('Coma', 'separador', ['separador'])).toBe('Coma (detectado)');
    expect(conMarcaDeDetectado('utf-8', 'codificacion', ['codificacion'])).toBe('utf-8 (detectada)');
    expect(conMarcaDeDetectado('MORA', 'hoja', ['separador'])).toBe('MORA');
    expect(conMarcaDeDetectado('MORA', 'hoja', [])).toBe('MORA');
  });

  it('un Excel admite hoja si tiene varias; un CSV, separador y codificación', () => {
    expect(opcionesQueAplican({ formato: 'xlsx', hojas: ['A', 'B'] })).toEqual({ hoja: true, separador: false, codificacion: false });
    expect(opcionesQueAplican({ formato: 'xlsx', hojas: ['A'] })).toEqual({ hoja: false, separador: false, codificacion: false });
    expect(opcionesQueAplican({ formato: 'csv', hojas: ['datos'] })).toEqual({ hoja: false, separador: true, codificacion: true });
  });
});

describe('el campo que choca en un nombre repetido', () => {
  const choca = {
    nombre: 'saldo_capital_pendiente',
    clave_etiqueta: 'campo.saldo_capital_pendiente',
    tipo: 'numero',
    obligatorio: false,
    alias: [],
    etiqueta: null,
    adicional: false,
  };

  it('un campo base se nombra por el diccionario, y el texto lo lleva', () => {
    const error = rechazo(409, 'nombre_repetido', { campo: choca });
    expect(campoDelError(error)?.etiquetaVisible).toBe('Saldo de capital pendiente');
    expect(textoDeError(error, 'red', 'general')).toBe('Ya existe el campo «Saldo de capital pendiente». Elígelo en la lista o usa otro nombre.');
  });

  it('un adicional se nombra por su etiqueta propia', () => {
    const error = rechazo(409, 'nombre_repetido', { campo: { ...choca, nombre: 'ad_zona', clave_etiqueta: 'campo.ad_zona', etiqueta: 'Zona de cobranza', adicional: true } });
    expect(campoDelError(error)?.etiquetaVisible).toBe('Zona de cobranza');
    expect(textoDeError(error, 'red', 'general')).toContain('«Zona de cobranza»');
  });

  it('sin campo en el cuerpo no hay nada que nombrar', () => {
    expect(campoDelError(rechazo(409, 'nombre_repetido'))).toBeNull();
    expect(campoDelError(new Error('x'))).toBeNull();
  });
});
