---
name: "ContextCraft"
description: "Software Broadsheet: warm paper, expressive serif headlines, moss actions, and open technical reading surfaces."
colors:
  moss: "#354e37"
  moss-deep: "#253f2c"
  paper: "#faf9f6"
  ink: "#101114"
  sage: "#a6b0a0"
  muted: "#4d5257"
  rule: "#d5d9d0"
  panel: "#eeeee7"
  working-surface: "#edf0e6"
  budget-hover: "#dce3d3"
  benchmark-surface: "#f1f0e9"
  dark-paper: "#1b211d"
  dark-heading: "#f5f5ee"
  dark-text: "#d4d9d1"
  dark-muted: "#a9b3a4"
  dark-accent: "#b7d0a8"
  dark-accent-high: "#c3d9b8"
  dark-accent-wash: "#273b2c"
  dark-rule: "#424e43"
  dark-subtle: "#252e27"
  dark-code: "#202820"
  dark-note: "#29382b"
  dark-note-text: "#d2dfc9"
  light-heading: "#151a16"
  light-text: "#3e4640"
  light-muted: "#586452"
  light-rule: "#d7ddcf"
  light-subtle: "#f0f2eb"
  light-code: "#efefe8"
  light-inline-code: "#e9ede2"
  light-accent-wash: "#e9eee2"
  sheet: "#f1f1e9"
  sheet-middle: "#e7e9df"
  sheet-back: "#e0e4d8"
  bar-track: "#dce0d6"
  bar: "#a7b09e"
  bar-emphasis: "#47664a"
  pipeline-surface: "#eff1e9"
  syntax-surface: "#e1e6d9"
  home-dark-sage: "#7f9078"
  home-dark-muted: "#c4cdc0"
  home-dark-panel: "#29332b"
  home-dark-sheet: "#263028"
  home-dark-sheet-middle: "#303b31"
  home-dark-sheet-back: "#374337"
  home-dark-bar-track: "#354137"
  home-dark-working: "#253027"
  home-dark-hover: "#344631"
  home-dark-pipeline: "#202b23"
  home-dark-benchmark: "#232a24"
  home-dark-syntax: "#334030"
typography:
  display:
    fontFamily: "\"Source Serif 4 Variable\", Georgia, serif"
    fontSize: "clamp(4rem, 5.35vw, 5.7rem)"
    fontWeight: 650
    lineHeight: 1.06
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "\"Source Serif 4 Variable\", Georgia, serif"
    fontSize: "clamp(2.4rem, 3.4vw, 3.6rem)"
    fontWeight: 650
    lineHeight: 1.12
    letterSpacing: "-0.02em"
  process-title:
    fontFamily: "\"Source Serif 4 Variable\", Georgia, serif"
    fontSize: "clamp(1.15rem, 1.5vw, 1.5rem)"
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: "-0.01em"
  body:
    fontFamily: "\"Hanken Grotesk Variable\", \"Segoe UI\", sans-serif"
    fontSize: "1rem"
    lineHeight: 1.6
    fontWeight: 400
  reading-body:
    fontFamily: "\"Hanken Grotesk Variable\", \"Segoe UI\", sans-serif"
    fontSize: "1rem"
    lineHeight: 1.75
    fontWeight: 400
  docs-headline:
    fontFamily: "\"Source Serif 4 Variable\", Georgia, serif"
    fontSize: "3.15rem"
    fontWeight: 650
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  docs-section:
    fontFamily: "\"Source Serif 4 Variable\", Georgia, serif"
    fontSize: "2rem"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.015em"
  label:
    fontFamily: "\"Hanken Grotesk Variable\", \"Segoe UI\", sans-serif"
    fontSize: "0.875rem"
  action:
    fontFamily: "\"Hanken Grotesk Variable\", \"Segoe UI\", sans-serif"
    fontSize: "0.9rem"
    fontWeight: 500
  code:
    fontFamily: "\"JetBrains Mono Variable\", ui-monospace, monospace"
rounded:
  badge: "4px"
  navigation: "5px"
  control: "6px"
  working-surface: "7px"
  dialog: "8px"
  pill: "999px"
spacing:
  gutter-mobile: "1.25rem"
  block: "1.5rem"
  column: "2.5rem"
  section: "5rem"
  section-mobile: "3rem"
  table-inline: "0.75rem"
components:
  button-primary:
    backgroundColor: "{colors.moss}"
    textColor: "{colors.paper}"
    rounded: "{rounded.pill}"
    padding: "1rem 1.4rem"
    typography: "{typography.action}"
  button-primary-hover:
    backgroundColor: "{colors.moss-deep}"
  button-primary-dark:
    backgroundColor: "{colors.dark-accent}"
    textColor: "{colors.dark-paper}"
    rounded: "{rounded.pill}"
    padding: "0.8rem 1.25rem"
  button-primary-dark-hover:
    backgroundColor: "{colors.dark-accent-high}"
  copy-button:
    backgroundColor: "{colors.moss}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
    padding: "0.7rem 1.1rem"
  budget-selected:
    backgroundColor: "{colors.moss}"
    textColor: "{colors.paper}"
    rounded: "{rounded.pill}"
    padding: "0.5rem 0.7rem"
  fidelity-example:
    textColor: "{colors.moss}"
    typography: "{typography.code}"
  working-surface:
    backgroundColor: "{colors.working-surface}"
    rounded: "{rounded.working-surface}"
    padding: "1.75rem"
  navigation-current-light:
    backgroundColor: "{colors.light-accent-wash}"
    textColor: "{colors.moss}"
    rounded: "{rounded.navigation}"
  navigation-current-dark:
    backgroundColor: "{colors.dark-accent-wash}"
    textColor: "{colors.dark-accent-high}"
    rounded: "{rounded.navigation}"
  home-theme-selector:
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    width: "6.25em"
  configuration-entry:
    padding: "0.9rem 0.75rem"
  footer-roadmap:
    textColor: "{colors.muted}"
    typography: "{typography.label}"
  search-trigger:
    rounded: "{rounded.control}"
  note-light:
    backgroundColor: "{colors.working-surface}"
    textColor: "{colors.moss}"
    rounded: "{rounded.control}"
    padding: "1.1rem 1.25rem"
  note-dark:
    backgroundColor: "{colors.dark-note}"
    textColor: "{colors.dark-note-text}"
    rounded: "{rounded.control}"
    padding: "1.1rem 1.25rem"
---

# Design System: ContextCraft

## Overview

**Creative North Star: "Software Broadsheet"**

ContextCraft reads like a developer publication: expressive serif headlines, warm paper, near-black ink, and moss green actions. Open columns and deliberate whitespace carry the hierarchy; tinted working surfaces appear where code or an interaction needs a bounded home.

The homepage pairs an engraved raster tree illustration with code-native process figures. Homepage and documentation share Light, Dark, and Auto theme preferences; documentation carries the same type and palette into familiar Starlight navigation and search. Page composition remains in the surface brief; this record captures the durable visual language implemented in the shipped code.

**Key Characteristics:**

- Warm paper and ink with moss green actions and sage technical detail.
- Source Serif 4 for readable editorial headings; Hanken Grotesk for reading and controls; JetBrains Mono for code.
- Open layouts, restrained rules, rounded actions, and flat working surfaces.
- Readable code, explicit selection, keyboard focus, and familiar documentation navigation.

## Colors

Warm neutral paper and near-black ink support a single moss accent, with sage and pale green working tones. The frontmatter owns exact values.

### Primary

- **Moss and moss-deep:** Homepage primary actions, copy controls, selected budget controls, and light-theme documentation links/actions. The deeper tone supplies hover feedback.
- **Dark-accent and dark-accent-high:** Light green actions and text emphasis on dark homepage and documentation surfaces. Dark actions use dark-paper text, with the lighter variant on hover.

### Neutral

- **Paper and ink:** Light-theme homepage background and foreground. In dark mode the homepage resolves these roles to dark-paper and dark-heading. Documentation uses matching theme-specific reading colors.
- **Sage, muted, and rule:** Quiet chart segments, supporting copy, connectors, and restrained separators.
- **Panel and working-surface:** Command containers and interactive/code examples. Budget-hover distinguishes control states; benchmark-surface separates the historical chart band.
- **Light documentation:** Light-heading, light-text, and light-muted establish reading hierarchy; light-subtle, light-inline-code, light-code, and light-rule organize controls, literals, and tables. Light-accent-wash marks the current chapter.
- **Dark documentation:** Dark-paper, dark-heading, dark-text, and dark-muted establish reading hierarchy. Dark-subtle, dark-code, dark-rule, dark-note, and dark-note-text keep bounded examples legible. Dark-accent-wash marks navigation selection.

- **Homepage diagram materials:** Sheet, sheet-middle, and sheet-back distinguish stacked source pages; bar-track, bar, and bar-emphasis distinguish chart density and relevance. Pipeline-surface and syntax-surface organize the process band and its nodes without adding elevation.
- **Dark homepage:** Shared dark-paper/dark-heading become page/ink; dark-accent/dark-accent-high become action/default-hover; dark-rule becomes the divider. Home-dark-sage also supplies ordinary bar fill. Home-dark-muted, home-dark-panel, the three home-dark-sheet layers, home-dark-bar-track, home-dark-working, home-dark-hover, home-dark-pipeline, home-dark-benchmark, and home-dark-syntax replace every matching light surface or chart role. Dark-accent supplies emphasized bars. These are theme variants of the existing material roles, not additional brand accents.

**The Working Surface Rule.** Use a tinted surface to hold code, an interactive example, or a note; use open space for ordinary narrative sections.

## Typography

**Display Font:** Source Serif 4 Variable, with Georgia and serif fallbacks.
**Body Font:** Hanken Grotesk Variable, with Segoe UI and sans-serif fallbacks; normal and italic styles are bundled.
**Code Font:** JetBrains Mono Variable, with UI monospace fallbacks, for paths, commands, source, and data literals.

All three families are bundled through @fontsource-variable packages in the shared font stylesheet. Shared body, heading, and code variables connect both homepage and documentation; Starlight's mono variable also carries JetBrains Mono into Expressive Code. Font optical sizing is automatic. The former manually hosted TTF font faces and their page preloads are retired.

Source Serif 4 keeps the publication character with more readable letterforms and relaxed heading leading. Hanken Grotesk supplies normal-weight reading text and controls; JetBrains Mono keeps technical literals distinct. Documentation's contents rail retains sans-serif headings for navigation utility. Headings balance naturally without horizontal squeezing or forced no-wrap constraints.

### Hierarchy

- **Display:** Homepage headline uses the fluid display role with consistent line height (1.06). At the tablet breakpoint it becomes (clamp(3.5rem, 7.4vw, 5rem)); on mobile, (clamp(2rem, 10.5vw, 4.1rem)). The hero grows with its copy rather than imposing a maximum height.
- **Headline:** Editorial section titles use the headline role with relaxed line height (1.12); mobile section titles use (2.5rem). The compact detail introduction uses its own fluid serif size and the same leading, remaining local to that composition.
- **Process title:** Compact serif headings identify numbered stages with weight (650) and line height (1.25); mobile increases these to (1.6rem). Pipeline and fidelity-example headings share this weight and leading at their component-specific sizes.
- **Body:** Normal reading text is weight (400), based on (16px). Homepage prose uses the body role, with supporting section prose at line height (1.7) and maximum measure (60ch). Hero supporting copy has local fluid sizes and line height (1.6). Pipeline descriptions use (1rem); pipeline rows reserve enough prose height before the figures. The quieter footer roadmap uses (0.875rem) with semibold tool names.
- **Documentation:** Reading-body supplies generous leading. Page and section headings use docs-headline and docs-section; below the documentation mobile breakpoint these become (2.5rem) and (1.8rem). Direct prose and lists are limited to (72ch).
- **Label and action:** Sans-serif labels, controls, and navigation remain quieter than editorial titles. Small figure annotations stay attached to their figure. Tables and chart values use tabular numerals.
- **Component-local sizes:** The broad source scale distinguishes reading text from figure annotations and controls. Repeated supporting sizes (0.75rem, 0.8rem, 0.8125rem, 0.85rem, 0.875rem, 0.9rem, 0.9375rem) belong to captions, status, source examples, navigation, and reference content. Diagram-only markers use (0.6rem), (0.65rem), (0.7rem), and (0.72rem); these are attached technical annotations, not defaults for prose. Local responsive or fluid values remain component-specific rather than expanding the global type ramp for every CSS literal.

**The Two Voices Rule.** Use Source Serif 4 for editorial headings, Hanken Grotesk for reading and controls, and JetBrains Mono for technical literals.

## Layout

The homepage uses an open container (91.5% width, maximum 1560px). Below (700px), total horizontal inset is (2.5rem). Main narrative sections have spacious section intervals, reducing to section-mobile on narrow screens. Split introductions, side-by-side examples, and open lists replace repeated card grids.

At desktop widths above (1100px), the process figure has four open columns with shared heading rows through subgrid. The budget and output diagrams share a fluid height (11.43vw) and aligned chart tops. At (1100px) and below, it becomes two columns; at (700px) and below, a single sequence. Below the desktop breakpoint, the budget retains its (172px) minimum height and the output retains its (172px) height. These are figure-specific values, not general card heights.

The repository example becomes two columns with the result spanning below at tablet width. Comparisons, benchmark copy/chart, pipeline, and final command stack on mobile. Static fidelity examples use four columns above (1100px), two through (1100px), and one through (700px). The desktop introduction sits above the examples to give complete source enough reading width. Shared grid tracks keep code blocks equal in height: (20rem) on desktop, (19rem) on tablet, and (18rem) on mobile. These heights belong to the supplied example set, not a global code-container rule. Arrows between process stages disappear when columns wrap. Interactive controls wrap without truncating labels.

Documentation retains Starlight's reading column (46rem), chapter sidebar (17rem), desktop contents rail, and mobile menu/contents controls. The chapter sidebar appears at (50rem), the right rail at (72rem). Configuration reference uses one semantic definition-list representation at every width, organized under three task-oriented section headings. Desktop entries form a three-column grid; through (49.99rem), the same entries stack with visible default labels. All eleven setting anchors remain unique and stable; there are no hidden duplicate desktop/mobile entries. Long literals wrap; ordinary tables and source code retain their overflow behavior.

## Elevation & Depth

Ordinary surfaces are flat: paper, pale green working tones, and restrained rules supply grouping. Expressive Code frames and pagination explicitly remove shadows. Starlight's search dialog retains its framework overlay treatment, including backdrop and shadow; that transient exception does not define ordinary cards. The repository figure's offset paper layers are literal stacked-sheet geometry, not hard offset box shadows.

**The Flat Paper Rule.** Separate ordinary content with space, tone, and restrained rules. Reserve overlay elevation for the search dialog.

## Shapes

Rounded actions soften the precise editorial grid. Desktop primary links use pill corners; mobile primary links use the control radius. Copy buttons, code frames, notes, and mobile menu controls use the control radius. Working examples use working-surface radius; navigation and source badges use their smaller recorded radii. Search dialogs use dialog radius.

The form language also includes square source sheets, straight chart bars, dashed budget bounds, and restrained connector strokes. Keep these functional diagram shapes distinct from rounded controls. The engraved tree is a shipping raster illustration; other process figures use HTML/CSS/SVG. The dark homepage adapts the same hero raster with CSS invert(1) hue-rotate(180deg); its source asset is unchanged. New artwork should follow the same restrained paper-and-ink character and retain provenance.

## Components

### Buttons and copy controls

Primary actions are moss with paper text and moss-deep hover on light homepage/documentation. Both dark surfaces reverse to light green with dark-paper text. Homepage primary links use button-primary; documentation actions use padding (0.8rem 1.25rem) and minimum height (44px). Both become softly rectangular on mobile. The homepage header contains Documentation, GitHub, and the theme selector; command copying lives in the hero. Navigation links and the selector share a 44px control height, 20px line height, inherited font size, and centered alignment. Individual link translations are not used.

Copy controls use the copy-button token with minimum height (50px) normally. The hero uses a compact icon-only (44px) square with a visually hidden accessible label and a native tooltip. On successful copy, its icon becomes a checkmark for 2.2 seconds. Success confirmation is screen-reader-only; error guidance flows in the command grid below the command, spanning both columns so it cannot overlap the helper text. The install command sits on panel with working-surface corners. Its two-column grid gives the command a shrinkable, wrapping track and keeps the copy button inside the panel at every width. The final `contextcraft .` token pair stays together when wrapping. Clipboard success/failure produces visible feedback and a status message; failed copying leaves the command selectable.

Copy controls start disabled until their handlers are installed. During a request they use `aria-busy` and `aria-disabled`, a duplicate-activation guard, reduced opacity (0.65), and a wait cursor while remaining keyboard-focusable. A new request clears old success feedback; completion always clears pending attributes. Missing or denied clipboard support exposes visible recovery and selects the source command. Without JavaScript, copy buttons are hidden and commands remain readable in a single-column panel.

A muted helper line sits below the hero command: (0.875rem / 14px), line height (1.55), maximum measure (65ch), and top margin (0.75rem). It explains repository location, the uv prerequisite, and terminal output, with green links to installation guidance. The final installation-options link stays on one line so its label remains intact. This adjacent assistance stays outside the command panel and its failure message.

### Selection controls

Budget choices are actual buttons in a labeled group with aria-pressed. Targets are at least (44px) in both dimensions; selected choices use budget-selected and unselected choices remain transparent. Allocation widths transition over (240ms) using cubic-bezier(0.16, 1, 0.3, 1), with a polite text update. Budget buttons start disabled until initialized and accept only the known values. Without JavaScript the controls are hidden while the default 8k illustration and its text remain readable.

Fidelity is shown once as four static examples: full source, skeleton, signatures, and paths. The supplied UserService class carries the same get method through source, skeleton, and signatures; the paths example is a directory tree. Shared title, description, code, and note tracks align the examples without adding selection controls. Code uses pre-wrapped lines with normal overflow wrapping, monospace type (0.8125rem), and line height (1.65). Budget selection and command copying remain the interactive demonstrations.

### Working surfaces and figures

Interactive results use pale green, lightly rounded, flat surfaces. Static fidelity examples remain open. Code stays monospace with readable leading and overflow where needed. Narrative lists and feature descriptions remain open. Process bars, token allocation, and source sheets are conceptual figures with explicit labels; benchmark values keep their historical scope beside the data.

Repository entries use authored inline SVG folder/file icons with round stroke caps and joins, not text glyphs or CSS placeholder boxes. The budget figure separates a (3.8rem) relevance scale from a flexible plot in a grid. Its down arrow sits between more/less labels; the plot distributes bars above the caption while matching the Context figure’s height and top alignment.

The task-to-context connector uses one SVG path in a (100 × 24) viewBox, rendered full-width at (24px) tall. The shaft and arrowhead meet at the same coordinate (99, 12). A non-scaling stroke keeps their shared weight at (1.5px) as available width changes; no separate CSS line or nested SVG is used.

The five pipeline illustrations are native HTML/CSS with inline SVG icons where needed: included/excluded/redacted source rows; a function branching to args/body; api.py and routes.py feeding auth.py; four paper samples for detail tiers; and a segmented allocation bar bounded by a token limit. Figures share a (9rem) illustration area and maximum width (260px), with aligned desktop row tracks. Mobile moves each illustration beside its stage text. Muted struck-through excluded files, solid redaction marks, fine connectors, moss emphasis, and sage secondary bars communicate the operation without rasterized labels.

### Navigation and search

The homepage has a compact serif wordmark with Documentation, GitHub, and a native theme select. Mobile shortens Documentation to Docs. Through (380px), the header wraps into two rows with navigation spanning the full second row, preserving all controls at (320px). Documentation retains Starlight chapter disclosures, current-page state, contents, search, and theme selector. Current chapters use a theme-specific green wash and text accent; hover uses the subtle surface. Nested sidebar lists have no decorative vertical rules.

Both surfaces use the shared guarded theme provider and native selector override, retaining Starlight’s select presentation. Its width is (6.25em), minimum height (44px), type size (0.875rem), reduced to (0.8125rem) through (700px), and foreground follows muted text. Light/Dark/Auto share the preference under `starlight-theme`; Auto follows system changes, and cross-tab preference changes update both surfaces. Invalid stored values resolve to Auto. If browser storage is unavailable, the selected preference persists in memory for the current page. The head provider resolves the initial theme before paint; the selector remains inert until handlers are ready and is hidden without JavaScript. Pointer selection suppresses the persistent focus outline; keyboard focus remains visible. Native option surfaces follow the selected theme.

Search uses a borderless subtle-surface trigger with control corners and minimum height (44px), becoming an icon control on mobile. Its bounded desktop dialog uses dialog corners; mobile retains the framework overlay. The input placeholder stays opaque and uses the theme's secondary text. Search focus is inset (2px outline with -2px offset), avoiding a detached second frame.

### Documentation code, notes, and reference

Expressive Code retains Vitesse Dark and Vitesse Light syntax themes, built-in copy feedback, softly rounded frames, and no shadow; terminal headers are hidden. Notes and asides use theme-specific pale/dark green fill and text with no border. Pagination stays open until hover adds a subtle surface; its link titles use Source Serif 4.

Ordinary reference tables use subtle headers, tabular numerals, and padding (0.8rem 0.75rem). Configuration instead uses semantic definition lists from shared settings data, under three task headings: Budget, focus, and output; Files and privacy; Execution and token accounting. Each setting appears once, with a linked name, default, meaning, and stable identifier. Desktop headings are visual aids hidden from assistive technology; names/defaults/meanings form grid columns (1fr / 1.1fr / 2.1fr), with gap (1.25rem), padding (0.9rem 0.75rem), and a fine top rule. Entries have scroll margin (6rem) and zero block margins, overriding inherited prose sibling spacing so the rows remain continuous. Through (49.99rem), the same entry stacks into one column with gap (0.5rem) and padding (1.25rem 0); the Default label becomes visible and the desktop heading disappears. Long literals wrap naturally. Empty groups, duplicate setting names, and unknown names fail the build rather than silently omit reference content. Source badges use moss/paper with badge corners.

### Footer disclosure and supporting guidance

Footer navigation links use inline flex with centered content and minimum height (44px). Planned tools use a native details disclosure in the footer after the main content, collapsed by default. Its muted summary and prose use (0.875rem); the summary retains a minimum target height (44px) and vertical padding (0.75rem). The three tool descriptions use a definition list with three equal columns and gap (2rem), stacking through (700px) with gap (1.25rem). Semibold names use the primary foreground; descriptions retain quiet reading text. This is a secondary disclosure, not a main narrative panel; the final command action follows the historical benchmark directly.

Documentation keeps prerequisite guidance close to runnable examples, connects the uv and pip installation routes through ordinary prose links, and presents SDK recovery guidance as concise symptom/remedy bullets with linked references. These use the existing reading hierarchy rather than new alert or card variants.

### Focus and motion

Homepage keyboard focus uses a moss outline (2px), offset (5px), or (4px) for buttons. Documentation uses the theme's text accent with offset (4px), except for inset search focus. Selection uses moss/paper. Reduced motion disables transitions, animations, and smooth scrolling; allocation movement communicates selection rather than decorating reading content.

Forced-colors styles give copy buttons and primary links a system-color boundary (1px ButtonText), foreground (ButtonText), and fill (ButtonFace). Selected budgets retain a (2px) ButtonText outline inset by (3px); the task connector uses CanvasText. These are source-defined adaptations; operating-system forced-colors behavior has not been browser-verified in this pass.

## Do's and Don'ts

### Do:

- **Do** use the same paper, moss, serif, and sans-serif vocabulary across homepage and documentation.
- **Do** reserve tinted working surfaces for examples, code, notes, and selected states.
- **Do** preserve visible focus, pressed/current states, clipboard feedback, and reduced-motion behavior.
- **Do** stack complex figures and retain readable code and labels on narrow screens.
- **Do** use one responsive semantic representation for configuration entries, preserving unique anchors and name/default/meaning order.

### Don't:

- **Don't** revive the previous navy/rust palette or blanket square-corner treatment.
- **Don't** wrap every narrative section in a card or add decorative shadows to reading content.
- **Don't** replace familiar documentation navigation with homepage composition.
- **Don't** shrink long code or settings to force a desktop layout onto a narrow screen.
- **Don't** present conceptual illustrations or historical charts as unlabeled current product measurements.

The task-to-context connector uses one continuous moss stroke: its rule and arrowhead share the same 1.5px weight and join without a gap.

Theme selection retains native select behavior. Pointer interaction suppresses its outline; a keypress or blur clears the pointer marker so keyboard focus keeps the standard visible indicator.
