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
    async def generate_slides_design_spec(
        project_id: str = "",
        outline_json: str = "",
        total_slides: int = 0,
        color_theme: str = "dark",
        slide_indices: str = "",
        ctx: Context | None = None,
    ) -> str:
        """슬라이드 디자인 스펙을 생성합니다 (전체 또는 선택적, 서버 내부 병렬 처리).

        전체 슬라이드를 일괄 생성하거나, slide_indices로 특정 슬라이드만 선택적으로 생성할 수 있습니다.
        **병렬 처리는 서버 내부에서 자동으로 수행**되므로, 이 도구를 여러 번 병렬 호출할 필요가 없습니다.
        환경변수 DESIGN_SPEC_PARALLEL(기본 4)로 동시 생성 수를 제어합니다.

        **처리 순서:**
        1. slide_indices에 인덱스 0이 포함되고 design_summary가 없으면,
           slide[0]을 먼저 생성하여 design_summary(디자인 테마)를 추출합니다.
        2. 나머지 슬라이드를 병렬로 생성합니다 (각 슬라이드의 HTML 미리보기도 자동 생성).
        3. 일부 슬라이드가 실패해도 나머지는 정상 저장됩니다.
           실패한 슬라이드는 이 도구에 해당 slide_indices만 지정하여 재시도할 수 있습니다.

        **개별 슬라이드 수정은 `modify_design_spec`의 update action을 사용하세요.**

        **사전 조건: 아웃라인 생성 후 사용자에게 아웃라인 수정 사항이 없는지 반드시 확인을 받은 뒤 호출하세요.**

        Args:
            project_id: 프로젝트 ID. 지정하면 저장된 script.json(없으면 outline.json)에서 자동 로드합니다.
            outline_json: 전체 아웃라인 JSON ({"slides": [...]}) - 모든 슬라이드 포함. project_id를 지정하면 생략 가능합니다.
            total_slides: 전체 슬라이드 수. 0이면 로드된 아웃라인에서 자동 계산됩니다.
            color_theme: 색상 테마 ("dark" 또는 "light", 기본값: "dark")
            slide_indices: 생성할 슬라이드 인덱스 (0-based, 콤마 구분). 예: "0,2,4". 빈 문자열이면 전체 생성.

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

        # slide_indices 미지정 시에만 total_slides 불일치 검증
        if not slide_indices and len(outline.slides) != total_slides:
            raise ValueError(
                f"outline의 slides 수({len(outline.slides)})와 "
                f"total_slides({total_slides})가 일치하지 않습니다."
            )

        # slide_indices 파싱
        if slide_indices:
            indices = sorted(set(int(x.strip()) for x in slide_indices.split(",")))
            for idx in indices:
                if idx < 0 or idx >= len(outline.slides):
                    raise ValueError(f"유효하지 않은 slide_index: {idx}")
        else:
            indices = list(range(total_slides))

        project_id, project_dir = project_service.resolve_project_dir(project_id)
        target_count = len(indices)
        results: list[dict] = []
        results_map: dict[int, dict] = {}
        success_count = 0
        error_count = 0

        async def _report(progress: int, message: str) -> None:
            if ctx is not None:
                await ctx.report_progress(progress, target_count, message)

        # design_summary 존재 여부 확인
        existing_summary = project_service.load_design_summary(project_dir)
        needs_summary_generation = 0 in indices and existing_summary is None

        # --- Phase 1: slide[0] 순차 생성 (design_summary 추출이 필요한 경우) ---
        if needs_summary_generation:
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
                results_map[0] = r0
                success_count += 1
                logger.info("slide[0] 생성 완료 (design_summary 추출됨)")
                await _report(success_count + error_count, f"슬라이드 1/{total_slides} 완료 (디자인 테마 추출)")
            except Exception as e:
                logger.error("slide[0] 생성 실패: %s", e)
                results_map[0] = {"slide_index": 0, "status": "error", "error": str(e)}
                error_count += 1
                await _report(success_count + error_count, f"슬라이드 1/{total_slides} 실패")

        # --- Phase 2: 나머지 슬라이드 병렬 생성 ---
        parallel_indices = [i for i in indices if i not in results_map]

        if parallel_indices:
            design_summary_for_batch = project_service.load_design_summary(project_dir)
            max_workers = min(DESIGN_SPEC_PARALLEL, len(parallel_indices))

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
                    for i in parallel_indices
                }
                for coro in asyncio.as_completed(future_to_idx):
                    res = await coro
                    idx = res["slide_index"]
                    results_map[idx] = res
                    if res["status"] == "success":
                        success_count += 1
                    else:
                        error_count += 1
                    await _report(
                        success_count + error_count,
                        f"슬라이드 {idx + 1}/{total_slides} "
                        f"{'완료' if res['status'] == 'success' else '실패'}",
                    )

        # 결과를 인덱스 순서로 정렬
        results = [results_map[i] for i in sorted(results_map)]

        project_service.update_step(project_dir, "design_spec")
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
