<slide_type_title>
Title slide (slide_type: "title") design rules:

- Title slides may omit `grid_layout`, `cell_assignment`, and `design_doc`.
- The first slide is mandatory and must contain exactly one non-empty textbox with
  `component_id: "title.main"`.
- A subtitle may use `component_id: "title.subtitle"`.
- Presenter information may use `component_id: "title.presenter"` only when the outline
  actually provides presenter information. Never create placeholder identity.
- `background_color` may be null for the project background image or a deliberate color
  allowed by DESIGN.md.
- Reserve the bottom-right area (left_px > 1080, top_px > 600) for the auto-inserted logo.
- Choose coordinates, typography, alignment, divider treatment, and composition from
  DESIGN.md. Keep every element inside the canvas.
</slide_type_title>

<examples>
  <layout_example id="title-1" hint="title — Presentation title slide with semantic roles">
  {
    "background_color": null,
    "speaker_notes": "",
    "textboxes": [
      {
        "component_id": "title.main",
        "left_px": 96, "top_px": 220, "width_px": 1000, "height_px": 140,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "Presentation Main Title", "font_size_pt": 40, "color": "#FFFFFF", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      },
      {
        "component_id": "title.subtitle",
        "left_px": 96, "top_px": 390, "width_px": 860, "height_px": 90,
        "vertical_alignment": "top",
        "paragraphs": [
          {"runs": [{"text": "Subtitle or presentation description", "font_size_pt": 16, "color": "#CBD5E1", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"},
          {"runs": [{"text": "Audience: Engineers | Internal Tech Sharing", "font_size_pt": 14, "color": "#CBD5E1", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      }
    ],
    "shapes": [
      {"left_px": 96, "top_px": 370, "width_px": 180, "height_px": 4,
       "shape_type": "rectangle", "fill_color": "#3B82F6"}
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
- Exactly one `title.main` textbox is required.
- `title.subtitle` and `title.presenter` are optional and unique.
- Array order and pixel coordinates do not define semantic roles.
</special_layout_contract>

<title_quality_guidance>
- Keep ordinary content within the canvas and reserve the bottom-right logo area.
- Size each textbox for likely wrapping and avoid accidental same-level overlap.
- Keep the key content from content_summary while preserving readable spacing.
- Use the deck accent color for the divider and the secondary text color for presenter info.
- Specify vertical alignment explicitly when it helps communicate intent.
</title_quality_guidance>
