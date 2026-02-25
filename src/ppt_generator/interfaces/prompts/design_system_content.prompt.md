<layout_grid>
사고 보조용 48열 × 20행 그리드 — 좌표 산출 시 아래 테이블을 참조하세요.
출력은 반드시 px 값으로 하되, 열/행 번호로 먼저 "논리 위치"를 결정한 뒤 변환하면 오류가 줄어듭니다.

■ 수평 48열 그리드 (콘텐츠 영역 1152px = 48 × 24px, 셀 24×24px 정사각형)
  공식: left_px = 64 + (col - 1) × 24

  | col |  1  |  2  |  3  |  4  |  5  |  6  |  7  |  8  |  9  | 10  | 11  | 12  | 13  | 14  | 15  | 16  |
  |-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
  | px  |  64 |  88 | 112 | 136 | 160 | 184 | 208 | 232 | 256 | 280 | 304 | 328 | 352 | 376 | 400 | 424 |

  | col | 17  | 18  | 19  | 20  | 21  | 22  | 23  | 24  | 25  | 26  | 27  | 28  | 29  | 30  | 31  | 32  |
  |-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
  | px  | 448 | 472 | 496 | 520 | 544 | 568 | 592 | 616 | 640 | 664 | 688 | 712 | 736 | 760 | 784 | 808 |

  | col | 33  | 34  | 35  | 36  | 37  | 38  | 39  | 40  | 41  | 42  | 43  | 44  | 45  | 46  | 47  | 48  |
  |-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
  | px  | 832 | 856 | 880 | 904 | 928 | 952 | 976 |1000 |1024 |1048 |1072 |1096 |1120 |1144 |1168 |1192 |

  주요 span → width 변환: span 48 = 1152px, span 24 = 576px, span 16 = 384px, span 12 = 288px

■ 수직 20행 그리드 (본문 영역 148~623, 500px = 20 × 25px)
  공식: top_px = 148 + (row - 1) × 25

  | row |  1  |  2  |  3  |  4  |  5  |  6  |  7  |  8  |  9  | 10  |
  |-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
  | px  | 148 | 173 | 198 | 223 | 248 | 273 | 298 | 323 | 348 | 373 |

  | row | 11  | 12  | 13  | 14  | 15  | 16  | 17  | 18  | 19  | 20  |
  |-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
  | px  | 398 | 423 | 448 | 473 | 498 | 523 | 548 | 573 | 598 | 623 |
</layout_grid>

<diagram_grid>
다이어그램(arch_diagram, pipeline, process_flow 등) 전용 미리 계산된 좌표 테이블.
블록을 균등 배치할 때 아래 테이블의 값을 그대로 사용하면 계산 오류를 방지할 수 있습니다.

■ 수평 N열 균등 배치 (콘텐츠 영역 1152px, gap = 32px)
  공식: width = (1152 - (N-1) × 32) / N  (소수점 이하 버림)
        left[i] = 64 + i × (width + 32)   (i = 0, 1, …, N-1)
  **같은 행의 모든 요소는 동일한 top_px와 height_px를 사용하세요.**

  | N | width | left 위치들                    |
  |---|-------|-------------------------------|
  | 2 |  560  | 64, 656                       |
  | 3 |  362  | 64, 458, 852                  |
  | 4 |  264  | 64, 360, 656, 952             |
  | 5 |  206  | 64, 302, 540, 778, 1016       |

■ 수직 M행 균등 배치 (본문 영역 508px, gap = 28px)
  공식: height = (508 - (M-1) × 28) / M  (소수점 이하 버림)
        top[j] = 148 + j × (height + 28)  (j = 0, 1, …, M-1)

  | M | height | top 위치들                    |
  |---|--------|------------------------------|
  | 1 |  508   | 148                          |
  | 2 |  240   | 148, 416                     |
  | 3 |  150   | 148, 326, 504                |
  | 4 |  106   | 148, 282, 416, 550           |

■ 화살표(line shape) 좌표 계산
  블록 간 연결선은 shape_type: "line"으로 표현합니다.
  line shape는 시작점(left_px, top_px)에서 끝점(left_px+width_px, top_px+height_px)까지의 직선 커넥터로 렌더링됩니다.

  - 수평 화살표 (좌→우, 같은 행):
      left_px  = 블록A의 left + 블록A의 width          (A의 오른쪽 끝)
      top_px   = 블록A의 top + 블록A의 height / 2       (A의 수직 중앙)
      width_px = 블록B의 left - (블록A의 left + 블록A의 width)  (= gap)
      height_px = 0
  - 수직 화살표 (위→아래, 같은 열):
      left_px  = 블록A의 left + 블록A의 width / 2       (A의 수평 중앙)
      top_px   = 블록A의 top + 블록A의 height            (A의 아래쪽 끝)
      width_px = 0
      height_px = 블록B의 top - (블록A의 top + 블록A의 height)  (= gap)

■ 화살표 속성
  - end_arrow: true → 끝점(오른쪽/아래쪽)에 삼각형 화살표 머리를 표시합니다.
  - start_arrow: true → 시작점(왼쪽/위쪽)에 삼각형 화살표 머리를 표시합니다.
  - dash_style: "solid" (기본, 실선), "dash" (대시선), "dot" (점선)
  - **다이어그램의 모든 연결선에는 반드시 end_arrow: true를 지정하여 흐름 방향을 명시하세요.**
  - 양방향 화살표가 필요하면 start_arrow: true와 end_arrow: true를 동시에 지정합니다.
  - 화살표 없는 단순 연결선이 필요한 경우만 end_arrow/start_arrow를 모두 생략(false)하세요.

■ 화살표 최소 gap 규칙 (필수)
  화살표 머리가 14px이므로, 블록 사이에 화살표를 배치할 때 **최소 28px 이상의 gap**을 확보해야 합니다.
  - 수평 화살표: width_px >= 28 (블록A의 right와 블록B의 left 사이 거리 >= 28)
  - 수직 화살표: height_px >= 28 (블록A의 bottom과 블록B의 top 사이 거리 >= 28)
  - gap이 28px 미만이면 화살표 머리가 블록에 겹치거나 잘려서 시각적으로 깨집니다.
  - 블록 간 공간이 부족하면 블록 크기를 줄여서 화살표 gap을 확보하세요.

■ 3×2 다이어그램 예시 (3열 × 2행, gap_h=32, gap_v=28)
  블록 크기: width=362, height=240
  1행: top=148  → (64,148), (458,148), (852,148)
  2행: top=416  → (64,416), (458,416), (852,416)
  수평 화살표 (1행, A→B): left=426, top=268, width=32, height=0, end_arrow=true
  수평 화살표 (1행, B→C): left=820, top=268, width=32, height=0, end_arrow=true
  수직 화살표 (1열, R1→R2): left=245, top=388, width=0, height=28, end_arrow=true
</diagram_grid>

<shapes_text_usage>
shapes에 텍스트를 넣는 방법은 2가지:
1. 간단한 텍스트: text, text_color, text_size_pt, text_bold 필드 사용 (한 줄 텍스트, 자동 중앙 정렬)
2. 구조화된 텍스트: paragraphs 배열 사용 (여러 줄, 불릿, 서식 혼합 시). paragraphs의 runs에서 font_family: "monospace"로 코드 폰트 지정 가능
둘 다 사용하면 paragraphs가 우선됨. 카드형 shape에는 paragraphs를 적극 활용하세요.
</shapes_text_usage>

<vertical_alignment_guide>
textboxes와 shapes 모두 vertical_alignment을 반드시 명시적으로 지정하세요. null 금지.
- "top": 상단 정렬, "middle": 수직 중앙, "bottom": 하단 정렬
- 용도별 권장값:
  - 제목/부제목 텍스트박스: "middle"
  - 본문/불릿 텍스트박스: 콘텐츠가 박스 높이의 65% 미만이면 "middle" 권장, 65% 이상이면 "top"
  - 카드/배너/버튼 shape (text 또는 paragraphs 포함): "middle"
  - 바닥글/하단 라벨: "bottom"
  - 장식용 shape (텍스트 없음): "top"
</vertical_alignment_guide>

<padding_guide>
shapes의 padding_*_px 필드로 텍스트와 shape 경계 사이 여백을 제어합니다.
이유: 적절한 패딩이 없으면 텍스트가 shape 경계에 붙어 가독성이 떨어집니다.

- 미지정 시 기본값: 좌우 약 5px, 상하 약 2.5px
- 카드형 shape 권장: padding_left_px: 16~20, padding_right_px: 16~20, padding_top_px: 12~16, padding_bottom_px: 12~16
- 넓은 배너/헤더 shape: padding_left_px: 16~24 권장
</padding_guide>

<slide_type_agenda>
목차 슬라이드 (slide_type: "content", component_hint: "agenda") 디자인 규칙:

- 프레젠테이션의 두 번째 슬라이드. 전체 발표의 주요 섹션/흐름을 안내
- 목차 항목은 개별 슬라이드를 모두 나열하지 않고, 관련 슬라이드들을 묶어 큰 주제 단위(섹션)로 추상화하여 3~6개 항목으로 간결하게 작성
- 레이아웃: 반드시 1열 레이아웃만 사용
  · 제목: left=64, top=72, width=1152, height=48
  · 본문: 제목 아래 단일 텍스트박스에 번호+항목을 세로로 나열 (left=64, top=148, width=1152, height=콘텐츠에 맞게 조절)
- 각 항목은 번호 + 섹션 제목 형태로, 간결하게 작성
- 시각적 구분을 위해 번호에 강조색 적용 권장
</slide_type_agenda>

<slide_type_content>
본문 슬라이드 (slide_type: "content") 디자인 규칙:

- 프레젠테이션의 본론 슬라이드. 주제의 핵심 내용을 다룸
- 캔버스 안전 영역: left 64~1216, top 64~656 (사방 64px 여백)
- 제목→본문 간격: 최소 **28px** 유지 (제목 bottom과 본문 top 사이)
- 인접 요소 간 최소 **16px** 간격 유지 (수직 방향)
- 본문 높이: 540px 고정이 아니라 **콘텐츠 양에 맞게 조절** (필요 높이를 추정하여 height_px 설정)
- component_hint별 레이아웃 가이드:

  bullets: 상단 제목 텍스트박스 + 본문 불릿 텍스트박스 (bullet_level 0/1)
    · 제목: left=64, top=72, width=1152, height=48
    · 본문: left=64, top=148, width=1152, height=콘텐츠에 맞게 조절 (최대 480)

  two_column: 제목 + 좌우 2개 텍스트박스 (각 width 약 552px, gap 48px)
    · 제목: left=64, top=72, width=1152, height=48
    · 좌측: left=64, top=148, width=552, height=콘텐츠에 맞게 조절
    · 우측: left=664, top=148, width=552, height=콘텐츠에 맞게 조절

  vs_comparison: 제목 + 좌우 2개 카드(shape) + 중앙 VS 라벨
    · 좌측: left=64, width=508 / VS: left=596, width=88 / 우측: left=708, width=508

  step_cards: 제목 + 3~4개 가로 배치 카드(shape), 각 카드에 번호+제목+설명
    · 3개 카드: width=352, gap=32px → left: 64, 448, 832
    · 4개 카드: width=260, gap=24px → left: 64, 348, 632, 916

  code_block: 제목 + 코드 영역(shape, 어두운 배경, monospace 폰트)
  arch_diagram: 제목 + 블록(shape)들을 화살표(line shape)로 연결한 다이어그램
  pipeline: 제목 + 좌에서 우 단계 블록(shape) + 화살표
  quote: 큰 인용 부호 + 인용문 텍스트박스 + 출처

  summary_grid: 제목 + 2x2 카드(shape) 그리드
    · 좌상: left=64, top=148, width=552, height=236
    · 우상: left=664, top=148, width=552, height=236
    · 좌하: left=64, top=412, width=552, height=236
    · 우하: left=664, top=412, width=552, height=236

  info_cards: 제목 + 3~4개 정보 카드(shape) 가로 배치
  feature_list: 제목 + 아이콘/불릿 + 기능 설명 텍스트
  process_flow: 제목 + 좌측 설명 텍스트박스 + 우측 플로우 다이어그램(shape+line)
  quote_code: 좌측 인용/설명 텍스트박스 + 우측 코드 shape
  concept_list: 좌측 개념 설명 텍스트 + 우측 다이어그램(shape)

■ 하단 보조 요소 레이아웃 규칙:
  슬라이드 하단에 info badge, 인사이트 배너, 컨텍스트 박스 등 보조 요소를 배치할 때:

  1. **하단에 독립 요소가 1개인 경우** (인사이트 배너 또는 info badge 행):
     - 인사이트 배너: left=64, top=612, width=1152, height=44, 전폭 사용
     - info badge 행 (2~3개): 동일한 top_px=612, height_px=44로 가로 배치 (diagram_grid의 N열 균등 배치 참조)

  2. **하단에 독립 요소가 2개인 경우** (예: 컨텍스트 박스 + 인사이트 배너):
     - 두 요소를 수직으로 겹치지 않게 배치하세요. **절대로 같은 y 영역에 겹쳐 놓지 마세요.**
     - 방법 A (수직 분리): 컨텍스트 박스를 위에, 인사이트 배너를 아래에 배치
       · 컨텍스트 박스: top=540, height=68 (bottom=608)
       · 인사이트 배너: top=624, height=32 (bottom=656)
     - 방법 B (수평 분리): 좌측에 컨텍스트 박스, 우측에 인사이트 배너를 나란히 배치
       · 컨텍스트 박스: left=64, width=500 / 인사이트 배너: left=596, width=620
     - 방법 C (통합): 하나의 shape에 모든 내용을 paragraphs로 통합

  3. **공간이 부족할 때**: 다이어그램 메인 영역의 height를 줄여 하단 보조 영역을 확보하세요. 메인 다이어그램 bottom은 최대 540px까지, 하단 보조 영역은 556px부터 사용하세요.
</slide_type_content>

<examples>
  <layout_example id="bullets-1" hint="bullets — 제목 + 불릿 포인트 리스트 (bullet_level 0/1 계층 구조, 전폭 텍스트박스)">
  {
    "background_color": "#232F3E",
    "speaker_notes": "이 슬라이드에서는...",
    "textboxes": [
      {
        "left_px": 64, "top_px": 72, "width_px": 1152, "height_px": 48,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "슬라이드 제목", "font_size_pt": 32, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      },
      {
        "left_px": 64, "top_px": 148, "width_px": 1152, "height_px": 346,
        "vertical_alignment": "middle",
        "line_spacing_pt": 28,
        "paragraphs": [
          {"runs": [{"text": "첫 번째 항목", "font_size_pt": 24, "color": "#F1F3F3", "bold": false, "italic": false}], "bullet_level": 0, "alignment": "left"},
          {"runs": [{"text": "세부 설명", "font_size_pt": 20, "color": "#D5DBDB", "bold": false, "italic": false}], "bullet_level": 1, "alignment": "left"},
          {"runs": [{"text": "두 번째 항목", "font_size_pt": 24, "color": "#F1F3F3", "bold": false, "italic": false}], "bullet_level": 0, "alignment": "left"}
        ]
      }
    ],
    "shapes": []
  }
  </layout_example>

  <layout_example id="step-cards-1" hint="step_cards — 3개 가로 배치 카드 (번호 + 제목 + 설명, paragraphs 사용, 균등 gap=32px)">
  {
    "background_color": "#232F3E",
    "speaker_notes": "",
    "textboxes": [
      {
        "left_px": 64, "top_px": 72, "width_px": 1152, "height_px": 48,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "진행 단계", "font_size_pt": 32, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      }
    ],
    "shapes": [
      {
        "left_px": 64, "top_px": 148, "width_px": 352, "height_px": 472,
        "shape_type": "rounded_rectangle", "fill_color": "#2E3D50", "corner_radius_px": 12,
        "vertical_alignment": "top",
        "padding_left_px": 16, "padding_right_px": 16, "padding_top_px": 12, "padding_bottom_px": 12,
        "paragraphs": [
          {"runs": [{"text": "01", "font_size_pt": 28, "color": "#FFC000", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"},
          {"runs": [{"text": "첫 번째 단계", "font_size_pt": 20, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"},
          {"runs": [{"text": "단계 설명 텍스트가 여기에 들어갑니다.", "font_size_pt": 16, "color": "#D5DBDB", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      },
      {
        "left_px": 448, "top_px": 148, "width_px": 352, "height_px": 472,
        "shape_type": "rounded_rectangle", "fill_color": "#2E3D50", "corner_radius_px": 12,
        "vertical_alignment": "top",
        "padding_left_px": 16, "padding_right_px": 16, "padding_top_px": 12, "padding_bottom_px": 12,
        "paragraphs": [
          {"runs": [{"text": "02", "font_size_pt": 28, "color": "#FFC000", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"},
          {"runs": [{"text": "두 번째 단계", "font_size_pt": 20, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"},
          {"runs": [{"text": "단계 설명 텍스트가 여기에 들어갑니다.", "font_size_pt": 16, "color": "#D5DBDB", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      },
      {
        "left_px": 832, "top_px": 148, "width_px": 352, "height_px": 472,
        "shape_type": "rounded_rectangle", "fill_color": "#2E3D50", "corner_radius_px": 12,
        "vertical_alignment": "top",
        "padding_left_px": 16, "padding_right_px": 16, "padding_top_px": 12, "padding_bottom_px": 12,
        "paragraphs": [
          {"runs": [{"text": "03", "font_size_pt": 28, "color": "#FFC000", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"},
          {"runs": [{"text": "세 번째 단계", "font_size_pt": 20, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"},
          {"runs": [{"text": "단계 설명 텍스트가 여기에 들어갑니다.", "font_size_pt": 16, "color": "#D5DBDB", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      }
    ]
  }
  </layout_example>

  <layout_example id="pipeline-1" hint="pipeline — 4개 블록을 화살표(end_arrow)로 좌→우 연결하는 수평 파이프라인 다이어그램">
  {
    "background_color": "#232F3E",
    "speaker_notes": "",
    "textboxes": [
      {
        "left_px": 64, "top_px": 72, "width_px": 1152, "height_px": 48,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "처리 파이프라인", "font_size_pt": 32, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      }
    ],
    "shapes": [
      {
        "left_px": 64, "top_px": 300, "width_px": 264, "height_px": 120,
        "shape_type": "rounded_rectangle", "fill_color": "#2E3D50", "corner_radius_px": 12,
        "text": "입력", "text_color": "#FFFFFF", "text_size_pt": 20, "text_bold": true,
        "vertical_alignment": "middle"
      },
      {
        "left_px": 328, "top_px": 360, "width_px": 32, "height_px": 0,
        "shape_type": "line", "border_color": "#FFC000", "border_width_pt": 2,
        "end_arrow": true, "vertical_alignment": "top"
      },
      {
        "left_px": 360, "top_px": 300, "width_px": 264, "height_px": 120,
        "shape_type": "rounded_rectangle", "fill_color": "#FF9900", "corner_radius_px": 12,
        "text": "처리", "text_color": "#1A2332", "text_size_pt": 20, "text_bold": true,
        "vertical_alignment": "middle"
      },
      {
        "left_px": 624, "top_px": 360, "width_px": 32, "height_px": 0,
        "shape_type": "line", "border_color": "#FFC000", "border_width_pt": 2,
        "end_arrow": true, "vertical_alignment": "top"
      },
      {
        "left_px": 656, "top_px": 300, "width_px": 264, "height_px": 120,
        "shape_type": "rounded_rectangle", "fill_color": "#2E3D50", "corner_radius_px": 12,
        "text": "검증", "text_color": "#FFFFFF", "text_size_pt": 20, "text_bold": true,
        "vertical_alignment": "middle"
      },
      {
        "left_px": 920, "top_px": 360, "width_px": 32, "height_px": 0,
        "shape_type": "line", "border_color": "#FFC000", "border_width_pt": 2,
        "end_arrow": true, "vertical_alignment": "top"
      },
      {
        "left_px": 952, "top_px": 300, "width_px": 264, "height_px": 120,
        "shape_type": "rounded_rectangle", "fill_color": "#2E3D50", "corner_radius_px": 12,
        "text": "출력", "text_color": "#FFFFFF", "text_size_pt": 20, "text_bold": true,
        "vertical_alignment": "middle"
      }
    ]
  }
  </layout_example>
</examples>

<typography_rules>
- 슬라이드 제목: font_size_pt 28~36, bold
- 부제목/라벨: font_size_pt 14~18
- 본문/설명: font_size_pt 20~28
- 카드 제목: font_size_pt 18~24, bold
- 카드 본문: font_size_pt 16~20
- 보조 텍스트: font_size_pt 12~16
- 코드: font_family: "monospace", font_size_pt 14~16
- line_spacing_pt 권장값: 본문 텍스트 24~28pt, 불릿 리스트 26~32pt, 카드 내부 20~24pt
</typography_rules>

<text_size_estimation>
텍스트가 박스에서 넘치지 않도록 다음 기준으로 필요 높이를 추정하세요.
이유: 텍스트 넘침은 렌더링 시 잘림으로 이어져 핵심 정보가 누락됩니다.

- 한글 1글자 폭 약 font_size_pt x 1.2px, Latin/숫자 1글자 폭 약 font_size_pt x 0.73px
- 예시: width_px=500, font_size_pt=18, 한글 -> 한 줄에 약 23글자 (500 / (18x1.2) = 23)
- shape의 padding을 반드시 차감하여 실제 텍스트 영역 폭을 계산하세요
- 줄수 = 총 텍스트 폭 / 실제 텍스트 영역 폭 (올림)
</text_size_estimation>

<constraints>
하드 제약 조건 (위반 시 렌더링 실패):

1. 폰트 크기 범위: 모든 font_size_pt는 10~44pt 범위 내로 지정하세요.

2. 좌표 경계 준수: 0 이상 left_px, 0 이상 top_px, left_px + width_px 이하 1280, top_px + height_px 이하 720으로 지정하세요.

3. 높이 충분성 확보: height_px는 실제 줄바꿈 포함 줄수 x font_size_pt x 2.0 이상으로 지정하세요. 텍스트가 박스 너비에서 줄바꿈되는 횟수를 반드시 계산하세요.

4. 콘텐츠 완전성: content_summary의 모든 핵심 내용을 textbox 또는 shape에 포함하세요.
   이유: 아웃라인에서 언급된 내용이 슬라이드에 누락되면 프레젠테이션의 완성도가 떨어집니다.

5. 요소 분리 (동일 레벨 겹침 금지, 컨테이너-자식 중첩 허용):
   - 동일 레벨 요소 간 겹침 금지: 같은 역할의 요소(예: 카드와 카드, 텍스트박스와 텍스트박스)는 bounding box가 겹치지 않아야 합니다. 겹침이 있으면 아래 요소의 top_px를 위 요소의 (top_px + height_px + 16) 이상으로 조정하세요.
   - **서로 다른 역할의 요소도 겹침 금지**: 예를 들어 "컨텍스트 상세 박스"와 "인사이트 요약 배너"처럼 역할이 다른 shape들도 bounding box가 겹쳐서는 안 됩니다. 하단에 2개 이상의 독립 요소를 배치할 때는 반드시 수직으로 쌓거나(위 요소의 bottom + 16 이상에서 아래 요소 시작), 수평으로 나란히 배치하세요(겹치지 않는 x 범위).
   - 컨테이너-자식 중첩 허용: 큰 shape가 배경/컨테이너 역할을 하고 그 안에 작은 shape나 textbox를 배치하는 것은 허용됩니다. 이 경우 자식 요소의 bounding box가 부모 shape의 bounding box 안에 완전히 포함되어야 합니다 (자식의 left >= 부모의 left, 자식의 top >= 부모의 top, 자식의 right <= 부모의 right, 자식의 bottom <= 부모의 bottom).
   - 다이어그램 연결선 허용: line shape(화살표, 커넥터)는 블록 shape와 겹칠 수 있습니다.
   - 컨테이너-자식 패턴 예시: arch_diagram에서 큰 rounded_rectangle(배경 패널) 안에 작은 rounded_rectangle(블록)들을 배치하고 line(화살표)으로 연결.
   이유: 동일 레벨 겹침은 텍스트 가독성을 저하시키지만, 컨테이너-자식 중첩은 다이어그램과 구조적 레이아웃에 필수적입니다.

6. 여백 확보 (수치 기준): 모든 콘텐츠 요소는 left_px >= 64, top_px >= 64, left_px + width_px <= 1216, top_px + height_px <= 656을 만족해야 합니다. 콘텐츠가 슬라이드 가장자리에 딱 붙지 않도록 사방 64px 여백을 유지하세요.

7. vertical_alignment 필수: 모든 textbox와 shape에 vertical_alignment을 반드시 지정하세요 (null 금지).

8. 제목 위치: 제목은 반드시 left=64, top=72, width=1152, height=48로 배치하세요.

9. 같은 행 요소의 좌표 일관성: 가로로 나란히 배치하는 요소(카드, 색상바, 블록, 하단 info badge 등)는
   반드시 **동일한 top_px와 height_px**를 사용하세요.
   - 예: 3개 카드를 가로 배치할 때 → 3개 모두 top_px=521, height_px=69로 통일
   - 예: 카드 상단 색상바 3개 → 3개 모두 top_px=493, height_px=10으로 통일
   - 예: 하단 info badge 3개 → 3개 모두 top_px=626, height_px=30으로 통일
   - 각 요소의 top_px를 개별적으로 계산하지 말고, **먼저 행의 top_px를 하나 결정**한 뒤 같은 행의 모든 요소에 동일하게 적용하세요.
   이유: top_px가 1px라도 다르면 시각적 정렬이 무너져 디자인 품질이 크게 저하됩니다.

10. 하단 보조 요소 겹침 금지: 슬라이드 하단(top_px >= 540)에 2개 이상의 독립 shape/textbox를 배치할 때,
    bounding box가 수직으로 겹쳐서는 안 됩니다. 반드시 수직 분리(위 요소 bottom + 16 <= 아래 요소 top) 또는
    수평 분리(겹치지 않는 x 범위)를 적용하세요. <slide_type_content>의 "하단 보조 요소 레이아웃 규칙"을 참조하세요.
    이유: 하단 영역은 공간이 제한적이어서 요소가 겹치면 내용이 가려져 핵심 정보가 누락됩니다.
</constraints>

<content_vertical_balance>
콘텐츠 양에 따른 수직 배치 전략:

- **본문 높이를 콘텐츠에 맞게 조절하세요.** height_px를 항상 540으로 고정하지 말고, 실제 텍스트 양에 맞는 높이를 계산하여 설정하세요 (최대 508px = 656 - 148). 참고: 우수한 프레젠테이션의 본문 높이는 평균 300px대이며, 540px 고정은 빈 공간이 과도하게 발생합니다.
- 본문 텍스트박스의 실제 콘텐츠가 height_px의 65% 미만이면 vertical_alignment을 "middle"로 설정하세요. 이렇게 하면 콘텐츠가 상단에 쏠리지 않고 시각적으로 균형 잡힌 배치가 됩니다.
- 카드 레이아웃(step_cards, info_cards 등)은 캔버스 수직 중앙 기준으로 배치하세요.
</content_vertical_balance>

<page_design_rules>
- 각 주제에 대한 이해를 도울 수 있는 다이어그램이나 인포그래픽을 항상 추가하세요. shape(rectangle, rounded_rectangle, ellipse, line)을 조합하여 흐름도, 관계도, 구조도 등의 시각적 요소를 적극 구성하세요.
- 그 외에도 페이지에 이미지나 인포그래픽을 넣을 수 있는 부분이 있다면 최대한 반영하세요.
- 각 페이지는 꼭 필요한 텍스트만 포함하여 너무 많은 텍스트는 자제하세요. 핵심 키워드와 짧은 문장 위주로 구성하세요.
- 부연 설명은 슬라이드 본문에 넣지 말고 speaker_notes에 포함하세요.
</page_design_rules>

<content_output_rules>
- shapes의 paragraphs를 적극 활용하여 카드 내부 텍스트를 구조화하세요.
</content_output_rules>
