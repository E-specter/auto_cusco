# Motor de reglas de mapeo y expresión de campos (RF-12)

Cómo se construye, campo por campo, el contenido de un archivo de carga a partir de los productos seleccionados. Es un módulo compartido: las cargas digitales (Fase 3) y las VoIP (Fase 4) lo usan con reglas propias por plataforma, en vez de reimplementarlo cada una.

## 1. Qué es una definición de carga

Una definición describe las columnas del archivo de salida y cómo se llena cada una. Es **configuración, no código** (RF-32): se guarda, se edita y se reutiliza sin tocar el sistema.

Cada campo de salida tiene:

| Parte | Para qué |
|---|---|
| `nombre` | La cabecera en el archivo generado |
| `plantilla` | Cómo se arma el valor, con texto fijo y referencias a campos del producto |
| `tipo` | `texto`, `numero`, `fecha` o `financiero` |
| `formato_fecha` | Notación tipo `%d/%m/%Y`. Sin él, la fecha sale como fecha nativa |
| `formato_financiero` | Separador de miles, separador decimal y cantidad de decimales |

## 2. Sintaxis de las plantillas

Texto plano con referencias a campos del producto entre `[@...]`:

| Plantilla | Resultado |
|---|---|
| `1010` | Valor fijo, igual en todas las filas |
| `[@telefono]` | Copia directa del campo |
| `51[@telefono]` | Prefijo más campo |
| `documento=[@documento_numero]` | Concatenación de texto y campo |
| `Pagare [@pagare] vence el [@fecha_vencimiento_cuota]` | Varios campos en una frase |

Los campos disponibles son los mismos de la cartera (ver `consulta-cartera.md`). **Una plantilla se valida al guardarla**, no al generar: si nombra un campo que no existe o deja un `[@` sin cerrar, se rechaza ahí mismo, antes de procesar miles de filas.

## 3. Tipado y formato

- **texto:** el resultado de la plantilla, tal cual.
- **numero:** el valor convertido a número. Si es entero, sale entero.
- **fecha:** con `formato_fecha` sale como texto con ese formato; sin él, como fecha nativa, útil para XLSX.
- **financiero:** importe con los separadores configurados. Por ejemplo `1,500.50` o `1.500,50`, según lo que pida la plataforma.

Dos reglas que evitan sorpresas:

- **Cuando la plantilla es una sola referencia, se conserva el valor original** en vez de pasarlo por texto. Así un importe no pierde decimales ni una fecha se reinterpreta.
- **Un campo sin dato de origen queda vacío**, no en cero ni en una fecha inventada. En una concatenación, el resto del texto se mantiene: `51[@telefono]` sin teléfono produce `51`.

## 4. Errores

Un error en un campo **no detiene la generación**. Se registra con su número de fila y su campo, y el resto de la carga se sigue construyendo, para que el usuario vea de una vez todo lo que hay que corregir. El resultado indica si la carga quedó completa.

## 5. Implementación

- **Entidades:** `backend/app/core/entities/mapeo.py`.
- **Motor:** `backend/app/core/services/mapeo_campos/`, con el intérprete de plantillas, el tipado y el generador de filas.
- **Pruebas:** plantillas, formatos y generación, incluidos los casos de error y de campos vacíos.

El motor no conoce ninguna plataforma. Las cabeceras y reglas concretas de cada una viven en su propio adaptador de salida.

## 6. Lo que falta

- **Guardar definiciones** y editarlas desde la interfaz.
- **Adaptadores por plataforma:** SMS y WhatsApp primero, luego Cisvox para VoIP. Su estructura exacta de campos debe levantarse con el usuario o su documentación antes de implementarlos (RF-10, RF-18).

La escritura del archivo ya está resuelta: cómo se convierte esta tabla en XLSX, CSV o JSON está en [generacion-cargas.md](generacion-cargas.md).
