import json

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.schemas import DesignSpecRequest
from ppt_generator.interfaces.utils import parse_outline_json
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.project.service import ProjectService


def register_design_tools(
    mcp: FastMCP,
    design_service: DesignService,
    project_service: ProjectService,
) -> None:
    @mcp.tool()
    def generate_design_spec(outline_json: str, project_id: str = "") -> str:
        """아웃라인을 기반으로 디자인 스펙(PptxSlideSpec JSON)을 생성합니다.

        슬라이드 아웃라인 JSON을 받아 각 슬라이드의 정밀한 시각적 레이아웃을
        PptxSlideSpec 형식으로 생성합니다. 생성된 디자인 스펙은
        generate_slides(design_spec_json=...)이나 export_pptx(design_spec_json=...)의
        입력으로 사용할 수 있습니다.

        Args:
            outline_json: generate_script로 생성된 슬라이드 아웃라인 JSON 문자열
            project_id: 프로젝트 ID (미지정 시 자동 생성)

        Returns:
            design_spec_path, project_id를 포함하는 JSON 문자열
        """
        outline = parse_outline_json(outline_json)
        request = DesignSpecRequest(slides=outline.slides)
        response = design_service.generate(request)

        project_id, project_dir = project_service.resolve_project_dir(project_id)
        project_service.save_design_spec(project_dir, response.design_spec)
        project_service.update_step(project_dir, "design_spec")

        return json.dumps(
            {
                "design_spec_dir": str(project_dir / "design_spec"),
                "slide_count": len(response.design_spec.slides),
                "project_id": project_id,
            },
            ensure_ascii=False,
        )

    @mcp.tool()
    def modify_design_spec(
        project_id: str,
        action: str,
        slide_index: int = -1,
        outline_json: str = "",
    ) -> str:
        """디자인 스펙의 개별 슬라이드를 추가, 수정, 삭제합니다.

        기존 프로젝트의 디자인 스펙에서 슬라이드 단위 CRUD를 수행합니다.
        add/update 시 첫 슬라이드의 디자인을 기반으로 일관된 스타일을 유지합니다.

        Args:
            project_id: 대상 프로젝트 ID (필수)
            action: 수행할 작업 ("add" | "update" | "delete")
            slide_index: add일 때 삽입 위치(-1이면 끝), update/delete일 때 대상 인덱스
            outline_json: add/update 시 슬라이드 아웃라인 JSON (title, content_summary, component_hint)

        Returns:
            design_spec_path, project_id, slide_count를 포함하는 JSON 문자열
        """
        if action not in ("add", "update", "delete"):
            raise ValueError(f"action은 'add', 'update', 'delete' 중 하나여야 합니다: {action}")

        _, project_dir = project_service.resolve_project_dir(project_id)
        slide_count = project_service.get_design_spec_slide_count(project_dir)

        # 디자인 요약 추출 (add/update 시 일관성 유지)
        design_summary = ""
        if action in ("add", "update") and slide_count > 0:
            first_slide = project_service.load_design_spec_slide(project_dir, 0)
            design_summary = design_service._extract_design_summary(first_slide)

        if action == "add":
            if not outline_json:
                raise ValueError("add 시 outline_json이 필수입니다.")
            outline = parse_outline_json(outline_json)
            slide_outline = outline.slides[0]
            new_spec = design_service.generate_single_slide(slide_outline, design_summary)
            insert_idx = slide_index if 0 <= slide_index < slide_count else slide_count
            project_service.insert_design_spec_slide(project_dir, insert_idx, new_spec)

        elif action == "update":
            if not outline_json:
                raise ValueError("update 시 outline_json이 필수입니다.")
            if slide_index < 0 or slide_index >= slide_count:
                raise ValueError(f"유효하지 않은 slide_index: {slide_index} (전체 {slide_count}장)")
            outline = parse_outline_json(outline_json)
            slide_outline = outline.slides[0]
            new_spec = design_service.generate_single_slide(slide_outline, design_summary)
            project_service.save_design_spec_slide(project_dir, slide_index, new_spec)

        elif action == "delete":
            if slide_index < 0 or slide_index >= slide_count:
                raise ValueError(f"유효하지 않은 slide_index: {slide_index} (전체 {slide_count}장)")
            project_service.delete_design_spec_slide(project_dir, slide_index)

        project_service.update_step(project_dir, "design_spec_modified")
        new_count = project_service.get_design_spec_slide_count(project_dir)

        return json.dumps(
            {
                "design_spec_dir": str(project_dir / "design_spec"),
                "project_id": project_id,
                "slide_count": new_count,
            },
            ensure_ascii=False,
        )
