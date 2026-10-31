<task>
Create this deck's design intent from the outline and presentation context.
Return JSON matching response_schema: theme, tone, anti_slop and page_requests.
Ground visual choices in the subject, audience, viewing setting and intended outcome.
</task>

<design_judgment>
Choose a coherent palette, type hierarchy and visual treatment that help this specific
content. Existing brand/user constraints take priority over generic design preferences.
Cards, bullets, gradients and large numbers are options when they serve the material;
do not apply or reject them as a universal style. Avoid inventing evidence or decoration
to make a sparse slide look busy. Repetition may support comparisons and continuity.
</design_judgment>

<parts>
- theme: Choose background and text colors, optional card fills/borders, type scale and
  region bands. The schema's title_font_pt range is 28–36 and body_font_pt is 16–22;
  these are deck defaults, not the permitted size range for every individual element.
- tone: Describe the visual hierarchy and narrative arc: how the deck opens, develops,
  changes emphasis and lands. Add a recognizable treatment when useful. Keep this global
  direction concise without a sentence quota or a requirement to invent a signature motif.
- anti_slop: Supply concrete guidance for all five fields below. Tie it to the outline
  rather than repeating a general anti-pattern checklist.
- page_requests: Add selective deviations when a particular slide needs direction beyond
  the shared system. An empty list is valid. Do not generate a compulsory quota of changes.
</parts>

<anti_slop_guardrails>
- subject_specificity: Identify subject-specific visual material, terminology or artifacts.
- visual_hierarchy: Explain the primary emphasis and how supporting evidence stays readable.
- layout_rhythm: Describe useful variation and continuity. Three consecutive uses of the
  same actual archetype are a review signal; preserve purposeful repetition.
- decoration_policy: Explain when decoration supports grouping, navigation or a brand motif.
- content_grounding: Keep claims, examples, supplied sources and assumptions distinguishable.
</anti_slop_guardrails>

<theme_contract>
Choose background_image="none" for solid backgrounds or "gradient" when automatic
cover/closing imagery serves the deck. This explicit policy controls export; prose alone
does not disable imagery. Legacy responses that omit it default to "gradient".
The schema requires header_region, content_region and footer_region. Reliable defaults
are (top_px,height_px)=(64,64), (148,508), (664,24). Choose different valid bands when
appropriate. Header ends before content, content ends before footer, and footer ends
at or before 688px. Individual slides need not use a footer cell.
</theme_contract>

<page_requests_contract>
Each request has a 1-based number, the exact outline title and a nonblank request.
Use existing slide numbers/titles; do not create new slides or silently rebind a request.
</page_requests_contract>

<context>
Total slides: {total_slides}
Color theme: {color_theme}
</context>
<input>
{outline_json}
</input>
