/**
 * The notice of the archived additional fields the speech still reads (RF-65, T-MM-F12): in the campaign
 * preview and in the speech editor. A sheet loaded after a field is archived no longer brings it, so the
 * products that need it are left out; the texts must say that, with the readable names, and not be the engine's
 * notice (`avisoDeArchivados`, whose words are about Cartera and /columnas). Every name is synthetic.
 */
import { afterEach, describe, expect, it } from 'vitest';

import { avisoDeCamposArchivados } from '../../src/lib/mowa-mes-seguimiento';
import { setLanguageForTests } from './idioma';

const REGION = { nombre: 'ad_region', etiqueta: 'Región' };
const ZONA = { nombre: 'ad_zona', etiqueta: 'Zona' };

afterEach(() => setLanguageForTests('es'));

describe('sin campos archivados no hay aviso', () => {
  it('una lista vacía o ausente da null, en la campaña y en el editor', () => {
    for (const donde of ['campana', 'editor'] as const) {
      expect(avisoDeCamposArchivados([], donde)).toBeNull();
      expect(avisoDeCamposArchivados(undefined, donde)).toBeNull();
    }
  });
});

describe('el aviso de la campaña', () => {
  it('con uno, en singular y con su nombre legible', () => {
    expect(avisoDeCamposArchivados([REGION], 'campana')).toBe(
      'El speech usa el campo archivado «Región». Las sábanas cargadas después de archivarlo ya no lo traen, y los productos que lo necesitan quedan fuera. Para evitarlo, reactívalo en Cargas › Campos adicionales o quítalo del speech.',
    );
  });

  it('con varios, en plural y con todos los nombres', () => {
    expect(avisoDeCamposArchivados([REGION, ZONA], 'campana')).toBe(
      'El speech usa los campos archivados «Región», «Zona». Las sábanas cargadas después de archivarlos ya no los traen, y los productos que los necesitan quedan fuera. Para evitarlo, reactívalos en Cargas › Campos adicionales o quítalos del speech.',
    );
  });

  it('en inglés, con las comillas del inglés, en singular y en plural', () => {
    setLanguageForTests('en');
    expect(avisoDeCamposArchivados([REGION], 'campana')).toBe(
      'The speech uses the archived field “Región”. Sheets loaded after it was archived no longer bring it, and the products that need it are left out. To avoid this, reactivate it in Uploads › Additional fields or remove it from the speech.',
    );
    expect(avisoDeCamposArchivados([REGION, ZONA], 'campana')).toBe(
      'The speech uses the archived fields “Región”, “Zona”. Sheets loaded after they were archived no longer bring them, and the products that need them are left out. To avoid this, reactivate them in Uploads › Additional fields or remove them from the speech.',
    );
  });
});

describe('el aviso del editor', () => {
  it('con uno y con varios, con su propio texto: dice qué pasa en la campaña y cierra con la misma acción', () => {
    expect(avisoDeCamposArchivados([REGION], 'editor')).toBe(
      'El speech usa el campo archivado «Región». Las sábanas cargadas después de archivarlo ya no lo traen: en la campaña, los productos que lo necesitan quedan fuera. Para evitarlo, reactívalo en Cargas › Campos adicionales o quítalo del speech.',
    );
    expect(avisoDeCamposArchivados([REGION, ZONA], 'editor')).toBe(
      'El speech usa los campos archivados «Región», «Zona». Las sábanas cargadas después de archivarlos ya no los traen: en la campaña, los productos que los necesitan quedan fuera. Para evitarlo, reactívalos en Cargas › Campos adicionales o quítalos del speech.',
    );
  });

  it('en inglés, singular y plural', () => {
    setLanguageForTests('en');
    expect(avisoDeCamposArchivados([REGION], 'editor')).toBe(
      'The speech uses the archived field “Región”. Sheets loaded after it was archived no longer bring it: in the campaign, the products that need it are left out. To avoid this, reactivate it in Uploads › Additional fields or remove it from the speech.',
    );
    expect(avisoDeCamposArchivados([REGION, ZONA], 'editor')).toBe(
      'The speech uses the archived fields “Región”, “Zona”. Sheets loaded after they were archived no longer bring them: in the campaign, the products that need them are left out. To avoid this, reactivate them in Uploads › Additional fields or remove them from the speech.',
    );
  });
});

describe('lo que el aviso nunca dice', () => {
  it('ni el nombre técnico, ni las palabras del motor («sigue funcionando», «ahí sale vacío»), ni una clave cruda', () => {
    for (const donde of ['campana', 'editor'] as const) {
      for (const campos of [[REGION], [REGION, ZONA]]) {
        const texto = avisoDeCamposArchivados(campos, donde)!;
        expect(texto).not.toContain('ad_');
        expect(texto).not.toContain('sigue funcionando');
        expect(texto).not.toContain('ahí sale vacío');
        expect(texto).not.toContain('mowaMes.');
      }
    }
  });

  it('la campaña y el editor cierran con la misma acción, pero son textos distintos', () => {
    const campana = avisoDeCamposArchivados([REGION], 'campana')!;
    const editor = avisoDeCamposArchivados([REGION], 'editor')!;
    for (const texto of [campana, editor]) {
      expect(texto).toContain('Para evitarlo, reactívalo en Cargas › Campos adicionales o quítalo del speech.');
    }
    expect(editor).not.toBe(campana);
    // El del editor dice «en la campaña» porque todavía no está en ella.
    expect(editor).toContain('en la campaña, los productos que lo necesitan quedan fuera');
  });
});
