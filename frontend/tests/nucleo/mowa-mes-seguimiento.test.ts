/**
 * Logic of the MOWA MES follow-up screen: months, the download summary, the
 * reconciliation's shape and paging. It also pins the exclusion filter to the
 * backend's catalogue, so a new exclusion reason cannot go missing from it.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import type { Conciliacion } from '../../src/lib/api-mowa-mes';
import { formatDate } from '../../src/lib/format';
import {
  CODIGOS_EXCLUSION,
  advertirAlDescartar,
  busquedaConVista,
  campanaDeLaUrl,
  elegirMesDescartadas,
  etiquetaDelMes,
  fechaDeDescarte,
  filasConciliacion,
  leerResumenDescarga,
  mesDe,
  moverMes,
  nombreArchivo,
  opcionesDeMeses,
  ordenarEstados,
  ordenarMeses,
  pendienteVisible,
  rangoPagina,
  usoDelLimite,
  vistaDeLaUrl,
} from '../../src/lib/mowa-mes-seguimiento';

const CATALOGO = fileURLToPath(
  new URL('../../../backend/app/core/entities/mowa_mes.py', import.meta.url),
);

/** Exclusion codes as `TIPO_CODIGO` maps them, in the enum's order. */
function exclusionesDelCatalogo(): string[] {
  const fuente = readFileSync(CATALOGO, 'utf8');
  const clase = fuente.match(/class CodigoMowaMes\(StrEnum\):([\s\S]*?)(?=\n\S)/);
  const tipos = fuente.match(/TIPO_CODIGO[^=]*=\s*\{([\s\S]*?)\}/);
  if (!clase || !tipos) {
    throw new Error(`No se encontró CodigoMowaMes o TIPO_CODIGO en ${CATALOGO}; esta prueba debe seguirlos.`);
  }
  const valores = new Map(
    [...clase[1].matchAll(/^\s+([A-Z][A-Z0-9_]*)\s*=\s*"([a-z][a-z0-9_]*)"/gm)].map(([, nombre, valor]) => [
      nombre,
      valor,
    ]),
  );
  const exclusiones = new Set(
    [...tipos[1].matchAll(/CodigoMowaMes\.([A-Z0-9_]+)\s*:\s*TipoCodigo\.EXCLUSION/g)].map(([, nombre]) => nombre),
  );
  return [...valores].filter(([nombre]) => exclusiones.has(nombre)).map(([, valor]) => valor);
}

describe('filtro de exclusiones contra el catálogo del backend', () => {
  it('lista exactamente las exclusiones del catálogo, en su orden de evaluación', () => {
    const catalogo = exclusionesDelCatalogo();
    expect(catalogo.length).toBeGreaterThanOrEqual(6);
    expect([...CODIGOS_EXCLUSION]).toEqual(catalogo);
  });
});

describe('meses', () => {
  it('toma el mes de una fecha local', () => {
    expect(mesDe(new Date(2099, 0, 31))).toBe('2099-01');
    expect(mesDe(new Date(2099, 11, 1))).toBe('2099-12');
  });

  it('se mueve cruzando años en los dos sentidos', () => {
    expect(moverMes('2099-01', -1)).toBe('2098-12');
    expect(moverMes('2099-12', 1)).toBe('2100-01');
    expect(moverMes('2099-06', 0)).toBe('2099-06');
    expect(moverMes('2099-03', -15)).toBe('2097-12');
  });

  it('el uso del límite es la fracción cargada, y 0 con un límite no positivo', () => {
    expect(usoDelLimite({ cargados_mes: 625_000, limite: 2_500_000 })).toBe(0.25);
    expect(usoDelLimite({ cargados_mes: 2_600_000, limite: 2_500_000 })).toBeCloseTo(1.04);
    expect(usoDelLimite({ cargados_mes: 10, limite: 0 })).toBe(0);
  });
});

describe('resumen de la descarga', () => {
  it('lee las cabeceras X-Mowa-Mes-* como enteros', () => {
    expect(
      leerResumenDescarga({
        campana: '7',
        archivo: '2',
        'archivos-total': '3',
        filas: '45851',
        supervision: '0',
        bytes: '1530000',
      }),
    ).toEqual({ campana: 7, archivo: 2, total: 3, filas: 45851, supervision: 0, bytes: 1530000 });
  });

  it('una cabecera ausente o que no es un entero queda en null, sin adivinar', () => {
    expect(leerResumenDescarga({ filas: '12.5', supervision: '', bytes: '-1' })).toEqual({
      campana: null,
      archivo: null,
      total: null,
      filas: null,
      supervision: null,
      bytes: null,
    });
  });

  it('usa el nombre del servidor y, sin él, uno estable', () => {
    expect(nombreArchivo('CAMPANA_7_1.xlsx', 7, 1)).toBe('CAMPANA_7_1.xlsx');
    expect(nombreArchivo(null, 7, 2)).toBe('mowa_mes_campana_7_archivo_2.xlsx');
    expect(nombreArchivo('  ', 7, 2)).toBe('mowa_mes_campana_7_archivo_2.xlsx');
  });
});

describe('conciliación', () => {
  const cifras = (cargados: number, enviados: number) => ({
    cargados,
    enviados,
    no_enviados: cargados - enviados,
    por_estado: [],
  });
  const conciliacion: Conciliacion = {
    campana_id: 1,
    reportes: [],
    productos: cifras(980, 950),
    supervision: cifras(2, 2),
    total: cifras(982, 952),
    sin_correspondencia: 0,
    sin_correspondencia_por_estado: [],
    por_id: [],
    advertencias: [],
    tarifa_sms: '0.0200',
    costo_real: '19.0400',
    costo_real_estado: 'calculado',
  };

  it('productos, supervisión y total van siempre separados y en ese orden (RF-41)', () => {
    expect(filasConciliacion(conciliacion).map((f) => [f.grupo, f.cifras.enviados])).toEqual([
      ['productos', 950],
      ['supervision', 2],
      ['total', 952],
    ]);
  });

  it('ordena los estados por cantidad y desempata por nombre', () => {
    expect(
      ordenarEstados([
        { estado: 'rechazado', cantidad: 3 },
        { estado: 'enviado', cantidad: 40 },
        { estado: 'anulado', cantidad: 3 },
      ]).map((e) => e.estado),
    ).toEqual(['enviado', 'anulado', 'rechazado']);
  });
});

describe('paginación', () => {
  it('da el rango de la página en base 1', () => {
    expect(rangoPagina(0, 20, 25)).toEqual({ desde: 1, hasta: 20 });
    expect(rangoPagina(20, 5, 25)).toEqual({ desde: 21, hasta: 25 });
  });

  it('una página vacía no tiene rango', () => {
    expect(rangoPagina(0, 0, 0)).toBeNull();
    expect(rangoPagina(40, 0, 25)).toBeNull();
  });
});

describe('campanaDeLaUrl (el enlace de «Para subir a MES»)', () => {
  it('lee el id de ?campana=', () => {
    expect(campanaDeLaUrl('?campana=9')).toBe(9);
    expect(campanaDeLaUrl('campana=123')).toBe(123);
  });

  it('con otros parámetros, sigue encontrándolo', () => {
    expect(campanaDeLaUrl('?mes=2026-09&campana=7')).toBe(7);
  });

  it('sin el parámetro, o vacío, no hay campaña', () => {
    expect(campanaDeLaUrl('')).toBeNull();
    expect(campanaDeLaUrl('?mes=2026-09')).toBeNull();
    expect(campanaDeLaUrl('?campana=')).toBeNull();
  });

  it('un valor que no es un entero positivo no es una campaña', () => {
    for (const malo of ['abc', '0', '-3', '2.5', '1e3', ' 4', '4 ', '99999999999999999999', '0x10', '+5']) {
      expect(campanaDeLaUrl(`?campana=${encodeURIComponent(malo)}`), malo).toBeNull();
    }
  });
});

describe('la vista de las campañas en la URL (RF-MM-31)', () => {
  it('?vista=descartadas abre las descartadas; cualquier otra cosa, las activas', () => {
    expect(vistaDeLaUrl('?vista=descartadas')).toBe('descartadas');
    expect(vistaDeLaUrl('?mes=2026-09&vista=descartadas')).toBe('descartadas');
    for (const otra of ['', '?vista=activas', '?vista=', '?vista=Descartadas', '?vista=otra', '?campana=3']) {
      expect(vistaDeLaUrl(otra), otra).toBe('activas');
    }
  });

  it('elegir una vista conserva los demás parámetros', () => {
    expect(busquedaConVista('?campana=3', 'descartadas')).toBe('?campana=3&vista=descartadas');
    expect(busquedaConVista('?vista=descartadas&campana=3', 'activas')).toBe('?campana=3');
  });

  it('las activas son la vista por defecto: no escriben `vista`', () => {
    expect(busquedaConVista('', 'activas')).toBe('');
    expect(busquedaConVista('?vista=descartadas', 'activas')).toBe('');
    expect(busquedaConVista('', 'descartadas')).toBe('?vista=descartadas');
  });
});

describe('los meses de las descartadas (RF-MM-32)', () => {
  it('van del más reciente al más antiguo, sin repetirse', () => {
    expect(ordenarMeses(['2026-08', '2026-10', '2025-12', '2026-09', '2026-10'])).toEqual([
      '2026-10',
      '2026-09',
      '2026-08',
      '2025-12',
    ]);
  });

  it('el orden es el del calendario, no el del texto de otro formato', () => {
    expect(ordenarMeses(['2026-02', '2026-11', '2026-01'])).toEqual(['2026-11', '2026-02', '2026-01']);
  });

  it('lo que no es AAAA-MM no es un mes', () => {
    expect(ordenarMeses(['2026-13', '2026-00', '26-10', '2026-1', 'octubre', '', '2026-10'])).toEqual(['2026-10']);
  });

  it('se escriben con la inicial en mayúscula', () => {
    expect(etiquetaDelMes('2026-10')).toBe('Octubre de 2026');
    expect(etiquetaDelMes('2025-01')).toBe('Enero de 2025');
  });

  it('las opciones del select salen ordenadas y con su texto', () => {
    expect(opcionesDeMeses(['2026-08', '2026-10'])).toEqual([
      { valor: '2026-10', texto: 'Octubre de 2026' },
      { valor: '2026-08', texto: 'Agosto de 2026' },
    ]);
    expect(opcionesDeMeses([])).toEqual([]);
  });

  it('la vista abre en el más reciente, y conserva el elegido mientras tenga campañas', () => {
    expect(elegirMesDescartadas(['2026-08', '2026-10'], '')).toBe('2026-10');
    expect(elegirMesDescartadas(['2026-08', '2026-10'], '2026-08')).toBe('2026-08');
    // The chosen month lost its last campaign: it falls to the newest left.
    expect(elegirMesDescartadas(['2026-10'], '2026-08')).toBe('2026-10');
    expect(elegirMesDescartadas([], '2026-08')).toBe('');
  });

  it('el día del descarte se escribe como el resto del sitio', () => {
    expect(fechaDeDescarte('2026-10-30T12:00:00Z')).toBe(formatDate('2026-10-30'));
    expect(fechaDeDescarte('2026-10-30T12:00:00Z')).toContain('2026');
  });
});

describe('qué avisa descartar y qué muestra una descartada', () => {
  it('avisa del reporte solo cuando ya hay uno importado (pendiente_reporte === false)', () => {
    expect(advertirAlDescartar({ pendiente_reporte: false })).toBe(true);
    expect(advertirAlDescartar({ pendiente_reporte: true })).toBe(false);
  });

  it('el aviso de «pendiente del reporte» es de las activas: una descartada nunca lo muestra', () => {
    expect(pendienteVisible({ pendiente_reporte: true, descartada_en: null })).toBe(true);
    expect(pendienteVisible({ pendiente_reporte: false, descartada_en: null })).toBe(false);
    expect(pendienteVisible({ pendiente_reporte: true, descartada_en: '2026-10-30T10:00:00-05:00' })).toBe(false);
    expect(pendienteVisible({ pendiente_reporte: false, descartada_en: '2026-10-30T10:00:00-05:00' })).toBe(false);
  });
});
