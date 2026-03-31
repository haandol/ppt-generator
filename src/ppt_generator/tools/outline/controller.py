import json
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
from ppt_generator.interfaces.utils import format_token_usage
from ppt_generator.tools.outline.service import OutlineService
from ppt_generator.tools.project.service import ProjectService


def register_outline_tools(mcp: FastMCP, outline_service: OutlineService, project_service: ProjectService) -> None:
    @mcp.tool()
    def generate_outline(
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
        """Generates a slide outline JSON based on the given topic.

        Analyzes the core content of the topic and generates a structured outline
        including per-slide titles, content summaries, and component hints.
        The outline determines only the structure; design is decided in the subsequent HTML slide generation step.

        **IMPORTANT — Required checks before calling:**
        Before calling this tool, you must ask the user to confirm the following items:
        1. **Presentation purpose** (purpose): What is the purpose of the presentation (e.g., "internal tech sharing", "customer proposal", "conference talk")
        2. **Presentation time** (presentation_minutes): How many minutes the presentation will be
        3. **Audience type** (audience_type): Who the audience is (general/technical/executive)
        4. **Presenter info** (presenter_name, presenter_title, presenter_org): Name, job title, and organization of the presenter. presenter_org can be empty if not applicable.
        If the user has not explicitly provided these, never use default values — always ask.

        **IMPORTANT: After generating the outline, you must show the result to the user and get confirmation.**
        Confirm that the user is satisfied with the outline structure (number of slides, titles, content composition, etc.)
        before proceeding to the next step (generate_script).
        If the user requests changes, incorporate the modifications and call generate_outline again.

        Args:
            topic: Presentation topic (e.g., "2024 Cloud Computing Trends")
            purpose: Presentation purpose (e.g., "internal tech sharing", "customer proposal", "conference talk"). Must confirm with the user before setting.
            audience_type: Audience type — "general", "technical", "executive". Must confirm with the user before setting.
            presentation_minutes: Presentation duration in minutes. 3~60 min. Must confirm with the user before setting.
            num_slides: Recommended number of slides (0 = auto-calculate based on presentation time: 1 slide per 1~2 min). Actual count may differ to ensure one topic per slide.
            presenter_name: Presenter's name (e.g., "DongGyun Lee"). Must confirm with the user before setting.
            presenter_title: Presenter's job title (e.g., "Solutions Architect"). Must confirm with the user before setting.
            presenter_org: Presenter's organization (e.g., "Amazon Web Services"). Can be empty if not applicable. Must confirm with the user before setting.
            project_id: Project ID (auto-generated if not specified)

        Returns:
            JSON string containing outline_path and project_id
        """
        if audience_type not in VALID_AUDIENCE_TYPES:
            audience_type = DEFAULT_AUDIENCE_TYPE
        presentation_minutes = max(MIN_PRESENTATION_MINUTES, min(MAX_PRESENTATION_MINUTES, presentation_minutes))
        if num_slides <= 0:
            num_slides = max(MIN_NUM_SLIDES, min(MAX_NUM_SLIDES, presentation_minutes // 2 + 2))
        else:
            num_slides = max(MIN_NUM_SLIDES, min(MAX_NUM_SLIDES, num_slides))
        request = OutlineRequest(
            topic=topic,
            num_slides=num_slides,
            audience_type=audience_type,
            presentation_minutes=presentation_minutes,
            purpose=purpose,
            presenter_name=presenter_name,
            presenter_title=presenter_title,
            presenter_org=presenter_org,
        )
        response = outline_service.generate(request)
        actual_num_slides = len(response.slides)
        result = json.dumps(asdict(response), ensure_ascii=False, indent=2)

        project_id, project_dir = project_service.resolve_project_dir(project_id)
        project_service.save_metadata(
            project_dir,
            ProjectMetadata(
                topic=topic,
                num_slides=actual_num_slides,
                steps_completed={},
                audience_type=audience_type,
                presentation_minutes=presentation_minutes,
                purpose=purpose,
                presenter_name=presenter_name,
                presenter_title=presenter_title,
                presenter_org=presenter_org,
            ),
        )
        project_service.save_outline(project_dir, result)
        project_service.update_step(project_dir, "outline")

        resp: dict = {
            "outline_path": str(project_dir / "outline"),
            "project_id": project_id,
        }
        usage = format_token_usage(outline_service.last_token_usage)
        if usage:
            resp["token_usage"] = usage
        return json.dumps(resp, ensure_ascii=False)
