import json
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.constants import (
    DEFAULT_AUDIENCE_TYPE,
    DEFAULT_PRESENTATION_MINUTES,
    MAX_NUM_SLIDES,
    MAX_PRESENTATION_MINUTES,
    MIN_NUM_SLIDES,
    MIN_PRESENTATION_MINUTES,
    VALID_AUDIENCE_TYPES,
)
from ppt_generator.interfaces.schemas import OutlineRequest, ProjectMetadata
from ppt_generator.interfaces.utils import format_token_usage
from ppt_generator.tools.outline.service import OutlineService
from ppt_generator.tools.project.service import ProjectService


def register_outline_tools(mcp: FastMCP, outline_service: OutlineService, project_service: ProjectService) -> None:
    @mcp.tool()
    def generate_outline(
        topic: str,
        purpose: str = "",
        audience_type: str = DEFAULT_AUDIENCE_TYPE,
        presentation_minutes: int = DEFAULT_PRESENTATION_MINUTES,
        num_slides: int = 0,
        project_id: str = "",
    ) -> str:
        """주제를 기반으로 슬라이드 아웃라인 JSON을 생성합니다.

        주제의 핵심 내용을 분석하여 슬라이드별 제목, 내용 요약, 컴포넌트 힌트를
        포함한 구조화된 아웃라인을 생성합니다.
        아웃라인은 슬라이드의 구조만 결정하며, 디자인은 이후 HTML 슬라이드 생성 단계에서 결정됩니다.

        **중요 — 호출 전 필수 확인 사항:**
        이 도구를 호출하기 전에 반드시 사용자에게 다음 세 가지를 질문하여 확인하세요:
        1. **발표 목적** (purpose): 이 발표의 목적이 무엇인지 (예: "사내 기술 공유", "고객 제안", "컨퍼런스 발표")
        2. **발표 시간** (presentation_minutes): 몇 분짜리 발표인지
        3. **청중 유형** (audience_type): 청중이 누구인지 (일반인/기술자/의사결정자)
        사용자가 명시적으로 알려주지 않은 경우, 절대 기본값을 임의로 사용하지 말고 반드시 물어보세요.

        **중요: 아웃라인 생성 후 반드시 사용자에게 결과를 보여주고 확인을 받으세요.**
        사용자가 아웃라인 구조(슬라이드 수, 제목, 내용 구성 등)에 만족하는지 확인한 뒤
        다음 단계(generate_script)로 진행해야 합니다.
        사용자가 수정을 요청하면 수정 사항을 반영하여 generate_outline을 다시 호출하세요.

        Args:
            topic: 발표 주제 (예: "2024년 클라우드 컴퓨팅 트렌드")
            purpose: 발표 목적 (예: "사내 기술 공유", "고객 제안", "컨퍼런스 발표"). 사용자에게 반드시 확인 후 지정하세요.
            audience_type: 청중 유형 — "general" (일반), "technical" (기술), "executive" (의사결정자). 사용자에게 반드시 확인 후 지정하세요.
            presentation_minutes: 발표 시간(분). 3~60분. 사용자에게 반드시 확인 후 지정하세요.
            num_slides: 권장 슬라이드 수 (0이면 발표 시간 기준 자동 계산: 1~2분당 1장). 한 슬라이드에 하나의 주제만 다루기 위해 실제 생성 수는 달라질 수 있습니다.
            project_id: 프로젝트 ID (미지정 시 자동 생성)

        Returns:
            outline_path, project_id를 포함하는 JSON 문자열
        """
        if audience_type not in VALID_AUDIENCE_TYPES:
            audience_type = DEFAULT_AUDIENCE_TYPE
        presentation_minutes = max(MIN_PRESENTATION_MINUTES, min(MAX_PRESENTATION_MINUTES, presentation_minutes))
        if num_slides <= 0:
            num_slides = max(MIN_NUM_SLIDES, min(MAX_NUM_SLIDES, presentation_minutes // 2 + 2))
        else:
            num_slides = max(MIN_NUM_SLIDES, min(MAX_NUM_SLIDES, num_slides))
        request = OutlineRequest(
            topic=topic,
            num_slides=num_slides,
            audience_type=audience_type,
            presentation_minutes=presentation_minutes,
            purpose=purpose,
        )
        response = outline_service.generate(request)
        actual_num_slides = len(response.slides)
        result = json.dumps(asdict(response), ensure_ascii=False, indent=2)

        project_id, project_dir = project_service.resolve_project_dir(project_id)
        project_service.save_metadata(
            project_dir,
            ProjectMetadata(
                topic=topic,
                num_slides=actual_num_slides,
                steps_completed={},
                audience_type=audience_type,
                presentation_minutes=presentation_minutes,
                purpose=purpose,
            ),
        )
        project_service.save_outline(project_dir, result)
        project_service.update_step(project_dir, "outline")

        resp: dict = {
            "outline_path": str(project_dir / "outline.json"),
            "project_id": project_id,
        }
        usage = format_token_usage(outline_service.last_token_usage)
        if usage:
            resp["token_usage"] = usage
        return json.dumps(resp, ensure_ascii=False)
