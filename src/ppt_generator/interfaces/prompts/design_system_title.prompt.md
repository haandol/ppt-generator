<slide_type_title>
제목 슬라이드 (slide_type: "title") 디자인 규칙:

- 프레젠테이션의 첫 번째 슬라이드. 주제명, 부제목, 발표자 정보를 포함
- background_color를 null로 설정하세요 (배경 이미지가 자동 삽입됨)
- 우측 하단 영역(left_px > 1080, top_px > 600)에 요소를 배치하지 마세요 (로고 자동 삽입 영역)
- 메인 텍스트를 캔버스 수직 중앙에 배치합니다. 전체 텍스트 그룹의 수직 중심이 캔버스 중앙(y=360) 부근에 오도록 합니다.
- 레이아웃 (반드시 아래 좌표를 그대로 사용):
  · 대제목: left=64, top=260, width=1152, height=80, font_size_pt 32~40, bold, vertical_alignment "middle"
  · 구분선: shape(rectangle), left=64, top=350, width=80, height=4, fill_color 강조색(#FF9900), vertical_alignment "top"
  · 부제목: left=64, top=370, width=1152, height=100, font_size_pt 14~18, vertical_alignment "top"
</slide_type_title>

<examples>
  <layout_example id="title-1" hint="title — 프레젠테이션 제목 슬라이드 (대제목 + 구분선 + 부제목)">
  {
    "background_color": null,
    "speaker_notes": "발표 소개...",
    "textboxes": [
      {
        "left_px": 64, "top_px": 260, "width_px": 1152, "height_px": 80,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "프레젠테이션 대제목", "font_size_pt": 36, "color": "#FFFFFF", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      },
      {
        "left_px": 64, "top_px": 370, "width_px": 1152, "height_px": 100,
        "vertical_alignment": "top",
        "paragraphs": [
          {"runs": [{"text": "부제목 또는 발표 설명", "font_size_pt": 16, "color": "#D5DBDB", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"},
          {"runs": [{"text": "대상: 엔지니어  |  사내 기술 공유", "font_size_pt": 14, "color": "#D5DBDB", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      }
    ],
    "shapes": [
      {
        "left_px": 64, "top_px": 350, "width_px": 80, "height_px": 4,
        "shape_type": "rectangle", "fill_color": "#FF9900",
        "vertical_alignment": "top"
      }
    ]
  }
  </layout_example>
</examples>

<typography_rules>
- 슬라이드 대제목: font_size_pt 32~40, bold
- 부제목/라벨: font_size_pt 14~18
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
8. 제목 위치: 대제목은 반드시 left=64, top=260, width=1152, height=80으로 배치하세요.
</constraints>
