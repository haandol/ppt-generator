import json

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.utils import parse_outline_json
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.project.service import ProjectService


def register_design_tools(
    mcp: FastMCP,
    design_service: DesignService,
    project_service: ProjectService,
) -> None:
    @mcp.tool()
    def generate_slide_design_spec(
        outline_json: str,
        slide_index: int,
        total_slides: int,
        project_id: str = "",
        color_theme: str = "dark",
    ) -> str:
        """단일 슬라이드의 디자인 스펙을 생성합니다.

        슬라이드를 하나씩 생성하고 검토/수정한 뒤 다음 슬라이드로 진행할 수 있습니다.
        첫 슬라이드(slide_index=0) 생성 시 디자인 테마를 추출하여 저장하고,
        이후 슬라이드에서 자동으로 로드하여 시각적 일관성을 유지합니다.

        **사전 조건: 아웃라인 생성 후 사용자에게 아웃라인 수정 사항이 없는지 반드시 확인을 받은 뒤 호출하세요.**
        아웃라인의 슬라이드 수, 제목, 내용 구성 등에 수정이 필요한지 사용자에게 물어보고,
        수정이 필요하면 generate_outline을 다시 호출하여 반영한 후 진행하세요.

        Args:
            outline_json: 단일 슬라이드 아웃라인 JSON (title, content_summary, component_hint, speaker_notes)
            slide_index: 생성할 슬라이드 인덱스 (0-based)
            total_slides: 전체 슬라이드 수
            project_id: 프로젝트 ID (미지정 시 자동 생성)
            color_theme: 색상 테마 ("dark" 또는 "light", 기본값: "dark")

        Returns:
            design_spec_dir, slide_file, slide_index, slide_count, total_slides, project_id를 포함하는 JSON 문자열
        """
        outline = parse_outline_json(outline_json)
        slide_outline = outline.slides[0]

        project_id, project_dir = project_service.resolve_project_dir(project_id)

        # 디자인 요약 결정
        design_summary: dict | None = None
        if slide_index > 0:
            design_summary = project_service.load_design_summary(project_dir)

        # 슬라이드 생성 (1-based index를 프롬프트에 전달)
        spec = design_service.generate_single_slide(
            slide_outline,
            design_summary=design_summary,
            slide_index=slide_index + 1,
            total_slides=total_slides,
            color_theme=color_theme,
        )

        # 저장
        project_service.create_design_spec_slide(project_dir, slide_index, spec)

        # 첫 슬라이드인 경우 디자인 요약 추출 및 저장
        if slide_index == 0:
            summary = design_service.extract_design_summary(spec)
            project_service.save_design_summary(project_dir, summary)

        project_service.update_step(project_dir, "design_spec")
        slide_count = project_service.get_design_spec_slide_count(project_dir)
        slide_file = f"slide_{slide_index + 1:02d}.json"

        return json.dumps(
            {
                "design_spec_dir": str(project_dir / "design_spec"),
                "slide_file": slide_file,
                "slide_index": slide_index,
                "slide_count": slide_count,
                "total_slides": total_slides,
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
        color_theme: str = "dark",
    ) -> str:
        """디자인 스펙의 개별 슬라이드를 추가, 수정, 삭제합니다.

        기존 프로젝트의 디자인 스펙에서 슬라이드 단위 CRUD를 수행합니다.
        add/update 시 첫 슬라이드의 디자인을 기반으로 일관된 스타일을 유지합니다.

        Args:
            project_id: 대상 프로젝트 ID (필수)
            action: 수행할 작업 ("add" | "update" | "delete")
            slide_index: add일 때 삽입 위치(-1이면 끝), update/delete일 때 대상 인덱스
            outline_json: add/update 시 슬라이드 아웃라인 JSON (title, content_summary, component_hint)
            color_theme: 색상 테마 ("dark" 또는 "light", 기본값: "dark")

        Returns:
            design_spec_path, project_id, slide_count를 포함하는 JSON 문자열
        """
        if action not in ("add", "update", "delete"):
            raise ValueError(f"action은 'add', 'update', 'delete' 중 하나여야 합니다: {action}")

        _, project_dir = project_service.resolve_project_dir(project_id)
        slide_count = project_service.get_design_spec_slide_count(project_dir)

        # 디자인 요약 추출 (add/update 시 일관성 유지)
        design_summary: dict | None = None
        if action in ("add", "update") and slide_count > 0:
            first_slide = project_service.load_design_spec_slide(project_dir, 0)
            design_summary = design_service.extract_design_summary(first_slide)

        if action == "add":
            if not outline_json:
                raise ValueError("add 시 outline_json이 필수입니다.")
            outline = parse_outline_json(outline_json)
            slide_outline = outline.slides[0]
            new_spec = design_service.generate_single_slide(
                slide_outline, design_summary, color_theme=color_theme,
            )
            insert_idx = slide_index if 0 <= slide_index < slide_count else slide_count
            project_service.insert_design_spec_slide(project_dir, insert_idx, new_spec)

        elif action == "update":
            if not outline_json:
                raise ValueError("update 시 outline_json이 필수입니다.")
            if slide_index < 0 or slide_index >= slide_count:
                raise ValueError(f"유효하지 않은 slide_index: {slide_index} (전체 {slide_count}장)")
            outline = parse_outline_json(outline_json)
            slide_outline = outline.slides[0]
            new_spec = design_service.generate_single_slide(
                slide_outline, design_summary, color_theme=color_theme,
            )
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
