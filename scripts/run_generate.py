#!/usr/bin/env python3
"""note.md 기반 PPT 생성 스크립트.

프로젝트의 서비스 레이어를 직접 호출하여 5단계 파이프라인을 실행합니다.
1. generate_outline - 아웃라인 생성
2. generate_script - 스크립트 생성 (아웃라인 기반 speaker_notes 채우기)
3. generate_images - 이미지 생성
4. export_html - HTML 슬라이드 내보내기 (F4)
5. export_pptx - PPTX 내보내기 (F6)

--project-dir 옵션으로 결과물을 디렉토리에 저장할 수 있습니다.
"""

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

# 프로젝트 소스를 임포트 경로에 추가
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ppt_generator.di.container import DIContainer
from ppt_generator.interfaces.schemas import (
    ExportPptxRequest,
    ImageRequest,
    OutlineRequest,
    ProjectMetadata,
    ScriptRequest,
    SlidesRequest,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

NOTE_TOPIC = """에이전트 시대의 개발자를 위한 AI 기초 - LLM, 도구, 에이전트, MCP, 파인튜닝, RAG, 그리고 실시간 데이터 파이프라인

아래 내용을 45분 발표 분량으로 자연스럽게 풀어서 작성해주세요. 청중은 에이전트를 잘 모르지만 앞으로 개발해야 할 가능성이 높은 서버/클라이언트 개발자입니다. 엄밀한 정확성보다 명확한 이해를 우선합니다.

1. LLM은 다음 토큰을 출력하는 함수
- 모든 LLM은 하나 이상의 토큰을 입력받아 다음 토큰 하나를 반환하는 함수
- "I love you" 출력 과정: "I" → 토큰화(3차원 숫자) → LLM 입력 → 출력 토큰 → "love" 텍스트, "I love" → 토큰화 → LLM → "you", EOS 나올 때까지 반복
- 입력 내용 = 컨텍스트, 컨텍스트에 따라 다음 토큰이 확률적으로 결정
- 원하는 결과를 얻으려면 컨텍스트를 잘 관리해야 함
- 핵심: LLM은 토큰 입력 → 토큰 출력하는 함수

2. 도구(Tool)란 외부 함수 호출을 텍스트로 정형화한 것
- LLM은 텍스트만 입출력하는데, 웹 검색 같은 외부 기능을 어떻게 쓸까?
- LLM 시작 시 컨텍스트에: 도구 존재 사실, 필요한 파라미터(JSON), 사용 조건을 포함
- LLM이 필요하다고 판단하면 JSON 형태로 파라미터를 출력
- 모니터링 후 JSON 파싱 → 함수 호출 → 결과를 컨텍스트 뒤에 추가 → EOS까지 출력 계속

3. 에이전트란 LLM이 도구를 통해 외부 리소스를 호출할 수 있게 구성한 애플리케이션
- 에이전트 = LLM + 도구를 통한 외부 리소스 접근
- 키로, 커서 등의 개발용 에이전트가 대표 사례
- 최신 에이전트도 기본 원리(토큰 입출력 + 도구 호출)는 동일

4. MCP는 도구를 별도 서버에 두고 호출하는 방법을 정의한 프로토콜
- 도구가 에이전트에 종속되면: 언어/런타임 제약, 에이전트 팀이 모든 연동을 담당해야 하는 부담
- MCP로 도구를 외부 서버로 분리: 에이전트는 LLM에 집중, 외부 리소스 담당팀이 도구 관리
- MCP = 원격 도구 서버에서 정보를 가져오고 호출하는 방법을 정의한 명세

5. 파인튜닝과 RAG는 같은 문제를 푸는 다른 방법
- LLM에는 컷오프 날짜가 있어서 최신 정보가 없음
- 파인튜닝: LLM에 직접 데이터 학습, GPU 필요, 추가 서빙 비용 발생
- RAG: 외부 정보를 동적으로 가져와 컨텍스트에 삽입, 자주 업데이트되는 데이터에 유리
- 파인튜닝 장점: 프롬프트가 간결해짐 / RAG 장점: 실시간 데이터 반영 가능

6. 에이전트 시대에 실시간 데이터 파이프라인이 중요한 이유
- 에이전트 동작에 필요한 데이터는 자주 업데이트되므로 RAG가 일반적
- 에이전트 성능 = LLM 성능 + 프롬프트보다 접근 가능한 데이터의 범위와 품질이 더 중요
- 고품질 데이터를 적시에 접근할 수 있는 파이프라인이 없으면 에이전트 성능 향상 불가

7. AWS는 에이전트 개발 플랫폼 회사
- 에이전트 프레임워크, 운영, RAG 지식베이스, 실시간 데이터 파이프라인 모두 제공
- 이후 발표에서 세부 내용을 다룰 예정"""

NUM_SLIDES = 9


def main() -> None:
    parser = argparse.ArgumentParser(description="PPT 생성 파이프라인")
    parser.add_argument("--project-dir", default="", help="결과물 저장 디렉토리")
    args = parser.parse_args()

    container = DIContainer(project_root=Path(__file__).parent)
    project_dir = Path(args.project_dir) if args.project_dir else None

    if project_dir:
        project_dir.mkdir(parents=True, exist_ok=True)
        container.project_service.save_metadata(
            project_dir,
            ProjectMetadata(topic=NOTE_TOPIC, num_slides=NUM_SLIDES),
        )

    # Step 1: 아웃라인 생성
    logger.info("=== Step 1: 아웃라인 생성 시작 ===")
    outline_request = OutlineRequest(topic=NOTE_TOPIC, num_slides=NUM_SLIDES)
    outline_response = container.outline_service.generate(outline_request)
    logger.info("아웃라인 생성 완료 (슬라이드 %d장)", len(outline_response.slides))
    outline_json = json.dumps(asdict(outline_response), ensure_ascii=False, indent=2)
    if project_dir:
        container.project_service.save_outline(project_dir, outline_json)
        container.project_service.update_step(project_dir, "outline")

    # Step 2: 스크립트 생성 (아웃라인 기반 speaker_notes 채우기)
    logger.info("=== Step 2: 스크립트 생성 시작 ===")
    script_request = ScriptRequest(outline=outline_response)
    script_response = container.script_service.generate(script_request)
    logger.info("스크립트 생성 완료 (슬라이드 %d장)", len(script_response.slides))
    script_json = json.dumps(
        {"slides": [asdict(s) for s in script_response.slides]},
        ensure_ascii=False,
        indent=2,
    )
    if project_dir:
        container.project_service.save_script(project_dir, script_json)
        container.project_service.update_step(project_dir, "script")

    # speaker_notes가 채워진 슬라이드 목록 사용
    slides = script_response.slides

    # Step 3: 이미지 생성
    logger.info("=== Step 3: 이미지 생성 시작 ===")
    image_request = ImageRequest(slides=slides)
    image_response = container.image_service.generate(image_request)
    logger.info("이미지 생성 완료 (%d개)", len(image_response.images))
    images_json = json.dumps(asdict(image_response), ensure_ascii=False, indent=2)
    if project_dir:
        container.project_service.save_images(project_dir, images_json)
        container.project_service.update_step(project_dir, "images")

    # Step 4: HTML 슬라이드 생성 (F4)
    logger.info("=== Step 4: HTML 슬라이드 생성 시작 ===")
    image_paths: dict[int, str] = {}
    for img in image_response.images:
        image_paths[img.slide_index] = img.image_path
    slides_request = SlidesRequest(slides=slides, image_paths=image_paths)
    slides_response = container.slides_service.generate(slides_request)
    logger.info("HTML 슬라이드 생성 완료: session_id=%s", slides_response.session_id)
    if project_dir:
        container.project_service.save_slides_html(project_dir, slides_response.session_id, slides_response.html)
        container.project_service.update_step(project_dir, "slides")

    # Step 5: PPTX 내보내기 (F6)
    logger.info("=== Step 5: PPTX 내보내기 시작 ===")
    export_request = ExportPptxRequest(session_id=slides_response.session_id)
    export_response = container.export_service.export(export_request)
    logger.info("=== PPTX 내보내기 완료! ===")
    if project_dir:
        container.project_service.save_pptx(project_dir, export_response.pptx_path)
        container.project_service.update_step(project_dir, "pptx")

    print(f"\n생성된 파일: {export_response.pptx_path}")
    if project_dir:
        print(f"프로젝트 디렉토리: {project_dir}")


if __name__ == "__main__":
    main()
