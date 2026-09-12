---
name: auto_cusco
description: A technobrutalist console for daily collections ingestion — exposed hairline grid, two signal hues, monospaced data.
colors:
  signal-green: "hsl(155 72% 45%)"
  signal-red-orange: "hsl(14 92% 52%)"
  color-bg: "hsl(14 25% 98%)"
  color-surface: "hsl(14 20% 95%)"
  color-surface-sunken: "hsl(14 15% 90%)"
  color-bg-inverse: "hsl(155 25% 6%)"
  color-text: "hsl(155 25% 6%)"
  color-text-muted: "hsl(155 12% 34%)"
  color-text-inverse: "hsl(14 25% 98%)"
  color-border: "hsl(155 20% 10%)"
  color-border-subtle: "hsl(14 16% 84%)"
  color-accent: "hsl(155 72% 45%)"
  color-accent-hover: "hsl(155 75% 37%)"
  color-accent-text: "hsl(155 75% 29%)"
  color-accent-wash: "hsl(155 70% 96%)"
  color-signal: "hsl(14 92% 52%)"
  color-signal-text: "hsl(14 88% 36%)"
  color-signal-wash: "hsl(14 90% 96%)"
  color-focus-ring: "hsl(14 92% 52%)"
  color-success-text: "hsl(155 75% 29%)"
  color-danger-text: "hsl(14 88% 36%)"
  color-warning-text: "hsl(14 82% 27%)"
  color-warning-wash: "hsl(14 88% 91%)"
  color-info-text: "hsl(155 12% 34%)"
  color-info-wash: "hsl(14 15% 90%)"
  color-selection-bg: "hsl(155 65% 80%)"
  ink-1000: "hsl(155 30% 3%)"
typography:
  display:
    fontFamily: "Inter, 'Inter Fallback', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "clamp(2.058rem, 3.2vw + 1.1rem, 4.236rem)"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Inter, 'Inter Fallback', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "2.058rem"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Inter, 'Inter Fallback', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "1.618rem"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Inter, 'Inter Fallback', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0"
  data:
    fontFamily: "'JetBrains Mono', 'JetBrains Mono Fallback', ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "0.786rem"
    fontWeight: 400
    lineHeight: 1.3
    fontFeature: "tabular-nums"
  label:
    fontFamily: "'JetBrains Mono', 'JetBrains Mono Fallback', ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "0.618rem"
    fontWeight: 500
    lineHeight: 1.3
    letterSpacing: "0.12em"
  stat:
    fontFamily: "'JetBrains Mono', 'JetBrains Mono Fallback', ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "2.058rem"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.03em"
    fontFeature: "tabular-nums"
rounded:
  structural: "0"
  pill: "9999px"
spacing:
  space-1: "0.309rem"
  space-2: "0.5rem"
  space-3: "0.809rem"
  space-4: "1.309rem"
  space-5: "2.118rem"
  space-6: "3.427rem"
components:
  button:
    backgroundColor: "transparent"
    textColor: "{colors.color-text}"
    rounded: "{rounded.pill}"
    padding: "0.5rem 1.309rem"
    typography: "{typography.data}"
  button-primary:
    backgroundColor: "{colors.color-accent}"
    textColor: "{colors.color-text}"
    rounded: "{rounded.pill}"
    padding: "0.5rem 1.309rem"
  button-primary-hover:
    backgroundColor: "{colors.color-accent-hover}"
    textColor: "{colors.color-text-inverse}"
  button-primary-disabled:
    backgroundColor: "{colors.color-surface-sunken}"
    textColor: "{colors.color-text-muted}"
  button-danger:
    backgroundColor: "transparent"
    textColor: "{colors.color-danger-text}"
    rounded: "{rounded.pill}"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.color-text-muted}"
    rounded: "{rounded.pill}"
  segmented-item:
    backgroundColor: "transparent"
    textColor: "{colors.color-text-muted}"
    rounded: "{rounded.structural}"
    padding: "0.309rem 0.809rem"
    typography: "{typography.label}"
  segmented-item-pressed:
    backgroundColor: "{colors.color-bg-inverse}"
    textColor: "{colors.color-text-inverse}"
  input:
    backgroundColor: "{colors.color-bg}"
    textColor: "{colors.color-text}"
    rounded: "{rounded.structural}"
    padding: "0.5rem 0.809rem"
    typography: "{typography.data}"
  panel:
    backgroundColor: "{colors.color-bg}"
    textColor: "{colors.color-text}"
    rounded: "{rounded.structural}"
    padding: "1.309rem"
  panel-head:
    backgroundColor: "{colors.color-surface}"
    textColor: "{colors.color-text}"
    padding: "0.809rem 1.309rem"
    typography: "{typography.label}"
  eyebrow:
    backgroundColor: "transparent"
    textColor: "{colors.color-text-muted}"
    rounded: "{rounded.pill}"
    padding: "0.309rem 0.809rem"
    typography: "{typography.label}"
  tag-error:
    backgroundColor: "{colors.color-signal-wash}"
    textColor: "{colors.color-danger-text}"
    rounded: "{rounded.pill}"
    padding: "0.309rem 0.809rem"
    typography: "{typography.label}"
  tag-vigente:
    backgroundColor: "{colors.color-accent-wash}"
    textColor: "{colors.color-accent-text}"
    rounded: "{rounded.pill}"
    padding: "0.309rem 0.809rem"
  dialog:
    backgroundColor: "{colors.color-bg}"
    textColor: "{colors.color-text}"
    rounded: "{rounded.structural}"
    width: "min(42rem, calc(100vw - 2.118rem))"
  notice-warning:
    backgroundColor: "{colors.color-warning-wash}"
    textColor: "{colors.color-warning-text}"
    rounded: "{rounded.structural}"
    padding: "0.809rem 1.309rem"
  date-node:
    backgroundColor: "{colors.color-bg}"
    textColor: "{colors.color-text}"
    rounded: "{rounded.structural}"
    padding: "0.5rem 0.809rem"
  date-node-selected:
    backgroundColor: "{colors.color-surface}"
    textColor: "{colors.color-text}"
    padding: "calc(0.5rem - 1px) calc(0.809rem - 1px)"
---

# Design System: auto_cusco

## Overview

**Creative North Star: "The Exposed Ledger"**

This is an instrument, not a page. A collections analyst opens it at a call-centre desk under high office light, early, in a hurry, with a 46 000-row spreadsheet to land before the phones start. Everything the system knows is laid out on a visible hairline grid with nothing hidden behind soft edges or drop shadows: the rules are drawn, the numerals are large and monospaced, and the structure of the data is the structure of the screen. The house style is **Technobrutalism (organic-fused)** as pinned in `docs/design_ui/brand_guide.json` — Orderful's exposed grid, dotted node-link diagrams and oversized numerals, softened by exactly one inherited gesture: the fully-rounded pill, and only on things you can press or read as status.

Two hues do all the signalling. A signal green (hue 155) and a signal red-orange (hue 14), and every neutral in the interface is a heavily desaturated tint of one of those two — warm paper from the red-orange, cool ink from the green. There is no gray anywhere in this system, and there is no third hue. When a third or fourth reading is needed (warning, info), it is taken from the same two ramps at a different lightness and weight rather than by adding a colour.

Density is the point. The product's own principle is *density before breathing room*: the analyst reads thousands of rows and compares versions, so clarity is bought with hierarchy and alignment, not with air. Both surfaces are built from the same tokens; the welcome screen is the only one locked to a single viewport, and it is the only place fluid type is allowed.

**Key Characteristics:**
- Exposed hairline grid — 1px borders are structure made visible, not container decoration
- Exactly two hues; every neutral is a tint of one of them, never gray
- Golden-ratio (φ = 1.618) ladders for both type and space
- Radius 0 on everything structural; 9999px pills only on buttons, badges, tags and dots
- Inter for chrome, JetBrains Mono for every value the analyst reads
- Absolutely flat: no drop shadows anywhere
- Light theme leads; dark is preserved but secondary
- State is carried by two colours plus one non-colour channel (a dashed edge)

## Colors

Two signal hues on tinted neutrals, at high contrast, with the accent used as a state marker rather than as decoration.

### Primary

- **Signal Green** (`hsl(155 72% 45%)`): The brand anchor and the "this one counts" colour. It fills the primary button, marks the header's API pulse when the database answers, colours the *vigente* (current version) dot on a date node, fills the live path in the welcome diagram, and lights the dropzone while a file is dragged over it. It is a **fill**, not a text colour.
- **Deep Green** (`hsl(155 75% 29%)`): the reading of the same hue. Every link, every success sentence, every `vigente` tag label. The build records this at 4.65:1 on paper.

### Secondary

- **Signal Red-Orange** (`hsl(14 92% 52%)`): urgency and attention. It is the focus ring on every focusable element, the caret colour in every input, and the dot on a cut-off date that has **no** current version. Not an error colour by itself — an "act on this" colour.
- **Deep Red-Orange** (`hsl(14 88% 36%)`): the reading of that hue — destructive button labels, invalid field borders, error tags, failure reasons on a failed version row. The build records this at 6.2:1 on paper.
- **Burnt Red-Orange** (`hsl(14 82% 27%)`): the warning voice, always on its own pale wash. This is how the system gets a third state reading without a third hue.

### Neutral

- **Paper** (`hsl(14 25% 98%)` → `hsl(14 15% 90%)`): the light canvas, warm because it is tinted from the red-orange hue. `paper-50` is the page, `paper-100` every panel header and table head, `paper-200` the sunken step used for pressed buttons and skeletons.
- **Ink** (`hsl(155 12% 34%)` → `hsl(155 30% 3%)`): the dark canvas and all text, cool because it is tinted from the green hue. `ink-950` is body text and the inverse background; `ink-900` is the hairline border colour; `ink-700` is muted text, recorded at 6.3:1 on paper — a real muted step, not a faded one.
- **Hairline Subtle** (`hsl(14 16% 84%)`): the only neutral that belongs to no ramp. It divides table rows, marks optional bands, and draws the dashed connector behind the date ruler.

### Named Rules

**The Two-Hue Rule.** Hue 155 and hue 14 are the entire palette. Every background, border, disabled state, "black" and "white" is a desaturated tint of one of them. A third hue is never introduced — a state that needs a fourth reading is found at a different lightness on an existing ramp. This is constitutional, not a preference.

**The Fill-Is-Not-Text Rule.** The 500 step of either ramp is a fill only. Text in a hue always reads from the 700 step in light and the 400 step in dark; that is why `--color-accent-text` and `--color-accent` are separate tokens with different values. Never set text to `--color-accent`.

**The Ramps Meet at Their Base Rule.** In light, the two text steps sit at 700 because that is where they clear contrast on paper. On ink both 500-adjacent steps clear it, so the dark theme pulls text up to the 400 step of each ramp. The dark palette is a re-derivation, not a filter.

**The Light-Leads Rule.** The confirmed use scene is a call-centre desk under high office light, so the light palette is declared on bare `:root` with `color-scheme: light` and is the polished default. Dark is expressed twice on purpose: once under `@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])`, so a system preference applies but an explicit light choice always wins, and once under `:root[data-theme="dark"]`, so an explicit dark choice wins against a light system. A colour is never defined for the first time inside a media query.

**The One-Leads Rule.** The two hues never appear at full saturation with the same visual weight in the same component. One leads; the other is a single touch — one dot, one border, one CTA.

## Typography

**Display / UI Font:** Inter (self-hosted variable woff2, weights 100–900, with `-apple-system`, `Segoe UI` fallbacks)
**Data / Mono Font:** JetBrains Mono (self-hosted static 400/500/700, with `ui-monospace`, `Menlo` fallbacks)

**Character:** Inter speaks for the product; JetBrains Mono speaks for the data. The split is semantic, not decorative — if the analyst would trace a value back to a row in a spreadsheet, it is set in mono with tabular numerals. Headings are heavy (800) and tightly tracked; everything technical is small, spaced and uppercase.

### Hierarchy

- **Display** (800, `clamp(2.058rem, 3.2vw + 1.1rem, 4.236rem)`, 1.05, −0.03em): the welcome headline only, capped at 18ch. The single fluid type size in the system.
- **Headline** (800, `2.058rem`, 1.05, −0.02em): `h1`. The console's ruler title is a `h1` stepped down to `1.272rem` because it sits inside a panel header rather than over the page.
- **Title** (800, `1.618rem` / `1.272rem` / `1rem` for h2/h3/h4, 1.05, −0.02em): section headings and dialog titles.
- **Body** (400, `1rem`, 1.5, 0): prose. Capped at `68ch` (`--measure-prose`) in empty states, 58ch in the console stand-in, 46ch in the welcome subcopy.
- **Data** (400, `0.786rem`, 1.3, tabular): table cells, version metadata, inputs, pager ranges. Applied by element (`code`, `kbd`, `samp`, `pre`, `time`, `output`), by `[data-mono]`, or by the `.mono` utility.
- **Label** (mono, 500, `0.618rem`, 1.3, 0.12em, uppercase): eyebrow badges, field labels, panel titles (700), table headers (700), legends. The small technical voice.
- **Stat** (mono, 700, `2.058rem` / `2.618rem` in the console summary, 1, −0.03em, tabular): the oversized numeral. Its `<dt>` label is the one label in Inter (600, `0.618rem`, uppercase) rather than mono, so the figure and its name never read as one mono string.

The type ladder is the golden-ratio geometric progression from a 1rem base: `0.618 · 0.786 · 1 · 1.272 · 1.618 · 2.058 · 2.618 · 4.236`.

### Named Rules

**The Mono-Is-Data Rule.** JetBrains Mono is reserved for values, identifiers, stamps and technical microcopy — anything the analyst might match against the source file. Prose, headings and button labels stay in Inter. A sentence never goes mono to look technical.

**The Fixed-Ladder Rule.** Component rules read a ladder step, never a raw size. The one exception is the welcome screen (`/`), which is locked to `100dvh` with no scroll and therefore clamps every size between two ladder steps so the composition compresses instead of overflowing. Operating screens scroll and use the ladder as-is.

**The Numeral-Leads Rule.** In a stat block the markup stays valid (`<dt>` label, then `<dd>` value) and CSS `order: -1` puts the numeral on top. Never reorder the markup to get the visual order.

**The Underline-Means-Link Rule.** Real underlines belong to `<a>`. Non-link emphasis (`<u>`) is drawn dotted *and* coloured in the red-orange text step, so it can never be mistaken for a link.

## Layout

The spatial model is the same golden-ratio ladder as the type, based at 0.5rem: `0.309 · 0.5 · 0.809 · 1.309 · 2.118 · 3.427 · 5.545 · 8.972` rem. Every gap, padding and inset in the system reads one of these steps; `--shell-gutter` is `--space-4` and the outer container caps at `--shell-max` (96rem), centred.

Both principal compositions are the same asymmetric split, expressed once as `--phi-minor: 0.618fr`: the welcome hero puts the words in the narrow column and the diagram in the wide one; the console's day-in-focus puts the day's versions in the narrow column and the selected version's figures in the wide one. That is 38.2% / 61.8%, and it appears only at 64rem and up — below it, both stack.

The layout is mobile-first and structural: base styles carry no media query, and the two real breakpoints (`48rem`, `64rem`) match the brand guide's `--bp-md` and `--bp-lg`. Two things make this system unusual:

- **Height is a breakpoint too.** The welcome screen gates its diagram on `(min-width: 48rem) and (min-height: 34rem)` and its stat band on `(min-height: 40rem)`. Short viewports drop the optional bands rather than compressing everything.
- **Two deliberate `max-width` exceptions exist.** `console.css` reflows the ruler rail at `max-width: 63.99rem` so the upload action drops to its own row below the scrolling dates, and `Shell.astro` centres the header and reorders the API pulse at `max-width: 30rem`. These are the only downward queries in the build; the constitution otherwise says min-width only, and new work should add min-width queries.

Two data surfaces get explicit width management. The issues table runs `table-layout: fixed` with stated column shares below 64rem (6/18/17/15/32/12 percent — DETALLE takes the largest) because auto layout hands the width to whichever column holds the longest unbroken identifier, then switches to `auto` with nowrap headers at 64rem and up. Snake_case identifiers are written into cells with `<wbr>` at each underscore and `overflow-wrap: normal`, so they break only where a break is honest.

### Named Rules

**The Golden Split Rule.** When a screen has a narrow side and a wide side, the split is `var(--phi-minor) 1fr` and it engages at 64rem. Narrow speaks; wide shows.

**The One-Viewport Exception Rule.** Exactly one surface is locked to `100dvh` with `overflow: hidden` — the welcome screen, opted in via `lockViewport` on the shell. Operating screens scroll and keep the same tokens. Never extend the lock to a screen that carries a table.

**The Ladder-Only Rule.** No component rule contains a raw length or a raw colour. If a value is needed that is not on a ladder, it is either a `ch`/`ratio` measure (`68ch`, `aspect-ratio: 1`) or it belongs in `tokens.css`.

## Elevation & Depth

**This system has no shadows.** There is not one drop shadow in the build, and there is no elevation scale. Depth is carried entirely by two devices: a visible 1px hairline border in ink (`--color-border`) that exposes the grid, and tonal layering between `--color-bg`, `--color-surface` and `--color-surface-sunken`. A panel is a rectangle with an edge; its header is one tonal step up; a pressed button is one tonal step down. Modal separation comes from a `::backdrop` mixed at 72% of the darkest ink, not from lifting the dialog.

The three `box-shadow` declarations in the system are not elevation:

- **Selection marker** (`box-shadow: inset 3px 0 0 0 var(--color-text)`): an inset rule on the selected version row — a bar, drawn with the only property that can draw it without moving the row.
- **Pulse ring** (`box-shadow: 0 0 0 0 → 0 0 0 5px` of `currentColor` at 45% → 0%): the working dot's animation.
- **Reduced-motion ring** (`box-shadow: 0 0 0 3px` of `currentColor` at 30%): the static substitute for that pulse.

### Named Rules

**The Flat-Grid Rule.** Depth is a border and a tonal step. Never add a `box-shadow` to lift a surface, never use a shadow for hover, and never soften an edge to suggest a layer. If two things need separating, draw the hairline.

**The Scroll-Says-So Rule.** A region that scrolls horizontally says so with edge gradients bound to scroll position (`background-attachment: local` for the fades, `scroll` for the shade), so an edge shades only while content remains off-screen on that side. This is used identically on the issues table and the date ruler, and is the only ornamental gradient in the system.

## Shapes

Rectangles with visible edges. Panels, dialogs, inputs, file pickers, date nodes, notices, choices and the diagram's node boxes are all `--radius-structural: 0` with a 1px border — even the SVG diagram sets `rx: 0` explicitly so the rule holds in vector space.

The one inherited soft gesture is the pill, `--radius-pill: 9999px`, and it is reserved exclusively for things that are interactive or are status: buttons (all variants, including the file picker's label trigger), the segmented control's outer shell, eyebrow badges, tags, and the 0.5rem status dot. The segmented control is the rule in miniature: pill on the outside, `overflow: hidden`, and sharp 1px dividers between its items.

Borders carry meaning by style as well as colour. A **solid** hairline is a container edge. A **dashed** hairline means something is provisional or invited: the file picker's dropzone, the connector line behind the date ruler, the connectors in the welcome diagram, and — critically — the edge of a cut-off date that is still processing.

### Named Rules

**The Radius-Zero Rule.** Everything structural is sharp. If a shape holds content, it has square corners.

**The Pill-Is-Interactive Rule.** `9999px` means "you can press this" or "this is a state". A pill is never used on a container, a card, a panel, an input or an image.

**The No-Reflow Selection Rule.** When selection thickens a border from 1px to 2px, the padding loses the same 1px (`calc(var(--space-2) - 1px)`) so nothing around it moves. Selection is never allowed to shift the grid.

## Components

### Buttons

- **Shape:** Fully rounded pill (`9999px`), 1px border, `0.5rem 1.309rem` padding, mono-adjacent sizing at `0.786rem` / weight 600.
- **Default:** transparent fill with an ink hairline. Hover fills with the sunken tone; active fills with the subtle border tone.
- **Primary:** signal green fill and border, with an **ink** label — the accent is a light fill in both themes, so its text is dark. Hover moves to the 600 step and the label flips to paper; active moves to the 700 step.
- **Danger:** transparent with the red-orange text step for both label and border. Hover fills with the red-orange wash.
- **Quiet:** no border, muted label, weight 500. Used for dialog close controls, paired with `--icon` (square, `aspect-ratio: 1`).
- **Small:** `--sm` drops to the `0.618rem` step with 0.04em tracking, for in-row actions.
- **Disabled:** opacity 0.6 for the plain variants. A **primary** button never fades — a faded accent fill leaves a pale shape with an unreadable label — so it drops the fill entirely for the sunken surface, a subtle border and muted text at full opacity.
- **Loading:** `data-loading="true"` fades the label to 0.55 and reveals a 1em ring spinner (`border-top-color: transparent`, 640ms linear). The label stays legible; the button does not change size.

### Segmented Control

One pressed-state group for every either/or in the product: language, theme, severity filter. Items are mono, `0.618rem`, 0.08em tracking, muted at rest; the pressed item inverts to the inverse background with inverse text via `aria-pressed="true"` — the accessible state *is* the visual state. Focus pulls its ring inside (`outline-offset: -2px`) so it is not clipped by the pill's `overflow: hidden`.

### Fields

- **Style:** square (`radius 0`), 1px ink border, page background, mono text at `0.786rem`. Labels sit above in the uppercase mono label style; hints below in the same face at `0.618rem`.
- **Hover:** border shifts to the green text step over 120ms.
- **Invalid:** border goes to the red-orange text step, driven by `:user-invalid` or `aria-invalid="true"` — never by a class alone.
- **Error message:** a fully bordered block (`1px solid currentColor`) on the red-orange wash, in mono 500. It self-hides when empty (`:empty { display: none }`), and the script pairs it with `aria-invalid`, `aria-describedby` and a focus move to the offending control.
- **File picker:** a dashed-bordered row that behaves as a real dropzone (`data-dragging="true"` swaps to the accent border and wash). The native `<input type=file>` stays real and focusable but visually hidden, because its built-in button text follows the *browser's* locale, not the page's; a `<label>` is the visible, translated trigger. Once a file is named, the "or drop it here" invitation removes itself via `:has([data-file-name]:not([data-i18n]))`.

### Panels and Dialogs

- **Corner style:** square. **Border:** 1px ink hairline. **Shadow:** none, ever.
- **Head:** one tonal step up (`--color-surface`), `0.809rem 1.309rem`, with a mono uppercase title at `0.618rem`/700 and room for a trailing badge.
- **Body:** `1.309rem`.
- **Dialog:** `min(42rem, 100vw − 2.118rem)` (`--wide`: 46rem), capped at `100dvh − 2.118rem`, re-centred with `margin: auto` because the reset zeroes the UA's own centring. Head and foot both carry the surface tone and a hairline; the foot right-aligns and wraps. Entrance is a 220ms opacity + 0.5rem rise, wrapped in `prefers-reduced-motion: no-preference`.
- **Stacking:** dialogs never stack. A modal that wants to open while another is up waits for the `close` event of whatever is blocking.

### Tags and Notices

Tags are pills bordered in `currentColor`, mono uppercase `0.618rem` with 0.06em tracking, in five semantic variants: `error` (red-orange text on red-orange wash), `advertencia` (burnt red-orange on its wash), `info` (muted ink on the paper wash), `vigente` (green text on green wash) and `neutral` (muted, no fill). Notices are the square-cornered, full-width version of the same idea — `1px solid currentColor` on the matching wash, with an inline lucide icon nudged down 0.15em to sit on the first line and any `<strong>` pulled back to full-strength text.

### Data Table

Collapsed borders, mono, tabular numerals, `0.786rem`. Headers are uppercase mono `0.618rem`/700 in muted ink on the surface tone, sticky to the top of their scroll container with a full-strength bottom hairline; body rows divide on the subtle hairline and highlight to the surface tone on hover. A `.num` class right-aligns numeric columns. Every table lives inside `.table-scroll`, which supplies both the overflow and the scroll-position-bound edge shading.

### Empty and Loading States

The empty block is left-aligned, muted, `0.786rem`, capped at the prose measure, with a mono `1rem` title in full-strength text. The skeleton is a sunken-tone bar at `1em` that breathes between 1 and 0.5 opacity over 1.6s — and only under `prefers-reduced-motion: no-preference`; otherwise it is a static bar, which still reads as "not yet".

### Signature Component: the date ruler

The brand's node-link motif doing a job. Every cut-off date is a node on a horizontal rail with a dashed 1px connector drawn behind the row (`::before`, inset by one space step), and the rail scrolls while the primary "upload" action stays put beside it. A node is a square-cornered button in a two-by-two grid — dot and day on top, year and version count beneath — with the day in mono 700 and the rest in the mono micro style. Nodes are `role="tab"`; the selected one thickens its border to 2px and gains the surface tone without moving. On load and on every re-render, the selected node scrolls itself into view (`block: nearest, inline: center`).

Its state vocabulary is the whole system in one control:

- **`vigente`** (this date has a current version) — green dot.
- **`sin`** (this date has none, so the day counts for nothing) — red-orange dot.
- **`procesando`** — muted dot *plus a dashed border on the node itself*. The dot may also pulse, but the dash is what carries the state, and the legend's marker for it is a dashed rule, not a coloured dot.

### Motion

Three durations and one curve: `120ms` for micro-interactions (background, border and colour shifts on buttons, inputs, segments, choices), `220ms` for state entrances (the dialog), `400ms` for on-load entrances, all on `cubic-bezier(0.22, 1, 0.36, 1)`. Nothing bounces, nothing parallaxes, nothing is triggered by scrolling.

The welcome screen's entrance is a 60ms-stepped stagger of an 8px rise (eyebrow → headline → subcopy → CTA → stats) plus the diagram's connectors drawing in — animated with `clip-path: inset()` rather than `stroke-dashoffset`, because animating the offset marches the dashes along the line instead of drawing it.

**The Bounded-Motion Rule.** Every non-essential animation lives inside `@media (prefers-reduced-motion: no-preference)`, and a global reduce block collapses all durations to 0.01ms as a backstop.

**The Substitute-Don't-Subtract Rule.** Reduced motion never means information is lost. The pulsing "working" dot becomes a static 3px ring of its own colour; the processing date node was already carrying a dashed border, which reads in a still frame and to anyone who cannot separate the two greens. When motion carries meaning, a still equivalent ships with it.

### Internationalisation

The i18n mechanism is part of this system, because the strings are laid out by the markup, not by a framework. Both dictionaries (`es`, `en`) ship in the bundle, so a switch repaints with no network round trip and no flash of keys. `es` leads; `en` is the fallback; an unresolved key returns itself.

- `data-i18n` replaces `textContent`; `data-i18n-html` replaces `innerHTML` and is reserved for copy that carries a `<br>`; `data-i18n-attr="aria-label:key,title:key"` writes attributes.
- `t(key, params)` interpolates `{name}` placeholders. **A node whose text was interpolated deletes its own `data-i18n`**, so the generic re-translation pass cannot overwrite it with the raw template.
- `setLanguage()` updates `<html lang>` and dispatches a `languagechange` event; every surface that builds DOM at runtime re-renders from that event, because `applyTranslations()` alone cannot reach script-built nodes.
- Theme and language persist in `localStorage` under `app:appearance` and are applied by an inline synchronous script before first paint, so neither can flash. A blocked storage API degrades to the CSS defaults silently.
- **Issue details are translated by code with a server fallback.** The API writes `detalle` in Spanish from the ingestion core; the enumerable part is `codigo`, so the interface looks up `incidencia.<codigo>` (22 codes per dictionary) and falls back to the server's own sentence when it does not know the code. A new backend code degrades to Spanish prose rather than to a missing string.
- Formatting follows the language: `es-PE` / `en-GB` for `Intl`. Timestamps are hand-built (`10.09 · 14:32`) rather than passed through `Intl`, because the locale's short-month form lands as `10-set.,` and reads like a defect in a column of monospaced data.

### Iconography

lucide only, inlined from source at build time — no icon font, no per-icon request, no glyph characters standing in for icons. Stroke width is 1.75, `fill: none`, `stroke: currentColor`, sizes restricted to 16/20/24/32, and every icon is `aria-hidden` and `focusable="false"`; the meaning lives in adjacent text or in the control's label.

### Why `console.css` is global and `index.astro` is scoped

Astro's scoped styles only reach markup Astro rendered. The console's ruler nodes, version rows, summary figures, issue cells and empty blocks are all built by the page script at runtime, so a scoped rule would never match them — `console.css` is therefore a plain global stylesheet imported by the page. The welcome screen renders its hero, diagram and stat shells on the server, so its styles stay scoped in the component's own `<style>` block, and `Shell.astro` keeps its chrome scoped for the same reason (reaching out with `:global()` only for the viewport lock on `html`/`body`). This is the rule: **markup built at runtime needs global CSS; markup rendered by Astro keeps its styles scoped.**

## Do's and Don'ts

### Do:

- **Do** read a token for every colour and every length. `tokens.css` is the single source of visual truth; a component rule containing a hex, an `hsl()` or a raw `px` is a bug.
- **Do** use the 700 step (light) / 400 step (dark) when a hue must be read as text, and the 500 step only as a fill.
- **Do** define every colour first on bare `:root`, then redefine it under both `@media (prefers-color-scheme: dark) :root:not([data-theme="light"])` and `:root[data-theme="dark"]` so an explicit choice wins in both directions.
- **Do** carry state on a second channel as well as colour — a dashed edge, a border weight, a word — so it survives a still frame and colour-blind reading.
- **Do** wrap non-essential motion in `prefers-reduced-motion: no-preference` and ship a static substitute for anything that was carrying meaning.
- **Do** reach for the native element first: `button` for actions, `a` only for navigation, `dialog` for modals, `form` with native validation, `fieldset`/`legend` for groups, `dl`/`dt`/`dd` for stats. `aria-pressed` and `aria-selected` drive the styling, so the accessible state and the visual state cannot drift.
- **Do** compensate padding when a border thickens on selection, so nothing on the grid moves.
- **Do** add media queries upward from `48rem` and `64rem`, matching the pinned breakpoints.
- **Do** put runtime-built markup's styles in a global stylesheet and server-rendered markup's styles in a scoped block.

### Don't:

- **Don't** introduce a third hue, and don't use a pure gray for anything. A state needing a new reading is found at a different lightness on one of the two ramps.
- **Don't** add a `box-shadow` for depth. This system is flat; separation is a hairline and a tonal step.
- **Don't** round a structural container. `9999px` belongs to buttons, badges, tags and dots and nothing else; everything that holds content is `radius 0`.
- **Don't** put both hues at full saturation and equal weight in the same component.
- **Don't** fade a filled primary button to show a disabled state — drop the fill and keep the label at full opacity.
- **Don't** set data, identifiers or numerals in Inter, and don't set prose or headings in JetBrains Mono to make them look technical.
- **Don't** animate `stroke-dashoffset` to draw a dotted connector; it marches the dashes. Use `clip-path: inset()`.
- **Don't** stack modals. Queue the second one behind the first's `close`.
- **Don't** rely on a native control's own button text in a translated interface — the browser's locale wins over the page's.
- **Don't** add a `max-width` media query without a structural reason; two exist and they are documented exceptions, not the pattern.
- **Don't** lock a scrolling operating screen to `100dvh`. The no-scroll rule is the welcome screen's alone.
- **Don't** put real collections data — names, documents, phone numbers — into any screen, example, test or screenshot. Sample data is synthetic, always.
