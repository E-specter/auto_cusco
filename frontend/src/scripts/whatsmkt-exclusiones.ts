/**
 * The table of the products a campaign leaves out (Pagaré, Motivo and Detalle), stacking at 360 px: the one of the preview of the lot and the one of
 * the detail in the tracking draw the same thing, so it is drawn here once (docs/whatsmkt-interfaz.md §3.8 and §4.2).
 */

import { t, traducirPorPrefijo } from '../lib/i18n';
import { celda, tabla } from '../lib/tabla-dom';

export function tablaDeExclusiones(filas: ReadonlyArray<{ pagare: string | null; codigo: string; detalle: string }>): HTMLElement {
  const { envoltorio, cuerpo } = tabla(
    'wm-exclusiones',
    [
      [t('whatsmkt.previa.col.pagare'), false],
      [t('whatsmkt.previa.col.motivo'), false],
      [t('whatsmkt.previa.col.detalle'), false],
    ],
    { apilable: true },
  );
  filas.forEach((exclusion) => {
    const motivo = celda('td', '', '', t('whatsmkt.previa.col.motivo'));
    const marca = document.createElement('span');
    marca.className = 'tag tag--neutral';
    marca.textContent = traducirPorPrefijo('whatsmkt.codigo', exclusion.codigo, exclusion.detalle);
    motivo.append(marca);
    const fila = document.createElement('tr');
    fila.append(
      celda('td', exclusion.pagare ?? '—', 'mono', t('whatsmkt.previa.col.pagare')),
      motivo,
      celda('td', traducirPorPrefijo('whatsmkt.exclusiones', exclusion.codigo, exclusion.detalle), '', t('whatsmkt.previa.col.detalle')),
    );
    cuerpo.append(fila);
  });
  return envoltorio;
}
