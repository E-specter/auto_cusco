/**
 * Which fields a definition uses, by technical name: the variables of its columns and variants (and the
 * ones their functions refer to) and the field its segmentation counts by. Pure: it lets the preview say
 * that it still uses an archived field (RF-65).
 */

import type { Expresion } from './expresion';

/** What both a draft (/columnas) and a saved version (/generar-carga) have of a definition. */
interface ContenidoLeible {
  columnas: ReadonlyArray<{ expresion: Expresion; variantes: ReadonlyArray<{ expresion: Expresion }> }>;
  segmentacion: { criterio: { tipo: string; campo?: string } } | null;
}

function deExpresion(expresion: Expresion): string[] {
  return expresion.nodos.flatMap((nodo) =>
    nodo.tipo === 'variable'
      ? [
          nodo.nombre,
          ...nodo.funciones.flatMap((f) => f.args.flatMap((a) => (typeof a === 'object' ? [a.variable] : []))),
        ]
      : [],
  );
}

export function variablesEnUso(borrador: ContenidoLeible): string[] {
  const criterio = borrador.segmentacion?.criterio;
  return [
    ...borrador.columnas.flatMap((c) => [deExpresion(c.expresion), ...c.variantes.map((v) => deExpresion(v.expresion))].flat()),
    ...(criterio?.tipo === 'campo' && criterio.campo ? [criterio.campo] : []),
  ];
}
