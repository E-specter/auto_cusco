# Revisión de cierre de la fase C3 del motor (T-MTE-C3)

Cerrada el 2026-10-24, sobre `main` en `19adb4c`. Las decisiones del usuario del 2026-10-19 (`b12d384`, `204b3dc`) y del 2026-10-20 (los espacios en GSM-7) están implementadas. **RF-55, RF-56 y M3: cumplidos. Parte del motor de RF-MM-27: cumplida.** Subido hasta `5ce9834`, con el CI en verde; `8894874` y `19adb4c` todavía sin push.

## 1. Trazabilidad

| Requerimiento | Qué pide | Dónde quedó | Pruebas principales | Estado |
|---|---|---|---|---|
| RF-55 | Días de atraso ajustados a la fecha de envío en todas las cargas; por defecto, hoy; rechazo si es anterior al corte; la previsualización dice qué fecha usa; `fecha_envio` y `dias_atraso_ajustados` como variables | B13 (`5ce9834`): `services/fecha_envio.py` («hoy» en Lima con reloj inyectable), `fecha_envio` en `/archivos-carga`, su previsualización y la muestra de cartera de `/texto-enriquecido/previsualizacion`, 400 `fecha_envio_anterior` con las dos fechas antes de leer la cartera. F6 (`19adb4c`): «Fecha de envío» en `/generar-carga` y la fecha visible en `/generar-carga` y `/columnas` | `test_fecha_envio`, `test_api_fecha_envio`, el `@postgres` del 400 con corte futuro, `generar-carga.spec`, `columnas.spec` | Cumplido. La campaña de MOWA MES conserva su regla (RF-MM-15), y su previsualización usa la misma fórmula (prueba de paridad) |
| RF-50 (ampliado) | El segmento calculado usa los días ajustados; la tabla por defecto es la de MOWA MES | B13: las definiciones nuevas resuelven `variable_dias = "dias_atraso_ajustados"`. La tabla por defecto ya era la de MOWA MES y no necesitó código | `test_definiciones_columnas_servicio` (una versión vieja no se reinterpreta) | Cumplido, según D-C3-1 = (a). F6 avisa en `/columnas` si una versión segmenta sin ajuste |
| RF-56 | Renombrar una definición sin crear versión | B14 (`3cdb54f`): `PATCH /definiciones-columnas/{id}` con 409 `nombre_repetido` y `PATCH` en CORS. F7 (`eb97a55`): diálogo «Renombrar» en `/columnas` | `test_api_definiciones_columnas`, `test_definiciones_columnas_postgres`, `columnas.spec` (15 escenarios) | Cumplido. architec lo probó contra el backend real |
| RF-MM-17 (M3) | No se crean ni editan versiones de dos partes (v1); las existentes se siguen leyendo, usando y convirtiendo | B15 (`32bfebf`): 400 `version_v1_retirada`. F8 (`3fe79af`): las v1 en solo lectura con «Convertir a v2». Commits seguidos, sin nada en medio | `test_api_mowa_mes_speech_v2`, `test_mowa_mes_campana` (una v1 heredada), `mowa-mes-configuracion.spec` | Cumplido |
| RF-MM-27 (parte del motor) | Mensaje en GSM-7: diacríticos, transliteración y borrado; el largo medido sobre lo normalizado | B16 (`535a61b`): `texto_enriquecido/gsm7.py` (`a_gsm7`, `largo_gsm7`, `largo_gsm7_normalizado`, `caracteres_borrados`), `compilar(..., medida=...)` y la función «Adaptar a SMS (GSM-7)» en el catálogo. Los espacios Unicode y la tabulación pasan a espacio (decisión del usuario, 2026-10-20). Lo aplica T-MM-B9 de MOWA MES (`8894874`) | `test_texto_enriquecido_gsm7` (65 pruebas y propiedades), `test_texto_enriquecido_gsm7_grafemas`, el oro de B5 con `MATRIZ_HUELLA_GSM7` | Cumplido por el motor. Faltan de MOWA MES `b9b` (el editor mide en GSM-7, con las líneas del motor ya revisadas) y T-MM-F7 |
| RF-54 (ampliado) | El `mensaje` de MOWA MES normalizado es un cambio decidido | B16 agregó al oro los esperados normalizados sin tocar las constantes de `3e567d7`. T-MM-B9 cambió los esperados | `test_mowa_mes_speech_oro` | Cumplido |

## 2. Hallazgos

1. **Textos que prometían algo que todavía no pasaba.** El aviso del segmento con días ajustados y la ayuda de GSM-7 iban en F8, antes de que B13 y T-MM-B9 los volvieran ciertos. Se movieron a F6 y a T-MM-F7. **Regla:** un texto entra en el mismo corte que vuelve cierto lo que dice.
2. **La cota de `a_gsm7` no era un tope verdadero.** La primera versión suponía 1 carácter por carácter, y «…» pasa a 3. Lo encontró la §13 de MOWA MES. Quedó en 3 por entrada. El supuesto de «1 por carácter» es de MOWA MES y vive en su `medida`.
3. **Un valor por defecto que depende del reloj rompió pruebas con fechas fijas.** La primera entrega de B13 hizo fallar 13 `@postgres`, que ingestan cortes de 2099 y pedían la carga sin `fecha_envio`. Se corrigió, y el dev corrió todo el backend con «hoy» movido a tres fechas para comprobar que ninguna prueba depende del día.
4. **El CI en Linux.** Las huellas del XLSX de B10 se habían calculado en Windows (`a154df6`). Desde entonces, los valores congelados tienen que dar lo mismo en Linux, y architec corre el backend en WSL antes de commitear.
5. **Revisar solo lo congelado.** Dos veces se revisó un worktree mientras el dev lo cambiaba: B16 en la primera pasada de MOWA MES, y el orden del valor por defecto en `b9b`. Desde entonces, cada entrega se congela hasta que se revisa.
6. **`tasks.md`.** El commit de F8 no dejó B15 y F8 en «hecho», como decía su mensaje. Se corrige con este cierre.
7. **Decisión del usuario del 2026-10-20** (en la sesión del coordinador): los espacios especiales y la tabulación pasan a un espacio normal en GSM-7. Está registrada en RF-MM-27 y en §24 del diseño. architec la anotó como tomada en esta sesión.

## 3. Límites conocidos y pendientes

- **Supuesto S-MM-9:** los extendidos de GSM-7 cuentan 2. Falta confirmar con MES cómo los cobra.
- **`grafemas_borrados`** agrupa emoji según UAX #29, pero no las sílabas de hangul ni la virama índica (está documentado).
- **La cota de `a_gsm7` (3×)** es conservadora a propósito. El control exacto es por fila.
- **Las regex de fecha de F6** en Linux las confirma el CI en el próximo push.
- **De MOWA MES quedan `b9b` y T-MM-F7**, a cargo de `coordinador_modulo_mowa_mes`.
- **Push:** subido hasta `5ce9834` (B13), con el CI en verde; lo posterior, sin subir. Lo decide el usuario.

## 4. Lecciones del proceso

- Las revisiones cruzadas encontraron lo que las pruebas no cubrían: la cota (MOWA MES), los textos adelantados (MOWA MES y el coordinador) y las `@postgres` (architec).
- Entregar un corte que depende de otro como «índice = la dependencia, árbol = lo propio» (F8 sobre B15, F6 sobre B13) dejó revisar solo el diff propio y rebasar sin rehacer.
- Cuando un parámetro nuevo tiene un valor por defecto que sale del reloj, hay que buscar las fechas fijas en todas las pruebas y correrlas con el reloj movido antes de entregar.

## 5. Commits de C3

`b12d384` y `204b3dc` (decisiones), `3cdb54f` (B14), `3f6e8c1` (experiencia de C3), `a154df6` (CI), `f32d47b` (designer), `eb97a55` (F7), `535a61b` (B16), `32bfebf` (B15), `3fe79af` (F8), `837df75` y `90ecc80` (designer), `5ce9834` (B13) y `19adb4c` (F6). De MOWA MES, sobre el motor: `8894874` (T-MM-B9).
