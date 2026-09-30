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
- **Compilar una vez, aplicar muchas.** Validar tipos y resolver funciones al compilar; por fila, solo aplicar funciones ya resueltas. Sin expresiones regulares por fila.
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

**Definiciones guardadas** (decisión del usuario): con nombre único normalizado y versiones. Una versión usada en una carga no se modifica: se crea otra. Son compartidas entre usuarios y módulos, siguiendo el patrón de selecciones guardadas y del speech.

## 9. Exportación y seguridad de la salida

La definición no conoce el formato. Los exportadores reciben la tabla ya generada, como hoy.

**Inyección de fórmulas** (decisión del usuario):

- **XLSX:** todo valor de texto se escribe como texto literal, aunque empiece con `=`, `+`, `-` o `@`. No se ejecuta y el contenido no cambia. Los números y las fechas se escriben con su tipo nativo, como hoy. **Es la única excepción a RF-54:** hoy un texto como `=1+1` se escribe como fórmula viva, también en los archivos de MOWA MES; ahora se escribe como texto. El resto del archivo queda idéntico byte a byte, y una prueba lo comprueba (ajustes D6 y D7).
- **CSV:** por defecto, un texto que empieza con `=`, `+`, `-`, `@`, tabulación o retorno de carro lleva un apóstrofo delante. **No se protegen los valores que no son texto ni los textos que son solo un número** (`^[+-]?\d[\d.,]*$`): un importe negativo (`-1,234.56`) o `+51987654321` no son fórmulas, y el apóstrofo rompería la plataforma. Un texto como `-2+3` sí se protege (ajuste D5, aprobado por architec como precisión de la decisión del usuario). Cada definición puede apagar la protección (`proteger_formulas: false`). La opción viaja en `OpcionesArchivo`, porque los exportadores no conocen la definición (precisión D4).
- **JSON:** sin cambios. Se escribe con `ensure_ascii=False`, en UTF-8.
- **Textos y canal:** UTF-8 en todo el camino. Los saltos de línea se conservan: el módulo CSV los entrecomilla y el XLSX los guarda en la celda. Cada plataforma declara si los admite; si no, la previsualización lo advierte.

## 10. Contrato backend ↔ frontend

La forma exacta la fija el backend en `contratos/openapi.json`, como siempre. Este es el acuerdo de diseño:

| Endpoint | Para qué |
|---|---|
| `GET /texto-enriquecido/catalogo?contexto=` | Variables del contexto con su tipo, y funciones con parámetros, tipos y claves i18n. La interfaz arma los menús con esto |
| `POST /texto-enriquecido/validacion` | Recibe una expresión y un contexto. Devuelve los problemas con su ubicación (nodo, función, parámetro) y código, el tipo resultante y la cota de largo si existe |
| `POST /texto-enriquecido/previsualizacion` | Recibe una expresión o una definición, y un registro: el ejemplo del catálogo o un producto real (fecha de corte y pagaré). Devuelve el resultado total y el de cada nodo, y los problemas de fila |
| `GET, POST /definiciones-columnas`, `GET /definiciones-columnas/{id}`, `POST /definiciones-columnas/{id}/versiones` | Definiciones guardadas y versionadas |
| `/archivos-carga` | Acepta una definición guardada (id y versión) o una en línea, como hoy |
| `/mowa-mes/speech` | Acepta versiones en formato v2 (una expresión por segmento) sin dejar de leer las v1 |

- **Errores:** los 400 extienden `DetalleError` con `codigo` (catálogo `CodigoTexto`) y `ubicacion`, según la regla de `contrato-api.md` §3.
- **i18n:** `textoEnriquecido.codigo.*`, con una prueba espejo entre el catálogo del backend y el i18n, como la de `CodigoMowaMes`.
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
