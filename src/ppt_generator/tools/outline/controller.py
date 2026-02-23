import json
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.constants import (
    DEFAULT_AUDIENCE_LEVEL,
    DEFAULT_PRESENTATION_MINUTES,
    MAX_NUM_SLIDES,
    MAX_PRESENTATION_MINUTES,
    MIN_NUM_SLIDES,
    MIN_PRESENTATION_MINUTES,
    VALID_AUDIENCE_LEVELS,
)
from ppt_generator.interfaces.schemas import OutlineRequest, ProjectMetadata
from ppt_generator.interfaces.utils import format_token_usage
from ppt_generator.tools.outline.service import OutlineService
from ppt_generator.tools.project.service import ProjectService


def register_outline_tools(mcp: FastMCP, outline_service: OutlineService, project_service: ProjectService) -> None:
    @mcp.tool()
    def generate_outline(
        topic: str,
        audience_level: str = DEFAULT_AUDIENCE_LEVEL,
        presentation_minutes: int = DEFAULT_PRESENTATION_MINUTES,
        num_slides: int = 0,
        project_id: str = "",
    ) -> str:
        """주제를 기반으로 슬라이드 아웃라인 JSON을 생성합니다.

        주제의 핵심 내용을 분석하여 슬라이드별 제목, 내용 요약, 컴포넌트 힌트를
        포함한 구조화된 아웃라인을 생성합니다.
        아웃라인은 슬라이드의 구조만 결정하며, 디자인은 이후 HTML 슬라이드 생성 단계에서 결정됩니다.

        **중요: 아웃라인 생성 후 반드시 사용자에게 결과를 보여주고 확인을 받으세요.**
        사용자가 아웃라인 구조(슬라이드 수, 제목, 내용 구성 등)에 만족하는지 확인한 뒤
        다음 단계(generate_script)로 진행해야 합니다.
        사용자가 수정을 요청하면 수정 사항을 반영하여 generate_outline을 다시 호출하세요.

        Args:
            topic: 발표 주제 (예: "2024년 클라우드 컴퓨팅 트렌드")
            audience_level: 청중 수준 — "general" (일반), "technical" (기술), "executive" (의사결정자). 기본값 "general"
            presentation_minutes: 발표 시간(분). 3~60분, 기본값 15분
            num_slides: 권장 슬라이드 수 (0이면 발표 시간 기준 자동 계산: 1~2분당 1장). 한 슬라이드에 하나의 주제만 다루기 위해 실제 생성 수는 달라질 수 있습니다.
            project_id: 프로젝트 ID (미지정 시 자동 생성)

        Returns:
            outline_path, project_id를 포함하는 JSON 문자열
        """
        if audience_level not in VALID_AUDIENCE_LEVELS:
            audience_level = DEFAULT_AUDIENCE_LEVEL
        presentation_minutes = max(MIN_PRESENTATION_MINUTES, min(MAX_PRESENTATION_MINUTES, presentation_minutes))
        if num_slides <= 0:
            num_slides = max(MIN_NUM_SLIDES, min(MAX_NUM_SLIDES, presentation_minutes // 2 + 2))
        else:
            num_slides = max(MIN_NUM_SLIDES, min(MAX_NUM_SLIDES, num_slides))
        request = OutlineRequest(
            topic=topic,
            num_slides=num_slides,
            audience_level=audience_level,
            presentation_minutes=presentation_minutes,
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
                audience_level=audience_level,
                presentation_minutes=presentation_minutes,
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
