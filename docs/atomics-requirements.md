# Requerimientos funcionales — Sistema de gestión de cobranzas / cartera

## 1. Carga y procesamiento de sábanas diarias

* **RF-01 — Carga de archivos:** Permitir la carga de las sábanas diarias al sistema mediante archivos estructurados.
* **RF-02 — Validación y normalización de datos:** Procesar automáticamente los archivos durante la carga para validar, normalizar y estandarizar los datos según las reglas de negocio definidas.
  * Validar formatos de documentos de identidad: **DNI, RUC, extranjero, etc.**
  * Validar números telefónicos según el formato establecido: **9 dígitos e inicio con 9**.
  * Detectar inconsistencias, datos inválidos y registros que no cumplan las reglas de validación.
* **RF-03 — Gestión de cartera:** Permitir identificar, registrar, actualizar y omitir productos de la cartera en función de la información contenida en las sábanas cargadas.
* **RF-57 — Formatos de archivo de la sábana:** Aceptar la sábana en Excel (`.xlsx`, `.xlsb`, `.xls`), ODS, CSV y JSON.
  * Excel y ODS: si el libro tiene varias hojas, el usuario elige cuál cargar; por defecto, `VENCIDA` si existe y, si no, la primera.
  * CSV: se detectan el separador (coma, punto y coma o tabulación) y la codificación (UTF-8, con o sin BOM; Windows-1252, la del Excel en español; o Latin-1 si Windows-1252 no la decodifica). El usuario puede cambiarlos, y el análisis de RF-58 se repite con lo elegido. La primera fila no vacía es la de encabezados.
  * JSON: una lista de objetos; cada clave es un encabezado, en el orden en que aparece por primera vez. Si el archivo no es una lista de objetos, entonces se rechaza indicando el motivo. Si un valor es un objeto o una lista, entonces se guarda como texto y se registra una advertencia en esa fila.
* **RF-58 — Análisis de encabezados antes de cargar:** Antes de procesar la sábana, mostrar cada encabezado del archivo con hasta 3 valores de ejemplo y su relación con los campos de carga, sin importar el orden de las columnas.
  * Cada encabezado tiene uno de cuatro estados: **recordado** (RF-61), **coincide**, **parecido** o **sin coincidencia**.
  * **Coincide:** el encabezado normalizado (sin tildes, en minúsculas y con los espacios colapsados) es igual al nombre de un campo o a uno de sus alias.
  * **Parecido:** no coincide, pero su similitud con un campo supera un umbral configurable (RF-32); se sugiere el campo más parecido que no esté ya asignado. Si dos campos empatan, entonces no se sugiere ninguno.
* **RF-59 — Asignación de campos:** Permitir elegir, para cada encabezado, el campo de carga al que corresponde, en una lista con todos los campos por su nombre legible y la opción «No cargar esta columna».
  * Los encabezados recordados y los que coinciden llegan con su campo elegido. Los parecidos llegan con el campo sugerido elegido y marcados para revisar. Los que no tienen coincidencia llegan en «No cargar esta columna».
  * Una acción acepta de una vez todas las sugerencias parecidas.
  * **Búsqueda en la lista (2026-10-27):** la lista de campos de cada encabezado permite escribir para filtrarla. La búsqueda no distingue mayúsculas ni tildes y compara contra el nombre legible del campo y sus alias. «No cargar esta columna» queda siempre disponible. Si nada coincide, entonces se indica que no hay campos con ese texto, sin cambiar la elección vigente. Se maneja por completo con el teclado y un lector de pantalla anuncia la opción activa y la cantidad de resultados (RF-34).
  * Un campo ya asignado a otro encabezado aparece en la lista pero no se puede elegir, con el encabezado que lo usa a la vista.
* **RF-60 — Validación del mapeo:** No permitir confirmar la carga mientras haya un parecido sin revisar, un campo obligatorio sin columna (hoy, el pagaré) o dos encabezados asignados al mismo campo. Cada problema se muestra en el encabezado que lo causa.
  * Las columnas en «No cargar esta columna» se conservan en el registro crudo de cada fila, como las columnas desconocidas de hoy.
* **RF-61 — Mapeo recordado:** Guardar cada asignación confirmada (encabezado normalizado → campo, o «No cargar») y aplicarla en las cargas siguientes como **recordado**.
  * Un mapeo recordado tiene prioridad sobre la coincidencia por nombre o alias.
  * Si el usuario confirma una asignación distinta para ese encabezado, entonces se reemplaza la recordada.
* **RF-62 — Trazabilidad del mapeo:** Guardar con cada versión de la sábana el mapeo con el que se procesó y el origen de cada asignación (recordado, coincide, parecido aceptado o manual).
* **RF-63 — Mapeador reutilizable:** Implementar el mapeador de RF-57 a RF-62 como una capacidad transversal, que cualquier carga de archivos tabulares pueda usar con su propio catálogo de campos (nombre, nombre legible, alias, tipo y si es obligatorio), sin modificar el mapeador.
  * Los mapeos recordados (RF-61) se guardan por catálogo: lo que se recuerda para la sábana no se aplica a otro catálogo.
  * La sábana es el primer catálogo. Otros candidatos, cuando se decida usarlo en ellos: el reporte de enviados de MOWA MES y las fuentes de reportes de la Fase 5.

* **RF-64 — Crear un campo adicional desde el mapeo:** Permitir crear, desde el formulario de mapeo de RF-58 a RF-60, un **campo adicional** del catálogo a partir de un encabezado del archivo que no corresponde a ningún campo existente.
  * Un **campo adicional** es un campo de la cartera que no viene en el catálogo base de la sábana: lo crea el usuario porque Caja Cusco agregó una columna en la que quiere enfocar la gestión.
  * Al final del formulario de mapeo hay una referencia visible para crearlo. Se elige el encabezado de origen (uno sin coincidencia o en «No cargar esta columna»), un **nombre legible** y un **tipo**: `texto`, `número` o `fecha`.
  * El nombre legible es obligatorio y único en el catálogo: no puede repetir el nombre ni un alias de otro campo, comparados como en RF-58. Si se repite, entonces se rechaza indicando con qué campo choca.
  * El sistema deriva un nombre técnico estable a partir del nombre legible; ese nombre no cambia aunque después se renombre el campo.
  * Al crearlo, el encabezado de origen queda asignado al campo nuevo en ese mismo mapeo, y se recuerda como en RF-61.
  * Un campo adicional es siempre opcional: nunca bloquea una carga por faltar (RF-60).
  * Si un valor de la columna no se puede convertir al tipo elegido, entonces ese valor queda vacío y se registra una advertencia en su fila, como el resto de la normalización (RF-02). La carga no se rechaza por eso.
* **RF-65 — Vigencia de los campos adicionales:** Mantener los campos adicionales en el catálogo de la sábana para todas las cargas siguientes.
  * La próxima sábana que traiga ese encabezado lo relaciona sola con el campo adicional (recordado, RF-61).
  * Si una sábana no trae la columna, entonces el campo queda vacío en esa versión, sin error. Las versiones cargadas antes de crear el campo también lo tienen vacío.
  * El nombre legible se puede cambiar después; las selecciones, los indicadores y las definiciones guardadas que lo usan siguen funcionando, porque lo referencian por su nombre técnico (RF-64).
  * **Decidido por el usuario el 2026-10-27:** el tipo no se cambia después de creado; para otro tipo se crea otro campo. Un campo adicional no se borra: se **archiva**. Deja de ofrecerse en las listas y en el mapeador, no se borra ningún dato, su nombre técnico no se reutiliza y se puede reactivar. Lo que ya lo usa (selecciones, definiciones guardadas, speech) sigue funcionando y muestra un aviso.
* **RF-66 — Uso transversal de los campos adicionales:** Ofrecer cada campo adicional en todas las capacidades que trabajan con los campos de la cartera, con el mismo trato que un campo del catálogo base.
  * Como mínimo: filtros y segmentación de la selección (RF-05, RF-06), indicadores adicionales (RF-27; suma, promedio, mínimo y máximo solo si el tipo es `número`), variables de texto (RF-43) y columnas de carga (RF-49), con sus funciones según el tipo (RF-44).
  * Todas esas capacidades obtienen los campos de una sola fuente, el catálogo de campos de la cartera. Una capacidad nueva que use ese catálogo recibe los campos adicionales sin código específico para ellos (RF-31, RF-32, RF-63).
  * En pantalla, un campo adicional se muestra con su nombre legible y se distingue como adicional, con la misma accesibilidad que los demás campos (RF-34).

## 2. Selección y segmentación de productos

* **RF-04 — Selección de productos:** Permitir seleccionar los productos correspondientes a la asignación del día de gestión.
* **RF-05 — Filtrado avanzado:** Permitir aplicar filtros simples y complejos sobre los productos mediante múltiples criterios configurables.
* **RF-06 — Análisis por criterios:** Permitir segmentar y analizar los productos seleccionados según diferentes atributos y reglas de negocio.
* **RF-07 — Control de gestiones:** Permitir consultar y filtrar los productos según su historial de gestiones, incluyendo la validación de si han recibido gestiones durante el **mes actual**.
  * Para efectos de este control, se considera "gestión" a cualquier contacto realizado a través de **llamadas VoIP, SMS, WhatsApp, correo electrónico** u otro canal de contactabilidad que se incorpore posteriormente. El historial de gestiones debe consolidar eventos de todos estos canales, no solo de uno.
* **RF-08 — Selección por cantidad definida ("top n"):** Permitir al usuario ingresar un valor numérico **"n"** mediante un input, para seleccionar automáticamente los primeros "n" productos de la lista final presentada (con filtros aplicados o sin ellos), respetando el ordenamiento vigente de dicha lista.
  * La selección debe tomar los registros desde la posición 1 hasta la posición "n" según el orden final mostrado.
  * **Condición de insuficiencia:** si la cantidad de productos disponibles es menor que "n", el sistema debe seleccionar únicamente los disponibles y mostrar una indicación explícita de que la cantidad disponible es insuficiente respecto al "n" solicitado.

## 3. Generación de cargas para plataformas digitales

* **RF-09 — Generación de tablas de carga:** Permitir generar tablas de carga personalizadas a partir de los productos seleccionados mediante los filtros y criterios previamente configurados.
* **RF-10 — Configuración de cargas por plataforma:** Permitir generar archivos de carga para diferentes plataformas de contacto digital, tales como:
  * SMS.
  * WhatsApp.
  * Correo electrónico.
  * Otras plataformas futuras.
* **RF-11 — Reglas de transformación:** Permitir configurar y modificar las condiciones, reglas de negocio, estructura y transformación de datos necesarias para cada plataforma.
* **RF-12 — Reglas de mapeo y expresión de campos:** Permitir definir, campo por campo, la forma en que se construye cada valor del archivo de carga, mediante expresiones configurables. Esta regla aplica de forma transversal tanto a las cargas de plataformas digitales (sección 3) como a las cargas VoIP (sección 4). Debe soportar como mínimo:
  * **Valores fijos/constantes:** por ejemplo, `anexo_agente = 1010`.
  * **Concatenación de texto con campos de origen** (referenciados con notación `[@nombre_campo]`): por ejemplo, `campo_info = "documento=" + [@documento]`.
  * **Concatenación de prefijos/sufijos con campos de origen:** por ejemplo, `numero = "51" + [@telefono]`.
  * **Parseo/tipado explícito por campo**, incluyendo como mínimo:
    * `fecha`, con formato de fecha configurable.
    * `numero`.
    * `texto`.
    * `financiero`, con separadores de miles y decimales configurables (por ejemplo, `","` y `"."`).
* **RF-13 — Soporte de formatos:** Permitir generar archivos en diferentes formatos según los requerimientos de cada plataforma:
  * `XLSX`
  * `CSV`
  * `JSON`
  * Otros formatos que puedan incorporarse posteriormente.
* **RF-14 — Arquitectura modular de integraciones:** Diseñar el módulo de generación de cargas bajo un enfoque **modular y extensible**, de manera que sea posible incorporar nuevas plataformas, modificar formatos o actualizar reglas de transformación sin afectar el núcleo del sistema.
* **RF-15 — Flujo de generación:** Habilitar la generación de las cargas inmediatamente después de completar el proceso de selección y filtrado de productos.

## 4. Cargas para plataformas de llamadas VoIP

* **RF-16 — Preparación de cargas VoIP:** Permitir generar las estructuras de datos requeridas por las plataformas de llamadas **VoIP**.
* **RF-17 — Composición de cargas:** Permitir construir las cargas a partir de múltiples tablas y archivos de origen, aplicando las reglas de mapeo y expresión de campos definidas en **RF-12**.
* **RF-18 — Estructura específica:** Adaptar automáticamente las cargas a las **cabeceras, campos, estructuras y formatos** requeridos por cada plataforma VoIP.
* **RF-19 — Configuración por plataforma:** Mantener independientes las reglas de generación de cada plataforma para facilitar su mantenimiento y evolución.

## 5. Reportes y trazabilidad

* **RF-20 — Reportes de gestión:** Permitir generar reportes sobre la evolución de los productos y sus gestiones.
* **RF-21 — Seguimiento de atributos:** Permitir analizar la evolución de cada campo o atributo de los productos contenidos en las sábanas, optimizando el procesamiento mediante la siguiente clasificación:
  * **Campos variables:** campos cuyo valor puede cambiar entre sábanas; sobre estos se ejecuta el análisis de evolución/comparación.
  * **Campos invariables:** campos que no cambian; se excluyen del análisis de evolución para no saturar el procesamiento, pero igualmente se almacenan.
  * En todos los casos, **se debe almacenar la información completa** recibida, sin importar la clasificación del campo.
  * El sistema debe reconocer y marcar los **campos de interés interno de la entidad**, es decir, aquellos campos que la entidad (origen de las sábanas) señala como relevantes para su propio seguimiento, para priorizarlos en el análisis y en los reportes.
* **RF-22 — Historial evolutivo de cuentas:** Permitir consultar, por cuenta/producto, el **historial evolutivo** de los campos clasificados como variables (según RF-21), mostrando los cambios de valor a lo largo del tiempo/las sucesivas sábanas.
* **RF-23 — Control de presencia:** Permitir identificar y reportar si un determinado producto, registro o atributo aparece o no en las diferentes sábanas y procesos.
* **RF-24 — Reportes especializados:** Implementar un módulo de reportes que contemple lo siguiente:
  * **Tipos de reporte:** reconocer que existen (a) formatos de reporte ya establecidos/estándar y (b) formatos nuevos solicitados de manera ocasional.
  * **Definición desde interfaz gráfica:** permitir crear y configurar definiciones de reporte mediante interfaz gráfica, sin requerir desarrollo, tanto para formatos estándar como para solicitudes ocasionales.
  * **Reutilización:** permitir guardar las definiciones de reporte creadas para generarlas nuevamente en el futuro.
  * **Fuentes de datos variables:** el módulo debe poder construir reportes a partir de distintas fuentes, incluyendo como mínimo:
    * Las sábanas cargadas al sistema.
    * Reportes descargados desde las plataformas de contactabilidad una vez enviadas las cargas (por ejemplo, reportes de campañas de SMS, WhatsApp, correo electrónico).
    * Reportes de gestiones de VoIP, ya sean manuales, progresivas o predictivas.

## 6. Métricas y analítica de selección

* **RF-25 — Métricas dinámicas:** Mostrar métricas calculadas en tiempo real a partir de los productos resultantes de los filtros y selecciones realizados por el usuario.
* **RF-26 — Indicadores de selección:** Mostrar, como mínimo, los siguientes indicadores:
  * **Total de capital.**
  * **Cantidad total de cuentas.**
  * **Cantidad de cuentas por segmento financiero**: segmento 1, 2, 3, 4, etc.
  * **Monto de cuota mínima.**
  * **Monto de cuota máxima.**
  * Otros indicadores que puedan definirse posteriormente.
* **RF-27 — Indicadores adicionales configurables:** Permitir agregar indicadores adicionales definidos por el usuario a partir de los campos disponibles, calculados mediante **funciones simples** (por ejemplo: suma, conteo, promedio, mínimo, máximo). Debe evitarse el uso de funciones o cálculos complejos que puedan saturar el procesamiento en tiempo real.
* **RF-28 — Actualización de métricas:** Actualizar automáticamente las métricas (incluyendo los indicadores adicionales de RF-27) cuando el usuario modifique los filtros, criterios o selección de productos.

## 7. Diseño modular y extensible

* **RF-29 — Modularidad:** Diseñar las funcionalidades de procesamiento, filtrado, generación de cargas, integraciones y reportes como módulos independientes.
* **RF-30 — Arquitectura de puertos/adaptadores con vertical slicing:** Implementar la arquitectura del sistema bajo el siguiente enfoque:
  * **Inputs/outputs y adaptadores:** cada módulo debe exponer entradas y salidas bien definidas, delegando la integración con sistemas externos (plataformas digitales, VoIP, CRM, bases de datos) a adaptadores independientes y sustituibles.
  * **Vertical slicing interno:** organizar el código internamente por funcionalidad/caso de uso de extremo a extremo (por ejemplo: "generar carga SMS", "generar reporte especializado"), en lugar de organizarlo únicamente por capas técnicas, de modo que cada módulo sea autocontenible, fácil de mantener y de extender sin impactar a los demás.
* **RF-31 — Extensibilidad:** Permitir incorporar nuevas plataformas, formatos, reglas de negocio y tipos de reporte sin requerir modificaciones significativas en los módulos existentes.
* **RF-32 — Configurabilidad:** Priorizar la configuración de reglas, formatos y criterios sobre valores rígidos en el código fuente.
* **RF-33 — Evolución del producto:** La solución deberá estar preparada para soportar cambios en las plataformas externas, nuevos formatos de archivos y modificaciones en las reglas de negocio.

## 8. Experiencia de usuario e interfaz

* **RF-34 — Interfaz intuitiva y clara:** El diseño y la interfaz gráfica del sistema (selección, filtros, configuración de cargas, métricas, reportes) deben ser intuitivos y limpios, priorizando la claridad en la presentación de la información sobre cualquier otro criterio estético.

## 9. Documentación y entorno de trabajo con agentes de IA

* **RF-35 — Centro de documentación técnica:** Mantener el directorio **`/docs`** como el repositorio central de la documentación técnica del proyecto (especificaciones, arquitectura, documentación de módulos y reglas de negocio), tanto general como específica de cada módulo.
* **RF-36 — Espacio de trabajo multi-agente:** Mantener el subdirectorio **`/docs/agents`** como espacio de trabajo dedicado para agentes de inteligencia artificial, permitiendo que múltiples agentes —de distintos proveedores (Anthropic, OpenAI, Google u otros modelos)— puedan operar y coordinarse sobre el mismo proyecto a partir de esta documentación compartida.

## 10. Gestiones digitales: registros de supervisión

Reglas transversales a toda **plataforma digital** (SMS, WhatsApp, correo y futuras, según RF-10). Los requerimientos propios de cada plataforma viven en su documento de módulo; el primero es [requerimientos-mowa-mes.md](requerimientos-mowa-mes.md).

* **RF-37 — Registros de supervisión en campañas digitales:** Permitir inyectar, en la carga de cada campaña digital, un conjunto de registros de control dirigidos a supervisores, para que la gestión les llegue como si fueran productos de la cartera y puedan monitorear el envío real.
  * Aplica a toda carga generada según RF-09 y RF-10, sea cual sea la plataforma digital.
  * Si la selección de la campaña no tiene productos que se puedan cargar, entonces no se generan registros de supervisión ni carga.
* **RF-38 — Configuración de supervisores por campaña:** Mantener una lista de supervisores por defecto, donde cada supervisor define su **número de contacto** y su **procedencia** (tag interno), y permitir ajustarla en cada campaña antes de generar la carga.
  * Distribución por defecto: **5 registros, 3 de procedencia `Caja Cusco` y 2 de procedencia `nuestra empresa`**.
  * Procedencias iniciales: `Caja Cusco` y `nuestra empresa` (lista no exhaustiva, ampliable).
  * La campaña guarda la lista de supervisores con la que se generó, aunque la lista por defecto cambie después.
  * Los números de los supervisores se cargan desde la configuración; no se fijan en el código (RF-32).
* **RF-39 — Documento asignado a los registros de supervisión:** Asignar a cada registro de supervisión un DNI no real, secuencial desde `00000001`, que solo sirve para permitir la carga y su seguimiento.
  * Orden de asignación: primero los supervisores de procedencia `Caja Cusco` y luego los de `nuestra empresa`, cada grupo en el orden de la lista de la campaña.
  * Con la distribución por defecto: `00000001`–`00000003` → `Caja Cusco`; `00000004`–`00000005` → `nuestra empresa`.
  * Si la campaña cambia la cantidad de supervisores, la secuencia se extiende o se acorta siguiendo el mismo orden.
* **RF-40 — Campos de carga de los registros de supervisión:** Completar los campos de carga de cada registro de supervisión que no sean su número ni su documento (por ejemplo, `mensaje`) tomando como plantilla **la primera fila válida de los productos filtrados** de la campaña.
  * "Primera fila válida" es la primera, según el orden vigente de la selección (RF-08), que quedó dentro de la carga después de aplicar las exclusiones propias de la plataforma.
* **RF-41 — Inclusión en la carga y en el seguimiento:** Anexar los registros de supervisión a la carga de la campaña e incluirlos en el resumen y el seguimiento de mensajes cargados y enviados.
  * Si la carga se divide en varios archivos por los límites de la plataforma, entonces los registros de supervisión van en el **primer archivo**.
  * El resumen muestra por separado los productos de la cartera y los registros de supervisión, además del total.
  * La posición exacta de los registros dentro del primer archivo la fija cada plataforma en su documento de módulo.

## 11. Motor de texto enriquecido y constructor de columnas dinámicas

Capacidad transversal que amplía RF-12: la usan todas las cargas digitales y VoIP, y el primer consumidor es el speech de MOWA MES. El diseño técnico está en [motor-texto-enriquecido.md](motor-texto-enriquecido.md).

* **RF-42 — Composición de textos:** Permitir construir un texto combinando texto fijo, variables y funciones que transforman las variables, para usarlo como valor de una columna de carga.
  * El texto fijo puede tener cualquier carácter UTF-8 y saltos de línea, y nunca se interpreta como variable ni como función.
  * La notación `[@nombre_campo]` de RF-12 sigue siendo válida y produce el mismo resultado que hoy.
* **RF-43 — Variables disponibles:** Ofrecer como variables los campos de la cartera y las variables de contexto que aporte el módulo que usa el motor, cada una con su tipo (`texto`, `numero`, `fecha` o `booleano`).
  * Ejemplos de variables de contexto: número de WhatsApp de contacto, fecha de envío, días de atraso ajustados y segmento calculado (lista no exhaustiva, ampliable por cada módulo).
* **RF-44 — Catálogo de funciones:** Mantener un catálogo de funciones aplicables en cadena a una variable, que como mínimo cubra:
  * Texto: primeros y últimos N caracteres, mayúsculas y minúsculas, recorte y limpieza de espacios, quitar tildes, reemplazo literal y relleno a la izquierda.
  * Número: sumar, restar, multiplicar y dividir por un valor fijo o por otra variable; redondeo; formato con separador de miles y cantidad de decimales.
  * Fecha: sumar o restar días (fijos o de otra variable) y formato configurable con marcas legibles (`dd`, `mm`, `aaaa`).
  * Conversión de texto a número, de texto a fecha y de número o fecha a texto.
  * Enlace de WhatsApp: un prefijo configurable, por defecto `https://wa.me/+51`, más el teléfono de una variable, validado según RF-02.
  * Valor alternativo cuando la variable está vacía.
  * Se pueden agregar funciones nuevas sin modificar el núcleo del motor (RF-14).
* **RF-45 — Valores vacíos:** Definir el resultado cuando falta un dato.
  * Si una variable está vacía, entonces su parte del texto queda vacía y el resto del texto se conserva (como en RF-12), salvo que se aplique la función de valor alternativo.
  * Una variable puede marcarse como obligatoria: si falta, la fila se informa con el nombre de la variable, y el módulo decide si la excluye o la reporta como error.
  * Una columna puede tener un valor por defecto para cuando todo su resultado queda vacío.
* **RF-46 — Validación al guardar:** Validar cada texto al guardarlo: que las variables existan, que las funciones existan, que sus parámetros sean válidos y que cada función reciba el tipo que admite.
  * Si hay un problema, entonces se rechaza indicando en qué parte del texto está (variable, función o parámetro), antes de procesar ninguna fila.
* **RF-47 — Previsualización:** Mostrar el resultado de un texto aplicado a un registro de ejemplo o a un producto real de la cartera, antes de guardarlo o de generar la carga.
  * Cuando el texto se puede acotar, se muestra también el largo máximo que puede alcanzar (por ejemplo, para el límite de caracteres de un SMS).
* **RF-48 — Seguridad de las expresiones:** Procesar los textos como estructuras declarativas con un conjunto cerrado de funciones, sin ejecutar código escrito por el usuario (`eval` ni equivalentes), y con límites de tamaño que se validan al guardar.
* **RF-49 — Constructor de columnas:** Permitir definir N columnas de salida para una carga, cada una con nombre, orden, tipo de dato, formato, valor por defecto opcional y su contenido: una variable directa o un texto compuesto según RF-42.
  * Una columna de variable directa conserva el valor original (fecha o importe) sin pasarlo por texto, como en RF-12.
* **RF-50 — Segmentación de las columnas:** Permitir que el contenido de una columna varíe según el segmento de cada producto, con un contenido por segmento y uno por defecto opcional.
  * **Criterio por defecto: segmento financiero calculado** a partir de los días de atraso del producto, ajustados a la fecha de envío según RF-55, con una tabla de rangos y etiquetas configurable. No se usa por defecto el campo de segmento financiero de la sábana, porque llega mal cargado (decisión del usuario, 2026-09-29).
  * **Tabla de rangos por defecto:** la del speech de MOWA MES (RF-MM-15), que es la que está en uso: `Preventiva` (hasta 0 días), `1 a 8`, `9 a 30`, `31 a 60`, `61 a 90` y `91 a 120` (decisión del usuario, 2026-10-19). La partición del campo de la sábana (1–8, 9–15, 16–30, 31–60 y 61–90) no es la por defecto.
  * También se puede usar como criterio el valor de un campo de la cartera, incluido el segmento financiero de la sábana.
  * Si un producto no cae en ningún segmento, entonces se excluye con su motivo o se usa el contenido por defecto, según lo que declare la definición.
* **RF-51 — Definiciones guardadas y versionadas:** Guardar las definiciones de columnas con un nombre, compartidas entre usuarios y módulos, y versionarlas: una versión usada en una carga no se modifica, un cambio crea una versión nueva.
* **RF-52 — Exportación independiente de la definición:** Exportar la tabla generada a XLSX, CSV o JSON (RF-13) sin que la definición de columnas dependa del formato.
* **RF-53 — Protección contra fórmulas en la exportación:** Evitar que un valor exportado se ejecute como fórmula al abrir el archivo.
  * XLSX: los textos se escriben siempre como texto literal, sin cambiar su contenido.
  * CSV: un texto que empieza con `=`, `+`, `-`, `@`, tabulación o retorno de carro lleva un apóstrofo delante. La protección está activa por defecto y cada definición puede desactivarla si la plataforma de destino no la tolera.
  * No se protegen los valores que no son texto ni los textos que son solo un número, con o sin signo (por ejemplo, `-1,234.56` o `+51900000001`): no son fórmulas y el apóstrofo rompería la plataforma.
  * JSON: sin cambios.
* **RF-54 — Compatibilidad con lo existente:** Incorporar el motor sin cambiar el resultado de las cargas actuales.
  * Las definiciones con `[@campo]` de `/archivos-carga` generan lo mismo que antes.
  * El speech de MOWA MES (RF-MM-14 a RF-MM-19) se representa con el motor produciendo exactamente los mismos mensajes y largos; las versiones existentes, incluido el Speech original, se siguen leyendo y siguen siendo inmutables.
  * **Excepciones, por seguridad (RF-53):** son las únicas dos, y solo afectan a los textos que empiezan con un carácter de fórmula; el resto del archivo no cambia.
    * XLSX: un texto que antes se escribía como fórmula viva (por ejemplo `=1+1`) ahora se escribe como texto, con el mismo contenido.
    * CSV: un texto que empieza con `=`, `+`, `-`, `@`, tabulación o retorno de carro, y que no es solo un número, ahora lleva un apóstrofo delante (por ejemplo `=SUMA(A1)` o `@usuario`), salvo que la definición desactive la protección.
  * **Cambio decidido por el usuario (2026-10-19), fuera de esas dos excepciones:** el `mensaje` de MOWA MES sale normalizado a GSM-7 (RF-MM-27), así que deja de ser idéntico al de antes del motor cuando el speech tiene tildes u otros caracteres fuera de GSM-7. El Speech original y las versiones guardadas no cambian: la normalización se aplica al generar.
* **RF-55 — Días de atraso ajustados a la fecha de envío:** Calcular los días de atraso de cada producto ajustados a la fecha de envío de la carga, y usarlos en el segmento calculado de RF-50, en todas las cargas.

  ```
  dias_atraso_ajustados = dias_atraso (de la sábana) + días calendario entre la fecha de corte y la fecha de envío
  ```

  * Es la misma fórmula de RF-MM-15, que deja de ser propia de MOWA MES (decisión del usuario, 2026-10-19).
  * Al generar una carga (`/generar-carga`), el usuario elige la fecha de envío; por defecto es el día en que se genera. La campaña de MOWA MES conserva su propia regla para la fecha de envío (RF-MM-15).
  * Si la fecha de envío es anterior a la fecha de corte de la sábana, entonces se rechaza indicando las dos fechas.
  * La previsualización (RF-47) usa la misma fecha de envío que la carga y dice cuál es; en el constructor de columnas, sin una carga en curso, es el día de hoy.
  * `fecha_envio` y `dias_atraso_ajustados` quedan disponibles como variables de contexto de la carga (RF-43).
* **RF-56 — Renombrar una definición guardada:** Permitir cambiar el nombre de una definición de columnas guardada (RF-51) sin crear una versión nueva ni modificar ninguna existente.
  * El nombre identifica la definición, no una versión: las versiones, sus usos y las cargas ya generadas no cambian.
  * Si ya existe otra definición con ese nombre, entonces se rechaza el cambio.

## Registro de cambios de esta versión

- **RF nuevos incorporados:** RF-37, RF-38, RF-39, RF-40, RF-41 (sección 10, 2026-09-13); RF-42 a RF-54 (sección 11, motor de texto enriquecido y constructor de columnas, 2026-09-29); RF-55 (días de atraso ajustados a la fecha de envío) y RF-56 (renombrar una definición guardada), en la sección 11 (2026-10-19); RF-57 a RF-63 (formatos de la sábana y mapeador de encabezados reutilizable), en la sección 1 (2026-10-24); RF-64 a RF-66 (campos adicionales creados desde el mapeo), en la sección 1 (2026-10-27).
- **RF existentes ampliados/modificados en su redacción:** RF-12 conserva su texto: RF-42 a RF-56 lo amplían, y RF-54 exige que lo que hoy cumple RF-12 siga produciendo el mismo resultado. **2026-10-19, decisiones del usuario:** RF-50 ampliado (el segmento calculado usa los días ajustados de RF-55, y la tabla por defecto es la de MOWA MES); RF-54 ampliado (el `mensaje` de MOWA MES normalizado a GSM-7, RF-MM-27, es un cambio decidido fuera de sus dos excepciones). **2026-10-24, decisiones del usuario:** RF-57 a RF-63 complementan RF-01 y RF-02 sin cambiar su texto; los parecidos van preseleccionados y a confirmar, el mapeo se recuerda, la hoja de Excel se elige y CSV detecta separador y codificación con ajuste manual. **2026-10-27, al revisar `/cargas` en dos pasos:** RF-59 ampliado con la búsqueda dentro de la lista de campos y con el campo ya asignado visible pero no elegible (decisión del 2026-10-27, ya implementada en `171025e`); RF-64 a RF-66 agregados: el campo adicional queda en el catálogo para las próximas sábanas y se usa en filtros, segmentación, indicadores, textos y columnas de carga, y en lo que venga después. Ese mismo día, con el plan T-CA-C1, el usuario decidió el supuesto de RF-65 (tipo fijo y archivar). Para MOWA MES decidió: el speech ofrece los adicionales; se exige `primeros(n)` a uno de texto o de número; uno vacío excluye el producto; y el archivo de MES no gana columnas (RF-54).
- **Nota de numeración:** los RF-01 a RF-36 conservan su número y su texto. Los nuevos se agregaron como sección 10 al final, sin renumerar, por decisión del usuario: RF-16 a RF-36 se citan por número en el código y en la documentación, y renumerarlos rompería esas referencias. Los requerimientos específicos de cada plataforma se numeran en su propio documento de módulo (por ejemplo, `RF-MM-01` en `requerimientos-mowa-mes.md`) para no mezclar su secuencia con la global.
