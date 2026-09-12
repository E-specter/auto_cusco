# Configuración multiagente

Este proyecto está pensado para que trabajen en él varios agentes de código en paralelo o en distintas sesiones (Claude Code, Codex, OpenCode, Hermes, u otros). Para que todos compartan el mismo contexto sin duplicar información, se usa esta convención:

## Archivo compartido: `AGENTS.md`

`/AGENTS.md` (raíz del repo) es la fuente de verdad universal. La mayoría de agentes de código modernos (Codex, OpenCode, y otros que siguen la convención [agents.md](https://agents.md)) lo leen automáticamente al iniciar sesión en el repositorio. Contiene:

- Qué es el proyecto y dónde está cada pieza.
- Stack tecnológico.
- Reglas críticas (p. ej. no versionar datos sensibles).
- Punteros a `docs/` para detalle profundo.

**Regla**: si una instrucción aplica a cualquier agente, va en `AGENTS.md`, no en un archivo específico de un agente.

## Archivos específicos por agente

| Agente | Archivo | Contenido |
|---|---|---|
| Claude Code | `/CLAUDE.md` | Importa `AGENTS.md` (`@AGENTS.md`) + notas específicas de Claude Code (uso de herramientas dedicadas, entorno Windows/PowerShell). |
| Codex | `/AGENTS.md` (directo) | Codex CLI lee `AGENTS.md` de forma nativa; no requiere archivo propio salvo que se necesite override. |
| OpenCode | `/AGENTS.md` (directo) | Igual que Codex — sigue la misma convención `agents.md`. |
| Hermes | `/AGENTS.md` (directo, hasta confirmar convención propia) | Si Hermes requiere un archivo con nombre distinto, crear `/HERMES.md` como thin wrapper que importe/repita `AGENTS.md`, siguiendo el mismo patrón que `CLAUDE.md`. |

## Firma de los commits

Varios agentes trabajan sobre el mismo repositorio, así que cada commit dice **qué sesión lo desarrolló**. No basta con el autor de git: todas las sesiones commitean con la misma identidad configurada en la máquina.

La marca es un trailer al final del mensaje, después del cuerpo y junto a los que ya se usan:

```
feat(frontend): pruebas automaticas con Vitest y Playwright

Cuerpo del mensaje.

Agente: designer
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_...
```

- **El valor es el nombre de la sesión**, el mismo con el que los agentes se llaman entre sí. Hoy en uso: `architec` (backend y arquitectura) y `designer` (frontend e interfaz).
- **Un trailer, no una etiqueta de git.** Las etiquetas de git marcan versiones, no autoría, y una por commit no serviría de nada. Un trailer viaja con el mensaje y se consulta directo:

  ```powershell
  git log --grep="Agente: designer" --oneline
  ```

- **Se firma el trabajo propio.** Si una sesión commitea trabajo de otra —pasa, y es legítimo— el mensaje lo dice en el cuerpo y el trailer nombra a quien lo escribió, no a quien ejecutó el commit.

## Informar cada commit

**Todo commit se le informa al usuario en el momento en que se crea**, no al final de la tarea ni agrupado con otros. El aviso dice:

- el hash corto y el mensaje,
- qué incluye, en una o dos líneas,
- cómo se verificó: qué niveles de prueba corrieron y cuáles quedaron fuera, con el motivo,
- si queda pendiente subirlo con `git push`.

Varios agentes commitean en el mismo repositorio; si el usuario no se entera de un commit, no puede revisarlo ni saber qué está por subir.

Esto no reemplaza el prefijo por módulo (`feat`, `fix`, `docs`, `test`, `refactor`, `chore`) que define `docs/testing.md`, sección 4: lo complementa.

## Archivos anidados

Subcarpetas pueden tener su propio `AGENTS.md` (o equivalente) con reglas específicas de esa parte del código, que complementan (no reemplazan) el de la raíz. Ejemplo existente: `frontend/AGENTS.md` (convenciones del dev server de Astro).

## Cuándo actualizar qué

- Cambia el stack, la estructura de carpetas o una regla que aplica a todos → editar `/AGENTS.md`.
- Cambia una preferencia de comportamiento de un agente específico → editar su archivo propio (`CLAUDE.md`, etc.), nunca `AGENTS.md`.
- Cambia arquitectura, requerimientos, módulos o el roadmap → editar el documento correspondiente en `docs/` (ver [../README.md](../README.md)); `AGENTS.md` solo debe apuntar ahí, no duplicar el contenido.

## Agregar un nuevo agente

1. Confirmar si el agente soporta la convención `AGENTS.md` nativamente (la mayoría sí). Si es así, no se necesita archivo adicional.
2. Si no, crear un archivo thin wrapper en la raíz (`<AGENTE>.md`) que referencie `AGENTS.md` y agregue solo lo específico de ese agente — siguiendo el patrón de `CLAUDE.md`.
3. Añadir la fila correspondiente a la tabla de arriba.
