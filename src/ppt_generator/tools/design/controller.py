import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from mcp.server.fastmcp import Context, FastMCP

from ppt_generator.interfaces.constants import DESIGN_SPEC_PARALLEL
from ppt_generator.interfaces.utils import parse_outline_json
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.slides.service import SlidesService

logger = logging.getLogger(__name__)


def register_design_tools(
    mcp: FastMCP,
    design_service: DesignService,
    project_service: ProjectService,
    slides_service: SlidesService | None = None,
    design_service_factory: Callable[[], DesignService] | None = None,
) -> None:
    @mcp.tool()
    def generate_slide_design_spec(
        slide_index: int,
        project_id: str = "",
        outline_json: str = "",
        total_slides: int = 0,
        color_theme: str = "dark",
    ) -> str:
        """단일 슬라이드의 디자인 스펙을 생성합니다.

        슬라이드를 하나씩 생성하고 검토/수정한 뒤 다음 슬라이드로 진행할 수 있습니다.
        첫 슬라이드(slide_index=0) 생성 시 디자인 테마를 추출하여 저장하고,
        이후 슬라이드에서 자동으로 로드하여 시각적 일관성을 유지합니다.

        여러 슬라이드를 한 번에 생성하려면 `generate_slides_design_spec`을 사용하세요.

        **사전 조건: 아웃라인 생성 후 사용자에게 아웃라인 수정 사항이 없는지 반드시 확인을 받은 뒤 호출하세요.**
        아웃라인의 슬라이드 수, 제목, 내용 구성 등에 수정이 필요한지 사용자에게 물어보고,
        수정이 필요하면 generate_outline을 다시 호출하여 반영한 후 진행하세요.

        Args:
            slide_index: 생성할 슬라이드 인덱스 (0-based)
            project_id: 프로젝트 ID. 지정하면 저장된 script.json(없으면 outline.json)에서 자동 로드합니다.
            outline_json: 단일 슬라이드 아웃라인 JSON. project_id를 지정하면 생략 가능합니다.
            total_slides: 전체 슬라이드 수. 0이면 로드된 아웃라인에서 자동 계산됩니다.
            color_theme: 색상 테마 ("dark" 또는 "light", 기본값: "dark")

        Returns:
            design_spec_dir, slide_file, slide_index, slide_count, total_slides, project_id를 포함하는 JSON 문자열
        """
        if outline_json:
            outline = parse_outline_json(outline_json)
            slide_outline = outline.slides[0]
        elif project_id:
            _, proj_dir = project_service.resolve_project_dir(project_id)
            raw = project_service.load_script_or_outline(proj_dir)
            outline = parse_outline_json(raw)
            slide_outline = outline.slides[slide_index]
        else:
            raise ValueError("outline_json 또는 project_id 중 하나를 제공해야 합니다.")

        if total_slides == 0:
            total_slides = len(outline.slides)

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

        # 디자인 스펙 생성 직후 해당 슬라이드 HTML도 바로 생성·저장
        slide_html_path: str | None = None
        if slides_service is not None:
            slide_html = slides_service.render_single_slide_html(slide_index, spec)
            html_path = project_service.save_single_slide_html(
                project_dir, slide_index, slide_html,
            )
            slide_html_path = str(html_path)

        result: dict = {
            "design_spec_dir": str(project_dir / "design_spec"),
            "slide_file": slide_file,
            "slide_index": slide_index,
            "slide_count": slide_count,
            "total_slides": total_slides,
            "project_id": project_id,
        }
        if slide_html_path:
            result["slide_html_path"] = slide_html_path

        return json.dumps(result, ensure_ascii=False)

    @mcp.tool()
    async def generate_slides_design_spec(
        project_id: str = "",
        outline_json: str = "",
        total_slides: int = 0,
        color_theme: str = "dark",
        ctx: Context | None = None,
    ) -> str:
        """전체 슬라이드의 디자인 스펙을 일괄 생성합니다 (서버 내부 병렬 처리).

        아웃라인의 모든 슬라이드를 한 번에 받아, 첫 슬라이드로 디자인 테마를 추출한 뒤
        나머지 슬라이드를 서버 내부에서 병렬로 생성합니다.
        환경변수 DESIGN_SPEC_PARALLEL(기본 4)로 동시 생성 수를 제어합니다.

        **처리 순서:**
        1. slide[0]을 먼저 생성하여 design_summary(디자인 테마)를 추출합니다.
        2. slide[1..N-1]을 병렬로 생성합니다 (각 슬라이드의 HTML 미리보기도 자동 생성).
        3. 일부 슬라이드가 실패해도 나머지는 정상 저장됩니다.
           실패한 슬라이드는 generate_slide_design_spec(단수)으로 개별 재시도할 수 있습니다.

        **사전 조건: 아웃라인 생성 후 사용자에게 아웃라인 수정 사항이 없는지 반드시 확인을 받은 뒤 호출하세요.**

        Args:
            project_id: 프로젝트 ID. 지정하면 저장된 script.json(없으면 outline.json)에서 자동 로드합니다.
            outline_json: 전체 아웃라인 JSON ({"slides": [...]}) - 모든 슬라이드 포함. project_id를 지정하면 생략 가능합니다.
            total_slides: 전체 슬라이드 수. 0이면 로드된 아웃라인에서 자동 계산됩니다.
            color_theme: 색상 테마 ("dark" 또는 "light", 기본값: "dark")

        Returns:
            design_spec_dir, slide_count, total_slides, project_id, success_count, error_count, results를 포함하는 JSON 문자열
        """
        if outline_json:
            outline = parse_outline_json(outline_json)
        elif project_id:
            _, proj_dir = project_service.resolve_project_dir(project_id)
            raw = project_service.load_script_or_outline(proj_dir)
            outline = parse_outline_json(raw)
        else:
            raise ValueError("outline_json 또는 project_id 중 하나를 제공해야 합니다.")

        if total_slides == 0:
            total_slides = len(outline.slides)

        if len(outline.slides) != total_slides:
            raise ValueError(
                f"outline의 slides 수({len(outline.slides)})와 "
                f"total_slides({total_slides})가 일치하지 않습니다."
            )

        project_id, project_dir = project_service.resolve_project_dir(project_id)
        results: list[dict] = [{}] * total_slides
        success_count = 0
        error_count = 0

        async def _report(progress: int, message: str) -> None:
            if ctx is not None:
                await ctx.report_progress(progress, total_slides, message)

        # --- Phase 1: slide[0] 순차 생성 ---
        slide0_outline = outline.slides[0]
        try:
            spec0 = design_service.generate_single_slide(
                slide0_outline,
                design_summary=None,
                slide_index=1,
                total_slides=total_slides,
                color_theme=color_theme,
            )
            project_service.create_design_spec_slide(project_dir, 0, spec0)
            summary = design_service.extract_design_summary(spec0)
            project_service.save_design_summary(project_dir, summary)
            project_service.update_step(project_dir, "design_spec")

            slide_html_path: str | None = None
            if slides_service is not None:
                slide_html = slides_service.render_single_slide_html(0, spec0)
                html_path = project_service.save_single_slide_html(project_dir, 0, slide_html)
                slide_html_path = str(html_path)

            r0: dict = {"slide_index": 0, "status": "success", "slide_file": "slide_01.json"}
            if slide_html_path:
                r0["slide_html_path"] = slide_html_path
            results[0] = r0
            success_count += 1
            logger.info("slide[0] 생성 완료 (design_summary 추출됨)")
            await _report(1, f"슬라이드 1/{total_slides} 완료 (디자인 테마 추출)")
        except Exception as e:
            logger.error("slide[0] 생성 실패: %s", e)
            results[0] = {"slide_index": 0, "status": "error", "error": str(e)}
            error_count += 1
            await _report(1, f"슬라이드 1/{total_slides} 실패")

        # --- Phase 2: slide[1..N-1] 병렬 생성 ---
        if total_slides > 1:
            design_summary_for_batch = (
                project_service.load_design_summary(project_dir)
                if error_count == 0
                else None
            )
            max_workers = min(DESIGN_SPEC_PARALLEL, total_slides - 1)

            def _generate_slide(idx: int) -> dict:
                """worker 함수: 개별 슬라이드 생성."""
                svc = design_service_factory() if design_service_factory else design_service
                try:
                    spec = svc.generate_single_slide(
                        outline.slides[idx],
                        design_summary=design_summary_for_batch,
                        slide_index=idx + 1,
                        total_slides=total_slides,
                        color_theme=color_theme,
                    )
                    project_service.create_design_spec_slide(project_dir, idx, spec)
                    project_service.update_step(project_dir, "design_spec")

                    html_path_str: str | None = None
                    if slides_service is not None:
                        html = slides_service.render_single_slide_html(idx, spec)
                        hp = project_service.save_single_slide_html(project_dir, idx, html)
                        html_path_str = str(hp)

                    r: dict = {
                        "slide_index": idx,
                        "status": "success",
                        "slide_file": f"slide_{idx + 1:02d}.json",
                    }
                    if html_path_str:
                        r["slide_html_path"] = html_path_str
                    return r
                except Exception as exc:
                    logger.error("slide[%d] 생성 실패: %s", idx, exc)
                    return {"slide_index": idx, "status": "error", "error": str(exc)}

            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_idx = {
                    loop.run_in_executor(executor, _generate_slide, i): i
                    for i in range(1, total_slides)
                }
                for coro in asyncio.as_completed(future_to_idx):
                    res = await coro
                    idx = res["slide_index"]
                    results[idx] = res
                    if res["status"] == "success":
                        success_count += 1
                    else:
                        error_count += 1
                    await _report(
                        success_count + error_count,
                        f"슬라이드 {idx + 1}/{total_slides} "
                        f"{'완료' if res['status'] == 'success' else '실패'}",
                    )

        slide_count = project_service.get_design_spec_slide_count(project_dir)

        return json.dumps(
            {
                "design_spec_dir": str(project_dir / "design_spec"),
                "slide_count": slide_count,
                "total_slides": total_slides,
                "project_id": project_id,
                "success_count": success_count,
                "error_count": error_count,
                "results": results,
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

        slide_html_path: str | None = None

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
            if slides_service is not None:
                html = slides_service.render_single_slide_html(insert_idx, new_spec)
                html_path = project_service.save_single_slide_html(
                    project_dir, insert_idx, html,
                )
                slide_html_path = str(html_path)

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
            if slides_service is not None:
                html = slides_service.render_single_slide_html(slide_index, new_spec)
                html_path = project_service.save_single_slide_html(
                    project_dir, slide_index, html,
                )
                slide_html_path = str(html_path)

        elif action == "delete":
            if slide_index < 0 or slide_index >= slide_count:
                raise ValueError(f"유효하지 않은 slide_index: {slide_index} (전체 {slide_count}장)")
            project_service.delete_design_spec_slide(project_dir, slide_index)

        project_service.update_step(project_dir, "design_spec_modified")
        new_count = project_service.get_design_spec_slide_count(project_dir)

        result = {
            "design_spec_dir": str(project_dir / "design_spec"),
            "project_id": project_id,
            "slide_count": new_count,
        }
        if slide_html_path:
            result["slide_html_path"] = slide_html_path

        return json.dumps(result, ensure_ascii=False)
