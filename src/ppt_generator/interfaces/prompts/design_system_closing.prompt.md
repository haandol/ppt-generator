<slide_type_closing>
Thank You 슬라이드 (slide_type: "closing") 디자인 규칙:

- 프레젠테이션의 마지막 슬라이드. 감사 인사, 연락처, Q&A 안내
- background_color를 null로 설정하세요 (배경 이미지가 자동 삽입됨)
- 우측 하단 영역(left_px > 1080, top_px > 600)에 요소를 배치하지 마세요 (로고 자동 삽입 영역)
- 메인 텍스트를 캔버스 수직 중앙에 배치합니다. 감사 인사 텍스트와 부가 정보의 수직 중심이 캔버스 중앙(y=360) 부근에 오도록 합니다.
- 레이아웃 (반드시 아래 좌표를 그대로 사용):
  · 감사 인사: left=64, top=240, width=1152, height=80, font_size_pt 40~44, bold, vertical_alignment "middle", alignment "center"
  · 부제목/Q&A: left=64, top=340, width=1152, height=60, font_size_pt 16~20, vertical_alignment "middle", alignment "center"
  · 연락처/요약 (선택): left=64, top=420, width=1000, height=120, font_size_pt 14~16, vertical_alignment "top", alignment "center"
</slide_type_closing>

<examples>
  <layout_example id="closing-1" hint="closing — Thank You 슬라이드 (감사 인사 화면 중앙, 부제목·연락처 아래)">
  {
    "background_color": null,
    "speaker_notes": "질문과 피드백을 환영합니다.",
    "textboxes": [
      {
        "left_px": 64, "top_px": 240, "width_px": 1152, "height_px": 80,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "감사합니다", "font_size_pt": 40, "color": "#FFFFFF", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "center"}
        ]
      },
      {
        "left_px": 64, "top_px": 340, "width_px": 1152, "height_px": 60,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "Questions & Feedback", "font_size_pt": 20, "color": "#FFC000", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "center"}
        ]
      },
      {
        "left_px": 64, "top_px": 420, "width_px": 1000, "height_px": 120,
        "vertical_alignment": "top",
        "paragraphs": [
          {"runs": [{"text": "참고 자료  ", "font_size_pt": 14, "color": "#FF9900", "bold": true, "italic": false}, {"text": "공식 문서  |  가이드 링크", "font_size_pt": 14, "color": "#D5DBDB", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "center"}
        ]
      }
    ],
    "shapes": []
  }
  </layout_example>
</examples>

<typography_rules>
- 감사 인사: font_size_pt 40~44, bold
- 부제목/라벨: font_size_pt 16~20
- 보조 텍스트: font_size_pt 12~16
</typography_rules>

<constraints>
하드 제약 조건 (위반 시 렌더링 실패):

1. 폰트 크기 범위: 모든 font_size_pt는 10~44pt 범위 내로 지정하세요.
2. 좌표 경계 준수: 0 이상 left_px, 0 이상 top_px, left_px + width_px 이하 1280, top_px + height_px 이하 720으로 지정하세요.
3. 높이 충분성 확보: height_px는 실제 줄바꿈 포함 줄수 x font_size_pt x 2.0 이상으로 지정하세요.
4. 콘텐츠 완전성: content_summary의 모든 핵심 내용을 textbox 또는 shape에 포함하세요.
5. 요소 겹침 금지: 동일 레벨 요소 간 bounding box가 겹치지 않아야 합니다.
6. 여백 확보: 모든 콘텐츠 요소는 left_px >= 64, top_px >= 64, left_px + width_px <= 1216, top_px + height_px <= 656을 만족해야 합니다.
7. vertical_alignment 필수: 모든 textbox와 shape에 vertical_alignment을 반드시 지정하세요 (null 금지).
8. 감사 인사 위치: 감사 인사는 반드시 left=64, top=240, width=1152, height=80으로 배치하세요.
9. 감사 인사 폰트 크기: 감사 인사 텍스트의 font_size_pt는 반드시 40~44 범위로 설정하세요. 40pt 미만은 금지합니다.
</constraints>
