/**
 * What WhatsMKT reads when Columnas de carga sends it back (T-WM-F2b): the definition and version in the URL against the definitions listed, the
 * sentence of each way back, and the link that goes to Columnas. docs/motor-texto-enriquecido-interfaz.md §12.4.
 */
import { afterEach, beforeAll, describe, expect, it } from 'vitest';

import { destinoDeColumnas, enlaceConVolver, textoDeVuelta, vueltaDeDefinicion } from '../../src/lib/whatsmkt-vuelta';
import { setLanguageForTests } from './idioma';

beforeAll(() => setLanguageForTests('es'));
afterEach(() => setLanguageForTests('es'));

const LISTA = [
  { id: 4, nombre: 'Contactos WhatsMKT', plataforma: 'whatsmkt', version_vigente: 3 },
  { id: 5, nombre: 'Libre', plataforma: null, version_vigente: 1 },
  { id: 6, nombre: 'De otro canal', plataforma: 'mowa_mes', version_vigente: 2 },
];

describe('la vuelta de Columnas de carga', () => {
  it('sin definición y versión en la URL no vuelve nada', () => {
    expect(vueltaDeDefinicion('', LISTA)).toEqual({ tipo: 'ninguna' });
    expect(vueltaDeDefinicion('?seleccion=7', LISTA)).toEqual({ tipo: 'ninguna' });
    // One without the other is nothing: both come, or none does.
    expect(vueltaDeDefinicion('?definicion=4', LISTA)).toEqual({ tipo: 'ninguna' });
    expect(vueltaDeDefinicion('?version=2', LISTA)).toEqual({ tipo: 'ninguna' });
    expect(vueltaDeDefinicion('?definicion=abc&version=2', LISTA)).toEqual({ tipo: 'ninguna' });
  });

  it('una definición de WhatsMKT con su versión queda elegida, con su nombre', () => {
    expect(vueltaDeDefinicion('?definicion=4&version=3', LISTA)).toEqual({ tipo: 'elegida', id: 4, version: 3, nombre: 'Contactos WhatsMKT' });
    // An older version exists too, but what is chosen is the latest: that is the version that is said.
    expect(vueltaDeDefinicion('?definicion=4&version=1', LISTA)).toEqual({ tipo: 'elegida', id: 4, version: 3, nombre: 'Contactos WhatsMKT' });
  });

  it('una definición que ya no está, o una versión que no existe, no existe', () => {
    expect(vueltaDeDefinicion('?definicion=99&version=1', LISTA)).toEqual({ tipo: 'noExiste' });
    expect(vueltaDeDefinicion('?definicion=4&version=4', LISTA)).toEqual({ tipo: 'noExiste' });
    expect(vueltaDeDefinicion('?definicion=4&version=1', [])).toEqual({ tipo: 'noExiste' });
  });

  it('una definición libre o de otro canal no es de WhatsMKT', () => {
    expect(vueltaDeDefinicion('?definicion=5&version=1', LISTA)).toEqual({ tipo: 'noEsDeWhatsmkt' });
    expect(vueltaDeDefinicion('?definicion=6&version=2', LISTA)).toEqual({ tipo: 'noEsDeWhatsmkt' });
  });

  it('lo que sale con la vuelta es lo mismo que ya se sabe de los demás: otras claves de la URL no estorban', () => {
    expect(vueltaDeDefinicion('?seleccion=7&definicion=4&version=3', LISTA)).toMatchObject({ tipo: 'elegida', id: 4 });
  });
});

describe('lo que dice cada vuelta', () => {
  it('la elegida lleva el nombre citado y la versión; la que no existe y la que no es de WhatsMKT, sus frases', () => {
    expect(textoDeVuelta({ tipo: 'elegida', id: 4, version: 3, nombre: 'Contactos WhatsMKT' })).toBe('Se eligió «Contactos WhatsMKT», versión 3.');
    expect(textoDeVuelta({ tipo: 'noExiste' })).toBe('La definición que editaste ya no existe. Elige otra.');
    expect(textoDeVuelta({ tipo: 'noEsDeWhatsmkt' })).toBe('La definición elegida no es de WhatsMKT.');
    // The settings only put it on the select: they add that it still has to be saved.
    expect(textoDeVuelta({ tipo: 'elegida', id: 4, version: 3, nombre: 'Contactos WhatsMKT' }, true)).toBe(
      'Se eligió «Contactos WhatsMKT», versión 3. Falta guardarla como definición por defecto.',
    );
    expect(textoDeVuelta({ tipo: 'ninguna' })).toBe('');
  });

  it('en inglés', () => {
    setLanguageForTests('en');
    expect(textoDeVuelta({ tipo: 'elegida', id: 4, version: 3, nombre: 'Contactos WhatsMKT' })).toMatch(/version 3, was chosen\.$/);
    expect(textoDeVuelta({ tipo: 'noExiste' })).toBe('The definition you edited no longer exists. Choose another one.');
    expect(textoDeVuelta({ tipo: 'elegida', id: 4, version: 3, nombre: 'Contactos WhatsMKT' }, true)).toMatch(
      /version 3, was chosen\. It still has to be saved as the default definition\.$/,
    );
  });
});

describe('el enlace a Columnas de carga', () => {
  const volver = '/whatsmkt/campana?seleccion=7';

  it('con definiciones y ninguna elegida abre Columnas con solo el camino de vuelta, y sigue diciendo «Editar»', () => {
    const { href, clave } = destinoDeColumnas(null, true, volver);
    expect(clave).toBe('whatsmkt.archivo.editar');
    const url = new URL(href, 'http://x.invalid');
    expect(url.pathname).toBe('/columnas');
    expect([...url.searchParams.keys()]).toEqual(['volver']);
    expect(url.searchParams.get('volver')).toBe(volver);
  });

  it('con una definición elegida la edita, y vuelve a la pantalla con su consulta', () => {
    const { href, clave } = destinoDeColumnas(4, true, volver);
    expect(clave).toBe('whatsmkt.archivo.editar');
    const url = new URL(href, 'http://x.invalid');
    expect(url.pathname).toBe('/columnas');
    expect(url.searchParams.get('definicion')).toBe('4');
    expect(url.searchParams.get('volver')).toBe(volver);
    expect(url.searchParams.has('plataforma')).toBe(false);
  });

  it('sin definiciones crea una de la plataforma WhatsMKT', () => {
    const { href, clave } = destinoDeColumnas(null, false, '/whatsmkt/configuracion');
    expect(clave).toBe('whatsmkt.archivo.crear');
    const url = new URL(href, 'http://x.invalid');
    expect(url.searchParams.get('plataforma')).toBe('whatsmkt');
    expect(url.searchParams.get('volver')).toBe('/whatsmkt/configuracion');
    expect(url.searchParams.has('definicion')).toBe(false);
  });

  it('Supervisores y Calendario llevan solo el volver, codificado', () => {
    expect(enlaceConVolver('/supervisores', volver)).toBe('/supervisores?volver=%2Fwhatsmkt%2Fcampana%3Fseleccion%3D7');
    expect(enlaceConVolver('/calendario', '/whatsmkt/configuracion')).toBe('/calendario?volver=%2Fwhatsmkt%2Fconfiguracion');
  });
});
