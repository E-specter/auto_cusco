# Diagnóstico del motor de texto enriquecido (2026-11-04)

Encargo del usuario (2026-11-04), por `architec`: «Quiero que se aplique de mejor manera en WhatsMKT y que sea una herramienta reutilizable, intuitiva y cómoda de usar». El pedido nombra el constructor de archivos de carga («no se ha implementado, o no correctamente») y el speech por segmento de MOWA MES («aún sigue siendo limitado»).

Este documento es el paso 1: solo diagnóstico, sin código. Se hizo sobre `main` 8a90258 con el código, la interfaz aprobada (`motor-texto-enriquecido-interfaz.md` §2 a §5) y la revisión de uso de `designer`. **No se recorrió el navegador con la cartera real:** la regla de datos personales lo impide. Lo que solo se ve con la sábana real va marcado como «a confirmar por el usuario».

## 1. Qué hay hoy

| | Columnas de carga | Speech por segmento (MOWA MES) | Mensaje de WhatsMKT |
|---|---|---|---|
| Editor | `EditorTexto`, el editor de piezas (§2) | El mismo, con un editor por segmento (`VariantesSegmento`) | Un `textarea` plano (F1b2) |
| Variables | Contexto `cartera`: los 44 campos base de la sábana, la fecha de envío, los días ajustados y los campos adicionales | Contexto `mowa_mes.speech`: solo 4 (titular, vencimiento de la cuota, WhatsApp de contacto, días ajustados) más los adicionales | Ninguna. Botones que insertan `[$MACROn$]` y `[whatsapp]` |
| Funciones | Las 26 del motor (texto, número, conversión, fecha, nulos y enlaces) | Las mismas 26 | Ninguna: las aplica cada columna macro de la definición |
| Cómo se inserta | «+ Variable», un buscador agrupado por origen y el panel de la pieza para las funciones | Igual | Un botón por macro |
| Vista previa | Registro de ejemplo o producto real (fecha y pagaré a mano) | Igual, y además el segmento | «Fila 1, 2 y 3» de la definición |

Los nombres visibles y las descripciones de las 26 funciones existen en es y en, y las cubre una prueba espejo. El catálogo de variables base sale del de la sábana (`CATALOGO_VENCIDA`), así que **todas las columnas de la sábana con valor están ofrecidas en Columnas**. A confirmar por el usuario: si echa de menos alguna columna concreta de su sábana real, o un campo derivado que no existe hoy, por ejemplo «nombres del titular» como variable propia y no como función.

## 2. Brechas frente al pedido

1. **Campos de la sábana en el speech de MOWA.** El contexto ofrece 4 variables y no los 44 campos. Es la causa del «limitado». El usuario lo lee como «el editor no deja», y el buscador no explica por qué falta un campo. Cerrarlo toca el backend de MOWA: el contexto y la generación del speech, que hoy pasan solo esas 4 y los adicionales. Los adicionales ya usan el mecanismo de pasar el campo por nombre, así que extenderlo es acotado.
2. **Funciones en el mensaje de WhatsMKT.** El mensaje no tiene variables ni funciones. Para «Nombres del titular, en mayúsculas», hay que ir a Columnas de carga, crear una columna macro y volver. Es el punto central del pedido.
3. **Descubrible e intuitivo**, según la revisión de `designer`:
   - Insertar va contra la mano. «+ Variable» queda lejos de donde se escribe, no hay disparador al escribir (`[@`) ni autocompletar, e inserta al final sin avisar si nunca hubo foco.
   - El buscador agrupa por origen y no por tema (persona, cuota, deuda, fechas). Con 46 variables, la lista es larga, y no muestra un valor de ejemplo.
   - Las funciones van en un `select`, y su descripción aparece recién al elegirla. La cadena muestra solo el resultado final, y el error de un parámetro no dice su rango.
   - Las píldoras con funciones crecen y la frase deja de leerse. La línea parece un campo de una fila.
   - Pegar un texto con marcadores lo deja plano.
   - «Producto real» pide la fecha y el pagaré a mano.
4. **Reutilizable en los tres sitios.** Hay dos modelos para lo mismo:
   - el WhatsApp es una variable en MOWA y un marcador en WhatsMKT;
   - hay tres vistas previas y tres contadores distintos;
   - hay dos patrones de error.

   El editor es uno, pero WhatsMKT no lo usa.

Lo que **no** es brecha: el motor (las expresiones, sus funciones, la validación en su lugar y el largo) está completo y probado. El trabajo es de oferta de variables, de uso y de llevarlo a WhatsMKT, no de reescribir el motor.

## 3. Opciones

### Opción 1 — Mínima: el speech completo y el disparador al escribir

- **Qué es:**
  - el speech de MOWA ofrece todos los campos de la cartera, como Columnas (brecha 1);
  - el editor común suma `[@` para abrir el buscador donde está el cursor, más un valor de ejemplo en cada variable.
  - WhatsMKT sigue como hoy, con macros e ir y volver al constructor.
- **A favor:** cierra el «limitado» de MOWA. Es poco código: un contexto, la generación del speech y un disparador en el editor.
- **En contra:** no cumple «de mejor manera en WhatsMKT», que es el centro del pedido.
- **Costo:** bajo, con 2 cortes: uno de backend de MOWA y uno de frontend del editor.
- **Riesgo:** bajo. MOWA revisa la generación con su prueba de oro.

### Opción 2 — Recomendada: el editor común mejorado y WhatsMKT con píldoras que crean macros

- **Qué es,** en dos fases:
  - **Fase A, el editor común, sirve a los tres sitios:**
    - todo lo de la opción 1;
    - el buscador por tema, con un valor de ejemplo;
    - la descripción y el resultado de cada función antes de elegirla;
    - el error de parámetro con su rango;
    - un solo contador «n / tope» y un solo patrón de error.
  - **Fase B, el mensaje de WhatsMKT con el editor de piezas.** Insertar «Nombres del titular · mayúsculas» crea en la definición elegida una columna macro con esa expresión, o **reusa** una con la misma variable y las mismas funciones. El mensaje sigue guardando `[$MACROn$]`, que es lo que espera la plataforma (RF-WM-17). Para que el usuario no se pierda, según `designer`:
    - la píldora muestra la variable y su función, y la macro es un dato secundario («Columna 3 del archivo, `[$MACRO3$]`»);
    - al insertar, un aviso: «Se agregó la columna 3…» o «Usa la columna 2, que ya lleva lo mismo»;
    - un solo guardado, con un resumen antes de confirmar: «Mensaje Preventivo, versión 2; Contactos WhatsMKT, versión 4, columna 3 nueva». Por dentro primero se guarda la definición y después el mensaje, así una falla no deja un mensaje que apunte a una macro inexistente;
    - editar la función de una píldora cuya columna usan otros mensajes crea una columna nueva y lo avisa. Un mensaje nunca altera a otro;
    - quitar la píldora no borra la columna. La configuración marca qué mensajes usa cada macro;
    - el constructor sigue para lo avanzado (el formato de celda o el número fijo), con su ir y volver.
- **A favor:** cumple los tres pedidos con un solo editor y deja de obligar a ir al constructor para lo común. Respeta cómo funciona WhatsMKT: las macros son columnas por posición.
- **En contra:** es lo más caro, porque la fase B toca el mensaje, la definición y su versionado juntos. La definición puede crecer con columnas casi iguales, aunque reusar la columna idéntica lo mitiga.
- **Costo:** alto. La fase A son 2 o 3 cortes. La fase B, 2 o 3 más, con `designer` en la especificación y la revisión §13 de MOWA para el editor común.
- **Riesgo:** medio. Lo principal es el doble guardado (definición y mensaje) y el reuso de columnas compartidas. Se acota con el orden de guardado y con la regla de «columna nueva si otro mensaje la usa».

### Opción 3 — Intermedia: el editor común mejorado y el constructor en un panel lateral del mensaje

- **Qué es:** la fase A de la opción 2. En WhatsMKT, «Agregar macro» abre el constructor de la definición en un panel lateral, sin salir del mensaje. Al guardar la columna, la macro queda insertada en el cursor.
- **A favor:** reusa el constructor tal cual, sin una lógica nueva de crear o reusar columnas. Es más barato que la fase B.
- **En contra:** el usuario sigue viendo dos herramientas (mensaje y columnas) para una sola idea, y el mensaje sigue mostrando `[$MACRO3$]` en vez de lo que significa.
- **Costo:** medio-alto, con 3 o 4 cortes.
- **Riesgo:** medio-bajo.

**Recomendación:** la opción 2, por fases. La fase A primero, porque mejora los tres sitios y ya cierra el «limitado» de MOWA. La fase B después, sobre esa base. Si el costo de la fase B no se justifica todavía, la opción 3 es el paso intermedio razonable, y no tira nada de la fase A.

## 4. Preguntas para el usuario (reglas de WhatsMKT que no se inventan)

1. **Tope de macros (DU-WM-1).** WhatsMKT publica «hasta 5 variables» por mensaje. ¿Se limita a 5 por mensaje o por definición? Con píldoras que crean columnas, el tope se avisaría al insertar la sexta.
2. **El WhatsApp de contacto.** En WhatsMKT es el marcador `[whatsapp]`, que cuenta como el enlace fijo de 26 caracteres. ¿Puede pasar a ser una variable, como en MOWA, o `[whatsapp]` tiene que quedar literal en el mensaje que se sube?
3. **Una macro compartida por varios mensajes.** ¿Está bien que varios mensajes de la misma definición usen la misma columna macro? ¿O cada mensaje debe tener sus propias columnas?
4. **Campos que echa de menos.** ¿Hay alguna columna de su sábana o algún dato derivado que no encuentre hoy en Columnas de carga? Solo se puede confirmar con la sábana real.
5. **El speech de MOWA con todos los campos.** ¿Lo quiere así? Hoy MOWA excluye un producto si le falta el titular o el vencimiento. ¿Un campo nuevo usado en el speech sigue la regla «Obligatoria» del motor (RF-45)?
</content>
</invoke>
