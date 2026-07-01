"""Visual QA 서비스 (prepare/ingest).

스크린샷 캡처(Playwright)는 결정론적 브라우저 렌더라 서버에 남는다. 그 스크린샷에
대한 비전 분석과 수정 spec 생성만 클라이언트로 오프로딩한다:

  1. capture_screenshots — 서버 (Playwright)
  2. prepare_analysis / ingest_analysis — 스크린샷+spec 로 이슈 감지 (클라이언트 생성)
  3. prepare_fix / ingest_fix — 이슈를 반영한 수정 spec 생성 (클라이언트 생성)
  4. 저장 + HTML 재렌더 — 서버

iteration 루프(분석→수정→재캡처)는 클라이언트(스킬)가 오케스트레이션한다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path

from ppt_generator.interfaces.constants import (
    VISUAL_QA_ANALYSIS_SYSTEM_PROMPT,
    VISUAL_QA_FIX_SYSTEM_PROMPT,
)
from ppt_generator.interfaces.handoff import build_llm_task
from ppt_generator.interfaces.llm_output_models import (
    ContentSlideSpecOutput,
    SimpleSlideSpecOutput,
    VisualQAOutput,
    _BaseSlideSpecOutput,
)
from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.interfaces.spec_utils import clean_slide_spec
from ppt_generator.interfaces.spec_utils.serializer import slide_spec_to_json
from ppt_generator.tools.visual_qa.screenshot import capture_screenshots

logger = logging.getLogger(__name__)


class VisualQAService:
    """스크린샷 캡처(서버) + 분석/수정 태스크 조립·검증(prepare/ingest)."""

    # ------------------------------------------------------------------
    # Phase 1: 스크린샷 캡처 (서버, Playwright)
    # ------------------------------------------------------------------

    @staticmethod
    def capture_screenshots(
        project_dir: Path,
        indices: list[int],
        iteration: int = 0,
    ) -> dict[int, Path]:
        """Playwright headless Chromium으로 슬라이드 스크린샷을 캡처한다."""
        return capture_screenshots(project_dir, indices, iteration)

    # ------------------------------------------------------------------
    # Phase 2: 스크린샷 분석 (prepare/ingest)
    # ------------------------------------------------------------------

    def prepare_analysis(
        self,
        png_path: Path,
        slide_index: int,
        design_spec: PptxSlideSpec,
    ) -> dict:
        """스크린샷 분석 태스크를 조립한다. images 에 스크린샷 경로를 실어 보낸다.

        Args:
            png_path: 분석할 스크린샷 파일 경로.
            slide_index: 0-based 슬라이드 인덱스.
            design_spec: 해당 슬라이드의 현재 디자인 스펙.
        """
        spec_json = slide_spec_to_json(design_spec)
        prompt = (
            f"다음은 슬라이드 {slide_index + 1}의 스크린샷과 디자인 스펙입니다.\n\n"
            f"<design_spec>\n{spec_json}\n</design_spec>\n\n"
            "위 스크린샷을 분석하여 시각적 이슈를 감지해주세요."
        )
        return build_llm_task(
            system_prompt=VISUAL_QA_ANALYSIS_SYSTEM_PROMPT,
            user_prompt=prompt,
            response_schema=VisualQAOutput.model_json_schema(),
            images=[str(png_path)],
        )

    def ingest_analysis(self, analysis_json: str | dict) -> VisualQAOutput:
        """클라이언트가 생성한 분석 결과 JSON 을 검증한다."""
        if isinstance(analysis_json, str):
            return VisualQAOutput.model_validate_json(analysis_json)
        return VisualQAOutput.model_validate(analysis_json)

    # ------------------------------------------------------------------
    # Phase 3: 디자인 스펙 수정 (prepare/ingest)
    # ------------------------------------------------------------------

    def prepare_fix(
        self,
        png_path: Path,
        current_spec: PptxSlideSpec,
        issues: list[dict],
    ) -> dict:
        """수정 태스크를 조립한다. 현재 spec + 스크린샷 + 이슈 목록을 실어 보낸다."""
        spec_json = slide_spec_to_json(current_spec)
        issues_json = json.dumps(issues, ensure_ascii=False, indent=2)
        prompt = (
            "다음 슬라이드 디자인 스펙에서 시각적 이슈를 수정해주세요.\n\n"
            f"<current_design_spec>\n{spec_json}\n</current_design_spec>\n\n"
            f"<detected_issues>\n{issues_json}\n</detected_issues>\n\n"
            "위 이슈를 수정한 전체 디자인 스펙 JSON을 출력해주세요."
        )
        slide_type = current_spec.slide_type or "content"
        model: type[_BaseSlideSpecOutput] = (
            ContentSlideSpecOutput if slide_type == "content" else SimpleSlideSpecOutput
        )
        return build_llm_task(
            system_prompt=VISUAL_QA_FIX_SYSTEM_PROMPT,
            user_prompt=prompt,
            response_schema=model.model_json_schema(),
            images=[str(png_path)],
        )

    def ingest_fix(
        self,
        fix_json: str | dict,
        current_spec: PptxSlideSpec,
    ) -> PptxSlideSpec | None:
        """클라이언트가 생성한 수정 spec JSON 을 검증·정합화한다.

        기존 fix_design_spec 의 후처리와 동일 — Pydantic 검증 → to_dataclass →
        images/slide_type 복원 → clean_slide_spec. 검증 실패 시 None.
        """
        slide_type = current_spec.slide_type or "content"
        model: type[_BaseSlideSpecOutput] = (
            ContentSlideSpecOutput if slide_type == "content" else SimpleSlideSpecOutput
        )
        try:
            if isinstance(fix_json, str):
                output = model.model_validate_json(fix_json)
            else:
                output = model.model_validate(fix_json)
            spec = output.to_dataclass()
            restore = {}
            if current_spec.images:
                restore["images"] = current_spec.images
            if current_spec.slide_type != "content":
                restore["slide_type"] = current_spec.slide_type
            if restore:
                spec = replace(spec, **restore)
            return clean_slide_spec(spec)
        except Exception:
            logger.exception("디자인 스펙 수정 검증 실패")
            return None
