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
  "card_borders": ["#RRGGBB", ...]
}}

Field descriptions:
- background_color: Slide background color (based on design_principles color palette)
- text_colors: Array of colors for title, body, and secondary text
- title_font_pt: Slide title font size (28~36 range)
- body_font_pt: Body text font size (16~22 range)
- card_fills: Array of card/shape background colors
- card_borders: Array of card/shape border colors (empty array if none)
</output_format>

<input>
{outline_json}
</input>
