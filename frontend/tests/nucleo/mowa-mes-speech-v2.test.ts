/**
 * The v2 speech of MOWA MES (docs/motor-texto-enriquecido-interfaz.md §5.6; B6): one expression of
 * the engine per segment instead of two fixed parts. What matters here is what costs a campaign
 * when it is wrong: a segment without content is never sent as if it were saved, a level is never
 * claimed without a maximum length, and a problem is translated from the catalogue it came from
 * (the two catalogues share `telefono_invalido` with different texts).
 */
import { describe, expect, it } from 'vitest';

import type { LargoSegmento, VersionSpeech } from '../../src/lib/api-mowa-mes';
import {
  entradaDeExpresiones,
  esV2,
  hayCambiosV2,
  mensajeDeProblema,
  nivelesDeV2,
  segmentosDeVersion,
  segmentosSinContenido,
  variantesDeVersion,
  type ProblemaSpeech,
} from '../../src/lib/mowa-mes-speech-v2';

const TEXTO = (valor: string) => ({ tipo: 'texto' as const, valor });
const VARIABLE = (nombre: string, obligatoria = false) => ({
  tipo: 'variable' as const,
  nombre,
  funciones: [],
  obligatoria,
});

const RANGOS = [
  { segmento: 'preventiva' as const, etiqueta: 'Preventiva', dias_desde: null, dias_hasta: 0 },
  { segmento: '1_a_8' as const, etiqueta: '1 a 8', dias_desde: 1, dias_hasta: 8 },
  { segmento: '9_a_30' as const, etiqueta: '9 a 30', dias_desde: 9, dias_hasta: 30 },
  { segmento: '31_a_60' as const, etiqueta: '31 a 60', dias_desde: 31, dias_hasta: 60 },
  { segmento: '61_a_90' as const, etiqueta: '61 a 90', dias_desde: 61, dias_hasta: 90 },
  { segmento: '91_a_120' as const, etiqueta: '91 a 120', dias_desde: 91, dias_hasta: 120 },
];

/** A saved v2 as the API gives it: one expression per segment, in no particular order. */
function versionV2(parcial: Partial<VersionSpeech> = {}): VersionSpeech {
  return {
    id: 5,
    nombre: 'Speech 2',
    formato: 'v2',
    original: false,
    basada_en_id: 1,
    usada: false,
    editable: true,
    creado_en: '2026-10-10T09:00:00-05:00',
    partes: [],
    expresiones: [...RANGOS].reverse().map((r) => ({
      ...r,
      expresion: { nodos: [VARIABLE('titular', true), TEXTO(` te recuerda tu cuota de ${r.etiqueta}`)] },
      usa_titular: true,
      usa_vencimiento: false,
      usa_whatsapp: false,
    })),
    ...parcial,
  };
}

function largo(parcial: Partial<LargoSegmento> = {}): LargoSegmento {
  return {
    segmento: '9_a_30',
    etiqueta: '9 a 30',
    usa_whatsapp: false,
    falta_whatsapp: false,
    largo_maximo: 100,
    sin_maximo: null,
    codigo: null,
    ejemplo: 'ejemplo',
    ...parcial,
  };
}

describe('qué versión es v2', () => {
  it('lo dice el formato, no la forma de sus datos', () => {
    expect(esV2(versionV2())).toBe(true);
    expect(esV2(versionV2({ formato: 'v1', expresiones: [] }))).toBe(false);
  });
});

describe('el borrador que sale de una versión', () => {
  it('trae una expresión por segmento, en el orden de los segmentos', () => {
    const variantes = variantesDeVersion(versionV2());

    expect(variantes.map((v) => v.segmento)).toEqual(RANGOS.map((r) => r.segmento));
  });

  it('es una copia: editarlo no cambia la versión', () => {
    const version = versionV2();

    const variantes = variantesDeVersion(version);
    variantes[0].expresion.nodos.push({ tipo: 'texto', valor: 'x' });

    expect(version.expresiones.find((e) => e.segmento === 'preventiva')?.expresion.nodos).toHaveLength(2);
  });

  it('los segmentos que ofrece el selector salen de la propia versión, con su rango de días', () => {
    const segmentos = segmentosDeVersion(versionV2());

    expect(segmentos.map((s) => s.clave)).toEqual(RANGOS.map((r) => r.segmento));
    expect(segmentos[0]).toEqual({ clave: 'preventiva', etiqueta: 'Preventiva', desde: null, hasta: 0 });
    expect(segmentos[2]).toEqual({ clave: '9_a_30', etiqueta: '9 a 30', desde: 9, hasta: 30 });
  });
});

describe('cambios sin guardar', () => {
  it('un borrador recién leído no los tiene', () => {
    const v = versionV2();

    expect(hayCambiosV2(v, variantesDeVersion(v))).toBe(false);
  });

  it('el orden no es un cambio', () => {
    const v = versionV2();

    expect(hayCambiosV2(v, [...variantesDeVersion(v)].reverse())).toBe(false);
  });

  it('«obligatoria: false» y la marca ausente son lo mismo: el editor la omite', () => {
    const v = versionV2();
    const variantes = variantesDeVersion(v).map((x) => ({
      ...x,
      expresion: {
        nodos: x.expresion.nodos.map((n) => {
          if (n.tipo !== 'variable') return n;
          const { obligatoria: _o, ...resto } = n;
          return resto;
        }),
      },
    }));
    const conFalse = versionV2({
      expresiones: v.expresiones.map((e) => ({
        ...e,
        expresion: {
          nodos: e.expresion.nodos.map((n) => (n.tipo === 'variable' ? { ...n, obligatoria: false } : n)),
        },
      })),
    });

    expect(hayCambiosV2(conFalse, variantes)).toBe(false);
  });

  it('cambiar el texto de un segmento sí lo es, con sus espacios de los extremos', () => {
    const v = versionV2();
    const variantes = variantesDeVersion(v);
    variantes[2].expresion.nodos.push(TEXTO(' '));

    expect(hayCambiosV2(v, variantes)).toBe(true);
  });

  it('vaciar un segmento es un cambio', () => {
    const v = versionV2();
    const variantes = variantesDeVersion(v).filter((x) => x.segmento !== '31_a_60');

    expect(hayCambiosV2(v, variantes)).toBe(true);
  });
});

describe('qué se manda al guardar', () => {
  it('una expresión por segmento con contenido, en el orden de los segmentos', () => {
    const entrada = entradaDeExpresiones([...variantesDeVersion(versionV2())].reverse());

    expect(entrada.map((e) => e.segmento)).toEqual(RANGOS.map((r) => r.segmento));
    expect(entrada[0].expresion.nodos).toHaveLength(2);
  });

  it('un segmento vacío no se manda como si se hubiera guardado', () => {
    const variantes = variantesDeVersion(versionV2());
    variantes[1] = { ...variantes[1], expresion: { nodos: [TEXTO('')] } };

    const entrada = entradaDeExpresiones(variantes);

    expect(entrada.map((e) => e.segmento)).not.toContain('1_a_8');
    expect(entrada).toHaveLength(5);
  });

  it('los segmentos sin contenido se reconocen para avisarlos', () => {
    const variantes = variantesDeVersion(versionV2());
    variantes[1] = { ...variantes[1], expresion: { nodos: [] } };
    const segmentos = segmentosDeVersion(versionV2());

    expect(segmentosSinContenido(variantes, segmentos).map((s) => s.clave)).toEqual(['1_a_8']);
  });

  it('un segmento que falta del todo también está sin contenido', () => {
    const variantes = variantesDeVersion(versionV2()).filter((x) => x.segmento !== '91_a_120');

    expect(segmentosSinContenido(variantes, segmentosDeVersion(versionV2())).map((s) => s.clave)).toEqual([
      '91_a_120',
    ]);
  });
});

describe('niveles por segmento', () => {
  it('cabe, advertencia y excede usan sus tonos y llevan el largo', () => {
    const niveles = nivelesDeV2([
      largo({ segmento: 'preventiva', largo_maximo: 120 }),
      largo({ segmento: '1_a_8', largo_maximo: 156, codigo: 'mensaje_excede_150' }),
      largo({ segmento: '9_a_30', largo_maximo: 170, codigo: 'mensaje_excede_160' }),
    ]);

    expect(niveles.preventiva.tono).toBe('vigente');
    expect(niveles['1_a_8'].tono).toBe('advertencia');
    expect(niveles['9_a_30'].tono).toBe('error');
    expect(niveles['9_a_30'].texto).toContain('170');
  });

  it('nunca afirma «Cabe» sin un máximo: sin cota explica el motivo', () => {
    const niveles = nivelesDeV2([
      largo({
        segmento: '9_a_30',
        largo_maximo: null,
        sin_maximo: {
          codigo: 'sin_cota_variable',
          detalle: 'x',
          ubicacion: { nodo: 0, funcion: null, parametro: null },
        },
      }),
    ]);

    expect(niveles['9_a_30'].tono).toBe('advertencia');
    expect(niveles['9_a_30'].texto).not.toMatch(/cabe/i);
    expect(niveles['9_a_30'].texto).toMatch(/máximo/i);
  });

  it('sin máximo ni motivo no se dice nada del segmento', () => {
    const niveles = nivelesDeV2([largo({ segmento: '9_a_30', largo_maximo: null, sin_maximo: null })]);

    expect(niveles).not.toHaveProperty('9_a_30');
  });

  it('falta el WhatsApp es un estado propio y gana sobre el largo', () => {
    const niveles = nivelesDeV2([largo({ segmento: '9_a_30', falta_whatsapp: true, usa_whatsapp: true })]);

    expect(niveles['9_a_30'].tono).toBe('neutral');
    expect(niveles['9_a_30'].texto).toMatch(/whatsapp/i);
  });
});

describe('qué texto lleva un problema', () => {
  const problema = (parcial: Partial<ProblemaSpeech>): ProblemaSpeech => ({
    segmento: '9_a_30',
    campo: 'expresion',
    detalle: 'detalle del backend',
    codigo: null,
    catalogo: null,
    ubicacion: null,
    ...parcial,
  });

  it('un código del motor se traduce con textoEnriquecido.*', () => {
    const texto = mensajeDeProblema(problema({ codigo: 'variable_desconocida', catalogo: 'texto' }));

    expect(texto).not.toBe('detalle del backend');
    expect(texto).not.toContain('textoEnriquecido.');
  });

  it('un código de MOWA MES se traduce con mowaMes.*', () => {
    const texto = mensajeDeProblema(problema({ codigo: 'falta_whatsapp', catalogo: 'mowa_mes' }));

    expect(texto).not.toBe('detalle del backend');
    expect(texto).not.toContain('mowaMes.');
  });

  it('el mismo código en los dos catálogos usa la clave de su catálogo, no la del otro', () => {
    const delMotor = mensajeDeProblema(problema({ codigo: 'telefono_invalido', catalogo: 'texto' }));
    const deMowa = mensajeDeProblema(problema({ codigo: 'telefono_invalido', catalogo: 'mowa_mes' }));

    expect(delMotor).not.toBe(deMowa);
  });

  it('un código que no se conoce degrada al texto del backend, nunca a una clave', () => {
    expect(mensajeDeProblema(problema({ codigo: 'codigo_nuevo' as never, catalogo: 'texto' }))).toBe(
      'detalle del backend',
    );
  });

  it('sin código usa el detalle del backend', () => {
    expect(mensajeDeProblema(problema({}))).toBe('detalle del backend');
  });
});
