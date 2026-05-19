<task>
Analyze the entire presentation outline below and generate a design theme summary (design_summary) as JSON that will be consistently applied across all slides.

First, identify the presentation's purpose and tone:
- Purpose: Determine the type — technical education, decision proposal, performance review, architecture introduction, etc.
- Tone: Estimate formality level, technical depth (overview vs. deep-dive), and audience level (executives vs. engineers)
- Adjust design direction accordingly — color intensity, font sizes, card styles, etc.
</task>

<context>
Total slides: {total_slides}
Color theme: {color_theme}
</context>

<output_format>
Output only the following JSON format (no other text):
{{
  "background_color": "#RRGGBB",
  "text_colors": ["#RRGGBB", ...],
  "title_font_pt": number,
  "body_font_pt": number,
  "card_fills": ["#RRGGBB", ...],
  "card_borders": ["#RRGGBB", ...],
  "header_region": {{"top_px": number, "height_px": number}},
  "content_region": {{"top_px": number, "height_px": number}},
  "footer_region": {{"top_px": number, "height_px": number}}
}}

Field descriptions:
- background_color: Slide background color (based on design_principles color palette)
- text_colors: Array of colors for title, body, and secondary text
- title_font_pt: Slide title font size (28~36 range)
- body_font_pt: Body text font size (16~22 range)
- card_fills: Array of card/shape background colors
- card_borders: Array of card/shape border colors (empty array if none)
- header_region: Top y-axis band reserved for slide titles (recommended). Default: top_px=64, height_px=64 (covers title at top=72, height=48 with margin).
- content_region: Middle y-axis band where the body content sits (REQUIRED). Default: top_px=148, height_px=508 (covers 148~656).
- footer_region: Bottom y-axis band for footnotes/source/page numbers (optional). Default: top_px=664, height_px=24 (sits above the 32px bottom margin). When a slide does not need a footer it simply omits cells in this region — the pixel band itself is still reserved for cross-slide consistency.

Region rules:
- All three regions are presentation-level — every slide shares the SAME pixel ranges for cross-slide visual consistency.
- header_region.top_px + header_region.height_px <= content_region.top_px
- content_region.top_px + content_region.height_px <= footer_region.top_px (when footer is used)
- footer_region.top_px + footer_region.height_px <= 688 (32px bottom margin enforced)
- Choose values that match the presentation tone. For dense technical decks, header may be smaller (e.g., height_px=56) to expand content. For executive decks, header may be larger to give the title more breathing room.
</output_format>

<input>
{outline_json}
</input>
