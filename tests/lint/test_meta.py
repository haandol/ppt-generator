"""lint 메타 동작 테스트.

- clean_slide_spec (빈 textbox 제거 + 5단 계층 무손실 보존)
- lint 가 spec 을 수정하지 않는지 (No modification)
- lint_slide_spec(layers=[...]) 필터 + by_layer 출력
- RULE_LAYER_MAP 전수 분류 (결정 8)
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import (
    DesignDoc,
    LayoutNode,
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.interfaces.spec_utils import (
    clean_slide_spec,
    lint_design_spec,
    lint_slide_spec,
)
from lint._lint_helpers import minimal_content_grid_plan, slide, tb


# ---------------------------------------------------------------------------
# clean_slide_spec — 빈 textbox 제거
# ---------------------------------------------------------------------------


class TestCleanSpec:
    def test_empty_textbox_removed(self) -> None:
        empty_tb = PptxTextBox(
            left_px=64,
            top_px=64,
            width_px=500,
            height_px=50,
            paragraphs=[PptxParagraph(runs=[PptxTextRun(text="")])],
        )
        text_tb = tb("유효 텍스트", font=18, top_px=200)
        result = clean_slide_spec(slide(textboxes=[empty_tb, text_tb]))
        assert len(result.textboxes) == 1
        assert result.textboxes[0].paragraphs[0].runs[0].text == "유효 텍스트"

    def test_whitespace_only_textbox_removed(self) -> None:
        ws_tb = PptxTextBox(
            left_px=64,
            top_px=64,
            width_px=500,
            height_px=50,
            paragraphs=[PptxParagraph(runs=[PptxTextRun(text=" ")])],
        )
        result = clean_slide_spec(slide(textboxes=[ws_tb]))
        assert len(result.textboxes) == 0

    def test_valid_textbox_preserved(self) -> None:
        result = clean_slide_spec(slide(textboxes=[tb("유효 텍스트", font=18)]))
        assert len(result.textboxes) == 1

    def test_shapes_not_affected(self) -> None:
        shape = PptxShape(
            left_px=64,
            top_px=148,
            width_px=400,
            height_px=200,
            shape_type="rounded_rectangle",
            fill_color="#2E3D50",
            text="카드 본문",
            text_size_pt=12,
        )
        result = clean_slide_spec(slide(shapes=[shape]))
        assert len(result.shapes) == 1
        assert result.shapes[0].text_size_pt == 12


# ---------------------------------------------------------------------------
# 레이아웃/색상 비개입 — lint 와 clean 모두 위치/색상을 바꾸지 않는다
# ---------------------------------------------------------------------------


class TestNoModification:
    def test_position_preserved(self) -> None:
        tb_ = PptxTextBox(
            left_px=100,
            top_px=100,
            width_px=1000,
            height_px=60,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="제목", font_size_pt=32, bold=True)]
                )
            ],
        )
        result = clean_slide_spec(slide(textboxes=[tb_]))
        assert result.textboxes[0].left_px == 100
        assert result.textboxes[0].top_px == 100

    def test_color_preserved(self) -> None:
        tb_ = PptxTextBox(
            left_px=64,
            top_px=64,
            width_px=500,
            height_px=50,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="테스트", font_size_pt=18, color="#222222")]
                )
            ],
        )
        result = clean_slide_spec(
            PptxSlideSpec(background_color="#1a1a2e", textboxes=[tb_])
        )
        assert result.textboxes[0].paragraphs[0].runs[0].color == "#222222"

    def test_padding_preserved(self) -> None:
        tb_ = PptxTextBox(
            left_px=64,
            top_px=200,
            width_px=500,
            height_px=100,
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="테스트", font_size_pt=18)])
            ],
            padding_left_px=16,
            padding_right_px=16,
            padding_top_px=12,
            padding_bottom_px=12,
        )
        result = clean_slide_spec(slide(textboxes=[tb_]))
        v = result.textboxes[0]
        assert v.padding_left_px == 16
        assert v.padding_right_px == 16
        assert v.padding_top_px == 12
        assert v.padding_bottom_px == 12

    def test_vertical_alignment_preserved(self) -> None:
        tb_ = PptxTextBox(
            left_px=64,
            top_px=180,
            width_px=1152,
            height_px=480,
            vertical_alignment="top",
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="짧은 본문", font_size_pt=20)],
                    bullet_level=0,
                )
            ],
        )
        result = clean_slide_spec(slide(textboxes=[tb_]))
        assert result.textboxes[0].vertical_alignment == "top"

    def test_shape_position_preserved(self) -> None:
        shape = PptxShape(
            left_px=0,
            top_px=100,
            width_px=1280,
            height_px=3,
            shape_type="rectangle",
            fill_color="#FF9900",
        )
        result = clean_slide_spec(slide(shapes=[shape]))
        assert result.shapes[0].left_px == 0
        assert result.shapes[0].height_px == 3
        assert result.shapes[0].width_px == 1280

    def test_shape_gap_preserved(self) -> None:
        s1 = PptxShape(
            left_px=100,
            top_px=100,
            width_px=200,
            height_px=50,
            shape_type="rectangle",
            text="A",
            text_size_pt=16,
        )
        s2 = PptxShape(
            left_px=100,
            top_px=153,
            width_px=200,
            height_px=50,
            shape_type="rectangle",
            text="B",
            text_size_pt=16,
        )
        result = clean_slide_spec(
            PptxSlideSpec(background_color="#FFFFFF", shapes=[s1, s2])
        )
        assert result.shapes[0].top_px == s1.top_px
        assert result.shapes[1].top_px == s2.top_px


# ---------------------------------------------------------------------------
# lint_design_spec — cleaned_specs 반환
# ---------------------------------------------------------------------------


class TestCleanedSpecsReturned:
    def test_cleaned_specs_returned(self) -> None:
        empty_tb = PptxTextBox(
            left_px=64,
            top_px=64,
            width_px=500,
            height_px=50,
            paragraphs=[PptxParagraph(runs=[PptxTextRun(text="")])],
        )
        text_tb = tb("유효 텍스트", font=24, top_px=200)
        result = lint_design_spec([slide(textboxes=[empty_tb, text_tb])])
        assert len(result.cleaned_specs[0].textboxes) == 1


# ---------------------------------------------------------------------------
# layer 필터 종합 + by_layer 출력
# ---------------------------------------------------------------------------


class TestLayerFiltering:
    """5단 계층 단계적 lint 호출 시 layer 별 위반만 반환."""

    def _spec(self) -> PptxSlideSpec:
        # title font 16pt < 24pt → content 위반
        # grid_plan=None & content slide → layout 위반
        return PptxSlideSpec(
            background_color="#1a1a2e",
            slide_type="content",
            textboxes=[tb("제목", font=16)],
            shapes=[],
            grid_plan=None,
        )

    def test_default_returns_all_layers(self) -> None:
        layers = {v.layer for v in lint_slide_spec(self._spec()).violations}
        assert "content" in layers
        assert "layout" in layers

    def test_to_dict_contains_by_layer(self) -> None:
        d = lint_slide_spec(self._spec()).to_dict()
        assert "by_layer" in d
        assert d["by_layer"].get("layout", 0) >= 1
        assert d["by_layer"].get("content", 0) >= 1


# ---------------------------------------------------------------------------
# 결정 7 — clean_slide_spec 5단 계층 무손실
# ---------------------------------------------------------------------------


class TestCleanSpecPreservesFiveLayer:
    """clean_slide_spec 가 grid_plan / design_doc / images / slide_type / 배경 메타를 보존."""

    def _full_spec(self) -> PptxSlideSpec:
        layout = [
            LayoutNode(
                id="s1",
                kind="section",
                role="hero",
                description="hero section",
                cell_id="c1",
                left_px=64,
                top_px=148,
                width_px=1152,
                height_px=400,
            )
        ]
        return PptxSlideSpec(
            background_color="#0F172A",
            background_image_bytes=b"\x89PNG\r\n",
            background_image_src="images/slide_01_bg.png",
            textboxes=[tb("real", font=20)],
            shapes=[],
            speaker_notes="narrator",
            slide_type="content",
            grid_plan=minimal_content_grid_plan(),
            design_doc=DesignDoc(topic="t", layout_summary="ls", layout=layout),
        )

    def test_grid_plan_preserved(self) -> None:
        spec = self._full_spec()
        cleaned = clean_slide_spec(spec)
        assert cleaned.grid_plan is not None
        assert cleaned.grid_plan == spec.grid_plan

    def test_design_doc_preserved(self) -> None:
        spec = self._full_spec()
        cleaned = clean_slide_spec(spec)
        assert cleaned.design_doc is not None
        assert cleaned.design_doc.topic == "t"
        assert len(cleaned.design_doc.layout) == 1
        assert cleaned.design_doc.layout[0].id == "s1"

    def test_images_and_bg_preserved(self) -> None:
        from ppt_generator.interfaces.schemas import PptxImage

        spec = self._full_spec()
        spec_with_img = PptxSlideSpec(
            background_color=spec.background_color,
            background_image_bytes=spec.background_image_bytes,
            background_image_src=spec.background_image_src,
            textboxes=spec.textboxes,
            shapes=spec.shapes,
            images=[
                PptxImage(
                    left_px=10,
                    top_px=10,
                    width_px=100,
                    height_px=100,
                    src="images/x.png",
                )
            ],
            speaker_notes=spec.speaker_notes,
            slide_type=spec.slide_type,
            grid_plan=spec.grid_plan,
            design_doc=spec.design_doc,
        )
        cleaned = clean_slide_spec(spec_with_img)
        assert len(cleaned.images) == 1
        assert cleaned.images[0].src == "images/x.png"
        assert cleaned.background_image_bytes == b"\x89PNG\r\n"
        assert cleaned.background_image_src == "images/slide_01_bg.png"

    def test_slide_type_preserved(self) -> None:
        cleaned = clean_slide_spec(self._full_spec())
        assert cleaned.slide_type == "content"

    def test_empty_textboxes_removed_but_others_intact(self) -> None:
        spec = PptxSlideSpec(
            background_color="#0F172A",
            textboxes=[
                tb("keep", font=20),
                PptxTextBox(
                    left_px=0,
                    top_px=0,
                    width_px=10,
                    height_px=10,
                    paragraphs=[PptxParagraph(runs=[PptxTextRun(text=" ")])],
                ),
            ],
            shapes=[],
            slide_type="content",
            grid_plan=minimal_content_grid_plan(),
            design_doc=DesignDoc(topic="t", layout_summary="ls", layout=[]),
        )
        cleaned = clean_slide_spec(spec)
        assert len(cleaned.textboxes) == 1
        assert cleaned.grid_plan is not None
        assert cleaned.design_doc is not None


# ---------------------------------------------------------------------------
# 결정 8 — RULE_LAYER_MAP 전수 분류
# ---------------------------------------------------------------------------


class TestRuleLayerMapCoverage:
    """lint_rules/ 의 모든 rule id 가 RULE_LAYER_MAP 에 등록되어 있는지 검증."""

    def _all_rule_ids(self) -> set[str]:
        import re
        from pathlib import Path

        import ppt_generator.interfaces.spec_utils.lint_rules as pkg

        rules_dir = Path(pkg.__file__).parent
        ids: set[str] = set()
        pattern = re.compile(r'rule="([a-z][a-z0-9-]+)"')
        for py in rules_dir.glob("*.py"):
            if py.name == "__init__.py":
                continue
            for m in pattern.finditer(py.read_text(encoding="utf-8")):
                ids.add(m.group(1))
        return ids

    def test_all_rules_classified(self) -> None:
        from ppt_generator.interfaces.spec_utils.lint_types import RULE_LAYER_MAP

        rule_ids = self._all_rule_ids()
        unmapped = rule_ids - set(RULE_LAYER_MAP.keys())
        assert not unmapped, (
            f"RULE_LAYER_MAP 에 등록 안 된 lint rule: {sorted(unmapped)} — "
            "결정 8 위반. lint_types.RULE_LAYER_MAP 에 분류 추가 필요."
        )

    def test_layer_values_are_valid(self) -> None:
        from ppt_generator.interfaces.spec_utils.lint_types import RULE_LAYER_MAP

        valid = {"layout", "section", "content", "cross"}
        bad = {r: lyr for r, lyr in RULE_LAYER_MAP.items() if lyr not in valid}
        assert not bad, f"허용되지 않는 layer 값: {bad}"
