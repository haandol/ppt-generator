"""PptxSlideSpec 디자인 lint — 위반 감지 + 기계적 정리.

강제 수정(보정)은 하지 않는다. 디자인 규칙 위반을 감지하여 리포트하고,
기계적 정리(빈 textbox 제거)만 spec에 적용한다.

규칙 구현은 lint_rules/ 패키지에 규칙별 파일로 분리되어 있다.

결정 13b — `lint_slide_spec(stop_on_layer_error=True)` 가 layer 별
단계적 검증을 수행한다. layout → section → cross → content 순으로 검사하다가
어느 layer 에 severity="error" 위반이 나오면 그 다음 layer 검사를 중단한다.
거시 위반의 신호가 미시 노이즈에 가려지지 않게 한다.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from ppt_generator.interfaces.schemas import PptxSlideSpec, PptxTextBox
from ppt_generator.interfaces.spec_utils.lint_rules import (
    ALL_RULES,
    RULES_BY_LAYER,
    RULES_BY_PROFILE,
)
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintResult,
    LintViolation,
    SlideLintResult,
    layer_for_rule,
)

logger = logging.getLogger(__name__)

# 단계적 lint 진행 순서. 결정 13a — 거시(Layout) → 의미(Section) →
# 계층 간 link(Cross) → 미시 픽셀(Content).
_LAYER_ORDER: tuple[str, ...] = ("layout", "section", "cross", "content")


def _run_rules(
    rules: list, spec: PptxSlideSpec, slide_index: int, target: SlideLintResult
) -> None:
    for rule in rules:
        try:
            rule(spec, target)
        except Exception:
            # 한 규칙의 버그가 다른 규칙 결과를 가리지 않도록 격리.
            logger.error(
                "lint rule %s raised on slide[%d] (textboxes=%d shapes=%d) — "
                "skipping this rule",
                getattr(rule, "__name__", repr(rule)),
                slide_index,
                len(spec.textboxes),
                len(spec.shapes),
                exc_info=True,
            )


def lint_slide_spec(
    spec: PptxSlideSpec,
    slide_index: int = 1,
    layers: list[str] | None = None,
    stop_on_layer_error: bool = False,
    profile: str = "generation",
) -> SlideLintResult:
    """단일 슬라이드를 lint한다. 위반을 감지하되 수정하지 않는다.

    Args:
        spec: 검사할 슬라이드
        slide_index: 슬라이드 번호 (1-based)
        layers: 5단 계층 중 검사할 layer 목록 (예: ["layout"], ["section"]).
            None 이면 모든 layer 검사. layer 별 단계적 lint 호출 시 사용.
        stop_on_layer_error: True 면 layout → section → cross → content 순으로
            layer 별 검사를 진행하다가 어느 layer 에 severity="error" 위반이
            발견되면 다음 layer 검사를 중단한다. 거시 위반이 미시 노이즈에
            가려지지 않게 한다. 기본 False — 모든 규칙을
            한 번에 실행 (기존 동작).
        profile: "generation"은 기존 전체 규칙, "import"는 원본 충실도에
            유효한 렌더 안전 규칙만 실행한다.
    """
    if profile not in RULES_BY_PROFILE:
        raise ValueError(
            f"Unknown lint profile: {profile!r}. "
            f"Expected one of {sorted(RULES_BY_PROFILE)}"
        )

    result = SlideLintResult(slide_index=slide_index)

    target_layers = layers if layers else list(_LAYER_ORDER)
    # 기존 호출자와 테스트가 lint 모듈의 ALL_RULES를 monkeypatch할 수 있으므로
    # generation 프로필은 이 공개 심볼을 계속 기준으로 삼는다.
    profile_rules = ALL_RULES if profile == "generation" else RULES_BY_PROFILE[profile]
    profile_rule_ids = {id(rule) for rule in profile_rules}

    if stop_on_layer_error:
        # 단계적 진행 — 한 layer 검사 후 error 가 있으면 다음 layer 스킵.
        for layer in _LAYER_ORDER:
            if layer not in target_layers:
                continue
            before = len(result.violations)
            layer_rules = [
                rule
                for rule in RULES_BY_LAYER.get(layer, [])
                if id(rule) in profile_rule_ids
            ]
            _run_rules(layer_rules, spec, slide_index, result)
            new_violations = result.violations[before:]
            if any(v.severity == "error" for v in new_violations):
                logger.info(
                    "slide[%d] layer=%s 에 error %d 건 발견 → 이후 layer 스킵",
                    slide_index,
                    layer,
                    sum(1 for v in new_violations if v.severity == "error"),
                )
                break
    else:
        # 일괄 실행 — 모든 규칙 호출.
        if layers:
            rules = [
                rule
                for layer in target_layers
                for rule in RULES_BY_LAYER.get(layer, [])
                if id(rule) in profile_rule_ids
            ]
        else:
            rules = profile_rules
        _run_rules(rules, spec, slide_index, result)

    # rule 결과에 layer 메타 자동 부여 (rule 파일 자체는 layer 모름).
    annotated: list[LintViolation] = [
        replace(v, layer=layer_for_rule(v.rule)) for v in result.violations
    ]
    if layers:
        annotated = [v for v in annotated if v.layer in layers]
    result.violations[:] = annotated
    return result


def lint_design_spec(
    specs: list[PptxSlideSpec],
    layers: list[str] | None = None,
    stop_on_layer_error: bool = False,
    profile: str = "generation",
) -> LintResult:
    """전체 슬라이드에 대해 lint를 실행한다.

    Args:
        specs: 슬라이드 spec 리스트
        layers: layer 필터 (lint_slide_spec 와 동일)
        stop_on_layer_error: 단계적 layer 검사 (lint_slide_spec 와 동일)
        profile: lint 규칙 프로필 (lint_slide_spec 와 동일)

    Returns:
        LintResult: 슬라이드별 위반 리포트 + 기계적 정리가 적용된 spec 리스트
    """
    result = LintResult()
    for idx, spec in enumerate(specs):
        slide_result = lint_slide_spec(
            spec,
            slide_index=idx + 1,
            layers=layers,
            stop_on_layer_error=stop_on_layer_error,
            profile=profile,
        )
        result.slides.append(slide_result)
        result.cleaned_specs.append(_clean_spec(spec))
    return result


def clean_slide_spec(spec: PptxSlideSpec) -> PptxSlideSpec:
    """기계적 정리만 적용한다 (빈 textbox 제거). 디자인 변경 없음."""
    return _clean_spec(spec)


def _clean_spec(spec: PptxSlideSpec) -> PptxSlideSpec:
    """빈 텍스트박스를 제거한다.

    결정 7: 정리 의도가 들어간 필드(textboxes)만 변경하고 5단 계층 필드
    (grid_plan, design_doc 등) 는 무손실로 통과시킨다. 새 필드 추가 시 누락
    위험이 없도록 dataclass.replace() 를 사용한다.
    """
    cleaned_tbs: list[PptxTextBox] = []
    for tb in spec.textboxes:
        has_text = any(run.text.strip() for para in tb.paragraphs for run in para.runs)
        if has_text:
            cleaned_tbs.append(tb)
    return replace(spec, textboxes=cleaned_tbs)
