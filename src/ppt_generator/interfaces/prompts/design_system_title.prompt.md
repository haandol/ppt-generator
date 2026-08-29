<slide_type_title>
Title slide (slide_type: "title") design rules:

- Title slides have a fixed special layout (main title + divider + subtitle + presenter info), so `grid_layout`, `cell_assignment`, and `design_doc` MAY all be omitted (output `null` or skip the fields). Element-level `grid_cell` and `component_id` should also be omitted/null. (결정 9: title/closing 슬라이드는 5단 계층 중 Layout/Section 단계 생략 허용.)
- The first slide of the presentation. Contains topic name, subtitle, and presenter information
- Set background_color to null (background image will be auto-inserted)
- Reserve the bottom-right area (left_px > 1080, top_px > 600) for the auto-inserted logo.
- Keep the main text group visually centered near y=360.
- Layout (must use these exact coordinates):
  · Main title: left=64, top=260, width=1152, height=80 (1 line) or 160 (2 lines), font_size_pt 40~44, bold, vertical_alignment "middle". If the title is long enough to wrap to 2 lines, set height=160 and adjust the divider and subtitle top positions downward accordingly.
  · Divider: shape (rectangle), left=64, top=350 (1 line) or 430 (2 lines), width=80, height=4
  · Subtitle: left=64, top=370 (1 line) or 450 (2 lines), width=1152, height=100, font_size_pt 14~18, vertical_alignment "top"
  · Presenter info (mandatory): Always placed at bottom-left. A single textbox with 3 lines — name, job title, organization — each on a separate paragraph line.
    - Position: left=64, top=560, width=400, height=96
    - Font: font_size_pt 18, vertical_alignment "bottom"
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
          {"runs": [{"text": "Audience: Engineers | Internal Tech Sharing", "font_size_pt": 14, "color": "#CBD5E1", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
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

<special_layout_contract>
The title slide intentionally uses a fixed layout contract:

- Main title: left=64, top=260, width=1152; height=80 for one line or 160 for two.
- Main title type: 40~44pt.
- Presenter info: a three-paragraph textbox at left=64, top=560, width=400,
  height=96, using 18pt text.
</special_layout_contract>

<title_quality_guidance>
- Keep ordinary content within the canvas and reserve the bottom-right logo area.
- Size each textbox for likely wrapping and avoid accidental same-level overlap.
- Keep the key content from content_summary while preserving readable spacing.
- Use the deck accent color for the divider and the secondary text color for presenter info.
- Specify vertical alignment explicitly when it helps communicate intent.
</title_quality_guidance>
