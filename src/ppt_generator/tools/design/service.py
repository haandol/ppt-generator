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
from dataclasses import replace
from typing import NoReturn

from ppt_generator.interfaces.constants import (
    BACKFILL_DESIGN_DOC_SYSTEM_PROMPT,
    BACKFILL_DESIGN_DOC_USER_PROMPT_TEMPLATE,
    COMPONENT_MODIFY_SYSTEM_PROMPT,
    COMPONENT_MODIFY_USER_PROMPT_TEMPLATE,
    DESIGN_DOC_DRAFT_USER_PROMPT_TEMPLATE,
    DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE,
    DESIGN_SPEC_SYSTEM_PROMPTS,
    DESIGN_SPEC_USER_PROMPT_TEMPLATE,
)
from ppt_generator.interfaces.handoff import build_llm_task
from ppt_generator.interfaces.llm_output_models import (
    BackfillDesignDocOutput,
    BackfillNode,
    ComponentModifyOutput,
    DesignDocDraftOutput,
    shape_output_to_dataclass,
    slide_spec_output_model,
    textbox_output_to_dataclass,
)
from ppt_generator.interfaces.schemas import (
    DesignDoc,
    GridCell,
    GridPlan,
    LayoutNode,
    OutlineResponse,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    SlideOutline,
)
from ppt_generator.interfaces.spec_utils import clean_slide_spec
from ppt_generator.interfaces.spec_utils.serializer import slide_spec_to_json

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

        system_prompt = DESIGN_SPEC_SYSTEM_PROMPTS.get(
            slide_type, DESIGN_SPEC_SYSTEM_PROMPTS["content"]
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
    # DESIGN.md 초안 (theme + tone + page_requests): prepare / ingest
    # ------------------------------------------------------------------

    def prepare_design_doc_draft(
        self,
        outline: OutlineResponse,
        color_theme: str = "dark",
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
        return build_llm_task(
            system_prompt=DESIGN_SPEC_SYSTEM_PROMPTS["content"],
            user_prompt=prompt,
            response_schema=DesignDocDraftOutput.model_json_schema(),
        )

    def ingest_design_doc_draft(self, draft_text: str) -> tuple[dict, str, list]:
        """클라이언트가 생성한 DESIGN.md 초안 JSON 을 파싱한다.

        prepare 에서 반환한 동일 Pydantic 모델로 검증한다. Markdown JSON fence 는
        클라이언트 호환을 위해 허용한다.

        Returns:
            (design_summary, tone, page_requests)
        """
        from ppt_generator.tools.design.design_doc_md import PageRequest

        raw_text = str(draft_text)
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw_text, re.DOTALL)
        if json_match:
            raw_text = json_match.group(1)
        output = self._validate(DesignDocDraftOutput, raw_text.strip())
        summary = output.theme.model_dump()
        tone = output.tone.strip()
        page_requests = [
            PageRequest(
                number=item.number,
                title=item.title.strip(),
                text=item.request.strip(),
            )
            for item in output.page_requests
        ]

        logger.info(
            "design_doc draft ingested: tone=%dchars, page_requests=%d",
            len(tone),
            len(page_requests),
        )
        return summary, tone, page_requests

    @staticmethod
    def extract_design_summary(spec: PptxSlideSpec) -> dict:
        """Extracts design theme summary directly from slide spec (no LLM call)."""
        text_colors: set[str] = set()
        title_font: int | None = None
        body_font: int | None = None

        for tb in spec.textboxes:
            for para in tb.paragraphs:
                for run in para.runs:
                    if run.color:
                        text_colors.add(run.color)
                    if run.font_size_pt:
                        if run.bold and (
                            title_font is None or run.font_size_pt > title_font
                        ):
                            title_font = run.font_size_pt
                        elif not run.bold and (
                            body_font is None or run.font_size_pt > body_font
                        ):
                            body_font = run.font_size_pt

        card_fills: set[str] = set()
        card_borders: set[str] = set()
        for s in spec.shapes:
            if s.fill_color:
                card_fills.add(s.fill_color)
            if s.border_color:
                card_borders.add(s.border_color)
            for para in s.paragraphs:
                for run in para.runs:
                    if run.color:
                        text_colors.add(run.color)
                    if run.font_size_pt:
                        if run.bold and (
                            title_font is None or run.font_size_pt > title_font
                        ):
                            title_font = run.font_size_pt
                        elif not run.bold and (
                            body_font is None or run.font_size_pt > body_font
                        ):
                            body_font = run.font_size_pt
            if s.text_color:
                text_colors.add(s.text_color)

        return {
            "background_color": spec.background_color or None,
            "text_colors": sorted(text_colors) if text_colors else [],
            "title_font_pt": title_font,
            "body_font_pt": body_font,
            "card_fills": sorted(card_fills) if card_fills else [],
            "card_borders": sorted(card_borders) if card_borders else [],
        }

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
            new_bbox = (
                new_tb.left_px,
                new_tb.top_px,
                new_tb.width_px,
                new_tb.height_px,
            )
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
            new_bbox = (
                new_shape.left_px,
                new_shape.top_px,
                new_shape.width_px,
                new_shape.height_px,
            )

        old_bbox = (
            existing.left_px,
            existing.top_px,
            existing.width_px,
            existing.height_px,
        )
        bbox_changed = new_bbox != old_bbox
        if bbox_changed and new_spec.design_doc is not None:
            updated_layout = _replace_node_bbox(
                new_spec.design_doc.layout, component_id, new_bbox
            )
            new_design_doc = replace(new_spec.design_doc, layout=updated_layout)
            new_spec = replace(new_spec, design_doc=new_design_doc)

        return new_spec

    # ------------------------------------------------------------------
    # 검증 헬퍼
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(model, payload: str | dict):
        """클라이언트 JSON 을 Pydantic 모델로 검증한다 (문자열/딕셔너리 모두 허용)."""
        if isinstance(payload, str):
            return model.model_validate_json(payload)
        return model.model_validate(payload)

    @staticmethod
    def _outline_summary_json(outline: OutlineResponse) -> str:
        """DESIGN.md 초안 프롬프트용 outline 요약 JSON."""
        return json.dumps(
            [
                {
                    "title": s.title,
                    "content_summary": s.content_summary,
                    "component_hint": s.component_hint,
                    "slide_type": s.slide_type,
                }
                for s in outline.slides
            ],
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
            return {
                "title": outline.title,
                "content_summary": outline.content_summary,
                "component_hint": outline.component_hint,
                "slide_type": outline.slide_type,
            }

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
            {
                "title": slide.title,
                "content_summary": slide.content_summary,
                "component_hint": slide.component_hint,
                "speaker_notes": slide.speaker_notes,
                "slide_type": slide.slide_type,
            },
            ensure_ascii=False,
            indent=2,
        )


# ---------------------------------------------------------------------------
# helpers for modify_component
# ---------------------------------------------------------------------------


def _find_element_by_component_id(
    spec: PptxSlideSpec, component_id: str
) -> tuple[str, int, "PptxTextBox | PptxShape"]:
    """spec 의 textboxes/shapes 중 component_id 일치 element 를 찾는다.

    Returns:
        (kind, index, element) — kind 는 "textbox" | "shape", index 는 0-based.

    Raises:
        ValueError: component_id 가 어디에도 없거나 (정상 케이스), 두 곳 이상에서
            중복 매칭 (ambiguous link, 결정 12).
    """
    matches: list[tuple[str, int, PptxTextBox | PptxShape]] = []
    for i, tb in enumerate(spec.textboxes):
        if tb.component_id == component_id:
            matches.append(("textbox", i, tb))
    for i, s in enumerate(spec.shapes):
        if s.component_id == component_id:
            matches.append(("shape", i, s))
    if not matches:
        raise ValueError(
            f"component_id not found in slide: {component_id!r}. "
            "Check design_doc.layout for the available component ids."
        )
    if len(matches) > 1:
        locs = ", ".join(f"{k}#{i}" for k, i, _ in matches)
        raise ValueError(
            f"component_id {component_id!r} is ambiguous — matches multiple "
            f"elements: {locs}. component_id must be unique within a slide."
        )
    return matches[0]


def _find_layout_leaf_by_id(nodes: list[LayoutNode], component_id: str) -> LayoutNode:
    """design tree에서 id가 일치하는 유일한 component leaf를 찾는다."""
    matches: list[LayoutNode] = []

    def _walk(node: LayoutNode) -> None:
        if node.id == component_id:
            matches.append(node)
        for child in node.children:
            _walk(child)

    for root in nodes:
        _walk(root)
    if not matches:
        raise ValueError(
            f"component_id not found in design_doc.layout: {component_id!r}"
        )
    if len(matches) > 1:
        raise ValueError(
            f"component_id {component_id!r} is ambiguous in design_doc.layout"
        )
    node = matches[0]
    if node.kind != "component" or node.children:
        raise ValueError(
            f"component_id {component_id!r} must reference a component leaf"
        )
    return node


def _replace_node_bbox(
    nodes: list[LayoutNode],
    target_id: str,
    bbox: tuple[float, float, float, float],
) -> list[LayoutNode]:
    """design_doc.layout 트리(임의 깊이)에서 target_id 노드의 bbox 만 교체한다.

    frozen dataclass 라 path 따라 부모 체인을 replace 로 새로 만든다.
    """
    left, top, width, height = bbox

    def _walk(node: LayoutNode) -> tuple[LayoutNode, bool]:
        if node.id == target_id:
            return (
                replace(
                    node,
                    left_px=left,
                    top_px=top,
                    width_px=width,
                    height_px=height,
                ),
                True,
            )
        new_children: list[LayoutNode] = []
        changed = False
        for child in node.children:
            new_child, child_changed = _walk(child)
            new_children.append(new_child)
            if child_changed:
                changed = True
        if changed:
            return (replace(node, children=new_children), True)
        return (node, False)

    out: list[LayoutNode] = []
    for n in nodes:
        new_node, _ = _walk(n)
        out.append(new_node)
    return out


# ---------------------------------------------------------------------------
# helpers for backfill_design_doc
# ---------------------------------------------------------------------------


def _is_decorative(shape: PptxShape) -> bool:
    """단순 connecting line/arrow (텍스트 없고 두께 ≤3px) 는 backfill 에서 제외."""
    has_text = bool(shape.text and shape.text.strip())
    if not has_text and shape.paragraphs:
        has_text = any(
            run.text.strip() for para in shape.paragraphs for run in para.runs
        )
    if has_text:
        return False
    is_thin_line = (
        shape.shape_type == "line"
        or abs(shape.width_px) <= 3
        or abs(shape.height_px) <= 3
    )
    return is_thin_line


def _serialize_elements_for_backfill(spec: PptxSlideSpec) -> str:
    """LLM 에 전달할 element 요약 JSON. bbox + 텍스트 + 핵심 스타일."""
    items: list[dict] = []
    for i, tb in enumerate(spec.textboxes):
        text_parts: list[str] = []
        for para in tb.paragraphs:
            for run in para.runs:
                if run.text.strip():
                    text_parts.append(run.text)
        items.append(
            {
                "kind": "textbox",
                "index": i,
                "bbox": [tb.left_px, tb.top_px, tb.width_px, tb.height_px],
                "text": " ".join(text_parts).strip(),
            }
        )
    for i, s in enumerate(spec.shapes):
        text_parts = []
        if s.text and s.text.strip():
            text_parts.append(s.text)
        for para in s.paragraphs:
            for run in para.runs:
                if run.text.strip():
                    text_parts.append(run.text)
        item: dict = {
            "kind": "shape",
            "index": i,
            "bbox": [s.left_px, s.top_px, s.width_px, s.height_px],
            "shape_type": s.shape_type,
            "fill_color": s.fill_color,
            "text": " ".join(text_parts).strip(),
            "decorative": _is_decorative(s),
        }
        items.append(item)
    return json.dumps({"elements": items}, ensure_ascii=False, indent=2)


def _backfill_fail(reason: str, **context) -> NoReturn:
    """backfill 검증 실패를 로깅하고 ValueError raise. context 는 디버깅용 메타."""
    ctx_str = " ".join(f"{k}={v!r}" for k, v in context.items() if v is not None)
    logger.error("backfill validation failed: %s | %s", reason, ctx_str)
    raise ValueError(reason)


def _apply_backfill_output(
    spec: PptxSlideSpec, output: BackfillDesignDocOutput
) -> PptxSlideSpec:
    """LLM 응답을 검증하고, design_doc 트리 + textbox/shape component_id 를 채운다.

    bbox 후처리:
      - leaf component bbox = 참조한 element bbox
      - section/group bbox = 자식 bbox 의 axis-aligned 합집합
    """
    nodes_by_id: dict[str, BackfillNode] = {}
    for ni, n in enumerate(output.nodes):
        if not n.id:
            _backfill_fail(
                "backfill output contains a node with empty id",
                node_position=ni,
                kind=n.kind,
                parent_id=n.parent_id,
            )
        if n.id in nodes_by_id:
            _backfill_fail(
                f"backfill output has duplicate node id: {n.id}",
                node_id=n.id,
                node_position=ni,
            )
        nodes_by_id[n.id] = n

    # parent 검증
    for n in output.nodes:
        pid = n.parent_id or ""
        if pid and pid not in nodes_by_id:
            _backfill_fail(
                f"backfill node {n.id!r} has unknown parent_id: {pid!r}",
                node_id=n.id,
                parent_id=pid,
                known_ids=sorted(nodes_by_id.keys()),
            )

    # leaf 의 element_ref 검증 + 매핑 수집
    tb_to_component: dict[int, str] = {}
    sh_to_component: dict[int, str] = {}
    for n in output.nodes:
        if n.kind != "component":
            continue
        if n.element_ref is None:
            _backfill_fail(
                f"component leaf {n.id!r} has no element_ref",
                node_id=n.id,
            )
        ref = n.element_ref
        if ref.kind == "textbox":
            if ref.index >= len(spec.textboxes):
                _backfill_fail(
                    f"component {n.id!r} references textbox#{ref.index} but slide "
                    f"has {len(spec.textboxes)} textboxes",
                    node_id=n.id,
                    ref_kind=ref.kind,
                    ref_index=ref.index,
                    textbox_count=len(spec.textboxes),
                )
            if ref.index in tb_to_component:
                _backfill_fail(
                    f"textbox#{ref.index} is referenced by multiple components: "
                    f"{tb_to_component[ref.index]!r} and {n.id!r}",
                    ref_index=ref.index,
                    first_node=tb_to_component[ref.index],
                    second_node=n.id,
                )
            tb_to_component[ref.index] = n.id
        else:
            if ref.index >= len(spec.shapes):
                _backfill_fail(
                    f"component {n.id!r} references shape#{ref.index} but slide "
                    f"has {len(spec.shapes)} shapes",
                    node_id=n.id,
                    ref_kind=ref.kind,
                    ref_index=ref.index,
                    shape_count=len(spec.shapes),
                )
            if ref.index in sh_to_component:
                _backfill_fail(
                    f"shape#{ref.index} is referenced by multiple components: "
                    f"{sh_to_component[ref.index]!r} and {n.id!r}",
                    ref_index=ref.index,
                    first_node=sh_to_component[ref.index],
                    second_node=n.id,
                )
            sh_to_component[ref.index] = n.id

    # 모든 textbox 가 매핑되었는지 확인 (decorative 가 textbox 일 수는 없음)
    missing_tb = [i for i in range(len(spec.textboxes)) if i not in tb_to_component]
    if missing_tb:
        _backfill_fail(
            f"backfill missed textbox indices: {missing_tb} — "
            "every textbox must map to exactly one component leaf",
            missing_textbox_indices=missing_tb,
        )
    # decorative 가 아닌 모든 shape 매핑 확인
    missing_sh = [
        i
        for i, s in enumerate(spec.shapes)
        if i not in sh_to_component and not _is_decorative(s)
    ]
    if missing_sh:
        _backfill_fail(
            f"backfill missed non-decorative shape indices: {missing_sh}",
            missing_shape_indices=missing_sh,
        )

    # 1) component leaf bbox 계산
    leaf_bboxes: dict[str, tuple[float, float, float, float]] = {}
    for n in output.nodes:
        if n.kind != "component":
            continue
        ref = n.element_ref
        if ref.kind == "textbox":
            tb = spec.textboxes[ref.index]
            leaf_bboxes[n.id] = (tb.left_px, tb.top_px, tb.width_px, tb.height_px)
        else:
            sh = spec.shapes[ref.index]
            leaf_bboxes[n.id] = (sh.left_px, sh.top_px, sh.width_px, sh.height_px)

    # 2) parent → children 인덱스 (입력 순서 유지)
    children_of: dict[str, list[str]] = {}
    order: list[str] = []
    for n in output.nodes:
        order.append(n.id)
        children_of.setdefault(n.parent_id or "", []).append(n.id)

    # 3) post-order 로 bbox 합집합
    bbox_of: dict[str, tuple[float, float, float, float]] = dict(leaf_bboxes)
    pending = list(order)
    while pending:
        progress = False
        for nid in list(pending):
            kids = children_of.get(nid, [])
            if all(k in bbox_of for k in kids):
                if nid in bbox_of:
                    pending.remove(nid)
                    progress = True
                    continue
                if not kids:
                    _backfill_fail(
                        f"non-component node {nid!r} has no children — invalid tree",
                        node_id=nid,
                    )
                lefts = [bbox_of[k][0] for k in kids]
                tops = [bbox_of[k][1] for k in kids]
                rights = [bbox_of[k][0] + bbox_of[k][2] for k in kids]
                bottoms = [bbox_of[k][1] + bbox_of[k][3] for k in kids]
                left = min(lefts)
                top = min(tops)
                width = max(rights) - left
                height = max(bottoms) - top
                bbox_of[nid] = (left, top, width, height)
                pending.remove(nid)
                progress = True
        if not progress:
            _backfill_fail(
                f"backfill tree has cycle or dangling parent_id: pending={pending}",
                pending_ids=pending,
            )

    # 4) LayoutNode 트리 구성 (post-order, frozen dataclass replace)
    finalized: dict[str, LayoutNode] = {}
    pending = list(order)
    while pending:
        progress = False
        for nid in list(pending):
            kids = children_of.get(nid, [])
            if all(k in finalized for k in kids):
                src = nodes_by_id[nid]
                left, top, width, height = bbox_of[nid]
                cell_id = ""
                # leaf 의 component_id 는 textbox/shape 의 grid_cell 에서 가져오면
                # imported 슬라이드는 None 이므로 그대로 빈 문자열 유지
                ref = src.element_ref
                if ref is not None:
                    if ref.kind == "textbox":
                        cell_id = spec.textboxes[ref.index].grid_cell or ""
                    else:
                        cell_id = spec.shapes[ref.index].grid_cell or ""
                finalized[nid] = LayoutNode(
                    id=nid,
                    kind=src.kind,
                    role=src.role or "",
                    description=src.description or "",
                    cell_id=cell_id,
                    left_px=left,
                    top_px=top,
                    width_px=width,
                    height_px=height,
                    children=[finalized[k] for k in kids],
                )
                pending.remove(nid)
                progress = True
        if not progress:
            _backfill_fail(
                "backfill tree finalization failed (cycle or unresolvable parent)",
                pending_ids=pending,
            )

    roots: list[LayoutNode] = [
        finalized[nid] for nid in order if not (nodes_by_id[nid].parent_id or "")
    ]
    new_design_doc = DesignDoc(
        topic=output.topic,
        layout_summary=output.layout_summary,
        layout=roots,
    )

    # 5) textbox/shape 에 component_id 채우기
    new_textboxes = [
        replace(tb, component_id=tb_to_component.get(i))
        for i, tb in enumerate(spec.textboxes)
    ]
    new_shapes = [
        replace(s, component_id=sh_to_component.get(i))
        for i, s in enumerate(spec.shapes)
    ]

    # 6) grid_plan 백필 — LLM 이 grid_layout/cell_assignment 를 출력했을
    # 때만 채운다. 그렇지 않으면 기존 spec.grid_plan 유지 (보통 None).
    new_grid_plan: GridPlan | None = spec.grid_plan
    if output.grid_layout is not None:
        cells_src = (
            output.cell_assignment.cells if output.cell_assignment is not None else []
        )
        new_grid_plan = GridPlan(
            regions=list(output.grid_layout.regions),
            content_columns=output.grid_layout.content_columns,
            content_rows=output.grid_layout.content_rows,
            cells=[
                GridCell(
                    id=c.id,
                    region=c.region,
                    row=c.row,
                    col=c.col,
                    row_span=c.row_span,
                    col_span=c.col_span,
                    role=c.role,
                )
                for c in cells_src
            ],
        )

    return replace(
        spec,
        textboxes=new_textboxes,
        shapes=new_shapes,
        design_doc=new_design_doc,
        grid_plan=new_grid_plan,
    )
