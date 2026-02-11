BEDROCK_MODEL_ID = "us.anthropic.claude-opus-4-20250514-v1:0"
BEDROCK_REGION = "us-east-1"
BEDROCK_TEMPERATURE = 0.7

DEFAULT_NUM_SLIDES = 5
MIN_NUM_SLIDES = 3
MAX_NUM_SLIDES = 20

SCRIPT_SYSTEM_PROMPT = (
    "당신은 전문 프레젠테이션 스크립트 작성자입니다. "
    "주어진 슬라이드 아웃라인을 기반으로 각 슬라이드에 대한 발표자 노트(speaker_notes)를 작성하세요.\n\n"
    "작성 규칙:\n"
    "- 각 슬라이드의 제목과 본문 요점을 자연스럽게 풀어서 발표 스크립트를 작성하세요.\n"
    "- 청중에게 말하듯 자연스러운 구어체를 사용하세요.\n"
    "- 핵심 내용을 명확하게 전달하되, 지나치게 길지 않게 작성하세요.\n"
    "- 슬라이드 간 자연스러운 전환을 고려하세요.\n"
    "- 반드시 아래 JSON 형식만 출력하세요. 다른 텍스트는 포함하지 마세요.\n\n"
    "출력 형식:\n"
    "```json\n"
    '{"scripts": [{"slide_index": 0, "speaker_notes": "..."}, '
    '{"slide_index": 1, "speaker_notes": "..."}]}\n'
    "```"
)

SCRIPT_USER_PROMPT_TEMPLATE = (
    "다음 슬라이드 아웃라인을 기반으로 각 슬라이드의 발표자 노트를 작성해주세요.\n\n"
    "슬라이드 아웃라인:\n{outline_json}"
)

OUTLINE_SYSTEM_PROMPT = (
    "당신은 프레젠테이션 구조 설계 전문가입니다. "
    "주어진 주제를 기반으로 슬라이드 아웃라인을 JSON 형식으로 생성하세요.\n\n"
    "작성 규칙:\n"
    "- 주제의 핵심 내용을 논리적으로 구성하여 슬라이드를 설계하세요.\n"
    "- 최소 3장(제목/본문/마무리) 이상으로 구성하세요.\n"
    "- 각 슬라이드에 title, bullets, image_idea, layout_type, speaker_notes를 포함하세요.\n"
    "- layout_type은 title, text_image, text_only, chart, closing 중 하나를 선택하세요.\n"
    "- 첫 번째 슬라이드는 layout_type을 'title'로, 마지막 슬라이드는 'closing'으로 지정하세요.\n"
    "- image_idea는 해당 슬라이드의 시각적 요소를 설명하는 짧은 문장으로, 이미지 생성 프롬프트로 사용됩니다.\n"
    "- speaker_notes는 빈 문자열(\"\")로 두세요. 발표자 노트는 이후 별도 단계에서 생성됩니다.\n"
    "- bullets는 핵심 요점을 간결하게 정리한 목록입니다.\n"
    "- 반드시 아래 JSON 형식만 출력하세요. 다른 텍스트는 포함하지 마세요.\n\n"
    "출력 형식:\n"
    "```json\n"
    '{"slides": [{"title": "...", "bullets": ["...", "..."], '
    '"image_idea": "...", "layout_type": "...", "speaker_notes": ""}]}\n'
    "```"
)

OUTLINE_USER_PROMPT_TEMPLATE = (
    "주제: {topic}\n"
    "슬라이드 수: {num_slides}장\n\n"
    "위 주제에 대해 {num_slides}장의 슬라이드 아웃라인 JSON을 생성해주세요."
)

OUTLINE_FREEFORM_SYSTEM_PROMPT = (
    "당신은 프레젠테이션 구조 설계 전문가입니다. "
    "주어진 주제를 기반으로 free-form 레이아웃의 슬라이드 아웃라인을 JSON 형식으로 생성하세요.\n\n"
    "좌표계:\n"
    "- 슬라이드 크기: 13.333 x 7.5 인치 (16:9 widescreen)\n"
    "- 모든 좌표와 크기는 인치 단위입니다.\n"
    "- left: 0 ~ 13.333, top: 0 ~ 7.5\n"
    "- 요소가 슬라이드 밖으로 나가지 않도록 하세요 (left + width <= 13.333, top + height <= 7.5).\n\n"
    "작성 규칙:\n"
    "- 모든 슬라이드의 layout_type은 'freeform'으로 지정하세요.\n"
    "- 각 슬라이드에 title, bullets(빈 배열 가능), image_idea, layout_type, speaker_notes, elements를 포함하세요.\n"
    "- elements 배열에 각 요소의 type, left, top, width, height, content, font_size_pt, bold를 포함하세요.\n"
    "- type은 'textbox', 'image', 'shape' 중 하나를 선택하세요.\n"
    "- 제목 텍스트박스는 font_size_pt를 28 이상, bold를 true로 설정하세요.\n"
    "- 본문 텍스트박스는 font_size_pt를 16~20으로 설정하세요.\n"
    "- 시각적으로 균형 잡힌 레이아웃을 구성하세요.\n"
    "- speaker_notes는 빈 문자열(\"\")로 두세요. 발표자 노트는 이후 별도 단계에서 생성됩니다.\n"
    "- 반드시 아래 JSON 형식만 출력하세요. 다른 텍스트는 포함하지 마세요.\n\n"
    "출력 형식:\n"
    "```json\n"
    '{"slides": [{"title": "...", "bullets": [], "image_idea": "...", '
    '"layout_type": "freeform", "speaker_notes": "", '
    '"elements": [{"type": "textbox", "left": 0.5, "top": 0.5, "width": 12, "height": 1.5, '
    '"content": "...", "font_size_pt": 28, "bold": true}]}]}\n'
    "```"
)

OUTLINE_FREEFORM_USER_PROMPT_TEMPLATE = (
    "다음 주제를 기반으로 free-form 레이아웃의 슬라이드 아웃라인 JSON을 생성해주세요.\n"
    "모든 슬라이드를 layout_type 'freeform'으로 구성하고, elements 배열에 요소별 좌표를 포함하세요.\n\n"
    "주제: {topic}\n"
    "슬라이드 수: {num_slides}장"
)

TITAN_IMAGE_MODEL_ID = "amazon.titan-image-generator-v2:0"
TITAN_IMAGE_REGION = "us-east-1"
TITAN_IMAGE_WIDTH = 1280
TITAN_IMAGE_HEIGHT = 768
TITAN_IMAGE_CFG_SCALE = 8.0

SKIP_IMAGE_LAYOUT_TYPES = {"text_only"}

PPTX_TEMPLATE_PATH = "2026 Confidential AWS Powerpoint Template Light & Dark Themes.pptx"
PPTX_FONT_NAME = "맑은 고딕"
PPTX_BODY_FONT_SIZE_PT = 16
PPTX_TITLE_FONT_SIZE_PT = 28

SLIDES_WIDTH_PX = 960
SLIDES_HEIGHT_PX = 540

SLIDES_SYSTEM_PROMPT = (
    "당신은 프레젠테이션 HTML/CSS 디자인 전문가입니다. "
    "주어진 슬라이드 아웃라인을 기반으로 시각적으로 완성도 높은 HTML/CSS 슬라이드를 생성하세요.\n\n"
    "규격:\n"
    "- 슬라이드 크기: 960px × 540px (16:9)\n"
    "- 각 슬라이드는 <div class=\"slide\" data-speaker-notes=\"발표자 노트\"> 구조를 사용하세요.\n"
    "- 슬라이드 div에 width: 960px, height: 540px, position: relative, overflow: hidden을 적용하세요.\n"
    "- 내부 요소는 position: absolute 기반으로 자유롭게 배치하세요.\n"
    "- 모든 스타일은 인라인 CSS로 작성하세요.\n\n"
    "이미지 처리:\n"
    "- 이미지가 있는 슬라이드에는 {IMAGE_N} placeholder를 사용하세요 (N은 0부터 시작하는 슬라이드 인덱스).\n"
    "- 예: <img src=\"{IMAGE_0}\" style=\"...\" />\n"
    "- 이미지가 없는 슬라이드에는 이미지 태그를 사용하지 마세요.\n\n"
    "layout_type별 디자인 가이드:\n"
    "- title: 중앙 정렬된 큰 제목과 부제목. 깔끔하고 임팩트 있는 레이아웃.\n"
    "- text_image: 좌측에 텍스트(제목+불릿), 우측에 이미지. 6:4 또는 5:5 비율.\n"
    "- text_only: 전체 영역에 텍스트 콘텐츠. 가독성 높은 레이아웃.\n"
    "- chart: 데이터 시각화 중심. 이미지나 텍스트 기반 차트 표현.\n"
    "- closing: 마무리/감사 슬라이드. 간결하고 인상적인 레이아웃.\n"
    "- freeform: 자유 배치. elements 정보를 참고하여 좌표 기반 배치.\n\n"
    "디자인 원칙:\n"
    "- 한글 폰트: font-family에 'Pretendard', 'Noto Sans KR', sans-serif를 지정하세요.\n"
    "- 배경색, 텍스트 색상 등을 활용하여 전문적인 프레젠테이션을 만드세요.\n"
    "- 슬라이드 간 일관된 디자인 테마를 유지하세요.\n"
    "- 제목은 28px 이상, 본문은 16~20px로 설정하세요.\n\n"
    "출력 규칙:\n"
    "- 완전한 HTML 문서를 출력하세요 (<!DOCTYPE html> 포함).\n"
    "- 마크다운 코드블록(```)으로 감싸지 마세요. HTML 코드만 출력하세요.\n"
    "- <head>에 공통 스타일을 정의하고, <body>에 슬라이드 div들을 나열하세요."
)

SLIDES_USER_PROMPT_TEMPLATE = (
    "다음 아웃라인을 기반으로 HTML/CSS 슬라이드를 생성해주세요.\n\n"
    "슬라이드 아웃라인:\n{outline_json}\n\n"
    "이미지 정보:\n{image_data}"
)
