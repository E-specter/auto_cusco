/**
 * Going back from a tool to a channel (T-HI-F3, RF-74; docs/whatsmkt-interfaz.md §2, docs/mowa-mes-interfaz.md §4.7).
 * The tools accept `volver` from MOWA MES and from WhatsMKT, with the defences `volverValido` always had, and read
 * `?definicion=` and `?plataforma=` of Columnas de carga. The MOWA cases stay in `mowa-mes-editar-en-cartera.test.ts`.
 */
import { describe, expect, it } from 'vitest';

import {
  definicionDeLaUrl,
  definicionPedidaDeLaUrl,
  destinoConDefinicion,
  destinoSinDefinicion,
  enlaceCrearDefinicion,
  enlaceEditarDefinicion,
  enlaceEditarEnCartera,
  origenDeVolver,
  plataformaDeLaUrl,
  seleccionDeLaUrl,
  volverValido,
} from '../../src/lib/volver';

const ORIGEN = 'http://localhost:4321';

describe('volverValido con WhatsMKT', () => {
  it('acepta una ruta de /whatsmkt/ del mismo origen, y sigue aceptando las de /mowa-mes/', () => {
    expect(volverValido('/whatsmkt/campana', ORIGEN)).toBe('/whatsmkt/campana');
    expect(volverValido('/whatsmkt/configuracion', ORIGEN)).toBe('/whatsmkt/configuracion');
    expect(volverValido('/whatsmkt/campana?x=1', ORIGEN)).toBe('/whatsmkt/campana?x=1');
    expect(volverValido(`${ORIGEN}/whatsmkt/campana`, ORIGEN)).toBe('/whatsmkt/campana');
    expect(volverValido('/mowa-mes/campana', ORIGEN)).toBe('/mowa-mes/campana');
  });

  it('ignora una dirección que empieza con // aunque la ruta sea de /whatsmkt/', () => {
    expect(volverValido('//evil.com', ORIGEN)).toBeNull();
    expect(volverValido('//evil.com/whatsmkt/campana', ORIGEN)).toBeNull();
    expect(volverValido('///whatsmkt/campana', ORIGEN)).toBeNull();
    expect(volverValido('//localhost:4321/whatsmkt/campana', ORIGEN)).toBeNull();
  });

  it('ignora otro origen aunque la ruta sea de /whatsmkt/', () => {
    expect(volverValido('https://evil.com/whatsmkt/', ORIGEN)).toBeNull();
    expect(volverValido('https://evil.com/whatsmkt/campana', ORIGEN)).toBeNull();
    expect(volverValido('http://localhost:9999/whatsmkt/campana', ORIGEN)).toBeNull();
    expect(volverValido('http://localhost:4321.evil.com/whatsmkt/campana', ORIGEN)).toBeNull();
  });

  it('ignora lo que no es una página: javascript:, data:, vacío', () => {
    expect(volverValido('javascript:alert(1)//whatsmkt/', ORIGEN)).toBeNull();
    expect(volverValido('JaVaScRiPt:alert(1)', ORIGEN)).toBeNull();
    expect(volverValido('data:text/html,<script>alert(1)</script>', ORIGEN)).toBeNull();
    expect(volverValido('', ORIGEN)).toBeNull();
    expect(volverValido(null, ORIGEN)).toBeNull();
    expect(volverValido(undefined, ORIGEN)).toBeNull();
  });

  it('valida la ruta YA normalizada: /whatsmkt/../cartera es /cartera y se ignora', () => {
    expect(volverValido('/whatsmkt/../cartera', ORIGEN)).toBeNull();
    expect(volverValido('/whatsmkt/%2e%2e/cartera', ORIGEN)).toBeNull();
    expect(volverValido('/whatsmkt/./campana', ORIGEN)).toBe('/whatsmkt/campana');
    expect(volverValido('/otra/../whatsmkt/campana', ORIGEN)).toBe('/whatsmkt/campana');
    // De un canal a otro por la ruta: lo que queda decide, y las dos son canales.
    expect(volverValido('/whatsmkt/../mowa-mes/campana', ORIGEN)).toBe('/mowa-mes/campana');
  });

  it('ignora lo que no cuelga de un canal, y los parecidos', () => {
    expect(volverValido('/cartera', ORIGEN)).toBeNull();
    expect(volverValido('/columnas', ORIGEN)).toBeNull();
    expect(volverValido('/whatsmkt', ORIGEN)).toBeNull();
    expect(volverValido('/whatsmktx/campana', ORIGEN)).toBeNull();
    expect(volverValido('/x/whatsmkt/campana', ORIGEN)).toBeNull();
    expect(volverValido('whatsmkt/campana', ORIGEN)).toBe('/whatsmkt/campana');
  });

  it('ignora las barras invertidas y los caracteres de control que el navegador convierte en //', () => {
    expect(volverValido('/\\evil.com', ORIGEN)).toBeNull();
    expect(volverValido('\\\\evil.com/whatsmkt/', ORIGEN)).toBeNull();
    expect(volverValido('/\t/evil.com', ORIGEN)).toBeNull();
    expect(volverValido('\t//evil.com/whatsmkt/', ORIGEN)).toBeNull();
  });
});

describe('el canal de un volver', () => {
  it('sale del prefijo de la ruta ya validada', () => {
    expect(origenDeVolver('/whatsmkt/campana')).toBe('whatsmkt');
    expect(origenDeVolver('/whatsmkt/configuracion?x=1')).toBe('whatsmkt');
    expect(origenDeVolver('/mowa-mes/campana')).toBe('mowa-mes');
    expect(origenDeVolver('/mowa-mes/configuracion')).toBe('mowa-mes');
  });
});

describe('los enlaces de ida a Columnas de carga', () => {
  it('editar una definición lleva el id y adónde volver, bien escapado, y lo que llega se valida', () => {
    expect(enlaceEditarDefinicion(7, '/whatsmkt/campana')).toBe('/columnas?definicion=7&volver=%2Fwhatsmkt%2Fcampana');
    const ida = new URL(enlaceEditarDefinicion(7, '/whatsmkt/campana?a=1&b=2'), ORIGEN);
    expect(ida.pathname).toBe('/columnas');
    expect(definicionPedidaDeLaUrl(ida.search)).toBe(7);
    expect(volverValido(ida.searchParams.get('volver'), ORIGEN)).toBe('/whatsmkt/campana?a=1&b=2');
  });

  it('crear una definición lleva la plataforma y adónde volver', () => {
    expect(enlaceCrearDefinicion('whatsmkt', '/whatsmkt/configuracion')).toBe('/columnas?plataforma=whatsmkt&volver=%2Fwhatsmkt%2Fconfiguracion');
    const ida = new URL(enlaceCrearDefinicion('whatsmkt', '/whatsmkt/campana'), ORIGEN);
    expect(ida.searchParams.get('plataforma')).toBe('whatsmkt');
    expect(volverValido(ida.searchParams.get('volver'), ORIGEN)).toBe('/whatsmkt/campana');
  });

  it('una clave con caracteres especiales viaja escapada y vuelve igual', () => {
    const ida = new URL(enlaceCrearDefinicion('a b&c=d', '/whatsmkt/campana'), ORIGEN);
    expect(ida.searchParams.get('plataforma')).toBe('a b&c=d');
    expect(ida.searchParams.get('volver')).toBe('/whatsmkt/campana');
  });

  it('el enlace a Cartera de MOWA sigue como estaba', () => {
    expect(enlaceEditarEnCartera(7, '/mowa-mes/campana')).toBe('/cartera?seleccion=7&volver=%2Fmowa-mes%2Fcampana');
    expect(enlaceEditarEnCartera(7, '/whatsmkt/campana')).toBe('/cartera?seleccion=7&volver=%2Fwhatsmkt%2Fcampana');
  });
});

describe('leer ?definicion= y ?plataforma=', () => {
  it('?definicion= (para abrirla) es un id entero positivo, o nada', () => {
    expect(definicionPedidaDeLaUrl('?definicion=7')).toBe(7);
    expect(definicionPedidaDeLaUrl('?volver=%2Fwhatsmkt%2Fcampana&definicion=12')).toBe(12);
    for (const malo of ['', '?definicion=', '?definicion=abc', '?definicion=0', '?definicion=-3', '?definicion=2.5', '?definicion=1e3', '?definicion=7abc', '?definicion=%207', '?x=1']) {
      expect(definicionPedidaDeLaUrl(malo), malo).toBeNull();
    }
    expect(definicionPedidaDeLaUrl('?definicion=99999999999999999999')).toBeNull();
  });

  it('lo que el canal lee al volver es {id, version}, y falta uno o no es entero positivo, nada', () => {
    expect(definicionDeLaUrl('?definicion=7&version=3')).toEqual({ id: 7, version: 3 });
    expect(definicionDeLaUrl('?x=1&version=3&definicion=7')).toEqual({ id: 7, version: 3 });
    for (const mala of ['', '?definicion=7', '?version=3', '?definicion=7&version=', '?definicion=7&version=0', '?definicion=0&version=3', '?definicion=a&version=3', '?definicion=7&version=-1', '?definicion=7&version=2.5']) {
      expect(definicionDeLaUrl(mala), mala).toBeNull();
    }
  });

  it('?definicion= y ?seleccion= no se confunden', () => {
    expect(seleccionDeLaUrl('?definicion=7')).toBeNull();
    expect(definicionPedidaDeLaUrl('?seleccion=7')).toBeNull();
    expect(seleccionDeLaUrl('?seleccion=7&definicion=9')).toBe(7);
  });

  it('?plataforma= es la clave de una plataforma registrada, y una que no lo es se ignora', () => {
    const plataformas = [{ clave: 'whatsmkt' }, { clave: 'mowa_mes' }];
    expect(plataformaDeLaUrl('?plataforma=whatsmkt', plataformas)).toBe('whatsmkt');
    expect(plataformaDeLaUrl('?volver=%2Fwhatsmkt%2Fcampana&plataforma=mowa_mes', plataformas)).toBe('mowa_mes');
    for (const mala of ['', '?plataforma=', '?plataforma=otra', '?plataforma=WhatsMKT', '?plataforma=whatsmkt%20', '?plataforma=__proto__', '?x=1']) {
      expect(plataformaDeLaUrl(mala, plataformas), mala).toBeNull();
    }
    // Sin plataformas registradas nada es válido.
    expect(plataformaDeLaUrl('?plataforma=whatsmkt', [])).toBeNull();
  });
});

describe('el destino al volver de una definición', () => {
  it('al guardar lleva definicion y version, conservando lo demás', () => {
    expect(destinoConDefinicion('/whatsmkt/campana', 7, 3)).toBe('/whatsmkt/campana?definicion=7&version=3');
    expect(destinoConDefinicion('/whatsmkt/campana?x=1', 7, 3)).toBe('/whatsmkt/campana?x=1&definicion=7&version=3');
    expect(destinoConDefinicion('/whatsmkt/campana?definicion=2&version=1', 7, 3)).toBe('/whatsmkt/campana?definicion=7&version=3');
  });

  it('sin guardar vuelve sin ninguno de los dos', () => {
    expect(destinoSinDefinicion('/whatsmkt/campana?definicion=7&version=3')).toBe('/whatsmkt/campana');
    expect(destinoSinDefinicion('/whatsmkt/campana?x=1&definicion=7&version=3')).toBe('/whatsmkt/campana?x=1');
    expect(destinoSinDefinicion('/whatsmkt/campana')).toBe('/whatsmkt/campana');
  });

  it('el destino de un volver válido queda en el mismo canal y el mismo origen', () => {
    const volver = volverValido('/whatsmkt/campana?x=1', ORIGEN)!;
    const con = destinoConDefinicion(volver, 7, 3);
    expect(volverValido(con, ORIGEN)).toBe(con);
    expect(new URL(con, ORIGEN).origin).toBe(ORIGEN);
  });
});
