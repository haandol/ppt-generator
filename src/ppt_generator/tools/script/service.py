"""실제 덱에서 대본 문맥을 만들고 노트만 갱신한다."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ppt_generator.interfaces.handoff import build_llm_task
from ppt_generator.interfaces.output_models.script import SpeakerScriptOutput
from ppt_generator.interfaces.prompts import SPEAKER_SCRIPT_SYSTEM_PROMPT
from ppt_generator.tools.design.edit_context import (
    ProjectSnapshot,
    decode_signed_context,
    encode_signed_context,
    project_edit_lock,
)
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.project.slide_file_store import slide_filename


class SpeakerScriptService:
    """클라이언트 작성 대본을 기존 노트 저장 형식과 연결한다."""

    def prepare(
        self,
        project_service: ProjectService,
        project_id: str,
        brief: str = "",
    ) -> dict[str, Any]:
        """순서·화면·근거·기존 노트를 고정한 준비 응답을 만든다."""
        _, project_dir = project_service.resolve_existing_project_dir(project_id)
        with project_edit_lock(project_dir):
            deck = self._load_deck(project_service, project_dir)
            schema = SpeakerScriptOutput.model_json_schema()
            return build_llm_task(
                system_prompt=SPEAKER_SCRIPT_SYSTEM_PROMPT,
                user_prompt=json.dumps(
                    {"brief": brief, **deck}, ensure_ascii=False, indent=2
                ),
                response_schema=schema,
                project_id=project_id,
                script_context=encode_signed_context(
                    {
                        "kind": "speaker_script",
                        "version": 1,
                        "project_id": project_id,
                        "fingerprint": self._fingerprint(deck),
                        "schema_fingerprint": self._fingerprint(schema),
                    },
                    project_dir,
                ),
            )

    def ingest(
        self,
        project_service: ProjectService,
        project_id: str,
        script_json: str,
        script_context: str,
    ) -> dict[str, Any]:
        """잘못된 제출을 모두 검증한 후 노트와 낭독 문서를 함께 저장한다."""
        output = SpeakerScriptOutput.model_validate_json(script_json)
        _, project_dir = project_service.resolve_existing_project_dir(project_id)
        with project_edit_lock(project_dir):
            context = decode_signed_context(script_context, project_dir)
            if (
                context.get("kind") != "speaker_script"
                or context.get("version") != 1
                or context.get("project_id") != project_id
            ):
                raise ValueError("script_context does not match speaker script request")
            if context.get("schema_fingerprint") != self._fingerprint(
                SpeakerScriptOutput.model_json_schema()
            ):
                raise ValueError("Stale script_context: response schema changed")
            deck = self._load_deck(project_service, project_dir)
            if context.get("fingerprint") != self._fingerprint(deck):
                raise ValueError("Stale script_context: deck changed; prepare again")
            expected = set(range(1, len(deck["slides"]) + 1))
            if {script.slide_index for script in output.scripts} != expected:
                raise ValueError("speaker script must cover every slide exactly once")
            notes = {
                script.slide_index: script.speaker_notes for script in output.scripts
            }
            with ProjectSnapshot(project_dir) as snapshot:
                for slide in deck["slides"]:
                    index = slide["slide_index"]
                    slide["design_spec"]["speaker_notes"] = notes[index]
                    self._write_json(
                        project_dir / "design_spec" / slide_filename(index - 1),
                        slide["design_spec"],
                    )
                    if slide["outline"] is not None:
                        slide["outline"]["speaker_notes"] = notes[index]
                        self._write_json(
                            project_dir / "outline" / slide_filename(index - 1),
                            slide["outline"],
                        )
                result = self._export(project_id, project_dir, deck)
                snapshot.commit()
            return {**result, "export_required": True}

    def export(
        self, project_service: ProjectService, project_id: str
    ) -> dict[str, Any]:
        """현재 저장된 노트로 낭독 문서를 다시 생성한다."""
        _, project_dir = project_service.resolve_existing_project_dir(project_id)
        with project_edit_lock(project_dir):
            return self._export(
                project_id, project_dir, self._load_deck(project_service, project_dir)
            )

    @staticmethod
    def _load_deck(
        project_service: ProjectService, project_dir: Path
    ) -> dict[str, Any]:
        """화면의 원본 JSON을 보존해 노트 이외의 값을 변경하지 않는다."""
        count = project_service.design_spec_store.validate_contiguous_design_spec(
            project_dir
        )
        if not count:
            raise ValueError("Generate or import a design spec before writing a script")
        try:
            outline = json.loads(project_service.load_outline(project_dir))["slides"]
        except FileNotFoundError:
            if (project_dir / "outline").exists():
                raise ValueError("outline is empty; repair the deck before scripting")
            outline = None
        if outline is not None:
            names = sorted(
                path.name for path in (project_dir / "outline").glob("slide_*.json")
            )
            expected = [slide_filename(i) for i in range(count)]
            if len(outline) != count or names != expected:
                raise ValueError("outline and design spec slide order/count must match")
        slides = []
        for i in range(count):
            spec = json.loads(
                (project_dir / "design_spec" / slide_filename(i)).read_text(
                    encoding="utf-8"
                )
            )
            item = outline[i] if outline is not None else None
            topic = (spec.get("design_doc") or {}).get("topic", "")
            title = (item or {}).get("title") or topic or f"Slide {i + 1}"
            slides.append(
                {
                    "slide_index": i + 1,
                    "title": title,
                    "design_spec": spec,
                    "outline": item,
                }
            )
        return {
            "presentation_context": asdict(project_service.load_metadata(project_dir)),
            "design_intent": project_service.design_spec_store.load_design_doc_md(
                project_dir
            )
            or "",
            "slides": slides,
        }

    @staticmethod
    def _fingerprint(value: dict[str, Any]) -> str:
        """순서와 발표 조건을 포함한 준비 입력을 결정론적으로 식별한다."""
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    @staticmethod
    def _export(
        project_id: str, project_dir: Path, deck: dict[str, Any]
    ) -> dict[str, Any]:
        """노트 원문과 줄바꿈을 보존해 현재 순서로 Markdown을 만든다."""
        blocks = []
        counts = []
        for slide in deck["slides"]:
            notes = slide["design_spec"].get("speaker_notes", "")
            title = " ".join(str(slide["title"]).splitlines())
            blocks.append(f"## Slide {slide['slide_index']} — {title}\n\n{notes}\n\n")
            counts.append(
                {"slide_index": slide["slide_index"], "word_count": len(notes.split())}
            )
        path = project_dir / "speaker-script.md"
        path.write_text("".join(blocks), encoding="utf-8")
        return {
            "project_id": project_id,
            "script_path": str(path),
            "slide_count": len(blocks),
            "word_counts": counts,
            "word_count_method": "whitespace-separated tokens; not a multilingual timing estimate",
        }
