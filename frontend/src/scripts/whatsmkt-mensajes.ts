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
import { previsualizarTexto } from '../lib/api-texto-enriquecido';
import { listarTextos, type ContenidoTexto, type ResumenTexto } from '../lib/api-textos-guardados';
import { guardarSegmentos, type ConfiguracionWhatsmkt, type SegmentoWhatsmkt } from '../lib/api-whatsmkt';
import { guardadaDesdeRespuesta } from '../lib/constructor-columnas';
import { t } from '../lib/i18n';
import {
  MARCADOR_WHATSAPP,
  largoDelMensaje,
  macrosDeLaDefinicion,
  partesDeLaVista,
  primerEmoji,
  primeraMacroInexistente,
  textoDeMacro,
  textoDeProblemaDelMensaje,
  type EmojiEncontrado,
  type MacroDeDefinicion,
} from '../lib/whatsmkt-mensaje';
import { EVENTO_TEXTOS, montarTextosGuardados, type ControladorTextos, type EstadoTextos, type FabricaEditor } from './textos-guardados';

export const CONTEXTO_MENSAJE = 'whatsmkt.mensaje';
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
  let segmentos = opciones.segmentos;
  let textos: ResumenTexto[] = [];
  let activo = segmentos[0]?.clave ?? '';
  let datos: DatosDeLaDefinicion = { id: null, macros: [], ejemplos: null };
  const alta = new AbortController();
  const escucha = { signal: alta.signal };
  const editores = new Set<{ repintar: () => void }>();
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

  // ---- The editor of a message (§5.1) ----------------------------------------------------------------------------

  function fabricaDeEditor(prefijo: string): FabricaEditor {
    return (anfitrion, { alCambiar }) => {
      const barra = nodo('div', 'wm-editor__barra');
      barra.setAttribute('role', 'group');
      const rotulo = nodo('label', 'field__label');
      rotulo.htmlFor = `${prefijo}-texto`;
      const area = nodo('textarea', 'input wm-editor__campo');
      area.id = `${prefijo}-texto`;
      area.rows = 4;
      area.spellcheck = true;
      area.setAttribute('aria-describedby', `${prefijo}-contador ${prefijo}-error`);
      const contador = nodo('p', 'wm-contador');
      contador.id = `${prefijo}-contador`;
      const anuncio = nodo('p', 'visually-hidden');
      anuncio.setAttribute('role', 'status');
      // One line per problem, in the order of the interface rules (§5.1): the macro, the emoji, the length.
      const errores = nodo('div', 'wm-editor__errores');
      errores.id = `${prefijo}-error`;
      errores.setAttribute('role', 'alert');
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
      const raiz = nodo('div', 'wm-editor');
      raiz.append(barra, rotulo, area, contador, anuncio, errores, vista);
      anfitrion.replaceChildren(raiz);

      let soloLectura = false;
      let paso = false;
      let emoji: EmojiEncontrado | null = null;
      let fila = 0;
      let errorVisible = false;

      const tope = (): number => configuracion.tope_mensaje;

      function pintarBarra(): void {
        barra.setAttribute('aria-label', t('whatsmkt.mensaje.insertarMacro'));
        const botones: Node[] = [];
        if (datos.id === null) {
          const aviso = nodo('p', 'field__hint wm-editor__aviso');
          aviso.textContent = t('whatsmkt.mensaje.sinMacros');
          botones.push(aviso);
        }
        for (const macro of datos.macros) {
          const boton = nodo('button', 'btn btn--sm');
          boton.type = 'button';
          boton.textContent = textoDeMacro(macro);
          boton.disabled = soloLectura;
          boton.addEventListener('click', () => insertar(`[$MACRO${macro.n}$]`));
          botones.push(boton);
        }
        if (datos.macros.length > 0) {
          const separador = nodo('span', 'wm-editor__separador');
          separador.textContent = '|';
          separador.setAttribute('aria-hidden', 'true');
          botones.push(separador);
        }
        const whatsapp = nodo('button', 'btn btn--sm');
        whatsapp.type = 'button';
        whatsapp.textContent = t('whatsmkt.mensaje.insertarWhatsapp');
        whatsapp.disabled = soloLectura;
        whatsapp.addEventListener('click', () => insertar(MARCADOR_WHATSAPP));
        botones.push(whatsapp);
        barra.replaceChildren(...botones);
      }

      /** Writes `texto` where the cursor is (or over what is selected) and gives the focus back to the field. */
      function insertar(texto: string): void {
        if (soloLectura) return;
        area.focus();
        area.setRangeText(texto, area.selectionStart, area.selectionEnd, 'end');
        alEscribir();
      }

      function pintarContador(): void {
        const largo = largoDelMensaje(area.value);
        const excede = largo > tope();
        contador.textContent = t('whatsmkt.mensaje.largo', { largo, maximo: tope() });
        contador.dataset.excede = String(excede);
        // The announcement is said only when the limit is crossed, not at every key.
        if (excede !== paso) {
          paso = excede;
          anuncio.textContent = excede ? t('whatsmkt.mensaje.pasoElTope', { largo, maximo: tope() }) : '';
        }
      }

      /**
       * What is wrong with the text, every problem and in this order (§5.1): the first macro the definition lacks (RF-WM-25), the first emoji
       * with its position (RF-WM-24) and the length over the limit (RF-WM-26). The red counter does not replace the last one.
       */
      function pintarError(): void {
        emoji = primerEmoji(area.value);
        const macro = datos.id === null ? null : primeraMacroInexistente(area.value, datos.macros.length);
        const largo = largoDelMensaje(area.value);
        const lineas: HTMLElement[] = [];
        const linea = (texto: string): HTMLElement => {
          const p = nodo('p', 'field__error');
          p.textContent = texto;
          lineas.push(p);
          return p;
        };
        if (macro) linea(t('whatsmkt.codigo.macro_inexistente', { macro, n: datos.macros.length }));
        if (emoji) {
          const delEmoji = linea(t('whatsmkt.codigo.mensaje_con_emoji', { caracter: emoji.caracter, posicion: emoji.posicion }));
          // The cursor goes where the error says: over the emoji it names. The move waits for the event to end: inside it the browser gives
          // the focus back to the line, and the field's `focusout` would then redraw the lines and drop the focus on the page.
          delEmoji.dataset.emoji = '';
          delEmoji.tabIndex = -1;
          delEmoji.addEventListener('focus', () =>
            window.setTimeout(() => {
              area.focus();
              if (emoji) area.setSelectionRange(emoji.indice, emoji.indice + emoji.caracter.length);
            }, 0),
          );
        }
        if (largo > tope()) linea(t('whatsmkt.codigo.mensaje_largo', { largo, maximo: tope() }));
        errores.replaceChildren(...(errorVisible ? lineas : []));
        if (errorVisible && lineas.length > 0) area.setAttribute('aria-invalid', 'true');
        else area.removeAttribute('aria-invalid');
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
        const partes = partesDeLaVista(area.value, ejemplos[fila] ? ejemplos[fila].slice(1) : [], configuracion.whatsapp_contacto, t('whatsmkt.mensaje.sinWhatsapp'));
        cuerpoVista.replaceChildren(
          ...partes.map((parte) => {
            if (!parte.apagado) return document.createTextNode(parte.texto);
            const apagado = nodo('span', 'muted');
            apagado.textContent = parte.texto;
            return apagado;
          }),
        );
      }

      function crecer(): void {
        area.style.height = 'auto';
        area.style.height = `${area.scrollHeight}px`;
      }

      function repintar(): void {
        pintarBarra();
        rotulo.textContent = t('whatsmkt.mensaje.global');
        pintarContador();
        pintarError();
        pintarVista();
        crecer();
      }

      function alEscribir(): void {
        pintarContador();
        // Once an error is there it follows what is typed; a new one waits for the field to be left.
        if (errorVisible) pintarError();
        pintarVista();
        crecer();
        alCambiar();
      }

      area.addEventListener('input', alEscribir);
      selectFila.addEventListener('change', () => {
        fila = Number(selectFila.value);
        pintarVista();
      });
      // Leaving the field says its errors, except on the way to «Guardar»: there the answer of the save is what is said, and a message
      // that appeared and moved the button would lose the click.
      area.addEventListener('focusout', (evento) => {
        const destino = evento.relatedTarget;
        if (destino instanceof HTMLElement && destino.matches('[data-textos-guardar]')) return;
        errorVisible = true;
        pintarError();
      });

      const editor = {
        repintar,
        fijar(contenido: ContenidoTexto | null, lectura: boolean): void {
          soloLectura = lectura;
          area.value = String(contenido?.texto ?? '');
          area.readOnly = lectura;
          errorVisible = false;
          // A text that opens already over the limit is not a crossing: only what is typed past it is announced.
          paso = largoDelMensaje(area.value) > tope();
          anuncio.textContent = '';
          repintar();
        },
        leer: (): ContenidoTexto => ({ texto: area.value }),
        destruir(): void {
          editores.delete(editor);
          anfitrion.replaceChildren();
        },
        enfocar(): void {
          // After a refused save the cursor goes to the first emoji, as the error says.
          const rechazado = primerEmoji(area.value);
          area.focus();
          if (rechazado) area.setSelectionRange(rechazado.indice, rechazado.indice + rechazado.caracter.length);
        },
      };
      editores.add(editor);
      repintar();
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
      editor: fabricaDeEditor('wm-msg-segmento'),
      etiquetaDe,
    }),
    globales: await montarTextosGuardados(opciones.raizGlobales, {
      ...opcionesComunes,
      titulo: t('whatsmkt.mensaje.globales'),
      editor: fabricaDeEditor('wm-msg-global'),
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
      configuracion = nueva;
      editores.forEach((editor) => editor.repintar());
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
