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
