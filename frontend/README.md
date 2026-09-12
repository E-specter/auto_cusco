# frontend — auto_cusco

Interfaz de `auto_cusco`: dos pantallas Astro estáticas que hablan con la API REST desde el navegador. Sin framework de UI, sin estado de servidor, CSS vanilla.

El desglose completo está en `docs/modules.md` §10; las convenciones de agentes, en `AGENTS.md`.

## Arrancar

El frontend necesita el backend en marcha:

```sh
# terminal 1 — API
cd backend
uv run fastapi dev app/main.py

# terminal 2 — interfaz
cd frontend
npm install
npx astro dev --background     # gestión: astro dev stop | status | logs
```

La interfaz queda en <http://localhost:4321> y la API en <http://127.0.0.1:8000>.

El navegador **nunca** habla con `127.0.0.1:8000` directamente: pide a un prefijo `/api` del mismo origen que `astro.config.mjs` redirige al backend, así no hacen falta cabeceras CORS. Para apuntar a otro origen:

- `API_ORIGIN=http://otro-host:8000 npx astro dev` cambia el destino del proxy de desarrollo;
- `PUBLIC_API_URL=https://api.ejemplo.com` hace que el navegador llame a ese origen absoluto — **y entonces hay que habilitar CORS en el backend**, completando `CORS_ORIGENES` en `/.env` con ese origen (ver `docs/setup.md` paso 4). Viene apagado por defecto a propósito: sin origen configurado la API no envía cabeceras CORS.

## Rutas

| Ruta | Qué es |
|---|---|
| `/` | Bienvenida. La **única** pantalla bloqueada a `100dvh` sin scroll, por regla del brand guide. Sus cifras son reales: salen de `GET /cargas` |
| `/cargas` | Consola de cargas. Una fecha de corte a la vez: regla de fechas, versiones del día, resumen e incidencias, más los diálogos de V-4, V-6, V-7 y V-8 |

## Dónde tocar qué

```
src/
├── pages/        index.astro (bienvenida) · cargas.astro (consola)
├── layouts/      Shell.astro — cabecera, pulso de la API, idioma y tema
├── components/   Icon.astro — inserta iconos lucide en compilación
├── styles/       tokens.css · base.css · ui.css · console.css
├── lib/          api.ts (cliente) · i18n.ts · format.ts
└── i18n/         es.json · en.json
```

- **`tokens.css` es la única fuente de verdad visual.** Deriva de `docs/design_ui/brand_guide.json`. Ninguna regla de componente escribe un hex ni un px a mano: todo sale de un token.
- **`console.css` es global, no con ámbito de Astro**, a propósito: la consola construye la regla de fechas, las filas de versión, las cifras y la tabla de incidencias desde el script en tiempo de ejecución, y los estilos con ámbito no alcanzan al DOM que crea el script. Si agregas estilos para algo que dibuja el script, van ahí.
- **Los diccionarios están emparejados.** Cada clave existe en los dos idiomas y ninguna clave sin usar sobrevive. Los mensajes de incidencia se traducen por **código** (`incidencia.<codigo>`), con la frase del backend como respaldo: si `backend/app/core/services/ingesta_sabana/` emite un código nuevo, agrégalo a ambos JSON.
- **Las fuentes están autohospedadas** en `public/fonts/` y se precargan. Se copian de `@fontsource-variable/inter` y `@fontsource/jetbrains-mono`; si cambian de versión, vuelve a copiarlas.

## Pruebas

```sh
npx playwright install chromium   # solo la primera vez
npm run verificar                 # build + nucleo/DOM + extremo a extremo
```

O por separado: `npx astro check`, `npm run test`, `npm run test:e2e`.

| Carpeta | Qué cubre | Entorno |
|---|---|---|
| `tests/nucleo/` | Fecha sugerida desde el nombre del archivo, formatos, cliente de API y el contrato de traducción de incidencias | `node` |
| `tests/dom/` | Cola de diálogos (V-6 → V-4) y cambio de idioma | `jsdom` |
| `e2e/` | Las pantallas contra el sitio construido | Chromium |

Dos cosas que conviene saber antes de tocarlas:

- **Las pruebas de extremo a extremo no necesitan backend ni PostgreSQL.** Playwright levanta `npm run preview` y cada prueba intercepta `/api` con `page.route` (`e2e/api-falsa.ts`). Comprueban qué hace la interfaz con una respuesta, que es la única parte que le pertenece.
- **`tests/nucleo/i18n-incidencias.test.ts` lee el catálogo canónico del backend** (`backend/app/core/entities/incidencias.py`, constante `CODIGOS_INCIDENCIA`) y falla si un código no está traducido en los dos idiomas, o si sobra una traducción de un código retirado. Es la mitad frontend de un contrato: el backend tiene su propia prueba que falla si emite un código fuera del catálogo. Así ninguno de los dos lee el código fuente del otro, solo esa lista compartida. Sin esto, un código nuevo deja una frase en español dentro de la tabla en inglés y nada se queja.

Si una pieza de lógica no se puede importar, no se puede probar: sácala del `<script>` de la página a `src/lib/` antes de escribirle una prueba.

## Comprobar a mano antes de cerrar una tarea

Lo que las pruebas no ven: en el navegador, contra el backend real, a 360x640, 768x1024, 1440x900 y 1920x1080, en tema claro y oscuro, con foco visible en todo control y con `prefers-reduced-motion` activo. El protocolo general está en `docs/testing.md`.

**Nunca uses sábanas reales para probar.** Los datos de cobranza son sensibles: genera archivos sintéticos y no dejes nombres, documentos ni teléfonos reales en capturas, pruebas ni documentación.
