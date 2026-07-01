import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / "env" / "local.env", override=False)

PPT_GENERATOR_HOME = Path.home() / ".ppt-generator"

# --- Visual QA ---
# 스크린샷 캡처 병렬도 (Playwright, 서버측). LLM 분석/수정은 클라이언트가 담당.
VISUAL_QA_PARALLEL = int(os.environ.get("VISUAL_QA_PARALLEL", "8"))
VISUAL_QA_MAX_ITERATIONS = int(os.environ.get("VISUAL_QA_MAX_ITERATIONS", "2"))

# --- Timeouts (seconds) ---
SCREENSHOT_TIMEOUT = int(os.environ.get("SCREENSHOT_TIMEOUT", "60"))

VISUAL_QA_VIEWPORT_WIDTH = 1280
VISUAL_QA_VIEWPORT_HEIGHT = 720

DEFAULT_NUM_SLIDES = 5
MIN_NUM_SLIDES = 3
MAX_NUM_SLIDES = 20

VALID_AUDIENCE_TYPES = ("general", "technical", "executive")
DEFAULT_AUDIENCE_TYPE = "general"
DEFAULT_PRESENTATION_MINUTES = 15
MIN_PRESENTATION_MINUTES = 3
MAX_PRESENTATION_MINUTES = 60

# --- Structured Output JSON Schemas (re-export) ---

from ppt_generator.interfaces.json_schemas import OUTLINE_JSON_SCHEMA  # noqa: E402

# --- PPTX numeric constants ---

PPTX_SLIDE_WIDTH_EMU = 12_192_000  # 13.333" x 914400
PPTX_SLIDE_HEIGHT_EMU = 6_858_000  # 7.5" x 914400
PPTX_FONT_NAME = "맑은 고딕"
PPTX_MONOSPACE_FONT_NAME = "Consolas"
PPTX_BODY_FONT_SIZE_PT = 20
PPTX_TITLE_FONT_SIZE_PT = 32

PPTX_BULLET_CHAR_L0 = "\u2022"
PPTX_BULLET_MARGIN_EMU_L0 = 228600  # ~0.25in
PPTX_BULLET_INDENT_EMU_L0 = -171450
PPTX_BULLET_MARGIN_EMU_L1 = 457200  # ~0.5in
PPTX_BULLET_INDENT_EMU_L1 = -171450

SLIDES_WIDTH_PX = 1280
SLIDES_HEIGHT_PX = 720

PPTX_VALIDATE_FONT_MIN_PT = 10
PPTX_VALIDATE_FONT_MAX_PT = 44
PPTX_VALIDATE_LINE_HEIGHT_FACTOR = 2.0  # pt→px(1.33) × line-height(1.5) ≈ 2.0

# Card-specific font floors (checked by lint for shapes with fill_color)
CARD_TITLE_FONT_MIN_PT = 18
CARD_BODY_FONT_MIN_PT = 16
SECTION_LABEL_FONT_MIN_PT = 14
SLIDE_TITLE_FONT_MIN_PT = 24

SPEC_VALIDATE_MARGIN_PX = 64  # Min margin from slide edges (px)
SPEC_VALIDATE_MARGIN_BOTTOM_PX = 32  # Min bottom margin (px)
SPEC_VALIDATE_MIN_GAP_PX = 8  # Min gap between text shapes (px)

EXPORT_PX_TO_INCHES_X = 13.333 / 1280  # ~0.01042
EXPORT_PX_TO_INCHES_Y = 7.5 / 720  # ~0.01042

# --- Text measurement constants ---

TEXT_MEASURE_PX_PER_PT = 1.333
TEXT_MEASURE_CJK_WIDTH_RATIO = 0.9
TEXT_MEASURE_LATIN_WIDTH_RATIO = 0.55
TEXT_MEASURE_MONOSPACE_WIDTH_RATIO = 0.6
TEXT_MEASURE_BULLET_INDENT_L0_PX = 24.0
TEXT_MEASURE_BULLET_INDENT_L1_PX = 48.0
TEXT_MEASURE_DEFAULT_SHAPE_PADDING_LR_PX = 4.8
TEXT_MEASURE_DEFAULT_SHAPE_PADDING_TB_PX = 2.4

# PPT의 폰트 메트릭(시스템 폰트)과 브라우저의 폰트 메트릭(웹 폰트) 차이를 흡수하기 위한 nowrap 게이트.
# 단일 paragraph 텍스트의 추정 폭이 사용 가능 폭의 이 배율 이내면 white-space:nowrap을 적용한다.
# 1.15(과거)는 박스를 뚫고 좌우로 텍스트가 넘치는 사고를 유발했다.
# 0.95는 박스 폭의 5% 안전 마진을 남겨 어떤 메트릭 차이가 있어도 좌우 오버플로우가 발생하지 않도록 한다.
# 메트릭 차이로 짧은 라벨이 wrap 되는 케이스는 spec 단계에서 박스 폭을 살짝 키워 해결한다.
TEXT_MEASURE_NOWRAP_TOLERANCE_RATIO = 0.95

# --- Lint thresholds ---
# 화살표 끝점이 이 거리 이내에 박스 외곽 변이 있어야 부착된 것으로 간주.
LINT_ARROW_ATTACH_TOLERANCE_PX = 8.0
# label-orphan: 라벨 textbox 가 이 거리 이내에 박스가 없으면 orphan.
LINT_LABEL_ORPHAN_PROXIMITY_PX = 32.0
# label-orphan: 라벨로 간주할 텍스트 길이/폰트/높이 상한.
LINT_LABEL_ORPHAN_MAX_CHARS = 12
LINT_LABEL_ORPHAN_MAX_FONT_PT = 14
LINT_LABEL_ORPHAN_MAX_HEIGHT_PX = 32.0
# textbox-shape-intrusion: 텍스트박스 bbox 가 fill 있는 다른 shape bbox 안으로
# 침범하는 양 (겹침 면적 / 텍스트박스 면적). 이 비율을 넘으면 위반.
LINT_TEXTBOX_INTRUSION_RATIO = 0.5
# decoration-shape-overlap: 작은 ellipse/뱃지 등이 fill 있는 카드 위에 얹힌 경우
# 겹침 면적 / decoration 면적 이 비율을 넘으면 위반.
LINT_DECORATION_OVERLAP_RATIO = 0.5
# decoration 으로 간주할 도형의 한 변 최대 길이 (px).
LINT_DECORATION_MAX_DIM_PX = 80.0
# textbox-textbox-overlap: 두 텍스트박스 bbox 의 교집합 면적이 더 작은 쪽 면적의
# 이 비율을 넘으면 위반. 글자끼리 충돌은 허용 안 함이라 임계값을 낮게 (10%) 둔다.
LINT_TEXTBOX_TEXTBOX_OVERLAP_RATIO = 0.1

PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU = 45720  # ~0.05 inch
PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU = 22860  # ~0.025 inch
PX_TO_EMU = 9525  # 914400 / 96
EMU_TO_PX = 1.0 / PX_TO_EMU  # inverse: EMU → px
EMU_PER_INCH = 914400
DPI = 96
IMPORT_EMU_TO_PX = DPI / EMU_PER_INCH  # EMU → px (= 1/9525)

COMPONENT_HINT_COMPLEXITY: dict[str, int] = {
    "arch_diagram": 5,
    "process_flow": 5,
    "pipeline": 5,
    "concept_list": 5,
    "vs_comparison": 5,
    "summary_grid": 5,
    "quote_code": 4,
    "step_cards": 4,
    "info_cards": 4,
    "code_block": 3,
    "two_column": 3,
    "feature_list": 2,
    "agenda": 1,
    "cta": 2,
    "bullets": 1,
    "quote": 1,
}

# --- Project directory layout ---
PROJECT_SLIDES_DIR = "slides"
PROJECT_IMAGES_DIR = "slides/images"
PROJECT_OUTLINE_DIR = "outline"

TEMPLATE_BG_IMAGES_DIR = (
    Path(__file__).parent.parent / "templates" / "template_bg_images"
)

SLIDES_TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "slides.html"
SLIDE_TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "slide.html"
SLIDES_CONTAINER_TEMPLATE_PATH = (
    Path(__file__).parent.parent / "templates" / "slides_container.html"
)

SLIDE_WIDTH = 1280
SLIDE_HEIGHT = 720
SLIDE_FOOTER_HEIGHT = 48

# --- Prompt constants (re-exported from prompts module) ---

from ppt_generator.interfaces.prompts import (  # noqa: E402
    BACKFILL_DESIGN_DOC_SYSTEM_PROMPT,
    BACKFILL_DESIGN_DOC_USER_PROMPT_TEMPLATE,
    COMPONENT_MODIFY_SYSTEM_PROMPT,
    COMPONENT_MODIFY_USER_PROMPT_TEMPLATE,
    DESIGN_DOC_DRAFT_USER_PROMPT_TEMPLATE,
    DESIGN_REVIEW_SYSTEM_PROMPT,
    DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE,
    DESIGN_SPEC_SYSTEM_PROMPT,
    DESIGN_SPEC_SYSTEM_PROMPTS,
    DESIGN_SPEC_USER_PROMPT_TEMPLATE,
    DESIGN_SUMMARY_USER_PROMPT_TEMPLATE,
    OUTLINE_SYSTEM_PROMPT,
    OUTLINE_USER_PROMPT_TEMPLATE,
    VISUAL_QA_ANALYSIS_SYSTEM_PROMPT,
    VISUAL_QA_FIX_SYSTEM_PROMPT,
)

__all__ = [
    # Numeric constants
    "DEFAULT_NUM_SLIDES",
    "MIN_NUM_SLIDES",
    "MAX_NUM_SLIDES",
    "VALID_AUDIENCE_TYPES",
    "DEFAULT_AUDIENCE_TYPE",
    "DEFAULT_PRESENTATION_MINUTES",
    "MIN_PRESENTATION_MINUTES",
    "MAX_PRESENTATION_MINUTES",
    "PPTX_SLIDE_WIDTH_EMU",
    "PPTX_SLIDE_HEIGHT_EMU",
    "PPTX_FONT_NAME",
    "PPTX_MONOSPACE_FONT_NAME",
    "PPTX_BODY_FONT_SIZE_PT",
    "PPTX_TITLE_FONT_SIZE_PT",
    "PPTX_BULLET_CHAR_L0",
    "PPTX_BULLET_MARGIN_EMU_L0",
    "PPTX_BULLET_INDENT_EMU_L0",
    "PPTX_BULLET_MARGIN_EMU_L1",
    "PPTX_BULLET_INDENT_EMU_L1",
    "SLIDES_WIDTH_PX",
    "SLIDES_HEIGHT_PX",
    "PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU",
    "PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU",
    "PX_TO_EMU",
    "EMU_TO_PX",
    "EMU_PER_INCH",
    "DPI",
    "IMPORT_EMU_TO_PX",
    "PPTX_VALIDATE_FONT_MIN_PT",
    "PPTX_VALIDATE_FONT_MAX_PT",
    "PPTX_VALIDATE_LINE_HEIGHT_FACTOR",
    "CARD_TITLE_FONT_MIN_PT",
    "CARD_BODY_FONT_MIN_PT",
    "SECTION_LABEL_FONT_MIN_PT",
    "SLIDE_TITLE_FONT_MIN_PT",
    "SPEC_VALIDATE_MARGIN_PX",
    "SPEC_VALIDATE_MARGIN_BOTTOM_PX",
    "SPEC_VALIDATE_MIN_GAP_PX",
    "EXPORT_PX_TO_INCHES_X",
    "EXPORT_PX_TO_INCHES_Y",
    # Text measurement constants
    "TEXT_MEASURE_PX_PER_PT",
    "TEXT_MEASURE_CJK_WIDTH_RATIO",
    "TEXT_MEASURE_LATIN_WIDTH_RATIO",
    "TEXT_MEASURE_MONOSPACE_WIDTH_RATIO",
    "TEXT_MEASURE_BULLET_INDENT_L0_PX",
    "TEXT_MEASURE_BULLET_INDENT_L1_PX",
    "TEXT_MEASURE_DEFAULT_SHAPE_PADDING_LR_PX",
    "TEXT_MEASURE_DEFAULT_SHAPE_PADDING_TB_PX",
    "TEXT_MEASURE_NOWRAP_TOLERANCE_RATIO",
    "LINT_ARROW_ATTACH_TOLERANCE_PX",
    "LINT_LABEL_ORPHAN_PROXIMITY_PX",
    "LINT_LABEL_ORPHAN_MAX_CHARS",
    "LINT_LABEL_ORPHAN_MAX_FONT_PT",
    "LINT_LABEL_ORPHAN_MAX_HEIGHT_PX",
    "LINT_TEXTBOX_INTRUSION_RATIO",
    "LINT_DECORATION_OVERLAP_RATIO",
    "LINT_DECORATION_MAX_DIM_PX",
    "LINT_TEXTBOX_TEXTBOX_OVERLAP_RATIO",
    "PROJECT_SLIDES_DIR",
    "PROJECT_IMAGES_DIR",
    "PROJECT_OUTLINE_DIR",
    "TEMPLATE_BG_IMAGES_DIR",
    "SLIDES_TEMPLATE_PATH",
    "SLIDE_TEMPLATE_PATH",
    "SLIDES_CONTAINER_TEMPLATE_PATH",
    "SLIDE_WIDTH",
    "SLIDE_HEIGHT",
    "SLIDE_FOOTER_HEIGHT",
    # JSON schemas
    "OUTLINE_JSON_SCHEMA",
    # Prompts (re-exported from prompts module)
    "BACKFILL_DESIGN_DOC_SYSTEM_PROMPT",
    "BACKFILL_DESIGN_DOC_USER_PROMPT_TEMPLATE",
    "COMPONENT_MODIFY_SYSTEM_PROMPT",
    "COMPONENT_MODIFY_USER_PROMPT_TEMPLATE",
    "DESIGN_DOC_DRAFT_USER_PROMPT_TEMPLATE",
    "DESIGN_REVIEW_SYSTEM_PROMPT",
    "DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE",
    "DESIGN_SPEC_SYSTEM_PROMPT",
    "DESIGN_SPEC_SYSTEM_PROMPTS",
    "DESIGN_SPEC_USER_PROMPT_TEMPLATE",
    "DESIGN_SUMMARY_USER_PROMPT_TEMPLATE",
    "OUTLINE_SYSTEM_PROMPT",
    "OUTLINE_USER_PROMPT_TEMPLATE",
    "VISUAL_QA_ANALYSIS_SYSTEM_PROMPT",
    "VISUAL_QA_FIX_SYSTEM_PROMPT",
    # Paths
    "PPT_GENERATOR_HOME",
    # Visual QA
    "VISUAL_QA_PARALLEL",
    "VISUAL_QA_MAX_ITERATIONS",
    "VISUAL_QA_VIEWPORT_WIDTH",
    "VISUAL_QA_VIEWPORT_HEIGHT",
    # Complexity
    "COMPONENT_HINT_COMPLEXITY",
    # Timeouts
    "SCREENSHOT_TIMEOUT",
]
