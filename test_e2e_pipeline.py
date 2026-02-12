"""전체 파이프라인 E2E 테스트 스크립트.

note.md를 기반으로 아웃라인 → 스크립트 → 슬라이드 → PPTX 내보내기까지 실행.
"""

import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ppt_generator.di.container import DIContainer
from ppt_generator.interfaces.schemas import (
    ExportPptxRequest,
    OutlineRequest,
    OutlineResponse,
    ScriptRequest,
)


def main():
    note = Path.home() / "Documents" / "note.md"
    topic = note.read_text(encoding="utf-8")

    container = DIContainer()
    output_dir = Path(__file__).parent / "test_output"
    output_dir.mkdir(exist_ok=True)

    # --- Step 1: 아웃라인 생성 ---
    print("=" * 60)
    print("[Step 1] 아웃라인 생성 중...")
    t0 = time.time()
    outline_request = OutlineRequest(topic=topic, num_slides=9)
    outline_response = container.outline_service.generate(outline_request)
    t1 = time.time()

    print(f"  완료! ({t1 - t0:.1f}s)")
    print(f"  슬라이드 수: {len(outline_response.slides)}")
    for i, slide in enumerate(outline_response.slides):
        print(f"    [{i}] {slide.title} ({slide.component_hint})")

    outline_json = json.dumps(
        {"slides": [asdict(s) for s in outline_response.slides]},
        ensure_ascii=False,
        indent=2,
    )
    (output_dir / "01_outline.json").write_text(outline_json, encoding="utf-8")
    print(f"  -> {output_dir / '01_outline.json'}")

    # --- Step 2: 스크립트 생성 ---
    print()
    print("=" * 60)
    print("[Step 2] 스크립트 생성 중...")
    t0 = time.time()
    script_request = ScriptRequest(outline=outline_response)
    script_response = container.script_service.generate(script_request)
    t1 = time.time()

    print(f"  완료! ({t1 - t0:.1f}s)")
    for i, slide in enumerate(script_response.slides):
        notes_preview = slide.speaker_notes[:60] + "..." if len(slide.speaker_notes) > 60 else slide.speaker_notes
        print(f"    [{i}] {slide.title}: {notes_preview}")

    script_json = json.dumps(
        {"slides": [asdict(s) for s in script_response.slides]},
        ensure_ascii=False,
        indent=2,
    )
    (output_dir / "02_script.json").write_text(script_json, encoding="utf-8")
    print(f"  -> {output_dir / '02_script.json'}")

    # --- Step 3: 슬라이드 HTML 생성 ---
    print()
    print("=" * 60)
    print("[Step 3] 슬라이드 HTML 생성 중...")
    t0 = time.time()
    slides_response = container.slides_service.generate(slides=script_response.slides)
    t1 = time.time()

    print(f"  완료! ({t1 - t0:.1f}s)")
    print(f"  session_id: {slides_response.session_id}")
    print(f"  HTML 크기: {len(slides_response.html)} bytes")

    (output_dir / "03_slides.html").write_text(slides_response.html, encoding="utf-8")
    print(f"  -> {output_dir / '03_slides.html'}")

    # --- Step 4: PPTX 내보내기 ---
    print()
    print("=" * 60)
    print("[Step 4] PPTX 내보내기 중...")
    t0 = time.time()
    export_request = ExportPptxRequest(session_id=slides_response.session_id)
    export_response = container.export_service.export(export_request, output_dir=output_dir)
    t1 = time.time()

    pptx_path = Path(export_response.pptx_path)
    print(f"  완료! ({t1 - t0:.1f}s)")
    print(f"  PPTX 크기: {pptx_path.stat().st_size / 1024:.1f} KB")
    print(f"  -> {pptx_path}")

    # --- 결과 요약 ---
    print()
    print("=" * 60)
    print("[결과 요약]")
    print(f"  아웃라인: {output_dir / '01_outline.json'}")
    print(f"  스크립트: {output_dir / '02_script.json'}")
    print(f"  HTML:     {output_dir / '03_slides.html'}")
    print(f"  PPTX:     {pptx_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
