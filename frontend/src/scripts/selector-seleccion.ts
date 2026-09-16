/**
 * The selection picker: a cut-off date plus a saved selection, and in full
 * mode the editor for filters, order, the top n and custom indicators.
 *
 * It owns the selection and nothing else. Whoever mounts it listens for
 * `seleccioncambiada` on the root and decides what to compute with it: the
 * portfolio screen recalculates metrics, the MOWA MES campaign builds its
 * base. The markup lives in `components/SelectorSeleccion.astro`; this module
 * is imported and mounted by the page, after it has subscribed, so no change
 * is ever emitted before someone is listening.
 *
 * Saved selections are shared with the whole team (decision C-3: anyone may
 * edit or delete). Nothing is overwritten without an explicit action.
 */

import {
  ApiError,
  NetworkError,
  actualizarSeleccion,
  crearSeleccion,
  eliminarSeleccion,
  listarCampos,
  listarSelecciones,
  listarVersiones,
  revisarSeleccion,
  type Campos,
  type SeleccionEntrada,
  type SeleccionGuardada,
  type Version,
} from '../lib/api';
import { openWhenFree } from '../lib/dialogs';
import { formatDate } from '../lib/format';
import { t } from '../lib/i18n';
import {
  FUNCIONES,
  borradorDe,
  consultaDe,
  funcionAdmiteCampo,
  humanizarCampo,
  leerCantidad,
  operadoresPara,
  partesIncompletas,
  seleccionVacia,
  tipoDe,
  ubicarProblemas,
  valoresQuePide,
  type Consulta,
  type FiltroBorrador,
  type Funcion,
  type IndicadorBorrador,
  type ProblemaUbicado,
  type SeleccionBorrador,
  type TipoCampo,
} from '../lib/seleccion';

export const EVENTO_SELECCION = 'seleccioncambiada';

/** Long enough that a review does not fire on every keystroke. */
const ESPERA_REVISION = 600;

export interface FechaDeCorte {
  fecha: string;
  vigente: boolean;
}

export interface EstadoSeleccion {
  fechaCorte: string | null;
  fechas: FechaDeCorte[];
  /** Complete parts only, in the API's syntax. */
  consulta: Consulta;
  /** False while the API says a part does not apply: do not query with it. */
  aplicable: boolean;
  /** Parts still being written; they are left out of `consulta`. */
  incompletas: number;
  guardada: SeleccionGuardada | null;
  campos: Campos;
}

export interface ControladorSelector {
  estado(): EstadoSeleccion;
}

/** Cut-off dates, newest first, each saying whether it has a current version. */
function fechasDe(versiones: Version[]): FechaDeCorte[] {
  const porFecha = new Map<string, boolean>();
  versiones.forEach((version) => {
    porFecha.set(version.fecha_corte, (porFecha.get(version.fecha_corte) ?? false) || version.vigente);
  });
  return [...porFecha]
    .map(([fecha, vigente]) => ({ fecha, vigente }))
    .sort((a, b) => (a.fecha < b.fecha ? 1 : -1));
}

function valoresPara(operador: string, previos: string[] = []): string[] {
  const pide = valoresQuePide(operador);
  if (pide === 0) return [];
  if (pide === null) return previos.length ? previos : [''];
  return Array.from({ length: pide }, (_, i) => previos[i] ?? '');
}

/**
 * Mount the picker inside `root`. Rejects with `NetworkError` when the API
 * cannot be reached, so the page can stand down with its own message.
 */
export async function montarSelector(root: HTMLElement): Promise<ControladorSelector> {
  const [campos, selecciones, versiones] = await Promise.all([
    listarCampos(),
    listarSelecciones(),
    listarVersiones({ limite: 200 }),
  ]);

  const fechas = fechasDe(versiones);
  const s = {
    campos,
    selecciones,
    fechas,
    fechaCorte: ((fechas.find((f) => f.vigente) ?? fechas[0])?.fecha ?? null) as string | null,
    borrador: seleccionVacia() as SeleccionBorrador,
    /** The draft as last loaded or saved; any difference is an unsaved change. */
    base: JSON.stringify(seleccionVacia()),
    guardada: null as SeleccionGuardada | null,
    problemas: [] as ProblemaUbicado[],
    cantidadInvalida: false,
  };

  const q = <T extends Element>(selector: string) => root.querySelector<T>(selector);
  const el = {
    fecha: q<HTMLSelectElement>('[data-selector-fecha]')!,
    guardada: q<HTMLSelectElement>('[data-selector-guardada]')!,
    estado: q<HTMLElement>('[data-selector-estado]')!,
    problemas: q<HTMLElement>('[data-selector-problemas]')!,
    problemasLista: q<HTMLElement>('[data-selector-problemas-lista]')!,
    editor: q<HTMLElement>('[data-editor]'),
  };

  const nombresDeCampos = (): string[] =>
    Object.keys(s.campos).sort((a, b) => humanizarCampo(a).localeCompare(humanizarCampo(b)));

  const sucio = (): boolean => JSON.stringify(s.borrador) !== s.base;

  const incompletas = (): number => {
    const partes = partesIncompletas(s.borrador);
    return partes.filtros.length + partes.indicadores.length + (s.cantidadInvalida ? 1 : 0);
  };

  function estado(): EstadoSeleccion {
    return {
      fechaCorte: s.fechaCorte,
      fechas: s.fechas,
      consulta: consultaDe(s.borrador),
      aplicable: s.problemas.length === 0,
      incompletas: incompletas(),
      guardada: s.guardada,
      campos: s.campos,
    };
  }

  function emitir(): void {
    root.dispatchEvent(
      new CustomEvent<EstadoSeleccion>(EVENTO_SELECCION, { bubbles: true, detail: estado() }),
    );
  }

  // ---- Small DOM builders -------------------------------------------------------

  function crearSelect(
    etiqueta: string,
    opciones: Array<[string, string]>,
    valor: string,
    clase: string,
  ): HTMLSelectElement {
    const select = document.createElement('select');
    select.className = `input ${clase}`;
    select.setAttribute('aria-label', etiqueta);
    opciones.forEach(([value, texto]) => {
      const opcion = document.createElement('option');
      opcion.value = value;
      opcion.textContent = texto;
      opcion.selected = value === valor;
      select.append(opcion);
    });
    return select;
  }

  function botonQuitar(etiqueta: string): HTMLButtonElement {
    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'btn btn--quiet btn--icon fila__quitar';
    boton.setAttribute('aria-label', etiqueta);
    boton.title = etiqueta;
    const plantilla = q<HTMLTemplateElement>('template[data-icono-quitar]');
    if (plantilla) boton.append(plantilla.content.cloneNode(true));
    return boton;
  }

  function controlDeValor(tipo: TipoCampo | null, valor: string, etiqueta: string): HTMLInputElement | HTMLSelectElement {
    if (tipo === 'booleano') {
      return crearSelect(
        etiqueta,
        [
          ['', '—'],
          ['true', t('selector.filtro.si')],
          ['false', t('selector.filtro.no')],
        ],
        valor,
        'fila__valor',
      );
    }
    const input = document.createElement('input');
    input.className = 'input fila__valor';
    input.setAttribute('aria-label', etiqueta);
    input.value = valor;
    if (tipo === 'fecha') {
      input.type = 'date';
    } else {
      input.type = 'text';
      if (tipo === 'numero') input.inputMode = 'decimal';
    }
    return input;
  }

  // ---- Dates and saved selections -------------------------------------------------

  function renderFechas(): void {
    el.fecha.replaceChildren();
    if (s.fechas.length === 0) {
      const opcion = document.createElement('option');
      opcion.value = '';
      opcion.textContent = t('selector.fecha.ninguna');
      el.fecha.append(opcion);
      el.fecha.disabled = true;
      return;
    }
    el.fecha.disabled = false;
    s.fechas.forEach(({ fecha, vigente }) => {
      const opcion = document.createElement('option');
      opcion.value = fecha;
      // A date with no current version stays choosable: the screen then says
      // plainly that it has no portfolio, instead of hiding the date.
      opcion.textContent = vigente
        ? formatDate(fecha)
        : `${formatDate(fecha)} · ${t('selector.fecha.sinVigente')}`;
      opcion.selected = fecha === s.fechaCorte;
      el.fecha.append(opcion);
    });
  }

  function renderGuardadas(): void {
    el.guardada.replaceChildren();
    const nueva = document.createElement('option');
    nueva.value = '';
    nueva.textContent = t('selector.guardada.nueva');
    el.guardada.append(nueva);
    s.selecciones.forEach((seleccion) => {
      const opcion = document.createElement('option');
      opcion.value = String(seleccion.id);
      opcion.textContent = seleccion.aplicable
        ? seleccion.nombre
        : `${seleccion.nombre} · ${t('selector.guardada.noAplica')}`;
      opcion.selected = seleccion.id === s.guardada?.id;
      el.guardada.append(opcion);
    });
  }

  function cargarGuardada(id: number | null): void {
    s.guardada = s.selecciones.find((seleccion) => seleccion.id === id) ?? null;
    s.borrador = s.guardada ? borradorDe(s.guardada) : seleccionVacia();
    s.base = JSON.stringify(s.borrador);
    s.cantidadInvalida = false;
    // A saved selection that stopped applying loads anyway, with the broken
    // part marked: the analyst sees what broke instead of losing the work.
    s.problemas =
      s.guardada && !s.guardada.aplicable ? ubicarProblemas(s.guardada.problemas, s.borrador) : [];
    renderTodo();
    emitir();
  }

  el.fecha.addEventListener('change', () => {
    s.fechaCorte = el.fecha.value || null;
    emitir();
  });

  // ---- Marks, status line and actions ------------------------------------------------

  function marcar(fila: HTMLElement, marca: 'ok' | 'incompleta' | 'problema', detalle = ''): void {
    fila.dataset.estado = marca;
    const nota = fila.querySelector<HTMLElement>('.fila__nota')!;
    nota.textContent =
      marca === 'problema' ? detalle : marca === 'incompleta' ? t('selector.fila.incompleta') : '';
    fila.querySelectorAll<HTMLElement>('.input').forEach((control) => {
      if (marca === 'problema') {
        control.setAttribute('aria-invalid', 'true');
      } else {
        control.removeAttribute('aria-invalid');
      }
      if (nota.textContent) {
        control.setAttribute('aria-describedby', nota.id);
      } else {
        control.removeAttribute('aria-describedby');
      }
    });
  }

  function pintarMarcas(): void {
    const partes = partesIncompletas(s.borrador);

    root.querySelectorAll<HTMLElement>('[data-filtros] > .fila').forEach((fila) => {
      const indice = Number(fila.dataset.indice);
      const problema = s.problemas.find((p) => p.parte === 'filtro' && p.indice === indice);
      marcar(
        fila,
        problema ? 'problema' : partes.filtros.includes(indice) ? 'incompleta' : 'ok',
        problema?.detalle,
      );
    });

    root.querySelectorAll<HTMLElement>('[data-indicadores] > .fila').forEach((fila) => {
      const indice = Number(fila.dataset.indice);
      const problema = s.problemas.find((p) => p.parte === 'indicador' && p.indice === indice);
      marcar(
        fila,
        problema ? 'problema' : partes.indicadores.includes(indice) ? 'incompleta' : 'ok',
        problema?.detalle,
      );
    });

    el.problemas.hidden = s.problemas.length === 0;
    el.problemasLista.replaceChildren(
      ...s.problemas.map((problema) => {
        const item = document.createElement('li');
        const parte = document.createElement('strong');
        parte.textContent = `${t(`parte.${problema.parte}`)} `;
        const expresion = document.createElement('code');
        expresion.textContent = problema.expresion;
        item.append(parte, expresion, document.createTextNode(` — ${problema.detalle}`));
        return item;
      }),
    );
  }

  function pintarEstado(): void {
    const g = s.guardada;
    let texto = !g
      ? t('selector.estado.nueva')
      : sucio()
        ? t('selector.estado.cambios', { nombre: g.nombre })
        : t('selector.estado.guardada', { nombre: g.nombre });
    const n = incompletas();
    if (n === 1) texto += ` ${t('selector.estado.incompletaUna')}`;
    if (n > 1) texto += ` ${t('selector.estado.incompletas', { n })}`;
    // The line is a live region; rewriting the same words would re-announce them.
    if (el.estado.textContent !== texto) el.estado.textContent = texto;

    if (!el.editor) return;
    const guardar = q<HTMLButtonElement>('[data-guardar]')!;
    guardar.hidden = !g;
    guardar.disabled = !sucio() || n > 0;
    q<HTMLButtonElement>('[data-guardar-como]')!.disabled = n > 0;
    q<HTMLButtonElement>('[data-descartar]')!.hidden = !sucio();
    q<HTMLButtonElement>('[data-borrar]')!.hidden = !g;
  }

  /** An edit: the last review no longer describes the draft. */
  function cambio(): void {
    s.problemas = [];
    q<HTMLElement>('[data-selector-error]')?.replaceChildren();
    pintarMarcas();
    pintarEstado();
    emitir();
    programarRevision();
  }

  // ---- Live review ------------------------------------------------------------------

  let temporizadorRevision = 0;
  let controlRevision: AbortController | null = null;

  function entradaDe(nombre: string): SeleccionEntrada {
    const consulta = consultaDe(s.borrador);
    return {
      nombre,
      filtros: consulta.filtros,
      orden: consulta.orden,
      cantidad: consulta.cantidad,
      indicadores: consulta.indicadores,
    };
  }

  function programarRevision(): void {
    if (!el.editor) return;
    window.clearTimeout(temporizadorRevision);
    controlRevision?.abort();
    temporizadorRevision = window.setTimeout(() => void revisar(), ESPERA_REVISION);
  }

  async function revisar(): Promise<void> {
    const consulta = consultaDe(s.borrador);
    if (!consulta.filtros.length && !consulta.indicadores.length && !consulta.orden && !consulta.cantidad) {
      return;
    }
    const control = new AbortController();
    controlRevision = control;
    const revisado = JSON.stringify(s.borrador);
    try {
      const revision = await revisarSeleccion(
        entradaDe(s.guardada?.nombre ?? t('selector.title')),
        control.signal,
      );
      if (control.signal.aborted || JSON.stringify(s.borrador) !== revisado) return;
      const eraAplicable = s.problemas.length === 0;
      // The name is only checked on save; a draft is not yet named.
      s.problemas = ubicarProblemas(
        revision.problemas.filter((problema) => problema.parte !== 'nombre'),
        s.borrador,
      );
      pintarMarcas();
      if (eraAplicable !== (s.problemas.length === 0)) emitir();
    } catch {
      /* A review is a courtesy: the query itself still reports a bad part. */
    }
  }

  // ---- Editor: filters --------------------------------------------------------------

  function filaFiltro(filtro: FiltroBorrador, indice: number): HTMLLIElement {
    const fila = document.createElement('li');
    fila.className = 'fila fila--filtro';
    fila.dataset.indice = String(indice);

    const campo = crearSelect(
      t('selector.filtro.campo'),
      [['', t('selector.filtro.campo.elige')], ...nombresDeCampos().map((n): [string, string] => [n, humanizarCampo(n)])],
      filtro.campo,
      'fila__campo',
    );
    campo.addEventListener('change', () => {
      filtro.campo = campo.value;
      filtro.operador = operadoresPara(s.campos, filtro.campo)[0] ?? '';
      filtro.valores = valoresPara(filtro.operador);
      renderFiltros('.fila__campo', indice);
      cambio();
    });

    const operadores = filtro.campo ? operadoresPara(s.campos, filtro.campo) : [];
    const operador = crearSelect(
      t('selector.filtro.operador'),
      operadores.map((o): [string, string] => [o, t(`op.${o}`)]),
      filtro.operador,
      'fila__operador',
    );
    operador.disabled = !filtro.campo;
    operador.addEventListener('change', () => {
      filtro.operador = operador.value;
      filtro.valores = valoresPara(filtro.operador, filtro.valores);
      renderFiltros('.fila__operador', indice);
      cambio();
    });

    const quitar = botonQuitar(t('selector.filtro.quitar'));
    quitar.addEventListener('click', () => {
      s.borrador.filtros.splice(indice, 1);
      renderFiltros();
      q<HTMLButtonElement>('[data-agregar-filtro]')?.focus();
      cambio();
    });

    const valores = document.createElement('div');
    valores.className = 'fila__valores';
    const tipo = tipoDe(s.campos, filtro.campo);
    const pide = valoresQuePide(filtro.operador);

    if (!filtro.campo || !filtro.operador || pide === 0) {
      valores.hidden = true;
    } else if (pide === null) {
      const lista = document.createElement('textarea');
      lista.className = 'input fila__valor';
      lista.rows = 2;
      lista.value = filtro.valores.join('\n');
      lista.placeholder = t('selector.filtro.lista');
      lista.setAttribute('aria-label', `${t('selector.filtro.valor')} · ${t('selector.filtro.lista')}`);
      lista.addEventListener('input', () => {
        filtro.valores = lista.value.split('\n');
        cambio();
      });
      valores.append(lista);
    } else {
      for (let i = 0; i < pide; i += 1) {
        const etiqueta =
          pide === 2 ? t(i === 0 ? 'selector.filtro.desde' : 'selector.filtro.hasta') : t('selector.filtro.valor');
        const control = controlDeValor(tipo, filtro.valores[i] ?? '', etiqueta);
        const alCambiar = () => {
          filtro.valores[i] = control.value;
          cambio();
        };
        control.addEventListener('input', alCambiar);
        if (control instanceof HTMLSelectElement) control.addEventListener('change', alCambiar);
        valores.append(control);
        if (pide === 2 && i === 0) {
          const y = document.createElement('span');
          y.className = 'fila__y';
          y.textContent = t('selector.filtro.y');
          valores.append(y);
        }
      }
    }

    const nota = document.createElement('p');
    nota.className = 'fila__nota';
    nota.id = `${root.id || 'selector'}-filtro-${indice}-nota`;

    fila.append(campo, operador, quitar, valores, nota);
    return fila;
  }

  /** Rebuild the filter rows, optionally returning focus to one control. */
  function renderFiltros(foco?: string, indice?: number): void {
    const lista = q<HTMLElement>('[data-filtros]');
    if (!lista) return;
    lista.replaceChildren(...s.borrador.filtros.map(filaFiltro));
    q<HTMLElement>('[data-filtros-vacio]')!.hidden = s.borrador.filtros.length > 0;
    if (foco !== undefined && indice !== undefined) {
      lista.querySelector<HTMLElement>(`.fila[data-indice="${indice}"] ${foco}`)?.focus();
    }
  }

  // ---- Editor: order and top n ------------------------------------------------------

  function renderOrden(): void {
    const campo = q<HTMLSelectElement>('[data-orden-campo]');
    if (!campo) return;
    campo.replaceChildren(
      ...[['', t('selector.orden.ninguno')] as [string, string], ...nombresDeCampos().map((n): [string, string] => [n, humanizarCampo(n)])].map(
        ([value, texto]) => {
          const opcion = document.createElement('option');
          opcion.value = value;
          opcion.textContent = texto;
          opcion.selected = value === (s.borrador.orden?.campo ?? '');
          return opcion;
        },
      ),
    );
    root.querySelectorAll<HTMLButtonElement>('[data-orden-dir]').forEach((boton) => {
      const descendente = boton.dataset.ordenDir === 'desc';
      boton.disabled = !s.borrador.orden;
      boton.setAttribute('aria-pressed', String(Boolean(s.borrador.orden) && s.borrador.orden?.descendente === descendente));
    });
  }

  function renderCantidad(): void {
    const input = q<HTMLInputElement>('[data-cantidad]');
    if (!input) return;
    input.value = s.borrador.cantidad ? String(s.borrador.cantidad) : '';
    input.removeAttribute('aria-invalid');
    q<HTMLElement>('[data-cantidad-error]')!.textContent = '';
  }

  // ---- Editor: indicators -----------------------------------------------------------

  function filaIndicador(indicador: IndicadorBorrador, indice: number): HTMLLIElement {
    const fila = document.createElement('li');
    fila.className = 'fila fila--indicador';
    fila.dataset.indice = String(indice);

    const nombre = document.createElement('input');
    nombre.type = 'text';
    nombre.className = 'input fila__nombre';
    nombre.maxLength = 60;
    nombre.value = indicador.nombre;
    nombre.placeholder = t('selector.indicador.nombre');
    nombre.setAttribute('aria-label', t('selector.indicador.nombre'));
    nombre.addEventListener('input', () => {
      // The colon separates the parts of the syntax; a name cannot carry one.
      if (nombre.value.includes(':')) nombre.value = nombre.value.replace(/:/g, '');
      indicador.nombre = nombre.value;
      cambio();
    });

    const funcion = crearSelect(
      t('selector.indicador.funcion'),
      FUNCIONES.map((f): [string, string] => [f, t(`funcion.${f}`)]),
      indicador.funcion,
      'fila__funcion',
    );
    funcion.addEventListener('change', () => {
      indicador.funcion = funcion.value as Funcion;
      if (indicador.campo && !funcionAdmiteCampo(indicador.funcion, tipoDe(s.campos, indicador.campo))) {
        indicador.campo = null;
      }
      renderIndicadores('.fila__funcion', indice);
      cambio();
    });

    const admitidos = nombresDeCampos().filter((n) => funcionAdmiteCampo(indicador.funcion, tipoDe(s.campos, n)));
    const campo = crearSelect(
      t('selector.indicador.campo'),
      [
        ['', indicador.funcion === 'conteo' ? t('selector.indicador.sinCampo') : t('selector.filtro.campo.elige')],
        ...admitidos.map((n): [string, string] => [n, humanizarCampo(n)]),
      ],
      indicador.campo ?? '',
      'fila__campoIndicador',
    );
    campo.addEventListener('change', () => {
      indicador.campo = campo.value || null;
      cambio();
    });

    const quitar = botonQuitar(t('selector.indicador.quitar'));
    quitar.addEventListener('click', () => {
      s.borrador.indicadores.splice(indice, 1);
      renderIndicadores();
      q<HTMLButtonElement>('[data-agregar-indicador]')?.focus();
      cambio();
    });

    const nota = document.createElement('p');
    nota.className = 'fila__nota';
    nota.id = `${root.id || 'selector'}-indicador-${indice}-nota`;

    fila.append(nombre, quitar, funcion, campo, nota);
    return fila;
  }

  function renderIndicadores(foco?: string, indice?: number): void {
    const lista = q<HTMLElement>('[data-indicadores]');
    if (!lista) return;
    lista.replaceChildren(...s.borrador.indicadores.map(filaIndicador));
    q<HTMLElement>('[data-indicadores-vacio]')!.hidden = s.borrador.indicadores.length > 0;
    if (foco !== undefined && indice !== undefined) {
      lista.querySelector<HTMLElement>(`.fila[data-indice="${indice}"] ${foco}`)?.focus();
    }
  }

  function renderTodo(): void {
    renderFechas();
    renderGuardadas();
    renderFiltros();
    renderOrden();
    renderCantidad();
    renderIndicadores();
    pintarMarcas();
    pintarEstado();
  }

  // ---- Editor wiring -----------------------------------------------------------------

  const dialogos = {
    guardarComo: q<HTMLDialogElement>('[data-dialog="guardar-como"]'),
    borrar: q<HTMLDialogElement>('[data-dialog="borrar-seleccion"]'),
    descartar: q<HTMLDialogElement>('[data-dialog="descartar"]'),
  };

  root.querySelectorAll<HTMLElement>('[data-cerrar]').forEach((boton) => {
    boton.addEventListener('click', () => boton.closest('dialog')?.close());
  });

  function mensajeDeError(error: unknown): string {
    if (error instanceof NetworkError) return t('console.upload.error.network');
    if (error instanceof ApiError && error.detail) return error.detail;
    return t('common.errorBody');
  }

  function ocupado(boton: HTMLButtonElement, si: boolean): void {
    boton.dataset.loading = String(si);
    boton.disabled = si;
  }

  /** After a save: reread the shared list, since others may have changed it. */
  async function trasGuardar(guardada: SeleccionGuardada): Promise<void> {
    try {
      s.selecciones = await listarSelecciones();
    } catch {
      s.selecciones = [...s.selecciones.filter((x) => x.id !== guardada.id), guardada];
    }
    s.guardada = s.selecciones.find((x) => x.id === guardada.id) ?? guardada;
    s.borrador = borradorDe(s.guardada);
    s.base = JSON.stringify(s.borrador);
    s.problemas = [];
    s.cantidadInvalida = false;
    renderTodo();
    emitir();
  }

  if (el.editor) {
    q<HTMLButtonElement>('[data-agregar-filtro]')!.addEventListener('click', () => {
      s.borrador.filtros.push({ campo: '', operador: '', valores: [] });
      renderFiltros('.fila__campo', s.borrador.filtros.length - 1);
      cambio();
    });

    q<HTMLButtonElement>('[data-agregar-indicador]')!.addEventListener('click', () => {
      s.borrador.indicadores.push({ nombre: '', funcion: 'conteo', campo: null });
      renderIndicadores('.fila__nombre', s.borrador.indicadores.length - 1);
      cambio();
    });

    q<HTMLSelectElement>('[data-orden-campo]')!.addEventListener('change', (event) => {
      const campo = (event.currentTarget as HTMLSelectElement).value;
      // The first n usually means the largest first, so a new order starts descending.
      s.borrador.orden = campo ? { campo, descendente: s.borrador.orden?.descendente ?? true } : null;
      renderOrden();
      cambio();
    });

    root.querySelectorAll<HTMLButtonElement>('[data-orden-dir]').forEach((boton) => {
      boton.addEventListener('click', () => {
        if (!s.borrador.orden) return;
        s.borrador.orden.descendente = boton.dataset.ordenDir === 'desc';
        renderOrden();
        cambio();
      });
    });

    const cantidad = q<HTMLInputElement>('[data-cantidad]')!;
    cantidad.addEventListener('input', () => {
      const texto = cantidad.value;
      const n = leerCantidad(texto);
      s.cantidadInvalida = texto.trim() !== '' && n === null;
      s.borrador.cantidad = n;
      const error = q<HTMLElement>('[data-cantidad-error]')!;
      error.textContent = s.cantidadInvalida ? t('selector.cantidad.error') : '';
      if (s.cantidadInvalida) {
        cantidad.setAttribute('aria-invalid', 'true');
      } else {
        cantidad.removeAttribute('aria-invalid');
      }
      cambio();
    });

    q<HTMLButtonElement>('[data-descartar]')!.addEventListener('click', () => {
      cargarGuardada(s.guardada?.id ?? null);
    });

    // Save changes over the loaded selection.
    const guardar = q<HTMLButtonElement>('[data-guardar]')!;
    guardar.addEventListener('click', async () => {
      const g = s.guardada;
      if (!g) return;
      const error = q<HTMLElement>('[data-selector-error]')!;
      error.textContent = '';
      ocupado(guardar, true);
      try {
        await trasGuardar(await actualizarSeleccion(g.id, entradaDe(g.nombre)));
      } catch (caught) {
        if (caught instanceof ApiError && caught.status === 404) {
          // Someone else deleted it. What is on screen survives as new work.
          s.selecciones = s.selecciones.filter((x) => x.id !== g.id);
          s.guardada = null;
          s.base = JSON.stringify(seleccionVacia());
          renderGuardadas();
          pintarEstado();
          error.textContent = t('selector.guardar.noExiste');
        } else {
          error.textContent = mensajeDeError(caught);
          if (caught instanceof ApiError && caught.status === 400) void revisar();
        }
      } finally {
        ocupado(guardar, false);
        pintarEstado();
      }
    });

    // Save as a new, shared selection.
    const formGuardar = dialogos.guardarComo!.querySelector<HTMLFormElement>('form')!;
    const nombre = formGuardar.querySelector<HTMLInputElement>('[data-nombre]')!;
    const errorNombre = formGuardar.querySelector<HTMLElement>('[data-nombre-error]')!;

    const fallarNombre = (texto: string) => {
      errorNombre.textContent = texto;
      nombre.setAttribute('aria-invalid', 'true');
      nombre.focus();
    };

    q<HTMLButtonElement>('[data-guardar-como]')!.addEventListener('click', () => {
      formGuardar.reset();
      errorNombre.textContent = '';
      nombre.removeAttribute('aria-invalid');
      void openWhenFree(dialogos.guardarComo!);
    });

    nombre.addEventListener('input', () => {
      errorNombre.textContent = '';
      nombre.removeAttribute('aria-invalid');
    });

    formGuardar.addEventListener('submit', async (event) => {
      event.preventDefault();
      const texto = nombre.value.trim();
      if (!texto) {
        fallarNombre(t('selector.guardar.vacio'));
        return;
      }
      const enviar = formGuardar.querySelector<HTMLButtonElement>('button[type="submit"]')!;
      ocupado(enviar, true);
      try {
        const creada = await crearSeleccion(entradaDe(texto));
        dialogos.guardarComo!.close();
        await trasGuardar(creada);
      } catch (caught) {
        if (caught instanceof ApiError && caught.status === 409) {
          fallarNombre(t('selector.guardar.repetido'));
        } else {
          fallarNombre(mensajeDeError(caught));
          if (caught instanceof ApiError && caught.status === 400) void revisar();
        }
      } finally {
        ocupado(enviar, false);
      }
    });

    // Delete, for the whole team. Cancel is the focused default.
    const formBorrar = dialogos.borrar!.querySelector<HTMLFormElement>('form')!;
    const errorBorrar = formBorrar.querySelector<HTMLElement>('[data-borrar-error]')!;

    q<HTMLButtonElement>('[data-borrar]')!.addEventListener('click', () => {
      if (!s.guardada) return;
      formBorrar.querySelector<HTMLElement>('[data-borrar-titulo]')!.textContent = t('selector.borrar.titulo', {
        nombre: s.guardada.nombre,
      });
      errorBorrar.textContent = '';
      void openWhenFree(dialogos.borrar!);
    });

    formBorrar.addEventListener('submit', async (event) => {
      event.preventDefault();
      const g = s.guardada;
      if (!g) return;
      const enviar = formBorrar.querySelector<HTMLButtonElement>('button[type="submit"]')!;
      ocupado(enviar, true);
      try {
        await eliminarSeleccion(g.id);
      } catch (caught) {
        if (!(caught instanceof ApiError && caught.status === 404)) {
          errorBorrar.textContent = mensajeDeError(caught);
          ocupado(enviar, false);
          return;
        }
      }
      ocupado(enviar, false);
      dialogos.borrar!.close();
      s.selecciones = s.selecciones.filter((x) => x.id !== g.id);
      s.guardada = null;
      // The criteria stay on screen as a new, unsaved selection.
      s.base = JSON.stringify(seleccionVacia());
      s.problemas = [];
      renderGuardadas();
      pintarEstado();
      emitir();
    });
  }

  // Switching selections while editing asks first; keeping the edits is the default.
  let pendiente: number | null = null;
  el.guardada.addEventListener('change', () => {
    const id = el.guardada.value ? Number(el.guardada.value) : null;
    if (el.editor && sucio() && dialogos.descartar) {
      pendiente = id;
      el.guardada.value = s.guardada ? String(s.guardada.id) : '';
      void openWhenFree(dialogos.descartar);
      return;
    }
    cargarGuardada(id);
  });

  dialogos.descartar?.querySelector('form')?.addEventListener('submit', (event) => {
    event.preventDefault();
    dialogos.descartar!.close();
    cargarGuardada(pendiente);
  });

  document.addEventListener('languagechange', () => renderTodo());

  renderTodo();
  emitir();

  return { estado };
}
