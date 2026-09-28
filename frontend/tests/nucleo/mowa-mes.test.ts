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
  CAMPOS_DE_ERROR,
  campoDeError,
  entradaSupervision,
  FILAS_POR_PAGINA,
  hayCambiosSpeech,
  insertarVariable,
  modoGuardado,
  moverElemento,
  nivelLargo,
  paginar,
  presentarCosto,
  problemasConfiguracion,
  problemasSupervision,
  rangoSegmento,
  tarifaEditable,
  tarifaNormalizada,
  variablesDesconocidas,
  renombrarProcedencia,
  resumenNiveles,
  supervisionCambio,
  traducirCodigo,
} from '../../src/lib/mowa-mes';
import { t } from '../../src/lib/i18n';
import { setLanguageForTests } from './idioma';

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

describe('paginar (RF-MM-26)', () => {
  const filas = (n: number) => Array.from({ length: n }, (_, i) => i + 1);

  it('lee de a 10 filas', () => {
    expect(FILAS_POR_PAGINA).toBe(10);
  });

  it.each([
    // total, páginas, hayPaginador
    [0, 1, false],
    [10, 1, false],
    [11, 2, true],
    [20, 2, true],
    [100, 10, true],
  ])('con %i filas hay %i página(s) y el paginador es %s', (total, paginas, hayPaginador) => {
    const pagina = paginar(filas(total), 1);
    expect(pagina.total).toBe(total);
    expect(pagina.paginas).toBe(paginas);
    expect(pagina.hayPaginador).toBe(hayPaginador);
  });

  it('sin filas no hay rango y la página es la primera', () => {
    expect(paginar([], 1)).toEqual({
      filas: [],
      pagina: 1,
      paginas: 1,
      desde: 0,
      hasta: 0,
      total: 0,
      hayPaginador: false,
    });
  });

  it('la primera página trae las 10 primeras filas', () => {
    const pagina = paginar(filas(20), 1);
    expect(pagina.filas).toEqual(filas(10));
    expect([pagina.desde, pagina.hasta]).toEqual([1, 10]);
  });

  it('la última página completa termina en el total', () => {
    const pagina = paginar(filas(20), 2);
    expect(pagina.filas).toEqual([11, 12, 13, 14, 15, 16, 17, 18, 19, 20]);
    expect([pagina.desde, pagina.hasta]).toEqual([11, 20]);
  });

  it('la última página incompleta trae solo lo que queda', () => {
    const pagina = paginar(filas(11), 2);
    expect(pagina.filas).toEqual([11]);
    expect([pagina.desde, pagina.hasta]).toEqual([11, 11]);
  });

  it('con 100 filas la página 10 es la última', () => {
    const pagina = paginar(filas(100), 10);
    expect(pagina.filas).toEqual(filas(100).slice(90));
    expect([pagina.desde, pagina.hasta, pagina.paginas]).toEqual([91, 100, 10]);
  });

  it('con exactamente 10 filas no hay una segunda página vacía', () => {
    const pagina = paginar(filas(10), 2);
    expect(pagina.pagina).toBe(1);
    expect(pagina.filas).toEqual(filas(10));
  });

  it('una página fuera de rango se lleva a la más cercana', () => {
    expect(paginar(filas(25), 0).pagina).toBe(1);
    expect(paginar(filas(25), -3).pagina).toBe(1);
    expect(paginar(filas(25), 99).pagina).toBe(3);
    expect(paginar(filas(25), Number.NaN).pagina).toBe(1);
  });

  it('todas las páginas juntas reproducen las filas, sin repetir ni perder', () => {
    for (const total of [0, 1, 9, 10, 11, 19, 20, 21, 100]) {
      const todas = filas(total);
      const unidas = Array.from({ length: paginar(todas, 1).paginas }, (_, i) => paginar(todas, i + 1).filas).flat();
      expect(unidas).toEqual(todas);
    }
  });
});

describe('tarifaNormalizada (RF-MM-23)', () => {
  it.each([
    ['0.02', '0.02'],
    ['0', '0'],
    ['1', '1'],
    ['0.0215', '0.0215'],
    ['0,02', '0.02'],
    ['  0.03  ', '0.03'],
    ['12.5', '12.5'],
  ])('acepta %j y lo entrega como %j', (entrada, esperado) => {
    expect(tarifaNormalizada(entrada)).toBe(esperado);
  });

  it.each(['', '   ', '-0.02', '0.02345', '.5', '5.', '1e3', 'abc', '0.0.2', '1,2,3', 'S/ 0.02', '0.02 soles'])(
    'rechaza %j',
    (entrada) => {
      expect(tarifaNormalizada(entrada)).toBeNull();
    },
  );

  it('no pasa por un número: conserva los ceros y la precisión que se escribieron', () => {
    expect(tarifaNormalizada('0.0200')).toBe('0.0200');
    expect(tarifaNormalizada('0.1000')).toBe('0.1000');
  });
});

describe('variablesDesconocidas (RF-MM-25)', () => {
  const validas = ['campana', 'descripcion', 'fecha_envio', 'fecha_corte', 'archivo', 'total', 'cantidad'].map(
    (nombre) => ({ nombre, descripcion: `d ${nombre}` }),
  );

  it('sin llaves no hay nada que marcar', () => {
    expect(variablesDesconocidas('mowa_mes_carga', validas)).toEqual([]);
    expect(variablesDesconocidas('', validas)).toEqual([]);
  });

  it('las variables de la lista no se marcan', () => {
    expect(variablesDesconocidas('mowa_mes_campana_{campana}_{archivo}_de_{total}', validas)).toEqual([]);
  });

  it('marca cada desconocida una vez y en el orden en que aparece', () => {
    expect(variablesDesconocidas('{banco}_{campana}_{otra}_{banco}', validas)).toEqual(['banco', 'otra']);
  });

  it('distingue mayúsculas: la lista manda', () => {
    expect(variablesDesconocidas('{Campana}', validas)).toEqual(['Campana']);
  });

  it('unas llaves vacías cuentan como desconocidas', () => {
    expect(variablesDesconocidas('a{}b', validas)).toEqual(['']);
  });

  it('no inventa variables: con una lista vacía, todas son desconocidas', () => {
    expect(variablesDesconocidas('{campana}', [])).toEqual(['campana']);
  });

  it('una llave sin cerrar no es una variable: eso lo dice el 400 del backend', () => {
    expect(variablesDesconocidas('{campana', validas)).toEqual([]);
    expect(variablesDesconocidas('campana}', validas)).toEqual([]);
  });
});

describe('insertarVariable', () => {
  it('inserta en la posición del cursor y deja el cursor después de la variable', () => {
    expect(insertarVariable('ab', 1, 1, 'total')).toEqual({ texto: 'a{total}b', cursor: 8 });
  });

  it('reemplaza lo seleccionado', () => {
    expect(insertarVariable('abcdef', 2, 4, 'archivo')).toEqual({ texto: 'ab{archivo}ef', cursor: 11 });
  });

  it('al principio y al final', () => {
    expect(insertarVariable('x', 0, 0, 'campana').texto).toBe('{campana}x');
    expect(insertarVariable('x', 1, 1, 'campana').texto).toBe('x{campana}');
  });

  it('sobre un campo vacío', () => {
    expect(insertarVariable('', 0, 0, 'total')).toEqual({ texto: '{total}', cursor: 7 });
  });

  it('una selección al revés o fuera del texto se acota', () => {
    expect(insertarVariable('abc', 3, 1, 'x').texto).toBe('a{x}');
    expect(insertarVariable('abc', -5, 99, 'x').texto).toBe('{x}');
    expect(insertarVariable('abc', 50, 60, 'x').texto).toBe('abc{x}');
  });
});

describe('presentarCosto (RF-MM-24)', () => {
  it('calculado muestra el monto', () => {
    expect(presentarCosto('calculado', '1234.5000')).toEqual({ tipo: 'monto', valor: '1234.5000' });
  });

  it('un costo real de cero con estado calculado es un monto, no «pendiente» ni «no disponible»', () => {
    expect(presentarCosto('calculado', '0.0000')).toEqual({ tipo: 'monto', valor: '0.0000' });
  });

  it('decide el estado, no el null: calculado con monto nulo no se lee como no disponible', () => {
    expect(presentarCosto('calculado', null)).toEqual({ tipo: 'monto', valor: null });
  });

  it('pendiente y no disponible no muestran monto, aunque llegue uno', () => {
    expect(presentarCosto('pendiente', null)).toEqual({ tipo: 'pendiente' });
    expect(presentarCosto('pendiente', '5.0000')).toEqual({ tipo: 'pendiente' });
    expect(presentarCosto('no_disponible', null)).toEqual({ tipo: 'no_disponible' });
    expect(presentarCosto('no_disponible', '5.0000')).toEqual({ tipo: 'no_disponible' });
  });
});

describe('tarifaEditable', () => {
  it.each([
    ['0.0200', '0.02'],
    ['0.0215', '0.0215'],
    ['0.1000', '0.10'],
    ['1.0000', '1.00'],
    ['12', '12.00'],
    ['0.0250', '0.025'],
    [' 0.0300 ', '0.03'],
  ])('%j se edita como %j', (guardada, editable) => {
    expect(tarifaEditable(guardada)).toBe(editable);
  });

  it('lo que se muestra al editar se acepta de vuelta y dice lo mismo', () => {
    for (const guardada of ['0.0200', '0.0215', '5.0000']) {
      expect(tarifaNormalizada(tarifaEditable(guardada))).not.toBeNull();
    }
  });
});

describe('campoDeError', () => {
  it('cubre exactamente los campos que el contrato puede nombrar', () => {
    // `CAMPOS_DE_ERROR` is a record over the generated enum: `astro check` fails if the
    // contract renames, adds or drops one. This pins the list the screens act on.
    expect(Object.keys(CAMPOS_DE_ERROR).sort()).toEqual([
      'bytes_por_archivo',
      'limite_mensual',
      'plantilla_nombre_archivo',
      'registros_por_archivo',
      'tarifa_sms',
      'whatsapp_contacto',
    ]);
  });

  it.each([
    'limite_mensual',
    'whatsapp_contacto',
    'registros_por_archivo',
    'bytes_por_archivo',
    'tarifa_sms',
    'plantilla_nombre_archivo',
  ])('lee el campo %s que nombra la API', (campo) => {
    expect(campoDeError({ detail: 'lo que sea', campo })).toBe(campo);
  });

  it('no adivina por el texto: sin campo, o con uno nulo, no hay campo', () => {
    expect(campoDeError({ detail: 'La tarifa debe ser un numero decimal' })).toBeNull();
    expect(campoDeError({ detail: 'La plantilla tiene una llave { sin cerrar', campo: null })).toBeNull();
    expect(campoDeError({ detail: 'El numero de WhatsApp no cumple RF-02' })).toBeNull();
  });

  it('un campo que este cliente no conoce, o que no es texto, no es un campo', () => {
    expect(campoDeError({ campo: 'campo_nuevo' })).toBeNull();
    expect(campoDeError({ campo: 7 })).toBeNull();
    expect(campoDeError({ campo: ['tarifa_sms'] })).toBeNull();
    expect(campoDeError({ campo: '' })).toBeNull();
  });

  it('un cuerpo que no llegó (no era un objeto JSON) tampoco', () => {
    expect(campoDeError(null)).toBeNull();
    expect(campoDeError({})).toBeNull();
  });
});
