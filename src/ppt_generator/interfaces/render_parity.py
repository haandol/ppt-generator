"""HTML/PPTX 렌더 필드의 책임 분류 계약."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ppt_generator.interfaces.schemas import (
    DesignDoc,
    DesignSpec,
    GridCell,
    GridPlan,
    LayoutNode,
    PptxImage,
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)


class RenderFieldKind(StrEnum):
    """디자인 스펙 필드가 어느 렌더 출력에 책임을 갖는지 나타낸다."""

    SHARED = "shared"
    HTML_ONLY = "html_only"
    PPTX_ONLY = "pptx_only"
    METADATA = "metadata"


@dataclass(frozen=True)
class RenderFieldPolicy:
    """렌더 필드 하나의 출력 책임과 비공유 사유."""

    kind: RenderFieldKind
    rationale: str = ""


def _shared(*names: str) -> dict[str, RenderFieldPolicy]:
    return {name: RenderFieldPolicy(RenderFieldKind.SHARED) for name in names}


def _scoped(
    kind: RenderFieldKind,
    rationale: str,
    *names: str,
) -> dict[str, RenderFieldPolicy]:
    return {name: RenderFieldPolicy(kind, rationale) for name in names}


RENDER_FIELD_POLICIES: dict[type, dict[str, RenderFieldPolicy]] = {
    DesignSpec: {
        **_shared("slides"),
    },
    PptxSlideSpec: {
        **_shared(
            "background_color",
            "textboxes",
            "shapes",
            "images",
            "speaker_notes",
            "slide_type",
        ),
        **_scoped(
            RenderFieldKind.PPTX_ONLY,
            "PPTX 패키지에 직접 삽입하는 인메모리 배경 이미지 바이트다.",
            "background_image_bytes",
        ),
        **_scoped(
            RenderFieldKind.HTML_ONLY,
            "HTML 문서가 참조하는 프로젝트 상대 배경 이미지 경로다.",
            "background_image_src",
        ),
        **_scoped(
            RenderFieldKind.METADATA,
            "레이아웃 lint와 부분 수정에 쓰이며 출력 픽셀을 직접 결정하지 않는다.",
            "grid_plan",
            "design_doc",
        ),
    },
    PptxTextRun: {
        **_shared(
            "text",
            "font_size_pt",
            "color",
            "bold",
            "italic",
            "font_family",
            "href",
            "font_name",
        ),
    },
    PptxParagraph: {
        **_shared(
            "runs",
            "bullet_level",
            "alignment",
            "space_before_pt",
            "space_after_pt",
        ),
    },
    PptxTextBox: {
        **_shared(
            "left_px",
            "top_px",
            "width_px",
            "height_px",
            "paragraphs",
            "line_spacing_pt",
            "vertical_alignment",
            "padding_left_px",
            "padding_right_px",
            "padding_top_px",
            "padding_bottom_px",
            "autofit",
            "autofit_font_scale",
            "z_index",
        ),
        **_scoped(
            RenderFieldKind.PPTX_ONLY,
            "HTML용 기본 행간 근사값을 PPTX 문단별 폰트 크기로 정규화하는 표식이다.",
            "line_spacing_is_default",
        ),
        **_scoped(
            RenderFieldKind.METADATA,
            "그리드 lint와 의미 단위 부분 수정에 쓰이는 연결 정보다.",
            "grid_cell",
            "component_id",
        ),
    },
    PptxShape: {
        **_shared(
            "left_px",
            "top_px",
            "width_px",
            "height_px",
            "shape_type",
            "fill_color",
            "border_color",
            "border_width_pt",
            "corner_radius_px",
            "text",
            "text_color",
            "text_size_pt",
            "text_bold",
            "paragraphs",
            "line_spacing_pt",
            "padding_left_px",
            "padding_right_px",
            "padding_top_px",
            "padding_bottom_px",
            "vertical_alignment",
            "end_arrow",
            "start_arrow",
            "dash_style",
            "svg_path",
            "elbow_points",
            "autofit_mode",
            "z_index",
            "rotation",
        ),
        **_scoped(
            RenderFieldKind.PPTX_ONLY,
            "HTML용 기본 행간 근사값을 PPTX 문단별 폰트 크기로 정규화하는 표식이다.",
            "line_spacing_is_default",
        ),
        **_scoped(
            RenderFieldKind.METADATA,
            "그리드 lint와 의미 단위 부분 수정에 쓰이는 연결 정보다.",
            "grid_cell",
            "component_id",
        ),
    },
    PptxImage: {
        **_shared(
            "left_px",
            "top_px",
            "width_px",
            "height_px",
            "corner_radius_px",
            "z_index",
        ),
        **_scoped(
            RenderFieldKind.PPTX_ONLY,
            "PPTX 패키지에 직접 삽입하는 인메모리 이미지 바이트다.",
            "image_bytes",
        ),
        **_scoped(
            RenderFieldKind.HTML_ONLY,
            "HTML 문서가 참조하는 프로젝트 상대 이미지 경로다.",
            "src",
        ),
        **_scoped(
            RenderFieldKind.METADATA,
            "프로젝트 저장 단계에서 출력별 이미지 표현으로 변환되는 원본 위치다.",
            "image_path",
        ),
        **_scoped(
            RenderFieldKind.METADATA,
            "그리드 lint에 쓰이며 출력 픽셀을 직접 결정하지 않는다.",
            "grid_cell",
        ),
    },
    GridCell: {
        **_scoped(
            RenderFieldKind.METADATA,
            "레이아웃 lint와 디자인 수정의 추상 그리드 정보다.",
            "id",
            "region",
            "row",
            "col",
            "row_span",
            "col_span",
            "role",
        ),
    },
    GridPlan: {
        **_scoped(
            RenderFieldKind.METADATA,
            "레이아웃 lint와 디자인 수정의 추상 그리드 정보다.",
            "regions",
            "content_columns",
            "content_rows",
            "cells",
        ),
    },
    LayoutNode: {
        **_scoped(
            RenderFieldKind.METADATA,
            "부분 수정과 계층 lint를 위한 의미 레이아웃 트리다.",
            "id",
            "kind",
            "role",
            "description",
            "cell_id",
            "left_px",
            "top_px",
            "width_px",
            "height_px",
            "children",
        ),
    },
    DesignDoc: {
        **_scoped(
            RenderFieldKind.METADATA,
            "디자인 의도와 부분 수정 컨텍스트이며 렌더러 입력 요소가 아니다.",
            "topic",
            "layout_summary",
            "layout",
        ),
    },
}
