import json
import logging
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.constants import (
    DEFAULT_AUDIENCE_TYPE,
    DEFAULT_PRESENTATION_MINUTES,
    MAX_NUM_SLIDES,
    MAX_PRESENTATION_MINUTES,
    MIN_NUM_SLIDES,
    MIN_PRESENTATION_MINUTES,
    VALID_AUDIENCE_TYPES,
)
from ppt_generator.interfaces.schemas import OutlineRequest, ProjectMetadata
from ppt_generator.tools.outline.service import OutlineService
from ppt_generator.tools.project.service import ProjectService

logger = logging.getLogger(__name__)


def register_outline_tools(
    mcp: FastMCP, outline_service: OutlineService, project_service: ProjectService
) -> None:
    def _build_request(
        topic: str,
        purpose: str,
        audience_type: str,
        presentation_minutes: int,
        num_slides: int,
        presenter_name: str,
        presenter_title: str,
        presenter_org: str,
    ) -> OutlineRequest:
        if audience_type not in VALID_AUDIENCE_TYPES:
            audience_type = DEFAULT_AUDIENCE_TYPE
        presentation_minutes = max(
            MIN_PRESENTATION_MINUTES,
            min(MAX_PRESENTATION_MINUTES, presentation_minutes),
        )
        if num_slides <= 0:
            num_slides = max(
                MIN_NUM_SLIDES, min(MAX_NUM_SLIDES, presentation_minutes // 2 + 2)
            )
        else:
            num_slides = max(MIN_NUM_SLIDES, min(MAX_NUM_SLIDES, num_slides))
        return OutlineRequest(
            topic=topic,
            num_slides=num_slides,
            audience_type=audience_type,
            presentation_minutes=presentation_minutes,
            purpose=purpose,
            presenter_name=presenter_name,
            presenter_title=presenter_title,
            presenter_org=presenter_org,
        )

    @mcp.tool()
    def prepare_outline(
        topic: str,
        purpose: str = "",
        audience_type: str = DEFAULT_AUDIENCE_TYPE,
        presentation_minutes: int = DEFAULT_PRESENTATION_MINUTES,
        num_slides: int = 0,
        presenter_name: str = "",
        presenter_title: str = "",
        presenter_org: str = "",
        project_id: str = "",
    ) -> str:
        """Prepares the prompt + JSON schema for the CLIENT to generate a slide outline.

        This tool does NOT call an LLM. It normalizes inputs, creates/loads the
        project, saves the presentation metadata, and returns the system prompt,
        user prompt, and the JSON schema the outline must conform to. **You (the
        client) then generate the outline JSON that follows `response_schema`, and
        pass it to `ingest_outline`.**

        **IMPORTANT — Required checks before calling:**
        Before calling this tool, you must ask the user to confirm the following items:
        1. **Presentation purpose** (purpose): e.g., "internal tech sharing", "customer proposal", "conference talk"
        2. **Presentation time** (presentation_minutes): how many minutes the presentation will be
        3. **Audience type** (audience_type): general/technical/executive
        4. **Presenter info** (presenter_name, presenter_title, presenter_org): presenter_org can be empty if not applicable.
        If the user has not explicitly provided these, never use default values — always ask.

        Args:
            topic: Presentation topic (e.g., "2024 Cloud Computing Trends")
            purpose: Presentation purpose. Must confirm with the user before setting.
            audience_type: "general" | "technical" | "executive". Must confirm with the user.
            presentation_minutes: 3~60 min. Must confirm with the user.
            num_slides: Recommended number of slides (0 = auto-calculate from presentation time).
            presenter_name: Presenter's name. Must confirm with the user.
            presenter_title: Presenter's job title. Must confirm with the user.
            presenter_org: Presenter's organization (can be empty). Must confirm with the user.
            project_id: Project ID (auto-generated if not specified)

        Returns:
            JSON string with: system_prompt, user_prompt, response_schema, project_id.

        **Next step:** Generate the outline JSON matching `response_schema`, then call
        `ingest_outline(project_id=<project_id>, outline_json=<your JSON>)`.
        """
        request = _build_request(
            topic,
            purpose,
            audience_type,
            presentation_minutes,
            num_slides,
            presenter_name,
            presenter_title,
            presenter_org,
        )

        project_id, project_dir = project_service.resolve_project_dir(project_id)
        project_service.save_metadata(
            project_dir,
            ProjectMetadata(
                topic=request.topic,
                num_slides=request.num_slides,
                steps_completed={},
                audience_type=request.audience_type,
                presentation_minutes=request.presentation_minutes,
                purpose=request.purpose,
                presenter_name=request.presenter_name,
                presenter_title=request.presenter_title,
                presenter_org=request.presenter_org,
            ),
        )

        task = outline_service.prepare(request)
        task["project_id"] = project_id
        logger.info(
            "outline prepare 완료 (topic=%s, num_slides=%d, project_id=%s)",
            topic,
            request.num_slides,
            project_id,
        )
        return json.dumps(task, ensure_ascii=False)

    @mcp.tool()
    def ingest_outline(project_id: str, outline_json: str) -> str:
        """Ingests the client-generated outline JSON: validates, injects presenter info, saves.

        Call this AFTER `prepare_outline`, passing the outline JSON you generated
        following the returned `response_schema`.

        **IMPORTANT: After ingesting, you must show the outline to the user and get
        confirmation** (number of slides, titles, content composition) before
        proceeding to the next step (prepare_design_slide). If the user requests
        changes, incorporate them and call `ingest_outline` again with the revised JSON.

        Args:
            project_id: Project ID returned by prepare_outline (required).
            outline_json: The outline JSON generated by the client, matching the
                schema from prepare_outline ({"slides": [...]}).

        Returns:
            JSON string containing outline_path and project_id.
        """
        _, project_dir = project_service.resolve_project_dir(project_id)
        metadata = project_service.load_metadata(project_dir)
        request = OutlineRequest(
            topic=metadata.topic,
            num_slides=metadata.num_slides,
            audience_type=metadata.audience_type,
            presentation_minutes=metadata.presentation_minutes,
            purpose=metadata.purpose,
            presenter_name=metadata.presenter_name,
            presenter_title=metadata.presenter_title,
            presenter_org=metadata.presenter_org,
        )

        response = outline_service.ingest(outline_json, request)
        actual_num_slides = len(response.slides)
        result = json.dumps(asdict(response), ensure_ascii=False, indent=2)

        # 실제 생성된 슬라이드 수로 메타데이터 갱신
        metadata.num_slides = actual_num_slides
        project_service.save_metadata(project_dir, metadata)
        project_service.save_outline(project_dir, result)
        project_service.update_step(project_dir, "outline")

        logger.info("outline ingest 완료 (slides=%d)", actual_num_slides)
        return json.dumps(
            {
                "outline_path": str(project_dir / "outline"),
                "project_id": project_id,
            },
            ensure_ascii=False,
        )
