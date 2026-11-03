/**
 * Behaviour of the saved-texts component (RF-69, docs/motor-texto-enriquecido-interfaz.md §11.3): the texts of
 * one context, their versions, and what can be done with them. The markup is `components/TextosGuardados.astro`;
 * the module that uses it hands over the root and the editor of the content, and decides what the content means.
 *
 *     const textos = await montarTextosGuardados(raiz, { contexto, editor, titulo });
 *     textos.destruir();
 *
 * The backend decides: names are unique per context, a used text cannot be deleted, a disabled one takes no new
 * version. This only shows the list and sends what was chosen; a refusal is read by its `codigo`, never by its
 * text. No version is ever modified: saving creates the next one, and an old one is read-only until «Usar como
 * base» makes it the starting point of a new one.
 */

import { ApiError, mensajeDeError } from '../lib/api';
import {
  agregarVersion,
  crearTexto,
  deshabilitarTexto,
  eliminarTexto,
  habilitarTexto,
  listarContextos,
  listarTextos,
  obtenerTexto,
  renombrarTexto,
  type ContenidoTexto,
  type ContextoGuardado,
  type ProblemaTexto,
  type ResumenTexto,
  type TextoRespuesta,
} from '../lib/api-textos-guardados';
import { openWhenFree } from '../lib/dialogs';
import { confirmarDescartar } from './confirmar-descartar';
import { t, traducirPorPrefijo } from '../lib/i18n';
import {
  clasificarError,
  descartar,
  esEditable,
  hayNombreNuevo,
  iguales,
  listaConNombre,
  modoInicial,
  problemasPorCampo,
  puedeEliminar,
  puedeGuardar,
  repartir,
  usarComoBase,
  vecinoDe,
  versionAlGuardar,
  visibles,
  type ModoTexto,
} from '../lib/textos-guardados';

/** The longest name the backend takes (`LARGO_MAXIMO_NOMBRE` of the saved texts): it only goes into the sentence of a refused name. */
const LARGO_MAXIMO_NOMBRE = 120;

/** Fired on the root when what is on screen changes: another text or version, or a change that is not saved. */
export const EVENTO_TEXTOS = 'textoscambiados';

export interface EstadoTextos {
  /** `null` is a text that has not been saved. */
  id: number | null;
  version: number | null;
  nombre: string | null;
  modo: ModoTexto;
  hayCambios: boolean;
}

/** How the content is edited. The module builds it; the component never looks inside the content. */
export interface EditorDelTexto {
  /**
   * Shows `contenido` (`null` is an empty one, for a text that is not saved yet), editable or not. It takes effect at
   * once: `leer()` right after reads what was just shown.
   */
  fijar(contenido: ContenidoTexto | null, soloLectura: boolean): void;
  /** The content as it would be sent. */
  leer(): ContenidoTexto;
  destruir(): void;
  /** Puts the focus on the editor, if it can. */
  enfocar?(): void;
}

export interface OpcionesEditor {
  /** The shape of the content the context keeps: an engine expression or a plain text. */
  tipo: ContextoGuardado['tipo'];
  /** Tell the component the content changed by hand. */
  alCambiar: () => void;
}

export type FabricaEditor = (anfitrion: HTMLElement, opciones: OpcionesEditor) => EditorDelTexto | Promise<EditorDelTexto>;

export interface OpcionesTextos {
  /** The key of a context the module registered (`GET /textos-guardados/contextos`). */
  contexto: string;
  editor: FabricaEditor;
  /** The panel's heading, in the module's words («Mensajes globales»). */
  titulo: string;
  /** What the module adds to the option of a text: «Preventivo · versión 2». By default, the name. */
  etiquetaDe?: (texto: ResumenTexto) => string;
  /** How many times a version was used, for «usada en 2 campañas». The API only says whether it was. */
  usos?: (texto: TextoRespuesta, version: number) => number | null;
  /** The confirmation of deleting: the module's words. */
  eliminar?: { titulo: (nombre: string) => string; cuerpo: string };
  /** The module's own sentence for a problem of the content, or `null` for the default one. */
  textoDeProblema?: (problema: ProblemaTexto) => string | null;
  /**
   * Which texts the panel offers, in the list of the enabled ones and in the folded list of the disabled ones. It is asked every
   * time the panel is drawn (see `repintar`), so a link that changed without mounting again is reflected. A text that is open and
   * stops passing it stays open until another one is chosen; it only leaves the `select`. Without it, every text is offered.
   */
  filtrar?: (texto: ResumenTexto) => boolean;
}

export interface ControladorTextos {
  estado(): EstadoTextos;
  /** Whether what is on screen differs from what is saved. */
  hayCambios(): boolean;
  /** Asks before leaving what has changed; `true` means go ahead. For the module that is about to leave. */
  confirmarSalida(): Promise<boolean>;
  /** Reads the lists again, and the text on screen if it still exists. */
  recargar(): Promise<void>;
  /** Draws the panel again without asking the API: the module's `filtrar` is evaluated again. */
  repintar(): void;
  destruir(): void;
}

export async function montarTextosGuardados(raiz: HTMLElement, opciones: OpcionesTextos): Promise<ControladorTextos> {
  const q = <T extends Element>(selector: string) => raiz.querySelector<T>(selector)!;
  const alta = new AbortController();
  const escucha = { signal: alta.signal };
  const el = {
    titulo: q<HTMLElement>('[data-textos-titulo]'),
    error: q<HTMLElement>('[data-textos-error]'),
    reintentar: q<HTMLButtonElement>('[data-textos-reintentar]'),
    select: q<HTMLSelectElement>('[data-textos-select]'),
    nuevo: q<HTMLButtonElement>('[data-textos-nuevo]'),
    renombrar: q<HTMLButtonElement>('[data-textos-renombrar]'),
    deshabilitar: q<HTMLButtonElement>('[data-textos-deshabilitar]'),
    eliminar: q<HTMLButtonElement>('[data-textos-eliminar]'),
    motivo: q<HTMLElement>('[data-textos-motivo]'),
    campoNombre: q<HTMLElement>('[data-textos-campo-nombre]'),
    nombre: q<HTMLInputElement>('[data-textos-nombre]'),
    nombreError: q<HTMLElement>('[data-textos-nombre-error]'),
    versionFila: q<HTMLElement>('[data-textos-version-fila]'),
    version: q<HTMLElement>('[data-textos-version]'),
    tagDeshabilitado: q<HTMLElement>('[data-textos-tag-deshabilitado]'),
    campoVersiones: q<HTMLElement>('[data-textos-campo-versiones]'),
    versiones: q<HTMLSelectElement>('[data-textos-versiones]'),
    aviso: q<HTMLElement>('[data-textos-aviso]'),
    avisoTexto: q<HTMLElement>('[data-textos-aviso-texto]'),
    irVigente: q<HTMLButtonElement>('[data-textos-ir-vigente]'),
    usarBase: q<HTMLButtonElement>('[data-textos-usar-base]'),
    editor: q<HTMLElement>('[data-textos-editor]'),
    problemas: q<HTMLElement>('[data-textos-problemas]'),
    pie: q<HTMLElement>('[data-textos-pie]'),
    guardar: q<HTMLButtonElement>('[data-textos-guardar]'),
    descartar: q<HTMLButtonElement>('[data-textos-descartar]'),
    hint: q<HTMLElement>('[data-textos-hint]'),
    anuncio: q<HTMLElement>('[data-textos-anuncio]'),
    deshab: q<HTMLDetailsElement>('[data-textos-deshab]'),
    deshabTitulo: q<HTMLElement>('[data-textos-deshab-titulo]'),
    deshabLista: q<HTMLElement>('[data-textos-deshab-lista]'),
  };
  const dialogos = {
    renombrar: q<HTMLDialogElement>('[data-textos-dialogo="renombrar"]'),
    eliminar: q<HTMLDialogElement>('[data-textos-dialogo="eliminar"]'),
    cambios: q<HTMLDialogElement>('[data-textos-dialogo="cambios"]'),
  };
  const ren = {
    form: q<HTMLFormElement>('[data-textos-renombrar-form]'),
    titulo: q<HTMLElement>('[data-textos-renombrar-titulo]'),
    nombre: q<HTMLInputElement>('[data-textos-renombrar-nombre]'),
    error: q<HTMLElement>('[data-textos-renombrar-error]'),
    confirmar: q<HTMLButtonElement>('[data-textos-renombrar-confirmar]'),
  };
  const eli = {
    titulo: q<HTMLElement>('[data-textos-eliminar-titulo]'),
    cuerpo: q<HTMLElement>('[data-textos-eliminar-cuerpo]'),
    casilla: q<HTMLInputElement>('[data-textos-eliminar-casilla]'),
    error: q<HTMLElement>('[data-textos-eliminar-error]'),
    aceptar: q<HTMLButtonElement>('[data-textos-eliminar-aceptar]'),
  };

  const s = {
    contexto: null as ContextoGuardado | null,
    /** The enabled texts, by name. */
    lista: [] as ResumenTexto[],
    deshabilitados: [] as ResumenTexto[],
    /** What is on screen as saved (the version being looked at); `null` is a text not saved yet. */
    texto: null as TextoRespuesta | null,
    modo: 'nuevo' as ModoTexto,
    /** What the editor held when the text was shown: what «changed» is measured against. */
    inicial: {} as ContenidoTexto,
    problemas: { nombre: [] as ProblemaTexto[], contenido: [] as ProblemaTexto[] },
    nombreRepetido: false,
    guardando: false,
    renombrando: false,
    eliminando: false,
    /** The text the delete dialog is about, from the select or from a row of the disabled ones. */
    aEliminar: null as { id: number; nombre: string } | null,
    /** Disabled texts the backend refused to delete because a version was used: their button is gone for good. */
    usados: new Set<number>(),
  };

  let editor: EditorDelTexto | null = null;

  // ---- Helpers -------------------------------------------------------------------------------

  const nombreDe = () => s.texto?.nombre ?? '';

  /** A name in the quotes of the language («Preventivo» / “Preventivo”), never quotes written in a key. */
  const citado = (nombre: string): string => t('camposAdicionales.nombreCitado', { campo: nombre });

  function anunciar(mensaje: string): void {
    // Emptied first, so the same sentence twice in a row is announced twice.
    el.anuncio.textContent = '';
    requestAnimationFrame(() => {
      el.anuncio.textContent = mensaje;
    });
  }

  function mostrarError(texto: string): void {
    el.error.textContent = texto;
  }

  /** The sentence of a refusal that is not about a field. */
  function textoDeErrorGeneral(error: unknown): string {
    const clasificado = clasificarError(error);
    if (clasificado.tipo === 'deshabilitado') return t('textoEnriquecido.codigo.texto_guardado_deshabilitado');
    if (clasificado.tipo === 'usado') return t('textoEnriquecido.codigo.texto_guardado_usado');
    if (clasificado.tipo === 'no_existe') return t('textoEnriquecido.codigo.texto_guardado_no_encontrado');
    if (clasificado.tipo === 'contexto') return t('textoEnriquecido.codigo.contexto_guardado_desconocido');
    if (clasificado.tipo === 'invalido') return t('textoEnriquecido.codigo.texto_guardado_invalido');
    return mensajeDeError(error);
  }

  const contenidoActual = (): ContenidoTexto => editor?.leer() ?? {};

  function hayCambios(): boolean {
    if (s.modo === 'nuevo') return el.nombre.value.trim() !== '' || !iguales(contenidoActual(), s.inicial);
    if (s.modo === 'editable' || s.modo === 'base') return !iguales(contenidoActual(), s.inicial);
    return false;
  }

  function estado(): EstadoTextos {
    return {
      id: s.texto?.id ?? null,
      version: s.texto?.version.numero ?? null,
      nombre: s.texto?.nombre ?? null,
      modo: s.modo,
      hayCambios: hayCambios(),
    };
  }

  function emitir(): void {
    raiz.dispatchEvent(new CustomEvent<EstadoTextos>(EVENTO_TEXTOS, { detail: estado(), bubbles: true }));
  }

  /** Ask before leaving what has changed; `true` means go ahead. The question is the shared one (`confirmar-descartar.ts`). */
  async function puedoSoltar(): Promise<boolean> {
    return hayCambios() ? confirmarDescartar(dialogos.cambios) : true;
  }

  /** What the panel offers, asked every time it is drawn: the lists are the API's, the filter is the module's. */
  const ofrecidos = () => visibles(s.lista, opciones.filtrar);
  const ofrecidosDeshabilitados = () => visibles(s.deshabilitados, opciones.filtrar);

  const textoDelProblema = (problema: ProblemaTexto): string =>
    opciones.textoDeProblema?.(problema) ?? traducirPorPrefijo('textoEnriquecido.codigo', problema.codigo, problema.detalle);

  // ---- Painting ------------------------------------------------------------------------------

  const etiquetaDeOpcion = (texto: ResumenTexto): string => opciones.etiquetaDe?.(texto) ?? texto.nombre;

  function pintarSelect(): void {
    el.select.replaceChildren();
    const guardado = s.texto !== null;
    const lista = ofrecidos();
    if (!guardado || lista.length === 0) {
      const sinGuardar = document.createElement('option');
      sinGuardar.value = '';
      sinGuardar.textContent = t('textosGuardados.sinGuardar');
      el.select.append(sinGuardar);
    }
    for (const texto of lista) {
      const opcion = document.createElement('option');
      opcion.value = String(texto.id);
      opcion.textContent = etiquetaDeOpcion(texto);
      el.select.append(opcion);
    }
    // A disabled text that is being looked at is not in the list of the enabled: it has its own option, with its state.
    if (s.texto !== null && s.modo === 'deshabilitado') {
      const opcion = document.createElement('option');
      opcion.value = String(s.texto.id);
      opcion.textContent = `${s.texto.nombre} · ${t('textosGuardados.deshabilitado')}`;
      el.select.append(opcion);
    }
    el.select.value = s.texto === null ? '' : String(s.texto.id);
  }

  function pintarAcciones(): void {
    const texto = s.texto;
    const activo = texto !== null && s.modo !== 'deshabilitado';
    const nombre = nombreDe();
    el.renombrar.hidden = !activo;
    el.deshabilitar.hidden = !activo;
    el.renombrar.setAttribute('aria-label', t('textosGuardados.renombrarPara', { nombre }));
    el.deshabilitar.setAttribute('aria-label', t('textosGuardados.deshabilitarPara', { nombre }));
    // Delete is offered only when no version was ever used; otherwise the reason takes its place.
    const eliminable = activo && texto !== null && puedeEliminar(texto);
    el.eliminar.hidden = !eliminable;
    el.eliminar.setAttribute('aria-label', t('textosGuardados.eliminarPara', { nombre }));
    const sinEliminar = activo && !eliminable;
    el.motivo.hidden = !sinEliminar;
    el.motivo.textContent = sinEliminar ? t('textosGuardados.noEliminable') : '';
  }

  function pintarVersion(): void {
    const texto = s.texto;
    el.versionFila.hidden = texto === null;
    el.tagDeshabilitado.hidden = s.modo !== 'deshabilitado';
    if (texto === null) {
      el.campoVersiones.hidden = true;
      return;
    }
    const numero = texto.version.numero;
    const usos = texto.version.usada ? (opciones.usos?.(texto, numero) ?? null) : null;
    el.version.textContent = !texto.version.usada
      ? t('textosGuardados.version', { n: numero })
      : usos === null
        ? t('textosGuardados.versionUsadaSin', { n: numero })
        : usos === 1
          ? t('textosGuardados.versionUsadaUna', { n: numero })
          : t('textosGuardados.versionUsada', { n: numero, usos });
    el.campoVersiones.hidden = texto.versiones.length < 2;
    el.versiones.replaceChildren();
    for (const v of [...texto.versiones].reverse()) {
      const opcion = document.createElement('option');
      opcion.value = String(v.numero);
      opcion.textContent = t(v.numero === texto.version_vigente ? 'textosGuardados.versionOpcionVigente' : 'textosGuardados.versionOpcion', {
        n: v.numero,
      });
      el.versiones.append(opcion);
    }
    el.versiones.value = String(numero);
  }

  function pintarAviso(): void {
    const texto = s.texto;
    const lectura = s.modo === 'lectura' && texto !== null;
    const deshabilitado = s.modo === 'deshabilitado';
    el.aviso.hidden = !lectura && !deshabilitado;
    el.irVigente.hidden = !lectura;
    el.usarBase.hidden = !lectura;
    el.avisoTexto.textContent = lectura
      ? t('textosGuardados.lectura', { vista: texto.version.numero, vigente: texto.version_vigente })
      : deshabilitado
        ? t('textosGuardados.deshabilitadoVer')
        : '';
  }

  function pintarProblemas(): void {
    const lista = s.problemas.contenido;
    el.problemas.hidden = lista.length === 0;
    el.problemas.replaceChildren(
      ...lista.map((p) => {
        const item = document.createElement('li');
        item.className = 'field__error';
        item.textContent = textoDelProblema(p);
        return item;
      }),
    );
    const delNombre = s.nombreRepetido
      ? t('textosGuardados.nombreRepetido')
      : s.problemas.nombre.map(textoDelProblema).join(' ');
    el.nombreError.textContent = delNombre;
    if (delNombre) el.nombre.setAttribute('aria-invalid', 'true');
    else el.nombre.removeAttribute('aria-invalid');
  }

  function pintarPie(): void {
    const reglas = versionAlGuardar(s.texto);
    const cambios = hayCambios();
    const verPie = esEditable(s.modo);
    el.pie.hidden = !verPie;
    el.guardar.disabled = !puedeGuardar(s.modo, cambios, s.guardando);
    el.guardar.dataset.loading = s.guardando ? 'true' : 'false';
    el.descartar.disabled = s.guardando || (!cambios && s.modo !== 'base');
    el.hint.textContent =
      s.modo === 'nuevo'
        ? t('textosGuardados.guardarHintPrimera')
        : s.modo === 'base' && s.texto
          ? t('textosGuardados.guardarHintBase', { nueva: reglas.nueva, base: s.texto.version.numero })
          : t('textosGuardados.guardarHint', { nueva: reglas.nueva, actual: reglas.actual ?? '' });
  }

  function filaDeshabilitada(texto: ResumenTexto): HTMLElement {
    const fila = document.createElement('li');
    fila.className = 'textos__deshab-fila';
    fila.dataset.texto = String(texto.id);
    const nombre = document.createElement('span');
    nombre.className = 'textos__deshab-nombre';
    nombre.textContent = texto.nombre;
    const marca = document.createElement('span');
    marca.className = 'tag tag--neutral';
    marca.append(
      q<HTMLTemplateElement>('[data-textos-icono="deshabilitado"]').content.cloneNode(true),
      document.createTextNode(t('textosGuardados.deshabilitado')),
    );

    const boton = (icono: 'ver' | 'habilitar' | 'eliminar', clave: string, claveAria: string, clase: string) => {
      const nodo = document.createElement('button');
      nodo.type = 'button';
      nodo.className = `btn btn--sm ${clase}`.trim();
      nodo.setAttribute('aria-label', t(claveAria, { nombre: texto.nombre }));
      nodo.append(q<HTMLTemplateElement>(`[data-textos-icono="${icono}"]`).content.cloneNode(true), document.createTextNode(t(clave)));
      return nodo;
    };
    const ver = boton('ver', 'textosGuardados.ver', 'textosGuardados.verPara', '');
    ver.addEventListener('click', () => void verDeshabilitado(texto), escucha);
    const habilitar = boton('habilitar', 'textosGuardados.habilitar', 'textosGuardados.habilitarPara', '');
    habilitar.addEventListener('click', () => void habilitar_(texto), escucha);
    const acciones = document.createElement('div');
    acciones.className = 'textos__acciones';
    acciones.append(ver, habilitar);
    // The list says whether any version was used (`eliminable`, T-HI-B6). `usados` is the safety net: a 409 after all
    // (someone used it since the list was read) takes the button away for good.
    const eliminable = texto.eliminable && !s.usados.has(texto.id);
    if (eliminable) {
      const borrar = boton('eliminar', 'textosGuardados.eliminar', 'textosGuardados.eliminarPara', 'btn--danger');
      borrar.addEventListener('click', () => pedirEliminar(texto.id, texto.nombre), escucha);
      acciones.append(borrar);
    }
    // The name with its tag on one side and the actions on the other; the reason, as a hint, under the row.
    const titulo = document.createElement('div');
    titulo.className = 'textos__deshab-titulo';
    titulo.append(nombre, marca);
    fila.append(titulo, acciones);
    if (!eliminable) {
      const motivo = document.createElement('p');
      motivo.className = 'field__hint textos__deshab-motivo';
      motivo.textContent = t('textosGuardados.noEliminableDeshabilitado');
      fila.append(motivo);
    }
    return fila;
  }

  function pintarDeshabilitados(): void {
    const lista = ofrecidosDeshabilitados();
    el.deshab.hidden = lista.length === 0;
    el.deshabTitulo.textContent = t('textosGuardados.deshabilitados', { n: lista.length });
    el.deshabLista.replaceChildren(...lista.map(filaDeshabilitada));
  }

  function pintar(): void {
    el.titulo.textContent = opciones.titulo;
    pintarSelect();
    pintarAcciones();
    el.campoNombre.hidden = s.modo !== 'nuevo';
    pintarVersion();
    pintarAviso();
    pintarProblemas();
    pintarPie();
    pintarDeshabilitados();
  }

  // ---- Showing a text ------------------------------------------------------------------------

  /** Puts `texto` on screen (`null`: a new one) and what the editor holds as its starting point. */
  function poner(texto: TextoRespuesta | null, modo: ModoTexto = modoInicial(texto)): void {
    s.texto = texto;
    s.modo = modo;
    s.problemas = { nombre: [], contenido: [] };
    s.nombreRepetido = false;
    el.nombre.value = '';
    editor?.fijar(texto?.version.contenido ?? null, !esEditable(modo));
    s.inicial = contenidoActual();
    pintar();
    emitir();
  }

  async function abrirTexto(id: number, version?: number): Promise<boolean> {
    try {
      poner(await obtenerTexto(id, version));
      return true;
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        await recargarListas().catch(() => undefined);
        poner(null);
        mostrarError(t('textoEnriquecido.codigo.texto_guardado_no_encontrado'));
      } else {
        mostrarError(textoDeErrorGeneral(error));
        pintar();
      }
      return false;
    }
  }

  async function recargarListas(): Promise<void> {
    // Both kinds in one request: the enabled ones fill the select, the others the folded list.
    const reparto = repartir(await listarTextos(opciones.contexto, true));
    s.lista = reparto.habilitados;
    s.deshabilitados = reparto.deshabilitados;
  }

  /** The first text, or an empty new one when there is none. */
  async function mostrarPrimero(): Promise<void> {
    const primeros = ofrecidos();
    if (primeros.length > 0) await abrirTexto(primeros[0].id);
    else poner(null);
  }

  // ---- Actions -------------------------------------------------------------------------------

  el.select.addEventListener(
    'change',
    async () => {
      const elegido = el.select.value;
      if (!(await puedoSoltar())) {
        pintarSelect();
        return;
      }
      mostrarError('');
      if (elegido === '') poner(null);
      else await abrirTexto(Number(elegido));
    },
    escucha,
  );

  el.versiones.addEventListener(
    'change',
    async () => {
      if (!s.texto) return;
      const numero = Number(el.versiones.value);
      if (!(await puedoSoltar())) {
        pintarVersion();
        return;
      }
      mostrarError('');
      await abrirTexto(s.texto.id, numero === s.texto.version_vigente ? undefined : numero);
    },
    escucha,
  );

  el.nuevo.addEventListener(
    'click',
    async () => {
      if (!(await puedoSoltar())) return;
      mostrarError('');
      poner(null);
      el.nombre.focus();
    },
    escucha,
  );

  el.irVigente.addEventListener(
    'click',
    async () => {
      if (s.texto) await abrirTexto(s.texto.id);
    },
    escucha,
  );

  el.usarBase.addEventListener(
    'click',
    () => {
      if (!s.texto) return;
      s.modo = usarComoBase(s.modo);
      editor?.fijar(s.texto.version.contenido, false);
      s.inicial = contenidoActual();
      pintar();
      emitir();
      editor?.enfocar?.();
    },
    escucha,
  );

  el.descartar.addEventListener(
    'click',
    () => {
      if (s.modo === 'base' && s.texto) {
        poner(s.texto, descartar(s.modo));
        return;
      }
      poner(s.texto);
    },
    escucha,
  );

  el.nombre.addEventListener(
    'input',
    () => {
      s.nombreRepetido = false;
      s.problemas = { ...s.problemas, nombre: [] };
      pintarProblemas();
      pintarPie();
      emitir();
    },
    escucha,
  );

  async function guardar(): Promise<void> {
    if (!puedeGuardar(s.modo, hayCambios(), s.guardando)) return;
    s.guardando = true;
    s.problemas = { nombre: [], contenido: [] };
    s.nombreRepetido = false;
    mostrarError('');
    pintarProblemas();
    pintarPie();
    const creando = s.texto === null;
    try {
      const contenido = contenidoActual();
      const guardado = creando
        ? await crearTexto(opciones.contexto, el.nombre.value, contenido)
        : await agregarVersion(s.texto!.id, contenido);
      s.guardando = false;
      await recargarListas().catch(() => undefined);
      poner(guardado);
      anunciar(
        creando
          ? t('textosGuardados.creado', { nombre: guardado.nombre })
          : t('textosGuardados.guardado', { n: guardado.version.numero, nombre: guardado.nombre }),
      );
      el.guardar.focus();
    } catch (error) {
      s.guardando = false;
      const clasificado = clasificarError(error);
      if (clasificado.tipo === 'repetido') {
        s.nombreRepetido = true;
      } else if (clasificado.tipo === 'invalido') {
        const porCampo = problemasPorCampo(error);
        s.problemas = porCampo;
        if (porCampo.nombre.length === 0 && porCampo.contenido.length === 0) mostrarError(textoDeErrorGeneral(error));
      } else if (clasificado.tipo === 'no_existe') {
        await recargarListas().catch(() => undefined);
        poner(null);
        mostrarError(textoDeErrorGeneral(error));
        return;
      } else {
        mostrarError(textoDeErrorGeneral(error));
      }
      pintarProblemas();
      pintarPie();
      if (s.nombreRepetido || s.problemas.nombre.length > 0) el.nombre.focus();
      else if (s.problemas.contenido.length > 0) el.problemas.scrollIntoView({ block: 'nearest' });
    }
  }
  el.guardar.addEventListener('click', () => void guardar(), escucha);

  async function deshabilitar(): Promise<void> {
    const texto = s.texto;
    if (!texto || s.modo === 'deshabilitado') return;
    if (!(await puedoSoltar())) return;
    mostrarError('');
    const vecino = vecinoDe(ofrecidos(), texto.id);
    try {
      await deshabilitarTexto(texto.id);
      await recargarListas();
      // The text leaves the list of the enabled: what is shown is the one next to it, or a new one.
      const ofrecidosAhora = ofrecidos();
      const siguiente = vecino !== null && ofrecidosAhora.some((x) => x.id === vecino.id) ? vecino : (ofrecidosAhora[0] ?? null);
      if (siguiente) await abrirTexto(siguiente.id);
      else poner(null);
      anunciar(t('textosGuardados.deshabilitadoAviso', { nombre: texto.nombre }));
    } catch (error) {
      mostrarError(textoDeErrorGeneral(error));
    }
    el.select.focus();
  }
  el.deshabilitar.addEventListener('click', () => void deshabilitar(), escucha);

  async function habilitar_(texto: ResumenTexto): Promise<void> {
    mostrarError('');
    try {
      await habilitarTexto(texto.id);
      await recargarListas();
      // If it is the one on screen it is not a disabled text any more: read it again, so it is editable and in the select.
      if (s.texto?.id === texto.id) await abrirTexto(texto.id);
      else pintar();
      anunciar(t('textosGuardados.habilitado', { nombre: texto.nombre }));
    } catch (error) {
      mostrarError(textoDeErrorGeneral(error));
    }
    // Its button went with the row: the select is where the focus goes.
    el.select.focus();
  }

  async function verDeshabilitado(texto: ResumenTexto): Promise<void> {
    if (!(await puedoSoltar())) return;
    mostrarError('');
    await abrirTexto(texto.id);
    el.select.focus();
  }

  // ---- Renaming (§10.1) ----------------------------------------------------------------------

  function pintarConfirmarRenombrar(): void {
    ren.confirmar.disabled = s.renombrando || !hayNombreNuevo(nombreDe(), ren.nombre.value);
    ren.confirmar.dataset.loading = s.renombrando ? 'true' : 'false';
  }

  el.renombrar.addEventListener(
    'click',
    () => {
      if (!s.texto) return;
      ren.titulo.textContent = t('textosGuardados.renombrarTitulo', { nombreCitado: citado(s.texto.nombre) });
      ren.nombre.value = s.texto.nombre;
      ren.error.textContent = '';
      ren.nombre.removeAttribute('aria-invalid');
      pintarConfirmarRenombrar();
      void openWhenFree(dialogos.renombrar).then(() => {
        ren.nombre.focus();
        ren.nombre.select();
      });
    },
    escucha,
  );
  // Closing by any way (Cancel, Escape, a rename that worked) returns the focus to the button, if it is still there.
  dialogos.renombrar.addEventListener('close', () => (el.renombrar.hidden ? el.select : el.renombrar).focus(), escucha);

  ren.nombre.addEventListener(
    'input',
    () => {
      ren.error.textContent = '';
      ren.nombre.removeAttribute('aria-invalid');
      pintarConfirmarRenombrar();
    },
    escucha,
  );

  ren.form.addEventListener(
    'submit',
    async (evento) => {
      evento.preventDefault();
      const texto = s.texto;
      if (!texto || s.renombrando || !hayNombreNuevo(texto.nombre, ren.nombre.value)) return;
      s.renombrando = true;
      ren.error.textContent = '';
      pintarConfirmarRenombrar();
      try {
        const renombrado = await renombrarTexto(texto.id, ren.nombre.value);
        // Only the name changes: a version that was open to read stays as it is, and so does what was typed.
        s.texto = { ...texto, nombre: renombrado.nombre };
        s.lista = listaConNombre(s.lista, texto.id, renombrado.nombre);
        pintar();
        anunciar(t('textosGuardados.renombrado', { nombre: renombrado.nombre }));
        dialogos.renombrar.close();
        emitir();
      } catch (error) {
        const clasificado = clasificarError(error);
        ren.error.textContent =
          clasificado.tipo === 'repetido'
            ? t('textosGuardados.nombreRepetido')
            : clasificado.tipo === 'invalido'
              ? t('textosGuardados.nombreInvalido', { max: LARGO_MAXIMO_NOMBRE })
              : textoDeErrorGeneral(error);
        ren.nombre.setAttribute('aria-invalid', 'true');
        ren.nombre.focus();
      } finally {
        s.renombrando = false;
        pintarConfirmarRenombrar();
      }
    },
    escucha,
  );

  // ---- Deleting (§4.6 of mowa-mes-interfaz.md) -------------------------------------------------

  function pintarAceptarEliminar(): void {
    eli.aceptar.disabled = s.eliminando || !eli.casilla.checked;
    eli.aceptar.dataset.loading = s.eliminando ? 'true' : 'false';
  }

  function pedirEliminar(id: number, nombre: string): void {
    s.aEliminar = { id, nombre };
    eli.titulo.textContent = opciones.eliminar?.titulo(nombre) ?? t('textosGuardados.eliminarTitulo', { nombreCitado: citado(nombre) });
    eli.cuerpo.textContent = opciones.eliminar?.cuerpo ?? t('textosGuardados.eliminarCuerpo');
    eli.casilla.checked = false;
    eli.error.textContent = '';
    pintarAceptarEliminar();
    void openWhenFree(dialogos.eliminar).then(() => q<HTMLButtonElement>('[data-textos-eliminar-cancelar]').focus());
  }

  el.eliminar.addEventListener(
    'click',
    () => {
      if (s.texto) pedirEliminar(s.texto.id, s.texto.nombre);
    },
    escucha,
  );
  eli.casilla.addEventListener('change', pintarAceptarEliminar, escucha);
  q<HTMLButtonElement>('[data-textos-eliminar-cancelar]').addEventListener('click', () => dialogos.eliminar.close(), escucha);

  eli.aceptar.addEventListener(
    'click',
    async () => {
      const objetivo = s.aEliminar;
      if (!objetivo || s.eliminando || !eli.casilla.checked) return;
      s.eliminando = true;
      eli.error.textContent = '';
      pintarAceptarEliminar();
      try {
        const eraElMostrado = s.texto?.id === objetivo.id;
        const vecino = vecinoDe(ofrecidos(), objetivo.id);
        await eliminarTexto(objetivo.id);
        dialogos.eliminar.close();
        await recargarListas();
        if (eraElMostrado) {
          const ofrecidosAhora = ofrecidos();
          const siguiente = vecino !== null && ofrecidosAhora.some((x) => x.id === vecino.id) ? vecino : (ofrecidosAhora[0] ?? null);
          if (siguiente) await abrirTexto(siguiente.id);
          else poner(null);
        } else {
          pintar();
        }
        anunciar(t('textosGuardados.eliminado', { nombre: objetivo.nombre }));
        el.select.focus();
      } catch (error) {
        const clasificado = clasificarError(error);
        eli.error.textContent = textoDeErrorGeneral(error);
        if (clasificado.tipo === 'usado') {
          // Used after all: there is no deleting it, and the screen stops offering to.
          s.usados.add(objetivo.id);
          await recargarListas().catch(() => undefined);
          if (s.texto?.id === objetivo.id) {
            const actualizado = await obtenerTexto(objetivo.id, s.texto.version.numero).catch(() => null);
            if (actualizado) s.texto = actualizado;
          }
          pintar();
        } else if (clasificado.tipo === 'no_existe') {
          dialogos.eliminar.close();
          await recargarListas().catch(() => undefined);
          await mostrarPrimero();
        }
      } finally {
        s.eliminando = false;
        pintarAceptarEliminar();
      }
    },
    escucha,
  );

  // ---- Start ---------------------------------------------------------------------------------

  document.addEventListener('languagechange', () => pintar(), escucha);

  const alCambiarEditor = () => {
    pintarProblemas();
    pintarPie();
    emitir();
  };

  /** The controls that need the lists: off while they could not be read, on when they could. */
  function habilitarControles(si: boolean): void {
    el.nuevo.disabled = !si;
    el.select.disabled = !si;
  }

  /**
   * Reads the context and the lists and shows the first text. It can run again: the editor is built once, so
   * «Reintentar» after a failed load starts over from the request that failed.
   */
  async function arrancar(): Promise<void> {
    mostrarError('');
    el.reintentar.hidden = true;
    try {
      const contextos = await listarContextos();
      s.contexto = contextos.find((c) => c.clave === opciones.contexto) ?? null;
      if (s.contexto === null) {
        el.titulo.textContent = opciones.titulo;
        mostrarError(t('textoEnriquecido.codigo.contexto_guardado_desconocido'));
        el.pie.hidden = true;
        habilitarControles(false);
        return;
      }
      editor ??= await editorMontado(opciones, el.editor, s.contexto.tipo, alCambiarEditor);
      await recargarListas();
      habilitarControles(true);
      await mostrarPrimero();
    } catch {
      // Whatever the reason, the answer is the same: the lists are not there, and asking again is the way out.
      el.titulo.textContent = opciones.titulo;
      mostrarError(t('textosGuardados.errorCarga'));
      el.reintentar.hidden = false;
      el.pie.hidden = true;
      habilitarControles(false);
    }
  }
  el.reintentar.addEventListener('click', () => void arrancar(), escucha);

  await arrancar();

  raiz.dataset.montado = 'true';

  return {
    estado,
    hayCambios,
    confirmarSalida: puedoSoltar,
    async recargar() {
      await recargarListas();
      const id = s.texto?.id ?? null;
      if (id !== null) await abrirTexto(id, s.texto?.version.numero === s.texto?.version_vigente ? undefined : s.texto?.version.numero);
      else pintar();
    },
    repintar: pintar,
    destruir() {
      alta.abort();
      editor?.destruir();
      for (const dialogo of Object.values(dialogos)) if (dialogo.open) dialogo.close();
      raiz.removeAttribute('data-montado');
    },
  };
}

async function editorMontado(
  opciones: OpcionesTextos,
  anfitrion: HTMLElement,
  tipo: ContextoGuardado['tipo'],
  alCambiar: () => void,
): Promise<EditorDelTexto> {
  return opciones.editor(anfitrion, { tipo, alCambiar });
}
