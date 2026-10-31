"""Design spec generation service.

LLM 호출을 클라이언트로 오프로딩했다. 이 서비스는 각 생성 단계를 prepare/ingest
두 단계로 나눈다:

- ``prepare_*``: 클라이언트가 생성하는 데 필요한 system/user 프롬프트와 출력 스키마를
  조립해 반환한다 (LLM 호출 없음).
- ``ingest_*``: 클라이언트가 스키마대로 생성해 돌려준 JSON 을 Pydantic 으로 검증하고,
  dataclass 변환·정합화(clean_slide_spec)·트리 재구성 등 후처리를 수행한다.

프롬프트·출력 스키마·후처리 로직은 서버가 그대로 소유하므로 산출물이 불변이다.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, replace

from ppt_generator.interfaces.constants import (
    BACKFILL_DESIGN_DOC_SYSTEM_PROMPT,
    BACKFILL_DESIGN_DOC_USER_PROMPT_TEMPLATE,
    COMPONENT_MODIFY_SYSTEM_PROMPT,
    COMPONENT_MODIFY_USER_PROMPT_TEMPLATE,
    DESIGN_DOC_DRAFT_USER_PROMPT_TEMPLATE,
    DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE,
    DESIGN_SPEC_USER_PROMPT_TEMPLATE,
)
from ppt_generator.interfaces.handoff import build_llm_task, validate_llm_output
from ppt_generator.interfaces.layout_derivation import (
    derive_spec_layout_bboxes,
)
from ppt_generator.interfaces.output_models.design_doc import DesignDocDraftOutput
from ppt_generator.interfaces.output_models.elements import (
    shape_output_to_dataclass,
    textbox_output_to_dataclass,
)
from ppt_generator.interfaces.output_models.modification import (
    BackfillDesignDocOutput,
    ComponentModifyOutput,
)
from ppt_generator.interfaces.output_models.slides import slide_spec_output_model
from ppt_generator.interfaces.prompts import (
    DESIGN_DOC_DRAFT_SYSTEM_PROMPT,
    get_design_spec_system_prompt,
)
from ppt_generator.interfaces.schemas import (
    OutlineResponse,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    SlideOutline,
)
from ppt_generator.interfaces.spec_utils import clean_slide_spec
from ppt_generator.interfaces.spec_utils.serializer import slide_spec_to_json
from ppt_generator.tools.design.backfill import (
    _apply_backfill_output,
    _serialize_elements_for_backfill,
)
from ppt_generator.tools.design.backfill import (
    _is_decorative as _is_decorative,
)
from ppt_generator.tools.design.components import (
    _find_element_by_component_id,
    _find_layout_leaf_by_id,
)
from ppt_generator.tools.design.components import (
    _replace_node_bbox as _replace_node_bbox,
)
from ppt_generator.tools.design.summary import (
    extract_design_summary as summarize_design,
)

logger = logging.getLogger(__name__)


class DesignService:
    """슬라이드 아웃라인으로부터 PptxSlideSpec 을 생성하기 위한 prepare/ingest 서비스."""

    # ------------------------------------------------------------------
    # 단일 슬라이드 design spec: prepare / ingest
    # ------------------------------------------------------------------

    def prepare_slide(
        self,
        slide_outline: SlideOutline,
        design_summary: dict | None = None,
        slide_index: int = 1,
        total_slides: int = 1,
        color_theme: str = "dark",
        prev_outline: SlideOutline | None = None,
        next_outline: SlideOutline | None = None,
        review_feedback: str = "",
        design_directives: str = "",
        budget_tokens: int = 8192,
    ) -> dict:
        """단일 슬라이드 design spec 생성을 위한 LLM 태스크를 조립한다.

        Args 는 기존 generate_single_slide 와 동일하며, 프롬프트 조립도 동일하다.

        Returns:
            build_llm_task 결과 (system_prompt, user_prompt, response_schema) +
            slide_type, thinking_budget 힌트.
        """
        slide_type = slide_outline.slide_type or "content"
        outline_json = self._outline_to_json(slide_outline)
        adjacent_context = self._adjacent_context_section(prev_outline, next_outline)
        slide_type_instruction = self._slide_type_instruction(slide_outline.slide_type)

        if design_summary:
            summary_text = json.dumps(design_summary, ensure_ascii=False, indent=2)
            prompt = DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE.format(
                slide_index=slide_index,
                total_slides=total_slides,
                design_summary=summary_text,
                outline_json=outline_json,
                color_theme=color_theme,
                adjacent_context=adjacent_context,
                slide_type_instruction=slide_type_instruction,
            )
        else:
            prompt = DESIGN_SPEC_USER_PROMPT_TEMPLATE.format(
                slide_index=slide_index,
                total_slides=total_slides,
                outline_json=outline_json,
                color_theme=color_theme,
                adjacent_context=adjacent_context,
                slide_type_instruction=slide_type_instruction,
            )

        if design_directives:
            prompt = prompt + "\n\n" + design_directives

        if review_feedback:
            prompt = prompt + "\n\n" + review_feedback

        system_prompt = get_design_spec_system_prompt(
            slide_type,
            slide_outline.component_hint,
        )
        model = slide_spec_output_model(slide_type)
        return build_llm_task(
            system_prompt=system_prompt,
            user_prompt=prompt,
            response_schema=model.model_json_schema(),
            slide_type=slide_type,
            thinking_budget=budget_tokens,
        )

    def ingest_slide(
        self,
        spec_json: str | dict,
        slide_type: str | None = "content",
    ) -> tuple[PptxSlideSpec, list[dict]]:
        """클라이언트가 생성한 슬라이드 spec JSON 을 검증·정합화한다.

        기존 generate_single_slide 후처리와 동일:
        Pydantic 검증 → to_dataclass → clean_slide_spec, overflow 추출, slide_type 세팅.
        동작 불변: 응답 모델 선택은 정규화된 `slide_type or "content"` 로, 최종 spec 에
        저장하는 slide_type 은 전달받은 원본 값(None/"" 포함) 그대로 둔다 — 기존
        `replace(spec, slide_type=slide_outline.slide_type)` 과 동일하다.

        Returns:
            (spec, overflow) — overflow 는 초과 컨텐츠 dict 리스트.
        """
        model = slide_spec_output_model(slide_type or "content")
        output = self._validate(model, spec_json)
        overflow = (
            [item.model_dump() for item in output.overflow] if output.overflow else []
        )
        if overflow:
            logger.info(
                "slide overflow detected: %d item(s) to suggest as new slides",
                len(overflow),
            )
        spec = clean_slide_spec(output.to_dataclass())
        spec = replace(spec, slide_type=slide_type)
        return spec, overflow

    # ------------------------------------------------------------------
    # DESIGN.md 초안 (theme + tone + anti_slop + page_requests): prepare / ingest
    # ------------------------------------------------------------------

    def prepare_design_doc_draft(
        self,
        outline: OutlineResponse,
        color_theme: str = "dark",
        *,
        presentation_context: dict | None = None,
    ) -> dict:
        """DESIGN.md 초안(수치 테마 + 톤 + 선별적 페이지 요청) 생성 태스크를 조립한다.

        prepare 와 ingest 가 동일한 Pydantic 출력 모델을 사용한다.
        """
        outline_json = self._outline_summary_json(outline)
        prompt = DESIGN_DOC_DRAFT_USER_PROMPT_TEMPLATE.format(
            total_slides=len(outline.slides),
            color_theme=color_theme,
            outline_json=outline_json,
        )
        if presentation_context:
            prompt += (
                "\n\n<presentation_context>\n"
                + json.dumps(presentation_context, ensure_ascii=False, indent=2)
                + "\n</presentation_context>"
            )
        return build_llm_task(
            system_prompt=DESIGN_DOC_DRAFT_SYSTEM_PROMPT,
            user_prompt=prompt,
            response_schema=DesignDocDraftOutput.model_json_schema(),
        )

    def ingest_design_doc_draft(self, draft_text: str) -> tuple[dict, str, str, list]:
        """클라이언트가 생성한 DESIGN.md 초안 JSON 을 파싱한다.

        prepare 에서 반환한 동일 Pydantic 모델로 검증한다. Markdown JSON fence 는
        클라이언트 호환을 위해 허용한다.

        Returns:
            (design_summary, tone, anti_slop, page_requests)
        """
        from ppt_generator.tools.design.design_doc_md import PageRequest

        raw_text = str(draft_text)
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw_text, re.DOTALL)
        if json_match:
            raw_text = json_match.group(1)
        output = self._validate(DesignDocDraftOutput, raw_text.strip())
        summary = output.theme.model_dump()
        tone = output.tone.strip()
        anti_slop_data = output.anti_slop.model_dump()
        # 기존 클라이언트의 필드는 허용하지만 생성 지시에 강제 반복 상한을 남기지 않는다.
        anti_slop_data.pop("max_consecutive_same_archetype", None)
        anti_slop = "\n".join(
            f"- {key}: {value}" for key, value in anti_slop_data.items()
        )
        page_requests = [
            PageRequest(
                number=item.number,
                title=item.title,
                text=item.request.strip(),
            )
            for item in output.page_requests
        ]

        logger.info(
            "design_doc draft ingested: tone=%dchars, anti_slop=%dchars, page_requests=%d",
            len(tone),
            len(anti_slop),
            len(page_requests),
        )
        return summary, tone, anti_slop, page_requests

    @staticmethod
    def extract_design_summary(spec: PptxSlideSpec) -> dict:
        """디자인·임포트 경로에서 공통 테마 요약을 반환한다."""
        return summarize_design(spec)

    # ------------------------------------------------------------------
    # imported 슬라이드 design_doc backfill: prepare / ingest
    # ------------------------------------------------------------------

    def prepare_backfill(
        self,
        spec: PptxSlideSpec,
        slide_index: int = 1,
    ) -> dict:
        """imported 슬라이드 design_doc backfill 을 위한 LLM 태스크를 조립한다.

        Raises:
            ValueError: 이미 design_doc 이 있는 슬라이드.
        """
        if spec.design_doc is not None:
            raise ValueError(
                f"slide {slide_index} already has a design_doc; backfill not needed."
            )
        elements_json = _serialize_elements_for_backfill(spec)
        prompt = BACKFILL_DESIGN_DOC_USER_PROMPT_TEMPLATE.format(
            slide_index=slide_index,
            elements_json=elements_json,
        )
        return build_llm_task(
            system_prompt=BACKFILL_DESIGN_DOC_SYSTEM_PROMPT,
            user_prompt=prompt,
            response_schema=BackfillDesignDocOutput.model_json_schema(),
        )

    def ingest_backfill(
        self,
        spec: PptxSlideSpec,
        output_json: str | dict,
        slide_index: int = 1,
    ) -> PptxSlideSpec:
        """클라이언트가 생성한 backfill JSON 을 검증하고 design_doc 트리를 채운다.

        기존 backfill_design_doc 의 후처리(_apply_backfill_output)와 동일.
        """
        if spec.design_doc is not None:
            return spec
        output = self._validate(BackfillDesignDocOutput, output_json)
        return _apply_backfill_output(spec, output)

    # ------------------------------------------------------------------
    # 단일 component 부분 수정: prepare / ingest
    # ------------------------------------------------------------------

    def prepare_modify_component(
        self,
        spec: PptxSlideSpec,
        component_id: str,
        instruction: str,
        slide_index: int = 1,
        color_theme: str = "dark",
    ) -> dict:
        """단일 component 부분 수정을 위한 LLM 태스크를 조립한다.

        대상 component_id 가 존재하는지 먼저 검증(_find_element_by_component_id)한다.

        Raises:
            ValueError: design_doc 없음, 또는 component_id 미존재/모호.
        """
        if spec.design_doc is None:
            raise ValueError(
                "modify_component requires a slide with design_doc "
                "(content slides only). Use prepare_slide_edit(action='update') "
                "for title/closing/imported slides."
            )
        # element와 design tree leaf가 각각 하나인지 검증한다.
        _find_element_by_component_id(spec, component_id)
        _find_layout_leaf_by_id(spec.design_doc.layout, component_id)

        slide_spec_json = slide_spec_to_json(spec)
        prompt = COMPONENT_MODIFY_USER_PROMPT_TEMPLATE.format(
            slide_index=slide_index,
            color_theme=color_theme,
            target_component_id=component_id,
            slide_spec_json=slide_spec_json,
            instruction=instruction,
        )
        return build_llm_task(
            system_prompt=COMPONENT_MODIFY_SYSTEM_PROMPT,
            user_prompt=prompt,
            response_schema=ComponentModifyOutput.model_json_schema(),
        )

    def ingest_modify_component(
        self,
        spec: PptxSlideSpec,
        component_id: str,
        output_json: str | dict,
    ) -> PptxSlideSpec:
        """클라이언트가 생성한 부분 수정 JSON 을 검증하고 단일 element 만 교체한다.

        기존 modify_component 의 후처리와 동일 — element_kind 검증, z_index/grid_cell
        보존, bbox_changed 시 design_doc.layout 노드 bbox 동기화, clean_slide_spec.
        """
        if spec.design_doc is None:
            raise ValueError(
                "modify_component requires a slide with design_doc "
                "(content slides only)."
            )
        kind, idx, existing = _find_element_by_component_id(spec, component_id)
        _find_layout_leaf_by_id(spec.design_doc.layout, component_id)
        output = self._validate(ComponentModifyOutput, output_json)

        if output.element_kind != kind:
            raise ValueError(
                f"LLM returned element_kind={output.element_kind} but target "
                f"component_id={component_id} is a {kind}. Modification rejected."
            )

        # 결정 11: LLM schema 에 없는 비-design 메타 필드는 기존 element 에서 보존.
        if kind == "textbox":
            if output.textbox is None:
                raise ValueError(
                    "LLM response missing textbox body for element_kind='textbox'."
                )
            new_tb = textbox_output_to_dataclass(output.textbox)
            new_tb = replace(
                new_tb,
                component_id=component_id,
                z_index=existing.z_index,
                grid_cell=existing.grid_cell,
            )
            new_textboxes = list(spec.textboxes)
            new_textboxes[idx] = new_tb
            new_spec = replace(spec, textboxes=new_textboxes)
        else:
            if output.shape is None:
                raise ValueError(
                    "LLM response missing shape body for element_kind='shape'."
                )
            new_shape = shape_output_to_dataclass(output.shape)
            new_shape = replace(
                new_shape,
                component_id=component_id,
                z_index=existing.z_index,
                grid_cell=existing.grid_cell,
            )
            new_shapes = list(spec.shapes)
            new_shapes[idx] = new_shape
            new_spec = replace(spec, shapes=new_shapes)

        return derive_spec_layout_bboxes(new_spec)

    # ------------------------------------------------------------------
    # 검증 헬퍼
    # ------------------------------------------------------------------

    _validate = staticmethod(validate_llm_output)

    @staticmethod
    def _outline_summary_json(outline: OutlineResponse) -> str:
        """DESIGN.md 초안 프롬프트용 outline 요약 JSON."""
        return json.dumps(
            [_outline_prompt_data(s, include_notes=False) for s in outline.slides],
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def _slide_type_instruction(slide_type: str) -> str:
        """Returns the layout instruction to pass to the LLM based on slide_type."""
        if slide_type == "title":
            return "\nThis slide is a **title slide**."
        if slide_type == "closing":
            return "\nThis slide is a **closing slide**."
        return ""

    @staticmethod
    def _adjacent_context_section(
        prev_outline: SlideOutline | None,
        next_outline: SlideOutline | None,
    ) -> str:
        """Generates a prompt section with adjacent slide outline summaries.

        Excludes speaker_notes to save tokens.
        Returns empty string if both are None.
        """
        if prev_outline is None and next_outline is None:
            return ""

        def _summarize(outline: SlideOutline) -> dict:
            return _outline_prompt_data(outline, include_notes=False)

        parts: list[str] = ["<adjacent_slides>"]
        if prev_outline is not None:
            prev_json = json.dumps(
                _summarize(prev_outline), ensure_ascii=False, indent=2
            )
            parts.append(f"<previous_slide>\n{prev_json}\n</previous_slide>")
        if next_outline is not None:
            next_json = json.dumps(
                _summarize(next_outline), ensure_ascii=False, indent=2
            )
            parts.append(f"<next_slide>\n{next_json}\n</next_slide>")
        parts.append("</adjacent_slides>")
        return "\n".join(parts)

    @staticmethod
    def find_element_by_component_id(
        spec: PptxSlideSpec, component_id: str
    ) -> tuple[str, int, PptxTextBox | PptxShape]:
        """대상 component_id 의 element 를 찾아 (kind, index, element) 반환."""
        return _find_element_by_component_id(spec, component_id)

    @staticmethod
    def _outline_to_json(slide: SlideOutline) -> str:
        """Converts a SlideOutline to a JSON string."""
        return json.dumps(
            _outline_prompt_data(slide),
            ensure_ascii=False,
            indent=2,
        )


def _outline_prompt_data(slide: SlideOutline, *, include_notes: bool = True) -> dict:
    """계획과 근거를 보존하고 내부 저장 인덱스만 프롬프트에서 제외한다."""
    data = asdict(slide)
    data.pop("slide_index", None)
    if not include_notes:
        data.pop("speaker_notes", None)
    return data
