/**
 * The list of values of a list filter (RF-67, docs/filtro-valores-interfaz.md §2): a text field with «es uno de»
 * or «no es ninguno de» offers the real values of the date, with how many products each has, in the row of the
 * filter, in place of the text area. It lives apart from `selector-seleccion.ts` because it has a life of its own:
 * each filter asks the backend for its list with the filters above it (the cascade), waits 300 ms after the last
 * change, drops an old answer, and keeps what was checked whatever comes back.
 *
 * The backend decides; this shows. Whether a list is offered at all, the threshold and the order of the values are
 * in the answer (`GET /cartera/valores`); nothing here counts or sorts a value. What the analyst checked lives in
 * the filter itself (`valores` and `vacio`), so every redraw of a row or of this list starts from it.
 */

import { ApiError, valoresDeCampo, type Campos, type ValoresDeCampo } from '../lib/api';
import { formatNumber } from '../lib/format';
import { t } from '../lib/i18n';
import type { FiltroBorrador } from '../lib/seleccion';
import {
  MAS_DE_PARA_BUSCAR,
  buscar,
  claveDeDecision,
  claveDeLista,
  conValor,
  filtrosDeArriba,
  marcados,
  pideLista,
  repartir,
  resumen,
  type ValorConCantidad,
} from '../lib/valores-filtro';

/** After the last change, the same wait the review of the selection has for a keystroke (§2.6). */
const ESPERA = 300;

type Fase = 'cargando' | 'lista' | 'actualizando' | 'sobre' | 'error' | 'sin';

interface EstadoLista {
  fase: Fase;
  respuesta: ValoresDeCampo | null;
  /** The key of the last list asked for (or being asked for). */
  claveSolicitada: string | null;
  /** The key that decided there is no list: it only changes with the date or the field. */
  claveSobre: string | null;
  temporizador: number;
  control: AbortController | null;
  busqueda: string;
  contenedor: HTMLElement | null;
}

export interface OpcionesGestorValores {
  campos: () => Campos;
  fecha: () => string | null;
  filtros: () => FiltroBorrador[];
  /** The analyst checked or unchecked something: the selection changed. */
  alMarcar: () => void;
  /** The visible name of a field (`etiquetaEnCatalogo`). */
  nombreDe: (campo: string) => string;
}

export interface GestorValores {
  /** Whether this filter picks from a list (and so draws through `pintar`). */
  aplica(filtro: FiltroBorrador): boolean;
  /** Draws the filter's values control in `contenedor`; asking for the list is `sincronizar`'s job. */
  pintar(contenedor: HTMLElement, filtro: FiltroBorrador): void;
  /** Asks for the lists whose date, field or filters above changed since the last time. */
  sincronizar(): void;
}

let contador = 0;

export function crearGestorValores(opciones: OpcionesGestorValores): GestorValores {
  const estados = new Map<FiltroBorrador, EstadoLista>();

  const aplica = (filtro: FiltroBorrador) => pideLista(opciones.campos(), filtro);

  function estadoDe(filtro: FiltroBorrador): EstadoLista {
    let estado = estados.get(filtro);
    if (!estado) {
      estado = {
        fase: opciones.fecha() ? 'cargando' : 'sin',
        respuesta: null,
        claveSolicitada: null,
        claveSobre: null,
        temporizador: 0,
        control: null,
        busqueda: '',
        contenedor: null,
      };
      estados.set(filtro, estado);
    }
    return estado;
  }

  function olvidar(filtro: FiltroBorrador): void {
    const estado = estados.get(filtro);
    if (!estado) return;
    window.clearTimeout(estado.temporizador);
    estado.control?.abort();
    estados.delete(filtro);
  }

  // ---- Drawing -------------------------------------------------------------------------------

  function textarea(filtro: FiltroBorrador): HTMLTextAreaElement {
    const area = document.createElement('textarea');
    area.className = 'input fila__valor';
    area.rows = 2;
    area.value = filtro.valores.join('\n');
    area.placeholder = t('selector.filtro.lista');
    area.setAttribute('aria-label', `${t('selector.filtro.valor')} · ${t('selector.filtro.lista')}`);
    area.dataset.foco = 'texto';
    area.addEventListener('input', () => {
      filtro.valores = area.value.split('\n');
      opciones.alMarcar();
    });
    return area;
  }

  function texto(clase: string, contenido: string, etiqueta?: string): HTMLParagraphElement {
    const p = document.createElement('p');
    p.className = clase;
    p.textContent = contenido;
    if (etiqueta) p.setAttribute('role', etiqueta);
    return p;
  }

  /** A checkbox with its text and, for a value of the list, its count. `valor === null` is «(vacío)». */
  function opcion(
    filtro: FiltroBorrador,
    estado: EstadoLista,
    valor: string | null,
    cantidad: number | null,
    marcado: boolean,
    claseExtra = '',
  ): HTMLLabelElement {
    const etiqueta = document.createElement('label');
    etiqueta.className = `valores__opcion ${claseExtra}`.trim();
    const casilla = document.createElement('input');
    casilla.type = 'checkbox';
    casilla.className = 'valores__casilla';
    casilla.checked = marcado;
    casilla.dataset.foco = valor === null ? 'casilla-vacio' : `casilla:${valor}`;
    if (valor !== null) casilla.value = valor;
    const nombre = valor === null ? t('selector.valores.vacio') : valor;
    // The accessible name is the text and the count: «Primera asignación, 1 820 productos».
    casilla.setAttribute(
      'aria-label',
      cantidad === null
        ? nombre
        : t(cantidad === 1 ? 'selector.valores.cantidadUno' : 'selector.valores.cantidad', { valor: nombre, n: formatNumber(cantidad) }),
    );
    const visible = document.createElement(valor === null ? 'em' : 'span');
    visible.className = 'valores__texto';
    visible.textContent = nombre;
    visible.title = nombre;
    etiqueta.append(casilla, visible);
    if (cantidad !== null) {
      const cuenta = document.createElement('span');
      cuenta.className = 'valores__cantidad mono';
      cuenta.textContent = formatNumber(cantidad);
      etiqueta.append(cuenta);
    }
    casilla.addEventListener('change', () => {
      if (valor === null) {
        if (casilla.checked) filtro.vacio = true;
        else delete filtro.vacio;
      } else {
        filtro.valores = conValor(filtro.valores, valor, casilla.checked);
      }
      dibujar(filtro, estado);
      opciones.alMarcar();
    });
    return etiqueta;
  }

  /** «(vacío)» under the text area: it is not a line of it (a blank line would be dropped), so it is its own box. */
  function casillaVacioSuelta(filtro: FiltroBorrador, estado: EstadoLista): HTMLElement | null {
    return filtro.vacio ? opcion(filtro, estado, null, null, true, 'valores__opcion--suelta') : null;
  }

  function lista(filtro: FiltroBorrador, estado: EstadoLista): HTMLFieldSetElement {
    const respuesta = estado.respuesta?.valores ?? [];
    const reparto = repartir(respuesta, filtro);
    const marcadosSet = new Set(marcados(filtro));
    const identificador = `valores-${(contador += 1)}`;
    const ocupado = estado.fase === 'actualizando';

    const grupo = document.createElement('fieldset');
    grupo.className = 'valores';
    grupo.dataset.fase = estado.fase;
    grupo.setAttribute('aria-busy', String(ocupado));
    grupo.setAttribute('aria-describedby', `${identificador}-ayuda`);
    const leyenda = document.createElement('legend');
    leyenda.className = 'visually-hidden';
    leyenda.textContent = t('selector.valores.leyenda', { campo: opciones.nombreDe(filtro.campo) });
    const ayuda = texto('field__hint valores__ayuda', t(filtro.operador === 'no_en' ? 'selector.valores.excluye' : 'selector.valores.incluye'));
    ayuda.id = `${identificador}-ayuda`;
    grupo.append(leyenda, ayuda);
    if (ocupado) grupo.append(texto('field__hint valores__actualizando', t('selector.valores.actualizando'), 'status'));

    let visibles: ValorConCantidad[] = reparto.enLista;
    if (reparto.enLista.length > MAS_DE_PARA_BUSCAR) {
      const busqueda = document.createElement('input');
      busqueda.type = 'search';
      busqueda.className = 'input valores__buscar';
      busqueda.value = estado.busqueda;
      busqueda.setAttribute('aria-label', t('selector.valores.buscar'));
      busqueda.placeholder = t('selector.valores.buscar');
      busqueda.autocomplete = 'off';
      busqueda.dataset.foco = 'busqueda';
      busqueda.addEventListener('input', () => {
        estado.busqueda = busqueda.value;
        dibujar(filtro, estado);
      });
      grupo.append(busqueda);
      visibles = buscar(reparto.enLista, estado.busqueda);
    }

    const cuerpo = document.createElement('div');
    cuerpo.className = 'valores__lista';
    visibles.forEach((item) => cuerpo.append(opcion(filtro, estado, item.valor, item.cantidad, marcadosSet.has((item.valor ?? '').trim()))));
    if (estado.busqueda.trim() && visibles.length === 0) {
      cuerpo.append(texto('field__hint valores__sinResultados', t('selector.valores.sinResultados', { texto: estado.busqueda.trim() })));
    }
    // «(vacío)» is always last and always in sight: it is not searched.
    if (reparto.mostrarVacio) cuerpo.append(opcion(filtro, estado, null, reparto.cantidadVacio, filtro.vacio === true));
    grupo.append(cuerpo);

    if (reparto.sinProductos.length > 0) {
      const aparte = document.createElement('fieldset');
      aparte.className = 'valores__sinProductos';
      const titulo = document.createElement('legend');
      titulo.textContent = t('selector.valores.sinProductos.titulo');
      aparte.append(titulo, texto('field__hint', t('selector.valores.sinProductos.aviso')));
      reparto.sinProductos.forEach((valor) => {
        const fila = opcion(filtro, estado, valor, 0, true);
        const marca = document.createElement('span');
        marca.className = 'tag tag--advertencia';
        marca.textContent = t('selector.valores.sinProductos.tag');
        fila.append(marca);
        aparte.append(fila);
      });
      grupo.append(aparte);
    }

    const { n, total } = resumen(filtro, reparto);
    const pie = document.createElement('p');
    pie.className = 'field__hint valores__resumen';
    pie.append(t('selector.valores.marcados', { n: formatNumber(n), total: formatNumber(total) }));
    if (n > 0) {
      const desmarcar = document.createElement('button');
      desmarcar.type = 'button';
      desmarcar.className = 'btn btn--sm btn--quiet';
      desmarcar.dataset.foco = 'desmarcar';
      desmarcar.textContent = t('selector.valores.desmarcar');
      desmarcar.addEventListener('click', () => {
        filtro.valores = [];
        delete filtro.vacio;
        dibujar(filtro, estado);
        opciones.alMarcar();
      });
      pie.append(' ', desmarcar);
    }
    grupo.append(pie);
    return grupo;
  }

  /** The control of the filter for what is known now (§2.1 and §2.5). */
  function contenido(filtro: FiltroBorrador, estado: EstadoLista): HTMLElement[] {
    switch (estado.fase) {
      case 'cargando': {
        const grupo = document.createElement('fieldset');
        grupo.className = 'valores';
        grupo.dataset.fase = 'cargando';
        grupo.setAttribute('aria-busy', 'true');
        const leyenda = document.createElement('legend');
        leyenda.className = 'visually-hidden';
        leyenda.textContent = t('selector.valores.leyenda', { campo: opciones.nombreDe(filtro.campo) });
        grupo.append(leyenda, texto('field__hint', t('selector.valores.cargando'), 'status'));
        return [grupo];
      }
      case 'lista':
      case 'actualizando':
        return [lista(filtro, estado)];
      case 'sobre': {
        const aviso = texto(
          'field__hint valores__sobreUmbral',
          t('selector.valores.sobreUmbral', { umbral: formatNumber(estado.respuesta?.umbral ?? 0) }),
        );
        return [aviso, textarea(filtro), casillaVacioSuelta(filtro, estado)].filter((nodo): nodo is HTMLElement => nodo !== null);
      }
      case 'error': {
        const error = document.createElement('div');
        error.className = 'valores__error field__error';
        error.setAttribute('role', 'alert');
        const mensaje = document.createElement('span');
        mensaje.textContent = t('selector.valores.error');
        const reintentar = document.createElement('button');
        reintentar.type = 'button';
        reintentar.className = 'btn btn--sm';
        reintentar.dataset.foco = 'reintentar';
        reintentar.textContent = t('selector.valores.reintentar');
        reintentar.addEventListener('click', () => reintentar_(filtro, estado));
        error.append(mensaje, reintentar);
        return [error, textarea(filtro), casillaVacioSuelta(filtro, estado)].filter((nodo): nodo is HTMLElement => nodo !== null);
      }
      default:
        // A date with no current version, or a field that is not text: the text area of always.
        return [textarea(filtro), casillaVacioSuelta(filtro, estado)].filter((nodo): nodo is HTMLElement => nodo !== null);
    }
  }

  /** Draws again, keeping the focus where it was (the box, the search, a button) and the caret with it. */
  function dibujar(filtro: FiltroBorrador, estado: EstadoLista): void {
    const contenedor = estado.contenedor;
    if (!contenedor || !contenedor.isConnected) return;
    const activo = document.activeElement instanceof HTMLElement && contenedor.contains(document.activeElement) ? document.activeElement : null;
    const foco = activo?.dataset.foco;
    const rango = activo instanceof HTMLInputElement || activo instanceof HTMLTextAreaElement ? [activo.selectionStart, activo.selectionEnd] : null;
    contenedor.replaceChildren(...contenido(filtro, estado));
    if (foco === undefined) return;
    const nuevo = [...contenedor.querySelectorAll<HTMLElement>('[data-foco]')].find((nodo) => nodo.dataset.foco === foco);
    nuevo?.focus();
    if (nuevo && rango && rango[0] !== null && rango[1] !== null && (nuevo instanceof HTMLInputElement || nuevo instanceof HTMLTextAreaElement)) {
      nuevo.setSelectionRange(rango[0], rango[1]);
    }
  }

  // ---- Asking ----------------------------------------------------------------------------------

  async function pedir(filtro: FiltroBorrador, estado: EstadoLista, clave: string): Promise<void> {
    const indice = opciones.filtros().indexOf(filtro);
    const fecha = opciones.fecha();
    if (indice < 0 || !fecha || !aplica(filtro)) return;
    // The cascade moved on while waiting: this question is not the current one.
    if (clave !== claveDeLista(fecha, filtro.campo, filtrosDeArriba(opciones.filtros(), indice))) return;
    const control = new AbortController();
    estado.control = control;
    try {
      const respuesta = await valoresDeCampo(fecha, filtro.campo, filtrosDeArriba(opciones.filtros(), indice), control.signal);
      if (control.signal.aborted) return;
      estado.respuesta = respuesta;
      estado.fase = respuesta.ofrece_lista ? 'lista' : 'sobre';
      estado.claveSobre = respuesta.ofrece_lista ? null : claveDeDecision(fecha, filtro.campo);
    } catch (error) {
      if (control.signal.aborted) return;
      // 404 (no current version) and 400 (not text) are not the row's to report: the text area of always.
      estado.fase = error instanceof ApiError && (error.status === 404 || error.status === 400) ? 'sin' : 'error';
      estado.respuesta = estado.fase === 'sin' ? null : estado.respuesta;
    }
    dibujar(filtro, estado);
  }

  function programar(filtro: FiltroBorrador, estado: EstadoLista, clave: string, espera: number): void {
    window.clearTimeout(estado.temporizador);
    estado.control?.abort();
    estado.claveSolicitada = clave;
    estado.fase = estado.respuesta?.ofrece_lista ? 'actualizando' : 'cargando';
    dibujar(filtro, estado);
    estado.temporizador = window.setTimeout(() => void pedir(filtro, estado, clave), espera);
  }

  function reintentar_(filtro: FiltroBorrador, estado: EstadoLista): void {
    const fecha = opciones.fecha();
    const indice = opciones.filtros().indexOf(filtro);
    if (!fecha || indice < 0) return;
    programar(filtro, estado, claveDeLista(fecha, filtro.campo, filtrosDeArriba(opciones.filtros(), indice)), 0);
  }

  function sincronizar(): void {
    const filtros = opciones.filtros();
    const fecha = opciones.fecha();
    // A filter that left, or no longer picks from a list, takes its question with it.
    for (const filtro of [...estados.keys()]) {
      if (!filtros.includes(filtro) || !aplica(filtro)) olvidar(filtro);
    }
    filtros.forEach((filtro, indice) => {
      if (!aplica(filtro)) return;
      const estado = estadoDe(filtro);
      if (!fecha) {
        if (estado.fase !== 'sin') {
          window.clearTimeout(estado.temporizador);
          estado.control?.abort();
          estado.fase = 'sin';
          estado.claveSolicitada = null;
          dibujar(filtro, estado);
        }
        return;
      }
      const clave = claveDeLista(fecha, filtro.campo, filtrosDeArriba(filtros, indice));
      if (estado.claveSolicitada === clave) return;
      // A field over the threshold stays a text area whatever the filters above say: only the date or the field can change that.
      if (estado.fase === 'sobre' && estado.claveSobre === claveDeDecision(fecha, filtro.campo)) {
        estado.claveSolicitada = clave;
        return;
      }
      // The first question of a filter goes at once; a change above it waits for the last one.
      programar(filtro, estado, clave, estado.claveSolicitada === null ? 0 : ESPERA);
    });
  }

  return {
    aplica,
    pintar(contenedor, filtro) {
      const estado = estadoDe(filtro);
      estado.contenedor = contenedor;
      contenedor.replaceChildren(...contenido(filtro, estado));
    },
    sincronizar,
  };
}
