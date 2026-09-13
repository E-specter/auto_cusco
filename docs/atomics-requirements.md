# Requerimientos funcionales — Sistema de gestión de cobranzas / cartera

## 1. Carga y procesamiento de sábanas diarias

* **RF-01 — Carga de archivos:** Permitir la carga de las sábanas diarias al sistema mediante archivos estructurados.
* **RF-02 — Validación y normalización de datos:** Procesar automáticamente los archivos durante la carga para validar, normalizar y estandarizar los datos según las reglas de negocio definidas.
  * Validar formatos de documentos de identidad: **DNI, RUC, extranjero, etc.**
  * Validar números telefónicos según el formato establecido: **9 dígitos e inicio con 9**.
  * Detectar inconsistencias, datos inválidos y registros que no cumplan las reglas de validación.
* **RF-03 — Gestión de cartera:** Permitir identificar, registrar, actualizar y omitir productos de la cartera en función de la información contenida en las sábanas cargadas.

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

## Registro de cambios de esta versión

- **RF nuevos incorporados:** RF-37, RF-38, RF-39, RF-40, RF-41 (sección 10, 2026-09-13).
- **RF existentes ampliados/modificados en su redacción:** ninguno.
- **Nota de numeración:** los RF-01 a RF-36 conservan su número y su texto. Los nuevos se agregaron como sección 10 al final, sin renumerar, por decisión del usuario: RF-16 a RF-36 se citan por número en el código y en la documentación, y renumerarlos rompería esas referencias. Los requerimientos específicos de cada plataforma se numeran en su propio documento de módulo (por ejemplo, `RF-MM-01` en `requerimientos-mowa-mes.md`) para no mezclar su secuencia con la global.
