import html
import json
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

OUTLINE_SYSTEM_PROMPT = (
    "당신은 프레젠테이션 구조 설계 전문가입니다. "
    "주어진 주제를 기반으로 슬라이드 아웃라인을 JSON 형식으로 생성하세요.\n\n"
    "각 슬라이드에는 다음 4개 필드를 포함합니다:\n"
    "- title: 슬라이드 제목\n"
    "- content_summary: 슬라이드에 담길 핵심 내용 요약 (불릿 포인트, 설명, 키워드 등을 자연어로 작성)\n"
    "- layout_index: PPTX 템플릿 레이아웃 인덱스 (아래 목록 참고)\n"
    "- component_hint: 슬라이드에 사용할 시각적 컴포넌트 유형 (아래 목록 참고)\n\n"
    "사용 가능한 layout_index:\n"
    "- 0: 제목 슬라이드 (타이틀 + 부제목, 첫 번째 슬라이드에 사용)\n"
    "- 22: 텍스트 전용 (제목 + 본문 불릿, 가장 범용적)\n"
    "- 21: 차트/데이터 (제목 + 데이터 시각화 영역)\n"
    "- 87: 마무리 슬라이드 (감사/Q&A, 마지막 슬라이드에 사용)\n"
    "- 88: 자유 배치 (Blank, 특수한 레이아웃이 필요한 경우)\n\n"
    "사용 가능한 component_hint:\n"
    "- bullets: 기본 불릿 포인트 (기본값)\n"
    "- two_column: 2칼럼 레이아웃\n"
    "- vs_comparison: VS 비교 패널 (A vs B)\n"
    "- step_cards: 단계별 카드\n"
    "- code_block: 코드 블록 포함\n"
    "- arch_diagram: 아키텍처 다이어그램 (흐름도)\n"
    "- pipeline: 파이프라인 흐름\n"
    "- quote: 인용문 강조\n"
    "- summary_grid: 요약 그리드 (2x2)\n"
    "- agenda: 목차/안건 리스트\n"
    "- info_cards: 정보 카드 그리드\n"
    "- feature_list: 기능/특징 리스트\n"
    "- cta: Call-to-Action 강조\n\n"
    "작성 규칙:\n"
    "- content_summary는 해당 슬라이드에서 다룰 핵심 내용을 구체적으로 작성하세요.\n"
    "- 디자인이나 레이아웃 세부사항은 포함하지 마세요. 구조만 결정합니다.\n"
    "- 같은 component_hint를 연속으로 사용하지 마세요. 다양한 시각적 구조를 활용하세요.\n"
    "- 반드시 아래 JSON 형식만 출력하세요. 다른 텍스트는 포함하지 마세요.\n\n"
    "출력 형식:\n"
    "```json\n"
    '{"slides": [{"title": "...", "content_summary": "...", "layout_index": 0, "component_hint": "bullets"}]}\n'
    "```"
)

OUTLINE_USER_PROMPT_TEMPLATE = (
    "다음 주제를 기반으로 슬라이드 아웃라인 JSON을 생성해주세요.\n\n"
    "주제: {topic}\n"
    "슬라이드 수: {num_slides}장"
)

PPTX_SLIDE_WIDTH_EMU = 12_192_000   # 13.333" × 914400
PPTX_SLIDE_HEIGHT_EMU = 6_858_000   # 7.5" × 914400
PPTX_FONT_NAME = "맑은 고딕"
PPTX_BODY_FONT_SIZE_PT = 16
PPTX_TITLE_FONT_SIZE_PT = 28

REM_TO_PX = 16  # 1rem = 16px

# PPTX 폰트 크기 스케일링
PPTX_FONT_MIN_SIZE_PT = 16        # PPTX 최소 폰트 크기
PPTX_FONT_SCALE_FACTOR = 1.5      # HTML px → PPTX pt 스케일 팩터

# PPTX 불릿 포맷팅
PPTX_BULLET_CHAR_L0 = "\u2022"
PPTX_BULLET_MARGIN_EMU_L0 = 228600    # ~0.25in
PPTX_BULLET_INDENT_EMU_L0 = -171450
PPTX_BULLET_MARGIN_EMU_L1 = 457200    # ~0.5in
PPTX_BULLET_INDENT_EMU_L1 = -171450

SLIDES_WIDTH_PX = 1280
SLIDES_HEIGHT_PX = 720

# HTML→PPTX 좌표 변환 (1280x720px → 13.333x7.5인치)
EXPORT_PX_TO_INCHES_X = 13.333 / 1280  # ~0.01042
EXPORT_PX_TO_INCHES_Y = 7.5 / 720      # ~0.01042

# --- 레이아웃 영역 좌표 (template/layout.json에서 로드) ---
# scripts/extract_layout_json.py로 template.pptx에서 추출.
# 각 값은 {"left": px, "top": px, "width": px, "height": px} 형식 (1280x720px 기준).
def _load_layout_regions() -> dict[int, dict[str, dict[str, int]]]:
    """layout.json에서 레이아웃별 region 좌표를 로드."""
    layout_json = Path(__file__).resolve().parent.parent.parent.parent / "template" / "layout.json"
    if not layout_json.exists():
        # layout.json이 없으면 최소 폴백
        return {
            22: {
                "title": {"left": 57, "top": 96, "width": 1152, "height": 56},
                "body": {"left": 64, "top": 180, "width": 1152, "height": 231},
            },
        }
    with open(layout_json, encoding="utf-8") as f:
        data = json.load(f)
    regions: dict[int, dict[str, dict[str, int]]] = {}
    for layout in data.get("layouts", []):
        idx = layout["layout_index"]
        r = layout.get("regions", {})
        if r:
            regions[idx] = r
    return regions


LAYOUT_REGIONS: dict[int, dict[str, dict[str, int]]] = _load_layout_regions()

DEFAULT_LAYOUT_INDEX = 22  # text_only

SLIDES_TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "slides.html"


def build_layout_skeleton(
    layout_index: int,
    slide_index: int,
    speaker_notes: str = "",
) -> str:
    """LAYOUT_REGIONS 좌표를 기반으로 <section> 골격 HTML을 생성한다.

    각 region div에 data-region 속성과 position:absolute 스타일을 부여하여
    LLM이 내부 컨텐츠만 채우도록 구조를 강제한다.
    """
    regions = LAYOUT_REGIONS.get(layout_index, LAYOUT_REGIONS[DEFAULT_LAYOUT_INDEX])
    parts: list[str] = []
    escaped_notes = html.escape(speaker_notes, quote=True) if speaker_notes else ""
    notes_attr = f' data-speaker-notes="{escaped_notes}"' if speaker_notes else ' data-speaker-notes=""'
    parts.append(f'<section id="slide-{slide_index}" data-layout-index="{layout_index}"{notes_attr}>')
    parts.append('  <div data-wrapper="true" style="position:absolute; top:0; left:0; right:0; bottom:0;">')

    for region_name, coords in regions.items():
        style = (
            f"position:absolute; left:{coords['left']}px; top:{coords['top']}px; "
            f"width:{coords['width']}px; height:{coords['height']}px; overflow:hidden;"
        )
        parts.append(f'    <div data-region="{region_name}" style="{style}">')
        parts.append(f"      <!-- CONTENT:{region_name} -->")
        parts.append("    </div>")

    parts.append("  </div>")
    parts.append("</section>")
    return "\n".join(parts)


SLIDES_SYSTEM_PROMPT = (
    "당신은 프레젠테이션 HTML/CSS 디자인 전문가입니다. "
    "주어진 슬라이드 아웃라인을 기반으로 슬라이드 <section> 요소들을 생성하세요.\n\n"
    "규격:\n"
    "- 각 슬라이드는 <section id=\"slide-{N}\" data-speaker-notes=\"발표자 노트\"> 구조를 사용하세요 (N은 0부터 시작하는 슬라이드 인덱스).\n"
    "- 템플릿에 사전 정의된 CSS 클래스를 적극 활용하세요. 인라인 style로 색상 등을 오버라이드할 수 있습니다.\n"
    "- <style> 태그를 출력하지 마세요. 커스텀 CSS 클래스를 절대 만들지 마세요.\n"
    "- 그라데이션, 그림자 등도 인라인 style로 표현하세요.\n\n"
    "슬라이드 레이아웃 (매우 중요):\n"
    "- 각 <section>은 position:relative, 크기 1280x720px 고정, overflow:hidden인 컨테이너입니다.\n"
    "- 각 section의 직계 자식으로 반드시 하나의 래퍼 div를 만들고, 이 div에 position:absolute; top:0; left:0; right:0; bottom:0을 지정하세요.\n"
    "- 래퍼 div에 display:flex와 background-color 등을 적용하여 슬라이드 전체를 커버하세요.\n"
    "- 래퍼 div에 padding:40px 64px을 적용하여 슬라이드 가장자리에 충분한 여백을 확보하세요.\n"
    "- 예시 구조 (제목+콘텐츠):\n"
    "  <section id=\"slide-0\" data-speaker-notes=\"...\">\n"
    "    <div style=\"position:absolute; top:0; left:0; right:0; bottom:0; display:flex; flex-direction:column; background-color:#0f172a; padding:40px 64px;\">\n"
    "      <h2 style=\"color:#fff; font-size:2.25rem; font-weight:bold; margin-bottom:8px;\">제목</h2>\n"
    "      <div style=\"width:64px; height:4px; background-color:#3b82f6; border-radius:9999px; margin-bottom:24px;\"></div>\n"
    "      <div style=\"flex:1; display:flex; align-items:flex-start; gap:32px;\">\n"
    "        <!-- 좌우 분할 콘텐츠 -->\n"
    "      </div>\n"
    "    </div>\n"
    "  </section>\n\n"
    "overflow 방지 규칙 (반드시 준수):\n"
    "- 모든 콘텐츠는 1280x720px 영역 안에 완전히 들어와야 합니다.\n"
    "- 장식용 배경 요소(원, 도형 등)를 사용하지 마세요. 배경 장식이 필요하면 래퍼 div의 background에 linear-gradient 등을 사용하세요.\n"
    "- transform: translate()로 요소를 이동하지 마세요.\n"
    "- 좌우 분할 시 각 영역에 width:50%와 overflow:hidden을 적용하세요.\n"
    "- flex:1과 min-height:0을 함께 사용하여 flex 자식이 부모를 넘지 않게 하세요.\n"
    "- 콘텐츠가 많으면 텍스트 크기를 줄이거나 항목 수를 줄이세요. 스크롤은 허용하지 않습니다.\n\n"
    "layout_index별 레이아웃 영역 (AWS 템플릿 기준 px 좌표, 1280x720 슬라이드):\n"
    "- 0 (title): 제목 left=50 top=359 w=678 h=97, 부제목 left=64 top=458 w=678 h=56. "
    "래퍼에 align-items:center; justify-content:center로 수직·수평 중앙 정렬. 큰 제목 + 구분선 + 부제목. 하단에 발표자 정보. 이미지 없이 텍스트만.\n"
    "- 22 (text_only): 제목 left=57 top=96 w=1152 h=56, 본문 left=64 top=180 w=1152 h=472. "
    "상단에 제목 + 구분선, 아래에 전체폭 본문 영역에 불릿/텍스트 배치. 이미지 없이 텍스트만.\n"
    "- 21 (chart): 제목 left=57 top=96 w=1152 h=56, 본문 left=64 top=180 w=1152 h=472. "
    "상단에 제목 + 구분선, 아래에 데이터 시각화.\n"
    "- 87 (closing): 제목 left=64 top=240 w=1152 h=106, 본문 left=64 top=370 w=1152 h=214. "
    "align-items:center; justify-content:center로 중앙 정렬. 간결한 마무리. 이미지 없이 텍스트만.\n"
    "- 88 (freeform): 제목 left=57 top=96 w=1152 h=56, 본문 left=64 top=180 w=1152 h=472. "
    "상단에 제목 + 구분선, 아래에 flex:1 영역에서 콘텐츠를 자유롭게 배치. "
    "display:flex/display:grid로 자연스럽게 배치하세요.\n\n"
    "영역 좌표 적용 방법:\n"
    "- 래퍼 div의 padding으로 좌우 여백(약 56~64px)과 상단 여백(약 96px)을 맞추세요.\n"
    "- 제목은 top 좌표 위치에서 시작하도록 배치하세요.\n"
    "- 본문은 제목 아래 top 좌표에서 시작하여 height만큼의 영역 안에 들어오도록 하세요.\n"
    "- 본문 영역 하단(top+height)을 넘지 않도록 콘텐츠 양을 조절하세요.\n"
    "- 이 좌표는 가이드라인이며, display:flex/display:grid 레이아웃으로 자연스럽게 구현하세요.\n\n"
    "디자인 원칙:\n"
    "- 폰트는 템플릿에서 전역 설정되므로 별도 지정하지 마세요.\n"
    "- 배경색은 반드시 인라인 style의 background-color로 래퍼 div에 직접 지정하세요.\n"
    "- 슬라이드 간 일관된 디자인 테마를 유지하세요.\n"
    "- 제목은 font-size:2.25rem(36px) 이상, 본문은 font-size:1.25rem~1.5rem(20~24px), "
    "보조 텍스트·라벨은 font-size:1rem(16px) 이상으로 설정하세요. "
    "12~14px처럼 작은 글꼴은 프레젠테이션에서 보이지 않으므로 절대 사용하지 마세요.\n\n"
    "출력 규칙:\n"
    "- <section> 요소들만 출력하세요. 완전한 HTML 문서를 출력하지 마세요.\n"
    "- JavaScript 코드를 포함하지 마세요.\n"
    "- 마크다운 코드블록(```)으로 감싸지 마세요. HTML 코드만 출력하세요."
)

SLIDES_REGION_SYSTEM_PROMPT = (
    "당신은 프레젠테이션 HTML/CSS 디자인 전문가입니다. "
    "제공된 레이아웃 골격(skeleton)의 각 영역 안에 콘텐츠를 채워 슬라이드를 완성하세요.\n\n"
    "규격:\n"
    "- 골격 HTML의 <!-- CONTENT:xxx --> 마커를 실제 HTML 콘텐츠로 교체하세요.\n"
    "- data-region div의 style 속성(position, left, top, width, height)은 절대 변경하지 마세요.\n"
    "- data-wrapper div에 인라인 style로 background-color를 지정하세요 (예: style=\"background-color:#0d1b2a;\").\n"
    "- 영역 내부에서 템플릿에 사전 정의된 CSS 클래스를 적극 활용하세요.\n"
    "- 커스텀 CSS 클래스를 절대 만들지 마세요. <style> 태그를 출력하지 마세요.\n"
    "- 인라인 style로 색상 등을 오버라이드할 수 있습니다 (인라인이 클래스보다 우선).\n\n"
    "사용 가능한 CSS 컴포넌트 클래스:\n"
    "- Layout: .two-col (2칼럼 grid), .two-col-wide (1.2fr 0.8fr), .three-col (3칼럼)\n"
    "- Typography: .tag (모노스페이스 라벨), .subtitle (부제목), .divider-bar (구분선)\n"
    "- Cards: .info-card (정보 카드), .step-card (단계 카드, 좌측 보더), .summary-card (요약 카드, 중앙 정렬)\n"
    "- Lists: .agenda-list (목차 리스트), .feature-list (기능 리스트 컨테이너), .feature-item (기능 항목)\n"
    "- Comparison: .vs-container (VS 3칼럼 grid), .vs-panel (비교 패널), .vs-badge (VS 뱃지)\n"
    "- Code: .code-block (코드 래퍼), .code-header (파일명/언어), .code-body (코드 본문)\n"
    "- Diagrams: .arch-flow (흐름도 flex), .arch-stage (단계 박스), .arch-arrow (화살표)\n"
    "           .pipeline-flow (파이프라인 flex), .pipeline-stage (파이프라인 단계)\n"
    "- Quote: .quote-box (인용문, 좌측 보더)\n"
    "- Grids: .summary-grid (2x2 grid), .info-grid-3 (3칼럼 grid)\n"
    "- CTA: .cta-box (Call-to-Action 박스)\n\n"
    "component_hint별 HTML 구조 예시:\n"
    "- bullets: <ul><li style=\"...\">항목</li></ul>\n"
    "- two_column: <div class=\"two-col\"><div class=\"info-card\">좌</div><div class=\"info-card\">우</div></div>\n"
    "- vs_comparison: <div class=\"vs-container\"><div class=\"vs-panel\">A</div><div class=\"vs-badge\">VS</div><div class=\"vs-panel\">B</div></div>\n"
    "- step_cards: <div class=\"three-col\"><div class=\"step-card\">1단계</div><div class=\"step-card\">2단계</div><div class=\"step-card\">3단계</div></div>\n"
    "- code_block: <div class=\"code-block\"><div class=\"code-header\">main.py</div><div class=\"code-body\">print('hello')</div></div>\n"
    "- arch_diagram: <div class=\"arch-flow\"><div class=\"arch-stage\">입력</div><div class=\"arch-arrow\">→</div><div class=\"arch-stage\">처리</div><div class=\"arch-arrow\">→</div><div class=\"arch-stage\">출력</div></div>\n"
    "- pipeline: <div class=\"pipeline-flow\"><div class=\"pipeline-stage\">1단계</div><div class=\"pipeline-stage\">2단계</div></div>\n"
    "- quote: <div class=\"quote-box\">인용문 텍스트</div>\n"
    "- summary_grid: <div class=\"summary-grid\"><div class=\"summary-card\">항목1</div><div class=\"summary-card\">항목2</div></div>\n"
    "- agenda: <ul class=\"agenda-list\"><li>안건 1</li><li>안건 2</li></ul>\n"
    "- info_cards: <div class=\"three-col\"><div class=\"info-card\">카드1</div><div class=\"info-card\">카드2</div><div class=\"info-card\">카드3</div></div>\n"
    "- feature_list: <div class=\"feature-list\"><div class=\"feature-item\">기능1</div><div class=\"feature-item\">기능2</div></div>\n"
    "- cta: <div class=\"cta-box\"><h3>행동 유도 메시지</h3></div>\n\n"
    "영역별 콘텐츠 가이드:\n"
    "- title 영역: 제목 텍스트. font-size:2.25rem(36px) 이상, font-weight:bold. .divider-bar 등 장식 요소 포함 가능.\n"
    "- subtitle 영역: 부제목/설명 텍스트. font-size:1.25rem(20px) 이상.\n"
    "- body 영역: component_hint에 맞는 CSS 컴포넌트를 사용하세요. font-size:1.25rem~1.5rem(20~24px). "
    "보조 텍스트·라벨도 최소 1rem(16px). 12~14px처럼 작은 글꼴은 절대 사용하지 마세요.\n"
    "\n"
    "overflow 방지 규칙:\n"
    "- 각 영역의 width/height 안에 콘텐츠가 완전히 들어와야 합니다.\n"
    "- 콘텐츠가 많으면 텍스트 크기를 줄이거나 항목 수를 줄이세요. 스크롤은 허용하지 않습니다.\n"
    "- 장식용 배경 요소(원, 도형 등)를 영역 내부에 사용하지 마세요.\n\n"
    "디자인 원칙:\n"
    "- 폰트는 템플릿에서 전역 설정되므로 별도 지정하지 마세요.\n"
    "- 슬라이드 간 일관된 디자인 테마를 유지하세요.\n"
    "- 텍스트 색상은 배경색에 맞는 대비를 유지하세요.\n\n"
    "출력 규칙:\n"
    "- 완성된 <section> 요소 하나만 출력하세요.\n"
    "- JavaScript 코드를 포함하지 마세요.\n"
    "- 마크다운 코드블록(```)으로 감싸지 마세요. HTML 코드만 출력하세요."
)

SLIDES_REGION_USER_PROMPT_TEMPLATE = (
    "다음 아웃라인을 기반으로 레이아웃 골격의 각 영역에 콘텐츠를 채워주세요.\n"
    "아웃라인에 speaker_notes가 포함되어 있다면 발표 스크립트의 맥락을 참고하여 "
    "콘텐츠를 더 풍부하고 구체적으로 작성하세요. "
    "speaker_notes 자체를 슬라이드에 표시하지는 마세요.\n\n"
    "슬라이드 아웃라인:\n{outline_json}\n\n"
    "레이아웃 골격:\n{skeleton_html}"
)

SLIDES_REGION_BATCH_USER_PROMPT_TEMPLATE = (
    "다음 아웃라인의 슬라이드 골격에 콘텐츠를 채워주세요. "
    "이전 배치에서 사용된 디자인 테마를 반드시 동일하게 유지하세요.\n"
    "아웃라인에 speaker_notes가 포함되어 있다면 발표 스크립트의 맥락을 참고하여 "
    "콘텐츠를 더 풍부하고 구체적으로 작성하세요. "
    "speaker_notes 자체를 슬라이드에 표시하지는 마세요.\n\n"
    "이전 배치의 디자인 요약:\n{design_summary}\n\n"
    "슬라이드 아웃라인:\n{outline_json}\n\n"
    "레이아웃 골격:\n{skeleton_html}\n\n"
    "출력 규칙:\n"
    "- 완성된 <section> 요소 하나만 출력하세요.\n"
    "- data-region div의 style 속성은 절대 변경하지 마세요.\n"
    "- 이전 배치와 동일한 배경색과 텍스트 색상을 사용하세요."
)

SLIDES_USER_PROMPT_TEMPLATE = (
    "다음 아웃라인을 기반으로 HTML/CSS 슬라이드를 생성해주세요.\n\n"
    "슬라이드 아웃라인:\n{outline_json}"
)

# --- F4: 슬라이드 분할 처리 ---
SLIDES_MAX_PER_BATCH = 1

SLIDES_BATCH_USER_PROMPT_TEMPLATE = (
    "다음 아웃라인의 슬라이드를 생성해주세요. "
    "이전 배치에서 사용된 디자인 테마를 반드시 동일하게 유지하세요.\n\n"
    "이전 배치의 디자인 요약:\n{design_summary}\n\n"
    "슬라이드 아웃라인:\n{outline_json}\n\n"
    "출력 규칙:\n"
    "- 완전한 HTML 문서를 출력하지 말고, <section ...> 요소들만 출력하세요.\n"
    "- <html>, <head>, <body> 태그 없이 <section> 요소들만 출력하세요.\n"
    "- 이전 배치와 동일한 인라인 style 색상 팔레트를 사용하세요."
)

SLIDES_DESIGN_SUMMARY_PROMPT = (
    "다음 HTML 슬라이드 코드에서 사용된 디자인 테마를 요약해주세요.\n"
    "인라인 style 기준으로 background-color, color, 제목 스타일, 본문 스타일, 전체적인 색상 팔레트를 포함하세요.\n"
    "간결하게 3~5줄로 요약하세요. HTML 코드는 출력하지 마세요.\n\n"
    "HTML:\n{html}"
)

# --- F5: 슬라이드 수정 ---
SLIDES_MODIFY_SYSTEM_PROMPT = (
    "당신은 프레젠테이션 HTML/CSS 수정 전문가입니다. "
    "사용자의 수정 요청에 따라 기존 슬라이드를 정확하게 수정하세요.\n\n"
    "지원하는 수정 유형:\n"
    "- 텍스트 변경: 제목, 본문 내용, 불릿 포인트의 수정/추가/삭제\n"
    "- 레이아웃 조정: 요소 위치, 크기, 간격 변경 (인라인 style 사용)\n"
    "- 스타일 변경: 색상, 배경색, 테두리 등 인라인 style 변경\n"
    "- 슬라이드 추가: 새로운 <section> 요소 추가\n"
    "- 슬라이드 삭제: 특정 <section> 요소 제거\n"
    "- 슬라이드 순서 변경: <section> 요소의 순서 재배치\n"
    "- 발표자 노트 수정: data-speaker-notes 속성 값 변경\n\n"
    "수정 규칙:\n"
    "- 수정 요청에 해당하는 부분만 변경하고, 나머지는 그대로 유지하세요.\n"
    "- 템플릿에 사전 정의된 CSS 클래스를 활용할 수 있습니다. 커스텀 CSS 클래스를 절대 만들지 마세요.\n"
    "- <style> 태그를 출력하지 마세요.\n"
    "- data-region 속성이 있는 div의 style 속성(position, left, top, width, height)은 절대 변경하지 마세요.\n"
    "- data-region div 내부의 콘텐츠만 수정 가능합니다.\n"
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
    "- 템플릿에 사전 정의된 CSS 클래스를 활용할 수 있습니다. 커스텀 CSS 클래스를 절대 만들지 마세요.\n"
    "- data-region 속성이 있는 div의 style 속성(position, left, top, width, height)은 절대 변경하지 마세요.\n"
    "- data-region div 내부의 콘텐츠만 수정 가능합니다."
)

# --- F5-LLM: HTML→PPTX LLM 변환 ---
PPTX_CONVERT_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
PPTX_CONVERT_MAX_TOKENS = 8_000

PPTX_CONVERT_SYSTEM_PROMPT = (
    "당신은 HTML 슬라이드를 PPTX 요소 JSON으로 변환하는 전문가입니다.\n"
    "주어진 <section> HTML을 분석하여, python-pptx로 재현할 수 있는 텍스트박스와 도형의 "
    "위치/크기/서식 정보를 JSON으로 출력하세요.\n\n"
    "슬라이드 좌표계: 1280x720 px\n\n"
    "출력 JSON 스키마:\n"
    "```json\n"
    "{\n"
    '  "background_color": "#RRGGBB 또는 null",\n'
    '  "textboxes": [\n'
    "    {\n"
    '      "left_px": number, "top_px": number, "width_px": number, "height_px": number,\n'
    '      "paragraphs": [\n'
    "        {\n"
    '          "runs": [\n'
    '            {"text": "...", "font_size_pt": number|null, "color": "#RRGGBB"|null, "bold": bool, "italic": bool}\n'
    "          ],\n"
    '          "bullet_level": -1|0|1\n'
    "        }\n"
    "      ]\n"
    "    }\n"
    "  ],\n"
    '  "shapes": [\n'
    "    {\n"
    '      "left_px": number, "top_px": number, "width_px": number, "height_px": number,\n'
    '      "shape_type": "rectangle"|"rounded_rectangle"|"line",\n'
    '      "fill_color": "#RRGGBB"|null,\n'
    '      "border_color": "#RRGGBB"|null,\n'
    '      "border_width_pt": number|null,\n'
    '      "corner_radius_px": number|null,\n'
    '      "text": "..."|null,\n'
    '      "text_color": "#RRGGBB"|null,\n'
    '      "text_size_pt": number|null,\n'
    '      "text_bold": bool\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "```\n\n"
    "변환 규칙:\n"
    "- 모든 텍스트를 빠짐없이 textbox로 변환하세요. 텍스트가 누락되면 안 됩니다.\n"
    "- 배경색은 래퍼 div의 background-color에서 추출하세요.\n"
    "- 장식용 div(구분선, 컬러 바 등)는 shapes로 변환하세요.\n"
    "- CSS rem 단위는 1rem=16px로 변환하세요.\n"
    "- flex/grid 레이아웃의 자식 요소는 각각 적절한 절대 좌표를 계산하여 배치하세요. "
    "컬럼이 N개이면 각 컬럼의 너비 = (부모 width - gap*(N-1)) / N 으로 균등 분배하세요.\n"
    "- 텍스트 색상(color)은 가장 가까운 조상의 인라인 style에서 상속하세요. "
    "배경이 어두우면 텍스트는 밝은 색이어야 합니다.\n"
    "- data-region div가 있으면 그 좌표(left, top, width, height)를 반드시 텍스트박스 좌표로 사용하세요. "
    "data-region의 좌표를 임의로 변경하거나 무시하지 마세요.\n"
    "- font_size_pt는 이 값이 python-pptx Pt()에 직접 전달됩니다. "
    "제목은 28~32pt, 본문은 16~20pt, 보조 텍스트는 12~14pt를 권장합니다.\n"
    "- 텍스트박스가 서로 겹치지 않도록 주의하세요.\n"
    "- 반드시 JSON만 출력하세요. 마크다운 코드블록으로 감싸지 마세요."
)

PPTX_CONVERT_USER_PROMPT_TEMPLATE = (
    "다음 HTML <section>을 PPTX 요소 JSON으로 변환해주세요.\n\n"
    "슬라이드 HTML:\n{section_html}"
)
