/**
 * Logic of the MOWA MES configuration screen: speech drafts and the
 * immutability rule, how a preview reads and the platform settings.
 * Numbers are synthetic, in the 900000xxx range.
 */
import { describe, expect, it } from 'vitest';

import type { VersionSpeech } from '../../src/lib/api-mowa-mes';
import {
  CAMPOS_DE_ERROR,
  campoDeError,
  insertarVariable,
  modoGuardado,
  presentarCosto,
  problemasConfiguracion,
  RANGOS_CONFIGURACION,
  tarifaEditable,
  textoDeRango,
  tarifaNormalizada,
  variablesDesconocidas,
  traducirCodigo,
} from '../../src/lib/mowa-mes';
import { formatNumber } from '../../src/lib/format';
import { FILAS_POR_PAGINA, paginar } from '../../src/lib/paginacion';
import { t } from '../../src/lib/i18n';
import { setLanguageForTests } from './idioma';

function version(parcial: Partial<VersionSpeech> = {}): VersionSpeech {
  return {
    id: 2,
    nombre: 'Speech 2',
    formato: 'v2',
    original: false,
    basada_en_id: 1,
    usada: false,
    editable: true,
    creado_en: '2099-01-01T08:00:00-05:00',
    deshabilitada_en: null,
    eliminable: false,
    motivo_no_eliminable: null,
    partes: [],
    expresiones: [],
    ...parcial,
  };
}

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

describe('textoDeRango (los límites salen de RANGOS_CONFIGURACION, formateados)', () => {
  const CAMPOS = ['limite_mensual', 'registros_por_archivo', 'bytes_por_archivo'] as const;

  it('en español, con el formato de números del resto del sitio', () => {
    setLanguageForTests('es');
    expect(textoDeRango('limite_mensual')).toBe('Escribe un número entero entre 1 y 1,000,000,000.');
    expect(textoDeRango('registros_por_archivo')).toBe('Las filas por archivo van de 1 a 50,000.');
    expect(textoDeRango('bytes_por_archivo')).toBe('El tamaño por archivo va de 100,000 a 2,000,000 bytes.');
  });

  it('en inglés, con el mismo formato', () => {
    setLanguageForTests('en');
    expect(textoDeRango('limite_mensual')).toBe('Enter a whole number between 1 and 1,000,000,000.');
    expect(textoDeRango('registros_por_archivo')).toBe('Rows per file range from 1 to 50,000.');
    expect(textoDeRango('bytes_por_archivo')).toBe('Size per file ranges from 100,000 to 2,000,000 bytes.');
    setLanguageForTests('es');
  });

  it.each(['es', 'en'] as const)('(%s) cada texto dice exactamente los límites de la tabla que valida, formateados', (idioma) => {
    setLanguageForTests(idioma);
    for (const campo of CAMPOS) {
      const { minimo, maximo } = RANGOS_CONFIGURACION[campo];
      const texto = textoDeRango(campo);
      expect(texto).toContain(formatNumber(minimo));
      expect(texto).toContain(formatNumber(maximo));
      // No grouping written by hand: a space or a non-breaking space between digits.
      expect(texto).not.toMatch(/\d[\s\u00a0\u202f]\d/);
    }
    setLanguageForTests('es');
  });

  it('el diccionario no lleva los números escritos: son placeholders {min} y {max}', () => {
    for (const idioma of ['es', 'en'] as const) {
      setLanguageForTests(idioma);
      for (const clave of ['limite', 'registros', 'bytes']) {
        const marcado = t(`mowaMes.plataforma.${clave}.rango`, { min: 'MIN', max: 'MAX' });
        expect(marcado, `${idioma} ${clave}`).toMatch(/MIN.*MAX/);
        expect(marcado.replace(/MIN|MAX/g, ''), `${idioma} ${clave}`).not.toMatch(/\d/);
      }
    }
    setLanguageForTests('es');
  });
});
