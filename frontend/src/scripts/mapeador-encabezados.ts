/**
 * Behaviour of the header mapper (docs/mapeador-encabezados-interfaz.md §2 and
 * §3). The markup is `components/MapeadorEncabezados.astro`. The page renders
 * it, listens for `mapeocambiado` on the root and then calls `montarMapeador`.
 *
 * The backend decides; this shows. Choices live in `lib/mapeador.ts`; every
 * change is validated through `validar` (300 ms after the last one, cancelling
 * the request before). Rows are built once per analysis and then updated in
 * place, so a field list never loses the focus while the analyst works.
 */

import { ApiError } from '../lib/api';
import { etiquetaCampo, etiquetaDeCampo } from '../lib/campos';
import { campoDelError, codigoDeError, esBorradorPerdido, textoDeError } from '../lib/carga-mapeada';
import { formatNumber } from '../lib/format';
import { t } from '../lib/i18n';
import {
  aceptar,
  aceptarTodas,
  asignacionesIniciales,
  asignarCampo,
  columnasLibres,
  elegir,
  etiquetaColumna,
  insignia,
  modificado,
  pendiente,
  porRevisar,
  puedeCrearCampo,
  usos,
  type Analisis,
  type Asignacion,
  type Insignia,
  type Problema,
  type TipoNuevo,
} from '../lib/mapeador';
import type { components } from '../lib/contrato-api';
import { crearSelectorCampo, type OpcionCampo, type SelectorCampo } from './selector-campo';

type CampoDestino = components['schemas']['CampoDestinoRespuesta'];
type CampoCreado = components['schemas']['CampoAdicionalCreadoRespuesta'];

export const EVENTO_MAPEO = 'mapeocambiado';

const ESPERA = 300;
const NO_CARGAR = '';

export interface EstadoMapeo {
  asignaciones: Asignacion[];
  problemas: Problema[];
  /** No problems in the last finished validation: confirming is allowed with `listo && !pendiente`. */
  listo: boolean;
  pendiente: boolean;
  /** The analyst chose or accepted something: changing the sheet, separator or encoding discards it. */
  modificado: boolean;
}

export interface OpcionesMapeador {
  analisis: Analisis;
  campos: readonly CampoDestino[];
  /** Calls `/mapeador/borradores/{id}/validacion`; the component does not know the sheet. */
  validar: (asignaciones: Asignacion[], signal: AbortSignal) => Promise<Problema[]>;
  /**
   * RF-64, optional: creates an additional field from a column (`POST …/campos-adicionales`). Without it
   * there is no reference and no form: another catalogue may not admit additional fields.
   */
  crearCampo?: (indice: number, nombreLegible: string, tipo: TipoNuevo, signal: AbortSignal) => Promise<CampoCreado>;
}

export interface ControladorMapeador {
  estado(): EstadoMapeo;
  /** After changing the sheet, separator or encoding: starts over from the new analysis. */
  fijarAnalisis(analisis: Analisis): void;
  /**
   * Problems from outside, as a finished validation (the 422 of confirming):
   * shown where they belong, without touching the assignments.
   */
  fijarProblemas(problemas: Problema[]): void;
  /** The catalogue's new field list (after creating one): keeps everything chosen, unlike `fijarAnalisis`. */
  fijarCampos(campos: readonly CampoDestino[]): void;
  destruir(): void;
}

const TONO: Record<Insignia, string> = {
  recordado: 'info',
  coincide: 'vigente',
  por_revisar: 'advertencia',
  aceptado: 'vigente',
  sin_coincidencia: 'neutral',
  manual: 'neutral',
  nuevo: 'info',
};

/** The visible name of a field: the label of an additional one, its catalogue key, or the portfolio label as a fallback. */
function etiquetaDe(campo: CampoDestino): string {
  return etiquetaDeCampo({ nombre: campo.nombre, etiqueta: campo.etiqueta, clave: campo.clave_etiqueta });
}

export function montarMapeador(raiz: HTMLElement, opciones: OpcionesMapeador): ControladorMapeador {
  const id = raiz.id;
  const q = <T extends Element>(selector: string) => raiz.querySelector<T>(selector)!;
  const el = {
    contexto: q<HTMLElement>('[data-contexto]'),
    listo: q<HTMLElement>('[data-listo]'),
    listoTexto: q<HTMLElement>('[data-listo-texto]'),
    verColumnas: q<HTMLButtonElement>('[data-ver-columnas]'),
    resumen: q<HTMLElement>('[data-resumen]'),
    resumenLista: q<HTMLElement>('[data-resumen-lista]'),
    cuerpo: q<HTMLElement>('[data-cuerpo]'),
    filtro: [...raiz.querySelectorAll<HTMLButtonElement>('[data-filtro-opcion]')],
    aceptarTodas: q<HTMLButtonElement>('[data-aceptar-todas]'),
    anuncio: q<HTMLElement>('[data-anuncio]'),
    anuncioBusqueda: q<HTMLElement>('[data-anuncio-busqueda]'),
    filas: q<HTMLElement>('[data-filas]'),
    advertencias: q<HTMLElement>('[data-advertencias]'),
    advertenciasTitulo: q<HTMLElement>('[data-advertencias-titulo]'),
    advertenciasLista: q<HTMLElement>('[data-advertencias-lista]'),
  };
  const adicional = {
    raiz: q<HTMLElement>('[data-adicional]'),
    abrir: q<HTMLButtonElement>('[data-adicional-abrir]'),
    panel: q<HTMLElement>('[data-adicional-panel]'),
    columna: q<HTMLSelectElement>('[data-adicional-columna]'),
    columnaError: q<HTMLElement>('[data-adicional-columna-error]'),
    ejemplos: q<HTMLElement>('[data-adicional-ejemplos]'),
    nombre: q<HTMLInputElement>('[data-adicional-nombre]'),
    nombreError: q<HTMLElement>('[data-adicional-nombre-error]'),
    usarHueco: q<HTMLElement>('[data-adicional-usar-hueco]'),
    tipos: [...raiz.querySelectorAll<HTMLInputElement>('[data-adicional-tipo]')],
    error: q<HTMLElement>('[data-adicional-error]'),
    cancelar: q<HTMLButtonElement>('[data-adicional-cancelar]'),
    crear: q<HTMLButtonElement>('[data-adicional-crear]'),
  };
  let campos = opciones.campos;
  const campoDe = (nombre: string | null) => campos.find((c) => c.nombre === nombre);
  const etiquetaDeNombre = (nombre: string) => {
    const campo = campoDe(nombre);
    return campo ? etiquetaDe(campo) : etiquetaCampo(nombre);
  };

  const s = {
    analisis: opciones.analisis,
    asignaciones: asignacionesIniciales(opciones.analisis),
    problemas: [...opciones.analisis.problemas] as Problema[],
    filtro: 'revisar' as 'revisar' | 'todas',
    /** Rows shown under «Por revisar», fixed when the filter is chosen, so the list never moves under the cursor. */
    visibles: new Set<number>(),
    programado: false,
    enCurso: false,
    validada: true,
    destruido: false,
    contadorAnunciado: null as number | null,
    /** Column → the field created from it in this load: its tag says «Campo nuevo» while it keeps it. Lost with a new analysis. */
    nuevos: new Map<number, string>(),
    adicionalAbierto: false,
    creando: false,
    nombreTocado: false,
  };

  const columnaLetra = (indice: number) => etiquetaColumna(indice, s.analisis.formato);
  const asignacionDe = (indice: number) => s.asignaciones.find((a) => a.indice === indice)!;

  // ---- Event and validation --------------------------------------------------------------

  const pendienteValidar = () => s.programado || s.enCurso;

  function estado(): EstadoMapeo {
    return {
      asignaciones: s.asignaciones.map((a) => ({ ...a })),
      problemas: [...s.problemas],
      listo: s.validada && s.problemas.length === 0,
      pendiente: pendienteValidar(),
      modificado: modificado(s.asignaciones, s.analisis),
    };
  }

  function emitir(): void {
    if (s.destruido) return;
    raiz.dispatchEvent(new CustomEvent<EstadoMapeo>(EVENTO_MAPEO, { bubbles: true, detail: estado() }));
  }

  let temporizador: ReturnType<typeof setTimeout> | undefined;
  let controlador: AbortController | null = null;

  function programar(): void {
    if (s.destruido) return;
    s.programado = true;
    clearTimeout(temporizador);
    temporizador = setTimeout(() => void validarAhora(), ESPERA);
  }

  async function validarAhora(): Promise<void> {
    s.programado = false;
    s.enCurso = true;
    controlador?.abort();
    const propio = new AbortController();
    controlador = propio;
    try {
      const problemas = await opciones.validar(s.asignaciones.map((a) => ({ ...a })), propio.signal);
      if (propio.signal.aborted || s.destruido) return;
      s.problemas = problemas;
      s.validada = true;
    } catch {
      if (propio.signal.aborted || s.destruido) return;
      // Unreachable or refused: nothing may be confirmed on a guess.
      s.validada = false;
    }
    s.enCurso = false;
    pintar();
    emitir();
  }

  function cambio(asignaciones: Asignacion[]): void {
    s.asignaciones = asignaciones;
    pintar();
    programar();
    emitir();
  }

  // ---- Rows --------------------------------------------------------------------------------

  /** Required fields first, then the rest, each by label (§3.5). */
  const ordenados = () =>
    [...campos].sort((a, b) => Number(b.obligatorio) - Number(a.obligatorio) || etiquetaDe(a).localeCompare(etiquetaDe(b)));

  /** The fields as one row's list shows them now: one another column uses is disabled, except in the rows that hold it. */
  function opcionesDe(indice: number): OpcionCampo[] {
    const enUso = usos(s.asignaciones);
    const propio = asignacionDe(indice).campo;
    return ordenados().map((campo) => {
      const otras = (enUso.get(campo.nombre) ?? []).filter((i) => i !== indice);
      const etiqueta = etiquetaDe(campo);
      return {
        nombre: campo.nombre,
        etiqueta,
        alias: campo.alias,
        texto: otras.length ? t('mapeador.vista.enUso', { campo: etiqueta, columnas: otras.map(columnaLetra).join(' y ') }) : etiqueta,
        grupo: campo.obligatorio ? 'obligatorios' : campo.adicional ? 'adicionales' : 'otros',
        // Decision of 2026-10-27.
        deshabilitada: otras.length > 0 && propio !== campo.nombre,
      };
    });
  }

  const selectores = new Map<number, SelectorCampo>();

  function crearSelector(indice: number, encabezado: string): SelectorCampo {
    const selector = crearSelectorCampo({
      id: `${id}-campo-${indice}`,
      nombre: t('mapeador.vista.campoPara', { columna: columnaLetra(indice), encabezado }),
      opciones: () => opcionesDe(indice),
      valor: () => asignacionDe(indice).campo ?? NO_CARGAR,
      onElegir: (valor) => cambio(elegir(s.asignaciones, s.analisis, indice, valor === NO_CARGAR ? null : valor)),
      anunciar: (texto) => (el.anuncioBusqueda.textContent = texto),
    });
    selector.input.dataset.campo = String(indice);
    selectores.set(indice, selector);
    return selector;
  }

  function crearFila(columna: Analisis['columnas'][number]): HTMLTableRowElement {
    const fila = document.createElement('tr');
    fila.dataset.fila = String(columna.indice);

    const celdaColumna = document.createElement('td');
    celdaColumna.className = 'mono mapeador__col';
    celdaColumna.dataset.etiqueta = t('mapeador.vista.col.columna');
    celdaColumna.textContent = columnaLetra(columna.indice);

    const celdaEncabezado = document.createElement('th');
    celdaEncabezado.scope = 'row';
    celdaEncabezado.className = 'mapeador__encabezado';
    celdaEncabezado.dataset.etiqueta = t('mapeador.vista.col.encabezado');
    celdaEncabezado.textContent = columna.encabezado;

    const celdaEjemplos = document.createElement('td');
    celdaEjemplos.dataset.etiqueta = t('mapeador.vista.col.ejemplos');
    if (columna.ejemplos.length === 0) {
      celdaEjemplos.textContent = '—';
    } else {
      const lista = document.createElement('span');
      lista.className = 'mono mapeador__ejemplos';
      columna.ejemplos.forEach((ejemplo, i) => {
        if (i > 0) lista.append(' · ');
        const uno = document.createElement('span');
        uno.className = 'mapeador__ejemplo';
        uno.textContent = ejemplo;
        uno.title = ejemplo;
        lista.append(uno);
      });
      celdaEjemplos.append(lista);
    }

    const celdaEstado = document.createElement('td');
    celdaEstado.dataset.etiqueta = t('mapeador.vista.col.estado');
    const tag = document.createElement('span');
    tag.dataset.insignia = '';
    const nota = document.createElement('span');
    nota.className = 'field__hint mapeador__nota';
    nota.dataset.nota = '';
    celdaEstado.append(tag, nota);

    const celdaCampo = document.createElement('td');
    celdaCampo.dataset.etiqueta = t('mapeador.vista.col.campo');
    const control = document.createElement('div');
    control.className = 'mapeador__control';
    const selector = crearSelector(columna.indice, columna.encabezado);
    const botonAceptar = document.createElement('button');
    botonAceptar.type = 'button';
    botonAceptar.className = 'btn btn--sm';
    botonAceptar.dataset.aceptar = String(columna.indice);
    botonAceptar.textContent = t('mapeador.vista.aceptar');
    botonAceptar.addEventListener('click', () => {
      cambio(aceptar(s.asignaciones, s.analisis, columna.indice));
      selector.input.focus();
    });
    control.append(selector.raiz, botonAceptar);
    const error = document.createElement('p');
    error.className = 'field__error';
    error.id = `${id}-error-${columna.indice}`;
    error.dataset.error = String(columna.indice);
    celdaCampo.append(control, error);

    fila.append(celdaColumna, celdaEncabezado, celdaEjemplos, celdaEstado, celdaCampo);
    return fila;
  }

  function mensajeProblema(problema: Problema): string {
    const clave = `mapeador.problema.${problema.codigo}`;
    const texto = t(clave, { campo: problema.campo ? etiquetaDeNombre(problema.campo) : '' });
    return texto === clave ? problema.detalle : texto;
  }

  /** Each row in place: tag, note, its field list, «Aceptar» and its problem. */
  function pintarFilas(): void {
    for (const columna of s.analisis.columnas) {
      const fila = el.filas.querySelector<HTMLTableRowElement>(`[data-fila="${columna.indice}"]`)!;
      const asignacion = asignacionDe(columna.indice);
      const tipo = insignia(columna, asignacion, s.nuevos.get(columna.indice) ?? null);

      const tag = fila.querySelector<HTMLElement>('[data-insignia]')!;
      tag.className = `tag tag--${TONO[tipo]}`;
      tag.textContent = t(`mapeador.vista.insignia.${tipo}`);
      const nota = fila.querySelector<HTMLElement>('[data-nota]')!;
      nota.textContent =
        tipo === 'recordado'
          ? t('mapeador.vista.nota.recordado')
          : tipo === 'nuevo'
            ? t('mapeador.vista.nota.nuevo')
            : tipo === 'por_revisar' && columna.sugerido
            ? t('mapeador.vista.nota.parecido', { campo: etiquetaDeNombre(columna.sugerido) })
            : '';

      const selector = selectores.get(columna.indice)!;
      selector.pintar();
      const campo = selector.input;

      const botonAceptar = fila.querySelector<HTMLButtonElement>('[data-aceptar]')!;
      botonAceptar.hidden = !pendiente(columna, asignacion);
      if (columna.sugerido) {
        botonAceptar.setAttribute(
          'aria-label',
          t('mapeador.vista.aceptarPara', { campo: etiquetaDeNombre(columna.sugerido), columna: columnaLetra(columna.indice) }),
        );
      }

      const error = fila.querySelector<HTMLElement>('[data-error]')!;
      const propios = s.problemas.filter((p) => p.indice === columna.indice);
      error.textContent = propios.map(mensajeProblema).join(' ');
      if (propios.length) {
        campo.setAttribute('aria-invalid', 'true');
        campo.setAttribute('aria-describedby', error.id);
      } else {
        campo.removeAttribute('aria-invalid');
        campo.removeAttribute('aria-describedby');
      }

      fila.hidden = s.filtro === 'revisar' && !s.visibles.has(columna.indice);
    }
  }

  // ---- Summary, filter and the rest ---------------------------------------------------------

  function pintarResumen(): void {
    const sinFila = s.problemas.filter((p) => p.indice === null || !s.analisis.columnas.some((c) => c.indice === p.indice));
    el.resumen.hidden = sinFila.length === 0;
    el.resumenLista.replaceChildren(
      ...sinFila.map((problema) => {
        const item = document.createElement('li');
        const texto = document.createElement('span');
        texto.textContent = mensajeProblema(problema);
        item.append(texto);
        if (problema.codigo === 'obligatorio_sin_columna') {
          const ir = document.createElement('button');
          ir.type = 'button';
          ir.className = 'btn btn--sm';
          ir.textContent = t('mapeador.vista.elegirColumna');
          ir.addEventListener('click', () => {
            fijarFiltro('todas');
            const libre = s.asignaciones.find((a) => a.campo === null) ?? s.asignaciones[0];
            if (libre) selectores.get(libre.indice)?.input.focus();
          });
          item.append(' ', ir);
        }
        return item;
      }),
    );
  }

  function pintarBarra(): void {
    const revisar = porRevisar(s.analisis, s.asignaciones, s.problemas).size;
    const [botonRevisar, botonTodas] = el.filtro;
    botonRevisar.textContent = t('mapeador.vista.filtro.revisar', { n: revisar });
    botonTodas.textContent = t('mapeador.vista.filtro.todas', { n: s.analisis.columnas.length });
    for (const b of el.filtro) b.setAttribute('aria-pressed', String(b.dataset.filtroOpcion === s.filtro));

    const pendientes = s.analisis.columnas.filter((c) => pendiente(c, asignacionDe(c.indice))).length;
    el.aceptarTodas.hidden = pendientes === 0;
    el.aceptarTodas.textContent = t('mapeador.vista.aceptarTodas', { n: pendientes });

    // Said only when the number changes; the first paint is silent.
    if (s.contadorAnunciado !== null && revisar !== s.contadorAnunciado) {
      el.anuncio.textContent = t('mapeador.vista.anuncioRevisar', { n: revisar });
    }
    s.contadorAnunciado = revisar;
  }

  function pintar(): void {
    pintarFilas();
    pintarResumen();
    pintarBarra();
    pintarAdicional();
  }

  // ---- Create an additional field (RF-64, docs/campos-adicionales-interfaz.md §2) -----------------

  const columnaElegida = (): number | null => (adicional.columna.value === '' ? null : Number(adicional.columna.value));
  const tipoElegido = (): TipoNuevo | null => (adicional.tipos.find((r) => r.checked)?.value as TipoNuevo | undefined) ?? null;
  const columnaPorIndice = (indice: number | null) => s.analisis.columnas.find((c) => c.indice === indice);

  function pintarEjemplos(): void {
    const columna = columnaPorIndice(columnaElegida());
    adicional.ejemplos.textContent =
      columna && columna.ejemplos.length > 0 ? t('mapeador.vista.adicional.ejemplos', { ejemplos: columna.ejemplos.join(' · ') }) : '';
  }

  function pintarBotonCrear(): void {
    adicional.crear.disabled = s.creando || !puedeCrearCampo(columnaElegida(), adicional.nombre.value, tipoElegido());
    adicional.crear.dataset.loading = String(s.creando);
  }

  /** The columns that can still hold a new field, as the list shows them; a column that stopped being free drops out. */
  function pintarColumnasLibres(): void {
    const libres = columnasLibres(s.analisis, s.asignaciones);
    const antes = adicional.columna.value;
    const opcionesColumna = libres.map((c) => {
      const opcion = document.createElement('option');
      opcion.value = String(c.indice);
      opcion.textContent = t('mapeador.vista.adicional.columnaOpcion', { columna: columnaLetra(c.indice), encabezado: c.encabezado });
      return opcion;
    });
    if (libres.length !== 1) {
      const elige = document.createElement('option');
      elige.value = '';
      elige.textContent = t('mapeador.vista.adicional.columnaElige');
      opcionesColumna.unshift(elige);
    }
    adicional.columna.replaceChildren(...opcionesColumna);
    adicional.columna.value = libres.some((c) => String(c.indice) === antes) ? antes : libres.length === 1 ? String(libres[0].indice) : '';
    pintarEjemplos();
    pintarBotonCrear();
  }

  function limpiarErroresAdicional(): void {
    for (const nodo of [adicional.columnaError, adicional.nombreError, adicional.error]) nodo.textContent = '';
    adicional.usarHueco.replaceChildren();
    adicional.nombre.removeAttribute('aria-invalid');
  }

  function pintarAdicional(): void {
    const hayColumnas = columnasLibres(s.analisis, s.asignaciones).length > 0;
    adicional.raiz.hidden = !opciones.crearCampo || (!hayColumnas && !s.adicionalAbierto);
    if (s.adicionalAbierto) pintarColumnasLibres();
  }

  function abrirAdicional(): void {
    s.adicionalAbierto = true;
    s.nombreTocado = false;
    adicional.panel.hidden = false;
    adicional.abrir.setAttribute('aria-expanded', 'true');
    for (const r of adicional.tipos) r.checked = false;
    limpiarErroresAdicional();
    pintarColumnasLibres();
    const unica = columnaElegida();
    adicional.nombre.value = columnaPorIndice(unica)?.encabezado ?? '';
    pintarBotonCrear();
    (unica === null ? adicional.columna : adicional.nombre).focus();
  }

  function cerrarAdicional(devolverFoco: boolean): void {
    s.adicionalAbierto = false;
    adicional.panel.hidden = true;
    adicional.abrir.setAttribute('aria-expanded', 'false');
    limpiarErroresAdicional();
    pintarAdicional();
    if (devolverFoco) adicional.abrir.focus();
  }

  /** After assigning a field to a column: the row stays in sight and its list gets the focus. */
  function mostrarFila(indice: number): void {
    s.visibles.add(indice);
    // «Todo listo» folds the table; the new assignment is shown, so it opens.
    if (el.cuerpo.hidden) {
      el.cuerpo.hidden = false;
      el.verColumnas.setAttribute('aria-expanded', 'true');
    }
    pintarFilas();
    const selector = selectores.get(indice);
    const fila = el.filas.querySelector<HTMLElement>(`[data-fila="${indice}"]`);
    if (!selector || !fila || fila.hidden || el.cuerpo.hidden) {
      adicional.abrir.focus();
      return;
    }
    fila.scrollIntoView?.({ block: 'nearest' });
    selector.input.focus();
  }

  function usarCampoExistente(indice: number, campo: CampoDestino): void {
    cambio(asignarCampo(s.asignaciones, indice, campo.nombre));
    el.anuncioBusqueda.textContent = t('mapeador.vista.adicional.usado', { campo: etiquetaDe(campo), columna: columnaLetra(indice) });
    cerrarAdicional(false);
    mostrarFila(indice);
  }

  function errorAlCrear(error: unknown, indice: number): void {
    // An expired draft: the page already took the analyst back to the first step.
    if (esBorradorPerdido(error) || s.destruido) return;
    const texto = textoDeError(error, t('console.upload.error.network'), t('common.errorBody'));
    const codigo = codigoDeError(error);
    const estado = error instanceof ApiError ? error.status : 0;
    if (estado === 409 && codigo === 'nombre_repetido') {
      // An additional field the catalogue no longer lists is an archived one: it cannot be chosen, so «Elígelo en la lista» would lie.
      const colision = campoDelError(error);
      const archivado = Boolean(colision?.campo.adicional) && !campoDe(colision!.campo.nombre);
      adicional.nombreError.textContent = archivado
        ? t('mapeador.vista.adicional.nombreArchivado', { campo: colision!.etiquetaVisible })
        : texto;
      adicional.nombre.setAttribute('aria-invalid', 'true');
      adicional.nombre.focus();
      const choca = campoDelError(error)?.campo;
      const enCatalogo = choca ? campoDe(choca.nombre) : undefined;
      const ocupado = enCatalogo ? (usos(s.asignaciones).get(enCatalogo.nombre) ?? []).some((i) => i !== indice) : true;
      if (enCatalogo && !ocupado) {
        const usar = document.createElement('button');
        usar.type = 'button';
        usar.className = 'btn btn--sm';
        usar.dataset.adicionalUsar = '';
        usar.textContent = t('mapeador.vista.adicional.usar', { campo: etiquetaDe(enCatalogo), columna: columnaLetra(indice) });
        usar.addEventListener('click', () => usarCampoExistente(indice, enCatalogo));
        adicional.usarHueco.replaceChildren(usar);
      }
    } else if (codigo === 'columna_inexistente') {
      adicional.columnaError.textContent = texto;
    } else if (estado === 422 && !codigo) {
      adicional.nombreError.textContent = t('mapeador.vista.adicional.nombreInvalido');
      adicional.nombre.setAttribute('aria-invalid', 'true');
      adicional.nombre.focus();
    } else {
      adicional.error.textContent = texto;
    }
  }

  let controladorCrear: AbortController | null = null;

  async function crearAdicional(): Promise<void> {
    const indice = columnaElegida();
    const tipo = tipoElegido();
    const nombre = adicional.nombre.value.trim();
    if (!opciones.crearCampo || s.creando || indice === null || tipo === null || !puedeCrearCampo(indice, nombre, tipo)) return;
    limpiarErroresAdicional();
    s.creando = true;
    pintarBotonCrear();
    controladorCrear = new AbortController();
    try {
      const creado = await opciones.crearCampo(indice, nombre, tipo, controladorCrear.signal);
      if (s.destruido) return;
      campos = creado.campos;
      s.nuevos.set(indice, creado.campo.nombre);
      cambio(asignarCampo(s.asignaciones, indice, creado.campo.nombre));
      el.anuncioBusqueda.textContent = t('mapeador.vista.adicional.creado', { campo: etiquetaDe(creado.campo), columna: columnaLetra(indice) });
      cerrarAdicional(false);
      mostrarFila(indice);
    } catch (error) {
      errorAlCrear(error, indice);
    } finally {
      s.creando = false;
      if (!s.destruido) pintarBotonCrear();
    }
  }

  adicional.abrir.addEventListener('click', () => (s.adicionalAbierto ? cerrarAdicional(true) : abrirAdicional()));
  adicional.cancelar.addEventListener('click', () => cerrarAdicional(true));
  adicional.crear.addEventListener('click', () => void crearAdicional());
  adicional.columna.addEventListener('change', () => {
    adicional.columnaError.textContent = '';
    if (!s.nombreTocado) adicional.nombre.value = columnaPorIndice(columnaElegida())?.encabezado ?? '';
    pintarEjemplos();
    pintarBotonCrear();
  });
  adicional.nombre.addEventListener('input', () => {
    s.nombreTocado = true;
    adicional.nombreError.textContent = '';
    adicional.usarHueco.replaceChildren();
    adicional.nombre.removeAttribute('aria-invalid');
    pintarBotonCrear();
  });
  // The mapper may sit inside a <form> (the upload dialog): Enter here creates the field, never submits that form.
  adicional.nombre.addEventListener('keydown', (evento) => {
    if (evento.key !== 'Enter') return;
    evento.preventDefault();
    void crearAdicional();
  });
  for (const radio of adicional.tipos) radio.addEventListener('change', pintarBotonCrear);

  function fijarFiltro(filtro: 'revisar' | 'todas'): void {
    s.filtro = filtro;
    s.visibles = porRevisar(s.analisis, s.asignaciones, s.problemas);
    pintar();
  }

  for (const boton of el.filtro) {
    boton.addEventListener('click', () => fijarFiltro(boton.dataset.filtroOpcion as 'revisar' | 'todas'));
  }
  el.aceptarTodas.addEventListener('click', () => cambio(aceptarTodas(s.asignaciones, s.analisis)));
  el.verColumnas.addEventListener('click', () => {
    const abierto = el.verColumnas.getAttribute('aria-expanded') !== 'true';
    el.verColumnas.setAttribute('aria-expanded', String(abierto));
    el.cuerpo.hidden = !abierto;
  });

  function pintarContexto(): void {
    const partes = [
      t('mapeador.vista.contexto.columnas', { n: formatNumber(s.analisis.columnas.length) }),
      t('mapeador.vista.contexto.filas', { n: formatNumber(s.analisis.filas) }),
    ];
    if (s.analisis.hoja) partes.push(t('mapeador.vista.contexto.hoja', { hoja: s.analisis.hoja }));
    el.contexto.textContent = partes.join(' · ');
  }

  function pintarAdvertencias(): void {
    const lista = s.analisis.advertencias;
    el.advertencias.hidden = lista.length === 0;
    el.advertenciasTitulo.textContent = t('mapeador.vista.advertencias', { n: formatNumber(lista.length) });
    el.advertenciasLista.replaceChildren(
      ...lista.map((a) => {
        const item = document.createElement('li');
        const clave = `mapeador.advertencia.${a.codigo}`;
        item.textContent = t('mapeador.vista.advertencia', {
          fila: formatNumber(a.numero_fila),
          columna: a.columna,
          texto: t(clave),
        });
        return item;
      }),
    );
  }

  /** Rows and texts that depend on the language; the analyst's choices stay. */
  function construir(): void {
    selectores.clear();
    el.filas.replaceChildren(...s.analisis.columnas.map(crearFila));
    el.listoTexto.textContent = t('mapeador.vista.listo', { n: formatNumber(s.analisis.columnas.length) });
    pintarContexto();
    pintarAdvertencias();
    pintar();
  }

  /** Start over from an analysis: choices, filter, and the «todo listo» case (§3.2). */
  function montarAnalisis(analisis: Analisis): void {
    s.analisis = analisis;
    s.asignaciones = asignacionesIniciales(analisis);
    s.problemas = [...analisis.problemas];
    s.validada = true;
    s.contadorAnunciado = null;
    s.nuevos.clear();
    if (s.adicionalAbierto) cerrarAdicional(false);
    const revisar = porRevisar(analisis, s.asignaciones, s.problemas);
    const todoListo = revisar.size === 0 && s.problemas.length === 0;
    s.filtro = revisar.size > 0 ? 'revisar' : 'todas';
    s.visibles = revisar;
    el.listo.hidden = !todoListo;
    el.verColumnas.setAttribute('aria-expanded', 'false');
    el.cuerpo.hidden = todoListo;
    construir();
  }

  const alCambiarIdioma = () => construir();
  document.addEventListener('languagechange', alCambiarIdioma);

  montarAnalisis(opciones.analisis);
  emitir();

  return {
    estado,
    fijarAnalisis(analisis) {
      clearTimeout(temporizador);
      controlador?.abort();
      s.programado = false;
      s.enCurso = false;
      montarAnalisis(analisis);
      emitir();
    },
    fijarProblemas(problemas) {
      clearTimeout(temporizador);
      controlador?.abort();
      s.programado = false;
      s.enCurso = false;
      s.problemas = [...problemas];
      s.validada = true;
      // The table comes back if it was folded away as «todo listo», on the rows to review.
      el.listo.hidden = true;
      el.cuerpo.hidden = false;
      s.visibles = porRevisar(s.analisis, s.asignaciones, s.problemas);
      s.filtro = s.visibles.size > 0 ? 'revisar' : 'todas';
      pintar();
      emitir();
    },
    fijarCampos(lista) {
      campos = lista;
      pintar();
    },
    destruir() {
      s.destruido = true;
      controladorCrear?.abort();
      document.removeEventListener('languagechange', alCambiarIdioma);
      clearTimeout(temporizador);
      controlador?.abort();
    },
  };
}
