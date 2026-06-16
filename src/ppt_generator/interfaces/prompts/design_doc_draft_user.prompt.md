<task>
You are the design lead for this specific deck. Read the entire presentation outline below and produce the **design intent** that will steer every slide — not just numeric theme values, but the deliberate tone and the few per-slide decisions that keep this deck from looking like a generic auto-generated slideshow.

Your output has three parts: a numeric design system (theme), a global tone & direction (prose), and a small set of per-slide requests (prose) — only for slides that would otherwise collapse into a default template.
</task>

<grounding>
First pin three things from the outline and let them drive every choice:
- Subject — what this deck is actually about, concretely.
- Audience & room — who is watching and where (executives in a boardroom, engineers at a conference, general customers). This sets formality, contrast, font sizes, density.
- The single job of the deck — to decide, to teach, to persuade, to report.
Adjust color intensity, font sizes, and card styles to match. A dense technical talk can carry detail; a customer/vision pitch needs space and a few large statements.
</grounding>

<avoid_ai_slop>
Auto-generated decks cluster around a recognizable set of unchosen defaults. Where the outline leaves a choice free, do NOT spend it on these:
- Every slide as title + three bullets — uniform structure means no slide was thought about as itself.
- The icon-card trio/quad — three or four rounded cards, each a two-word heading + a line of filler, repeated on slide after slide. This is decoration pretending to be structure. If several content slides all carry parallel items, do NOT let them all become identical card rows.
- Gradient wash / glassmorphism as a substitute for a real palette.
- A big number with a small label and a gradient accent as the answer to every "make this pop".
- Uniform pitch — every slide at identical density and emphasis, no arc, no breath.
- Numbered markers (01 / 02 / 03) on parallel features that are not an actual sequence.

The point is not to ban these and replace them with a different uniform — it is to choose what is true to THIS talk.
</avoid_ai_slop>

<how_to_write_each_part>

**Numeric design system (theme):** Pick a real palette with projection-grade contrast. The background, primary text, secondary text, and 1–2 accents must be deliberate — not a gradient wash. Set font sizes the back row can read (body floor ~16pt in cards, slide titles 28–36pt).

**Global tone & direction (prose, 3–6 sentences):** State the audience and room, the formality and density you chose, and — most importantly — the **narrative arc**: how the deck opens (the thesis), where it turns, where it breathes, how it lands. Name ONE signature treatment the deck is remembered by (a recurring motif, a typographic move, a consistent way of showing the key idea), to be used with restraint. This prose is injected into every slide's generation, so keep it about direction, not slide-by-slide detail.

**Per-slide requests (prose, SELECTIVE):** Look at the outline slide by slide. For the few slides that would otherwise become a generic card trio or sit flat in the arc, write a short deviation request that breaks the default — e.g. turn a set of parallel items into a comparison or a single dominant statement, make a turning-point slide a full-bleed one-liner, let a "breathe" moment be mostly negative space, render a process as an actual left-to-right diagram. 
- Be SELECTIVE: only flag slides that genuinely need to break the system. A deck where every slide has a special request is just a new uniformity. Aim for a minority of slides — concentrate the boldness, keep the rest quiet and disciplined.
- Do NOT add a request for the title slide or closing slide unless it genuinely needs one.
- Key each request by the slide's 1-based number AND its exact title from the outline.
- If no slide needs a deviation, return an empty list — that is a valid, disciplined answer.
</how_to_write_each_part>

<context>
Total slides: {total_slides}
Color theme: {color_theme}
</context>

<output_format>
Output ONLY the following JSON (no other text, no markdown fence):
{{
  "theme": {{
    "background_color": "#RRGGBB",
    "text_colors": ["#RRGGBB", "..."],
    "title_font_pt": number,
    "body_font_pt": number,
    "card_fills": ["#RRGGBB", "..."],
    "card_borders": ["#RRGGBB", "..."],
    "header_region": {{"top_px": number, "height_px": number}},
    "content_region": {{"top_px": number, "height_px": number}},
    "footer_region": {{"top_px": number, "height_px": number}}
  }},
  "tone": "3-6 sentence prose: audience/room, formality, density, the narrative arc, the one signature treatment.",
  "page_requests": [
    {{"number": <1-based int>, "title": "<exact slide title from outline>", "request": "<short prose deviation for this slide>"}}
  ]
}}

Theme field rules:
- background_color: slide background (deliberate, not a wash)
- text_colors: [title, body, secondary] colors
- title_font_pt: 28~36
- body_font_pt: 16~22
- card_fills / card_borders: arrays (empty array if none)
- header_region: default top_px=64, height_px=64
- content_region (REQUIRED): default top_px=148, height_px=508
- footer_region: default top_px=664, height_px=24
- All three regions are presentation-level — every slide shares the SAME pixel bands for cross-slide consistency.
- header_region.top_px + header_region.height_px <= content_region.top_px
- content_region.top_px + content_region.height_px <= footer_region.top_px
- footer_region.top_px + footer_region.height_px <= 688

page_requests rules:
- Selective — a minority of slides, only those that must break the default. Empty list is valid.
- number is 1-based and title must match the outline exactly (used to bind the request to the slide).
</output_format>

<input>
{outline_json}
</input>
