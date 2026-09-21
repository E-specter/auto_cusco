# Revisión integral del módulo `mowa_mes` (T-MM-C2)

> **Cerrada el 2026-09-21.** Todo el módulo está commiteado (sin push). Lo que queda fuera del módulo o sin confirmar está en las secciones 4 y 6.

Coordinador: `coordinador_modulo_mowa_mes`. Reporta a `architec`.

## 1. Commits del módulo (sin push)

| Commit | Contenido | Agente |
|---|---|---|
| `7849ef0` | B6a: calendario laboral, supervisión digital, speech versionado y contrato de configuración | dev_backend, coordinador |
| `25eab2f` | F4: pantalla de Configuración | dev_frontend |
| `082308c` | B6b: campaña, archivos de carga, reporte de enviados y conciliación, con E-1 y E-2 | dev_backend, dev_frontend, coordinador |
| `f86308b` | F3: pantalla de Seguimiento, PUT parcial de configuración y pruebas de la revisión B7 | dev_frontend, dev_backend, coordinador |
| `265ffca` | F2 parte A: lógica y cliente de campañas | dev_frontend |
| `ed08875` | F2 parte B: pantalla de Campaña, con el arreglo del 409 que encontró B7 | dev_frontend |
| `e15b075` | B7: cierre de la calidad de extremo a extremo (pruebas postgres de P1, P2 y P8) | dev_backend |
| `df53a6d` | F5: axe de las tres pantallas, tablas apilables, `.pager` e import de `idioma.ts` (Playwright 94/94) | dev_frontend |
| `0a6ba5d` | Código en el 409 de crear campaña (`huella_cambiada` / `limite_excedido`) y regla nueva de error del contrato | dev_backend, dev_frontend |

Commits transversales de los que depende: `774f39d` (cliente y descargas, designer), `7287f2d` (navegación, designer), `a9fe573` (`/cartera` con el selector, axe e `idioma.ts`, designer), `d7e3d71` (base de pruebas separada, architec).

## 2. Trazabilidad de requerimientos

Las pruebas se buscaron por comportamiento, no solo por el identificador citado: varios RF se prueban sin nombrarlos.

| RF | Implementación (backend) | Frontend | Pruebas que lo cubren |
|---|---|---|---|
| RF-MM-01 límite mensual | `mowa_mes_campanas.py` (consumo, 409 sin `confirmar_limite`), configuración | Seguimiento (consumo por mes), Campaña (confirmación) | Núcleo y postgres (`test_el_limite_se_imputa_al_mes_de_la_fecha_de_envio`, `test_limite_mensual_de_un_mes_sin_campanas`); Playwright S y P; mutación del mes de imputación |
| RF-MM-02 cargados y enviados | `mowa_mes_reporte.py`, `conciliacion.py` (E-1: solo estado `enviado`) | Seguimiento (cargados, enviados, no enviados) | `test_mowa_mes_conciliacion.py`, `test_cadena_completa_con_estados_distintos_de_enviado`; mutación de E-1 |
| RF-MM-03 tipo de carga | `Salida`/`TipoCarga` en `mowa_mes_campana.py`; "personalizada" da 400 | Opción visible y deshabilitada | `test_mowa_mes_campana.py` (opciones deshabilitadas), P de Campaña |
| RF-MM-04 descripción | `campana.py` (descripción sugerida) | Editable; sigue a la sugerida hasta que se edita | `descripcion_sugerida` en núcleo, API y Playwright |
| RF-MM-05 salida | `Salida.NUMERO_LARGO` por defecto; las otras dan 400 | Opciones deshabilitadas visibles | `test_mowa_mes_campana.py:468`, 422 por valor inválido en la API |
| RF-MM-06 herramientas | `HerramientasEntrada`; respuesta automática da 400 | Casillas | Núcleo, API y Playwright |
| RF-MM-07 programación | Tres modalidades; `enviar_ahora` con fechas da 400 | Hora de Lima explícita (`horaLimaISO`) | Vitest de `mowa-mes-campana`, P6 |
| RF-MM-08 día gestionable | `calendario/` (feriados por regla y excepciones) | Configuración (calendario) | `test_calendario.py` (Pascua 2024–2027, 2038, 2285), postgres; mutación de Jueves Santo |
| RF-MM-09 base de la campaña | `campana.py` con el recorrido paginado compartido (`recorrido.py`) | Selector compacto de designer | Postgres de paginación con mutación de LIMIT/OFFSET, P9 |
| RF-MM-10 formato `.xlsx` | `archivo_carga.py` (`Hoja1`, `numero` entero, `dni` texto; E-2) | Descarga | Adaptador releyendo el archivo, cadena por HTTP |
| RF-MM-11 50 000 y 2 MB | `division.py` (filas y después bytes reales), límites en la configuración | Configuración (límites, solo hacia abajo) | `test_mowa_mes_division.py`, postgres de división, C1b |
| RF-MM-12 supervisión al inicio | `campana.py` | Muestra con supervisión primero | Postgres (`test_la_muestra_de_la_previsualizacion_trae_la_supervision_primero`), P1; mutación del orden |
| RF-MM-13 exclusiones | `evaluar_producto` (un motivo, orden de §1.3 del plan, `falta_documento` por S-MM-8) | Tabla de exclusiones filtrable | Núcleo y API; mutación del orden |
| RF-MM-14 estructura del mensaje | `speech.py` sobre `GeneradorCargas`, sin tocar el motor | — | `test_mowa_mes_speech.py` |
| RF-MM-15 segmento por días ajustados | `segmentos.py` (S-MM-5, S-MM-6) | Rango "(9–30 días)" | Núcleo, Vitest |
| RF-MM-16 WhatsApp | Enlace `wa.me/+51`; sin número, error y 400 | Configuración y campaña | Núcleo, API (null y "" borran), postgres |
| RF-MM-17 speech versionado | `usada_en`; el original y los usados son inmutables | Editable → PUT, si no → POST `basada_en_id` | Postgres; mutación de las dos condiciones del UPDATE |
| RF-MM-18 speech original | Sembrado con el texto exacto | — | `test_speech_original.py` contra el documento |
| RF-MM-19 150/160 | `codigo_por_largo` | Previsualización del largo y `role=status` | Núcleo (borde 150), Vitest, Playwright |
| RF-MM-20 importar el reporte | `lector_reporte_mowa_mes.py` (8 columnas) | Importación multipart, 413 propio | `test_lector_reporte_mowa_mes.py`, S |
| RF-MM-21 asociar a la campaña | Cada `id` de MES a la campaña elegida; 409 salvo `reemplazar` (C-5) | Diálogo de reemplazo | `reemplazar` en 12 archivos de pruebas del backend, S4 |
| RF-MM-22 conciliación | Multiconjunto con NFD en los dos lados | Seguimiento; "coinciden por id" separado de enviados | Núcleo y postgres; mutaciones de b) y c) |
| RF-37 supervisión en la carga | `gestiones_digitales/supervision.py` | — | Núcleo; postgres de sin supervisores y sin productos (P2) |
| RF-38 supervisores configurables | `api/supervisores.py`, copia por campaña | Configuración y supervisores propios de la campaña | Núcleo, API y postgres (restitución), Playwright |
| RF-39 DNI secuencial | `documentos_asignados` por orden de procedencia | Documento visible | `00000001` en 38 archivos de pruebas del backend; mutación del orden |
| RF-40 campos de la primera fila válida | `filas_supervision` con plantilla | — | Núcleo, P1 |
| RF-41 inclusión y resumen | Primer archivo; cifras separadas | Seguimiento (productos, supervisión y total) | Postgres, S1 |

**Resultado:** los 27 requerimientos (RF-MM-01 a 22 y RF-37 a 41) tienen implementación y pruebas. No hay ninguno sin cubrir.

## 3. Decisiones

- **Del usuario:** E-1 (enviado = estado `enviado`), E-2 (documento no estándar se carga con advertencia), S-MM-7 (el límite se imputa al mes de envío) y S-MM-8 (sin documento se excluye).
- **Tomadas dentro del módulo:** ver `plan.md` (C-1 a C-6, PUT parcial de configuración, 409 con código).
- **De `architec`:** feriados calculados por regla, contrato en dos cortes, regla nueva de error del contrato (todo 4xx con `detail` obligatorio, sin lista de permitidos).
- **Supuestos abiertos:** sección 5.

## 4. Capas que quedaron fuera, con su motivo

| Capa | Estado | Motivo |
|---|---|---|
| Lector de pantalla real (NVDA) | No corrida | No hay lector de pantalla en este entorno. Lo verificado es el árbol de accesibilidad de Chromium y axe (WCAG 2.1 AA) en las tres pantallas, en tema claro y oscuro y en los diálogos con error |
| Zoom al 200 % | Aproximada | Se emula con un viewport de 640 px, no con zoom real del navegador |
| Regresión visual | No existe | El proyecto no la tiene configurada |
| Cobertura | No existe | El proyecto no la tiene configurada |
| Basadas en propiedades | No existe | Sin Hypothesis. Cubierto con casos borde a mano: Pascua (2024–2027, 2038, 2285), largos de 150 y 160, normalización de la conciliación |
| Seguridad (análisis estático) | No existe | El proyecto no lo tiene. Lo que sí hay: tope de 32 MB en la subida del reporte, lectura solo con `python-calamine`, sin SQL escrito a mano y sin datos personales en pruebas ni documentación |
| Rendimiento después de E-1 y E-2 | No repetida | Las dos decisiones agregan comprobaciones O(1) por fila, sin consultas nuevas. La medición con 46 000 filas (`mowa-mes.md` §13) tiene margen frente al volumen documentado. Aceptado por `architec` |
| Mutación HTTP de tres reglas de supervisión | No repetida | Ya tienen mutación en el núcleo; las pruebas nuevas verifican el cableado HTTP y PostgreSQL |

## 5. Supuestos que siguen sin confirmar con el usuario

De la sección 8 de `requerimientos-mowa-mes.md`. S-MM-7 y S-MM-8 se confirmaron el 2026-09-14 y pasaron a decisiones.

| Supuesto | Qué se asumió | Riesgo si el usuario decide otra cosa |
|---|---|---|
| S-MM-1 | Sin integración por API: se generan archivos y el reporte se importa a mano | Cambia el alcance del módulo: haría falta un adaptador de salida hacia MES (RF-14), no rehacer el núcleo |
| S-MM-2 | Superar el límite mensual se advierte y se confirma, no se bloquea | Cambio chico: quitar `confirmar_limite` y dejar el 409 siempre |
| S-MM-3 | La descripción de campaña no tiene largo máximo | Cambio chico: agregar el máximo que confirme MES, con su validación |
| S-MM-4 | Feriados nacionales vigentes al 2026, calculados por regla; decretos y cambios de ley por configuración | Revisar la lista de la regla; las excepciones ya son configurables |
| S-MM-5 | Con `Enviar en diferentes horas`, el segmento se calcula con la fecha más temprana | Cambio chico en `segmentos.py`, con su prueba |
| S-MM-6 | `dias_ajustados = 0` es `Preventiva` | Cambio chico en el rango del segmento, con su prueba |

## 6. Qué falta para marcar el módulo como cerrado

1. **`docs/planning.md`, Fase 3:** pasar el conector MOWA MES de "en progreso" a hecho, con los commits, y dejar anotado que WhatsApp sigue bloqueado por la estructura del proveedor.
2. **`docs/modules.md` §5.1:** pasar el estado de "implementación delegada" a implementado, con las rutas reales (`calendario/`, `gestiones_digitales/`, `plataformas/mowa_mes/`, `api/mowa_mes.py`, `api/mowa_mes_campanas.py`, las tres pantallas) y el documento técnico.
3. **Confirmar S-MM-1 a S-MM-6** con el usuario, o dejarlos anotados como supuestos vigentes.
4. **Nada del módulo está subido:** todos los commits siguen sin `git push`.
5. **Fuera del módulo, ya cerrado:** el enlace "Campaña" entró con la navegación de `designer` (`de45322`), y el puerto propio de Playwright con `13fadf1`.

## 7. Lecciones de proceso registradas

- **Mutaciones solo en worktree o copia**, nunca en el árbol compartido (una lectura cayó en la ventana de una mutación).
- **Un valor desconocido en una base se reporta, no se restituye.** Las pruebas postgres van contra `auto_cusco_test`.
- **Los informes dicen la base** (árbol o worktree desde qué commit) y el desglose de `--list`.
- **No se copian teléfonos ni documentos** a documentación, pruebas ni mensajes, aunque sean de prueba.
