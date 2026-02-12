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
    "- 22: 범용 콘텐츠 (제목 + 본문, 모든 본론 슬라이드에 사용). 본문 영역이 가장 넓어 불릿, 카드, 다이어그램 등 다양한 component_hint를 수용 가능.\n"
    "- 21: 차트/데이터 (제목 + 데이터 시각화 영역)\n"
    "- 87: 마무리 슬라이드 (간결한 감사/Q&A 한 줄만, 마지막 슬라이드에 사용. 본문 영역이 매우 작으므로 긴 내용 불가)\n\n"
    "중요: layout_index=88은 사용하지 마세요. 본론 슬라이드는 반드시 layout_index=22를 사용하세요.\n\n"
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
    "- cta: Call-to-Action 강조\n"
    "- process_flow: 프로세스 워크스루 (2칼럼: 설명 + 플로우 다이어그램)\n"
    "- quote_code: 인용문 + 코드 블록 조합 (2칼럼: 좌측 인용문/특징, 우측 코드)\n"
    "- concept_list: 개념 설명 리스트 (아이콘 + 제목 + 설명, 2칼럼: 좌측 텍스트 + 우측 다이어그램/이미지)\n\n"
    "슬라이드 구성 권장 패턴:\n"
    "- 1장: 타이틀 슬라이드 (layout_index=0) — 주제, 부제목, 발표자 정보\n"
    "- 2장: 목차/개요 (agenda) — 전체 흐름 안내\n"
    "- 3~N-1장: 본론 — 아래 유형을 주제에 맞게 조합:\n"
    "  · 개념 설명: two_column, info_cards, bullets\n"
    "  · 프로세스/워크플로: process_flow, step_cards, pipeline\n"
    "  · 비교/분석: vs_comparison, summary_grid\n"
    "  · 기술 상세: code_block, arch_diagram, quote_code\n"
    "  · 인사이트/강조: quote, feature_list\n"
    "- N장: 마무리 슬라이드 (layout_index=87) — 요약, CTA, Q&A\n\n"
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

# PPTX 검증 상수 (LLM 출력 보정용)
PPTX_VALIDATE_FONT_MIN_PT = 10
PPTX_VALIDATE_FONT_MAX_PT = 44
PPTX_VALIDATE_LINE_HEIGHT_FACTOR = 1.5  # height_px >= 줄수 × font_pt × factor

# HTML→PPTX 좌표 변환 (1280x720px → 13.333x7.5인치)
EXPORT_PX_TO_INCHES_X = 13.333 / 1280  # ~0.01042
EXPORT_PX_TO_INCHES_Y = 7.5 / 720      # ~0.01042

# --- 레이아웃 영역 좌표 (template/layout.json에서 로드) ---
# scripts/extract_layout_json.py로 template.pptx에서 추출.
# 각 값은 {"left": px, "top": px, "width": px, "height": px} 형식 (1280x720px 기준).


def _load_layout_regions() -> dict[int, dict[str, dict[str, int]]]:
    """layout.json에서 레이아웃별 region 좌표를 로드."""
    layout_json = Path(__file__).resolve(
    ).parent.parent.parent.parent / "template" / "layout.json"
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

SLIDES_TEMPLATE_PATH = Path(__file__).parent.parent / \
    "templates" / "slides.html"


SLIDE_WIDTH = 1280
SLIDE_HEIGHT = 720
SLIDE_FOOTER_HEIGHT = 48  # footer 영역 예약 높이


def build_layout_skeleton(
    layout_index: int,
    slide_index: int,
    speaker_notes: str = "",
) -> str:
    """LAYOUT_REGIONS 좌표를 기반으로 <section> 골격 HTML을 생성한다.

    각 region div에 data-region 속성과 position:absolute 스타일을 부여하여
    LLM이 내부 컨텐츠만 채우도록 구조를 강제한다.

    body region은 height를 고정하지 않고 슬라이드 하단(footer 제외)까지
    자동 확장하여 컨텐츠가 잘리지 않도록 한다.
    """
    regions = LAYOUT_REGIONS.get(
        layout_index, LAYOUT_REGIONS[DEFAULT_LAYOUT_INDEX])
    parts: list[str] = []
    escaped_notes = html.escape(
        speaker_notes, quote=True) if speaker_notes else ""
    notes_attr = f' data-speaker-notes="{escaped_notes}"' if speaker_notes else ' data-speaker-notes=""'
    parts.append(
        f'<section id="slide-{slide_index}" data-layout-index="{layout_index}"{notes_attr}>')
    parts.append(
        '  <div data-wrapper="true" style="position:absolute; top:0; left:0; right:0; bottom:0;">')

    for region_name, coords in regions.items():
        if region_name == "body":
            # body region: absolute positioning 없이 margin으로 위치만 지정
            # 컨텐츠에 맞게 높이 자동 조절
            style = (
                f"margin-left:{coords['left']}px; margin-top:{coords['top']}px; "
                f"width:{coords['width']}px;"
            )
        else:
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
    "- 템플릿에 사전 정의된 CSS 클래스를 적극 활용하세요.\n"
    "- <style> 태그를 출력하지 마세요. 커스텀 CSS 클래스를 절대 만들지 마세요.\n\n"
    "스타일링 우선순위 (매우 중요):\n"
    "- 가능한 한 항상 Tailwind CSS 유틸리티 클래스를 사용하세요. 인라인 style은 최후의 수단입니다.\n"
    "- Tailwind로 표현 가능한 속성은 반드시 클래스로 작성하세요:\n"
    "  · 레이아웃: flex, flex-col, grid, items-center, justify-center, gap-4, gap-8 등\n"
    "  · 간격: p-4, px-8, py-10, mt-2, mb-4 등\n"
    "  · 크기: w-full, h-full, w-1/2, min-h-0 등\n"
    "  · 타이포그래피: text-sm, text-base, text-lg, text-xl, text-2xl, text-4xl, font-bold, font-extrabold, leading-relaxed 등\n"
    "  · 색상: text-white, text-gray-400, bg-gray-900, bg-slate-800 등\n"
    "  · 테두리/모양: rounded-lg, rounded-xl, border, border-gray-700 등\n"
    "  · 기타: overflow-hidden, z-10, opacity-80 등\n"
    "- 인라인 style은 다음 경우에만 사용하세요:\n"
    "  · Tailwind에 없는 정확한 커스텀 색상값 (예: style=\"color:#FF9900;\")\n"
    "  · 정확한 px 좌표 지정이 필요한 position:absolute 요소\n"
    "  · 그라데이션 (linear-gradient 등)\n"
    "  · Tailwind로 표현할 수 없는 특수 속성\n"
    "- 자주 사용하는 매핑 (반드시 인라인 대신 클래스 사용):\n"
    "  · padding:12px → p-3, padding:16px → p-4, padding:20px → p-5, padding:24px → p-6\n"
    "  · gap:12px → gap-3, gap:16px → gap-4, gap:20px → gap-5, gap:24px → gap-6, gap:32px → gap-8\n"
    "  · display:flex → flex, display:grid → grid, flex-direction:column → flex-col\n"
    "  · grid-template-columns:1fr 1fr → grid-cols-2, 1fr 1fr 1fr → grid-cols-3, 1fr 1fr 1fr 1fr → grid-cols-4\n"
    "  · font-size:0.875rem → text-sm, 1rem → text-base, 1.125rem → text-lg, 1.25rem → text-xl, 1.5rem → text-2xl, 2.25rem → text-4xl\n"
    "  · height:100% → h-full, width:100% → w-full\n"
    "- 나쁜 예: <div style=\"display:flex; gap:32px; padding:16px;\"> → 좋은 예: <div class=\"flex gap-8 p-4\">\n"
    "- 나쁜 예: <h2 style=\"font-size:2.25rem; font-weight:800; color:#fff;\"> → 좋은 예: <h2 class=\"text-4xl font-extrabold text-white\">\n"
    "- 나쁜 예: <div style=\"display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; height:100%;\"> → 좋은 예: <div class=\"grid grid-cols-3 gap-4 h-full\">\n\n"
    "슬라이드 레이아웃 (매우 중요):\n"
    "- 각 <section>은 position:relative, 크기 1280x720px 고정, overflow:hidden인 컨테이너입니다.\n"
    "- 각 section의 직계 자식으로 반드시 하나의 래퍼 div를 만들고, 이 div에 position:absolute; top:0; left:0; right:0; bottom:0을 지정하세요.\n"
    "- 래퍼 div에 display:flex와 background-color 등을 적용하여 슬라이드 전체를 커버하세요.\n"
    "- 래퍼 div에 padding:40px 64px을 적용하여 슬라이드 가장자리에 충분한 여백을 확보하세요.\n"
    "- 예시 구조 (제목+콘텐츠, Tailwind 우선):\n"
    "  <section id=\"slide-0\" data-speaker-notes=\"...\">\n"
    "    <div class=\"flex flex-col\" style=\"position:absolute; top:0; left:0; right:0; bottom:0; background-color:#232F3E; padding:40px 64px;\">\n"
    "      <div class=\"tech-grid\"></div>\n"
    "      <div class=\"z-10\">\n"
    "        <div class=\"accent-bar\"></div>\n"
    "        <h2 class=\"text-4xl font-extrabold text-white mb-2\">제목</h2>\n"
    "        <p class=\"accent-eyebrow\">SECTION LABEL</p>\n"
    "      </div>\n"
    "      <div class=\"flex-1 flex items-start gap-8 z-10\">\n"
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
    "- 0 (title): 제목 left=50 top=359 w=678 h=97, 부제목 left=64 top=458 w=678 h=56, body left=64 top=552 w=399 h=39. "
    "래퍼에 align-items:center; justify-content:center로 수직·수평 중앙 정렬. 큰 제목 + 구분선 + 부제목. 하단에 발표자 정보. 이미지 없이 텍스트만.\n"
    "- 22 (text_only): 제목 left=57 top=96 w=1152 h=56, 본문 left=64 top=180 w=1152 h=231. "
    "상단에 제목 + 구분선, 아래에 전체폭 본문 영역에 불릿/텍스트 배치. "
    "본문 영역이 231px이므로 콘텐츠가 반드시 이 안에 들어와야 합니다. 목록은 최대 5~6개(padding 줄임), feature-item은 4개 이내, 카드는 3개 이내.\n"
    "- 21 (chart): 제목 left=57 top=96 w=1152 h=56, 본문 left=64 top=180 w=1152 h=264. "
    "상단에 제목 + 구분선, 아래에 데이터 시각화.\n"
    "- 87 (closing): body left=65 top=380 w=209 h=39. "
    "텍스트 영역이 매우 작으므로 body에는 'Q&A' 같은 짧은 한 줄만 배치하세요. "
    "하지만 wrapper div에 큰 중앙 텍스트(예: position:absolute로 '감사합니다' 제목)를 추가하여 마무리 슬라이드답게 꾸미세요. "
    "예: wrapper에 <h1 style=\"position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); font-size:3rem; color:#fff;\">감사합니다</h1>를 추가.\n\n"
    "영역 좌표 적용 방법:\n"
    "- 래퍼 div의 padding으로 좌우 여백(약 56~64px)과 상단 여백(약 96px)을 맞추세요.\n"
    "- 제목은 top 좌표 위치에서 시작하도록 배치하세요.\n"
    "- 본문은 제목 아래 top 좌표에서 시작하여 height만큼의 영역 안에 들어오도록 하세요.\n"
    "- 본문 영역 하단(top+height)을 넘지 않도록 콘텐츠 양을 조절하세요.\n"
    "- 이 좌표는 가이드라인이며, display:flex/display:grid 레이아웃으로 자연스럽게 구현하세요.\n\n"
    "디자인 원칙:\n"
    "- 폰트는 템플릿에서 전역 설정(Inter, Pretendard)되므로 별도 지정하지 마세요.\n"
    "- 모노스페이스 폰트가 필요하면 font-family:'Roboto Mono', monospace를 사용하세요.\n"
    "- 배경색은 반드시 인라인 style의 background-color로 래퍼 div에 직접 지정하세요.\n"
    "- 슬라이드 간 일관된 디자인 테마를 유지하세요.\n"
    "- Tailwind CSS 유틸리티 클래스를 적극 활용하세요 (예: text-gray-400, flex, gap-4, rounded-lg 등).\n"
    "- Font Awesome 아이콘을 활용하세요 (예: <i class=\"fa-solid fa-brain\" style=\"color:#FF9900;\"></i>).\n"
    "- 배경 장식이 필요하면 .tech-grid(격자) 또는 .tech-dots(도트)를 래퍼 div 안에 첫 자식으로 추가하세요.\n"
    "- 타이포그래피 규칙 (프레젠테이션 스케일 — 1280x720px 슬라이드 기준):\n"
    "  · 슬라이드 대제목(임팩트): 2.5~4rem(40~64px), font-weight:800 — 타이틀/아젠다 슬라이드처럼 여백이 많을 때\n"
    "  · 슬라이드 제목(일반): .slide-title 클래스 또는 2.5rem(40px), font-weight:800\n"
    "  · 부제목: .slide-subtitle 클래스 또는 1.1~1.2rem(17.6~19.2px), Roboto Mono\n"
    "  · 리스트 항목(주요): 1.2~1.6rem(19.2~25.6px) — 아젠다, 핵심 포인트 등 콘텐츠가 적은 슬라이드\n"
    "  · 카드/섹션 제목: 0.9~1.1rem(14.4~17.6px), font-weight:700 — 콘텐츠가 많은 슬라이드\n"
    "  · 본문/설명: 0.9~1rem(14.4~16px), line-height:1.4~1.5 — 카드 내부, 설명 텍스트\n"
    "  · 보조 텍스트/라벨: .accent-eyebrow, .step-number, .tag 클래스 (0.8~1.2rem, Roboto Mono)\n"
    "  · 코드/토큰: .code-display, .token-box 클래스 (0.9rem, Roboto Mono)\n"
    "  · 최소 글꼴: 0.75rem(12px). 이보다 작은 글꼴은 사용하지 마세요.\n"
    "  · 핵심 원칙: 콘텐츠 양에 따라 텍스트 크기를 조절하세요. 항목이 적으면 크게(1.2~1.6rem), 많으면 밀도있게(0.9~1rem).\n\n"
    "슬라이드 구조 패턴 (header-area + content-area 방식 권장):\n"
    "  <section id=\"slide-0\" data-speaker-notes=\"...\">\n"
    "    <div style=\"position:absolute; top:0; left:0; right:0; bottom:0; background-color:#232F3E;\" class=\"flex flex-col\">\n"
    "      <div class=\"tech-grid\"></div>\n"
    "      <div class=\"header-area\">\n"
    "        <div class=\"accent-bar\"></div>\n"
    "        <h1 class=\"slide-title\">제목</h1>\n"
    "        <p class=\"slide-subtitle\">부제목 텍스트</p>\n"
    "      </div>\n"
    "      <div class=\"content-area\">\n"
    "        <div class=\"text-col\"><!-- 좌측 --></div>\n"
    "        <div class=\"visual-col\"><!-- 우측 --></div>\n"
    "      </div>\n"
    "    </div>\n"
    "  </section>\n\n"
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
    "- 커스텀 CSS 클래스를 절대 만들지 마세요. <style> 태그를 출력하지 마세요.\n\n"
    "스타일링 우선순위 (매우 중요):\n"
    "- 가능한 한 항상 Tailwind CSS 유틸리티 클래스를 사용하세요. 인라인 style은 최후의 수단입니다.\n"
    "- Tailwind로 표현 가능한 속성은 반드시 클래스로 작성하세요:\n"
    "  · 레이아웃: flex, flex-col, grid, items-center, justify-center, gap-4, gap-8 등\n"
    "  · 간격: p-4, px-8, py-10, mt-2, mb-4 등\n"
    "  · 크기: w-full, h-full, w-1/2, min-h-0 등\n"
    "  · 타이포그래피: text-sm, text-base, text-lg, text-xl, text-2xl, text-4xl, font-bold, font-extrabold, leading-relaxed 등\n"
    "  · 색상: text-white, text-gray-400, bg-gray-900, bg-slate-800 등\n"
    "  · 테두리/모양: rounded-lg, rounded-xl, border, border-gray-700 등\n"
    "  · 기타: overflow-hidden, z-10, opacity-80 등\n"
    "- 인라인 style은 다음 경우에만 사용하세요:\n"
    "  · Tailwind에 없는 정확한 커스텀 색상값 (예: style=\"color:#FF9900;\")\n"
    "  · data-wrapper의 background-color 지정\n"
    "  · 그라데이션 (linear-gradient 등)\n"
    "  · Tailwind로 표현할 수 없는 특수 속성\n"
    "- 자주 사용하는 매핑 (반드시 인라인 대신 클래스 사용):\n"
    "  · padding:12px → p-3, padding:16px → p-4, padding:20px → p-5, padding:24px → p-6\n"
    "  · gap:12px → gap-3, gap:16px → gap-4, gap:20px → gap-5, gap:24px → gap-6, gap:32px → gap-8\n"
    "  · display:flex → flex, display:grid → grid, flex-direction:column → flex-col\n"
    "  · grid-template-columns:1fr 1fr → grid-cols-2, 1fr 1fr 1fr → grid-cols-3, 1fr 1fr 1fr 1fr → grid-cols-4\n"
    "  · font-size:0.875rem → text-sm, 1rem → text-base, 1.125rem → text-lg, 1.25rem → text-xl, 1.5rem → text-2xl, 2.25rem → text-4xl\n"
    "  · height:100% → h-full, width:100% → w-full\n"
    "- 나쁜 예: <div style=\"display:flex; gap:32px; padding:16px;\"> → 좋은 예: <div class=\"flex gap-8 p-4\">\n"
    "- 나쁜 예: <h2 style=\"font-size:2.25rem; font-weight:800; color:#fff;\"> → 좋은 예: <h2 class=\"text-4xl font-extrabold text-white\">\n"
    "- 나쁜 예: <div style=\"display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; height:100%;\"> → 좋은 예: <div class=\"grid grid-cols-3 gap-4 h-full\">\n\n"
    "사용 가능한 CSS 컴포넌트 클래스:\n"
    "- Layout: .two-col (2칼럼 grid), .two-col-wide (1.2fr 0.8fr), .three-col (3칼럼)\n"
    "- Typography: .tag (모노스페이스 라벨), .accent-eyebrow (상단 라벨, 모노스페이스+오렌지), .subtitle (부제목), .divider-bar (구분선), .accent-bar (오렌지 강조 바)\n"
    "- Cards: .info-card (정보 카드), .step-card (단계 카드, 좌측 보더), .summary-card (요약 카드, 중앙 정렬)\n"
    "- Lists: .agenda-list (목차 리스트), .feature-list (기능 리스트 컨테이너), .feature-item (기능 항목)\n"
    "- Concept: .concept-list (개념 리스트), .concept-item (아이콘+텍스트 항목), .concept-icon (아이콘), .concept-header (항목 제목), .concept-desc (항목 설명)\n"
    "- Comparison: .vs-container (VS 3칼럼 grid), .vs-panel (비교 패널), .vs-badge (VS 뱃지)\n"
    "- Code: .code-block (코드 래퍼), .code-header (파일명/언어), .code-body (코드 본문)\n"
    "- Token: .token-box (코드/데이터 토큰), .token-box.json (JSON 강조, 인디고), .token-box.highlight (오렌지 강조)\n"
    "- Diagrams: .arch-flow (흐름도 flex), .arch-stage (단계 박스), .arch-arrow (화살표)\n"
    "           .pipeline-flow (파이프라인 flex), .pipeline-stage (파이프라인 단계)\n"
    "           .diagram-frame (이미지/다이어그램 프레임), .frame-label (프레임 내 라벨)\n"
    "- Background: .tech-grid (격자 배경 패턴), .tech-dots (도트 배경 패턴) — 래퍼 div 안 첫 자식으로 사용\n"
    "- Labels: .tech-label (플로팅 기술 라벨 뱃지), .slide-footer (우측 하단 슬라이드 푸터)\n"
    "- Quote: .quote-box (인용문, 좌측 보더)\n"
    "- Grids: .summary-grid (2x2 grid), .info-grid-3 (3칼럼 grid)\n"
    "- CTA: .cta-box (Call-to-Action 박스)\n"
    "- Flow: .flow-diagram (플로우 flex), .flow-token (입력 토큰), .flow-arrow (화살표),\n"
    "        .flow-process (처리 단계 강조), .flow-result (결과 박스, 초록)\n\n"
    "외부 라이브러리 (템플릿에 포함됨, 적극 활용하세요):\n"
    "- Tailwind CSS: 유틸리티 클래스 사용 가능 (예: text-gray-400, flex, items-center, gap-4, rounded-lg, p-4, mt-2 등)\n"
    "- Font Awesome 6: 아이콘 사용 가능 (예: <i class=\"fa-solid fa-brain\"></i>, <i class=\"fa-solid fa-gears\"></i>, <i class=\"fa-solid fa-cube\"></i>)\n"
    "- Google Fonts: Inter(본문), Roboto Mono(모노스페이스) 사용 가능\n\n"
    "component_hint별 HTML 구조 예시:\n"
    "- bullets: <ul><li class=\"text-base leading-relaxed\">항목</li></ul>\n"
    "- two_column: <div class=\"two-col\"><div class=\"info-card\">좌</div><div class=\"info-card\">우</div></div>\n"
    "- vs_comparison: <div class=\"vs-container\"><div class=\"vs-panel\">A</div><div class=\"vs-badge\">VS</div><div class=\"vs-panel\">B</div></div>\n"
    "- step_cards: <div class=\"three-col\"><div class=\"step-card\">1단계</div><div class=\"step-card\">2단계</div><div class=\"step-card\">3단계</div></div>\n"
    "- code_block: <div class=\"code-block\"><div class=\"code-header\">main.py</div><div class=\"code-body\">print('hello')</div></div>\n"
    "- arch_diagram: <div class=\"arch-flow\"><div class=\"arch-stage\">입력</div><div class=\"arch-arrow\">→</div><div class=\"arch-stage\">처리</div><div class=\"arch-arrow\">→</div><div class=\"arch-stage\">출력</div></div>\n"
    "- pipeline: <div class=\"pipeline-flow\"><div class=\"pipeline-stage\">1단계</div><div class=\"pipeline-stage\">2단계</div></div>\n"
    "- quote: <div class=\"quote-box\">인용문 텍스트</div>\n"
    "- summary_grid: <div class=\"summary-grid\"><div class=\"summary-card\">항목1</div><div class=\"summary-card\">항목2</div></div>\n"
    "- agenda: <ul class=\"agenda-list\"><li class=\"py-1.5 text-lg\">안건 1</li></ul> (6개 이상이면 text-base py-1)\n"
    "- info_cards: <div class=\"three-col\"><div class=\"info-card\">카드1</div><div class=\"info-card\">카드2</div><div class=\"info-card\">카드3</div></div>\n"
    "- feature_list: <div class=\"feature-list\"><div class=\"feature-item\">기능1</div><div class=\"feature-item\">기능2</div></div>\n"
    "- cta: <div class=\"cta-box\"><h3>행동 유도 메시지</h3></div>\n"
    "- process_flow: <div class=\"two-col\"><div><div class=\"step-card\">설명 1</div><div class=\"step-card\">설명 2</div></div>"
    "<div><div class=\"flow-diagram\"><div class=\"flow-token\">입력</div><div class=\"flow-arrow\">→</div>"
    "<div class=\"flow-process\">처리</div><div class=\"flow-arrow\">→</div><div class=\"flow-result\">결과</div></div></div></div>\n"
    "- quote_code: <div class=\"two-col\"><div><div class=\"quote-box\">핵심 인용문</div>"
    "<div class=\"feature-list\"><div class=\"feature-item\">특징 1</div></div></div>"
    "<div><div class=\"code-block\"><div class=\"code-header\">example.py</div><div class=\"code-body\">코드 내용</div></div></div></div>\n"
    "- concept_list: <div class=\"concept-list\"><div class=\"concept-item\">"
    "<i class=\"fa-solid fa-cube concept-icon\"></i>"
    "<div><p class=\"concept-header\">제목</p><p class=\"concept-desc\">설명 텍스트</p></div>"
    "</div></div>\n\n"
    "영역별 콘텐츠 가이드:\n"
    "- title 영역: .slide-title 클래스 또는 2.5rem(40px), font-weight:800. .accent-bar 또는 .divider-bar 등 장식 요소 포함 가능.\n"
    "- subtitle 영역: .slide-subtitle 클래스 또는 1.1rem(17.6px). .accent-eyebrow 클래스로 라벨 표현 가능.\n"
    "- body 영역: component_hint에 맞는 CSS 컴포넌트를 사용하세요.\n"
    "- closing 레이아웃(layout 87): body 영역이 매우 작습니다(209x39px). body에는 짧은 텍스트만 넣고, "
    "data-wrapper div에 큰 중앙 제목을 position:absolute로 추가하여 마무리 슬라이드를 꾸미세요.\n"
    "\n"
    "타이포그래피 규칙 (프레젠테이션 스케일 — body 영역 내):\n"
    "- 리스트 항목(주요): 1.2~1.6rem(19.2~25.6px) — 아젠다, 핵심 포인트 등 항목이 적을 때\n"
    "- 카드/섹션 제목(h3): 0.9~1.1rem(14.4~17.6px), font-weight:700 — 콘텐츠가 많을 때\n"
    "- 본문/설명: 0.9~1rem(14.4~16px), line-height:1.4~1.5\n"
    "- 보조 텍스트/라벨: .step-number(0.9rem), .tag(0.875rem), .accent-eyebrow(1rem~1.2rem) 클래스 사용\n"
    "- 코드/토큰: .code-display, .token-box 클래스 (0.9rem, Roboto Mono)\n"
    "- 강조(<strong>): 강조색 적용, font-weight:700\n"
    "- 최소 글꼴: 0.75rem(12px). 이보다 작은 글꼴은 사용하지 마세요.\n"
    "- 핵심 원칙: 콘텐츠 양에 따라 텍스트 크기를 조절하세요. 항목이 적으면 크게, 많으면 밀도있게.\n"
    "\n"
    "overflow 방지 규칙 (반드시 준수 — 가장 중요한 규칙):\n"
    "- body 영역 높이(보통 231px)를 절대 초과하지 마세요. overflow:hidden이므로 넘치면 잘립니다.\n"
    "- 높이 계산 가이드 (231px 기준):\n"
    "  · agenda-list li(py-1.5, text-lg → 약 28px/항목): 최대 7개=196px. 항목이 6개 이상이면 text-base py-1으로 줄이세요.\n"
    "  · feature-item(padding:12px, font:1.1rem → 약 44px/항목): 최대 4개=176px. gap은 8px 이내.\n"
    "  · two-col/three-col 내부: 카드 3개 이내, 각 카드 padding 12~16px.\n"
    "  · vs-container: 양쪽 패널에 각각 항목 3개 이내, 패널 padding 16px 이내.\n"
    "  · pipeline-flow/arch-flow: 단계 4~5개 이내, padding 12px 이내.\n"
    "- 상위 컨테이너에 height:100%를 설정하되 내부 콘텐츠가 그 안에 들어와야 합니다.\n"
    "- padding/gap/margin을 최소화하세요: gap은 8~12px, padding은 12~16px.\n"
    "- 스크롤은 허용하지 않습니다. 넘치면 잘립니다.\n"
    "- 장식용 배경 요소(원, 도형 등)를 영역 내부에 사용하지 마세요.\n"
    "- 콘텐츠가 많으면 반드시 font-size를 줄이거나(최소 0.85rem) 항목 수를 줄이세요.\n\n"
    "디자인 원칙:\n"
    "- 폰트는 템플릿에서 전역 설정(Inter, Pretendard)되므로 별도 지정하지 마세요.\n"
    "- 모노스페이스 폰트가 필요하면 font-family:'Roboto Mono', monospace를 사용하세요.\n"
    "- 슬라이드 간 일관된 디자인 테마를 유지하세요.\n"
    "- 텍스트 색상은 배경색에 맞는 대비를 유지하세요.\n"
    "- Tailwind CSS 유틸리티 클래스를 적극 활용하세요 (예: text-gray-400, flex, gap-4, rounded-lg 등).\n"
    "- Font Awesome 아이콘을 활용하여 시각적 풍부함을 더하세요 (예: <i class=\"fa-solid fa-brain\" style=\"color:#FF9900;\"></i>).\n"
    "- 배경 장식이 필요하면 .tech-grid(격자) 또는 .tech-dots(도트)를 래퍼 div 안에 첫 자식으로 추가하세요.\n\n"
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
    "- 레이아웃 조정: 요소 위치, 크기, 간격 변경 (Tailwind 클래스 우선, 불가 시 인라인 style)\n"
    "- 스타일 변경: 색상, 배경색, 테두리 등 변경 (Tailwind 클래스 우선, 커스텀 색상 등은 인라인 style)\n"
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
    "스타일링 우선순위 (매우 중요):\n"
    "- 가능한 한 항상 Tailwind CSS 유틸리티 클래스를 사용하세요. 인라인 style은 최후의 수단입니다.\n"
    "- Tailwind로 표현 가능한 속성은 반드시 클래스로 작성하세요:\n"
    "  · 레이아웃: flex, flex-col, grid, items-center, justify-center, gap-4, gap-8 등\n"
    "  · 간격: p-4, px-8, py-10, mt-2, mb-4 등\n"
    "  · 크기: w-full, h-full, w-1/2, min-h-0 등\n"
    "  · 타이포그래피: text-sm, text-base, text-lg, text-xl, text-2xl, text-4xl, font-bold, font-extrabold, leading-relaxed 등\n"
    "  · 색상: text-white, text-gray-400, bg-gray-900, bg-slate-800 등\n"
    "  · 테두리/모양: rounded-lg, rounded-xl, border, border-gray-700 등\n"
    "  · 기타: overflow-hidden, z-10, opacity-80 등\n"
    "- 인라인 style은 다음 경우에만 사용하세요:\n"
    "  · Tailwind에 없는 정확한 커스텀 색상값 (예: style=\"color:#FF9900;\")\n"
    "  · 정확한 px 좌표 지정이 필요한 position:absolute 요소\n"
    "  · 그라데이션 (linear-gradient 등)\n"
    "  · Tailwind로 표현할 수 없는 특수 속성\n"
    "- 자주 사용하는 매핑 (반드시 인라인 대신 클래스 사용):\n"
    "  · padding:12px → p-3, padding:16px → p-4, padding:20px → p-5, padding:24px → p-6\n"
    "  · gap:12px → gap-3, gap:16px → gap-4, gap:20px → gap-5, gap:24px → gap-6, gap:32px → gap-8\n"
    "  · display:flex → flex, display:grid → grid, flex-direction:column → flex-col\n"
    "  · grid-template-columns:1fr 1fr → grid-cols-2, 1fr 1fr 1fr → grid-cols-3, 1fr 1fr 1fr 1fr → grid-cols-4\n"
    "  · font-size:0.875rem → text-sm, 1rem → text-base, 1.125rem → text-lg, 1.25rem → text-xl, 1.5rem → text-2xl, 2.25rem → text-4xl\n"
    "  · height:100% → h-full, width:100% → w-full\n"
    "- 나쁜 예: <div style=\"display:flex; gap:32px; padding:16px;\"> → 좋은 예: <div class=\"flex gap-8 p-4\">\n"
    "- 기존 코드에 인라인 style로 되어 있는 부분도, 수정 시 Tailwind 클래스로 대체할 수 있으면 대체하세요.\n\n"
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
    "- data-region div 내부의 콘텐츠만 수정 가능합니다.\n"
    "- Tailwind CSS 유틸리티 클래스를 인라인 style보다 우선 사용하세요. "
    "인라인 style은 커스텀 색상값, position:absolute 좌표, 그라데이션 등 Tailwind로 표현할 수 없는 경우에만 사용하세요."
)

# --- F5-LLM: HTML→PPTX LLM 변환 ---
PPTX_CONVERT_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
PPTX_CONVERT_MAX_TOKENS = 8_000

PPTX_CONVERT_SYSTEM_PROMPT = (
    "당신은 HTML 슬라이드를 PPTX 요소 JSON으로 변환하는 전문가입니다.\n"
    "주어진 <section> HTML을 분석하여, python-pptx로 재현할 수 있는 텍스트박스와 도형의 "
    "위치/크기/서식 정보를 JSON으로 출력하세요.\n\n"
    "이미지가 함께 제공되는 경우:\n"
    "- 이미지는 해당 HTML을 브라우저에서 렌더링한 정확한 스크린샷(1280x720px)입니다.\n"
    "- flex/grid 레이아웃의 실제 배치 결과는 이미지를 기준으로 판단하세요.\n"
    "- HTML 코드와 이미지 사이에 차이가 있다면 이미지의 시각적 위치를 우선하세요.\n\n"
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
    "제목은 28~36pt(최대 36pt 초과 금지), 본문은 16~22pt, 보조 텍스트는 12~16pt를 권장합니다. "
    "font_size_pt가 커지면 height_px도 비례하여 커져야 합니다 (height_px ≥ 줄수 × font_size_pt × 1.5).\n"
    "- font_size_pt와 height_px의 관계를 반드시 지켜주세요:\n"
    "  · 1pt ≈ 1.33px이므로, 단일 행 텍스트박스의 height_px ≥ font_size_pt × 1.5\n"
    "  · 여러 줄이면: height_px ≥ 줄수 × font_size_pt × 1.5\n"
    "  · 예: font_size_pt=28이면 height_px ≥ 42, font_size_pt=20이면 height_px ≥ 30\n"
    "  · 텍스트박스 높이가 부족하면 font_size_pt를 줄이거나 height_px를 늘리세요.\n"
    "- 권장 크기 범위 (엄격히 지켜주세요):\n"
    "  · 제목(h1): font_size_pt 28~36, height_px 50~60\n"
    "  · 본문: font_size_pt 16~22, height_px ≥ font_size_pt × 1.5 × 줄수\n"
    "  · 보조 텍스트: font_size_pt 12~16\n"
    "- 텍스트박스가 서로 겹치지 않도록 주의하세요.\n"
    "- 반드시 JSON만 출력하세요. 마크다운 코드블록으로 감싸지 마세요.\n\n"
    "=== 하드 제약 조건 (위반 시 렌더링 실패) ===\n"
    "1. 폰트 크기: 모든 font_size_pt와 text_size_pt는 반드시 10~44pt 범위여야 합니다. "
    "이 범위를 벗어나면 후처리에서 강제 클램핑됩니다.\n"
    "2. 좌표 경계: 모든 요소는 0 ≤ left_px < 1280, 0 ≤ top_px < 720이어야 합니다. "
    "left_px + width_px ≤ 1280, top_px + height_px ≤ 720이어야 합니다.\n"
    "3. shape의 text 필드: 카드, 박스 등 텍스트를 포함하는 shape에는 반드시 text 필드를 채우세요. "
    "텍스트 없이 shape만 두면 빈 박스가 렌더링됩니다.\n"
    "4. 카드 패턴: 카드(info-card, step-card 등)는 shape(rounded_rectangle) + 내부 textbox 조합으로 변환하세요.\n"
    "   예시 — 3칼럼 카드:\n"
    "   shapes: [{left_px:64, top_px:180, width_px:370, height_px:200, shape_type:\"rounded_rectangle\", "
    "fill_color:\"#1e293b\", text:\"카드 제목\\n\\n카드 설명 텍스트\", text_color:\"#ffffff\", text_size_pt:16}]\n"
    "   각 카드의 제목과 본문을 모두 text에 \\n으로 구분하여 포함하세요.\n"
    "5. 텍스트 누락 금지: HTML에 보이는 모든 텍스트 콘텐츠는 반드시 textbox 또는 shape의 text로 출력하세요. "
    "카드 내부 본문, 리스트 항목, 설명 텍스트가 누락되면 안 됩니다."
)

PPTX_CONVERT_USER_PROMPT_TEMPLATE = (
    "다음 HTML <section>을 PPTX 요소 JSON으로 변환해주세요.\n\n"
    "슬라이드 HTML:\n{section_html}"
)

PPTX_CONVERT_USER_PROMPT_WITH_IMAGE_TEMPLATE = (
    "다음 HTML <section>을 PPTX 요소 JSON으로 변환해주세요.\n\n"
    "첨부된 이미지는 이 HTML을 브라우저에서 렌더링한 스크린샷(1280x720px)입니다.\n"
    "이미지를 참고하여 각 요소의 정확한 위치와 크기를 결정하세요.\n\n"
    "슬라이드 HTML:\n{section_html}"
)
