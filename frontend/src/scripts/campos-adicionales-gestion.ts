/**
 * Behaviour of the dialog that manages the additional fields (docs/campos-adicionales-interfaz.md §4, RF-65):
 * the table of every field of the catalogue, archived ones last, and the three gestures on a row. The markup is
 * `components/GestionCamposAdicionales.astro`; the page mounts it and hears of every change.
 *
 * The backend decides: it keeps the names unique and never changes a technical name or a type. This only shows
 * the list and sends what was chosen. A refusal is read by its `codigo`, never by its text.
 */

import { ApiError } from '../lib/api';
import {
  cambiarCampoAdicional,
  listarCamposAdicionales,
  type CambioCampoAdicional,
  type CampoAdicional,
} from '../lib/api-mapeador';
import { campoDelError, codigoDeError, textoDeError } from '../lib/carga-mapeada';
import { ordenarAdicionales, puedeGuardarNombre } from '../lib/campos-adicionales';
import { t } from '../lib/i18n';

export interface OpcionesGestion {
  dialogo: HTMLDialogElement;
  /** The buttons that open it; each one shows «Campos adicionales (N)». */
  disparadores: readonly HTMLElement[];
  /** The list changed (loaded, renamed, archived, reactivated): the page redraws what names these fields. */
  alCambiar: (campos: readonly CampoAdicional[]) => void;
  /** Opens the dialog when nothing else is open. */
  abrir: (dialogo: HTMLDialogElement) => void;
}

export interface ControladorGestion {
  campos(): readonly CampoAdicional[];
  /** Reads the list again; an unreachable API leaves the last one as it was. */
  recargar(): Promise<void>;
}

export function montarGestion(opciones: OpcionesGestion): ControladorGestion {
  const { dialogo } = opciones;
  const q = <T extends Element>(selector: string) => dialogo.querySelector<T>(selector)!;
  const el = {
    estado: q<HTMLElement>('[data-adicionales-estado]'),
    error: q<HTMLElement>('[data-adicionales-error]'),
    vacio: q<HTMLElement>('[data-adicionales-vacio]'),
    tabla: q<HTMLElement>('[data-adicionales-tabla]'),
    filas: q<HTMLElement>('[data-adicionales-filas]'),
  };
  const s = {
    campos: [] as CampoAdicional[],
    /** The field whose name is being edited, if any: one at a time. */
    editando: null as string | null,
    /** What the open edit shows when it is drawn again (a language change, a new list). */
    error: null as { campo: string; texto: string } | null,
    guardando: false,
    /** What is typed in the open edit: it survives every redraw, a refusal included. */
    texto: null as string | null,
  };

  const mensajeGeneral = (error: unknown) => textoDeError(error, t('console.upload.error.network'), t('common.errorBody'));

  // ---- Drawing -------------------------------------------------------------------------------

  function boton(clase: string, clave: string, claveAria: string | null, campo: string): HTMLButtonElement {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = `btn btn--sm ${clase}`.trim();
    b.textContent = t(clave);
    if (claveAria) b.setAttribute('aria-label', t(claveAria, { campo }));
    return b;
  }

  function celda(etiqueta: string, clase = ''): HTMLTableCellElement {
    const c = document.createElement('td');
    if (clase) c.className = clase;
    c.dataset.etiqueta = t(etiqueta);
    return c;
  }

  function filaDe(campo: CampoAdicional): HTMLTableRowElement {
    const fila = document.createElement('tr');
    fila.dataset.campo = campo.nombre;
    const editando = s.editando === campo.nombre;

    const nombre = document.createElement('th');
    nombre.scope = 'row';
    nombre.dataset.etiqueta = t('camposAdicionales.gestion.col.nombre');
    const acciones = celda('camposAdicionales.gestion.col.acciones', 'adicionales__acciones');

    if (editando) {
      const entrada = document.createElement('input');
      entrada.type = 'text';
      entrada.className = 'input';
      entrada.maxLength = 80;
      entrada.autocomplete = 'off';
      entrada.value = s.texto ?? campo.nombre_legible;
      entrada.dataset.nombre = '';
      entrada.id = `adicional-nombre-${campo.nombre}`;
      entrada.setAttribute('aria-label', t('camposAdicionales.gestion.nombreNuevo', { campo: campo.nombre_legible }));
      entrada.setAttribute('aria-describedby', `${entrada.id}-hint ${entrada.id}-error`);
      const hint = document.createElement('p');
      hint.className = 'field__hint adicionales__nota';
      hint.id = `${entrada.id}-hint`;
      hint.textContent = t('camposAdicionales.gestion.nombreHint');
      const error = document.createElement('p');
      error.className = 'field__error';
      error.id = `${entrada.id}-error`;
      error.dataset.nombreError = '';
      if (s.error?.campo === campo.nombre) {
        error.textContent = s.error.texto;
        entrada.setAttribute('aria-invalid', 'true');
      }
      nombre.append(entrada, hint, error);

      const guardar = boton('btn--primary', 'camposAdicionales.gestion.guardar', null, campo.nombre_legible);
      guardar.dataset.guardar = '';
      guardar.disabled = s.guardando || !puedeGuardarNombre(entrada.value, campo.nombre_legible);
      const cancelar = boton('', 'camposAdicionales.gestion.cancelar', null, campo.nombre_legible);
      cancelar.dataset.cancelar = '';
      acciones.append(guardar, cancelar);

      entrada.addEventListener('input', () => {
        s.texto = entrada.value;
        s.error = null;
        error.textContent = '';
        entrada.removeAttribute('aria-invalid');
        guardar.disabled = s.guardando || !puedeGuardarNombre(entrada.value, campo.nombre_legible);
      });
      entrada.addEventListener('keydown', (evento) => {
        if (evento.key === 'Enter') {
          // The dialog may sit inside a form on another page: Enter here saves the name, nothing else.
          evento.preventDefault();
          if (!guardar.disabled) void guardarNombre(campo, entrada.value);
        } else if (evento.key === 'Escape') {
          // Escape leaves the edit, not the whole dialog.
          evento.preventDefault();
          evento.stopPropagation();
          cancelarEdicion(campo.nombre);
        }
      });
      guardar.addEventListener('click', () => void guardarNombre(campo, entrada.value));
      cancelar.addEventListener('click', () => cancelarEdicion(campo.nombre));
    } else {
      nombre.textContent = campo.nombre_legible;
      const renombrar = boton('', 'camposAdicionales.gestion.renombrar', 'camposAdicionales.gestion.renombrarPara', campo.nombre_legible);
      renombrar.dataset.renombrar = '';
      renombrar.addEventListener('click', () => empezarEdicion(campo.nombre));
      const cambia = campo.archivado
        ? boton('', 'camposAdicionales.gestion.reactivar', 'camposAdicionales.gestion.reactivarPara', campo.nombre_legible)
        : boton('', 'camposAdicionales.gestion.archivar', 'camposAdicionales.gestion.archivarPara', campo.nombre_legible);
      cambia.dataset[campo.archivado ? 'reactivar' : 'archivar'] = '';
      cambia.addEventListener('click', () => void cambiarEstado(campo, !campo.archivado));
      acciones.append(renombrar, cambia);
    }

    const tipo = celda('camposAdicionales.gestion.col.tipo');
    tipo.textContent = t(`mapeador.vista.adicional.tipo.${campo.tipo}`);
    const origen = celda('camposAdicionales.gestion.col.origen', 'mono');
    origen.textContent = campo.encabezado_origen;
    const estado = celda('camposAdicionales.gestion.col.estado');
    if (campo.archivado) {
      const marca = document.createElement('span');
      marca.className = 'tag tag--advertencia';
      marca.textContent = t('camposAdicionales.archivado');
      estado.append(marca);
    } else {
      estado.textContent = t('camposAdicionales.gestion.activo');
    }

    fila.append(nombre, tipo, origen, estado, acciones);
    return fila;
  }

  function contar(): void {
    for (const disparador of opciones.disparadores) {
      const texto = disparador.querySelector<HTMLElement>('[data-adicionales-n]');
      if (texto) texto.textContent = t('camposAdicionales.gestion.abrir', { n: s.campos.length });
    }
  }

  const CONTROLES = ['input[data-nombre]', '[data-guardar]', '[data-cancelar]', '[data-renombrar]', '[data-archivar]', '[data-reactivar]'];

  /** The rows are drawn again on every change: whoever has the focus keeps it, and the caret with it. */
  function pintar(): void {
    const activo = document.activeElement instanceof HTMLElement && el.filas.contains(document.activeElement) ? document.activeElement : null;
    const campo = activo?.closest<HTMLElement>('tr[data-campo]')?.dataset.campo;
    const control = activo ? CONTROLES.find((selector) => activo.matches(selector)) : undefined;
    const rango = activo instanceof HTMLInputElement ? [activo.selectionStart, activo.selectionEnd] : null;

    el.vacio.hidden = s.campos.length > 0;
    el.tabla.hidden = s.campos.length === 0;
    el.filas.replaceChildren(...s.campos.map(filaDe));
    contar();

    if (campo && control) {
      const nuevo = filaPorNombre(campo)?.querySelector<HTMLElement>(control);
      nuevo?.focus();
      if (nuevo instanceof HTMLInputElement && rango && rango[0] !== null && rango[1] !== null) nuevo.setSelectionRange(rango[0], rango[1]);
    }
  }

  const filaPorNombre = (nombre: string) => el.filas.querySelector<HTMLElement>(`[data-campo="${nombre}"]`);

  // ---- Reading and changing -------------------------------------------------------------------

  function fijar(lista: readonly CampoAdicional[]): void {
    const ordenada = ordenarAdicionales(lista);
    // The same list again (opening the dialog reads it once more): nothing to draw, nobody to tell.
    if (JSON.stringify(ordenada) === JSON.stringify(s.campos)) return;
    s.campos = ordenada;
    pintar();
    opciones.alCambiar(s.campos);
  }

  async function recargar(): Promise<void> {
    try {
      fijar(await listarCamposAdicionales());
      el.error.textContent = '';
    } catch (error) {
      // The list on screen stays; a dialog that is open says it could not be refreshed.
      if (dialogo.open) el.error.textContent = `${t('camposAdicionales.gestion.errorCarga')} ${mensajeGeneral(error)}`;
    }
  }

  function empezarEdicion(nombre: string): void {
    s.editando = nombre;
    s.texto = null;
    s.error = null;
    pintar();
    filaPorNombre(nombre)?.querySelector<HTMLInputElement>('input[data-nombre]')?.focus();
  }

  function cancelarEdicion(nombre: string): void {
    s.editando = null;
    s.texto = null;
    s.error = null;
    pintar();
    filaPorNombre(nombre)?.querySelector<HTMLElement>('[data-renombrar]')?.focus();
  }

  function sustituir(nuevo: CampoAdicional): void {
    fijar(s.campos.map((c) => (c.nombre === nuevo.nombre ? nuevo : c)));
  }

  async function guardarNombre(campo: CampoAdicional, texto: string): Promise<void> {
    const nombre = texto.trim();
    if (s.guardando || !puedeGuardarNombre(nombre, campo.nombre_legible)) return;
    s.guardando = true;
    s.error = null;
    el.error.textContent = '';
    pintar();
    // The rows are drawn again once this ends, so the focus is set after that.
    let enfocar = '[data-renombrar]';
    try {
      const guardado = await cambiarCampoAdicional(campo.nombre, { nombre_legible: nombre });
      s.editando = null;
      s.texto = null;
      sustituir(guardado);
      el.estado.textContent = t('camposAdicionales.gestion.renombrado', { anterior: campo.nombre_legible, nuevo: guardado.nombre_legible });
    } catch (error) {
      enfocar = 'input[data-nombre]';
      s.error = { campo: campo.nombre, texto: textoDelRechazo(error) };
      if (error instanceof ApiError && codigoDeError(error) === 'campo_adicional_no_encontrado') {
        // Gone while the dialog was open: the edit ends and the list is read again.
        const aviso = s.error.texto;
        s.editando = null;
        s.texto = null;
        s.error = null;
        enfocar = '[data-renombrar]';
        await recargar();
        // Reading the list clears the notice: it is said after.
        el.error.textContent = aviso;
      }
    } finally {
      s.guardando = false;
      pintar();
      filaPorNombre(campo.nombre)?.querySelector<HTMLElement>(enfocar)?.focus();
    }
  }

  /** The text under the name: an archived field in the way is told apart, because it is in this very table. */
  function textoDelRechazo(error: unknown): string {
    if (error instanceof ApiError && error.status === 409 && codigoDeError(error) === 'nombre_repetido') {
      const choca = campoDelError(error);
      if (choca) {
        const archivado = s.campos.find((c) => c.nombre === choca.campo.nombre)?.archivado;
        return t(archivado ? 'camposAdicionales.gestion.nombreArchivado' : 'camposAdicionales.gestion.nombreRepetido', {
          campo: choca.etiquetaVisible,
        });
      }
    }
    if (error instanceof ApiError && error.status === 422 && !codigoDeError(error)) return t('mapeador.vista.adicional.nombreInvalido');
    return mensajeGeneral(error);
  }

  async function cambiarEstado(campo: CampoAdicional, archivado: boolean): Promise<void> {
    const cambio: CambioCampoAdicional = { archivado };
    el.error.textContent = '';
    try {
      sustituir(await cambiarCampoAdicional(campo.nombre, cambio));
      el.estado.textContent = t(archivado ? 'camposAdicionales.gestion.archivado' : 'camposAdicionales.gestion.reactivado', {
        campo: campo.nombre_legible,
      });
      // The row moves (archived ones go last); the focus goes to the gesture that undoes this one.
      filaPorNombre(campo.nombre)?.querySelector<HTMLElement>(archivado ? '[data-reactivar]' : '[data-archivar]')?.focus();
    } catch (error) {
      el.error.textContent = mensajeGeneral(error);
      if (error instanceof ApiError && codigoDeError(error) === 'campo_adicional_no_encontrado') await recargar();
    }
  }

  // ---- Opening ----------------------------------------------------------------------------------

  for (const disparador of opciones.disparadores) {
    disparador.addEventListener('click', () => {
      s.editando = null;
      s.texto = null;
      s.error = null;
      el.estado.textContent = '';
      el.error.textContent = '';
      pintar();
      opciones.abrir(dialogo);
      void recargar();
    });
  }
  dialogo.addEventListener('close', () => {
    s.editando = null;
    s.texto = null;
    s.error = null;
  });
  document.addEventListener('languagechange', () => {
    pintar();
  });

  return { campos: () => s.campos, recargar };
}
