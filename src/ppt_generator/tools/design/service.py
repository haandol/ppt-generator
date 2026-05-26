"""Design spec generation service.

Generates PptxSlideSpec-based design specs from slide outlines via LLM.
Uses strands structured_output for direct parsing into Pydantic models.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import replace
from typing import NoReturn

from strands import Agent
from strands.types.exceptions import ModelThrottledException

from ppt_generator.interfaces.constants import (
    BACKFILL_DESIGN_DOC_USER_PROMPT_TEMPLATE,
    COMPONENT_MODIFY_USER_PROMPT_TEMPLATE,
    DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE,
    DESIGN_SPEC_USER_PROMPT_TEMPLATE,
    DESIGN_SUMMARY_USER_PROMPT_TEMPLATE,
)
from ppt_generator.interfaces.llm_output_models import (
    BackfillDesignDocOutput,
    ComponentModifyOutput,
    ContentSlideSpecOutput,
    SimpleSlideSpecOutput,
    _BaseSlideSpecOutput,
    shape_output_to_dataclass,
    textbox_output_to_dataclass,
)
from ppt_generator.interfaces.schemas import (
    DesignDoc,
    LayoutNode,
    OutlineResponse,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    SlideOutline,
)
from ppt_generator.interfaces.spec_utils import clean_slide_spec
from ppt_generator.interfaces.spec_utils.serializer import slide_spec_to_json
from ppt_generator.interfaces.utils import log_token_usage

logger = logging.getLogger(__name__)


class DesignService:
    """Service that generates PptxSlideSpec from slide outlines."""

    def __init__(self, agent: Agent, backfill_agent: Agent | None = None) -> None:
        self._agent = agent
        self._backfill_agent = backfill_agent
        self._last_token_usage: dict[str, int] = {}
        self._last_overflow: list[dict] = []

    def generate_single_slide(
        self,
        slide_outline: SlideOutline,
        design_summary: dict | None = None,
        slide_index: int = 1,
        total_slides: int = 1,
        color_theme: str = "dark",
        prev_outline: SlideOutline | None = None,
        next_outline: SlideOutline | None = None,
        review_feedback: str = "",
    ) -> PptxSlideSpec:
        """Generates the design spec for a single slide.

        Args:
            slide_outline: Slide outline
            design_summary: Existing design summary dict (maintains consistency when provided)
            slide_index: Slide number (1-based)
            total_slides: Total number of slides
            color_theme: Color theme ("dark" or "light", default: "dark")
            prev_outline: Previous slide outline (None for first slide)
            next_outline: Next slide outline (None for last slide)

        Returns:
            Generated PptxSlideSpec
        """
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

        if review_feedback:
            prompt = prompt + "\n\n" + review_feedback

        spec = self._generate_with_structured_output(
            prompt,
            slide_type=slide_outline.slide_type or "content",
            label=f"slide[{slide_index}/{total_slides}]",
        )
        return replace(spec, slide_type=slide_outline.slide_type)

    def generate_design_summary(
        self,
        outline: OutlineResponse,
        color_theme: str = "dark",
    ) -> dict:
        """Pre-generates a design_summary via LLM based on the full outline.

        Args:
            outline: Full outline (OutlineResponse)
            color_theme: Color theme ("dark" or "light")

        Returns:
            Dict in the same format as extract_design_summary()
        """
        outline_json = json.dumps(
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

        prompt = DESIGN_SUMMARY_USER_PROMPT_TEMPLATE.format(
            total_slides=len(outline.slides),
            color_theme=color_theme,
            outline_json=outline_json,
        )

        try:
            result = self._agent(prompt)
            log_token_usage(result, "design_summary")
        except ModelThrottledException:
            logger.warning("Bedrock throttling during design_summary generation")
            raise
        raw_text = str(result)

        # Extract JSON block (```json... ``` or raw JSON)
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw_text, re.DOTALL)
        if json_match:
            raw_text = json_match.group(1)

        summary = json.loads(raw_text.strip())
        logger.info("design_summary LLM generation completed: %s", summary)
        return summary

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

    def backfill_design_doc(
        self,
        spec: PptxSlideSpec,
        slide_index: int = 1,
    ) -> PptxSlideSpec:
        """Imported 슬라이드(design_doc=None)에 design_doc 트리를 LLM 으로 backfill한다.

        textbox/shape 의 좌표/스타일/텍스트는 변경하지 않고, design_doc.layout
        트리 + 각 element 의 component_id 만 채운다. grid_plan 은 None 유지.
        bbox 는 코드에서 element bbox 합집합으로 계산.

        Returns:
            새 PptxSlideSpec — design_doc 채워지고 textbox/shape 의 component_id 도 링크됨.

        Raises:
            ValueError: 백필 대상이 부적합하거나(이미 design_doc 있음, content slide 아님 등)
                LLM 응답 검증 실패.
        """
        if spec.design_doc is not None:
            return spec
        if self._backfill_agent is None:
            raise RuntimeError(
                "DesignService backfill_agent is not configured. "
                "Pass it via DIContainer.create_design_service."
            )

        elements_json = _serialize_elements_for_backfill(spec)
        prompt = BACKFILL_DESIGN_DOC_USER_PROMPT_TEMPLATE.format(
            slide_index=slide_index,
            elements_json=elements_json,
        )

        try:
            result = self._backfill_agent(
                prompt, structured_output_model=BackfillDesignDocOutput
            )
            self._last_token_usage = log_token_usage(
                result, f"backfill_design_doc[{slide_index}]"
            )
        except ModelThrottledException:
            logger.warning("Bedrock throttling during design_doc backfill")
            raise

        output: BackfillDesignDocOutput = result.structured_output
        return _apply_backfill_output(spec, output)

    def modify_component(
        self,
        spec: PptxSlideSpec,
        component_id: str,
        instruction: str,
        slide_index: int = 1,
        color_theme: str = "dark",
    ) -> PptxSlideSpec:
        """Applies a surgical modification to a single component.

        Returns a new PptxSlideSpec with exactly one textbox/shape replaced
        (and its design_doc.layout node bbox synced if bbox changed).
        Raises ValueError when component_id is not found or design_doc is missing.
        """
        if spec.design_doc is None:
            raise ValueError(
                "modify_component requires a slide with design_doc "
                "(content slides only). Use modify_design_spec(action='update') "
                "for title/closing/imported slides."
            )
        kind, idx, existing = _find_element_by_component_id(spec, component_id)

        slide_spec_json = slide_spec_to_json(spec)
        prompt = COMPONENT_MODIFY_USER_PROMPT_TEMPLATE.format(
            slide_index=slide_index,
            color_theme=color_theme,
            target_component_id=component_id,
            slide_spec_json=slide_spec_json,
            instruction=instruction,
        )

        try:
            result = self._agent(prompt, structured_output_model=ComponentModifyOutput)
            self._last_token_usage = log_token_usage(
                result, f"modify_component[{component_id}]"
            )
        except ModelThrottledException:
            logger.warning("Bedrock throttling during component modification")
            raise

        output: ComponentModifyOutput = result.structured_output
        if output.element_kind != kind:
            raise ValueError(
                f"LLM returned element_kind={output.element_kind} but target "
                f"component_id={component_id} is a {kind}. Modification rejected."
            )

        # 결정 11: LLM schema 에 없는 비-design 메타 필드는 기존 element
        # 에서 보존한다. component_id 는 입력값을 그대로 유지.
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

        if output.bbox_changed and new_spec.design_doc is not None:
            updated_layout = _replace_node_bbox(
                new_spec.design_doc.layout, component_id, new_bbox
            )
            new_design_doc = replace(new_spec.design_doc, layout=updated_layout)
            new_spec = replace(new_spec, design_doc=new_design_doc)

        return clean_slide_spec(new_spec)

    @property
    def last_token_usage(self) -> dict[str, int]:
        """Token usage from the last LLM call. Empty dict before first call."""
        return self._last_token_usage

    @property
    def last_overflow(self) -> list[dict]:
        """Overflow content from the last LLM call. Empty list if none."""
        return self._last_overflow

    def _generate_with_structured_output(
        self,
        prompt: str,
        *,
        slide_type: str,
        label: str = "design_spec",
    ) -> PptxSlideSpec:
        """Generates and validates slide spec via strands structured_output.

        slide_type 에 따라 응답 모델을 분기해 content 슬라이드는
        grid_plan 을 Pydantic Required 로 강제한다. title/closing 은 옵셔널.
        """
        model: type[_BaseSlideSpecOutput] = (
            ContentSlideSpecOutput if slide_type == "content" else SimpleSlideSpecOutput
        )
        try:
            result = self._agent(prompt, structured_output_model=model)
            self._last_token_usage = log_token_usage(result, label)
        except ModelThrottledException:
            logger.warning("Bedrock throttling during design spec generation")
            raise
        output: _BaseSlideSpecOutput = result.structured_output
        self._last_overflow = (
            [item.model_dump() for item in output.overflow] if output.overflow else []
        )
        if self._last_overflow:
            logger.info(
                "slide overflow detected: %d item(s) to suggest as new slides",
                len(self._last_overflow),
            )
        spec = output.to_dataclass()
        return clean_slide_spec(spec)

    @staticmethod
    def _slide_type_instruction(slide_type: str) -> str:
        """Returns the layout instruction to pass to the LLM based on slide_type.

        Since system prompts are separated by slide_type,
        the user prompt only specifies the slide type.
        """
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
    return replace(
        spec,
        textboxes=new_textboxes,
        shapes=new_shapes,
        design_doc=new_design_doc,
    )
