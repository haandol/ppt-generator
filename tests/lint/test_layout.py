"""Layout layer lint 테스트.

grid_plan(거시 격자) 단계의 lint:
- grid-plan-required, grid-cell-coverage, grid-cell-uniformity, region-stacking

여기서는 lint_design_spec / lint_slide_spec 의 layout layer 동작을 검증한다.
세부 grid 규칙별 케이스는 tests/test_grid_lint.py 에서 다룬다.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.interfaces.spec_utils import lint_design_spec, lint_slide_spec
from lint._lint_helpers import minimal_content_grid_plan, slide, tb


class TestLintDesignSpec:
    """layout layer 가 lint_design_spec 결과에 합쳐지는지 확인."""

    def test_all_pass(self) -> None:
        slides = [
            slide(
                textboxes=[
                    tb("제목1", font=28, grid_cell="h1"),
                    tb("body", font=18, top_px=200, grid_cell="c1"),
                ],
                grid_plan=minimal_content_grid_plan(),
            ),
            slide(
                textboxes=[
                    tb("제목2", font=26, grid_cell="h1"),
                    tb("body", font=18, top_px=200, grid_cell="c1"),
                ],
                grid_plan=minimal_content_grid_plan(),
            ),
        ]
        result = lint_design_spec(slides)
        assert not result.has_violations
        assert result.total_violations == 0
        assert len(result.cleaned_specs) == 2

    def test_mixed_violations(self) -> None:
        ok_slide = slide(
            textboxes=[
                tb("OK 제목", font=28, grid_cell="h1"),
                tb("body", font=18, top_px=200, grid_cell="c1"),
            ],
            grid_plan=minimal_content_grid_plan(),
        )
        bad_slide = slide(
            textboxes=[
                tb("작은 제목", font=16, grid_cell="h1"),
                tb("body", font=18, top_px=200, grid_cell="c1"),
            ],
            grid_plan=minimal_content_grid_plan(),
        )
        result = lint_design_spec([ok_slide, bad_slide])
        assert result.has_violations
        assert result.total_violations >= 1
        assert not result.slides[0].has_violations
        assert result.slides[1].has_violations

    def test_to_dict_format(self) -> None:
        slides = [slide(textboxes=[tb("작은 제목", font=16)])]
        d = lint_design_spec(slides).to_dict()
        assert d["total_slides"] == 1
        assert d["total_violations"] >= 1
        assert d["failed_slides"] == 1
        assert d["passed_slides"] == 0
        assert len(d["per_slide"]) == 1
        slide_d = d["per_slide"][0]
        assert slide_d["slide_index"] == 1
        assert slide_d["status"] == "fail"
        assert "violations" in slide_d

    def test_pass_slide_not_in_per_slide(self) -> None:
        slides = [
            slide(
                textboxes=[
                    tb("OK 제목", font=28, grid_cell="h1"),
                    tb("body", font=18, top_px=200, grid_cell="c1"),
                ],
                grid_plan=minimal_content_grid_plan(),
            ),
        ]
        d = lint_design_spec(slides).to_dict()
        assert len(d["per_slide"]) == 0


class TestLayoutLayerFilter:
    """layer 필터로 layout 위반만 추출."""

    def _slide_with_layout_and_content_violations(self) -> PptxSlideSpec:
        # title font 16pt < 24pt → content / grid_plan=None & content slide → layout
        return PptxSlideSpec(
            background_color="#1a1a2e",
            slide_type="content",
            textboxes=[tb("제목", font=16)],
            shapes=[],
            grid_plan=None,
        )

    def test_filter_layout_only(self) -> None:
        spec = self._slide_with_layout_and_content_violations()
        result = lint_slide_spec(spec, layers=["layout"])
        assert {v.layer for v in result.violations} == {"layout"}

    def test_default_includes_layout(self) -> None:
        spec = self._slide_with_layout_and_content_violations()
        layers = {v.layer for v in lint_slide_spec(spec).violations}
        assert "layout" in layers
