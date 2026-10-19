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
  argumentosIniciales,
  cambiarVariableDirecta,
  conArgumento,
  esReferencia,
  leerArgumento,
  nivelDeLargo,
  nodoDePieza,
  piezaDeAncla,
  resumenFunciones,
  textoArgumento,
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
import { t } from '../lib/i18n';
import { crearSelectorPatronFecha } from './selector-patron-fecha';
import { crearSelectorVariable, etiquetaTipo } from './selector-variable';
import type { components } from '../lib/contrato-api';

type Esquemas = components['schemas'];
type FuncionCatalogo = Esquemas['FuncionRespuesta'];
type ParametroCatalogo = Esquemas['ParametroRespuesta'];
type Columna = Esquemas['ColumnaRespuesta'];

export const EVENTO_EXPRESION = 'expresioncambiada';

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
  const clave = `textoEnriquecido.codigo.${problema.codigo}`;
  const texto = t(clave);
  return texto === clave ? problema.detalle : texto;
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

  const piezasDe = (expresion: Expresion | null | undefined): Pieza[] =>
    desdeExpresion(soloVariable ? aVariableDirecta(expresion) : expresion);

  const s = {
    piezas: piezasDe(opciones.expresion),
    /** Id of the variable whose panel is open. */
    abierta: null as string | null,
    selectorAbierto: false,
    /** Last text run with focus and its caret: where `+ Variable` inserts. */
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
    const lineas = area.value.split('\n');
    const ancho = Math.max(2, ...lineas.map((l) => [...l].length + 1));
    area.style.inlineSize = `${ancho}ch`;
    area.style.blockSize = 'auto';
    area.style.blockSize = `${area.scrollHeight}px`;
  }

  function etiquetaPieza(pieza: PiezaVariable, conProblema: boolean): { visible: string; accesible: string } {
    const variable = nombreVariable(pieza.nombre);
    const resumen = resumenFunciones(pieza.funciones, nombreFuncion, nombreVariable);
    const visible = resumen ? `${variable} · ${resumen}` : variable;
    const accesible = [
      t('editorTexto.pieza.variable', { variable }),
      resumen ? `, ${resumen}` : '',
      conProblema ? t('editorTexto.pieza.conProblema') : '',
      '. ',
      t('editorTexto.pieza.abre'),
    ].join('');
    return { visible, accesible };
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
    area.addEventListener('focus', recordar);
    area.addEventListener('keyup', recordar);
    area.addEventListener('pointerup', recordar);
    area.addEventListener('select', recordar);
    area.addEventListener('input', () => {
      s.piezas = editarTramo(s.piezas, indice, area.value);
      recordar();
      ajustar(area);
      cambio();
    });
    area.addEventListener('keydown', (evento) => {
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
    const { visible, accesible } = etiquetaPieza(pieza, conProblema);
    const texto = boton.querySelector<HTMLElement>('.editor-texto__piezaTexto')!;
    texto.textContent = visible;
    boton.setAttribute('aria-label', accesible);
    boton.title = visible;
    boton.classList.toggle('editor-texto__pieza--problema', conProblema);
    boton.querySelector('svg')?.remove();
    if (conProblema) boton.prepend(icono('triangle-alert'));
  }

  function pintarLinea(): void {
    el.linea.replaceChildren(
      ...s.piezas.map((pieza, indice) =>
        pieza.tipo === 'texto' ? crearTramo(indice, pieza.valor) : crearPildora(indice, pieza),
      ),
    );
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

  function abrirSelector(): void {
    s.selectorAbierto = true;
    el.agregar.setAttribute('aria-expanded', 'true');
    const selector = crearSelectorVariable({
      id: `${id}-variable`,
      variables: catalogo.contexto.variables,
      contextos: catalogo.contextos,
      onElegir: (nombre) => insertar(nombre),
      onCerrar: () => {
        cerrarSelector();
        el.agregar.focus();
      },
    });
    el.selectorHueco.replaceChildren(selector);
    selector.querySelector<HTMLInputElement>('input[type="search"]')?.focus();
  }

  function cerrarSelector(): void {
    s.selectorAbierto = false;
    el.agregar.setAttribute('aria-expanded', 'false');
    el.selectorHueco.replaceChildren();
  }

  function insertar(nombre: string): void {
    const destino = s.ultimoTramo ?? { indice: s.piezas.length - 1, cursor: Number.MAX_SAFE_INTEGER };
    const { piezas, indiceVariable } = insertarVariable(s.piezas, destino.indice, destino.cursor, nombre);
    s.piezas = piezas;
    s.ultimoTramo = { indice: indiceVariable + 1, cursor: 0 };
    s.abierta = (piezas[indiceVariable] as PiezaVariable).id;
    cerrarSelector();
    pintarLinea();
    pintarPanel();
    enfocarEnPanel('agregar-funcion');
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
    titulo.textContent = nombre;
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
    const compatibles = catalogo.contexto.variables.filter((v) => tipo === null || v.tipo === tipo);

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

    const label = document.createElement('label');
    label.className = 'visually-hidden';
    label.htmlFor = `${id}-agregar-funcion`;
    label.textContent = t('editorTexto.funcion.agregar');
    const select = document.createElement('select');
    select.className = 'input';
    select.id = `${id}-agregar-funcion`;
    select.dataset.foco = 'agregar-funcion';
    select.disabled = s.soloLectura;
    const primera = document.createElement('option');
    primera.value = '';
    primera.textContent = `+ ${t('editorTexto.funcion.agregar')}`;
    select.append(primera);
    for (const familia of catalogo.familias) {
      const deFamilia = compatibles.filter((f) => f.familia === familia);
      if (deFamilia.length === 0) continue;
      const grupo = document.createElement('optgroup');
      grupo.label = nombreTraducido(deFamilia[0].clave_familia, familia);
      for (const funcion of deFamilia) {
        const opcion = document.createElement('option');
        opcion.value = funcion.nombre;
        opcion.textContent = nombreFuncion(funcion.nombre);
        grupo.append(opcion);
      }
      select.append(grupo);
    }
    select.addEventListener('change', () => {
      const funcion = funcionDe(select.value);
      if (!funcion) return;
      const nueva = pieza.funciones.length;
      cambiarCadena(
        agregarFuncion(s.piezas, indiceDe(pieza.id), { nombre: funcion.nombre, args: argumentosIniciales(funcion.parametros) }),
        `param-${nueva}-0`,
        `quitar-${nueva}`,
      );
    });
    campo.append(label, select);
    return campo;
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
      const mensaje = mensajeProblema(problema);
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
        texto.textContent = `${lugarProblema(problema)}: ${mensajeProblema(problema)}`;
        const ir = document.createElement('button');
        ir.type = 'button';
        ir.className = 'btn btn--sm btn--quiet';
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
    const datos = [
      ...(s.vista?.excluida ? [s.vista.excluida] : []),
      ...(columna?.problemas ?? []),
    ];
    el.problemasFila.hidden = datos.length === 0;
    el.problemasFila.replaceChildren(
      ...datos.map((problema) => {
        const item = document.createElement('li');
        item.className = 'notice notice--info';
        item.textContent = mensajeProblema(problema);
        return item;
      }),
    );
  }

  function pintarLargo(): void {
    const { actual, maximo, limite, sinCota } = largo();
    if (actual === null) {
      el.largoTexto.textContent = '';
      el.largoNivel.hidden = true;
      return;
    }
    const partes = [t('editorTexto.largo.actual', { n: actual })];
    if (maximo !== null) {
      partes.push(
        limite === null
          ? t('editorTexto.largo.maximo', { maximo })
          : t('editorTexto.largo.maximoDe', { maximo, limite }),
      );
    } else if (sinCota) {
      partes.push(t('editorTexto.largo.sinCota', { motivo: mensajeProblema(sinCota) }));
    } else if (limite !== null) {
      partes.push(t('editorTexto.largo.limite', { limite }));
    }
    el.largoTexto.textContent = partes.join(' · ');

    const nivel = nivelDeLargo(maximo ?? actual, limite, catalogo.contexto.umbral_advertencia);
    el.largoNivel.hidden = nivel === 'sin_limite';
    el.largoNivel.className = `tag tag--${{ sin_limite: 'neutral', dentro: 'vigente', cerca: 'advertencia', excedido: 'error' }[nivel]}`;
    el.largoNivel.textContent = nivel === 'sin_limite' ? '' : t(`editorTexto.largo.nivel.${nivel}`);
    // Said once per change of level, never on every key; the first paint is silent.
    if (s.nivelAnunciado !== null && nivel !== s.nivelAnunciado && nivel !== 'sin_limite') {
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
      for (const variable of variables) {
        const opcion = document.createElement('option');
        opcion.value = variable.nombre;
        opcion.textContent = `${etiquetaVariable(variable)} (${etiquetaTipo(variable.tipo)})`;
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

  el.agregar.addEventListener('click', () => (s.selectorAbierto ? cerrarSelector() : abrirSelector()));

  function fijarSoloLectura(soloLectura: boolean): void {
    s.soloLectura = soloLectura;
    el.agregar.disabled = soloLectura;
    el.directaSelect.disabled = soloLectura;
    if (soloLectura) cerrarSelector();
    raiz.classList.toggle('editor-texto--soloLectura', soloLectura);
    pintarLinea();
    pintarPanel();
  }

  function alCambiarIdioma(): void {
    pintarDirecta();
    pintarLinea();
    pintarPanel();
    pintarResumen();
    pintarVista();
    if (s.selectorAbierto) abrirSelector();
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
      cerrarSelector();
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
