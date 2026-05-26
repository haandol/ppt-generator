"""tests/lint/ 공용 데이터 빌더.

ADR-0049 5단 계층(layout/section/content/cross/meta)으로 분리된 lint
테스트들이 공유한다. fixture 가 아닌 일반 함수로 두고 각 테스트 파일에서
직접 import 한다 (`tests/` 는 pytest rootdir 에 의해 sys.path 에 들어와
있어 `from lint._lint_helpers import ...` 가능).
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import (
    DesignDoc,
    GridCell,
    GridPlan,
    LayoutNode,
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)


def minimal_content_grid_plan() -> GridPlan:
    """content 슬라이드용 최소 grid_plan: header + content 1열 1행."""
    return GridPlan(
        regions=["header", "content"],
        content_columns=1,
        content_rows=1,
        cells=[
            GridCell(id="h1", region="header", row=1, col=1, role="title"),
            GridCell(id="c1", region="content", row=1, col=1, role="body"),
        ],
    )


def tb(text: str, font: int = 18, **kw) -> PptxTextBox:
    """간이 textbox helper."""
    defaults = dict(left_px=64, top_px=64, width_px=500, height_px=50)
    defaults.update(kw)
    return PptxTextBox(
        paragraphs=[PptxParagraph(runs=[PptxTextRun(text=text, font_size_pt=font)])],
        **defaults,
    )


def slide(
    textboxes: list[PptxTextBox] | None = None,
    shapes: list[PptxShape] | None = None,
    slide_type: str = "content",
    grid_plan: GridPlan | None = None,
) -> PptxSlideSpec:
    """간이 슬라이드 spec helper."""
    return PptxSlideSpec(
        background_color="#1a1a2e",
        textboxes=textboxes or [],
        shapes=shapes or [],
        slide_type=slide_type,
        grid_plan=grid_plan,
    )


def slide_with_design_doc(layout: list[LayoutNode]) -> PptxSlideSpec:
    """design_doc.layout 트리만 채운 content 슬라이드 spec."""
    return PptxSlideSpec(
        background_color="#1a1a2e",
        slide_type="content",
        design_doc=DesignDoc(topic="t", layout_summary="ls", layout=layout),
    )
