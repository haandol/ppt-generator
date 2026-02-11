import json
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.constants import DEFAULT_NUM_SLIDES, MAX_NUM_SLIDES, MIN_NUM_SLIDES
from ppt_generator.interfaces.schemas import OutlineRequest, ProjectMetadata
from ppt_generator.tools.outline.service import OutlineService
from ppt_generator.tools.project.service import ProjectService


def register_outline_tools(mcp: FastMCP, outline_service: OutlineService, project_service: ProjectService) -> None:
    @mcp.tool()
    def generate_outline(
        topic: str, num_slides: int = DEFAULT_NUM_SLIDES, project_id: str = ""
    ) -> str:
        """주제를 기반으로 슬라이드 아웃라인 JSON을 생성합니다.

        주제의 핵심 내용을 분석하여 슬라이드별 제목, 본문 요점, 이미지 아이디어,
        레이아웃 타입을 포함한 구조화된 아웃라인을 생성합니다.
        요소별 좌표 기반 자유 배치(freeform) 레이아웃으로 생성되어
        PPTX 변환 시 최대한의 디자인 자유도를 보장합니다.
        speaker_notes는 빈 문자열로 생성되며, 이후 generate_script에서 채워집니다.

        Args:
            topic: 발표 주제 (예: "2024년 클라우드 컴퓨팅 트렌드")
            num_slides: 슬라이드 수 (3~20, 기본값 5)
            project_id: 프로젝트 ID (미지정 시 자동 생성)

        Returns:
            슬라이드 아웃라인 JSON 문자열 (project_id 포함)
        """
        num_slides = max(MIN_NUM_SLIDES, min(MAX_NUM_SLIDES, num_slides))
        request = OutlineRequest(topic=topic, num_slides=num_slides)
        response = outline_service.generate(request)
        result = json.dumps(asdict(response), ensure_ascii=False, indent=2)

        project_id, project_dir = project_service.resolve_project_dir(project_id)
        project_service.save_metadata(
            project_dir,
            ProjectMetadata(topic=topic, num_slides=num_slides, steps_completed={}),
        )
        project_service.save_outline(project_dir, result)
        project_service.update_step(project_dir, "outline")

        return json.dumps(
            {**json.loads(result), "project_id": project_id},
            ensure_ascii=False,
            indent=2,
        )
