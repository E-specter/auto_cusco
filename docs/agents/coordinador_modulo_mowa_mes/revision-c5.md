# Revisión de los extendidos de GSM-7 transliterados en `mowa_mes` (T-MM-C5)

> **Revisada el 2026-10-27.** RF-MM-27, ampliado el 2026-10-26: los caracteres de la tabla extendida de GSM-7 se transliteran y el mensaje queda solo en el alfabeto básico. Cierra el supuesto S-MM-9. T-MTE-B19 (backend del motor) está en `18b8b36`, ya subido. T-MM-F8 (frontend) está revisado y sin commit, rebasado sobre `18b8b36`.

Coordinador: `coordinador_modulo_mowa_mes`. Reporta a `architec`. Requerimiento: `requerimientos-mowa-mes.md` RF-MM-27 (`52fec25`).

## 1. Cortes

| Corte | Dónde | Contenido | Agente | Mi revisión |
|---|---|---|---|---|
| **T-MTE-B19** | `18b8b36` (desde el worktree `auto_cusco_mte_b19`); 22 archivos | `a_gsm7` translitera los extendidos y borra `^`; `CARACTERES_GSM7` queda solo con el alfabeto básico; `largo_gsm7_normalizado` = `len(a_gsm7(…))`; oro, conciliación, contrato (una descripción) y docs | dev_backend_motor_texto_enriquecido, coordinado por `coordinador_motor` | §13, dos pasadas |
| **T-MM-F8** | `auto_cusco_mowa_f8`, rama `mowa-f8-extendidos`, rebasado sobre `18b8b36`; 7 archivos (el contrato ya viene de B19) | API falsa de GSM-7 con la misma tabla; texto `mowaMes.speech.calculoUnidad` (es y en) con visto bueno de `designer`; Vitest y Playwright; el contrato de B19 aplicado con `git apply` | dev_frontend_modulo_mowa_mes | completa, dos pasadas |

F8 se rebasó sobre `18b8b36`: el `openapi.json` y el `contrato-api.d.ts` que traía aplicados coinciden con los de B19 y salen de su diff.

## 2. Trazabilidad

| RF-MM-27, lo nuevo | Implementación | Pruebas |
|---|---|---|
| `€`→`EUR`, `[ {`→`(`, `] }`→`)`, `\ \|`→`/`, `~`→`-`, `\f`→espacio | Entradas nuevas en `TRANSLITERACION` (una sola regla por carácter, la misma que usan `a_gsm7`, `caracteres_borrados` y `grafemas_borrados`). En el frontend, `REEMPLAZOS` y el espacio especial | Un caso por signo; cada equivalente cae en el alfabeto básico (`test_texto_enriquecido_gsm7.py:56`); la salida siempre está dentro del básico (`:353`); idempotencia y aplicación por pieza con los extendidos en `ALFABETO_RICO`. Vitest: «[€5]»→«(EUR5)», `\f`→espacio, nada extendido sobrevive |
| `^` se borra y se avisa | Fuera de la tabla y fuera del básico: lo borra la regla general | `caracteres_borrados` y `grafemas_borrados` lo listan (`:133-135`); Playwright: la línea «Al enviar se borran» de v1 y v2 lo muestra |
| El mensaje queda en el alfabeto básico y mide su largo | `CARACTERES_GSM7 = frozenset(_BASICO)`; `largo_gsm7` sigue contando 2 por extendido, como el estándar, y para lo normalizado da `len` | Bordes de 150 y 160 con `€` (127, 128, 137 y 138 «y» + `€`); cota de una v2 con `…` y `€`; cota 3× con `€`×8 = 24; Playwright: escenario `v1ConExtendidos` con largo 39 y sin línea de borrados |
| Ayuda del largo | `calculoUnidad` ya no dice que los extendidos ocupan 2: «…» ocupa 3, como «...», y «€» también, como «EUR». El hint `gsm7` no cambia (sigue siendo cierto) | Constantes del texto en `mowa-mes-gsm7.spec.ts`; mutaciones M5 y M6 |
| Conciliación (sin cambio de código) | `normalizar_mensaje` sigue con NFD y `strip`, sin `a_gsm7` | Una campaña anterior a B19 con `€ [ya] {x} a\|b ~ \ ^` concilia contra el mismo texto crudo; la clave no translitera; una anterior y una nueva concilian cada una contra su texto |

## 3. Constantes y literales que cambian a propósito

- `MATRIZ_HUELLA_GSM7`: de `550b0d25…` a `82c6aaa9…`. `MATRIZ_FILAS_QUE_CAMBIAN_A_GSM7`: de 1 376 a 2 104. Son 832 filas de tres versiones sintéticas con `[` y `]` (`corchetes_sueltos`, `otra_escritura_de_whatsapp` y `un_texto_distinto_por_segmento`). Está demostrado: con el `a_gsm7` anterior la matriz vuelve a dar la huella vieja. No cambian la matriz cruda, la huella del Speech original, las 384 filas de espacios ni la cota de «9 a 30» (156).
- `[whatsapp]` normalizado mide 10, `(whatsapp)` (antes 12). El marcador de las v1 se reemplaza por el enlace antes de compilar, así que `a_gsm7` no lo toca. Un `[@…` suelto sale `(@…`.
- `test_mowa_mes_conciliacion.py`: «paga €10» pasa a «paga EUR10».
- `test_los_extendidos_se_conservan_en_el_mensaje` se invierte y pasa a `…_se_transliteran_…`.
- Las tres `@postgres` que comparan mensajes armados (`test_mowa_mes_campanas_postgres.py`, `test_mowa_mes_speech_v2_postgres.py` y `test_mowa_mes_conciliacion_v2_postgres.py`) se leyeron una por una y no aplican: no tienen extendidos.

## 4. Decisiones

- **Del usuario (2026-10-26):** transliterar los extendidos con la tabla fija y borrar `^`. Cierra S-MM-9 sin esperar a MES.
- **Del coordinador, acordadas con `coordinador_motor`:**
  - la conciliación no cambia ni usa `a_gsm7`, para que las campañas anteriores sigan conciliando;
  - `largo_gsm7` conserva la cuenta del estándar;
  - se acepta `largo_gsm7_normalizado = len(a_gsm7(…))`, porque la invariante «la salida está en el básico» tiene su prueba.
- **Con `designer`:** el texto de `calculoUnidad`, con el ejemplo de en qué se convierte cada signo. `designer` corrige su §10.2 por su cuenta.
- **Incógnita que solo resuelve MES** (`mowa-mes.md` §17.2): si en las campañas anteriores MES devolvió el `€` cambiado por otro carácter, esas filas no concilian. Con el `€` crudo, sí.

## 5. Verificación

- **B19** (según `coordinador_motor`): ruff limpio; pytest 2 758 pasan y 145 omitidas; 23/23 mutaciones; WSL 244 en las pruebas de gsm7, speech y conciliación.
- **F8** (dev_frontend, `PLAYWRIGHT_PUERTO=4381`). Corrió la cadena de `npm run verificar` por pasos, porque la máquina tenía poca memoria (de 2,9 a 4,1 GB libres):
  - contrato OK, `astro check` 0 errores, tipos y build OK;
  - Vitest 875 pruebas;
  - Playwright completo con `--workers=2`: 443/443, antes del arreglo de `\v`. Después del arreglo: Vitest completo y `mowa-mes-gsm7.spec.ts` 16/16.
- **Mutaciones de F8** (en una copia desechable, de una en una), 8 de 8 detectadas por el motivo correcto:
  - `[` conservado;
  - `€`→`E`;
  - `^` sin listar;
  - `\f` borrado;
  - el texto viejo de `calculoUnidad` en es y en (solo lo ve Playwright);
  - el largo sobre el texto sin normalizar (solo lo ve Playwright);
  - `\v` de vuelta como espacio.
- **Queda para `architec`:** sobre F8, contrato, `astro check`, tipos, Vitest, `build:produccion` y Playwright completo. Lo que corrió para B19 (`-ConBase`, Linux y la medición de la campaña de 46 000 filas) está en su commit.

## 6. Lo que encontró la revisión antes del commit

- **B19:** la justificación escrita de por qué `largo_gsm7` sigue contando 2 era falsa: decía que medía mensajes guardados antes de B19. Ningún código mide un mensaje guardado: `largo_gsm7` solo se usa sobre mensajes recién armados (`campana.py:216` y la previsualización de la campaña). El error venía de mi pedido. Se corrigieron cuatro lugares; no cambió código.
- **F8, heredado de F7:** la API falsa cambiaba la tabulación vertical (U+000B, categoría `Cc`) por un espacio. El backend la borra y la lista. Se corrigió con una prueba nueva y una mutación. Se me había pasado en C4.
- **F8:** una línea de comentario de 129 caracteres.
