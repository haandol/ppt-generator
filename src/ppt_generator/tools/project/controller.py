import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ppt_generator.tools.project.service import ProjectService


def register_project_tools(mcp: FastMCP, project_service: ProjectService) -> None:
    @mcp.tool()
    def load_project_status(project_dir: str) -> str:
        """프로젝트 상태 및 메타데이터를 로드합니다.

        저장된 프로젝트의 주제, 슬라이드 수, 각 단계 완료 상태를 확인합니다.

        Args:
            project_dir: 프로젝트 디렉토리 경로

        Returns:
            프로젝트 메타데이터 JSON 문자열
        """
        metadata = project_service.load_metadata(Path(project_dir))
        return json.dumps(
            {
                "topic": metadata.topic,
                "num_slides": metadata.num_slides,
                "steps_completed": metadata.steps_completed,
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    def load_outline(project_dir: str) -> str:
        """저장된 아웃라인 JSON을 로드합니다.

        프로젝트 디렉토리에서 이전에 생성된 슬라이드 아웃라인을 불러옵니다.
        불러온 결과를 generate_script, generate_images, generate_slides의 입력으로
        바로 사용할 수 있습니다.

        Args:
            project_dir: 프로젝트 디렉토리 경로

        Returns:
            슬라이드 아웃라인 JSON 문자열
        """
        return project_service.load_outline(Path(project_dir))

    @mcp.tool()
    def load_script(project_dir: str) -> str:
        """저장된 스크립트 JSON을 로드합니다.

        프로젝트 디렉토리에서 이전에 생성된 스크립트(speaker_notes 포함 아웃라인)를
        불러옵니다. 불러온 결과를 generate_images, generate_slides의 입력으로
        바로 사용할 수 있습니다.

        Args:
            project_dir: 프로젝트 디렉토리 경로

        Returns:
            speaker_notes가 채워진 슬라이드 아웃라인 JSON 문자열
        """
        return project_service.load_script(Path(project_dir))

    @mcp.tool()
    def load_images(project_dir: str) -> str:
        """저장된 이미지 메타 JSON을 로드합니다.

        프로젝트 디렉토리에서 이전에 생성된 이미지 경로 정보를 불러옵니다.
        불러온 결과를 generate_slides의 images_json 입력으로 바로 사용할 수 있습니다.

        Args:
            project_dir: 프로젝트 디렉토리 경로

        Returns:
            이미지 경로 목록 JSON 문자열
        """
        return project_service.load_images(Path(project_dir))

    @mcp.tool()
    def load_slides_html(project_dir: str) -> str:
        """저장된 HTML 슬라이드를 로드하고 세션을 복원합니다.

        프로젝트 디렉토리에서 이전에 생성된 HTML 슬라이드를 불러오고,
        SlidesService의 인메모리 세션을 복원합니다.
        반환된 session_id를 modify_slides나 export_pptx에 바로 사용할 수 있습니다.

        Args:
            project_dir: 프로젝트 디렉토리 경로

        Returns:
            session_id와 html을 포함하는 JSON 문자열
        """
        session_id, html = project_service.load_slides_html(Path(project_dir))
        return json.dumps(
            {"session_id": session_id, "html": html},
            ensure_ascii=False,
        )
