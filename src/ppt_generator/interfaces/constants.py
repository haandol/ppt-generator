BEDROCK_MODEL_ID = "us.anthropic.claude-opus-4-20250514-v1:0"
BEDROCK_REGION = "us-east-1"
BEDROCK_TEMPERATURE = 0.7

DEFAULT_NUM_SLIDES = 5
MIN_NUM_SLIDES = 3
MAX_NUM_SLIDES = 20

SCRIPT_SYSTEM_PROMPT = (
    "당신은 전문 프레젠테이션 스크립트 작성자입니다. "
    "주어진 주제에 대해 청중 앞에서 발표하는 자연스러운 한국어 발표 스크립트를 작성하세요.\n\n"
    "작성 규칙:\n"
    "- 도입, 본론, 결론의 자연스러운 흐름을 갖추세요.\n"
    "- 슬라이드 번호나 구분 표시 없이 연속적인 발표 스크립트로 작성하세요.\n"
    "- 청중에게 말하듯 자연스러운 구어체를 사용하세요.\n"
    "- 핵심 내용을 명확하게 전달하되, 지나치게 길지 않게 작성하세요.\n"
    "- 스크립트 텍스트만 출력하세요. 다른 부가 설명은 포함하지 마세요."
)

SCRIPT_USER_PROMPT_TEMPLATE = (
    "주제: {topic}\n"
    "슬라이드 수: {num_slides}장\n\n"
    "위 주제에 대해 {num_slides}장 분량의 프레젠테이션에서 사용할 발표 스크립트를 작성해주세요."
)

OUTLINE_SYSTEM_PROMPT = (
    "당신은 프레젠테이션 구조 설계 전문가입니다. "
    "발표 스크립트를 분석하여 슬라이드 아웃라인을 JSON 형식으로 생성하세요.\n\n"
    "작성 규칙:\n"
    "- 스크립트 내용의 논리적 구분에 따라 적절한 슬라이드 수를 자동 결정하세요.\n"
    "- 최소 3장(제목/본문/마무리) 이상으로 구성하세요.\n"
    "- 각 슬라이드에 title, bullets, image_idea, layout_type, speaker_notes를 포함하세요.\n"
    "- layout_type은 title, text_image, text_only, chart, closing 중 하나를 선택하세요.\n"
    "- 첫 번째 슬라이드는 layout_type을 'title'로, 마지막 슬라이드는 'closing'으로 지정하세요.\n"
    "- image_idea는 해당 슬라이드의 시각적 요소를 설명하는 짧은 문장으로, 이미지 생성 프롬프트로 사용됩니다.\n"
    "- speaker_notes에는 해당 슬라이드에 대응하는 스크립트 내용을 포함하세요.\n"
    "- bullets는 핵심 요점을 간결하게 정리한 목록입니다.\n"
    "- 반드시 아래 JSON 형식만 출력하세요. 다른 텍스트는 포함하지 마세요.\n\n"
    "출력 형식:\n"
    "```json\n"
    '{"slides": [{"title": "...", "bullets": ["...", "..."], '
    '"image_idea": "...", "layout_type": "...", "speaker_notes": "..."}]}\n'
    "```"
)

OUTLINE_USER_PROMPT_TEMPLATE = (
    "다음 발표 스크립트를 분석하여 슬라이드 아웃라인 JSON을 생성해주세요.\n\n"
    "발표 스크립트:\n{script}"
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
