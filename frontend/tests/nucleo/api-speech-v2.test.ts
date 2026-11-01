/**
 * What the v2 speech adds to the MOWA MES client: the problems a refused save carries.
 */
import { describe, expect, it } from 'vitest';

import { ApiError } from '../../src/lib/api';
import { problemasDeErrorSpeech } from '../../src/lib/api-speech-v2';

const PROBLEMA = {
  segmento: '9_a_30',
  campo: 'expresion',
  detalle: 'x',
  codigo: 'variable_desconocida',
  catalogo: 'texto',
  ubicacion: { nodo: 1, funcion: null, parametro: null },
};

describe('los problemas de un guardado rechazado', () => {
  it('se leen del cuerpo del 400, con su segmento, su campo y su catálogo', () => {
    const fallo = new ApiError(400, 'No se guarda', null, { detail: 'No se guarda', problemas: [PROBLEMA] });

    expect(problemasDeErrorSpeech(fallo)).toEqual([PROBLEMA]);
  });

  it('lo que no tiene forma de problema se descarta, y lo que no es una lista no se inventa', () => {
    const conCuerpo = (cuerpo: Record<string, unknown> | null) => new ApiError(400, 'x', null, cuerpo);

    expect(problemasDeErrorSpeech(conCuerpo(null))).toEqual([]);
    expect(problemasDeErrorSpeech(conCuerpo({ problemas: 'texto' }))).toEqual([]);
    expect(problemasDeErrorSpeech(conCuerpo({ problemas: [{ sin: 'forma' }, PROBLEMA] }))).toEqual([PROBLEMA]);
    expect(problemasDeErrorSpeech(new Error('otra cosa'))).toEqual([]);
    expect(problemasDeErrorSpeech(undefined)).toEqual([]);
  });
});
