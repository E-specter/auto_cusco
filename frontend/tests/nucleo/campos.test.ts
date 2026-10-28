/**
 * Field and variable names on screen. A portfolio field shows its label; a
 * context variable shows the context's own key; anything without a label
 * falls back to its technical name with spaces instead of a raw key.
 */
import { afterEach, describe, expect, it } from 'vitest';

import {
  archivadosEnUso,
  avisoDeArchivados,
  etiquetaCampo,
  etiquetaDeCampo,
  etiquetaVariable,
  humanizarNombre,
  opcionesDeCampos,
  ordenarCampos,
  ordenarPorEtiqueta,
} from '../../src/lib/campos';
import { setLanguageForTests } from './idioma';

afterEach(() => setLanguageForTests('es'));

describe('etiqueta de un campo', () => {
  it('usa la etiqueta del diccionario en el idioma de la interfaz', () => {
    expect(etiquetaCampo('saldo_capital_pendiente')).toBe('Saldo de capital pendiente');

    setLanguageForTests('en');

    expect(etiquetaCampo('saldo_capital_pendiente')).toBe('Outstanding principal');
  });

  it('un campo sin etiqueta muestra su nombre técnico con espacios, nunca la clave', () => {
    expect(etiquetaCampo('campo_nuevo_sin_etiqueta')).toBe('campo nuevo sin etiqueta');
    expect(humanizarNombre('a_b')).toBe('a b');
  });
});

describe('etiqueta de una variable del catálogo', () => {
  it('una variable de contexto usa su propia clave', () => {
    expect(etiquetaVariable({ nombre: 'whatsapp_contacto', clave_nombre: 'textoEnriquecido.variable.whatsapp_contacto' })).toBe(
      'WhatsApp de contacto',
    );
  });

  it('un campo de la cartera, sin clave propia, usa la etiqueta del campo', () => {
    expect(etiquetaVariable({ nombre: 'titular', clave_nombre: null })).toBe('Titular');
  });

  it('una clave que el diccionario no conoce cae a la etiqueta del campo', () => {
    expect(etiquetaVariable({ nombre: 'titular', clave_nombre: 'textoEnriquecido.variable.inexistente' })).toBe('Titular');
  });
});

describe('orden de lectura', () => {
  it('ordena por la etiqueta visible, no por el nombre técnico', () => {
    expect(ordenarPorEtiqueta(['pagare', 'dias_atraso', 'agencia'])).toEqual(['agencia', 'dias_atraso', 'pagare']);
    expect(ordenarPorEtiqueta(['titular', 'saldo_capital_pendiente'])).toEqual(['saldo_capital_pendiente', 'titular']);
  });
});

describe('etiqueta de un campo adicional (RF-66)', () => {
  it('la etiqueta propia manda sobre la clave y sobre el nombre técnico', () => {
    expect(etiquetaDeCampo({ nombre: 'ad_monto_mora', etiqueta: 'Monto en mora' })).toBe('Monto en mora');
    expect(etiquetaDeCampo({ nombre: 'saldo_capital_pendiente', etiqueta: 'Otro nombre' })).toBe('Otro nombre');
  });

  it('sin etiqueta usa la clave dada, o la del campo, y al final el nombre con espacios', () => {
    expect(etiquetaDeCampo({ nombre: 'saldo_capital_pendiente', etiqueta: null })).toBe('Saldo de capital pendiente');
    expect(etiquetaDeCampo({ nombre: 'otro', clave: 'campo.titular' })).toBe('Titular');
    expect(etiquetaDeCampo({ nombre: 'ad_sin_etiqueta' })).toBe('ad sin etiqueta');
  });

  it('una variable del catálogo con etiqueta propia la muestra, aunque traiga clave', () => {
    expect(etiquetaVariable({ nombre: 'ad_monto_mora', clave_nombre: null, etiqueta: 'Monto en mora' })).toBe('Monto en mora');
    expect(etiquetaVariable({ nombre: 'titular', clave_nombre: null, etiqueta: null })).toBe('Titular');
  });
});

describe('listas de campos con adicionales', () => {
  const campos = {
    titular: { adicional: false, etiqueta: null },
    agencia: { adicional: false, etiqueta: null },
    ad_zona: { adicional: true, etiqueta: 'Zona', archivado: false },
    ad_antiguo: { adicional: true, etiqueta: 'Antiguo', archivado: true },
    ad_monto: { adicional: true, etiqueta: 'Aporte', archivado: false },
  };
  const nombres = Object.keys(campos);

  it('los base van primero y los adicionales al final, cada grupo por su nombre visible', () => {
    expect(ordenarCampos(campos, nombres)).toEqual(['agencia', 'titular', 'ad_antiguo', 'ad_monto', 'ad_zona']);
  });

  it('un archivado no se ofrece, salvo el que ya está elegido, que lo dice en el texto', () => {
    expect(opcionesDeCampos(campos, nombres, null).map(([valor]) => valor)).toEqual(['agencia', 'titular', 'ad_monto', 'ad_zona']);
    const conActual = opcionesDeCampos(campos, nombres, 'ad_antiguo');
    expect(conActual.find(([valor]) => valor === 'ad_antiguo')?.[1]).toBe('Antiguo (archivado)');
  });

  it('solo los adicionales llevan grupo, y es «Campos adicionales»', () => {
    const opciones = opcionesDeCampos(campos, nombres, null);
    expect(opciones.filter(([, , grupo]) => grupo === 'Campos adicionales').map(([valor]) => valor)).toEqual(['ad_monto', 'ad_zona']);
    expect(opciones.filter(([, , grupo]) => grupo === undefined).map(([valor]) => valor)).toEqual(['agencia', 'titular']);
  });

  it('el grupo y el sufijo siguen el idioma', () => {
    setLanguageForTests('en');
    expect(opcionesDeCampos(campos, nombres, 'ad_antiguo').find(([valor]) => valor === 'ad_antiguo')).toEqual([
      'ad_antiguo',
      'Antiguo (archived)',
      'Additional fields',
    ]);
  });
});

describe('el aviso de un campo archivado en uso', () => {
  const campos = {
    titular: { adicional: false },
    ad_viejo: { adicional: true, etiqueta: 'Monto en mora', archivado: true },
    ad_otro: { adicional: true, etiqueta: 'Zona', archivado: true },
    ad_vivo: { adicional: true, etiqueta: 'Vivo', archivado: false },
  };

  it('nombra solo los archivados que se usan, sin repetirlos', () => {
    expect(archivadosEnUso(campos, ['titular', 'ad_viejo', 'ad_vivo', 'ad_viejo', 'inexistente'])).toEqual(['Monto en mora']);
  });

  it('en singular y en plural, y sin aviso si no hay ninguno', () => {
    expect(avisoDeArchivados(['Monto en mora'])).toBe('Usa el campo archivado «Monto en mora». Las sábanas cargadas después de archivarlo ya no lo traen: ahí sale vacío. Para evitarlo, reactívalo en Cargas › Campos adicionales.');
    expect(avisoDeArchivados(['Monto en mora', 'Zona'])).toBe(
      'Usa los campos archivados «Monto en mora», «Zona». Las sábanas cargadas después de archivarlos ya no los traen: ahí salen vacíos. Para evitarlo, reactívalos en Cargas › Campos adicionales.',
    );
    expect(avisoDeArchivados([])).toBeNull();
  });

  it('en inglés cita el nombre con las comillas del idioma, no con las fijas del español', () => {
    setLanguageForTests('en');
    expect(avisoDeArchivados(['Monto en mora'])).toBe(
      'It uses the archived field “Monto en mora”. Sheets loaded after it was archived no longer bring it: there it is empty. To avoid this, reactivate it in Uploads › Additional fields.',
    );
    expect(avisoDeArchivados(['Monto en mora', 'Zona'])).toBe(
      'It uses the archived fields “Monto en mora”, “Zona”. Sheets loaded after they were archived no longer bring them: there they are empty. To avoid this, reactivate them in Uploads › Additional fields.',
    );
    expect(avisoDeArchivados(['Monto en mora'])).not.toContain('«');
  });
});
