/**
 * Behaviour of the "Generar carga" screen (T-MTE-F5, plan-f5.md). The page is markup; everything that
 * moves is here.
 *
 * It owns nothing about the selection: it subscribes to `seleccioncambiada` before mounting the
 * picker, so no change is lost, and keeps the rest of the request (definition, version, format, amount,
 * options) in a `Borrador` whose rules live in `lib/generar-carga.ts`. The preview and the download take
 * the same body. The backend is the authority: nothing here validates a platform rule or computes a
 * figure; a refusal shows the server's reason and what was typed stays.
 *
 * Two promises worth keeping:
 *   - The last change wins. A newer preview aborts the one in flight, and an answer that is no longer
 *     the latest is dropped.
 *   - Cancel only frees the screen. The server runs a generation to the end, so the notice after a
 *     cancel says what is not known, and a new download cannot start while one is in flight.
 */

import { NetworkError } from '../lib/api';
import { generarCarga, listarFormatos, previsualizarCarga } from '../lib/api-archivos-carga';
import {
  listarDefiniciones,
  obtenerDefinicion,
  type DefinicionGuardadaRespuesta,
  type ResumenDefinicion,
} from '../lib/api-definiciones';
import { guardarArchivo } from '../lib/descargas';
import { formatDate, formatNumber } from '../lib/format';
import {
  CANTIDAD_MAXIMA,
  CANTIDAD_POR_DEFECTO,
  agruparProblemas,
  borradorNuevo,
  cantidadInvalida,
  cantidadSigueLaSeleccion,
  conCantidad,
  conDefinicion,
  conFormato,
  conFormatos,
  conOpcion,
  conSeleccion,
  conVersion,
  filasMaximas,
  mismaPeticion,
  motivoInactivo,
  opcionesDe,
  opcionesParaEnviar,
  peticionDe,
  problemasDeCarga,
  resumenDeCabeceras,
  valorDeOpcion,
  versionEfectiva,
  type Borrador,
  type FormatoArchivo,
  type OpcionFormato,
  type PeticionGeneracion,
  type PrevisualizacionCarga,
} from '../lib/generar-carga';
import {
  avisoDeCancelacion,
  avisoDeErrores,
  avisoDeExclusiones,
  avisoDeExito,
  avisoDeSuficiencia,
  descripcionDeGrupo,
  descripcionDeProblema,
  etiquetaDeFormato,
  etiquetaDeSugerido,
  lineaDeSalida,
  mensajeDeError,
  textoMotivo,
} from '../lib/generar-carga-mensajes';
import { t } from '../lib/i18n';
import { EVENTO_SELECCION, montarSelector, type EstadoSeleccion } from './selector-seleccion';
import { crearSelectorPatronFecha } from './selector-patron-fecha';

/** Long enough that typing an amount does not fire a preview per keystroke. */
const ESPERA_PREVIA = 600;

type EstadoPrevia = 'pendiente' | 'calculando' | 'lista' | 'error';

function q<T extends Element>(selector: string, raiz: ParentNode = document): T {
  return raiz.querySelector<T>(selector)!;
}

function esAborto(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

export async function arrancar(): Promise<void> {
  const el = {
    offline: q<HTMLElement>('[data-offline]'),
    contenido: q<HTMLElement>('[data-contenido]'),
    reintentar: q<HTMLButtonElement>('[data-reintentar]'),
    selector: q<HTMLElement>('[data-selector]'),
    vacio: q<HTMLElement>('[data-vacio]'),
    camposDefinicion: q<HTMLElement>('[data-definicion-campos]'),
    definicion: q<HTMLSelectElement>('[data-definicion]'),
    campoVersion: q<HTMLElement>('[data-campo-version]'),
    version: q<HTMLSelectElement>('[data-version]'),
    definicionError: q<HTMLElement>('[data-definicion-error]'),
    resumen: q<HTMLElement>('[data-definicion-resumen]'),
    resumenColumnas: q<HTMLElement>('[data-resumen-columnas]'),
    resumenSegmentacion: q<HTMLElement>('[data-resumen-segmentacion]'),
    resumenProteger: q<HTMLElement>('[data-resumen-proteger]'),
    formatos: q<HTMLElement>('[data-formatos]'),
    cantidad: q<HTMLInputElement>('[data-cantidad]'),
    cantidadHint: q<HTMLElement>('[data-cantidad-hint]'),
    cantidadError: q<HTMLElement>('[data-cantidad-error]'),
    opcionesGrupo: q<HTMLElement>('[data-opciones-grupo]'),
    opciones: q<HTMLElement>('[data-opciones]'),
    previa: q<HTMLElement>('[data-previa]'),
    calculoTexto: q<HTMLElement>('[data-calculo-texto]'),
    previaPendiente: q<HTMLElement>('[data-previa-pendiente]'),
    previaError: q<HTMLElement>('[data-previa-error]'),
    previaErrorTexto: q<HTMLElement>('[data-previa-error-texto]'),
    previaReintentar: q<HTMLButtonElement>('[data-previa-reintentar]'),
    previaContenido: q<HTMLElement>('[data-previa-contenido]'),
    cifraDisponibles: q<HTMLElement>('[data-cifra-disponibles]'),
    cifraSolicitados: q<HTMLElement>('[data-cifra-solicitados]'),
    cifraMuestra: q<HTMLElement>('[data-cifra-muestra]'),
    avisoSuficiencia: q<HTMLElement>('[data-aviso-suficiencia]'),
    avisoSuficienciaTexto: q<HTMLElement>('[data-aviso-suficiencia-texto]'),
    avisoExclusiones: q<HTMLElement>('[data-aviso-exclusiones]'),
    avisoExclusionesTexto: q<HTMLElement>('[data-aviso-exclusiones-texto]'),
    avisoErrores: q<HTMLElement>('[data-aviso-errores]'),
    avisoErroresTexto: q<HTMLElement>('[data-aviso-errores-texto]'),
    tablaContenedor: q<HTMLElement>('[data-tabla-contenedor]'),
    tablaCaption: q<HTMLElement>('[data-tabla-caption]'),
    tablaCabeza: q<HTMLElement>('[data-tabla-cabeza]'),
    tablaCuerpo: q<HTMLElement>('[data-tabla-cuerpo]'),
    problemas: q<HTMLElement>('[data-problemas]'),
    problemasCuerpo: q<HTMLElement>('[data-problemas-cuerpo]'),
    linea: q<HTMLElement>('[data-linea]'),
    generar: q<HTMLButtonElement>('[data-generar]'),
    cancelar: q<HTMLButtonElement>('[data-cancelar]'),
    exito: q<HTMLElement>('[data-resultado-exito]'),
    exitoTexto: q<HTMLElement>('[data-resultado-exito-texto]'),
    cancelado: q<HTMLElement>('[data-resultado-cancelado]'),
    canceladoTexto: q<HTMLElement>('[data-resultado-cancelado-texto]'),
    error: q<HTMLElement>('[data-resultado-error]'),
    errorTexto: q<HTMLElement>('[data-resultado-error-texto]'),
    iconoAbrir: q<HTMLTemplateElement>('[data-icono-abrir]'),
  };

  // ---- State -----------------------------------------------------------------------------

  let borrador: Borrador = borradorNuevo();
  let definiciones: ResumenDefinicion[] = [];
  /** The chosen definition as the API gave it for the chosen version: name, versions, content. */
  let definicion: DefinicionGuardadaRespuesta | null = null;

  let estadoPrevia: EstadoPrevia = 'pendiente';
  let datosPrevia: PrevisualizacionCarga | null = null;
  let peticionPrevia: PeticionGeneracion | null = null;
  let textoErrorPrevia = '';
  let temporizador: number | undefined;
  let controladorPrevia: AbortController | null = null;

  /** Bumped by every definition load, so a slow answer for a choice already replaced is dropped. */
  let cargaDefinicion = 0;

  let generando = false;
  let controladorGeneracion: AbortController | null = null;

  // ---- Definition ------------------------------------------------------------------------

  function pintarDefiniciones(): void {
    const hay = definiciones.length > 0;
    el.vacio.hidden = hay;
    el.camposDefinicion.hidden = !hay;
    const opciones: HTMLOptionElement[] = [];
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = t('generar.definicion.placeholder');
    opciones.push(placeholder);
    definiciones.forEach((d) => {
      const opcion = document.createElement('option');
      opcion.value = String(d.id);
      opcion.textContent = d.nombre;
      opciones.push(opcion);
    });
    el.definicion.replaceChildren(...opciones);
    el.definicion.value = borrador.definicionId === null ? '' : String(borrador.definicionId);
  }

  function pintarVersiones(): void {
    if (!definicion) {
      el.campoVersion.hidden = true;
      el.version.replaceChildren();
      return;
    }
    const versiones = [...definicion.versiones].sort((a, b) => b.numero - a.numero);
    el.version.replaceChildren(
      ...versiones.map((v) => {
        const opcion = document.createElement('option');
        opcion.value = String(v.numero);
        opcion.textContent =
          v.numero === definicion!.version_vigente
            ? t('generar.definicion.versionVigente', { n: v.numero })
            : t('generar.definicion.versionAnterior', { n: v.numero, fecha: formatDate(v.creado_en.slice(0, 10)) });
        return opcion;
      }),
    );
    el.version.value = String(versionEfectiva(borrador) ?? definicion.version_vigente);
    el.campoVersion.hidden = false;
  }

  function pintarResumenDefinicion(): void {
    if (!definicion) {
      el.resumen.hidden = true;
      return;
    }
    const contenido = definicion.version.contenido;
    el.resumenColumnas.textContent = t('generar.definicion.columnasValor', { n: formatNumber(contenido.columnas.length) });
    el.resumenSegmentacion.textContent = contenido.segmentacion
      ? t(
          contenido.segmentacion.politica === 'excluir'
            ? 'generar.definicion.segmentacion.excluir'
            : 'generar.definicion.segmentacion.defecto',
        )
      : t('generar.definicion.segmentacion.ninguna');
    el.resumenProteger.textContent = t(
      contenido.proteger_formulas ? 'generar.definicion.proteger.si' : 'generar.definicion.proteger.no',
    );
    el.resumen.hidden = false;
  }

  /** Whether the chosen version may leave products out of the file (a segmentation that excludes). */
  const puedeExcluir = (): boolean => definicion?.version.contenido.segmentacion?.politica === 'excluir';

  async function cargarDefinicion(id: number, version?: number): Promise<void> {
    const turno = ++cargaDefinicion;
    el.definicionError.textContent = '';
    try {
      const cargada = await obtenerDefinicion(id, version);
      if (turno !== cargaDefinicion) return;
      definicion = cargada;
      // The latest version may have moved since the list was read.
      borrador = { ...borrador, versionVigente: cargada.version_vigente };
      if (version !== undefined) borrador = conVersion(borrador, version);
      pintarVersiones();
      pintarResumenDefinicion();
    } catch (error) {
      if (turno !== cargaDefinicion) return;
      // Without its content the screen cannot say what the file will hold, so the choice is dropped.
      definicion = null;
      borrador = conDefinicion(borrador, null, null);
      el.definicion.value = '';
      pintarVersiones();
      pintarResumenDefinicion();
      el.definicionError.textContent = `${t('generar.definicion.error')} ${mensajeDeError(error)}`;
    }
    programarPrevia();
  }

  el.definicion.addEventListener('change', () => {
    const id = el.definicion.value === '' ? null : Number(el.definicion.value);
    const resumen = definiciones.find((d) => d.id === id);
    definicion = null;
    borrador = id === null || !resumen ? conDefinicion(borrador, null, null) : conDefinicion(borrador, id, resumen.version_vigente);
    pintarVersiones();
    pintarResumenDefinicion();
    el.definicionError.textContent = '';
    if (id === null) {
      cargaDefinicion += 1;
      programarPrevia();
      return;
    }
    void cargarDefinicion(id);
  });

  el.version.addEventListener('change', () => {
    if (borrador.definicionId === null) return;
    void cargarDefinicion(borrador.definicionId, Number(el.version.value));
  });

  // ---- Format, amount and options ------------------------------------------------------------

  function pintarFormatos(): void {
    el.formatos.replaceChildren(
      ...borrador.formatos.map((f) => {
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.className = 'segmented__item';
        boton.dataset.formato = f.formato;
        boton.setAttribute('aria-pressed', String(f.formato === borrador.formato));
        boton.textContent = etiquetaDeFormato(f.formato as FormatoArchivo);
        boton.addEventListener('click', () => {
          if (borrador.formato === f.formato) return;
          borrador = conFormato(borrador, f.formato as FormatoArchivo);
          pintarFormatos();
          pintarOpciones();
          programarPrevia();
        });
        return boton;
      }),
    );
  }

  function pintarCantidad(escribir: boolean): void {
    if (escribir) el.cantidad.value = borrador.cantidadTexto;
    const sigue = cantidadSigueLaSeleccion(borrador);
    const clave = !sigue
      ? 'generar.cantidad.hint.propia'
      : borrador.consulta.cantidad === null
        ? 'generar.cantidad.hint.sinCantidad'
        : 'generar.cantidad.hint.sigue';
    el.cantidadHint.textContent = t(clave, {
      max: formatNumber(CANTIDAD_MAXIMA),
      n: formatNumber(CANTIDAD_POR_DEFECTO),
    });
    const invalida = cantidadInvalida(borrador);
    el.cantidad.setAttribute('aria-invalid', String(invalida));
    el.cantidadError.textContent = invalida ? t('generar.cantidad.error', { max: formatNumber(CANTIDAD_MAXIMA) }) : '';
  }

  el.cantidad.addEventListener('input', () => {
    borrador = conCantidad(borrador, el.cantidad.value);
    pintarCantidad(false);
    programarPrevia();
  });

  const etiquetaDeOpcion = (opcion: OpcionFormato): string => {
    const clave = `generar.opcion.${opcion.nombre}`;
    return t(clave) === clave ? opcion.nombre : t(clave);
  };

  /** The limits the API announces, in words: a per-option sentence when there is one, else a generic one. */
  function pistaDeOpcion(opcion: OpcionFormato): string {
    const limites = { min: opcion.minimo ?? '', max: opcion.maximo ?? '' };
    const clave = `generar.opcion.${opcion.nombre}.hint`;
    if (t(clave) !== clave) return t(clave, limites);
    if (opcion.minimo !== null && opcion.maximo !== null) return t('generar.rango.entre', limites);
    if (opcion.maximo !== null) return t('generar.rango.hasta', limites);
    if (opcion.minimo !== null) return t('generar.rango.desde', limites);
    return '';
  }

  function alCambiarOpcion(nombre: string, valor: string | boolean): void {
    borrador = conOpcion(borrador, nombre, valor);
    pintarGenerar();
    programarPrevia();
  }

  function controlDeOpcion(opcion: OpcionFormato): HTMLElement {
    const id = `gc-op-${opcion.nombre}`;
    const idPista = `${id}-pista`;
    const envoltura = document.createElement('div');
    envoltura.className = 'field';
    envoltura.dataset.opcion = opcion.nombre;
    const pista = pistaDeOpcion(opcion);
    const elementoPista = document.createElement('p');
    elementoPista.className = 'field__hint';
    elementoPista.id = idPista;
    elementoPista.textContent = pista;

    if (opcion.tipo === 'booleano') {
      const etiqueta = document.createElement('label');
      etiqueta.className = 'gc-check';
      const casilla = document.createElement('input');
      casilla.type = 'checkbox';
      casilla.id = id;
      casilla.checked = valorDeOpcion(borrador, opcion) === true;
      casilla.addEventListener('change', () => alCambiarOpcion(opcion.nombre, casilla.checked));
      const texto = document.createElement('span');
      texto.textContent = etiquetaDeOpcion(opcion);
      etiqueta.append(casilla, texto);
      envoltura.append(etiqueta);
      return envoltura;
    }

    const valorActual = String(valorDeOpcion(borrador, opcion));
    if (opcion.tipo === 'texto' && opcion.sugeridos && opcion.sugeridos.length > 0) {
      const selector = crearSelectorPatronFecha({
        id,
        etiqueta: etiquetaDeOpcion(opcion),
        opciones: opcion.sugeridos.map((valor) => ({
          valor,
          ejemplo: null,
          etiqueta: etiquetaDeSugerido(opcion.nombre, valor),
        })),
        cerradas: false,
        marcas: [],
        valor: valorActual,
        describe: pista ? idPista : undefined,
        onCambio: (valor) => alCambiarOpcion(opcion.nombre, valor),
      });
      const propio = selector.querySelector<HTMLInputElement>(`#${id}-propio`);
      if (propio && opcion.maximo !== null) propio.maxLength = opcion.maximo;
      envoltura.replaceWith(selector);
      selector.dataset.opcion = opcion.nombre;
      if (pista) selector.append(elementoPista);
      return selector;
    }

    const etiqueta = document.createElement('label');
    etiqueta.className = 'field__label';
    etiqueta.htmlFor = id;
    etiqueta.textContent = etiquetaDeOpcion(opcion);
    const campo = document.createElement('input');
    campo.type = 'text';
    campo.className = 'input';
    campo.id = id;
    campo.autocomplete = 'off';
    campo.value = valorActual;
    if (pista) campo.setAttribute('aria-describedby', idPista);
    if (opcion.tipo === 'entero') {
      campo.inputMode = 'numeric';
      campo.classList.add('mono');
    } else if (opcion.maximo !== null) {
      campo.maxLength = opcion.maximo;
    }
    campo.addEventListener('input', () => alCambiarOpcion(opcion.nombre, campo.value));
    envoltura.append(etiqueta, campo);
    if (pista) envoltura.append(elementoPista);
    return envoltura;
  }

  function pintarOpciones(): void {
    const opciones = opcionesDe(borrador.formatos, borrador.formato);
    el.opcionesGrupo.hidden = opciones.length === 0;
    el.opciones.replaceChildren(...opciones.map(controlDeOpcion));
  }

  // ---- Preview ---------------------------------------------------------------------------------

  function celda(valor: unknown): HTMLTableCellElement {
    const td = document.createElement('td');
    if (valor === null || valor === undefined || valor === '') {
      const marca = document.createElement('span');
      marca.className = 'marca-vacio';
      marca.setAttribute('role', 'img');
      marca.setAttribute('aria-label', t('generar.tabla.vacio'));
      td.append(marca);
    } else {
      td.textContent = String(valor);
    }
    return td;
  }

  function pintarTabla(datos: PrevisualizacionCarga): void {
    const hayFilas = datos.cabeceras.length > 0 && datos.filas.length > 0;
    el.tablaContenedor.hidden = !hayFilas;
    el.tablaCaption.textContent = t('generar.tabla.caption', { n: datos.filas.length });
    const cabecera = document.createElement('tr');
    datos.cabeceras.forEach((c) => {
      const th = document.createElement('th');
      th.scope = 'col';
      th.textContent = c;
      cabecera.append(th);
    });
    el.tablaCabeza.replaceChildren(cabecera);
    el.tablaCuerpo.replaceChildren(
      ...datos.filas.map((fila) => {
        const tr = document.createElement('tr');
        datos.cabeceras.forEach((c) => tr.append(celda(fila[c])));
        return tr;
      }),
    );
  }

  let contadorGrupos = 0;

  function celdaDeProblema(etiqueta: string): HTMLTableCellElement {
    const td = document.createElement('td');
    td.dataset.etiqueta = etiqueta;
    return td;
  }

  function pintarProblemas(datos: PrevisualizacionCarga): void {
    const elementos = agruparProblemas(problemasDeCarga(datos));
    el.problemas.hidden = elementos.length === 0;
    const etiquetaDonde = t('generar.problemas.donde');
    const etiquetaQue = t('generar.problemas.que');
    const filas: HTMLElement[] = [];
    for (const elemento of elementos) {
      if (elemento.tipo === 'fila') {
        const { donde, mensaje } = descripcionDeProblema(elemento.problema);
        const tr = document.createElement('tr');
        const a = celdaDeProblema(etiquetaDonde);
        a.textContent = donde;
        const b = celdaDeProblema(etiquetaQue);
        b.textContent = mensaje;
        tr.append(a, b);
        filas.push(tr);
        continue;
      }
      const { donde, mensaje, ver } = descripcionDeGrupo(elemento);
      const idDetalle = `gc-grupo-${(contadorGrupos += 1)}`;
      const cabeza = document.createElement('tr');
      const celdaDonde = celdaDeProblema(etiquetaDonde);
      const lugar = document.createElement('span');
      lugar.className = 'gc-problemas__donde';
      const cuantos = document.createElement('span');
      cuantos.textContent = donde;
      const boton = document.createElement('button');
      boton.type = 'button';
      boton.className = 'btn btn--sm table__abrir';
      boton.setAttribute('aria-expanded', 'false');
      boton.setAttribute('aria-controls', idDetalle);
      const textoBoton = document.createElement('span');
      textoBoton.textContent = ver;
      boton.append(textoBoton, el.iconoAbrir.content.cloneNode(true));
      lugar.append(cuantos, boton);
      celdaDonde.append(lugar);
      const celdaQue = celdaDeProblema(etiquetaQue);
      celdaQue.textContent = mensaje;
      cabeza.append(celdaDonde, celdaQue);

      const detalle = document.createElement('tr');
      detalle.className = 'table__detalle';
      detalle.id = idDetalle;
      detalle.hidden = true;
      const celdaDetalle = document.createElement('td');
      celdaDetalle.colSpan = 2;
      const lista = document.createElement('ul');
      lista.className = 'gc-problemas__lista';
      elemento.problemas.forEach((p) => {
        const { donde: dondeFila, mensaje: mensajeFila } = descripcionDeProblema(p);
        const item = document.createElement('li');
        // The group's row already says what they share; a row repeats it only when it says something else.
        item.textContent = mensajeFila === mensaje ? dondeFila : `${dondeFila}: ${mensajeFila}`;
        lista.append(item);
      });
      celdaDetalle.append(lista);
      detalle.append(celdaDetalle);

      boton.addEventListener('click', () => {
        const abierto = boton.getAttribute('aria-expanded') === 'true';
        boton.setAttribute('aria-expanded', String(!abierto));
        detalle.hidden = abierto;
      });
      filas.push(cabeza, detalle);
    }
    el.problemasCuerpo.replaceChildren(...filas);
  }

  function pintarPrevia(): void {
    const motivo = motivoInactivo(borrador);
    el.previa.dataset.calculando = String(estadoPrevia === 'calculando');
    el.previa.setAttribute('aria-busy', String(estadoPrevia === 'calculando'));
    el.calculoTexto.textContent = estadoPrevia === 'calculando' ? t('generar.previa.calculando') : '';
    q<HTMLElement>('.gc-calculo', el.previa).querySelector('.dot')?.classList.toggle('dot--pulse', estadoPrevia === 'calculando');

    const hayDatos = datosPrevia !== null && (estadoPrevia === 'lista' || estadoPrevia === 'calculando');
    // The reason a request cannot be made is written once, next to the button; here only what is waiting.
    el.previaPendiente.textContent =
      hayDatos || estadoPrevia === 'error'
        ? ''
        : motivo === 'sin_definicion'
          ? t('generar.previa.pendiente')
          : motivo
            ? t('generar.previa.pendiente.otro')
            : t('generar.previa.calculando');
    el.previaError.hidden = estadoPrevia !== 'error';
    el.previaErrorTexto.textContent = estadoPrevia === 'error' ? t('generar.previa.error', { mensaje: textoErrorPrevia }) : '';
    el.previaContenido.hidden = !hayDatos;
    if (!hayDatos || !datosPrevia) return;

    const datos = datosPrevia;
    if (datos.disponibles === 0) {
      el.previaContenido.hidden = true;
      el.previaPendiente.textContent = t('generar.previa.vacia');
      return;
    }
    el.cifraDisponibles.textContent = formatNumber(datos.disponibles);
    el.cifraSolicitados.textContent = formatNumber(datos.solicitados);
    el.cifraMuestra.textContent = formatNumber(datos.generados);

    const insuficiente = !datos.suficiente;
    el.avisoSuficiencia.hidden = !insuficiente;
    el.avisoSuficienciaTexto.textContent = insuficiente
      ? avisoDeSuficiencia({ disponibles: datos.disponibles, solicitados: datos.solicitados })
      : '';
    el.avisoExclusiones.hidden = datos.excluidos === 0;
    el.avisoExclusionesTexto.textContent =
      datos.excluidos > 0 ? avisoDeExclusiones({ excluidos: datos.excluidos, muestra: datos.generados + datos.excluidos }) : '';
    el.avisoErrores.hidden = datos.errores.length === 0;
    el.avisoErroresTexto.textContent = datos.errores.length > 0 ? avisoDeErrores(datos.errores.length) : '';

    pintarTabla(datos);
    pintarProblemas(datos);
  }

  function opcionInvalida(): string | undefined {
    return opcionesParaEnviar(borrador).invalidas[0];
  }

  function cancelarPrevia(): void {
    window.clearTimeout(temporizador);
    controladorPrevia?.abort();
    controladorPrevia = null;
  }

  async function calcularPrevia(peticion: PeticionGeneracion): Promise<void> {
    controladorPrevia?.abort();
    const controlador = new AbortController();
    controladorPrevia = controlador;
    estadoPrevia = 'calculando';
    pintarPrevia();
    try {
      const datos = await previsualizarCarga(peticion, controlador.signal);
      if (controladorPrevia !== controlador) return;
      datosPrevia = datos;
      peticionPrevia = peticion;
      estadoPrevia = 'lista';
    } catch (error) {
      if (esAborto(error) || controladorPrevia !== controlador) return;
      textoErrorPrevia = mensajeDeError(error);
      datosPrevia = null;
      peticionPrevia = null;
      estadoPrevia = 'error';
    }
    controladorPrevia = null;
    pintarPrevia();
    pintarGenerar();
  }

  /** Ask for the preview of the request as it stands, once the user stops changing it. */
  function programarPrevia(): void {
    window.clearTimeout(temporizador);
    const peticion = peticionDe(borrador);
    if (!peticion) {
      cancelarPrevia();
      estadoPrevia = 'pendiente';
      datosPrevia = null;
      peticionPrevia = null;
      pintarPrevia();
      pintarGenerar();
      return;
    }
    if (estadoPrevia === 'lista' && mismaPeticion(peticion, peticionPrevia)) {
      pintarPrevia();
      pintarGenerar();
      return;
    }
    if (datosPrevia) {
      estadoPrevia = 'calculando';
    } else if (estadoPrevia !== 'error') {
      estadoPrevia = 'pendiente';
    }
    pintarPrevia();
    pintarGenerar();
    temporizador = window.setTimeout(() => void calcularPrevia(peticion), ESPERA_PREVIA);
  }

  el.previaReintentar.addEventListener('click', () => {
    const peticion = peticionDe(borrador);
    if (peticion) void calcularPrevia(peticion);
  });

  // ---- Generate ----------------------------------------------------------------------------------

  function pintarGenerar(): void {
    const motivo = motivoInactivo(borrador);
    const peticion = peticionDe(borrador);
    if (motivo || !peticion) {
      el.linea.textContent = textoMotivo(motivo ?? 'sin_definicion', opcionInvalida());
    } else {
      const previaVigente = estadoPrevia === 'lista' && mismaPeticion(peticion, peticionPrevia) ? datosPrevia : null;
      el.linea.textContent = lineaDeSalida({
        filas: filasMaximas(peticion.cantidad, previaVigente?.disponibles ?? null),
        esTope: puedeExcluir() || (previaVigente?.excluidos ?? 0) > 0,
        formato: peticion.formato,
        version: versionEfectiva(borrador),
        nombre: definicion?.nombre ?? definiciones.find((d) => d.id === borrador.definicionId)?.nombre ?? '',
      });
    }
    el.generar.disabled = motivo !== null || generando;
    el.generar.dataset.loading = String(generando);
    q<HTMLElement>('[data-generar-texto]').textContent = t(generando ? 'generar.generando' : 'generar.generar');
    el.cancelar.hidden = !generando;
  }

  function ocultarResultados(): void {
    el.exito.hidden = true;
    el.cancelado.hidden = true;
    el.error.hidden = true;
  }

  /** While a file is being generated the rest of the form is closed; only Cancel is within reach. */
  function bloquearFormulario(bloquear: boolean): void {
    document.querySelectorAll<HTMLElement>('[data-contenido] > section:not(.gc-generar)').forEach((seccion) => {
      seccion.inert = bloquear;
    });
  }

  async function generar(): Promise<void> {
    const peticion = peticionDe(borrador);
    if (!peticion || generando) return;
    const version = versionEfectiva(borrador);
    const nombre = definicion?.nombre ?? '';

    generando = true;
    controladorGeneracion = new AbortController();
    ocultarResultados();
    bloquearFormulario(true);
    // Focus first goes to Cancel: a button that turns disabled drops the focus it held.
    el.cancelar.hidden = false;
    el.cancelar.focus();
    pintarGenerar();

    try {
      const descargado = await generarCarga(peticion, controladorGeneracion.signal);
      const archivo = descargado.nombre ?? `carga.${peticion.formato}`;
      guardarArchivo(descargado.blob, archivo);
      const lineas = avisoDeExito({ archivo, resumen: resumenDeCabeceras(descargado.resumen), version, nombre });
      el.exitoTexto.replaceChildren(
        ...lineas.map((linea) => {
          const p = document.createElement('p');
          p.textContent = linea;
          return p;
        }),
      );
      el.exito.hidden = false;
    } catch (error) {
      if (esAborto(error)) {
        el.canceladoTexto.textContent = avisoDeCancelacion(version);
        el.cancelado.hidden = false;
      } else {
        el.errorTexto.textContent = mensajeDeError(error);
        el.error.hidden = false;
      }
    } finally {
      generando = false;
      controladorGeneracion = null;
      bloquearFormulario(false);
      pintarGenerar();
      el.generar.focus();
    }
  }

  el.generar.addEventListener('click', () => void generar());
  el.cancelar.addEventListener('click', () => controladorGeneracion?.abort());

  // ---- Selection and start-up ----------------------------------------------------------------

  // Subscribed before mounting, so the first emission is never missed.
  el.selector.addEventListener(EVENTO_SELECCION, (event) => {
    const seleccion = (event as CustomEvent<EstadoSeleccion>).detail;
    // `conSeleccion` leaves an edited amount as written, so rewriting the field is always right.
    borrador = conSeleccion(borrador, seleccion);
    pintarCantidad(true);
    programarPrevia();
  });

  function ponerOffline(offline: boolean): void {
    el.offline.hidden = !offline;
    el.contenido.hidden = offline;
    document.dispatchEvent(new CustomEvent('healthchanged'));
  }

  let montado = false;

  async function cargar(): Promise<void> {
    try {
      const [formatos, lista] = await Promise.all([listarFormatos(), listarDefiniciones()]);
      definiciones = lista;
      if (!montado) {
        borrador = conFormatos(borrador, formatos);
        const preferido = formatos.find((f) => f.formato === borrador.formato) ?? formatos[0];
        if (preferido) borrador = conFormato(borrador, preferido.formato as FormatoArchivo);
        pintarDefiniciones();
        pintarFormatos();
        pintarOpciones();
        pintarCantidad(true);
        pintarPrevia();
        pintarGenerar();
        await montarSelector(el.selector);
        montado = true;
      } else {
        pintarDefiniciones();
      }
      ponerOffline(false);
    } catch (error) {
      if (!(error instanceof NetworkError)) console.error(error);
      ponerOffline(true);
    }
  }

  el.reintentar.addEventListener('click', async () => {
    el.reintentar.dataset.loading = 'true';
    await cargar();
    delete el.reintentar.dataset.loading;
  });

  await cargar();
}
