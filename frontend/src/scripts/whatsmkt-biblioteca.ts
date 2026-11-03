/**
 * The attachment library panel of `/whatsmkt/configuracion` (T-WM-F1b1, RF-WM-30 to RF-WM-32): the active
 * attachments in a stacking table with Download and Archive, the archived ones in a closed `<details>` with
 * Download and Restore, and one picker to upload a file. An attachment is never deleted: it is archived.
 *
 * It binds to the markup of the page by data attributes and keeps its own state. `cargar()` reads both lists;
 * `repintar()` draws them again after a language switch. A failure of the library never takes the rest of the
 * screen down: it is said in the panel.
 */

import { mensajeDeError } from '../lib/api';
import {
  archivarAdjunto,
  descargarAdjunto,
  desarchivarAdjunto,
  listarAdjuntos,
  subirAdjunto,
  type AdjuntoSubido,
  type AdjuntoWhatsmkt,
} from '../lib/api-whatsmkt';
import { guardarArchivo } from '../lib/descargas';
import { $, ocupado } from '../lib/dom';
import { formatDateTime, formatNumber } from '../lib/format';
import { t } from '../lib/i18n';
import { celda, celdaDeFila, tabla, vacio } from '../lib/tabla-dom';
import { errorDeModulo, esImagen, nombreDeTipo, tamanoLegible, textoDeErrorAdjunto } from '../lib/whatsmkt';

export interface Biblioteca {
  /** Read the active and the archived attachments and draw them. */
  cargar(): Promise<void>;
  /** Draw what is already read again, in the language that is on. */
  repintar(): void;
}

type Icono = 'descargar' | 'archivar' | 'restaurar';

export function montarBiblioteca(): Biblioteca {
  const activos = $<HTMLElement>('[data-biblioteca-activos]');
  const archivadosCaja = $<HTMLDetailsElement>('[data-biblioteca-archivados]');
  const archivadosTitulo = $<HTMLElement>('[data-biblioteca-archivados-titulo]');
  const archivadosTabla = $<HTMLElement>('[data-biblioteca-archivados-tabla]');
  const errorGeneral = $<HTMLElement>('[data-biblioteca-error]');
  const estadoNodo = $<HTMLElement>('[data-biblioteca-estado]');
  const restaurarSubido = $<HTMLButtonElement>('[data-restaurar-subido]');
  const formulario = $<HTMLFormElement>('[data-form-subir]');
  const campo = $<HTMLInputElement>('#wm-adjunto');
  const nombreElegido = $<HTMLElement>('[data-adjunto-nombre]');
  const errorCampo = $<HTMLElement>('[data-adjunto-error]');
  const botonSubir = $<HTMLButtonElement>('[data-subir]');

  let listaActivos: AdjuntoWhatsmkt[] = [];
  let listaArchivados: AdjuntoWhatsmkt[] = [];
  /** The attachment an upload found already archived, which the status line offers to restore. */
  let porRestaurar: AdjuntoWhatsmkt | null = null;

  const icono = (clave: Icono): Node =>
    $<HTMLTemplateElement>(`template[data-icono-${clave}]`).content.cloneNode(true);

  /** A status that says what just happened. It stays until the next action: it may carry the Restore button. */
  function anunciar(texto: string): void {
    estadoNodo.textContent = texto;
  }

  function limpiar(): void {
    anunciar('');
    errorGeneral.textContent = '';
    errorCampo.textContent = '';
    campo.removeAttribute('aria-invalid');
    campo.closest('.filepick')?.removeAttribute('aria-invalid');
    porRestaurar = null;
    restaurarSubido.hidden = true;
  }

  // ---- The tables -------------------------------------------------------------------------------

  /** A row's button: its name is its own text and then the file's («Descargar» + «afiche.jpg»), so rows tell apart. */
  function boton(adjunto: AdjuntoWhatsmkt, clave: Icono, texto: string, nombre: HTMLElement): HTMLButtonElement {
    const nodo = document.createElement('button');
    nodo.type = 'button';
    nodo.id = `wm-adj-${clave}-${adjunto.id}`;
    nodo.className = 'btn btn--sm';
    nodo.setAttribute('aria-labelledby', `${nodo.id} ${nombre.id}`);
    nodo.append(icono(clave), document.createTextNode(texto));
    return nodo;
  }

  function fila(adjunto: AdjuntoWhatsmkt, archivado: boolean): HTMLTableRowElement {
    const nodo = document.createElement('tr');
    nodo.dataset.adjunto = String(adjunto.id);
    const nombre = celdaDeFila(adjunto.nombre, 'mono wm-adjunto__nombre', t('whatsmkt.biblioteca.col.nombre'));
    nombre.id = `wm-adj-nombre-${adjunto.id}`;

    const descargar = boton(adjunto, 'descargar', t('whatsmkt.biblioteca.descargar'), nombre);
    descargar.addEventListener('click', () => void descargarFila(adjunto));
    const cambiar = archivado
      ? boton(adjunto, 'restaurar', t('whatsmkt.biblioteca.restaurar'), nombre)
      : boton(adjunto, 'archivar', t('whatsmkt.biblioteca.archivar'), nombre);
    cambiar.addEventListener('click', () => void cambiarArchivado(adjunto, !archivado));
    const acciones = document.createElement('div');
    acciones.className = 'wm-acciones';
    acciones.append(descargar, cambiar);
    const accion = celda('td', '', '', t('whatsmkt.biblioteca.col.accion'));
    accion.append(acciones);

    nodo.append(
      nombre,
      celda('td', nombreDeTipo(adjunto.tipo), '', t('whatsmkt.biblioteca.col.tipo')),
      celda('td', tamanoLegible(adjunto.tamano), 'num', t('whatsmkt.biblioteca.col.tamano')),
      celda('td', formatDateTime(adjunto.creado_en), '', t('whatsmkt.biblioteca.col.subido')),
      accion,
    );
    return nodo;
  }

  function tablaDe(lista: readonly AdjuntoWhatsmkt[], archivado: boolean): HTMLElement {
    const { envoltorio, cuerpo } = tabla(
      'wm-adjuntos',
      [
        [t('whatsmkt.biblioteca.col.nombre'), false],
        [t('whatsmkt.biblioteca.col.tipo'), false],
        [t('whatsmkt.biblioteca.col.tamano'), true],
        [t('whatsmkt.biblioteca.col.subido'), false],
        [t('whatsmkt.biblioteca.col.accion'), false],
      ],
      { apilable: true },
    );
    const nodoTabla = envoltorio.querySelector('table')!;
    nodoTabla.setAttribute('aria-label', t(archivado ? 'whatsmkt.biblioteca.tablaArchivados' : 'whatsmkt.biblioteca.tablaActivos'));
    // The same widths in the active and the archived table (`table-layout: fixed`), so the columns line up and the two
    // read as one list. Under 48rem the table stacks and the widths do not apply.
    const grupo = document.createElement('colgroup');
    ['nombre', 'tipo', 'tamano', 'subido', 'accion'].forEach((columna) => {
      const col = document.createElement('col');
      col.className = `wm-col-${columna}`;
      grupo.append(col);
    });
    nodoTabla.prepend(grupo);
    cuerpo.append(...lista.map((adjunto) => fila(adjunto, archivado)));
    return envoltorio;
  }

  function pintar(): void {
    activos.replaceChildren(listaActivos.length === 0 ? vacio(t('whatsmkt.biblioteca.vacia')) : tablaDe(listaActivos, false));
    archivadosCaja.hidden = listaArchivados.length === 0;
    archivadosTitulo.textContent = t('whatsmkt.biblioteca.archivados', { n: formatNumber(listaArchivados.length) });
    archivadosTabla.replaceChildren(listaArchivados.length === 0 ? '' : tablaDe(listaArchivados, true));
  }

  async function cargar(): Promise<void> {
    try {
      [listaActivos, listaArchivados] = await Promise.all([listarAdjuntos(false), listarAdjuntos(true)]);
      pintar();
    } catch (caido) {
      errorGeneral.textContent = mensajeDeError(caido);
    }
  }

  // ---- Download, archive and restore ---------------------------------------------------------------

  async function descargarFila(adjunto: AdjuntoWhatsmkt): Promise<void> {
    errorGeneral.textContent = '';
    try {
      const archivo = await descargarAdjunto(adjunto.id);
      guardarArchivo(archivo.blob, archivo.nombre || adjunto.nombre);
    } catch (caido) {
      errorGeneral.textContent = mensajeDeError(caido);
    }
  }

  /** The button that takes the place of a row that left its list: the one now at its position, else the picker. */
  function enfocarEnSuLugar(archivado: boolean, posicion: number): void {
    const lista = archivado ? listaArchivados : listaActivos;
    const siguiente = lista[Math.min(posicion, lista.length - 1)];
    const destino = siguiente
      ? document.querySelector<HTMLElement>(`tr[data-adjunto="${siguiente.id}"] button`)
      : null;
    (destino ?? campo).focus();
  }

  async function cambiarArchivado(adjunto: Pick<AdjuntoWhatsmkt, 'id' | 'nombre'>, archivar: boolean): Promise<void> {
    limpiar();
    // Where it was in its list, so the focus can stay near it once it has moved to the other one.
    const origen = archivar ? listaActivos : listaArchivados;
    const posicion = Math.max(0, origen.findIndex((a) => a.id === adjunto.id));
    try {
      const cambiado = archivar ? await archivarAdjunto(adjunto.id) : await desarchivarAdjunto(adjunto.id);
      await cargar();
      anunciar(t(archivar ? 'whatsmkt.biblioteca.archivado' : 'whatsmkt.biblioteca.restaurado', { nombre: cambiado.nombre }));
      enfocarEnSuLugar(!archivar, posicion);
    } catch (caido) {
      errorGeneral.textContent = mensajeDeError(caido);
    }
  }

  restaurarSubido.addEventListener('click', () => {
    if (porRestaurar) void cambiarArchivado(porRestaurar, false);
  });

  // ---- Upload ---------------------------------------------------------------------------------------

  /**
   * The name of the chosen file or the invitation. The invitation is a translated node (`data-i18n`); a file name is
   * not, so the attribute goes while a file is chosen and a language switch cannot write the invitation over it.
   */
  function pintarNombreElegido(): void {
    const nombre = campo.files?.[0]?.name;
    if (nombre) {
      delete nombreElegido.dataset.i18n;
      nombreElegido.textContent = nombre;
    } else {
      nombreElegido.dataset.i18n = 'whatsmkt.biblioteca.sinArchivo';
      nombreElegido.textContent = t('whatsmkt.biblioteca.sinArchivo');
    }
  }
  campo.addEventListener('change', () => {
    errorCampo.textContent = '';
    campo.removeAttribute('aria-invalid');
    pintarNombreElegido();
  });

  function decir(subido: AdjuntoSubido): void {
    if (subido.ya_existia && subido.archivado_en !== null) {
      // The same file is in the library but archived, and an upload does not bring it back: it is offered.
      porRestaurar = subido;
      restaurarSubido.hidden = false;
      anunciar(t('whatsmkt.biblioteca.yaEstabaArchivado', { nombre: subido.nombre }));
    } else if (subido.ya_existia) {
      anunciar(t('whatsmkt.biblioteca.yaEstaba', { nombre: subido.nombre }));
    } else {
      const base = t('whatsmkt.biblioteca.subido', { nombre: subido.nombre });
      // The images are stored without metadata (EXIF, location): the user asked for it (P-8).
      anunciar(esImagen(subido.tipo) ? `${base} ${t('whatsmkt.biblioteca.sinMetadatos')}` : base);
    }
  }

  formulario.addEventListener('submit', async (evento) => {
    evento.preventDefault();
    limpiar();
    const archivo = campo.files?.[0];
    if (!archivo) {
      errorCampo.textContent = t('whatsmkt.biblioteca.sinArchivoError');
      campo.setAttribute('aria-invalid', 'true');
      campo.closest('.filepick')?.setAttribute('aria-invalid', 'true');
      campo.focus();
      return;
    }
    ocupado(botonSubir, true);
    try {
      const subido = await subirAdjunto(archivo);
      campo.value = '';
      pintarNombreElegido();
      await cargar();
      decir(subido);
    } catch (caido) {
      const fallo = errorDeModulo(caido);
      errorCampo.textContent = fallo ? textoDeErrorAdjunto(fallo) : mensajeDeError(caido);
      campo.setAttribute('aria-invalid', 'true');
      campo.closest('.filepick')?.setAttribute('aria-invalid', 'true');
    } finally {
      ocupado(botonSubir, false);
    }
  });

  return {
    cargar,
    repintar(): void {
      pintar();
    },
  };
}
