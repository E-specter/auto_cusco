/**
 * The order of the table that manages the additional fields and the names the incidences show (T-CA-F2, RF-65 and RF-66).
 */
import { afterEach, describe, expect, it } from 'vitest';

import type { CampoAdicional } from '../../src/lib/api-mapeador';
import { columnaDeIncidencia, nombreVisibleDeCampo, ordenarAdicionales, puedeGuardarNombre } from '../../src/lib/campos-adicionales';
import { setLanguageForTests } from './idioma';

afterEach(() => setLanguageForTests('es'));

const campo = (nombre: string, nombreLegible: string, archivado = false): CampoAdicional => ({
  nombre,
  nombre_legible: nombreLegible,
  tipo: 'texto',
  encabezado_origen: nombre,
  archivado,
});

const CAMPOS = [campo('ad_zona', 'Zona de cobranza'), campo('ad_monto', 'Monto en mora'), campo('ad_viejo', 'Campo antiguo', true)];

describe('el orden de la tabla', () => {
  it('los activos primero y los archivados al final, cada grupo por su nombre visible', () => {
    const desordenados = [campo('ad_c', 'Zeta', true), campo('ad_b', 'Beta'), campo('ad_a', 'Alfa', true), campo('ad_z', 'Zona')];
    expect(ordenarAdicionales(desordenados).map((c) => c.nombre_legible)).toEqual(['Beta', 'Zona', 'Alfa', 'Zeta']);
  });

  it('no cambia la lista que recibe', () => {
    const lista = [...CAMPOS];
    ordenarAdicionales(lista);
    expect(lista).toEqual(CAMPOS);
  });
});

describe('guardar un nombre', () => {
  it('pide un nombre que no esté vacío y que sea otro', () => {
    expect(puedeGuardarNombre('Zona norte', 'Zona de cobranza')).toBe(true);
    expect(puedeGuardarNombre('   ', 'Zona de cobranza')).toBe(false);
    expect(puedeGuardarNombre('', 'Zona de cobranza')).toBe(false);
    expect(puedeGuardarNombre('Zona de cobranza', 'Zona de cobranza')).toBe(false);
    // Spaces at the ends are not a new name.
    expect(puedeGuardarNombre('  Zona de cobranza ', 'Zona de cobranza')).toBe(false);
  });
});

describe('el nombre de un campo conocido por su nombre técnico', () => {
  it('un adicional, por su nombre legible, también archivado', () => {
    expect(nombreVisibleDeCampo('ad_zona', CAMPOS)).toBe('Zona de cobranza');
    expect(nombreVisibleDeCampo('ad_viejo', CAMPOS)).toBe('Campo antiguo');
  });

  it('uno base, por el diccionario, en el idioma de la interfaz', () => {
    expect(nombreVisibleDeCampo('telefono', CAMPOS)).toBe('Teléfono');
    setLanguageForTests('en');
    expect(nombreVisibleDeCampo('telefono', CAMPOS)).not.toBe('Teléfono');
  });

  it('un adicional que la lista no trae cae al nombre técnico con espacios, nunca a la clave', () => {
    expect(nombreVisibleDeCampo('ad_sin_lista', [])).toBe('ad sin lista');
  });
});

describe('la «Columna» de una incidencia', () => {
  it('valor_no_convertible nombra un campo adicional', () => {
    expect(columnaDeIncidencia('valor_no_convertible', 'ad_monto', CAMPOS)).toBe('Monto en mora');
  });

  it('columnas_opcionales_ausentes separa por «, » y traduce cada nombre', () => {
    expect(columnaDeIncidencia('columnas_opcionales_ausentes', 'telefono, titular,ad_zona', CAMPOS)).toBe('Teléfono, Titular, Zona de cobranza');
  });

  it('una lista con huecos no deja nombres vacíos', () => {
    expect(columnaDeIncidencia('columnas_opcionales_ausentes', 'telefono, , titular,', CAMPOS)).toBe('Teléfono, Titular');
  });

  it('cualquier otro código trae un encabezado del archivo y se deja tal cual', () => {
    expect(columnaDeIncidencia('columna_faltante', 'bpo', CAMPOS)).toBe('bpo');
    expect(columnaDeIncidencia('cabecera_duplicada', 'telefono', CAMPOS)).toBe('telefono');
  });

  it('sin columna no hay nada que nombrar', () => {
    expect(columnaDeIncidencia('valor_no_convertible', null, CAMPOS)).toBeNull();
  });
});
