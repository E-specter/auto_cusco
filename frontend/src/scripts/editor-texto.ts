/**
 * Behaviour of the rich-text editor (docs/motor-texto-enriquecido-interfaz.md
 * §2 to §4; mount contract §9.2). The markup is `components/EditorTexto.astro`.
 *
 * The page renders the component, listens for `expresioncambiada` on its root
 * and then calls `montarEditor`. The editor talks to the backend itself:
 * validation and preview 500 ms after the last change, cancelling the request
 * before. It never decides on its own whether the text is valid, how long it
 * can get or what a function returns — it shows what the backend answered.
 *
 * State lives in `lib/expresion.ts` (pieces) and `lib/editor-texto.ts`
 * (helpers); this file only paints it and wires the controls.
 */

import { ApiError } from '../lib/api';
import {
  obtenerCatalogo,
  previsualizarTexto,
  validarTexto,
  type CatalogoTexto,
  type MuestraTexto,
  type PrevisualizacionTexto,
  type ValidacionTexto,
} from '../lib/api-texto-enriquecido';
import { etiquetaVariable, humanizarNombre } from '../lib/campos';
import {
  aVariableDirecta,
  agruparPorOrigen,
  anclaDe,
  anchoDeTramo,
  argumentosIniciales,
  cambiarVariableDirecta,
  conArgumento,
  consultaDelBuscador,
  disparadorEn,
  errorDeParametro,
  esReferencia,
  leerArgumento,
  nivelDeLargo,
  nodoDePieza,
  piezaDeAncla,
  resumenFunciones,
  textoArgumento,
  tramoPegado,
  type Ancla,
  type NivelLargo,
} from '../lib/editor-texto';
import {
  aExpresion,
  agregarFuncion,
  catalogoDe,
  desdeExpresion,
  editarTramo,
  fijarArgumentos,
  funcionesCompatibles,
  insertarVariable,
  marcarObligatoria,
  moverFuncion,
  posicionTramo,
  quitarFuncion,
  quitarVariable,
  tipoEnPosicion,
  ubicarProblemas,
  type Argumento,
  type Expresion,
  type Pieza,
  type PiezaVariable,
  type Problema,
  type ProblemaUbicado,
} from '../lib/expresion';
import { t, traducirPorPrefijo } from '../lib/i18n';
import { crearSelectorPatronFecha } from './selector-patron-fecha';
import { crearBuscadorFunciones } from './selector-funcion';
import { crearBuscadorVariables, etiquetaTipo, type BuscadorVariables } from './selector-variable';
import type { components } from '../lib/contrato-api';

type Esquemas = components['schemas'];
type FuncionCatalogo = Esquemas['FuncionRespuesta'];
type ParametroCatalogo = Esquemas['ParametroRespuesta'];
type Columna = Esquemas['ColumnaRespuesta'];

export const EVENTO_EXPRESION = 'expresioncambiada';

/**
 * The variables that are the contact's WhatsApp link, in MOWA and in WhatsMKT: their pill carries the message-circle icon.
 * shortcut: los nombres de las variables de WhatsApp van fijos; pasar a un dato del catálogo si aparece un tercero.
 */
const VARIABLES_WHATSAPP = new Set(['whatsapp_contacto', 'whatsapp']);

/**
 * The variable search while it is open: where in which text run it will insert and what was typed to filter it. From `[@`
 * (`desdeBoton` false) `inicio` is where the trigger starts and the text run drives the search; from the button it is the
 * caret, and the search has a field of its own.
 */
type Disparo = { indice: number; inicio: number; desdeBoton: boolean; consulta: string; buscador: BuscadorVariables };

/** Same wait as the portfolio summary: long enough not to fire on every key. */
const ESPERA = 500;

export interface LargoTexto {
  /** Length of the sample's text; `null` until a preview arrives. */
  actual: number | null;
  /** The most the text can reach, when the backend could bound it. */
  maximo: number | null;
  /** The context's limit (160 for the MOWA MES speech); `null` without one. */
  limite: number | null;
  /** Why the backend could not bound it, when it could not. */
  sinCota: { codigo: string; detalle: string } | null;
}

export interface EstadoEditor {
  expresion: Expresion;
  /** 'externo' after `fijarExpresion`: not an unsaved change. */
  origen: 'usuario' | 'externo';
  /** A validation is scheduled or in flight. */
  pendiente: boolean;
  /** No problems in the last finished validation. */
  valida: boolean;
  /** Placed on the editor's pieces (`pieza: null` is the whole text). */
  problemas: ProblemaUbicado[];
  largo: LargoTexto;
}

export interface OpcionesEditor {
  /** The catalogue context: variables, functions, limit and threshold come from it. */
  contexto: string;
  /** Initial expression; `null` is an empty one. */
  expresion?: Expresion | null;
  /** `false`: the page sets the sample with `fijarMuestra` (the column builder). */
  controlMuestra?: boolean;
  /** `'ninguno'`: the screen shows one summary for every editor (§9.4). */
  resumen?: 'propio' | 'ninguno';
  /** An old version, opened to look at: nothing can change (§5.1). */
  soloLectura?: boolean;
  /**
   * A direct-variable column (§5.3): a select of variables instead of the line
   * of pieces, and the variable's panel of functions always open. An
   * expression with text is reduced to its first variable.
   */
  soloVariable?: boolean;
  /**
   * What the panel of a piece says where the context does not admit functions (`admite_funciones: false` in the catalogue):
   * the page's own words and, if it has one, a link to where they are made. The engine names no channel and brings no text.
   * Without it a context that does not admit functions just does not offer «Agregar función».
   */
  sinFunciones?: { texto: string; enlace?: { texto: string; href: string } };
  muestra?: MuestraTexto;
}

export interface ControladorEditor {
  /** Replace the expression, close panels and validate again. Not a user change. */
  fijarExpresion(expresion: Expresion | null): void;
  fijarMuestra(muestra: MuestraTexto): void;
  /** Open the problem's piece and focus its field. `indice` counts `estado().problemas`. */
  irAProblema(indice: number): void;
  /** The current tree, ready for the request. */
  expresion(): Expresion;
  estado(): EstadoEditor;
  /**
   * Before saving: `true` when the text may be saved. Otherwise the summary
   * turns into an alert and the focus goes to the first problem (with
   * `resumen: 'propio'`); with a validation still pending it just says no.
   */
  comprobarAntesDeGuardar(): boolean;
  fijarSoloLectura(soloLectura: boolean): void;
  /**
   * A note about the sample, already translated, shown right under the
   * preview it qualifies and said once to a screen reader («Ningún producto
   * de la muestra cae en…»). `null` removes it. The page owns the text: it
   * calls this again after a language change.
   */
  fijarNotaMuestra(texto: string | null): void;
  /**
   * Unmount: removes the document listeners, cancels the scheduled and the
   * in-flight requests and stops emitting. The markup stays; the page removes
   * it. Call it before taking the component out of the page.
   */
  destruir(): void;
}

interface ProblemaAnclado {
  problema: Problema;
  ancla: Ancla;
}

interface Vista {
  columna: Columna;
  excluida: Esquemas['ExclusionFilaRespuesta'] | null;
  /** Variable piece id → node index, as of the request that produced it. */
  nodos: Map<string, number>;
}

const ejemplo = (): MuestraTexto => ({ tipo: 'ejemplo', cantidad: 1 });

/** A problem's message: the code's text, or the backend's detail for a code we lack. */
export function mensajeProblema(problema: Pick<Problema, 'codigo' | 'detalle'>): string {
  return traducirPorPrefijo('textoEnriquecido.codigo', problema.codigo, problema.detalle);
}

function nombreTraducido(clave: string, respaldo: string): string {
  const texto = t(clave);
  return texto === clave ? humanizarNombre(respaldo) : texto;
}

export async function montarEditor(raiz: HTMLElement, opciones: OpcionesEditor): Promise<ControladorEditor> {
  const id = raiz.id;
  const q = <T extends Element>(selector: string) => raiz.querySelector<T>(selector)!;
  const el = {
    resumen: q<HTMLElement>('[data-resumen]'),
    resumenTitulo: q<HTMLElement>('[data-resumen-titulo]'),
    resumenLista: q<HTMLElement>('[data-resumen-lista]'),
    linea: q<HTMLElement>('[data-linea]'),
    errorTramo: q<HTMLElement>('[data-error-tramo]'),
    agregar: q<HTMLButtonElement>('[data-agregar-variable]'),
    pista: q<HTMLElement>('[data-pista-disparador]'),
    disparadorAnuncio: q<HTMLElement>('[data-disparador-anuncio]'),
    selectorHueco: q<HTMLElement>('[data-selector-hueco]'),
    panelHueco: q<HTMLElement>('[data-panel-hueco]'),
    controlMuestra: q<HTMLElement>('[data-control-muestra]'),
    botonesMuestra: [...raiz.querySelectorAll<HTMLButtonElement>('[data-muestra]')],
    producto: q<HTMLElement>('[data-producto]'),
    fecha: q<HTMLInputElement>('[data-muestra-fecha]'),
    pagare: q<HTMLInputElement>('[data-muestra-pagare]'),
    errorMuestra: q<HTMLElement>('[data-muestra-error]'),
    resultado: q<HTMLElement>('[data-resultado]'),
    largoTexto: q<HTMLElement>('[data-largo-texto]'),
    largoNivel: q<HTMLElement>('[data-largo-nivel]'),
    largoAnuncio: q<HTMLElement>('[data-largo-anuncio]'),
    notaMuestra: q<HTMLElement>('[data-nota-muestra]'),
    notaAnuncio: q<HTMLElement>('[data-nota-anuncio]'),
    sinConexion: q<HTMLElement>('[data-sin-conexion]'),
    problemasFila: q<HTMLElement>('[data-problemas-fila]'),
    directa: q<HTMLElement>('[data-directa]'),
    directaSelect: q<HTMLSelectElement>('[data-directa-select]'),
    barra: q<HTMLElement>('[data-barra]'),
  };
  const soloVariable = Boolean(opciones.soloVariable);
  /** After `destruir()`: no request, no event, no repaint from outside. */
  let destruido = false;

  const icono = (nombre: string): Node =>
    q<HTMLTemplateElement>(`template[data-icono="${nombre}"]`).content.firstElementChild!.cloneNode(true);

  let catalogo: CatalogoTexto;
  try {
    catalogo = await obtenerCatalogo(opciones.contexto);
  } catch (error) {
    el.linea.replaceChildren();
    const aviso = document.createElement('p');
    aviso.className = 'muted';
    aviso.textContent = t('editorTexto.sinCatalogo');
    el.linea.append(aviso);
    throw error;
  }
  const tipos = catalogoDe(catalogo);
  /** `false` in the catalogue of a context that takes no functions (the message of a channel): nothing to add to a piece. */
  const admiteFunciones = catalogo.contexto.admite_funciones;

  const piezasDe = (expresion: Expresion | null | undefined): Pieza[] =>
    desdeExpresion(soloVariable ? aVariableDirecta(expresion) : expresion);

  const s = {
    piezas: piezasDe(opciones.expresion),
    /** Id of the variable whose panel is open. */
    abierta: null as string | null,
    /** The variable search, open from `[@` or from the button; `null` when closed. */
    disparo: null as Disparo | null,
    /** Last text run with focus and its caret: where «Insertar variable» opens the search. */
    ultimoTramo: null as { indice: number; cursor: number } | null,
    /** Piece whose part of the result is highlighted (hover or focus). */
    resaltada: null as string | null,
    problemas: [] as ProblemaAnclado[],
    origen: 'externo' as 'usuario' | 'externo',
    programado: false,
    enCurso: false,
    validada: false,
    valida: false,
    sinConexion: false,
    cota: null as number | null,
    sinCota: null as ValidacionTexto['sin_cota'],
    vista: null as Vista | null,
    muestra: opciones.muestra ?? ejemplo(),
    soloLectura: Boolean(opciones.soloLectura),
    /** The summary speaks up only after a refused save, until the next edit. */
    alertar: false,
    nivelAnunciado: null as NivelLargo | null,
    /** What the sample's hints said last, so a repaint that changes nothing does not make a screen reader say it again. */
    pistas: '',
  };

  const resumenPropio = (opciones.resumen ?? 'propio') === 'propio';

  // ---- Reading the catalogue -------------------------------------------------------------

  const variableDe = (nombre: string) => catalogo.contexto.variables.find((v) => v.nombre === nombre);
  const funcionDe = (nombre: string): FuncionCatalogo | undefined =>
    catalogo.funciones.find((f) => f.nombre === nombre);
  const nombreVariable = (nombre: string): string => {
    const variable = variableDe(nombre);
    return variable ? etiquetaVariable(variable) : humanizarNombre(nombre);
  };
  const nombreFuncion = (nombre: string): string => {
    const funcion = funcionDe(nombre);
    return funcion ? nombreTraducido(funcion.clave_nombre, nombre) : humanizarNombre(nombre);
  };
  const nombreParametro = (parametro: ParametroCatalogo): string =>
    nombreTraducido(parametro.clave_nombre, parametro.nombre);

  const indiceDe = (idPieza: string): number =>
    s.piezas.findIndex((p) => p.tipo === 'variable' && p.id === idPieza);
  const piezaAbierta = (): PiezaVariable | null => {
    const pieza = s.abierta === null ? undefined : s.piezas[indiceDe(s.abierta)];
    return pieza?.tipo === 'variable' ? pieza : null;
  };

  // ---- Problems --------------------------------------------------------------------------

  function problemasActuales(): ProblemaUbicado[] {
    return s.problemas.map(({ problema, ancla }) => ({ ...problema, pieza: piezaDeAncla(s.piezas, ancla) }));
  }

  const problemasDePieza = (indice: number) => problemasActuales().filter((p) => p.pieza === indice);

  /** A problem's message; a refused parameter says the range the catalogue gives (interface rules §13.4). */
  function mensajeDe(problema: ProblemaUbicado): string {
    const fi = problema.ubicacion?.funcion;
    const nombre = problema.ubicacion?.parametro;
    const pieza = problema.pieza === null ? undefined : s.piezas[problema.pieza];
    if (problema.codigo === 'parametro_invalido' && pieza?.tipo === 'variable' && fi !== null && fi !== undefined && nombre) {
      const llamada = pieza.funciones[fi];
      const funcion = llamada ? funcionDe(llamada.nombre) : undefined;
      const indice = funcion?.parametros.findIndex((p) => p.nombre === nombre) ?? -1;
      const parametro = funcion?.parametros[indice];
      const error = parametro ? errorDeParametro(parametro, llamada.args[indice]) : null;
      if (parametro && error) return t(error.clave, { ...error.valores, parametro: nombreParametro(parametro) });
    }
    return mensajeProblema(problema);
  }

  function nombreTramo(indice: number): string {
    const posicion = posicionTramo(s.piezas, indice);
    return t(`editorTexto.tramo.${posicion.caso}`, {
      variable: posicion.variable ? nombreVariable(posicion.variable) : '',
    });
  }

  /** Where a problem is, in words, for the summary («Titular · Primeros caracteres»). */
  function lugarProblema(problema: ProblemaUbicado): string {
    if (problema.pieza === null) return t('editorTexto.problema.todo');
    const pieza = s.piezas[problema.pieza];
    if (!pieza) return t('editorTexto.problema.todo');
    if (pieza.tipo === 'texto') return nombreTramo(problema.pieza);
    const partes = [nombreVariable(pieza.nombre)];
    const indiceFuncion = problema.ubicacion?.funcion;
    const llamada = indiceFuncion === null || indiceFuncion === undefined ? undefined : pieza.funciones[indiceFuncion];
    if (llamada) {
      partes.push(nombreFuncion(llamada.nombre));
      const parametro = funcionDe(llamada.nombre)?.parametros.find((p) => p.nombre === problema.ubicacion?.parametro);
      if (parametro) partes.push(nombreParametro(parametro));
    }
    return partes.join(' · ');
  }

  // ---- Event -----------------------------------------------------------------------------

  const pendiente = () => s.programado || s.enCurso;

  function largo(): LargoTexto {
    return {
      actual: s.vista?.columna.largo ?? null,
      maximo: s.cota,
      limite: catalogo.contexto.limite_largo,
      sinCota: s.sinCota ? { codigo: s.sinCota.codigo, detalle: s.sinCota.detalle } : null,
    };
  }

  function estado(): EstadoEditor {
    return {
      expresion: aExpresion(s.piezas),
      origen: s.origen,
      pendiente: pendiente(),
      valida: s.validada && s.valida,
      problemas: problemasActuales(),
      largo: largo(),
    };
  }

  function emitir(): void {
    if (destruido) return;
    raiz.dispatchEvent(new CustomEvent<EstadoEditor>(EVENTO_EXPRESION, { bubbles: true, detail: estado() }));
  }

  // ---- Validation and preview ------------------------------------------------------------

  let temporizador: ReturnType<typeof setTimeout> | undefined;
  let controlador: AbortController | null = null;

  function programar(): void {
    if (destruido) return;
    s.programado = true;
    el.resultado.classList.add('editor-texto__resultado--pendiente');
    clearTimeout(temporizador);
    temporizador = setTimeout(() => void comprobar(), ESPERA);
  }

  function peticionMuestra(): MuestraTexto | null {
    if (s.muestra.tipo !== 'producto_real') return s.muestra;
    // A real product needs both fields; until then the last preview stays.
    return s.muestra.fecha_corte && s.muestra.pagare ? s.muestra : null;
  }

  async function comprobar(): Promise<void> {
    s.programado = false;
    s.enCurso = true;
    controlador?.abort();
    const propio = new AbortController();
    controlador = propio;

    const enviadas = s.piezas;
    const expresion = aExpresion(enviadas);
    const muestra = peticionMuestra();

    const [validacion, vista] = await Promise.allSettled([
      validarTexto(opciones.contexto, expresion, propio.signal),
      muestra
        ? previsualizarTexto({ contexto: opciones.contexto, expresion, muestra }, propio.signal)
        : Promise.resolve(null),
    ]);
    if (propio.signal.aborted || destruido) return;
    s.enCurso = false;

    if (validacion.status === 'fulfilled') {
      s.problemas = ubicarProblemas(validacion.value.problemas, enviadas).map((problema) => ({
        problema,
        ancla: anclaDe(enviadas, problema.pieza),
      }));
      s.validada = true;
      s.valida = validacion.value.problemas.length === 0;
      s.cota = validacion.value.cota;
      s.sinCota = validacion.value.sin_cota;
      s.sinConexion = false;
    } else {
      // Unreachable or refused: nothing may be saved on a guess.
      s.valida = false;
      s.sinConexion = true;
    }

    if (vista.status === 'fulfilled') {
      el.errorMuestra.textContent = '';
      el.pagare.removeAttribute('aria-invalid');
      if (vista.value) recibirVista(vista.value, enviadas);
    } else if (vista.reason instanceof ApiError && vista.reason.codigo) {
      // An unknown pagaré or date is said under its field; the last preview stays.
      el.errorMuestra.textContent = mensajeProblema({ codigo: vista.reason.codigo, detalle: vista.reason.detail });
      el.pagare.setAttribute('aria-invalid', 'true');
    }

    if (!s.programado) el.resultado.classList.remove('editor-texto__resultado--pendiente');
    pintarProblemas();
    pintarVista();
    emitir();
  }

  function recibirVista(respuesta: PrevisualizacionTexto, enviadas: Pieza[]): void {
    const fila = respuesta.filas[0];
    const columna = fila?.columnas[0];
    if (!fila || !columna) return;
    s.vista = { columna, excluida: fila.excluida, nodos: nodoDePieza(enviadas) };
  }

  /** After any change by the analyst. */
  function cambio(): void {
    s.origen = 'usuario';
    s.alertar = false;
    programar();
    pintarResumen();
    emitir();
  }

  // ---- Line of pieces ------------------------------------------------------------------------

  const soportaAjuste = typeof CSS !== 'undefined' && CSS.supports('field-sizing', 'content');

  /** Browsers without `field-sizing` (Firefox): size the run to its text. */
  function ajustar(area: HTMLTextAreaElement): void {
    if (soportaAjuste) return;
    area.style.inlineSize = `${anchoDeTramo(area.value)}ch`;
    area.style.blockSize = 'auto';
    area.style.blockSize = `${area.scrollHeight}px`;
  }

  function etiquetaPieza(pieza: PiezaVariable, conProblema: boolean): { visible: string; titulo: string; accesible: string } {
    const variable = nombreVariable(pieza.nombre);
    const resumen = resumenFunciones(pieza.funciones, nombreFuncion, nombreVariable);
    // The whole chain goes in the tooltip and in the accessible name; the pill itself reads short (interface rules §13.5).
    const titulo = resumen ? `${variable} · ${resumen}` : variable;
    const visible =
      pieza.funciones.length === 0
        ? variable
        : pieza.funciones.length === 1
          ? `${variable} · ${nombreFuncion(pieza.funciones[0].nombre).toLowerCase()}`
          : t('editorTexto.pildora.funciones', { variable, n: pieza.funciones.length });
    const accesible = [
      t('editorTexto.pieza.variable', { variable }),
      resumen ? `, ${resumen}` : '',
      variableDe(pieza.nombre)?.archivado ? `, ${t('camposAdicionales.archivado')}` : '',
      conProblema ? t('editorTexto.pieza.conProblema') : '',
      '. ',
      t('editorTexto.pieza.abre'),
    ].join('');
    return { visible, titulo, accesible };
  }

  function crearTramo(indice: number, valor: string): HTMLTextAreaElement {
    const area = document.createElement('textarea');
    area.className = 'editor-texto__tramo';
    area.rows = 1;
    area.value = valor;
    area.dataset.tramo = String(indice);
    area.readOnly = s.soloLectura;
    area.setAttribute('aria-label', nombreTramo(indice));

    const recordar = () => {
      s.ultimoTramo = { indice, cursor: area.selectionStart ?? area.value.length };
    };
    const alMoverElCursor = () => {
      recordar();
      revisarBuscador(area, indice, false);
    };
    area.addEventListener('focus', recordar);
    area.addEventListener('keyup', alMoverElCursor);
    area.addEventListener('pointerup', alMoverElCursor);
    area.addEventListener('select', alMoverElCursor);
    area.addEventListener('blur', () => {
      if (disparoDelTramo(indice)) cerrarBuscador();
    });
    area.addEventListener('input', () => {
      s.piezas = editarTramo(s.piezas, indice, area.value);
      recordar();
      ajustar(area);
      area.closest('.editor-texto__par')?.classList.toggle('editor-texto__par--junto', tramoPegado(area.value));
      revisarBuscador(area, indice, true);
      cambio();
    });
    area.addEventListener('keydown', (evento) => {
      const disparo = disparoDelTramo(indice);
      if (disparo && teclaDelBuscador(evento, area, disparo)) return;
      const alInicio = area.selectionStart === 0 && area.selectionEnd === 0;
      const alFinal = area.selectionStart === area.value.length && area.selectionEnd === area.value.length;
      if (evento.key === 'Backspace' && alInicio && indice > 0) {
        evento.preventDefault();
        enfocarPieza(indice - 1);
      } else if (evento.key === 'Delete' && alFinal && indice < s.piezas.length - 1) {
        evento.preventDefault();
        enfocarPieza(indice + 1);
      }
    });
    return area;
  }

  function crearPildora(indice: number, pieza: PiezaVariable): HTMLButtonElement {
    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'editor-texto__pieza';
    boton.dataset.pieza = pieza.id;
    boton.setAttribute('aria-controls', `${id}-panel`);
    boton.setAttribute('aria-expanded', String(s.abierta === pieza.id));
    const texto = document.createElement('span');
    texto.className = 'editor-texto__piezaTexto';
    boton.append(texto);
    pintarPildora(boton, pieza, problemasDePieza(indice).length > 0);

    boton.addEventListener('click', () => alternarPanel(pieza.id));
    boton.addEventListener('keydown', (evento) => {
      if ((evento.key === 'Delete' || evento.key === 'Backspace') && !s.soloLectura) {
        evento.preventDefault();
        quitar(pieza.id);
      }
    });
    boton.addEventListener('focus', () => resaltar(pieza.id));
    boton.addEventListener('blur', () => resaltar(null));
    boton.addEventListener('pointerenter', () => resaltar(pieza.id));
    boton.addEventListener('pointerleave', () => resaltar(null));
    return boton;
  }

  function pintarPildora(boton: HTMLButtonElement, pieza: PiezaVariable, conProblema: boolean): void {
    const { visible, titulo, accesible } = etiquetaPieza(pieza, conProblema);
    const texto = boton.querySelector<HTMLElement>('.editor-texto__piezaTexto')!;
    texto.textContent = visible;
    if (variableDe(pieza.nombre)?.archivado) {
      const marca = document.createElement('span');
      marca.className = 'tag tag--advertencia editor-texto__archivado';
      marca.textContent = t('camposAdicionales.archivado');
      texto.append(' ', marca);
    }
    boton.setAttribute('aria-label', accesible);
    boton.title = titulo;
    boton.classList.toggle('editor-texto__pieza--problema', conProblema);
    boton.querySelector('svg')?.remove();
    // The problem's icon wins; the contact WhatsApp is the one pill that carries its own (message-circle).
    if (conProblema) boton.prepend(icono('triangle-alert'));
    else if (VARIABLES_WHATSAPP.has(pieza.nombre)) boton.prepend(icono('message-circle'));
  }

  function pintarLinea(): void {
    // A pill and the run after it go in a pair: while the run is short (empty, or one sign) the pair stays together on a row;
    // otherwise the pair dissolves (`display: contents`) and pill and run flow as items of the line.
    const hijos: HTMLElement[] = [];
    let pildora: HTMLButtonElement | null = null;
    s.piezas.forEach((pieza, indice) => {
      if (pieza.tipo === 'variable') {
        pildora = crearPildora(indice, pieza);
        return;
      }
      const tramo = crearTramo(indice, pieza.valor);
      if (pildora) {
        const par = document.createElement('span');
        par.className = 'editor-texto__par';
        par.classList.toggle('editor-texto__par--junto', tramoPegado(pieza.valor));
        par.append(pildora, tramo);
        hijos.push(par);
        pildora = null;
      } else {
        hijos.push(tramo);
      }
    });
    el.linea.replaceChildren(...hijos);
    el.linea.querySelectorAll('textarea').forEach(ajustar);
    pintarProblemasLinea();
  }

  function enfocarPieza(indice: number): void {
    el.linea.querySelector<HTMLElement>(`[data-pieza="${(s.piezas[indice] as PiezaVariable).id}"]`)?.focus();
  }

  function enfocarTramo(indice: number, cursor: number): void {
    const area = el.linea.querySelector<HTMLTextAreaElement>(`[data-tramo="${indice}"]`);
    if (!area) return;
    area.focus();
    area.setSelectionRange(cursor, cursor);
    s.ultimoTramo = { indice, cursor };
  }

  // ---- Inserting and removing variables ------------------------------------------------------

  const areaDe = (indice: number) => el.linea.querySelector<HTMLTextAreaElement>(`[data-tramo="${indice}"]`);

  function anunciarBuscador(texto: string): void {
    el.disparadorAnuncio.textContent = texto;
  }

  /** What the context does not offer, in words, or `undefined` when it offers everything or the text is not translated. */
  function textoDeAlcance(): string | undefined {
    const clave = catalogo.contexto.clave_alcance;
    const texto = clave ? t(clave) : '';
    return texto && texto !== clave ? texto : undefined;
  }

  /** Where, from the viewport's left edge, the character `indice` of a text run starts (a mirror of the run measures it). */
  function xDelCaracter(area: HTMLTextAreaElement, indice: number): number {
    const espejo = document.createElement('div');
    const estilo = getComputedStyle(area);
    Object.assign(espejo.style, {
      position: 'absolute',
      visibility: 'hidden',
      whiteSpace: 'pre-wrap',
      overflowWrap: 'break-word',
      width: `${area.offsetWidth + 4}px`,
      font: estilo.font,
      letterSpacing: estilo.letterSpacing,
      padding: estilo.padding,
      border: estilo.border,
      boxSizing: estilo.boxSizing,
    });
    espejo.textContent = area.value.slice(0, indice);
    const marca = document.createElement('span');
    marca.textContent = '\u200b';
    espejo.append(marca);
    document.body.append(espejo);
    const x = area.getBoundingClientRect().left + marca.offsetLeft - area.scrollLeft;
    espejo.remove();
    return x;
  }

  /**
   * Puts the search under the line, at the caret's column, as wide as a search needs (interface rules §13.2); where the line is
   * about as narrow as the search (a phone) it keeps the whole width of the line. The search opened from the button has no
   * caret to follow and stays at the left.
   */
  function alinearAlCursor(panel: HTMLElement, area: HTMLTextAreaElement, desde: number): void {
    const ANCHO = 448;
    const linea = el.linea.getBoundingClientRect();
    if (linea.width <= ANCHO + 32) return;
    const sangria = Math.max(0, Math.min(xDelCaracter(area, desde) - linea.left, linea.width - ANCHO));
    panel.style.inlineSize = `${ANCHO}px`;
    panel.style.marginInlineStart = `${sangria}px`;
  }

  /** The search a text run drives, if it is the run `indice` (the button's search has a field of its own). */
  const disparoDelTramo = (indice: number): Disparo | null =>
    s.disparo && !s.disparo.desdeBoton && s.disparo.indice === indice ? s.disparo : null;

  /**
   * Opens the search that will insert at `inicio` of a text run (interface rules §13.2). From `[@` the focus stays in the run,
   * which becomes a combobox over the list until the search closes. From the button the search brings its own field,
   * which takes the focus and is the combobox; Escape closes it and gives the focus back to the button.
   */
  function abrirBuscador(indice: number, inicio: number, desdeBoton: boolean, aviso = ''): void {
    const area = areaDe(indice);
    if (!area || s.soloLectura) return;
    cerrarBuscador();
    const buscador = crearBuscadorVariables({
      id: `${id}-variable`,
      variables: catalogo.contexto.variables.filter((v) => !v.archivado),
      ejemplo: catalogo.contexto.ejemplo,
      alcance: textoDeAlcance(),
      onElegir: insertar,
      conCampo: desdeBoton,
      onCerrar: (porEscape) => {
        cerrarBuscador();
        if (porEscape) el.agregar.focus();
      },
    });
    s.disparo = { indice, inicio, desdeBoton, consulta: '', buscador };
    if (!desdeBoton) {
      area.setAttribute('role', 'combobox');
      area.setAttribute('aria-expanded', 'true');
      area.setAttribute('aria-controls', buscador.listaId);
      area.setAttribute('aria-autocomplete', 'list');
      apuntarActiva(area, s.disparo);
    }
    el.agregar.setAttribute('aria-expanded', 'true');
    el.selectorHueco.replaceChildren(buscador.raiz);
    if (!desdeBoton) alinearAlCursor(buscador.raiz, area, inicio);
    buscador.campo?.focus();
    anunciarBuscador([t('editorTexto.disparador.abierto'), aviso].filter(Boolean).join(' '));
  }

  function cerrarBuscador(): void {
    const disparo = s.disparo;
    if (!disparo) return;
    s.disparo = null;
    const area = areaDe(disparo.indice);
    for (const atributo of ['role', 'aria-expanded', 'aria-controls', 'aria-autocomplete', 'aria-activedescendant']) {
      area?.removeAttribute(atributo);
    }
    el.agregar.setAttribute('aria-expanded', 'false');
    el.selectorHueco.replaceChildren();
  }

  function apuntarActiva(area: HTMLTextAreaElement, disparo: Disparo): void {
    const activa = disparo.buscador.idActiva();
    if (activa) area.setAttribute('aria-activedescendant', activa);
    else area.removeAttribute('aria-activedescendant');
  }

  /** After the caret or the text of a run changed: filter, close, or (only when typing) open the search. */
  function revisarBuscador(area: HTMLTextAreaElement, indice: number, tecleando: boolean): void {
    const cursor = area.selectionStart ?? area.value.length;
    const disparo = disparoDelTramo(indice);
    if (disparo) {
      const consulta = consultaDelBuscador(area.value, disparo.inicio, cursor);
      if (consulta !== null) {
        if (consulta !== disparo.consulta) {
          disparo.consulta = consulta;
          disparo.buscador.filtrar(consulta);
          apuntarActiva(area, disparo);
        }
        return;
      }
      cerrarBuscador();
    }
    const inicio = tecleando ? disparadorEn(area.value, cursor) : null;
    if (inicio !== null) abrirBuscador(indice, inicio, false);
  }

  /** The keys of the open search; `true` when it took the key. Enter and Tab insert, Escape leaves the text as typed. */
  function teclaDelBuscador(evento: KeyboardEvent, area: HTMLTextAreaElement, disparo: Disparo): boolean {
    if (evento.isComposing) return false;
    if (evento.key === 'ArrowDown' || evento.key === 'ArrowUp') {
      evento.preventDefault();
      disparo.buscador.mover(evento.key === 'ArrowDown' ? 1 : -1);
      apuntarActiva(area, disparo);
      return true;
    }
    if (evento.key === 'Escape') {
      evento.preventDefault();
      evento.stopPropagation();
      cerrarBuscador();
      return true;
    }
    if (evento.key === 'Enter' || (evento.key === 'Tab' && !evento.shiftKey)) {
      const nombre = disparo.buscador.activa();
      // With no match Enter does nothing, and Tab moves on (leaving the run closes the search).
      if (nombre === null && evento.key === 'Tab') return false;
      evento.preventDefault();
      if (nombre !== null) insertar(nombre);
      return true;
    }
    return false;
  }

  /** «Insertar variable»: the search with its own field, to insert at the last caret or, if there was none, at the end of the text. */
  function abrirDesdeElBoton(): void {
    const ultimo = s.ultimoTramo;
    const hayTramo = ultimo !== null && s.piezas[ultimo.indice]?.tipo === 'texto';
    const indice = hayTramo ? ultimo.indice : s.piezas.length - 1;
    const area = areaDe(indice);
    if (!area) return;
    const cursor = hayTramo ? Math.min(ultimo.cursor, area.value.length) : area.value.length;
    abrirBuscador(indice, cursor, true, hayTramo ? '' : t('editorTexto.disparador.alFinal'));
  }

  /**
   * Puts the variable where the search opened, in place of what was typed to find it. From `[@` the caret ends after the
   * piece, so the analyst keeps typing; from the button the piece opens its panel (§2.2), to add functions.
   */
  function insertar(nombre: string): void {
    const disparo = s.disparo;
    if (!disparo) return;
    const area = areaDe(disparo.indice);
    const tecleando = !disparo.desdeBoton;
    const conPanel = !tecleando && admiteFunciones;
    // From `[@` what was typed to find the variable goes away with the trigger; from the button nothing was typed in the text.
    if (tecleando && area) {
      const fin = area.selectionStart ?? area.value.length;
      s.piezas = editarTramo(s.piezas, disparo.indice, area.value.slice(0, disparo.inicio) + area.value.slice(fin));
    }
    const { piezas, indiceVariable } = insertarVariable(s.piezas, disparo.indice, disparo.inicio, nombre);
    s.piezas = piezas;
    s.ultimoTramo = { indice: indiceVariable + 1, cursor: 0 };
    if (conPanel) s.abierta = (piezas[indiceVariable] as PiezaVariable).id;
    cerrarBuscador();
    pintarLinea();
    anunciarBuscador(t('editorTexto.disparador.insertada', { variable: nombreVariable(nombre) }));
    if (!conPanel) {
      enfocarTramo(indiceVariable + 1, 0);
    } else {
      pintarPanel();
      mostrarPanel();
      enfocarEnPanel('agregar-funcion');
    }
    cambio();
  }

  function quitar(idPieza: string): void {
    const indice = indiceDe(idPieza);
    if (indice < 0) return;
    const { piezas, indiceTramo, cursor } = quitarVariable(s.piezas, indice);
    s.piezas = piezas;
    if (s.abierta === idPieza) s.abierta = null;
    pintarLinea();
    pintarPanel();
    enfocarTramo(indiceTramo, cursor);
    cambio();
  }

  // ---- Panel of the open piece ----------------------------------------------------------------

  function alternarPanel(idPieza: string): void {
    // A direct variable's panel is the whole editor: it never closes.
    if (soloVariable) return;
    s.abierta = s.abierta === idPieza ? null : idPieza;
    el.linea.querySelectorAll<HTMLElement>('[data-pieza]').forEach((boton) => {
      boton.setAttribute('aria-expanded', String(boton.dataset.pieza === s.abierta));
    });
    pintarPanel();
    if (s.abierta !== null) mostrarPanel();
  }

  function cerrarPanel(): void {
    const idPieza = s.abierta;
    if (idPieza === null) return;
    alternarPanel(idPieza);
    el.linea.querySelector<HTMLElement>(`[data-pieza="${idPieza}"]`)?.focus();
  }

  function enfocarEnPanel(clave: string): boolean {
    const destino = el.panelHueco.querySelector<HTMLElement>(`[data-foco="${CSS.escape(clave)}"]`);
    if (!destino || (destino as HTMLButtonElement).disabled) return false;
    destino.focus();
    return true;
  }

  /** Change the open piece's chain and repaint its panel, keeping the focus on `foco`. */
  function cambiarCadena(piezas: Pieza[], ...foco: string[]): void {
    s.piezas = piezas;
    pintarPanel();
    actualizarPildoras();
    for (const clave of foco) if (enfocarEnPanel(clave)) break;
    cambio();
  }

  function boton(clave: string, nombreIcono: string, etiqueta: string, accion: () => void, deshabilitado = false) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'btn btn--icon btn--sm btn--quiet';
    b.dataset.foco = clave;
    b.setAttribute('aria-label', etiqueta);
    b.title = etiqueta;
    b.disabled = deshabilitado || s.soloLectura;
    b.append(icono(nombreIcono));
    b.addEventListener('click', accion);
    return b;
  }

  function pintarPanel(): void {
    const pieza = piezaAbierta();
    if (!pieza) {
      s.abierta = null;
      el.panelHueco.replaceChildren();
      return;
    }
    const variable = variableDe(pieza.nombre);
    const nombre = nombreVariable(pieza.nombre);

    const panel = document.createElement('section');
    panel.className = 'panel editor-texto__panel';
    panel.setAttribute('aria-labelledby', `${id}-panel-titulo`);
    panel.addEventListener('keydown', (evento) => {
      if (evento.key === 'Escape' && !soloVariable) {
        evento.preventDefault();
        cerrarPanel();
      }
    });
    panel.addEventListener('focusin', () => resaltar(pieza.id));

    const cabeza = document.createElement('div');
    cabeza.className = 'panel__head editor-texto__panelCabeza';
    const titulo = document.createElement('h3');
    titulo.className = 'panel__title';
    titulo.id = `${id}-panel-titulo`;
    // The same variable more than once: the panel says which one it is («Titular (2.ª vez)»).
    const iguales = s.piezas.filter((p) => p.tipo === 'variable' && p.nombre === pieza.nombre);
    titulo.textContent = iguales.length > 1 ? t('editorTexto.panel.vez', { variable: nombre, n: iguales.indexOf(pieza) + 1 }) : nombre;
    const tipo = document.createElement('span');
    tipo.className = 'tag tag--neutral';
    tipo.textContent = variable ? etiquetaTipo(variable.tipo) : '';
    const cerrar = document.createElement('button');
    cerrar.type = 'button';
    cerrar.className = 'btn btn--icon btn--sm btn--quiet';
    cerrar.dataset.foco = 'cerrar';
    cerrar.setAttribute('aria-label', t('editorTexto.panel.cerrar', { variable: nombre }));
    cerrar.title = cerrar.getAttribute('aria-label')!;
    cerrar.append(icono('x'));
    cerrar.addEventListener('click', cerrarPanel);
    cabeza.append(titulo, tipo);
    if (!soloVariable) cabeza.append(cerrar);

    const cuerpo = document.createElement('div');
    cuerpo.className = 'panel__body editor-texto__panelCuerpo';

    const errorPieza = document.createElement('p');
    errorPieza.className = 'field__error';
    errorPieza.dataset.errorPieza = '';
    cuerpo.append(errorPieza);

    if (pieza.funciones.length > 0) {
      const cadena = document.createElement('ol');
      cadena.className = 'editor-texto__cadena';
      cadena.setAttribute('aria-label', t('editorTexto.panel.cadena', { variable: nombre }));
      pieza.funciones.forEach((llamada, fi) => cadena.append(crearFuncion(pieza, llamada, fi)));
      cuerpo.append(cadena);
    }

    cuerpo.append(crearAgregarFuncion(pieza));

    const casilla = document.createElement('label');
    casilla.className = 'editor-texto__casilla';
    const marca = document.createElement('input');
    marca.type = 'checkbox';
    marca.checked = pieza.obligatoria;
    marca.disabled = s.soloLectura;
    marca.dataset.foco = 'obligatoria';
    marca.setAttribute('aria-describedby', `${id}-obligatoria-hint`);
    marca.addEventListener('change', () => {
      s.piezas = marcarObligatoria(s.piezas, indiceDe(pieza.id), marca.checked);
      cambio();
    });
    const textoMarca = document.createElement('span');
    textoMarca.textContent = t('editorTexto.panel.obligatoria');
    casilla.append(marca, textoMarca);
    const hint = document.createElement('p');
    hint.className = 'field__hint';
    hint.id = `${id}-obligatoria-hint`;
    hint.textContent = t('editorTexto.panel.obligatoriaHint');

    const resultado = document.createElement('p');
    resultado.className = 'editor-texto__resultadoPieza';
    const resultadoEtiqueta = document.createElement('span');
    resultadoEtiqueta.className = 'muted';
    resultadoEtiqueta.textContent = t('editorTexto.panel.resultado');
    const resultadoValor = document.createElement('span');
    resultadoValor.className = 'mono';
    resultadoValor.dataset.resultadoPieza = '';
    resultado.append(resultadoEtiqueta, ' ', resultadoValor);

    const pie = document.createElement('div');
    pie.className = 'editor-texto__panelPie';
    const quitarBoton = document.createElement('button');
    quitarBoton.type = 'button';
    quitarBoton.className = 'btn btn--danger btn--sm';
    quitarBoton.dataset.foco = 'quitar-variable';
    quitarBoton.textContent = t('editorTexto.panel.quitarVariable');
    quitarBoton.disabled = s.soloLectura;
    quitarBoton.addEventListener('click', () => quitar(pieza.id));
    pie.append(quitarBoton);

    cuerpo.append(casilla, hint, resultado);
    // A direct variable changes or clears from its select, not from here.
    if (!soloVariable) cuerpo.append(pie);
    panel.append(cabeza, cuerpo);
    el.panelHueco.replaceChildren(panel);
    pintarErroresPanel();
    pintarResultadoPieza();
  }

  /** When a piece's panel opens, the panel comes into view; a repaint of the same panel does not move the page. */
  const mostrarPanel = () => el.panelHueco.firstElementChild?.scrollIntoView({ block: 'nearest' });

  function crearFuncion(pieza: PiezaVariable, llamada: PiezaVariable['funciones'][number], fi: number) {
    const funcion = funcionDe(llamada.nombre);
    const nombre = nombreFuncion(llamada.nombre);
    const fila = document.createElement('li');
    fila.className = 'editor-texto__funcion';
    fila.dataset.funcion = String(fi);

    const cabeza = document.createElement('div');
    cabeza.className = 'editor-texto__funcionCabeza';
    const titulo = document.createElement('span');
    titulo.className = 'editor-texto__funcionNombre';
    titulo.id = `${id}-f${fi}-nombre`;
    titulo.textContent = nombre;
    const acciones = document.createElement('div');
    acciones.className = 'editor-texto__funcionAcciones';
    const ultima = pieza.funciones.length - 1;
    acciones.append(
      boton(`subir-${fi}`, 'arrow-up', t('editorTexto.funcion.subir', { funcion: nombre }), () =>
        cambiarCadena(moverFuncion(s.piezas, indiceDe(pieza.id), fi, -1), `subir-${fi - 1}`, `bajar-${fi - 1}`),
      fi === 0),
      boton(`bajar-${fi}`, 'arrow-down', t('editorTexto.funcion.bajar', { funcion: nombre }), () =>
        cambiarCadena(moverFuncion(s.piezas, indiceDe(pieza.id), fi, 1), `bajar-${fi + 1}`, `subir-${fi + 1}`),
      fi === ultima),
      boton(`quitar-${fi}`, 'x', t('editorTexto.funcion.quitar', { funcion: nombre }), () =>
        cambiarCadena(quitarFuncion(s.piezas, indiceDe(pieza.id), fi), `quitar-${fi}`, `quitar-${fi - 1}`, 'agregar-funcion'),
      ),
    );
    cabeza.append(titulo, acciones);
    fila.append(cabeza);

    if (funcion) {
      const descripcion = document.createElement('p');
      descripcion.className = 'field__hint';
      descripcion.textContent = nombreTraducido(funcion.clave_descripcion, '');
      if (descripcion.textContent) fila.append(descripcion);
      funcion.parametros.forEach((parametro, pi) =>
        fila.append(crearParametro(pieza, llamada, fi, parametro, pi)),
      );
    }

    const error = document.createElement('p');
    error.className = 'field__error';
    error.dataset.errorFuncion = String(fi);
    fila.append(error);
    return fila;
  }

  function crearParametro(
    pieza: PiezaVariable,
    llamada: PiezaVariable['funciones'][number],
    fi: number,
    parametro: ParametroCatalogo,
    pi: number,
  ): HTMLElement {
    const control = `${id}-f${fi}-${parametro.nombre}`;
    const errorId = `${control}-error`;
    const clave = `${fi}:${parametro.nombre}`;
    const argumento = llamada.args[pi];
    const etiqueta = nombreParametro(parametro);
    // The type of an 'entrada' parameter is whatever reaches this function.
    const tipo = parametro.tipo === 'entrada' ? tipoEnPosicion(tipos, pieza, fi) : parametro.tipo;

    const fijar = (valor: Argumento | undefined) => {
      const actual = s.piezas[indiceDe(pieza.id)] as PiezaVariable;
      s.piezas = fijarArgumentos(s.piezas, indiceDe(pieza.id), fi, conArgumento(actual.funciones[fi].args, pi, valor));
      actualizarPildoras();
      cambio();
    };
    const desdeTexto = (texto: string): Argumento | undefined =>
      texto === '' && !parametro.obligatorio ? undefined : leerArgumento(texto, tipo);

    const error = document.createElement('p');
    error.className = 'field__error';
    error.id = errorId;
    error.dataset.errorParametro = clave;

    if (parametro.opciones.length > 0) {
      const selector = crearSelectorPatronFecha({
        id: control,
        etiqueta,
        opciones: parametro.opciones,
        cerradas: parametro.opciones_cerradas,
        marcas: funcionDe(llamada.nombre)?.familia === 'fecha' ? catalogo.marcas_fecha : [],
        valor: textoArgumento(argumento),
        describe: errorId,
        onCambio: (valor) => fijar(desdeTexto(valor)),
      });
      selector.querySelectorAll<HTMLElement>('select, input').forEach((c) => {
        c.dataset.controlParametro = clave;
        (c as HTMLInputElement).disabled = s.soloLectura;
      });
      selector.querySelector<HTMLElement>('select')!.dataset.foco = `param-${fi}-${pi}`;
      selector.append(error);
      return selector;
    }

    const campoFijo = (): HTMLInputElement => {
      const input = document.createElement('input');
      input.type = 'text';
      input.className = 'input';
      input.id = control;
      input.autocomplete = 'off';
      input.value = textoArgumento(argumento);
      if (tipo === 'numero') input.inputMode = parametro.entero ? 'numeric' : 'decimal';
      if (parametro.por_defecto !== null && parametro.por_defecto !== undefined) {
        input.placeholder = String(parametro.por_defecto);
      }
      input.disabled = s.soloLectura;
      input.dataset.controlParametro = clave;
      input.dataset.foco = `param-${fi}-${pi}`;
      input.setAttribute('aria-describedby', errorId);
      input.addEventListener('input', () => fijar(desdeTexto(input.value)));
      return input;
    };

    if (!parametro.acepta_variable) {
      const campo = document.createElement('div');
      campo.className = 'field';
      const label = document.createElement('label');
      label.className = 'field__label';
      label.htmlFor = control;
      label.textContent = etiqueta;
      campo.append(label, campoFijo(), error);
      return campo;
    }

    // A literal or another variable: two options, then the matching control.
    const grupo = document.createElement('fieldset');
    grupo.className = 'field editor-texto__alternativa';
    const leyenda = document.createElement('legend');
    leyenda.className = 'field__label';
    leyenda.textContent = etiqueta;
    const modos = document.createElement('div');
    modos.className = 'segmented';
    const esVariable = esReferencia(argumento);
    const actual = esVariable ? argumento.variable : null;
    const compatibles = catalogo.contexto.variables.filter(
      (v) => (tipo === null || v.tipo === tipo) && (!v.archivado || v.nombre === actual),
    );

    const cambiarModo = (aVariable: boolean) => {
      if (aVariable === esReferencia((s.piezas[indiceDe(pieza.id)] as PiezaVariable).funciones[fi].args[pi])) return;
      const primera = compatibles[0];
      const valor: Argumento | undefined = aVariable
        ? primera
          ? { variable: primera.nombre }
          : undefined
        : parametro.obligatorio
          ? ''
          : undefined;
      const actual = s.piezas[indiceDe(pieza.id)] as PiezaVariable;
      cambiarCadena(
        fijarArgumentos(s.piezas, indiceDe(pieza.id), fi, conArgumento(actual.funciones[fi].args, pi, valor)),
        `param-${fi}-${pi}`,
      );
    };
    for (const [aVariable, texto] of [
      [false, t('editorTexto.parametro.fijo')],
      [true, t('editorTexto.parametro.variable')],
    ] as const) {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'segmented__item';
      item.textContent = texto;
      item.setAttribute('aria-pressed', String(aVariable === esVariable));
      item.disabled = s.soloLectura;
      item.dataset.foco = `modo-${fi}-${pi}-${aVariable ? 'variable' : 'fijo'}`;
      item.addEventListener('click', () => cambiarModo(aVariable));
      modos.append(item);
    }

    let entrada: HTMLElement;
    if (esVariable) {
      const select = document.createElement('select');
      select.className = 'input';
      select.id = control;
      select.disabled = s.soloLectura;
      select.dataset.controlParametro = clave;
      select.dataset.foco = `param-${fi}-${pi}`;
      select.setAttribute('aria-label', etiqueta);
      select.setAttribute('aria-describedby', errorId);
      for (const variable of compatibles) {
        const opcion = document.createElement('option');
        opcion.value = variable.nombre;
        opcion.textContent = etiquetaVariable(variable);
        opcion.selected = esReferencia(argumento) && variable.nombre === argumento.variable;
        select.append(opcion);
      }
      select.addEventListener('change', () => fijar({ variable: select.value }));
      entrada = select;
    } else {
      const input = campoFijo();
      input.setAttribute('aria-label', etiqueta);
      entrada = input;
    }
    grupo.append(leyenda, modos, entrada, error);
    return grupo;
  }

  function crearAgregarFuncion(pieza: PiezaVariable): HTMLElement {
    const campo = document.createElement('div');
    campo.className = 'field editor-texto__agregarFuncion';
    if (!admiteFunciones) {
      const palabras = opciones.sinFunciones;
      if (!palabras) return campo;
      const nota = document.createElement('p');
      nota.className = 'field__hint';
      nota.dataset.sinFunciones = '';
      nota.textContent = palabras.texto;
      if (palabras.enlace) {
        const enlace = document.createElement('a');
        enlace.href = palabras.enlace.href;
        enlace.textContent = palabras.enlace.texto;
        nota.append(' ', enlace);
      }
      campo.append(nota);
      return campo;
    }
    const tipo = tipoEnPosicion(tipos, pieza);
    const compatibles = funcionesCompatibles(tipos, tipo);
    if (compatibles.length === 0) {
      const nada = document.createElement('p');
      nada.className = 'muted';
      nada.tabIndex = -1;
      nada.dataset.foco = 'agregar-funcion';
      nada.textContent = t('editorTexto.funcion.ninguna');
      campo.append(nada);
      return campo;
    }

    const grupos = catalogo.familias
      .map((familia) => {
        const funciones = compatibles.filter((f) => f.familia === familia);
        return { familia, nombre: nombreTraducido(funciones[0]?.clave_familia ?? '', familia), funciones };
      })
      .filter((g) => g.funciones.length > 0);

    // A button that opens the list: search field, families, each function with its description and what it would give.
    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'btn btn--sm';
    boton.id = `${id}-agregar-funcion`;
    boton.dataset.foco = 'agregar-funcion';
    boton.disabled = s.soloLectura;
    boton.setAttribute('aria-expanded', 'false');
    boton.setAttribute('aria-controls', `${id}-funciones`);
    const textoBoton = document.createElement('span');
    textoBoton.textContent = t('editorTexto.funcion.agregar');
    boton.append(icono('plus'), textoBoton);
    const hueco = document.createElement('div');
    hueco.id = `${id}-funciones`;

    let pedidos: AbortController | null = null;
    const cerrar = (devolverFoco: boolean) => {
      pedidos?.abort();
      hueco.replaceChildren();
      boton.setAttribute('aria-expanded', 'false');
      if (devolverFoco) boton.focus();
    };
    const elegir = (nombre: string) => {
      const funcion = funcionDe(nombre);
      if (!funcion) return;
      const nueva = pieza.funciones.length;
      cambiarCadena(
        agregarFuncion(s.piezas, indiceDe(pieza.id), { nombre: funcion.nombre, args: argumentosIniciales(funcion.parametros) }),
        `param-${nueva}-0`,
        `quitar-${nueva}`,
      );
    };
    boton.addEventListener('click', () => {
      pedidos?.abort();
      const propios = new AbortController();
      pedidos = propios;
      const buscador = crearBuscadorFunciones({
        id: `${id}-funcion`,
        grupos,
        nombreDe: (funcion) => nombreFuncion(funcion.nombre),
        descripcionDe: (funcion) => nombreTraducido(funcion.clave_descripcion, ''),
        resultados: (funciones) => resultadosDeFunciones(pieza, funciones, propios.signal),
        onElegir: elegir,
        onCerrar: cerrar,
      });
      boton.setAttribute('aria-expanded', 'true');
      hueco.replaceChildren(buscador.raiz);
      buscador.campo.focus();
    });
    campo.append(boton, hueco);
    return campo;
  }

  /**
   * What each function without a required parameter would give added at the end of the piece's chain, with the example record,
   * by function name. One request: an expression with a node per function, and the preview answers node by node, so one that
   * fails (a problem located at its node) only leaves its own row without a result. The backend evaluates; the editor asks.
   */
  async function resultadosDeFunciones(
    pieza: PiezaVariable,
    funciones: readonly FuncionCatalogo[],
    signal: AbortSignal,
  ): Promise<Map<string, string>> {
    const resultados = new Map<string, string>();
    const probadas = funciones.filter((f) => !f.parametros.some((p) => p.obligatorio));
    if (probadas.length === 0) return resultados;
    const piezas: PiezaVariable[] = probadas.map((funcion) => ({
      ...pieza,
      funciones: [...pieza.funciones, { nombre: funcion.nombre, args: argumentosIniciales(funcion.parametros) }],
    }));
    const respuesta = await previsualizarTexto({ contexto: opciones.contexto, expresion: aExpresion(piezas), muestra: ejemplo() }, signal);
    const columna = respuesta.filas[0]?.columnas[0];
    for (const nodo of columna?.nodos ?? []) {
      const falla = columna?.problemas.some((p) => p.ubicacion?.nodo === nodo.indice);
      if (!falla && !nodo.vacio && probadas[nodo.indice]) resultados.set(probadas[nodo.indice].nombre, nodo.texto);
    }
    return resultados;
  }

  // ---- Painting problems ------------------------------------------------------------------------

  /** Pills' names and marks, in place: never rebuilds a run the analyst is typing in. */
  function actualizarPildoras(): void {
    s.piezas.forEach((pieza, indice) => {
      if (pieza.tipo !== 'variable') return;
      const boton = el.linea.querySelector<HTMLButtonElement>(`[data-pieza="${pieza.id}"]`);
      if (boton) pintarPildora(boton, pieza, problemasDePieza(indice).length > 0);
    });
  }

  function pintarProblemasLinea(): void {
    const problemas = problemasActuales();
    const deTramos = problemas.filter((p) => p.pieza !== null && s.piezas[p.pieza]?.tipo === 'texto');
    el.linea.querySelectorAll<HTMLTextAreaElement>('[data-tramo]').forEach((area) => {
      const conProblema = deTramos.some((p) => p.pieza === Number(area.dataset.tramo));
      area.classList.toggle('editor-texto__tramo--problema', conProblema);
      if (conProblema) {
        area.setAttribute('aria-invalid', 'true');
        area.setAttribute('aria-describedby', el.errorTramo.id);
      } else {
        area.removeAttribute('aria-invalid');
        area.removeAttribute('aria-describedby');
      }
    });
    el.errorTramo.textContent = deTramos
      .map((p) => `${nombreTramo(p.pieza!)}: ${mensajeProblema(p)}`)
      .join(' ');
  }

  function pintarErroresPanel(): void {
    const pieza = piezaAbierta();
    if (!pieza) return;
    const panel = el.panelHueco;
    panel.querySelectorAll<HTMLElement>('[data-error-pieza], [data-error-funcion], [data-error-parametro]').forEach((e) => {
      e.textContent = '';
    });
    panel.querySelectorAll('[data-control-parametro]').forEach((c) => c.removeAttribute('aria-invalid'));

    for (const problema of problemasDePieza(indiceDe(pieza.id))) {
      const fi = problema.ubicacion?.funcion;
      const parametro = problema.ubicacion?.parametro;
      const mensaje = mensajeDe(problema);
      let destino: HTMLElement | null = null;
      if (fi !== null && fi !== undefined && parametro) {
        destino = panel.querySelector(`[data-error-parametro="${CSS.escape(`${fi}:${parametro}`)}"]`);
        panel
          .querySelectorAll(`[data-control-parametro="${CSS.escape(`${fi}:${parametro}`)}"]`)
          .forEach((c) => c.setAttribute('aria-invalid', 'true'));
      }
      if (!destino && fi !== null && fi !== undefined) destino = panel.querySelector(`[data-error-funcion="${fi}"]`);
      destino ??= panel.querySelector('[data-error-pieza]');
      if (destino) destino.textContent = destino.textContent ? `${destino.textContent} ${mensaje}` : mensaje;
    }
  }

  function pintarResumen(): void {
    const problemas = problemasActuales();
    if (!resumenPropio || problemas.length === 0) {
      el.resumen.hidden = true;
      el.resumen.removeAttribute('role');
      return;
    }
    el.resumenTitulo.textContent =
      problemas.length === 1 ? t('editorTexto.resumen.uno') : t('editorTexto.resumen.varios', { n: problemas.length });
    el.resumenLista.replaceChildren(
      ...problemas.map((problema, indice) => {
        const item = document.createElement('li');
        const texto = document.createElement('span');
        texto.id = `${id}-problema-${indice}`;
        texto.textContent = `${lugarProblema(problema)}: ${mensajeDe(problema)}`;
        const ir = document.createElement('button');
        ir.type = 'button';
        ir.className = 'editor-texto__ir';
        ir.textContent = t('editorTexto.resumen.ir');
        ir.setAttribute('aria-describedby', texto.id);
        ir.addEventListener('click', () => irAProblema(indice));
        item.append(texto, ' ', ir);
        return item;
      }),
    );
    if (s.alertar) el.resumen.setAttribute('role', 'alert');
    else el.resumen.removeAttribute('role');
    el.resumen.hidden = false;
  }

  function pintarProblemas(): void {
    actualizarPildoras();
    pintarProblemasLinea();
    pintarErroresPanel();
    pintarResumen();
  }

  // ---- Preview ----------------------------------------------------------------------------------

  function parteDeNodo(nodo: Columna['nodos'][number]): HTMLElement {
    if (nodo.vacio) {
      const marca = document.createElement('span');
      marca.className = 'marca-vacio';
      marca.setAttribute('role', 'img');
      marca.setAttribute('aria-label', t('editorTexto.vacio'));
      marca.dataset.nodo = String(nodo.indice);
      return marca;
    }
    const parte = document.createElement('span');
    parte.dataset.nodo = String(nodo.indice);
    parte.textContent = nodo.texto;
    return parte;
  }

  function resaltar(idPieza: string | null): void {
    s.resaltada = idPieza ?? s.abierta;
    el.resultado.querySelectorAll('.editor-texto__parte--resaltada').forEach((p) => {
      p.classList.remove('editor-texto__parte--resaltada');
    });
    const nodo = s.resaltada === null ? undefined : s.vista?.nodos.get(s.resaltada);
    if (nodo === undefined) return;
    el.resultado.querySelector(`[data-nodo="${nodo}"]`)?.classList.add('editor-texto__parte--resaltada');
  }

  function pintarResultadoPieza(): void {
    const destino = el.panelHueco.querySelector<HTMLElement>('[data-resultado-pieza]');
    if (!destino) return;
    const pieza = piezaAbierta();
    const indiceNodo = pieza ? s.vista?.nodos.get(pieza.id) : undefined;
    const nodo = indiceNodo === undefined ? undefined : s.vista?.columna.nodos.find((n) => n.indice === indiceNodo);
    destino.replaceChildren(nodo ? parteDeNodo(nodo) : document.createTextNode('—'));
  }

  function pintarVista(): void {
    const columna = s.vista?.columna;
    if (!columna) {
      el.resultado.textContent = '';
    } else if (columna.nodos.length === 0) {
      el.resultado.replaceChildren();
      const vacio = document.createElement('span');
      vacio.className = 'muted';
      vacio.textContent = t('editorTexto.vista.vacia');
      el.resultado.append(vacio);
    } else {
      el.resultado.replaceChildren(...columna.nodos.map(parteDeNodo));
    }
    resaltar(s.resaltada);
    pintarResultadoPieza();
    pintarLargo();

    el.sinConexion.hidden = !s.sinConexion;
    // What the sample says about its data is not an error of what was written: it goes under the preview as hints (§13.6),
    // first «Con este producto, falta el dato de {variable}.» for each variable that came empty, then the row's own reasons.
    const vacias = (columna?.nodos ?? [])
      .filter((nodo) => nodo.vacio && nodo.tipo === 'variable')
      .map((nodo) => {
        const idPieza = [...(s.vista?.nodos ?? [])].find(([, indice]) => indice === nodo.indice)?.[0];
        const pieza = s.piezas.find((p): p is PiezaVariable => p.tipo === 'variable' && p.id === idPieza);
        return pieza ? t('editorTexto.muestra.vacia', { variable: nombreVariable(pieza.nombre) }) : null;
      })
      .filter((texto): texto is string => texto !== null);
    const datos = [
      ...vacias,
      ...[...(s.vista?.excluida ? [s.vista.excluida] : []), ...(columna?.problemas ?? [])].map((problema) => mensajeProblema(problema)),
    ];
    // The list is a polite live region that is never hidden (an empty list takes no room): content that appears in a region
    // that was hidden is not announced reliably. It is rewritten only when what it says changes.
    const pistas = datos.join('\n');
    if (pistas !== s.pistas) {
      s.pistas = pistas;
      el.problemasFila.replaceChildren(
        ...datos.map((texto) => {
          const item = document.createElement('li');
          item.className = 'field__hint';
          item.textContent = texto;
          return item;
        }),
      );
    }
  }

  function pintarLargo(): void {
    const { actual, maximo, limite, sinCota } = largo();
    if (actual === null) {
      el.largoTexto.textContent = '';
      el.largoNivel.hidden = true;
      return;
    }
    // One form in every place (interface rules §13.6): «{n} / {tope} caracteres», or «{n} caracteres» with no limit; and when the
    // data can make it longer, «· hasta {maximo} con los datos más largos».
    const partes = [limite === null ? t('editorTexto.largo.actual', { n: actual }) : t('editorTexto.largo.deTope', { n: actual, tope: limite })];
    if (maximo !== null) {
      if (maximo > actual) partes.push(t('editorTexto.largo.hasta', { maximo }));
    } else if (sinCota) {
      partes.push(`· ${t('editorTexto.largo.sinCota', { motivo: mensajeProblema(sinCota) })}`);
    }
    el.largoTexto.textContent = partes.join(' ');

    // Only two tags, and only when there is something to say: near the limit (the context's threshold) and over it.
    const nivel = nivelDeLargo(maximo ?? actual, limite, catalogo.contexto.umbral_advertencia);
    const conAviso = nivel === 'cerca' || nivel === 'excedido';
    // Over the limit the counter turns the error colour, with no box of its own (the tag says it too).
    el.largoTexto.classList.toggle('editor-texto__largo--error', nivel === 'excedido');
    el.largoNivel.hidden = !conAviso;
    el.largoNivel.className = `tag tag--${nivel === 'excedido' ? 'error' : 'advertencia'}`;
    el.largoNivel.textContent = conAviso ? t(nivel === 'excedido' ? 'editorTexto.largo.pasa' : 'editorTexto.largo.cerca') : '';
    // Said once when the threshold or the limit is crossed, never on every key; the first paint is silent.
    if (s.nivelAnunciado !== null && nivel !== s.nivelAnunciado && conAviso) {
      el.largoAnuncio.textContent = el.largoNivel.textContent;
    }
    s.nivelAnunciado = nivel;
  }

  // ---- Sample control ---------------------------------------------------------------------------

  function pintarMuestra(): void {
    el.controlMuestra.hidden = opciones.controlMuestra === false;
    const real = s.muestra.tipo === 'producto_real';
    for (const b of el.botonesMuestra) {
      b.setAttribute('aria-pressed', String((b.dataset.muestra === 'producto_real') === real));
    }
    el.producto.hidden = !real;
  }

  function muestraReal(): MuestraTexto {
    return {
      tipo: 'producto_real',
      fecha_corte: el.fecha.value || null,
      pagare: el.pagare.value.trim() || null,
      cantidad: 1,
    };
  }

  for (const b of el.botonesMuestra) {
    b.addEventListener('click', () => {
      s.muestra = b.dataset.muestra === 'producto_real' ? muestraReal() : ejemplo();
      el.errorMuestra.textContent = '';
      el.pagare.removeAttribute('aria-invalid');
      pintarMuestra();
      programar();
    });
  }
  for (const campo of [el.fecha, el.pagare]) {
    campo.addEventListener('input', () => {
      s.muestra = muestraReal();
      programar();
    });
  }

  // ---- Reaching a problem -----------------------------------------------------------------------

  function irAProblema(indice: number): void {
    const problema = problemasActuales()[indice];
    if (!problema) return;
    const pieza = problema.pieza === null ? undefined : s.piezas[problema.pieza];
    if (!pieza) {
      (el.resumen.hidden ? el.linea.querySelector<HTMLElement>('[data-tramo]') : el.resumen)?.focus();
      return;
    }
    if (pieza.tipo === 'texto') {
      enfocarTramo(problema.pieza!, pieza.valor.length);
      return;
    }
    if (s.abierta !== pieza.id) alternarPanel(pieza.id);
    const fi = problema.ubicacion?.funcion;
    const parametro = problema.ubicacion?.parametro;
    if (fi !== null && fi !== undefined) {
      const pi = funcionDe(pieza.funciones[fi]?.nombre ?? '')?.parametros.findIndex((p) => p.nombre === parametro) ?? -1;
      if (pi >= 0 && enfocarEnPanel(`param-${fi}-${pi}`)) return;
      if (enfocarEnPanel(`quitar-${fi}`)) return;
    }
    if (soloVariable) el.directaSelect.focus();
    else el.linea.querySelector<HTMLElement>(`[data-pieza="${pieza.id}"]`)?.focus();
  }

  // ---- Direct variable ----------------------------------------------------------------------------

  function abrirDirecta(): void {
    const variable = s.piezas.find((p): p is PiezaVariable => p.tipo === 'variable');
    s.abierta = variable?.id ?? null;
  }

  function pintarDirecta(): void {
    if (!soloVariable) return;
    const elegida = s.piezas.find((p): p is PiezaVariable => p.tipo === 'variable')?.nombre ?? '';
    const ninguna = document.createElement('option');
    ninguna.value = '';
    ninguna.textContent = t('editorTexto.directa.elegir');
    const grupos = agruparPorOrigen(catalogo.contexto.variables).map(([origen, variables]) => {
      const grupo = document.createElement('optgroup');
      const contexto = catalogo.contextos.find((c) => c.nombre === origen);
      grupo.label = contexto ? nombreTraducido(contexto.clave_nombre, origen) : origen;
      for (const variable of variables.filter((v) => !v.archivado || v.nombre === elegida)) {
        const opcion = document.createElement('option');
        opcion.value = variable.nombre;
        const campo = etiquetaVariable(variable);
        opcion.textContent = variable.archivado
          ? t('camposAdicionales.archivadoEnLista', { campo })
          : variable.adicional
            ? t('camposAdicionales.opcionVariable', { campo, tipo: etiquetaTipo(variable.tipo) })
            : `${campo} (${etiquetaTipo(variable.tipo)})`;
        grupo.append(opcion);
      }
      return grupo;
    });
    el.directaSelect.replaceChildren(ninguna, ...grupos);
    // A saved variable the catalogue no longer has stays visible, so the backend's problem has a place.
    if (elegida && !variableDe(elegida)) {
      const perdida = document.createElement('option');
      perdida.value = elegida;
      perdida.textContent = humanizarNombre(elegida);
      el.directaSelect.append(perdida);
    }
    el.directaSelect.value = elegida;
  }

  el.directaSelect.addEventListener('change', () => {
    s.piezas = desdeExpresion(cambiarVariableDirecta(aExpresion(s.piezas), el.directaSelect.value));
    abrirDirecta();
    pintarLinea();
    pintarPanel();
    cambio();
  });

  // ---- Wiring -----------------------------------------------------------------------------------

  el.agregar.addEventListener('click', abrirDesdeElBoton);

  function fijarSoloLectura(soloLectura: boolean): void {
    s.soloLectura = soloLectura;
    el.agregar.disabled = soloLectura;
    el.directaSelect.disabled = soloLectura;
    el.pista.hidden = soloVariable || soloLectura;
    if (soloLectura) cerrarBuscador();
    raiz.classList.toggle('editor-texto--soloLectura', soloLectura);
    pintarLinea();
    pintarPanel();
  }

  function alCambiarIdioma(): void {
    cerrarBuscador();
    pintarDirecta();
    pintarLinea();
    pintarPanel();
    pintarResumen();
    pintarVista();
  }
  document.addEventListener('languagechange', alCambiarIdioma);

  el.directa.hidden = !soloVariable;
  el.linea.hidden = soloVariable;
  el.barra.hidden = soloVariable;
  if (soloVariable) abrirDirecta();
  pintarDirecta();
  fijarSoloLectura(s.soloLectura);
  pintarMuestra();
  programar();

  return {
    fijarExpresion(expresion) {
      s.piezas = piezasDe(expresion);
      s.abierta = null;
      if (soloVariable) abrirDirecta();
      s.ultimoTramo = null;
      s.problemas = [];
      s.validada = false;
      s.origen = 'externo';
      s.alertar = false;
      cerrarBuscador();
      pintarDirecta();
      pintarLinea();
      pintarPanel();
      pintarResumen();
      programar();
      emitir();
    },
    fijarMuestra(muestra) {
      s.muestra = muestra;
      pintarMuestra();
      programar();
    },
    irAProblema,
    expresion: () => aExpresion(s.piezas),
    estado,
    comprobarAntesDeGuardar() {
      if (pendiente()) return false;
      if (s.validada && s.valida) return true;
      if (resumenPropio) {
        s.alertar = true;
        pintarResumen();
        if (problemasActuales().length > 0) irAProblema(0);
        else el.resumen.focus();
      }
      return false;
    },
    fijarSoloLectura,
    fijarNotaMuestra(texto) {
      const nueva = texto ?? '';
      const cambio = nueva !== el.notaMuestra.textContent;
      el.notaMuestra.textContent = nueva;
      el.notaMuestra.hidden = nueva === '';
      // The visible note is not a live region: one that appears from hidden is not announced
      // reliably. The announcement goes to its own region, and only when the note changes.
      if (cambio) el.notaAnuncio.textContent = nueva;
    },
    destruir() {
      destruido = true;
      document.removeEventListener('languagechange', alCambiarIdioma);
      clearTimeout(temporizador);
      controlador?.abort();
      s.programado = false;
      s.enCurso = false;
    },
  };
}
