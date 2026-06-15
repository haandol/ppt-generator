---
name: presentation-design
description: Guidance for distinctive, intentional presentation (slide deck) design that doesn't read as AI slop. Use when generating or reshaping a slide deck with ppt-generator — to set the deck's visual identity, narrative arc, per-slide information density, and to fill in DESIGN.md. Helps avoid the title+three-bullets, icon-card-trio, gradient-wash defaults.
---

# Presentation Design

Approach this as the design lead at a studio that makes decks a room remembers — not the ones that dissolve into every other quarterly review. The client has sat through a hundred title-and-three-bullets slideshows and is paying for a deck with a point of view: deliberate, opinionated choices about palette, type, layout, and narrative that are specific to *this* talk, to *this* audience, in *this* room. Take one real aesthetic risk you can justify.

This skill is the taste layer in front of ppt-generator. Its output is not slides directly — it is the **design intent** that goes into `DESIGN.md` (the human-editable single source of design intent), which the generation pipeline then turns into concrete slide specs. Think in terms of what fills DESIGN.md's three regions: the global design system, the global tone & direction, and the per-slide special requests.

## Ground it in the talk

A deck is not a document and not a webpage. It is a *spoken argument* with a visual track. Before designing, pin three things and state them:

- **The subject** — what is this actually about, in one concrete sentence.
- **The audience and the room** — executives in a boardroom, engineers at a conference, investors over video. This sets contrast, density, font floor, and formality.
- **The single job of the deck** — to decide, to teach, to persuade, to report. Every slide either serves this job or gets cut.

If the brief doesn't pin these, pin them yourself and say so. Check memory for the human's prior decks, preferences, and brand. The subject's own world — its vocabulary, its artifacts, its data — is where distinctive choices come from. Build with the talk's real content throughout, not lorem-ipsum stand-ins.

## Design principles

**The deck is the unit, not the slide.** A webpage is one canvas; a deck is a *sequence*. The equivalent of a web hero is the **opening slide as thesis** plus the **arc across slides**. Design the rhythm: where it opens loud, where it breathes, where the turn happens, where it lands. A great deck has tension and release — not 18 slides at the same pitch. This narrative axis has no equivalent in web design and is where most AI decks fail: they treat every slide as an independent template fill.

**One idea per slide.** The cardinal rule of spoken decks. If a slide needs three bullets to make one point, the point is the headline and the bullets are probably speaker notes. Dense slides are for documents people read alone; a deck supports a person talking. When in doubt, cut and let the next slide carry the rest.

**Typography carries the personality — and it has to survive projection.** Pair a characteristic display face with a clean body face, deliberately, not the families you'd reach for on any deck. Set a real type scale. But unlike web: type has a hard floor (body rarely below ~18–20pt for a projected room), high contrast against the background is non-negotiable, and line length per slide is short. Make the type treatment memorable *within* those constraints — that is the craft.

**Structure encodes the argument, not decoration.** Section dividers, an agenda, running progress markers, slide numbering — use them only when the deck's logic actually is sequential or sectioned. Numbered markers (01 / 02 / 03) belong on a real process or timeline, not on three parallel features. Question every structural device: does it tell the audience where they are in the *argument*, or is it just furniture?

**Restraint reads as confidence; clutter reads as AI.** Spend your boldness in one place — a signature treatment that embodies the talk — and keep every other slide quiet and disciplined. A deck where every slide shouts has no emphasis left for the slide that matters.

**Match complexity to the room.** A data-dense engineering talk can carry detailed diagrams; a vision keynote needs space and a few enormous statements. Pick the density the room and the job call for, and hold it consistently.

## Calibration: what presentation AI slop looks like

AI-generated decks cluster around a recognizable set of defaults. They are not *wrong* — they are *unchosen*, applied regardless of subject. Where the brief leaves an axis free, don't spend that freedom on:

- **Every slide is title + three bullets.** The single most common tell. Uniform structure means no slide has been thought about as itself.
- **The icon-card trio.** Three (or four) rounded cards, each with a generic icon, a two-word heading, and a line of filler. Decoration pretending to be structure.
- **Gradient wash + glassmorphism** as a substitute for a real palette.
- **Stock-metaphor imagery** — handshakes, glowing brains, rising arrows, abstract network dots.
- **A big number with a small label and a gradient accent**, used as the answer to every "make this slide pop."
- **Uniform pitch** — 20 slides at identical density and emphasis, no arc, no breath.
- **Decorative full-bleed background images** that fight the text and lower contrast.

Where the brief explicitly asks for one of these, follow the brief — its words win. Where it's silent, choose something true to *this* talk instead.

## Process: brainstorm, critique, then write DESIGN.md

Work in two passes, mostly in your head; show the user high-confidence ideas, not raw exploration.

**Pass 1 — a compact deck design system:**

- **Palette** — 4–6 named hex values. State background, primary text, secondary text, and 1–2 accents. Must clear projection contrast.
- **Type** — display face + body face (+ a data/caption face if the deck has charts or footnotes), each with a role and a size in the scale. State the body floor.
- **Layout system** — the reusable slide archetypes this deck will draw from (e.g. statement slide, two-column compare, full-bleed quote, diagram slide, data slide). Sketch the key ones as ASCII wireframes to compare. Define the consistent header/content/footer bands.
- **Narrative arc** — one line per movement: how the deck opens, where it turns, how it closes. Mark which slides are *loud* and which *breathe*.
- **Signature** — the one element the deck is remembered by, embodying the talk (a recurring visual motif, a typographic treatment, a way of showing data). Used with restraint.

**Pass 2 — critique against the brief before writing anything.** Work through what you'd produce for any similar talk; if a choice matches that generic default rather than this brief, revise it and say what changed and why. Confirm the palette isn't a wash, the layout isn't title+bullets-everywhere, the arc actually has tension. Apply Chanel's rule: remove one accessory.

**Then translate the plan into DESIGN.md:**

- Global design system → the structured `key: value` region (theme, palette hexes, font sizes, region bands) — these parse deterministically.
- Global tone & direction → prose: audience, room, formality, density, the arc, the signature.
- Per-slide special requests → only the slides that deviate from the default archetype, keyed by `number. title` (e.g. `### 3. Architecture Overview`). Don't write a request for every slide — only where a slide needs to break the system on purpose.

Hand DESIGN.md to the user to edit, then let the pipeline generate from it. After generation, a screenshot pass (visual_qa) is the deck equivalent of "take a screenshot as you build" — use it to catch contrast, overflow, and slides that drifted back toward slop.

## Writing the words on slides

Slide copy is design material. The spoken track carries the detail; the slide carries the *anchor*.

- **Headlines are claims, not topics.** "Revenue grew 40% on retention, not acquisition" beats "Q3 Revenue." A topic labels; a claim argues.
- **Cut to the spoken floor.** If the presenter will say it aloud, it doesn't need to be on the slide. Move it to speaker notes. What stays is what the audience needs to *see*.
- **Active voice, sentence case, plain verbs.** One job per element — a headline claims, a label labels, a caption sources. Nothing does double duty.
- **Be specific over clever.** Concrete numbers, named things, real examples. Cleverness in deck copy reads as filler.
- **Consistent vocabulary across the deck.** The same concept keeps the same name from agenda to conclusion — that's how an audience tracks an argument.

## Quality floor (don't announce it, just clear it)

- Text contrast survives a projector and a bright room.
- Body type stays above the legibility floor for the back row.
- No slide overflows its safe area; the footer band stays clear.
- The deck holds one consistent system — a stranger could tell two slides came from the same deck.
- One idea per slide, an arc across slides, boldness spent in one place.
