# Requerimientos del módulo `whatsmkt` — conector de WhatsApp de WhatsMKT

Segundo conector de plataforma del sistema y primero de WhatsApp. Aplica los requerimientos generales de gestiones digitales (RF-37 a RF-41, sección 10 de [atomics-requirements.md](atomics-requirements.md)), los de generación de cargas digitales (RF-09 a RF-15) y los del motor de texto enriquecido y el constructor de columnas (RF-42 a RF-56), y agrega las reglas propias de la plataforma.

Los requerimientos de este documento se numeran `RF-WM-XX` dentro del módulo, para no mezclar su secuencia con la global ni con la de MOWA MES (`RF-MM-XX`, [requerimientos-mowa-mes.md](requerimientos-mowa-mes.md)).

La fuente de diseño es el plan WhatsMKT v2 de architec, validado por el usuario el 2026-11-02. Las citas «decisión del usuario, 2026-11-02» son palabras del usuario en esa validación. Lo que el plan asume con un valor por defecto queda como supuesto explícito (sección 10), no como regla firme, y lo que no está ni en el plan ni en las palabras del usuario queda como duda (sección 11).

**Herramientas compartidas.** Algunas capacidades que usa este módulo no son de WhatsMKT, sino de todas las plataformas. Las define `coordinador_herramientas_implementadas` en `atomics-requirements.md` (tarea T-HI-0), y este documento solo las cita:

| Cambio del plan | Capacidad compartida | RF global |
|---|---|---|
| H-1 | Funciones `nombres` y `apellidos` del motor | RF-44, ampliado |
| H-4 | Textos guardados y versionados por contexto | RF-69 |
| H-6 | Día gestionable común, de lunes a sábado, fijo para todos los canales | RF-70 |
| H-6 | Próximos N días gestionables | RF-71 |
| H-7 | Etiqueta por columna en las definiciones | RF-49, ampliado |
| H-8 | Definiciones de columnas con plataforma | RF-72 |
| H-9 | Celda con formato «Texto» en el exportador XLSX | RF-73 |
| — | Sección «Herramientas» del menú | RF-74 |

Números acordados con `coordinador_herramientas_implementadas` el 2026-11-02.

El cambio de RF-MM-08 a lunes a sábado (D-A) lo escribe `coordinador_modulo_mowa_mes` en su documento (T-MM-0).

## 1. Plataforma, navegación y configuración

| Dato | Valor |
|---|---|
| Plataforma | WhatsMKT (whatsmkt.com) |
| Canal | WhatsApp |
| País | Perú, único (decisión del usuario, 2026-11-02, P-9) |
| Tipos de envío publicados | Texto, imagen de perfil más texto, con imagen, con audio, video o PDF, y con vCard |
| Variables por mensaje publicadas | «hasta 5 variables» (ver duda DU-WM-1) |
| API o webhooks | No publicados |

* **RF-WM-01 — Módulo propio:** Implementar WhatsMKT como un módulo de canal propio, hermano de MOWA MES y distinto de él (decisión del usuario, 2026-11-02, P-1).
  * El módulo no envía mensajes a WhatsMKT. Genera el archivo de contactos y una ficha con los datos del formulario (RF-WM-36). Un operador sube la campaña en la web de WhatsMKT y, al terminar, importa en el sistema el informe que genera WhatsMKT (RF-WM-37).
  * Si WhatsMKT ofreciera una API más adelante, se incorporaría como otro adaptador (RF-14).
  * Reutiliza las piezas comunes (selección de cartera, supervisión, calendario laboral, motor de texto enriquecido, constructor de columnas y exportadores) sin modificarlas: los cambios que necesite en ellas los pide al equipo dueño (RF-44, RF-49 y RF-69 a RF-74).
* **RF-WM-02 — Navegación del módulo:** Ofrecer el módulo en el menú como `Canales ▸ WhatsMKT ▾`, con el mismo menú desplegable que MOWA MES, y tres rutas:

  | Ruta | Sección | Para qué |
  |---|---|---|
  | `/whatsmkt/campana` | Campaña | Crear campañas |
  | `/whatsmkt/seguimiento` | Seguimiento | Importar el informe y conciliar |
  | `/whatsmkt/configuracion` | Configuración | Lo propio de WhatsMKT |

  * Fuente: «el flujo debe ser similar a MOWA-MES: Realizar 'Campañas', Registrar 'Seguimientos' y Definir 'Configuración'. Además recuerda usar la implementación de menú desplegable con un botón que se usa con el módulo de MOWA-MES para sus rutas» (decisión del usuario, 2026-11-02).
* **RF-WM-03 — Herramientas reutilizables fuera del módulo:** Usar desde WhatsMKT las pantallas comunes de Columnas de carga, Supervisores y Calendario laboral, que forman la sección «Herramientas» del menú (RF-74), en lugar de copiarlas en su Configuración.
  * Solo pasan a Herramientas las pantallas reutilizables. Lo propio de cada canal queda en la Configuración de ese canal: la de MOWA MES no se mueve (decisión del usuario, 2026-11-02).
  * El nombre «Herramientas» lo decidió `designer` (P-13).
  * La campaña y la Configuración de WhatsMKT enlazan a esas pantallas con ir y volver, como «Editar en Cartera» (RF-MM-09).
* **RF-WM-04 — Configuración de WhatsMKT:** Mantener en `/whatsmkt/configuracion` todos los valores propios de la plataforma, sin fijar ninguna regla de WhatsMKT en el código (RF-32):
  * los dos horarios de envío (RF-WM-07);
  * la tabla de segmentos y el mensaje guardado de cada uno (RF-WM-20);
  * los mensajes globales (RF-WM-19);
  * la plantilla del nombre de campaña (RF-WM-33);
  * la definición de columnas por defecto (RF-WM-09);
  * el tope de largo del mensaje (RF-WM-26);
  * los topes de tamaño de los adjuntos (RF-WM-31);
  * la biblioteca de adjuntos (RF-WM-30).

## 2. Base y programación de la campaña

* **RF-WM-05 — Base de la campaña:** Tomar como base de la campaña una selección de cartera de una fecha de corte (filtros, orden y cantidad, o una selección guardada), con el mismo orden y desempate que `/cartera` y el top n (RF-08).
  * Si se quieren cambiar los filtros, entonces la campaña ofrece «Editar en Cartera» y vuelve con la selección actualizada, sin editor de filtros propio, igual que RF-MM-09.
  * La selección queda congelada con la campaña.
  * La base es la cartera regular. Las sábanas especiales («vienen por casos específicos para nuestras asignaciones o son complementarios de cuentas que no se nos han asignado», decisión del usuario, 2026-11-02) quedan fuera de esta entrega: entran en la Fase 5 para todos los canales (D-B).
* **RF-WM-06 — Fecha de envío:** Sugerir como fecha de envío el siguiente día gestionable después de hoy en Lima (RF-55), con la misma mecánica que MOWA MES: «La programación de la gestión se hace de la misma forma que con MOWA-MES. No se puede enviar gestión únicamente los domingos» (decisión del usuario, 2026-11-02, P-3).
  * Los días de envío son de lunes a sábado (D-A, RF-70). Se excluyen los domingos, los feriados de ley y las excepciones registradas en el calendario laboral.
  * Los días de envío son fijos y comunes a todos los canales: no se configuran en WhatsMKT (RF-70).
  * La fecha mínima es mañana: hoy nunca es una fecha válida.
  * Si al crear la campaña la fecha elegida dejó de ser válida, entonces se rechaza y se devuelve la nueva fecha sugerida.
* **RF-WM-07 — Horarios de envío:** Registrar en la campaña uno o los dos horarios de envío de WhatsMKT (decisión del usuario, 2026-11-02, P-2):

  | Horario | Franja |
  |---|---|
  | Horario 1 | `08:00 - 14:00` |
  | Horario 2 | `14:00 - 20:00` |

  * La campaña debe marcar al menos uno.
  * Los horarios se definen por campaña: varias campañas pueden usar el mismo (supuesto S-WM-2).
  * Las franjas se guardan en la configuración (RF-WM-04).
* **RF-WM-08 — «Lo antes posible»:** Registrar en la campaña la casilla «Deseo que salga mi envío lo antes posible» y copiarla en la ficha (RF-WM-36).
  * El sistema no cambia la fecha ni los horarios por ella (supuesto S-WM-3).

## 3. Archivo de carga (lista de contactos)

Fuente: «al momento de generar la carga, se use el generador de columnas para archivos de carga, implementando el motor de texto enriquecido por completo, con la posibilidad de poder insertar cualquier variable proveniente de la sábana. La única diferencia sería que la primera columna del archivo de carga tendrá necesariamente el nombre 'número' y será un campo de texto enriquecido (formato texto en excel) donde por defecto será la concatenación de "51" (prefijo de números telefónicos en el Perú) y la variable de 'teléfono' de cada registro de la sábana. Luego los siguientes campos creados serán por defecto [$MARCROn$] ([$MARCRO1$], [$MARCRO2$], [$MARCRO3$], etc) donde se definirá necesariamente como campo de texto enriquecido pudiendo usar únicamente una variable o varias variables, además de poder realizar las funciones de alteración de estas variables (formatos de fecha, financiero, numero entero, numero con decimales, apellidos, nombres de titular, etc)» (decisión del usuario, 2026-11-02).

* **RF-WM-09 — Definición de columnas de plataforma WhatsMKT:** Generar el archivo de contactos con una definición de columnas guardada de plataforma `whatsmkt` (RF-51, RF-72) y con el mismo generador que «Generar carga», sin un armado propio del módulo.
  * La campaña usa por defecto la definición elegida en la configuración (RF-WM-04) y permite elegir otra de plataforma `whatsmkt`.
  * La campaña abre la definición elegida en Columnas de carga, en modo WhatsMKT, y vuelve con la versión guardada.
  * La campaña registra la versión de la definición con la que se generó.
  * El constructor muestra las reglas de RF-WM-10 y RF-WM-11 y no deja guardar una definición `whatsmkt` que las rompa. El núcleo no conoce WhatsMKT: el módulo registra sus reglas (RF-72).
  * Definición de referencia, la que reproduce el archivo del 29.10:

    | Encabezado | Etiqueta | Contenido |
    |---|---|---|
    | `número` | Número con prefijo | `51[@telefono]` |
    | `[$MARCRO1$]` | Nombres del titular | titular → `nombres` (RF-44) |
    | `[$MARCRO2$]` | Vencimiento de la cuota | `fecha_vencimiento_cuota` → fecha `dd/mm/aaaa` |
    | `[$MARCRO3$]` | Monto de la cuota | `monto_cuota` → financiero con 2 decimales |

* **RF-WM-10 — Columna `número`:** Ubicar como primera columna de toda definición `whatsmkt` la columna `número`, fija, que no se borra ni se mueve.
  * Es un campo de texto enriquecido, con valor por defecto `51[@telefono]`: el prefijo de Perú más el teléfono del producto.
  * Se escribe en una celda con formato «Texto» de Excel (RF-73), para que Excel no la deforme.
  * El encabezado es exactamente `número`, con tilde.
* **RF-WM-11 — Columnas de macro:** Tratar cada columna después de `número` como una macro de WhatsMKT, identificada por su posición: la segunda columna es la macro 1, la tercera la macro 2, y así.
  * El encabezado por defecto es `[$MARCROn$]`, según su posición (`[$MARCRO1$]`, `[$MARCRO2$]`, …), como en el archivo que funcionó y como lo pidió el usuario (supuesto S-WM-5).
  * Si se reordenan las columnas, entonces los encabezados por defecto se renumeran según su nueva posición.
  * El encabezado se puede editar, pero WhatsMKT toma las macros por orden, no por nombre (decisión del usuario, 2026-11-02, P-4).
  * Cada macro es un campo de texto enriquecido de tipo texto: una o varias variables de la sábana, base o adicionales (RF-66), un valor fijo, o una mezcla, con las funciones del motor (RF-44): formato de fecha, financiero, número entero, número con decimales, nombres y apellidos (RF-44), lista no exhaustiva, ampliable.
  * La salida es siempre texto ya formateado, no una celda de fecha o de número, para que el mensaje muestre el valor tal como se definió.
* **RF-WM-12 — Etiqueta de las columnas:** Mostrar la Etiqueta de cada columna (RF-49), por ejemplo «Nombres del titular», en el constructor y en el editor del mensaje (RF-WM-27).
  * La etiqueta no sale en el archivo.
* **RF-WM-13 — Una fila por producto:** Generar una fila por producto de la selección: «No es relevante si se repite un teléfono o cliente. Se toma en cuenta el producto» (decisión del usuario, 2026-11-02, P-7).
  * Un teléfono con dos productos sale en dos filas. No es motivo de exclusión.
* **RF-WM-14 — Supervisores en WhatsMKT:** Ubicar los registros de supervisión (RF-37 a RF-40) al inicio del archivo, antes de los productos, sin cambios respecto de la regla general (decisión del usuario, 2026-11-02, P-11).
  * `número`: `51` más el número del supervisor.
  * Las macros copian las de la primera fila de productos del archivo (RF-40). En un lote por segmento (RF-WM-23), es la primera fila de productos del archivo de esa campaña.
  * Si no hay supervisores configurados, entonces la campaña no se crea, como en MOWA MES (RF-37). La previsualización ya lo indica con el código `sin_supervisores` y no deja crear, con un enlace a Supervisores.
* **RF-WM-15 — Productos excluidos de la carga:** Excluir de la carga, y reportar con su código, cada producto que cumpla alguna de estas condiciones:
  * `sin_telefono`: no tiene teléfono;
  * `telefono_invalido`: el teléfono no es válido según RF-02;
  * `macro_vacia`: una de sus macros queda vacía y la columna no tiene valor por defecto. Así no sale un mensaje como «Hola  Caja Cusco». Si la columna tiene valor por defecto, entonces se usa ese valor y el producto no se excluye.
  * `sin_dias_atraso`: en el modo por segmento (RF-WM-18), el producto no tiene días de atraso y no cae en ningún segmento (RF-WM-20). En el modo global no es motivo de exclusión.
* **RF-WM-16 — Formato del archivo:** Generar la lista de contactos en `.xlsx`, con una sola hoja (supuesto S-WM-9).
  * Los textos pasan por la protección contra fórmulas del exportador (RF-53).
  * No se divide en varios archivos: el campo de cantidad de WhatsMKT admite 18 dígitos, así que no hay un tope práctico (RF-WM-34).
  * El archivo se conserva con la campaña: una descarga posterior entrega exactamente el mismo archivo, aunque la cartera, la definición o la configuración hayan cambiado.

## 4. Mensaje

Fuente: «El campo de mensaje es un solo bloque, WhatsMKT ya hace el reemplazo de los textos internamente.» y «Las variables con [$MACROn$] son columnas después del número en el archivo de carga a la plataforma. Estos datos provienen de campos de las sábanas o un valor en específico (contemplar ambas posibilidades). Esto, junto con el mensaje que se carga, la plataforma construye el mensaje reemplazando las referencias de [$MACROn$] por el valor del archivo de carga.» (decisiones del usuario, 2026-11-02).

* **RF-WM-17 — Mensaje de un solo bloque:** Registrar el mensaje de la campaña como un único bloque de texto plano, con marcadores `[$MACROn$]` que WhatsMKT reemplaza por el valor de la macro n de cada fila, es decir, la columna n + 1 del archivo (RF-WM-11).
  * El sistema no compila ni reemplaza el mensaje: lo guarda, lo valida (RF-WM-24 a RF-WM-26) y lo muestra para copiarlo en WhatsMKT (RF-WM-36).
  * El marcador del mensaje es `[$MACROn$]`, como en los speeches del usuario (supuesto S-WM-6).
* **RF-WM-18 — Segmentación del mensaje:** Permitir redactar el mensaje de la campaña de una de estas dos formas: «según la segmentación de rangos de 'segmento financiero actual' según el 'día de atraso', o una segmentación global por filtro (es decir, al realizar los filtrados, ya se sobreentiende que todos van a tener el mismo speech)» (decisión del usuario, 2026-11-02).
  * **Global:** un solo mensaje para toda la selección, que da una sola campaña de WhatsMKT. Es el modo de las campañas especiales.
  * **Por segmento:** un mensaje por segmento de WhatsMKT (RF-WM-20), que da un lote de campañas (RF-WM-23).
* **RF-WM-19 — Mensajes guardados y versionados:** Guardar los mensajes de WhatsMKT como textos guardados y versionados del contexto `whatsmkt.mensaje` (RF-69), con crear, versionar, renombrar, deshabilitar y eliminar si no se usó (decisión del usuario, 2026-11-02, P-12).
  * Hay un mensaje por segmento (RF-WM-20) y los mensajes globales que se quieran, para las campañas especiales.
  * Cada campaña registra la versión del mensaje y una copia de su texto. Si después cambia el mensaje, entonces la campaña conserva el que usó.
  * Si una versión ya se usó en una campaña, entonces no se modifica: el cambio crea una versión nueva.
* **RF-WM-20 — Segmentos de WhatsMKT:** Asignar cada producto a un segmento de WhatsMKT según sus días de atraso ajustados a la fecha de envío (RF-55), con una tabla de segmentos propia del módulo:

  | Segmento | Días de atraso ajustados |
  |---|---|
  | Preventivo | `dias_ajustados <= 0` |
  | Tramo 2 | `1 <= dias_ajustados <= 8` |
  | Tramos mayores al 2 | `dias_ajustados >= 9`, sin tope |

  * Los límites son los del supuesto S-WM-1 y se editan en la configuración (RF-WM-04).
  * La tabla es propia de WhatsMKT: cambiarla no altera los segmentos del speech de MOWA MES (RF-MM-15).
  * Los rangos no se superponen y cubren todos los días de atraso, así que ningún producto queda sin segmento.
* **RF-WM-21 — Mensajes iniciales de los segmentos:** Sembrar como versión 1 del mensaje de cada segmento el speech dado por el usuario, textual (decisión del usuario, 2026-11-02):
  * Preventivo:

    ```
    Hola [$MACRO1$] Caja Cusco te informa que tu cuota vence  el [$MACRO2$] , pague puntualmente en nuestras agencias, agentes  KASNET o a través de Wayki app. Si ya pagaste, omite este mensaje. INFO por [whatsapp]
    ```

  * Tramo 2:

    ```
    Hola [$MACRO1$] Caja Cusco te informa que tu cuota venció el [$MACRO2$] , ponte al día, te invitamos a pagar en nuestras agencias, agentes KASNET o a través de Wayki app. Si ya pagaste, omite este mensaje. INFO por [whatsapp]
    ```

  * Tramos mayores al 2, el que usó la campaña del 29.10 (P-5):

    ```
    Hola [$MACRO1$] Caja Cusco te informa que tu cuota venció el [$MACRO2$] , evita estar mal calificado en el sistema financiero, el monto de tu cuota es [$MACRO3$] , acércate a pagar a nuestras agencias , agentes KASNET y/o canales alternativos. INFO por [whatsapp]
    ```

  * Los espacios dobles («vence  el», «agentes  KASNET») y los espacios antes de una coma se conservan tal como vienen, hasta que el usuario decida (duda DU-WM-2).
  * `[whatsapp]` reemplaza aquí el enlace `https://wa.me/+51…` con el número de WhatsApp de contacto que trae el speech original. El número real no se escribe en el repositorio (regla de datos sintéticos, `AGENTS.md`), ni en este documento ni en la siembra. Cómo entra a los mensajes es la duda DU-WM-11.
* **RF-WM-22 — Mensaje de la campaña:** Elegir al crear la campaña el mensaje guardado que usa: en modo global, un mensaje global o el de un segmento; en modo por segmento, el de cada segmento, que por defecto es su mensaje de la configuración.
  * Una versión deshabilitada no se ofrece, y crear o previsualizar una campaña con ella se rechaza con el motivo.
* **RF-WM-23 — Lote de campañas por segmento:** Si el modo es por segmento, entonces crear una campaña de WhatsMKT por cada segmento que tenga productos, porque cada campaña de WhatsMKT lleva un solo mensaje.
  * Cada campaña del lote tiene su archivo, su mensaje, su nombre (RF-WM-33) y su cantidad (RF-WM-34).
  * Las campañas del lote se crean juntas, con un identificador de lote común: o se crean todas, o ninguna.
  * Un segmento sin productos no genera campaña.
  * Si ningún segmento tiene productos, después de las exclusiones, entonces no se crea nada y se informa el motivo.
* **RF-WM-24 — Mensaje sin emojis:** Rechazar el mensaje que contenga emojis: «mensaje solo texto, sin emoticons» (decisión del usuario, 2026-11-02, P-14).
  * Se rechazan los pictogramas, el unificador de ancho cero (ZWJ) y los selectores de variante, con una lista explícita de rangos.
  * Las tildes, la `ñ`, la `ü` y los signos `¿` y `¡` se aceptan.
  * El rechazo indica la posición del primer carácter rechazado.
* **RF-WM-25 — Macros del mensaje contra las columnas:** Rechazar el mensaje si contiene un `[$MACROn$]` cuya macro n no existe en la definición de columnas elegida.
  * Ejemplo: con una definición de 3 macros, `[$MACRO4$]` se rechaza.
  * Una macro de la definición que el mensaje no usa no es un error.
* **RF-WM-26 — Largo del mensaje:** Mostrar un contador de caracteres del mensaje y rechazar el que pase el tope configurado: «con el largo que define WhatsApp» (decisión del usuario, 2026-11-02, P-14).
  * El tope inicial es de 4096 caracteres (supuesto S-WM-7).
  * El largo se mide sobre el mensaje tal como se guarda, con los marcadores sin reemplazar (duda DU-WM-3).
* **RF-WM-27 — Editor del mensaje:** Ofrecer en el editor del mensaje botones que insertan `[$MACROn$]` mostrando su etiqueta (por ejemplo, «MACRO2 · Vencimiento de la cuota») y una vista previa que reemplaza las macros con los valores de las primeras filas, como lo hará WhatsMKT.

## 5. Envío, adjuntos y ficha

* **RF-WM-28 — Tipo de envío:** Registrar el tipo de envío de la campaña:
  * Solo texto.
  * Texto + archivo: imagen, video, audio o PDF, elegido de la biblioteca (RF-WM-30).
  * Texto + vCard, con la etiqueta del contacto (duda DU-WM-4).
  * Los campos de cada tipo se muestran solo cuando ese tipo está elegido. Al cambiar de tipo se conserva lo escrito, pero solo se envía lo del tipo elegido.
* **RF-WM-29 — Foto de perfil:** Registrar la foto de perfil de la campaña, elegida de la biblioteca de adjuntos (RF-WM-30).
  * La foto debe ser JPEG de 200 × 200 píxeles, medido en el propio archivo, y pesar hasta 1 MB. Si no cumple, entonces se rechaza con el motivo.
  * Si la foto es obligatoria en toda campaña es la duda DU-WM-5.
* **RF-WM-30 — Biblioteca de adjuntos:** Guardar en la base de datos la foto y los adjuntos que se suben, en una biblioteca del módulo, para elegirlos en cualquier campaña y volver a descargarlos desde cualquier equipo: «la foto y los adjuntos se suben en cada carga y deben quedar guardados en la plataforma» (decisión del usuario, 2026-11-02, P-8).
  * Si se sube un archivo idéntico a uno de la biblioteca, comparado por su huella SHA-256, entonces se reutiliza el existente y no se guarda dos veces.
  * Un adjunto se archiva en lugar de borrarse: deja de ofrecerse en las campañas nuevas, y las campañas que lo usaron lo conservan.
  * Cada campaña registra la foto y el adjunto que usó.
* **RF-WM-31 — Validación de los adjuntos:** Validar cada archivo al subirlo:
  * el tipo se reconoce por la firma del archivo, no por la extensión;
  * el tamaño se controla antes de leer el archivo completo;
  * los topes de video, audio y PDF son configurables (RF-WM-04), con el valor inicial del supuesto S-WM-8. Los límites reales de WhatsMKT no se conocen (P-8).
  * el tope de las imágenes es fijo, de 5 000 000 bytes, el máximo de imagen de WhatsApp (duda DU-WM-13).
* **RF-WM-32 — Limpieza de metadatos:** Quitar los metadatos de las imágenes al guardarlas, sin perder calidad (P-8): no se vuelve a codificar la imagen, solo se quitan bloques del archivo.
  * JPEG: se quitan los segmentos EXIF y XMP (APP1), IPTC (APP13) y los comentarios. El perfil de color (APP2) y los datos de la imagen quedan byte a byte.
  * Del EXIF se conserva solo la orientación, en un APP1 mínimo: sin ella, una foto de celular tomada en vertical se vería girada, y la orientación no es un dato personal. Si la foto no trae orientación, si vale «normal» o si el EXIF es ilegible, no queda ningún APP1 (duda DU-WM-12).
  * PNG: se quitan los bloques de texto, `eXIf` y `tIME`.
  * Si el archivo está truncado o mal formado, entonces se rechaza.
  * Video, audio y PDF se guardan tal como llegan: limpiarlos exigiría herramientas externas y queda fuera de esta entrega.
* **RF-WM-33 — Nombre de la campaña:** Proponer el nombre de cada campaña con una plantilla editable de texto fijo y variables entre llaves, definida por defecto en la configuración y editable al crear la campaña, como el nombre de archivo de MOWA (RF-MM-25) (decisión del usuario, 2026-11-02, P-15).
  * Variables: la fecha de corte y el segmento (vacío en una campaña global). El resto de las variables es la duda DU-WM-6.
  * La plantilla por defecto reproduce la forma del nombre usado el 29.10: `CUZCO_Vencida (<filtros>) whatsapp AAAA.MM.DD`, de 75 caracteres (duda DU-WM-6).
  * Largo máximo: 75 caracteres (decisión del usuario, 2026-11-02, P-14). La pantalla no deja escribir más de 75 y muestra cuántos van. Si el nombre resultante pasa de 75, entonces no se deja crear la campaña hasta acortarlo.
  * Si una variable de la plantilla no existe, entonces se rechaza al guardarla, indicando cuál.
* **RF-WM-34 — Cantidad de teléfonos declarada:** Calcular la cantidad que se declara en el campo «¿Cuántos teléfonos tiene en su Lista de contactos?» de WhatsMKT como las filas del archivo, incluidos los supervisores (supuesto S-WM-4).
  * El campo de WhatsMKT admite hasta 18 dígitos (`maxlength="18"`, P-14).
* **RF-WM-35 — Previsualización de la campaña:** Mostrar antes de crear, por cada campaña que resultará: el segmento, la cantidad, las exclusiones con su código, una muestra de filas con sus macros y un mensaje de ejemplo con las macros reemplazadas.
  * La muestra y las exclusiones se paginan con el paginador compartido, sin volver a calcular, como RF-MM-26.
  * Muestra los problemas de validación del mensaje (RF-WM-24 a RF-WM-26) y de la definición (RF-WM-09).
* **RF-WM-36 — Ficha «Para subir a WhatsMKT»:** Al crear la campaña, mostrar una ficha por cada campaña del lote con cada dato del formulario de WhatsMKT y su valor listo para copiar, y el archivo para descargar, como «Para subir a MES» (RF-MM-35):

  | Campo de WhatsMKT | De dónde sale |
  |---|---|
  | Nombre de campaña | RF-WM-33 |
  | Fecha y horarios | RF-WM-06 y RF-WM-07 |
  | Lo antes posible | RF-WM-08 |
  | País | Perú, fijo (P-9) |
  | Foto de perfil | RF-WM-29, para descargar |
  | Lista de contactos | El `.xlsx` de la campaña (RF-WM-16) |
  | ¿Cuántos teléfonos tiene en su Lista de contactos? | RF-WM-34 |
  | Tipo de envío | RF-WM-28, con su adjunto para descargar o la etiqueta de la vCard |
  | Texto del mensaje | El mensaje de la campaña (RF-WM-22), con un botón para copiarlo |

  * La campaña recién creada enlaza a su seguimiento.

## 6. Seguimiento y conciliación

* **RF-WM-37 — Importar el informe de WhatsMKT:** Permitir importar en una campaña el informe que genera WhatsMKT al terminar, que es el único formato (decisión del usuario, 2026-11-02, P-10), validando su estructura:

  | Fila | Contenido |
  |---|---|
  | 1 | `FECHA` y la fecha del informe (`dd-mm-aaaa`) |
  | 2 | `TOTAL DE ENVIO` y el total informado |
  | 4 | Encabezados `CAMPAÑA`, `TIPO DE ENVIO`, `NUMERO` |
  | 6 en adelante | Una fila por número enviado |

  * La hoja observada se llama `Informe`. Las filas vacías se ignoran.
  * Se guardan la fecha y el total informados y los números.
  * Si falta un encabezado o no hay filas de detalle, entonces se rechaza con el motivo.
  * Si el total informado no coincide con las filas de detalle, entonces se muestran los dos valores (duda DU-WM-7).
  * El formato del archivo se reconoce por su contenido y se lee con el lector de tablas común, como el reporte de MOWA (RF-MM-20).
  * Si la campaña está descartada, entonces se rechaza: hay que restaurarla primero, como en MOWA (RF-MM-31).
* **RF-WM-38 — Reemplazo del informe:** Si la campaña ya tiene un informe importado, entonces pedir confirmación antes de reemplazarlo, y no guardar nada si no se confirma.
* **RF-WM-39 — Conciliación por número:** Conciliar a nivel de producto las filas cargadas con el informe, usando el número como clave: un producto cuenta como enviado si su número aparece en el informe.
  * Resultado por campaña: cargados, enviados, no enviados y números del informe sin correspondencia en la carga.
  * Si un número cubre dos productos, entonces el envío cuenta para los dos (P-7).
  * Los números se comparan como texto de dígitos. El informe no sigue el orden de la carga: la conciliación es por conjuntos.
  * Los registros de supervisión se concilian y se muestran aparte de los productos (RF-41).
  * El nombre de campaña que trae el informe solo se muestra: no sirve como clave, porque se escribe a mano en WhatsMKT (el del 29.10 dice `CUZCO` donde el archivo dice `CUSCO`).
* **RF-WM-40 — Lista de campañas:** Mostrar en el seguimiento las campañas activas, paginadas, con filtros, con su lote, su segmento, su fecha de envío y su estado de conciliación, y descargar de nuevo su archivo.
  * Se señalan las campañas que todavía no tienen informe importado, con el paso siguiente, como RF-MM-33.
* **RF-WM-41 — Descartar una campaña:** Permitir descartar una campaña desde el seguimiento como operación lógica, con las mismas reglas que RF-MM-31: no se borra nada, sale de todos los cálculos del módulo y pide confirmación.
* **RF-WM-42 — Campañas descartadas:** Mostrar las campañas descartadas en una sección propia, donde se pueden ver, restaurar y eliminar definitivamente, con las mismas reglas que RF-MM-32.
  * Eliminar definitivamente no borra los adjuntos de la biblioteca ni las versiones del mensaje que usó.

## 7. Interfaz

* **RF-WM-43 — Retroalimentación de la validación:** Validar cada campo de la campaña y de la configuración al salir de él, y de nuevo al crear.
  * Los errores se muestran por su código (`whatsmkt.codigo.*`), traducidos, con la frase del servidor como respaldo.
  * Al fallar, el foco va al primer error.
* **RF-WM-44 — Accesibilidad y diseño:** Construir las pantallas del módulo con controles nativos, con las ayudas asociadas a su campo, y que pasen el análisis de accesibilidad en tema claro y oscuro, a 1280 y a 360 px.
  * Las tablas de conciliación se apilan en celular desde el inicio.
  * Usa los tokens de diseño del proyecto y los iconos con el criterio de RF-MM-36. Los textos llevan el visto bueno de `designer`.

## 8. Decisiones tomadas

| Punto | Decisión | Fuente |
|---|---|---|
| Canal propio o dentro de MOWA (P-1) | Módulo propio, distinto de MOWA MES (RF-WM-01) | Decisión del usuario, 2026-11-02 |
| Flujo y menú | Campaña, Seguimiento y Configuración, con el desplegable de MOWA MES (RF-WM-02) | Decisión del usuario, 2026-11-02 |
| Qué pasa a Herramientas | Solo lo reutilizable; lo de cada canal queda en su Configuración (RF-WM-03) | Decisión del usuario, 2026-11-02 |
| Nombre y orden del menú (P-13) | Los decide `designer`: la sección compartida se llama «Herramientas», y WhatsMKT va en Canales con su desplegable (RF-WM-02, RF-WM-03) | Decisión del usuario, 2026-11-02; nombre de `designer` |
| Horarios (P-2) | Horario 1 `08:00 - 14:00` y Horario 2 `14:00 - 20:00` (RF-WM-07) | Decisión del usuario, 2026-11-02 |
| Programación (P-3) | Como MOWA MES; solo los domingos no se envía (RF-WM-06) | Decisión del usuario, 2026-11-02 |
| Sábados (D-A) | WhatsMKT y MOWA envían de lunes a sábado (RF-WM-06, RF-70; RF-MM-08 lo cambia T-MM-0) | Decisión del usuario, 2026-11-02 |
| Sábanas especiales (P-6, D-B) | Fuera de esta entrega; Fase 5 para todos los canales (RF-WM-05) | Decisión del usuario, 2026-11-02 |
| Archivo de MOWA (D-C) | Pasa al constructor en esta entrega; lo especifica MOWA, no este documento | Decisión del usuario, 2026-11-02 |
| Cómo se arma el archivo | Con el constructor de columnas y el motor completo; `número` primero, macros después (RF-WM-09 a RF-WM-11) | Decisión del usuario, 2026-11-02 |
| Macros (P-4) | Encabezados que se fijan por orden; campo Etiqueta en el constructor (RF-WM-11, RF-WM-12) | Decisión del usuario, 2026-11-02 |
| Mensaje | Un solo bloque; WhatsMKT reemplaza las macros (RF-WM-17) | Decisión del usuario, 2026-11-02 |
| Segmentación del mensaje | Por segmento según los días de atraso, o global por filtro (RF-WM-18) | Decisión del usuario, 2026-11-02 |
| Speech de la campaña del 29.10 (P-5) | El de tramos mayores al 2 (RF-WM-21) | Decisión del usuario, 2026-11-02 |
| Teléfono o producto (P-7) | Cuenta el producto: una fila por producto (RF-WM-13, RF-WM-39) | Decisión del usuario, 2026-11-02 |
| Foto y adjuntos (P-8) | Se guardan en el sistema, sin metadatos y sin perder calidad; límites desconocidos (RF-WM-29 a RF-WM-32) | Decisión del usuario, 2026-11-02 |
| País (P-9) | Solo Perú (sección 1) | Decisión del usuario, 2026-11-02 |
| Informe (P-10) | El que genera WhatsMKT al terminar, único formato (RF-WM-37) | Decisión del usuario, 2026-11-02 |
| Supervisores (P-11) | Sin cambios (RF-WM-14) | Decisión del usuario, 2026-11-02 |
| Mensajes guardados (P-12) | Textos guardados y versionados, compartidos (RF-WM-19, RF-69) | Decisión del usuario, 2026-11-02 |
| Nombre, mensaje y cantidad (P-14) | Nombre de hasta 75 caracteres; mensaje solo texto, sin emojis, con el largo de WhatsApp; cantidad con `maxlength="18"` (RF-WM-24, RF-WM-26, RF-WM-33, RF-WM-34) | Decisión del usuario, 2026-11-02 |
| Nombre de campaña (P-15) | Plantilla editable, como RF-MM-25 (RF-WM-33) | Decisión del usuario, 2026-11-02 |

## 9. Evidencia de los ejemplos

Los ejemplos están en `data/whatsmkt/`, que **no se versiona** (`.gitignore`) porque contiene datos de cobranza. Lo que sigue son solo agregados y formas, sin ningún valor personal.

**Archivo de carga** (`CUSCO_Vencida WhatsMKT Whatsapp 2026.10.29.xlsx`):

- Una hoja, `Hoja1`, con 105 filas y 4 columnas: `número`, `[$MARCRO1$]`, `[$MARCRO2$]` y `[$MARCRO3$]`. El encabezado escribe `MARCRO`; los speeches del usuario escriben `MACRO` (supuestos S-WM-5 y S-WM-6).
- `número`: texto de 11 dígitos, `51` más 9 dígitos que empiezan en 9. Una celda quedó guardada como número: es el riesgo de que Excel la deforme (RF-WM-10).
- 104 números distintos: un teléfono con dos productos aparece en dos filas (RF-WM-13).
- Los 5 supervisores ocupan las filas 1 a 5 y repiten las macros de la primera fila de cliente (RF-WM-14).
- Origen, cruzado con la cartera vigente del 29.10: `número` es `51` más el teléfono; `[$MARCRO1$]`, los nombres del titular (lo que va después de la coma); `[$MARCRO2$]`, la fecha de vencimiento de la cuota, en una celda de fecha; `[$MARCRO3$]`, el monto de la cuota, en una celda de número con 1 o 2 decimales. Las tres macros coinciden en 100 de 100 productos.
- No tiene columna de mensaje: el texto se escribe en el formulario de WhatsMKT.

**Informe** (`CUSCO_Vencida Reporte_Gestiones_Digitales whatsapp p 2026.10.29.xlsx`):

- Una hoja, `Informe`, con la estructura de RF-WM-37: `FECHA` en la fila 1, `TOTAL DE ENVIO` (101) en la fila 2, encabezados en la fila 4 y 101 filas de detalle desde la 6.
- `CAMPAÑA`: un solo valor, el nombre escrito en WhatsMKT, que describe la selección y dice `CUZCO` donde la carga dice `CUSCO`. `TIPO DE ENVIO`: `CAMPAÑA DE IMAGEN + TEXTO`. `NUMERO`: 11 dígitos.
- No trae estado por número ni hora: es la lista de los enviados.
- De los 104 números distintos de la carga, 101 se enviaron y 3 no; ningún número del informe falta en la carga, y el número repetido se envió una vez. La carga es del corte 29.10 y el envío fue el 30.10.

## 10. Supuestos por confirmar con el usuario

Vienen del plan v2 (S-1 a S-9). No frenan el desarrollo: cada uno se corrige con una línea de configuración o con la respuesta del usuario.

| Supuesto | Qué se asumió | Dónde aplica |
|---|---|---|
| S-WM-1 | Los segmentos se calculan con los días de atraso ajustados: preventivo hasta 0 días, tramo 2 de 1 a 8 (el `2. 1 a 8` de `segmento_financiero`) y mayores al 2 desde 9, sin tope | RF-WM-20 |
| S-WM-2 | Los horarios son por campaña: una campaña marca uno o los dos, y otras pueden usar el mismo | RF-WM-07 |
| S-WM-3 | «Lo antes posible» solo se guarda y se copia en la ficha | RF-WM-08 |
| S-WM-4 | La cantidad declarada son las filas del archivo, con los supervisores (105 el 29.10) | RF-WM-34 |
| S-WM-5 | La Etiqueta es descriptiva y no sale en el archivo. El encabezado sigue siendo `[$MARCROn$]`, como en el archivo que funcionó y como lo pidió el usuario | RF-WM-11, RF-WM-12 |
| S-WM-6 | En el mensaje, el marcador es `[$MACROn$]`, como en los speeches del usuario. `[&MACROn&]` de P-3 y P-4 se toma como errata | RF-WM-17 |
| S-WM-7 | El tope del mensaje es configurable y empieza en 4096 caracteres, el largo de un mensaje de WhatsApp. No es un dato verificado de WhatsMKT | RF-WM-26 |
| S-WM-8 | Los topes de video, audio y PDF son configurables y empiezan en 16 MB, el límite general de WhatsApp para multimedia. No es un dato verificado de WhatsMKT | RF-WM-31 |
| S-WM-9 | La lista se genera en `.xlsx`. El CSV ya lo tiene el exportador; el `.xls`, no | RF-WM-16 |

## 11. Dudas para el usuario

No están en el plan v2 ni en las decisiones del 2026-11-02. Mientras no se respondan, el RF citado aplica la regla escrita entre paréntesis, que es la más conservadora.

| Duda | Pregunta | Dónde aplica |
|---|---|---|
| DU-WM-1 | WhatsMKT publica «hasta 5 variables» por mensaje, y el pedido dice que no hay una cantidad fija de macros. ¿Se limita la definición a 5 macros o se deja libre? (Libre.) | RF-WM-11, RF-WM-25 |
| DU-WM-2 | Los speeches traen espacios dobles («vence  el», «agentes  KASNET») y espacios antes de una coma («[$MACRO2$] ,», «agencias ,»). ¿Se normalizan al sembrarlos, o se dejan tal cual? (Tal cual.) | RF-WM-21 |
| DU-WM-3 | ¿El tope de largo se mide sobre el mensaje con los marcadores o sobre el mensaje ya reemplazado con los valores más largos de las filas? (Con los marcadores.) | RF-WM-26 |
| DU-WM-4 | En «texto + vCard», ¿qué datos lleva la vCard (nombre, teléfono, otros) y de dónde salen? (Solo la etiqueta del contacto, escrita en la campaña.) | RF-WM-28 |
| DU-WM-5 | ¿La foto de perfil es obligatoria en toda campaña? ¿De dónde sale la regla de JPEG de 200 × 200 y 1 MB: del formulario de WhatsMKT? (Opcional; si se elige, debe cumplir esa regla.) | RF-WM-29 |
| DU-WM-6 | Para la plantilla del nombre: ¿se agrega una variable con el resumen de los filtros (la parte entre paréntesis del 29.10) y la fecha de envío? ¿El texto fijo dice `CUZCO` o `CUSCO`? Si el lote tiene varias campañas y la plantilla no usa el segmento, ¿se agrega el segmento al final para que no se repitan los nombres? (Solo fecha de corte y segmento; se agrega el segmento al final.) | RF-WM-33 |
| DU-WM-7 | Si el `TOTAL DE ENVIO` del informe no coincide con sus filas de detalle, ¿se rechaza el informe o solo se advierte? (Se muestran los dos valores, sin rechazar.) | RF-WM-37 |
| DU-WM-8 | ¿Se confirma el formato de las macros en el mensaje: fecha `15/10/2026` y monto `1,234.50`, sin `S/`? En el archivo del 29.10 eran una celda de fecha y una de número. (Ese formato, editable en la definición.) | RF-WM-09 |
| DU-WM-9 | ¿Se registra una tarifa por mensaje y un costo por campaña, o un límite mensual, como en MOWA MES (RF-MM-01, RF-MM-23, RF-MM-24)? (No, en esta entrega.) | Sección 6 |
| DU-WM-10 | ¿Cómo se nombra el archivo de contactos que se descarga? El del 29.10 se llamaba `CUSCO_Vencida WhatsMKT Whatsapp 2026.10.29.xlsx`. (El nombre de la campaña más `.xlsx`, con los caracteres no válidos en Windows cambiados por `_`.) | RF-WM-16 |
| DU-WM-11 | El speech original trae el enlace de WhatsApp de contacto de la Caja dentro del texto, pero el número real no puede guardarse en el repositorio, ni en la siembra de B3. ¿Cómo entra? (a) Como en MOWA (RF-MM-16): un número de contacto en la configuración de WhatsMKT, que el sistema pone en lugar de `[whatsapp]` al mostrar y copiar el mensaje; sin número configurado, no se crea una campaña cuyo mensaje lo use. (b) La v1 se siembra con `[whatsapp]` literal, y el usuario lo cambia por el enlace al editar el mensaje en la configuración. (Provisional: (a), el patrón ya probado en MOWA; se decide antes de B3.) | RF-WM-21 |
| DU-WM-12 | Al limpiar un JPEG, ¿se conserva la orientación del EXIF (que la foto no se vea girada) o se quita todo el EXIF, como decía RF-WM-32? (Se conserva solo la orientación; todo lo demás, incluido el GPS, se quita.) | RF-WM-32 |
| DU-WM-13 | La configuración no tiene tope para las imágenes. ¿Se agrega como los de video, audio y PDF, o queda fijo? (Fijo, de 5 000 000 bytes, el máximo de imagen de WhatsApp; no está verificado en WhatsMKT.) | RF-WM-31 |

## 12. Registro de cambios

**2026-11-02**
- **RF nuevos incorporados:** RF-WM-01 a RF-WM-44, documento nuevo (T-WM-0b), a partir del plan WhatsMKT v2 y de las decisiones del usuario del 2026-11-02.
- **RF existentes ampliados o modificados:** ninguno en este documento. Cita los RF globales RF-44 y RF-49 (ampliados) y RF-69 a RF-74 (nuevos), que escribe T-HI-0, y el cambio de RF-MM-08 a lunes a sábado (T-MM-0), que escriben sus dueños.
- **Supuestos nuevos:** S-WM-1 a S-WM-9 (los S-1 a S-9 del plan). **Dudas nuevas:** DU-WM-1 a DU-WM-13.
- **Nota de numeración:** secuencia propia del módulo, continua y sin huecos. Los RF que se agreguen después continúan la secuencia sin renumerar los existentes, como en MOWA MES.
- **RF existentes ampliados:** RF-WM-21: el enlace de WhatsApp de contacto de los speeches pasa a `[whatsapp]`, porque el número real no puede estar en el repositorio (la prueba `test_datos_sinteticos` lo detectó en `main`). DU-WM-11 se reescribe con las dos opciones.
- **RF existentes ampliados:** RF-WM-31 (tope fijo de las imágenes) y RF-WM-32 (del EXIF se conserva solo la orientación), según lo implementado en T-WM-B5. **Dudas nuevas:** DU-WM-12 y DU-WM-13.
- **RF existentes ampliados:** RF-WM-14 (sin supervisores configurados no se crea la campaña, código `sin_supervisores`) y RF-WM-15 (exclusión `sin_dias_atraso` en el modo por segmento), según las decisiones de la entrega de T-WM-B2, con los textos de designer.
