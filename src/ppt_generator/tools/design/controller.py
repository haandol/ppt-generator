"""Design 도구 MCP 등록 (prepare/ingest 오프로딩).

LLM 생성은 클라이언트가 수행한다. 각 생성 단계는 prepare_*(프롬프트+스키마 반환) /
ingest_*(검증+후처리+저장) 로 나뉜다. move/delete 는 LLM 이 없어 단일 도구로 유지.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ppt_generator.tools.design.handlers.deps import DesignDeps
from ppt_generator.tools.design.handlers.generation import (
    handle_finalize_design_spec,
    handle_ingest_design_doc_draft,
    handle_ingest_design_slide,
    handle_prepare_design_doc_draft,
    handle_prepare_design_slide,
)
from ppt_generator.tools.design.handlers.modification import (
    handle_delete,
    handle_ingest_backfill,
    handle_ingest_modify_component,
    handle_ingest_slide_edit,
    handle_move,
    handle_prepare_modify_component,
    handle_prepare_slide_edit,
)
from ppt_generator.tools.design.handlers.review import (
    handle_ingest_review,
    handle_prepare_review,
)
from ppt_generator.tools.design.review_service import DesignReviewService
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.slides.service import SlidesService


def register_design_tools(
    mcp: FastMCP,
    project_service: ProjectService,
    design_service: DesignService,
    slides_service: SlidesService | None = None,
    review_service: DesignReviewService | None = None,
) -> None:
    deps = DesignDeps(
        project_service=project_service,
        design_service=design_service,
        slides_service=slides_service,
        review_service=review_service,
    )

    # ------------------------------------------------------------------
    # DESIGN.md 초안 (theme + tone + page_requests)
    # ------------------------------------------------------------------

    @mcp.tool()
    def prepare_design_doc_draft(
        project_id: str = "",
        outline_json: str = "",
        color_theme: str = "dark",
    ) -> str:
        """Prepares the prompt for the CLIENT to draft DESIGN.md (design intent).

        No LLM call. If DESIGN.md already exists, returns {"skip": true} — reuse the
        existing design intent (do not regenerate). Otherwise returns system_prompt,
        user_prompt, response_schema, and project_id. **Generate the draft JSON
        (theme + tone + page_requests) matching response_schema, then call
        `ingest_design_doc_draft`.**

        Call this ONCE before generating slides, so every slide shares one design
        theme and narrative arc.

        Args:
            project_id: Project ID. Loads outline from the saved project.
            outline_json: Full outline JSON. Optional if project_id is given.
            color_theme: Color theme ("dark" or "light", default: "dark").

        Returns:
            JSON with system_prompt, user_prompt, response_schema, project_id,
            color_theme — or {"skip": true}.
        """
        return handle_prepare_design_doc_draft(
            deps,
            project_id=project_id,
            outline_json=outline_json,
            color_theme=color_theme,
        )

    @mcp.tool()
    def ingest_design_doc_draft(
        project_id: str,
        draft_json: str,
        color_theme: str = "dark",
    ) -> str:
        """Ingests the client-generated DESIGN.md draft and saves DESIGN.md.

        Call AFTER prepare_design_doc_draft with the draft JSON you generated.

        Args:
            project_id: Project ID (required).
            draft_json: Draft JSON (theme + tone + page_requests) from the client.
            color_theme: Color theme (stored into the theme).

        Returns:
            JSON with project_id and design_doc_path.
        """
        return handle_ingest_design_doc_draft(
            deps,
            project_id=project_id,
            draft_json=draft_json,
            color_theme=color_theme,
        )

    # ------------------------------------------------------------------
    # 단일 슬라이드 design spec 생성
    # ------------------------------------------------------------------

    @mcp.tool()
    def prepare_design_slide(
        project_id: str,
        slide_index: int,
        outline_json: str = "",
        total_slides: int = 0,
        color_theme: str = "dark",
    ) -> str:
        """Prepares the prompt + JSON schema for the CLIENT to generate ONE slide's design spec.

        No LLM call. Returns the system prompt, user prompt (with adjacent-slide
        context and DESIGN.md directives baked in), the `response_schema` the spec
        must match, and a `thinking_budget` hint. **Generate the slide spec JSON that
        conforms to `response_schema`, then call `ingest_design_slide`.**

        **Parallelize across slides**: call prepare→generate→ingest for each slide
        concurrently. Slides are independent server-side. Call
        `prepare_design_doc_draft`/`ingest_design_doc_draft` FIRST so all slides share
        one theme.

        Args:
            project_id: Project ID (required).
            slide_index: 1-based slide number to generate.
            outline_json: Full outline JSON. Optional if project_id has a saved outline.
            total_slides: Total slide count (0 = infer from outline).
            color_theme: Color theme ("dark" or "light").

        Returns:
            JSON with system_prompt, user_prompt, response_schema, slide_type,
            thinking_budget, project_id, slide_index.
        """
        return handle_prepare_design_slide(
            deps,
            project_id=project_id,
            slide_index=slide_index,
            outline_json=outline_json,
            total_slides=total_slides,
            color_theme=color_theme,
        )

    @mcp.tool()
    def ingest_design_slide(
        project_id: str,
        slide_index: int,
        spec_json: str,
        generation_context: str,
        color_theme: str = "dark",
    ) -> str:
        """Ingests the client-generated slide spec: validate, normalize, save, render, lint.

        Call AFTER prepare_design_slide with the spec JSON you generated.

        Args:
            project_id: Project ID (required).
            slide_index: 1-based slide number (same as prepare).
            spec_json: The slide spec JSON generated by the client, matching the schema.
            generation_context: Opaque token returned by prepare_design_slide.
            color_theme: Color theme ("dark" or "light").

        Returns:
            JSON with status, slide_file, slide_html_path, optional lint and overflow.

        **After ingesting ALL slides, call `finalize_design_spec` once.**
        """
        return handle_ingest_design_slide(
            deps,
            project_id=project_id,
            slide_index=slide_index,
            spec_json=spec_json,
            generation_context=generation_context,
            color_theme=color_theme,
        )

    @mcp.tool()
    def finalize_design_spec(
        project_id: str,
        overflow_json: str = "",
    ) -> str:
        """Finalizes a freshly generated deck: builds slides.html, runs deck-wide lint.

        No LLM call. Call ONCE after all slides have been ingested via
        `ingest_design_slide`. Pass the collected overflow items (if any) as JSON.

        Args:
            project_id: Project ID (required).
            overflow_json: JSON array of overflow items collected from ingest calls
                (optional, "" if none).

        Returns:
            JSON with design_spec_dir, slide_count, slides_html_path, lint, overflow.

        **IMPORTANT — Required follow-up:** call `export_html(project_id=<project_id>)`
        and share slides_html_path with the user.
        """
        return handle_finalize_design_spec(
            deps,
            project_id=project_id,
            overflow_json=overflow_json,
        )

    # ------------------------------------------------------------------
    # move / delete (LLM 불필요)
    # ------------------------------------------------------------------

    @mcp.tool()
    def move_slide(
        project_id: str,
        from_index: int,
        to_index: int,
    ) -> str:
        """Moves a slide from one position to another. No LLM call — pure file reordering.

        Reorders all related files (outline, design_spec, slide HTML) atomically.
        After this call, you must call `export_html(project_id=<project_id>)` to refresh HTML.

        Args:
            project_id: Target project ID (required)
            from_index: Current slide position (1-based).
            to_index: Desired slide position (1-based).

        Returns:
            JSON string containing project_id, slide_count, from_index, to_index.
        """
        return handle_move(
            deps,
            project_id=project_id,
            from_index=from_index,
            to_index=to_index,
        )

    @mcp.tool()
    def delete_slide(
        project_id: str,
        slide_index: int,
    ) -> str:
        """Deletes a slide. No LLM call — pure file removal + reindex.

        Args:
            project_id: Target project ID (required)
            slide_index: Slide position to delete (1-based).

        Returns:
            JSON string containing project_id and the new slide_count.

        **After this call, call `export_html(project_id=<project_id>)` to refresh HTML.**
        """
        return handle_delete(
            deps,
            project_id=project_id,
            slide_index=slide_index,
        )

    # ------------------------------------------------------------------
    # add / update 슬라이드 (prepare/ingest)
    # ------------------------------------------------------------------

    @mcp.tool()
    def prepare_slide_edit(
        project_id: str,
        action: str,
        slide_index: int = -1,
        title: str = "",
        content_summary: str = "",
        component_hint: str = "bullets",
        slide_type: str = "content",
        speaker_notes: str = "",
        color_theme: str = "dark",
    ) -> str:
        """Prepares to add or update ONE slide without changing project files.

        No LLM call. Returns the slide generation prompt, `response_schema`, and an
        immutable `edit_context`. **Generate the slide spec JSON, then call
        `ingest_slide_edit` with the SAME action, slide_index, and edit_context.**

        For narrow single-element tweaks, use `prepare_modify_component` instead.

        Args:
            project_id: Target project ID (required).
            action: "add" | "update".
            slide_index: 1-based position. add: insertion point (-1 = end). update: target.
            title: Slide title (required for add; required for update on imported projects).
            content_summary: Content description (required for add; required for update on imported).
            component_hint: Layout hint (default: "bullets").
            slide_type: "title" | "content" | "closing" | "agenda" (default: "content").
            speaker_notes: Optional speaker notes.
            color_theme: Color theme ("dark" or "light").

        Returns:
            JSON with prompts, response_schema, action, project_id, edit_context.
        """
        return handle_prepare_slide_edit(
            deps,
            project_id=project_id,
            action=action,
            slide_index=slide_index,
            title=title,
            content_summary=content_summary,
            component_hint=component_hint,
            slide_type=slide_type,
            speaker_notes=speaker_notes,
            color_theme=color_theme,
        )

    @mcp.tool()
    def ingest_slide_edit(
        project_id: str,
        action: str,
        slide_index: int,
        spec_json: str,
        edit_context: str,
        color_theme: str = "dark",
    ) -> str:
        """Ingests an add/update slide spec: validate, save (insert for add), render, lint.

        Call AFTER prepare_slide_edit with the same action/slide_index, returned
        edit_context, and your spec JSON.

        Args:
            project_id: Target project ID (required).
            action: "add" | "update" (same as prepare).
            slide_index: 1-based position (same as prepare; use the insertion point for add).
            spec_json: The slide spec JSON generated by the client.
            edit_context: Opaque token returned by prepare_slide_edit.
            color_theme: Color theme ("dark" or "light").

        Returns:
            JSON with design_spec_dir, slide_count, slide_index, slide_html_path, optional lint.

        **IMPORTANT — Required follow-up:** call `export_html(project_id=<project_id>)`.
        """
        return handle_ingest_slide_edit(
            deps,
            project_id=project_id,
            action=action,
            slide_index=slide_index,
            spec_json=spec_json,
            edit_context=edit_context,
            color_theme=color_theme,
        )

    # ------------------------------------------------------------------
    # modify_component (prepare/ingest, + lazy backfill)
    # ------------------------------------------------------------------

    @mcp.tool()
    def prepare_modify_component(
        project_id: str,
        slide_index: int,
        component_id: str,
        instruction: str,
        color_theme: str = "dark",
    ) -> str:
        """Prepares a narrow single-component edit on a content slide.

        No LLM call. Returns a generation task with `stage`:
        - `stage="modify"`: generate the ComponentModify JSON, then call
          `ingest_modify_component`.
        - `stage="backfill"` (imported slides with no design_doc): generate the backfill
          JSON, call `ingest_backfill` to get `available_components`, then call
          `prepare_modify_component` again with a valid component_id.

        Use for narrow changes like "make the LLM box red". For broader changes use
        `prepare_slide_edit(action="update")`.

        Args:
            project_id: Target project ID (required).
            slide_index: 1-based slide position.
            component_id: Target component id from design_doc.layout leaf.
            instruction: Natural-language description of the change.
            color_theme: Color theme ("dark" or "light").

        Returns:
            JSON with system_prompt, user_prompt, response_schema, stage, project_id,
            slide_index, component_id.
        """
        return handle_prepare_modify_component(
            deps,
            project_id=project_id,
            slide_index=slide_index,
            component_id=component_id,
            instruction=instruction,
            color_theme=color_theme,
        )

    @mcp.tool()
    def ingest_backfill(
        project_id: str,
        slide_index: int,
        backfill_json: str,
    ) -> str:
        """Ingests the design_doc backfill for an imported slide (stage="backfill").

        Call AFTER a prepare_modify_component that returned stage="backfill".
        Saves the backfilled design_doc and returns `available_components`. Pick a
        component id and call `prepare_modify_component` again.

        Args:
            project_id: Target project ID (required).
            slide_index: 1-based slide position.
            backfill_json: The backfill JSON generated by the client.

        Returns:
            JSON with status="backfilled", available_components.
        """
        return handle_ingest_backfill(
            deps,
            project_id=project_id,
            slide_index=slide_index,
            backfill_json=backfill_json,
        )

    @mcp.tool()
    def ingest_modify_component(
        project_id: str,
        slide_index: int,
        component_id: str,
        modify_json: str,
        edit_context: str,
        color_theme: str = "dark",
    ) -> str:
        """Ingests a single-component edit: validate, apply to exactly one element, save, render.

        Call AFTER a prepare_modify_component that returned stage="modify".

        Args:
            project_id: Target project ID (required).
            slide_index: 1-based slide position.
            component_id: Target component id (same as prepare).
            modify_json: The ComponentModify JSON generated by the client.
            edit_context: Opaque context returned by prepare_modify_component.
            color_theme: Color theme ("dark" or "light").

        Returns:
            JSON with modified_element, slide_html_path, optional lint.

        **After this call, share the returned slide_html_path with the user.**
        """
        return handle_ingest_modify_component(
            deps,
            project_id=project_id,
            slide_index=slide_index,
            component_id=component_id,
            modify_json=modify_json,
            edit_context=edit_context,
            color_theme=color_theme,
        )

    # ------------------------------------------------------------------
    # review (prepare/ingest, 슬라이드 단위)
    # ------------------------------------------------------------------

    @mcp.tool()
    def prepare_review(
        project_id: str,
        slide_index: int,
    ) -> str:
        """Prepares a design-rule review task for ONE slide (mechanical lint baked in as a hint).

        No LLM call. Returns the review prompt + `response_schema`. **Generate the
        review JSON, then call `ingest_review`.** Review slides in parallel.

        Args:
            project_id: Target project ID (required).
            slide_index: 1-based slide position.

        Returns:
            JSON with system_prompt, user_prompt, response_schema, project_id, slide_index.
        """
        return handle_prepare_review(
            deps,
            project_id=project_id,
            slide_index=slide_index,
        )

    @mcp.tool()
    def ingest_review(
        project_id: str,
        slide_index: int,
        review_json: str,
        review_context: str,
    ) -> str:
        """Ingests a slide's review result: validate, return issues (report-only).

        Call AFTER prepare_review. Does NOT auto-regenerate. If has_high_severity,
        the response includes `fix_feedback` — pass it into `prepare_slide_edit(
        action="update")` to regenerate the slide with the review feedback applied.

        Args:
            project_id: Target project ID (required).
            slide_index: 1-based slide position.
            review_json: The review result JSON generated by the client.
            review_context: Opaque token returned by prepare_review.

        Returns:
            JSON with has_high_severity, issues, optional fix_feedback.
        """
        return handle_ingest_review(
            deps,
            project_id=project_id,
            slide_index=slide_index,
            review_json=review_json,
            review_context=review_context,
        )
