# Generación de archivos de carga (RF-09, RF-13, RF-15)

Cómo se convierte una selección de cartera en un archivo listo para subir a una plataforma. Une tres piezas que ya existían por separado: la **selección** (`consulta-cartera.md`), las **reglas de mapeo campo por campo** (`mapeo-campos.md`) y la **escritura del archivo** en el formato que pida el destino.

## 1. El recorrido

1. El usuario arma su selección en la pantalla de cartera: fecha de corte, filtros, orden y cuántos productos quiere.
2. Elige o escribe una **definición de carga**: qué columnas tiene el archivo y cómo se llena cada una.
3. **Previsualiza:** ve las primeras filas tal como van a quedar y los errores que haya, sin generar nada.
4. **Genera:** descarga el archivo en XLSX, CSV o JSON.

La generación queda disponible apenas termina la selección, sin pasos intermedios (RF-15).

## 2. Endpoints

| Método | Ruta | Para qué |
|---|---|---|
| `GET` | `/archivos-carga/formatos` | Formatos disponibles y qué opciones admite cada uno |
| `POST` | `/archivos-carga/previsualizacion` | Primeras filas y errores, en JSON |
| `POST` | `/archivos-carga` | El archivo completo, para descargar |

> `/cargas` es otra cosa: son las **versiones de sábana** que se suben (ver `versionado-sabanas.md`). `/archivos-carga` son los archivos que salen hacia las plataformas.

Los filtros y el orden usan **la misma sintaxis que `/cartera`** (`campo:operador:valor`, orden `campo` o `-campo`), para que lo que el usuario armó en la pantalla de selección se reutilice tal cual.

Cuerpo de las dos operaciones `POST`:

```json
{
  "fecha_corte": "2026-09-10",
  "formato": "csv",
  "cantidad": 5000,
  "filtros": ["segmento_financiero:igual:1. Preventiva", "telefono:no_vacio"],
  "orden": "-saldo_capital_pendiente",
  "definicion": {
    "nombre": "SMS preventiva",
    "campos": [
      {"nombre": "anexo", "plantilla": "1010", "tipo": "numero"},
      {"nombre": "numero", "plantilla": "51[@telefono]"},
      {"nombre": "deuda", "plantilla": "[@saldo_capital_pendiente]", "tipo": "financiero"},
      {"nombre": "vence", "plantilla": "[@fecha_vencimiento_cuota]", "tipo": "fecha",
       "formato_fecha": "%d/%m/%Y"}
    ]
  },
  "opciones": {"delimitador": ";"}
}
```

La definición viaja completa en cada llamada porque **todavía no se guarda en la base**. Cuando se pueda guardar, el cuerpo llevará su identificador en vez del detalle; el resto del contrato no cambia.

### Respuestas

- **Previsualización:** `cabeceras`, una muestra de `filas`, `disponibles` (el total de la selección completa, no el de la muestra), `solicitados`, `generados`, `suficiente`, `completa` y la lista de `errores` con su fila y su campo.
- **Generación:** el archivo, con `Content-Disposition` para el nombre y el resumen en cabeceras `X-Carga-Generados`, `X-Carga-Disponibles`, `X-Carga-Solicitados`, `X-Carga-Suficiente` y `X-Carga-Errores`. El detalle de los errores se consulta en la previsualización, porque el cuerpo ya es el archivo.

`suficiente` en `false` significa que había menos productos que los pedidos (RF-08): el archivo se genera igual, con los que hay.

### Errores

| Situación | Respuesta |
|---|---|
| La fecha no tiene versión vigente | `404` |
| Filtro, orden o plantilla mal escritos | `400` |
| Formato inexistente, cantidad fuera de rango, definición sin campos | `422` |

Una plantilla inválida se rechaza **antes de consultar la base**: no se paga una consulta para descubrir un error de escritura.

## 3. Formatos

| Formato | Opciones | Notas |
|---|---|---|
| `xlsx` | `con_cabeceras`, `hoja` | El texto se queda como texto: el pagaré y el documento no pierden sus ceros a la izquierda. Las fechas van como fecha nativa de Excel |
| `csv` | `delimitador`, `codificacion`, `con_cabeceras` | Fin de línea `\r\n` (RFC 4180). `utf-8-sig` hace que Excel abra el archivo con las tildes correctas |
| `json` | `codificacion`, `sangria` | Lista de objetos, con las claves en el orden de las cabeceras. Un campo vacío sale como `null` |

Agregar un formato es agregar su adaptador en `backend/app/adapters/output/exportadores/` y una entrada en el registro; ni el núcleo ni los demás formatos cambian (RF-14).

### Tres detalles que evitan datos alterados

- **Una celda vacía queda vacía** en los tres formatos: nunca un cero ni una fecha inventada.
- **Los números decimales pierden los ceros a la derecha** tanto en JSON como en XLSX, porque ambos los guardan como número. Un importe que deba verse siempre con dos decimales corresponde declararlo `financiero`, que produce texto con el formato exacto.
- **Si un carácter no cabe en la codificación pedida** (por ejemplo latin-1) o Excel no lo admite en una celda, la generación falla con un aviso claro en vez de entregar un archivo con el dato cambiado.

El nombre del archivo sale del nombre de la definición, pasado a ASCII y sin separadores de ruta: lo escribe el usuario y termina en una cabecera HTTP y en el disco.

## 4. Volumen

La selección se lee por páginas y las filas de salida se arman sobre la marcha, así una carga grande no obliga a tener la cartera entera en memoria. El tope por archivo es de **50 000 productos**; una campaña mayor se parte en varios archivos.

## 5. Implementación

- **Entidades:** `backend/app/core/entities/exportacion.py` (formatos, opciones, tabla, archivo).
- **Puerto:** `backend/app/core/ports/exportador_tabla_port.py`.
- **Adaptadores:** `backend/app/adapters/output/exportadores/` — uno por formato, más el registro.
- **Caso de uso:** `backend/app/core/services/generacion_cargas/servicio.py`.
- **API:** `backend/app/api/archivos_carga.py`; la lectura de filtros y orden, compartida con `/cartera`, está en `backend/app/api/consultas.py`.
- **Pruebas:** `test_exportadores.py`, `test_generacion_cargas.py` y `test_api_archivos_carga.py`.

Los exportadores no saben nada de cobranza: reciben cabeceras y filas. Los reportes configurables (RF-24) van a reutilizarlos tal como están.

## 6. Lo que falta

- **Guardar definiciones** de carga y editarlas desde la interfaz (RF-11, RF-32).
- **Adaptadores por plataforma:** SMS y WhatsApp primero, luego Cisvox para VoIP. Lo que falta de ellos no es el motor ni el formato, sino **la estructura exacta de campos y cabeceras que exige cada proveedor**, que hay que levantar con el usuario o con su documentación antes de implementarlos (RF-10, RF-18).
- **Pantalla de generación** en el frontend, sobre estos endpoints.
