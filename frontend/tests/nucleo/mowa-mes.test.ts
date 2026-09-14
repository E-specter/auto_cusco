/**
 * Logic of the MOWA MES configuration screen: speech drafts and the
 * immutability rule, how a preview reads, calendar actions and supervisor
 * drafts. Numbers are synthetic, in the 900000xxx range.
 */
import { describe, expect, it } from 'vitest';

import type { LargoSegmento, PartesSpeech, VersionSpeech } from '../../src/lib/api-mowa-mes';
import {
  accionDia,
  borradorDeSupervision,
  borradorDesdeVersion,
  entradaSupervision,
  hayCambiosSpeech,
  modoGuardado,
  moverElemento,
  nivelLargo,
  problemasConfiguracion,
  problemasSupervision,
  rangoSegmento,
  renombrarProcedencia,
  resumenNiveles,
  supervisionCambio,
  traducirCodigo,
} from '../../src/lib/mowa-mes';
import { setLanguage, t, type Language } from '../../src/lib/i18n';

/**
 * Switch the interface language inside a `node` test. `setLanguage` also
 * touches the document, which does not exist here, so this stub gives it just
 * enough of one.
 *
 * PROVISIONAL: a copy of `tests/nucleo/idioma.ts` from designer, which is not
 * committed yet. Replace it with that import once it is (T-MM-F5).
 */
function setLanguageForTests(language: Language): void {
  const global = globalThis as { document?: unknown };
  const teniaDocumento = 'document' in global;
  if (!teniaDocumento) {
    global.document = { documentElement: {}, querySelectorAll: () => [], dispatchEvent: () => true };
  }
  setLanguage(language, { querySelectorAll: () => [] } as unknown as ParentNode);
  if (!teniaDocumento) delete global.document;
}

function parte(segmento: PartesSpeech['segmento'], parte_1 = ' p1 ', parte_2 = ' p2'): PartesSpeech {
  return {
    segmento,
    etiqueta: segmento,
    dias_desde: segmento === 'preventiva' ? null : 1,
    dias_hasta: 8,
    parte_1,
    parte_2,
    usa_whatsapp: false,
  };
}

function version(parcial: Partial<VersionSpeech> = {}): VersionSpeech {
  return {
    id: 2,
    nombre: 'Speech 2',
    original: false,
    basada_en_id: 1,
    usada: false,
    editable: true,
    creado_en: '2099-01-01T08:00:00-05:00',
    // Desordenadas a propósito: el borrador sigue el orden de RF-MM-15.
    partes: [parte('9_a_30'), parte('preventiva'), parte('1_a_8')],
    ...parcial,
  };
}

function largo(parcial: Partial<LargoSegmento> = {}): LargoSegmento {
  return {
    segmento: '9_a_30',
    etiqueta: '9 a 30',
    usa_whatsapp: false,
    falta_whatsapp: false,
    largo_maximo: 120,
    codigo: null,
    ejemplo: 'ejemplo',
    ...parcial,
  };
}

describe('borrador de speech', () => {
  it('ordena las partes por segmento y deja solo lo editable', () => {
    expect(borradorDesdeVersion(version())).toEqual([
      { segmento: 'preventiva', parte_1: ' p1 ', parte_2: ' p2' },
      { segmento: '1_a_8', parte_1: ' p1 ', parte_2: ' p2' },
      { segmento: '9_a_30', parte_1: ' p1 ', parte_2: ' p2' },
    ]);
  });

  it('sin tocar nada no hay cambios', () => {
    const v = version();
    expect(hayCambiosSpeech(v, borradorDesdeVersion(v))).toBe(false);
  });

  it('un espacio en un extremo cuenta como cambio, porque es texto del mensaje', () => {
    const v = version();
    const borrador = borradorDesdeVersion(v);
    borrador[0] = { ...borrador[0], parte_1: ' p1' };
    expect(hayCambiosSpeech(v, borrador)).toBe(true);
  });
});

describe('modo de guardado (RF-MM-17)', () => {
  it('una versión sin uso se edita', () => {
    expect(modoGuardado(version())).toBe('editar');
  });

  it('el Speech original nunca se edita, aunque viniera marcado editable', () => {
    expect(modoGuardado(version({ original: true, editable: true }))).toBe('nueva');
  });

  it('una versión usada crea otra', () => {
    expect(modoGuardado(version({ usada: true, editable: false }))).toBe('nueva');
  });

  it('lo que la API marca no editable crea otra', () => {
    expect(modoGuardado(version({ editable: false }))).toBe('nueva');
  });
});

describe('lectura de la previsualización', () => {
  it('sin código queda bien', () => {
    expect(nivelLargo(largo())).toBe('ok');
  });

  it('más de 150 advierte y más de 160 excluye', () => {
    expect(nivelLargo(largo({ largo_maximo: 156, codigo: 'mensaje_excede_150' }))).toBe('advertencia');
    expect(nivelLargo(largo({ largo_maximo: 161, codigo: 'mensaje_excede_160' }))).toBe('excede');
  });

  it('la falta de WhatsApp manda sobre el largo', () => {
    expect(
      nivelLargo(largo({ falta_whatsapp: true, usa_whatsapp: true, codigo: 'mensaje_excede_160', ejemplo: null })),
    ).toBe('falta_whatsapp');
  });

  it('el rango de preventiva no tiene inicio', () => {
    expect(rangoSegmento({ dias_desde: null, dias_hasta: 0 })).toEqual({
      clave: 'mowaMes.speech.rango.hasta',
      params: { hasta: 0 },
    });
    expect(rangoSegmento({ dias_desde: 9, dias_hasta: 30 })).toEqual({
      clave: 'mowaMes.speech.rango.entre',
      params: { desde: 9, hasta: 30 },
    });
  });
});

describe('texto del rango', () => {
  const texto = (desde: number | null, hasta: number) => {
    const { clave, params } = rangoSegmento({ dias_desde: desde, dias_hasta: hasta });
    return t(clave, params);
  };

  it('va entre paréntesis y no repite el nombre del segmento', () => {
    setLanguageForTests('es');
    expect(texto(9, 30)).toBe('(9–30 días)');
    expect(texto(null, 0)).toBe('(hasta 0 días)');
  });

  it('se traduce al inglés con la misma forma', () => {
    setLanguageForTests('en');
    expect(texto(9, 30)).toBe('(9–30 days)');
    expect(texto(null, 0)).toBe('(up to 0 days)');
    setLanguageForTests('es');
  });
});

describe('resumen de niveles para lectores de pantalla', () => {
  it('sin previsualización no dice nada', () => {
    expect(resumenNiveles([])).toBe('');
  });

  it('si todo cabe lo dice una vez', () => {
    setLanguageForTests('es');
    expect(resumenNiveles([largo(), largo({ segmento: 'preventiva' })])).toBe(
      'Todos los segmentos caben en un SMS.',
    );
  });

  it('cuenta en singular y en plural, lo más grave primero', () => {
    setLanguageForTests('es');
    const resumen = resumenNiveles([
      largo({ codigo: 'mensaje_excede_150' }),
      largo({ segmento: '31_a_60', falta_whatsapp: true, usa_whatsapp: true, ejemplo: null }),
      largo({ segmento: '61_a_90', falta_whatsapp: true, usa_whatsapp: true, ejemplo: null }),
      largo({ segmento: '1_a_8', codigo: 'mensaje_excede_160' }),
      largo({ segmento: 'preventiva' }),
    ]);
    expect(resumen).toBe(
      '2 segmentos no se pueden generar sin WhatsApp. 1 segmento pasa de 160 caracteres. 1 segmento pasa de 150 caracteres.',
    );
  });

  it('se traduce al inglés', () => {
    setLanguageForTests('en');
    expect(resumenNiveles([largo({ codigo: 'mensaje_excede_150' }), largo({ codigo: 'mensaje_excede_150' })])).toBe(
      '2 segments are longer than 150 characters.',
    );
    setLanguageForTests('es');
  });
});

describe('traducción de códigos', () => {
  it('traduce un código conocido según el idioma', () => {
    setLanguageForTests('en');
    expect(traducirCodigo('mensaje_excede_150', 'respaldo')).not.toBe('respaldo');
    setLanguageForTests('es');
    expect(traducirCodigo('mensaje_excede_150', 'respaldo')).not.toBe('respaldo');
  });

  it('un código desconocido cae en la frase del servidor', () => {
    setLanguageForTests('es');
    expect(traducirCodigo('codigo_que_no_existe', 'Frase del servidor')).toBe('Frase del servidor');
  });
});

describe('configuración del conector (RF-MM-11)', () => {
  const validos = { limite_mensual: '2500000', registros_por_archivo: '50000', bytes_por_archivo: '2000000' };

  it('los valores de la plataforma son válidos', () => {
    expect(problemasConfiguracion(validos)).toEqual([]);
  });

  it('los límites por archivo solo bajan: pasar de 50 000 filas o 2 000 000 bytes no se acepta', () => {
    expect(
      problemasConfiguracion({ ...validos, registros_por_archivo: '50001', bytes_por_archivo: '2000001' }),
    ).toEqual(['registros_por_archivo', 'bytes_por_archivo']);
  });

  it('respeta los mínimos en los bordes', () => {
    expect(problemasConfiguracion({ ...validos, registros_por_archivo: '1', bytes_por_archivo: '100000' })).toEqual([]);
    expect(problemasConfiguracion({ ...validos, registros_por_archivo: '0', bytes_por_archivo: '99999' })).toEqual([
      'registros_por_archivo',
      'bytes_por_archivo',
    ]);
  });

  it('rechaza lo que no es un entero, sin convertirlo', () => {
    expect(problemasConfiguracion({ ...validos, limite_mensual: '2.5e6' })).toEqual(['limite_mensual']);
    expect(problemasConfiguracion({ ...validos, limite_mensual: '' })).toEqual(['limite_mensual']);
    expect(problemasConfiguracion({ ...validos, registros_por_archivo: '-5' })).toEqual(['registros_por_archivo']);
  });

  it('tolera espacios alrededor', () => {
    expect(problemasConfiguracion({ ...validos, registros_por_archivo: ' 40000 ' })).toEqual([]);
  });
});

describe('acciones del calendario', () => {
  const dia = { fecha: '2099-07-28', descripcion: 'Feriado sintetico' };

  it('un feriado de ley se retira, nunca se borra', () => {
    expect(accionDia({ ...dia, origen: 'ley', retirado: false })).toBe('retirar');
  });

  it('un feriado de ley retirado se restaura', () => {
    expect(accionDia({ ...dia, origen: 'ley', retirado: true })).toBe('restaurar');
  });

  it('un día agregado se quita', () => {
    expect(accionDia({ ...dia, origen: 'agregado', retirado: false })).toBe('quitar');
  });
});

describe('borrador de supervisores', () => {
  const guardada = {
    procedencias: ['Procedencia A', 'Procedencia B'],
    supervisores: [
      { numero: '900000101', procedencia: 'Procedencia A', documento: '00000001' },
      { numero: '900000102', procedencia: 'Procedencia B', documento: '00000002' },
    ],
  };

  it('parte de lo guardado sin cambios', () => {
    expect(supervisionCambio(guardada, borradorDeSupervision(guardada))).toBe(false);
  });

  it('los espacios de los extremos no cuentan como cambio y no viajan', () => {
    const borrador = borradorDeSupervision(guardada);
    borrador.supervisores[0].numero = ' 900000101 ';
    expect(supervisionCambio(guardada, borrador)).toBe(false);
    expect(entradaSupervision(borrador).supervisores[0].numero).toBe('900000101');
  });

  it('renombrar una procedencia arrastra a sus supervisores', () => {
    const renombrado = renombrarProcedencia(borradorDeSupervision(guardada), 0, 'Procedencia C');
    expect(renombrado.procedencias).toEqual(['Procedencia C', 'Procedencia B']);
    expect(renombrado.supervisores.map((s) => s.procedencia)).toEqual(['Procedencia C', 'Procedencia B']);
    expect(supervisionCambio(guardada, renombrado)).toBe(true);
  });

  it('mover cambia el orden, y fuera de rango no hace nada', () => {
    expect(moverElemento(['a', 'b', 'c'], 0, 1)).toEqual(['b', 'a', 'c']);
    expect(moverElemento(['a', 'b', 'c'], 2, -1)).toEqual(['a', 'c', 'b']);
    expect(moverElemento(['a', 'b', 'c'], 0, -1)).toEqual(['a', 'b', 'c']);
    expect(moverElemento(['a', 'b', 'c'], 2, 1)).toEqual(['a', 'b', 'c']);
  });

  it('una lista válida no tiene problemas', () => {
    expect(problemasSupervision(borradorDeSupervision(guardada))).toEqual([]);
  });

  it('señala procedencias vacías, largas y repetidas sin distinguir mayúsculas', () => {
    const problemas = problemasSupervision({
      procedencias: ['Procedencia A', ' ', 'procedencia a', 'x'.repeat(61)],
      supervisores: [],
    });
    expect(problemas).toEqual([
      { tipo: 'procedencia_vacia', indice: 1 },
      { tipo: 'procedencia_repetida', indice: 2 },
      { tipo: 'procedencia_larga', indice: 3 },
    ]);
  });

  it('señala un supervisor sin número o con una procedencia que ya no está', () => {
    const problemas = problemasSupervision({
      procedencias: ['Procedencia A'],
      supervisores: [
        { numero: '', procedencia: 'Procedencia A' },
        { numero: '900000103', procedencia: 'Procedencia borrada' },
      ],
    });
    expect(problemas).toEqual([
      { tipo: 'numero_vacio', indice: 0 },
      { tipo: 'procedencia_desconocida', indice: 1 },
    ]);
  });

  it('sin procedencias no se puede guardar', () => {
    expect(problemasSupervision({ procedencias: [], supervisores: [] })).toEqual([
      { tipo: 'sin_procedencias' },
    ]);
  });
});
