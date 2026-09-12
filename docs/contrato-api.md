# Contrato entre la API y el frontend

El backend y el frontend los desarrollan sesiones distintas. Sin un contrato escrito, los tipos de `frontend/src/lib/api.ts` son lo que el frontend *cree* que responde el backend, y nada avisa cuando un campo cambia de nombre o deja de venir. Este documento describe cómo se evita eso.

## 1. Qué es

**`contratos/openapi.json`**, en la raíz del repositorio: el esquema OpenAPI de la API, exportado desde la aplicación real y versionado en git.

| Lado | Responsabilidad |
|---|---|
| Backend | Mantener el archivo idéntico a la API. Si un endpoint cambia, el archivo se regenera en el mismo commit |
| Frontend | Escribir sus tipos contra el archivo y comprobar en CI que coinciden |

Es la única fuente de verdad de la forma de la API. Lo que un endpoint *hace* sigue documentado en su propio documento (`versionado-sabanas.md`, `consulta-cartera.md`, `generacion-cargas.md`); el contrato dice qué forma tienen las peticiones y las respuestas.

## 2. Cómo se mantiene del lado backend

Desde `backend/`:

```powershell
uv run python scripts/exportar_openapi.py              # regenera contratos/openapi.json
uv run python scripts/exportar_openapi.py --comprobar  # termina con error si está desactualizado
```

No hace falta acordarse de correr `--comprobar`: **`tests/test_contrato_openapi.py` falla si el archivo versionado no coincide con la API**, y esa prueba corre en `verificar.ps1` y en CI como cualquier otra. El mensaje de la falla dice qué comando corre.

La exportación es estable —el mismo esquema produce los mismos bytes— y se compara ya interpretada, así que el fin de línea que ponga git en Windows no cuenta como diferencia.

## 3. Qué garantizan las pruebas

Que el archivo coincida no alcanza si el esquema no dice nada. Las pruebas cuidan además que el contrato sea útil:

- **Toda respuesta exitosa declara su forma.** Un endpoint que devuelve un `dict` sin modelo aparece en el esquema como un objeto libre, y el frontend no puede tiparlo. La prueba lo rechaza: por eso `/health` y `/cartera/campos` tienen ahora su modelo.
- **Los errores están declarados y usan el cuerpo común** `{"detail": "..."}` (`DetalleError`), con el código que corresponde a cada endpoint: `400`, `404`, `409` o `413`. El `422` de validación lo declara FastAPI con su propio esquema.
- **La descarga de `/archivos-carga` describe lo que envía:** un cuerpo binario en XLSX, CSV o JSON, el nombre en `Content-Disposition` y el resumen en las cabeceras `X-Carga-*`. Una prueba hace la descarga y comprueba que **las cabeceras que se envían son exactamente las declaradas**. La misma lista alimenta lo que CORS deja leer al navegador, así que las tres cosas no pueden desalinearse.

## 4. Lo que el contrato no cubre

- **Columnas dinámicas.** Los `productos` de `/cartera` y las `filas` de la previsualización son objetos libres a propósito: sus claves dependen del catálogo de campos (`/cartera/campos`) o de la definición de carga que armó el usuario. El contrato declara el objeto; las claves se leen en tiempo de ejecución.
- **Comportamiento.** Que un filtro filtre bien o que la paginación no repita productos lo verifican las pruebas de cada nivel (ver `testing.md`), no el contrato.

## 5. Estado

- **Backend: configurado.** `contratos/openapi.json`, `backend/app/api/contrato.py`, `backend/scripts/exportar_openapi.py` y `backend/tests/test_contrato_openapi.py`.
- **Frontend: pendiente, a cargo de la sesión `designer`.** Generar los tipos desde `contratos/openapi.json` y comprobar en CI que `api.ts` coincide con ellos.
