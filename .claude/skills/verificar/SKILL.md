---
name: verificar
description: Usar antes de dar por terminado cualquier cambio en auto_cusco, y cuando el usuario pregunte si algo está probado o pida pruebas. Decide qué niveles de prueba le corresponden al cambio, cómo correrlos y qué se puede afirmar al reportarlo. Cubre backend (pytest, integración con PostgreSQL) y frontend (Vitest, Playwright).
---

# Verificar un cambio en auto_cusco

El protocolo completo está en `docs/testing.md`. Esta guía es lo que hay que tener presente **mientras** se trabaja, no después.

## La regla

**Un cambio no está verificado hasta correr todos los niveles que le apliquen.** Pasar el nivel de abajo no dice nada del de arriba: un caso de uso probado con dobles no demuestra que la consulta real funcione, y una API probada con `TestClient` no demuestra que la pantalla haga lo correcto.

Si un nivel aplica y no se corrió, **se dice explícitamente al reportar**, con el motivo. Nunca se reporta "probado" a secas.

## Qué nivel le toca a tu cambio

| Si tocaste... | Corre como mínimo |
|---|---|
| Reglas de negocio o un caso de uso (`app/core/`) | Núcleo, con dobles de prueba |
| Un adaptador de entrada/salida (lectura de archivos, exportadores) | Adaptadores, con archivos generados en memoria |
| Un router (`app/api/`) | API con `TestClient`, sustituyendo la dependencia del caso de uso |
| Persistencia, SQL, modelos o migraciones | **Integración contra PostgreSQL real** (marcador `postgres`) |
| Algo que atraviesa varias capas | Además, una prueba de la cadena completa contra PostgreSQL |
| Una pantalla o lógica de interfaz | Núcleo y DOM del frontend, más extremo a extremo con Playwright |

El hueco que más se cuela: **un caso de uso nuevo que consulta la base queda con todas sus pruebas en verde usando un repositorio en memoria.** Eso deja sin verificar la paginación real, el orden real y los tipos que devuelve PostgreSQL. Si tu caso de uso consulta o escribe, le toca una prueba `postgres`.

## Comandos

Desde `backend/`:

```powershell
.\scripts\verificar.ps1            # formato, lint y pruebas
.\scripts\verificar.ps1 -ConBase   # agrega migraciones e integración con PostgreSQL
```

Desde `frontend/`, cuando la tarea tocó la interfaz:

```powershell
npm run verificar                  # tipos, build, núcleo/DOM y extremo a extremo
```

Las pruebas `postgres` se saltan solas sin `AUTO_CUSCO_DB_TESTS=1`; que el resumen diga "9 skipped" **no** es que estén en verde.

## Cómo se escribe una prueba aquí

- **Datos sintéticos siempre.** Nunca nombres, documentos ni teléfonos reales, ni en pruebas ni en documentación ni en la conversación (ver `/AGENTS.md`). Para una sábana completa, `backend/scripts/generar_sabana_sintetica.py`.
- **Las pruebas contra la base limpian lo que crean** y usan fechas fuera de rango operativo para no pisar datos de trabajo.
- **Preparar, ejecutar y comprobar,** separados por una línea en blanco. Una idea por prueba, nombre en español que describa el comportamiento.
- **Cobertura mínima de algo nuevo:** caso normal, bordes, entradas inválidas y, cuando dos piezas deben coincidir, una prueba de contrato entre ellas.
- **Un error se reproduce con una prueba que falla antes de corregirlo,** en el nivel más bajo donde se reproduzca, y esa prueba se queda como regresión.

## Cómo se reporta

Nombra el nivel y lo que quedó fuera. Comparar:

- ❌ "Implementado y probado, 47 pruebas en verde."
- ✅ "Núcleo, adaptadores y API en verde (47 pruebas). Falta la integración contra PostgreSQL: la paginación real y los tipos que devuelve la base están supuestos, no verificados."

Lo segundo es lo que permite decidir si se puede seguir. Lo primero suena mejor y vale menos.

## Antes de cerrar

- `docs/planning.md` si se completó un punto o cambió el alcance; `docs/modules.md` si cambió el estado de un módulo.
- Si cambió una regla de negocio, actualízala en su documento (`docs/sabana-schema.md`, `docs/versionado-sabanas.md`, `docs/mapeo-campos.md`, `docs/generacion-cargas.md`, `docs/consulta-cartera.md`).
- Commit con prefijo `feat`, `fix`, `docs`, `test`, `refactor` o `chore` y el módulo entre paréntesis, firmado con el trailer `Agente: <nombre de la sesión>` (ver `docs/agents/README.md`).
- **Informa el commit al usuario en cuanto lo creas:** hash corto, mensaje, qué incluye, qué niveles de prueba corrieron y cuáles no, y si falta `git push`.
