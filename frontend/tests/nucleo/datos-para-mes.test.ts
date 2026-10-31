/**
 * The data to upload to MES (RF-MM-35): what the form of MES asks for, in its order, as the screen reads it
 * and the analyst copies it. Values are synthetic.
 */
import { afterEach, describe, expect, it } from 'vitest';

import type { Campana } from '../../src/lib/api-mowa-mes';
import { datosParaMes, fechaHoraParaMes } from '../../src/lib/mowa-mes-campana';
import { setLanguageForTests } from './idioma';

type Datos = Pick<Campana, 'tipo_carga' | 'descripcion' | 'salida' | 'herramientas' | 'programacion' | 'envios'>;

const base = (parcial: Partial<Datos> = {}): Datos => ({
  tipo_carga: 'masiva',
  descripcion: 'Preventiva 9 a 30 · septiembre',
  salida: 'numero_largo',
  herramientas: { keyword: false, respuesta_automatica: false, blacklist_indecopi: false, speech_optimizado: false },
  programacion: 'hora_determinada',
  envios: ['2026-09-14T09:00:00-05:00'],
  ...parcial,
});

afterEach(() => setLanguageForTests('es'));

describe('fechaHoraParaMes', () => {
  it('dd/mm/aaaa hh:mm en hora de Lima, venga el instante en la zona que venga', () => {
    expect(fechaHoraParaMes('2026-09-14T09:00:00-05:00')).toBe('14/09/2026 09:00');
    expect(fechaHoraParaMes('2026-09-14T14:00:00Z')).toBe('14/09/2026 09:00');
  });

  it('la medianoche es 00:00, no 24:00', () => {
    expect(fechaHoraParaMes('2026-09-14T00:00:00-05:00')).toBe('14/09/2026 00:00');
  });

  it('un instante que en UTC ya es otro día sigue siendo el día de Lima', () => {
    expect(fechaHoraParaMes('2026-09-15T02:30:00Z')).toBe('14/09/2026 21:30');
  });
});

describe('datosParaMes', () => {
  it('son cinco, en el orden del formulario de MES', () => {
    expect(datosParaMes(base()).map((d) => d.clave)).toEqual([
      'tipoCarga',
      'descripcion',
      'salida',
      'herramientas',
      'programacion',
    ]);
  });

  it('cada dato lleva su etiqueta y su valor, con las palabras de la pantalla', () => {
    expect(datosParaMes(base({ herramientas: { keyword: true, respuesta_automatica: false, blacklist_indecopi: true, speech_optimizado: false } }))).toEqual([
      { clave: 'tipoCarga', etiqueta: 'Tipo de carga', valor: 'Masiva' },
      { clave: 'descripcion', etiqueta: 'Descripción de la campaña', valor: 'Preventiva 9 a 30 · septiembre' },
      { clave: 'salida', etiqueta: 'Salida', valor: 'Número largo' },
      { clave: 'herramientas', etiqueta: 'Herramientas', valor: 'Keyword, Blacklist Indecopi' },
      { clave: 'programacion', etiqueta: 'Programación del envío', valor: 'Enviar en hora determinada: 14/09/2026 09:00' },
    ]);
  });

  it('la descripción viaja tal cual la guardó la API, sin cambiarla', () => {
    const valor = datosParaMes(base({ descripcion: '  Dos  espacios y una ñ ' }))[1].valor;
    expect(valor).toBe('  Dos  espacios y una ñ ');
  });

  it('sin herramientas dice «Ninguna», no una cadena vacía que se copiaría vacía', () => {
    expect(datosParaMes(base())[3].valor).toBe('Ninguna');
  });

  it('una sola herramienta no lleva coma', () => {
    const herramientas = { keyword: true, respuesta_automatica: false, blacklist_indecopi: false, speech_optimizado: false };
    expect(datosParaMes(base({ herramientas }))[3].valor).toBe('Keyword');
  });

  it('varias fechas de envío van todas, separadas', () => {
    const envios = ['2026-09-14T09:00:00-05:00', '2026-09-14T15:30:00-05:00'];
    const valor = datosParaMes(base({ programacion: 'diferentes_horas', envios }))[4].valor;
    expect(valor).toBe('Enviar en diferentes horas: 14/09/2026 09:00; 14/09/2026 15:30');
  });

  it('enviar ahora, sin fechas, es solo la palabra', () => {
    expect(datosParaMes(base({ programacion: 'enviar_ahora', envios: [] }))[4].valor).toBe('Enviar ahora');
  });

  it('en inglés traduce etiquetas y valores, y las fechas siguen igual', () => {
    setLanguageForTests('en');
    const datos = datosParaMes(base());
    expect(datos.map((d) => d.etiqueta)).toEqual(['Load type', 'Campaign description', 'Output', 'Tools', 'Send scheduling']);
    expect(datos[0].valor).toBe('Mass');
    expect(datos[4].valor).toMatch(/: 14\/09\/2026 09:00$/);
  });
});
