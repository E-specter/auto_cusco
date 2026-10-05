# Motor de texto enriquecido y constructor de columnas dinámicas

Diseño técnico de una capacidad transversal: componer textos a partir de datos de la cartera, variables derivadas y funciones, y armar con ellos las columnas de cualquier carga. El primer consumidor es el speech por segmento de MOWA MES; después, cualquier módulo que genere cargas (SMS, WhatsApp, correo, VoIP).

```
Datos → Variables → Funciones → Motor de texto → Columnas → Segmentación → Tabla → Exportación / canal
```

Requerimientos: RF-42 a RF-54 en [atomics-requirements.md](atomics-requirements.md), sección 11. Pedido del usuario del 2026-09-29; decisiones del usuario en la sección 13.

---

## 1. Estado actual del proyecto (verificado en el código el 2026-09-29)

| Pieza que ya existe | Dónde | Qué hace hoy |
|---|---|---|
| Motor de mapeo (RF-12) | `app/core/entities/mapeo.py`, `app/core/services/mapeo_campos/` (`plantillas.py`, `formatos.py`, `generador.py`) | Plantillas de texto con referencias `[@campo]`, validadas al compilar contra el catálogo de campos. Tipado por columna (`texto`, `numero`, `fecha` con `strftime`, `financiero` con separadores). `GeneradorCargas` compila una definición una vez y genera filas; un error de campo no detiene la carga (`ErrorGeneracion`). Un campo vacío queda vacío |
| Definición de columnas | `DefinicionCarga` y `CampoSalida` en `mapeo.py` | Nombre, plantilla, tipo, formato. **No se guardan:** viajan en cada pedido a `/archivos-carga` |
| Generación genérica | `app/core/services/generacion_cargas/servicio.py`, `app/api/archivos_carga.py` | Selección de cartera → definición → tabla → archivo |
| Exportadores | `app/adapters/output/exportadores/` (`comunes.py`, CSV, JSON, XLSX) detrás de `ExportadorTablaPort` | Formato independiente de la definición (RF-13). **No hay protección contra la inyección de fórmulas** |
| Catálogo de campos | `seleccion_cartera/campos.py`, `/cartera/campos` | Campos de la cartera con su tipo. `dias_atraso` ("días atraso hoy") y `segmento_financiero` existen |
| Speech de MOWA MES | `plataformas/mowa_mes/speech.py`, `segmentos.py`, entidades en `entities/mowa_mes.py` | Ver sección 2 |
| Versionado con inmutabilidad | Speech de MOWA MES (`usada_en`), selecciones guardadas | Patrón probado: una versión usada no se edita, se crea otra |
| Regla de errores del contrato | `docs/contrato-api.md` §3 | Todo 4xx trae `detail`; un endpoint puede extenderlo (`codigo`, `campo`) |

## 2. Análisis de MOWA MES (speech por segmento)

**Cómo funciona hoy:**

- Cada versión de speech guarda, por segmento, `parte_1` y `parte_2`, en `mowa_mes_speech_version.partes` (JSON).
- `plantilla_mensaje` arma para cada segmento la plantilla fija `[@titular_8]` + `parte_1` + `[@vencimiento]` + `parte_2`, y antes de compilar reemplaza el texto `[whatsapp]` por `https://wa.me/+51` + número.
- `contexto_fila` deriva los valores: titular recortado a 8, vencimiento con `%d/%m/%Y` y enlace.
- `ConstructorMensajes` compila un `GeneradorCargas` por segmento. Los que usan WhatsApp sin número quedan sin compilar (`FaltaWhatsapp`).
- `previsualizar` calcula el largo máximo por segmento con aritmética fija: 8 + 10 + texto + enlace. Con el Speech original, `9 a 30` da 156.
- El segmento sale de `dias_ajustados` (`segmentos.py`) contra `RANGOS_SEGMENTO`, una tabla de datos. No se usa el `segmento_financiero` de la sábana: llega mal cargado (decisión del usuario, RF-MM-15).
- La campaña guarda la **huella** (SHA-256) de las partes y devuelve 409 si cambió entre la previsualización y la creación.
- Las exclusiones `falta_titular` y `falta_vencimiento` se evalúan en `campana.py`, antes de armar el mensaje.

**Qué se reutiliza tal cual:** el pipeline de `GeneradorCargas` (compilar una vez, aplicar muchas), el manejo de errores por fila, los códigos de largo (`codigo_por_largo`), la huella, el versionado con `usada_en` y la semántica de `FaltaWhatsapp`.

**Qué se migra:**

1. La estructura fija de dos partes pasa a una **expresión por segmento** del motor, que puede tener cualquier cantidad de textos, variables y funciones.
2. Las derivaciones de `contexto_fila` pasan a ser funciones del catálogo (`primeros(8)`, `formato_fecha`, `enlace_whatsapp`).
3. La aritmética fija del largo máximo pasa a un **cálculo de cota por expresión** del motor.
4. `RANGOS_SEGMENTO` y el cálculo de días ajustados pasan al núcleo compartido como **segmento calculado** (sección 7), porque no son propios de MOWA.

**Riesgos de regresión:**

| Riesgo | Cómo se controla |
|---|---|
| Un mensaje cambia en un carácter: espacios de las partes, nulos, recorte del titular | Prueba de oro: para los 6 segmentos y un conjunto sintético de productos (titular corto, largo, con tildes, vacío; con y sin WhatsApp), el mensaje por el camino actual y por el motor son **idénticos byte a byte**. El camino actual no se retira hasta que esa prueba pase |
| Cambia el largo máximo mostrado (156 en `9 a 30`) | La misma prueba de oro compara el largo máximo por segmento |
| Cambia la huella de las versiones existentes y una previsualización en curso recibe 409 | Las versiones v1 conservan su huella calculada sobre sus partes; solo las versiones nuevas (v2) usan la huella de la expresión |
| Se pierden las exclusiones `falta_titular` y `falta_vencimiento` | El motor informa qué variables obligatorias faltaron, y MOWA MES las sigue traduciendo a sus códigos. Pruebas de exclusión existentes en verde |
| Rendimiento con 46 000 filas | `scripts/medir_campana_mowa_mes.py` antes y después; umbral en la sección 11 |

## 3. Diseño general

El motor **extiende** `mapeo_campos`; no es un segundo motor. Estructura objetivo en `backend/app/core/`:

```
entities/texto_enriquecido.py        Expresion, Nodo, LlamadaFuncion, TipoValor, Problema, CodigoTexto
services/texto_enriquecido/
    sintaxis.py                     texto <-> expresión (compatible con [@campo])
    funciones/                      catálogo: un módulo por familia, registrado en un índice
    tipos.py                        comprobación de tipos al compilar
    evaluador.py                    compila una vez y evalúa por fila
    cota.py                         largo máximo de una expresión, si se puede acotar
    segmentacion.py                 criterios de segmento: campo o calculado por rangos
services/mapeo_campos/              pasa a usar el motor para evaluar cada columna
```

Principios:

- **El backend es la autoridad.** Valida, evalúa y previsualiza. El frontend arma la expresión y muestra lo que devuelve el backend: no reimplementa funciones.
- **Declarativo y sin `eval`.** Una expresión es un árbol de datos (JSON) con nodos de un conjunto cerrado. Las funciones se buscan por nombre en un registro; nada del usuario se ejecuta como código. Hay límites de tamaño: nodos, funciones encadenadas y largo de los literales.
- **Compilar una vez, aplicar muchas.** Validar tipos y resolver funciones al compilar; por fila, solo aplicar funciones ya resueltas. Por fila no se compilan expresiones regulares ni hay patrones con backtracking; usar una ya compilada y lineal (la del teléfono de RF-02) es válido.
- **Agregar una función sin tocar el núcleo:** un módulo nuevo en `funciones/` que declara sus metadatos y se registra. El evaluador, el comprobador de tipos, el catálogo de la API y la interfaz lo toman del registro.

## 4. Modelo de datos

### 4.1 Expresión

Representación canónica: JSON. La sintaxis de texto existe para compatibilidad y para mostrarla, no como formato principal.

```json
{
  "nodos": [
    {"tipo": "variable", "nombre": "titular", "funciones": [{"nombre": "primeros", "args": [8]}]},
    {"tipo": "texto", "valor": " Caja Cusco te informa que tu cuota venció el "},
    {"tipo": "variable", "nombre": "fecha_vencimiento_cuota",
     "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}]},
    {"tipo": "texto", "valor": ", acércate a pagar."}
  ]
}
```

- **Nodo `texto`:** literal. UTF-8, puede tener saltos de línea. Nunca se interpreta: un `[@` dentro de un literal es texto.
- **Nodo `variable`:** una variable del catálogo (sección 5) y una cadena de funciones que se aplican en orden.
- **Argumentos:** literal (número, texto) o referencia a otra variable (`{"variable": "dias_gracia"}`), para operar entre variables.

**Sintaxis de texto compatible:** `[@campo]` sigue significando lo mismo que en RF-12. Se amplía con tuberías: `[@titular | primeros(8)]`, `[@fecha_vencimiento_cuota | sumar_dias(3) | formato_fecha("dd/mm/aaaa")]`. Toda plantilla válida hoy produce el mismo resultado; una prueba lo exige sobre las plantillas de las pruebas actuales. Ida y vuelta: texto → expresión → texto da lo mismo.

### 4.2 Tipos de valor

`texto`, `numero` (Decimal, nunca float), `fecha`, `booleano`, `nulo`. `booleano` cubre los campos `BOOLEANO` y `*_aplica` del catálogo (ajuste D2 del coordinador, 2026-09-29). Cada variable tiene tipo según el catálogo. Cada función declara qué tipo recibe, qué parámetros admite (con tipo y rango) y qué devuelve. Al compilar se comprueba la cadena entera: `formato_fecha` sobre un texto se rechaza al guardar, no al generar.

Al final de un nodo `variable`, el valor pasa a texto **igual que hoy en `plantillas.aplicar`** (`str(valor)`). No se usa `exportadores/comunes.a_texto`: el núcleo no puede importar de `adapters/`, y `a_texto` cambia resultados actuales (un booleano da `1` en lugar de `True`), lo que rompería RF-54 (ajuste D1). Para controlar el formato, se usan las funciones de formato.

Una columna que es un solo nodo `variable` conserva el tipo del valor final, aunque lleve funciones (una fecha sumada sigue siendo fecha para XLSX), igual que hoy `valor_crudo` sin funciones (precisión D11).

### 4.3 Nulos

- Si una variable llega vacía, la cadena de funciones no se aplica y el nodo produce vacío, igual que hoy en RF-12. **Excepción:** las funciones marcadas como `acepta_nulo`, como `si_vacio("—")`.
- Una columna puede declarar `valor_por_defecto`, que se usa cuando todo su resultado queda vacío.
- Una variable puede marcarse **obligatoria** en una expresión. Si falta, la fila lleva el problema `variable_obligatoria_vacia` con el nombre de la variable. El módulo consumidor decide qué hacer: MOWA MES lo traduce a `falta_titular` o `falta_vencimiento` y excluye; `/archivos-carga` lo reporta como error de fila.

## 5. Variables

Dos fuentes, un mismo catálogo:

1. **Campos de la cartera:** los de `/cartera/campos`, con su tipo.
2. **Variables de contexto:** las aporta el módulo que usa el motor, con nombre, tipo y descripción. Por ejemplo, MOWA MES aporta `whatsapp_contacto` (texto), `fecha_envio` (fecha), `dias_atraso_ajustados` (número) y `segmento_calculado` (texto). El motor no conoce MOWA MES: recibe la lista.

El catálogo de la API devuelve las variables del contexto pedido (`contexto=cartera` o `contexto=mowa_mes.speech`), con sus tipos. Así la interfaz solo ofrece lo que existe.

## 6. Catálogo inicial de funciones

Cada función tiene nombre estable, clave i18n para su nombre y descripción, tipos de entrada y salida, parámetros y, cuando se puede, su efecto sobre el largo máximo.

| Familia | Función | Recibe → devuelve | Parámetros | Notas |
|---|---|---|---|---|
| Texto | `primeros(n)` | texto → texto | n ≥ 1 | Cota: n |
| | `ultimos(n)` | texto → texto | n ≥ 1 | Cota: n |
| | `mayusculas`, `minusculas`, `capitalizar` | texto → texto | — | |
| | `recortar` | texto → texto | — | Quita espacios de los extremos y colapsa los repetidos |
| | `sin_tildes` | texto → texto | — | Normalización NFD, igual que la conciliación de MOWA MES |
| | `reemplazar(a, b)` | texto → texto | textos | Literal, no expresión regular |
| | `rellenar_izquierda(n, c)` | texto → texto | n, un carácter | Por ejemplo, DNI con ceros |
| Número | `sumar(x)`, `restar(x)`, `multiplicar(x)`, `dividir(x)` | número → número | número o variable numérica | División por cero: problema de fila `division_por_cero` |
| | `redondear(d)` | número → número | d de 0 a 6 | A la mitad hacia arriba, igual que los montos de MOWA MES |
| | `formato_numero(d, miles, decimal)` | número → texto | decimales y separadores | Reutiliza `formatos.formatear_importe` |
| | `a_numero` | texto → número | — | Si no es número: problema de fila `no_es_numero` |
| | `a_texto` | número o fecha → texto | — | Representación estable (4.2) |
| Fecha | `sumar_dias(x)`, `restar_dias(x)` | fecha → fecha | entero o variable numérica | |
| | `formato_fecha(patron)` | fecha → texto | Patrón con marcas legibles: `dd`, `mm`, `aaaa`, `aa`, `nombre_mes` | Se traduce a `strftime` en el backend; el usuario no escribe `%`. Cota conocida según el patrón |
| | `a_fecha(patron)` | texto → fecha | patrón | Si no se puede leer: problema de fila `no_es_fecha` |
| Nulos | `si_vacio(x)` | cualquiera → cualquiera | literal o variable | `acepta_nulo` |
| Enlaces | `enlace_whatsapp(prefijo)` | texto (teléfono) → texto | Prefijo configurable; por defecto `https://wa.me/+51` | Valida el teléfono con la regla RF-02 (`numero_valido`). Si no es válido: `telefono_invalido`. Cota: largo del prefijo + 9 |

Queda para después, sin cambiar el núcleo: enlace de WhatsApp con mensaje prellenado (`?text=`, con codificación de URL), condicionales por valor y funciones de mayúscula por palabra con excepciones.

## 7. Segmentación

Una definición puede declarar **variantes por segmento**: para cada valor del criterio, una expresión propia, más una variante por defecto opcional.

**Criterios:**

| Criterio | Cómo se calcula | Uso |
|---|---|---|
| **Segmento financiero calculado** (por defecto) | Días de atraso (`dias_atraso`, "días atraso hoy"), opcionalmente ajustados a la fecha de envío, contra una tabla de rangos con etiquetas | Es el criterio por defecto porque el `segmento_financiero` de la sábana llega mal cargado (decisión del usuario del 2026-09-29) |
| Campo categórico | El valor de un campo de la cartera, tal cual | `segmento_financiero` crudo, `tramo_actual` u otro. Disponible, no por defecto |

- La **tabla de rangos** son datos: etiqueta, desde, hasta. La de hoy (`RANGOS_SEGMENTO` de MOWA MES) pasa al núcleo compartido con el cálculo de días ajustados (`segmentos.dias_ajustados`). En el núcleo, cada rango usa una clave de texto (`RangoDias`), porque el enum `Segmento` es de MOWA MES. MOWA MES arma su `RANGOS_SEGMENTO` desde la tabla del núcleo, con una prueba de que las claves coinciden con su enum; su API no cambia (precisión D3). Por eso la tarea de columnas y segmentación también toca MOWA MES.
- **Sin segmento:** si un producto no cae en ningún rango o valor, la definición elige entre **excluir con motivo** (`sin_segmento`, lo que hace MOWA MES con `sin_speech`) o **usar la variante por defecto**.
- Ningún código del motor nombra `segmento_financiero`: el criterio es un dato de la definición.

## 8. Constructor de columnas dinámicas

Extiende `DefinicionCarga` y `CampoSalida` en su lugar, con campos nuevos y opcionales, para que lo que usa `/archivos-carga` hoy siga igual:

| Campo | Hoy | Nuevo |
|---|---|---|
| `nombre` | cabecera | igual |
| orden | orden de la tupla | igual; en el almacenamiento, un entero explícito |
| `tipo`, `formato_fecha`, `formato_financiero` | sí | igual |
| valor | `plantilla` (texto `[@...]`) | `expresion` (sección 4), o `plantilla` por compatibilidad, que se compila a expresión |
| `valor_por_defecto` | — | opcional |
| `variantes` | — | opcional: por segmento, según la segmentación de la definición |
| `segmentacion` | — | a nivel de definición: criterio, tabla o campo, y política sin segmento |

Una columna con variable directa es una expresión de un solo nodo `variable` sin funciones. Conserva el valor original sin pasarlo por texto, igual que hoy (`valor_crudo`).

**Definiciones guardadas** (decisión del usuario): con nombre único normalizado y versiones. Una versión usada en una carga no se modifica: se crea otra. Son compartidas entre usuarios y módulos, siguiendo el patrón de selecciones guardadas y del speech. **Precisión de B4b:** como la API solo crea versiones nuevas (no hay `PUT`), ninguna versión se modifica nunca y `usada_en` es informativo: dice que la versión ya generó una carga, no habilita ni bloquea nada (sección 22).

## 9. Exportación y seguridad de la salida

La definición no conoce el formato. Los exportadores reciben la tabla ya generada, como hoy.

**Inyección de fórmulas** (decisión del usuario):

- **XLSX:** todo valor de texto se escribe como texto literal, aunque empiece con `=`, `+`, `-` o `@`. No se ejecuta y el contenido no cambia. Los números y las fechas se escriben con su tipo nativo, como hoy. **Es una de las dos excepciones a RF-54** (la otra es el apóstrofo del CSV, abajo): hoy un texto como `=1+1` se escribe como fórmula viva, también en los archivos de MOWA MES; ahora se escribe como texto. El resto del archivo queda idéntico byte a byte, y una prueba lo comprueba (ajustes D6 y D7).
- **CSV:** por defecto, un texto que empieza con `=`, `+`, `-`, `@`, tabulación o retorno de carro lleva un apóstrofo delante. **No se protegen los valores que no son texto ni los textos que son solo un número** (`^[+-]?\d[\d.,]*$`): un importe negativo (`-1,234.56`) o `+51987654321` no son fórmulas, y el apóstrofo rompería la plataforma. Un texto como `-2+3` sí se protege (ajuste D5, aprobado por architec como precisión de la decisión del usuario). Cada definición puede apagar la protección (`proteger_formulas: false`). **Es la segunda excepción a RF-54:** hoy `/archivos-carga` escribe esos textos sin apóstrofo. La opción viaja en `OpcionesArchivo`, porque los exportadores no conocen la definición (precisión D4).
- **JSON:** sin cambios. Se escribe con `ensure_ascii=False`, en UTF-8.
- **Textos y canal:** UTF-8 en todo el camino. Los saltos de línea se conservan: el módulo CSV los entrecomilla y el XLSX los guarda en la celda. Cada plataforma declara si los admite; si no, la previsualización lo advierte.

## 10. Contrato backend ↔ frontend

La forma exacta la fija el backend en `contratos/openapi.json`, como siempre. Este es el acuerdo de diseño:

| Endpoint | Para qué |
|---|---|
| `GET /texto-enriquecido/catalogo?contexto=` | Variables del contexto con su tipo, y funciones con parámetros, tipos y claves i18n. La interfaz arma los menús con esto |
| `POST /texto-enriquecido/validacion` | Recibe una expresión y un contexto. Devuelve los problemas con su ubicación (nodo, función, parámetro) y código, el tipo resultante y la cota de largo si existe |
| `POST /texto-enriquecido/previsualizacion` | Recibe una expresión o una definición, y una muestra. Devuelve por fila el resultado total, el de cada nodo, su segmento y los problemas de fila. La muestra puede ser: el registro de ejemplo del catálogo; **ejemplos por segmento**, que es la opción por defecto para una definición: una fila por segmento con un valor sintético de días que cae en cada rango, tomado de la tabla de rangos (B4a); un producto real (fecha de corte y pagaré); o **cartera real**: una fecha de corte y una selección con la forma de `/cartera` (filtros, orden y cantidad hasta 5), con el mismo orden y desempate que la carga (B4b). Solo lectura: no guarda nada |
| `GET, POST /definiciones-columnas`, `GET /definiciones-columnas/{id}?version=N`, `POST /definiciones-columnas/{id}/versiones` | Definiciones guardadas y versionadas (B4b, sección 22) |
| `/archivos-carga` | Acepta una definición guardada (`definicion_guardada`: id y versión) o una en línea, como hoy; exactamente una de las dos (B4b) |
| `/mowa-mes/speech` | Acepta versiones en formato v2 (una expresión por segmento) sin dejar de leer las v1 |

- **Errores:** (los de las definiciones guardadas, `400` con `problemas`, `404` y `409` con `codigo`, están en la sección 22)
  - **Una expresión o definición con problemas no es un error de la petición:** validar y previsualizar responden `200` con los problemas y su ubicación, porque es lo que el editor muestra mientras se escribe. Una forma JSON imposible (un tipo de nodo que no existe, un argumento nulo, una clave de más) es el problema `expresion_invalida` en su nodo y función, no un `422`; el `422` queda para lo que el esquema del pedido no admite (una `expresion` y una `definicion` a la vez, un producto real sin pagaré).
  - **Lo que no existe es un `404`** que extiende `DetalleError` con `codigo` (`contexto_desconocido`, `producto_no_encontrado`, `sin_version_vigente`).
  - **El `400` queda reservado para guardar** (B4b: nombre repetido, definición que no compila): extiende `DetalleError` con `codigo` y la ubicación, según la regla de `contrato-api.md` §3.
- **i18n:** `textoEnriquecido.codigo.*`, con una prueba espejo entre el catálogo del backend y el i18n, como la de `CodigoMowaMes` (`backend/tests/test_i18n_texto_enriquecido.py`, que además cubre funciones, parámetros, familias, marcas de fecha y contextos, y `frontend/tests/nucleo/i18n-codigos-texto-enriquecido.test.ts`).
- **La interfaz no evalúa ni valida reglas de negocio.** Pide validación y previsualización al backend, con espera tras cada cambio, como la selección de cartera.

## 11. Estrategia de migración de MOWA MES

| Fase | Qué cambia | Qué no cambia | Salida |
|---|---|---|---|
| **M1 — Motor por dentro** | `ConstructorMensajes` convierte cada versión v1 (partes) a una expresión y la evalúa con el motor. Largo máximo con `cota.py` | API, base de datos, interfaz, huellas | Prueba de oro en verde: mensajes y largos idénticos. Rendimiento con 46 000 filas a no más de 10 % sobre el actual |
| **M2 — Speech v2** | Versiones nuevas guardadas como una expresión por segmento, con el editor nuevo en `/mowa-mes/configuracion` | Las v1, incluido el Speech original, se siguen leyendo y siguen siendo inmutables; conservan su huella | Crear una versión v2 desde la interfaz, generar una campaña y conciliarla, contra la base de pruebas |
| **M3 — Retiro** | Se retira el editor de dos partes | — | Solo cuando M2 lleve un tiempo en uso y el usuario lo apruebe |

Vuelta atrás: el camino v1 queda en el código hasta cerrar M2.

## 12. Pruebas

| Nivel | Qué |
|---|---|
| Núcleo | Sintaxis (incluida la compatibilidad con `[@campo]` y la ida y vuelta), cada función con bordes y nulos, comprobación de tipos, cota de largo, segmentación con rangos y con campo, política sin segmento. Propiedades con semilla fija sobre la sintaxis y sobre `sin_tildes` y `primeros` |
| Oro de MOWA MES | Mensajes y largos idénticos en los 6 segmentos (sección 2) |
| Exportadores | Leer de vuelta CSV y XLSX con textos que empiezan con `=`, `+`, `-` y `@`; saltos de línea; tildes y ñ |
| Integración (`auto_cusco_test`) | Definiciones versionadas, inmutabilidad al usarse, `/archivos-carga` con definición guardada, campaña de MOWA MES con speech v2 |
| API y contrato | Catálogo, validación y previsualización; errores con `codigo` y `ubicacion`; prueba espejo de códigos con el i18n |
| Frontend | Vitest del estado del editor y del constructor; Playwright del flujo completo; axe en los estados nuevos |
| Rendimiento | `medir_campana_mowa_mes.py` y `medir_generacion.py` antes y después |
| Mutación | A mano, en worktree: orden de funciones, nulos, cota, protección de fórmulas, oro |

## 13. Decisiones del usuario (2026-09-29)

| Punto | Decisión |
|---|---|
| Criterio de segmentación por defecto | Segmento financiero **calculado** desde los días de atraso, con etiquetas; el campo `segmento_financiero` de la sábana llega mal cargado. El campo crudo queda disponible como criterio categórico |
| Inyección de fórmulas | XLSX como texto literal; CSV con apóstrofo por defecto, que cada definición puede apagar; JSON sin cambios |
| Ejecución | Sesiones `coordinador_motor_texto_enriquecido`, `dev_backend_motor_texto_enriquecido` y `dev_frontend_motor_texto_enriquecido`, con `designer` como responsable de la experiencia y de los componentes compartidos |
| Definiciones | Guardadas, versionadas e inmutables una vez usadas, compartidas |

## 14. Riesgos, decisiones técnicas y pendientes

**Decisiones técnicas de architec:**

- Extender `mapeo_campos` en lugar de crear un motor paralelo.
- Expresión canónica en JSON, con la sintaxis de texto como compatibilidad.
- Montos siempre como Decimal.
- Marcas de fecha legibles en lugar de `strftime`.
- Tabla de rangos en el núcleo compartido.
- Huella v1 intacta.

**Pendientes a confirmar con el usuario:**

1. **Tabla de rangos por defecto del segmento calculado.** La de MOWA MES es Preventiva, 1–8, 9–30, 31–60, 61–90 y 91–120. La partición del campo de la sábana es otra: 1–8, 9–15, 16–30, 31–60 y 61–90. Por ahora, la por defecto es la de MOWA MES, que es la que está en uso.
2. **Codificación SMS.** Un SMS con tildes o caracteres fuera de GSM-7 pasa a UCS-2 y su límite baja de 160 a 70 caracteres. Hoy MOWA MES cuenta caracteres, y MES quita las tildes al enviar. Hay que confirmar con MES cómo cobra y corta. Mientras tanto, `sin_tildes` queda disponible y la previsualización muestra el largo en caracteres.
3. **Días ajustados en otros módulos.** El ajuste a la fecha de envío es de MOWA MES. En otro canal, el criterio usa `dias_atraso` sin ajuste, salvo que ese módulo aporte `fecha_envio`.

**Decisiones del usuario del 2026-09-30:**

- **Redondeo:** las columnas `financiero` de hoy (a la mitad al par) y las funciones del motor (a la mitad hacia arriba) quedan como están; la diferencia está documentada en `mapeo-campos.md`.
- **Pruebas con base de datos:** solo `architec` las corre, al verificar cada entrega en su copia aislada. Los agentes delegados no copian el `.env` ni reciben credenciales: escriben sus pruebas `postgres` sin correrlas y lo declaran en la entrega. Las mediciones de rendimiento con base (antes y después) también las corre `architec`.

**Fuera de alcance:** la plantilla del nombre de archivo de MOWA MES (`{campana}`, `{archivo}`…, en `mowa_mes/nombre_archivo.py`) es otro minilenguaje, con saneamiento para Windows. Queda como está (precisión D12 del coordinador).

**Riesgos:**

| Riesgo | Mitigación |
|---|---|
| Regresión del speech | Prueba de oro y fases M1 a M3 |
| Rendimiento con cadenas de funciones en 46 000 filas | Compilar una vez; medición con umbral |
| Expresiones enormes o abusivas | Límites de nodos, funciones y literales; rechazo al validar |
| El apóstrofo del CSV rompe una plataforma | Configurable por definición, con valor por defecto seguro |
| Dos lugares con la tabla de rangos | Se mueve, no se copia; MOWA MES la importa |

## 15. Documentación para reutilizar

Al cerrar, `docs/motor-texto-enriquecido.md` queda como guía de uso: cómo un módulo aporta sus variables de contexto, cómo agrega una función, cómo declara una definición con segmentos y cómo elige la protección de fórmulas. `docs/mapeo-campos.md` apunta aquí para lo nuevo.

## 16. Implementación del núcleo (B1)

Estado: núcleo hecho y probado (2026-09-30), sin conectar todavía a `GeneradorCargas`, `/archivos-carga` ni MOWA MES (B2 y B5). Código en `backend/app/core/entities/texto_enriquecido.py` y `backend/app/core/services/texto_enriquecido/`. El puente de RF-54 existe: `evaluador.compilar_texto(plantilla, variables).evaluar(producto)` lee una plantilla `[@campo]` y da el mismo texto que `plantillas.aplicar`; `variables_desde_campos(CAMPOS_CARTERA)` arma las variables tipadas.

### Decisiones

- **Escape de `[@`.** Un `[@` literal en un nodo texto se escribe `[@@]`. Hoy ese texto es siempre inválido, así que ninguna plantilla existente cambia de significado. No se usa la barra invertida, porque `C:\[@campo]` vale hoy. Una variable no puede llamarse `@`: `[@@]` sería ambiguo (lo halló una prueba de propiedades).
- **Sintaxis de argumentos.** Número (`3`, `-2`, `2.50`), texto entre comillas con `\"` y `\` como únicos escapes (puede llevar `]`, `|` y saltos de línea), o variable con `@nombre` (`sumar_dias(@dias)`). El analizador es de un solo paso, sin expresiones regulares, y corta la lectura al pasar un límite.
- **Regex por fila.** Evaluar una fila no compila ninguna expresión regular (una prueba lo comprueba) ni usa patrones con backtracking. La única regex que se aplica por fila es la ya compilada y lineal del teléfono (`9\d{8}`, RF-02), dentro de `enlace_whatsapp`/`numero_valido`.
- **Ida y vuelta.** `escribir(leer(t))` es la forma canónica y se lee igual que `t`; para un texto ya canónico es idéntico. Una expresión sin forma de texto se informa con `no_se_puede_escribir_como_texto`: por ejemplo, una variable marcada `obligatoria`, porque **la marca obligatoria no tiene sintaxis de texto** (solo existe en la forma JSON).
- **Qué es vacío.** `None` o un texto en blanco (D10, igual que `_vacio` de MOWA MES). Un nodo sin funciones conserva `str(valor)` exacto, también con `"  "` (RF-54). Con funciones, el blanco cuenta como vacío: la cadena no se aplica y el nodo queda vacío, salvo `si_vacio`, la única función `acepta_nulo`. Un argumento que es una variable vacía da `argumento_vacio` (`si_vacio` lo admite).
- **Conversión a texto.** `str(valor)` como hoy (D1): un booleano da `"True"`. Las funciones devuelven `Decimal` en texto plano, sin notación científica. Los booleanos (D2) no tienen funciones propias, salvo `si_vacio`.
- **Valor tipado (D11).** `Resultado.valor` trae el valor final sin pasarlo por texto cuando la expresión es un solo nodo variable, aunque lleve funciones; en cualquier otra expresión es `None`.
- **Redondeo.** `redondear` y `formato_numero` van a la mitad hacia arriba (`ROUND_HALF_UP`, lejos del cero), como los montos de MOWA MES. **Diferencia conocida:** las columnas `financiero` de hoy (`formatos.formatear_importe`) usan `round()` de `Decimal`, a la mitad al par (RF-54 exige no cambiarlas), así que con un valor como `0.125` una columna `financiero` da `0.12` y `formato_numero(2)` da `0.13`.
- **Mayúsculas carácter a carácter.** `mayusculas`, `minusculas`, `capitalizar` y `sin_tildes` dejan igual el carácter que cambiaría de largo (`ß`, `İ`, una sílaba hangul), para que la cota sea un tope verdadero. Solo difieren de `str.upper()` en esos casos. `capitalizar` pone en mayúscula la primera letra del texto entero y en minúscula el resto; no es por palabra.
- **Fechas sin `strftime`.** Marcas `dd`, `mm`, `aaaa`, `aa`, `nombre_mes` (meses en español, sin depender del idioma del sistema; cualquier otro carácter es literal, `%` incluido). El patrón necesita al menos una marca. `a_fecha` lee con el mismo patrón: `dd` y `mm` de dos dígitos exactos, `aa` = 2000 + `aa`, y necesita día, mes y año.
- **Cota.** Siempre un tope verdadero. `primeros(n)` da `n` (o el menor, si la entrada ya estaba acotada); `formato_fecha("dd/mm/aaaa")` da 10; `enlace_whatsapp` da el largo del prefijo más 9; una fecha calculada (`sumar_dias`, `a_fecha`) mide 10. Las conversiones de número y `formato_numero` no tienen cota. Una variable sin funciones, o una sola parte sin cota, deja la expresión sin cota.
- **Límites por defecto** (`LimitesExpresion`, se rechazan al compilar y cortan el lector): 200 nodos, 10 funciones por nodo, 8 argumentos por función, 5 000 caracteres por literal y 30 por número.
- **Prefijo de WhatsApp.** `enlace_whatsapp` tiene su propio `PREFIJO_WHATSAPP` (`https://wa.me/+51`, mismo valor que el de MOWA MES). El núcleo es el dueño: B5 hace que MOWA MES lo importe, sin copias.

### Códigos (`CodigoTexto`)

Al compilar: `sintaxis_invalida`, `referencia_vacia`, `variable_desconocida`, `funcion_desconocida`, `parametro_invalido`, `tipo_incompatible`, `limite_excedido`, `no_se_puede_escribir_como_texto`. Al evaluar una fila: `variable_obligatoria_vacia`, `argumento_vacio`, `division_por_cero`, `no_es_numero`, `no_es_fecha`, `telefono_invalido`, `resultado_fuera_de_rango`. Una prueba exige que todos se emitan de verdad. La ubicación de un `Problema` es `nodo` y `funcion` (posiciones desde 0) y `parametro` (nombre del parámetro); con `nodo` en `None` el problema es de toda la expresión. B4a agrega ocho (sección 21): `expresion_invalida` (la forma JSON), `definicion_invalida`, `valor_no_convertible`, `sin_cota_variable`, `sin_cota_funcion`, `contexto_desconocido`, `producto_no_encontrado` y `sin_version_vigente`.

### Cómo se agrega una función

1. Escribir su `Funcion` (nombre estable, familia, `recibe`, `devuelve`, `parametros` con tipo y rango, `aplicar`, y `cota` si se puede) en el módulo de su familia de `backend/app/core/services/texto_enriquecido/funciones/`, o en un módulo nuevo que declare `FUNCIONES` y se sume a `FAMILIAS` en `funciones/__init__.py`.
2. `devuelve` es un `TipoValor`, o `MISMO_TIPO` (`"entrada"`) si devuelve lo que recibe. Un parámetro puede aceptar una variable (`acepta_variable`), tener valor por defecto y un `convertir` que prepara el literal una sola vez al compilar.
3. Si una fila no admite la función, `aplicar` lanza `ValorInvalido(codigo, detalle)`; el evaluador lo informa como problema de la fila con su ubicación y el resto del texto se conserva.
4. Nada más se toca: el comprobador de tipos, el evaluador y la cota leen el registro. Las claves i18n son `textoEnriquecido.funcion.<nombre>.nombre` y `.descripcion`.
5. Sumar sus pruebas: bordes, nulos y, si declara `cota`, un caso en `test_texto_enriquecido_cota.py`.

## 17. Migración M1 de MOWA MES (B5)

Estado: hecha y probada sin base (2026-09-30). El speech de MOWA MES se evalúa con el motor por dentro; la API, la base de datos, la interfaz, `huella_speech` y las firmas públicas (`ConstructorMensajes`, `mensaje_de`, `mensaje`, `requiere_whatsapp_faltante`, `previsualizar`, `codigo_por_largo`, `whatsapp_valido`, `problemas_de`, `limpiar`) no cambian. `contratos/openapi.json` tampoco.

- **Conversión v1 → expresión** (`speech.expresion_de`): `titular | primeros(8)`, la parte 1, `fecha_vencimiento_cuota | formato_fecha("dd/mm/aaaa")` y la parte 2. Cada `[whatsapp]` de una parte es la variable `whatsapp_contacto | enlace_whatsapp`; los espacios de los extremos se conservan y las partes vacías no dejan nodos. Se arma con nodos, nunca por la sintaxis de texto: `[`, `]`, `[whatsapp` sin cerrar o un `[@` son texto fijo.
- **Se compila una vez por segmento** (`compilar_segmento`). Los segmentos con `[whatsapp]` sin número siguen sin compilarse y lanzan `FaltaWhatsapp`. Los límites de tamaño del motor se ajustan a la expresión del conector: un speech no tiene tope de largo al editarlo (se mide y se advierte, RF-MM-19), y el motor no debe rechazar lo que antes se aceptaba.
- **Largo máximo = `Compilada.cota`.** Coincide con la aritmética de antes (8 + 10 + texto + 26 por cada `[whatsapp]`) en el Speech original y en 12 versiones sintéticas; `9 a 30` da 156. El `ejemplo` sigue por el camino de antes, con marcadores (D8).
- **Un solo dueño del prefijo de WhatsApp.** `PREFIJO_WHATSAPP` vive en `entities/texto_enriquecido.py`; `enlaces.py` lo importa y `entities/mowa_mes.py` lo reexporta con el mismo nombre. Una prueba fija `len(PREFIJO_WHATSAPP) + LARGO_NUMERO_WHATSAPP == 26` y que la cota de `enlace_whatsapp` sea 26.
- **Las exclusiones siguen en `campana.py`** (`_vacio` antes del mensaje, en el orden `falta_titular`, `falta_vencimiento`, `falta_whatsapp`). Titular y vencimiento no se marcan como obligatorios todavía: eso es de M2.
- **`plantilla_mensaje` y `contexto_fila` se borraron en B6** (sección 23); la prueba de oro sigue contra las constantes congeladas.
- **Diferencias, ambas fuera del camino real** (las dos con su prueba): un titular en blanco que llegara directo a `mensaje_de` da vacío (D10) y no los espacios que dejaba `titular[:8]`, pero `campana.py` lo excluye antes con `falta_titular`; y un número de WhatsApp inválido en el constructor ya no da un enlace con basura: el motor lo informa (`telefono_invalido`) y `mensaje` lanza `MensajeNoGenerable` (con el segmento y los códigos), para que no salga un SMS sin enlace en silencio. La configuración y la campaña lo validan antes, así que no se alcanza; si esas validaciones cambian, pasa a ser un 500.
- **Costo.** El motor cuesta unos 3,7 µs por mensaje contra 2,8 µs del camino de antes en el microbench de 46 000 filas (`scripts/medir_mensajes_mowa_mes.py`, sin base). Parte de la diferencia es la validación RF-02 del teléfono que `enlace_whatsapp` repite por fila (el camino de antes la hacía una vez al configurar). El umbral de 10 % se juzga sobre `medir_campana_mowa_mes.py` (con base, lo corre `architec`), donde este costo es una fracción pequeña del total.
- **El oro sobrevive a M2.** Compara siempre contra constantes congeladas en HEAD 3e567d7 con el código viejo (`tests/oro_mowa_mes_congelados.py`: los 6 mensajes literales del Speech original y un SHA-256 de la matriz completa de 4 992 casos, serializada de forma determinista), y contra el camino viejo en vivo solo mientras exista. En B6, al borrar `plantilla_mensaje` y `contexto_fila`, se borran solo las pruebas marcadas "en vivo".
- **Pruebas:** `tests/test_mowa_mes_speech_oro.py` (mensaje byte a byte, `previsualizar` entero, bordes de 150 y 160, orden de exclusiones, huellas del Speech original y de 12 versiones sintéticas fijadas en HEAD 3e567d7 antes de tocar `speech.py`, prefijo). Mutación a mano sobre la conversión, la cota y `FaltaWhatsapp`: 33 mutantes, todos muertos.

## 18. Exportación segura (B3)

Estado: hecha y probada sin base (2026-09-30). Independiente del motor y de B5. Detalle por formato en [generacion-cargas.md](generacion-cargas.md), «Protección contra fórmulas».

- **D4.** `OpcionesArchivo.proteger_formulas: bool = True` (`entities/exportacion.py`); los exportadores la leen de ahí. Solo afecta al CSV. **No se expone todavía en `/archivos-carga`**: la definición la guardará y la pasará B4b. `contratos/openapi.json` no cambia (comprobado con `exportar_openapi.py`; su prueba de contrato pasa).
- **XLSX (siempre, sin opción).** Un `str` que empieza con `=` se escribe con el tipo de texto explícito (`WriteOnlyCell` con `data_type = "s"`, que sale como `inlineStr`, igual que el resto de los textos). Vale también para las cabeceras. El contenido no cambia: sin apóstrofo y sin `quotePrefix="1"`. Es una de las dos excepciones a RF-54 (D6); la otra es el apóstrofo del CSV.
- **CSV (con `proteger_formulas`).** Un valor que es `str` en la tabla y empieza con `=`, `+`, `-`, `@`, tabulación o retorno de carro lleva `'` delante, salvo que el texto completo sea solo un número con signo (D5). `-2+3` se protege; `-1,234.56`, `+51987654321`, `-5` y `3.5` no. Un `Decimal`, un `int`, una fecha o un booleano nunca se tocan (`-1E-7`, el texto de un `Decimal` pequeño, no lleva apóstrofo). **Las cabeceras del CSV se protegen con el mismo criterio**: una definición compartida (RF-51) puede traer un nombre de columna `=...`, y RF-53 no distingue entre un valor y una cabecera. Con la opción apagada el CSV, cabeceras incluidas, es idéntico al de antes.
- **«Solo un número»** se comprueba carácter a carácter, sin expresiones regulares por celda: signo opcional, un dígito ASCII y luego solo dígitos, puntos y comas. Es más estricto que la expresión regular del diseño en dos casos, y siempre del lado de proteger: los dígitos de otros alfabetos no cuentan, y un salto de línea al final tampoco (la expresión lo admitiría por el `$`).
- **JSON:** sin cambios.
- **«Byte a byte» del XLSX (D7).** Un libro escrito dos veces nunca es idéntico byte a byte: openpyxl guarda la fecha y hora en `docProps/core.xml` y en la cabecera de cada entrada del zip. Las pruebas comparan un SHA-256 de **todas las partes del zip** con esas dos marcas de tiempo normalizadas, más el **largo sin el `core.xml` comprimido** (el largo bruto no sirve: ese `core.xml` comprimido mide entre 233 y 236 bytes según la hora, así que congelarlo era intermitente). Es el largo del que depende la división por bytes de MOWA MES. Una prueba escribe el libro con tres horas distintas (fijando la de openpyxl) y comprueba que huella y largo no se mueven. Las constantes (`tests/exportacion_seguridad_congelados.py`) se calcularon en HEAD 3e567d7 con los exportadores sin tocar; también las de CSV y JSON, que sí son deterministas.
- **MOWA MES.** `escribir_archivo_carga` con filas cuyo mensaje empieza con `=`, `-`, `+` o `@`: al leer de vuelta, `mensaje` y `dni` son idénticos a `FilaCarga.celdas()` (mismo largo y mismo texto, ambos como texto) y no hay fórmulas. El archivo sin `=` es idéntico al de HEAD y mide lo mismo.
- **Comportamiento previo, no introducido por B3:** openpyxl escribe un `\r` dentro de una celda sin escapar y un lector XML lo normaliza a `\n`. Pasa en HEAD con cualquier texto (se verificó con los exportadores sin tocar) y B3 no lo cambia; en XLSX no es riesgo de fórmula porque la celda es de tipo texto. Una prueba lo deja fijado.
- **Pruebas:** `tests/test_exportacion_segura.py` (32), dos casos nuevos en `tests/test_api_archivos_carga.py` (CSV con `=1+1` lleva apóstrofo; XLSX con `=1+1` sale como texto) y las de `test_exportadores.py` sin cambios. Mutación a mano sobre el conjunto de caracteres, la excepción numérica, `str` frente a otros tipos, la opción apagada y el `=` en XLSX: 47 mutantes; 46 muertos y 1 equivalente (escribir *todo* texto como celda de texto produce el mismo archivo).

## 19. Variables de contexto constantes (B7)

Estado: hecha y probada sin base (2026-09-30). Motivo: en B5, `enlace_whatsapp` validaba el teléfono (RF-02) en cada fila aunque el número es el mismo en toda la campaña.

- **API.** `evaluador.compilar(..., constantes: Mapping[str, Any] | None = None)` (y `compilar_texto`). Una constante es una variable **del catálogo** (si no, `ValueError`) con un valor fijo para toda la carga; `None` es una constante vacía. Las constantes pasan por la misma comprobación de tipos que una variable de la fila (`coaccionar`).
- **Cuándo se pliega.** Un nodo `variable` cuya variable es constante y cuyos argumentos variables también lo son (o son literales) se evalúa **una vez al compilar**. Si no hay problema y la expresión no es un único nodo, queda como texto fijo y se une a los textos fijos vecinos (una fila recorre menos trozos). Un nodo que no se pliega pero lee una constante como argumento la recibe igual en cada fila, y **la constante manda sobre lo que traiga la fila**.
- **Problemas.** Los del plegado se informan al compilar, con su ubicación (`Compilada.problemas_plegados`), y cada fila los vuelve a informar igual que sin plegado. Cada parte conserva el índice del nodo original aunque se unan textos: una propiedad halló que, sin eso, el problema decía otro nodo.
- **Invariantes.** Con o sin plegado, para cualquier fila: mismo `texto`, mismo `valor` tipado (D11: un nodo único conserva su valor), mismos `problemas` y misma cota. La cota es la de la expresión **sin plegar**: en MOWA MES el enlace mide 26 con o sin número. `variables` deja de incluir las constantes y `nodos_plegados` dice cuántos nodos se evaluaron al compilar. Sin constantes, todo sigue igual.
- **Pruebas.** Propiedad con semilla fija: 3 000 expresiones con funciones, argumentos variables y variables obligatorias, constantes al azar y 4 filas cada una (12 000 comparaciones), con y sin plegado; además, unitarias y una prueba que cuenta que el nodo constante se aplica una vez al compilar y no por fila.

### MOWA MES

- `ConstructorMensajes` compila cada segmento con `{whatsapp_contacto: número}` **solo si hay número**. Con `None` no se pasa constante: `_sin_whatsapp` sigue igual (`FaltaWhatsapp` solo al pedir un mensaje de esos segmentos) y un segmento que no usa `[whatsapp]` compila como antes. `previsualizar` sigue sin constantes (el largo no depende del número).
- **Momento en que se detecta un número inválido.** Antes (B5) salía en cada fila; ahora se detecta al construir el constructor y queda **en ese segmento**: se guarda y se lanza `MensajeNoGenerable` al pedirle un mensaje, sin romper el constructor ni los segmentos que no usan `[whatsapp]`. Sigue siendo inalcanzable: la configuración y la campaña validan el número (RF-02) y `previsualizar` del speech responde el 400 de hoy (no un 500).
- La fila ya no aporta el contacto: `mensaje_de` pasa solo titular y vencimiento; uno que llegue en `mensaje(contexto)` se ignora (la constante manda).
- El oro de B5 (6 mensajes, matriz de 4 992 casos y huellas) sigue en verde **sin tocarlo**.
- **Costo.** A/B intercalado en el mismo proceso, con la carga del microbench (46 000 mensajes, 6 segmentos, Speech original): sin plegar (camino de B5) 4,92 µs por fila, plegado 3,76 µs: **−23,5 %**. Las cifras absolutas varían mucho con la carga de la máquina (otras sesiones corrían a la vez); el comparativo intercalado es el fiable. El microbench suelto (`medir_mensajes_mowa_mes.py`) no muestra la mejora con claridad porque su ruido entre corridas (±5 %) es del orden del ahorro promedio. El costo restante es la evaluación genérica de los dos nodos de la fila (titular y fecha), que este corte no toca.

## 20. Columnas dinámicas y segmentación (B2)

Estado: hecha y probada sin base (2026-09-30). Sin cambios en la API ni en `contratos/openapi.json`: `/archivos-carga` sigue aceptando solo plantillas; las columnas nuevas llegan con B4a y B4b.

### Entidades (`entities/mapeo.py`, `entities/segmentacion.py`)

- `CampoSalida` gana, todos opcionales: `expresion` (manda sobre `plantilla`, que entonces se ignora), `valor_por_defecto` y `variantes` (`VarianteCampo(segmento, plantilla | expresion)`). El contenido de la columna (`expresion` o `plantilla`) es el **contenido por defecto**; las variantes lo sustituyen por segmento.
- `DefinicionCarga` gana `segmentacion: Segmentacion | None`. `Segmentacion(criterio, politica)`:
  - **`CriterioCalculado(tabla, variable_dias)`** (el de por defecto): los días de la variable `variable_dias` (`dias_atraso`) contra una tabla de `RangoDias(clave, etiqueta, desde, hasta)`; `None` en un extremo es sin límite. La fecha de envío **no** entra al núcleo: un módulo que la tenga aporta una variable ya ajustada (`dias_atraso_ajustados`) y la nombra aquí.
  - **`CriterioCampo(campo)`**: el valor del campo tal cual (sin normalizar: `Vigente` y `vigente` son distintos; un valor vacío o en blanco no tiene segmento).
  - **`PoliticaSinSegmento`**: `excluir` (por defecto) o `usar_por_defecto`.
- Tabla por defecto: la de MOWA MES (`preventiva` hasta 0, `1_a_8`, `9_a_30`, `31_a_60`, `61_a_90`, `91_a_120`); más de 120 días queda sin segmento. Una tabla puede tener huecos pero no rangos que se pisen.
- `ErrorGeneracion` gana `codigo` (el `CodigoTexto` cuando lo informa el motor). `CargaGenerada` gana `exclusiones` (`FilaExcluida(fila, codigo, detalle)`). Código nuevo `sin_segmento` en `CodigoTexto`.

### `GeneradorCargas` (`services/mapeo_campos/generador.py`)

- **Cada columna se evalúa con el motor.** Una plantilla se compila a expresión (admite `[@titular | primeros(8)]`) y el tipo de la columna lo sigue aplicando `formatos.convertir`, después del motor: **un solo camino de tipado**. D11: una columna de una sola variable con funciones conserva su valor tipado (una fecha sumada sigue siendo fecha).
- **Variables.** Recibe un mapa nombre → tipo (`CAMPOS_CARTERA`, o ya `TipoValor`) o solo nombres (se toman como texto: una columna de variable directa sale igual).
- **Problemas de fila del motor** (división por cero, variable obligatoria vacía, teléfono inválido…) son un `ErrorGeneracion` con `codigo`, la celda queda vacía y el resto de la carga sigue.
- **Valor por defecto:** entra cuando todo el resultado queda vacío (no cuando hay un problema), y pasa por el tipo de la columna. Un campo en blanco (`"  "`) no cuenta como vacío (RF-12).
- **Segmento.** Un segmento está *reconocido* si es un rango de la tabla (criterio calculado) o un valor que alguna columna contempla en sus variantes (criterio por campo). Reconocido: cada columna usa su variante, o su contenido por defecto si no tiene una. No reconocido: con `excluir` la fila **no sale** y queda en `CargaGenerada.exclusiones` con `sin_segmento` y su motivo; con `usar_por_defecto` sale con el contenido por defecto. Los números de fila de errores y exclusiones son los del producto en el pedido, no los de la salida.
- **Se rechazan al compilar** (`PlantillaInvalida`, el 400 de hoy): variantes sin segmentación, clave de variante fuera de la tabla, variante repetida o sin contenido, plantilla y expresión a la vez, variable del criterio inexistente, criterio por campo sin variantes, tabla mal armada, y toda función mal usada (`formato_fecha` sobre un texto, parámetro inválido). Los errores de las plantillas de siempre (campo inexistente, `[@` sin cerrar, referencia vacía) conservan **su texto de antes**.
- **Límites de tamaño (RF-48).** Una `expresion` explícita conserva los límites por defecto. Una `plantilla` es la ruta de compatibilidad (RF-54): sus topes de nodos y de texto fijo crecen con ella, porque una plantilla grande que funcionaba sin límite no puede empezar a rechazarse (lo detectó el oro de MOWA MES con una de 12 000 caracteres).

### RF-54 a nivel de generador

La prueba compara la `CargaGenerada` **entera** —cabeceras, filas con el tipo de cada celda y errores con su fila, campo y texto— sobre 7 definiciones × 8 productos (texto, número, fecha, financiero, vacíos, valores que no se pueden convertir): contra un SHA-256 congelado en HEAD b8b9025 con el generador original y contra el camino de antes en vivo (`plantillas` + `formatos`, que siguen en el código como referencia). También con el catálogo tipado de la cartera.

### D3: la tabla de MOWA MES sale del núcleo

`RANGOS_SEGMENTO` (`entities/mowa_mes.py`) se arma desde `TABLA_RANGOS_POR_DEFECTO`: hay **una sola tabla**. El enum `Segmento` sigue siendo de MOWA MES y una prueba exige que sus valores sean las claves del núcleo. MOWA MES no admite un `hasta` abierto (el armado lo rechaza): más de 120 días ajustados sigue sin speech. `segmentos.dias_ajustados` es la función del núcleo (misma firma) y `segmentos.rango_de` delega en `segmentacion.rango_de`. No cambió `campana.py`, `speech.py`, la API ni el oro de B5.

### Rendimiento de la generación genérica

A/B intercalado sin base, 60 000 filas, definición de 6 columnas (texto fijo, prefijo + campo, variable directa, financiero, fecha con formato y un mensaje): camino de antes 10,2 µs por fila, ahora entre 10,1 y 10,9 según la corrida (**entre −0,3 % y +7 %**: el ruido de la máquina es del orden de la diferencia). La primera versión llegaba a +71 %; se bajó con tres cambios que no alteran el resultado: `Compilada.evaluar` decide la forma de cada parte al compilar (texto fijo, variable directa, plegado, nodo con funciones) y devuelve el resultado ya armado si la expresión no lee nada de la fila; `Resultado` pasó de dataclass congelada a `NamedTuple` (mucho más barata de crear, igual de inmutable); y el generador no llama al evaluador para las columnas de texto fijo ni de variable directa (`Compilada.texto_fijo` y `referencia_directa`). Una variable directa no se evalúa: da `str(valor)` y el valor sin tocar, exactamente como el motor (D1, D11).

## 21. Contrato del motor para la interfaz (B4a)

Estado: hecho y probado sin base (2026-10-02). Solo lectura: nada de lo de esta sección guarda datos. Código en `backend/app/api/texto_enriquecido.py` (router), `services/previsualizar_texto.py` (casos de uso), `services/contextos_texto.py` y `entities/contexto_texto.py` (contextos), `services/mapeo_campos/serializacion.py` y `diagnostico.py` (la definición como JSON y todos sus problemas) y `services/texto_enriquecido/catalogo.py` y `serializacion.py` (el catálogo de funciones y la expresión como JSON). Los tipos del frontend se regeneran con `npm run contrato` (`frontend/src/lib/contrato-api.d.ts`).

### Endpoints

| Endpoint | Pedido | Respuesta (`200`) |
|---|---|---|
| `GET /texto-enriquecido/catalogo?contexto=` (por defecto `cartera`) | | `contexto` (variables con tipo y clave i18n si el módulo la aporta, registro de ejemplo, `limite_largo`, `umbral_advertencia`, `variable_dias` y `segmentos`, la tabla de rangos), `contextos` (los disponibles), `funciones`, `familias`, `patrones_fecha`, `marcas_fecha` y `limites` |
| `POST /texto-enriquecido/validacion` | `contexto`, `expresion` | `problemas`, `tipo`, `cota`, `sin_cota` (el motivo con su código y su nodo, si es válida y no hay largo máximo) y `variables` |
| `POST /texto-enriquecido/previsualizacion` | `contexto`, `expresion` **o** `definicion`, `muestra` | `problemas` (la expresión o definición no compila: sin filas) o `filas`; `limite_largo` y `umbral_advertencia` del contexto |

- **Catálogo de funciones.** Todo sale del registro: una función nueva aparece con sus tipos (`recibe`, `devuelve`, con `entrada` si devuelve el mismo tipo que recibe), sus parámetros (tipo, `obligatorio`, `por_defecto`, `acepta_variable`, rango, largo, `opciones` con su ejemplo y si son `opciones_cerradas`) y sus claves i18n sin tocar la API. Los textos no viajan: viajan las claves (`textoEnriquecido.funcion.<f>.nombre`, `.descripcion`, `.parametro.<p>`, `textoEnriquecido.familia.<f>`, `textoEnriquecido.marcaFecha.<m>`). Los ejemplos de patrones y de marcas se calculan con la función de siempre sobre `2026-10-05`.
- **Límites del motor** (`limites`): nodos, funciones por nodo, argumentos por función y largo de un texto fijo (`LimitesExpresion`), para que la interfaz no ofrezca lo que se rechazaría. El motor no limita el largo de un número: lo acotan `minimo` y `maximo` de cada parámetro.
- **`ubicacion`** de un problema: `{nodo, funcion, parametro}` (posiciones desde 0 y el nombre del parámetro) o `null` si es de toda la expresión (un límite de tamaño). En una definición, además, `columna` (el índice en la lista del pedido), `segmento` (la clave de la variante, o `null` para el contenido por defecto) y `campo`: el campo con el problema, de la columna (`nombre`, `orden`, `tipo`, `formato_fecha`, `expresion`, `variantes`...) o, sin columna, de la definición (`definicion`, `nombre`, `columnas`, `segmentacion`, `proteger_formulas`).
- **Pedido permisivo a propósito.** `tipo` de un nodo es un texto y los argumentos son cualquier valor JSON: una forma imposible llega al lector estricto (`expresion_desde_dict`, `definicion_desde_dict`) y vuelve como problema con su ubicación. Lo que el cliente envía como `null` equivale a un campo ausente. Una clave de más no se descarta: se informa.
- **Tipos cerrados en la respuesta.** `VariableRespuesta.tipo`, `ParametroRespuesta.tipo` y `FuncionRespuesta.recibe`/`devuelve` son uniones (`texto | numero | fecha | booleano`, y `entrada` donde el tipo es el de lo que se recibe), no `string`: el cliente generado atrapa un tipo nuevo o mal escrito. `nulo` no sale (ninguna variable ni función lo declara; el vacío de un valor llega por fila en `nodos[].vacio`). Una prueba exige que la lista siga a `TipoValor`.
- **`origen` de cada variable:** el contexto que la aporta (`cartera` para un campo de la cartera, `mowa_mes.speech` para `whatsapp_contacto` y `dias_atraso_ajustados`); la interfaz las agrupa por origen. `titular` y `fecha_vencimiento_cuota` son de la cartera aunque el speech los use.

### La definición de la previsualización (la forma que guardará B4b)

`definicion` = `{nombre, columnas[], segmentacion, proteger_formulas}`. Es una sola forma para el constructor y para guardar (C-1, C-3, C-4, C-10); la definición en línea de `/archivos-carga` no cambia (RF-54).

- **Columna** = `{nombre, orden, expresion, tipo, formato_fecha, formato_financiero, valor_por_defecto, variantes[{segmento, expresion}]}`. El contenido es solo expresión (no hay `plantilla`). `orden` es un entero explícito desde 0, único; las columnas salen ordenadas por él. La columna se identifica por su **posición en la lista del pedido** (`columna` de los problemas), también cuando `orden` las reordena. Un nombre vacío o repetido y un `orden` repetido o inválido son problemas `definicion_invalida` de esa columna (`campo` = `nombre` u `orden`). Una columna recién creada (nombre vacío, `expresion` vacía) da su problema ubicado, nunca un error; una expresión vacía por sí sola no es un problema: la columna sale vacía.
- **`formato_fecha` con marcas** (`dd`, `mm`, `aaaa`, `aa`, `nombre_mes`; C-3): se escribe con la misma traducción que `formato_fecha` del motor (`nombre_mes` en español). Un formato sin ninguna marca es un problema `parametro_invalido` de esa columna (`campo` = `formato_fecha`, `parametro` = `formato_fecha`), no un texto literal; el vacío es no tener formato. El `strftime` queda solo para `/archivos-carga` en línea: `CampoSalida.formato_fecha`; las marcas van en `CampoSalida.patron_fecha` y mandan sobre aquel.
- **`proteger_formulas`** (por defecto verdadero) se lee y se valida; lo aplica el exportador (RF-53) cuando B4b pase la de una definición guardada a `OpcionesArchivo`. Hasta entonces solo viaja en esta definición, no en `/archivos-carga`.

### Muestras de la previsualización

- **`ejemplos_por_segmento`** (por defecto): una fila por rango de la tabla de la definición (o la del contexto si no tiene segmentación), con el registro de ejemplo y un valor de días que cae en el rango —su inicio, o su fin si no tiene inicio—, escrito en la variable de días del criterio solo si es numérica. Con un criterio por campo, una fila por cada valor que alguna columna contempla en sus variantes. `etiqueta` es la del rango y `segmento` es la **clave** del rango (o el valor del campo) que representa la fila, **también cuando se previsualiza una expresión suelta o una definición sin segmentación**: es lo que permite asociar la fila con su segmento (`VariantesSegmento`).
- **`ejemplo`**: una fila con el registro de ejemplo del contexto.
- **`producto_real`** (`fecha_corte` y `pagare`): el producto sale de `ConsultaCarteraService.consultar` con `pagare = valor` y se convierte al registro del contexto. «Primeros N de una selección» llega con B4b.

Cada fila trae `numero`, `etiqueta`, `segmento` (en los ejemplos por segmento, la clave que representa la fila; en `ejemplo` y `producto_real`, el que calcula la definición, o `null` sin segmentación o si el producto no cae en ninguno, por ejemplo sin `dias_atraso`), `excluida` (`sin_segmento` con su motivo, si la política es excluir) y `columnas`. Cada columna: el `texto` (con el valor por defecto ya aplicado), el `valor` tipado que escribiría la carga, su `largo`, la `cota` o el motivo `sin_cota`, `usa_variante`, los `nodos` (`indice`, `tipo`, `texto`, `vacio`) y los `problemas` de esa fila. `vacio` distingue la variable que llegó sin dato de un texto vacío. Una prueba exige que las celdas coincidan con las de `generar_fila` sobre 300 productos con una semilla fija.

### Cómo un módulo registra su contexto

Un contexto (`ContextoTexto`) es lo que un módulo aporta al motor: sus variables con tipo, el registro de ejemplo, el límite de largo y el umbral de advertencia del canal (o ninguno), la variable de días y la tabla de rangos para segmentar, y cómo convertir un producto de la cartera a su registro. **El motor y el registro genérico no conocen a ningún módulo:** una prueba de arquitectura exige que `texto_enriquecido/`, `entities/contexto_texto.py` y `contextos_texto.py` no importen de `services/plataformas/`. Sumar un canal es:

1. Un archivo en su paquete, `services/plataformas/<canal>/contexto_texto.py`, con una función que devuelva su `ContextoTexto` a partir de lo que el canal ya tiene (para MOWA MES: `VARIABLES_DEL_MENSAJE`, `LARGO_MAXIMO`, `LARGO_ADVERTENCIA` y `RANGOS_SEGMENTO`; no se modificó nada suyo).
2. Una línea en `obtener_registro_contextos()` (`app/api/texto_enriquecido.py`), la capa de composición donde se cablean las dependencias de la API. No hay registro que se llene al importar un paquete.
3. Sus claves i18n (`textoEnriquecido.contexto.<nombre>` y las de las variables que aporta) en es y en, en el mismo commit: la prueba espejo falla si faltan.

Contextos hoy: `cartera` (el núcleo: los campos de la cartera con su tipo, sin límite de largo) y `mowa_mes.speech` (`titular`, `fecha_vencimiento_cuota`, `whatsapp_contacto` y `dias_atraso_ajustados`; límites 160 y 150; teléfono de ejemplo `900000123`). Los datos de ejemplo son sintéticos y a la vista (`TITULAR/SINTETICO,UNO`): ningún nombre que parezca de una persona.

**Previsualizar un producto real en `mowa_mes.speech`:** los días ajustados parten de `dias_atraso` de la sábana, **sin el ajuste a la fecha de envío**: el segmento que se ve es el de la fecha de corte, y en una campaña el mismo producto puede caer en otro (RF-MM-15). Pendiente de B6/F4: que el editor se lo diga al usuario («segmento según días de atraso a la fecha de corte»).

### Decisiones

- **`valor_no_convertible`.** El generador de cargas conserva `codigo=None` en el error de un texto que no cabe en el tipo de su columna (lo fija la prueba de paridad de RF-54); solo la previsualización lo informa con `valor_no_convertible`.
- **Previsualizar es evaluar.** La previsualización usa `GeneradorCargas.detallar_fila`, que evalúa cada celda por nodo con el mismo motor y el mismo tipado (`formatos.convertir`): no hay un segundo camino.
- **Nombres del contrato.** Los modelos propios llevan sufijo (`ProblemaTextoRespuesta`, `ExclusionFilaRespuesta`, `PrevisualizacionTextoRespuesta`, `DefinicionColumnasEntrada`) para no chocar con los de otros routers y que los tipos generados tengan nombres limpios.

## 22. Definiciones guardadas y versionadas (B4b)

Estado: hecho y probado sin base (2026-10-03); las pruebas de PostgreSQL (`@pytest.mark.postgres`, fechas de 2099, con limpieza) están escritas y **no corridas**, y la migración (`d5a7c1e9b342`) la verifica architec con ida y vuelta y `alembic check`. RF-51 y lo que quedaba de RF-46 y RF-47. Código en `entities/definiciones_columnas.py`, `ports/repositorio_definiciones_port.py`, `services/definiciones_columnas/servicio.py`, `adapters/persistence/repositorio_definiciones_postgres.py` (tablas `definicion_carga` y `definicion_carga_version`), `api/definiciones_columnas.py`, y los cambios en `api/archivos_carga.py`, `api/texto_enriquecido.py` y `services/previsualizar_texto.py`.

### Qué se guarda

- La **definición** (nombre y marcas de tiempo) y sus **versiones** numeradas desde 1; la vigente es la de mayor número. El nombre es único **sin distinguir mayúsculas ni espacios en los extremos** (lo impone la base sobre `nombre_normalizado`), compartido entre usuarios y módulos, hasta 120 caracteres. El nombre no cambia con una versión nueva.
- El contenido de cada versión es la **forma canónica del constructor** (la misma que acepta `/texto-enriquecido/previsualizacion`, sección 21): columnas con `orden` explícito, **siempre expresiones** (una `plantilla` `[@...]` que llega al servicio se convierte con la sintaxis de siempre; el modelo HTTP no la expone, así que `expresion` sigue obligatoria), `formato_fecha` con marcas, `segmentacion` y `proteger_formulas`. Se guarda **resuelta**: con la tabla de rangos y la variable de días explícitas, para que cambiar el valor por defecto después no cambie una definición guardada.
- Se valida **contra el contexto `cartera`** (las definiciones guardadas alimentan `/archivos-carga`), con el mismo lector y el mismo diagnóstico de la previsualización (RF-46): primero la forma, después el contenido. Límites (en el catálogo, C-9): `columnas_por_definicion` 100, `variantes_por_columna` 50 y `largo_nombre_definicion` 120.

### Endpoints

| Endpoint | Qué hace |
|---|---|
| `GET /definiciones-columnas` | El listado (C-7): `id`, `nombre`, `version_vigente`, `cantidad_versiones`, `actualizado_en`, `vigente_usada`. Ordenado por nombre, sin paginar (como las selecciones guardadas) |
| `POST /definiciones-columnas` | Guarda una definición nueva con su versión 1. `201` con la definición |
| `GET /definiciones-columnas/{id}?version=N` | La definición con todas sus versiones (sin contenido) y el contenido de la versión pedida (la vigente por defecto) |
| `POST /definiciones-columnas/{id}/versiones` | Guarda el cambio como una versión nueva, que pasa a ser la vigente. `201` |

- **Ninguna versión se modifica:** no hay `PUT`. Un cambio es una versión nueva y las anteriores quedan intactas; `usada_en` es informativo.
- **Pedido:** el mismo `DefinicionColumnasEntrada` de la previsualización (una sola forma para armar, previsualizar y guardar). En una versión nueva el `nombre` puede faltar o repetir el de la definición (sin distinguir mayúsculas); otro nombre es `400`.
- **Respuesta:** siempre expresiones, con tipos cerrados (`nodos` es una unión discriminada por `tipo`: `texto | variable`; el criterio, por `tipo`: `calculado | campo`) y las columnas por `orden`.
- **Errores:** `400` con `codigo` `definicion_invalida` y `problemas` (los mismos `ProblemaTextoRespuesta`: `columna` —posición en el pedido—, `segmento`, `campo`, ubicación de nodo, función y parámetro; C-2); `404` con `definicion_no_encontrada` o `version_no_encontrada`; `409` con `nombre_repetido`. Un `422` queda para lo que el esquema no admite (sin `columnas`, columna sin `orden` o sin `expresion`).

### Con `/archivos-carga`

- `PeticionGeneracion` acepta `definicion` (en línea, como hoy y sin cambios, RF-54) **o** `definicion_guardada` `{id, version?}` (sin versión, la vigente): **exactamente una**; si no, `400` con `codigo` `definicion_invalida` (no `422`). La definición del pedido pasó a ser opcional en el esquema.
- Con una guardada, `proteger_formulas` de la definición pasa a `OpcionesArchivo` (D4); con una en línea sigue en su valor por defecto (activa).
- **`usada_en`:** al generar el **archivo** (`POST /archivos-carga`) la versión usada queda marcada, la primera vez y sin cambiar después; la previsualización no la marca, ni una generación que falla. Solo `usada_en`: no hay tabla de usos (C-8, decisión del coordinador: nada en la interfaz la mostraría).
- Los errores de `/archivos-carga` ahora declaran `codigo` (nulo en los de siempre, y `sin_version_vigente` para una fecha sin sábana); el `detail` es el mismo de antes.

### La muestra «primeros N de una selección»

`muestra` de la previsualización gana `tipo: primeros_de_seleccion`: `fecha_corte` más `filtros` y `orden` con la sintaxis de `/cartera`, o `seleccion_id` de una selección guardada (no las dos), y `cantidad` de 1 a 5 (5 por defecto). Recorre con `SeleccionPaginada` (`seleccion_cartera/recorrido.py`), así que lleva el mismo orden y desempate por pagaré que la carga, y es de solo lectura. De una selección guardada toma sus filtros y su orden, **no su cantidad** (es una muestra). La respuesta gana `disponibles` (el total de la selección; `null` en las otras muestras). Errores: `404` `seleccion_no_encontrada` o `sin_version_vigente`; `400` (sin código) si un filtro o el orden no valen.

### Códigos nuevos

`definicion_no_encontrada`, `version_no_encontrada`, `nombre_repetido` y `seleccion_no_encontrada`, con sus claves `textoEnriquecido.codigo.*` en es y en (borradores a revisar por designer) y la prueba espejo del backend y del frontend.

### Decisiones y límites

- **Concurrencia:** una versión nueva toma el siguiente número con la fila de la definición bloqueada (`SELECT ... FOR UPDATE`) y la base impone `unique(definicion_id, numero)`.
- **Un problema de forma tapa los de contenido:** el lector estricto se detiene antes de compilar; el editor ve primero los de forma y, al corregirlos, los de contenido.
- **Una definición guardada puede quedar inválida** si cambia el catálogo de la cartera: se rechaza al generar, como una plantilla inválida (`400`), sin marcar la versión.
- **Nombres del contrato:** `VersionDefinicionRespuesta` y `DefinicionRespuesta` llevan sufijo para no chocar con `VersionRespuesta` de `/cargas`.

## 23. MOWA MES M2: el speech v2 (B6)

Estado: hecho y probado sin base (2026-10-04); las pruebas de PostgreSQL (`tests/test_mowa_mes_speech_v2_postgres.py`) están escritas y **no corridas**, y la migración `f2c8a4d7b915` la verifica architec con ida y vuelta. RF-MM-13 y la sección 6 de `requerimientos-mowa-mes.md`.

### Dos formatos que conviven

- Una versión de speech es **v1** (dos partes por segmento, como siempre) o **v2** (una expresión del motor por segmento). El formato se fija al crearla y **no cambia al editarla**: `PUT` con el otro formato es `400`. La misma regla de siempre: editable hasta que una campaña la usa (`usada_en`), inmutable después.
- `mowa_mes_speech_version` gana `formato` (`v1` por defecto, así que todo lo que existía queda v1) y `expresiones` (JSONB: lista de `{segmento, expresion}`; nula en las v1, y `partes` queda `[]` en las v2). Dos CHECK: `formato IN ('v1','v2')` y contenido según formato. El `downgrade` se niega si ya hay v2.
- **Las huellas de las v1 no cambian** (`huella_speech`, sin tocar): el Speech original sigue en `297c227c…` y la versión 92 de la base en `20990813…`. La v2 tiene la suya (`huella_expresiones`): SHA-256 sobre la forma canónica de las expresiones (`expresion_a_dict`, segmentos en el orden de `RANGOS_SEGMENTO`) con el formato `v2` por delante, así que no puede coincidir con la de una v1. `huella_de(datos)` elige según el formato. La campaña la vuelve a comprobar dentro de su transacción, así que el `409 huella_cambiada` funciona igual con una v2.

### De v1 a v2 (C-5)

`GET /mowa-mes/speech/{id}/como-v2` devuelve el **borrador** (no guarda nada): `expresion_de` por segmento, con `titular` y `fecha_vencimiento_cuota` **obligatorios**. Se guarda con `POST /mowa-mes/speech` (`expresiones`, `basada_en_id`): versión nueva con `basada_en_id` y huella propia; la v1 queda intacta. Condición de architec, con prueba sobre toda la matriz del oro (Speech original y 12 versiones sintéticas): el v2 convertido da los **mismos mensajes, largos, exclusiones y orden** que la v1 a través de `evaluar_producto`.

### Exclusiones en la v2 (decisión del usuario)

`falta_titular` y `falta_vencimiento` excluyen **solo si la expresión compilada de ese segmento usa la variable** (nodos de variable, también dentro de argumentos de función; nunca buscando texto: `services/texto_enriquecido/uso.py`). El orden no cambia (`telefono_invalido`, `falta_documento`, `sin_speech`, `falta_titular`, `falta_vencimiento`, `mensaje_excede_160`). Un segmento que no usa el titular genera su mensaje sin hueco aunque el titular venga vacío. «Vacío» es `campana._vacio`. En una v1 las dos exclusiones siguen siendo siempre.

### Previsualización (C-6)

`POST /mowa-mes/speech/previsualizacion` acepta `partes` (v1) **o** `expresiones` (v2), exactamente una. Por segmento devuelve `largo_maximo` (la cota de la expresión), `codigo` (`mensaje_excede_150`/`_160` si la cruza) y `ejemplo`. Sin cota calculable, `largo_maximo` es `null` y `sin_maximo` dice por qué (variable cuyo largo depende del dato, o función que no acota). `mensaje_excede_160` sigue excluyendo por fila sobre el mensaje real.

### Contrato

`VersionSpeechRespuesta` gana `formato` y `expresiones` (cada una con `usa_titular`, `usa_vencimiento`, `usa_whatsapp`); los pedidos de crear, editar y previsualizar aceptan `partes` o `expresiones` (XOR, `400` si vienen las dos o ninguna). `ProblemaSpeechRespuesta` gana `codigo` y `ubicacion`; el `400` es `DetalleErrorSpeech {detail, problemas}`. `SpeechCampanaRespuesta` gana `formato`. `contratos/openapi.json` y `frontend/src/lib/contrato-api.d.ts` regenerados; los mocks y pruebas del frontend que arman estas respuestas a mano (`e2e/api-falsa-mowa-mes.ts`, `e2e/mowa-mes-campana.spec.ts`, `tests/nucleo/mowa-mes*.test.ts`) fallan `tsc` hasta que F4 los adapte.

### Limpieza de M1

Se borraron `plantilla_mensaje`, `contexto_fila`, `CAMPOS_CONTEXTO` y las pruebas `test_en_vivo_*` de la prueba de oro. Siguen las constantes congeladas (`oro_mowa_mes_congelados.py`).

### Pruebas

`tests/test_mowa_mes_speech_v2.py` (núcleo: huellas, conversión sobre la matriz del oro, exclusiones en los dos sentidos, previsualización, `usa_*`), `tests/test_api_mowa_mes_speech_v2.py` (API, incluido el `409` con un v2 que cambia entre previsualizar y crear) y `tests/test_mowa_mes_speech_v2_postgres.py` (escrita, no corrida). El hueco de «campaña, reporte y conciliación con una v2» lo cierra B8: `tests/test_api_mowa_mes_conciliacion_v2.py` (en memoria, corre en todos lados) y su gemela `tests/test_mowa_mes_conciliacion_v2_postgres.py`. Mutación a mano sobre las huellas, el uso de variables, las exclusiones, la conversión, la previsualización, el servicio y la API: 72 mutantes, 68 muertos y 4 vivos. Dos son equivalentes (el borrador `como-v2` nunca trae problemas: ninguna v1 válida convierte a una v2 que el motor rechace) y dos solo los cubre la prueba de PostgreSQL sin correr (el filtro de formato al editar y la huella que comprueba la campaña dentro de su transacción).
