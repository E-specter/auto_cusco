/**
 * The WhatsMKT campaign screen (T-WM-F2a1, docs/whatsmkt-interfaz.md §3): it holds the form, asks the API for the preview of
 * the lot it would give every time something changes, and draws the answer. «Crear» is there but off (T-WM-F2a2 turns it on).
 *
 * The rules that need no browser are in `lib/whatsmkt-campana.ts`; this binds them to the markup of `pages/whatsmkt/campana.astro`
 * by data attributes. A failure of a list (the texts, the library, the definitions) is said in its section and never takes the
 * rest of the screen down; only an API that cannot be reached at all stands the page down.
 */

import { ApiError, NetworkError, mensajeDeError } from '../lib/api';
import { listarDefiniciones, obtenerDefinicion, type ResumenDefinicion } from '../lib/api-definiciones';
import { obtenerCatalogo } from '../lib/api-texto-enriquecido';
import { listarTextos, obtenerTexto, type ResumenTexto } from '../lib/api-textos-guardados';
import { etiquetaVariable } from '../lib/campos';
import {
  crearCampanas,
  listarAdjuntos,
  listarSegmentos,
  obtenerConfiguracion,
  obtenerProgramacion,
  previsualizarCampanas,
  type AdjuntoWhatsmkt,
  type CampanaPrevista,
  type ConfiguracionWhatsmkt,
  type ErrorFechaNoGestionable,
  type PrevisualizacionCampanas,
  type ProblemaCampana,
  type ProgramacionWhatsmkt,
  type SegmentoWhatsmkt,
} from '../lib/api-whatsmkt';
import { openWhenFree } from '../lib/dialogs';
import { $, ocupado } from '../lib/dom';
import { formatDate, formatNumber } from '../lib/format';
import { applyTranslations, t, traducirPorPrefijo } from '../lib/i18n';
import { pintarBotonesDeVariables } from '../lib/mowa-mes-plantilla';
import { FILAS_POR_PAGINA, paginar, pintarPaginador } from '../lib/paginacion';
import { celda, celdaDeFila, cifra, tabla, vacio } from '../lib/tabla-dom';
import { enlaceEditarEnCartera, seleccionDeLaUrl } from '../lib/volver';
import { largoDelMensaje } from '../lib/whatsmkt-mensaje';
import { tablaDeExclusiones } from './whatsmkt-exclusiones';
import { montarFicha } from './whatsmkt-ficha';
import { montarSubida } from './whatsmkt-subida';
import {
  MACROS_PUBLICADAS,
  borradorInicial,
  cantidadDeMacros,
  diasDeSegmento,
  entradaDeCreacion,
  entradaDePrevisualizacion,
  etiquetaDeAdjunto,
  filasDeColumnas,
  motivoDeCrear,
  nombresDeLote,
  problemasLocales,
  seccionDeProblema,
  textoDeProblema,
  textoDeProblemaConSegmento,
  type BorradorCampana,
  type ProblemaLocal,
  type SeccionDeProblema,
  type SeleccionBase,
} from '../lib/whatsmkt-campana';
import { FECHA_DE_EJEMPLO, LARGO_MAXIMO_NOMBRE, definicionesDeWhatsmkt, errorDeModulo, textoDeCodigo } from '../lib/whatsmkt';
import { EVENTO_SELECCION, montarSelector, type ControladorSelector, type EstadoSeleccion } from './selector-seleccion';

/** Long enough that a typed template or a click on a box does not ask the API for each change. */
const ESPERA_PREVIA = 400;
/** The page of the saved selection that Cartera sends the analyst back to. */
const VUELTA = '/whatsmkt/campana';

const estado = {
  configuracion: null as ConfiguracionWhatsmkt | null,
  segmentos: [] as SegmentoWhatsmkt[],
  textos: [] as ResumenTexto[],
  adjuntos: [] as AdjuntoWhatsmkt[],
  /** The suggested send date and the first one that can be picked; `null` when the API did not say. */
  programacion: null as ProgramacionWhatsmkt | null,
  /** The saved definitions of the WhatsMKT platform. */
  definiciones: [] as ResumenDefinicion[],
  versionDefinicion: null as number | null,
  columnas: filasDeColumnas([]),
  borrador: null as BorradorCampana | null,
  seleccion: null as EstadoSeleccion | null,
  previa: null as PrevisualizacionCampanas | null,
  campanaElegida: 0,
  paginaExclusiones: 1,
  paginaFuera: 1,
  /** The sections the analyst already left: their local problems show under their fields (RF-WM-43). */
  tocadas: new Set<SeccionDeProblema>(),
  /** What failed reading the definitions, or a definition's columns; empty when nothing did. */
  errorDefinicion: '',
  /** What failed reading the saved texts or the library, said in their section. */
  errorMensajes: '',
  errorAdjuntos: '',
  errorProgramacion: '',
  /** The lot is being created: «Crear» waits. */
  creando: false,
};

const raiz = $<HTMLElement>('[data-selector]');
const formulario = $<HTMLElement>('[data-formulario]');
const panelPrevia = $<HTMLElement>('[data-previa]');
let controlador: ControladorSelector | null = null;
let botonEditar: HTMLButtonElement | null = null;
let montado = false;
let temporizador = 0;
let controlPrevia: AbortController | null = null;

const borrador = (): BorradorCampana => estado.borrador!;

// ---- Shared helpers --------------------------------------------------------------------------------------------

function mostrarError(error: unknown): void {
  $<HTMLElement>('[data-error-body]').textContent = mensajeDeError(error);
  void openWhenFree($<HTMLDialogElement>('[data-dialog="error"]'));
}

document.querySelectorAll<HTMLElement>('[data-close]').forEach((boton) => {
  boton.addEventListener('click', () => boton.closest('dialog')?.close());
});

function opcion(valor: string, texto: string): HTMLOptionElement {
  const nodo = document.createElement('option');
  nodo.value = valor;
  nodo.textContent = texto;
  return nodo;
}

const icono = (clave: string): Node => $<HTMLTemplateElement>(`template[data-icono-${clave}]`).content.cloneNode(true);

/** Put `valor` on a select only if one of its options is it (the saved id of a disabled text is not offered). */
function elegir(select: HTMLSelectElement, valor: string): void {
  select.value = [...select.options].some((o) => o.value === valor) ? valor : '';
}

const aNumero = (valor: string): number | null => (valor === '' ? null : Number(valor));

// ---- 2. Load file: the definitions of the platform ---------------------------------------------------------------

const selectDefinicion = $<HTMLSelectElement>('#wm-definicion');
const errorDefinicion = $<HTMLElement>('[data-definicion-error]');

function pintarDefinicion(): void {
  const lista = estado.definiciones;
  selectDefinicion.replaceChildren(opcion('', lista.length === 0 ? t('whatsmkt.archivo.sinDefiniciones') : t('whatsmkt.archivo.elegirDefinicion')));
  lista.forEach((definicion) => selectDefinicion.append(opcion(String(definicion.id), definicion.nombre)));
  selectDefinicion.disabled = lista.length === 0;
  const elegida = borrador().definicionId;
  selectDefinicion.value = elegida !== null && lista.some((d) => d.id === elegida) ? String(elegida) : '';
  $<HTMLElement>('[data-sin-definiciones]').hidden = lista.length > 0;
  // With none of the platform the link goes to create one; both go to the same screen (shortcut: a plain link until T-WM-F2b brings the go-and-back to the constructor).
  const texto = $<HTMLElement>('[data-columnas-texto]');
  const clave = lista.length === 0 ? 'whatsmkt.archivo.crear' : 'whatsmkt.archivo.editar';
  texto.dataset.i18n = clave;
  texto.textContent = t(clave);
  $<HTMLElement>('[data-version-linea]').textContent =
    estado.versionDefinicion === null ? '' : t('whatsmkt.archivo.versionLinea', { n: estado.versionDefinicion });
}

function pintarColumnas(): void {
  const destino = $<HTMLElement>('[data-columnas-tabla]');
  if (estado.columnas.length === 0) {
    destino.replaceChildren();
  } else {
    const { envoltorio, cuerpo } = tabla(
      'wm-columnas',
      [
        [t('whatsmkt.archivo.col.macro'), false],
        [t('whatsmkt.archivo.col.encabezado'), false],
        [t('whatsmkt.archivo.col.etiqueta'), false],
        [t('whatsmkt.archivo.col.contenido'), false],
      ],
      { apilable: true },
    );
    envoltorio.querySelector('table')!.setAttribute('aria-label', t('whatsmkt.archivo.tabla'));
    estado.columnas.forEach((columna) => {
      const fila = document.createElement('tr');
      fila.append(
        celda('td', columna.macro === null ? '—' : String(columna.macro), 'mono', t('whatsmkt.archivo.col.macro')),
        celda('td', columna.encabezado, 'mono', t('whatsmkt.archivo.col.encabezado')),
        celda('td', columna.etiqueta || '—', '', t('whatsmkt.archivo.col.etiqueta')),
        celda('td', columna.contenido, '', t('whatsmkt.archivo.col.contenido')),
      );
      cuerpo.append(fila);
    });
    destino.replaceChildren(envoltorio);
  }
  // DU-WM-1, provisional: more variables than WhatsMKT publishes warns and does not block.
  const macros = cantidadDeMacros(estado.columnas);
  const aviso = $<HTMLElement>('[data-cinco-macros]');
  aviso.hidden = macros <= MACROS_PUBLICADAS;
  aviso.textContent = macros > MACROS_PUBLICADAS ? t('whatsmkt.archivo.cincoMacros', { n: macros }) : '';
  // The macros marked in the message blocks carry the label of their column: they are drawn again once the columns are known.
  document.querySelectorAll<HTMLElement>('[data-texto-mensaje]').forEach((bloque) => {
    const id = Number(bloque.dataset.id);
    if (id > 0) void pintarTextoDeMensaje(bloque, id);
  });
}

/** The columns of the definition chosen, at its latest version (the one the preview and the creation use). */
async function cargarColumnas(): Promise<void> {
  const id = borrador().definicionId;
  estado.errorDefinicion = '';
  if (id === null) {
    estado.columnas = filasDeColumnas([]);
    estado.versionDefinicion = null;
    pintarColumnas();
    pintarDefinicion();
    pintarErroresLocales();
    return;
  }
  try {
    const definicion = await obtenerDefinicion(id);
    if (borrador().definicionId !== id) return;
    estado.versionDefinicion = definicion.version.numero;
    // The label of each variable is the catalogue's; without it (a courtesy) the portfolio's own label is used.
    const catalogo = await obtenerCatalogo('cartera').catch(() => null);
    if (borrador().definicionId !== id) return;
    const etiquetas = new Map((catalogo?.contexto.variables ?? []).map((v) => [v.nombre, etiquetaVariable(v)]));
    estado.columnas = filasDeColumnas(
      definicion.version.contenido.columnas.map((c) => ({ nombre: c.nombre, etiqueta: c.etiqueta, expresion: c.expresion, variantes: c.variantes })),
      (nombre) => etiquetas.get(nombre) ?? etiquetaVariable({ nombre, clave_nombre: null }),
    );
  } catch (caido) {
    estado.columnas = filasDeColumnas([]);
    estado.versionDefinicion = null;
    estado.errorDefinicion = mensajeDeError(caido);
  }
  pintarColumnas();
  pintarDefinicion();
  pintarErroresLocales();
}

selectDefinicion.addEventListener('change', () => {
  borrador().definicionId = aNumero(selectDefinicion.value);
  void cargarColumnas();
  cambioDelFormulario();
});

// ---- 3. Message: by segment or global, chosen from the saved texts ---------------------------------------------------

const contenedorSegmentos = $<HTMLElement>('[data-mensaje-segmentos]');
const campoGlobal = $<HTMLElement>('[data-mensaje-global]');
const selectGlobal = $<HTMLSelectElement>('#wm-mensaje-global');

/** The ids of the texts that are a segment's own (the rest are the global ones). */
const idsDeSegmentos = (): Set<number> =>
  new Set(estado.segmentos.map((s) => s.texto_guardado_id).filter((id): id is number => id !== null));

function pintarSelectGlobal(): void {
  const propios = idsDeSegmentos();
  const globales = estado.textos.filter((texto) => !propios.has(texto.id));
  const deSegmentos = estado.textos.filter((texto) => propios.has(texto.id));
  const grupo = (clave: string, textos: ResumenTexto[]): HTMLOptGroupElement => {
    const nodo = document.createElement('optgroup');
    nodo.label = t(clave);
    textos.forEach((texto) => nodo.append(opcion(String(texto.id), texto.nombre)));
    return nodo;
  };
  selectGlobal.replaceChildren(opcion('', t('whatsmkt.mensaje.elegir')));
  if (globales.length > 0) selectGlobal.append(grupo('whatsmkt.mensaje.globales', globales));
  if (deSegmentos.length > 0) selectGlobal.append(grupo('whatsmkt.mensaje.porSegmento', deSegmentos));
  const elegido = borrador().mensajeGlobal;
  elegir(selectGlobal, elegido === null ? '' : String(elegido));
  void pintarTextoDeMensaje($<HTMLElement>('[data-texto-mensaje="global"]'), elegido);
}

/** The latest version of each text read once: the block under a select shows what the message says, which a longer name cannot. */
const textosLeidos = new Map<number, Promise<string>>();
const textoDe = (id: number): Promise<string> => {
  const leido = textosLeidos.get(id) ?? obtenerTexto(id).then((texto) => String(texto.version.contenido.texto ?? ''));
  textosLeidos.set(id, leido);
  // A failed read is forgotten so the next paint asks again.
  leido.catch(() => textosLeidos.delete(id));
  return leido;
};

/**
 * The text of the message chosen, under its select (§3.4): read only, as written, with its macros marked (their label in the `title`) and its
 * length against the limit («312 / 4096»). Without a message, or if the text cannot be read, there is no block: the select says the rest.
 */
async function pintarTextoDeMensaje(destino: HTMLElement, id: number | null): Promise<void> {
  destino.dataset.id = String(id);
  if (id === null) {
    destino.hidden = true;
    destino.replaceChildren();
    return;
  }
  let texto: string;
  try {
    texto = await textoDe(id);
  } catch {
    if (destino.dataset.id === String(id)) destino.hidden = true;
    return;
  }
  // Another message was chosen while this one was being read.
  if (destino.dataset.id !== String(id)) return;
  const cuerpo = document.createElement('p');
  cuerpo.className = 'mono wm-mensaje-texto__cuerpo';
  texto.split(/(\[\$MACRO\d+\$\])/).forEach((trozo) => {
    const macro = /^\[\$MACRO(\d+)\$\]$/.exec(trozo);
    if (!macro) return void cuerpo.append(trozo);
    const marca = document.createElement('mark');
    marca.className = 'wm-macro';
    marca.textContent = trozo;
    const etiqueta = estado.columnas.find((c) => c.macro === Number(macro[1]))?.etiqueta;
    if (etiqueta) marca.title = t('whatsmkt.mensaje.macro', { n: macro[1], etiqueta });
    cuerpo.append(marca);
  });
  const largo = document.createElement('p');
  largo.className = 'wm-contador';
  largo.textContent = t('whatsmkt.mensaje.largo', { largo: largoDelMensaje(texto), maximo: estado.configuracion?.tope_mensaje ?? 0 });
  destino.replaceChildren(cuerpo, largo);
  destino.hidden = false;
}

/** One row per segment of the platform: its days, and the select of its message with its problems under it. */
function pintarMensajesPorSegmento(): void {
  const { envoltorio, cuerpo } = tabla(
    'wm-mensajes',
    [
      [t('whatsmkt.configuracion.col.segmento'), false],
      [t('whatsmkt.campana.col.dias'), false],
      [t('whatsmkt.seccion.mensaje'), false],
    ],
    { apilable: true },
  );
  estado.segmentos.forEach((segmento) => {
    const fila = document.createElement('tr');
    fila.dataset.segmento = segmento.clave;
    const identificador = `wm-mensaje-${segmento.clave}`;

    const celdaMensaje = celda('td', '', '', t('whatsmkt.seccion.mensaje'));
    const select = document.createElement('select');
    select.className = 'input';
    select.id = identificador;
    select.dataset.selectMensaje = segmento.clave;
    select.setAttribute('aria-label', t('whatsmkt.mensaje.paraSegmento', { segmento: segmento.etiqueta }));
    select.setAttribute('aria-describedby', `${identificador}-problemas`);
    select.append(opcion('', t('whatsmkt.mensaje.elegir')));
    estado.textos.forEach((texto) => select.append(opcion(String(texto.id), texto.nombre)));
    const elegido = borrador().mensajesPorSegmento[segmento.clave] ?? null;
    elegir(select, elegido === null ? '' : String(elegido));
    const textoElegido = document.createElement('div');
    textoElegido.className = 'wm-mensaje-texto';
    textoElegido.dataset.textoMensaje = segmento.clave;
    textoElegido.hidden = true;
    void pintarTextoDeMensaje(textoElegido, elegido);
    select.addEventListener('change', () => {
      borrador().mensajesPorSegmento[segmento.clave] = aNumero(select.value);
      void pintarTextoDeMensaje(textoElegido, borrador().mensajesPorSegmento[segmento.clave]);
      cambioDelFormulario();
    });
    const problemas = document.createElement('div');
    problemas.className = 'wm-problemas';
    problemas.id = `${identificador}-problemas`;
    problemas.dataset.problemasMensaje = segmento.clave;
    problemas.setAttribute('role', 'alert');
    // A segment with no products in the selection makes no campaign, which is why it has no error without a message.
    const sinProductos = document.createElement('p');
    sinProductos.className = 'field__hint';
    sinProductos.id = `${identificador}-sin-productos`;
    sinProductos.dataset.sinProductos = segmento.clave;
    sinProductos.hidden = true;
    sinProductos.textContent = t('whatsmkt.mensaje.sinProductos');
    select.setAttribute('aria-describedby', `${identificador}-problemas ${identificador}-sin-productos`);
    celdaMensaje.append(select, problemas, sinProductos, textoElegido);

    fila.append(celdaDeFila(segmento.etiqueta, '', t('whatsmkt.configuracion.col.segmento')), celda('td', diasDeSegmento(segmento), 'mono', t('whatsmkt.campana.col.dias')), celdaMensaje);
    cuerpo.append(fila);
  });
  contenedorSegmentos.replaceChildren(envoltorio);
}

function pintarMensajes(): void {
  const porSegmento = borrador().modo === 'por_segmento';
  contenedorSegmentos.hidden = !porSegmento;
  campoGlobal.hidden = porSegmento;
  document.querySelectorAll<HTMLButtonElement>('button[data-modo]').forEach((boton) => {
    boton.setAttribute('aria-pressed', String(boton.dataset.modo === borrador().modo));
  });
  $<HTMLElement>('[data-modo-hint]').textContent = t(porSegmento ? 'whatsmkt.mensaje.modo.segmentoHint' : 'whatsmkt.mensaje.modo.globalHint');
  $<HTMLElement>('[data-sin-mensajes]').hidden = estado.textos.length > 0 || estado.errorMensajes !== '';
  $<HTMLElement>('[data-mensajes-error]').textContent = estado.errorMensajes;
  pintarMensajesPorSegmento();
  pintarSelectGlobal();
  pintarProblemasDeMensaje();
}

document.querySelectorAll<HTMLButtonElement>('button[data-modo]').forEach((boton) => {
  boton.addEventListener('click', () => {
    borrador().modo = boton.dataset.modo === 'global' ? 'global' : 'por_segmento';
    estado.campanaElegida = 0;
    pintarMensajes();
    cambioDelFormulario();
  });
});

selectGlobal.addEventListener('change', () => {
  borrador().mensajeGlobal = aNumero(selectGlobal.value);
  void pintarTextoDeMensaje($<HTMLElement>('[data-texto-mensaje="global"]'), borrador().mensajeGlobal);
  cambioDelFormulario();
});

/** The problems of the message, in the order they arrive, under the select of their segment (`null` is the global one). */
function pintarProblemasDeMensaje(): void {
  document.querySelectorAll<HTMLElement>('[data-problemas-mensaje]').forEach((caja) => {
    const clave = caja.dataset.problemasMensaje!;
    const propios = (estado.previa?.problemas ?? []).filter(
      (p) => seccionDeProblema(p.codigo) === 'mensaje' && (clave === 'global' ? p.segmento === null : p.segmento === clave),
    );
    caja.replaceChildren(
      ...propios.map((problema) => {
        const linea = document.createElement('p');
        linea.className = 'field__error';
        linea.textContent = textoDeProblema(problema);
        return linea;
      }),
    );
    const select = caja.parentElement?.querySelector('select');
    if (select) {
      if (propios.length > 0) select.setAttribute('aria-invalid', 'true');
      else select.removeAttribute('aria-invalid');
    }
    const previa = estado.previa;
    const aviso = caja.parentElement?.querySelector<HTMLElement>('[data-sin-productos]');
    if (aviso) {
      aviso.hidden = !(previa !== null && clave !== 'global' && propios.length === 0 && !previa.campanas.some((c) => c.segmento === clave));
    }
  });
}

// ---- 4. Programming ------------------------------------------------------------------------------------------------

const campoFecha = $<HTMLInputElement>('#wm-fecha');
const errorHorarios = $<HTMLElement>('[data-horarios-error]');

function pintarHorarios(): void {
  const config = estado.configuracion!;
  const caja = $<HTMLElement>('[data-horarios]');
  caja.replaceChildren(
    ...(['horario_1', 'horario_2'] as const).map((franja) => {
      const horario = config[franja];
      const etiqueta = document.createElement('label');
      etiqueta.className = 'wm-check';
      const entrada = document.createElement('input');
      entrada.type = 'checkbox';
      entrada.dataset.franja = franja;
      entrada.checked = borrador().horarios[franja];
      entrada.addEventListener('change', () => {
        borrador().horarios[franja] = entrada.checked;
        pintarErroresLocales();
        cambioDelFormulario();
      });
      const cuerpo = document.createElement('span');
      cuerpo.className = 'wm-check__cuerpo';
      const titulo = document.createElement('span');
      titulo.className = 'wm-check__titulo';
      titulo.textContent = t('whatsmkt.programacion.horario', {
        n: franja === 'horario_1' ? 1 : 2,
        desde: horario.inicio,
        hasta: horario.fin,
      });
      cuerpo.append(titulo);
      etiqueta.append(entrada, cuerpo);
      return etiqueta;
    }),
  );
}

const errorFecha = $<HTMLElement>('[data-fecha-error]');
const botonUsarFecha = $<HTMLButtonElement>('[data-fecha-usar]');

/**
 * The send date: the API's suggestion, not before the earliest allowed. A date that is not a working day comes back from the
 * preview as a problem; it is said under the field, with the suggested day to take in one click.
 */
function pintarFecha(): void {
  campoFecha.min = estado.programacion?.minima ?? '';
  // A date being typed is not overwritten by a preview that arrives in the middle.
  if (document.activeElement !== campoFecha) campoFecha.value = borrador().fechaEnvio;
  const problema = (estado.previa?.problemas ?? []).find((p) => p.codigo === 'fecha_no_gestionable');
  const sugerida = problema ? (problema.parametros as Record<string, string | undefined>).sugerida : undefined;
  errorFecha.textContent = problema ? textoDeProblema(problema) : estado.errorProgramacion;
  if (problema) campoFecha.setAttribute('aria-invalid', 'true');
  else campoFecha.removeAttribute('aria-invalid');
  botonUsarFecha.hidden = !sugerida;
  if (sugerida) {
    botonUsarFecha.dataset.fecha = sugerida;
    botonUsarFecha.textContent = t('whatsmkt.programacion.usar', { fecha: formatDate(sugerida) });
  }
}

campoFecha.addEventListener('change', () => {
  avisoFechaVencida.hidden = true;
  borrador().fechaEnvio = campoFecha.value;
  cambioDelFormulario();
});
botonUsarFecha.addEventListener('click', () => {
  const sugerida = botonUsarFecha.dataset.fecha;
  if (!sugerida) return;
  borrador().fechaEnvio = sugerida;
  campoFecha.value = sugerida;
  campoFecha.focus();
  cambioDelFormulario();
});
$<HTMLInputElement>('#wm-antes').addEventListener('change', (evento) => {
  borrador().antes = (evento.target as HTMLInputElement).checked;
});

// ---- 5. Sending --------------------------------------------------------------------------------------------------------

const selectAdjunto = $<HTMLSelectElement>('#wm-adjunto');
const selectFoto = $<HTMLSelectElement>('#wm-foto');
const campoVcard = $<HTMLInputElement>('#wm-vcard');
const errorEnvio = $<HTMLElement>('[data-envio-error]');

function pintarEnvio(): void {
  selectAdjunto.replaceChildren(opcion('', t('whatsmkt.envio.elegirArchivo')), ...estado.adjuntos.map((a) => opcion(String(a.id), etiquetaDeAdjunto(a))));
  elegir(selectAdjunto, borrador().adjuntoId === null ? '' : String(borrador().adjuntoId));
  // With an empty library there is nothing to choose: the select waits, and «Subir un archivo» beside it fills it.
  selectAdjunto.disabled = estado.adjuntos.length === 0;
  const fotos = estado.adjuntos.filter((a) => a.tipo === 'imagen_jpeg');
  selectFoto.replaceChildren(opcion('', t('whatsmkt.envio.sinFoto')), ...fotos.map((a) => opcion(String(a.id), etiquetaDeAdjunto(a))));
  elegir(selectFoto, borrador().fotoId === null ? '' : String(borrador().fotoId));
  campoVcard.value = borrador().etiquetaVcard;
  // Each type shows only its own fields, and keeps what was written in the others while the analyst looks at another.
  document.querySelectorAll<HTMLElement>('[data-condicional]').forEach((caja) => {
    caja.hidden = caja.dataset.condicional !== borrador().tipoEnvio;
  });
  document.querySelectorAll<HTMLInputElement>('input[name="wm-tipo-envio"]').forEach((radio) => {
    radio.checked = radio.value === borrador().tipoEnvio;
  });
}

document.querySelectorAll<HTMLInputElement>('input[name="wm-tipo-envio"]').forEach((radio) => {
  radio.addEventListener('change', () => {
    if (!radio.checked) return;
    borrador().tipoEnvio = radio.value === 'archivo' ? 'archivo' : radio.value === 'vcard' ? 'vcard' : 'solo_texto';
    document.querySelectorAll<HTMLElement>('[data-condicional]').forEach((caja) => {
      caja.hidden = caja.dataset.condicional !== borrador().tipoEnvio;
    });
    pintarErroresLocales();
    cambioDelFormulario();
  });
});
selectAdjunto.addEventListener('change', () => {
  borrador().adjuntoId = aNumero(selectAdjunto.value);
  pintarErroresLocales();
  cambioDelFormulario();
});
selectFoto.addEventListener('change', () => {
  borrador().fotoId = aNumero(selectFoto.value);
  cambioDelFormulario();
});
campoVcard.addEventListener('input', () => {
  borrador().etiquetaVcard = campoVcard.value;
  pintarErroresLocales();
  cambioDelFormulario();
});

/** What an upload leaves in the library is listed and chosen in its select, as if it had been picked there (§3.6). */
function usarAdjunto(adjunto: AdjuntoWhatsmkt, comoFoto: boolean): void {
  if (!estado.adjuntos.some((a) => a.id === adjunto.id)) estado.adjuntos = [...estado.adjuntos, adjunto];
  if (comoFoto) borrador().fotoId = adjunto.id;
  else borrador().adjuntoId = adjunto.id;
  pintarEnvio();
  pintarErroresLocales();
  cambioDelFormulario();
}
montarSubida({ proposito: 'adjunto', select: selectAdjunto, alUsar: (adjunto) => usarAdjunto(adjunto, false) });
montarSubida({ proposito: 'foto', select: selectFoto, alUsar: (adjunto) => usarAdjunto(adjunto, true) });

// ---- 6. Campaign name -------------------------------------------------------------------------------------------------

const campoPlantilla = $<HTMLInputElement>('#wm-plantilla');
const errorPlantilla = $<HTMLElement>('[data-plantilla-error]');

/** The names the lot has or would have: the preview's campaigns, or the segments' (or a single one) before it arrives. */
function nombresActuales(): string[] {
  const campanas =
    estado.previa?.campanas ??
    (borrador().modo === 'global' ? [{ etiqueta_segmento: null }] : estado.segmentos.map((s) => ({ etiqueta_segmento: s.etiqueta })));
  return nombresDeLote(borrador().plantilla, campanas, estado.seleccion?.fechaCorte ?? FECHA_DE_EJEMPLO.replaceAll('.', '-'));
}

function pintarNombre(): void {
  const nombres = nombresActuales();
  const largo = Math.max(0, ...nombres.map((nombre) => nombre.length));
  const contador = $<HTMLElement>('[data-contador]');
  contador.textContent = t('whatsmkt.configuracion.nombre.contador', { largo, maximo: LARGO_MAXIMO_NOMBRE });
  contador.dataset.excede = String(largo > LARGO_MAXIMO_NOMBRE);
  // In a lot, a template without {segmento} gets the segment added at the end (DU-WM-6): the hint says it.
  const enLote = (estado.previa?.campanas.length ?? (borrador().modo === 'por_segmento' ? estado.segmentos.length : 1)) > 1;
  $<HTMLElement>('[data-segmento-al-final]').hidden = !(enLote && !borrador().plantilla.includes('{segmento}'));
}

function montarNombre(): void {
  const config = estado.configuracion!;
  campoPlantilla.value = borrador().plantilla;
  pintarBotonesDeVariables(
    $<HTMLElement>('[data-variables]'),
    campoPlantilla,
    config.variables_plantilla.map((nombre) => ({ nombre, descripcion: '' })),
  );
  // The helper sets the API's sentence as a title; WhatsMKT has none, and the hint under the chips says it in view.
  $<HTMLElement>('[data-variables]').querySelectorAll('button').forEach((boton) => boton.removeAttribute('title'));
  pintarNombre();
}

campoPlantilla.addEventListener('input', () => {
  borrador().plantilla = campoPlantilla.value;
  pintarNombre();
  pintarErroresLocales();
  cambioDelFormulario();
});

// ---- The problems that stop creating -------------------------------------------------------------------------------------

const idDeSeccion = (seccion: SeccionDeProblema): string => `wm-sec-${seccion === 'whatsapp' || seccion === 'supervisores' ? 'previa' : seccion}`;

function localesActuales(): ProblemaLocal[] {
  return problemasLocales(borrador(), estado.configuracion?.variables_plantilla ?? [], nombresActuales());
}

/** The local problems of the sections already left, under their fields; each field is only told what is its. */
function pintarErroresLocales(): void {
  const visibles = localesActuales().filter((p) => estado.tocadas.has(p.seccion));
  const de = (seccion: SeccionDeProblema, codigos?: string[]): string =>
    visibles.filter((p) => p.seccion === seccion && (!codigos || codigos.includes(p.codigo))).map((p) => p.texto).join(' ');
  errorHorarios.textContent = de('programacion');
  errorEnvio.textContent = [estado.errorAdjuntos, de('envio')].filter(Boolean).join(' ');
  errorPlantilla.textContent = de('nombre');
  // What the API said about the definition (a list or a read that failed) comes before what the form says by itself.
  errorDefinicion.textContent = estado.errorDefinicion || de('archivo');
  // The field of each error is marked too, as the select of a message is when its message has a problem.
  const hay = (codigo: string): boolean => visibles.some((p) => p.codigo === codigo);
  marcar(selectDefinicion, estado.errorDefinicion !== '' || hay('sin_definicion'));
  marcar(selectAdjunto, hay('sin_adjunto'));
  marcar(campoVcard, hay('sin_etiqueta'));
  marcar(campoPlantilla, visibles.some((p) => p.seccion === 'nombre'));
}

function marcar(campo: HTMLElement, invalido: boolean): void {
  if (invalido) campo.setAttribute('aria-invalid', 'true');
  else campo.removeAttribute('aria-invalid');
}

/** Leaving a section tells it its local problems. Nothing moves at a click: «Crear» is off, so none is lost (T-WM-F2a2 will guard it). */
document.querySelectorAll<HTMLElement>('section[id^="wm-sec-"]').forEach((seccion) => {
  seccion.addEventListener('focusout', (evento) => {
    const destino = evento.relatedTarget;
    if (destino instanceof Node && seccion.contains(destino)) return;
    const nombre = seccion.id.replace('wm-sec-', '') as SeccionDeProblema;
    estado.tocadas.add(nombre);
    pintarErroresLocales();
  });
  // A section the analyst changed tells its errors as soon as they exist: a vCard without its label is said under the label.
  (['input', 'change'] as const).forEach((tipo) =>
    seccion.addEventListener(tipo, (evento) => {
      // The date is not what the time slots are about: picking it does not ask for them yet.
      if (evento.target === campoFecha) return;
      estado.tocadas.add(seccion.id.replace('wm-sec-', '') as SeccionDeProblema);
      pintarErroresLocales();
    }),
  );
});

/** The field each problem is about, when it is not the first control of its section. */
const CAMPO_DE_CODIGO: Record<string, string> = {
  sin_definicion: '#wm-definicion',
  definicion_no_whatsmkt: '#wm-definicion',
  sin_horario: '[data-franja]',
  sin_adjunto: '#wm-adjunto',
  sin_etiqueta: '#wm-vcard',
  variable_inexistente: '#wm-plantilla',
  nombre_largo: '#wm-plantilla',
  fecha_no_gestionable: '#wm-fecha',
};

/** Take the focus to the field a problem is about: the select of its segment's message, or the field its code names. */
function irAlCampo(seccion: SeccionDeProblema, codigo: string, segmento: string | null = null): void {
  const sec = document.getElementById(idDeSeccion(seccion));
  const destino =
    seccion === 'mensaje'
      ? `#wm-mensaje-${segmento ?? 'global'}`
      : (CAMPO_DE_CODIGO[codigo] ?? 'select, input, button');
  const campo = sec?.querySelector<HTMLElement>(destino) ?? sec?.querySelector<HTMLElement>('select, input, button') ?? sec;
  campo?.focus();
  (campo ?? sec)?.scrollIntoView({ block: 'center' });
}

function pintarProblemas(): void {
  const etiquetas = Object.fromEntries(estado.segmentos.map((s) => [s.clave, s.etiqueta]));
  const delServidor = (estado.previa?.problemas ?? []).filter((p) => p.codigo !== 'sin_productos');
  const lista = $<HTMLElement>('[data-problemas-lista]');
  const items: HTMLElement[] = [];
  localesActuales().forEach((problema) => items.push(itemDeProblema(problema.texto, problema.seccion, problema.codigo)));
  delServidor.forEach((problema) => {
    items.push(
      itemDeProblema(textoDeProblemaConSegmento(problema, etiquetas), seccionDeProblema(problema.codigo), problema.codigo, problema.segmento),
    );
  });
  lista.replaceChildren(...items);
  $<HTMLElement>('[data-problemas]').hidden = items.length === 0;
  pintarCrear(items.length);
}

/** A problem with its text and, when it has a section, the link that takes the focus there (or to the screen that fixes it). */
function itemDeProblema(texto: string, seccion: SeccionDeProblema | null, codigo: string, segmento: string | null = null): HTMLElement {
  const item = document.createElement('li');
  item.append(texto);
  if (seccion === null) return item;
  item.append(' ');
  if (seccion === 'supervisores' || seccion === 'whatsapp') {
    // They are fixed in another screen: a plain link (shortcut: no way back to the campaign until T-WM-F2b wires the go-and-back).
    const enlace = document.createElement('a');
    enlace.href = seccion === 'supervisores' ? '/supervisores' : '/whatsmkt/configuracion#wm-whatsapp';
    enlace.textContent = t(seccion === 'supervisores' ? 'whatsmkt.previa.irSupervisores' : 'whatsmkt.previa.irWhatsapp');
    item.append(enlace);
    return item;
  }
  const boton = document.createElement('button');
  boton.type = 'button';
  boton.className = 'wm-enlace';
  boton.textContent = t('whatsmkt.previa.irAlCampo');
  boton.addEventListener('click', () => irAlCampo(seccion, codigo, segmento));
  item.append(boton);
  return item;
}

const botonCrear = $<HTMLButtonElement>('[data-crear]');
const alertaCrear = $<HTMLElement>('[data-crear-error]');
const avisoFechaVencida = $<HTMLElement>('[data-fecha-vencida]');
const ficha = montarFicha();
let problemasActuales = 0;

/**
 * «Crear» is on when nothing stops it and the preview on screen is the one of the form as it is now: not while a new one is being asked for
 * and not while the lot is being created. After creating, the form is inert and «Armar otra campaña» starts again.
 */
function pintarCrear(problemas = problemasActuales): void {
  problemasActuales = problemas;
  const cantidad = estado.previa?.campanas.length ?? 0;
  $<HTMLElement>('[data-crear-texto]').textContent = cantidad > 1 ? t('whatsmkt.crear.varias', { n: cantidad }) : t('whatsmkt.crear.una');
  const calculando = panelPrevia.dataset.calculando === 'true';
  botonCrear.disabled = problemas > 0 || cantidad === 0 || calculando || estado.creando;
  $<HTMLElement>('[data-crear-motivo]').textContent = problemas > 0 ? motivoDeCrear(problemas) : '';
}

function limpiarFalloDeCrear(): void {
  alertaCrear.hidden = true;
  $<HTMLElement>('[data-crear-error-lista]').replaceChildren();
  avisoFechaVencida.hidden = true;
}

/** The send date stopped being a working day between the preview and creating: the next one is offered, and what was written stays. */
function mostrarFechaVencida({ fecha, sugerida }: Pick<ErrorFechaNoGestionable, 'fecha' | 'sugerida'>): void {
  $<HTMLElement>('[data-fecha-vencida-texto]').textContent = t('whatsmkt.crear.fechaVencida', { fecha: formatDate(fecha), sugerida: formatDate(sugerida) });
  const usar = $<HTMLButtonElement>('[data-fecha-vencida-usar]');
  usar.dataset.fecha = sugerida;
  usar.textContent = t('whatsmkt.programacion.usar', { fecha: formatDate(sugerida) });
  avisoFechaVencida.hidden = false;
  avisoFechaVencida.scrollIntoView({ block: 'center' });
}

$<HTMLButtonElement>('[data-fecha-vencida-usar]').addEventListener('click', (evento) => {
  const sugerida = (evento.currentTarget as HTMLElement).dataset.fecha;
  if (!sugerida) return;
  borrador().fechaEnvio = sugerida;
  campoFecha.value = sugerida;
  avisoFechaVencida.hidden = true;
  campoFecha.focus();
  cambioDelFormulario();
});

/** The reason a lot was not created, at the top and in an alert: the problems of a 422 each on its line, or the one sentence of the rest. */
function decirFalloDeCrear(caido: unknown): void {
  if (caido instanceof ApiError && caido.status === 409 && caido.cuerpo?.codigo === 'fecha_no_gestionable') {
    mostrarFechaVencida(caido.cuerpo as unknown as ErrorFechaNoGestionable);
    return;
  }
  const etiquetas = Object.fromEntries(estado.segmentos.map((s) => [s.clave, s.etiqueta]));
  const problemas = caido instanceof ApiError && Array.isArray(caido.cuerpo?.problemas) ? (caido.cuerpo.problemas as ProblemaCampana[]) : [];
  const delModulo = errorDeModulo(caido);
  const lineas =
    problemas.length > 0
      ? problemas.map((p) => textoDeProblemaConSegmento(p, etiquetas))
      : [delModulo ? textoDeCodigo(delModulo, delModulo as unknown as Record<string, string | number | null>) : mensajeDeError(caido)];
  $<HTMLElement>('[data-crear-error-lista]').replaceChildren(
    ...lineas.map((texto) => {
      const linea = document.createElement('p');
      linea.textContent = texto;
      return linea;
    }),
  );
  alertaCrear.hidden = false;
  alertaCrear.focus();
  alertaCrear.scrollIntoView({ block: 'start' });
}

/** Creates the whole lot with what the preview on screen showed, and shows the card to upload it; if it fails nothing was created. */
async function crear(): Promise<void> {
  const base = baseDeSeleccion();
  const entrada = base ? entradaDePrevisualizacion(base, borrador()) : null;
  const previa = estado.previa;
  if (!entrada || !previa || previa.campanas.length === 0) return;
  limpiarFalloDeCrear();
  estado.creando = true;
  ocupado(botonCrear, true);
  pintarCrear();
  try {
    const creadas = await crearCampanas(entradaDeCreacion(entrada, previa, borrador(), nombresActuales()));
    cerrarFormulario();
    const nombreDeSegmento = (clave: string | null): string | undefined => estado.segmentos.find((s) => s.clave === clave)?.etiqueta;
    ficha.mostrar(creadas, estado.adjuntos, (campana) => nombreDeSegmento(campana.segmento) ?? campana.nombre);
  } catch (caido) {
    decirFalloDeCrear(caido);
  } finally {
    estado.creando = false;
    ocupado(botonCrear, false);
    pintarCrear();
  }
}
botonCrear.addEventListener('click', () => void crear());

/**
 * The lot exists: the card takes the place of the preview and the form stops answering, so the same lot is not created twice by accident.
 * Another campaign starts from a clean page (what MOWA MES does).
 */
function cerrarFormulario(): void {
  panelPrevia.hidden = true;
  document.querySelectorAll<HTMLElement>('[data-formulario] > section.panel:not(#wm-sec-ficha)').forEach((seccion) => (seccion.inert = true));
  raiz.inert = true;
}
$<HTMLButtonElement>('[data-creada-otra]').addEventListener('click', () => window.location.reload());

// ---- 7. Preview ----------------------------------------------------------------------------------------------------------

const campanas = $<HTMLElement>('[data-campanas]');
const bloqueCampana = $<HTMLElement>('[data-campana]');
const pagerExclusiones = $<HTMLElement>('[data-exclusiones-pager]');
const pagerFuera = $<HTMLElement>('[data-fuera-pager]');

function marcarCalculando(si: boolean): void {
  panelPrevia.dataset.calculando = String(si);
  panelPrevia.setAttribute('aria-busy', String(si));
  pintarCrear();
}

function pintarExclusiones(campana: CampanaPrevista): void {
  const pagina = paginar(campana.exclusiones, estado.paginaExclusiones, FILAS_POR_PAGINA);
  estado.paginaExclusiones = pagina.pagina;
  $<HTMLElement>('[data-exclusiones]').replaceChildren(
    campana.exclusiones.length === 0 ? vacio(t('whatsmkt.previa.sinExclusiones')) : tablaDeExclusiones(pagina.filas),
  );
  pintarPaginador(pagerExclusiones, pagina.hayPaginador ? pagina : null);
  const truncadas = $<HTMLElement>('[data-exclusiones-truncadas]');
  const recortada = campana.total_exclusiones > campana.exclusiones.length;
  truncadas.hidden = !recortada;
  truncadas.textContent = recortada
    ? t('whatsmkt.previa.exclusionesTruncadas', { mostradas: formatNumber(campana.exclusiones.length), total: formatNumber(campana.total_exclusiones) })
    : '';
}

function pintarMuestra(campana: CampanaPrevista): void {
  const { envoltorio, cuerpo } = tabla('wm-muestra', campana.cabeceras.map((c) => [c.nombre, false] as [string, boolean]), { apilable: true });
  // Each header is the name as it goes in the file and, under it, the label of the column (muted).
  envoltorio.querySelectorAll('thead th').forEach((th, i) => {
    const etiqueta = campana.cabeceras[i].etiqueta;
    if (!etiqueta) return;
    const segunda = document.createElement('span');
    segunda.className = 'wm-cabecera__etiqueta';
    segunda.textContent = etiqueta;
    th.append(document.createElement('br'), segunda);
  });
  campana.muestra.forEach((fila) => {
    const nodo = document.createElement('tr');
    fila.celdas.forEach((valor, i) => {
      const dato = celda('td', valor ?? '', 'mono', campana.cabeceras[i]?.nombre ?? '');
      if (i === 0 && fila.supervision) {
        const marca = document.createElement('span');
        marca.className = 'tag tag--info';
        marca.textContent = t('whatsmkt.previa.cifra.supervision');
        dato.append(' ', marca);
      }
      nodo.append(dato);
    });
    cuerpo.append(nodo);
  });
  $<HTMLElement>('[data-muestra]').replaceChildren(envoltorio);
}

function pintarCampana(): void {
  const previa = estado.previa;
  const campana = previa?.campanas[estado.campanaElegida] ?? null;
  bloqueCampana.hidden = campana === null;
  if (!previa || !campana) return;

  $<HTMLElement>('[data-cifras]').replaceChildren(
    cifra(t('whatsmkt.previa.cifra.filas'), formatNumber(campana.cantidad), undefined, false, icono('filas')),
    cifra(t('whatsmkt.previa.cifra.supervision'), formatNumber(campana.supervisores), undefined, false, icono('supervision')),
    cifra(t('whatsmkt.previa.cifra.excluidos'), formatNumber(campana.total_exclusiones), undefined, false, icono('excluidos')),
  );
  const nombre = nombresActuales()[estado.campanaElegida] ?? '';
  $<HTMLElement>('[data-nombre-rotulo]').textContent =
    campana.etiqueta_segmento === null ? t('whatsmkt.seccion.nombre') : t('whatsmkt.nombre.resultante', { segmento: campana.etiqueta_segmento });
  $<HTMLElement>('[data-nombre-resultante]').textContent = nombre;
  const ejemplo = $<HTMLElement>('[data-ejemplo]');
  $<HTMLElement>('[data-ejemplo-bloque]').hidden = campana.mensaje_ejemplo === null;
  ejemplo.textContent = campana.mensaje_ejemplo ?? '';
  pintarMuestra(campana);
  pintarExclusiones(campana);
}

function pintarSelectorDeCampanas(): void {
  const lista = estado.previa?.campanas ?? [];
  campanas.hidden = lista.length < 2;
  campanas.replaceChildren(
    ...lista.map((campana, indice) => {
      const boton = document.createElement('button');
      boton.type = 'button';
      boton.className = 'segmented__item';
      boton.setAttribute('aria-pressed', String(indice === estado.campanaElegida));
      boton.textContent = `${campana.etiqueta_segmento ?? ''} (${formatNumber(campana.cantidad)})`;
      boton.addEventListener('click', () => {
        estado.campanaElegida = indice;
        estado.paginaExclusiones = 1;
        pintarSelectorDeCampanas();
        pintarCampana();
      });
      return boton;
    }),
  );
}

function pintarFuera(): void {
  const previa = estado.previa;
  const visible = previa !== null && borrador().modo === 'por_segmento' && previa.total_exclusiones_sin_campana > 0;
  $<HTMLElement>('[data-fuera]').hidden = !visible;
  if (!previa || !visible) return;
  $<HTMLElement>('[data-fuera-titulo]').textContent = t('whatsmkt.previa.fuera.titulo', { n: formatNumber(previa.total_exclusiones_sin_campana) });
  const pagina = paginar(previa.exclusiones_sin_campana, estado.paginaFuera, FILAS_POR_PAGINA);
  estado.paginaFuera = pagina.pagina;
  $<HTMLElement>('[data-fuera-tabla]').replaceChildren(tablaDeExclusiones(pagina.filas));
  pintarPaginador(pagerFuera, pagina.hayPaginador ? pagina : null);
  const recortada = previa.total_exclusiones_sin_campana > previa.exclusiones_sin_campana.length;
  const aviso = $<HTMLElement>('[data-fuera-truncadas]');
  aviso.hidden = !recortada;
  aviso.textContent = recortada
    ? t('whatsmkt.previa.fuera.truncadas', {
        mostradas: formatNumber(previa.exclusiones_sin_campana.length),
        total: formatNumber(previa.total_exclusiones_sin_campana),
      })
    : '';
}

function pintarResumen(): void {
  const resumen = $<HTMLElement>('[data-resumen]');
  const previa = estado.previa;
  if (!previa || previa.campanas.length === 0) {
    resumen.replaceChildren();
    return;
  }
  const filas = previa.campanas.reduce((suma, c) => suma + c.cantidad, 0);
  const principal =
    previa.campanas.length > 1
      ? t('whatsmkt.previa.resumenVarias', { n: previa.campanas.length, filas: formatNumber(filas) })
      : t('whatsmkt.previa.resumenUna', { filas: formatNumber(filas) });
  resumen.replaceChildren(document.createTextNode(principal));
  const fuera = previa.total_exclusiones_sin_campana;
  if (fuera > 0 && borrador().modo === 'por_segmento') {
    // The products out of every campaign are counted here and listed below: the sentence links to their table.
    const enlace = document.createElement('a');
    enlace.href = '#wm-fuera-titulo';
    enlace.textContent = t(fuera === 1 ? 'whatsmkt.previa.resumenFueraUno' : 'whatsmkt.previa.resumenFuera', { n: formatNumber(fuera) }).replace(/^·\s*/, '');
    resumen.append(' · ', enlace);
  }
}

function pintarPrevia(): void {
  const previa = estado.previa;
  pintarResumen();
  const sinCampanas = previa !== null && previa.campanas.length === 0;
  const aviso = $<HTMLElement>('[data-sin-campanas]');
  aviso.hidden = !sinCampanas;
  if (sinCampanas) {
    const problema = previa.problemas.find((p) => p.codigo === 'sin_productos');
    $<HTMLElement>('[data-sin-campanas-texto]').textContent = problema ? textoDeProblema(problema) : t('whatsmkt.codigo.sin_productos');
  }
  if (previa && estado.campanaElegida >= previa.campanas.length) estado.campanaElegida = 0;
  pintarSelectorDeCampanas();
  pintarCampana();
  pintarFuera();
  pintarProblemasDeMensaje();
  pintarFecha();
  pintarProblemas();
  pintarNombre();
}

/** What the selection says, if it is enough to ask for a preview; the reason it is not shows in the guard notice. */
function baseDeSeleccion(): SeleccionBase | null {
  const seleccion = estado.seleccion;
  const guardia = $<HTMLElement>('[data-guardia]');
  const decir = (clave: string | null): null => {
    guardia.hidden = clave === null;
    if (clave !== null) $<HTMLElement>('[data-guardia-texto]').textContent = t(clave);
    return null;
  };
  if (!seleccion || !seleccion.fechaCorte || !seleccion.guardada || !seleccion.aplicable) return decir(seleccion?.guardada ? null : 'whatsmkt.campana.sinSeleccion');
  if (seleccion.consulta.cantidad === null) return decir('whatsmkt.campana.sinCantidad');
  decir(null);
  return { fechaCorte: seleccion.fechaCorte, consulta: seleccion.consulta, guardadaId: seleccion.guardada.id };
}

/** Ask for the preview of what the form holds now; a newer ask cancels the older one. */
function programarPrevia(espera = ESPERA_PREVIA): void {
  window.clearTimeout(temporizador);
  controlPrevia?.abort();
  const base = baseDeSeleccion();
  formulario.hidden = base === null;
  const entrada = base ? entradaDePrevisualizacion(base, borrador()) : null;
  $<HTMLElement>('[data-previa-error]').textContent = '';
  if (!entrada) {
    estado.previa = null;
    marcarCalculando(false);
    pintarPrevia();
    return;
  }
  const control = new AbortController();
  controlPrevia = control;
  marcarCalculando(true);
  temporizador = window.setTimeout(async () => {
    try {
      const respuesta = await previsualizarCampanas(entrada, control.signal);
      if (control.signal.aborted) return;
      estado.previa = respuesta;
    } catch (caido) {
      if (caido instanceof DOMException && caido.name === 'AbortError') return;
      estado.previa = null;
      $<HTMLElement>('[data-previa-error]').textContent = mensajeDeError(caido);
    }
    if (controlPrevia === control) marcarCalculando(false);
    pintarPrevia();
  }, espera);
}

/** Every field that changes what the preview says asks again; the problems and the counter are painted at once. */
function cambioDelFormulario(): void {
  pintarProblemas();
  pintarNombre();
  programarPrevia();
}

pagerExclusiones.querySelector('[data-page-prev]')!.addEventListener('click', () => {
  estado.paginaExclusiones -= 1;
  const campana = estado.previa?.campanas[estado.campanaElegida];
  if (campana) pintarExclusiones(campana);
});
pagerExclusiones.querySelector('[data-page-next]')!.addEventListener('click', () => {
  estado.paginaExclusiones += 1;
  const campana = estado.previa?.campanas[estado.campanaElegida];
  if (campana) pintarExclusiones(campana);
});
pagerFuera.querySelector('[data-page-prev]')!.addEventListener('click', () => {
  estado.paginaFuera -= 1;
  pintarFuera();
});
pagerFuera.querySelector('[data-page-next]')!.addEventListener('click', () => {
  estado.paginaFuera += 1;
  pintarFuera();
});

// ---- 1. Base: the selection, and «Editar en Cartera» ------------------------------------------------------------------

raiz.addEventListener(EVENTO_SELECCION, (evento) => {
  estado.seleccion = (evento as CustomEvent<EstadoSeleccion>).detail ?? controlador?.estado() ?? null;
  pintarEditarEnCartera();
  estado.campanaElegida = 0;
  programarPrevia(0);
});

/** The button is on only with a saved selection to edit; without one it says what to do, in its `title`. */
function pintarEditarEnCartera(): void {
  if (!botonEditar) return;
  const hay = Boolean(estado.seleccion?.guardada);
  botonEditar.disabled = !hay;
  if (hay) botonEditar.removeAttribute('title');
  else botonEditar.title = t('whatsmkt.base.editarInactivo');
}

/** «Editar en Cartera» goes next to the saved-selection list, which the selector draws and knows nothing of this. */
function montarEditarEnCartera(): void {
  const campo = raiz.querySelector('[data-selector-guardada]')?.closest('.field');
  if (!campo) return;
  const boton = document.createElement('button');
  boton.type = 'button';
  boton.className = 'btn btn--sm wm-editar-cartera';
  const etiqueta = document.createElement('span');
  etiqueta.dataset.i18n = 'whatsmkt.base.editarEnCartera';
  etiqueta.textContent = t('whatsmkt.base.editarEnCartera');
  boton.append(icono('editar-cartera'), etiqueta);
  boton.addEventListener('click', () => {
    const id = estado.seleccion?.guardada?.id;
    // Cartera brings the analyst back with `?seleccion=<id>` (`restaurarAlVolver`); the rest of the form comes back as new.
    if (id !== undefined) window.location.assign(enlaceEditarEnCartera(id, VUELTA));
  });
  campo.append(boton);
  botonEditar = boton;
  pintarEditarEnCartera();
}

/** Coming back from Cartera: the selection `?seleccion=` names is loaded; if it is gone, none is chosen and a notice says why. */
function restaurarAlVolver(): void {
  if (!controlador) return;
  const id = seleccionDeLaUrl(window.location.search);
  if (id !== null && !controlador.cargarGuardada(id)) $<HTMLElement>('[data-seleccion-borrada]').hidden = false;
  if (new URLSearchParams(window.location.search).has('seleccion')) window.history.replaceState(null, '', window.location.pathname);
}

// ---- Boot -----------------------------------------------------------------------------------------------------------------

function sinConexion(si: boolean): void {
  $<HTMLElement>('[data-offline]').hidden = !si;
  $<HTMLElement>('[data-contenido]').hidden = si;
  document.dispatchEvent(new CustomEvent('healthchanged'));
}

/** A list that fails is said in its section; the rest of the screen goes on. */
async function leer<T>(pedido: Promise<T>, vacio: T, alFallar: (texto: string) => void): Promise<T> {
  try {
    return await pedido;
  } catch (caido) {
    if (caido instanceof NetworkError) throw caido;
    alFallar(mensajeDeError(caido));
    return vacio;
  }
}

function repintarTodo(): void {
  if (!estado.configuracion || !estado.borrador) return;
  pintarDefinicion();
  pintarColumnas();
  pintarMensajes();
  pintarHorarios();
  pintarFecha();
  pintarEnvio();
  pintarNombre();
  pintarEditarEnCartera();
  pintarPrevia();
  ficha.repintar();
}

async function arrancar(): Promise<void> {
  try {
    const [configuracion, segmentos] = await Promise.all([obtenerConfiguracion(), listarSegmentos()]);
    estado.configuracion = configuracion;
    estado.segmentos = segmentos;
    estado.borrador = borradorInicial(configuracion, segmentos);
    const [textos, adjuntos, definiciones, programacion] = await Promise.all([
      leer(listarTextos('whatsmkt.mensaje'), [] as ResumenTexto[], (texto) => (estado.errorMensajes = texto)),
      leer(listarAdjuntos(false), [] as AdjuntoWhatsmkt[], (texto) => (estado.errorAdjuntos = texto)),
      leer(listarDefiniciones(), [] as ResumenDefinicion[], (texto) => (estado.errorDefinicion = texto)),
      leer(obtenerProgramacion(), null as ProgramacionWhatsmkt | null, (texto) => (estado.errorProgramacion = texto)),
    ]);
    estado.textos = textos;
    estado.adjuntos = adjuntos;
    estado.definiciones = definicionesDeWhatsmkt(definiciones);
    estado.programacion = programacion;
    // The date comes filled with the suggested working day; the analyst can change it.
    if (programacion && borrador().fechaEnvio === '') borrador().fechaEnvio = programacion.sugerida;
    // The default definition, if it is still one of the platform's.
    if (!estado.definiciones.some((d) => d.id === borrador().definicionId)) borrador().definicionId = null;

    sinConexion(false);
    pintarDefinicion();
    pintarMensajes();
    pintarHorarios();
    pintarFecha();
    pintarEnvio();
    montarNombre();
    pintarProblemas();
    void cargarColumnas();

    if (!montado) {
      controlador = await montarSelector(raiz);
      montado = true;
      montarEditarEnCartera();
      restaurarAlVolver();
      estado.seleccion = controlador.estado();
      programarPrevia(0);
    }
  } catch (caido) {
    if (caido instanceof NetworkError) {
      sinConexion(true);
    } else {
      sinConexion(false);
      mostrarError(caido);
    }
  }
}

const reintentar = $<HTMLButtonElement>('[data-reintentar]');
reintentar.addEventListener('click', async () => {
  ocupado(reintentar, true);
  try {
    await arrancar();
  } finally {
    ocupado(reintentar, false);
  }
});

document.addEventListener('languagechange', () => {
  applyTranslations();
  repintarTodo();
});

void arrancar();
