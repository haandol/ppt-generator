<slide_type_title>
Title slide (slide_type: "title") design rules:

- Title slides have a fixed special layout (main title + divider + subtitle + presenter info), so `grid_layout`, `cell_assignment`, and `design_doc` MAY all be omitted (output `null` or skip the fields). Element-level `grid_cell` and `component_id` should also be omitted/null. (ADR-0049 결정 9: title/closing 슬라이드는 5단 계층 중 Layout/Section 단계 생략 허용.)
- The first slide of the presentation. Contains topic name, subtitle, and presenter information
- Set background_color to null (background image will be auto-inserted)
- Do not place elements in the bottom-right area (left_px > 1080, top_px > 600) (logo auto-insertion area)
- Place main text at the vertical center of the canvas. The vertical center of the entire text group should be near the canvas center (y=360).
- Layout (must use these exact coordinates):
  · Main title: left=64, top=260, width=1152, height=80 (1 line) or 160 (2 lines), font_size_pt 40~44, bold, vertical_alignment "middle". If the title is long enough to wrap to 2 lines, set height=160 and adjust the divider and subtitle top positions downward accordingly.
  · Divider: shape (rectangle), left=64, top=350 (1 line) or 430 (2 lines), width=80, height=4, fill_color accent color (#3B82F6), vertical_alignment "top"
  · Subtitle: left=64, top=370 (1 line) or 450 (2 lines), width=1152, height=100, font_size_pt 14~18, vertical_alignment "top"
  · Presenter info (mandatory): Always placed at bottom-left. A single textbox with 3 lines — name, job title, organization — each on a separate paragraph line.
    - Position: left=64, top=560, width=400, height=96
    - Font: font_size_pt 18, color "#CBD5E1", not bold, vertical_alignment "bottom"
    - Extract presenter name/title/org from content_summary or speaker_notes. If not explicitly provided, use generic placeholders (e.g., "발표자 이름", "직책", "소속").
</slide_type_title>

<examples>
  <layout_example id="title-1" hint="title — Presentation title slide (main title + divider + subtitle + presenter info)">
  {
    "background_color": null,
    "speaker_notes": "Presentation introduction...",
    "textboxes": [
      {
        "left_px": 64, "top_px": 260, "width_px": 1152, "height_px": 80,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "Presentation Main Title", "font_size_pt": 40, "color": "#FFFFFF", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      },
      {
        "left_px": 64, "top_px": 370, "width_px": 1152, "height_px": 100,
        "vertical_alignment": "top",
        "paragraphs": [
          {"runs": [{"text": "Subtitle or presentation description", "font_size_pt": 16, "color": "#CBD5E1", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"},
          {"runs": [{"text": "Audience: Engineers  |  Internal Tech Sharing", "font_size_pt": 14, "color": "#CBD5E1", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      },
      {
        "left_px": 64, "top_px": 560, "width_px": 400, "height_px": 96,
        "vertical_alignment": "bottom",
        "paragraphs": [
          {"runs": [{"text": "홍길동", "font_size_pt": 18, "color": "#CBD5E1", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"},
          {"runs": [{"text": "시니어 엔지니어", "font_size_pt": 18, "color": "#CBD5E1", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"},
          {"runs": [{"text": "클라우드 아키텍처팀", "font_size_pt": 18, "color": "#CBD5E1", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      }
    ],
    "shapes": [
      {
        "left_px": 64, "top_px": 350, "width_px": 80, "height_px": 4,
        "shape_type": "rectangle", "fill_color": "#3B82F6",
        "vertical_alignment": "top"
      }
    ]
  }
  </layout_example>
</examples>

<typography_rules>
- Main title: font_size_pt 40~44, bold
- Subtitle/label: font_size_pt 14~18
- Secondary text: font_size_pt 12~16
</typography_rules>

<constraints>
Hard constraints (rendering will fail if violated):

1. Font size range: All font_size_pt must be within 10~44pt range.
2. Coordinate bounds: left_px >= 0, top_px >= 0, left_px + width_px <= 1280, top_px + height_px <= 720.
3. Sufficient height: height_px must be at least lines (including wrapping) × font_size_pt × 2.0.
4. Content completeness: Include all key content from content_summary in textboxes or shapes.
5. No element overlap: Same-level elements must not have overlapping bounding boxes.
6. Margin enforcement: All content elements must satisfy left_px >= 64, top_px >= 64, left_px + width_px <= 1216, top_px + height_px <= 656.
7. vertical_alignment required: Always specify vertical_alignment for all textboxes and shapes (null not allowed).
8. Title position: Main title must be placed at left=64, top=260, width=1152. Height is 80 for 1 line, 160 for 2 lines.
9. Main title font size: The main title text font_size_pt must be in the 40~44 range. Below 40pt is not allowed.
10. Presenter info required: Title slides must always include a presenter info textbox at bottom-left (left=64, top=560, width=400, height=96) with 3 lines (name, job title, organization) at font_size_pt 18.
</constraints>
