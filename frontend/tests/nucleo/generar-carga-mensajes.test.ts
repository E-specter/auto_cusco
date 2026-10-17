/**
 * The sentences of "Generar carga" that depend on state. What matters is that none of them promises
 * more than is known: the line next to the button says "hasta" when the file may leave products out,
 * a cancel does not claim the version was or was not marked used, and a refusal reads from the
 * catalogue before falling back to the server's own words.
 */
import { beforeEach, describe, expect, it } from 'vitest';

import { ApiError, NetworkError } from '../../src/lib/api';
import {
  avisoDeCancelacion,
  avisoDeErrores,
  avisoDeExclusiones,
  avisoDeExito,
  avisoDeSuficiencia,
  descripcionDeGrupo,
  descripcionDeProblema,
  etiquetaDeFormato,
  etiquetaDeSugerido,
  lineaDeSalida,
  mensajeDeError,
  textoDeCodigo,
  textoMotivo,
} from '../../src/lib/generar-carga-mensajes';
import type { ProblemaDeCarga, ResumenDeCarga } from '../../src/lib/generar-carga';
import { setLanguageForTests } from './idioma';

beforeEach(() => setLanguageForTests('es'));

const RESUMEN: ResumenDeCarga = {
  generados: 497,
  disponibles: 3200,
  solicitados: 500,
  suficiente: true,
  errores: 0,
  excluidos: 3,
};

describe('textoDeCodigo', () => {
  it('traduce un código del catálogo', () => {
    expect(textoDeCodigo('sin_segmento', 'respaldo')).toContain('no cae en ningún segmento');
  });

  it('un código que esta versión no conoce cae en la frase del servidor', () => {
    expect(textoDeCodigo('codigo_inventado', 'La frase del servidor')).toBe('La frase del servidor');
  });
});

describe('mensajeDeError', () => {
  it('prefiere el código traducido al detalle', () => {
    const error = new ApiError(404, 'No hay cartera vigente', 'sin_version_vigente');
    expect(mensajeDeError(error)).toBe('No hay cartera vigente para esa fecha de corte. Elige otra fecha.');
  });

  it('un código desconocido cae en el detalle del servidor', () => {
    expect(mensajeDeError(new ApiError(400, 'La codificación «x» no existe', 'codigo_nuevo'))).toBe('La codificación «x» no existe');
  });

  it('sin código usa el detalle', () => {
    expect(mensajeDeError(new ApiError(400, 'El filtro está mal escrito'))).toBe('El filtro está mal escrito');
  });

  it('sin detalle ni código dice el estado, no una cadena vacía', () => {
    expect(mensajeDeError(new ApiError(422, ''))).toBe('El servidor rechazó la petición (422).');
  });

  it('una API que no responde no es un rechazo', () => {
    expect(mensajeDeError(new NetworkError())).toContain('No se pudo contactar con el backend');
    expect(mensajeDeError(new TypeError('x'))).toContain('No se pudo contactar con el backend');
  });
});

describe('textoMotivo', () => {
  it('dice cada razón en palabras', () => {
    expect(textoMotivo('sin_fecha')).toBe('Elige la fecha de corte para poder generar.');
    expect(textoMotivo('seleccion_no_aplica')).toBe('La selección tiene partes que no aplican; corrígelas en Cartera.');
    expect(textoMotivo('sin_definicion')).toBe('Elige una definición de columnas para poder generar.');
    expect(textoMotivo('cantidad_invalida')).toBe('Escribe una cantidad válida para poder generar.');
  });

  it('nombra la opción que no es un número, con su nombre visible', () => {
    expect(textoMotivo('opcion_invalida', 'sangria')).toBe('Corrige la opción «Sangría»: debe ser un número entero.');
  });

  it('una opción que esta versión no conoce se nombra como llega', () => {
    expect(textoMotivo('opcion_invalida', 'otra')).toBe('Corrige la opción «otra»: debe ser un número entero.');
  });
});

describe('lineaDeSalida', () => {
  const base = { filas: 500, formato: 'xlsx' as const, version: 4, nombre: 'SMS preventivo' };

  it('exacta cuando el archivo no puede perder productos', () => {
    expect(lineaDeSalida({ ...base, esTope: false })).toBe('Se generarán 500 filas en XLSX con la versión 4 de “SMS preventivo”.');
  });

  it('«hasta» cuando puede dejar productos fuera, y lo explica', () => {
    const linea = lineaDeSalida({ ...base, esTope: true });
    expect(linea).toContain('Se generarán hasta 500 filas');
    expect(linea).toContain('los productos sin segmento quedan fuera');
  });

  it('usa comillas inglesas dobles dentro, nunca «» anidadas', () => {
    const linea = lineaDeSalida({ ...base, esTope: false });
    expect(linea).not.toMatch(/«.*»/);
  });

  it('sin versión conocida no inventa un número', () => {
    expect(lineaDeSalida({ ...base, version: null, esTope: false })).toContain('versión —');
  });

  it('el formato va en mayúsculas', () => {
    expect(etiquetaDeFormato('csv')).toBe('CSV');
    expect(lineaDeSalida({ ...base, formato: 'json', esTope: false })).toContain('en JSON');
  });
});

describe('problemas de la muestra', () => {
  const error: ProblemaDeCarga = { tipo: 'error', fila: 2, campo: 'mensaje', detalle: 'La variable titular está vacía' };
  const exclusion: ProblemaDeCarga = {
    tipo: 'exclusion',
    fila: 4,
    pagare: '9000004',
    codigo: 'sin_segmento',
    detalle: 'detalle del servidor',
  };

  it('un error dice la columna y la fila de la tabla, con la frase del servidor', () => {
    expect(descripcionDeProblema(error)).toEqual({
      donde: 'Columna «mensaje», fila 2 de la tabla',
      mensaje: 'La variable titular está vacía',
    });
  });

  it('una exclusión dice el lugar en la selección y el pagaré, con el texto del catálogo', () => {
    const { donde, mensaje } = descripcionDeProblema(exclusion);
    expect(donde).toBe('Producto 4 de la selección · pagaré 9000004');
    expect(mensaje).toContain('no cae en ningún segmento');
  });

  it('sin pagaré no escribe un hueco', () => {
    expect(descripcionDeProblema({ ...exclusion, pagare: null }).donde).toBe('Producto 4 de la selección');
  });

  it('una exclusión con un código nuevo cae en el detalle del servidor', () => {
    expect(descripcionDeProblema({ ...exclusion, codigo: 'motivo_nuevo' }).mensaje).toBe('detalle del servidor');
  });

  it('un grupo dice dónde (cuántos), qué pasó (lo que los une) y el botón que los abre', () => {
    const grupo = { tipo: 'grupo' as const, clave: 'exclusion:sin_segmento', problemas: Array(6).fill(exclusion) };
    const { donde, mensaje, ver } = descripcionDeGrupo(grupo);
    expect(donde).toBe('6 productos');
    expect(mensaje).toContain('no cae en ningún segmento');
    expect(ver).toBe('Ver los 6');
    expect(donde).not.toContain(mensaje);
  });

  it('un grupo de errores nombra la columna y usa la frase del servidor', () => {
    const errores = { tipo: 'grupo' as const, clave: 'error:mensaje', problemas: Array(7).fill(error) };
    expect(descripcionDeGrupo(errores)).toEqual({
      donde: '7 filas en «mensaje»',
      mensaje: 'La variable titular está vacía',
      ver: 'Ver los 7',
    });
  });
});

describe('avisos', () => {
  it('suficiencia dice cuántos había y cuántos se pidieron', () => {
    expect(avisoDeSuficiencia({ disponibles: 300, solicitados: 500 })).toBe(
      'Hay 300 productos y se pidieron 500. El archivo sale con los 300 que hay.',
    );
  });

  it('exclusiones y errores se dicen cada uno por su lado', () => {
    expect(avisoDeExclusiones({ excluidos: 3, muestra: 20 })).toContain('3 de 20');
    expect(avisoDeErrores(2)).toContain('2');
    expect(avisoDeExclusiones({ excluidos: 3, muestra: 20 })).not.toBe(avisoDeSuficiencia({ disponibles: 3, solicitados: 20 }));
  });

  it('el éxito cuenta filas generadas y excluidas y que la versión queda marcada como usada', () => {
    const lineas = avisoDeExito({ archivo: 'sms.xlsx', resumen: RESUMEN, version: 4, nombre: 'SMS preventivo' });
    expect(lineas).toEqual([
      'Se descargó «sms.xlsx»: 497 filas generadas y 3 excluidas.',
      'La versión 4 de “SMS preventivo” queda marcada como usada.',
    ]);
  });

  it('con 0 excluidos no menciona exclusiones', () => {
    const lineas = avisoDeExito({
      archivo: 'sms.xlsx',
      resumen: { ...RESUMEN, generados: 300, excluidos: 0 },
      version: 4,
      nombre: 'SMS preventivo',
    });
    expect(lineas[0]).toBe('Se descargó «sms.xlsx»: 300 filas generadas.');
    expect(lineas.join(' ')).not.toMatch(/excluid/);
  });

  it('si el archivo no traía alcanzan los productos añade la línea de suficiencia', () => {
    const lineas = avisoDeExito({
      archivo: 'sms.xlsx',
      resumen: { ...RESUMEN, suficiente: false, disponibles: 300, solicitados: 500, generados: 300, excluidos: 0 },
      version: 4,
      nombre: 'SMS preventivo',
    });
    expect(lineas).toHaveLength(3);
    expect(lineas[1]).toBe('Había 300 productos y se pidieron 500.');
    // The preview's promise would contradict the rows just reported.
    expect(lineas.join(' ')).not.toContain('El archivo sale con');
  });

  it('sin resumen legible no inventa números', () => {
    const lineas = avisoDeExito({ archivo: 'sms.xlsx', resumen: null, version: 4, nombre: 'SMS preventivo' });
    expect(lineas[0]).toBe('Se descargó «sms.xlsx».');
    expect(lineas.join(' ')).not.toMatch(/\d+ filas/);
  });

  it('la cancelación no afirma que se generó ni que no: dice que puede figurar como usada', () => {
    const aviso = avisoDeCancelacion(4);
    expect(aviso).toBe('Se canceló la descarga. Si el servidor alcanzó a terminarla, la versión 4 puede figurar como usada.');
    expect(aviso).not.toMatch(/queda marcada/);
  });
});

describe('etiquetaDeSugerido', () => {
  it('nombra los delimitadores usuales, también el que no se ve', () => {
    expect(etiquetaDeSugerido('delimitador', ',')).toBe('coma');
    expect(etiquetaDeSugerido('delimitador', ';')).toBe('punto y coma');
    expect(etiquetaDeSugerido('delimitador', '\t')).toBe('tabulación');
    expect(etiquetaDeSugerido('delimitador', '|')).toBe('barra vertical');
  });

  it('un delimitador sin nombre o una opción que se lee sola no lleva etiqueta', () => {
    expect(etiquetaDeSugerido('delimitador', '~')).toBeUndefined();
    expect(etiquetaDeSugerido('codificacion', 'utf-8')).toBeUndefined();
  });
});
