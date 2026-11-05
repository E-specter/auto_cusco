/**
 * The messages of the WhatsMKT settings (T-WM-F1b2, docs/whatsmkt-interfaz.md §5 and §5.1): two panels of `TextosGuardados` over the
 * context `whatsmkt.mensaje`, and the editor each one hands the component.
 *
 * - Panel 1 («Segmentos y mensajes») chooses a segment with a `.segmented` and opens the text that is its message; «Usar como mensaje
 *   de …» links the text that is on screen to it (`PUT /whatsmkt/segmentos`, which keeps what a body leaves out).
 * - Panel 2 («Mensajes globales») offers the texts that are no segment's message.
 * - The editor is a plain textarea with the macros of the default definition, a counter that counts `[whatsapp]` as the link it
 *   becomes, the emoji and macro errors, and the preview with a sample row. The backend is the judge of what is saved.
 *
 *     const mensajes = await montarMensajes({ configuracion, segmentos, raizSegmentos, raizGlobales, panel, alVincular });
 *     mensajes.destruir();
 */

import { mensajeDeError } from '../lib/api';
import { obtenerDefinicion } from '../lib/api-definiciones';
import { olvidarCatalogo, previsualizarTexto } from '../lib/api-texto-enriquecido';
import { listarTextos, type ContenidoTexto, type ProblemaTexto, type ResumenTexto } from '../lib/api-textos-guardados';
import { guardarSegmentos, type ConfiguracionWhatsmkt, type SegmentoWhatsmkt } from '../lib/api-whatsmkt';
import { guardadaDesdeRespuesta } from '../lib/constructor-columnas';
import { t } from '../lib/i18n';
import type { Expresion } from '../lib/expresion';
import { largoDelMensaje, macrosDeLaDefinicion, partesDeLaVista, primerEmoji, textoDeProblemaDelMensaje, type MacroDeDefinicion } from '../lib/whatsmkt-mensaje';
import { expresionDeMensaje, numeroDeMacro, textoDeMensaje } from '../lib/whatsmkt-mensaje-expresion';
import { destinoDeColumnas } from '../lib/whatsmkt-vuelta';
import { EVENTO_EXPRESION, mensajeProblema, montarEditor, type ControladorEditor, type EstadoEditor, type OpcionesEditor as OpcionesDelEditor } from './editor-texto';
import { EVENTO_TEXTOS, montarTextosGuardados, type ControladorTextos, type EstadoTextos, type FabricaEditor } from './textos-guardados';

export const CONTEXTO_MENSAJE = 'whatsmkt.mensaje';
/** Where Columnas de carga sends the analyst back to from the panel of functions: these settings. */
const VUELTA = '/whatsmkt/configuracion';
/** The rows of the preview: the first three of the example of the context, one per segment of the engine. */
const FILAS_DE_EJEMPLO = 3;

/** What the editors read of the default definition: its macros and the values of some example rows. */
interface DatosDeLaDefinicion {
  id: number | null;
  macros: MacroDeDefinicion[];
  /** One entry per example row, with the value of every column (the first is the number: macro n is index n); `null` when it could not be built. */
  ejemplos: Array<Array<string | null>> | null;
}

export interface OpcionesMensajes {
  configuracion: ConfiguracionWhatsmkt;
  segmentos: SegmentoWhatsmkt[];
  /** Roots of the two `TextosGuardados` components (`<TextosGuardados id=…>`). */
  raizSegmentos: HTMLElement;
  raizGlobales: HTMLElement;
  /** The block of panel 1 that holds the segment buttons and the link: `[data-segmentos-mensaje]`, `[data-vinculo-texto]`, `[data-vinculo-usar]`. */
  bloqueSegmentos: HTMLElement;
  /** Tells the page the segments changed (a message was linked): it keeps its own list. */
  alVincular: (segmentos: SegmentoWhatsmkt[]) => void;
}

export interface ControladorMensajes {
  /** The limit, the contact WhatsApp or the default definition changed: the editors read them again. */
  configuracionCambio(configuracion: ConfiguracionWhatsmkt): void;
  /** The segment table was saved: the labels the panels carry are the new ones. */
  segmentosCambiaron(segmentos: SegmentoWhatsmkt[]): void;
  destruir(): void;
}

/** A name in the quotes of the language («Preventivo» / “Preventivo”), never quotes written in a key. */
const citado = (nombre: string): string => t('camposAdicionales.nombreCitado', { campo: nombre });

const nodo = <K extends keyof HTMLElementTagNameMap>(etiqueta: K, clase?: string): HTMLElementTagNameMap[K] => {
  const creado = document.createElement(etiqueta);
  if (clase) creado.className = clase;
  return creado;
};

export async function montarMensajes(opciones: OpcionesMensajes): Promise<ControladorMensajes> {
  let configuracion = opciones.configuracion;
  /** What the editors were mounted with: the page may change the object it handed over, so a change is told against these. */
  let contexto = { definicion: configuracion.definicion_defecto_id, tope: configuracion.tope_mensaje };
  let segmentos = opciones.segmentos;
  let textos: ResumenTexto[] = [];
  let activo = segmentos[0]?.clave ?? '';
  let datos: DatosDeLaDefinicion = { id: null, macros: [], ejemplos: null };
  const alta = new AbortController();
  const escucha = { signal: alta.signal };
  const editores = new Set<{ repintar: (contextoCambio?: boolean) => Promise<void> }>();
  /** Each panel's editor listens for what its panel's save was refused (`alRechazar`): by the prefix of the editor. */
  const alRechazarDe = new Map<string, (problemas: ProblemaTexto[]) => void>();
  let controladores: { segmentos: ControladorTextos | null; globales: ControladorTextos | null } = { segmentos: null, globales: null };

  const vinculadoASegmento = (id: number): boolean => segmentos.some((s) => s.texto_guardado_id === id);
  const etiquetaDeSegmento = (clave: string): string => segmentos.find((s) => s.clave === clave)?.etiqueta ?? clave;

  // ---- What the editors read: the macros and the sample of the default definition ---------------------------------

  async function cargarDatos(): Promise<void> {
    const id = configuracion.definicion_defecto_id;
    if (id === datos.id && (id === null || datos.macros.length > 0 || datos.ejemplos !== null)) return;
    datos = { id, macros: [], ejemplos: null };
    editores.forEach((editor) => editor.repintar());
    if (id === null) return;
    try {
      const definicion = await obtenerDefinicion(id);
      if (configuracion.definicion_defecto_id !== id) return;
      datos = { id, macros: macrosDeLaDefinicion(definicion.version.contenido.columnas), ejemplos: null };
      editores.forEach((editor) => editor.repintar());
      const previa = await previsualizarTexto({
        contexto: 'cartera',
        definicion: guardadaDesdeRespuesta(definicion),
        muestra: { tipo: 'ejemplos_por_segmento', cantidad: FILAS_DE_EJEMPLO },
      });
      if (configuracion.definicion_defecto_id !== id) return;
      const filas = previa.filas.filter((fila) => fila.excluida === null).slice(0, FILAS_DE_EJEMPLO);
      datos = { ...datos, ejemplos: filas.map((fila) => fila.columnas.map((columna) => columna.texto ?? null)) };
    } catch {
      // The editor still works: it says its preview or its macros are not there, and the rest of the screen goes on.
      if (configuracion.definicion_defecto_id === id && datos.macros.length === 0) datos = { id, macros: [], ejemplos: null };
    }
    editores.forEach((editor) => editor.repintar());
  }

  // ---- The editor of a message (§13.7 of the engine) --------------------------------------------------------------

  /** Where the editors rest while no panel holds one: the page renders them (the markup of the engine is built with the page) and the factory moves them. */
  const ALMACEN = '[data-editores-mensaje]';

  /** What the panel of a piece says, the context admitting no functions, and the link to where the function is made: the column, in Columnas de carga. */
  function palabrasSinFunciones(): NonNullable<OpcionesDelEditor['sinFunciones']> {
    const id = configuracion.definicion_defecto_id;
    const { href, clave } = destinoDeColumnas(id, id !== null, VUELTA);
    return { texto: t('whatsmkt.mensaje.sinFunciones'), enlace: { texto: t(clave), href } };
  }

  /**
   * The editor of a message is the common one, in the context `whatsmkt.mensaje`: its macros and the link of WhatsApp are pills, and the
   * text that is saved stays plain (`lib/whatsmkt-mensaje-expresion.ts`). It brings its own counter and its own problems of the backend's
   * validation; this adds the rules the backend only applies when it saves (no emojis, the limit) and the preview with a row of the definition,
   * and gathers every problem in ONE summary above the editor (§13.6), with «Ir al problema» for each one. The summary follows each change: it does not
   * wait for the save to say there is an emoji. What the backend refuses on save comes in too (`alRechazar` of the component) and the focus goes to the
   * summary; then the component's own list would say the same twice, and it is hidden while the summary carries what it refused.
   */
  function fabricaDeEditor(prefijo: string, panel: HTMLElement): FabricaEditor {
    return async (anfitrion, { alCambiar }) => {
      const idEditor = `${prefijo}-editor`;
      let raizEditor = document.getElementById(idEditor)!;
      // Mounting binds the markup it is given: a second mount (the context changed) takes a fresh copy, not the one that is bound.
      const intacta = raizEditor.cloneNode(true) as HTMLElement;

      // The summary of every problem, above the editor.
      const resumen = nodo('div', 'notice notice--danger editor-texto__resumen');
      resumen.tabIndex = -1;
      resumen.hidden = true;
      const cuerpoResumen = nodo('div');
      const tituloResumen = nodo('p', 'editor-texto__resumenTitulo');
      // The focus goes to it after a refused save and that is all: no `role="alert"` (it would be said twice). Its title is its name.
      tituloResumen.id = `${prefijo}-resumen-titulo`;
      resumen.setAttribute('role', 'group');
      resumen.setAttribute('aria-labelledby', tituloResumen.id);
      const listaResumen = nodo('ul', 'editor-texto__resumenLista');
      cuerpoResumen.append(tituloResumen, listaResumen);
      resumen.append(
        raizEditor.querySelector<HTMLTemplateElement>('template[data-icono="triangle-alert"]')!.content.firstElementChild!.cloneNode(true),
        cuerpoResumen,
      );
      const sinMacros = nodo('p', 'field__hint wm-editor__aviso');
      // Each problem once, in its place (§13.6): the emoji marks its text run and says itself under the line, as any error of a run does (the editor
      // does not know this rule, so the page puts that line); the limit is the counter in the error colour with its tag, with no box of its own; an
      // unknown macro is its red pill, which the editor draws.
      const errorDeEmoji = nodo('p', 'field__error');
      const vista = nodo('div', 'wm-vista');
      const tituloVista = nodo('h3', 'wm-subtitulo');
      const campoFila = nodo('div', 'field wm-vista__fila');
      const rotuloFila = nodo('label', 'field__label');
      rotuloFila.htmlFor = `${prefijo}-fila`;
      const selectFila = nodo('select', 'input');
      selectFila.id = `${prefijo}-fila`;
      campoFila.append(rotuloFila, selectFila);
      const cuerpoVista = nodo('p', 'wm-vista__texto mono');
      cuerpoVista.setAttribute('role', 'status');
      cuerpoVista.setAttribute('aria-live', 'off');
      const notaVista = nodo('p', 'field__hint');
      vista.append(tituloVista, campoFila, cuerpoVista, notaVista);
      anfitrion.replaceChildren(resumen, sinMacros, raizEditor, vista);

      const opcionesEditor: OpcionesDelEditor = {
        contexto: CONTEXTO_MENSAJE,
        expresion: null,
        // No «Producto real» here: the sample is the example of the context, and the rows of the definition have their own preview below.
        controlMuestra: false,
        // One preview only: «Así lo verá el cliente», below. The editor keeps its counter (which still asks the engine for the length).
        vistaPrevia: false,
        resumen: 'ninguno',
        sinFunciones: palabrasSinFunciones(),
        // A macro the definition does not have reads «MACRO4» as the marker says, and the engine gives the pill its error icon and its name.
        nombreDesconocida: (nombre) => nombre.toUpperCase(),
      };
      let controlador!: ControladorEditor;
      let soloLectura = false;
      let fila = 0;
      /** What the backend refused on the last save, as the summary says it; it goes with the next edit. */
      let refusados: ProblemaDelMensaje[] = [];

      const tope = (): number => configuracion.tope_mensaje;
      const textoActual = (): string => textoDeMensaje(controlador.expresion());
      const tramos = (): HTMLTextAreaElement[] => [...raizEditor.querySelectorAll<HTMLTextAreaElement>('[data-linea] [data-tramo]')];

      /** Puts the caret over the first emoji, in the text run that has it: where the error says it is. */
      function irAlEmoji(): void {
        for (const area of tramos()) {
          const encontrado = primerEmoji(area.value);
          if (!encontrado) continue;
          area.focus();
          area.setSelectionRange(encontrado.indice, encontrado.indice + encontrado.caracter.length);
          return;
        }
      }

      function irAlFinal(): void {
        const ultimo = tramos().at(-1);
        ultimo?.focus();
        ultimo?.setSelectionRange(ultimo.value.length, ultimo.value.length);
      }

      interface ProblemaDelMensaje {
        texto: string;
        ir: () => void;
      }

      /** What the editor found when it validated (the backend's judgement), in the words of this screen where it has them: an unknown macro says so as the rule does (RF-WM-25). */
      function problemasDelEditor(): ProblemaDelMensaje[] {
        const nodos = controlador.expresion().nodos;
        return controlador.estado().problemas.map((problema, indice) => {
          const nodo = problema.ubicacion ? nodos[problema.ubicacion.nodo] : undefined;
          const macro = problema.codigo === 'variable_desconocida' && nodo?.tipo === 'variable' ? numeroDeMacro(nodo.nombre) : null;
          const texto =
            macro === null
              ? mensajeProblema(problema)
              : t('whatsmkt.codigo.macro_inexistente', { macro: `[$MACRO${(nodo as { nombre: string }).nombre.slice(5)}$]`, n: datos.macros.length });
          return { texto, ir: () => controlador.irAProblema(indice) };
        });
      }

      /** The rules the backend applies when it saves: the first emoji with its position (RF-WM-24) and the limit (RF-WM-26). */
      function problemasDeGuardado(): ProblemaDelMensaje[] {
        const texto = textoActual();
        const lista: ProblemaDelMensaje[] = [];
        const emoji = primerEmoji(texto);
        if (emoji) lista.push({ texto: t('whatsmkt.codigo.mensaje_con_emoji', { caracter: emoji.caracter, posicion: emoji.posicion }), ir: irAlEmoji });
        const largo = largoDelMensaje(texto);
        if (largo > tope()) lista.push({ texto: t('whatsmkt.codigo.mensaje_largo', { largo, maximo: tope() }), ir: irAlFinal });
        return lista;
      }

      function pintarProblemas(): void {
        const propios = problemasDeGuardado();
        // What the backend refused and this summary does not already say (its sentence is another).
        const dichos = new Set([...problemasDelEditor(), ...propios].map((problema) => problema.texto));
        const todos = [...problemasDelEditor(), ...propios, ...refusados.filter((problema) => !dichos.has(problema.texto))];
        resumen.hidden = todos.length === 0;
        panel.classList.toggle('wm-resumen-activo', refusados.length > 0 && !resumen.hidden);
        tituloResumen.textContent = todos.length === 1 ? t('editorTexto.resumen.uno') : t('editorTexto.resumen.varios', { n: todos.length });
        listaResumen.replaceChildren(
          ...todos.map((problema, indice) => {
            const item = nodo('li');
            const texto = nodo('span');
            texto.id = `${prefijo}-problema-${indice}`;
            texto.textContent = problema.texto;
            const ir = nodo('button', 'editor-texto__ir');
            ir.type = 'button';
            ir.textContent = t('editorTexto.resumen.ir');
            ir.setAttribute('aria-describedby', texto.id);
            ir.addEventListener('click', problema.ir);
            item.append(texto, ' ', ir);
            return item;
          }),
        );
        const emoji = primerEmoji(textoActual());
        errorDeEmoji.textContent = emoji ? t('whatsmkt.codigo.mensaje_con_emoji', { caracter: emoji.caracter, posicion: emoji.posicion }) : '';
        // The text run that holds the emoji is marked invalid; only the mark this put is taken off.
        tramos().forEach((area) => {
          if (primerEmoji(area.value)) {
            area.setAttribute('aria-invalid', 'true');
            area.dataset.emoji = '';
          } else if ('emoji' in area.dataset) {
            delete area.dataset.emoji;
            area.removeAttribute('aria-invalid');
          }
        });
      }

      function pintarVista(): void {
        tituloVista.textContent = t('whatsmkt.mensaje.vistaPrevia');
        rotuloFila.textContent = t('whatsmkt.mensaje.filaEjemplo');
        const ejemplos = datos.ejemplos ?? [];
        campoFila.hidden = ejemplos.length === 0;
        selectFila.replaceChildren(
          ...ejemplos.map((_, i) => {
            const opcion = nodo('option');
            opcion.value = String(i);
            opcion.textContent = String(i + 1);
            return opcion;
          }),
        );
        fila = Math.min(fila, Math.max(0, ejemplos.length - 1));
        selectFila.value = String(fila);
        notaVista.textContent = datos.id === null ? '' : datos.ejemplos === null ? t('whatsmkt.mensaje.sinFilasEjemplo') : '';
        const partes = partesDeLaVista(textoActual(), ejemplos[fila] ? ejemplos[fila].slice(1) : [], configuracion.whatsapp_contacto, t('whatsmkt.mensaje.sinWhatsapp'));
        cuerpoVista.replaceChildren(
          ...partes.map((parte) => {
            if (!parte.apagado) return document.createTextNode(parte.texto);
            const apagado = nodo('span', 'muted');
            apagado.textContent = parte.texto;
            return apagado;
          }),
        );
      }

      function pintar(): void {
        sinMacros.textContent = datos.id === null ? t('whatsmkt.mensaje.sinMacros') : '';
        sinMacros.hidden = datos.id !== null;
        pintarProblemas();
        pintarVista();
      }

      function alEvento(evento: Event): void {
        // The editor emits as it mounts, before `montarEditor` hands the controller back.
        if ((controlador as ControladorEditor | undefined) === undefined) return;
        // A change of the person's own, not the one the component made showing a text: that one is not an unsaved change.
        if ((evento as CustomEvent<EstadoEditor>).detail.origen === 'usuario') {
          refusados = [];
          alCambiar();
        }
        pintar();
      }

      /** A save refused for its content: the summary gets what was refused and takes the focus (§13.6). */
      function alRechazar(problemas: ProblemaTexto[]): void {
        // The module's own sentence for its codes; for a rule this build does not know, the backend's detail says more than the generic text.
        refusados = problemas.map((problema) => ({
          texto: textoDeProblemaDelMensaje(problema) ?? (problema.codigo === 'regla_del_contexto' ? problema.detalle : mensajeProblema(problema)),
          ir: () => tramos()[0]?.focus(),
        }));
        pintar();
        resumen.focus();
      }

      /** Mounts the engine's editor on the root it has now, with the text and the mode that are on screen. */
      async function montar(expresion: Expresion | null): Promise<void> {
        // Under the line of text runs and the errors of the editor's own: where an error of a run is said.
        raizEditor.querySelector('[data-error-tramo]')!.after(errorDeEmoji);
        raizEditor.addEventListener(EVENTO_EXPRESION, alEvento);
        opcionesEditor.expresion = expresion;
        opcionesEditor.soloLectura = soloLectura;
        controlador = await montarEditor(raizEditor, opcionesEditor);
      }

      selectFila.addEventListener('change', () => {
        fila = Number(selectFila.value);
        pintarVista();
      });

      await montar(null);

      const editor = {
        /** The configuration changed: the words follow it, and with another default definition or limit the context itself is another. */
        async repintar(contextoCambio = false): Promise<void> {
          opcionesEditor.sinFunciones = palabrasSinFunciones();
          if (contextoCambio) {
            const expresion = controlador.expresion();
            controlador.destruir();
            raizEditor.removeEventListener(EVENTO_EXPRESION, alEvento);
            // The catalogue of this context is built per request (its macros and its limit follow the configuration), and the client keeps one per context.
            olvidarCatalogo(CONTEXTO_MENSAJE);
            const nueva = intacta.cloneNode(true) as HTMLElement;
            raizEditor.replaceWith(nueva);
            raizEditor = nueva;
            await montar(expresion);
          }
          pintar();
        },
        fijar(contenido: ContenidoTexto | null, lectura: boolean): void {
          soloLectura = lectura;
          refusados = [];
          controlador.fijarExpresion(expresionDeMensaje(String(contenido?.texto ?? '')));
          controlador.fijarSoloLectura(lectura);
          pintar();
        },
        leer: (): ContenidoTexto => ({ texto: textoActual() }),
        destruir(): void {
          editores.delete(editor);
          alRechazarDe.delete(prefijo);
          panel.classList.remove('wm-resumen-activo');
          controlador.destruir();
          raizEditor.removeEventListener(EVENTO_EXPRESION, alEvento);
          // The editor goes back to where the page keeps it, so the next factory finds it.
          document.querySelector(ALMACEN)?.append(raizEditor);
          anfitrion.replaceChildren();
        },
        enfocar(): void {
          if (!resumen.hidden) resumen.focus();
          else tramos()[0]?.focus();
        },
      };
      editores.add(editor);
      alRechazarDe.set(prefijo, alRechazar);
      pintar();
      return editor;
    };
  }

  // ---- The two panels of saved texts -----------------------------------------------------------------------------

  /** «Preventivo · Oferta de octubre» for the text that is a segment's message; the name alone for any other. */
  const etiquetaDe = (texto: ResumenTexto): string => {
    const segmento = segmentos.find((s) => s.texto_guardado_id === texto.id);
    if (!segmento || segmento.etiqueta === texto.nombre) return texto.nombre;
    return `${texto.nombre} · ${segmento.etiqueta}`;
  };

  const opcionesComunes = { contexto: CONTEXTO_MENSAJE, textoDeProblema: textoDeProblemaDelMensaje };

  controladores = {
    segmentos: await montarTextosGuardados(opciones.raizSegmentos, {
      ...opcionesComunes,
      titulo: t('whatsmkt.mensaje.porSegmento'),
      editor: fabricaDeEditor('wm-msg-segmento', opciones.raizSegmentos),
      alRechazar: (problemas) => alRechazarDe.get('wm-msg-segmento')?.(problemas),
      etiquetaDe,
    }),
    globales: await montarTextosGuardados(opciones.raizGlobales, {
      ...opcionesComunes,
      titulo: t('whatsmkt.mensaje.globales'),
      editor: fabricaDeEditor('wm-msg-global', opciones.raizGlobales),
      alRechazar: (problemas) => alRechazarDe.get('wm-msg-global')?.(problemas),
      etiquetaDe,
      // The global messages are the ones no segment owns.
      filtrar: (texto) => !vinculadoASegmento(texto.id),
    }),
  };

  // Panel 2's hint belongs to its panel, which the component draws: it goes at the top of its body.
  const pista = nodo('p', 'field__hint');
  pista.dataset.i18n = 'whatsmkt.configuracion.globalesHint';
  pista.textContent = t('whatsmkt.configuracion.globalesHint');
  opciones.raizGlobales.querySelector('.textos__cuerpo')?.prepend(pista);

  // ---- Panel 1: the segment whose message is edited, and the link ---------------------------------------------------

  const botones = opciones.bloqueSegmentos.querySelector<HTMLElement>('[data-segmentos-mensaje]')!;
  const textoVinculo = opciones.bloqueSegmentos.querySelector<HTMLElement>('[data-vinculo-texto]')!;
  const botonUsar = opciones.bloqueSegmentos.querySelector<HTMLButtonElement>('[data-vinculo-usar]')!;
  const selectDelComponente = (): HTMLSelectElement | null => opciones.raizSegmentos.querySelector<HTMLSelectElement>('[data-textos-select]');

  const segmentoActivo = (): SegmentoWhatsmkt | undefined => segmentos.find((s) => s.clave === activo);
  const textoElegido = (): EstadoTextos | null => controladores.segmentos?.estado() ?? null;

  function pintarVinculo(): void {
    const segmento = segmentoActivo();
    if (!segmento) {
      textoVinculo.textContent = '';
      botonUsar.hidden = true;
      return;
    }
    const propio = textos.find((x) => x.id === segmento.texto_guardado_id);
    textoVinculo.textContent = propio
      ? t('whatsmkt.configuracion.mensajeDelSegmento', { segmento: segmento.etiqueta, nombreCitado: citado(propio.nombre) })
      : t('whatsmkt.configuracion.sinMensajeDelSegmento', { segmento: segmento.etiqueta });
    const elegido = textoElegido();
    botonUsar.textContent = t('whatsmkt.configuracion.usarComoMensaje', { segmento: segmento.etiqueta });
    // Only a saved, enabled text that is not already its message can become it; otherwise the button is not there (the line above says it).
    botonUsar.hidden = !elegido || elegido.id === null || elegido.modo === 'deshabilitado' || elegido.id === segmento.texto_guardado_id;
  }

  function pintarSegmentos(): void {
    botones.replaceChildren(
      ...segmentos.map((segmento) => {
        const boton = nodo('button', 'segmented__item');
        boton.type = 'button';
        boton.dataset.segmento = segmento.clave;
        boton.textContent = segmento.etiqueta;
        boton.setAttribute('aria-pressed', String(segmento.clave === activo));
        boton.addEventListener('click', () => void elegirSegmento(segmento.clave));
        return boton;
      }),
    );
    botones.setAttribute('aria-label', t('whatsmkt.configuracion.segmentoDelMensaje'));
    // The box scrolls sideways when the names do not fit: the open one is kept in sight (without moving the page).
    const abierto = botones.querySelector<HTMLElement>('[aria-pressed="true"]');
    if (abierto) botones.scrollLeft = abierto.offsetLeft - (botones.clientWidth - abierto.offsetWidth) / 2;
    pintarVinculo();
  }

  /** Opens the text that is the segment's message in the component: it is its own `select`, driven as a person would. */
  async function elegirSegmento(clave: string): Promise<void> {
    activo = clave;
    pintarSegmentos();
    const id = segmentoActivo()?.texto_guardado_id;
    const select = selectDelComponente();
    if (id === null || id === undefined || !select || select.value === String(id)) return;
    if (![...select.options].some((opcion) => opcion.value === String(id))) return;
    select.value = String(id);
    select.dispatchEvent(new Event('change'));
    // The component may ask about unsaved changes first and stay where it was: the link says what is on screen.
    window.setTimeout(pintarVinculo, 0);
  }

  async function cargarTextos(): Promise<void> {
    try {
      textos = await listarTextos(CONTEXTO_MENSAJE, true);
    } catch {
      // The names only decorate the sentence of the link: without them it says the segment has none chosen.
      textos = [];
    }
    pintarVinculo();
  }

  botonUsar.addEventListener(
    'click',
    async () => {
      const segmento = segmentoActivo();
      const elegido = textoElegido();
      if (!segmento || !elegido || elegido.id === null) return;
      botonUsar.disabled = true;
      try {
        // The body repeats what is saved and adds only the link of this segment: the others keep theirs (the body leaves out `texto_guardado_id`).
        const nuevos = await guardarSegmentos(
          segmentos.map((s) => ({
            clave: s.clave,
            etiqueta: s.etiqueta,
            desde: s.desde,
            hasta: s.hasta,
            ...(s.clave === segmento.clave ? { texto_guardado_id: elegido.id } : {}),
          })),
        );
        segmentos = nuevos;
        opciones.alVincular(nuevos);
        // The label of the options and the list of the global ones follow the link, without asking the lists again.
        controladores.segmentos?.repintar();
        controladores.globales?.repintar();
        await cargarTextos();
        textoVinculo.textContent = t('whatsmkt.configuracion.mensajeVinculado', { nombreCitado: citado(elegido.nombre ?? ''), segmento: segmento.etiqueta });
        // The button went away with the link: the focus goes to the list of texts, where the next thing to do is.
        selectDelComponente()?.focus();
      } catch (caido) {
        textoVinculo.textContent = mensajeDeError(caido);
        pintarVinculo();
      }
    },
    escucha,
  );

  // The button of the link follows what the first panel shows.
  opciones.raizSegmentos.addEventListener(EVENTO_TEXTOS, pintarVinculo, escucha);

  /**
   * What one panel did (saved, created, renamed, enabled, disabled or deleted a text) shows in the other without throwing away what
   * is being typed there. The component says each result in its status region, so only a real action asks the lists again, and
   * choosing another text does not.
   */
  function sincronizar(origen: HTMLElement, otro: () => ControladorTextos | null): void {
    const anuncio = origen.querySelector<HTMLElement>('[data-textos-anuncio]');
    if (!anuncio) return;
    const observador = new MutationObserver(() => {
      if (!anuncio.textContent) return;
      const destino = otro();
      if (destino && !destino.hayCambios()) void destino.recargar();
      void cargarTextos();
    });
    observador.observe(anuncio, { childList: true, characterData: true, subtree: true });
    alta.signal.addEventListener('abort', () => observador.disconnect());
  }
  sincronizar(opciones.raizSegmentos, () => controladores.globales);
  sincronizar(opciones.raizGlobales, () => controladores.segmentos);

  document.addEventListener(
    'languagechange',
    () => {
      pintarSegmentos();
      editores.forEach((editor) => editor.repintar());
      pista.textContent = t('whatsmkt.configuracion.globalesHint');
    },
    escucha,
  );

  pintarSegmentos();
  void cargarDatos();
  void cargarTextos().then(() => void elegirSegmento(activo));

  return {
    configuracionCambio(nueva) {
      // With another default definition or another limit the context the editors read is another: they mount again.
      const contextoCambio = nueva.definicion_defecto_id !== contexto.definicion || nueva.tope_mensaje !== contexto.tope;
      contexto = { definicion: nueva.definicion_defecto_id, tope: nueva.tope_mensaje };
      configuracion = nueva;
      editores.forEach((editor) => void editor.repintar(contextoCambio));
      void cargarDatos();
    },
    segmentosCambiaron(nuevos) {
      // The table only edits labels and limits: the links are the ones this module keeps.
      segmentos = nuevos;
      pintarSegmentos();
      controladores.segmentos?.repintar();
      controladores.globales?.repintar();
    },
    destruir() {
      alta.abort();
      controladores.segmentos?.destruir();
      controladores.globales?.destruir();
      editores.clear();
    },
  };
}
