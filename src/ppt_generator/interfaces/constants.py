from pathlib import Path

PPT_GENERATOR_HOME = Path.home() / ".ppt-generator"

BEDROCK_MODEL_ID = "us.anthropic.claude-opus-4-6-v1"
BEDROCK_OUTLINE_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
BEDROCK_REGION = "us-east-1"
BEDROCK_TEMPERATURE = 0.7
BEDROCK_MAX_TOKENS = 32_000
BEDROCK_OUTLINE_MAX_TOKENS = 16_000
BEDROCK_SCRIPT_MAX_TOKENS = 16_000

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
    "- speaker_notes는 빈 문자열(\"\")로 두세요. 발표자 노트는 이후 별도 단계에서 생성됩니다.\n\n"
    "이미지 생성 가이드 (중요):\n"
    "- 이미지 생성 모델은 텍스트 렌더링이 불가능합니다. 텍스트가 주된 슬라이드에는 image_idea를 빈 문자열(\"\")로 두세요.\n"
    "- 다음 경우에 image_idea를 빈 문자열로 두세요:\n"
    "  - 제목/오프닝 슬라이드 (title)\n"
    "  - 텍스트 전용 슬라이드 (text_only)\n"
    "  - 마무리/감사 슬라이드 (closing)\n"
    "  - 불릿 포인트가 3개 이상인 텍스트 중심 슬라이드\n"
    "  - 표, 목록, 코드 등 텍스트 정보가 핵심인 슬라이드\n"
    "- image_idea를 작성하는 경우:\n"
    "  - 개념도, 다이어그램, 사진 등 시각 자료가 내용 이해에 도움이 되는 슬라이드\n"
    "  - 텍스트와 이미지를 나란히 배치하는 슬라이드 (text_image)\n"
    "  - image_idea는 영어로 작성하고, 텍스트가 포함된 이미지를 요청하지 마세요.\n\n"
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

GEMINI_IMAGE_MODEL_ID = "gemini-2.5-flash-image"
GEMINI_IMAGE_ASPECT_RATIO = "16:9"

SKIP_IMAGE_LAYOUT_TYPES = {"text_only", "title", "closing"}

PPTX_TEMPLATE_PATH = "2026 Confidential AWS Powerpoint Template Light & Dark Themes.pptx"
PPTX_FONT_NAME = "맑은 고딕"
PPTX_BODY_FONT_SIZE_PT = 16
PPTX_TITLE_FONT_SIZE_PT = 28

SLIDES_WIDTH_PX = 1280
SLIDES_HEIGHT_PX = 720

# HTML→PPTX 좌표 변환 (1280x720px → 13.333x7.5인치)
EXPORT_PX_TO_INCHES_X = 13.333 / 1280  # ~0.01042
EXPORT_PX_TO_INCHES_Y = 7.5 / 720      # ~0.01042

# --- 레이아웃 영역 좌표 (AWS PPTX 템플릿 placeholder → 1280x720px 변환) ---
# scripts/extract_layout_positions.py로 추출한 결과.
# 각 값은 {"left": px, "top": px, "width": px, "height": px} 형식.
LAYOUT_REGIONS: dict[str, dict[str, dict[str, int]]] = {
    "title": {
        "title": {"left": 50, "top": 359, "width": 678, "height": 97},
        "subtitle": {"left": 64, "top": 458, "width": 678, "height": 56},
    },
    "text_image": {
        "title": {"left": 57, "top": 96, "width": 560, "height": 103},
        "body": {"left": 64, "top": 228, "width": 560, "height": 424},
        "image": {"left": 702, "top": 36, "width": 542, "height": 616},
    },
    "text_only": {
        "title": {"left": 57, "top": 96, "width": 1152, "height": 56},
        "body": {"left": 64, "top": 180, "width": 1152, "height": 472},
    },
    "chart": {
        "title": {"left": 57, "top": 96, "width": 1152, "height": 56},
        "body": {"left": 64, "top": 180, "width": 1152, "height": 472},
    },
    "closing": {
        "title": {"left": 64, "top": 240, "width": 1152, "height": 106},
        "body": {"left": 64, "top": 370, "width": 1152, "height": 214},
    },
    "freeform": {
        "title": {"left": 57, "top": 96, "width": 1152, "height": 56},
        "body": {"left": 64, "top": 180, "width": 1152, "height": 472},
    },
}

SLIDES_TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "slides.html"

SLIDES_SYSTEM_PROMPT = (
    "당신은 프레젠테이션 HTML/CSS 디자인 전문가입니다. "
    "주어진 슬라이드 아웃라인을 기반으로 슬라이드 <section> 요소들을 생성하세요.\n\n"
    "규격:\n"
    "- 각 슬라이드는 <section id=\"slide-{N}\" data-speaker-notes=\"발표자 노트\"> 구조를 사용하세요 (N은 0부터 시작하는 슬라이드 인덱스).\n"
    "- 슬라이드 내부 요소 배치에는 TailwindCSS 유틸리티 클래스(flex, grid, items-center, justify-center 등)를 사용하세요.\n"
    "- 인라인 style 대신 TailwindCSS 유틸리티 클래스(text-center, bg-blue-500, p-8, rounded-lg 등)를 사용하세요.\n"
    "- 커스텀 CSS 클래스를 절대 만들지 마세요. 모든 스타일은 TailwindCSS 유틸리티 클래스만 사용하세요.\n"
    "- 그라데이션, 그림자 등 Tailwind로 표현 가능한 것은 반드시 Tailwind 클래스를 사용하세요.\n"
    "- Tailwind로 불가능한 스타일만 인라인 style 속성을 허용합니다.\n"
    "- <style> 태그를 출력하지 마세요.\n\n"
    "슬라이드 레이아웃 (매우 중요):\n"
    "- 각 <section>은 position:relative, 크기 1280x720px 고정, overflow:hidden인 컨테이너입니다.\n"
    "- 각 section의 직계 자식으로 반드시 하나의 래퍼 div를 만들고, 이 div에 absolute inset-0을 지정하세요.\n"
    "- 래퍼 div에 flex/grid와 배경색 등을 적용하여 슬라이드 전체를 커버하세요.\n"
    "- 래퍼 div에 px-16 py-10 패딩을 적용하여 슬라이드 가장자리에 충분한 여백을 확보하세요.\n"
    "- 예시 구조 (제목+콘텐츠):\n"
    "  <section id=\"slide-0\" data-speaker-notes=\"...\">\n"
    "    <div class=\"absolute inset-0 flex flex-col bg-slate-900 px-16 py-10\">\n"
    "      <h2 class=\"text-white text-3xl font-bold mb-2\">제목</h2>\n"
    "      <div class=\"w-16 h-1 bg-blue-500 rounded-full mb-6\"></div>\n"
    "      <div class=\"flex-1 flex items-start gap-8\">\n"
    "        <!-- 좌우 분할 콘텐츠 -->\n"
    "      </div>\n"
    "    </div>\n"
    "  </section>\n\n"
    "overflow 방지 규칙 (반드시 준수):\n"
    "- 모든 콘텐츠는 1280x720px 영역 안에 완전히 들어와야 합니다.\n"
    "- 장식용 배경 요소(원, 도형 등)를 사용하지 마세요. 배경 장식이 필요하면 래퍼 div의 bg-gradient 등 Tailwind 배경 클래스만 사용하세요.\n"
    "- transform: translate()로 요소를 이동하지 마세요.\n"
    "- 좌우 분할 시 각 영역에 w-1/2와 overflow-hidden을 적용하세요.\n"
    "- flex-1과 min-h-0을 함께 사용하여 flex 자식이 부모를 넘지 않게 하세요.\n"
    "- 콘텐츠가 많으면 텍스트 크기를 줄이거나 항목 수를 줄이세요. 스크롤은 허용하지 않습니다.\n\n"
    "이미지 처리:\n"
    "- 이미지가 있는 슬라이드에는 {IMAGE_N} placeholder를 사용하세요 (N은 0부터 시작하는 슬라이드 인덱스).\n"
    "- 예: <img src=\"{IMAGE_0}\" class=\"w-full h-auto rounded-lg object-cover\" />\n"
    "- 이미지가 없는 슬라이드에는 이미지 태그를 절대 사용하지 마세요.\n"
    "- title, text_only, closing 슬라이드는 이미지가 생성되지 않으므로 이미지 태그를 넣지 마세요. "
    "텍스트와 TailwindCSS만으로 디자인하세요.\n\n"
    "layout_type별 레이아웃 영역 (AWS 템플릿 기준 px 좌표, 1280x720 슬라이드):\n"
    "- title: 제목 left=50 top=359 w=678 h=97, 부제목 left=64 top=458 w=678 h=56. "
    "래퍼에 items-center justify-center로 수직·수평 중앙 정렬. 큰 제목 + 구분선 + 부제목. 하단에 발표자 정보. 이미지 없이 텍스트만.\n"
    "- text_image: 제목 left=57 top=96 w=560 h=103, 본문 left=64 top=228 w=560 h=424, 이미지 left=702 top=36 w=542 h=616. "
    "상단에 제목, 아래에 좌우 분할. 좌측(약 44%) 텍스트, 우측(약 42%) 이미지. 이미지 영역은 슬라이드 상단부터 시작.\n"
    "- text_only: 제목 left=57 top=96 w=1152 h=56, 본문 left=64 top=180 w=1152 h=472. "
    "상단에 제목 + 구분선, 아래에 전체폭 본문 영역에 불릿/텍스트 배치. 이미지 없이 텍스트만.\n"
    "- chart: 제목 left=57 top=96 w=1152 h=56, 본문 left=64 top=180 w=1152 h=472. "
    "상단에 제목 + 구분선, 아래에 데이터 시각화.\n"
    "- closing: 제목 left=64 top=240 w=1152 h=106, 본문 left=64 top=370 w=1152 h=214. "
    "items-center justify-center로 중앙 정렬. 간결한 마무리. 이미지 없이 텍스트만.\n"
    "- freeform: 제목 left=57 top=96 w=1152 h=56, 본문 left=64 top=180 w=1152 h=472. "
    "상단에 제목 + 구분선, 아래에 flex-1 영역에서 elements 정보를 참고하여 콘텐츠 배치. "
    "elements의 좌표는 참고용이며, HTML에서는 flex/grid로 자연스럽게 배치하세요.\n\n"
    "영역 좌표 적용 방법:\n"
    "- 래퍼 div의 패딩으로 좌우 여백(약 px-14~px-16)과 상단 여백(약 pt-[96px])을 맞추세요.\n"
    "- 제목은 top 좌표 위치에서 시작하도록 배치하세요.\n"
    "- 본문은 제목 아래 top 좌표에서 시작하여 height만큼의 영역 안에 들어오도록 하세요.\n"
    "- text_image의 좌우 분할 비율: 좌측 텍스트 약 44%, 우측 이미지 약 42%, gap 포함.\n"
    "- 본문 영역 하단(top+height)을 넘지 않도록 콘텐츠 양을 조절하세요.\n"
    "- 이 좌표는 가이드라인이며, flex/grid 레이아웃으로 자연스럽게 구현하세요.\n\n"
    "디자인 원칙:\n"
    "- 폰트는 템플릿에서 전역 설정되므로 별도 지정하지 마세요.\n"
    "- 배경색은 반드시 Tailwind 유틸리티 클래스(bg-slate-900, bg-gray-800 등)로 래퍼 div에 직접 지정하세요.\n"
    "- 슬라이드 간 일관된 디자인 테마를 유지하세요.\n"
    "- 제목은 text-3xl 이상, 본문은 text-base~text-lg로 설정하세요.\n\n"
    "출력 규칙:\n"
    "- <section> 요소들만 출력하세요. 완전한 HTML 문서를 출력하지 마세요.\n"
    "- JavaScript 코드를 포함하지 마세요.\n"
    "- 마크다운 코드블록(```)으로 감싸지 마세요. HTML 코드만 출력하세요."
)

SLIDES_USER_PROMPT_TEMPLATE = (
    "다음 아웃라인을 기반으로 HTML/CSS 슬라이드를 생성해주세요.\n\n"
    "슬라이드 아웃라인:\n{outline_json}\n\n"
    "이미지 정보:\n{image_data}"
)

# --- F4: 슬라이드 분할 처리 ---
SLIDES_MAX_PER_BATCH = 1

SLIDES_BATCH_USER_PROMPT_TEMPLATE = (
    "다음 아웃라인의 슬라이드를 생성해주세요. "
    "이전 배치에서 사용된 디자인 테마를 반드시 동일하게 유지하세요.\n\n"
    "이전 배치의 디자인 요약:\n{design_summary}\n\n"
    "슬라이드 아웃라인:\n{outline_json}\n\n"
    "이미지 정보:\n{image_data}\n\n"
    "출력 규칙:\n"
    "- 완전한 HTML 문서를 출력하지 말고, <section ...> 요소들만 출력하세요.\n"
    "- <html>, <head>, <body> 태그 없이 <section> 요소들만 출력하세요.\n"
    "- 이전 배치와 동일한 Tailwind 클래스와 색상 팔레트를 사용하세요."
)

SLIDES_DESIGN_SUMMARY_PROMPT = (
    "다음 HTML 슬라이드 코드에서 사용된 디자인 테마를 요약해주세요.\n"
    "사용된 Tailwind 클래스 기준으로 배경색(bg-*), 텍스트 색상(text-*), 제목 스타일, 본문 스타일, 전체적인 색상 팔레트를 포함하세요.\n"
    "간결하게 3~5줄로 요약하세요. HTML 코드는 출력하지 마세요.\n\n"
    "HTML:\n{html}"
)

# --- F5: 슬라이드 수정 ---
SLIDES_MODIFY_SYSTEM_PROMPT = (
    "당신은 프레젠테이션 HTML/CSS 수정 전문가입니다. "
    "사용자의 수정 요청에 따라 기존 슬라이드를 정확하게 수정하세요.\n\n"
    "지원하는 수정 유형:\n"
    "- 텍스트 변경: 제목, 본문 내용, 불릿 포인트의 수정/추가/삭제\n"
    "- 레이아웃 조정: 요소 위치, 크기, 간격 변경 (Tailwind 클래스 사용)\n"
    "- 스타일 변경: 색상, 배경색, 테두리 등 Tailwind 유틸리티 클래스 변경\n"
    "- 이미지 교체: 기존 이미지 제거, 위치/크기 변경 (src 속성의 file:// 경로 자체는 유지)\n"
    "- 슬라이드 추가: 새로운 <section> 요소 추가\n"
    "- 슬라이드 삭제: 특정 <section> 요소 제거\n"
    "- 슬라이드 순서 변경: <section> 요소의 순서 재배치\n"
    "- 발표자 노트 수정: data-speaker-notes 속성 값 변경\n\n"
    "수정 규칙:\n"
    "- 수정 요청에 해당하는 부분만 변경하고, 나머지는 그대로 유지하세요.\n"
    "- 이미지의 file:// 경로(src 속성 값)는 변경하지 마세요. 위치나 크기만 변경 가능합니다.\n"
    "- 스타일 변경 시 인라인 style 대신 TailwindCSS 유틸리티 클래스를 사용하세요.\n"
    "- 커스텀 CSS 클래스를 절대 만들지 마세요. 모든 스타일은 TailwindCSS 유틸리티 클래스만 사용하세요.\n"
    "- Tailwind로 불가능한 스타일만 인라인 style 속성을 허용합니다.\n"
    "- 기존 슬라이드의 레이아웃 영역(제목/본문/이미지 위치 비율)을 유지하세요. "
    "레이아웃 변경이 명시적으로 요청되지 않는 한 제목과 본문의 위치를 바꾸지 마세요.\n\n"
    "출력 규칙:\n"
    "- 완전한 HTML 문서를 출력하세요 (<!DOCTYPE html> 포함).\n"
    "- JavaScript 코드를 포함하지 마세요.\n"
    "- 마크다운 코드블록(```)으로 감싸지 마세요. HTML 코드만 출력하세요."
)

SLIDES_MODIFY_USER_PROMPT_TEMPLATE = (
    "다음 HTML 슬라이드를 수정 요청에 따라 수정해주세요.\n\n"
    "현재 HTML 슬라이드:\n{current_html}\n\n"
    "수정 요청:\n{modification_request}"
)

SLIDES_MODIFY_SINGLE_USER_PROMPT_TEMPLATE = (
    "다음은 슬라이드 {slide_index}번의 HTML 코드입니다. "
    "이 슬라이드만 수정 요청에 따라 수정해주세요.\n\n"
    "현재 슬라이드 HTML:\n{current_slide_html}\n\n"
    "수정 요청:\n{modification_request}\n\n"
    "출력 규칙:\n"
    "- <section ...> 요소 하나만 출력하세요.\n"
    "- 완전한 HTML 문서를 출력하지 마세요.\n"
    "- 마크다운 코드블록(```)으로 감싸지 마세요.\n"
    "- 커스텀 CSS 클래스를 만들지 말고 TailwindCSS 유틸리티 클래스만 사용하세요."
)
