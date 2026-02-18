import json

from mcp.server.fastmcp import FastMCP

from ppt_generator.tools.project.service import ProjectService


def register_project_tools(mcp: FastMCP, project_service: ProjectService) -> None:
    @mcp.tool()
    def list_projects() -> str:
        """기존 프로젝트 목록을 조회합니다.

        ~/.ppt-generator/ 디렉토리를 확인하여 저장된 프로젝트 목록을 반환합니다.
        각 프로젝트의 ID, 주제, 슬라이드 수, 완료 단계, 생성 시간을 포함합니다.
        최신 프로젝트가 먼저 표시됩니다.

        **사용 시점**: PPT 생성 파이프라인을 시작하기 전에 반드시 이 도구를 먼저 호출하세요.
        - 프로젝트가 없으면: 새 프로젝트를 시작합니다 (generate_outline 호출).
        - 프로젝트가 있으면: 사용자에게 기존 프로젝트를 이어서 작업할지,
          새 프로젝트를 시작할지 선택하도록 안내합니다.

        Returns:
            프로젝트 목록 JSON 문자열. 프로젝트가 없으면 빈 배열 [].
        """
        projects = project_service.list_projects()
        return json.dumps(
            {"total": len(projects), "projects": projects},
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    def load_project_status(project_id: str) -> str:
        """프로젝트 상태 및 메타데이터를 로드합니다.

        저장된 프로젝트의 주제, 슬라이드 수, 각 단계 완료 상태를 확인합니다.

        Args:
            project_id: 프로젝트 ID

        Returns:
            프로젝트 메타데이터 JSON 문자열
        """
        _, project_dir = project_service.resolve_project_dir(project_id)
        metadata = project_service.load_metadata(project_dir)
        return json.dumps(
            {
                "topic": metadata.topic,
                "num_slides": metadata.num_slides,
                "steps_completed": metadata.steps_completed,
                "audience_level": metadata.audience_level,
                "presentation_minutes": metadata.presentation_minutes,
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    def load_outline(project_id: str) -> str:
        """저장된 아웃라인 JSON을 로드합니다.

        프로젝트 디렉토리에서 이전에 생성된 슬라이드 아웃라인을 불러옵니다.
        불러온 결과를 generate_script, generate_slides의 입력으로
        바로 사용할 수 있습니다.

        Args:
            project_id: 프로젝트 ID

        Returns:
            outline_path를 포함하는 JSON 문자열
        """
        _, project_dir = project_service.resolve_project_dir(project_id)
        # 파일 존재 확인 (없으면 예외 발생)
        project_service.load_outline(project_dir)
        return json.dumps(
            {"outline_path": str(project_dir / "outline.json")},
            ensure_ascii=False,
        )

    @mcp.tool()
    def load_script(project_id: str) -> str:
        """저장된 스크립트 JSON을 로드합니다.

        프로젝트 디렉토리에서 이전에 생성된 스크립트(speaker_notes 포함 아웃라인)를
        불러옵니다. 불러온 결과를 generate_slides의 입력으로
        바로 사용할 수 있습니다.

        Args:
            project_id: 프로젝트 ID

        Returns:
            script_path를 포함하는 JSON 문자열
        """
        _, project_dir = project_service.resolve_project_dir(project_id)
        # 파일 존재 확인 (없으면 예외 발생)
        project_service.load_script(project_dir)
        return json.dumps(
            {"script_path": str(project_dir / "script.json")},
            ensure_ascii=False,
        )

    @mcp.tool()
    def load_design_spec(project_id: str) -> str:
        """저장된 디자인 스펙을 로드합니다.

        프로젝트 디렉토리에서 이전에 생성된 디자인 스펙(PptxSlideSpec JSON)을
        불러옵니다. project_id를 generate_slides(project_id=...)이나
        export_pptx(project_id=...)에 전달하여 사용할 수 있습니다.

        Args:
            project_id: 프로젝트 ID

        Returns:
            design_spec_dir, slide_count, slide_files를 포함하는 JSON 문자열
        """
        _, project_dir = project_service.resolve_project_dir(project_id)
        # 존재 확인 (없으면 예외 발생)
        design_spec = project_service.load_design_spec(project_dir)
        spec_dir = project_dir / "design_spec"
        slide_files = sorted(str(f.name) for f in spec_dir.glob("slide_*.json"))
        return json.dumps(
            {
                "design_spec_dir": str(spec_dir),
                "slide_count": len(design_spec.slides),
                "slide_files": slide_files,
            },
            ensure_ascii=False,
        )
