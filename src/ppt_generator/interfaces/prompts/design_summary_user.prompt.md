<task>
다음 프레젠테이션 아웃라인 전체를 분석하여, 모든 슬라이드에 일관되게 적용할 디자인 테마 요약(design_summary)을 JSON으로 생성해주세요.
</task>

<context>
전체 슬라이드 수: {total_slides}장
색상 테마: {color_theme}
</context>

<output_format>
다음 JSON 형식으로만 출력하세요 (다른 텍스트 없이):
{{
  "background_color": "#RRGGBB",
  "text_colors": ["#RRGGBB", ...],
  "title_font_pt": number,
  "body_font_pt": number,
  "card_fills": ["#RRGGBB", ...],
  "card_borders": ["#RRGGBB", ...]
}}

각 필드 설명:
- background_color: 슬라이드 배경색 (design_principles의 색상 팔레트 기반)
- text_colors: 제목, 본문, 보조 텍스트에 사용할 색상 배열
- title_font_pt: 슬라이드 제목 폰트 크기 (28~36 범위)
- body_font_pt: 본문 텍스트 폰트 크기 (16~22 범위)
- card_fills: 카드/shape 배경색 배열
- card_borders: 카드/shape 테두리색 배열 (없으면 빈 배열)
</output_format>

<input>
{outline_json}
</input>