"""Design spec generation service.

Generates PptxSlideSpec-based design specs from slide outlines via LLM.
Uses strands structured_output for direct parsing into Pydantic models.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import replace

from strands import Agent
from strands.types.exceptions import ModelThrottledException

from ppt_generator.interfaces.constants import (
    DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE,
    DESIGN_SPEC_USER_PROMPT_TEMPLATE,
    DESIGN_SUMMARY_USER_PROMPT_TEMPLATE,
)
from ppt_generator.interfaces.llm_output_models import SlideSpecOutput
from ppt_generator.interfaces.schemas import (
    OutlineResponse,
    PptxSlideSpec,
    SlideOutline,
)
from ppt_generator.interfaces.spec_utils import validate_slide_spec
from ppt_generator.interfaces.spec_utils.serializer import slide_spec_to_json
from ppt_generator.interfaces.utils import log_token_usage

logger = logging.getLogger(__name__)


class DesignService:
    """Service that generates PptxSlideSpec from slide outlines."""

    def __init__(self, agent: Agent) -> None:
        self._agent = agent
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
        reference_specs: list[PptxSlideSpec] | None = None,
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
        reference_specs_section = self._reference_specs_section(reference_specs)

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
                reference_specs=reference_specs_section,
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

        # Extract JSON block (```json ... ``` or raw JSON)
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

    @property
    def last_token_usage(self) -> dict[str, int]:
        """Token usage from the last LLM call. Empty dict before first call."""
        return self._last_token_usage

    @property
    def last_overflow(self) -> list[dict]:
        """Overflow content from the last LLM call. Empty list if none."""
        return self._last_overflow

    def _generate_with_structured_output(
        self, prompt: str, *, label: str = "design_spec"
    ) -> PptxSlideSpec:
        """Generates and validates slide spec via strands structured_output."""
        try:
            result = self._agent(prompt, structured_output_model=SlideSpecOutput)
            self._last_token_usage = log_token_usage(result, label)
        except ModelThrottledException:
            logger.warning("Bedrock throttling during design spec generation")
            raise
        output: SlideSpecOutput = result.structured_output
        self._last_overflow = (
            [item.model_dump() for item in output.overflow] if output.overflow else []
        )
        if self._last_overflow:
            logger.info(
                "slide overflow detected: %d item(s) to suggest as new slides",
                len(self._last_overflow),
            )
        spec = output.to_dataclass()
        return validate_slide_spec(spec)

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
    def _reference_specs_section(
        reference_specs: list[PptxSlideSpec] | None,
    ) -> str:
        """Generates a prompt section with reference design spec JSONs.

        Strips speaker_notes and images to save tokens.
        Returns empty string if reference_specs is None or empty.
        """
        if not reference_specs:
            return ""

        parts: list[str] = [
            "<reference_specs>",
            "The following are existing slide design specs for reference. "
            "Match the coordinate system, font sizes, padding, spacing, "
            "and color patterns used in these specs.",
        ]
        for i, spec in enumerate(reference_specs):
            spec_json = slide_spec_to_json(replace(spec, speaker_notes="", images=[]))
            parts.append(f"<spec_{i + 1}>\n{spec_json}\n</spec_{i + 1}>")
        parts.append("</reference_specs>")
        return "\n".join(parts)

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
