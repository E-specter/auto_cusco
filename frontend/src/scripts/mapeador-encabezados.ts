/**
 * Behaviour of the header mapper (docs/mapeador-encabezados-interfaz.md §2 and
 * §3). The markup is `components/MapeadorEncabezados.astro`. The page renders
 * it, listens for `mapeocambiado` on the root and then calls `montarMapeador`.
 *
 * The backend decides; this shows. Choices live in `lib/mapeador.ts`; every
 * change is validated through `validar` (300 ms after the last one, cancelling
 * the request before). Rows are built once per analysis and then updated in
 * place, so a select never loses the focus while the analyst works.
 */

import { etiquetaCampo } from '../lib/campos';
import { formatNumber } from '../lib/format';
import { t } from '../lib/i18n';
import {
  aceptar,
  aceptarTodas,
  asignacionesIniciales,
  elegir,
  etiquetaColumna,
  insignia,
  modificado,
  pendiente,
  porRevisar,
  usos,
  type Analisis,
  type Asignacion,
  type Insignia,
  type Problema,
} from '../lib/mapeador';
import type { components } from '../lib/contrato-api';

type CampoDestino = components['schemas']['CampoDestinoRespuesta'];

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
  destruir(): void;
}

const TONO: Record<Insignia, string> = {
  recordado: 'info',
  coincide: 'vigente',
  por_revisar: 'advertencia',
  aceptado: 'vigente',
  sin_coincidencia: 'neutral',
  manual: 'neutral',
};

/** The visible name of a field: its catalogue key, or the portfolio label as a fallback. */
function etiquetaDe(campo: CampoDestino): string {
  const texto = t(campo.clave_etiqueta);
  return texto === campo.clave_etiqueta ? etiquetaCampo(campo.nombre) : texto;
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
    filas: q<HTMLElement>('[data-filas]'),
    advertencias: q<HTMLElement>('[data-advertencias]'),
    advertenciasTitulo: q<HTMLElement>('[data-advertencias-titulo]'),
    advertenciasLista: q<HTMLElement>('[data-advertencias-lista]'),
  };
  const campos = opciones.campos;
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

  /** Options in order: «No cargar», required fields, then the rest by label (§3.5). */
  function crearSelect(indice: number, encabezado: string): HTMLSelectElement {
    const select = document.createElement('select');
    select.className = 'input';
    select.id = `${id}-campo-${indice}`;
    select.dataset.campo = String(indice);
    select.setAttribute(
      'aria-label',
      t('mapeador.vista.campoPara', { columna: columnaLetra(indice), encabezado }),
    );
    const ninguno = document.createElement('option');
    ninguno.value = NO_CARGAR;
    ninguno.textContent = t('mapeador.vista.noCargar');
    select.append(ninguno);
    for (const [clave, obligatorio] of [
      ['mapeador.vista.obligatorios', true],
      ['mapeador.vista.otros', false],
    ] as const) {
      const grupo = document.createElement('optgroup');
      grupo.label = t(clave);
      const delGrupo = campos
        .filter((c) => c.obligatorio === obligatorio)
        .sort((a, b) => etiquetaDe(a).localeCompare(etiquetaDe(b)));
      for (const campo of delGrupo) {
        const opcion = document.createElement('option');
        opcion.value = campo.nombre;
        grupo.append(opcion);
      }
      if (delGrupo.length > 0) select.append(grupo);
    }
    select.addEventListener('change', () => {
      cambio(elegir(s.asignaciones, s.analisis, indice, select.value === NO_CARGAR ? null : select.value));
    });
    return select;
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
    const select = crearSelect(columna.indice, columna.encabezado);
    const botonAceptar = document.createElement('button');
    botonAceptar.type = 'button';
    botonAceptar.className = 'btn btn--sm';
    botonAceptar.dataset.aceptar = String(columna.indice);
    botonAceptar.textContent = t('mapeador.vista.aceptar');
    botonAceptar.addEventListener('click', () => {
      cambio(aceptar(s.asignaciones, s.analisis, columna.indice));
      select.focus();
    });
    control.append(select, botonAceptar);
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

  /** Each row in place: tag, note, select options (in use, disabled), «Aceptar» and its problem. */
  function pintarFilas(): void {
    const enUso = usos(s.asignaciones);
    for (const columna of s.analisis.columnas) {
      const fila = el.filas.querySelector<HTMLTableRowElement>(`[data-fila="${columna.indice}"]`)!;
      const asignacion = asignacionDe(columna.indice);
      const tipo = insignia(columna, asignacion);

      const tag = fila.querySelector<HTMLElement>('[data-insignia]')!;
      tag.className = `tag tag--${TONO[tipo]}`;
      tag.textContent = t(`mapeador.vista.insignia.${tipo}`);
      const nota = fila.querySelector<HTMLElement>('[data-nota]')!;
      nota.textContent =
        tipo === 'recordado'
          ? t('mapeador.vista.nota.recordado')
          : tipo === 'por_revisar' && columna.sugerido
            ? t('mapeador.vista.nota.parecido', { campo: etiquetaDeNombre(columna.sugerido) })
            : '';

      const select = fila.querySelector<HTMLSelectElement>('[data-campo]')!;
      for (const opcion of select.querySelectorAll('option')) {
        if (opcion.value === NO_CARGAR) continue;
        const otras = (enUso.get(opcion.value) ?? []).filter((i) => i !== columna.indice);
        const etiqueta = etiquetaDeNombre(opcion.value);
        opcion.textContent = otras.length
          ? t('mapeador.vista.enUso', { campo: etiqueta, columnas: otras.map(columnaLetra).join(' y ') })
          : etiqueta;
        // A field another column uses is disabled, except in the rows that hold it (decision of 2026-10-27).
        opcion.disabled = otras.length > 0 && asignacion.campo !== opcion.value;
      }
      select.value = asignacion.campo ?? NO_CARGAR;

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
        select.setAttribute('aria-invalid', 'true');
        select.setAttribute('aria-describedby', error.id);
      } else {
        select.removeAttribute('aria-invalid');
        select.removeAttribute('aria-describedby');
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
            if (libre) el.filas.querySelector<HTMLSelectElement>(`[data-campo="${libre.indice}"]`)?.focus();
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
  }

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
    destruir() {
      s.destruido = true;
      document.removeEventListener('languagechange', alCambiarIdioma);
      clearTimeout(temporizador);
      controlador?.abort();
    },
  };
}
