/**
 * Behaviour of the per-segment variants (docs/motor-texto-enriquecido-interfaz.md
 * §5.4, §9.1 and §9.2). The markup is `components/VariantesSegmento.astro`,
 * which holds a single `EditorTexto`: choosing a segment swaps the editor's
 * expression, never mounts a second editor.
 *
 * The rules — what each segment uses, copying, falling back to the default —
 * live in `lib/variantes.ts`. A module's own length levels (MOWA MES: Cabe,
 * Más de 150…) are not known here: the page computes them and hands them over
 * with `fijarNiveles`.
 */

import { validarTexto } from '../lib/api-texto-enriquecido';
import {
  estaVacia,
  expresionDeSegmento,
  fijarVariante,
  quitarVariante,
  resumirSegmentos,
  varianteDe,
} from '../lib/variantes';
import type { EstadoVariante, Segmento, Variante } from '../lib/variantes';
import { aExpresion, desdeExpresion, ubicarProblemas, type Expresion, type ProblemaUbicado } from '../lib/expresion';
import { t } from '../lib/i18n';
import { EVENTO_EXPRESION, montarEditor, type ControladorEditor, type EstadoEditor } from './editor-texto';

export const EVENTO_VARIANTES = 'variantescambiadas';

/** One of `.tag`'s tones (§9.1). */
export type Tono = 'vigente' | 'advertencia' | 'error' | 'neutral';
export type Niveles = Record<string, { tono: Tono; texto: string }>;

/** A problem with the segment it belongs to; `null` is the default content. */
export type ProblemaVariante = ProblemaUbicado & { segmento: string | null };

export interface EstadoVariantes {
  porDefecto: Expresion;
  variantes: Variante[];
  /** Segment on screen; `null` is the default content. */
  seleccionado: string | null;
  origen: 'usuario' | 'externo';
  pendiente: boolean;
  valida: boolean;
  problemas: ProblemaVariante[];
}

export interface OpcionesVariantes {
  contexto: string;
  segmentos: readonly Segmento[];
  /** The column's own expression: what a segment without a variant uses. */
  porDefecto?: Expresion | null;
  variantes?: readonly Variante[];
  /** Show «Por defecto» as one more entry, editable like a segment. */
  conPorDefecto?: boolean;
  /** Passed to the editor; the screen usually shows one summary for all (§9.4). */
  resumen?: 'propio' | 'ninguno';
  soloLectura?: boolean;
  /** Passed to the editor: a direct-variable column that varies by segment (§5.3). */
  soloVariable?: boolean;
  /**
   * Passed to the editor. `false` hides its sample control: the screen sets
   * the sample with `editor.fijarMuestra` (the column builder, §9.2 and §5.4).
   */
  controlMuestra?: boolean;
}

export interface ControladorVariantes {
  fijarVariantes(datos: { porDefecto?: Expresion | null; variantes: readonly Variante[] }): void;
  fijarNiveles(niveles: Niveles): void;
  /** Choose the segment, then open the problem's piece. `indice` counts that segment's problems. */
  irAProblema(segmento: string | null, indice: number): void;
  seleccionar(segmento: string | null): void;
  /** «Usar como base» (§5.1): editable or read-only without remounting. */
  fijarSoloLectura(soloLectura: boolean): void;
  /**
   * The criterion or its table of ranges changed. The chosen segment stays if
   * it still exists; otherwise the first one is chosen. Variants of segments
   * that are gone are kept untouched: the screen decides about them
   * (`variantesHuerfanas`).
   */
  fijarSegmentos(segmentos: readonly Segmento[]): void;
  estado(): EstadoVariantes;
  /** Unmount: the inner editor too, the pending validations and the listeners. */
  destruir(): void;
  editor: ControladorEditor;
}

const DEFECTO = '';
const clave = (segmento: string | null) => segmento ?? DEFECTO;
const vacia = (): Expresion => ({ nodos: [] });

interface Revision {
  problemas: ProblemaUbicado[];
  /** The backend's bound on the length, to flag an exceeded segment. */
  cota: number | null;
}

const TONO_ESTADO: Record<EstadoVariante, Tono> = {
  propia: 'vigente',
  por_defecto: 'neutral',
  vacia: 'advertencia',
  con_problema: 'error',
};

export async function montarVariantes(raiz: HTMLElement, opciones: OpcionesVariantes): Promise<ControladorVariantes> {
  const id = raiz.id;
  const q = <T extends Element>(selector: string) => raiz.querySelector<T>(selector)!;
  const el = {
    select: q<HTMLSelectElement>('[data-segmento-select]'),
    botones: q<HTMLElement>('[data-segmento-botones]'),
    estado: q<HTMLElement>('[data-estado]'),
    copiarSelect: q<HTMLSelectElement>('[data-copiar-select]'),
    copiar: q<HTMLButtonElement>('[data-copiar]'),
    usarDefecto: q<HTMLButtonElement>('[data-usar-defecto]'),
    anuncio: q<HTMLElement>('[data-anuncio]'),
    editor: q<HTMLElement>('[data-editor-texto]'),
    etiquetaEditor: q<HTMLElement>(`#${CSS.escape(`${id}-editor-etiqueta`)}`),
  };
  const conPorDefecto = Boolean(opciones.conPorDefecto);
  let segmentos: readonly Segmento[] = [...opciones.segmentos];
  let destruido = false;

  const s = {
    porDefecto: opciones.porDefecto ?? vacia(),
    variantes: [...(opciones.variantes ?? [])] as Variante[],
    seleccionado: (segmentos[0]?.clave ?? null) as string | null,
    origen: 'externo' as 'usuario' | 'externo',
    /** Last validation of each content, by segment key ('' is the default). */
    revisiones: new Map<string, Revision>(),
    /** The validations of the segments not on screen are running. */
    revisando: false,
    editorPendiente: true,
    editorValido: false,
    niveles: {} as Niveles,
    /** A problem to reach once the editor has validated the segment just chosen. */
    irDespues: null as number | null,
    soloLectura: Boolean(opciones.soloLectura),
    /** The context's length limit, as the editor reports it. */
    limite: null as number | null,
  };

  // ---- Names ------------------------------------------------------------------------------

  const etiquetaBase = () => {
    const claveEtiqueta = raiz.dataset.claveEtiqueta;
    const texto = claveEtiqueta ? t(claveEtiqueta) : '';
    return texto && texto !== claveEtiqueta ? texto : (raiz.dataset.etiqueta ?? '');
  };
  const nombreSegmento = (segmento: string | null): string =>
    segmento === null
      ? t('variantes.porDefecto')
      : (segmentos.find((x) => x.clave === segmento)?.etiqueta ?? segmento);

  // ---- What each segment shows -------------------------------------------------------------

  const problemasDeSegmento = (segmento: string | null): ProblemaVariante[] =>
    (s.revisiones.get(clave(segmento))?.problemas ?? []).map((p) => ({ ...p, segmento }));

  function todosLosProblemas(): ProblemaVariante[] {
    const claves: Array<string | null> = [
      ...(conPorDefecto ? [null] : []),
      ...segmentos.map((x) => x.clave),
    ];
    return claves.flatMap(problemasDeSegmento);
  }

  function resumen() {
    return resumirSegmentos(segmentos, s.porDefecto, s.variantes, todosLosProblemas());
  }

  function estadoDefecto(): EstadoVariante {
    if (problemasDeSegmento(null).length > 0) return 'con_problema';
    return estaVacia(s.porDefecto) ? 'vacia' : 'propia';
  }

  const excedido = (segmento: string | null) => {
    const cota = s.revisiones.get(clave(segmento))?.cota ?? null;
    return cota !== null && s.limite !== null && cota > s.limite;
  };

  function textoEstado(estado: EstadoVariante, segmento: string | null): string {
    if (segmento === null && estado === 'propia') return t('variantes.estado.conContenido');
    return t(`variantes.estado.${estado}`);
  }

  function tag(tono: Tono, texto: string): HTMLElement {
    const marca = document.createElement('span');
    marca.className = `tag tag--${tono}`;
    marca.textContent = texto;
    return marca;
  }

  function marcas(segmento: string | null, estado: EstadoVariante): HTMLElement[] {
    const lista = [tag(TONO_ESTADO[estado], textoEstado(estado, segmento))];
    const nivel = segmento === null ? undefined : s.niveles[segmento];
    if (nivel) lista.push(tag(nivel.tono, nivel.texto));
    else if (excedido(segmento)) lista.push(tag('error', t('variantes.estado.excedido')));
    return lista;
  }

  function entradas(): Array<{ segmento: string | null; etiqueta: string; estado: EstadoVariante }> {
    return [
      ...(conPorDefecto ? [{ segmento: null, etiqueta: nombreSegmento(null), estado: estadoDefecto() }] : []),
      ...resumen().map((r) => ({ segmento: r.clave as string | null, etiqueta: r.etiqueta, estado: r.estado })),
    ];
  }

  function pintarBoton(
    boton: HTMLButtonElement,
    { segmento, etiqueta, estado }: { segmento: string | null; etiqueta: string; estado: EstadoVariante },
  ): void {
    boton.setAttribute('aria-pressed', String(segmento === s.seleccionado));
    boton.querySelector<HTMLElement>('.variantes__nombre')!.textContent = etiqueta;
    boton.querySelector<HTMLElement>('.variantes__marcas')!.replaceChildren(...marcas(segmento, estado));
  }

  /**
   * Validations arrive one after another and each repaints the states. The
   * buttons are updated in place while the segments are the same, so a
   * keyboard user who is on one never loses it; when the segments change
   * (`fijarSegmentos`), the list is rebuilt and the focus goes back to the
   * same segment by its key, if it still exists.
   */
  function pintarLista(): void {
    const lista = entradas();
    const actuales = [...el.botones.querySelectorAll<HTMLButtonElement>('.variantes__boton')];
    const mismos =
      actuales.length === lista.length && actuales.every((b, i) => b.dataset.segmento === clave(lista[i].segmento));
    if (mismos) {
      actuales.forEach((boton, i) => pintarBoton(boton, lista[i]));
    } else {
      const activo = document.activeElement;
      const enfocado =
        activo instanceof HTMLElement && el.botones.contains(activo)
          ? activo.closest<HTMLElement>('.variantes__boton')?.dataset.segmento
          : undefined;
      el.botones.replaceChildren(
        ...lista.map((entrada) => {
          const item = document.createElement('li');
          const boton = document.createElement('button');
          boton.type = 'button';
          boton.className = 'variantes__boton';
          boton.dataset.segmento = clave(entrada.segmento);
          const nombre = document.createElement('span');
          nombre.className = 'variantes__nombre';
          const grupo = document.createElement('span');
          grupo.className = 'variantes__marcas';
          boton.append(nombre, grupo);
          boton.addEventListener('click', () => seleccionar(entrada.segmento));
          pintarBoton(boton, entrada);
          item.append(boton);
          return item;
        }),
      );
      if (enfocado !== undefined) {
        el.botones.querySelector<HTMLElement>(`[data-segmento="${CSS.escape(enfocado)}"]`)?.focus();
      }
    }

    el.select.replaceChildren(
      ...lista.map(({ segmento, etiqueta, estado }) => {
        const opcion = document.createElement('option');
        opcion.value = clave(segmento);
        opcion.textContent = `${etiqueta} — ${textoEstado(estado, segmento)}`;
        opcion.selected = segmento === s.seleccionado;
        return opcion;
      }),
    );

    el.copiarSelect.replaceChildren(
      ...lista
        .filter(({ segmento }) => segmento !== s.seleccionado)
        .map(({ segmento, etiqueta }) => {
          const opcion = document.createElement('option');
          opcion.value = clave(segmento);
          opcion.textContent = etiqueta;
          return opcion;
        }),
    );
    el.copiar.disabled = s.soloLectura || el.copiarSelect.options.length === 0;
    el.copiarSelect.disabled = s.soloLectura;

    const actual = lista.find((x) => x.segmento === s.seleccionado);
    el.estado.replaceChildren();
    if (actual) {
      el.estado.append(...marcas(actual.segmento, actual.estado));
      if (actual.estado === 'por_defecto') {
        const hint = document.createElement('span');
        hint.className = 'muted';
        hint.textContent = t('variantes.hint.porDefecto');
        el.estado.append(hint);
      }
    }
    el.usarDefecto.hidden =
      !conPorDefecto || s.seleccionado === null || !varianteDe(s.variantes, s.seleccionado) || s.soloLectura;
    el.etiquetaEditor.textContent =
      s.seleccionado === null
        ? t('variantes.etiqueta.porDefecto', { campo: etiquetaBase() })
        : t('variantes.etiqueta.segmento', { campo: etiquetaBase(), segmento: nombreSegmento(s.seleccionado) });
  }

  // ---- Event ------------------------------------------------------------------------------

  function estado(): EstadoVariantes {
    const problemas = todosLosProblemas();
    const pendiente = s.editorPendiente || s.revisando;
    return {
      porDefecto: s.porDefecto,
      variantes: s.variantes,
      seleccionado: s.seleccionado,
      origen: s.origen,
      pendiente,
      valida: !pendiente && s.editorValido && problemas.length === 0,
      problemas,
    };
  }

  function emitir(): void {
    if (destruido) return;
    raiz.dispatchEvent(new CustomEvent<EstadoVariantes>(EVENTO_VARIANTES, { bubbles: true, detail: estado() }));
  }

  // ---- Validating the segments not on screen ----------------------------------------------------

  let ronda = 0;
  let revision: AbortController | null = null;

  /**
   * Validate each content the editor is not showing, so every segment has a
   * state. A newer round cancels the one before; only the last one counts.
   */
  async function revisarTodas(): Promise<void> {
    revision?.abort();
    const propia = new AbortController();
    revision = propia;
    const mia = (ronda += 1);
    const claves: Array<string | null> = [
      ...(conPorDefecto ? [null] : []),
      ...s.variantes.map((v) => v.segmento),
    ].filter((segmento) => segmento !== s.seleccionado);
    s.revisando = true;
    await Promise.all(
      claves.map(async (segmento) => {
        const expresion = segmento === null ? s.porDefecto : varianteDe(s.variantes, segmento)?.expresion;
        if (!expresion) return;
        try {
          const respuesta = await validarTexto(opciones.contexto, expresion, propia.signal);
          // The analyst may have chosen this segment meanwhile: the editor's answer wins.
          if (propia.signal.aborted || segmento === s.seleccionado) return;
          s.revisiones.set(clave(segmento), {
            problemas: ubicarProblemas(respuesta.problemas, desdeExpresion(expresion)),
            cota: respuesta.cota,
          });
        } catch {
          // Unreachable: the segment keeps its last state; the editor says it when shown.
        }
      }),
    );
    if (destruido || mia !== ronda) return;
    s.revisando = false;
    pintarLista();
    emitir();
  }

  // ---- The editor -----------------------------------------------------------------------------

  el.editor.addEventListener(EVENTO_EXPRESION, (evento) => {
    const detalle = (evento as CustomEvent<EstadoEditor>).detail;
    evento.stopPropagation();
    s.editorPendiente = detalle.pendiente;
    s.editorValido = detalle.valida;
    if (detalle.origen === 'usuario') {
      s.origen = 'usuario';
      if (s.seleccionado === null) s.porDefecto = detalle.expresion;
      else s.variantes = fijarVariante(s.variantes, s.seleccionado, detalle.expresion);
    }
    if (!detalle.pendiente) {
      s.revisiones.set(clave(s.seleccionado), { problemas: detalle.problemas, cota: detalle.largo.maximo });
      s.limite = detalle.largo.limite;
      if (s.irDespues !== null) {
        const indice = s.irDespues;
        s.irDespues = null;
        editor.irAProblema(indice);
      }
    }
    pintarLista();
    emitir();
  });

  const editor = await montarEditor(el.editor, {
    contexto: opciones.contexto,
    expresion: s.seleccionado === null ? s.porDefecto : expresionDeSegmento(s.porDefecto, s.variantes, s.seleccionado),
    resumen: opciones.resumen ?? 'ninguno',
    soloLectura: s.soloLectura,
    soloVariable: opciones.soloVariable,
    controlMuestra: opciones.controlMuestra,
  });

  function seleccionar(segmento: string | null): void {
    if (segmento === s.seleccionado) return;
    s.seleccionado = segmento;
    s.editorPendiente = true;
    editor.fijarExpresion(
      segmento === null ? s.porDefecto : expresionDeSegmento(s.porDefecto, s.variantes, segmento),
    );
    pintarLista();
    el.anuncio.textContent = t('variantes.anuncio', { segmento: nombreSegmento(segmento) });
  }

  el.select.addEventListener('change', () => seleccionar(el.select.value === DEFECTO ? null : el.select.value));

  el.copiar.addEventListener('click', () => {
    const desde = el.copiarSelect.value === DEFECTO ? null : el.copiarSelect.value;
    const contenido = desde === null ? s.porDefecto : expresionDeSegmento(s.porDefecto, s.variantes, desde);
    const copia = aExpresion(desdeExpresion(contenido));
    if (s.seleccionado === null) s.porDefecto = copia;
    else s.variantes = fijarVariante(s.variantes, s.seleccionado, copia);
    s.origen = 'usuario';
    s.editorPendiente = true;
    editor.fijarExpresion(copia);
    pintarLista();
    el.anuncio.textContent = t('variantes.copiado', { desde: nombreSegmento(desde) });
    emitir();
  });

  el.usarDefecto.addEventListener('click', () => {
    if (s.seleccionado === null) return;
    s.variantes = quitarVariante(s.variantes, s.seleccionado);
    s.origen = 'usuario';
    s.editorPendiente = true;
    editor.fijarExpresion(s.porDefecto);
    pintarLista();
    el.usarDefecto.hidden = true;
    el.copiarSelect.focus();
    emitir();
  });

  const alCambiarIdioma = () => pintarLista();
  document.addEventListener('languagechange', alCambiarIdioma);

  pintarLista();
  void revisarTodas();

  return {
    fijarVariantes({ porDefecto, variantes }) {
      s.porDefecto = porDefecto ?? vacia();
      s.variantes = [...variantes];
      s.origen = 'externo';
      s.revisiones.clear();
      s.editorPendiente = true;
      editor.fijarExpresion(
        s.seleccionado === null ? s.porDefecto : expresionDeSegmento(s.porDefecto, s.variantes, s.seleccionado),
      );
      pintarLista();
      void revisarTodas();
    },
    fijarNiveles(niveles) {
      s.niveles = { ...niveles };
      pintarLista();
    },
    irAProblema(segmento, indice) {
      if (segmento === s.seleccionado && !s.editorPendiente) {
        editor.irAProblema(indice);
        return;
      }
      s.irDespues = indice;
      seleccionar(segmento);
    },
    seleccionar,
    fijarSoloLectura(soloLectura) {
      s.soloLectura = soloLectura;
      editor.fijarSoloLectura(soloLectura);
      pintarLista();
    },
    fijarSegmentos(nuevos) {
      segmentos = [...nuevos];
      const sigue =
        (s.seleccionado === null && conPorDefecto) || segmentos.some((x) => x.clave === s.seleccionado);
      for (const guardada of [...s.revisiones.keys()]) {
        if (guardada !== DEFECTO && !segmentos.some((x) => x.clave === guardada)) s.revisiones.delete(guardada);
      }
      if (sigue) {
        pintarLista();
        emitir();
      } else {
        // The chosen one is gone, so the first differs from it: seleccionar()
        // swaps the editor and repaints; its next event carries the state out.
        seleccionar(segmentos[0]?.clave ?? null);
      }
    },
    estado,
    destruir() {
      destruido = true;
      document.removeEventListener('languagechange', alCambiarIdioma);
      revision?.abort();
      editor.destruir();
    },
    editor,
  };
}
