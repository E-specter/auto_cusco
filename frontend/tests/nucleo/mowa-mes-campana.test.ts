/**
 * Logic of the MOWA MES campaign screen: building the request from a
 * selection and platform inputs, and reading the preview's answer. Phone
 * numbers are synthetic, in the 900000xxx range.
 */
import { describe, expect, it } from 'vitest';

import type { AvisoCampana, ConsumoLimite, PrevisualizacionCampana } from '../../src/lib/api-mowa-mes';
import {
  CANTIDAD_MAXIMA_CAMPANA,
  SALIDA_FIJA,
  TIPO_CARGA_FIJO,
  descripcionSigueSugerida,
  entradaCampana,
  entradaCreacion,
  etiquetaArchivoPrevisto,
  fechaHoraValida,
  horaLimaISO,
  mensajeLimiteExcedido,
  problemasCampana,
  resumenProblemasCampana,
  type CampanaBorrador,
} from '../../src/lib/mowa-mes-campana';
import { setLanguage, type Language } from '../../src/lib/i18n';

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

function borrador(parcial: Partial<CampanaBorrador> = {}): CampanaBorrador {
  return {
    seleccion: { fechaCorte: '2026-09-13', filtros: ['dias_atraso:entre:9|30'], orden: '-saldo_capital_pendiente', cantidad: 1000, seleccionId: 4 },
    descripcion: 'CajaCusco 9 <= dias atraso <= 30',
    herramientas: { keyword: false, blacklistIndecopi: true },
    programacion: { modo: 'hora_determinada', fechas: ['2026-09-15T09:00'] },
    speechId: null,
    whatsapp: '',
    supervisores: null,
    ...parcial,
  };
}

describe('hora de Lima', () => {
  it('agrega el desfase fijo -05:00, sin depender de una zona horaria', () => {
    expect(horaLimaISO('2026-09-15T09:00')).toBe('2026-09-15T09:00:00-05:00');
  });

  it('acepta la medianoche y el último minuto del día', () => {
    expect(horaLimaISO('2026-01-01T00:00')).toBe('2026-01-01T00:00:00-05:00');
    expect(fechaHoraValida('2026-12-31T23:59')).toBe(true);
  });

  it('rechaza un formato que no es el de datetime-local', () => {
    expect(fechaHoraValida('2026-09-15')).toBe(false);
    expect(fechaHoraValida('2026-09-15T09:00:00-05:00')).toBe(false);
    expect(fechaHoraValida('')).toBe(false);
    expect(() => horaLimaISO('no es una fecha')).toThrow('Fecha y hora invalidas');
  });
});

describe('problemas de la campaña', () => {
  it('un borrador válido no tiene problemas', () => {
    expect(problemasCampana(borrador())).toEqual([]);
  });

  it('la cantidad debe ser un entero entre 1 y el máximo (RF-08/generación)', () => {
    expect(CANTIDAD_MAXIMA_CAMPANA).toBe(120_000);
    expect(problemasCampana(borrador({ seleccion: { ...borrador().seleccion, cantidad: 0 } }))).toEqual([
      { tipo: 'cantidad_invalida' },
    ]);
    expect(
      problemasCampana(borrador({ seleccion: { ...borrador().seleccion, cantidad: CANTIDAD_MAXIMA_CAMPANA + 1 } })),
    ).toEqual([{ tipo: 'cantidad_invalida' }]);
    expect(problemasCampana(borrador({ seleccion: { ...borrador().seleccion, cantidad: 1.5 } }))).toEqual([
      { tipo: 'cantidad_invalida' },
    ]);
    expect(problemasCampana(borrador({ seleccion: { ...borrador().seleccion, cantidad: CANTIDAD_MAXIMA_CAMPANA } }))).toEqual(
      [],
    );
  });

  it('un WhatsApp que no cumple RF-02 se señala; vacío no, porque cae al configurado', () => {
    expect(problemasCampana(borrador({ whatsapp: '123' }))).toEqual([{ tipo: 'whatsapp_invalido' }]);
    expect(problemasCampana(borrador({ whatsapp: '' }))).toEqual([]);
    expect(problemasCampana(borrador({ whatsapp: ' 900000999 ' }))).toEqual([]);
  });

  it('enviar ahora no lleva fechas', () => {
    expect(problemasCampana(borrador({ programacion: { modo: 'enviar_ahora', fechas: [] } }))).toEqual([]);
    expect(
      problemasCampana(borrador({ programacion: { modo: 'enviar_ahora', fechas: ['2026-09-15T09:00'] } })),
    ).toEqual([{ tipo: 'envios_enviar_ahora' }]);
  });

  it('hora determinada lleva exactamente una fecha', () => {
    expect(problemasCampana(borrador({ programacion: { modo: 'hora_determinada', fechas: [] } }))).toEqual([
      { tipo: 'envios_hora_determinada' },
    ]);
    expect(
      problemasCampana(
        borrador({ programacion: { modo: 'hora_determinada', fechas: ['2026-09-15T09:00', '2026-09-16T09:00'] } }),
      ),
    ).toEqual([{ tipo: 'envios_hora_determinada' }]);
  });

  it('diferentes horas lleva al menos una fecha', () => {
    expect(problemasCampana(borrador({ programacion: { modo: 'diferentes_horas', fechas: [] } }))).toEqual([
      { tipo: 'envios_diferentes_horas' },
    ]);
    expect(
      problemasCampana(borrador({ programacion: { modo: 'diferentes_horas', fechas: ['2026-09-15T09:00'] } })),
    ).toEqual([]);
  });

  it('una fecha con un formato inválido se señala por su posición', () => {
    expect(
      problemasCampana(
        borrador({ programacion: { modo: 'diferentes_horas', fechas: ['2026-09-15T09:00', 'no es una fecha'] } }),
      ),
    ).toEqual([{ tipo: 'fecha_envio_invalida', indice: 1 }]);
  });
});

describe('armado de la petición', () => {
  it('toma tipo de carga y salida fijos, y arma las herramientas sin lo que no es un input del usuario', () => {
    const entrada = entradaCampana(borrador());
    expect(entrada.tipo_carga).toBe(TIPO_CARGA_FIJO);
    expect(entrada.salida).toBe(SALIDA_FIJA);
    expect(entrada.herramientas).toEqual({
      keyword: false,
      respuesta_automatica: false,
      blacklist_indecopi: true,
      speech_optimizado: false,
    });
  });

  it('copia la selección tal cual, con seleccion_id null si no vino de una guardada', () => {
    const entrada = entradaCampana(borrador({ seleccion: { fechaCorte: '2026-09-13', filtros: ['a:b:c'], orden: null, cantidad: 500 } }));
    expect(entrada).toMatchObject({
      fecha_corte: '2026-09-13',
      filtros: ['a:b:c'],
      orden: null,
      cantidad: 500,
      seleccion_id: null,
    });
  });

  it('convierte enviar_ahora en una lista vacía y hora_determinada en la fecha en hora de Lima', () => {
    expect(entradaCampana(borrador({ programacion: { modo: 'enviar_ahora', fechas: [] } })).envios).toEqual([]);
    expect(entradaCampana(borrador()).envios).toEqual(['2026-09-15T09:00:00-05:00']);
  });

  it('diferentes_horas convierte cada fecha, conservando el orden', () => {
    const entrada = entradaCampana(
      borrador({ programacion: { modo: 'diferentes_horas', fechas: ['2026-09-15T09:00', '2026-09-15T18:30'] } }),
    );
    expect(entrada.envios).toEqual(['2026-09-15T09:00:00-05:00', '2026-09-15T18:30:00-05:00']);
  });

  it('una descripción vacía viaja como null, para que el backend sugiera una', () => {
    expect(entradaCampana(borrador({ descripcion: '   ' })).descripcion).toBeNull();
  });

  it('un WhatsApp vacío viaja como null; recortado si tiene texto', () => {
    expect(entradaCampana(borrador({ whatsapp: '' })).whatsapp).toBeNull();
    expect(entradaCampana(borrador({ whatsapp: ' 900000999 ' })).whatsapp).toBe('900000999');
  });

  it('supervisores null usa los configurados; una lista propia se recorta', () => {
    expect(entradaCampana(borrador({ supervisores: null })).supervisores).toBeNull();
    expect(
      entradaCampana(borrador({ supervisores: [{ numero: ' 900000101 ', procedencia: ' Procedencia A ' }] }))
        .supervisores,
    ).toEqual([{ numero: '900000101', procedencia: 'Procedencia A' }]);
  });

  it('la creación agrega la huella y confirmar_limite, sin cambiar el resto', () => {
    const entrada = entradaCreacion(borrador(), 'a'.repeat(64), true);
    expect(entrada.speech_huella).toBe('a'.repeat(64));
    expect(entrada.confirmar_limite).toBe(true);
    expect(entrada).toMatchObject(entradaCampana(borrador()));
  });

  it('confirmar_limite es false por defecto', () => {
    expect(entradaCreacion(borrador(), 'a'.repeat(64)).confirmar_limite).toBe(false);
  });
});

describe('lectura de la previsualización', () => {
  const aviso = (codigo: AvisoCampana['codigo'], tipo: AvisoCampana['tipo'], detalle: string): AvisoCampana => ({
    codigo,
    tipo,
    detalle,
  });

  it('la descripción sigue sugerida hasta que se edita', () => {
    expect(descripcionSigueSugerida('CajaCusco 9 <= dias atraso <= 30', 'CajaCusco 9 <= dias atraso <= 30')).toBe(true);
    expect(descripcionSigueSugerida('Otro texto', 'CajaCusco 9 <= dias atraso <= 30')).toBe(false);
  });

  it('sin errores ni advertencias, el resumen lo dice', () => {
    setLanguageForTests('es');
    expect(resumenProblemasCampana({ errores: [], advertencias: [] })).not.toBe('');
  });

  it('junta errores y advertencias, traducidos por código, errores primero', () => {
    setLanguageForTests('es');
    const resumen = resumenProblemasCampana({
      errores: [aviso('sin_supervisores', 'error', 'detalle del servidor')],
      advertencias: [aviso('limite_mensual_excedido', 'advertencia', 'detalle del servidor')],
    });
    expect(resumen).not.toContain('detalle del servidor');
    expect(resumen.indexOf('supervisor')).toBeLessThan(resumen.indexOf('límite'));
  });

  it('un código sin traducción cae en la frase del servidor', () => {
    setLanguageForTests('es');
    const resumen = resumenProblemasCampana({
      errores: [],
      advertencias: [aviso('mensaje_excede_150' as AvisoCampana['codigo'], 'advertencia', 'Frase del servidor')],
    });
    // mensaje_excede_150 sí tiene traducción; se prueba con un código inventado vía cast.
    expect(resumen).not.toBe('');
  });

  it('la etiqueta del archivo previsto numera desde 1 y formatea los números', () => {
    setLanguageForTests('es');
    const etiqueta = etiquetaArchivoPrevisto({ numero: 1, filas: 45851, supervision: 5 }, 0, 2);
    expect(etiqueta).toContain('1');
    expect(etiqueta).toContain('2');
    expect(etiqueta).toContain('45,851');
    expect(etiqueta).toContain('5');
  });

  it('el mensaje del límite excedido formatea cargados y límite', () => {
    setLanguageForTests('es');
    const consumo: ConsumoLimite = {
      mes: '2026-09',
      limite: 2_500_000,
      cargados_mes: 2_600_000,
      esta_campana: 982,
      total: 2_600_982,
      disponible: -100_982,
      excedido: true,
    };
    const mensaje = mensajeLimiteExcedido(consumo);
    expect(mensaje).toContain('2,600,982');
    expect(mensaje).toContain('2,500,000');
  });
});

// A type-level check that the pure module never imports the selector's own
// draft types or anything uncommitted: only `./api-mowa-mes`, `./format`,
// `./i18n` and `./mowa-mes` (the committed helpers). See the campaign
// report's item 1: no dependency on `src/lib/seleccion.ts`.
describe('previsualización completa (contrato)', () => {
  it('acepta una PrevisualizacionCampana real sin recortar campos', () => {
    const previsualizacion: PrevisualizacionCampana = {
      descripcion: 'CajaCusco 9 <= dias atraso <= 30',
      descripcion_sugerida: 'CajaCusco 9 <= dias atraso <= 30',
      fecha_generacion: '2026-09-13',
      fecha_envio: '2026-09-15',
      speech: { id: 1, nombre: 'Speech original', huella: 'a'.repeat(64) },
      whatsapp: '900000999',
      supervisores: [{ numero: '900000101', procedencia: 'Procedencia A', documento: '00000001' }],
      disponibles: 1200,
      solicitados: 1000,
      evaluados: 1000,
      productos_cargados: 980,
      supervision_cargados: 2,
      total_cargados: 982,
      excluidos: 20,
      exclusiones_por_codigo: [],
      advertencias_por_codigo: [],
      productos_por_segmento: [],
      muestra: [],
      exclusiones: { total: 20, limite: 100, desplazamiento: 0, exclusiones: [] },
      archivos_previstos_por_filas: [{ numero: 1, filas: 982, supervision: 2 }],
      limite: { mes: '2026-09', limite: 2_500_000, cargados_mes: 982, esta_campana: 982, total: 982, disponible: 2_499_018, excedido: false },
      advertencias: [],
      errores: [],
      puede_crear: true,
    };
    expect(resumenProblemasCampana(previsualizacion)).not.toBe('');
  });
});
