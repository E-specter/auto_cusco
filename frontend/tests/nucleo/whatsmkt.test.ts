/**
 * What the WhatsMKT configuration screen decides on its own: the MB <-> bytes conversion of the limits,
 * the time slots, the name examples, the reading of the segment table, and the texts of the module's
 * error codes. The API stays the judge of every rule; these are the checks a field makes on leaving it.
 */
import { afterEach, beforeAll, describe, expect, it } from 'vitest';

import { ApiError } from '../../src/lib/api';
import type { CodigoWhatsmkt, ErrorWhatsmkt } from '../../src/lib/api-whatsmkt';
import {
  BYTES_POR_MB,
  FECHA_DE_EJEMPLO,
  LARGO_MAXIMO_NOMBRE,
  RANGOS_TOPES,
  bytesAMb,
  errorDeModulo,
  errorDeSegmentos,
  horarioValido,
  leerSegmentos,
  leerTope,
  mbABytes,
  nombreDeCampana,
  nombresDeEjemplo,
  textoDeCodigo,
  textoDeHorarioInvalido,
  textoDeTope,
  type FilaSegmentoTexto,
} from '../../src/lib/whatsmkt';
import { setLanguageForTests } from './idioma';

beforeAll(() => setLanguageForTests('es'));
afterEach(() => setLanguageForTests('es'));

/** The 422 body the API sends: every parameter travels, the ones the code does not use are null. */
function cuerpo(codigo: CodigoWhatsmkt, parcial: Partial<ErrorWhatsmkt> = {}): ErrorWhatsmkt {
  return { detail: 'motivo del servidor', codigo, horarios: null, variable: null, segmento: null, fila: null, desde: null, hasta: null, peso: null, maximo: null, tipo: null, ancho: null, alto: null, ...parcial };
}

describe('topes: MB en la pantalla, bytes en la API (1 MB = 1 000 000)', () => {
  it('toma el megabyte en base decimal', () => {
    expect(BYTES_POR_MB).toBe(1_000_000);
    expect(mbABytes(16)).toBe(16_000_000);
    expect(bytesAMb(16_000_000)).toBe(16);
  });

  it('muestra el valor de la API en la unidad del campo', () => {
    expect(textoDeTope('tope_video', 16_000_000)).toBe('16');
    expect(textoDeTope('tope_pdf', 1_500_000)).toBe('1.5');
    expect(textoDeTope('tope_mensaje', 4096)).toBe('4096');
  });

  it('manda en bytes lo que se escribe en MB, con decimales', () => {
    expect(leerTope('tope_video', '16')).toBe(16_000_000);
    expect(leerTope('tope_audio', '1.5')).toBe(1_500_000);
    expect(leerTope('tope_pdf', ' 2 ')).toBe(2_000_000);
    // The float product of 1.234567 * 1e6 is not a whole number: the bytes are rounded, never fractional.
    expect(leerTope('tope_pdf', '1.234567')).toBe(1_234_567);
  });

  it('ida y vuelta: lo que se guarda es lo que se vuelve a mostrar', () => {
    for (const mb of [1, 2.5, 16, 100, 2000]) {
      expect(leerTope('tope_video', textoDeTope('tope_video', mbABytes(mb)))).toBe(mbABytes(mb));
    }
  });

  it('el mensaje va en caracteres enteros, sin convertir', () => {
    expect(leerTope('tope_mensaje', '4096')).toBe(4096);
    expect(leerTope('tope_mensaje', '4096.5')).toBeNull();
  });

  it('un tope de cero, negativo o fuera de rango no llega a la API', () => {
    for (const texto of ['', '  ', 'abc', '1,5', '-3', '0', '0.99', '2001']) {
      expect(leerTope('tope_video', texto), texto).toBeNull();
    }
    expect(leerTope('tope_mensaje', '0')).toBeNull();
    expect(leerTope('tope_mensaje', '-1')).toBeNull();
    expect(leerTope('tope_mensaje', '2000000000')).toBe(2_000_000_000);
    expect(leerTope('tope_mensaje', '2000000001')).toBeNull();
  });

  it('el mínimo de cada campo es 1, el min="1" del marcado', () => {
    for (const rango of Object.values(RANGOS_TOPES)) expect(rango.minimo).toBe(1);
  });
});

describe('horarios de envío', () => {
  it('una franja vale si el inicio es anterior al fin', () => {
    expect(horarioValido('08:00', '14:00')).toBe(true);
    expect(horarioValido('14:00', '20:00')).toBe(true);
    expect(horarioValido('00:00', '23:59')).toBe(true);
  });

  it('la misma hora o al revés no valen', () => {
    expect(horarioValido('14:00', '14:00')).toBe(false);
    expect(horarioValido('14:00', '08:00')).toBe(false);
  });

  it('una hora mal escrita no vale', () => {
    for (const [inicio, fin] of [['', '14:00'], ['08:00', ''], ['8:00', '14:00'], ['08:00', '24:00'], ['08:60', '14:00']]) {
      expect(horarioValido(inicio, fin), `${inicio}-${fin}`).toBe(false);
    }
  });

  it('el error nombra la franja, en cada idioma', () => {
    expect(textoDeHorarioInvalido('horario_2')).toBe(
      'Horario 2 termina antes de empezar: la hora de inicio tiene que ser anterior a la de fin.',
    );
    setLanguageForTests('en');
    expect(textoDeHorarioInvalido('horario_1')).toBe(
      'Time slot 1 ends before it starts: the start time must be earlier than the end time.',
    );
  });
});

describe('nombre de la campaña', () => {
  const POR_DEFECTO = 'CUZCO_Vencida ({segmento}) whatsapp {fecha_corte}';

  it('reemplaza las dos variables', () => {
    expect(nombreDeCampana(POR_DEFECTO, { fecha_corte: '2026.10.29', segmento: 'Preventivo' })).toBe(
      'CUZCO_Vencida (Preventivo) whatsapp 2026.10.29',
    );
  });

  it('reemplaza una variable repetida y deja como está la que no conoce', () => {
    expect(nombreDeCampana('{segmento}-{segmento} {otra}', { segmento: 'A' })).toBe('A-A {otra}');
  });

  it('da un ejemplo por segmento, en su orden, con la fecha de ejemplo', () => {
    expect(nombresDeEjemplo(POR_DEFECTO, ['Preventivo', 'Tramo 2'])).toEqual([
      `CUZCO_Vencida (Preventivo) whatsapp ${FECHA_DE_EJEMPLO}`,
      `CUZCO_Vencida (Tramo 2) whatsapp ${FECHA_DE_EJEMPLO}`,
    ]);
  });

  it('el nombre por defecto cabe en el tope de 75 con el segmento más largo de la siembra', () => {
    const nombres = nombresDeEjemplo(POR_DEFECTO, ['Preventivo', 'Tramo 2', 'Tramos mayores al 2']);
    expect(Math.max(...nombres.map((nombre) => nombre.length))).toBeLessThanOrEqual(LARGO_MAXIMO_NOMBRE);
  });
});

describe('tabla de segmentos', () => {
  const filas = (cambios: Partial<Record<string, Partial<FilaSegmentoTexto>>> = {}): FilaSegmentoTexto[] =>
    [
      { clave: 'preventivo', etiqueta: 'Preventivo', desde: null, hasta: '0' },
      { clave: 'tramo_2', etiqueta: 'Tramo 2', desde: '1', hasta: '8' },
      { clave: 'mayores_2', etiqueta: 'Tramos mayores al 2', desde: '9', hasta: null },
    ].map((fila) => ({ ...fila, ...cambios[fila.clave] }));

  it('arma el cuerpo de la API, con la etiqueta recortada y los límites fijos en null', () => {
    const { entrada, problemas } = leerSegmentos(filas({ preventivo: { etiqueta: '  Preventivo  ' } }));

    expect(problemas).toEqual([]);
    expect(entrada).toEqual([
      { clave: 'preventivo', etiqueta: 'Preventivo', desde: null, hasta: 0 },
      { clave: 'tramo_2', etiqueta: 'Tramo 2', desde: 1, hasta: 8 },
      { clave: 'mayores_2', etiqueta: 'Tramos mayores al 2', desde: 9, hasta: null },
    ]);
  });

  it('una etiqueta vacía o de más de 80 caracteres es un problema de su fila', () => {
    for (const etiqueta of ['', '   ', 'x'.repeat(81)]) {
      const { problemas } = leerSegmentos(filas({ tramo_2: { etiqueta } }));
      expect(problemas.map(({ clave, campo }) => [clave, campo]), etiqueta).toEqual([['tramo_2', 'etiqueta']]);
    }
    expect(leerSegmentos(filas({ tramo_2: { etiqueta: 'x'.repeat(80) } })).problemas).toEqual([]);
  });

  it('un límite que no es un entero de días es un problema del campo', () => {
    for (const desde of ['', '1.5', 'abc', '100001', '-100001']) {
      const { problemas } = leerSegmentos(filas({ tramo_2: { desde } }));
      expect(problemas.map(({ clave, campo }) => [clave, campo]), desde).toEqual([['tramo_2', 'desde']]);
    }
    expect(leerSegmentos(filas({ preventivo: { hasta: '-5' } })).problemas).toEqual([]);
  });

  it('«desde» mayor que «hasta» se dice en la fila, sin esperar a la API', () => {
    const { problemas } = leerSegmentos(filas({ tramo_2: { desde: '9', hasta: '8' } }));

    expect(problemas).toEqual([
      { clave: 'tramo_2', campo: 'desde', texto: '«Desde» no puede ser mayor que «Hasta».' },
    ]);
  });

  it('los huecos y las superposiciones no se juzgan aquí: son de la API', () => {
    expect(leerSegmentos(filas({ tramo_2: { desde: '3', hasta: '5' } })).problemas).toEqual([]);
    expect(leerSegmentos(filas({ tramo_2: { desde: '0', hasta: '8' } })).problemas).toEqual([]);
  });
});

describe('códigos de error del módulo', () => {
  it('reconoce el 422 con su código y no otro fallo', () => {
    const cuerpoDeApi = cuerpo('segmentos_con_hueco', { desde: 3, hasta: 5 });

    expect(errorDeModulo(new ApiError(422, 'x', 'segmentos_con_hueco', cuerpoDeApi))).toEqual(cuerpoDeApi);
    expect(errorDeModulo(new ApiError(404, 'x', null, { detail: 'x' }))).toBeNull();
    // The generic 422 of the validation has no code: it is not a rule of the module.
    expect(errorDeModulo(new ApiError(422, '', undefined, { detail: [{ msg: 'x' }] }))).toBeNull();
    expect(errorDeModulo(new Error('red'))).toBeNull();
  });

  it('pone los parámetros en el texto del código', () => {
    expect(textoDeCodigo(cuerpo('mensaje_largo'), { largo: 5000, maximo: 4096 })).toBe(
      'El mensaje tiene 5000 caracteres: el máximo es 4096.',
    );
    expect(textoDeCodigo(cuerpo('variable_inexistente'), { variable: '{otra}' })).toBe(
      'La variable {otra} no existe. Usa las de la lista.',
    );
  });

  it('un código que esta versión no traduce cae en la frase del servidor, nunca en la clave', () => {
    expect(textoDeCodigo(cuerpo('codigo_nuevo' as CodigoWhatsmkt))).toBe('motivo del servidor');
  });

  it('una superposición va bajo su fila y nombra al segmento con el que se pisa', () => {
    const etiquetas = { preventivo: 'Preventivo', tramo_2: 'Tramo 2' };

    expect(errorDeSegmentos(cuerpo('segmentos_superpuestos', { segmento: 'preventivo', fila: 'tramo_2' }), etiquetas)).toEqual({
      fila: 'tramo_2',
      texto: 'Los rangos de días se superponen con Preventivo.',
    });
  });

  it('una fila que se pisa consigo misma dice el motivo del servidor, no «se superpone con» ella', () => {
    const resultado = errorDeSegmentos(
      cuerpo('segmentos_superpuestos', { segmento: 'tramo_2', fila: 'tramo_2' }),
      { tramo_2: 'Tramo 2' },
    );

    expect(resultado).toEqual({ fila: 'tramo_2', texto: 'motivo del servidor' });
  });

  it('un hueco va bajo la tabla, con los días que quedan sin segmento', () => {
    expect(errorDeSegmentos(cuerpo('segmentos_con_hueco', { desde: 3, hasta: 5 }), {})).toEqual({
      fila: null,
      texto: 'Quedan días de atraso sin segmento: 3 a 5.',
    });
    expect(errorDeSegmentos(cuerpo('segmentos_con_hueco', { desde: null, hasta: -1 }), {}).texto).toBe(
      'Quedan días de atraso sin segmento: −∞ a -1.',
    );
  });
});
