"""발표 대본 스킬을 위한 MCP 도구."""

import json

from mcp.server.fastmcp import FastMCP

from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.script.service import SpeakerScriptService


def register_script_tools(
    mcp: FastMCP,
    script_service: SpeakerScriptService,
    project_service: ProjectService,
) -> None:
    @mcp.tool()
    def prepare_speaker_script(project_id: str, brief: str = "") -> str:
        """Prepares a deck-wide spoken script task for the ppt-speaker-script skill.

        Use after design or PPTX import. Returns actual slide specs, existing notes,
        outline evidence when available, presentation context, response_schema, and
        script_context. The client writes the script; the server never calls an LLM.

        Args:
            project_id: Existing project with a completed design spec.
            brief: User's language, audience, time, delivery, and Q&A preferences.
        """
        return json.dumps(
            script_service.prepare(project_service, project_id, brief),
            ensure_ascii=False,
        )

    @mcp.tool()
    def ingest_speaker_script(
        project_id: str, script_json: str, script_context: str
    ) -> str:
        """Validates and saves notes only, preserving the deck's visual content.

        Rejects stale context, missing/duplicate/out-of-range slides, and schema
        violations before saving. Synchronizes existing outline notes and writes
        speaker-script.md from the same source. Export HTML/PPTX at the final
        checkpoint to refresh those artifacts.

        Args:
            project_id: Same project used in prepare_speaker_script.
            script_json: JSON matching the response_schema returned by prepare.
            script_context: Opaque context returned by that prepare call, unchanged.
        """
        return json.dumps(
            script_service.ingest(
                project_service, project_id, script_json, script_context
            ),
            ensure_ascii=False,
        )

    @mcp.tool()
    def export_speaker_script(project_id: str) -> str:
        """Exports speaker-script.md from current saved notes without generation.

        Call again at the stable checkpoint after slide edits, moves, or deletion.
        Preserves slide order and the notes' meaningful line breaks.

        Args:
            project_id: Existing generated or imported project.
        """
        return json.dumps(
            script_service.export(project_service, project_id), ensure_ascii=False
        )
