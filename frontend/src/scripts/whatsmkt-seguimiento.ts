/**
 * The WhatsMKT tracking screen (T-WM-F3a, docs/whatsmkt-interfaz.md §4): the campaigns created, active or discarded, with their filters, and the
 * detail of one. The rules that need no browser are in `lib/whatsmkt-seguimiento.ts`; this binds them to the markup of `pages/whatsmkt/seguimiento.astro`
 * by data attributes. The API counts (active, discarded, pending the report); this filters and pages what it gave (see the shortcut of the lib).
 * Discarding, restoring and deleting go through one confirmation; deleting is only for a discarded campaign and says it cannot be undone.
 */

import { ApiError, NetworkError, mensajeDeError } from '../lib/api';
import {
  descargarArchivoCampana,
  descargarAdjunto,
  descartarCampana,
  eliminarCampana,
  importarInforme,
  listarAdjuntos,
  listarCampanas,
  obtenerCampana,
  obtenerConciliacion,
  restaurarCampana,
  type AdjuntoWhatsmkt,
  type DetalleCampana,
  type EstadoInforme,
  type ResumenCampana,
} from '../lib/api-whatsmkt';
import { guardarArchivo } from '../lib/descargas';
import { openWhenFree } from '../lib/dialogs';
import { $, ocupado } from '../lib/dom';
import { formatDate, formatNumber } from '../lib/format';
import { applyTranslations, t } from '../lib/i18n';
import { FILAS_POR_PAGINA, paginar, pintarPaginador } from '../lib/paginacion';
import { celda, celdaDeFila, cifra, tabla, vacio } from '../lib/tabla-dom';
import { datosDeFicha } from '../lib/whatsmkt-campana';
import {
  CAMPANAS_POR_PAGINA,
  LIMITE_DE_CAMPANAS,
  SIN_FILTRO,
  avisoDeTotalDistinto,
  busquedaConVista,
  campanaDeLaUrl,
  cifrasDeDetalle,
  encabezadoDeDetalle,
  estadoDeFila,
  fechaDeDescarte,
  fechasDeDetalle,
  filtrarCampanas,
  fueraDelLoteVisible,
  lineaDeInforme,
  lotesDeLista,
  mesesDeLista,
  opcionesDeMeses,
  pendienteDeInforme,
  segmentosDeLista,
  tablasDeConciliacion,
  textoDeHorarios,
  textoDeNombreInformado,
  textoDePendientes,
  textoSinCorrespondencia,
  vistaDeLaUrl,
  type FiltroDeLista,
  type TablaDeConciliacion,
  type VistaCampanas,
} from '../lib/whatsmkt-seguimiento';
import { textoDeCodigo } from '../lib/whatsmkt';
import { tablaDeExclusiones } from './whatsmkt-exclusiones';
import { filaDeArchivo, pintarDatosDeFicha } from './whatsmkt-ficha-partes';

/** What the API said about the exclusions of a detail is asked in one go; more than this are not listed (the total is still said). */
const EXCLUSIONES_POR_PEDIDO = 1000;

const estado = {
  vista: vistaDeLaUrl(window.location.search) as VistaCampanas,
  /** The campaigns of the view, as the API gave them (the latest first). */
  campanas: [] as ResumenCampana[],
  totales: { activas: 0, descartadas: 0, pendientes: 0 },
  filtro: { ...SIN_FILTRO } as FiltroDeLista,
  pagina: 1,
  /** Every attachment of the library, archived or not: a campaign may have used one that was archived since. */
  adjuntos: [] as AdjuntoWhatsmkt[],
  detalle: null as DetalleCampana | null,
  /** The report of the campaign open and its reconciliation; `null` while it has none (or while it could not be read: `errorConciliacion` says it). */
  informe: null as EstadoInforme | null,
  errorConciliacion: '',
  paginaExclusiones: 1,
  paginaFuera: 1,
};

const dialogoError = $<HTMLDialogElement>('[data-dialog="error"]');
const dialogoConfirmar = $<HTMLDialogElement>('[data-dialog="confirmar"]');
document.querySelectorAll<HTMLElement>('[data-close]').forEach((boton) => {
  boton.addEventListener('click', () => boton.closest('dialog')?.close());
});

const icono = (clave: string): Node => $<HTMLTemplateElement>(`template[data-icono-${clave}]`).content.cloneNode(true);

function mostrarError(error: unknown): void {
  $<HTMLElement>('[data-error-body]').textContent = mensajeDeError(error);
  void openWhenFree(dialogoError);
}

/** The sentence of a refusal by its code (409 `campana_no_descartada`…), or the server's own. */
function textoDeFallo(caido: unknown): string {
  const codigo = caido instanceof ApiError ? caido.cuerpo?.codigo : undefined;
  return typeof codigo === 'string'
    ? textoDeCodigo({ codigo: codigo as Parameters<typeof textoDeCodigo>[0]['codigo'], detail: mensajeDeError(caido) })
    : mensajeDeError(caido);
}

function sinConexion(si: boolean): void {
  $<HTMLElement>('[data-offline]').hidden = !si;
  $<HTMLElement>('[data-contenido]').hidden = si;
  document.dispatchEvent(new CustomEvent('healthchanged'));
}

// ---- The list -------------------------------------------------------------------------------------------------

const contenedorTabla = $<HTMLElement>('[data-tabla]');
const paginador = $<HTMLElement>('[data-pager]');
const estadoLista = $<HTMLElement>('[data-lista-estado]');
const selectores = {
  mes: $<HTMLSelectElement>('[data-filtro="mes"]'),
  lote: $<HTMLSelectElement>('[data-filtro="lote"]'),
  segmento: $<HTMLSelectElement>('[data-filtro="segmento"]'),
};

function opcion(valor: string, texto: string): HTMLOptionElement {
  const nodo = document.createElement('option');
  nodo.value = valor;
  nodo.textContent = texto;
  return nodo;
}

/** The options of each filter come from the campaigns of the view; one that no campaign has any more is dropped, with its filter. */
function pintarFiltros(): void {
  const todos = t('whatsmkt.seguimiento.filtro.todos');
  const meses = opcionesDeMeses(mesesDeLista(estado.campanas));
  const lotes = lotesDeLista(estado.campanas);
  const segmentos = segmentosDeLista(estado.campanas);
  if (!meses.some((m) => m.valor === estado.filtro.mes)) estado.filtro.mes = '';
  if (estado.filtro.lote !== null && !lotes.includes(estado.filtro.lote)) estado.filtro.lote = null;
  if (!segmentos.some((s) => s.valor === estado.filtro.segmento)) estado.filtro.segmento = '';
  selectores.mes.replaceChildren(opcion('', todos), ...meses.map((m) => opcion(m.valor, m.texto)));
  selectores.lote.replaceChildren(opcion('', todos), ...lotes.map((l) => opcion(String(l), String(l))));
  selectores.segmento.replaceChildren(opcion('', todos), ...segmentos.map((s) => opcion(s.valor, s.texto)));
  selectores.mes.value = estado.filtro.mes;
  selectores.lote.value = estado.filtro.lote === null ? '' : String(estado.filtro.lote);
  selectores.segmento.value = estado.filtro.segmento;
}

selectores.mes.addEventListener('change', () => cambiarFiltro({ mes: selectores.mes.value }));
selectores.lote.addEventListener('change', () => cambiarFiltro({ lote: selectores.lote.value === '' ? null : Number(selectores.lote.value) }));
selectores.segmento.addEventListener('change', () => cambiarFiltro({ segmento: selectores.segmento.value }));

function cambiarFiltro(cambio: Partial<FiltroDeLista>): void {
  estado.filtro = { ...estado.filtro, ...cambio };
  estado.pagina = 1;
  pintarLista();
}

function pintarVistas(): void {
  document.querySelectorAll<HTMLButtonElement>('[data-vista]').forEach((boton) => {
    const vista = boton.dataset.vista as VistaCampanas;
    const cantidad = vista === 'activas' ? estado.totales.activas : estado.totales.descartadas;
    boton.textContent = t(`mowaMes.seguimiento.vista.${vista}`, { n: formatNumber(cantidad) });
    boton.setAttribute('aria-pressed', String(vista === estado.vista));
  });
}

function boton(clave: string, texto: string, nombre: string, alPulsar: () => void, clase = 'btn btn--sm'): HTMLButtonElement {
  const nodo = document.createElement('button');
  nodo.type = 'button';
  nodo.className = clase;
  nodo.setAttribute('aria-label', `${texto} ${nombre}`);
  nodo.append(icono(clave), document.createTextNode(texto));
  nodo.addEventListener('click', alPulsar);
  return nodo;
}

function marcaDeEstado(campana: ResumenCampana): Node {
  const situacion = estadoDeFila(campana);
  const marca = document.createElement('span');
  if (situacion === 'conciliada') return document.createTextNode('');
  marca.className = situacion === 'pendiente' ? 'tag tag--advertencia' : 'tag tag--neutral';
  if (situacion === 'pendiente') marca.append(icono('pendiente'), document.createTextNode(t('whatsmkt.estado.pendienteInforme')));
  else marca.append(icono('descartar'), document.createTextNode(t('mowaMes.estado.descartada')));
  return marca;
}

function filaDeCampana(campana: ResumenCampana): HTMLTableRowElement {
  const fila = document.createElement('tr');
  fila.dataset.campana = String(campana.id);
  const lote = celda('td', '', 'mono', t('whatsmkt.seguimiento.col.lote'));
  const verLote = document.createElement('button');
  verLote.type = 'button';
  verLote.className = 'wm-enlace mono';
  verLote.textContent = String(campana.lote_id);
  verLote.setAttribute('aria-label', t('whatsmkt.seguimiento.verLote', { lote: campana.lote_id }));
  verLote.addEventListener('click', () => cambiarFiltro({ lote: campana.lote_id }));
  lote.append(verLote);
  const estadoCelda = celda('td', '', '', t('whatsmkt.seguimiento.col.estado'));
  estadoCelda.append(marcaDeEstado(campana));
  const acciones = celda('td', '', 'wm-seg__acciones', t('whatsmkt.seguimiento.col.accion'));
  const nombre = campana.nombre;
  acciones.append(boton('ver', t('mowaMes.accion.ver'), nombre, () => void abrir(campana.id)));
  if (campana.descartada_en === null) {
    acciones.append(
      boton('descargar', t('whatsmkt.biblioteca.descargar'), nombre, () => void descargarArchivoDeLista(campana)),
      boton('descartar', t('mowaMes.accion.descartar'), nombre, () => confirmarDescartar(campana)),
    );
  } else {
    acciones.append(
      boton('restaurar', t('mowaMes.accion.restaurar'), nombre, () => confirmarRestaurar(campana)),
      boton('eliminar', t('mowaMes.accion.eliminar'), nombre, () => confirmarEliminar(campana), 'btn btn--sm btn--danger'),
    );
  }
  fila.append(
    celdaDeFila(String(campana.id), 'mono', t('whatsmkt.seguimiento.col.numero')),
    celda('td', formatDate(campana.creada_en.slice(0, 10)), '', t('whatsmkt.seguimiento.col.creada')),
    celda('td', campana.nombre, 'mono wm-seg__nombre', t('whatsmkt.seguimiento.col.nombre')),
    lote,
    celda('td', campana.segmento_etiqueta ?? t('whatsmkt.seguimiento.filtro.global'), '', t('whatsmkt.seguimiento.col.segmento')),
    celda('td', `${formatDate(campana.fecha_envio)} · ${textoDeHorarios(campana)}`, '', t('whatsmkt.seguimiento.col.envio')),
    celda('td', formatNumber(campana.cantidad), 'num', t('whatsmkt.seguimiento.col.filas')),
    estadoCelda,
    acciones,
  );
  return fila;
}

function pintarLista(): void {
  pintarVistas();
  pintarFiltros();
  const textoPendientes = textoDePendientes(estado.totales.pendientes);
  $<HTMLElement>('[data-pendientes]').hidden = textoPendientes === null || estado.vista === 'descartadas';
  $<HTMLElement>('[data-pendientes-texto]').textContent = textoPendientes ?? '';

  const visibles = filtrarCampanas(estado.campanas, estado.filtro);
  const pagina = paginar(visibles, estado.pagina, CAMPANAS_POR_PAGINA);
  estado.pagina = pagina.pagina;
  if (visibles.length === 0) {
    const sinNada = estado.campanas.length === 0;
    contenedorTabla.replaceChildren(
      vacio(
        sinNada
          ? estado.vista === 'descartadas'
            ? t('mowaMes.seguimiento.descartadas.vacio')
            : t('whatsmkt.seguimiento.sinCampanas')
          : t('whatsmkt.seguimiento.vacia'),
      ),
    );
  } else {
    const { envoltorio, cuerpo } = tabla(
      'wm-seg-tabla',
      [
        [t('whatsmkt.seguimiento.col.numero'), false],
        [t('whatsmkt.seguimiento.col.creada'), false],
        [t('whatsmkt.seguimiento.col.nombre'), false],
        [t('whatsmkt.seguimiento.col.lote'), false],
        [t('whatsmkt.seguimiento.col.segmento'), false],
        [t('whatsmkt.seguimiento.col.envio'), false],
        [t('whatsmkt.seguimiento.col.filas'), true],
        [t('whatsmkt.seguimiento.col.estado'), false],
        [t('whatsmkt.seguimiento.col.accion'), false],
      ],
      { apilable: true },
    );
    envoltorio.querySelector('table')!.setAttribute('aria-label', t('whatsmkt.seguimiento.tabla'));
    pagina.filas.forEach((campana) => cuerpo.append(filaDeCampana(campana)));
    contenedorTabla.replaceChildren(envoltorio);
  }
  pintarPaginador(paginador, pagina.hayPaginador ? pagina : null);
}

paginador.querySelector('[data-page-prev]')!.addEventListener('click', () => {
  estado.pagina -= 1;
  pintarLista();
});
paginador.querySelector('[data-page-next]')!.addEventListener('click', () => {
  estado.pagina += 1;
  pintarLista();
});

document.querySelectorAll<HTMLButtonElement>('[data-vista]').forEach((boton) => {
  boton.addEventListener('click', () => void cambiarVista(boton.dataset.vista as VistaCampanas));
});

/** Another view starts from a clean filter; the URL keeps the view (the active one is the default and says nothing). */
async function cambiarVista(vista: VistaCampanas): Promise<void> {
  if (vista === estado.vista) return;
  const antes = { vista: estado.vista, filtro: estado.filtro, pagina: estado.pagina, busqueda: window.location.search };
  estado.vista = vista;
  estado.filtro = { ...SIN_FILTRO };
  estado.pagina = 1;
  window.history.replaceState(null, '', `${window.location.pathname}${busquedaConVista(window.location.search, vista)}`);
  if (await cargarLista()) return;
  // The other view did not load and the screen still shows this one: the view, the filter and the URL stay with what is on screen.
  Object.assign(estado, { vista: antes.vista, filtro: antes.filtro, pagina: antes.pagina });
  window.history.replaceState(null, '', `${window.location.pathname}${antes.busqueda}`);
}

const listaVieja = $<HTMLElement>('[data-lista-vieja]');

/**
 * Reads the view from the API and paints it; false when it could not (and the screen says why). At the start (`alArrancar`) any failure, not only
 * a lost connection, stands the screen down with its «Reintentar»: there is no list to show yet.
 */
async function cargarLista(alArrancar = false): Promise<boolean> {
  try {
    const lista = await listarCampanas({ estado: estado.vista, limite: LIMITE_DE_CAMPANAS, desplazamiento: 0 });
    estado.campanas = lista.campanas;
    estado.totales = { activas: lista.total_activas, descartadas: lista.total_descartadas, pendientes: lista.total_pendientes };
    listaVieja.hidden = true;
    pintarLista();
    return true;
  } catch (caido) {
    if (caido instanceof NetworkError || alArrancar) sinConexion(true);
    else mostrarError(caido);
    return false;
  }
}

/** After an action that worked, the list is read again; if that fails it is not left old in silence: a notice says so and offers to try again. */
async function refrescarLista(): Promise<void> {
  if (!(await cargarLista())) listaVieja.hidden = false;
}

const reintentarLista = $<HTMLButtonElement>('[data-lista-reintentar]');
reintentarLista.addEventListener('click', async () => {
  ocupado(reintentarLista, true);
  try {
    await cargarLista();
  } finally {
    ocupado(reintentarLista, false);
  }
});

async function descargarArchivoDeLista(campana: ResumenCampana): Promise<void> {
  try {
    const archivo = await descargarArchivoCampana(campana.id);
    guardarArchivo(archivo.blob, archivo.nombre || `${campana.nombre}.xlsx`);
  } catch (caido) {
    mostrarError(caido);
  }
}

// ---- The detail ---------------------------------------------------------------------------------------------------

const panelDetalle = $<HTMLElement>('[data-detalle]');
const detalleEstadoCopia = $<HTMLElement>('[data-detalle-copia-estado]');
const detalleErrorDescarga = $<HTMLElement>('[data-detalle-descarga-error]');
const pagerExclusiones = $<HTMLElement>('[data-pager-exclusiones]');
const pagerFuera = $<HTMLElement>('[data-pager-fuera]');
const cajaFuera = $<HTMLDetailsElement>('[data-detalle-fuera]');

const nombreDeAdjunto = (id: number, respaldo: string): string => estado.adjuntos.find((a) => a.id === id)?.nombre ?? respaldo;

function pintarDetalle(): void {
  const detalle = estado.detalle;
  panelDetalle.hidden = detalle === null;
  if (!detalle) return;
  $<HTMLElement>('[data-detalle-titulo]').textContent = encabezadoDeDetalle(detalle);
  $<HTMLElement>('[data-detalle-fechas]').textContent = fechasDeDetalle(detalle);
  $<HTMLElement>('[data-detalle-pendiente]').hidden = !pendienteDeInforme(detalle);
  const descartada = detalle.descartada_en !== null;
  $<HTMLElement>('[data-detalle-descartada]').hidden = !descartada;
  $<HTMLElement>('[data-detalle-descartada-texto]').textContent = descartada
    ? t('mowaMes.seguimiento.descartadas.el', { fecha: fechaDeDescarte(detalle.descartada_en!) })
    : '';

  const iconoDe = { productos: 'productos', supervision: 'supervision', total: 'total', excluidos: 'excluidos', enviados: 'enviados', noEnviados: 'noEnviados' } as const;
  $<HTMLElement>('[data-detalle-cifras]').replaceChildren(
    ...cifrasDeDetalle(detalle, estado.informe?.conciliacion ?? null).map((c) =>
      cifra(t(`whatsmkt.seguimiento.cifra.${c.clave}`), formatNumber(c.valor), undefined, false, icono(iconoDe[c.clave])),
    ),
  );

  // The files in the order they are asked for: the list of contacts, the photo, the attachment.
  const alFallar = (texto: string): void => {
    detalleErrorDescarga.textContent = texto;
  };
  const ficha = detalle.ficha;
  const archivos: HTMLElement[] = [filaDeArchivo(t('whatsmkt.subir.archivo.lista'), detalle.archivo.nombre, () => descargarArchivoCampana(detalle.id), alFallar)];
  if (ficha.foto_id !== null) {
    const id = ficha.foto_id;
    archivos.push(filaDeArchivo(t('whatsmkt.subir.archivo.foto'), nombreDeAdjunto(id, t('whatsmkt.envio.foto')), () => descargarAdjunto(id), alFallar));
  }
  if (ficha.adjunto_id !== null) {
    const id = ficha.adjunto_id;
    archivos.push(filaDeArchivo(t('whatsmkt.subir.archivo.adjunto'), nombreDeAdjunto(id, t('whatsmkt.envio.adjunto')), () => descargarAdjunto(id), alFallar));
  }
  $<HTMLElement>('[data-detalle-archivos]').replaceChildren(...archivos);
  detalleErrorDescarga.textContent = '';

  // The card of the form, with the message as it was frozen when the campaign was created.
  pintarDatosDeFicha($<HTMLElement>('[data-detalle-datos]'), datosDeFicha(ficha, estado.adjuntos), (texto) => (detalleEstadoCopia.textContent = texto));
  detalleEstadoCopia.textContent = '';

  pintarInforme();
  pintarExclusiones();
  pintarFuera();
}

// ---- The report and its reconciliation (RF-WM-37 to RF-WM-41) -----------------------------------------------------

const formInforme = $<HTMLFormElement>('[data-form-informe]');
const inputInforme = $<HTMLInputElement>('#wm-informe');
const nombreInforme = $<HTMLElement>('[data-informe-nombre]');
const errorInforme = $<HTMLElement>('[data-informe-error]');
const estadoInforme = $<HTMLElement>('[data-informe-estado]');
const bloqueConciliacion = $<HTMLElement>('[data-conciliacion]');

/** The form of the report is for a campaign that is alive; a discarded one says to restore it first. The reconciliation is there only with a report. */
function pintarInforme(): void {
  const detalle = estado.detalle;
  if (!detalle) return;
  const descartada = detalle.descartada_en !== null;
  formInforme.hidden = descartada;
  $<HTMLElement>('[data-informe-descartada]').hidden = !descartada;
  $<HTMLElement>('[data-conciliacion-error]').textContent = estado.errorConciliacion;

  const informe = estado.informe?.informe ?? null;
  const conciliacion = estado.informe?.conciliacion ?? null;
  bloqueConciliacion.hidden = informe === null || conciliacion === null;
  if (informe === null || conciliacion === null) return;

  $<HTMLElement>('[data-conciliacion-linea]').textContent = lineaDeInforme(informe);
  const total = avisoDeTotalDistinto(informe);
  $<HTMLElement>('[data-conciliacion-total]').hidden = total === null;
  $<HTMLElement>('[data-conciliacion-total-texto]').textContent = total ?? '';
  $<HTMLElement>('[data-conciliacion-tablas]').replaceChildren(...tablasDeConciliacion(conciliacion).map(tablaDeConciliacionDom));
  // shortcut: every number with no match is drawn, however many; upgrade with a folded list if a report ever brings thousands.
  const sin = textoSinCorrespondencia(conciliacion);
  $<HTMLElement>('[data-conciliacion-sin]').hidden = sin === null;
  $<HTMLElement>('[data-conciliacion-sin-texto]').textContent = sin ?? '';
  $<HTMLElement>('[data-conciliacion-sin-lista]').replaceChildren(
    ...conciliacion.sin_correspondencia.map((numero) => {
      const nodo = document.createElement('span');
      nodo.textContent = numero;
      return nodo;
    }),
  );
  const nombre = textoDeNombreInformado(informe);
  const lineaNombre = $<HTMLElement>('[data-conciliacion-nombre]');
  lineaNombre.hidden = nombre === null;
  lineaNombre.textContent = nombre ?? '';
}

/** One table, stacked at 360 px, with the loaded, the sent and the not sent of the products or of the supervision. */
function tablaDeConciliacionDom(fila: TablaDeConciliacion): HTMLElement {
  const titulo = t(`whatsmkt.conciliacion.${fila.clave}`);
  const columnas = (['cargados', 'enviados', 'noEnviados'] as const).map((c) => t(`whatsmkt.conciliacion.col.${c}`));
  const { envoltorio, cuerpo } = tabla('wm-conciliacion', columnas.map((c) => [c, false] as [string, boolean]), { apilable: true });
  envoltorio.querySelector('table')!.setAttribute('aria-label', titulo);
  const cifras = [fila.cargados, fila.enviados, fila.noEnviados];
  const tr = document.createElement('tr');
  tr.append(...cifras.map((valor, i) => celda('td', formatNumber(valor), 'mono', columnas[i])));
  cuerpo.append(tr);
  // The same column as the sections of the detail (`wm-form`), so its subtitle has the room that “Exclusiones” has.
  const bloque = document.createElement('div');
  bloque.className = 'wm-form';
  const encabezado = document.createElement('h4');
  encabezado.className = 'wm-subtitulo';
  encabezado.textContent = titulo;
  bloque.append(encabezado, envoltorio);
  return bloque;
}

function limpiarErrorInforme(): void {
  errorInforme.textContent = '';
  inputInforme.removeAttribute('aria-invalid');
  inputInforme.setAttribute('aria-describedby', 'wm-informe-hint');
}

function fallarInforme(texto: string): void {
  errorInforme.textContent = texto;
  inputInforme.setAttribute('aria-invalid', 'true');
  inputInforme.setAttribute('aria-describedby', 'wm-informe-hint wm-informe-error');
}

function reiniciarInforme(): void {
  formInforme.reset();
  nombreInforme.dataset.i18n = 'mowaMes.seguimiento.reporte.sinArchivo';
  nombreInforme.textContent = t('mowaMes.seguimiento.reporte.sinArchivo');
  limpiarErrorInforme();
  estadoInforme.textContent = '';
}

inputInforme.addEventListener('change', () => {
  limpiarErrorInforme();
  const archivo = inputInforme.files?.[0];
  if (!archivo) return;
  nombreInforme.textContent = archivo.name;
  delete nombreInforme.dataset.i18n;
});

$<HTMLButtonElement>('[data-ir-informe]').addEventListener('click', () => {
  inputInforme.scrollIntoView({ block: 'center' });
  inputInforme.focus();
});

/**
 * Imports the file chosen. A campaign that already has a report answers 409 `informe_ya_importado`: the confirmation asks to replace it and, once
 * confirmed, sends it again with `reemplazar`. Any other refusal (the headers, no numbers, a discarded campaign, a file too big) goes under the
 * field by its code, with the server's sentence as the fallback.
 */
async function importar(): Promise<void> {
  const detalle = estado.detalle;
  if (!detalle) return;
  limpiarErrorInforme();
  const archivo = inputInforme.files?.[0];
  if (!archivo) {
    fallarInforme(t('whatsmkt.informe.sinArchivo'));
    inputInforme.focus();
    return;
  }
  const id = detalle.id;
  const boton = $<HTMLButtonElement>('[data-informe-importar]');
  ocupado(boton, true);
  try {
    await importarInforme(id, archivo, false);
  } catch (caido) {
    if (caido instanceof ApiError && caido.status === 409 && caido.codigo === 'informe_ya_importado') {
      pedirConfirmacion({
        titulo: t('whatsmkt.informe.yaImportado'),
        // What will happen, not the sentence of the code (that one stays as the fallback of the error): it is also asked when the file is another.
        cuerpo: t('whatsmkt.informe.reemplazarCuerpo'),
        aceptar: t('whatsmkt.informe.reemplazar'),
        cancelar: t('mowaMes.seguimiento.reemplazar.cancelar'),
        peligrosa: true,
        hecho: t('whatsmkt.informe.importado'),
        anunciar: estadoInforme,
        enfocar: () => bloqueConciliacion,
        accion: async () => {
          await importarInforme(id, archivo, true);
          await terminarImportacion(id);
        },
      });
    } else {
      fallarInforme(textoDeFallo(caido));
    }
    return;
  } finally {
    ocupado(boton, false);
  }
  await terminarImportacion(id);
  await refrescarLista();
  estadoInforme.textContent = t('whatsmkt.informe.importado');
  bloqueConciliacion.setAttribute('tabindex', '-1');
  bloqueConciliacion.focus();
}

/** The report is in: the form starts over and the detail is read again, so the notice of pending, the figures and the reconciliation are the new ones. */
async function terminarImportacion(id: number): Promise<void> {
  reiniciarInforme();
  if (estado.detalle?.id === id) await abrir(id, true);
}

formInforme.addEventListener('submit', (evento) => {
  evento.preventDefault();
  void importar();
});

function pintarExclusiones(): void {
  const detalle = estado.detalle;
  if (!detalle) return;
  const filas = detalle.exclusiones.exclusiones;
  const pagina = paginar(filas, estado.paginaExclusiones, FILAS_POR_PAGINA);
  estado.paginaExclusiones = pagina.pagina;
  $<HTMLElement>('[data-detalle-exclusiones]').replaceChildren(filas.length === 0 ? vacio(t('whatsmkt.previa.sinExclusiones')) : tablaDeExclusiones(pagina.filas));
  pintarPaginador(pagerExclusiones, pagina.hayPaginador ? pagina : null);
  const truncadas = $<HTMLElement>('[data-detalle-exclusiones-truncadas]');
  const recortada = detalle.exclusiones.total > filas.length;
  truncadas.hidden = !recortada;
  truncadas.textContent = recortada ? t('whatsmkt.seguimiento.exclusionesTruncadas', { mostradas: formatNumber(filas.length), total: formatNumber(detalle.exclusiones.total) }) : '';
}

function pintarFuera(): void {
  const detalle = estado.detalle;
  const visible = detalle !== null && fueraDelLoteVisible(detalle);
  cajaFuera.hidden = !visible;
  if (!detalle || !visible) return;
  $<HTMLElement>('[data-detalle-fuera-titulo]').textContent = t('whatsmkt.seguimiento.fueraLote', {
    lote: detalle.lote.id,
    n: formatNumber(detalle.exclusiones_fuera_del_lote.total),
  });
  const filas = detalle.exclusiones_fuera_del_lote.exclusiones;
  const pagina = paginar(filas, estado.paginaFuera, FILAS_POR_PAGINA);
  estado.paginaFuera = pagina.pagina;
  $<HTMLElement>('[data-detalle-fuera-tabla]').replaceChildren(tablaDeExclusiones(pagina.filas));
  pintarPaginador(pagerFuera, pagina.hayPaginador ? pagina : null);
}

for (const [pager, campo, pintar] of [
  [pagerExclusiones, 'paginaExclusiones', pintarExclusiones],
  [pagerFuera, 'paginaFuera', pintarFuera],
] as const) {
  pager.querySelector('[data-page-prev]')!.addEventListener('click', () => {
    estado[campo] -= 1;
    pintar();
  });
  pager.querySelector('[data-page-next]')!.addEventListener('click', () => {
    estado[campo] += 1;
    pintar();
  });
}

/** Opens a campaign: its detail comes from the API, and a new one starts on the first page of each list with «fuera del lote» closed. */
async function abrir(id: number, mantener = false): Promise<void> {
  let detalle: DetalleCampana;
  try {
    detalle = await obtenerCampana(id, { limite: EXCLUSIONES_POR_PEDIDO });
  } catch (caido) {
    estadoLista.textContent = textoDeFallo(caido);
    return;
  }
  // The reconciliation is asked only of a campaign with a report; if it cannot be read, its place says so and the rest of the detail stands.
  estado.informe = null;
  estado.errorConciliacion = '';
  if (detalle.con_informe) {
    try {
      estado.informe = await obtenerConciliacion(id);
    } catch (caido) {
      estado.errorConciliacion = textoDeFallo(caido);
    }
  }
  estado.detalle = detalle;
  if (!mantener) {
    estado.paginaExclusiones = 1;
    estado.paginaFuera = 1;
    cajaFuera.open = false;
    reiniciarInforme();
  }
  estadoLista.textContent = '';
  window.history.replaceState(null, '', `${window.location.pathname}${busquedaConCampana(id)}`);
  pintarDetalle();
  if (!mantener) {
    panelDetalle.focus();
    panelDetalle.scrollIntoView({ block: 'start' });
  }
}

/** The URL keeps the view and the campaign open, so a link to either lands where it was. */
function busquedaConCampana(id: number): string {
  const parametros = new URLSearchParams(busquedaConVista(window.location.search, estado.vista));
  parametros.set('campana', String(id));
  return `?${parametros}`;
}

function cerrarDetalle(): void {
  estado.detalle = null;
  estado.informe = null;
  estado.errorConciliacion = '';
  pintarDetalle();
  const parametros = new URLSearchParams(window.location.search);
  parametros.delete('campana');
  const texto = parametros.toString();
  window.history.replaceState(null, '', `${window.location.pathname}${texto === '' ? '' : `?${texto}`}`);
}

// ---- Discarding, restoring and deleting -------------------------------------------------------------------------

const confirmar = {
  titulo: $<HTMLElement>('[data-confirmar-titulo]'),
  cuerpo: $<HTMLElement>('[data-confirmar-cuerpo]'),
  casillaCaja: $<HTMLElement>('[data-confirmar-casilla-caja]'),
  casilla: $<HTMLInputElement>('[data-confirmar-casilla]'),
  error: $<HTMLElement>('[data-confirmar-error]'),
  aceptar: $<HTMLButtonElement>('[data-confirmar-aceptar]'),
  aceptarTexto: $<HTMLElement>('[data-confirmar-aceptar-texto]'),
  cancelar: $<HTMLButtonElement>('[data-confirmar-cancelar]'),
};

interface Confirmacion {
  titulo: string;
  cuerpo: string;
  aceptar: string;
  /** Deleting asks to tick that it cannot be undone. */
  conCasilla?: boolean;
  peligrosa?: boolean;
  /** What the cancel button says, if not «Cancelar» («No reemplazar»). */
  cancelar?: string;
  /** It may answer what to say instead of `hecho` (discarding what somebody discarded first says so). */
  accion: () => Promise<string | void>;
  /** What the status line says once it was done. */
  hecho: string;
  /** Where it is said, if not on the status line of the list. */
  anunciar?: HTMLElement;
  /** Where the focus goes when it closes, if not the list. */
  enfocar?: () => HTMLElement;
}

let pendiente: Confirmacion | null = null;

function pedirConfirmacion(confirmacion: Confirmacion): void {
  pendiente = confirmacion;
  confirmar.titulo.textContent = confirmacion.titulo;
  confirmar.cuerpo.textContent = confirmacion.cuerpo;
  confirmar.aceptarTexto.textContent = confirmacion.aceptar;
  confirmar.cancelar.textContent = confirmacion.cancelar ?? t('mowaMes.confirmar.cancelar');
  confirmar.casillaCaja.hidden = !confirmacion.conCasilla;
  confirmar.casilla.checked = false;
  confirmar.error.textContent = '';
  confirmar.aceptar.className = confirmacion.peligrosa ? 'btn btn--danger' : 'btn btn--primary';
  confirmar.aceptar.disabled = Boolean(confirmacion.conCasilla);
  void openWhenFree(dialogoConfirmar);
}

confirmar.casilla.addEventListener('change', () => {
  confirmar.aceptar.disabled = !confirmar.casilla.checked;
});

confirmar.aceptar.addEventListener('click', async () => {
  const actual = pendiente;
  if (!actual) return;
  confirmar.error.textContent = '';
  ocupado(confirmar.aceptar, true);
  let dicho: string | void;
  try {
    dicho = await actual.accion();
  } catch (caido) {
    // A refusal stays in the dialog, by its code, and nothing changes behind it.
    confirmar.error.textContent = textoDeFallo(caido);
    // Disabling the pressed button dropped the focus: it goes back to it, so the keyboard can try again.
    ocupado(confirmar.aceptar, false);
    confirmar.aceptar.focus();
    return;
  } finally {
    ocupado(confirmar.aceptar, false);
  }
  dialogoConfirmar.close();
  pendiente = null;
  await refrescarLista();
  (actual.anunciar ?? estadoLista).textContent = dicho || actual.hecho;
  const destino = actual.enfocar?.() ?? contenedorTabla;
  destino.setAttribute('tabindex', '-1');
  destino.focus();
});

function confirmarDescartar(campana: Pick<ResumenCampana, 'id'>): void {
  pedirConfirmacion({
    titulo: t('whatsmkt.confirmar.descartar.titulo', { id: campana.id }),
    cuerpo: t('whatsmkt.confirmar.descartar.cuerpo'),
    aceptar: t('mowaMes.accion.descartar'),
    hecho: t('whatsmkt.seguimiento.descartada', { id: campana.id }),
    accion: async () => {
      let yaEstaba = false;
      try {
        await descartarCampana(campana.id);
      } catch (caido) {
        // Somebody discarded it first: it is where it was asked to go, and the list that follows says so (it says so, not the code's own sentence).
        if (!(caido instanceof ApiError && caido.codigo === 'campana_descartada')) throw caido;
        yaEstaba = true;
      }
      if (estado.detalle?.id === campana.id) await abrir(campana.id, true);
      return yaEstaba ? t('whatsmkt.seguimiento.yaDescartada') : undefined;
    },
  });
}

function confirmarRestaurar(campana: Pick<ResumenCampana, 'id'>): void {
  pedirConfirmacion({
    titulo: t('whatsmkt.confirmar.restaurar.titulo', { id: campana.id }),
    cuerpo: t('whatsmkt.confirmar.restaurar.cuerpo'),
    aceptar: t('mowaMes.accion.restaurar'),
    hecho: t('whatsmkt.seguimiento.restaurada', { id: campana.id }),
    accion: async () => {
      await restaurarCampana(campana.id);
      if (estado.detalle?.id === campana.id) await abrir(campana.id, true);
    },
  });
}

function confirmarEliminar(campana: Pick<ResumenCampana, 'id'>): void {
  pedirConfirmacion({
    titulo: t('whatsmkt.confirmar.eliminar.titulo', { id: campana.id }),
    cuerpo: t('whatsmkt.confirmar.eliminar.cuerpo'),
    aceptar: t('mowaMes.accion.eliminar'),
    conCasilla: true,
    peligrosa: true,
    hecho: t('whatsmkt.seguimiento.eliminada', { id: campana.id }),
    accion: async () => {
      try {
        await eliminarCampana(campana.id);
      } catch (caido) {
        // Somebody else deleted it first: what was asked is already so, and the list that follows says it.
        if (!(caido instanceof ApiError && caido.status === 404)) throw caido;
      }
      if (estado.detalle?.id === campana.id) cerrarDetalle();
    },
  });
}

// ---- Start --------------------------------------------------------------------------------------------------------

async function leerAdjuntos(): Promise<AdjuntoWhatsmkt[]> {
  // The names and kinds of the photo and the attachment: without them the card says «archivo» and names them by what they are.
  try {
    const [activos, archivados] = await Promise.all([listarAdjuntos(false), listarAdjuntos(true)]);
    return [...activos, ...archivados];
  } catch {
    return [];
  }
}

async function arrancar(): Promise<void> {
  try {
    estado.adjuntos = await leerAdjuntos();
    const pedida = campanaDeLaUrl(window.location.search);
    sinConexion(false);
    if (!(await cargarLista(true))) return;
    if (pedida !== null) {
      await abrir(pedida);
      // A discarded campaign is in the other view: the list follows it, so what is open is also in the list.
      if (estado.detalle?.descartada_en && estado.vista === 'activas') await cambiarVista('descartadas');
    }
  } catch (caido) {
    if (caido instanceof NetworkError) sinConexion(true);
    else mostrarError(caido);
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
  pintarLista();
  pintarDetalle();
});

void arrancar();
